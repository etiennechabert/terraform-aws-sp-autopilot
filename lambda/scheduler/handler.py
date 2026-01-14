"""
Scheduler Lambda - Analyzes usage and queues Savings Plan purchase intents.

Supports both Compute Savings Plans and Database Savings Plans.

This Lambda:
1. Purges existing queue messages
2. Calculates current coverage (excluding plans expiring within renewal_window_days)
3. Gets AWS purchase recommendations
4. Calculates purchase need based on coverage_target_percent
5. Applies max_purchase_percent limit
6. Splits commitment by term mix (for Compute SP) or applies Database SP term
7. Queues purchase intents (or sends email only if dry_run=true)
8. Sends notification email with analysis results
"""

import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional

from botocore.exceptions import ClientError

from shared import notifications
from shared.handler_utils import (
    load_config_from_env,
    initialize_clients,
    lambda_handler_wrapper,
    send_error_notification
)

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)


@lambda_handler_wrapper('Scheduler')
def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Main handler for Scheduler Lambda.

    Args:
        event: EventBridge scheduled event
        context: Lambda context

    Returns:
        dict: Status and summary of analysis

    Raises:
        Exception: All errors are raised (no silent failures)
    """
    try:
        # Load configuration from environment
        config = load_config_from_env(CONFIG_SCHEMA)

        # Create error callback function
        def send_error_email(error_msg: str) -> None:
            """Send error notification using shared utility."""
            # Get SNS client directly (before full client initialization)
            import boto3
            sns = boto3.client('sns')
            send_error_notification(
                sns_client=sns,
                sns_topic_arn=config['sns_topic_arn'],
                error_message=error_msg,
                lambda_name='Scheduler'
            )

        # Initialize clients (with assume role if configured)
        clients = initialize_clients(config, 'sp-autopilot-scheduler', send_error_email)
        ce_client = clients['ce']
        savingsplans_client = clients['savingsplans']
        sqs_client = clients['sqs']
        sns_client = clients['sns']

        logger.info(f"Configuration loaded: dry_run={config['dry_run']}")

        # Step 1: Purge existing queue
        purge_queue(sqs_client, config['queue_url'])

        # Step 2: Calculate current coverage
        coverage = calculate_current_coverage(savingsplans_client, ce_client, config)
        logger.info(f"Current coverage - Compute: {coverage.get('compute', 0)}%, Database: {coverage.get('database', 0)}%, SageMaker: {coverage.get('sagemaker', 0)}%")

        # Step 3: Get AWS recommendations
        recommendations = get_aws_recommendations(ce_client, config)

        # Step 4: Calculate purchase need
        purchase_plans = calculate_purchase_need(config, coverage, recommendations)

        # Step 5: Apply purchase limits
        purchase_plans = apply_purchase_limits(config, purchase_plans)

        # Step 6: Split by term (for Compute SP)
        purchase_plans = split_by_term(config, purchase_plans)

        # Step 7: Queue or notify
        if config['dry_run']:
            logger.info("Dry run mode - sending email only, NOT queuing messages")
            send_dry_run_email(sns_client, config, purchase_plans, coverage)
        else:
            logger.info("Queuing purchase intents to SQS")
            queue_purchase_intents(sqs_client, config, purchase_plans)
            send_scheduled_email(sns_client, config, purchase_plans, coverage)

        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Scheduler completed successfully',
                'dry_run': config['dry_run'],
                'purchases_planned': len(purchase_plans)
            })
        }

    except Exception as e:
        # Try to send error notification
        try:
            config = load_config_from_env(CONFIG_SCHEMA)
            import boto3
            sns = boto3.client('sns')
            send_error_notification(
                sns_client=sns,
                sns_topic_arn=config['sns_topic_arn'],
                error_message=str(e),
                lambda_name='Scheduler'
            )
        except Exception as notification_error:
            logger.warning(f"Failed to send error notification: {notification_error}")
        raise  # Re-raise to ensure Lambda fails visibly


# Configuration schema for environment variable loading
CONFIG_SCHEMA = {
    'queue_url': {
        'required': True,
        'type': 'str',
        'env_var': 'QUEUE_URL'
    },
    'sns_topic_arn': {
        'required': True,
        'type': 'str',
        'env_var': 'SNS_TOPIC_ARN'
    },
    'dry_run': {
        'required': False,
        'type': 'bool',
        'default': 'true',
        'env_var': 'DRY_RUN'
    },
    'enable_compute_sp': {
        'required': False,
        'type': 'bool',
        'default': 'true',
        'env_var': 'ENABLE_COMPUTE_SP'
    },
    'enable_database_sp': {
        'required': False,
        'type': 'bool',
        'default': 'false',
        'env_var': 'ENABLE_DATABASE_SP'
    },
    'enable_sagemaker_sp': {
        'required': False,
        'type': 'bool',
        'default': 'false',
        'env_var': 'ENABLE_SAGEMAKER_SP'
    },
    'coverage_target_percent': {
        'required': False,
        'type': 'float',
        'default': '90',
        'env_var': 'COVERAGE_TARGET_PERCENT'
    },
    'max_purchase_percent': {
        'required': False,
        'type': 'float',
        'default': '10',
        'env_var': 'MAX_PURCHASE_PERCENT'
    },
    'renewal_window_days': {
        'required': False,
        'type': 'int',
        'default': '7',
        'env_var': 'RENEWAL_WINDOW_DAYS'
    },
    'lookback_days': {
        'required': False,
        'type': 'int',
        'default': '30',
        'env_var': 'LOOKBACK_DAYS'
    },
    'min_data_days': {
        'required': False,
        'type': 'int',
        'default': '14',
        'env_var': 'MIN_DATA_DAYS'
    },
    'min_commitment_per_plan': {
        'required': False,
        'type': 'float',
        'default': '0.001',
        'env_var': 'MIN_COMMITMENT_PER_PLAN'
    },
    'compute_sp_term_mix': {
        'required': False,
        'type': 'json',
        'default': '{"three_year": 0.67, "one_year": 0.33}',
        'env_var': 'COMPUTE_SP_TERM_MIX'
    },
    'compute_sp_payment_option': {
        'required': False,
        'type': 'str',
        'default': 'ALL_UPFRONT',
        'env_var': 'COMPUTE_SP_PAYMENT_OPTION'
    },
    'sagemaker_sp_term_mix': {
        'required': False,
        'type': 'json',
        'default': '{"three_year": 0.67, "one_year": 0.33}',
        'env_var': 'SAGEMAKER_SP_TERM_MIX'
    },
    'sagemaker_sp_payment_option': {
        'required': False,
        'type': 'str',
        'default': 'ALL_UPFRONT',
        'env_var': 'SAGEMAKER_SP_PAYMENT_OPTION'
    },
    'partial_upfront_percent': {
        'required': False,
        'type': 'float',
        'default': '50',
        'env_var': 'PARTIAL_UPFRONT_PERCENT'
    },
    'management_account_role_arn': {
        'required': False,
        'type': 'str',
        'env_var': 'MANAGEMENT_ACCOUNT_ROLE_ARN'
    },
    'tags': {
        'required': False,
        'type': 'json',
        'default': '{}',
        'env_var': 'TAGS'
    }
}


def purge_queue(sqs_client: Any, queue_url: str) -> None:
    """
    Purge all existing messages from the SQS queue.

    Args:
        sqs_client: Boto3 SQS client
        queue_url: SQS queue URL
    """
    logger.info(f"Purging queue: {queue_url}")
    try:
        sqs_client.purge_queue(QueueUrl=queue_url)
        logger.info("Queue purged successfully")
    except ClientError as e:
        if e.response['Error']['Code'] == 'PurgeQueueInProgress':
            logger.warning("Queue purge already in progress")
        else:
            raise


def calculate_current_coverage(savingsplans_client: Any, ce_client: Any, config: Dict[str, Any]) -> Dict[str, float]:
    """
    Calculate current Savings Plans coverage, excluding plans expiring soon.

    Args:
        savingsplans_client: Boto3 Savings Plans client
        ce_client: Boto3 Cost Explorer client
        config: Configuration dictionary

    Returns:
        dict: Coverage percentages by SP type
    """
    logger.info("Calculating current coverage")

    # Get current date for expiration filtering
    now = datetime.now(timezone.utc)
    renewal_window_days = config['renewal_window_days']

    # Get list of existing Savings Plans
    try:
        response = savingsplans_client.describe_savings_plans(
            filters=[
                {
                    'name': 'state',
                    'values': ['active']
                }
            ]
        )
        savings_plans = response.get('savingsPlans', [])
        logger.info(f"Found {len(savings_plans)} active Savings Plans")

        # Filter out plans expiring within renewal_window_days
        valid_plan_ids = []
        for plan in savings_plans:
            if 'end' in plan:
                # Parse end date (ISO 8601 format)
                end_date = datetime.fromisoformat(plan['end'].replace('Z', '+00:00'))
                days_until_expiry = (end_date - now).days

                if days_until_expiry > renewal_window_days:
                    valid_plan_ids.append(plan['savingsPlanId'])
                    logger.debug(f"Including plan {plan['savingsPlanId']} - expires in {days_until_expiry} days")
                else:
                    logger.info(f"Excluding plan {plan['savingsPlanId']} - expires in {days_until_expiry} days (within renewal window)")

        logger.info(f"Valid plans after filtering: {len(valid_plan_ids)}")

    except ClientError as e:
        logger.error(f"Failed to describe Savings Plans: {str(e)}")
        raise

    # Get coverage from Cost Explorer
    try:
        # Get coverage for the last 1 day (most recent data point)
        from datetime import timedelta
        end_date = now.date()
        start_date = end_date - timedelta(days=1)

        response = ce_client.get_savings_plans_coverage(
            TimePeriod={
                'Start': start_date.isoformat(),
                'End': end_date.isoformat()
            },
            Granularity='DAILY'
        )

        coverage_by_time = response.get('SavingsPlansCoverages', [])

        if not coverage_by_time:
            logger.warning("No coverage data available from Cost Explorer")
            return {
                'compute': 0.0,
                'database': 0.0,
                'sagemaker': 0.0
            }

        # Get the most recent coverage data point
        latest_coverage = coverage_by_time[-1]
        coverage_data = latest_coverage.get('Coverage', {})

        # Extract coverage percentage
        coverage_percentage = 0.0
        if 'CoveragePercentage' in coverage_data:
            coverage_percentage = float(coverage_data['CoveragePercentage'])

        logger.info(f"Overall Savings Plans coverage: {coverage_percentage}%")

        # Note: Cost Explorer doesn't separate coverage by SP type in the basic API call
        # For now, we'll use the overall coverage for compute and assume 0 for database and sagemaker
        # In a production system, you might need to call GetSavingsPlansCoverage with
        # GroupBy to separate by service or use DescribeSavingsPlans to categorize
        coverage = {
            'compute': coverage_percentage,
            'database': 0.0,
            'sagemaker': 0.0
        }

    except ClientError as e:
        logger.error(f"Failed to get coverage from Cost Explorer: {str(e)}")
        raise

    logger.info(f"Coverage calculated: {coverage}")
    return coverage


def _fetch_compute_sp_recommendation(ce_client: Any, config: Dict[str, Any], lookback_period: str) -> Optional[Dict[str, Any]]:
    """
    Fetch Compute Savings Plan recommendation from AWS Cost Explorer.

    This function is designed to be executed in parallel with other recommendation
    fetches using ThreadPoolExecutor. It makes a synchronous API call to AWS Cost
    Explorer's GetSavingsPlansPurchaseRecommendation API.

    Args:
        ce_client: Boto3 Cost Explorer client
        config: Configuration dictionary
        lookback_period: AWS API lookback period value

    Returns:
        dict: Compute SP recommendation or None

    Raises:
        ClientError: If the Cost Explorer API call fails
    """
    logger.info("Fetching Compute Savings Plan recommendations")
    try:
        response = ce_client.get_savings_plans_purchase_recommendation(
            SavingsPlansType='COMPUTE_SP',
            LookbackPeriodInDays=lookback_period,
            TermInYears='ONE_YEAR',
            PaymentOption='ALL_UPFRONT'
        )

        # Extract recommendation metadata
        metadata = response.get('Metadata', {})
        recommendation_id = metadata.get('RecommendationId', 'unknown')
        generation_timestamp = metadata.get('GenerationTimestamp', 'unknown')

        # Validate sufficient data
        lookback_period_days = metadata.get('LookbackPeriodInDays', '0')
        if lookback_period_days and int(lookback_period_days) < config['min_data_days']:
            logger.warning(
                f"Compute SP recommendation has insufficient data: "
                f"{lookback_period_days} days < {config['min_data_days']} days minimum"
            )
            return None

        # Extract recommendation details
        recommendation_details = response.get('SavingsPlansPurchaseRecommendation', {})
        recommendation_summary = recommendation_details.get('SavingsPlansPurchaseRecommendationDetails', [])

        if recommendation_summary:
            # Get the first (best) recommendation
            best_recommendation = recommendation_summary[0]
            hourly_commitment = best_recommendation.get('HourlyCommitmentToPurchase', '0')

            logger.info(
                f"Compute SP recommendation: ${hourly_commitment}/hour "
                f"(recommendation_id: {recommendation_id}, generated: {generation_timestamp})"
            )

            return {
                'HourlyCommitmentToPurchase': hourly_commitment,
                'RecommendationId': recommendation_id,
                'GenerationTimestamp': generation_timestamp,
                'Details': best_recommendation
            }
        else:
            logger.info("No Compute SP recommendations available from AWS")
            return None

    except ClientError as e:
        logger.error(f"Failed to get Compute SP recommendations: {str(e)}")
        raise


def _fetch_database_sp_recommendation(ce_client: Any, config: Dict[str, Any], lookback_period: str) -> Optional[Dict[str, Any]]:
    """
    Fetch Database Savings Plan recommendation from AWS Cost Explorer.

    This function is designed to be executed in parallel with other recommendation
    fetches using ThreadPoolExecutor. It makes a synchronous API call to AWS Cost
    Explorer's GetSavingsPlansPurchaseRecommendation API.

    Args:
        ce_client: Boto3 Cost Explorer client
        config: Configuration dictionary
        lookback_period: AWS API lookback period value

    Returns:
        dict: Database SP recommendation or None

    Raises:
        ClientError: If the Cost Explorer API call fails
    """
    logger.info("Fetching Database Savings Plan recommendations")
    try:
        # Database Savings Plans were added to AWS in December 2025
        # They use the DATABASE_SP type in the Cost Explorer API
        response = ce_client.get_savings_plans_purchase_recommendation(
            SavingsPlansType='DATABASE_SP',
            LookbackPeriodInDays=lookback_period,
            TermInYears='ONE_YEAR',
            PaymentOption='NO_UPFRONT'
        )

        # Extract recommendation metadata
        metadata = response.get('Metadata', {})
        recommendation_id = metadata.get('RecommendationId', 'unknown')
        generation_timestamp = metadata.get('GenerationTimestamp', 'unknown')

        # Validate sufficient data
        lookback_period_days = metadata.get('LookbackPeriodInDays', '0')
        if lookback_period_days and int(lookback_period_days) < config['min_data_days']:
            logger.warning(
                f"Database SP recommendation has insufficient data: "
                f"{lookback_period_days} days < {config['min_data_days']} days minimum"
            )
            return None

        # Extract recommendation details
        recommendation_details = response.get('SavingsPlansPurchaseRecommendation', {})
        recommendation_summary = recommendation_details.get('SavingsPlansPurchaseRecommendationDetails', [])

        if recommendation_summary:
            # Get the first (best) recommendation
            best_recommendation = recommendation_summary[0]
            hourly_commitment = best_recommendation.get('HourlyCommitmentToPurchase', '0')

            logger.info(
                f"Database SP recommendation: ${hourly_commitment}/hour "
                f"(recommendation_id: {recommendation_id}, generated: {generation_timestamp})"
            )

            return {
                'HourlyCommitmentToPurchase': hourly_commitment,
                'RecommendationId': recommendation_id,
                'GenerationTimestamp': generation_timestamp,
                'Details': best_recommendation
            }
        else:
            logger.info("No Database SP recommendations available from AWS")
            return None

    except ClientError as e:
        logger.error(f"Failed to get Database SP recommendations: {str(e)}")
        raise


def _fetch_sagemaker_sp_recommendation(ce_client: Any, config: Dict[str, Any], lookback_period: str) -> Optional[Dict[str, Any]]:
    """
    Fetch SageMaker Savings Plan recommendation from AWS Cost Explorer.

    This function is designed to be executed in parallel with other recommendation
    fetches using ThreadPoolExecutor. It makes a synchronous API call to AWS Cost
    Explorer's GetSavingsPlansPurchaseRecommendation API.

    Args:
        ce_client: Boto3 Cost Explorer client
        config: Configuration dictionary
        lookback_period: AWS API lookback period value

    Returns:
        dict: SageMaker SP recommendation or None

    Raises:
        ClientError: If the Cost Explorer API call fails
    """
    logger.info("Fetching SageMaker Savings Plan recommendations")
    try:
        # SageMaker Savings Plans use the SAGEMAKER_SP type in the Cost Explorer API
        response = ce_client.get_savings_plans_purchase_recommendation(
            SavingsPlansType='SAGEMAKER_SP',
            LookbackPeriodInDays=lookback_period,
            TermInYears='ONE_YEAR',
            PaymentOption='NO_UPFRONT'
        )

        # Extract recommendation metadata
        metadata = response.get('Metadata', {})
        recommendation_id = metadata.get('RecommendationId', 'unknown')
        generation_timestamp = metadata.get('GenerationTimestamp', 'unknown')

        # Validate sufficient data
        lookback_period_days = metadata.get('LookbackPeriodInDays', '0')
        if lookback_period_days and int(lookback_period_days) < config['min_data_days']:
            logger.warning(
                f"SageMaker SP recommendation has insufficient data: "
                f"{lookback_period_days} days < {config['min_data_days']} days minimum"
            )
            return None

        # Extract recommendation details
        recommendation_details = response.get('SavingsPlansPurchaseRecommendation', {})
        recommendation_summary = recommendation_details.get('SavingsPlansPurchaseRecommendationDetails', [])

        if recommendation_summary:
            # Get the first (best) recommendation
            best_recommendation = recommendation_summary[0]
            hourly_commitment = best_recommendation.get('HourlyCommitmentToPurchase', '0')

            logger.info(
                f"SageMaker SP recommendation: ${hourly_commitment}/hour "
                f"(recommendation_id: {recommendation_id}, generated: {generation_timestamp})"
            )

            return {
                'HourlyCommitmentToPurchase': hourly_commitment,
                'RecommendationId': recommendation_id,
                'GenerationTimestamp': generation_timestamp,
                'Details': best_recommendation
            }
        else:
            logger.info("No SageMaker SP recommendations available from AWS")
            return None

    except ClientError as e:
        logger.error(f"Failed to get SageMaker SP recommendations: {str(e)}")
        raise


def get_aws_recommendations(ce_client: Any, config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get Savings Plans purchase recommendations from AWS Cost Explorer.

    Uses ThreadPoolExecutor to fetch Compute and Database SP recommendations in parallel,
    reducing total execution time by making concurrent API calls to Cost Explorer. Each
    enabled SP type (Compute, Database) is fetched in its own thread, allowing multiple
    GetSavingsPlansPurchaseRecommendation API calls to execute simultaneously.

    Parallel Execution Details:
    - Creates a thread pool with max_workers equal to the number of enabled SP types
    - Submits _fetch_compute_sp_recommendation and _fetch_database_sp_recommendation
      as concurrent tasks
    - Uses as_completed() to collect results as they finish
    - If any thread raises an exception, it is re-raised immediately

    Performance: Reduces API call latency by ~50% when both SP types are enabled
    (2 sequential calls -> 2 parallel calls).

    Args:
        ce_client: Boto3 Cost Explorer client
        config: Configuration dictionary with enable_compute_sp, enable_database_sp,
                and lookback_days settings

    Returns:
        dict: Recommendations by SP type, e.g.:
              {'compute': {...}, 'database': {...}} or
              {'compute': None, 'database': None} if no recommendations available

    Raises:
        ClientError: If any Cost Explorer API call fails (propagated from worker threads)
    """
    logger.info("Getting AWS recommendations")

    recommendations = {
        'compute': None,
        'database': None,
        'sagemaker': None
    }

    # Map lookback_days to AWS API parameter value
    lookback_days = config['lookback_days']
    if lookback_days <= 7:
        lookback_period = 'SEVEN_DAYS'
    elif lookback_days <= 30:
        lookback_period = 'THIRTY_DAYS'
    else:
        lookback_period = 'SIXTY_DAYS'

    logger.info(f"Using lookback period: {lookback_period} (config: {lookback_days} days)")

    # Prepare tasks for parallel execution
    tasks = {}
    if config['enable_compute_sp']:
        tasks['compute'] = ('compute', _fetch_compute_sp_recommendation, ce_client, config, lookback_period)
    if config['enable_database_sp']:
        tasks['database'] = ('database', _fetch_database_sp_recommendation, ce_client, config, lookback_period)
    if config['enable_sagemaker_sp']:
        tasks['sagemaker'] = ('sagemaker', _fetch_sagemaker_sp_recommendation, ce_client, config, lookback_period)

    # Execute API calls in parallel using ThreadPoolExecutor
    if tasks:
        with ThreadPoolExecutor(max_workers=len(tasks)) as executor:
            # Submit all tasks
            futures = {}
            for sp_type, (key, func, client, cfg, period) in tasks.items():
                future = executor.submit(func, client, cfg, period)
                futures[future] = key

            # Collect results as they complete
            for future in as_completed(futures):
                key = futures[future]
                try:
                    result = future.result()
                    recommendations[key] = result
                except Exception as e:
                    logger.error(f"Failed to fetch {key} recommendation: {str(e)}")
                    raise

    logger.info(f"Recommendations retrieved: {recommendations}")
    return recommendations


def calculate_purchase_need(
    config: Dict[str, Any],
    coverage: Dict[str, float],
    recommendations: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Calculate required purchases to reach target coverage.

    Args:
        config: Configuration dictionary
        coverage: Current coverage by SP type
        recommendations: AWS recommendations

    Returns:
        list: Purchase plans to execute
    """
    logger.info("Calculating purchase need")

    purchase_plans = []
    target_coverage = config['coverage_target_percent']

    # Process Compute SP if enabled
    if config['enable_compute_sp']:
        current_compute_coverage = coverage.get('compute', 0.0)
        coverage_gap = target_coverage - current_compute_coverage

        logger.info(
            f"Compute SP - Current: {current_compute_coverage}%, "
            f"Target: {target_coverage}%, Gap: {coverage_gap}%"
        )

        # Only purchase if gap is positive and we have a recommendation
        if coverage_gap > 0 and recommendations.get('compute'):
            hourly_commitment = recommendations['compute'].get('HourlyCommitmentToPurchase', '0')
            hourly_commitment_float = float(hourly_commitment)

            if hourly_commitment_float > 0:
                purchase_plan = {
                    'sp_type': 'compute',
                    'hourly_commitment': hourly_commitment_float,
                    'payment_option': config.get('compute_sp_payment_option', 'ALL_UPFRONT'),
                    'recommendation_id': recommendations['compute'].get('RecommendationId', 'unknown')
                }
                purchase_plans.append(purchase_plan)
                logger.info(
                    f"Compute SP purchase planned: ${hourly_commitment_float}/hour "
                    f"(recommendation_id: {purchase_plan['recommendation_id']})"
                )
            else:
                logger.info("Compute SP recommendation has zero commitment - skipping")
        elif coverage_gap <= 0:
            logger.info("Compute SP coverage already meets or exceeds target - no purchase needed")
        else:
            logger.info("Compute SP has coverage gap but no AWS recommendation available")

    # Process Database SP if enabled
    if config['enable_database_sp']:
        current_database_coverage = coverage.get('database', 0.0)
        coverage_gap = target_coverage - current_database_coverage

        logger.info(
            f"Database SP - Current: {current_database_coverage}%, "
            f"Target: {target_coverage}%, Gap: {coverage_gap}%"
        )

        # Only purchase if gap is positive and we have a recommendation
        if coverage_gap > 0 and recommendations.get('database'):
            hourly_commitment = recommendations['database'].get('HourlyCommitmentToPurchase', '0')
            hourly_commitment_float = float(hourly_commitment)

            if hourly_commitment_float > 0:
                purchase_plan = {
                    'sp_type': 'database',
                    'hourly_commitment': hourly_commitment_float,
                    'term': 'ONE_YEAR',  # Database SP always uses 1-year term
                    'payment_option': 'NO_UPFRONT',  # Database SP uses no upfront payment
                    'recommendation_id': recommendations['database'].get('RecommendationId', 'unknown')
                }
                purchase_plans.append(purchase_plan)
                logger.info(
                    f"Database SP purchase planned: ${hourly_commitment_float}/hour "
                    f"(recommendation_id: {purchase_plan['recommendation_id']})"
                )
            else:
                logger.info("Database SP recommendation has zero commitment - skipping")
        elif coverage_gap <= 0:
            logger.info("Database SP coverage already meets or exceeds target - no purchase needed")
        else:
            logger.info("Database SP has coverage gap but no AWS recommendation available")

    # Process SageMaker SP if enabled
    if config['enable_sagemaker_sp']:
        current_sagemaker_coverage = coverage.get('sagemaker', 0.0)
        coverage_gap = target_coverage - current_sagemaker_coverage

        logger.info(
            f"SageMaker SP - Current: {current_sagemaker_coverage}%, "
            f"Target: {target_coverage}%, Gap: {coverage_gap}%"
        )

        # Only purchase if gap is positive and we have a recommendation
        if coverage_gap > 0 and recommendations.get('sagemaker'):
            hourly_commitment = recommendations['sagemaker'].get('HourlyCommitmentToPurchase', '0')
            hourly_commitment_float = float(hourly_commitment)

            if hourly_commitment_float > 0:
                purchase_plan = {
                    'sp_type': 'sagemaker',
                    'hourly_commitment': hourly_commitment_float,
                    'payment_option': config.get('sagemaker_sp_payment_option', 'ALL_UPFRONT'),
                    'recommendation_id': recommendations['sagemaker'].get('RecommendationId', 'unknown')
                }
                purchase_plans.append(purchase_plan)
                logger.info(
                    f"SageMaker SP purchase planned: ${hourly_commitment_float}/hour "
                    f"(recommendation_id: {purchase_plan['recommendation_id']})"
                )
            else:
                logger.info("SageMaker SP recommendation has zero commitment - skipping")
        elif coverage_gap <= 0:
            logger.info("SageMaker SP coverage already meets or exceeds target - no purchase needed")
        else:
            logger.info("SageMaker SP has coverage gap but no AWS recommendation available")

    logger.info(f"Purchase need calculated: {len(purchase_plans)} plans")
    return purchase_plans


def apply_purchase_limits(
    config: Dict[str, Any],
    purchase_plans: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Apply max_purchase_percent limit to planned purchases.

    Args:
        config: Configuration dictionary
        purchase_plans: List of planned purchases

    Returns:
        list: Limited purchase plans
    """
    logger.info("Applying purchase limits")

    if not purchase_plans:
        logger.info("No purchase plans to limit")
        return []

    # Calculate total hourly commitment
    total_commitment = sum(plan.get('hourly_commitment', 0.0) for plan in purchase_plans)
    logger.info(f"Total hourly commitment before limits: ${total_commitment:.4f}/hour")

    # Apply max_purchase_percent limit
    max_purchase_percent = config.get('max_purchase_percent', 100.0)
    scaling_factor = max_purchase_percent / 100.0

    logger.info(f"Applying {max_purchase_percent}% purchase limit (scaling factor: {scaling_factor:.4f})")

    # Scale down all plans by max_purchase_percent
    limited_plans = []
    for plan in purchase_plans:
        limited_plan = plan.copy()
        limited_plan['hourly_commitment'] = plan['hourly_commitment'] * scaling_factor
        limited_plans.append(limited_plan)

    # Filter out plans below minimum commitment threshold
    min_commitment = config.get('min_commitment_per_plan', 0.001)
    filtered_plans = [
        plan for plan in limited_plans
        if plan.get('hourly_commitment', 0.0) >= min_commitment
    ]

    removed_count = len(limited_plans) - len(filtered_plans)
    if removed_count > 0:
        logger.info(f"Removed {removed_count} plans below minimum commitment of ${min_commitment:.4f}/hour")

    final_commitment = sum(plan.get('hourly_commitment', 0.0) for plan in filtered_plans)
    logger.info(f"Purchase limits applied: {len(filtered_plans)} plans remain, ${final_commitment:.4f}/hour total commitment")

    return filtered_plans


def split_by_term(
    config: Dict[str, Any],
    purchase_plans: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Split Compute and SageMaker SP commitments by term mix.

    Args:
        config: Configuration dictionary
        purchase_plans: List of planned purchases

    Returns:
        list: Purchase plans split by term
    """
    logger.info("Splitting purchases by term")

    if not purchase_plans:
        logger.info("No purchase plans to split")
        return []

    split_plans = []
    compute_term_mix = config.get('compute_sp_term_mix', {})
    sagemaker_term_mix = config.get('sagemaker_sp_term_mix', {})

    # Map term_mix keys to API term values
    term_mapping = {
        'three_year': 'THREE_YEAR',
        'one_year': 'ONE_YEAR'
    }

    for plan in purchase_plans:
        sp_type = plan.get('sp_type')

        # Database SP already has term set - pass through unchanged
        if sp_type == 'database':
            split_plans.append(plan)
            logger.debug(f"Database SP plan passed through: ${plan.get('hourly_commitment', 0):.4f}/hour")
            continue

        # Compute SP needs to be split by term mix
        if sp_type == 'compute':
            base_commitment = plan.get('hourly_commitment', 0.0)
            min_commitment = config.get('min_commitment_per_plan', 0.001)

            logger.info(f"Splitting Compute SP: ${base_commitment:.4f}/hour across {len(compute_term_mix)} terms")

            for term_key, percentage in compute_term_mix.items():
                # Calculate commitment for this term
                term_commitment = base_commitment * percentage

                # Skip if below minimum threshold
                if term_commitment < min_commitment:
                    logger.info(
                        f"Skipping {term_key} term: commitment ${term_commitment:.4f}/hour "
                        f"below minimum ${min_commitment:.4f}/hour"
                    )
                    continue

                # Map term key to API value
                term_value = term_mapping.get(term_key)
                if not term_value:
                    logger.warning(f"Unknown term key '{term_key}' - skipping")
                    continue

                # Create new plan for this term
                term_plan = plan.copy()
                term_plan['hourly_commitment'] = term_commitment
                term_plan['term'] = term_value

                split_plans.append(term_plan)
                logger.info(
                    f"Created {term_value} plan: ${term_commitment:.4f}/hour "
                    f"({percentage * 100:.1f}% of base commitment)"
                )

        # SageMaker SP needs to be split by term mix
        elif sp_type == 'sagemaker':
            base_commitment = plan.get('hourly_commitment', 0.0)
            min_commitment = config.get('min_commitment_per_plan', 0.001)

            logger.info(f"Splitting SageMaker SP: ${base_commitment:.4f}/hour across {len(sagemaker_term_mix)} terms")

            for term_key, percentage in sagemaker_term_mix.items():
                # Calculate commitment for this term
                term_commitment = base_commitment * percentage

                # Skip if below minimum threshold
                if term_commitment < min_commitment:
                    logger.info(
                        f"Skipping {term_key} term: commitment ${term_commitment:.4f}/hour "
                        f"below minimum ${min_commitment:.4f}/hour"
                    )
                    continue

                # Map term key to API value
                term_value = term_mapping.get(term_key)
                if not term_value:
                    logger.warning(f"Unknown term key '{term_key}' - skipping")
                    continue

                # Create new plan for this term
                term_plan = plan.copy()
                term_plan['hourly_commitment'] = term_commitment
                term_plan['term'] = term_value

                split_plans.append(term_plan)
                logger.info(
                    f"Created {term_value} plan: ${term_commitment:.4f}/hour "
                    f"({percentage * 100:.1f}% of base commitment)"
                )
        else:
            # Unknown SP type - pass through
            logger.warning(f"Unknown SP type '{sp_type}' - passing through unchanged")
            split_plans.append(plan)

    logger.info(f"Term splitting complete: {len(purchase_plans)} plans -> {len(split_plans)} plans")
    return split_plans


def queue_purchase_intents(
    sqs_client: Any,
    config: Dict[str, Any],
    purchase_plans: List[Dict[str, Any]]
) -> None:
    """
    Queue purchase intents to SQS.

    Args:
        sqs_client: Boto3 SQS client
        config: Configuration dictionary
        purchase_plans: List of planned purchases
    """
    logger.info(f"Queuing {len(purchase_plans)} purchase intents")

    if not purchase_plans:
        logger.info("No purchase plans to queue")
        return

    queue_url = config['queue_url']
    queued_count = 0

    for plan in purchase_plans:
        try:
            # Generate unique client token for idempotency
            timestamp = datetime.now(timezone.utc).isoformat()
            sp_type = plan.get('sp_type', 'unknown')
            term = plan.get('term', 'unknown')
            commitment = plan.get('hourly_commitment', 0.0)
            client_token = f"scheduler-{sp_type}-{term}-{timestamp}"

            # Create purchase intent message
            purchase_intent = {
                'client_token': client_token,
                'sp_type': sp_type,
                'term': term,
                'hourly_commitment': commitment,
                'payment_option': plan.get('payment_option', 'ALL_UPFRONT'),
                'recommendation_id': plan.get('recommendation_id', 'unknown'),
                'queued_at': timestamp,
                'tags': config.get('tags', {})
            }

            # Send message to SQS
            response = sqs_client.send_message(
                QueueUrl=queue_url,
                MessageBody=json.dumps(purchase_intent)
            )

            message_id = response.get('MessageId')
            logger.info(
                f"Queued purchase intent: {sp_type} {term} ${commitment:.4f}/hour "
                f"(message_id: {message_id}, client_token: {client_token})"
            )
            queued_count += 1

        except ClientError as e:
            logger.error(f"Failed to queue purchase intent: {str(e)}")
            raise

    logger.info(f"All {queued_count} purchase intents queued successfully")


def send_scheduled_email(
    sns_client: Any,
    config: Dict[str, Any],
    purchase_plans: List[Dict[str, Any]],
    coverage: Dict[str, float]
) -> None:
    """
    Send email notification for scheduled purchases.

    Args:
        sns_client: Boto3 SNS client
        config: Configuration dictionary
        purchase_plans: List of planned purchases
        coverage: Current coverage
    """
    logger.info("Sending scheduled purchases email")

    # Format email body
    email_lines = [
        "Savings Plans Scheduled for Purchase",
        "=" * 50,
        "",
        f"Total Plans Queued: {len(purchase_plans)}",
        "",
        "Current Coverage:",
        f"  Compute SP:  {coverage.get('compute', 0):.2f}%",
        f"  Database SP: {coverage.get('database', 0):.2f}%",
        f"  SageMaker SP: {coverage.get('sagemaker', 0):.2f}%",
        "",
        f"Target Coverage: {config.get('coverage_target_percent', 90):.2f}%",
        "",
        "Scheduled Purchase Plans:",
        "-" * 50,
    ]

    # Add details for each purchase plan
    total_annual_cost = 0.0
    for i, plan in enumerate(purchase_plans, 1):
        sp_type = plan.get('sp_type', 'unknown')
        hourly_commitment = plan.get('hourly_commitment', 0.0)
        term = plan.get('term', 'unknown')
        payment_option = plan.get('payment_option', 'ALL_UPFRONT')

        # Calculate estimated annual cost (hourly * 24 * 365)
        annual_cost = hourly_commitment * 8760
        total_annual_cost += annual_cost

        email_lines.extend([
            f"{i}. {sp_type.upper()} Savings Plan",
            f"   Hourly Commitment: ${hourly_commitment:.4f}/hour",
            f"   Term: {term}",
            f"   Payment Option: {payment_option}",
            f"   Estimated Annual Cost: ${annual_cost:,.2f}",
            ""
        ])

    email_lines.extend([
        "-" * 50,
        f"Total Estimated Annual Cost: ${total_annual_cost:,.2f}",
        "",
        "CANCELLATION INSTRUCTIONS:",
        "To cancel these purchases before they execute:",
        "1. Purge the SQS queue to remove all pending purchase intents",
        f"2. Queue URL: {config.get('queue_url', 'N/A')}",
        "3. AWS CLI command:",
        f"   aws sqs purge-queue --queue-url {config.get('queue_url', 'QUEUE_URL')}",
        "",
        "These purchases will be executed by the Purchaser Lambda.",
        "Monitor CloudWatch Logs and SNS notifications for execution results.",
    ])

    message = "\n".join(email_lines)

    # Publish to SNS
    try:
        sns_client.publish(
            TopicArn=config['sns_topic_arn'],
            Subject='Savings Plans Scheduled for Purchase',
            Message=message
        )
        logger.info(f"Email sent successfully to {config['sns_topic_arn']}")
    except ClientError as e:
        logger.error(f"Failed to send email: {str(e)}")
        raise


def send_dry_run_email(
    sns_client: Any,
    config: Dict[str, Any],
    purchase_plans: List[Dict[str, Any]],
    coverage: Dict[str, float]
) -> None:
    """
    Send email notification for dry run analysis.

    Args:
        sns_client: Boto3 SNS client
        config: Configuration dictionary
        purchase_plans: List of what would be purchased
        coverage: Current coverage
    """
    logger.info("Sending dry run email")

    # Format email body
    email_lines = [
        "***** DRY RUN MODE ***** Savings Plans Analysis",
        "=" * 50,
        "",
        "*** NO PURCHASES WERE SCHEDULED ***",
        "",
        f"Total Plans Analyzed: {len(purchase_plans)}",
        "",
        "Current Coverage:",
        f"  Compute SP:  {coverage.get('compute', 0):.2f}%",
        f"  Database SP: {coverage.get('database', 0):.2f}%",
        f"  SageMaker SP: {coverage.get('sagemaker', 0):.2f}%",
        "",
        f"Target Coverage: {config.get('coverage_target_percent', 90):.2f}%",
        "",
        "Purchase Plans (WOULD BE SCHEDULED if dry_run=false):",
        "-" * 50,
    ]

    # Add details for each purchase plan
    total_annual_cost = 0.0
    for i, plan in enumerate(purchase_plans, 1):
        sp_type = plan.get('sp_type', 'unknown')
        hourly_commitment = plan.get('hourly_commitment', 0.0)
        term = plan.get('term', 'unknown')
        payment_option = plan.get('payment_option', 'ALL_UPFRONT')

        # Calculate estimated annual cost (hourly * 24 * 365)
        annual_cost = hourly_commitment * 8760
        total_annual_cost += annual_cost

        email_lines.extend([
            f"{i}. {sp_type.upper()} Savings Plan",
            f"   Hourly Commitment: ${hourly_commitment:.4f}/hour",
            f"   Term: {term}",
            f"   Payment Option: {payment_option}",
            f"   Estimated Annual Cost: ${annual_cost:,.2f}",
            ""
        ])

    email_lines.extend([
        "-" * 50,
        f"Total Estimated Annual Cost: ${total_annual_cost:,.2f}",
        "",
        "TO ENABLE ACTUAL PURCHASES:",
        "1. Set the DRY_RUN environment variable to 'false'",
        "2. Update the Lambda configuration:",
        "   aws lambda update-function-configuration \\",
        "     --function-name <scheduler-lambda-name> \\",
        "     --environment Variables={DRY_RUN=false,...}",
        "",
        "3. Or via Terraform:",
        "   Set dry_run = false in your terraform.tfvars",
        "",
        "Once disabled, the Scheduler will queue purchase intents to SQS,",
        "and the Purchaser Lambda will execute the actual purchases.",
    ])

    message = "\n".join(email_lines)

    # Publish to SNS
    try:
        sns_client.publish(
            TopicArn=config['sns_topic_arn'],
            Subject='[DRY RUN] Savings Plans Analysis - No Purchases Scheduled',
            Message=message
        )
        logger.info(f"Dry run email sent successfully to {config['sns_topic_arn']}")
    except ClientError as e:
        logger.error(f"Failed to send dry run email: {str(e)}")
        raise

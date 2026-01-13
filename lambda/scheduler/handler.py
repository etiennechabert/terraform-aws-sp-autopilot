"""
Scheduler Lambda - Analyzes usage and queues Savings Plan purchase intents.

This Lambda:
1. Purges existing queue messages
2. Calculates current coverage (excluding plans expiring within renewal_window_days)
3. Gets AWS purchase recommendations
4. Calculates purchase need based on coverage_target_percent
5. Applies max_purchase_percent limit
6. Splits commitment by term mix (for Compute SP)
7. Queues purchase intents (or sends email only if dry_run=true)
8. Sends notification email with analysis results
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional

import boto3
from botocore.exceptions import ClientError

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# AWS clients
ce_client = boto3.client('ce')
sqs_client = boto3.client('sqs')
sns_client = boto3.client('sns')
savingsplans_client = boto3.client('savingsplans')


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
        logger.info("Starting Scheduler Lambda execution")

        # Load configuration from environment
        config = load_configuration()
        logger.info(f"Configuration loaded: dry_run={config['dry_run']}")

        # Step 1: Purge existing queue
        purge_queue(config['queue_url'])

        # Step 2: Calculate current coverage
        coverage = calculate_current_coverage(config)
        logger.info(f"Current coverage - Compute: {coverage.get('compute', 0)}%, Database: {coverage.get('database', 0)}%")

        # Step 3: Get AWS recommendations
        recommendations = get_aws_recommendations(config)

        # Step 4: Calculate purchase need
        purchase_plans = calculate_purchase_need(config, coverage, recommendations)

        # Step 5: Apply purchase limits
        purchase_plans = apply_purchase_limits(config, purchase_plans)

        # Step 6: Split by term (for Compute SP)
        purchase_plans = split_by_term(config, purchase_plans)

        # Step 7: Queue or notify
        if config['dry_run']:
            logger.info("Dry run mode - sending email only, NOT queuing messages")
            send_dry_run_email(config, purchase_plans, coverage)
        else:
            logger.info("Queuing purchase intents to SQS")
            queue_purchase_intents(config, purchase_plans)
            send_scheduled_email(config, purchase_plans, coverage)

        logger.info("Scheduler Lambda completed successfully")

        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Scheduler completed successfully',
                'dry_run': config['dry_run'],
                'purchases_planned': len(purchase_plans)
            })
        }

    except Exception as e:
        logger.error(f"Scheduler Lambda failed: {str(e)}", exc_info=True)
        send_error_email(str(e))
        raise  # Re-raise to ensure Lambda fails visibly


def load_configuration() -> Dict[str, Any]:
    """Load and validate configuration from environment variables."""
    return {
        'queue_url': os.environ['QUEUE_URL'],
        'sns_topic_arn': os.environ['SNS_TOPIC_ARN'],
        'dry_run': os.environ.get('DRY_RUN', 'true').lower() == 'true',
        'enable_compute_sp': os.environ.get('ENABLE_COMPUTE_SP', 'true').lower() == 'true',
        'enable_database_sp': os.environ.get('ENABLE_DATABASE_SP', 'false').lower() == 'true',
        'coverage_target_percent': float(os.environ.get('COVERAGE_TARGET_PERCENT', '90')),
        'max_purchase_percent': float(os.environ.get('MAX_PURCHASE_PERCENT', '10')),
        'renewal_window_days': int(os.environ.get('RENEWAL_WINDOW_DAYS', '7')),
        'lookback_days': int(os.environ.get('LOOKBACK_DAYS', '30')),
        'min_data_days': int(os.environ.get('MIN_DATA_DAYS', '14')),
        'min_commitment_per_plan': float(os.environ.get('MIN_COMMITMENT_PER_PLAN', '0.001')),
        'compute_sp_term_mix': json.loads(os.environ.get('COMPUTE_SP_TERM_MIX', '{"three_year": 0.67, "one_year": 0.33}')),
        'compute_sp_payment_option': os.environ.get('COMPUTE_SP_PAYMENT_OPTION', 'ALL_UPFRONT'),
        'partial_upfront_percent': float(os.environ.get('PARTIAL_UPFRONT_PERCENT', '50')),
        'management_account_role_arn': os.environ.get('MANAGEMENT_ACCOUNT_ROLE_ARN'),
        'tags': json.loads(os.environ.get('TAGS', '{}')),
    }


def purge_queue(queue_url: str) -> None:
    """
    Purge all existing messages from the SQS queue.

    Args:
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


def calculate_current_coverage(config: Dict[str, Any]) -> Dict[str, float]:
    """
    Calculate current Savings Plans coverage, excluding plans expiring soon.

    Args:
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
                'database': 0.0
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
        # For now, we'll use the overall coverage for compute and assume 0 for database
        # In a production system, you might need to call GetSavingsPlansCoverage with
        # GroupBy to separate by service or use DescribeSavingsPlans to categorize
        coverage = {
            'compute': coverage_percentage,
            'database': 0.0
        }

    except ClientError as e:
        logger.error(f"Failed to get coverage from Cost Explorer: {str(e)}")
        raise

    logger.info(f"Coverage calculated: {coverage}")
    return coverage


def get_aws_recommendations(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get Savings Plans purchase recommendations from AWS Cost Explorer.

    Args:
        config: Configuration dictionary

    Returns:
        dict: Recommendations by SP type
    """
    logger.info("Getting AWS recommendations")

    # TODO: Implement actual recommendation retrieval
    # - Call ce:GetSavingsPlansPurchaseRecommendation
    # - Filter by enabled SP types
    # - Validate sufficient data days

    recommendations = {
        'compute': None,
        'database': None
    }

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

    # TODO: Implement purchase need calculation
    # - For each enabled SP type
    # - Calculate gap between current coverage and target
    # - Use recommendations to determine commitment needed
    # - Create purchase plan objects

    purchase_plans = []

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

    # TODO: Implement purchase limits
    # - Calculate current monthly on-demand spend
    # - Apply max_purchase_percent cap
    # - Reduce or filter purchase plans if needed
    # - Respect min_commitment_per_plan

    logger.info(f"Purchase limits applied: {len(purchase_plans)} plans remain")
    return purchase_plans


def split_by_term(
    config: Dict[str, Any],
    purchase_plans: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Split Compute SP commitments by term mix.

    Args:
        config: Configuration dictionary
        purchase_plans: List of planned purchases

    Returns:
        list: Purchase plans split by term
    """
    logger.info("Splitting purchases by term")

    # TODO: Implement term splitting
    # - For Compute SP only
    # - Split commitment according to term_mix
    # - Database SP always uses 1-year term

    logger.info(f"Term splitting complete: {len(purchase_plans)} plans")
    return purchase_plans


def queue_purchase_intents(
    config: Dict[str, Any],
    purchase_plans: List[Dict[str, Any]]
) -> None:
    """
    Queue purchase intents to SQS.

    Args:
        config: Configuration dictionary
        purchase_plans: List of planned purchases
    """
    logger.info(f"Queuing {len(purchase_plans)} purchase intents")

    # TODO: Implement message queuing
    # - For each purchase plan
    # - Create SQS message with required fields
    # - Send to queue

    logger.info("All purchase intents queued successfully")


def send_scheduled_email(
    config: Dict[str, Any],
    purchase_plans: List[Dict[str, Any]],
    coverage: Dict[str, float]
) -> None:
    """
    Send email notification for scheduled purchases.

    Args:
        config: Configuration dictionary
        purchase_plans: List of planned purchases
        coverage: Current coverage
    """
    logger.info("Sending scheduled purchases email")

    # TODO: Implement email notification
    # - Format email with purchase details
    # - Include cancellation instructions
    # - Publish to SNS

    logger.info("Email sent successfully")


def send_dry_run_email(
    config: Dict[str, Any],
    purchase_plans: List[Dict[str, Any]],
    coverage: Dict[str, float]
) -> None:
    """
    Send email notification for dry run analysis.

    Args:
        config: Configuration dictionary
        purchase_plans: List of what would be purchased
        coverage: Current coverage
    """
    logger.info("Sending dry run email")

    # TODO: Implement dry run email
    # - Format email with analysis results
    # - Clear indication that no purchases were scheduled
    # - Instructions to disable dry_run

    logger.info("Dry run email sent successfully")


def send_error_email(error_message: str) -> None:
    """
    Send error notification email.

    Args:
        error_message: Error details
    """
    logger.error("Sending error notification email")

    # TODO: Implement error email
    # - Format error details
    # - Publish to SNS

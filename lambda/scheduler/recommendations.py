"""
AWS Savings Plans recommendations fetching module.

This module handles fetching purchase recommendations from AWS Cost Explorer
for Compute, Database, and SageMaker Savings Plans. It uses ThreadPoolExecutor
to fetch multiple recommendation types in parallel for improved performance.
"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Optional

from botocore.exceptions import ClientError
from mypy_boto3_ce.client import CostExplorerClient

from shared.handler_utils import configure_logging


# Configure logging
logger = logging.getLogger()
configure_logging()


def _fetch_compute_sp_recommendation(
    ce_client: CostExplorerClient, lookback_period: str
) -> Optional[dict[str, Any]]:
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
            SavingsPlansType="COMPUTE_SP",
            LookbackPeriodInDays=lookback_period,
            TermInYears="ONE_YEAR",
            PaymentOption="ALL_UPFRONT",
        )

        logger.debug(f"Compute SP API response: {response}")

        # Extract recommendation metadata
        metadata = response.get("Metadata")
        if not metadata:
            raise ValueError(f"AWS returned no Metadata in response: {response}")

        recommendation_id = metadata.get("RecommendationId", "unknown")
        generation_timestamp = metadata.get("GenerationTimestamp", "unknown")

        # Extract recommendation details
        recommendation_details = response.get("SavingsPlansPurchaseRecommendation", {})
        recommendation_summary = recommendation_details.get(
            "SavingsPlansPurchaseRecommendationDetails", []
        )

        if recommendation_summary:
            # Get the first (best) recommendation
            best_recommendation = recommendation_summary[0]
            hourly_commitment = best_recommendation.get("HourlyCommitmentToPurchase", "0")

            logger.info(
                f"Compute SP recommendation: ${hourly_commitment}/hour "
                f"(recommendation_id: {recommendation_id}, generated: {generation_timestamp})"
            )

            return {
                "HourlyCommitmentToPurchase": hourly_commitment,
                "RecommendationId": recommendation_id,
                "GenerationTimestamp": generation_timestamp,
                "Details": best_recommendation,
            }
        logger.info("No Compute SP recommendations available from AWS")
        return None

    except ClientError as e:
        logger.error(f"Failed to get Compute SP recommendations: {e!s}")
        raise


def _fetch_database_sp_recommendation(
    ce_client: CostExplorerClient, lookback_period: str
) -> Optional[dict[str, Any]]:
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
            SavingsPlansType="DATABASE_SP",
            LookbackPeriodInDays=lookback_period,
            TermInYears="ONE_YEAR",
            PaymentOption="NO_UPFRONT",
        )

        # Extract recommendation metadata
        metadata = response.get("Metadata")
        if not metadata:
            raise ValueError(f"AWS returned no Metadata in response: {response}")

        recommendation_id = metadata.get("RecommendationId", "unknown")
        generation_timestamp = metadata.get("GenerationTimestamp", "unknown")

        # Extract recommendation details
        recommendation_details = response.get("SavingsPlansPurchaseRecommendation", {})
        recommendation_summary = recommendation_details.get(
            "SavingsPlansPurchaseRecommendationDetails", []
        )

        if recommendation_summary:
            # Get the first (best) recommendation
            best_recommendation = recommendation_summary[0]
            hourly_commitment = best_recommendation.get("HourlyCommitmentToPurchase", "0")

            logger.info(
                f"Database SP recommendation: ${hourly_commitment}/hour "
                f"(recommendation_id: {recommendation_id}, generated: {generation_timestamp})"
            )

            return {
                "HourlyCommitmentToPurchase": hourly_commitment,
                "RecommendationId": recommendation_id,
                "GenerationTimestamp": generation_timestamp,
                "Details": best_recommendation,
            }
        logger.info("No Database SP recommendations available from AWS")
        return None

    except ClientError as e:
        logger.error(f"Failed to get Database SP recommendations: {e!s}")
        raise


def _fetch_sagemaker_sp_recommendation(
    ce_client: CostExplorerClient, lookback_period: str
) -> Optional[dict[str, Any]]:
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
            SavingsPlansType="SAGEMAKER_SP",
            LookbackPeriodInDays=lookback_period,
            TermInYears="ONE_YEAR",
            PaymentOption="NO_UPFRONT",
        )

        # Extract recommendation metadata
        metadata = response.get("Metadata")
        if not metadata:
            raise ValueError(f"AWS returned no Metadata in response: {response}")

        recommendation_id = metadata.get("RecommendationId", "unknown")
        generation_timestamp = metadata.get("GenerationTimestamp", "unknown")

        # Extract recommendation details
        recommendation_details = response.get("SavingsPlansPurchaseRecommendation", {})
        recommendation_summary = recommendation_details.get(
            "SavingsPlansPurchaseRecommendationDetails", []
        )

        if recommendation_summary:
            # Get the first (best) recommendation
            best_recommendation = recommendation_summary[0]
            hourly_commitment = best_recommendation.get("HourlyCommitmentToPurchase", "0")

            logger.info(
                f"SageMaker SP recommendation: ${hourly_commitment}/hour "
                f"(recommendation_id: {recommendation_id}, generated: {generation_timestamp})"
            )

            return {
                "HourlyCommitmentToPurchase": hourly_commitment,
                "RecommendationId": recommendation_id,
                "GenerationTimestamp": generation_timestamp,
                "Details": best_recommendation,
            }
        logger.info("No SageMaker SP recommendations available from AWS")
        return None

    except ClientError as e:
        logger.error(f"Failed to get SageMaker SP recommendations: {e!s}")
        raise


def get_aws_recommendations(
    ce_client: CostExplorerClient, config: dict[str, Any]
) -> dict[str, Any]:
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

    recommendations = {"compute": None, "database": None, "sagemaker": None}

    # Map lookback_days to AWS API parameter value
    lookback_days = config["lookback_days"]
    if lookback_days <= 7:
        lookback_period = "SEVEN_DAYS"
    elif lookback_days <= 30:
        lookback_period = "THIRTY_DAYS"
    else:
        lookback_period = "SIXTY_DAYS"

    logger.info(f"Using lookback period: {lookback_period} (config: {lookback_days} days)")

    # Prepare tasks for parallel execution
    tasks = {}
    if config["enable_compute_sp"]:
        tasks["compute"] = (
            "compute",
            _fetch_compute_sp_recommendation,
            ce_client,
            lookback_period,
        )
    if config["enable_database_sp"]:
        tasks["database"] = (
            "database",
            _fetch_database_sp_recommendation,
            ce_client,
            lookback_period,
        )
    if config["enable_sagemaker_sp"]:
        tasks["sagemaker"] = (
            "sagemaker",
            _fetch_sagemaker_sp_recommendation,
            ce_client,
            lookback_period,
        )

    # Execute API calls in parallel using ThreadPoolExecutor
    if tasks:
        with ThreadPoolExecutor(max_workers=len(tasks)) as executor:
            # Submit all tasks
            futures = {}
            for sp_type, (key, func, client, period) in tasks.items():
                future = executor.submit(func, client, period)
                futures[future] = key

            # Collect results as they complete
            for future in as_completed(futures):
                key = futures[future]
                try:
                    result = future.result()
                    recommendations[key] = result
                except Exception as e:
                    logger.error(f"Failed to fetch {key} recommendation: {e!s}")
                    raise

    logger.info(f"Recommendations retrieved: {recommendations}")
    return recommendations

"""AWS Savings Plans recommendations fetching module."""

from __future__ import annotations

import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TYPE_CHECKING, Any

from botocore.exceptions import ClientError


if TYPE_CHECKING:
    from mypy_boto3_ce.client import CostExplorerClient

from shared.aws_debug import add_response
from shared.handler_utils import configure_logging


logger = logging.getLogger()
configure_logging()

SP_TYPE_CONFIG = {
    "compute": {
        "name": "Compute",
        "savings_plans_type": "COMPUTE_SP",
        "payment_option": "ALL_UPFRONT",
    },
    "database": {
        "name": "Database",
        "savings_plans_type": "DATABASE_SP",
        "payment_option": "NO_UPFRONT",
    },
    "sagemaker": {
        "name": "SageMaker",
        "savings_plans_type": "SAGEMAKER_SP",
        "payment_option": "NO_UPFRONT",
    },
}


def _fetch_sp_recommendation(
    ce_client: CostExplorerClient, lookback_period: str, sp_key: str
) -> dict[str, Any] | None:
    """Fetch a Savings Plan recommendation from AWS Cost Explorer."""
    sp_config = SP_TYPE_CONFIG[sp_key]
    sp_name = sp_config["name"]

    logger.info(f"Fetching {sp_name} Savings Plan recommendations")
    try:
        params = {
            "SavingsPlansType": sp_config["savings_plans_type"],
            "LookbackPeriodInDays": lookback_period,
            "TermInYears": "ONE_YEAR",
            "PaymentOption": sp_config["payment_option"],
        }
        response = ce_client.get_savings_plans_purchase_recommendation(**params)

        add_response(
            "get_savings_plans_purchase_recommendation",
            params,
            response,
            sp_type=sp_key,
            context="scheduler_preview_follow_aws",
        )

        logger.debug(f"{sp_name} SP API response:\n{json.dumps(response, indent=2, default=str)}")

        recommendation = response["SavingsPlansPurchaseRecommendation"]
        details_list = recommendation.get("SavingsPlansPurchaseRecommendationDetails", [])

        if not details_list:
            logger.info(f"No {sp_name} SP recommendations available from AWS")
            return None

        metadata = response.get("Metadata", {})
        recommendation_id = metadata.get("RecommendationId", "unknown")
        generation_timestamp = metadata.get("GenerationTimestamp", "unknown")
        best = details_list[0]

        logger.info(
            f"{sp_name} SP recommendation: ${best['HourlyCommitmentToPurchase']}/hour "
            f"(recommendation_id: {recommendation_id}, generated: {generation_timestamp})"
        )

        return {
            "HourlyCommitmentToPurchase": best["HourlyCommitmentToPurchase"],
            "RecommendationId": recommendation_id,
            "GenerationTimestamp": generation_timestamp,
            "Details": best,
        }

    except ClientError as e:
        logger.error(f"Failed to get {sp_name} SP recommendations: {e!s}")
        raise


def get_aws_recommendations(
    ce_client: CostExplorerClient, config: dict[str, Any]
) -> dict[str, Any]:
    """Get Savings Plans purchase recommendations from AWS Cost Explorer in parallel."""
    logger.info("Getting AWS recommendations")

    recommendations: dict[str, Any] = {"compute": None, "database": None, "sagemaker": None}

    lookback_days = config["lookback_days"]
    if lookback_days <= 7:
        lookback_period = "SEVEN_DAYS"
    elif lookback_days <= 30:
        lookback_period = "THIRTY_DAYS"
    else:
        lookback_period = "SIXTY_DAYS"

    logger.info(f"Using lookback period: {lookback_period} (config: {lookback_days} days)")

    enabled_types = [
        sp_key for sp_key, sp_conf in SP_TYPE_CONFIG.items() if config[f"enable_{sp_key}_sp"]
    ]

    if enabled_types:
        with ThreadPoolExecutor(max_workers=len(enabled_types)) as executor:
            futures = {
                executor.submit(
                    _fetch_sp_recommendation, ce_client, lookback_period, sp_key
                ): sp_key
                for sp_key in enabled_types
            }

            for future in as_completed(futures):
                key = futures[future]
                result = future.result()
                recommendations[key] = result

    logger.info(f"Recommendations retrieved:\n{json.dumps(recommendations, indent=2, default=str)}")
    return recommendations

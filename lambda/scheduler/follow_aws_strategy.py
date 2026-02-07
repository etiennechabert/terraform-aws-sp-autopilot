"""
Follow AWS Strategy Module - Uses AWS Cost Explorer recommendations exactly as provided.

This module implements the follow_aws strategy, which trusts AWS recommendations
completely and purchases exactly what Cost Explorer suggests.

Strategy Behavior:
- Uses 100% of AWS Cost Explorer recommendations
- No scaling or modification of recommended amounts
- Simplest possible strategy - just follow AWS guidance

Benefits:
- Maximum trust in AWS optimization algorithms
- No manual tuning required
- AWS recommendations already factor in your usage patterns
- Good starting point for new users

Use when:
- You trust AWS Cost Explorer recommendations
- You want hands-off automation
- You're starting with Savings Plans and want conservative approach
"""

import logging
from typing import Any

import recommendations as recommendations_module


# Configure logging
logger = logging.getLogger()


def calculate_purchase_need_follow_aws(
    config: dict[str, Any], clients: dict[str, Any], spending_data: dict[str, Any] | None = None
) -> list[dict[str, Any]]:
    """
    Calculate required purchases using FOLLOW_AWS strategy.

    This strategy uses AWS Cost Explorer recommendations exactly as provided,
    without any scaling or modification.

    Args:
        config: Configuration dictionary
        clients: AWS clients (ce, savingsplans, etc.)
        spending_data: Unused (follow_aws doesn't need spending analysis)

    Returns:
        list: Purchase plans to execute
    """
    logger.info("Calculating purchase need using FOLLOW_AWS strategy")

    # Fetch AWS recommendations (only data source this strategy needs)
    # Note: spending_data is ignored - follow_aws only uses AWS recommendations
    recommendations = recommendations_module.get_aws_recommendations(clients["ce"], config)

    purchase_plans = []

    # SP types configuration
    sp_types = [
        {
            "key": "compute",
            "enabled_config": "enable_compute_sp",
            "payment_option_config": "compute_sp_payment_option",
            "name": "Compute",
        },
        {
            "key": "database",
            "enabled_config": "enable_database_sp",
            "payment_option_config": "database_sp_payment_option",
            "name": "Database",
        },
        {
            "key": "sagemaker",
            "enabled_config": "enable_sagemaker_sp",
            "payment_option_config": "sagemaker_sp_payment_option",
            "name": "SageMaker",
        },
    ]

    for sp_type in sp_types:
        if not config[sp_type["enabled_config"]]:
            continue

        key = sp_type["key"]
        recommendation = recommendations.get(key)
        if not recommendation:
            logger.info(
                f"{sp_type['name']} SP has coverage gap but no AWS recommendation available"
            )
            continue

        # Use AWS recommendation exactly as provided (100%)
        hourly_commitment_float = float(recommendation.get("HourlyCommitmentToPurchase", "0"))
        if hourly_commitment_float <= 0:
            logger.info(f"{sp_type['name']} SP recommendation has zero commitment - skipping")
            continue

        details = recommendation.get("Details", {})
        estimated_savings_pct = float(details.get("EstimatedSavingsPercentage", "0"))

        purchase_plan = {
            "sp_type": key,
            "hourly_commitment": hourly_commitment_float,
            "payment_option": config[sp_type["payment_option_config"]],
            "recommendation_id": recommendation.get("RecommendationId", "unknown"),
            "strategy": "follow_aws",
            "estimated_savings_percentage": estimated_savings_pct,
        }

        # Set term based on SP type
        if key == "compute":
            purchase_plan["term"] = config.get("compute_sp_term", "THREE_YEAR")
        elif key == "sagemaker":
            purchase_plan["term"] = config.get("sagemaker_sp_term", "THREE_YEAR")
        elif key == "database":
            purchase_plan["term"] = "ONE_YEAR"  # AWS constraint

        purchase_plans.append(purchase_plan)
        logger.info(
            "%s SP purchase planned: $%s/hour (100%% of AWS recommendation, recommendation_id: %s)",
            sp_type["name"],
            hourly_commitment_float,
            purchase_plan["recommendation_id"],
        )

    logger.info(f"Follow AWS strategy purchase need calculated: {len(purchase_plans)} plans")
    return purchase_plans

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


# Configure logging
logger = logging.getLogger()


def calculate_purchase_need_follow_aws(
    config: dict[str, Any], coverage: dict[str, float], recommendations: dict[str, Any]
) -> list[dict[str, Any]]:
    """
    Calculate required purchases using FOLLOW_AWS strategy.

    This strategy uses AWS Cost Explorer recommendations exactly as provided,
    without any scaling or modification.

    Args:
        config: Configuration dictionary
        coverage: Current coverage by SP type
        recommendations: AWS recommendations

    Returns:
        list: Purchase plans to execute
    """
    logger.info("Calculating purchase need using FOLLOW_AWS strategy")

    purchase_plans = []
    target_coverage = config["coverage_target_percent"]

    # SP types configuration
    sp_types = [
        {
            "key": "compute",
            "enabled_config": "enable_compute_sp",
            "payment_option_config": "compute_sp_payment_option",
            "default_payment": "ALL_UPFRONT",
            "name": "Compute",
        },
        {
            "key": "database",
            "enabled_config": "enable_database_sp",
            "payment_option_config": "database_sp_payment_option",
            "default_payment": "NO_UPFRONT",
            "name": "Database",
            "term": "ONE_YEAR",
        },
        {
            "key": "sagemaker",
            "enabled_config": "enable_sagemaker_sp",
            "payment_option_config": "sagemaker_sp_payment_option",
            "default_payment": "ALL_UPFRONT",
            "name": "SageMaker",
        },
    ]

    for sp_type in sp_types:
        if not config[sp_type["enabled_config"]]:
            continue

        key = sp_type["key"]
        current_coverage = coverage.get(key, 0.0)
        coverage_gap = target_coverage - current_coverage

        logger.info(
            f"{sp_type['name']} SP - Current: {current_coverage}%, "
            f"Target: {target_coverage}%, Gap: {coverage_gap}%"
        )

        if coverage_gap <= 0:
            logger.info(f"{sp_type['name']} SP coverage already meets or exceeds target")
            continue

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

        purchase_plan = {
            "sp_type": key,
            "hourly_commitment": hourly_commitment_float,
            "payment_option": config.get(
                sp_type["payment_option_config"], sp_type["default_payment"]
            ),
            "recommendation_id": recommendation.get("RecommendationId", "unknown"),
            "strategy": "follow_aws",
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
            f"{sp_type['name']} SP purchase planned: ${hourly_commitment_float}/hour "
            f"(100% of AWS recommendation, recommendation_id: {purchase_plan['recommendation_id']})"
        )

    logger.info(f"Follow AWS strategy purchase need calculated: {len(purchase_plans)} plans")
    return purchase_plans

"""
Fixed Purchase Strategy Module - Fixed percentage purchase strategy.

This module implements the fixed purchase strategy, which applies
a fixed max_purchase_percent to all AWS recommendations uniformly.

Strategy Behavior:
- Applies the same percentage every cycle regardless of coverage gap
- Linear ramp to target coverage
- Predictable and easy to understand
- Best for stable workloads with predictable growth

Benefits:
- Simple and predictable
- No surprises in purchase amounts
- Easy to budget and forecast
- Good for steady-state optimization
"""

import logging
from typing import Any, Dict, List


# Configure logging
logger = logging.getLogger()


def calculate_purchase_need_fixed(
    config: Dict[str, Any], coverage: Dict[str, float], recommendations: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Calculate required purchases using FIXED strategy.

    Fixed strategy applies max_purchase_percent uniformly to all AWS recommendations.

    Args:
        config: Configuration dictionary
        coverage: Current coverage by SP type
        recommendations: AWS recommendations

    Returns:
        list: Purchase plans to execute
    """
    logger.info("Calculating purchase need using FIXED strategy")

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
            "strategy": "fixed",
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
            f"(recommendation_id: {purchase_plan['recommendation_id']})"
        )

    logger.info(f"Fixed strategy purchase need calculated: {len(purchase_plans)} plans")
    return purchase_plans

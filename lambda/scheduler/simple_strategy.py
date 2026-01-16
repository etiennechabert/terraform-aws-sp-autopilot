"""
Simple Purchase Strategy Module - Fixed percentage purchase strategy.

This module implements the simple (default) purchase strategy, which applies
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


def calculate_purchase_need_simple(
    config: Dict[str, Any], coverage: Dict[str, float], recommendations: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Calculate required purchases using SIMPLE strategy (legacy/default).

    Simple strategy applies max_purchase_percent uniformly to all AWS recommendations.

    Args:
        config: Configuration dictionary
        coverage: Current coverage by SP type
        recommendations: AWS recommendations

    Returns:
        list: Purchase plans to execute
    """
    logger.info("Calculating purchase need using SIMPLE strategy")

    purchase_plans = []
    target_coverage = config["coverage_target_percent"]

    # Process Compute SP if enabled
    if config["enable_compute_sp"]:
        current_compute_coverage = coverage.get("compute", 0.0)
        coverage_gap = target_coverage - current_compute_coverage

        logger.info(
            f"Compute SP - Current: {current_compute_coverage}%, "
            f"Target: {target_coverage}%, Gap: {coverage_gap}%"
        )

        # Only purchase if gap is positive and we have a recommendation
        if coverage_gap > 0 and recommendations.get("compute"):
            hourly_commitment = recommendations["compute"].get("HourlyCommitmentToPurchase", "0")
            hourly_commitment_float = float(hourly_commitment)

            if hourly_commitment_float > 0:
                purchase_plan = {
                    "sp_type": "compute",
                    "hourly_commitment": hourly_commitment_float,
                    "payment_option": config.get("compute_sp_payment_option", "ALL_UPFRONT"),
                    "recommendation_id": recommendations["compute"].get(
                        "RecommendationId", "unknown"
                    ),
                    "strategy": "simple",
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
    if config["enable_database_sp"]:
        current_database_coverage = coverage.get("database", 0.0)
        coverage_gap = target_coverage - current_database_coverage

        logger.info(
            f"Database SP - Current: {current_database_coverage}%, "
            f"Target: {target_coverage}%, Gap: {coverage_gap}%"
        )

        # Only purchase if gap is positive and we have a recommendation
        if coverage_gap > 0 and recommendations.get("database"):
            hourly_commitment = recommendations["database"].get("HourlyCommitmentToPurchase", "0")
            hourly_commitment_float = float(hourly_commitment)

            if hourly_commitment_float > 0:
                purchase_plan = {
                    "sp_type": "database",
                    "hourly_commitment": hourly_commitment_float,
                    "term": "ONE_YEAR",  # Database SP always uses 1-year term
                    "payment_option": "NO_UPFRONT",  # Database SP uses no upfront payment
                    "recommendation_id": recommendations["database"].get(
                        "RecommendationId", "unknown"
                    ),
                    "strategy": "simple",
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
    if config["enable_sagemaker_sp"]:
        current_sagemaker_coverage = coverage.get("sagemaker", 0.0)
        coverage_gap = target_coverage - current_sagemaker_coverage

        logger.info(
            f"SageMaker SP - Current: {current_sagemaker_coverage}%, "
            f"Target: {target_coverage}%, Gap: {coverage_gap}%"
        )

        # Only purchase if gap is positive and we have a recommendation
        if coverage_gap > 0 and recommendations.get("sagemaker"):
            hourly_commitment = recommendations["sagemaker"].get("HourlyCommitmentToPurchase", "0")
            hourly_commitment_float = float(hourly_commitment)

            if hourly_commitment_float > 0:
                purchase_plan = {
                    "sp_type": "sagemaker",
                    "hourly_commitment": hourly_commitment_float,
                    "payment_option": config.get("sagemaker_sp_payment_option", "ALL_UPFRONT"),
                    "recommendation_id": recommendations["sagemaker"].get(
                        "RecommendationId", "unknown"
                    ),
                    "strategy": "simple",
                }
                purchase_plans.append(purchase_plan)
                logger.info(
                    f"SageMaker SP purchase planned: ${hourly_commitment_float}/hour "
                    f"(recommendation_id: {purchase_plan['recommendation_id']})"
                )
            else:
                logger.info("SageMaker SP recommendation has zero commitment - skipping")
        elif coverage_gap <= 0:
            logger.info(
                "SageMaker SP coverage already meets or exceeds target - no purchase needed"
            )
        else:
            logger.info("SageMaker SP has coverage gap but no AWS recommendation available")

    logger.info(f"Simple strategy purchase need calculated: {len(purchase_plans)} plans")
    return purchase_plans

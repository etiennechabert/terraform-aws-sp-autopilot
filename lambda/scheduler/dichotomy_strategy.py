"""
Dichotomy Purchase Strategy Module - Adaptive purchase sizing based on coverage gap.

This module implements the dichotomy purchase strategy, which uses exponentially
decreasing purchase sizes based on coverage gap, creating a stable long-term
coverage profile.

Strategy Behavior:
- Purchase size is calculated as the largest power-of-2 fraction of max_purchase_percent
  that doesn't exceed the coverage gap
- Example sequence (max_purchase_percent = 50%, target = 90%):
  * Month 1: Coverage 0% → Gap 90% → Purchase 50% (max)
  * Month 2: Coverage 50% → Gap 40% → Purchase 25% (50% / 2)
  * Month 3: Coverage 75% → Gap 15% → Purchase 12.5% (25% / 2)
  * Month 4: Coverage 87.5% → Gap 2.5% → Purchase 2.5% (exact gap)

Benefits:
- Adaptive: Purchase size automatically adjusts based on coverage gap
- Stable: Creates distributed, smaller commitments over time
- Resilient: When large plans expire, naturally replaced by smaller distributed purchases
- Safe: Prevents over-commitment by halving approach
- Stateless: No need to track iteration count - gap determines purchase size
"""

import logging
from typing import Any, Dict, List


# Configure logging
logger = logging.getLogger()


def calculate_dichotomy_purchase_percent(
    current_coverage_percent: float,
    target_coverage_percent: float,
    max_purchase_percent: float,
    min_purchase_percent: float,
) -> float:
    """
    Calculate purchase percentage using dichotomy strategy.

    Always tries max_purchase_percent first, then halves until the purchase
    doesn't cause coverage to exceed the target.

    Args:
        current_coverage_percent: Current coverage (e.g., 50.0)
        target_coverage_percent: Target coverage (e.g., 90.0)
        max_purchase_percent: Maximum allowed purchase percentage (e.g., 50.0)
        min_purchase_percent: Minimum purchase percentage threshold (e.g., 1.0)

    Returns:
        Purchase percentage to use (largest power-of-2 that doesn't exceed target)

    Examples:
        >>> calculate_dichotomy_purchase_percent(0.0, 90.0, 50.0, 1.0)
        50.0  # At 0%, try 50% → would be 50%, OK

        >>> calculate_dichotomy_purchase_percent(50.0, 90.0, 50.0, 1.0)
        25.0  # At 50%, try 50% → 100% > 90%, try 25% → 75%, OK

        >>> calculate_dichotomy_purchase_percent(75.0, 90.0, 50.0, 1.0)
        12.5  # At 75%, try 50% → 125% > 90%, try 25% → 100% > 90%, try 12.5% → 87.5%, OK

        >>> calculate_dichotomy_purchase_percent(87.5, 90.0, 50.0, 1.0)
        2.5  # At 87.5%, keep halving until 2.5% → 90%, OK
    """
    # Calculate the gap
    coverage_gap_percent = target_coverage_percent - current_coverage_percent

    # Edge case: if gap is below min, return the gap (we're very close to target)
    if coverage_gap_percent < min_purchase_percent:
        return coverage_gap_percent

    # Start at maximum purchase percentage
    purchase_percent = max_purchase_percent

    # Halve until current + purchase doesn't exceed target
    while current_coverage_percent + purchase_percent > target_coverage_percent:
        # Halve the purchase percentage
        purchase_percent = purchase_percent / 2.0

        # If we've halved below the minimum threshold, return the exact gap
        if purchase_percent < min_purchase_percent:
            return coverage_gap_percent

    # Return the largest power-of-2 that fits
    return purchase_percent


def calculate_purchase_need_dichotomy(
    config: Dict[str, Any], coverage: Dict[str, float], recommendations: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Calculate required purchases using dichotomy strategy.

    This function applies the dichotomy strategy to determine purchase amounts:
    1. Calculate coverage gap for each SP type
    2. Use dichotomy algorithm to determine purchase percentage
    3. Apply percentage to AWS recommendations
    4. Ensure we don't exceed AWS recommendation (never scale up)

    Args:
        config: Configuration dictionary with strategy parameters
        coverage: Current coverage by SP type (e.g., {"compute": 50.0, "database": 0.0})
        recommendations: AWS recommendations by SP type

    Returns:
        list: Purchase plans to execute with calculated commitments
    """
    logger.info("Calculating purchase need using DICHOTOMY strategy")

    purchase_plans = []
    target_coverage = config["coverage_target_percent"]
    max_purchase_percent = config.get("max_purchase_percent", 50.0)
    min_purchase_percent = config.get("min_purchase_percent", 1.0)

    logger.info(
        f"Dichotomy strategy parameters: "
        f"target={target_coverage}%, "
        f"max_purchase={max_purchase_percent}%, "
        f"min_purchase={min_purchase_percent}%"
    )

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
            # Calculate purchase percentage using dichotomy algorithm
            purchase_percent = calculate_dichotomy_purchase_percent(
                current_compute_coverage,
                target_coverage,
                max_purchase_percent,
                min_purchase_percent,
            )

            logger.info(
                f"Dichotomy algorithm: current={current_compute_coverage}%, target={target_coverage}%, "
                f"purchase_percent={purchase_percent}%"
            )

            # Get AWS recommendation
            aws_hourly_commitment = float(
                recommendations["compute"].get("HourlyCommitmentToPurchase", "0")
            )

            # Calculate actual purchase based on percentage
            # NOTE: We scale DOWN from AWS recommendation, never UP
            # If AWS recommends $10/hour and we want 25%, we purchase $2.50/hour
            scaling_factor = purchase_percent / 100.0
            actual_hourly_commitment = aws_hourly_commitment * scaling_factor

            logger.info(
                f"AWS recommendation: ${aws_hourly_commitment:.4f}/hour, "
                f"Scaling by {purchase_percent}% -> ${actual_hourly_commitment:.4f}/hour"
            )

            if actual_hourly_commitment > 0:
                purchase_plan = {
                    "sp_type": "compute",
                    "hourly_commitment": actual_hourly_commitment,
                    "payment_option": config.get(
                        "compute_sp_payment_option", "ALL_UPFRONT"
                    ),
                    "recommendation_id": recommendations["compute"].get(
                        "RecommendationId", "unknown"
                    ),
                    "strategy": "dichotomy",
                    "purchase_percent": purchase_percent,
                }
                purchase_plans.append(purchase_plan)
                logger.info(
                    f"Compute SP purchase planned: ${actual_hourly_commitment:.4f}/hour "
                    f"({purchase_percent}% of AWS recommendation, "
                    f"recommendation_id: {purchase_plan['recommendation_id']})"
                )
            else:
                logger.info("Compute SP calculated commitment is zero - skipping")
        elif coverage_gap <= 0:
            logger.info(
                "Compute SP coverage already meets or exceeds target - no purchase needed"
            )
        else:
            logger.info(
                "Compute SP has coverage gap but no AWS recommendation available"
            )

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
            # Calculate purchase percentage using dichotomy algorithm
            purchase_percent = calculate_dichotomy_purchase_percent(
                current_database_coverage,
                target_coverage,
                max_purchase_percent,
                min_purchase_percent,
            )

            logger.info(
                f"Dichotomy algorithm: current={current_database_coverage}%, target={target_coverage}%, "
                f"purchase_percent={purchase_percent}%"
            )

            # Get AWS recommendation
            aws_hourly_commitment = float(
                recommendations["database"].get("HourlyCommitmentToPurchase", "0")
            )

            # Calculate actual purchase based on percentage
            scaling_factor = purchase_percent / 100.0
            actual_hourly_commitment = aws_hourly_commitment * scaling_factor

            logger.info(
                f"AWS recommendation: ${aws_hourly_commitment:.4f}/hour, "
                f"Scaling by {purchase_percent}% -> ${actual_hourly_commitment:.4f}/hour"
            )

            if actual_hourly_commitment > 0:
                purchase_plan = {
                    "sp_type": "database",
                    "hourly_commitment": actual_hourly_commitment,
                    "term": "ONE_YEAR",  # Database SP always uses 1-year term
                    "payment_option": "NO_UPFRONT",  # Database SP uses no upfront payment
                    "recommendation_id": recommendations["database"].get(
                        "RecommendationId", "unknown"
                    ),
                    "strategy": "dichotomy",
                    "purchase_percent": purchase_percent,
                }
                purchase_plans.append(purchase_plan)
                logger.info(
                    f"Database SP purchase planned: ${actual_hourly_commitment:.4f}/hour "
                    f"({purchase_percent}% of AWS recommendation, "
                    f"recommendation_id: {purchase_plan['recommendation_id']})"
                )
            else:
                logger.info("Database SP calculated commitment is zero - skipping")
        elif coverage_gap <= 0:
            logger.info(
                "Database SP coverage already meets or exceeds target - no purchase needed"
            )
        else:
            logger.info(
                "Database SP has coverage gap but no AWS recommendation available"
            )

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
            # Calculate purchase percentage using dichotomy algorithm
            purchase_percent = calculate_dichotomy_purchase_percent(
                current_sagemaker_coverage,
                target_coverage,
                max_purchase_percent,
                min_purchase_percent,
            )

            logger.info(
                f"Dichotomy algorithm: current={current_sagemaker_coverage}%, target={target_coverage}%, "
                f"purchase_percent={purchase_percent}%"
            )

            # Get AWS recommendation
            aws_hourly_commitment = float(
                recommendations["sagemaker"].get("HourlyCommitmentToPurchase", "0")
            )

            # Calculate actual purchase based on percentage
            scaling_factor = purchase_percent / 100.0
            actual_hourly_commitment = aws_hourly_commitment * scaling_factor

            logger.info(
                f"AWS recommendation: ${aws_hourly_commitment:.4f}/hour, "
                f"Scaling by {purchase_percent}% -> ${actual_hourly_commitment:.4f}/hour"
            )

            if actual_hourly_commitment > 0:
                purchase_plan = {
                    "sp_type": "sagemaker",
                    "hourly_commitment": actual_hourly_commitment,
                    "payment_option": config.get(
                        "sagemaker_sp_payment_option", "ALL_UPFRONT"
                    ),
                    "recommendation_id": recommendations["sagemaker"].get(
                        "RecommendationId", "unknown"
                    ),
                    "strategy": "dichotomy",
                    "purchase_percent": purchase_percent,
                }
                purchase_plans.append(purchase_plan)
                logger.info(
                    f"SageMaker SP purchase planned: ${actual_hourly_commitment:.4f}/hour "
                    f"({purchase_percent}% of AWS recommendation, "
                    f"recommendation_id: {purchase_plan['recommendation_id']})"
                )
            else:
                logger.info("SageMaker SP calculated commitment is zero - skipping")
        elif coverage_gap <= 0:
            logger.info(
                "SageMaker SP coverage already meets or exceeds target - no purchase needed"
            )
        else:
            logger.info(
                "SageMaker SP has coverage gap but no AWS recommendation available"
            )

    logger.info(f"Dichotomy purchase need calculated: {len(purchase_plans)} plans")
    return purchase_plans

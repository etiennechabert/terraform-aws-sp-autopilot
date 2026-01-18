"""
Conservative Purchase Strategy Module - Gap-threshold purchase strategy.

This module implements the conservative purchase strategy, which only makes
purchases when the coverage gap exceeds a minimum threshold, reducing churn
for stable workloads.

Strategy Behavior:
- Only purchase when (target_coverage - current_coverage) >= min_gap_threshold
- When threshold is met, purchase max_purchase_percent of AWS recommendation
- Skip purchases when gap is below threshold (avoiding small, frequent purchases)
- Good for stable workloads where coverage naturally fluctuates slightly

Benefits:
- Reduces purchase churn for workloads with stable coverage
- Prevents frequent small purchases when coverage is close to target
- Simple threshold-based decision making
- Configurable sensitivity via min_gap_threshold
- Predictable purchase amounts via max_purchase_percent

Example (min_gap_threshold = 5%, max_purchase_percent = 50%):
- Current: 88%, Target: 90%, Gap: 2% → No purchase (below threshold)
- Current: 84%, Target: 90%, Gap: 6% → Purchase 50% of AWS recommendation
- Current: 70%, Target: 90%, Gap: 20% → Purchase 50% of AWS recommendation
"""

import logging
from typing import Any, Dict, List


# Configure logging
logger = logging.getLogger()


def calculate_purchase_need_conservative(
    config: Dict[str, Any], coverage: Dict[str, float], recommendations: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Calculate required purchases using CONSERVATIVE strategy.

    Conservative strategy only purchases when coverage gap exceeds min_gap_threshold.
    When threshold is met, purchases max_purchase_percent of AWS recommendation.

    Args:
        config: Configuration dictionary with strategy parameters
        coverage: Current coverage by SP type (e.g., {"compute": 50.0, "database": 0.0})
        recommendations: AWS recommendations by SP type

    Returns:
        list: Purchase plans to execute with calculated commitments
    """
    logger.info("Calculating purchase need using CONSERVATIVE strategy")

    purchase_plans = []
    target_coverage = config["coverage_target_percent"]
    min_gap_threshold = config.get("min_gap_threshold", 5.0)
    max_purchase_percent = config.get("max_purchase_percent", 50.0)

    logger.info(
        f"Conservative strategy parameters: "
        f"target={target_coverage}%, "
        f"min_gap_threshold={min_gap_threshold}%, "
        f"max_purchase_percent={max_purchase_percent}%"
    )

    # Process Compute SP if enabled
    if config["enable_compute_sp"]:
        current_compute_coverage = coverage.get("compute", 0.0)
        coverage_gap = target_coverage - current_compute_coverage

        logger.info(
            f"Compute SP - Current: {current_compute_coverage}%, "
            f"Target: {target_coverage}%, Gap: {coverage_gap}%"
        )

        # Only purchase if gap exceeds threshold and we have a recommendation
        if coverage_gap >= min_gap_threshold and recommendations.get("compute"):
            logger.info(
                f"Coverage gap ({coverage_gap}%) meets threshold ({min_gap_threshold}%) - "
                f"proceeding with purchase"
            )

            # Get AWS recommendation
            aws_hourly_commitment = float(
                recommendations["compute"].get("HourlyCommitmentToPurchase", "0")
            )

            # Scale by max_purchase_percent
            scaling_factor = max_purchase_percent / 100.0
            actual_hourly_commitment = aws_hourly_commitment * scaling_factor

            logger.info(
                f"AWS recommendation: ${aws_hourly_commitment:.4f}/hour, "
                f"Scaling by {max_purchase_percent}% -> ${actual_hourly_commitment:.4f}/hour"
            )

            if actual_hourly_commitment > 0:
                purchase_plan = {
                    "sp_type": "compute",
                    "hourly_commitment": actual_hourly_commitment,
                    "payment_option": config.get("compute_sp_payment_option", "ALL_UPFRONT"),
                    "recommendation_id": recommendations["compute"].get(
                        "RecommendationId", "unknown"
                    ),
                    "strategy": "conservative",
                    "purchase_percent": max_purchase_percent,
                }
                purchase_plans.append(purchase_plan)
                logger.info(
                    f"Compute SP purchase planned: ${actual_hourly_commitment:.4f}/hour "
                    f"({max_purchase_percent}% of AWS recommendation, "
                    f"recommendation_id: {purchase_plan['recommendation_id']})"
                )
            else:
                logger.info("Compute SP calculated commitment is zero - skipping")
        elif coverage_gap < min_gap_threshold:
            logger.info(
                f"Compute SP coverage gap ({coverage_gap}%) below threshold "
                f"({min_gap_threshold}%) - skipping purchase"
            )
        elif coverage_gap < 0:
            logger.info("Compute SP coverage already meets or exceeds target - no purchase needed")
        else:
            logger.info(
                f"Compute SP has coverage gap ({coverage_gap}%) but no AWS recommendation available"
            )

    # Process Database SP if enabled
    if config["enable_database_sp"]:
        current_database_coverage = coverage.get("database", 0.0)
        coverage_gap = target_coverage - current_database_coverage

        logger.info(
            f"Database SP - Current: {current_database_coverage}%, "
            f"Target: {target_coverage}%, Gap: {coverage_gap}%"
        )

        # Only purchase if gap exceeds threshold and we have a recommendation
        if coverage_gap >= min_gap_threshold and recommendations.get("database"):
            logger.info(
                f"Coverage gap ({coverage_gap}%) meets threshold ({min_gap_threshold}%) - "
                f"proceeding with purchase"
            )

            # Get AWS recommendation
            aws_hourly_commitment = float(
                recommendations["database"].get("HourlyCommitmentToPurchase", "0")
            )

            # Scale by max_purchase_percent
            scaling_factor = max_purchase_percent / 100.0
            actual_hourly_commitment = aws_hourly_commitment * scaling_factor

            logger.info(
                f"AWS recommendation: ${aws_hourly_commitment:.4f}/hour, "
                f"Scaling by {max_purchase_percent}% -> ${actual_hourly_commitment:.4f}/hour"
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
                    "strategy": "conservative",
                    "purchase_percent": max_purchase_percent,
                }
                purchase_plans.append(purchase_plan)
                logger.info(
                    f"Database SP purchase planned: ${actual_hourly_commitment:.4f}/hour "
                    f"({max_purchase_percent}% of AWS recommendation, "
                    f"recommendation_id: {purchase_plan['recommendation_id']})"
                )
            else:
                logger.info("Database SP calculated commitment is zero - skipping")
        elif coverage_gap < min_gap_threshold:
            logger.info(
                f"Database SP coverage gap ({coverage_gap}%) below threshold "
                f"({min_gap_threshold}%) - skipping purchase"
            )
        elif coverage_gap < 0:
            logger.info("Database SP coverage already meets or exceeds target - no purchase needed")
        else:
            logger.info(
                f"Database SP has coverage gap ({coverage_gap}%) "
                f"but no AWS recommendation available"
            )

    # Process SageMaker SP if enabled
    if config["enable_sagemaker_sp"]:
        current_sagemaker_coverage = coverage.get("sagemaker", 0.0)
        coverage_gap = target_coverage - current_sagemaker_coverage

        logger.info(
            f"SageMaker SP - Current: {current_sagemaker_coverage}%, "
            f"Target: {target_coverage}%, Gap: {coverage_gap}%"
        )

        # Only purchase if gap exceeds threshold and we have a recommendation
        if coverage_gap >= min_gap_threshold and recommendations.get("sagemaker"):
            logger.info(
                f"Coverage gap ({coverage_gap}%) meets threshold ({min_gap_threshold}%) - "
                f"proceeding with purchase"
            )

            # Get AWS recommendation
            aws_hourly_commitment = float(
                recommendations["sagemaker"].get("HourlyCommitmentToPurchase", "0")
            )

            # Scale by max_purchase_percent
            scaling_factor = max_purchase_percent / 100.0
            actual_hourly_commitment = aws_hourly_commitment * scaling_factor

            logger.info(
                f"AWS recommendation: ${aws_hourly_commitment:.4f}/hour, "
                f"Scaling by {max_purchase_percent}% -> ${actual_hourly_commitment:.4f}/hour"
            )

            if actual_hourly_commitment > 0:
                purchase_plan = {
                    "sp_type": "sagemaker",
                    "hourly_commitment": actual_hourly_commitment,
                    "payment_option": config.get("sagemaker_sp_payment_option", "ALL_UPFRONT"),
                    "recommendation_id": recommendations["sagemaker"].get(
                        "RecommendationId", "unknown"
                    ),
                    "strategy": "conservative",
                    "purchase_percent": max_purchase_percent,
                }
                purchase_plans.append(purchase_plan)
                logger.info(
                    f"SageMaker SP purchase planned: ${actual_hourly_commitment:.4f}/hour "
                    f"({max_purchase_percent}% of AWS recommendation, "
                    f"recommendation_id: {purchase_plan['recommendation_id']})"
                )
            else:
                logger.info("SageMaker SP calculated commitment is zero - skipping")
        elif coverage_gap < min_gap_threshold:
            logger.info(
                f"SageMaker SP coverage gap ({coverage_gap}%) below threshold "
                f"({min_gap_threshold}%) - skipping purchase"
            )
        elif coverage_gap < 0:
            logger.info(
                "SageMaker SP coverage already meets or exceeds target - no purchase needed"
            )
        else:
            logger.info(
                f"SageMaker SP has coverage gap ({coverage_gap}%) "
                f"but no AWS recommendation available"
            )

    logger.info(f"Conservative strategy purchase need calculated: {len(purchase_plans)} plans")
    return purchase_plans

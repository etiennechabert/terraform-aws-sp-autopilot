"""
Purchase Calculator Module - Calculates and processes Savings Plan purchase plans.

This module contains the core logic for:
1. Calculating purchase need based on coverage gaps and AWS recommendations
2. Applying purchase limits (max_purchase_percent and min_commitment_per_plan)
3. Splitting commitments by term mix (for Compute and SageMaker SPs)
"""

import logging
from typing import Any, Dict, List


# Configure logging
logger = logging.getLogger()


def calculate_purchase_need(
    config: Dict[str, Any], coverage: Dict[str, float], recommendations: Dict[str, Any]
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

    logger.info(f"Purchase need calculated: {len(purchase_plans)} plans")
    return purchase_plans


def apply_purchase_limits(
    config: Dict[str, Any], purchase_plans: List[Dict[str, Any]]
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
    total_commitment = sum(plan.get("hourly_commitment", 0.0) for plan in purchase_plans)
    logger.info(f"Total hourly commitment before limits: ${total_commitment:.4f}/hour")

    # Apply max_purchase_percent limit
    max_purchase_percent = config.get("max_purchase_percent", 100.0)
    scaling_factor = max_purchase_percent / 100.0

    logger.info(
        f"Applying {max_purchase_percent}% purchase limit (scaling factor: {scaling_factor:.4f})"
    )

    # Scale down all plans by max_purchase_percent
    limited_plans = []
    for plan in purchase_plans:
        limited_plan = plan.copy()
        limited_plan["hourly_commitment"] = plan["hourly_commitment"] * scaling_factor
        limited_plans.append(limited_plan)

    # Filter out plans below minimum commitment threshold
    min_commitment = config.get("min_commitment_per_plan", 0.001)
    filtered_plans = [
        plan for plan in limited_plans if plan.get("hourly_commitment", 0.0) >= min_commitment
    ]

    removed_count = len(limited_plans) - len(filtered_plans)
    if removed_count > 0:
        logger.info(
            f"Removed {removed_count} plans below minimum commitment of ${min_commitment:.4f}/hour"
        )

    final_commitment = sum(plan.get("hourly_commitment", 0.0) for plan in filtered_plans)
    logger.info(
        f"Purchase limits applied: {len(filtered_plans)} plans remain, ${final_commitment:.4f}/hour total commitment"
    )

    return filtered_plans


def split_by_term(
    config: Dict[str, Any], purchase_plans: List[Dict[str, Any]]
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
    compute_term_mix = config.get("compute_sp_term_mix", {})
    sagemaker_term_mix = config.get("sagemaker_sp_term_mix", {})

    # Map term_mix keys to API term values
    term_mapping = {"three_year": "THREE_YEAR", "one_year": "ONE_YEAR"}

    for plan in purchase_plans:
        sp_type = plan.get("sp_type")

        # Database SP already has term set - pass through unchanged
        if sp_type == "database":
            split_plans.append(plan)
            logger.debug(
                f"Database SP plan passed through: ${plan.get('hourly_commitment', 0):.4f}/hour"
            )
            continue

        # Compute SP needs to be split by term mix
        if sp_type == "compute":
            base_commitment = plan.get("hourly_commitment", 0.0)
            min_commitment = config.get("min_commitment_per_plan", 0.001)

            logger.info(
                f"Splitting Compute SP: ${base_commitment:.4f}/hour across {len(compute_term_mix)} terms"
            )

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
                term_plan["hourly_commitment"] = term_commitment
                term_plan["term"] = term_value

                split_plans.append(term_plan)
                logger.info(
                    f"Created {term_value} plan: ${term_commitment:.4f}/hour "
                    f"({percentage * 100:.1f}% of base commitment)"
                )

        # SageMaker SP needs to be split by term mix
        elif sp_type == "sagemaker":
            base_commitment = plan.get("hourly_commitment", 0.0)
            min_commitment = config.get("min_commitment_per_plan", 0.001)

            logger.info(
                f"Splitting SageMaker SP: ${base_commitment:.4f}/hour across {len(sagemaker_term_mix)} terms"
            )

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
                term_plan["hourly_commitment"] = term_commitment
                term_plan["term"] = term_value

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

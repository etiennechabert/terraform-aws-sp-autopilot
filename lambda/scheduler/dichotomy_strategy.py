"""
Dichotomy Purchase Strategy Module - Adaptive purchase sizing based on coverage gap.

This module implements the dichotomy purchase strategy, which uses exponentially
decreasing purchase sizes based on coverage gap, creating a stable long-term
coverage profile.

Strategy Behavior:
- Calculates hourly commitment from actual spending data
- Purchase percentage uses binary halving algorithm
- Independent of AWS recommendations
- Automatically adapts to coverage gap

Calculation:
- Purchase percent = largest power-of-2 fraction that doesn't exceed gap
- Hourly commitment = avg_hourly_spend × purchase_percent / 100

Example sequence (max_purchase_percent = 50%, target = 90%, spend = $1,235/h):
  * Month 1: Coverage 0% → Gap 90% → Purchase 50% → $617.50/h
  * Month 2: Coverage 50% → Gap 40% → Purchase 25% → $308.75/h
  * Month 3: Coverage 75% → Gap 15% → Purchase 12.5% → $154.38/h
  * Month 4: Coverage 87.5% → Gap 2.5% → Purchase 2.5% → $30.88/h

Benefits:
- Adaptive: Purchase size automatically adjusts based on coverage gap
- Stable: Creates distributed, smaller commitments over time
- Resilient: When large plans expire, naturally replaced by smaller distributed purchases
- Safe: Prevents over-commitment by halving approach
- Stateless: No need to track iteration count - gap determines purchase size
- Works without AWS recommendations
"""

import logging
from typing import Any

from shared.spending_analyzer import SpendingAnalyzer


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
        min_purchase_percent: Minimum purchase granularity (e.g., 1.0)

    Returns:
        Purchase percentage to use (power-of-2 halving, rounded to min granularity)

    Examples:
        >>> calculate_dichotomy_purchase_percent(0.0, 90.0, 50.0, 1.0)
        50.0  # At 0%, try 50% → would be 50%, OK

        >>> calculate_dichotomy_purchase_percent(50.0, 90.0, 50.0, 1.0)
        25.0  # At 50%, try 50% → 100% > 90%, try 25% → 75%, OK

        >>> calculate_dichotomy_purchase_percent(75.0, 90.0, 50.0, 1.0)
        12.5  # At 75%, try 50% → 125% > 90%, try 25% → 100% > 90%, try 12.5% → 87.5%, OK

        >>> calculate_dichotomy_purchase_percent(87.5, 90.0, 50.0, 1.0)
        1.6  # At 87.5%, halve to 1.5625% → round to 1.6%
    """
    # Calculate the gap
    coverage_gap_percent = target_coverage_percent - current_coverage_percent

    # If already at or above target, no purchase needed
    if coverage_gap_percent <= 0:
        return 0.0

    # Edge case: if gap is below min, still return min (cannot buy less than min)
    # This may slightly overshoot target, but max_coverage_cap provides safety
    if coverage_gap_percent < min_purchase_percent:
        return min_purchase_percent

    # Start at maximum purchase percentage
    purchase_percent = max_purchase_percent

    # Halve until current + purchase doesn't exceed target
    while current_coverage_percent + purchase_percent > target_coverage_percent:
        # Halve the purchase percentage
        purchase_percent = purchase_percent / 2.0

        # If we've halved below the minimum, return the minimum
        if purchase_percent < min_purchase_percent:
            return min_purchase_percent

    # If result is below minimum, enforce minimum
    if purchase_percent < min_purchase_percent:
        return min_purchase_percent

    # Round to 1 decimal place for cleaner purchases (1.5625% → 1.6%)
    return round(purchase_percent, 1)


def calculate_purchase_need_dichotomy(
    config: dict[str, Any], clients: dict[str, Any], spending_data: dict[str, Any] | None = None
) -> list[dict[str, Any]]:
    """
    Calculate required purchases using dichotomy strategy.

    This function applies the dichotomy strategy to determine purchase amounts:
    1. Analyze current spending (fetch spending data)
    2. Calculate coverage gap for each SP type
    3. Use dichotomy algorithm to determine purchase percentage
    4. Calculate hourly commitment from spending data

    Args:
        config: Configuration dictionary with strategy parameters
        clients: AWS clients (savingsplans, ce)
        spending_data: Optional pre-fetched spending analysis (if None, will fetch it)

    Returns:
        list: Purchase plans to execute with calculated commitments
    """
    logger.info("Calculating purchase need using DICHOTOMY strategy")

    # Use provided spending data or fetch it
    if spending_data is None:
        analyzer = SpendingAnalyzer(clients["savingsplans"], clients["ce"])
        spending_data = analyzer.analyze_current_spending(config)
        spending_data.pop("_unknown_services", None)  # Remove metadata if we fetched it

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
        data = spending_data.get(key)
        if not data:
            logger.info(f"{sp_type['name']} SP - No spending data available")
            continue

        summary = data["summary"]
        current_coverage = summary["avg_coverage"]
        avg_hourly_total = summary["avg_hourly_total"]
        avg_hourly_covered = summary["avg_hourly_covered"]

        # Calculate coverage gap
        coverage_gap = target_coverage - current_coverage

        logger.info(
            f"{sp_type['name']} SP - Current: {current_coverage:.2f}%, "
            f"Target: {target_coverage:.2f}%, Gap: {coverage_gap:.2f}%, "
            f"Avg hourly spend: ${avg_hourly_total:.4f}/h"
        )

        if coverage_gap <= 0:
            logger.info(f"{sp_type['name']} SP coverage already meets or exceeds target")
            continue

        if avg_hourly_total <= 0:
            logger.info(f"{sp_type['name']} SP has zero spend - skipping")
            continue

        # Calculate purchase percentage using dichotomy algorithm
        purchase_percent = calculate_dichotomy_purchase_percent(
            current_coverage,
            target_coverage,
            max_purchase_percent,
            min_purchase_percent,
        )

        logger.info(
            f"Dichotomy algorithm: current={current_coverage:.2f}%, "
            f"target={target_coverage:.2f}%, purchase_percent={purchase_percent:.2f}%"
        )

        # Calculate actual hourly commitment from spending data
        hourly_commitment = avg_hourly_total * (purchase_percent / 100.0)

        # Apply minimum commitment threshold
        min_commitment = config.get("min_commitment_per_plan", 0.001)
        if hourly_commitment < min_commitment:
            logger.info(
                f"{sp_type['name']} SP calculated commitment ${hourly_commitment:.4f}/h "
                f"is below minimum ${min_commitment:.4f}/h - skipping"
            )
            continue

        if key == "compute":
            purchase_plan_term = config.get("compute_sp_term", "THREE_YEAR")
        elif key == "sagemaker":
            purchase_plan_term = config.get("sagemaker_sp_term", "THREE_YEAR")
        elif key == "database":
            purchase_plan_term = "ONE_YEAR"  # AWS constraint

        purchase_plan = {
            "strategy": "dichotomy",
            "sp_type": key,
            "hourly_commitment": hourly_commitment,
            "purchase_percent": purchase_percent,
            "payment_option": config[sp_type["payment_option_config"]],
            "term": purchase_plan_term,
            "details": {
                "coverage": {
                    "current": current_coverage,
                    "target": target_coverage,
                    "gap": coverage_gap,
                },
                "spending": {
                    "total": avg_hourly_total,
                    "covered": avg_hourly_covered,
                    "uncovered": avg_hourly_total - avg_hourly_covered,
                },
                "strategy_params": {
                    "max_purchase_percent": max_purchase_percent,
                    "min_purchase_percent": min_purchase_percent,
                },
            },
        }

        purchase_plans.append(purchase_plan)
        logger.info(
            f"{sp_type['name']} SP purchase planned: ${hourly_commitment:.4f}/h "
            f"({purchase_percent:.2f}% of spend, gap: {coverage_gap:.2f}%)"
        )

    logger.info(f"Dichotomy purchase need calculated: {len(purchase_plans)} plans")
    return purchase_plans



"""
Fixed Purchase Strategy Module - Fixed percentage purchase strategy.

This module implements the fixed purchase strategy, which purchases a fixed
percentage of uncovered spend up to max_purchase_percent.

Strategy Behavior:
- Calculates hourly commitment from actual spending data
- Purchases up to max_purchase_percent at a time (default: 10%)
- Linear ramp to target coverage
- Independent of AWS recommendations
- Predictable and easy to understand

Calculation:
- Hourly commitment = avg_hourly_spend * min(coverage_gap, max_purchase_percent) / 100

Example:
- Avg hourly spend: $1,235/h
- Current coverage: 25%
- Target coverage: 90%
- Coverage gap: 65%
- max_purchase_percent: 10%
- Purchase: $1,235 * 10% = $123.50/h (adds ~10% coverage)

Benefits:
- Simple and predictable
- No surprises in purchase amounts
- Easy to budget and forecast
- Works without AWS recommendations
- Best for stable workloads with predictable growth
"""

import logging
from typing import Any

from shared.spending_analyzer import SpendingAnalyzer


# Configure logging
logger = logging.getLogger()


def calculate_purchase_need_fixed(
    config: dict[str, Any], clients: dict[str, Any], spending_data: dict[str, Any] | None = None
) -> list[dict[str, Any]]:
    """
    Calculate required purchases using FIXED strategy.

    Fixed strategy purchases a fixed percentage of uncovered spend at a time.
    Analyzes current spending to calculate hourly commitment needs.

    Calculation:
    - Purchase percent = min(coverage_gap, max_purchase_percent)
    - Hourly commitment = avg_hourly_spend * purchase_percent / 100

    Args:
        config: Configuration dictionary
        clients: AWS clients (savingsplans, ce)
        spending_data: Optional pre-fetched spending analysis (if None, will fetch it)

    Returns:
        list: Purchase plans to execute
    """
    logger.info("Calculating purchase need using FIXED strategy")

    # Use provided spending data or fetch it
    if spending_data is None:
        analyzer = SpendingAnalyzer(clients["savingsplans"], clients["ce"])
        spending_data = analyzer.analyze_current_spending(config)
        spending_data.pop("_unknown_services", None)  # Remove metadata if we fetched it

    purchase_plans = []
    target_coverage = config["coverage_target_percent"]
    max_purchase_percent = config.get("max_purchase_percent", 10.0)

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
        current_coverage = summary["avg_coverage_total"]
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

        # Apply fixed split logic: purchase up to max_purchase_percent
        purchase_percent = min(coverage_gap, max_purchase_percent)
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
            "strategy": "fixed",
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
                },
            },
        }

        purchase_plans.append(purchase_plan)
        logger.info(
            f"{sp_type['name']} SP purchase planned: ${hourly_commitment:.4f}/h "
            f"({purchase_percent:.2f}% of spend, gap: {coverage_gap:.2f}%)"
        )

    logger.info(f"Fixed strategy purchase need calculated: {len(purchase_plans)} plans")
    return purchase_plans

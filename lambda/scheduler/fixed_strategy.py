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
- Hourly commitment = avg_hourly_spend × min(coverage_gap, max_purchase_percent) / 100

Example:
- Avg hourly spend: $1,235/h
- Current coverage: 25%
- Target coverage: 90%
- Coverage gap: 65%
- max_purchase_percent: 10%
- Purchase: $1,235 × 10% = $123.50/h (adds ~10% coverage)

Benefits:
- Simple and predictable
- No surprises in purchase amounts
- Easy to budget and forecast
- Works without AWS recommendations
- Best for stable workloads with predictable growth
"""

import logging
from typing import Any


# Configure logging
logger = logging.getLogger()


def calculate_purchase_need_fixed(
    config: dict[str, Any], clients: dict[str, Any], spending_data: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    """
    Calculate required purchases using FIXED strategy.

    Fixed strategy purchases a fixed percentage of uncovered spend at a time.

    Calculation:
    - Purchase percent = min(coverage_gap, max_purchase_percent)
    - Hourly commitment = avg_hourly_spend × purchase_percent / 100

    Args:
        config: Configuration dictionary
        clients: AWS clients (not used by this strategy)
        spending_data: Full spending analysis with time series and summary

    Returns:
        list: Purchase plans to execute
    """
    logger.info("Calculating purchase need using FIXED strategy")

    purchase_plans = []
    target_coverage = config["coverage_target_percent"]
    max_purchase_percent = config.get("max_purchase_percent", 10.0)

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
        data = spending_data.get(key)
        if not data:
            logger.info(f"{sp_type['name']} SP - No spending data available")
            continue

        summary = data["summary"]
        current_coverage = summary["avg_coverage"]
        total_spend = summary["total_spend"]
        num_hours = len(data["timeseries"])

        if num_hours == 0:
            logger.info(f"{sp_type['name']} SP - No time series data available")
            continue

        # Calculate average hourly spend
        avg_hourly_spend = total_spend / num_hours

        # Calculate coverage gap
        coverage_gap = target_coverage - current_coverage

        logger.info(
            f"{sp_type['name']} SP - Current: {current_coverage:.2f}%, "
            f"Target: {target_coverage:.2f}%, Gap: {coverage_gap:.2f}%, "
            f"Avg hourly spend: ${avg_hourly_spend:.4f}/h"
        )

        if coverage_gap <= 0:
            logger.info(f"{sp_type['name']} SP coverage already meets or exceeds target")
            continue

        if avg_hourly_spend <= 0:
            logger.info(f"{sp_type['name']} SP has zero spend - skipping")
            continue

        # Apply fixed split logic: purchase up to max_purchase_percent
        purchase_percent = min(coverage_gap, max_purchase_percent)
        hourly_commitment = avg_hourly_spend * (purchase_percent / 100.0)

        # Apply minimum commitment threshold
        min_commitment = config.get("min_commitment_per_plan", 0.001)
        if hourly_commitment < min_commitment:
            logger.info(
                f"{sp_type['name']} SP calculated commitment ${hourly_commitment:.4f}/h "
                f"is below minimum ${min_commitment:.4f}/h - skipping"
            )
            continue

        purchase_plan = {
            "sp_type": key,
            "hourly_commitment": hourly_commitment,
            "payment_option": config.get(
                sp_type["payment_option_config"], sp_type["default_payment"]
            ),
            "strategy": "fixed",
            "purchase_percent": purchase_percent,
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
            f"{sp_type['name']} SP purchase planned: ${hourly_commitment:.4f}/h "
            f"({purchase_percent:.2f}% of spend, gap: {coverage_gap:.2f}%)"
        )

    logger.info(f"Fixed strategy purchase need calculated: {len(purchase_plans)} plans")
    return purchase_plans

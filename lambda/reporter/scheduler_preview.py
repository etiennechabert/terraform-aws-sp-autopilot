"""
Scheduler Preview - Simulates scheduler purchase decisions for reporting.

This module calculates what the scheduler would purchase if it ran right now,
using the currently configured strategy (fixed, dichotomy, or follow_aws), and
compares it with the optimal commitment level using the knee-point algorithm.
"""

import logging
import sys
from pathlib import Path
from typing import Any


logger = logging.getLogger(__name__)


def calculate_scheduler_preview(
    config: dict[str, Any],
    clients: dict[str, Any],
    coverage_data: dict[str, Any],
    savings_data: dict[str, Any],
) -> dict[str, Any]:
    """
    Calculate what the scheduler would purchase right now and compare with optimal.

    Args:
        config: Reporter config (includes scheduler strategy params)
        clients: AWS clients dict (ce, savingsplans, s3, sns)
        coverage_data: Already-fetched coverage data from SpendingAnalyzer
        savings_data: Already-fetched savings data from get_savings_plans_summary

    Returns:
        dict: Preview data structure with scheduled and optimal recommendations
    """
    strategy_type = config.get("purchase_strategy_type", "fixed")

    try:
        # Calculate scheduled purchases using scheduler strategy
        scheduled_purchases = _calculate_scheduled_purchases(
            config, clients, coverage_data, strategy_type
        )

        # Calculate optimal purchases using knee-point algorithm
        optimal_analysis = _calculate_optimal_commitment(coverage_data, savings_data)

        # Enrich with efficiency comparison
        enriched_purchases = _enrich_with_optimization(
            scheduled_purchases, optimal_analysis, coverage_data
        )

        return {
            "strategy": strategy_type,
            "purchases": enriched_purchases,
            "has_recommendations": len(enriched_purchases) > 0,
            "error": None,
        }

    except Exception as e:
        logger.error(f"Failed to calculate scheduler preview: {e}", exc_info=True)
        return {
            "strategy": strategy_type,
            "purchases": [],
            "has_recommendations": False,
            "error": str(e),
        }


def _calculate_scheduled_purchases(
    config: dict[str, Any],
    clients: dict[str, Any],
    coverage_data: dict[str, Any],
    strategy_type: str,
) -> list[dict[str, Any]]:
    """
    Calculate scheduled purchases using the configured strategy.

    Imports scheduler strategy modules and calls the appropriate function.
    """
    # Import scheduler strategy modules
    scheduler_dir = Path(__file__).parent.parent / "scheduler"
    if str(scheduler_dir) not in sys.path:
        sys.path.insert(0, str(scheduler_dir))

    try:
        from dichotomy_strategy import calculate_purchase_need_dichotomy
        from fixed_strategy import calculate_purchase_need_fixed
        from follow_aws_strategy import calculate_purchase_need_follow_aws

        strategy_functions = {
            "fixed": calculate_purchase_need_fixed,
            "dichotomy": calculate_purchase_need_dichotomy,
            "follow_aws": calculate_purchase_need_follow_aws,
        }

        strategy_func = strategy_functions.get(strategy_type)
        if not strategy_func:
            logger.warning(f"Unknown strategy type: {strategy_type}, defaulting to fixed")
            strategy_func = calculate_purchase_need_fixed

        # Call strategy function (coverage_data structure matches spending_data structure)
        purchase_plans = strategy_func(config, clients, coverage_data)

        # Enrich with coverage impact
        enriched = []
        for plan in purchase_plans:
            sp_type = plan["sp_type"]
            sp_data = coverage_data.get(sp_type, {})
            summary = sp_data.get("summary", {})

            current_coverage = summary.get("avg_coverage_total", 0.0)
            avg_hourly_total = summary.get("avg_hourly_total", 0.0)

            # Calculate projected coverage
            purchase_percent = plan.get("purchase_percent", 0.0)
            projected_coverage = min(current_coverage + purchase_percent, 100.0)

            enriched.append(
                {
                    "sp_type": sp_type,
                    "hourly_commitment": plan["hourly_commitment"],
                    "purchase_percent": purchase_percent,
                    "current_coverage": current_coverage,
                    "projected_coverage": projected_coverage,
                    "payment_option": plan["payment_option"],
                    "term": plan["term"],
                }
            )

        return enriched

    except ImportError as e:
        logger.error(f"Failed to import scheduler strategies: {e}")
        raise
    except Exception as e:
        logger.error(f"Error calculating scheduled purchases: {e}", exc_info=True)
        raise


def _calculate_optimal_commitment(
    coverage_data: dict[str, Any], savings_data: dict[str, Any]
) -> dict[str, dict[str, Any]]:
    """
    Calculate optimal commitment using PurchaseOptimizer knee-point algorithm.

    Extracts actual discount rate from savings_data and calculates optimal
    commitment for each SP type based on percentile analysis.
    """
    from shared.purchase_optimizer import PurchaseOptimizer

    optimizer = PurchaseOptimizer()

    # Extract discount rates from actual savings data (breakdown by type)
    breakdown_by_type = savings_data.get("actual_savings", {}).get("breakdown_by_type", {})

    # Default discount rate if no active plans exist yet
    default_discount_rate = 0.30  # 30% default

    optimal_results = {}

    for sp_type in ["compute", "database", "sagemaker"]:
        # Get type-specific discount rate
        sp_type_name = sp_type.capitalize()
        type_savings = breakdown_by_type.get(sp_type_name, {})
        discount_rate = type_savings.get("savings_percentage", 0.0) / 100.0

        # Use default if no discount rate available
        if discount_rate == 0.0:
            discount_rate = default_discount_rate
            logger.info(
                f"{sp_type_name}: No active plans, using default discount rate {discount_rate * 100:.0f}%"
            )

        # Calculate optimal commitment (aggressiveness = 1.0 for full recommendation)
        optimal_result = optimizer.calculate_optimal_commitment(
            {sp_type: coverage_data.get(sp_type, {})}, discount_rate, aggressiveness=1.0
        )

        optimal_results[sp_type] = optimal_result.get(sp_type, {})

    return optimal_results


def _enrich_with_optimization(
    scheduled_purchases: list[dict[str, Any]],
    optimal_analysis: dict[str, dict[str, Any]],
    coverage_data: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Enrich scheduled purchases with optimal analysis and efficiency metrics.

    Compares scheduled commitment with optimal commitment and flags over-commitment.
    """
    enriched = []

    for scheduled in scheduled_purchases:
        sp_type = scheduled["sp_type"]
        optimal = optimal_analysis.get(sp_type, {})

        # Extract optimal values
        optimal_commit = optimal.get("recommended_hourly_commitment", 0.0)
        analysis = optimal.get("analysis", {})
        target_percentile = analysis.get("target_percentile", 0)
        discount_rate = analysis.get("discount_rate", 0.0)
        breakeven_hours_pct = analysis.get("breakeven_hours_pct", 0.0)

        # Calculate efficiency ratio
        sched_commit = scheduled["hourly_commitment"]
        efficiency_ratio = sched_commit / optimal_commit if optimal_commit > 0 else 0.0

        # Determine efficiency status
        if efficiency_ratio <= 1.1:
            status = "optimal"
            message = "Scheduled purchase is at optimal level"
        elif efficiency_ratio <= 1.2:
            status = "near_optimal"
            message = f"Scheduled purchase is {(efficiency_ratio - 1.0) * 100:.0f}% above optimal"
        else:
            status = "over_committed"
            message = f"Scheduled purchase is {(efficiency_ratio - 1.0) * 100:.0f}% above optimal (diminishing returns)"

        enriched.append(
            {
                "sp_type": sp_type,
                "scheduled": {
                    "hourly_commitment": sched_commit,
                    "purchase_percent": scheduled["purchase_percent"],
                    "current_coverage": scheduled["current_coverage"],
                    "projected_coverage": scheduled["projected_coverage"],
                },
                "optimal": {
                    "hourly_commitment": optimal_commit,
                    "target_percentile": target_percentile,
                    "discount_rate": discount_rate,
                    "breakeven_hours_pct": breakeven_hours_pct,
                },
                "efficiency": {
                    "ratio": efficiency_ratio,
                    "status": status,
                    "message": message,
                },
                "payment_option": scheduled["payment_option"],
                "term": scheduled["term"],
            }
        )

    return enriched

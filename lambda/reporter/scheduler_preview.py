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
    Calculate what the scheduler would purchase right now.

    Args:
        config: Reporter config (includes scheduler strategy params)
        clients: AWS clients dict (ce, savingsplans, s3, sns)
        coverage_data: Already-fetched coverage data from SpendingAnalyzer
        savings_data: Already-fetched savings data from get_savings_plans_summary

    Returns:
        dict: Preview data structure with scheduled purchase recommendations
    """
    strategy_type = config.get("purchase_strategy_type", "fixed")

    try:
        # Calculate scheduled purchases using scheduler strategy
        scheduled_purchases = _calculate_scheduled_purchases(
            config, clients, coverage_data, strategy_type
        )

        return {
            "strategy": strategy_type,
            "purchases": scheduled_purchases,
            "has_recommendations": len(scheduled_purchases) > 0,
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

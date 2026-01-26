"""
Scheduler Preview - Simulates scheduler purchase decisions for reporting.

This module calculates what all three scheduler strategies (fixed, dichotomy,
follow_aws) would purchase if they ran right now, allowing comparison between strategies.
"""

import logging
import sys
from pathlib import Path
from typing import Any


logger = logging.getLogger(__name__)


def _get_strategy_config(
    base_config: dict[str, Any], strategy_type: str, is_configured: bool
) -> dict[str, Any]:
    """
    Get configuration for a strategy with appropriate defaults.

    For the configured strategy, uses actual user config.
    For non-configured strategies, uses sensible strategy-specific defaults.

    Args:
        base_config: Base configuration from user
        strategy_type: Strategy type (fixed, dichotomy, follow_aws)
        is_configured: Whether this is the user's configured strategy

    Returns:
        dict: Configuration with strategy-appropriate defaults
    """
    config = base_config.copy()

    # If this is the configured strategy, use actual config as-is
    if is_configured:
        return config

    # For non-configured strategies, override with strategy-specific defaults
    if strategy_type == "fixed":
        # Fixed strategy defaults: conservative 10% purchases
        config["max_purchase_percent"] = 10.0
        config["min_purchase_percent"] = 1.0
        config["coverage_target_percent"] = 90.0

    elif strategy_type == "dichotomy":
        # Dichotomy strategy defaults: more aggressive with halving from 50%
        config["max_purchase_percent"] = 50.0
        config["min_purchase_percent"] = 1.0
        config["coverage_target_percent"] = 90.0
        config["dichotomy_initial_percent"] = 50.0

    # follow_aws doesn't need these parameters (uses AWS recommendations)

    return config


def calculate_scheduler_preview(
    config: dict[str, Any],
    clients: dict[str, Any],
    coverage_data: dict[str, Any],
    savings_data: dict[str, Any],
) -> dict[str, Any]:
    """
    Calculate what each scheduler strategy would purchase right now.

    Each non-configured strategy uses sensible defaults:
    - Fixed: 10% max purchase, 90% target (conservative)
    - Dichotomy: 50% max purchase, 1% min, 90% target (aggressive)
    - Follow AWS: Uses AWS recommendations (no parameters)

    Args:
        config: Reporter config (includes scheduler strategy params)
        clients: AWS clients dict (ce, savingsplans, s3, sns)
        coverage_data: Already-fetched coverage data from SpendingAnalyzer
        savings_data: Already-fetched savings data from get_savings_plans_summary

    Returns:
        dict: Preview data with all three strategies' recommendations
    """
    configured_strategy = config.get("purchase_strategy_type", "fixed")

    try:
        # Calculate purchases for all three strategies
        all_strategies = {}

        for strategy_type in ["fixed", "dichotomy", "follow_aws"]:
            try:
                # Get strategy-specific config (with defaults for non-configured strategies)
                strategy_config = _get_strategy_config(
                    config, strategy_type, is_configured=(strategy_type == configured_strategy)
                )

                purchases = _calculate_scheduled_purchases(
                    strategy_config, clients, coverage_data, strategy_type
                )
                all_strategies[strategy_type] = {
                    "purchases": purchases,
                    "has_recommendations": len(purchases) > 0,
                    "error": None,
                }
            except Exception as e:
                logger.error(f"Failed to calculate {strategy_type} strategy: {e}", exc_info=True)
                all_strategies[strategy_type] = {
                    "purchases": [],
                    "has_recommendations": False,
                    "error": str(e),
                }

        return {
            "configured_strategy": configured_strategy,
            "strategies": all_strategies,
            "error": None,
        }

    except Exception as e:
        logger.error(f"Failed to calculate scheduler preview: {e}", exc_info=True)
        return {
            "configured_strategy": configured_strategy,
            "strategies": {},
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
            avg_hourly_uncovered = summary.get("avg_hourly_uncovered", 0.0)
            hourly_commitment = plan["hourly_commitment"]

            # Calculate purchase_percent if not provided (Follow AWS case)
            if "purchase_percent" in plan:
                # Fixed/Dichotomy provide this
                purchase_percent = plan["purchase_percent"]
            # Follow AWS: calculate from hourly commitment and uncovered spend
            elif avg_hourly_uncovered > 0:
                purchase_percent = (hourly_commitment / avg_hourly_uncovered) * 100.0
            elif avg_hourly_total > 0:
                # If uncovered is 0, calculate as % of total spend
                purchase_percent = (hourly_commitment / avg_hourly_total) * 100.0
            else:
                # No spend data available
                purchase_percent = 0.0

            # Calculate projected coverage
            projected_coverage = min(current_coverage + purchase_percent, 100.0)

            enriched.append(
                {
                    "sp_type": sp_type,
                    "hourly_commitment": hourly_commitment,
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

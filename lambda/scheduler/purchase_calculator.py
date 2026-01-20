"""
Purchase Calculator Module - Strategy dispatcher and shared utilities.

This module contains:
1. Strategy registry and dispatcher (calculate_purchase_need)

Strategy Pattern:
- Each strategy is implemented in its own module (fixed_strategy.py, dichotomy_strategy.py, follow_aws_strategy.py)
- Each strategy handles its own purchase limits (max_purchase_percent, min_commitment_per_plan)
- Strategies are registered in PURCHASE_STRATEGIES registry
- Contributors can add new strategies by:
  1. Creating a new strategy module (e.g., aggressive_strategy.py)
  2. Implementing the strategy function: (config, clients, spending_data?) -> purchase_plans
  3. Strategy handles its own data fetching and limit enforcement
  4. Importing and registering in PURCHASE_STRATEGIES below
"""

import logging
from typing import Any, Callable

from dichotomy_strategy import calculate_purchase_need_dichotomy
from fixed_strategy import calculate_purchase_need_fixed
from follow_aws_strategy import calculate_purchase_need_follow_aws


# Configure logging
logger = logging.getLogger()


# ============================================================================
# Strategy Registry - Add new strategies here
# ============================================================================

# Type alias for strategy functions
# Strategies receive optional spending_data - handler pre-fetches if strategy needs it
StrategyFunction = Callable[
    [dict[str, Any], dict[str, Any], dict[str, Any] | None], list[dict[str, Any]]
]


# Registry mapping strategy names to their implementation functions
# Contributors: Add new strategies by importing and registering here
PURCHASE_STRATEGIES: dict[str, StrategyFunction] = {
    "fixed": calculate_purchase_need_fixed,
    "dichotomy": calculate_purchase_need_dichotomy,
    "follow_aws": calculate_purchase_need_follow_aws,
}


def calculate_purchase_need(
    config: dict[str, Any], clients: dict[str, Any], spending_data: dict[str, Any] | None = None
) -> list[dict[str, Any]]:
    """
    Calculate required purchases to reach target coverage using configured strategy.

    This function acts as a dispatcher to the appropriate strategy implementation.
    Handler pre-fetches spending_data for strategies that need it (fixed/dichotomy).

    Args:
        config: Configuration dictionary (must include "purchase_strategy_type")
        clients: Dictionary of AWS clients (ce, savingsplans, etc.)
        spending_data: Optional pre-fetched spending analysis (for fixed/dichotomy strategies)

    Returns:
        list: Purchase plans to execute

    Raises:
        ValueError: If configured strategy is not registered
    """
    strategy_type = config.get("purchase_strategy_type")

    if not strategy_type:
        available_strategies = ", ".join(PURCHASE_STRATEGIES.keys())
        raise ValueError(
            f"Missing required configuration 'purchase_strategy_type'. "
            f"Available strategies: {available_strategies}"
        )

    logger.info(f"Using purchase strategy: {strategy_type}")

    # Lookup strategy function from registry
    strategy_func = PURCHASE_STRATEGIES.get(strategy_type)

    if not strategy_func:
        available_strategies = ", ".join(PURCHASE_STRATEGIES.keys())
        raise ValueError(
            f"Unknown purchase strategy '{strategy_type}'. "
            f"Available strategies: {available_strategies}"
        )

    # Call strategy function with optional spending_data
    return strategy_func(config, clients, spending_data)


def apply_purchase_limits(
    config: dict[str, Any], purchase_plans: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """
    DEPRECATED: Apply max_purchase_percent limit to planned purchases.

    This function is no longer used. Strategies now handle their own limits internally.
    Kept for backward compatibility with existing tests.

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

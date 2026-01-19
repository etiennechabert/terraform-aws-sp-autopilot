"""
Purchase Calculator Module - Strategy dispatcher and shared utilities.

This module contains:
1. Strategy registry and dispatcher (calculate_purchase_need)
2. Shared utilities (apply_purchase_limits)

Strategy Pattern:
- Each strategy is implemented in its own module (fixed_strategy.py, dichotomy_strategy.py, follow_aws_strategy.py)
- Strategies are registered in PURCHASE_STRATEGIES registry
- Contributors can add new strategies by:
  1. Creating a new strategy module (e.g., aggressive_strategy.py)
  2. Implementing the strategy function: (config, coverage, recommendations) -> purchase_plans
  3. Importing and registering in PURCHASE_STRATEGIES below
"""

import logging
from typing import Any, Callable, Dict, List


# Configure logging
logger = logging.getLogger()


# ============================================================================
# Strategy Registry - Add new strategies here
# ============================================================================

# Type alias for strategy functions
StrategyFunction = Callable[
    [Dict[str, Any], Dict[str, float], Dict[str, Any]], List[Dict[str, Any]]
]

# Import strategy implementations
from dichotomy_strategy import calculate_purchase_need_dichotomy
from fixed_strategy import calculate_purchase_need_fixed
from follow_aws_strategy import calculate_purchase_need_follow_aws


# Registry mapping strategy names to their implementation functions
# Contributors: Add new strategies by importing and registering here
PURCHASE_STRATEGIES: Dict[str, StrategyFunction] = {
    "fixed": calculate_purchase_need_fixed,
    "dichotomy": calculate_purchase_need_dichotomy,
    "follow_aws": calculate_purchase_need_follow_aws,
}


def calculate_purchase_need(
    config: Dict[str, Any], coverage: Dict[str, float], recommendations: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Calculate required purchases to reach target coverage using configured strategy.

    This function acts as a dispatcher to the appropriate strategy implementation.
    Strategies are pluggable - see PURCHASE_STRATEGIES registry.

    Args:
        config: Configuration dictionary (must include "purchase_strategy_type")
        coverage: Current coverage by SP type
        recommendations: AWS recommendations

    Returns:
        list: Purchase plans to execute

    Raises:
        ValueError: If configured strategy is not registered
    """
    strategy_type = config.get("purchase_strategy_type", "follow_aws")

    logger.info(f"Using purchase strategy: {strategy_type}")

    # Lookup strategy function from registry
    strategy_func = PURCHASE_STRATEGIES.get(strategy_type)

    if not strategy_func:
        available_strategies = ", ".join(PURCHASE_STRATEGIES.keys())
        raise ValueError(
            f"Unknown purchase strategy '{strategy_type}'. "
            f"Available strategies: {available_strategies}"
        )

    # Call strategy function
    return strategy_func(config, coverage, recommendations)


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

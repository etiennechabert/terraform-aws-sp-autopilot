"""
Purchase Calculator Module - Strategy dispatcher and shared utilities.

This module contains:
1. Strategy registry and dispatcher (calculate_purchase_need)
2. Shared utilities (apply_purchase_limits, split_by_term)

Strategy Pattern:
- Each strategy is implemented in its own module (simple_strategy.py, dichotomy_strategy.py)
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
StrategyFunction = Callable[[Dict[str, Any], Dict[str, float], Dict[str, Any]], List[Dict[str, Any]]]

# Import strategy implementations
from simple_strategy import calculate_purchase_need_simple
from dichotomy_strategy import calculate_purchase_need_dichotomy

# Registry mapping strategy names to their implementation functions
# Contributors: Add new strategies by importing and registering here
PURCHASE_STRATEGIES: Dict[str, StrategyFunction] = {
    "simple": calculate_purchase_need_simple,
    "dichotomy": calculate_purchase_need_dichotomy,
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
    strategy_type = config.get("purchase_strategy_type", "simple")

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

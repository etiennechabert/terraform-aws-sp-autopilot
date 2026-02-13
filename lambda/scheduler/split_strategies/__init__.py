from typing import Any

from split_strategies.dichotomy_split import calculate_dichotomy_split
from split_strategies.linear_split import calculate_linear_split
from split_strategies.one_shot_split import calculate_one_shot_split


SPLIT_STRATEGIES = {
    "one_shot": calculate_one_shot_split,
    "linear": calculate_linear_split,
    "dichotomy": calculate_dichotomy_split,
}


def calculate_split(
    current_coverage: float, target_coverage: float, config: dict[str, Any]
) -> float:
    """
    Calculate the purchase percentage for this cycle using the configured split strategy.

    Args:
        current_coverage: Current coverage percentage
        target_coverage: Target coverage percentage
        config: Configuration dictionary (must include split_strategy_type)

    Returns:
        Purchase percentage (fraction of total spend to purchase this cycle)
    """
    split_type = config["split_strategy_type"]
    split_func = SPLIT_STRATEGIES.get(split_type)
    if not split_func:
        available = ", ".join(SPLIT_STRATEGIES.keys())
        raise ValueError(f"Unknown split strategy '{split_type}'. Available: {available}")
    return split_func(current_coverage, target_coverage, config)

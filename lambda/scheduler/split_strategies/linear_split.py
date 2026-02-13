from typing import Any


def calculate_linear_split(
    current_coverage: float, target_coverage: float, config: dict[str, Any]
) -> float:
    """
    Linear split: purchase up to step_percent of total spend per cycle.

    step_percent is interpreted as a percentage of total spend (same as old max_purchase_percent).
    """
    gap = target_coverage - current_coverage
    if gap <= 0:
        return 0.0

    step_percent = config.get("linear_step_percent", config.get("max_purchase_percent", 10.0))
    return min(gap, step_percent)

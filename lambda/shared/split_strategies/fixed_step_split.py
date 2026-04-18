from typing import Any


def calculate_fixed_step_split(
    current_coverage: float, target_coverage: float, config: dict[str, Any]
) -> float:
    """
    Fixed step split: purchase up to step_percent of total spend per cycle.

    step_percent is interpreted as a percentage of total spend (same as old max_purchase_percent).
    """
    gap = target_coverage - current_coverage
    if gap <= 0:
        return 0.0

    step_percent = config["fixed_step_percent"]
    return min(gap, step_percent)

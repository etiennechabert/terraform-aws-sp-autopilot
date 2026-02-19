from typing import Any


def calculate_one_shot_split(
    current_coverage: float, target_coverage: float, _config: dict[str, Any]
) -> float:
    gap = target_coverage - current_coverage
    return max(0.0, gap)

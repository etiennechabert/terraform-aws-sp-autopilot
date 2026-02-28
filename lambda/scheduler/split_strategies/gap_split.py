from typing import Any


def calculate_gap_split(
    current_coverage: float, target_coverage: float, config: dict[str, Any]
) -> float:
    gap = target_coverage - current_coverage
    if gap <= 0:
        return 0.0

    divider = config["gap_split_divider"]
    min_purchase = config["min_purchase_percent"]
    max_purchase = config.get("max_purchase_percent")

    divided = gap / divider

    if max_purchase is not None and divided > max_purchase:
        divided = max_purchase
    divided = max(divided, min_purchase)
    if gap < min_purchase:
        divided = gap

    return round(divided, 1)

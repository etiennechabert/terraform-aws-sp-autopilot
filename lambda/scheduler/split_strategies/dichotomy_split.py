from typing import Any


def calculate_dichotomy_purchase_percent(
    current_coverage_percent: float,
    target_coverage_percent: float,
    max_purchase_percent: float,
    min_purchase_percent: float,
) -> float:
    """
    Calculate purchase percentage using dichotomy strategy.

    Always tries max_purchase_percent first, then halves until the purchase
    doesn't cause coverage to exceed the target.
    """
    coverage_gap_percent = target_coverage_percent - current_coverage_percent

    if coverage_gap_percent <= 0:
        return 0.0

    if coverage_gap_percent < min_purchase_percent:
        return min_purchase_percent

    purchase_percent = max_purchase_percent

    while current_coverage_percent + purchase_percent > target_coverage_percent:
        purchase_percent = purchase_percent / 2.0
        if purchase_percent < min_purchase_percent:
            return min_purchase_percent

    if purchase_percent < min_purchase_percent:
        return min_purchase_percent

    return round(purchase_percent, 1)


def calculate_dichotomy_split(
    current_coverage: float, target_coverage: float, config: dict[str, Any]
) -> float:
    max_purchase_percent = config.get("max_purchase_percent", 50.0)
    min_purchase_percent = config.get("min_purchase_percent", 1.0)

    return calculate_dichotomy_purchase_percent(
        current_coverage, target_coverage, max_purchase_percent, min_purchase_percent
    )

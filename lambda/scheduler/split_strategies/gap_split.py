from typing import Any


TERM_TO_MONTHS = {"ONE_YEAR": 12, "THREE_YEAR": 36}


def _resolve_min_purchase(config: dict[str, Any]) -> float:
    """Resolve min_purchase_percent: use explicit value or auto-derive from term.

    Auto-derivation: 100% / term_months. For 1-year terms this gives ~8.33%,
    for 3-year terms ~2.78%. This ensures at most one plan per month of the term,
    preventing excessive fragmentation while still distributing renewals.
    """
    explicit = config.get("min_purchase_percent")
    if explicit is not None:
        return explicit

    # Derive from the longest term across enabled SP types
    terms = []
    if config.get("enable_compute_sp"):
        terms.append(config.get("compute_sp_term", "ONE_YEAR"))
    if config.get("enable_sagemaker_sp"):
        terms.append(config.get("sagemaker_sp_term", "ONE_YEAR"))
    if config.get("enable_database_sp"):
        terms.append("ONE_YEAR")  # database SP is always 1-year

    term_months = max((TERM_TO_MONTHS.get(t, 12) for t in terms), default=12)
    return round(100.0 / term_months, 2)


def calculate_gap_split(
    current_coverage: float, target_coverage: float, config: dict[str, Any]
) -> float:
    gap = target_coverage - current_coverage
    if gap <= 0:
        return 0.0

    divider = config["gap_split_divider"]
    min_purchase = _resolve_min_purchase(config)
    max_purchase = config.get("max_purchase_percent")

    divided = gap / divider

    if max_purchase is not None and divided > max_purchase:
        divided = max_purchase
    divided = max(divided, min_purchase)
    if gap < min_purchase:
        divided = gap

    return round(divided, 1)

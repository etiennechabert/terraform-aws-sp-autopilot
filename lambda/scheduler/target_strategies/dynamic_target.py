import logging
from typing import Any

from shared.optimal_coverage import calculate_strategies


logger = logging.getLogger()

VALID_RISK_LEVELS = ["prudent", "min_hourly", "optimal", "maximum"]


def resolve_dynamic(
    config: dict[str, Any],
    spending_data: dict[str, Any] | None = None,
    sp_type_key: str | None = None,
) -> float:
    risk_level = config["dynamic_risk_level"]

    if not spending_data:
        raise ValueError("Dynamic target strategy requires spending data")

    types_to_check = [sp_type_key] if sp_type_key else ["compute", "database", "sagemaker"]

    hourly_costs = []
    for key in types_to_check:
        sp_data = spending_data.get(key)
        if not sp_data:
            continue
        for item in sp_data.get("timeseries", []):
            total = item.get("total", 0.0)
            if total > 0:
                hourly_costs.append(total)

    if not hourly_costs:
        logger.warning(
            f"No hourly cost data for dynamic target ({sp_type_key or 'all'}), falling back to 90%"
        )
        return 90.0

    savings_percentage = (
        config.get(f"{sp_type_key}_savings_percentage", config["savings_percentage"])
        if sp_type_key
        else config["savings_percentage"]
    )

    prudent_pct = config.get("prudent_percentage", 90.0)
    strategies = calculate_strategies(hourly_costs, savings_percentage, prudent_pct=prudent_pct)
    coverage_hourly = strategies[risk_level]

    min_hourly = min(hourly_costs)
    if min_hourly <= 0:
        return 90.0

    target_percent = (coverage_hourly / min_hourly) * 100.0

    logger.info(
        f"Dynamic target ({risk_level}, {sp_type_key or 'all'}): "
        f"coverage=${coverage_hourly:.4f}/hr, min=${min_hourly:.4f}/hr, target={target_percent:.1f}%"
    )

    return target_percent

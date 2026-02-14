import logging
from typing import Any

from shared.optimal_coverage import calculate_strategies


logger = logging.getLogger()

VALID_RISK_LEVELS = ["too_prudent", "min_hourly", "balanced", "aggressive"]


def resolve_dynamic(config: dict[str, Any], spending_data: dict[str, Any] | None = None) -> float:
    """
    Resolve target coverage dynamically based on risk level and spending data.

    Uses the same strategy calculations as the GH-Pages simulator.
    Returns coverage as a percentage of min-hourly cost.

    Risk levels:
    - too_prudent: 80% of min-hourly
    - min_hourly: 100% of min-hourly (always safe)
    - balanced: Knee-point (where marginal efficiency drops to 30% of peak)
    - aggressive: Optimal coverage (maximum net savings)
    """
    risk_level = config["dynamic_risk_level"]
    savings_percentage = config.get("savings_percentage", 30.0)

    if not spending_data:
        raise ValueError("Dynamic target strategy requires spending data")

    all_hourly_costs = []
    for sp_type_key in ["compute", "database", "sagemaker"]:
        sp_data = spending_data.get(sp_type_key)
        if not sp_data:
            continue
        timeseries = sp_data.get("timeseries", [])
        for item in timeseries:
            total = item.get("total", 0.0)
            if total > 0:
                all_hourly_costs.append(total)

    if not all_hourly_costs:
        logger.warning("No hourly cost data available for dynamic target, falling back to 90%")
        return 90.0

    strategies = calculate_strategies(all_hourly_costs, savings_percentage)
    coverage_hourly = strategies[risk_level]

    avg_hourly = sum(all_hourly_costs) / len(all_hourly_costs)
    if avg_hourly <= 0:
        return 90.0

    target_percent = (coverage_hourly / avg_hourly) * 100.0

    logger.info(
        f"Dynamic target ({risk_level}): coverage=${coverage_hourly:.4f}/hr, "
        f"avg_hourly=${avg_hourly:.4f}/hr, target={target_percent:.1f}%"
    )

    return target_percent

"""
Purchase Calculator Module - Two-phase strategy pipeline.

Phase 1: Resolve target coverage (fixed/dynamic/aws)
Phase 2: Calculate split for each SP type (one_shot/linear/dichotomy)

AWS target short-circuits to follow_aws_strategy.py (special path).
"""

import logging
from typing import Any

from follow_aws_strategy import calculate_purchase_need_follow_aws
from split_strategies import calculate_split
from target_strategies import resolve_target

from shared import sp_calculations


logger = logging.getLogger()

SP_TYPES = [
    {
        "key": "compute",
        "enabled_config": "enable_compute_sp",
        "payment_option_config": "compute_sp_payment_option",
        "name": "Compute",
    },
    {
        "key": "database",
        "enabled_config": "enable_database_sp",
        "payment_option_config": "database_sp_payment_option",
        "name": "Database",
    },
    {
        "key": "sagemaker",
        "enabled_config": "enable_sagemaker_sp",
        "payment_option_config": "sagemaker_sp_payment_option",
        "name": "SageMaker",
    },
]


def _get_term(key: str, config: dict[str, Any]) -> str:
    if key == "compute":
        return config.get("compute_sp_term", "THREE_YEAR")
    if key == "sagemaker":
        return config.get("sagemaker_sp_term", "THREE_YEAR")
    return "ONE_YEAR"


def _process_sp_type(
    sp_type: dict[str, Any],
    config: dict[str, Any],
    spending_data: dict[str, Any],
    target_coverage: float,
) -> dict[str, Any] | None:
    if not config[sp_type["enabled_config"]]:
        return None

    key = sp_type["key"]
    data = spending_data.get(key)
    if not data:
        logger.info(f"{sp_type['name']} SP - No spending data available")
        return None

    summary = data["summary"]
    current_coverage_avg = summary["avg_coverage_total"]
    avg_hourly_total = summary["avg_hourly_total"]
    avg_hourly_covered = summary["avg_hourly_covered"]

    timeseries = data.get("timeseries", [])
    total_costs = [item.get("total", 0.0) for item in timeseries if item.get("total", 0.0) > 0]
    min_hourly = min(total_costs) if total_costs else avg_hourly_total

    avg_to_min_ratio = (
        avg_hourly_total / min_hourly if min_hourly > 0 and avg_hourly_total > 0 else 1.0
    )
    current_coverage = current_coverage_avg * avg_to_min_ratio
    target_coverage = target_coverage * avg_to_min_ratio

    coverage_gap = target_coverage - current_coverage

    logger.info(
        f"{sp_type['name']} SP - Current: {current_coverage:.2f}%, "
        f"Target: {target_coverage:.2f}%, Gap: {coverage_gap:.2f}%, "
        f"Avg hourly spend: ${avg_hourly_total:.4f}/h, Min hourly: ${min_hourly:.4f}/h"
    )

    if coverage_gap <= 0:
        logger.info(f"{sp_type['name']} SP coverage already meets or exceeds target")
        return None

    if avg_hourly_total <= 0:
        logger.info(f"{sp_type['name']} SP has zero spend - skipping")
        return None

    purchase_percent = calculate_split(current_coverage, target_coverage, config)
    savings_pct = config.get(f"{key}_savings_percentage", config.get("savings_percentage", 30.0))
    od_coverage_to_add = min_hourly * (purchase_percent / 100.0) if purchase_percent > 0 else 0
    hourly_commitment = sp_calculations.commitment_from_coverage(od_coverage_to_add, savings_pct)

    min_commitment = config.get("min_commitment_per_plan", 0.001)
    if purchase_percent <= 0 or hourly_commitment < min_commitment:
        if hourly_commitment > 0:
            logger.info(
                f"{sp_type['name']} SP calculated commitment ${hourly_commitment:.4f}/h "
                f"is below minimum ${min_commitment:.4f}/h - skipping"
            )
        return None

    split_type = config["split_strategy_type"]

    logger.info(
        f"{sp_type['name']} SP purchase planned: ${hourly_commitment:.4f}/h "
        f"({purchase_percent:.2f}% of spend, gap: {coverage_gap:.2f}%)"
    )

    return {
        "strategy": f"{config['target_strategy_type']}+{split_type}",
        "sp_type": key,
        "hourly_commitment": hourly_commitment,
        "purchase_percent": purchase_percent,
        "estimated_savings_percentage": savings_pct,
        "payment_option": config[sp_type["payment_option_config"]],
        "term": _get_term(key, config),
        "details": {
            "coverage": {
                "current": current_coverage,
                "target": target_coverage,
                "gap": coverage_gap,
            },
            "spending": {
                "total": avg_hourly_total,
                "covered": avg_hourly_covered,
                "uncovered": avg_hourly_total - avg_hourly_covered,
            },
            "strategy_params": {
                "target_strategy": config["target_strategy_type"],
                "split_strategy": split_type,
                "max_purchase_percent": config.get("max_purchase_percent"),
                "min_purchase_percent": config.get("min_purchase_percent"),
            },
        },
    }


def _ensure_savings_rates(config: dict[str, Any], clients: dict[str, Any]) -> dict[str, Any]:
    """Fetch actual per-type savings rates from AWS if not already in config."""
    from shared.savings_plans_metrics import get_savings_plans_metrics

    config = config.copy()
    for sp_type in SP_TYPES:
        key = sp_type["key"]
        config_key = f"{key}_savings_percentage"
        if config_key in config or not config.get(sp_type["enabled_config"]):
            continue
        try:
            metrics = get_savings_plans_metrics(
                clients["ce"],
                key,
                config.get("lookback_days", 13),
                config.get("granularity", "DAILY"),
            )
            if metrics["savings_percentage"] > 0:
                config[config_key] = metrics["savings_percentage"]
                logger.info(
                    f"{sp_type['name']} SP actual savings rate: {metrics['savings_percentage']:.1f}%"
                )
        except Exception:
            logger.debug(f"Could not fetch savings rate for {key}, using default")
    return config


def calculate_purchase_need(
    config: dict[str, Any], clients: dict[str, Any], spending_data: dict[str, Any] | None = None
) -> list[dict[str, Any]]:
    """
    Calculate required purchases using configured target + split strategy.

    Two-phase pipeline:
    1. resolve_target() -> coverage target %
    2. For each SP type: calculate_split() -> purchase %

    AWS target short-circuits to follow_aws_strategy.py.
    """
    target_strategy = config.get("target_strategy_type")
    split_strategy = config.get("split_strategy_type")

    if not target_strategy:
        raise ValueError("Missing required configuration 'target_strategy_type'")

    logger.info(f"Using target strategy: {target_strategy}, split strategy: {split_strategy}")

    # AWS target -> short-circuit to follow_aws special path
    if target_strategy == "aws":
        return calculate_purchase_need_follow_aws(config, clients, spending_data)

    # Fetch actual savings rates from existing SP plans (skips if already in config)
    config = _ensure_savings_rates(config, clients)

    if spending_data is None:
        from shared.spending_analyzer import SpendingAnalyzer

        analyzer = SpendingAnalyzer(clients["savingsplans"], clients["ce"])
        spending_data = analyzer.analyze_current_spending(config)
        spending_data.pop("_unknown_services", None)

    purchase_plans = []
    for sp_type in SP_TYPES:
        target_coverage = resolve_target(config, spending_data, sp_type_key=sp_type["key"])
        if target_coverage is None:
            continue
        logger.info(f"{sp_type['name']} SP resolved target: {target_coverage:.2f}%")
        plan = _process_sp_type(sp_type, config, spending_data, target_coverage)
        if plan:
            purchase_plans.append(plan)

    logger.info(f"Purchase need calculated: {len(purchase_plans)} plans")
    return purchase_plans

"""
Scheduler Preview - Simulates scheduler purchase decisions for reporting.

Shows what different target+split strategy combinations would purchase
if they ran right now, allowing comparison between strategies.
"""

import logging
import os
import sys
from typing import Any

from shared import sp_calculations


# purchase_calculator lives in the scheduler directory; in Lambda archives both
# are at the root, but during tests we need to add the scheduler path explicitly.
_scheduler_dir = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scheduler"
)
if _scheduler_dir not in sys.path:
    sys.path.append(_scheduler_dir)


logger = logging.getLogger(__name__)


DEFAULT_COMPARISONS = [
    {"target": "fixed", "split": "linear", "label": "Fixed + Linear"},
    {"target": "dynamic", "split": "dichotomy", "label": "Dynamic + Dichotomy"},
    {"target": "aws", "split": "one_shot", "label": "AWS Recommendation"},
]

STRATEGY_LABELS = {
    "fixed+linear": "Fixed + Linear",
    "fixed+dichotomy": "Fixed + Dichotomy",
    "fixed+one_shot": "Fixed + One Shot",
    "dynamic+linear": "Dynamic + Linear",
    "dynamic+dichotomy": "Dynamic + Dichotomy",
    "dynamic+one_shot": "Dynamic + One Shot",
    "aws+one_shot": "AWS Recommendation",
}


def _build_preview_config(base_config: dict[str, Any], target: str, split: str) -> dict[str, Any]:
    config = base_config.copy()
    config["target_strategy_type"] = target
    config["split_strategy_type"] = split

    if target == "fixed" and "coverage_target_percent" not in config:
        config["coverage_target_percent"] = 90.0
    if target == "dynamic" and not config.get("dynamic_risk_level"):
        config["dynamic_risk_level"] = "balanced"
    if split == "linear" and not config.get("linear_step_percent"):
        config["linear_step_percent"] = config.get("max_purchase_percent", 10.0)
    if split == "dichotomy":
        config.setdefault("max_purchase_percent", 50.0)
        config.setdefault("min_purchase_percent", 1.0)

    return config


def _get_configured_key(config: dict[str, Any]) -> str:
    return f"{config.get('target_strategy_type', 'fixed')}+{config.get('split_strategy_type', 'linear')}"


_AWS_TYPE_TO_KEY = {"Compute": "compute", "Database": "database", "SageMaker": "sagemaker"}


def _inject_actual_savings_rates(
    config: dict[str, Any], savings_data: dict[str, Any] | None
) -> dict[str, Any]:
    if not savings_data:
        return config
    breakdown = savings_data.get("actual_savings", {}).get("breakdown_by_type", {})
    if not breakdown:
        return config
    config = config.copy()
    for aws_name, key in _AWS_TYPE_TO_KEY.items():
        pct = breakdown.get(aws_name, {}).get("savings_percentage")
        if pct is not None:
            config[f"{key}_savings_percentage"] = pct
    return config


def calculate_scheduler_preview(
    config: dict[str, Any],
    clients: dict[str, Any],
    coverage_data: dict[str, Any],
    savings_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Calculate what each strategy combination would purchase right now.

    Returns preview data with all combinations' recommendations.
    """
    from purchase_calculator import calculate_purchase_need

    config = _inject_actual_savings_rates(config, savings_data)

    configured_key = _get_configured_key(config)
    configured_target = config.get("target_strategy_type", "fixed")
    configured_split = config.get("split_strategy_type", "linear")

    combos = [
        {
            "target": configured_target,
            "split": configured_split,
            "label": STRATEGY_LABELS.get(configured_key, configured_key),
        }
    ]
    for default in DEFAULT_COMPARISONS:
        key = f"{default['target']}+{default['split']}"
        if key != configured_key:
            combos.append(default)

    try:
        all_strategies = {}

        for combo in combos:
            strategy_key = f"{combo['target']}+{combo['split']}"
            try:
                preview_config = _build_preview_config(config, combo["target"], combo["split"])
                purchases = calculate_purchase_need(preview_config, clients, coverage_data)
                enriched = _enrich_purchases(
                    purchases, coverage_data, savings_data, combo["target"]
                )

                all_strategies[strategy_key] = {
                    "label": combo["label"],
                    "purchases": enriched,
                    "has_recommendations": len(enriched) > 0,
                    "error": None,
                }
            except Exception as e:
                logger.error(f"Failed to calculate {strategy_key}: {e}", exc_info=True)
                all_strategies[strategy_key] = {
                    "label": combo["label"],
                    "purchases": [],
                    "has_recommendations": False,
                    "error": str(e),
                }

        return {
            "configured_strategy": configured_key,
            "strategy_order": [f"{c['target']}+{c['split']}" for c in combos],
            "strategies": all_strategies,
            "error": None,
        }

    except Exception as e:
        logger.error(f"Failed to calculate scheduler preview: {e}", exc_info=True)
        return {
            "configured_strategy": configured_key,
            "strategies": {},
            "error": str(e),
        }


def _enrich_purchases(
    purchase_plans: list[dict[str, Any]],
    coverage_data: dict[str, Any],
    savings_data: dict[str, Any] | None,
    target_type: str,
) -> list[dict[str, Any]]:
    breakdown_by_type = (
        savings_data.get("actual_savings", {}).get("breakdown_by_type", {}) if savings_data else {}
    )

    enriched = []
    for plan in purchase_plans:
        sp_type = plan["sp_type"]
        sp_data = coverage_data.get(sp_type, {})
        summary = sp_data.get("summary", {})

        hourly_commitment = plan["hourly_commitment"]

        timeseries = sp_data.get("timeseries", [])
        total_costs = [item.get("total", 0.0) for item in timeseries if item.get("total", 0.0) > 0]
        min_hourly = min(total_costs) if total_costs else 0.0

        aws_type_name = {
            "compute": "Compute",
            "database": "Database",
            "sagemaker": "SageMaker",
        }.get(sp_type, sp_type)
        type_breakdown = breakdown_by_type.get(aws_type_name, {})
        savings_pct = type_breakdown.get("savings_percentage", 0.0)
        existing_commitment = type_breakdown.get("total_commitment", 0.0)

        current_od_equiv = sp_calculations.coverage_from_commitment(
            existing_commitment, savings_pct
        )
        new_savings_pct = plan.get("estimated_savings_percentage", savings_pct)
        new_od_equiv = sp_calculations.coverage_from_commitment(hourly_commitment, new_savings_pct)

        avg_hourly_total = summary.get("avg_hourly_total", 0.0)

        if min_hourly > 0:
            purchase_percent = (new_od_equiv / min_hourly) * 100.0
            current_coverage = (current_od_equiv / min_hourly) * 100.0
            projected_coverage = ((current_od_equiv + new_od_equiv) / min_hourly) * 100.0
            avg_to_min_ratio = avg_hourly_total / min_hourly if avg_hourly_total > 0 else 1.0
        else:
            purchase_percent = 0.0
            current_coverage = 0.0
            projected_coverage = 0.0
            avg_to_min_ratio = 1.0

        details = plan.get("details", {})
        target_min_hourly = details.get("coverage", {}).get("target")

        has_existing_plans = type_breakdown.get("plans_count", 0) > 0
        entry = {
            "sp_type": sp_type,
            "hourly_commitment": hourly_commitment,
            "purchase_percent": purchase_percent,
            "current_coverage": current_coverage,
            "projected_coverage": projected_coverage,
            "target_coverage": target_min_hourly,
            "payment_option": plan["payment_option"],
            "term": plan["term"],
            "discount_used": new_savings_pct,
            "average_utilization": type_breakdown.get("average_utilization", 0.0)
            if has_existing_plans
            else None,
            "avg_to_min_ratio": avg_to_min_ratio,
            "is_aws_target": target_type == "aws",
        }
        if "estimated_savings_percentage" in plan:
            entry["estimated_savings_percentage"] = plan["estimated_savings_percentage"]
        enriched.append(entry)

    return enriched

"""Chart data prep + optimal-coverage computation for the HTML report."""

from __future__ import annotations

import json
import logging
from typing import Any

from report_data import get_type_metrics_for_report

from shared import sp_calculations
from shared.optimal_coverage import calculate_optimal_coverage


logger = logging.getLogger(__name__)


def _build_timeseries_maps(coverage_data: dict[str, Any]) -> tuple[dict, set]:
    """Flatten per-type timeseries into {sp_type: {ts: {covered, ondemand, total}}}."""
    timeseries_maps = {
        "global": {},
        "compute": {},
        "database": {},
        "sagemaker": {},
    }
    all_timestamps = set()

    for sp_type in ("compute", "database", "sagemaker"):
        for item in coverage_data[sp_type].get("timeseries", []):
            ts = item["timestamp"]
            covered = item["covered"]
            total = item["total"]
            ondemand = total - covered
            all_timestamps.add(ts)

            for target in (sp_type, "global"):
                bucket = timeseries_maps[target].setdefault(
                    ts, {"covered": 0.0, "ondemand": 0.0, "total": 0.0}
                )
                bucket["covered"] += covered
                bucket["ondemand"] += ondemand
                bucket["total"] += total

    return timeseries_maps, all_timestamps


def _format_timestamp_label(ts: str, num_timestamps: int) -> str:
    """Short axis label; includes the date prefix once timestamps exceed 24."""
    if "T" in ts:
        date_part, time_part = ts.split("T")
        time_part = time_part[:5]
        return f"{date_part[5:]} {time_part}" if num_timestamps > 24 else time_part
    return ts[:10]


def _calculate_cost_statistics(total_costs: list[float]) -> dict[str, float]:
    """min/max/p50/p75/p90/p95 for non-zero costs; empty if all zero."""
    nonzero = [c for c in total_costs if c > 0]
    if not nonzero:
        return {}
    sorted_costs = sorted(nonzero)
    n = len(sorted_costs)
    return {
        "min": round(sorted_costs[0], 2),
        "max": round(sorted_costs[-1], 2),
        "p50": round(sorted_costs[int(n * 0.50)], 2),
        "p75": round(sorted_costs[int(n * 0.75)], 2),
        "p90": round(sorted_costs[int(n * 0.90)], 2),
        "p95": round(sorted_costs[int(n * 0.95)], 2),
    }


def _build_chart_data_for_type(
    type_map: dict[str, dict[str, float]], sorted_timestamps: list[str]
) -> dict[str, Any]:
    """Build {labels, timestamps, covered, ondemand, stats} for one SP type."""
    labels = []
    timestamps = []
    covered_values = []
    ondemand_values = []
    total_costs = []

    for ts in sorted_timestamps:
        labels.append(_format_timestamp_label(ts, len(sorted_timestamps)))
        timestamps.append(ts)
        data = type_map.get(ts, {"covered": 0.0, "ondemand": 0.0, "total": 0.0})
        covered_values.append(round(data["covered"], 2))
        ondemand_values.append(round(data["ondemand"], 2))
        total_costs.append(round(data["total"], 2))

    return {
        "labels": labels,
        "timestamps": timestamps,
        "covered": covered_values,
        "ondemand": ondemand_values,
        "stats": _calculate_cost_statistics(total_costs),
    }


def _prepare_chart_data(
    coverage_data: dict[str, Any],
    savings_data: dict[str, Any],
    config: dict[str, Any] | None = None,
    per_type_range: bool = False,
) -> tuple[str, dict[str, Any]]:
    """Return (chart_json, optimal_results) for Chart.js + knee-point analysis.

    per_type_range=True restricts each per-type series to timestamps where the
    type actually has data (used for daily charts so per-type tabs don't show
    empty bars outside that type's range).
    """
    config = config or {}
    timeseries_maps, all_timestamps = _build_timeseries_maps(coverage_data)
    sorted_timestamps = sorted(all_timestamps)

    chart_data = {
        "global": _build_chart_data_for_type(timeseries_maps["global"], sorted_timestamps),
    }
    for type_name in ("compute", "database", "sagemaker"):
        if per_type_range:
            type_ts = [
                ts
                for ts in sorted_timestamps
                if timeseries_maps[type_name].get(ts, {}).get("total", 0) > 0
            ]
            chart_data[type_name] = _build_chart_data_for_type(
                timeseries_maps[type_name], type_ts or sorted_timestamps
            )
        else:
            chart_data[type_name] = _build_chart_data_for_type(
                timeseries_maps[type_name], sorted_timestamps
            )

    return json.dumps(chart_data), _calculate_optimal_coverage(chart_data, savings_data)


def _calculate_sp_type_optimal(
    sp_type: str, type_data: dict[str, Any], savings_percentage: float
) -> dict[str, Any]:
    """Run the knee-point calc for one SP type; empty dict on no usable data."""
    if not (type_data["covered"] and type_data["ondemand"]):
        return {}
    hourly_costs = [
        covered + ondemand
        for covered, ondemand in zip(type_data["covered"], type_data["ondemand"], strict=True)
    ]
    if not hourly_costs or max(hourly_costs) <= 0:
        return {}
    logger.info(
        "Calculating optimal coverage for %s: using %.1f%% discount", sp_type, savings_percentage
    )
    try:
        return calculate_optimal_coverage(hourly_costs, savings_percentage)
    except Exception as e:
        logger.warning(f"Failed to calculate optimal coverage for {sp_type}: {e}")
        return {}


def _calculate_optimal_coverage(
    all_chart_data: dict[str, Any], savings_data: dict[str, Any]
) -> dict[str, Any]:
    """Per-type + global optimal coverage using each type's observed savings rate.

    IMPORTANT: this Python implementation must stay in sync with
    docs/js/costCalculator.js::calculateOptimalCoverage(). Algorithm changes
    must land in both places.
    """
    actual_savings = savings_data["actual_savings"]
    breakdown_by_type = actual_savings.get("breakdown_by_type", {})
    type_mapping = {"compute": "Compute", "database": "Database", "sagemaker": "SageMaker"}

    optimal_results: dict[str, Any] = {}
    for sp_type in ("compute", "database", "sagemaker"):
        type_breakdown = breakdown_by_type.get(type_mapping.get(sp_type, ""), {})
        type_savings_pct = type_breakdown.get("savings_percentage", 0.0)
        savings_percentage = type_savings_pct if type_savings_pct > 0 else 20.0
        result = _calculate_sp_type_optimal(sp_type, all_chart_data[sp_type], savings_percentage)
        if result:
            optimal_results[sp_type] = result

    overall_savings_pct = actual_savings.get("savings_percentage", 0.0)
    savings_percentage = overall_savings_pct if overall_savings_pct > 0 else 20.0
    optimal_results["savings_percentage_used"] = savings_percentage

    global_result = _calculate_sp_type_optimal(
        "global", all_chart_data["global"], savings_percentage
    )
    if global_result:
        optimal_results["global"] = global_result

    return optimal_results


def prepare_chart_and_preview_json(
    coverage_data: dict[str, Any],
    savings_data: dict[str, Any],
    config: dict[str, Any],
    daily_coverage_data: dict[str, Any] | None,
    preview_data: dict[str, Any] | None,
) -> tuple[str, str, str, str, str, str]:
    """Precompute every JSON blob the HTML template injects into the page."""
    chart_data, optimal_coverage_results = _prepare_chart_data(coverage_data, savings_data, config)

    daily_chart_data = "null"
    if daily_coverage_data:
        daily_chart_data, _ = _prepare_chart_data(
            daily_coverage_data, savings_data, config, per_type_range=True
        )

    breakdown_by_type = savings_data["actual_savings"]["breakdown_by_type"]
    metrics_json = json.dumps(
        {
            "compute": get_type_metrics_for_report(
                coverage_data["compute"], "Compute", breakdown_by_type
            ),
            "database": get_type_metrics_for_report(
                coverage_data["database"], "Database", breakdown_by_type
            ),
            "sagemaker": get_type_metrics_for_report(
                coverage_data["sagemaker"], "SageMaker", breakdown_by_type
            ),
        }
    )

    optimal_coverage_json = (
        json.dumps(optimal_coverage_results) if optimal_coverage_results else "{}"
    )

    follow_aws_by_type: dict[str, Any] = {}
    if preview_data:
        aws_strategy = preview_data["strategies"].get("aws+one_shot", {})
        for purchase in aws_strategy.get("purchases", []):
            follow_aws_by_type[purchase["sp_type"]] = {
                "hourly_commitment": purchase["hourly_commitment"],
                "estimated_savings_percentage": purchase.get("estimated_savings_percentage", 0),
            }
    follow_aws_json = json.dumps(follow_aws_by_type)

    configured_target_by_type: dict[str, Any] = {}
    if preview_data:
        configured_key = preview_data.get("configured_strategy", "")
        strategy_data = preview_data.get("strategies", {}).get(configured_key, {})
        for purchase in strategy_data.get("purchases", []):
            added_commitment = purchase.get("hourly_commitment", 0)
            discount = purchase.get("discount_used", 0)
            new_od_equiv = sp_calculations.coverage_from_commitment(added_commitment, discount)
            configured_target_by_type[purchase["sp_type"]] = {
                "projected_coverage": purchase.get("projected_coverage", 0),
                "added_od_equiv": round(new_od_equiv, 4),
                "added_commitment": round(added_commitment, 5),
            }
    configured_target_json = json.dumps(configured_target_by_type)

    return (
        chart_data,
        daily_chart_data,
        metrics_json,
        optimal_coverage_json,
        follow_aws_json,
        configured_target_json,
    )

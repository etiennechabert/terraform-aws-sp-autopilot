"""Shared data-prep helpers used by HTML/JSON/CSV report generators."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from shared import sp_calculations


def get_coverage_class(coverage: float) -> str:
    """CSS class by coverage band (green >= 70, orange >= 30, red otherwise)."""
    if coverage >= 70:
        return "green"
    if coverage >= 30:
        return "orange"
    return "red"


def get_utilization_class(utilization: float) -> str:
    """CSS class by utilization band."""
    if utilization >= 95:
        return "green"
    if utilization >= 80:
        return "orange"
    return "red"


def get_min_hourly_from_timeseries_data(sp_type_data: dict[str, Any]) -> float:
    """Minimum non-zero hourly cost across the timeseries."""
    timeseries = sp_type_data.get("timeseries", [])
    total_costs = [item.get("total", 0.0) for item in timeseries if item.get("total", 0.0) > 0]
    return min(total_costs) if total_costs else 0.0


def coverage_pct_of_min_hourly(sp_type_data: dict[str, Any]) -> float:
    """Convert avg_coverage_total (% of avg spend) to % of min-hourly spend."""
    summary = sp_type_data.get("summary", {})
    avg_coverage = summary.get("avg_coverage_total", 0.0)
    avg_total = summary.get("avg_hourly_total", 0.0)
    min_hourly = get_min_hourly_from_timeseries_data(sp_type_data)
    if min_hourly <= 0 or avg_total <= 0:
        return avg_coverage
    return avg_coverage * (avg_total / min_hourly)


def get_type_metrics_for_report(
    sp_type_data: dict[str, Any], sp_type_name: str, breakdown_by_type: dict[str, Any]
) -> dict[str, Any]:
    """Per-type metrics bundle consumed by the HTML template."""
    summary = sp_type_data.get("summary", {})
    current_coverage = coverage_pct_of_min_hourly(sp_type_data)
    avg_total_cost = summary.get("avg_hourly_total", 0.0)
    avg_covered_cost = summary.get("avg_hourly_covered", 0.0)
    avg_uncovered_cost = avg_total_cost - avg_covered_cost

    type_breakdown = breakdown_by_type.get(sp_type_name, {})
    type_savings_pct = type_breakdown.get("savings_percentage", 0.0)
    type_utilization = type_breakdown.get("average_utilization", 0.0)
    net_savings_hourly = type_breakdown.get("net_savings_hourly", 0.0)
    total_commitment = type_breakdown.get("total_commitment", 0.0)

    discount_pct = type_savings_pct if current_coverage > 0 and type_savings_pct > 0 else 0.0
    on_demand_coverage = sp_calculations.coverage_from_commitment(total_commitment, discount_pct)

    return {
        "current_coverage": current_coverage,
        "utilization": type_utilization,
        "actual_savings_hourly": net_savings_hourly,
        "savings_percentage": discount_pct,
        "sp_commitment_hourly": total_commitment,
        # Pre-calculated to eliminate JS duplication.
        "on_demand_coverage_hourly": on_demand_coverage,
        "uncovered_spend_hourly": avg_uncovered_cost,
        "total_spend_hourly": avg_total_cost,
        "total_commitment": total_commitment,
    }


def prepare_html_report_data(
    coverage_data: dict[str, Any], savings_data: dict[str, Any], config: dict[str, Any]
) -> dict[str, Any]:
    """Top-level metrics for the HTML template's summary section."""
    now = datetime.now(UTC)
    lookback_hours = config["lookback_hours"]
    data_end_date = now.date()
    data_start_date = data_end_date - timedelta(hours=lookback_hours)

    compute_summary = coverage_data["compute"]["summary"]
    database_summary = coverage_data["database"]["summary"]
    sagemaker_summary = coverage_data["sagemaker"]["summary"]

    compute_coverage = coverage_pct_of_min_hourly(coverage_data["compute"])
    database_coverage = coverage_pct_of_min_hourly(coverage_data["database"])
    sagemaker_coverage = coverage_pct_of_min_hourly(coverage_data["sagemaker"])

    total_hourly_spend = (
        compute_summary["avg_hourly_total"]
        + database_summary["avg_hourly_total"]
        + sagemaker_summary["avg_hourly_total"]
    )
    total_hourly_covered = (
        compute_summary["avg_hourly_covered"]
        + database_summary["avg_hourly_covered"]
        + sagemaker_summary["avg_hourly_covered"]
    )
    total_min_hourly = sum(
        get_min_hourly_from_timeseries_data(coverage_data[key])
        for key in ("compute", "database", "sagemaker")
    )
    overall_coverage = (
        (total_hourly_covered / total_min_hourly * 100) if total_min_hourly > 0 else 0.0
    )

    actual_savings = savings_data["actual_savings"]

    return {
        "report_timestamp": now.strftime("%Y-%m-%d %H:%M:%S UTC"),
        "data_period": f"{data_start_date.isoformat()} to {data_end_date.isoformat()}",
        "lookback_hours": lookback_hours,
        "compute_coverage": compute_coverage,
        "database_coverage": database_coverage,
        "sagemaker_coverage": sagemaker_coverage,
        "overall_coverage": overall_coverage,
        "overall_coverage_class": get_coverage_class(overall_coverage),
        "total_hourly_spend": total_hourly_spend,
        "total_hourly_covered": total_hourly_covered,
        "plans_count": savings_data.get("plans_count", 0),
        "net_savings_hourly": actual_savings.get("net_savings_hourly", 0.0),
        "savings_percentage": actual_savings.get("savings_percentage", 0.0),
        "total_commitment": savings_data.get("total_commitment", 0.0),
        "average_utilization": savings_data.get("average_utilization", 0.0),
        "utilization_class": get_utilization_class(savings_data.get("average_utilization", 0.0)),
        "on_demand_equivalent_hourly": actual_savings.get("on_demand_equivalent_hourly", 0.0),
        "breakdown_by_type": actual_savings.get("breakdown_by_type", {}),
    }

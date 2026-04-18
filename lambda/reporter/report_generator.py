"""Report generation entry point + JSON/CSV serializers.

The HTML generator lives in html_report.py; this module dispatches to the
right generator for the requested format.

The module also re-exports a few helpers that existing tests import by their
original names (so the split is invisible to test modules).
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

from html_report import generate_html_report
from html_sections import (
    build_breakdown_table_html as _build_breakdown_table_html,
)
from html_sections import (
    parse_plan_dates as _parse_plan_dates,
)
from html_sections import (
    render_spike_guard_warning_banner as _render_spike_guard_warning_banner,
)
from report_data import coverage_pct_of_min_hourly
from report_data import (
    get_type_metrics_for_report as _get_type_metrics_for_report,
)


logger = logging.getLogger(__name__)


# Test-compat re-exports: tests import these private names from report_generator.
__all__ = [
    "_build_breakdown_table_html",
    "_get_type_metrics_for_report",
    "_parse_plan_dates",
    "_render_spike_guard_warning_banner",
    "generate_csv_report",
    "generate_html_report",
    "generate_json_report",
    "generate_report",
]


def generate_report(
    coverage_data: dict[str, Any],
    savings_data: dict[str, Any],
    report_format: str = "html",
    config: dict[str, Any] | None = None,
    raw_data: dict[str, Any] | None = None,
    preview_data: dict[str, Any] | None = None,
    daily_coverage_data: dict[str, Any] | None = None,
    guard_results: dict[str, dict[str, Any]] | None = None,
) -> str:
    """Dispatch to the HTML/JSON/CSV generator."""
    if report_format == "json":
        return generate_json_report(coverage_data, savings_data, config, guard_results)
    if report_format == "csv":
        return generate_csv_report(coverage_data, savings_data)
    if report_format == "html":
        return generate_html_report(
            coverage_data,
            savings_data,
            config,
            raw_data,
            preview_data,
            daily_coverage_data,
            guard_results,
        )
    raise ValueError(f"Invalid report format: {report_format}")


def generate_json_report(
    coverage_data: dict[str, Any],
    savings_data: dict[str, Any],
    config: dict[str, Any] | None = None,
    guard_results: dict[str, dict[str, Any]] | None = None,
) -> str:
    """JSON report with coverage trends, savings metrics, and spike-guard results."""
    logger.info("Generating JSON report")
    config = config or {}

    report_timestamp = datetime.now(UTC).isoformat()

    compute_summary = coverage_data["compute"]["summary"]
    database_summary = coverage_data["database"]["summary"]
    sagemaker_summary = coverage_data["sagemaker"]["summary"]

    actual_savings = savings_data["actual_savings"]
    breakdown_by_type = actual_savings.get("breakdown_by_type", {})

    breakdown_array = [
        {
            "type": plan_type,
            "plans_count": type_data.get("plans_count", 0),
            "total_hourly_commitment": round(type_data.get("total_commitment", 0.0), 4),
        }
        for plan_type, type_data in breakdown_by_type.items()
    ]

    report: dict[str, Any] = {
        "report_metadata": {
            "generated_at": report_timestamp,
            "report_type": "savings_plans_coverage_and_savings",
            "generator": "sp-autopilot-reporter",
        },
        "report_parameters": {
            "lookback_hours": config["lookback_hours"],
            "granularity": "HOURLY",
            "enable_compute_sp": config["enable_compute_sp"],
            "enable_database_sp": config["enable_database_sp"],
            "enable_sagemaker_sp": config["enable_sagemaker_sp"],
            "low_utilization_threshold": config["low_utilization_threshold"],
        },
        "coverage_summary": {
            "compute": {
                "avg_coverage_percentage": round(
                    coverage_pct_of_min_hourly(coverage_data["compute"]), 2
                ),
                "avg_hourly_spend": round(compute_summary.get("avg_hourly_total", 0.0), 4),
            },
            "database": {
                "avg_coverage_percentage": round(
                    coverage_pct_of_min_hourly(coverage_data["database"]), 2
                ),
                "avg_hourly_spend": round(database_summary.get("avg_hourly_total", 0.0), 4),
            },
            "sagemaker": {
                "avg_coverage_percentage": round(
                    coverage_pct_of_min_hourly(coverage_data["sagemaker"]), 2
                ),
                "avg_hourly_spend": round(sagemaker_summary.get("avg_hourly_total", 0.0), 4),
            },
        },
        "savings_summary": {
            "active_plans_count": savings_data.get("plans_count", 0),
            "total_hourly_commitment": round(savings_data.get("total_commitment", 0.0), 4),
            "average_utilization_percentage": round(
                savings_data.get("average_utilization", 0.0), 2
            ),
        },
        "actual_savings": {
            "sp_cost_hourly": round(actual_savings.get("actual_sp_cost_hourly", 0.0), 2),
            "on_demand_cost_hourly": round(
                actual_savings.get("on_demand_equivalent_hourly", 0.0), 2
            ),
            "net_savings_hourly": round(actual_savings.get("net_savings_hourly", 0.0), 2),
            "savings_percentage": round(actual_savings.get("savings_percentage", 0.0), 2),
            "breakdown": breakdown_array,
        },
        "active_savings_plans": savings_data.get("plans", []),
    }

    if guard_results:
        flagged = {t: r for t, r in guard_results.items() if r["flagged"]}
        if flagged:
            report["spike_guard"] = {
                sp_type: {
                    "long_term_avg_hourly": round(r["long_term_avg"], 4),
                    "short_term_avg_hourly": round(r["short_term_avg"], 4),
                    "spike_percent": r["change_percent"],
                }
                for sp_type, r in flagged.items()
            }

    json_content = json.dumps(report, indent=2, default=str)
    logger.info(f"JSON report generated ({len(json_content)} bytes)")
    return json_content


def generate_csv_report(
    coverage_data: dict[str, Any],
    savings_data: dict[str, Any],
) -> str:
    """CSV report — summary block + active-plans table."""
    logger.info("Generating CSV report")

    report_timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    actual_savings = savings_data["actual_savings"]

    csv_parts = [
        "# Savings Plans Coverage & Savings Report",
        f"# Generated: {report_timestamp}",
        "",
        "## Summary",
        "metric,value",
        f"active_plans_count,{savings_data.get('plans_count', 0)}",
        f"total_hourly_commitment,{savings_data.get('total_commitment', 0.0):.5f}",
        f"average_utilization_percentage,{savings_data.get('average_utilization', 0.0):.2f}",
        f"compute_avg_coverage,{coverage_pct_of_min_hourly(coverage_data['compute']):.2f}",
        f"database_avg_coverage,{coverage_pct_of_min_hourly(coverage_data['database']):.2f}",
        f"sagemaker_avg_coverage,{coverage_pct_of_min_hourly(coverage_data['sagemaker']):.2f}",
        f"actual_sp_cost_hourly,{actual_savings.get('actual_sp_cost_hourly', 0.0):.2f}",
        f"on_demand_equivalent_hourly,{actual_savings.get('on_demand_equivalent_hourly', 0.0):.2f}",
        f"net_savings_hourly,{actual_savings.get('net_savings_hourly', 0.0):.2f}",
        f"savings_percentage,{actual_savings.get('savings_percentage', 0.0):.2f}",
        "",
        "## Active Savings Plans",
        "plan_id,plan_type,payment_option,term_years,hourly_commitment,start_date,end_date",
    ]

    for plan in savings_data.get("plans", []):
        csv_parts.append(
            f"{plan.get('plan_id', '')},"
            f"{plan.get('plan_type', '')},"
            f"{plan.get('payment_option', '')},"
            f"{plan.get('term_years', 0)},"
            f"{plan.get('hourly_commitment', 0.0):.5f},"
            f"{plan.get('start_date', '')},"
            f"{plan.get('end_date', '')}"
        )

    csv_content = "\n".join(csv_parts)
    logger.info(f"CSV report generated ({len(csv_content)} bytes)")
    return csv_content

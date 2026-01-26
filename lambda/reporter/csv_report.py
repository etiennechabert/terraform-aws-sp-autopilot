"""
CSV report generation for Reporter Lambda.

Generates CSV-formatted reports containing coverage history and savings data.
"""

import logging
from datetime import UTC, datetime
from typing import Any


# Configure logging
logger = logging.getLogger()


def generate_csv_report(
    coverage_history: list[dict[str, Any]], savings_data: dict[str, Any]
) -> str:
    """
    Generate CSV report with coverage trends and savings metrics.

    Args:
        coverage_history: List of coverage data points by day
        savings_data: Savings Plans data including commitment and estimated savings

    Returns:
        str: CSV report content
    """
    logger.info("Generating CSV report")

    # Calculate report timestamp
    report_timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")

    # Calculate coverage summary
    avg_coverage = 0.0
    if coverage_history:
        total_coverage = sum(item.get("coverage_percentage", 0.0) for item in coverage_history)
        avg_coverage = total_coverage / len(coverage_history)

    current_coverage = (
        coverage_history[-1].get("coverage_percentage", 0.0) if coverage_history else 0.0
    )

    # Calculate trend direction
    trend_direction = "stable"
    trend_value = 0.0
    if len(coverage_history) >= 2:
        first_coverage = coverage_history[0].get("coverage_percentage", 0.0)
        last_coverage = coverage_history[-1].get("coverage_percentage", 0.0)
        trend_value = last_coverage - first_coverage
        if trend_value > 0:
            trend_direction = "increasing"
        elif trend_value < 0:
            trend_direction = "decreasing"

    # Extract actual savings data
    actual_savings = savings_data.get("actual_savings", {})
    actual_sp_cost = actual_savings.get("actual_sp_cost", 0.0)
    on_demand_equivalent_cost = actual_savings.get("on_demand_equivalent_cost", 0.0)
    net_savings = actual_savings.get("net_savings", 0.0)
    savings_percentage = actual_savings.get("savings_percentage", 0.0)

    # Build CSV content
    csv_parts = []

    # Header
    csv_parts.append("# Savings Plans Coverage & Savings Report")
    csv_parts.append(f"# Generated: {report_timestamp}")
    csv_parts.append("")

    # Summary section
    csv_parts.append("## Summary")
    csv_parts.append("metric,value")
    csv_parts.append(f"current_coverage_percentage,{current_coverage:.2f}")
    csv_parts.append(f"average_coverage_percentage,{avg_coverage:.2f}")
    csv_parts.append(f"trend_direction,{trend_direction}")
    csv_parts.append(f"trend_value,{trend_value:.2f}")
    csv_parts.append(f"active_plans_count,{savings_data.get('plans_count', 0)}")
    csv_parts.append(f"total_hourly_commitment,{savings_data.get('total_commitment', 0.0):.4f}")
    csv_parts.append(
        f"average_utilization_percentage,{savings_data.get('average_utilization', 0.0):.2f}"
    )
    csv_parts.append(f"actual_sp_cost,{actual_sp_cost:.2f}")
    csv_parts.append(f"on_demand_equivalent_cost,{on_demand_equivalent_cost:.2f}")
    csv_parts.append(f"net_savings,{net_savings:.2f}")
    csv_parts.append(f"savings_percentage,{savings_percentage:.2f}")
    csv_parts.append("")

    # Coverage history section
    csv_parts.append("## Coverage History")
    csv_parts.append("date,coverage_percentage,on_demand_hours,covered_hours,total_hours")
    for item in coverage_history:
        csv_parts.append(
            f"{item.get('date', '')},{item.get('coverage_percentage', 0.0):.2f},"
            f"{item.get('on_demand_hours', 0.0):.2f},{item.get('covered_hours', 0.0):.2f},"
            f"{item.get('total_hours', 0.0):.2f}"
        )
    csv_parts.append("")

    # Active Savings Plans section
    csv_parts.append("## Active Savings Plans")
    csv_parts.append(
        "plan_id,plan_type,payment_option,term_years,hourly_commitment,start_date,end_date"
    )
    for plan in savings_data.get("plans", []):
        plan_id = plan.get("plan_id", "")
        plan_type = plan.get("plan_type", "")
        payment_option = plan.get("payment_option", "")
        term_years = plan.get("term_years", 0)
        hourly_commitment = plan.get("hourly_commitment", 0.0)
        start_date = plan.get("start_date", "")
        end_date = plan.get("end_date", "")

        csv_parts.append(
            f"{plan_id},{plan_type},{payment_option},{term_years},{hourly_commitment:.4f},"
            f"{start_date},{end_date}"
        )

    csv_content = "\n".join(csv_parts)

    logger.info(f"CSV report generated ({len(csv_content)} bytes)")
    return csv_content

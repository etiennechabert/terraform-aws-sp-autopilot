"""
JSON report generation for Reporter Lambda.

Generates structured JSON reports containing coverage history and savings data.
"""

import json
import logging
from datetime import UTC, datetime
from typing import Any


# Configure logging
logger = logging.getLogger()


def generate_json_report(
    coverage_history: list[dict[str, Any]], savings_data: dict[str, Any]
) -> str:
    """
    Generate JSON report with coverage trends and savings metrics.

    Args:
        coverage_history: List of coverage data points by day
        savings_data: Savings Plans data including commitment and estimated savings

    Returns:
        str: JSON report content
    """
    logger.info("Generating JSON report")

    # Calculate report timestamp
    report_timestamp = datetime.now(UTC).isoformat()

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
    breakdown_by_type = actual_savings.get("breakdown_by_type", {})

    # Format breakdown as array of objects
    breakdown_array = []
    for plan_type, type_data in breakdown_by_type.items():
        breakdown_array.append(
            {
                "type": plan_type,
                "plans_count": type_data.get("plans_count", 0),
                "total_hourly_commitment": round(type_data.get("total_commitment", 0.0), 4),
                "total_monthly_commitment": round(type_data.get("total_commitment", 0.0) * 730, 2),
            }
        )

    # Build JSON report structure
    report = {
        "report_metadata": {
            "generated_at": report_timestamp,
            "report_type": "savings_plans_coverage_and_savings",
            "generator": "sp-autopilot-reporter",
            "reporting_period_days": len(coverage_history),
        },
        "coverage_summary": {
            "current_coverage_percentage": round(current_coverage, 2),
            "average_coverage_percentage": round(avg_coverage, 2),
            "trend_direction": trend_direction,
            "trend_value": round(trend_value, 2),
            "data_points": len(coverage_history),
        },
        "coverage_history": coverage_history,
        "savings_summary": {
            "active_plans_count": savings_data.get("plans_count", 0),
            "total_hourly_commitment": round(savings_data.get("total_commitment", 0.0), 4),
            "total_monthly_commitment": round(savings_data.get("total_commitment", 0.0) * 730, 2),
            "estimated_monthly_savings": round(
                savings_data.get("estimated_monthly_savings", 0.0), 2
            ),
            "average_utilization_percentage": round(
                savings_data.get("average_utilization", 0.0), 2
            ),
        },
        "actual_savings": {
            "sp_cost": round(actual_sp_cost, 2),
            "on_demand_cost": round(on_demand_equivalent_cost, 2),
            "net_savings": round(net_savings, 2),
            "savings_percentage": round(savings_percentage, 2),
            "breakdown": breakdown_array,
            "historical_trend": [],  # Placeholder for future enhancement
        },
        "active_savings_plans": savings_data.get("plans", []),
    }

    # Convert to JSON string with pretty formatting
    json_content = json.dumps(report, indent=2, default=str)

    logger.info(f"JSON report generated ({len(json_content)} bytes)")
    return json_content

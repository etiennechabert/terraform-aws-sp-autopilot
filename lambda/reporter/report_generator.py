"""
Report Generation Module.

Generates Savings Plans reports in multiple formats (HTML, JSON, CSV).
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any


logger = logging.getLogger(__name__)


def generate_report(
    coverage_data: dict[str, Any],
    savings_data: dict[str, Any],
    report_format: str = "html",
    config: dict[str, Any] | None = None,
) -> str:
    """
    Generate report in specified format.

    Args:
        coverage_data: Coverage data from SpendingAnalyzer
        savings_data: Savings Plans summary from savings_plans_metrics
        report_format: Format - "html", "json", or "csv"
        config: Configuration parameters used for the report

    Returns:
        str: Generated report content

    Raises:
        ValueError: If report_format is invalid
    """
    if report_format == "json":
        return generate_json_report(coverage_data, savings_data, config)
    if report_format == "csv":
        return generate_csv_report(coverage_data, savings_data, config)
    if report_format == "html":
        return generate_html_report(coverage_data, savings_data, config)
    raise ValueError(f"Invalid report format: {report_format}")


def _prepare_chart_data(coverage_data: dict[str, Any]) -> str:
    """
    Prepare chart data from coverage timeseries for Chart.js visualization.

    Args:
        coverage_data: Coverage data from SpendingAnalyzer with timeseries

    Returns:
        str: JSON string with chart data (labels, covered, ondemand arrays)
    """
    # Aggregate timeseries across all SP types (compute, database, sagemaker)
    timeseries_map = {}

    for sp_type in ["compute", "database", "sagemaker"]:
        timeseries = coverage_data.get(sp_type, {}).get("timeseries", [])
        for item in timeseries:
            timestamp = item.get("timestamp", "")
            covered = item.get("covered", 0.0)
            total = item.get("total", 0.0)
            ondemand = total - covered

            if timestamp not in timeseries_map:
                timeseries_map[timestamp] = {"covered": 0.0, "ondemand": 0.0}

            timeseries_map[timestamp]["covered"] += covered
            timeseries_map[timestamp]["ondemand"] += ondemand

    # Sort by timestamp and format for chart
    sorted_timestamps = sorted(timeseries_map.keys())

    # Limit to last 168 hours (7 days) for readability, or show all if less
    if len(sorted_timestamps) > 168:
        sorted_timestamps = sorted_timestamps[-168:]

    labels = []
    timestamps = []  # Full timestamps for tooltip
    covered_values = []
    ondemand_values = []

    for ts in sorted_timestamps:
        # Format timestamp for display (remove seconds, show date if needed)
        if "T" in ts:
            date_part, time_part = ts.split("T")
            time_part = time_part[:5]  # HH:MM
            # Show MM-DD HH:MM for multi-day view, or just HH:MM for single day
            label = f"{date_part[5:]} {time_part}" if len(sorted_timestamps) > 24 else time_part
        else:
            label = ts[:10]  # Just date for daily granularity

        labels.append(label)
        timestamps.append(ts)  # Store full timestamp for tooltip
        covered_values.append(round(timeseries_map[ts]["covered"], 2))
        ondemand_values.append(round(timeseries_map[ts]["ondemand"], 2))

    chart_data = {
        "labels": labels,
        "timestamps": timestamps,  # Full ISO timestamps for day-of-week calculation
        "covered": covered_values,
        "ondemand": ondemand_values,
    }

    return json.dumps(chart_data)


def generate_html_report(
    coverage_data: dict[str, Any],
    savings_data: dict[str, Any],
    config: dict[str, Any] | None = None,
) -> str:
    """
    Generate HTML report with coverage trends and savings metrics.

    Args:
        coverage_data: Coverage data from SpendingAnalyzer
        savings_data: Savings Plans summary from savings_plans_metrics
        config: Configuration parameters used for the report

    Returns:
        str: HTML report content
    """
    logger.info("Generating HTML report")
    config = config or {}

    report_timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")

    # Extract coverage summary
    compute_coverage = coverage_data.get("compute", {}).get("summary", {}).get("avg_coverage", 0.0)

    # Calculate overall current coverage from timeseries
    current_coverage = 0.0
    for sp_type in ["compute", "database", "sagemaker"]:
        timeseries = coverage_data.get(sp_type, {}).get("timeseries", [])
        if timeseries:
            current_coverage = max(current_coverage, timeseries[-1].get("coverage", 0.0))

    # Extract savings summary
    plans_count = savings_data.get("plans_count", 0)
    actual_savings = savings_data.get("actual_savings", {})
    net_savings = actual_savings.get("net_savings", 0.0)
    savings_percentage = actual_savings.get("savings_percentage", 0.0)
    total_commitment = savings_data.get("total_commitment", 0.0)
    average_utilization = savings_data.get("average_utilization", 0.0)
    on_demand_equivalent = actual_savings.get("on_demand_equivalent_cost", 0.0)
    actual_sp_cost = actual_savings.get("actual_sp_cost", 0.0)
    breakdown_by_type = actual_savings.get("breakdown_by_type", {})

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Savings Plans Coverage & Savings Report</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            background-color: white;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            padding: 30px;
        }}
        h1 {{
            color: #232f3e;
            border-bottom: 3px solid #ff9900;
            padding-bottom: 10px;
            margin-bottom: 10px;
        }}
        .subtitle {{
            color: #6c757d;
            font-size: 0.9em;
            margin-bottom: 30px;
        }}
        .summary {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        .summary-card {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .summary-card.green {{
            background: linear-gradient(135deg, #56ab2f 0%, #a8e063 100%);
        }}
        .summary-card.blue {{
            background: linear-gradient(135deg, #2193b0 0%, #6dd5ed 100%);
        }}
        .summary-card.orange {{
            background: linear-gradient(135deg, #f46b45 0%, #eea849 100%);
        }}
        .summary-card h3 {{
            margin: 0 0 10px 0;
            font-size: 0.9em;
            font-weight: 500;
            opacity: 0.9;
        }}
        .summary-card .value {{
            font-size: 2em;
            font-weight: bold;
            margin: 0;
        }}
        .section {{
            margin-bottom: 40px;
        }}
        h2 {{
            color: #232f3e;
            border-bottom: 2px solid #e0e0e0;
            padding-bottom: 8px;
            margin-bottom: 15px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 20px;
            background-color: white;
        }}
        th {{
            background-color: #232f3e;
            color: white;
            padding: 12px;
            text-align: left;
            font-weight: 600;
        }}
        td {{
            padding: 10px 12px;
            border-bottom: 1px solid #e0e0e0;
        }}
        tr:hover {{
            background-color: #f8f9fa;
        }}
        .metric {{
            font-weight: bold;
            color: #232f3e;
        }}
        .footer {{
            margin-top: 40px;
            padding-top: 20px;
            border-top: 2px solid #e0e0e0;
            text-align: center;
            color: #6c757d;
            font-size: 0.9em;
        }}
        .no-data {{
            text-align: center;
            padding: 40px;
            color: #6c757d;
            font-style: italic;
        }}
        .chart-container {{
            position: relative;
            height: 400px;
            margin: 20px 0;
            padding: 20px;
            background-color: #f8f9fa;
            border-radius: 8px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Savings Plans Coverage & Savings Report</h1>
        <div class="subtitle">Generated: {report_timestamp}</div>

        <div class="summary">
            <div class="summary-card blue">
                <h3>Current Coverage</h3>
                <div class="value">{current_coverage:.1f}%</div>
            </div>
            <div class="summary-card green">
                <h3>Compute Coverage</h3>
                <div class="value">{compute_coverage:.1f}%</div>
            </div>
            <div class="summary-card orange">
                <h3>Active Plans</h3>
                <div class="value">{plans_count}</div>
            </div>
            <div class="summary-card">
                <h3>Actual Net Savings (30 days)</h3>
                <div class="value">${net_savings:,.0f}</div>
            </div>
            <div class="summary-card green">
                <h3>Savings Percentage</h3>
                <div class="value">{savings_percentage:.1f}%</div>
            </div>
        </div>

        <div class="section">
            <h2>Report Parameters</h2>
            <table>
                <tbody>
                    <tr>
                        <td style="font-weight: bold; width: 250px;">Lookback Period</td>
                        <td>{config.get("lookback_days", "N/A")} days</td>
                    </tr>
                    <tr>
                        <td style="font-weight: bold;">Data Granularity</td>
                        <td>{config.get("granularity", "N/A")}</td>
                    </tr>
                    <tr>
                        <td style="font-weight: bold;">Compute Savings Plans</td>
                        <td>{"✓ Enabled" if config.get("enable_compute_sp", True) else "✗ Disabled"}</td>
                    </tr>
                    <tr>
                        <td style="font-weight: bold;">Database Savings Plans</td>
                        <td>{"✓ Enabled" if config.get("enable_database_sp", False) else "✗ Disabled"}</td>
                    </tr>
                    <tr>
                        <td style="font-weight: bold;">SageMaker Savings Plans</td>
                        <td>{"✓ Enabled" if config.get("enable_sagemaker_sp", False) else "✗ Disabled"}</td>
                    </tr>
                    <tr>
                        <td style="font-weight: bold;">Low Utilization Threshold</td>
                        <td>{config.get("low_utilization_threshold", "N/A")}%</td>
                    </tr>
                </tbody>
            </table>
        </div>

        <div class="section">
            <h2>Usage Over Time</h2>
            <div class="chart-container">
                <canvas id="usageChart"></canvas>
            </div>
        </div>

        <div class="section">
            <h2>Active Savings Plans</h2>
"""

    plans = savings_data.get("plans", [])
    if plans:
        html += f"""
            <p>
                <strong>Total Hourly Commitment:</strong> ${total_commitment:.4f}/hour
                (${total_commitment * 730:,.2f}/month)
                <br>
                <strong>Average Utilization (30 days):</strong> {average_utilization:.2f}%
            </p>
            <table>
                <thead>
                    <tr>
                        <th>Plan ID</th>
                        <th>Type</th>
                        <th>Hourly Commitment</th>
                        <th>Term</th>
                        <th>Payment Option</th>
                        <th>Start Date</th>
                        <th>End Date</th>
                    </tr>
                </thead>
                <tbody>
"""
        for plan in plans:
            plan_id = plan.get("plan_id", "Unknown")
            plan_type = plan.get("plan_type", "Unknown")
            hourly_commitment = plan.get("hourly_commitment", 0.0)
            term_years = plan.get("term_years", 0)
            payment_option = plan.get("payment_option", "Unknown")
            start_date = plan.get("start_date", "Unknown")
            end_date = plan.get("end_date", "Unknown")

            # Format dates
            if "T" in start_date:
                start_date = start_date.split("T")[0]
            if "T" in end_date:
                end_date = end_date.split("T")[0]

            html += f"""
                    <tr>
                        <td style="font-family: monospace; font-size: 0.85em;">{plan_id[:20]}...</td>
                        <td>{plan_type}</td>
                        <td class="metric">${hourly_commitment:.4f}/hr</td>
                        <td>{term_years} year(s)</td>
                        <td>{payment_option}</td>
                        <td>{start_date}</td>
                        <td>{end_date}</td>
                    </tr>
"""
        html += """
                </tbody>
            </table>
"""
    else:
        html += """
            <div class="no-data">No active Savings Plans found</div>
"""

    html += """
        </div>

        <div class="section">
            <h2>Actual Savings Summary (Last 30 Days)</h2>
"""

    html += f"""
            <p>
                <strong>Net Savings:</strong> <span style="color: #28a745; font-size: 1.2em; font-weight: bold;">${net_savings:,.2f}</span>
                <span style="color: #6c757d; margin-left: 10px;">({savings_percentage:.2f}% savings)</span>
            </p>
            <p>
                <strong>On-Demand Equivalent Cost:</strong> ${on_demand_equivalent:,.2f}
                <br>
                <strong>Actual Savings Plans Cost:</strong> ${actual_sp_cost:,.2f}
                <br>
                <strong>Net Savings:</strong> ${net_savings:,.2f}
            </p>
"""

    if breakdown_by_type:
        html += """
            <h3 style="margin-top: 20px; color: #232f3e;">Savings Plans Breakdown by Type</h3>
            <table>
                <thead>
                    <tr>
                        <th>Plan Type</th>
                        <th>Active Plans</th>
                        <th>Total Hourly Commitment</th>
                        <th>Monthly Commitment</th>
                    </tr>
                </thead>
                <tbody>
"""
        for plan_type, type_data in breakdown_by_type.items():
            plans_count_type = type_data.get("plans_count", 0)
            total_commitment_type = type_data.get("total_commitment", 0.0)
            monthly_commitment = total_commitment_type * 730

            plan_type_display = plan_type
            if "Compute" in plan_type:
                plan_type_display = "Compute Savings Plans"
            elif "SageMaker" in plan_type:
                plan_type_display = "SageMaker Savings Plans"
            elif "EC2Instance" in plan_type:
                plan_type_display = "EC2 Instance Savings Plans"

            html += f"""
                    <tr>
                        <td><strong>{plan_type_display}</strong></td>
                        <td>{plans_count_type}</td>
                        <td class="metric">${total_commitment_type:.4f}/hr</td>
                        <td class="metric">${monthly_commitment:,.2f}/mo</td>
                    </tr>
"""
        html += """
                </tbody>
            </table>
"""

    html += f"""
        </div>

        <div class="footer">
            <p><strong>Savings Plans Autopilot</strong> - Automated Coverage & Savings Report</p>
            <p>Generated: {report_timestamp}</p>
        </div>
    </div>
"""

    # Prepare chart data from coverage timeseries
    chart_data = _prepare_chart_data(coverage_data)

    html += f"""
    <script>
        const ctx = document.getElementById('usageChart');

        const chartData = {chart_data};

        new Chart(ctx, {{
            type: 'bar',
            data: {{
                labels: chartData.labels,
                datasets: [
                    {{
                        label: 'Covered by Savings Plans',
                        data: chartData.covered,
                        backgroundColor: 'rgba(86, 171, 47, 0.7)',
                        borderColor: 'rgba(86, 171, 47, 1)',
                        borderWidth: 1,
                        stack: 'stack0'
                    }},
                    {{
                        label: 'On-Demand Cost',
                        data: chartData.ondemand,
                        backgroundColor: 'rgba(244, 107, 69, 0.7)',
                        borderColor: 'rgba(244, 107, 69, 1)',
                        borderWidth: 1,
                        stack: 'stack0'
                    }}
                ]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                interaction: {{
                    mode: 'index',
                    intersect: false
                }},
                plugins: {{
                    title: {{
                        display: true,
                        text: 'Hourly Usage: On-Demand vs Covered by Savings Plans',
                        font: {{ size: 16 }}
                    }},
                    legend: {{
                        display: true,
                        position: 'top'
                    }},
                    tooltip: {{
                        callbacks: {{
                            title: function(tooltipItems) {{
                                const index = tooltipItems[0].dataIndex;
                                const timestamp = chartData.timestamps[index];

                                // Parse timestamp and get day of week
                                const date = new Date(timestamp);
                                const days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
                                const dayName = days[date.getDay()];

                                // Format: "01-17 06:00 (Friday)"
                                const label = tooltipItems[0].label;
                                return label + ' (' + dayName + ')';
                            }},
                            footer: function(tooltipItems) {{
                                let covered = 0;
                                let ondemand = 0;

                                tooltipItems.forEach(function(item) {{
                                    if (item.dataset.label.includes('Covered')) {{
                                        covered = item.parsed.y;
                                    }} else {{
                                        ondemand = item.parsed.y;
                                    }}
                                }});

                                const total = covered + ondemand;
                                const coveragePercent = total > 0 ? (covered / total * 100).toFixed(1) : 0;

                                return 'Total: $' + total.toFixed(2) + '\\nCoverage: ' + coveragePercent + '%';
                            }}
                        }}
                    }}
                }},
                scales: {{
                    x: {{
                        stacked: true,
                        title: {{
                            display: true,
                            text: 'Time Period'
                        }}
                    }},
                    y: {{
                        stacked: true,
                        title: {{
                            display: true,
                            text: 'Cost (USD)'
                        }},
                        ticks: {{
                            callback: function(value) {{
                                return '$' + value.toFixed(2);
                            }}
                        }}
                    }}
                }}
            }}
        }});
    </script>
</body>
</html>
"""

    logger.info(f"HTML report generated ({len(html)} bytes)")
    return html


def generate_json_report(
    coverage_data: dict[str, Any],
    savings_data: dict[str, Any],
    config: dict[str, Any] | None = None,
) -> str:
    """
    Generate JSON report with coverage trends and savings metrics.

    Args:
        coverage_data: Coverage data from SpendingAnalyzer
        savings_data: Savings Plans summary from savings_plans_metrics
        config: Configuration parameters used for the report

    Returns:
        str: JSON report content
    """
    logger.info("Generating JSON report")
    config = config or {}

    report_timestamp = datetime.now(UTC).isoformat()

    # Extract coverage summary
    compute_summary = coverage_data.get("compute", {}).get("summary", {})
    database_summary = coverage_data.get("database", {}).get("summary", {})
    sagemaker_summary = coverage_data.get("sagemaker", {}).get("summary", {})

    # Extract savings data
    actual_savings = savings_data.get("actual_savings", {})
    breakdown_by_type = actual_savings.get("breakdown_by_type", {})

    # Format breakdown as array
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

    report = {
        "report_metadata": {
            "generated_at": report_timestamp,
            "report_type": "savings_plans_coverage_and_savings",
            "generator": "sp-autopilot-reporter",
        },
        "report_parameters": {
            "lookback_days": config.get("lookback_days"),
            "granularity": config.get("granularity"),
            "enable_compute_sp": config.get("enable_compute_sp"),
            "enable_database_sp": config.get("enable_database_sp"),
            "enable_sagemaker_sp": config.get("enable_sagemaker_sp"),
            "low_utilization_threshold": config.get("low_utilization_threshold"),
        },
        "coverage_summary": {
            "compute": {
                "avg_coverage_percentage": round(compute_summary.get("avg_coverage", 0.0), 2),
                "avg_hourly_spend": round(compute_summary.get("avg_hourly_total", 0.0), 4),
            },
            "database": {
                "avg_coverage_percentage": round(database_summary.get("avg_coverage", 0.0), 2),
                "avg_hourly_spend": round(database_summary.get("avg_hourly_total", 0.0), 4),
            },
            "sagemaker": {
                "avg_coverage_percentage": round(sagemaker_summary.get("avg_coverage", 0.0), 2),
                "avg_hourly_spend": round(sagemaker_summary.get("avg_hourly_total", 0.0), 4),
            },
        },
        "savings_summary": {
            "active_plans_count": savings_data.get("plans_count", 0),
            "total_hourly_commitment": round(savings_data.get("total_commitment", 0.0), 4),
            "total_monthly_commitment": round(savings_data.get("total_commitment", 0.0) * 730, 2),
            "average_utilization_percentage": round(
                savings_data.get("average_utilization", 0.0), 2
            ),
        },
        "actual_savings": {
            "sp_cost": round(actual_savings.get("actual_sp_cost", 0.0), 2),
            "on_demand_cost": round(actual_savings.get("on_demand_equivalent_cost", 0.0), 2),
            "net_savings": round(actual_savings.get("net_savings", 0.0), 2),
            "savings_percentage": round(actual_savings.get("savings_percentage", 0.0), 2),
            "breakdown": breakdown_array,
        },
        "active_savings_plans": savings_data.get("plans", []),
    }

    json_content = json.dumps(report, indent=2, default=str)
    logger.info(f"JSON report generated ({len(json_content)} bytes)")
    return json_content


def generate_csv_report(
    coverage_data: dict[str, Any],
    savings_data: dict[str, Any],
    config: dict[str, Any] | None = None,
) -> str:
    """
    Generate CSV report with coverage trends and savings metrics.

    Args:
        coverage_data: Coverage data from SpendingAnalyzer
        savings_data: Savings Plans summary from savings_plans_metrics

    Returns:
        str: CSV report content
    """
    logger.info("Generating CSV report")

    report_timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")

    # Extract summaries
    compute_summary = coverage_data.get("compute", {}).get("summary", {})
    database_summary = coverage_data.get("database", {}).get("summary", {})
    sagemaker_summary = coverage_data.get("sagemaker", {}).get("summary", {})
    actual_savings = savings_data.get("actual_savings", {})

    csv_parts = [
        "# Savings Plans Coverage & Savings Report",
        f"# Generated: {report_timestamp}",
        "",
        "## Summary",
        "metric,value",
        f"active_plans_count,{savings_data.get('plans_count', 0)}",
        f"total_hourly_commitment,{savings_data.get('total_commitment', 0.0):.4f}",
        f"total_monthly_commitment,{savings_data.get('total_commitment', 0.0) * 730:.2f}",
        f"average_utilization_percentage,{savings_data.get('average_utilization', 0.0):.2f}",
        f"compute_avg_coverage,{compute_summary.get('avg_coverage', 0.0):.2f}",
        f"database_avg_coverage,{database_summary.get('avg_coverage', 0.0):.2f}",
        f"sagemaker_avg_coverage,{sagemaker_summary.get('avg_coverage', 0.0):.2f}",
        f"actual_sp_cost,{actual_savings.get('actual_sp_cost', 0.0):.2f}",
        f"on_demand_equivalent_cost,{actual_savings.get('on_demand_equivalent_cost', 0.0):.2f}",
        f"net_savings,{actual_savings.get('net_savings', 0.0):.2f}",
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
            f"{plan.get('hourly_commitment', 0.0):.4f},"
            f"{plan.get('start_date', '')},"
            f"{plan.get('end_date', '')}"
        )

    csv_content = "\n".join(csv_parts)
    logger.info(f"CSV report generated ({len(csv_content)} bytes)")
    return csv_content

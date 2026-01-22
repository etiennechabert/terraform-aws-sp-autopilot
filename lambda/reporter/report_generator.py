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
        str: JSON string with chart data for all tabs (global, compute, database, sagemaker)
    """
    # Build timeseries maps for each SP type and global aggregate
    timeseries_maps = {
        "global": {},
        "compute": {},
        "database": {},
        "sagemaker": {},
    }

    # Collect all unique timestamps and build per-type data
    all_timestamps = set()

    for sp_type in ["compute", "database", "sagemaker"]:
        timeseries = coverage_data.get(sp_type, {}).get("timeseries", [])
        for item in timeseries:
            timestamp = item.get("timestamp", "")
            covered = item.get("covered", 0.0)
            total = item.get("total", 0.0)
            ondemand = total - covered

            all_timestamps.add(timestamp)

            # Store in per-type map
            if timestamp not in timeseries_maps[sp_type]:
                timeseries_maps[sp_type][timestamp] = {
                    "covered": 0.0,
                    "ondemand": 0.0,
                    "total": 0.0,
                }
            timeseries_maps[sp_type][timestamp]["covered"] += covered
            timeseries_maps[sp_type][timestamp]["ondemand"] += ondemand
            timeseries_maps[sp_type][timestamp]["total"] += total

            # Aggregate into global
            if timestamp not in timeseries_maps["global"]:
                timeseries_maps["global"][timestamp] = {
                    "covered": 0.0,
                    "ondemand": 0.0,
                    "total": 0.0,
                }
            timeseries_maps["global"][timestamp]["covered"] += covered
            timeseries_maps["global"][timestamp]["ondemand"] += ondemand
            timeseries_maps["global"][timestamp]["total"] += total

    # Sort timestamps
    sorted_timestamps = sorted(all_timestamps)

    # Build chart data for each type
    def build_chart_data_for_type(type_name):
        labels = []
        timestamps = []
        covered_values = []
        ondemand_values = []
        total_costs = []

        type_map = timeseries_maps[type_name]

        for ts in sorted_timestamps:
            # Format timestamp for display
            if "T" in ts:
                date_part, time_part = ts.split("T")
                time_part = time_part[:5]  # HH:MM
                label = f"{date_part[5:]} {time_part}" if len(sorted_timestamps) > 24 else time_part
            else:
                label = ts[:10]  # Just date for daily granularity

            labels.append(label)
            timestamps.append(ts)

            # Get values for this type (may be 0 if no data)
            data = type_map.get(ts, {"covered": 0.0, "ondemand": 0.0, "total": 0.0})
            covered_values.append(round(data["covered"], 2))
            ondemand_values.append(round(data["ondemand"], 2))
            total_costs.append(round(data["total"], 2))

        # Calculate statistics for optimal coverage recommendation
        total_costs_nonzero = [c for c in total_costs if c > 0]
        stats = {}
        if total_costs_nonzero:
            sorted_costs = sorted(total_costs_nonzero)
            n = len(sorted_costs)
            stats = {
                "min": round(sorted_costs[0], 2),
                "max": round(sorted_costs[-1], 2),
                "p50": round(sorted_costs[int(n * 0.50)], 2),
                "p75": round(sorted_costs[int(n * 0.75)], 2),
                "p90": round(sorted_costs[int(n * 0.90)], 2),
                "p95": round(sorted_costs[int(n * 0.95)], 2),
            }

        return {
            "labels": labels,
            "timestamps": timestamps,
            "covered": covered_values,
            "ondemand": ondemand_values,
            "stats": stats,
        }

    all_chart_data = {
        "global": build_chart_data_for_type("global"),
        "compute": build_chart_data_for_type("compute"),
        "database": build_chart_data_for_type("database"),
        "sagemaker": build_chart_data_for_type("sagemaker"),
    }

    return json.dumps(all_chart_data)


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
            margin-bottom: 15px;
        }}
        .summary {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 12px;
            margin-bottom: 20px;
        }}
        .summary-card {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 12px 15px;
            border-radius: 6px;
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
            margin: 0 0 6px 0;
            font-size: 0.8em;
            font-weight: 500;
            opacity: 0.9;
        }}
        .summary-card .value {{
            font-size: 1.6em;
            font-weight: bold;
            margin: 0;
        }}
        .section {{
            margin-bottom: 25px;
        }}
        h2 {{
            color: #232f3e;
            border-bottom: 2px solid #e0e0e0;
            padding-bottom: 6px;
            margin-bottom: 12px;
            font-size: 1.3em;
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
        .tabs {{
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
            border-bottom: 2px solid #e0e0e0;
        }}
        .tab {{
            padding: 12px 24px;
            cursor: pointer;
            background: none;
            border: none;
            border-bottom: 3px solid transparent;
            font-size: 14px;
            font-weight: 500;
            color: #6c757d;
            transition: all 0.3s ease;
        }}
        .tab:hover {{
            color: #232f3e;
            background-color: #f8f9fa;
        }}
        .tab.active {{
            color: #232f3e;
            border-bottom-color: #ff9900;
        }}
        .tab-content {{
            display: none;
        }}
        .tab-content.active {{
            display: block;
        }}
        .tab-metrics {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
            padding: 15px;
            background-color: #f8f9fa;
            border-radius: 8px;
        }}
        .metric-card {{
            background: white;
            padding: 15px;
            border-radius: 6px;
            border-left: 4px solid #667eea;
        }}
        .metric-card.green {{
            border-left-color: #56ab2f;
        }}
        .metric-card.orange {{
            border-left-color: #ff9900;
        }}
        .metric-card h4 {{
            margin: 0 0 8px 0;
            font-size: 0.85em;
            color: #6c757d;
            font-weight: 500;
        }}
        .metric-card .metric-value {{
            font-size: 1.5em;
            font-weight: bold;
            color: #232f3e;
        }}
        .optimization-section {{
            margin-top: 20px;
            padding: 15px;
            background-color: #fff3cd;
            border-left: 4px solid #ffc107;
            border-radius: 6px;
        }}
        .optimization-section h4 {{
            margin: 0 0 10px 0;
            font-size: 0.95em;
            color: #856404;
            font-weight: 600;
        }}
        .percentile-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
            gap: 10px;
            margin-top: 10px;
        }}
        .percentile-item {{
            text-align: center;
            padding: 8px;
            background: white;
            border-radius: 4px;
        }}
        .percentile-label {{
            font-size: 0.75em;
            color: #6c757d;
            margin-bottom: 4px;
        }}
        .percentile-value {{
            font-size: 1.1em;
            font-weight: bold;
            color: #232f3e;
        }}
        .recommendation {{
            margin-top: 12px;
            padding: 10px;
            background: white;
            border-radius: 4px;
            font-size: 0.9em;
            color: #856404;
        }}
        .params-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 10px;
            padding: 15px;
            background-color: #f8f9fa;
            border-radius: 6px;
        }}
        .param-item {{
            display: flex;
            justify-content: space-between;
            padding: 8px 12px;
            background: white;
            border-radius: 4px;
            font-size: 0.9em;
        }}
        .param-label {{
            font-weight: 600;
            color: #232f3e;
        }}
        .param-value {{
            color: #6c757d;
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
            <div class="params-grid">
                <div class="param-item">
                    <span class="param-label">Lookback Period</span>
                    <span class="param-value">{config.get("lookback_days", "N/A")} days</span>
                </div>
                <div class="param-item">
                    <span class="param-label">Granularity</span>
                    <span class="param-value">{config.get("granularity", "N/A")}</span>
                </div>
                <div class="param-item">
                    <span class="param-label">Compute SP</span>
                    <span class="param-value">{"✓ Enabled" if config.get("enable_compute_sp", True) else "✗ Disabled"}</span>
                </div>
                <div class="param-item">
                    <span class="param-label">Database SP</span>
                    <span class="param-value">{"✓ Enabled" if config.get("enable_database_sp", False) else "✗ Disabled"}</span>
                </div>
                <div class="param-item">
                    <span class="param-label">SageMaker SP</span>
                    <span class="param-value">{"✓ Enabled" if config.get("enable_sagemaker_sp", False) else "✗ Disabled"}</span>
                </div>
                <div class="param-item">
                    <span class="param-label">Low Util. Threshold</span>
                    <span class="param-value">{config.get("low_utilization_threshold", "N/A")}%</span>
                </div>
            </div>
        </div>

        <div class="section">
            <h2>Usage Over Time</h2>

            <div class="tabs">
                <button class="tab active" onclick="switchTab('global')">Global (All Types)</button>
                <button class="tab" onclick="switchTab('compute')">Compute</button>
                <button class="tab" onclick="switchTab('database')">Database</button>
                <button class="tab" onclick="switchTab('sagemaker')">SageMaker</button>
            </div>

            <div id="global-tab" class="tab-content active">
                <div class="chart-container">
                    <canvas id="globalChart"></canvas>
                </div>
            </div>

            <div id="compute-tab" class="tab-content">
                <div id="compute-metrics"></div>
                <div class="chart-container">
                    <canvas id="computeChart"></canvas>
                </div>
            </div>

            <div id="database-tab" class="tab-content">
                <div id="database-metrics"></div>
                <div class="chart-container">
                    <canvas id="databaseChart"></canvas>
                </div>
            </div>

            <div id="sagemaker-tab" class="tab-content">
                <div id="sagemaker-metrics"></div>
                <div class="chart-container">
                    <canvas id="sagemakerChart"></canvas>
                </div>
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

    # Extract per-type metrics
    compute_summary = coverage_data.get("compute", {}).get("summary", {})
    database_summary = coverage_data.get("database", {}).get("summary", {})
    sagemaker_summary = coverage_data.get("sagemaker", {}).get("summary", {})

    target_coverage = config.get("coverage_target_percent", 90.0)

    # Extract savings breakdown by type
    breakdown_by_type = savings_data.get("actual_savings", {}).get("breakdown_by_type", {})

    def get_type_metrics(sp_type_key, summary, sp_type_name):
        """Calculate metrics for a specific SP type"""
        current_coverage = summary.get("avg_coverage", 0.0)
        avg_total_cost = summary.get("avg_hourly_total", 0.0)
        avg_covered_cost = summary.get("avg_hourly_covered", 0.0)
        avg_ondemand_cost = avg_total_cost - avg_covered_cost

        # Get utilization for this type
        # Check if we have SP plans of this type and extract utilization
        type_utilization = 0.0
        type_keywords = {
            "Compute": ["compute"],
            "Database": ["rds", "database"],
            "SageMaker": ["sagemaker"],
        }
        keywords = type_keywords.get(sp_type_name, [sp_type_name.lower()])

        for plan in savings_data.get("plans", []):
            plan_type = plan.get("plan_type", "").lower()
            if any(keyword in plan_type for keyword in keywords):
                # If we have plans of this type, use overall utilization as approximation
                # Note: This is a simplification - ideally we'd query CE API per type
                type_utilization = average_utilization
                break

        # Actual savings achieved
        # Savings = what we would pay on-demand minus what we actually pay with SP
        # SP typically offers 30-40% discount, so if covered_cost is what we pay:
        # On-demand equivalent = covered_cost / (1 - discount_rate)
        # Assuming 35% average discount: on_demand_equiv = covered_cost / 0.65
        # Savings = on_demand_equiv - covered_cost
        discount_rate = 0.35
        ondemand_equivalent_for_covered = (
            avg_covered_cost / (1 - discount_rate) if avg_covered_cost > 0 else 0
        )
        actual_savings_hourly = ondemand_equivalent_for_covered - avg_covered_cost
        actual_savings_monthly = actual_savings_hourly * 730

        # Calculate potential additional savings if we reach target coverage
        if current_coverage < target_coverage and avg_total_cost > 0:
            # Additional coverage percentage points needed
            additional_coverage_points = target_coverage - current_coverage
            # Additional hourly cost that would be covered
            additional_covered_hourly = avg_total_cost * (additional_coverage_points / 100)
            # Savings on that additional coverage (35% discount)
            potential_additional_hourly = additional_covered_hourly * discount_rate
            potential_additional_monthly = potential_additional_hourly * 730
        else:
            potential_additional_monthly = 0.0

        return {
            "current_coverage": current_coverage,
            "utilization": type_utilization,
            "actual_savings_monthly": actual_savings_monthly,
            "potential_additional_savings": potential_additional_monthly,
            "target_coverage": target_coverage,
        }

    compute_metrics = get_type_metrics("compute", compute_summary, "Compute")
    database_metrics = get_type_metrics("database", database_summary, "Database")
    sagemaker_metrics = get_type_metrics("sagemaker", sagemaker_summary, "SageMaker")

    metrics_json = json.dumps(
        {"compute": compute_metrics, "database": database_metrics, "sagemaker": sagemaker_metrics}
    )

    html += f"""
    <script>
        const allChartData = {chart_data};
        const metricsData = {metrics_json};

        // Tab switching function
        function switchTab(tabName) {{
            // Hide all tab contents
            document.querySelectorAll('.tab-content').forEach(function(content) {{
                content.classList.remove('active');
            }});

            // Remove active class from all tabs
            document.querySelectorAll('.tab').forEach(function(tab) {{
                tab.classList.remove('active');
            }});

            // Show selected tab content
            document.getElementById(tabName + '-tab').classList.add('active');

            // Add active class to clicked tab
            event.target.classList.add('active');
        }}

        // Function to create chart for a specific type
        function createChart(canvasId, chartData, title) {{
            const ctx = document.getElementById(canvasId);

            return new Chart(ctx, {{
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
                            text: title,
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

                                    const date = new Date(timestamp);
                                    const days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
                                    const dayName = days[date.getDay()];

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
        }}

        // Function to render metrics for a specific type
        function renderMetrics(containerId, metrics, typeName, stats) {{
            const container = document.getElementById(containerId);

            // Determine utilization color class
            let utilizationClass = '';
            if (metrics.utilization >= 95) {{
                utilizationClass = 'green';
            }} else if (metrics.utilization >= 80) {{
                utilizationClass = 'orange';
            }}

            let optimizationHtml = '';
            if (stats && Object.keys(stats).length > 0) {{
                // Calculate optimal coverage recommendation based on percentiles
                const range = stats.max - stats.min;
                const variability = (range / stats.max * 100).toFixed(0);

                let recommendation = '';
                if (variability < 20) {{
                    recommendation = `Low variability (${{variability}}%). Consider covering close to P95 ($$${{stats.p95}}/hr) for maximum savings with minimal risk.`;
                }} else if (variability < 40) {{
                    recommendation = `Moderate variability (${{variability}}%). Consider covering P75-P90 ($$${{stats.p75}}-$$${{stats.p90}}/hr) to balance savings and risk.`;
                }} else {{
                    recommendation = `High variability (${{variability}}%). Consider covering P50-P75 ($$${{stats.p50}}-$$${{stats.p75}}/hr) to avoid over-commitment during low usage periods.`;
                }}

                optimizationHtml = `
                    <div class="optimization-section">
                        <h4>📊 Coverage Optimization Guide</h4>
                        <div class="percentile-grid">
                            <div class="percentile-item">
                                <div class="percentile-label">Min Hourly</div>
                                <div class="percentile-value">$$${{stats.min}}</div>
                            </div>
                            <div class="percentile-item">
                                <div class="percentile-label">P50 (Median)</div>
                                <div class="percentile-value">$$${{stats.p50}}</div>
                            </div>
                            <div class="percentile-item">
                                <div class="percentile-label">P75</div>
                                <div class="percentile-value">$$${{stats.p75}}</div>
                            </div>
                            <div class="percentile-item">
                                <div class="percentile-label">P90</div>
                                <div class="percentile-value">$$${{stats.p90}}</div>
                            </div>
                            <div class="percentile-item">
                                <div class="percentile-label">P95</div>
                                <div class="percentile-value">$$${{stats.p95}}</div>
                            </div>
                            <div class="percentile-item">
                                <div class="percentile-label">Max Hourly</div>
                                <div class="percentile-value">$$${{stats.max}}</div>
                            </div>
                        </div>
                        <div class="recommendation">
                            <strong>💡 Recommendation:</strong> ${{recommendation}}
                        </div>
                    </div>
                `;
            }}

            const html = `
                <div class="tab-metrics">
                    <div class="metric-card">
                        <h4>Current Coverage</h4>
                        <div class="metric-value">${{metrics.current_coverage.toFixed(1)}}%</div>
                    </div>
                    <div class="metric-card ${{utilizationClass}}">
                        <h4>Utilization</h4>
                        <div class="metric-value">${{metrics.utilization > 0 ? metrics.utilization.toFixed(1) + '%' : 'N/A'}}</div>
                    </div>
                    <div class="metric-card green">
                        <h4>Actual Savings (30 days)</h4>
                        <div class="metric-value">$$${{metrics.actual_savings_monthly.toLocaleString('en-US', {{maximumFractionDigits: 0}})}}</div>
                    </div>
                    <div class="metric-card orange">
                        <h4>Potential at ${{metrics.target_coverage}}% Target</h4>
                        <div class="metric-value">+$$${{metrics.potential_additional_savings.toLocaleString('en-US', {{maximumFractionDigits: 0}})}}</div>
                    </div>
                </div>
                ${{optimizationHtml}}
            `;
            container.innerHTML = html;
        }}

        // Create all charts
        createChart('globalChart', allChartData.global, 'Hourly Usage: On-Demand vs Covered (All Types)');
        createChart('computeChart', allChartData.compute, 'Compute Savings Plans - Hourly Usage');
        createChart('databaseChart', allChartData.database, 'Database Savings Plans - Hourly Usage');
        createChart('sagemakerChart', allChartData.sagemaker, 'SageMaker Savings Plans - Hourly Usage');

        // Render metrics for each type
        renderMetrics('compute-metrics', metricsData.compute, 'Compute', allChartData.compute.stats);
        renderMetrics('database-metrics', metricsData.database, 'Database', allChartData.database.stats);
        renderMetrics('sagemaker-metrics', metricsData.sagemaker, 'SageMaker', allChartData.sagemaker.stats);
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

"""
HTML Report Generator for Savings Plans Coverage & Savings Reports.

This module generates HTML-formatted reports with coverage trends,
savings metrics, and active Savings Plans data.
"""

import logging
from datetime import UTC, datetime
from typing import Any


# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def generate_html_report(
    coverage_history: list[dict[str, Any]], savings_data: dict[str, Any]
) -> str:
    """
    Generate HTML report with coverage trends and savings metrics.

    Args:
        coverage_history: List of coverage data points by day
        savings_data: Savings Plans data including commitment and estimated savings

    Returns:
        str: HTML report content
    """
    logger.info("Generating HTML report")

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
    if len(coverage_history) >= 2:
        first_coverage = coverage_history[0].get("coverage_percentage", 0.0)
        last_coverage = coverage_history[-1].get("coverage_percentage", 0.0)
        trend = last_coverage - first_coverage
        trend_symbol = "↑" if trend > 0 else "↓" if trend < 0 else "→"
        trend_color = "#28a745" if trend > 0 else "#dc3545" if trend < 0 else "#6c757d"
    else:
        trend_symbol = "→"
        trend_color = "#6c757d"

    # Build HTML content using string builder pattern
    html_parts = []
    html_parts.append(f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Savings Plans Coverage & Savings Report</title>
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
        .trend {{
            font-size: 1.2em;
            font-weight: bold;
        }}
        .no-data {{
            text-align: center;
            padding: 40px;
            color: #6c757d;
            font-style: italic;
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
                <h3>Average Coverage ({len(coverage_history)} days)</h3>
                <div class="value">{avg_coverage:.1f}%</div>
            </div>
            <div class="summary-card orange">
                <h3>Active Plans</h3>
                <div class="value">{savings_data.get("plans_count", 0)}</div>
            </div>
            <div class="summary-card">
                <h3>Actual Net Savings (30 days)</h3>
                <div class="value">${savings_data.get("actual_savings", {}).get("net_savings", 0):,.0f}</div>
            </div>
            <div class="summary-card green">
                <h3>Savings Percentage</h3>
                <div class="value">{savings_data.get("actual_savings", {}).get("savings_percentage", 0):.1f}%</div>
            </div>
        </div>

        <div class="section">
            <h2>Coverage Trends <span class="trend" style="color: {trend_color};">{trend_symbol}</span></h2>
""")

    # Coverage history table
    if coverage_history:
        html_parts.append("""
            <table>
                <thead>
                    <tr>
                        <th>Date</th>
                        <th>Coverage %</th>
                        <th>Covered Hours</th>
                        <th>On-Demand Hours</th>
                        <th>Total Hours</th>
                    </tr>
                </thead>
                <tbody>
""")
        for item in coverage_history:
            date = item.get("date", "Unknown")
            coverage_pct = item.get("coverage_percentage", 0.0)
            covered_hours = item.get("covered_hours", 0.0)
            on_demand_hours = item.get("on_demand_hours", 0.0)
            total_hours = item.get("total_hours", 0.0)

            html_parts.append(f"""
                    <tr>
                        <td>{date}</td>
                        <td class="metric">{coverage_pct:.2f}%</td>
                        <td>{covered_hours:,.0f}</td>
                        <td>{on_demand_hours:,.0f}</td>
                        <td>{total_hours:,.0f}</td>
                    </tr>
""")
        html_parts.append("""
                </tbody>
            </table>
""")
    else:
        html_parts.append("""
            <div class="no-data">No coverage data available</div>
""")

    html_parts.append("""
        </div>

        <div class="section">
            <h2>Active Savings Plans</h2>
""")

    # Savings Plans table
    plans = savings_data.get("plans", [])
    if plans:
        total_commitment = savings_data.get("total_commitment", 0.0)
        avg_utilization = savings_data.get("average_utilization", 0.0)

        html_parts.append(f"""
            <p>
                <strong>Total Hourly Commitment:</strong> ${total_commitment:.4f}/hour
                (${total_commitment * 730:,.2f}/month)
                <br>
                <strong>Average Utilization (7 days):</strong> {avg_utilization:.2f}%
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
""")
        for plan in plans:
            plan_id = plan.get("plan_id", "Unknown")
            plan_type = plan.get("plan_type", "Unknown")
            hourly_commitment = plan.get("hourly_commitment", 0.0)
            term_years = plan.get("term_years", 0)
            payment_option = plan.get("payment_option", "Unknown")
            start_date = plan.get("start_date", "Unknown")
            end_date = plan.get("end_date", "Unknown")

            # Format dates (extract date part from ISO timestamp)
            if "T" in start_date:
                start_date = start_date.split("T")[0]
            if "T" in end_date:
                end_date = end_date.split("T")[0]

            html_parts.append(f"""
                    <tr>
                        <td style="font-family: monospace; font-size: 0.85em;">{plan_id[:20]}...</td>
                        <td>{plan_type}</td>
                        <td class="metric">${hourly_commitment:.4f}/hr</td>
                        <td>{term_years} year(s)</td>
                        <td>{payment_option}</td>
                        <td>{start_date}</td>
                        <td>{end_date}</td>
                    </tr>
""")
        html_parts.append("""
                </tbody>
            </table>
""")
    else:
        html_parts.append("""
            <div class="no-data">No active Savings Plans found</div>
""")

    # Actual Savings Summary Section
    actual_savings = savings_data.get("actual_savings", {})
    net_savings = actual_savings.get("net_savings", 0.0)
    on_demand_equivalent = actual_savings.get("on_demand_equivalent_cost", 0.0)
    actual_sp_cost = actual_savings.get("actual_sp_cost", 0.0)
    savings_pct = actual_savings.get("savings_percentage", 0.0)
    breakdown_by_type = actual_savings.get("breakdown_by_type", {})

    html_parts.append("""
        </div>

        <div class="section">
            <h2>Actual Savings Summary (Last 30 Days)</h2>
""")

    html_parts.append(f"""
            <p>
                <strong>Net Savings:</strong> <span style="color: #28a745; font-size: 1.2em; font-weight: bold;">${net_savings:,.2f}</span>
                <span style="color: #6c757d; margin-left: 10px;">({savings_pct:.2f}% savings)</span>
            </p>
            <p>
                <strong>On-Demand Equivalent Cost:</strong> ${on_demand_equivalent:,.2f}
                <br>
                <strong>Actual Savings Plans Cost:</strong> ${actual_sp_cost:,.2f}
                <br>
                <strong>Net Savings:</strong> ${net_savings:,.2f}
            </p>
""")

    # Breakdown by Plan Type
    if breakdown_by_type:
        html_parts.append("""
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
""")

        for plan_type, type_data in breakdown_by_type.items():
            plans_count = type_data.get("plans_count", 0)
            total_commitment = type_data.get("total_commitment", 0.0)
            monthly_commitment = total_commitment * 730

            # Map plan types to readable names
            plan_type_display = plan_type
            if "Compute" in plan_type:
                plan_type_display = "Compute Savings Plans"
            elif "SageMaker" in plan_type:
                plan_type_display = "SageMaker Savings Plans"
            elif "EC2Instance" in plan_type:
                plan_type_display = "EC2 Instance Savings Plans"

            html_parts.append(f"""
                    <tr>
                        <td><strong>{plan_type_display}</strong></td>
                        <td>{plans_count}</td>
                        <td class="metric">${total_commitment:.4f}/hr</td>
                        <td class="metric">${monthly_commitment:,.2f}/mo</td>
                    </tr>
""")

        html_parts.append("""
                </tbody>
            </table>
""")
    else:
        html_parts.append("""
            <p style="color: #6c757d; font-style: italic;">No savings plan type breakdown available</p>
""")

    html_parts.append(f"""
        </div>

        <div class="footer">
            <p><strong>Savings Plans Autopilot</strong> - Automated Coverage & Savings Report</p>
            <p>Report Period: {len(coverage_history)} days | Generated: {report_timestamp}</p>
        </div>
    </div>
</body>
</html>
""")

    html = "".join(html_parts)
    logger.info(f"HTML report generated ({len(html)} bytes)")
    return html

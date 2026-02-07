"""
Report Generation Module.

Generates Savings Plans reports in multiple formats (HTML, JSON, CSV).
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from shared import sp_calculations
from shared.local_mode import is_local_mode
from shared.optimal_coverage import calculate_optimal_coverage


logger = logging.getLogger(__name__)


def _get_type_metrics_for_report(
    summary: dict[str, Any], sp_type_name: str, breakdown_by_type: dict[str, Any]
) -> dict[str, Any]:
    """Calculate metrics for a specific SP type for HTML report."""
    current_coverage = summary.get("avg_coverage_total", 0.0)
    avg_total_cost = summary.get("avg_hourly_total", 0.0)
    avg_covered_cost = summary.get("avg_hourly_covered", 0.0)
    avg_uncovered_cost = avg_total_cost - avg_covered_cost

    type_breakdown = breakdown_by_type.get(sp_type_name, {})
    type_savings_pct = type_breakdown.get("savings_percentage", 0.0)
    type_utilization = type_breakdown.get("average_utilization", 0.0)
    net_savings_hourly = type_breakdown.get("net_savings_hourly", 0.0)
    total_commitment = type_breakdown.get("total_commitment", 0.0)

    total_spend_hourly = avg_total_cost
    uncovered_spend_hourly = avg_uncovered_cost

    discount_pct = type_savings_pct if current_coverage > 0 and type_savings_pct > 0 else 0.0

    # Pre-calculate on-demand equivalent coverage to avoid formula duplication in JavaScript
    on_demand_coverage = sp_calculations.coverage_from_commitment(total_commitment, discount_pct)

    return {
        "current_coverage": current_coverage,
        "utilization": type_utilization,
        "actual_savings_hourly": net_savings_hourly,
        "savings_percentage": discount_pct,
        "sp_commitment_hourly": total_commitment,
        "on_demand_coverage_hourly": on_demand_coverage,  # Pre-calculated to eliminate JS duplication
        "uncovered_spend_hourly": uncovered_spend_hourly,
        "total_spend_hourly": total_spend_hourly,
        "total_commitment": total_commitment,
    }


def _get_coverage_class(coverage: float) -> str:
    """Return CSS class based on coverage percentage."""
    if coverage >= 70:
        return "green"
    if coverage >= 30:
        return "orange"
    return "red"


def _get_utilization_class(utilization: float) -> str:
    """Return CSS class based on utilization percentage."""
    if utilization >= 95:
        return "green"
    if utilization >= 80:
        return "orange"
    return "red"


def _get_min_hourly_from_timeseries_data(sp_type_data: dict[str, Any]) -> float:
    """Extract minimum hourly cost from timeseries data."""
    timeseries = sp_type_data.get("timeseries", [])
    total_costs = []
    for item in timeseries:
        total = item.get("total", 0.0)
        if total > 0:
            total_costs.append(total)
    return min(total_costs) if total_costs else 0.0


def _prepare_html_report_data(
    coverage_data: dict[str, Any], savings_data: dict[str, Any], config: dict[str, Any]
) -> dict[str, Any]:
    """Prepare all data needed for HTML report generation."""
    now = datetime.now(UTC)
    lookback_days = config["lookback_days"]
    data_end_date = now.date()
    data_start_date = data_end_date - timedelta(days=lookback_days)

    # Extract coverage summaries
    compute_summary = coverage_data.get("compute", {}).get("summary", {})
    database_summary = coverage_data.get("database", {}).get("summary", {})
    sagemaker_summary = coverage_data.get("sagemaker", {}).get("summary", {})

    compute_coverage = compute_summary.get("avg_coverage_total", 0.0)
    database_coverage = database_summary.get("avg_coverage_total", 0.0)
    sagemaker_coverage = sagemaker_summary.get("avg_coverage_total", 0.0)

    # Calculate overall coverage
    total_hourly_spend = (
        compute_summary.get("avg_hourly_total", 0.0)
        + database_summary.get("avg_hourly_total", 0.0)
        + sagemaker_summary.get("avg_hourly_total", 0.0)
    )
    total_hourly_covered = (
        compute_summary.get("avg_hourly_covered", 0.0)
        + database_summary.get("avg_hourly_covered", 0.0)
        + sagemaker_summary.get("avg_hourly_covered", 0.0)
    )

    compute_min = _get_min_hourly_from_timeseries_data(coverage_data.get("compute", {}))
    database_min = _get_min_hourly_from_timeseries_data(coverage_data.get("database", {}))
    sagemaker_min = _get_min_hourly_from_timeseries_data(coverage_data.get("sagemaker", {}))
    total_min_hourly = compute_min + database_min + sagemaker_min

    overall_coverage = (
        (total_hourly_covered / total_min_hourly * 100) if total_min_hourly > 0 else 0.0
    )

    # Extract savings data
    actual_savings = savings_data.get("actual_savings", {})

    return {
        "report_timestamp": now.strftime("%Y-%m-%d %H:%M:%S UTC"),
        "data_period": f"{data_start_date.isoformat()} to {data_end_date.isoformat()}",
        "lookback_days": lookback_days,
        "compute_coverage": compute_coverage,
        "database_coverage": database_coverage,
        "sagemaker_coverage": sagemaker_coverage,
        "overall_coverage": overall_coverage,
        "overall_coverage_class": _get_coverage_class(overall_coverage),
        "total_hourly_spend": total_hourly_spend,
        "total_hourly_covered": total_hourly_covered,
        "plans_count": savings_data.get("plans_count", 0),
        "net_savings_hourly": actual_savings.get("net_savings_hourly", 0.0),
        "savings_percentage": actual_savings.get("savings_percentage", 0.0),
        "total_commitment": savings_data.get("total_commitment", 0.0),
        "average_utilization": savings_data.get("average_utilization", 0.0),
        "utilization_class": _get_utilization_class(savings_data.get("average_utilization", 0.0)),
        "on_demand_equivalent_hourly": actual_savings.get("on_demand_equivalent_hourly", 0.0),
        "breakdown_by_type": actual_savings.get("breakdown_by_type", {}),
    }


def generate_report(
    coverage_data: dict[str, Any],
    savings_data: dict[str, Any],
    report_format: str = "html",
    config: dict[str, Any] | None = None,
    raw_data: dict[str, Any] | None = None,
    preview_data: dict[str, Any] | None = None,
) -> str:
    """
    Generate report in specified format.

    Args:
        coverage_data: Coverage data from SpendingAnalyzer
        savings_data: Savings Plans summary from savings_plans_metrics
        report_format: Format - "html", "json", or "csv"
        config: Configuration parameters used for the report
        raw_data: Optional raw AWS API responses to include in the report
        preview_data: Optional scheduler preview data

    Returns:
        str: Generated report content

    Raises:
        ValueError: If report_format is invalid
    """
    if report_format == "json":
        return generate_json_report(coverage_data, savings_data, config)
    if report_format == "csv":
        return generate_csv_report(coverage_data, savings_data)
    if report_format == "html":
        return generate_html_report(coverage_data, savings_data, config, raw_data, preview_data)
    raise ValueError(f"Invalid report format: {report_format}")


def _build_timeseries_maps(coverage_data: dict[str, Any]) -> tuple[dict, set]:
    """Build timeseries maps for each SP type and collect all timestamps."""
    timeseries_maps = {
        "global": {},
        "compute": {},
        "database": {},
        "sagemaker": {},
    }
    all_timestamps = set()

    for sp_type in ["compute", "database", "sagemaker"]:
        timeseries = coverage_data.get(sp_type, {}).get("timeseries", [])
        for item in timeseries:
            timestamp = item.get("timestamp", "")
            covered = item.get("covered", 0.0)
            total = item.get("total", 0.0)
            ondemand = total - covered

            all_timestamps.add(timestamp)

            for target_type in [sp_type, "global"]:
                if timestamp not in timeseries_maps[target_type]:
                    timeseries_maps[target_type][timestamp] = {
                        "covered": 0.0,
                        "ondemand": 0.0,
                        "total": 0.0,
                    }
                timeseries_maps[target_type][timestamp]["covered"] += covered
                timeseries_maps[target_type][timestamp]["ondemand"] += ondemand
                timeseries_maps[target_type][timestamp]["total"] += total

    return timeseries_maps, all_timestamps


def _format_timestamp_label(ts: str, num_timestamps: int) -> str:
    """Format timestamp for chart display."""
    if "T" in ts:
        date_part, time_part = ts.split("T")
        time_part = time_part[:5]
        return f"{date_part[5:]} {time_part}" if num_timestamps > 24 else time_part
    return ts[:10]


def _calculate_cost_statistics(total_costs: list[float]) -> dict[str, float]:
    """Calculate percentile statistics for cost data."""
    total_costs_nonzero = [c for c in total_costs if c > 0]
    if not total_costs_nonzero:
        return {}

    sorted_costs = sorted(total_costs_nonzero)
    n = len(sorted_costs)
    return {
        "min": round(sorted_costs[0], 2),
        "max": round(sorted_costs[-1], 2),
        "p50": round(sorted_costs[int(n * 0.50)], 2),
        "p75": round(sorted_costs[int(n * 0.75)], 2),
        "p90": round(sorted_costs[int(n * 0.90)], 2),
        "p95": round(sorted_costs[int(n * 0.95)], 2),
    }


def _build_chart_data_for_type(type_map: dict, sorted_timestamps: list[str]) -> dict[str, Any]:
    """Build chart data for a specific SP type."""
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
) -> tuple[str, dict[str, Any]]:
    """
    Prepare chart data from coverage timeseries for Chart.js visualization.

    Args:
        coverage_data: Coverage data from SpendingAnalyzer with timeseries
        config: Configuration dict with savings_percentage (default: 30)

    Returns:
        tuple: (JSON string with chart data, dict with optimal coverage results)
    """
    config = config or {}
    timeseries_maps, all_timestamps = _build_timeseries_maps(coverage_data)
    sorted_timestamps = sorted(all_timestamps)

    all_chart_data = {
        type_name: _build_chart_data_for_type(timeseries_maps[type_name], sorted_timestamps)
        for type_name in ["global", "compute", "database", "sagemaker"]
    }

    optimal_results = _calculate_optimal_coverage(all_chart_data, savings_data)
    return json.dumps(all_chart_data), optimal_results


def _calculate_sp_type_optimal(
    sp_type: str, type_data: dict[str, Any], savings_percentage: float
) -> dict[str, Any]:
    """Calculate optimal coverage for a single SP type."""
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
    """
    Calculate optimal coverage per SP type.

    IMPORTANT: This Python implementation must stay in sync with
    docs/js/costCalculator.js::calculateOptimalCoverage()
    Any changes to the algorithm must be applied to both implementations.
    """
    actual_savings = savings_data.get("actual_savings", {})
    breakdown_by_type = actual_savings.get("breakdown_by_type", {})
    type_mapping = {"compute": "Compute", "database": "Database", "sagemaker": "SageMaker"}
    optimal_results = {}

    for sp_type in ["compute", "database", "sagemaker"]:
        type_breakdown = breakdown_by_type.get(type_mapping.get(sp_type, ""), {})
        type_savings_pct = type_breakdown.get("savings_percentage", 0.0)
        savings_percentage = type_savings_pct if type_savings_pct > 0 else 20.0

        result = _calculate_sp_type_optimal(sp_type, all_chart_data[sp_type], savings_percentage)
        if result:
            optimal_results[sp_type] = result

    # Calculate global optimal coverage
    overall_savings_pct = actual_savings.get("savings_percentage", 0.0)
    savings_percentage = overall_savings_pct if overall_savings_pct > 0 else 20.0
    optimal_results["savings_percentage_used"] = savings_percentage

    global_result = _calculate_sp_type_optimal(
        "global", all_chart_data["global"], savings_percentage
    )
    if global_result:
        optimal_results["global"] = global_result

    return optimal_results


def _build_strategy_tooltip(
    strategy_type: str,
    strategy_desc: str,
    config: dict[str, Any],
    is_configured: bool,
) -> str:
    """Build tooltip text for a strategy."""
    if strategy_type == "fixed":
        if is_configured:
            params = f"max purchase: {config.get('max_purchase_percent', 10.0):.0f}%"
        else:
            params = "default: max purchase 10%"
        return f"{strategy_desc} ({params}) | Configure: PURCHASE_STRATEGY_TYPE=fixed, MAX_PURCHASE_PERCENT"
    if strategy_type == "dichotomy":
        if is_configured:
            max_p = config.get("max_purchase_percent", 50.0)
            min_p = config.get("min_purchase_percent", 1.0)
            params = f"max: {max_p:.0f}%, min: {min_p:.0f}%"
        else:
            params = "default: max 50%, min 1%"
        return f"{strategy_desc} ({params}) | Configure: PURCHASE_STRATEGY_TYPE=dichotomy, MAX_PURCHASE_PERCENT, MIN_PURCHASE_PERCENT"
    return f"{strategy_desc} | Configure: PURCHASE_STRATEGY_TYPE=follow_aws"


def _render_no_purchase_row(strategy_display: str, is_configured: bool, tooltip: str) -> str:
    """Render a table row for when no purchase is needed."""
    row_style = (
        'style="background: #fff9e6; font-weight: 600; cursor: help;"'
        if is_configured
        else 'style="cursor: help;"'
    )
    configured_badge = (
        ' <span style="background: #ff9900; color: white; padding: 2px 8px; border-radius: 3px; font-size: 0.75em; font-weight: 600;">CONFIGURED</span>'
        if is_configured
        else ""
    )
    return f"""
                    <tr {row_style} data-tooltip="{tooltip}">
                        <td><strong><span class="strategy-name">{strategy_display}</span></strong>{configured_badge}</td>
                        <td colspan="7" style="color: #6c757d; font-style: italic;">No purchase needed</td>
                    </tr>
                """


def _render_purchase_row(
    strategy_display: str,
    is_configured: bool,
    tooltip: str,
    purchase: dict[str, Any],
    target_coverage: float,
) -> str:
    """Render a table row for a purchase recommendation."""
    row_style = (
        'style="background: #fff9e6; font-weight: 600; cursor: help;"'
        if is_configured
        else 'style="cursor: help;"'
    )
    configured_badge = (
        ' <span style="background: #ff9900; color: white; padding: 2px 8px; border-radius: 3px; font-size: 0.75em; font-weight: 600;">CONFIGURED</span>'
        if is_configured
        else ""
    )

    hourly_commit = purchase["hourly_commitment"]
    purchase_percent = purchase.get("purchase_percent", 0.0)
    current_cov = purchase["current_coverage"]
    projected_cov = purchase["projected_coverage"]
    cov_increase = projected_cov - current_cov
    term = purchase.get("term", "N/A")
    payment_option = purchase.get("payment_option", "N/A")
    coverage_class = "green" if projected_cov >= target_coverage else "orange"
    discount_used = purchase.get("discount_used", 0.0)
    discount_tooltip = f"Computed with {discount_used:.1f}% discount rate"

    return f"""
                    <tr {row_style} data-tooltip="{tooltip}">
                        <td><strong><span class="strategy-name">{strategy_display}</span></strong>{configured_badge}</td>
                        <td class="metric" style="color: #2196f3; font-weight: bold;">${hourly_commit:.4f}/hr</td>
                        <td class="metric" title="{discount_tooltip}">{purchase_percent:.1f}%</td>
                        <td class="metric">{current_cov:.1f}%</td>
                        <td class="metric {coverage_class}" style="font-weight: bold;" title="{discount_tooltip}">{projected_cov:.1f}%</td>
                        <td class="metric" style="color: #28a745;" title="{discount_tooltip}">+{cov_increase:.1f}%</td>
                        <td>{term}</td>
                        <td>{payment_option}</td>
                    </tr>
                """


def _render_sp_type_scheduler_preview(
    sp_type: str, preview_data: dict[str, Any] | None, config: dict[str, Any]
) -> str:
    """Render scheduler preview comparison for a specific SP type."""
    strategy_names = {
        "fixed": "Fixed",
        "dichotomy": "Dichotomy",
        "follow_aws": "Follow AWS",
    }

    strategy_descriptions = {
        "fixed": "Purchases a fixed percentage of uncovered spend at a time.",
        "dichotomy": "Uses exponentially decreasing purchase sizes based on coverage gap.",
        "follow_aws": "Follows AWS Cost Explorer recommendations. Tends to aim for 100% coverage to min-hourly in a single purchase (no ramp-up, high risk of waste if workload decreases).",
    }

    if not preview_data:
        return ""

    if preview_data.get("error"):
        return f"""
            <div class="info-box" style="background: #fff3cd; border-left: 4px solid #ffc107; margin-top: 20px;">
                <strong>Scheduler Preview:</strong> Failed to calculate - {preview_data["error"]}
            </div>
        """

    strategies = preview_data.get("strategies", {})
    configured_strategy = preview_data.get("configured_strategy", "fixed")
    target_coverage = config.get("coverage_target_percent", 90.0)

    strategy_purchases = {}
    for strategy_name, strategy_data in strategies.items():
        for purchase in strategy_data.get("purchases", []):
            if purchase.get("sp_type") == sp_type:
                strategy_purchases[strategy_name] = purchase
                break

    if not strategy_purchases:
        return ""

    html = """
        <div style="margin-top: 30px; padding-top: 20px; border-top: 2px solid #e0e0e0;">
            <h3 style="color: #232f3e; margin-bottom: 15px;">🔮 Scheduler Preview - Strategy Comparison 🧞‍♂️</h3>
                <table style="width: 100%;">
                    <thead>
                        <tr>
                            <th>Strategy</th>
                            <th>Hourly Commitment</th>
                            <th>Purchase %</th>
                            <th>Current Coverage</th>
                            <th>Projected Coverage</th>
                            <th>Coverage Increase</th>
                            <th>Term</th>
                            <th>Payment</th>
                        </tr>
                    </thead>
                    <tbody>
    """

    for strategy_type in ["fixed", "dichotomy", "follow_aws"]:
        purchase = strategy_purchases.get(strategy_type)
        strategy_display = strategy_names.get(strategy_type, strategy_type)
        is_configured = strategy_type == configured_strategy
        strategy_desc = strategy_descriptions[strategy_type]

        tooltip = _build_strategy_tooltip(strategy_type, strategy_desc, config, is_configured)

        if not purchase:
            html += _render_no_purchase_row(strategy_display, is_configured, tooltip)
        else:
            html += _render_purchase_row(
                strategy_display, is_configured, tooltip, purchase, target_coverage
            )

    html += """
                </tbody>
            </table>
        </div>
    """

    return html


def _build_breakdown_table_html(
    breakdown_by_type: dict[str, Any],
    plans_count: int,
    average_utilization: float,
    total_commitment: float,
    overall_savings_percentage: float,
) -> str:
    """Build HTML for breakdown by type table."""
    if not breakdown_by_type:
        return ""

    html = """
            <table>
                <thead>
                    <tr>
                        <th>Plan Type</th>
                        <th>Active Plans</th>
                        <th>Utilization</th>
                        <th>Commitment/hr</th>
                        <th>Would Pay On-Demand/hr</th>
                        <th>Savings/hr</th>
                    </tr>
                </thead>
                <tbody>
"""

    for plan_type, type_data in breakdown_by_type.items():
        plans_count_type = type_data.get("plans_count", 0)
        total_commitment_type = type_data.get("total_commitment", 0.0)
        type_utilization = type_data.get("average_utilization", 0.0)
        type_savings_pct = type_data.get("savings_percentage", 0.0)

        # Calculate on-demand coverage capacity from commitment and discount rate
        # This shows what on-demand usage the commitment COVERS, not actual usage
        on_demand_coverage_capacity = sp_calculations.coverage_from_commitment(
            total_commitment_type, type_savings_pct
        )

        # Calculate potential savings: what you'd pay on-demand minus what you pay with SP
        potential_savings = on_demand_coverage_capacity - total_commitment_type

        plan_type_display = plan_type
        if "Compute" in plan_type:
            plan_type_display = "Compute Savings Plans"
        elif "SageMaker" in plan_type:
            plan_type_display = "SageMaker Savings Plans"
        elif "Database" in plan_type:
            plan_type_display = "Database Savings Plans"
        elif "EC2Instance" in plan_type:
            plan_type_display = "EC2 Instance Savings Plans"

        html += f"""
                    <tr>
                        <td><strong>{plan_type_display}</strong></td>
                        <td>{plans_count_type}</td>
                        <td class="metric">{type_utilization:.1f}%</td>
                        <td class="metric">${total_commitment_type:.2f}/hr</td>
                        <td class="metric">${on_demand_coverage_capacity:.2f}/hr</td>
                        <td class="metric" style="color: #28a745;">${potential_savings:.2f}/hr</td>
                    </tr>
"""

    if len(breakdown_by_type) > 1:
        # Calculate total on-demand coverage capacity
        total_coverage_capacity = sp_calculations.coverage_from_commitment(
            total_commitment, overall_savings_percentage
        )

        # Calculate total potential savings
        total_potential_savings = total_coverage_capacity - total_commitment

        html += f"""
                    <tr style="border-top: 2px solid #232f3e; font-weight: bold; background-color: #f8f9fa;">
                        <td><strong>Total</strong></td>
                        <td>{plans_count}</td>
                        <td class="metric">{average_utilization:.1f}%</td>
                        <td class="metric">${total_commitment:.2f}/hr</td>
                        <td class="metric">${total_coverage_capacity:.2f}/hr</td>
                        <td class="metric" style="color: #28a745;">${total_potential_savings:.2f}/hr</td>
                    </tr>
"""

    html += """
                </tbody>
            </table>
"""
    return html


def _build_raw_data_section_html(raw_data: dict[str, Any] | None, report_timestamp: str) -> str:
    """Build HTML for raw data section and footer."""
    html = """
        </div>
"""

    if raw_data:
        html += """
        <div class="section raw-data-section">
            <details>
                <summary>
                    <span>View Raw AWS Data</span>
                    <span style="font-size: 0.8em; color: #6c757d;">Click to expand • Toggle via <code>INCLUDE_DEBUG_DATA</code> env var</span>
                </summary>
                <div class="raw-data-controls">
                    <button class="raw-data-button" onclick="copyRawData()">Copy to Clipboard</button>
                    <button class="raw-data-button" onclick="expandAll()">Expand All</button>
                    <button class="raw-data-button" onclick="collapseAll()">Collapse All</button>
                </div>
                <div id="jsonViewer" class="json-viewer"></div>
            </details>
        </div>
"""

    html += f"""
        <div class="footer">
            <p><strong>Savings Plans Autopilot</strong> - Automated Coverage & Savings Report</p>
            <p>Generated: {report_timestamp}</p>
            <p style="margin-top: 15px; font-size: 0.9em;">
                Powered by <a href="https://github.com/etiennechabert/terraform-aws-sp-autopilot" target="_blank" style="color: #2196f3; text-decoration: none;">terraform-aws-sp-autopilot</a>
                <span style="opacity: 0.6;">| Open source on GitHub | Apache License 2.0</span>
            </p>
        </div>
    </div>
"""
    return html


def _parse_plan_dates(
    start_date: str, end_date: str, now: datetime, three_months_from_now: datetime
) -> tuple[str, str, str, bool, str]:
    """Parse plan dates and calculate expiration info."""
    start_date_display = start_date
    end_date_display = end_date
    days_remaining_display = "N/A"
    expiring_soon = False
    tooltip_text = ""

    try:
        if "T" in start_date:
            start_date_display = start_date.split("T", maxsplit=1)[0]

        if "T" in end_date:
            end_date_parsed = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
            end_date_display = end_date.split("T", maxsplit=1)[0]
        else:
            end_date_parsed = datetime.strptime(end_date, "%Y-%m-%d").replace(tzinfo=UTC)
            end_date_display = end_date

        days_remaining = (end_date_parsed - now).days

        if days_remaining < 0:
            days_remaining_display = "Expired"
        elif days_remaining == 0:
            days_remaining_display = "Today"
        elif days_remaining == 1:
            days_remaining_display = "1 day"
        else:
            days_remaining_display = f"{days_remaining} days"

        tooltip_text = f"Start: {start_date_display} | End: {end_date_display}"

        if end_date_parsed <= three_months_from_now:
            expiring_soon = True
    except Exception:
        # Catches ValueError, AttributeError, TypeError from date parsing
        pass

    return start_date_display, end_date_display, days_remaining_display, expiring_soon, tooltip_text


def _build_active_plans_table_html(plans: list[dict[str, Any]]) -> str:
    """Build HTML for active plans table."""
    if not plans:
        return """
            <div class="no-data">No active Savings Plans found</div>
"""

    sorted_plans = sorted(plans, key=lambda p: p.get("end_date", "9999-12-31"))
    now = datetime.now(UTC)
    three_months_from_now = now + timedelta(days=90)

    html = """
            <table>
                <thead>
                    <tr>
                        <th style="width: 30%;">Plan ID</th>
                        <th style="width: 12%;">Type</th>
                        <th style="width: 16%;">Hourly Commitment</th>
                        <th style="width: 10%;">Term</th>
                        <th style="width: 16%;">Payment Option</th>
                        <th style="width: 16%;">Days Remaining</th>
                    </tr>
                </thead>
                <tbody>
"""

    for plan in sorted_plans:
        plan_id = plan.get("plan_id", "Unknown")
        plan_type = plan.get("plan_type", "Unknown")
        hourly_commitment = plan.get("hourly_commitment", 0.0)
        term_years = plan.get("term_years", 0)
        payment_option = plan.get("payment_option", "Unknown")
        start_date = plan.get("start_date", "Unknown")
        end_date = plan.get("end_date", "Unknown")

        (
            _start_date_display,
            _end_date_display,
            days_remaining_display,
            expiring_soon,
            tooltip_text,
        ) = _parse_plan_dates(start_date, end_date, now, three_months_from_now)

        row_class = 'class="expiring-soon"' if expiring_soon else ""

        html += f"""
                    <tr {row_class}>
                        <td style="font-family: monospace; font-size: 0.8em; word-break: break-all;">{plan_id}</td>
                        <td>{plan_type}</td>
                        <td class="metric">${hourly_commitment:.2f}/hr</td>
                        <td>{term_years} year(s)</td>
                        <td>{payment_option}</td>
                        <td class="metric" title="{tooltip_text}" style="cursor: help;">{days_remaining_display}</td>
                    </tr>
"""

    html += """
                </tbody>
            </table>
"""
    return html


def generate_html_report(
    coverage_data: dict[str, Any],
    savings_data: dict[str, Any],
    config: dict[str, Any] | None = None,
    raw_data: dict[str, Any] | None = None,
    preview_data: dict[str, Any] | None = None,
) -> str:
    """
    Generate HTML report with coverage trends and savings metrics.

    Args:
        coverage_data: Coverage data from SpendingAnalyzer
        savings_data: Savings Plans summary from savings_plans_metrics
        config: Configuration parameters used for the report
        raw_data: Optional raw AWS API responses to include in the report

    Returns:
        str: HTML report content
    """
    logger.info("Generating HTML report")
    config = config or {}

    data = _prepare_html_report_data(coverage_data, savings_data, config)

    report_timestamp = data["report_timestamp"]
    data_period = data["data_period"]
    lookback_days = data["lookback_days"]
    overall_coverage = data["overall_coverage"]
    overall_coverage_class = data["overall_coverage_class"]
    plans_count = data["plans_count"]
    net_savings_hourly = data["net_savings_hourly"]
    savings_percentage = data["savings_percentage"]
    total_commitment = data["total_commitment"]
    average_utilization = data["average_utilization"]
    utilization_class = data["utilization_class"]
    breakdown_by_type = data["breakdown_by_type"]

    # Determine simulator base URL based on environment
    if is_local_mode():
        # Local development: use relative path from reports directory to docs
        simulator_base_url = "../../../../docs/index.html"
    else:
        # Production (Lambda): use GitHub Pages URL
        simulator_base_url = "https://etiennechabert.github.io/terraform-aws-sp-autopilot/"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Savings Plans Coverage & Savings Report</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-annotation@3.0.1/dist/chartjs-plugin-annotation.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/pako@2.1.0/dist/pako.min.js"></script>
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
            grid-template-columns: repeat(5, 1fr);
            gap: 12px;
            margin-bottom: 20px;
        }}
        @media (max-width: 900px) {{
            .summary {{
                grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            }}
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
        .summary-card.red {{
            background: linear-gradient(135deg, #eb3349 0%, #f45c43 100%);
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
            margin-bottom: 40px;
            padding-top: 30px;
            border-top: 3px solid #e8e8e8;
        }}
        .section:first-of-type {{
            border-top: none;
            padding-top: 0;
        }}
        h2 {{
            color: #232f3e;
            border-bottom: 3px solid #ff9900;
            padding-bottom: 10px;
            margin-top: 0;
            margin-bottom: 20px;
            font-size: 1.5em;
            font-weight: 600;
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
        .expiring-soon {{
            background-color: #fff3cd !important;
            border-left: 4px solid #ffc107;
        }}
        .expiring-soon:hover {{
            background-color: #ffe8a1 !important;
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
            color: #ffffff;
            background-color: #ff9900;
            border-bottom-color: #ff9900;
            font-weight: 600;
        }}
        .tab-content {{
            display: none;
        }}
        .tab-content.active {{
            display: block;
        }}
        .tab-metrics {{
            display: flex;
            gap: 15px;
            margin-bottom: 20px;
            padding: 15px;
            background-color: #f8f9fa;
            border-radius: 8px;
        }}
        .metric-card {{
            flex: 1;
            background: white;
            padding: 15px;
            border-radius: 6px;
            border-left: 4px solid #667eea;
        }}
        .metric-card.blue {{
            border-left-color: #4d9fff;
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
        .info-box {{
            margin-top: 10px;
            padding: 12px;
            background: #e7f3ff;
            border-left: 4px solid #2193b0;
            border-radius: 4px;
            font-size: 0.85em;
            color: #004085;
        }}
        .info-box strong {{
            color: #003366;
        }}
        .simulator-cta {{
            margin-top: 15px;
            text-align: center;
        }}
        .simulator-button {{
            display: inline-block;
            padding: 12px 24px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            text-decoration: none;
            border-radius: 6px;
            font-weight: 600;
            font-size: 1em;
            transition: transform 0.2s, box-shadow 0.2s;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }}
        .simulator-button:hover {{
            transform: translateY(-2px);
            box-shadow: 0 6px 12px rgba(0,0,0,0.15);
        }}
        .simulator-description {{
            margin-top: 10px;
            font-size: 0.85em;
            color: #856404;
        }}
        .color-toggle {{
            position: absolute;
            top: 10px;
            right: 10px;
            background: rgba(255, 255, 255, 0.9);
            border: 2px solid #ddd;
            border-radius: 6px;
            padding: 6px 12px;
            cursor: pointer;
            font-size: 0.85em;
            font-weight: 600;
            color: #333;
            transition: all 0.2s;
            z-index: 10;
        }}
        .color-toggle:hover {{
            background: white;
            border-color: #007bff;
            color: #007bff;
        }}
        .chart-container {{
            position: relative;
        }}
        .params-grid {{
            padding: 12px 15px;
            background-color: #f8f9fa;
            border-radius: 6px;
            font-size: 0.9em;
            display: flex;
            flex-wrap: wrap;
            gap: 8px 20px;
            align-items: center;
        }}
        .param-item {{
            display: inline-flex;
            gap: 6px;
            white-space: nowrap;
        }}
        .param-item strong {{
            color: #232f3e;
        }}
        .param-item span {{
            color: #6c757d;
        }}
        .raw-data-section {{
            margin-top: 30px;
            padding: 20px;
            background-color: #f8f9fa;
            border-radius: 8px;
            border: 1px solid #dee2e6;
        }}
        .raw-data-section summary {{
            cursor: pointer;
            font-size: 1.1em;
            font-weight: 600;
            color: #232f3e;
            padding: 10px;
            user-select: none;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .raw-data-section summary:hover {{
            background-color: #e9ecef;
            border-radius: 6px;
        }}
        .raw-data-controls {{
            margin: 15px 0;
            display: flex;
            gap: 10px;
        }}
        .raw-data-button {{
            padding: 8px 16px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 0.9em;
            font-weight: 500;
            transition: transform 0.2s, box-shadow 0.2s;
        }}
        .raw-data-button:hover {{
            transform: translateY(-2px);
            box-shadow: 0 4px 8px rgba(0,0,0,0.2);
        }}
        .json-viewer {{
            background-color: #1e1e1e;
            color: #d4d4d4;
            padding: 20px;
            border-radius: 6px;
            font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
            font-size: 13px;
            line-height: 1.5;
            overflow-x: auto;
            max-height: 600px;
            overflow-y: auto;
        }}
        .json-key {{
            color: #9cdcfe;
        }}
        .json-string {{
            color: #ce9178;
        }}
        .json-number {{
            color: #b5cea8;
        }}
        .json-boolean {{
            color: #569cd6;
        }}
        .json-null {{
            color: #569cd6;
        }}
        .json-item {{
            margin-left: 20px;
        }}
        .json-toggle {{
            cursor: pointer;
            user-select: none;
            color: #808080;
            margin-right: 6px;
            font-family: monospace;
            display: inline-block;
            width: 10px;
        }}
        .json-toggle:hover {{
            color: #ffffff;
        }}
        .json-children {{
            display: block;
        }}
        .json-children.collapsed {{
            display: none;
        }}

        /* Custom tooltips for strategy rows */
        .strategy-name {{
            position: relative;
            display: inline-block;
            text-decoration: underline dotted;
            text-decoration-color: rgba(0, 0, 0, 0.3);
            text-underline-offset: 3px;
        }}
        tr[data-tooltip] {{
            position: relative;
        }}
        tr[data-tooltip]:hover::after {{
            content: attr(data-tooltip);
            position: absolute;
            left: 10%;
            top: 100%;
            z-index: 1000;
            width: 400px;
            padding: 12px 16px;
            background: #232f3e;
            color: white;
            border-radius: 6px;
            font-size: 0.85em;
            line-height: 1.5;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
            margin-top: 8px;
            white-space: normal;
            pointer-events: none;
            animation: tooltipFadeIn 0.2s ease-in;
        }}
        @keyframes tooltipFadeIn {{
            from {{ opacity: 0; transform: translateY(-5px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Savings Plans Coverage & Savings Report</h1>
        <div class="subtitle">
            <div>Generated: {report_timestamp}</div>
            <div style="margin-top: 5px;"><strong>Data Period:</strong> {data_period}</div>
        </div>

        <div class="summary">
            <div class="summary-card green">
                <h3>Hourly Savings</h3>
                <div class="value">${net_savings_hourly:.2f}</div>
            </div>
            <div class="summary-card blue">
                <h3>Average Discount</h3>
                <div class="value">{savings_percentage:.1f}%</div>
            </div>
            <div class="summary-card {overall_coverage_class}">
                <h3>SP Coverage min-hourly</h3>
                <div class="value">{overall_coverage:.1f}%</div>
            </div>
            <div class="summary-card {utilization_class}">
                <h3>SP Utilization</h3>
                <div class="value">{average_utilization:.1f}%</div>
            </div>
            <div class="summary-card orange">
                <h3>Active Plans</h3>
                <div class="value">{plans_count}</div>
            </div>
        </div>

        <div class="section">
            <h2>Report Parameters</h2>
            <div class="params-grid">
                <div class="param-item">
                    <strong>Lookback Period:</strong> <span>{config["lookback_days"]} days</span>
                </div>
                <span style="color: #dee2e6;">•</span>
                <div class="param-item">
                    <strong>Granularity:</strong> <span>{config["granularity"]}</span>
                </div>
                <span style="color: #dee2e6;">•</span>
                <div class="param-item">
                    <strong>Enabled SP(s):</strong> <span>{", ".join([sp for sp, enabled in [("Compute", config["enable_compute_sp"]), ("Database", config["enable_database_sp"]), ("SageMaker", config["enable_sagemaker_sp"])] if enabled])}</span>
                </div>
                <span style="color: #dee2e6;">•</span>
                <div class="param-item">
                    <strong>Low Util. Threshold:</strong> <span>{config["low_utilization_threshold"]}%</span>
                </div>
            </div>
        </div>

        <div class="section">
            <h2>Usage Over Time and Scheduler Preview</h2>

            <div class="tabs">
                <button class="tab active" onclick="switchTab('global')">Global (All Types)</button>
                <button class="tab" onclick="switchTab('compute')">Compute</button>
                <button class="tab" onclick="switchTab('database')">Database</button>
                <button class="tab" onclick="switchTab('sagemaker')">SageMaker</button>
            </div>

            <div id="global-tab" class="tab-content active">
                <div class="chart-container">
                    <button class="color-toggle" onclick="toggleChartColors('globalChart')" title="Toggle color-blind friendly mode">
                        🎨 Toggle Colors
                    </button>
                    <canvas id="globalChart"></canvas>
                </div>
            </div>

            <div id="compute-tab" class="tab-content">
                <div id="compute-metrics"></div>
                <div class="chart-container">
                    <button class="color-toggle" onclick="toggleChartColors('computeChart')" title="Toggle color-blind friendly mode">
                        🎨 Toggle Colors
                    </button>
                    <canvas id="computeChart"></canvas>
                </div>
                {_render_sp_type_scheduler_preview("compute", preview_data, config or {})}
            </div>

            <div id="database-tab" class="tab-content">
                <div id="database-metrics"></div>
                <div class="chart-container">
                    <button class="color-toggle" onclick="toggleChartColors('databaseChart')" title="Toggle color-blind friendly mode">
                        🎨 Toggle Colors
                    </button>
                    <canvas id="databaseChart"></canvas>
                </div>
                {_render_sp_type_scheduler_preview("database", preview_data, config or {})}
            </div>

            <div id="sagemaker-tab" class="tab-content">
                <div id="sagemaker-metrics"></div>
                <div class="chart-container">
                    <button class="color-toggle" onclick="toggleChartColors('sagemakerChart')" title="Toggle color-blind friendly mode">
                        🎨 Toggle Colors
                    </button>
                    <canvas id="sagemakerChart"></canvas>
                </div>
                {_render_sp_type_scheduler_preview("sagemaker", preview_data, config or {})}
            </div>
        </div>

        <div class="section">
            <h2>Existing Savings Plans</h2>

            <h3 style="color: #232f3e; margin-top: 25px; margin-bottom: 15px; font-size: 1.2em;">Breakdown by Type</h3>
"""

    html += _build_breakdown_table_html(
        breakdown_by_type,
        plans_count,
        average_utilization,
        total_commitment,
        savings_percentage,
    )

    html += """
            <h3 style="color: #232f3e; margin-top: 35px; margin-bottom: 15px; font-size: 1.2em;">Active Plans Details</h3>
"""

    plans = savings_data.get("plans", [])
    html += _build_active_plans_table_html(plans)

    html += _build_raw_data_section_html(raw_data, report_timestamp)

    # Prepare chart data from coverage timeseries and calculate optimal coverage
    chart_data, optimal_coverage_results = _prepare_chart_data(coverage_data, savings_data, config)

    # Extract per-type metrics
    compute_summary = coverage_data.get("compute", {}).get("summary", {})
    database_summary = coverage_data.get("database", {}).get("summary", {})
    sagemaker_summary = coverage_data.get("sagemaker", {}).get("summary", {})

    # Extract savings breakdown by type
    breakdown_by_type = savings_data.get("actual_savings", {}).get("breakdown_by_type", {})

    compute_metrics = _get_type_metrics_for_report(compute_summary, "Compute", breakdown_by_type)
    database_metrics = _get_type_metrics_for_report(database_summary, "Database", breakdown_by_type)
    sagemaker_metrics = _get_type_metrics_for_report(
        sagemaker_summary, "SageMaker", breakdown_by_type
    )

    metrics_json = json.dumps(
        {"compute": compute_metrics, "database": database_metrics, "sagemaker": sagemaker_metrics}
    )

    optimal_coverage_json = (
        json.dumps(optimal_coverage_results) if optimal_coverage_results else "{}"
    )

    follow_aws_by_type = {}
    if preview_data:
        for purchase in (
            preview_data.get("strategies", {}).get("follow_aws", {}).get("purchases", [])
        ):
            sp = purchase["sp_type"]
            follow_aws_by_type[sp] = {
                "hourly_commitment": purchase["hourly_commitment"],
                "estimated_savings_percentage": purchase.get("estimated_savings_percentage", 0),
            }
    follow_aws_json = json.dumps(follow_aws_by_type)

    html += f"""
    <script>
        const allChartData = {chart_data};
        const metricsData = {metrics_json};
        const optimalCoverageFromPython = {optimal_coverage_json};
        const followAwsData = {follow_aws_json};
        const lookbackDays = {lookback_days};

        // Color palettes - Two combinations for different types of color vision deficiency
        const colorPalettes = {{
            palette1: {{
                // Blue & Orange - Best for red-green colorblind (Protanopia/Deuteranopia)
                covered: 'rgba(0, 114, 178, 0.7)',      // Deep Blue
                ondemand: 'rgba(230, 159, 0, 0.7)',     // Bright Orange
                coveredBorder: 'rgb(0, 114, 178)',
                ondemandBorder: 'rgb(230, 159, 0)'
            }},
            palette2: {{
                // Pink & Teal - Best for blue-yellow colorblind (Tritanopia)
                covered: 'rgba(204, 121, 167, 0.7)',    // Pink/Magenta
                ondemand: 'rgba(86, 180, 233, 0.7)',    // Teal/Cyan
                coveredBorder: 'rgb(204, 121, 167)',
                ondemandBorder: 'rgb(86, 180, 233)'
            }}
        }};

        // Track chart instances and current color mode
        const chartInstances = {{}};
        const chartColorModes = {{}};

        // Toggle chart colors function
        function toggleChartColors(chartId) {{
            const chart = chartInstances[chartId];
            if (!chart) return;

            // Toggle between palette1 and palette2
            chartColorModes[chartId] = chartColorModes[chartId] === 'palette2' ? 'palette1' : 'palette2';
            const palette = colorPalettes[chartColorModes[chartId]];

            // Update chart colors
            chart.data.datasets[0].backgroundColor = palette.covered;
            chart.data.datasets[0].borderColor = palette.coveredBorder;
            chart.data.datasets[1].backgroundColor = palette.ondemand;
            chart.data.datasets[1].borderColor = palette.ondemandBorder;

            chart.update();
        }}

        // Tab switching function (scoped to parent section)
        function switchTab(tabName) {{
            // Find the clicked button's parent section
            const clickedButton = event.target;
            const tabsContainer = clickedButton.closest('.tabs');
            const section = tabsContainer.closest('.section');

            // Hide all tab contents within this section only
            section.querySelectorAll('.tab-content').forEach(function(content) {{
                content.classList.remove('active');
            }});

            // Remove active class from all tabs within this section only
            section.querySelectorAll('.tab').forEach(function(tab) {{
                tab.classList.remove('active');
            }});

            // Show selected tab content
            document.getElementById(tabName + '-tab').classList.add('active');

            // Add active class to clicked tab
            clickedButton.classList.add('active');
        }}

        // Function to create chart for a specific type
        function createChart(canvasId, chartData, title, spType, showCoverageLine) {{
            const ctx = document.getElementById(canvasId);

            // Initialize color mode for this chart
            chartColorModes[canvasId] = 'palette1';
            const palette = colorPalettes['palette1'];

            // Build annotations array
            const annotations = {{}};

            // Only add current coverage line if requested and we have coverage
            if (showCoverageLine && spType) {{
                // Get metrics and stats for this SP type
                const metrics = metricsData[spType] || {{}};
                const stats = chartData.stats || {{}};
                const minHourly = stats.min || 0;
                const spCommitmentHourly = metrics.sp_commitment_hourly || 0;

                // Get pre-calculated on-demand equivalent (calculated in Python to eliminate duplication)
                const onDemandEquivalent = metrics.on_demand_coverage_hourly || 0;

                // Coverage as percentage of min-hourly
                const currentCoveragePct = minHourly > 0 ? (onDemandEquivalent / minHourly) * 100 : 0;

                // Only add current coverage line if we have coverage
                if (spCommitmentHourly > 0) {{
                    annotations.currentCoverage = {{
                        type: 'line',
                        yMin: onDemandEquivalent,
                        yMax: onDemandEquivalent,
                        borderColor: 'rgba(255, 255, 255, 0.9)',
                        borderWidth: 3,
                        borderDash: [8, 4],
                        label: {{
                            display: true,
                            content: 'Current: $' + spCommitmentHourly.toFixed(2) + '/hr (' + currentCoveragePct.toFixed(1) + '% coverage)',
                            position: 'center',
                            backgroundColor: 'rgba(0, 0, 0, 0.85)',
                            color: 'white',
                            font: {{
                                size: 12,
                                weight: 'bold'
                            }},
                            padding: 6
                        }}
                    }};
                }}

                // Add min-hourly line
                if (minHourly > 0) {{
                    annotations.minHourly = {{
                        type: 'line',
                        yMin: minHourly,
                        yMax: minHourly,
                        borderColor: 'rgba(70, 70, 70, 0.9)',
                        borderWidth: 3,
                        borderDash: [8, 4],
                        label: {{
                            display: true,
                            content: 'Min-hourly: $' + minHourly.toFixed(2) + '/hr',
                            position: 'end',
                            backgroundColor: 'rgba(0, 0, 0, 0.85)',
                            color: 'white',
                            font: {{
                                size: 12,
                                weight: 'bold'
                            }},
                            padding: 6
                        }}
                    }};
                }}
            }}

            chartInstances[canvasId] = new Chart(ctx, {{
                type: 'bar',
                data: {{
                    labels: chartData.labels,
                    datasets: [
                        {{
                            label: 'Covered by Savings Plans',
                            data: chartData.covered,
                            backgroundColor: palette.covered,
                            borderColor: palette.coveredBorder,
                            borderWidth: 1,
                            stack: 'stack0'
                        }},
                        {{
                            label: 'On-Demand Cost',
                            data: chartData.ondemand,
                            backgroundColor: palette.ondemand,
                            borderColor: palette.ondemandBorder,
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
                        }},
                        annotation: {{
                            annotations: annotations
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

            return chartInstances[canvasId];
        }}

        // Function to render metrics for a specific type
        function renderMetrics(containerId, metrics, typeName, stats, typeKey) {{
            const container = document.getElementById(containerId);

            // Determine utilization color class
            let utilizationClass = '';
            if (metrics.utilization >= 95) {{
                utilizationClass = 'green';
            }} else if (metrics.utilization >= 80) {{
                utilizationClass = 'orange';
            }}

            let optimizationHtml = '';
            // Show simulator if we have usage stats
            if (stats && Object.keys(stats).length > 0) {{
                // Calculate total hourly costs (covered + ondemand) for THIS TYPE ONLY
                const typeData = allChartData[typeKey];
                const hourlyCosts = typeData.covered.map((c, i) =>
                    (c + typeData.ondemand[i])
                );

                // Prepare usage data for simulator
                // Include optimal coverage calculated by Python for validation (type-specific)
                const typeOptimal = optimalCoverageFromPython[typeKey] || {{}};

                // Use type-specific savings percentage if available, otherwise use conservative 20% default
                const savingsPercentage = metrics.savings_percentage > 0 ? metrics.savings_percentage : 20;

                // Get pre-calculated on-demand equivalent (calculated in Python to eliminate duplication)
                const currentCoverageDollars = metrics.on_demand_coverage_hourly || 0;

                const usageData = {{
                    hourly_costs: hourlyCosts,
                    stats: stats,
                    current_coverage: currentCoverageDollars,  // On-demand equivalent coverage in $/hour
                    optimal_from_python: typeOptimal,
                    sp_type: typeName,  // Indicate which SP type this data is for
                    savings_percentage: savingsPercentage  // Type-specific discount or 20% default
                }};

                // Compress and encode for URL
                const compressed = pako.deflate(JSON.stringify(usageData));
                const base64 = btoa(String.fromCharCode.apply(null, compressed));

                // Base URL is determined server-side when generating the report
                const awsRec = followAwsData[typeKey];
                let simulatorUrl = `{simulator_base_url}?usage=${{encodeURIComponent(base64)}}`;
                if (awsRec) {{
                    simulatorUrl += `&aws=${{awsRec.hourly_commitment}},${{awsRec.estimated_savings_percentage}}`;
                }}

                optimizationHtml = `
                    <div class="simulator-cta">
                        <a href="${{simulatorUrl}}" target="_blank" class="simulator-button">
                            🎯 Optimize Your Coverage with Interactive Simulator
                        </a>
                        <p class="simulator-description">
                            Use our interactive tool to find the optimal coverage level and safely push beyond the min-hourly level based on your actual usage patterns.
                            Your hourly data has been pre-loaded for analysis.
                        </p>
                    </div>
                `;
            }}

            // Show 6 metric cards on a single line
            metricsHtml = `
                <div class="tab-metrics">
                    <div class="metric-card">
                        <h4>Avg Usage/hr</h4>
                        <div class="metric-value">${{metrics.total_spend_hourly > 0 ? '$' + metrics.total_spend_hourly.toFixed(2) : '$0'}}</div>
                    </div>
                    <div class="metric-card blue">
                        <h4>SP Commitment/hr</h4>
                        <div class="metric-value">${{metrics.sp_commitment_hourly > 0 ? '$' + metrics.sp_commitment_hourly.toFixed(2) : 'N/A'}}</div>
                    </div>
                    <div class="metric-card">
                        <h4>Avg On-Demand/hr</h4>
                        <div class="metric-value">${{metrics.uncovered_spend_hourly > 0 ? '$' + metrics.uncovered_spend_hourly.toFixed(2) : (metrics.current_coverage > 0 ? '$0' : 'N/A')}}</div>
                    </div>
                    <div class="metric-card">
                        <h4>SP Coverage min-hourly</h4>
                        <div class="metric-value">${{
                            (() => {{
                                if (metrics.current_coverage === 0) return 'N/A';
                                const minHourly = stats?.min || 0;
                                if (minHourly === 0) return 'N/A';
                                // Get pre-calculated on-demand equivalent (calculated in Python to eliminate duplication)
                                const onDemandEquiv = metrics.on_demand_coverage_hourly || 0;
                                const coverageMinHourlyPct = (onDemandEquiv / minHourly) * 100;
                                return coverageMinHourlyPct.toFixed(1) + '%';
                            }})()
                        }}</div>
                    </div>
                    <div class="metric-card ${{utilizationClass}}">
                        <h4>SP Utilization</h4>
                        <div class="metric-value">${{metrics.utilization > 0 ? metrics.utilization.toFixed(1) + '%' : 'N/A'}}</div>
                    </div>
                    <div class="metric-card blue">
                        <h4>SP Discount</h4>
                        <div class="metric-value">${{metrics.savings_percentage > 0 ? metrics.savings_percentage.toFixed(1) + '%' : 'N/A'}}</div>
                    </div>
                </div>
            `;

            // Add info box if there's no coverage
            if (metrics.current_coverage === 0 && metrics.total_spend_hourly > 0) {{
                metricsHtml += `
                    <div class="info-box">
                        <strong>💡 Opportunity:</strong> You have no Savings Plans coverage for this service type.
                        You're currently spending <strong>$${{metrics.total_spend_hourly.toFixed(2)}}/hour</strong> on-demand.
                        Consider purchasing Savings Plans to reduce costs - typical savings are around 30%.
                        <br><br>
                        <strong>Key insights:</strong>
                        <ul style="margin: 0.5em 0 0 1.5em; padding: 0;">
                            <li>Once you have your first Savings Plan in place, we'll know your precise discount rate for your usage for accurate optimization.</li>
                            <li>Any coverage up to your min-hourly usage (${{stats?.min ? stats.min.toFixed(2) : 'N/A'}}/hour) will be beneficial regardless of the exact discount - though you shouldn't aim for 100% coverage in a single purchase.</li>
                            <li>To optimize coverage above min-hourly, you first need to purchase a plan to reveal your precise discount rate and calculate the optimal commitment level.</li>
                        </ul>
                    </div>
                `;
            }}

            const html = metricsHtml + optimizationHtml;
            container.innerHTML = html;
        }}

        // Create all charts
        createChart('globalChart', allChartData.global, 'Hourly Usage: On-Demand vs Covered (All Types)', null, false);
        createChart('computeChart', allChartData.compute, 'Compute Savings Plans - Hourly Usage', 'compute', true);
        createChart('databaseChart', allChartData.database, 'Database Savings Plans - Hourly Usage', 'database', true);
        createChart('sagemakerChart', allChartData.sagemaker, 'SageMaker Savings Plans - Hourly Usage', 'sagemaker', true);

        // Render metrics for each type
        renderMetrics('compute-metrics', metricsData.compute, 'Compute', allChartData.compute.stats, 'compute');
        renderMetrics('database-metrics', metricsData.database, 'Database', allChartData.database.stats, 'database');
        renderMetrics('sagemaker-metrics', metricsData.sagemaker, 'SageMaker', allChartData.sagemaker.stats, 'sagemaker');
    </script>"""

    # Add JSON viewer JavaScript if raw data is provided
    if raw_data:
        # Convert to JSON and escape </script> to prevent breaking out of script tag
        raw_data_json = json.dumps(raw_data, indent=2, default=str)
        # Replace </script> with <\/script> to prevent early script termination
        raw_data_json = raw_data_json.replace("</script>", r"<\/script>")

        # Embed JSON in a script tag with type="application/json"
        html += f"""
    <script type="application/json" id="rawDataJsonSource">
{raw_data_json}
    </script>
    <script>

        function escapeHtml(text) {{
            return String(text).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
        }}

        function buildJsonTree(data, isRoot = false) {{
            if (data === null) {{
                return '<span class="json-null">null</span>';
            }}

            if (typeof data !== 'object') {{
                if (typeof data === 'string') {{
                    return '<span class="json-string">"' + escapeHtml(data) + '"</span>';
                }} else if (typeof data === 'number') {{
                    return '<span class="json-number">' + data + '</span>';
                }} else if (typeof data === 'boolean') {{
                    return '<span class="json-boolean">' + data + '</span>';
                }}
                return escapeHtml(String(data));
            }}

            const isArray = Array.isArray(data);
            const entries = isArray ? data : Object.entries(data);
            const isEmpty = isArray ? data.length === 0 : Object.keys(data).length === 0;

            if (isEmpty) {{
                return isArray ? '[]' : '{{}}';
            }}

            const id = 'tree-' + Math.random().toString(36).substr(2, 9);
            const openBracket = isArray ? '[' : '{{';
            const closeBracket = isArray ? ']' : '}}';

            let html = '<span class="json-toggle" onclick="toggleTree(\\'' + id + '\\')">▼</span>';
            html += openBracket;
            html += '<div class="json-children" id="' + id + '">';

            if (isArray) {{
                data.forEach((item, index) => {{
                    html += '<div class="json-item">';
                    html += buildJsonTree(item);
                    if (index < data.length - 1) html += ',';
                    html += '</div>';
                }});
            }} else {{
                const keys = Object.keys(data);
                keys.forEach((key, index) => {{
                    html += '<div class="json-item">';
                    html += '<span class="json-key">"' + escapeHtml(key) + '"</span>: ';
                    html += buildJsonTree(data[key]);
                    if (index < keys.length - 1) html += ',';
                    html += '</div>';
                }});
            }}

            html += '</div>';
            html += closeBracket;

            return html;
        }}

        function toggleTree(id) {{
            const element = document.getElementById(id);
            const toggle = element.previousElementSibling;
            if (element.classList.contains('collapsed')) {{
                element.classList.remove('collapsed');
                toggle.textContent = '▼';
            }} else {{
                element.classList.add('collapsed');
                toggle.textContent = '▶';
            }}
        }}

        function expandAll() {{
            document.querySelectorAll('.json-children').forEach(el => {{
                el.classList.remove('collapsed');
            }});
            document.querySelectorAll('.json-toggle').forEach(el => {{
                el.textContent = '▼';
            }});
        }}

        function collapseAll() {{
            // Get all json-children elements
            const allChildren = document.querySelectorAll('.json-children');

            // Skip the first one (root level), collapse the rest
            allChildren.forEach((el, index) => {{
                if (index > 0) {{
                    el.classList.add('collapsed');
                    // Update the toggle arrow for this element
                    const toggle = el.previousElementSibling;
                    if (toggle && toggle.classList.contains('json-toggle')) {{
                        toggle.textContent = '▶';
                    }}
                }}
            }});
        }}

        // Get raw data from the JSON script tag
        function getRawDataJson() {{
            const dataScript = document.getElementById('rawDataJsonSource');
            return dataScript ? dataScript.textContent : null;
        }}

        function copyRawData() {{
            const rawDataJson = getRawDataJson();
            if (rawDataJson) {{
                navigator.clipboard.writeText(rawDataJson).then(() => {{
                    alert('Raw data copied to clipboard!');
                }}).catch(err => {{
                    console.error('Failed to copy:', err);
                    alert('Failed to copy to clipboard');
                }});
            }}
        }}

        // Initialize JSON viewer on page load
        function initJsonViewer() {{
            const viewer = document.getElementById('jsonViewer');
            const rawDataJson = getRawDataJson();

            if (viewer && rawDataJson) {{
                try {{
                    const data = JSON.parse(rawDataJson);
                    viewer.innerHTML = buildJsonTree(data, true);
                }} catch (e) {{
                    console.error('JSON parse error:', e);
                    viewer.innerHTML = '<div style="color: #ff6b6b; padding: 10px;">Error rendering JSON: ' + e.message + '</div><pre style="color: #d4d4d4;">' + rawDataJson.substring(0, 1000) + '...</pre>';
                }}
            }} else {{
                console.log('Viewer element or rawDataJson not found', {{ viewer: !!viewer, rawDataJson: !!rawDataJson }});
                if (viewer && !rawDataJson) {{
                    viewer.innerHTML = '<div style="color: #ff6b6b; padding: 10px;">No raw data available</div>';
                }}
            }}
        }}

        // Run immediately if DOM is already loaded, otherwise wait
        if (document.readyState === 'loading') {{
            document.addEventListener('DOMContentLoaded', initJsonViewer);
        }} else {{
            initJsonViewer();
        }}
    </script>"""

    html += """
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
                "avg_coverage_percentage": round(compute_summary.get("avg_coverage_total", 0.0), 2),
                "avg_hourly_spend": round(compute_summary.get("avg_hourly_total", 0.0), 4),
            },
            "database": {
                "avg_coverage_percentage": round(
                    database_summary.get("avg_coverage_total", 0.0), 2
                ),
                "avg_hourly_spend": round(database_summary.get("avg_hourly_total", 0.0), 4),
            },
            "sagemaker": {
                "avg_coverage_percentage": round(
                    sagemaker_summary.get("avg_coverage_total", 0.0), 2
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

    json_content = json.dumps(report, indent=2, default=str)
    logger.info(f"JSON report generated ({len(json_content)} bytes)")
    return json_content


def generate_csv_report(
    coverage_data: dict[str, Any],
    savings_data: dict[str, Any],
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
        f"average_utilization_percentage,{savings_data.get('average_utilization', 0.0):.2f}",
        f"compute_avg_coverage,{compute_summary.get('avg_coverage_total', 0.0):.2f}",
        f"database_avg_coverage,{database_summary.get('avg_coverage_total', 0.0):.2f}",
        f"sagemaker_avg_coverage,{sagemaker_summary.get('avg_coverage_total', 0.0):.2f}",
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
            f"{plan.get('hourly_commitment', 0.0):.4f},"
            f"{plan.get('start_date', '')},"
            f"{plan.get('end_date', '')}"
        )

    csv_content = "\n".join(csv_parts)
    logger.info(f"CSV report generated ({len(csv_content)} bytes)")
    return csv_content

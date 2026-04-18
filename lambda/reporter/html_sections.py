"""Self-contained HTML fragments injected into the main template."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from shared import sp_calculations


def build_strategy_tooltip(strategy_key: str, config: dict[str, Any]) -> str:
    """Tooltip shown on each strategy row in the scheduler-preview table."""
    parts = strategy_key.split("+")
    target = parts[0] if parts else ""
    split = parts[1] if len(parts) > 1 else ""

    if target == "dynamic":
        target_line = f"Target: dynamic (risk_level: {config['dynamic_risk_level']})"
    else:
        target_line = "Target: aws"

    if split == "fixed_step":
        split_line = f"Split: fixed_step (step_percent: {config['fixed_step_percent']:.0f}%)"
    elif split == "gap_split":
        divider = config["gap_split_divider"]
        min_pct = config.get("min_purchase_percent")
        max_pct = config.get("max_purchase_percent")
        min_pct_str = f"{min_pct:.0f}%" if min_pct is not None else "auto"
        parts_str = f"divider: {divider:.0f}, min_purchase_percent: {min_pct_str}"
        if max_pct is not None:
            parts_str += f", max_purchase_percent: {max_pct:.0f}%"
        split_line = f"Split: gap_split ({parts_str})"
    else:
        split_line = "Split: one_shot"

    return f"{target_line}\n{split_line}"


def _render_no_purchase_row(strategy_display: str, is_configured: bool, tooltip: str) -> str:
    row_style = (
        'style="background: #fff9e6; font-weight: 600; cursor: help;"'
        if is_configured
        else 'style="cursor: help;"'
    )
    configured_badge = (
        ' <span style="background: rgb(0, 158, 115); color: white; padding: 2px 8px; border-radius: 3px; font-size: 0.75em; font-weight: 600;">CONFIGURED</span>'
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
    strategy_type: str,
    strategy_display: str,
    is_configured: bool,
    tooltip: str,
    purchase: dict[str, Any],
) -> str:
    row_style = (
        'style="background: #fff9e6; font-weight: 600; cursor: help;"'
        if is_configured
        else 'style="cursor: help;"'
    )
    configured_badge = (
        ' <span style="background: rgb(0, 158, 115); color: white; padding: 2px 8px; border-radius: 3px; font-size: 0.75em; font-weight: 600;">CONFIGURED</span>'
        if is_configured
        else ""
    )

    hourly_commit = purchase["hourly_commitment"]
    current_cov = purchase["current_coverage"]
    projected_cov = purchase["projected_coverage"]
    cov_increase = projected_cov - current_cov
    term = purchase.get("term", "N/A")
    payment_option = purchase.get("payment_option", "N/A")
    discount_used = purchase.get("discount_used", 0.0)
    discount_tooltip = f"Computed with {discount_used:.1f}% discount rate"

    is_aws = purchase.get("is_aws_target", strategy_type.startswith("aws"))
    actual_target = purchase.get("target_coverage")
    if is_aws or actual_target is None:
        target_cell = '<td class="metric" style="color: #6c757d;">N/A</td>'
        coverage_class = ""
    else:
        coverage_class = "green" if projected_cov >= actual_target else "orange"
        target_cell = f'<td class="metric">{actual_target:.1f}%</td>'

    return f"""
                    <tr {row_style} data-tooltip="{tooltip}">
                        <td><strong><span class="strategy-name">{strategy_display}</span></strong>{configured_badge}</td>
                        <td class="metric" style="color: #2196f3; font-weight: bold;">${hourly_commit:.5f}/hr</td>
                        <td class="metric">{current_cov:.1f}%</td>
                        <td class="metric" style="color: #28a745;" title="{discount_tooltip}">+{cov_increase:.1f}%</td>
                        <td class="metric {coverage_class}" style="font-weight: bold;" title="{discount_tooltip}">{projected_cov:.1f}%</td>
                        {target_cell}
                        <td class="metric">{discount_used:.1f}%</td>
                        <td>{term}, {payment_option}</td>
                    </tr>
                """


def render_sp_type_scheduler_preview(
    sp_type: str, preview_data: dict[str, Any] | None, config: dict[str, Any]
) -> str:
    """Per-type table comparing what each target+split strategy would buy."""
    if not preview_data:
        return ""

    if preview_data.get("error"):
        return f"""
            <div class="info-box" style="background: #fff3cd; border-left: 4px solid #ffc107; margin-top: 20px;">
                <strong>Scheduler Preview:</strong> Failed to calculate - {preview_data["error"]}
            </div>
        """

    strategies = preview_data.get("strategies", {})
    configured_strategy = preview_data.get("configured_strategy", "fixed+fixed_step")

    strategy_purchases = {}
    for strategy_key, strategy_data in strategies.items():
        for purchase in strategy_data.get("purchases", []):
            if purchase.get("sp_type") == sp_type:
                strategy_purchases[strategy_key] = purchase
                break

    if not strategy_purchases:
        return ""

    strategy_order = preview_data.get("strategy_order", list(strategies.keys()))

    html = """
        <div style="margin-top: 30px; padding-top: 20px; border-top: 2px solid #e0e0e0;">
            <h3 style="color: #232f3e; margin-bottom: 15px;">🔮 Scheduler Preview - Strategy Comparison 🧞‍♂️</h3>
                <table style="width: 100%;">
                    <thead>
                        <tr>
                            <th>Strategy</th>
                            <th>Added Commitment</th>
                            <th>Current Coverage</th>
                            <th>Added Coverage</th>
                            <th>Projected Coverage</th>
                            <th>Target Coverage</th>
                            <th>Discount Rate</th>
                            <th>Term &amp; Payment</th>
                        </tr>
                    </thead>
                    <tbody>
    """

    for strategy_key in strategy_order:
        strategy_data = strategies.get(strategy_key)
        if not strategy_data:
            continue
        purchase = strategy_purchases.get(strategy_key)
        strategy_display = strategy_data.get("label", strategy_key)
        is_configured = strategy_key == configured_strategy
        tooltip = build_strategy_tooltip(strategy_key, config)

        if not purchase:
            html += _render_no_purchase_row(strategy_display, is_configured, tooltip)
        else:
            html += _render_purchase_row(
                strategy_key, strategy_display, is_configured, tooltip, purchase
            )

    html += """
                </tbody>
            </table>
        </div>
    """

    return html


def build_breakdown_table_html(
    breakdown_by_type: dict[str, Any],
    plans_count: int,
    average_utilization: float,
    total_commitment: float,
    overall_savings_percentage: float,
) -> str:
    """Per-SP-type summary table (plans, utilization, commitment, savings)."""
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
                        <th>On-Demand Covered/hr</th>
                        <th>Savings/hr</th>
                        <th>Savings %</th>
                    </tr>
                </thead>
                <tbody>
"""

    na_tooltip = "This SP type is not enabled in your configuration, so metrics are not collected"

    for plan_type, type_data in breakdown_by_type.items():
        plans_count_type = type_data.get("plans_count", 0)
        total_commitment_type = type_data.get("total_commitment", 0.0)
        has_metrics = "average_utilization" in type_data

        plan_type_display = plan_type
        if "Compute" in plan_type:
            plan_type_display = "Compute Savings Plans"
        elif "SageMaker" in plan_type:
            plan_type_display = "SageMaker Savings Plans"
        elif "Database" in plan_type:
            plan_type_display = "Database Savings Plans"
        elif "EC2Instance" in plan_type:
            plan_type_display = "EC2 Instance Savings Plans"

        if has_metrics:
            type_utilization = type_data["average_utilization"]
            type_savings_pct = type_data.get("savings_percentage", 0.0)
            on_demand_coverage_capacity = sp_calculations.coverage_from_commitment(
                total_commitment_type, type_savings_pct
            )
            potential_savings = on_demand_coverage_capacity - total_commitment_type

            html += f"""
                    <tr>
                        <td><strong>{plan_type_display}</strong></td>
                        <td>{plans_count_type}</td>
                        <td class="metric">{type_utilization:.1f}%</td>
                        <td class="metric">${total_commitment_type:.2f}/hr</td>
                        <td class="metric">${on_demand_coverage_capacity:.2f}/hr</td>
                        <td class="metric" style="color: #28a745;">${potential_savings:.2f}/hr</td>
                        <td class="metric" style="color: #28a745;">{type_savings_pct:.1f}%</td>
                    </tr>
"""
        else:
            na_html = f'<span title="{na_tooltip}" style="cursor: help; color: #6c757d;">N/A</span>'
            html += f"""
                    <tr>
                        <td><strong>{plan_type_display}</strong></td>
                        <td>{plans_count_type}</td>
                        <td class="metric">{na_html}</td>
                        <td class="metric">${total_commitment_type:.2f}/hr</td>
                        <td class="metric">{na_html}</td>
                        <td class="metric">{na_html}</td>
                        <td class="metric">{na_html}</td>
                    </tr>
"""

    if len(breakdown_by_type) > 1:
        total_coverage_capacity = sp_calculations.coverage_from_commitment(
            total_commitment, overall_savings_percentage
        )
        total_potential_savings = total_coverage_capacity - total_commitment
        html += f"""
                    <tr style="border-top: 2px solid #232f3e; font-weight: bold; background-color: #f8f9fa;">
                        <td><strong>Total</strong></td>
                        <td>{plans_count}</td>
                        <td class="metric">{average_utilization:.1f}%</td>
                        <td class="metric">${total_commitment:.2f}/hr</td>
                        <td class="metric">${total_coverage_capacity:.2f}/hr</td>
                        <td class="metric" style="color: #28a745;">${total_potential_savings:.2f}/hr</td>
                        <td class="metric" style="color: #28a745;">{overall_savings_percentage:.1f}%</td>
                    </tr>
"""

    html += """
                </tbody>
            </table>
"""
    return html


def build_raw_data_section_html(
    raw_data: dict[str, Any] | None, report_timestamp: str, monthly_savings: float = 0.0
) -> str:
    """Collapsible raw AWS data panel + footer with optional coffee nudge."""
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

    if monthly_savings > 0:
        coffee_html = f"""
            <div style="margin: 20px auto 0; padding: 10px 18px; background: linear-gradient(135deg, #fff8e1 0%, #fff3cd 100%); border-radius: 10px; max-width: 520px; border: 1px solid #ffe082; font-size: 0.85em;">
                <p style="margin: 0 0 6px; color: #5d4037;">
                    Savings Plans Autopilot helped you save <strong style="color: #2e7d32;">${monthly_savings:,.2f}</strong> this month.
                </p>
                <p style="margin: 0 0 6px; color: #6d4c41;">
                    The human behind this tool is fueled by overpriced Berlin coffees — maybe you can help?
                </p>
                <a href="https://buymeacoffee.com/etiennechak" target="_blank"
                   style="display: inline-block; margin-top: 6px; padding: 6px 16px; background-color: #ffdd00; color: #000; font-weight: bold; border-radius: 6px; text-decoration: none; font-size: 0.9em; transition: transform 0.2s;"
                   onmouseover="this.style.transform='scale(1.05)'" onmouseout="this.style.transform='scale(1)'">
                    ☕ Buy me a coffee
                </a>
            </div>
"""
    else:
        coffee_html = """
            <div style="margin: 20px auto 0; padding: 10px 18px; background: linear-gradient(135deg, #fff8e1 0%, #fff3cd 100%); border-radius: 10px; max-width: 420px; border: 1px solid #ffe082; font-size: 0.85em;">
                <p style="margin: 0 0 4px; color: #6d4c41;">
                    No savings yet — but once Savings Plans Autopilot kicks in, it'll earn its Berlin flat white.
                </p>
                <a href="https://buymeacoffee.com/etiennechak" target="_blank"
                   style="display: inline-block; margin-top: 6px; padding: 6px 16px; background-color: #ffdd00; color: #000; font-weight: bold; border-radius: 6px; text-decoration: none; font-size: 0.9em; transition: transform 0.2s;"
                   onmouseover="this.style.transform='scale(1.05)'" onmouseout="this.style.transform='scale(1)'">
                    ☕ Buy me a coffee anyway
                </a>
            </div>
"""

    html += f"""
        <div class="footer">
{coffee_html}
            <p style="margin-top: 20px;">
                Generated: {report_timestamp} | <a href="https://github.com/etiennechabert/terraform-aws-sp-autopilot" target="_blank" style="color: #2196f3; text-decoration: none;">terraform-aws-sp-autopilot</a> <span style="opacity: 0.6;">| Open source | Apache 2.0</span>
            </p>
        </div>
    </div>
"""
    return html


def parse_plan_dates(
    start_date: str, end_date: str, now: datetime, three_months_from_now: datetime
) -> tuple[str, str, str, bool, str]:
    """Return (start_display, end_display, days_remaining_display, expiring_soon, tooltip)."""
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
    except (ValueError, TypeError):
        pass

    return start_date_display, end_date_display, days_remaining_display, expiring_soon, tooltip_text


def build_active_plans_table_html(plans: list[dict[str, Any]]) -> str:
    """Table of active Savings Plans sorted by end date, with expandable detail rows."""
    if not plans:
        return """
            <div class="no-data">No active Savings Plans found</div>
"""

    sorted_plans = sorted(plans, key=lambda p: p.get("end_date", "9999-12-31"))
    now = datetime.now(UTC)
    three_months_from_now = now + timedelta(days=90)

    html = """
            <table class="active-plans-table">
                <thead>
                    <tr>
                        <th style="width: 3%;"></th>
                        <th style="width: 28%;">Plan ID</th>
                        <th style="width: 12%;">Type</th>
                        <th style="width: 16%;">Hourly Commitment</th>
                        <th style="width: 9%;">Term</th>
                        <th style="width: 15%;">Payment Option</th>
                        <th style="width: 17%; text-align: right;">Days Remaining</th>
                    </tr>
                </thead>
                <tbody>
"""

    for idx, plan in enumerate(sorted_plans):
        plan_id = plan.get("plan_id", "Unknown")
        plan_type = plan.get("plan_type", "Unknown")
        hourly_commitment = plan.get("hourly_commitment", 0.0)
        term_years = plan.get("term_years", 0)
        payment_option = plan.get("payment_option", "Unknown")
        start_date = plan.get("start_date", "Unknown")
        end_date = plan.get("end_date", "Unknown")

        (
            _start_display,
            _end_display,
            days_remaining_display,
            expiring_soon,
            tooltip_text,
        ) = parse_plan_dates(start_date, end_date, now, three_months_from_now)

        summary_classes = ["plan-summary-row"]
        if expiring_soon:
            summary_classes.append("expiring-soon")
        summary_class_attr = " ".join(summary_classes)
        details_id = f"plan-details-{idx}"

        html += f"""
                    <tr class="{summary_class_attr}" onclick="togglePlanDetails('{details_id}', this)">
                        <td class="plan-toggle-cell"><span class="plan-toggle-icon">&#9656;</span></td>
                        <td style="font-family: monospace; font-size: 0.8em; word-break: break-all;">{plan_id}</td>
                        <td>{plan_type}</td>
                        <td class="metric">${hourly_commitment:.2f}/hr</td>
                        <td>{term_years} year(s)</td>
                        <td>{payment_option}</td>
                        <td class="metric" title="{tooltip_text}" style="cursor: help; text-align: right;">{days_remaining_display}</td>
                    </tr>
                    <tr id="{details_id}" class="plan-details-row" hidden>
                        <td colspan="7">{_render_plan_details(plan)}</td>
                    </tr>
"""

    html += """
                </tbody>
            </table>
"""
    return html


def build_plans_breakdown_section_html(
    breakdown_by_type: dict[str, Any],
    plans: list[dict[str, Any]],
    plans_count: int,
    average_utilization: float,
    total_commitment: float,
    overall_savings_percentage: float,
) -> str:
    """Nested breakdown table: plan type -> plans of that type -> full plan details.

    Two levels of click-to-expand: the type row opens a nested sub-table of
    that type's active plans; each plan row then opens its full details panel.
    """
    if not breakdown_by_type:
        return ""

    now = datetime.now(UTC)
    three_months_from_now = now + timedelta(days=90)

    plans_by_type: dict[str, list[dict[str, Any]]] = {}
    for plan in plans:
        plans_by_type.setdefault(plan.get("plan_type", "Unknown"), []).append(plan)

    na_tooltip = "This SP type is not enabled in your configuration, so metrics are not collected"

    html = """
            <table class="breakdown-table">
                <thead>
                    <tr>
                        <th style="width: 3%;"></th>
                        <th>Plan Type</th>
                        <th>Active Plans</th>
                        <th>Utilization</th>
                        <th>Commitment/hr</th>
                        <th>On-Demand Covered/hr</th>
                        <th>Savings/hr</th>
                        <th>Savings %</th>
                        <th style="text-align: right;">Next Expiry</th>
                    </tr>
                </thead>
                <tbody>
"""

    soonest_overall_days: int | None = None
    soonest_overall_date: str = ""

    for type_idx, (plan_type, type_data) in enumerate(breakdown_by_type.items()):
        plans_count_type = type_data.get("plans_count", 0)
        total_commitment_type = type_data.get("total_commitment", 0.0)
        has_metrics = "average_utilization" in type_data

        if "Compute" in plan_type:
            plan_type_display = "Compute Savings Plans"
        elif "SageMaker" in plan_type:
            plan_type_display = "SageMaker Savings Plans"
        elif "Database" in plan_type:
            plan_type_display = "Database Savings Plans"
        elif "EC2Instance" in plan_type:
            plan_type_display = "EC2 Instance Savings Plans"
        else:
            plan_type_display = plan_type

        type_plans = plans_by_type.get(plan_type, [])
        next_expiry_cell = _render_next_expiry_cell(type_plans, now, three_months_from_now)
        next_expiry_days = _next_expiry_days(type_plans, now)
        if next_expiry_days is not None and (
            soonest_overall_days is None or next_expiry_days < soonest_overall_days
        ):
            soonest_overall_days = next_expiry_days
            soonest_overall_date = _next_expiry_end(type_plans)

        type_details_id = f"type-plans-{type_idx}"

        if has_metrics:
            type_utilization = type_data["average_utilization"]
            type_savings_pct = type_data.get("savings_percentage", 0.0)
            on_demand_coverage_capacity = sp_calculations.coverage_from_commitment(
                total_commitment_type, type_savings_pct
            )
            potential_savings = on_demand_coverage_capacity - total_commitment_type

            html += f"""
                    <tr class="type-summary-row" onclick="togglePlanDetails('{type_details_id}', this)">
                        <td class="plan-toggle-cell"><span class="plan-toggle-icon">&#9656;</span></td>
                        <td><strong>{plan_type_display}</strong></td>
                        <td>{plans_count_type}</td>
                        <td class="metric">{type_utilization:.1f}%</td>
                        <td class="metric">${total_commitment_type:.2f}/hr</td>
                        <td class="metric">${on_demand_coverage_capacity:.2f}/hr</td>
                        <td class="metric" style="color: #28a745;">${potential_savings:.2f}/hr</td>
                        <td class="metric" style="color: #28a745;">{type_savings_pct:.1f}%</td>
                        <td class="metric" style="text-align: right;">{next_expiry_cell}</td>
                    </tr>
"""
        else:
            na_html = f'<span title="{na_tooltip}" style="cursor: help; color: #6c757d;">N/A</span>'
            html += f"""
                    <tr class="type-summary-row" onclick="togglePlanDetails('{type_details_id}', this)">
                        <td class="plan-toggle-cell"><span class="plan-toggle-icon">&#9656;</span></td>
                        <td><strong>{plan_type_display}</strong></td>
                        <td>{plans_count_type}</td>
                        <td class="metric">{na_html}</td>
                        <td class="metric">${total_commitment_type:.2f}/hr</td>
                        <td class="metric">{na_html}</td>
                        <td class="metric">{na_html}</td>
                        <td class="metric">{na_html}</td>
                        <td class="metric" style="text-align: right;">{next_expiry_cell}</td>
                    </tr>
"""
        # Nested sub-table with plans of this type, hidden by default.
        nested = _build_type_plans_subtable(type_idx, type_plans, now, three_months_from_now)
        html += f"""
                    <tr id="{type_details_id}" class="plan-details-row" hidden>
                        <td colspan="9" style="padding: 0;">{nested}</td>
                    </tr>
"""

    if len(breakdown_by_type) > 1:
        total_coverage_capacity = sp_calculations.coverage_from_commitment(
            total_commitment, overall_savings_percentage
        )
        total_potential_savings = total_coverage_capacity - total_commitment
        if soonest_overall_days is not None:
            total_expiry_cell = _format_days_cell(soonest_overall_days, soonest_overall_date)
        else:
            total_expiry_cell = '<span style="color: #6c757d;">N/A</span>'
        html += f"""
                    <tr style="border-top: 2px solid #232f3e; font-weight: bold; background-color: #f8f9fa;">
                        <td></td>
                        <td><strong>Total</strong></td>
                        <td>{plans_count}</td>
                        <td class="metric">{average_utilization:.1f}%</td>
                        <td class="metric">${total_commitment:.2f}/hr</td>
                        <td class="metric">${total_coverage_capacity:.2f}/hr</td>
                        <td class="metric" style="color: #28a745;">${total_potential_savings:.2f}/hr</td>
                        <td class="metric" style="color: #28a745;">{overall_savings_percentage:.1f}%</td>
                        <td class="metric" style="text-align: right;">{total_expiry_cell}</td>
                    </tr>
"""

    html += """
                </tbody>
            </table>
"""
    return html


def _build_type_plans_subtable(
    type_idx: int,
    type_plans: list[dict[str, Any]],
    now: datetime,
    three_months_from_now: datetime,
) -> str:
    """Collapsible card list of individual plans for one SP type."""
    if not type_plans:
        return (
            '<div class="plans-nested-wrap" style="color: #6c757d; font-style: italic;">'
            "No active plans for this type.</div>"
        )

    sorted_plans = sorted(type_plans, key=lambda p: p.get("end_date", "9999-12-31"))

    items = ""
    for plan_idx, plan in enumerate(sorted_plans):
        plan_id = plan.get("plan_id", "") or ""
        hourly_commitment = plan.get("hourly_commitment", 0.0)
        term_years = plan.get("term_years", 0)
        payment_option = plan.get("payment_option", "Unknown")
        start_date = plan.get("start_date", "") or ""
        end_date = plan.get("end_date", "") or ""

        (
            _start_display,
            _end_display,
            days_remaining_display,
            expiring_soon,
            tooltip_text,
        ) = parse_plan_dates(start_date, end_date, now, three_months_from_now)

        summary_classes = ["plan-card-row"]
        if expiring_soon:
            summary_classes.append("expiring-soon")
        summary_class_attr = " ".join(summary_classes)
        details_id = f"plan-details-{type_idx}-{plan_idx}"

        expiration_phrase = _expiration_phrase(days_remaining_display)
        expiration_class = "plan-card-expiration"
        if days_remaining_display == "Expired":
            expiration_class += " expired"
        elif expiring_soon:
            expiration_class += " expiring"

        meta_parts = [
            f"<span>{term_years}&nbsp;year</span>",
            f"<span>{payment_option}</span>",
            (f'<span class="{expiration_class}" title="{tooltip_text}">{expiration_phrase}</span>'),
        ]
        meta_html = '<span class="plan-card-sep">·</span>'.join(meta_parts)

        short_id_html = ""
        if plan_id and plan_id != "Unknown" and len(plan_id) > 6:
            short_id_html = (
                f'<span class="plan-card-id-short" title="{plan_id}">…{plan_id[-5:]}</span>'
            )

        metrics_html = _render_plan_card_metrics(plan)

        items += f"""
                    <div class="plan-card">
                        <div class="{summary_class_attr}" onclick="togglePlanDetails('{details_id}', this)">
                            <span class="plan-toggle-icon">&#9656;</span>
                            <span class="plan-card-commit">${hourly_commitment:.2f}/hr</span>
                            <span class="plan-card-meta">{meta_html}</span>
                            {metrics_html}
                            {short_id_html}
                        </div>
                        <div id="{details_id}" class="plan-card-details" hidden>{_render_plan_details(plan)}</div>
                    </div>
"""

    return f"""
                <div class="plans-nested-wrap">
                    {items}
                </div>
"""


def _next_expiry_days(type_plans: list[dict[str, Any]], now: datetime) -> int | None:
    """Days until the soonest-ending plan in the given list, or None if no parseable dates."""
    soonest: int | None = None
    for plan in type_plans:
        end_date = plan.get("end_date", "") or ""
        try:
            if "T" in end_date:
                end_parsed = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
            else:
                end_parsed = datetime.strptime(end_date, "%Y-%m-%d").replace(tzinfo=UTC)
        except (ValueError, TypeError):
            continue
        days = (end_parsed - now).days
        if soonest is None or days < soonest:
            soonest = days
    return soonest


def _next_expiry_end(type_plans: list[dict[str, Any]]) -> str:
    """End date of the soonest-expiring plan (used for tooltip)."""
    if not type_plans:
        return ""
    sorted_plans = sorted(type_plans, key=lambda p: p.get("end_date", "9999-12-31"))
    return sorted_plans[0].get("end_date", "") or ""


def _render_next_expiry_cell(
    type_plans: list[dict[str, Any]], now: datetime, three_months_from_now: datetime
) -> str:
    """Render the Next Expiry cell for a type row: days + color when <90 days out."""
    days = _next_expiry_days(type_plans, now)
    if days is None:
        return '<span style="color: #6c757d;">N/A</span>'
    end_date = _next_expiry_end(type_plans)
    return _format_days_cell(days, end_date)


def _format_days_cell(days: int, end_date: str) -> str:
    if days < 0:
        text, color = "Expired", "#dc3545"
    elif days == 0:
        text, color = "Today", "#dc3545"
    elif days <= 30:
        text, color = f"{days} days", "#dc3545"
    elif days <= 90:
        text, color = f"{days} days", "#ffc107"
    else:
        text, color = f"{days} days", "#232f3e"
    tooltip = f"Next plan ends: {end_date.split('T', 1)[0]}" if end_date else ""
    return f'<span title="{tooltip}" style="cursor: help; color: {color};">{text}</span>'


def _render_plan_details(plan: dict[str, Any]) -> str:
    """Render the expanded details panel for a single plan."""
    savings_plan_arn = plan.get("savings_plan_arn") or ""
    offering_id = plan.get("offering_id") or ""
    description = plan.get("description") or ""
    state = plan.get("state") or ""
    currency = plan.get("currency") or "USD"
    upfront = plan.get("upfront_payment_amount", 0.0) or 0.0
    recurring = plan.get("recurring_payment_amount", 0.0) or 0.0
    term_seconds = plan.get("term_seconds", 0) or 0
    returnable_until = plan.get("returnable_until") or ""
    product_types = plan.get("product_types") or []
    tags = plan.get("tags") or {}
    start_date = plan.get("start_date") or ""
    end_date = plan.get("end_date") or ""

    def _row(label: str, value: str) -> str:
        return f"<tr><th>{label}</th><td>{value}</td></tr>"

    mtd_card = _render_mtd_card(plan, currency)

    rows: list[str] = []

    if description:
        rows.append(_row("Description", description))
    if state:
        rows.append(_row("State", state))
    rows.append(_row("Start", start_date))
    rows.append(_row("End", end_date))
    if term_seconds:
        rows.append(_row("Term Duration", f"{term_seconds:,} seconds"))
    rows.append(_row("Commitment", f"{currency} {plan.get('hourly_commitment', 0.0):.5f}/hour"))
    rows.append(_row("Upfront Payment", f"{currency} {upfront:,.2f}"))
    rows.append(_row("Recurring Payment", f"{currency} {recurring:,.5f}/hour"))
    if product_types:
        chips = "".join(
            f'<span style="display: inline-block; background: #e8eef7; color: #232f3e; '
            f'padding: 2px 10px; border-radius: 12px; margin: 2px 4px 2px 0; font-size: 0.85em;">'
            f"{pt}</span>"
            for pt in product_types
        )
        rows.append(_row("Covered Products", chips))
    if returnable_until:
        rows.append(_row("Returnable Until", returnable_until))
    if savings_plan_arn:
        rows.append(
            _row(
                "ARN",
                f'<code style="font-size: 0.85em;">{savings_plan_arn}</code>',
            )
        )
    if offering_id:
        rows.append(
            _row(
                "Offering ID",
                f'<code style="font-size: 0.85em;">{offering_id}</code>',
            )
        )

    if tags:
        tag_rows = "".join(
            f'<tr><td style="padding: 2px 8px; font-family: monospace; font-size: 0.85em; '
            f'color: #555;">{k}</td>'
            f'<td style="padding: 2px 8px; font-family: monospace; font-size: 0.85em;">{v}</td></tr>'
            for k, v in tags.items()
        )
        tag_table = (
            '<table style="width: auto; margin: 0; border-collapse: collapse;">'
            f"<tbody>{tag_rows}</tbody></table>"
        )
        rows.append(_row("Tags", tag_table))
    else:
        rows.append(_row("Tags", '<em style="color: #6c757d;">none</em>'))

    return (
        '<div class="plan-details-panel">'
        f"{mtd_card}"
        '<table class="plan-details-kv">'
        "<tbody>" + "".join(rows) + "</tbody></table></div>"
    )


def _expiration_phrase(days_remaining_display: str) -> str:
    """Natural phrasing for the expiration meta chunk on a plan card."""
    if days_remaining_display in ("Expired", "Today", "N/A"):
        return (
            days_remaining_display.lower()
            if days_remaining_display == "Expired"
            else ("expires today" if days_remaining_display == "Today" else days_remaining_display)
        )
    return f"{days_remaining_display} left"


def _render_plan_card_metrics(plan: dict[str, Any]) -> str:
    """Compact MTD utilization + discount pills shown on the folded plan card.

    Returns empty when no MTD data is available (new plans, Cost Explorer lag).
    """
    if plan.get("mtd_total_commitment") is None:
        return ""

    utilization_pct = plan.get("mtd_utilization_percentage", 0.0) or 0.0
    discount_pct = plan.get("discount_percentage", 0.0) or 0.0
    net_savings = plan.get("mtd_net_savings", 0.0) or 0.0

    util_color = (
        "#28a745" if utilization_pct >= 95 else "#ff9900" if utilization_pct >= 80 else "#dc3545"
    )

    return (
        f'<span class="plan-card-pill" style="color: #28a745;" '
        f'title="MTD net savings">save ${net_savings:,.0f}</span>'
        f'<span class="plan-card-pill" style="color: {util_color};" '
        f'title="MTD utilization">util {utilization_pct:.0f}%</span>'
        f'<span class="plan-card-pill" style="color: #2196f3;" '
        f'title="Overall discount rate">disc {discount_pct:.1f}%</span>'
    )


def _render_mtd_card(plan: dict[str, Any], currency: str) -> str:
    """Month-to-date utilization/savings tiles for one plan.

    Returns an empty string when no MTD data is available (plan just purchased,
    Cost Explorer still catching up, or the API errored).
    """
    mtd_total = plan.get("mtd_total_commitment")
    if mtd_total is None:
        return ""

    utilization_pct = plan.get("mtd_utilization_percentage", 0.0) or 0.0
    net_savings = plan.get("mtd_net_savings", 0.0) or 0.0
    discount_pct = plan.get("discount_percentage", 0.0) or 0.0

    util_color = (
        "#28a745" if utilization_pct >= 95 else "#ff9900" if utilization_pct >= 80 else "#dc3545"
    )

    def _tile(label: str, value: str, color: str = "#232f3e") -> str:
        return (
            '<div style="flex: 1; min-width: 140px; background: white; padding: 10px 14px; '
            'border-radius: 6px; border: 1px solid #e0e0e0;">'
            f'<div style="font-size: 0.75em; color: #6c757d; text-transform: uppercase; '
            f'letter-spacing: 0.04em; margin-bottom: 4px;">{label}</div>'
            f'<div style="font-size: 1.25em; font-weight: 600; color: {color};">{value}</div>'
            "</div>"
        )

    tiles = "".join(
        [
            _tile("MTD Net Savings", f"{currency} {net_savings:,.2f}", "#28a745"),
            _tile("MTD Commitment", f"{currency} {mtd_total:,.2f}"),
            _tile("MTD Utilization", f"{utilization_pct:.1f}%", util_color),
            _tile("Overall Discount", f"{discount_pct:.1f}%", "#2196f3"),
        ]
    )
    return (
        '<div style="display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 14px;">'
        f"{tiles}</div>"
    )


def render_spike_guard_warning_banner(
    guard_results: dict[str, dict[str, Any]] | None,
    config: dict[str, Any] | None,
) -> str:
    """Yellow banner shown when spike guard flagged any SP type (empty otherwise)."""
    if not guard_results:
        return ""

    flagged = {t: r for t, r in guard_results.items() if r["flagged"]}
    if not flagged:
        return ""

    config = config or {}
    long_days = config["spike_guard_long_lookback_days"]
    short_days = config["spike_guard_short_lookback_days"]

    rows = ""
    for sp_type in sorted(flagged):
        r = flagged[sp_type]
        rows += f"""                <tr>
                    <td>{sp_type.upper()}</td>
                    <td>${r["long_term_avg"]:.4f}/h</td>
                    <td>${r["short_term_avg"]:.4f}/h</td>
                    <td style="color: #856404; font-weight: bold;">+{r["change_percent"]:.1f}%</td>
                </tr>
"""

    return f"""
        <div style="background: #fff3cd; border: 1px solid #ffc107; border-radius: 6px; padding: 15px 20px; margin-bottom: 20px;">
            <h3 style="color: #856404; margin: 0 0 10px 0; font-size: 1.1em;">&#9888; Usage Spike Detected</h3>
            <p style="color: #856404; margin: 0 0 10px 0; font-size: 0.9em;">
                Recent usage ({short_days}d avg) is abnormally high compared to long-term baseline ({long_days}d avg).
                The scheduler will block purchases for the following SP types to avoid over-committing on a temporary spike.
                To adjust sensitivity, configure <code>purchase_strategy.spike_guard</code> in your Terraform module.
            </p>
            <table style="width: auto; margin: 0; font-size: 0.9em;">
                <thead>
                    <tr>
                        <th style="text-align: left; padding: 4px 12px 4px 0;">SP Type</th>
                        <th style="text-align: left; padding: 4px 12px 4px 0;">{long_days}d Avg</th>
                        <th style="text-align: left; padding: 4px 12px 4px 0;">{short_days}d Avg</th>
                        <th style="text-align: left; padding: 4px 12px 4px 0;">Spike</th>
                    </tr>
                </thead>
                <tbody>
{rows}                </tbody>
            </table>
        </div>
"""


def render_sp_type_tab_button(
    sp_type: str, label: str, config: dict[str, Any], show_global_tab: bool
) -> str:
    if not config[f"enable_{sp_type}_sp"]:
        return ""
    active_class = "" if show_global_tab else " active"
    return f'<button class="tab{active_class}" onclick="switchTab(\'{sp_type}\')">{label}</button>'


def render_sp_type_tab_content(
    sp_type: str,
    config: dict[str, Any],
    single_type: str | None,
    preview_data: dict[str, Any] | None,
) -> str:
    if not config[f"enable_{sp_type}_sp"]:
        return ""
    active_class = " active" if single_type == sp_type else ""
    return f'''<div id="{sp_type}-tab" class="tab-content{active_class}">
                <div id="{sp_type}-metrics"></div>
                <div class="chart-container" id="{sp_type}-daily-container" style="display: none;">
                    <canvas id="{sp_type}DailyChart"></canvas>
                </div>
                <div class="chart-container">
                    <canvas id="{sp_type}Chart"></canvas>
                </div>
                {render_sp_type_scheduler_preview(sp_type, preview_data, config or {})}
            </div>'''

"""HTML report generator.

Renders the full HTML report page. Delegates section-level HTML to
html_sections and chart prep to chart_data.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from chart_data import prepare_chart_and_preview_json
from html_sections import (
    build_active_plans_table_html,
    build_breakdown_table_html,
    build_raw_data_section_html,
    render_sp_type_tab_button,
    render_sp_type_tab_content,
    render_spike_guard_warning_banner,
)
from report_data import prepare_html_report_data

from shared.local_mode import is_local_mode


logger = logging.getLogger(__name__)


def generate_html_report(
    coverage_data: dict[str, Any],
    savings_data: dict[str, Any],
    config: dict[str, Any] | None = None,
    raw_data: dict[str, Any] | None = None,
    preview_data: dict[str, Any] | None = None,
    daily_coverage_data: dict[str, Any] | None = None,
    guard_results: dict[str, dict[str, Any]] | None = None,
) -> str:
    """
    Generate HTML report with coverage trends and savings metrics.

    Args:
        coverage_data: Coverage data from SpendingAnalyzer
        savings_data: Savings Plans summary from savings_plans_metrics
        config: Configuration parameters used for the report
        raw_data: Optional raw AWS API responses to include in the report
        daily_coverage_data: Optional daily granularity coverage data for trend chart
        guard_results: Optional spike guard results

    Returns:
        str: HTML report content
    """
    logger.info("Generating HTML report")
    config = config or {}

    data = prepare_html_report_data(coverage_data, savings_data, config)

    report_timestamp = data["report_timestamp"]
    data_period = data["data_period"]
    lookback_hours = data["lookback_hours"]
    overall_coverage = data["overall_coverage"]
    overall_coverage_class = data["overall_coverage_class"]
    plans_count = data["plans_count"]
    net_savings_hourly = data["net_savings_hourly"]
    savings_percentage = data["savings_percentage"]
    total_commitment = data["total_commitment"]
    average_utilization = data["average_utilization"]
    utilization_class = data["utilization_class"]
    breakdown_by_type = data["breakdown_by_type"]

    enabled_types = [
        name
        for name, key in [
            ("compute", "enable_compute_sp"),
            ("database", "enable_database_sp"),
            ("sagemaker", "enable_sagemaker_sp"),
        ]
        if config[key]
    ]
    show_global_tab = len(enabled_types) != 1
    single_type = enabled_types[0] if len(enabled_types) == 1 else None

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
            padding: 30px 30px 0 30px;
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
            font-size: 0.85em;
            font-weight: 600;
            opacity: 0.95;
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
        .section:last-of-type {{
            margin-bottom: 0;
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
        .active-plans-table .plan-summary-row {{
            cursor: pointer;
        }}
        .active-plans-table .plan-toggle-cell {{
            text-align: center;
            color: #6c757d;
            user-select: none;
        }}
        .active-plans-table .plan-toggle-icon {{
            display: inline-block;
            transition: transform 0.15s ease;
        }}
        .active-plans-table .plan-summary-row.expanded .plan-toggle-icon {{
            transform: rotate(90deg);
            color: #2196f3;
        }}
        .active-plans-table .plan-details-row > td {{
            padding: 0;
            border-bottom: 1px solid #e0e0e0;
        }}
        .active-plans-table .plan-details-row:hover {{
            background: transparent;
        }}
        .metric {{
            font-weight: bold;
            color: #232f3e;
        }}
        .footer {{
            padding: 10px 0;
            text-align: center;
            color: #6c757d;
            font-size: 0.85em;
        }}
        .footer p {{
            margin: 2px 0;
        }}
        .no-data {{
            text-align: center;
            padding: 40px;
            color: #6c757d;
            font-style: italic;
        }}
        .chart-container {{
            position: relative;
            height: 280px;
            margin: 20px 0;
            padding: 20px;
            background-color: #f8f9fa;
            border-radius: 8px;
        }}
        .chart-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 4px;
        }}
        .chart-title {{
            font-weight: bold;
            font-size: 14px;
            color: #666;
        }}
        .chart-legend {{
            text-align: right;
            font-size: 13px;
            color: #666;
        }}
        .chart-legend-item {{
            margin-left: 16px;
        }}
        .chart-legend-color {{
            display: inline-block;
            width: 14px;
            height: 14px;
            margin-right: 4px;
            vertical-align: middle;
            border: 1px solid;
            border-radius: 2px;
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
            opacity: 0;
            max-height: 0;
            overflow: hidden;
            transition: opacity 0.3s, max-height 0.3s;
        }}
        .simulator-cta:hover .simulator-description {{
            opacity: 1;
            max-height: 60px;
        }}
        .color-toggle {{
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
        .color-toggle:hover {{
            color: #232f3e;
            background-color: #f8f9fa;
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
            white-space: nowrap;
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
            padding: 12px 16px;
            background: #232f3e;
            color: white;
            border-radius: 6px;
            font-size: 0.85em;
            line-height: 1.5;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
            margin-top: 8px;
            white-space: pre;
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
                <h3>Savings</h3>
                <div style="display: flex; justify-content: space-between; align-items: baseline;">
                    <div class="value" style="margin: 0;">${net_savings_hourly:.2f}/hr</div>
                    <div style="font-size: 0.8em; opacity: 0.9;">${
        net_savings_hourly * 24 * 30:,.0f}/mo</div>
                </div>
            </div>
            <div class="summary-card blue">
                <h3>Average Discount</h3>
                <div class="value">{savings_percentage:.1f}%</div>
            </div>
            <div class="summary-card {overall_coverage_class}">
                <h3>Coverage (% of min-hourly)</h3>
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

{render_spike_guard_warning_banner(guard_results, config)}
        <div class="section">
            <h2>Report Parameters</h2>
            <div class="params-grid">
                <div class="param-item">
                    <strong>Lookback Period:</strong> <span>{config["lookback_hours"]} hours</span>
                </div>
                <span style="color: #dee2e6;">•</span>
                <div class="param-item">
                    <strong>Granularity:</strong> <span>HOURLY</span>
                </div>
                <span style="color: #dee2e6;">•</span>
                <div class="param-item">
                    <strong>Enabled SP(s):</strong> <span>{
        ", ".join(
            [
                sp
                for sp, enabled in [
                    ("Compute", config["enable_compute_sp"]),
                    ("Database", config["enable_database_sp"]),
                    ("SageMaker", config["enable_sagemaker_sp"]),
                ]
                if enabled
            ]
        )
    }</span>
                </div>
                <span style="color: #dee2e6;">•</span>
                <div class="param-item">
                    <strong>Low Util. Threshold:</strong> <span>{
        config["low_utilization_threshold"]
    }%</span>
                </div>
            </div>
        </div>

        <div class="section">
            <h2>Usage Over Time and Scheduler Preview</h2>

            <div class="tabs">
                {
        '<button class="tab active" onclick="switchTab(\'global\')">Global (All Types)</button>'
        if show_global_tab
        else ""
    }
                {render_sp_type_tab_button("compute", "Compute", config, show_global_tab)}
                {render_sp_type_tab_button("database", "Database", config, show_global_tab)}
                {render_sp_type_tab_button("sagemaker", "SageMaker", config, show_global_tab)}
                <button class="color-toggle" onclick="toggleActiveTabColors()" title="Toggle color-blind friendly mode" style="margin-left: auto;">
                    🎨 Toggle Colors
                </button>
            </div>

            {
        '<div id="global-tab" class="tab-content active">'
        if show_global_tab
        else '<div id="global-tab" class="tab-content" style="display:none;">'
    }
                <div class="chart-container" id="global-daily-container" style="display: none;">
                    <canvas id="globalDailyChart"></canvas>
                </div>
                <div class="chart-container">
                    <canvas id="globalChart"></canvas>
                </div>
            </div>

            {render_sp_type_tab_content("compute", config, single_type, preview_data)}

            {render_sp_type_tab_content("database", config, single_type, preview_data)}

            {render_sp_type_tab_content("sagemaker", config, single_type, preview_data)}
        </div>

        <div class="section">
            <h2>Existing Savings Plans</h2>

            <h3 style="color: #232f3e; margin-top: 25px; margin-bottom: 15px; font-size: 1.2em;">Breakdown by Type</h3>
"""

    html += build_breakdown_table_html(
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
    html += build_active_plans_table_html(plans)

    monthly_savings = net_savings_hourly * 24 * 30
    html += build_raw_data_section_html(raw_data, report_timestamp, monthly_savings)

    (
        chart_data,
        daily_chart_data,
        metrics_json,
        optimal_coverage_json,
        follow_aws_json,
        configured_target_json,
    ) = prepare_chart_and_preview_json(
        coverage_data, savings_data, config, daily_coverage_data, preview_data
    )

    html += f"""
    <script>
        const allChartData = {chart_data};
        const dailyChartData = {daily_chart_data};
        const metricsData = {metrics_json};
        const optimalCoverageFromPython = {optimal_coverage_json};
        const followAwsData = {follow_aws_json};
        const configuredTargetData = {configured_target_json};
        const lookbackHours = {lookback_hours};

        // Color palettes - Two combinations for different types of color vision deficiency
        const colorPalettes = {{
            palette1: {{
                // Blue & Orange - Best for red-green colorblind (Protanopia/Deuteranopia)
                covered: 'rgba(0, 114, 178, 0.7)',      // Deep Blue
                ondemand: 'rgba(230, 159, 0, 0.7)',     // Bright Orange
                coveredBorder: 'rgb(0, 114, 178)',
                ondemandBorder: 'rgb(230, 159, 0)',
                configuredTarget: 'rgba(0, 158, 115, 0.9)',      // Bluish Green
                configuredTargetBg: 'rgba(0, 128, 90, 0.9)'
            }},
            palette2: {{
                // Pink & Teal - Best for blue-yellow colorblind (Tritanopia)
                covered: 'rgba(204, 121, 167, 0.7)',    // Pink/Magenta
                ondemand: 'rgba(86, 180, 233, 0.7)',    // Teal/Cyan
                coveredBorder: 'rgb(204, 121, 167)',
                ondemandBorder: 'rgb(86, 180, 233)',
                configuredTarget: 'rgba(213, 94, 0, 0.9)',       // Vermillion
                configuredTargetBg: 'rgba(180, 75, 0, 0.9)'
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

        // Toggle colors for all charts in the currently active tab
        function toggleActiveTabColors() {{
            const activeTab = document.querySelector('.tab-content.active');
            if (!activeTab) return;
            const tabType = activeTab.id.replace('-tab', '');
            const hourlyId = tabType + 'Chart';
            const dailyId = tabType + 'DailyChart';
            const currentMode = chartColorModes[hourlyId] || 'palette1';
            const newMode = currentMode === 'palette2' ? 'palette1' : 'palette2';
            const palette = colorPalettes[newMode];

            [hourlyId, dailyId].forEach(function(id) {{
                const chart = chartInstances[id];
                if (!chart) return;
                chartColorModes[id] = newMode;
                // Dataset 0 is always "covered"
                chart.data.datasets[0].backgroundColor = palette.covered;
                chart.data.datasets[0].borderColor = palette.coveredBorder;
                // With 3 datasets: [covered, future, ondemand]; with 2: [covered, ondemand]
                const lastIdx = chart.data.datasets.length - 1;
                chart.data.datasets[lastIdx].backgroundColor = palette.ondemand;
                chart.data.datasets[lastIdx].borderColor = palette.ondemandBorder;
                if (chart.data.datasets.length === 3) {{
                    chart.data.datasets[1].backgroundColor = palette.configuredTarget;
                    chart.data.datasets[1].borderColor = palette.configuredTarget;
                }}
                // Update configured target annotation color if present
                const ann = chart.options.plugins.annotation && chart.options.plugins.annotation.annotations;
                if (ann) {{
                    if (ann.currentCoverage) {{
                        ann.currentCoverage.label.backgroundColor = palette.coveredBorder;
                    }}
                    if (ann.configuredTarget) {{
                        ann.configuredTarget.label.backgroundColor = palette.configuredTargetBg;
                    }}
                }}
                chart.update();
            }});

            // Update legend colors in the header
            if (activeTab) {{
                activeTab.querySelectorAll('.chart-legend-color').forEach(function(el) {{
                    const role = el.getAttribute('data-role');
                    if (role === 'covered') {{
                        el.style.background = palette.covered;
                        el.style.borderColor = palette.coveredBorder;
                    }} else if (role === 'future') {{
                        el.style.background = palette.configuredTarget;
                        el.style.borderColor = palette.configuredTarget;
                    }} else if (role === 'ondemand') {{
                        el.style.background = palette.ondemand;
                        el.style.borderColor = palette.ondemandBorder;
                    }}
                }});
            }}
        }}

        // Active Plans: expand/collapse a row to show full plan details
        function togglePlanDetails(detailsId, summaryRow) {{
            const detailsRow = document.getElementById(detailsId);
            if (!detailsRow) return;
            const isHidden = detailsRow.hasAttribute('hidden');
            if (isHidden) {{
                detailsRow.removeAttribute('hidden');
                summaryRow.classList.add('expanded');
            }} else {{
                detailsRow.setAttribute('hidden', '');
                summaryRow.classList.remove('expanded');
            }}
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
        function _injectChartHeader(canvasId, title, spType) {{
            const canvas = document.getElementById(canvasId);
            const container = canvas.parentElement;
            if (!container.querySelector('.chart-header')) {{
                const palette = colorPalettes['palette1'];
                const hasTarget = spType && configuredTargetData[spType];
                const header = document.createElement('div');
                header.className = 'chart-header';
                let legendHtml = `
                    <span class="chart-legend-item"><span class="chart-legend-color" data-role="covered" style="background:${{palette.covered}};border-color:${{palette.coveredBorder}};"></span>Existing SP Commitment</span>`;
                if (hasTarget) {{
                    legendHtml += `
                    <span class="chart-legend-item"><span class="chart-legend-color" data-role="future" style="background:${{palette.configuredTarget}};border-color:${{palette.configuredTarget}};"></span>Added by next purchase</span>`;
                }}
                legendHtml += `
                    <span class="chart-legend-item"><span class="chart-legend-color" data-role="ondemand" style="background:${{palette.ondemand}};border-color:${{palette.ondemandBorder}};"></span>On-Demand Cost</span>`;
                header.innerHTML = `
                    <div class="chart-title">${{title}}</div>
                    <div class="chart-legend">${{legendHtml}}</div>`;
                container.insertBefore(header, canvas);
            }}
        }}

        function createChart(canvasId, chartData, title, spType, showCoverageLine) {{
            const ctx = document.getElementById(canvasId);
            _injectChartHeader(canvasId, title, spType);

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
                        z: 1,
                        yMin: onDemandEquivalent,
                        yMax: onDemandEquivalent,
                        borderColor: 'rgba(255, 255, 255, 0.8)',
                        borderWidth: 2,
                        borderDash: [4, 3],
                        label: {{
                            display: true,
                            z: 10,
                            content: 'Current coverage: $' + onDemandEquivalent.toFixed(2) + '/hr (' + currentCoveragePct.toFixed(1) + '%)',
                            position: 'start',
                            backgroundColor: palette.coveredBorder,
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
                        z: 1,
                        yMin: minHourly,
                        yMax: minHourly,
                        borderColor: 'rgba(70, 70, 70, 0.9)',
                        borderWidth: 2,
                        borderDash: [8, 4],
                        label: {{
                            display: true,
                            z: 10,
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

                // Add configured target line (projected coverage after next purchase)
                const targetData = configuredTargetData[spType];
                if (targetData) {{
                    const projectedOdEquiv = onDemandEquivalent + targetData.added_od_equiv;
                    const projectedCov = targetData.projected_coverage;
                    annotations.configuredTarget = {{
                        type: 'line',
                        z: 1,
                        yMin: projectedOdEquiv,
                        yMax: projectedOdEquiv,
                        borderColor: 'rgba(255, 255, 255, 0.8)',
                        borderWidth: 2,
                        borderDash: [4, 3],
                        label: {{
                            display: true,
                            z: 10,
                            content: 'Next coverage: $' + projectedOdEquiv.toFixed(2) + '/hr (' + projectedCov.toFixed(1) + '%)',
                            position: 'center',
                            backgroundColor: palette.configuredTargetBg,
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

            // Build "future" dataset: shows how much the configured purchase would cover
            const futureTargetData = spType ? configuredTargetData[spType] : null;
            let futureData = null;
            if (futureTargetData) {{
                const addedOd = futureTargetData.added_od_equiv;
                futureData = chartData.ondemand.map(function(od) {{
                    return Math.min(addedOd, od);
                }});
            }}

            const datasets = [
                {{
                    label: 'Existing SP Commitment',
                    data: chartData.covered,
                    backgroundColor: palette.covered,
                    borderColor: palette.coveredBorder,
                    borderWidth: 1,
                    stack: 'stack0'
                }}
            ];
            if (futureData) {{
                datasets.push({{
                    label: 'Added by next purchase',
                    data: futureData,
                    backgroundColor: palette.configuredTarget,
                    borderColor: palette.configuredTarget,
                    borderWidth: 1,
                    stack: 'stack0'
                }});
                const adjustedOndemand = chartData.ondemand.map(function(od, i) {{
                    return Math.max(0, od - futureData[i]);
                }});
                datasets.push({{
                    label: 'On-Demand Cost',
                    data: adjustedOndemand,
                    backgroundColor: palette.ondemand,
                    borderColor: palette.ondemandBorder,
                    borderWidth: 1,
                    stack: 'stack0'
                }});
            }} else {{
                datasets.push({{
                    label: 'On-Demand Cost',
                    data: chartData.ondemand,
                    backgroundColor: palette.ondemand,
                    borderColor: palette.ondemandBorder,
                    borderWidth: 1,
                    stack: 'stack0'
                }});
            }}

            chartInstances[canvasId] = new Chart(ctx, {{
                type: 'bar',
                data: {{
                    labels: chartData.labels,
                    datasets: datasets
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: {{
                        mode: 'index',
                        intersect: false
                    }},
                    plugins: {{
                        title: {{ display: false }},
                        legend: {{ display: false }},
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
                                        if (item.dataset.label.includes('Commitment') || item.dataset.label.includes('next purchase')) {{
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
                            title: {{ display: false }},
                            ticks: {{
                                autoSkip: false,
                                maxRotation: 0,
                                callback: function(value, index) {{
                                    const label = chartData.labels[index];
                                    if (!label) return '';
                                    const parts = label.split(' ');
                                    if (parts.length < 2) return '';
                                    if (parts[1] === '12:00') {{
                                        const dp = parts[0].split('-');
                                        return dp[1] + '/' + dp[0];
                                    }}
                                    return '';
                                }}
                            }}
                        }},
                        y: {{
                            stacked: true,
                            title: {{ display: false }},
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

        // Function to create daily chart (simplified - no annotation lines)
        function createDailyChart(canvasId, chartData, title) {{
            const ctx = document.getElementById(canvasId);
            _injectChartHeader(canvasId, title, null);
            const palette = colorPalettes['palette1'];

            chartInstances[canvasId] = new Chart(ctx, {{
                type: 'bar',
                data: {{
                    labels: chartData.labels,
                    datasets: [
                        {{
                            label: 'Existing SP Commitment',
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
                        title: {{ display: false }},
                        legend: {{ display: false }},
                        tooltip: {{
                            callbacks: {{
                                title: function(tooltipItems) {{
                                    const index = tooltipItems[0].dataIndex;
                                    const timestamp = chartData.timestamps[index];
                                    // Timestamps are period END dates, subtract 1 day to show actual date
                                    const date = new Date(timestamp + 'T00:00:00');
                                    date.setDate(date.getDate() - 1);
                                    const days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
                                    const dayName = days[date.getDay()];
                                    const yy = date.getFullYear();
                                    const mm = String(date.getMonth() + 1).padStart(2, '0');
                                    const dd = String(date.getDate()).padStart(2, '0');
                                    return yy + '-' + mm + '-' + dd + ' (' + dayName + ')';
                                }},
                                footer: function(tooltipItems) {{
                                    let covered = 0;
                                    let ondemand = 0;
                                    tooltipItems.forEach(function(item) {{
                                        if (item.dataset.label.includes('Commitment') || item.dataset.label.includes('next purchase')) {{
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
                            title: {{ display: false }},
                            ticks: {{
                                autoSkip: false,
                                maxRotation: 0,
                                callback: function(value, index) {{
                                    const ts = chartData.timestamps[index];
                                    if (!ts) return '';
                                    // Timestamps are period END dates; subtract 1 day to get actual date
                                    const date = new Date(ts + 'T00:00:00');
                                    date.setDate(date.getDate() - 1);
                                    if (date.getDate() !== 1) return '';
                                    const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
                                    return months[date.getMonth()] + ' ' + date.getFullYear();
                                }}
                            }}
                        }},
                        y: {{
                            stacked: true,
                            title: {{ display: false }},
                            ticks: {{
                                callback: function(value) {{
                                    return '$' + value.toFixed(0);
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

                // Include next purchase data if available
                const targetInfo = configuredTargetData[typeKey];
                const nextPurchase = targetInfo ? {{
                    added_od_equiv: targetInfo.added_od_equiv,
                    added_commitment: targetInfo.added_commitment,
                    projected_coverage: targetInfo.projected_coverage
                }} : null;

                const usageData = {{
                    hourly_costs: hourlyCosts,
                    stats: stats,
                    current_coverage: currentCoverageDollars,  // On-demand equivalent coverage in $/hour
                    next_purchase: nextPurchase,  // Configured next purchase (od equiv + projected coverage)
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

        // Create all charts (only for enabled SP types whose DOM elements exist)
        {"createChart('globalChart', allChartData.global, 'Hourly Usage: On-Demand vs Covered (All Types) - ' + lookbackHours + ' hours', null, false);" if show_global_tab else "// Global chart skipped (single type enabled)"}
        if (document.getElementById('computeChart')) {{
            createChart('computeChart', allChartData.compute, 'Compute Savings Plans - Hourly Usage (' + lookbackHours + ' hours)', 'compute', true);
        }}
        if (document.getElementById('databaseChart')) {{
            createChart('databaseChart', allChartData.database, 'Database Savings Plans - Hourly Usage (' + lookbackHours + ' hours)', 'database', true);
        }}
        if (document.getElementById('sagemakerChart')) {{
            createChart('sagemakerChart', allChartData.sagemaker, 'SageMaker Savings Plans - Hourly Usage (' + lookbackHours + ' hours)', 'sagemaker', true);
        }}

        // Create daily charts if data is available
        if (dailyChartData) {{
            const dailyDays = dailyChartData.global.labels.length;
            {"createDailyChart('globalDailyChart', dailyChartData.global, 'Daily Usage: On-Demand vs Covered (All Types) - ' + dailyDays + ' days'); document.getElementById('global-daily-container').style.display = '';" if show_global_tab else "// Global daily chart skipped (single type enabled)"}
            if (document.getElementById('computeDailyChart')) {{
                createDailyChart('computeDailyChart', dailyChartData.compute, 'Compute Savings Plans - Daily Usage (' + dailyChartData.compute.labels.length + ' days)');
                document.getElementById('compute-daily-container').style.display = '';
            }}
            if (document.getElementById('databaseDailyChart')) {{
                createDailyChart('databaseDailyChart', dailyChartData.database, 'Database Savings Plans - Daily Usage (' + dailyChartData.database.labels.length + ' days)');
                document.getElementById('database-daily-container').style.display = '';
            }}
            if (document.getElementById('sagemakerDailyChart')) {{
                createDailyChart('sagemakerDailyChart', dailyChartData.sagemaker, 'SageMaker Savings Plans - Daily Usage (' + dailyChartData.sagemaker.labels.length + ' days)');
                document.getElementById('sagemaker-daily-container').style.display = '';
            }}
        }}

        // Render metrics for each type (only if their container exists)
        if (document.getElementById('compute-metrics')) {{
            renderMetrics('compute-metrics', metricsData.compute, 'Compute', allChartData.compute.stats, 'compute');
        }}
        if (document.getElementById('database-metrics')) {{
            renderMetrics('database-metrics', metricsData.database, 'Database', allChartData.database.stats, 'database');
        }}
        if (document.getElementById('sagemaker-metrics')) {{
            renderMetrics('sagemaker-metrics', metricsData.sagemaker, 'SageMaker', allChartData.sagemaker.stats, 'sagemaker');
        }}
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

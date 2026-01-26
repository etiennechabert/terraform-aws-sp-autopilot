"""
Reporter Lambda - Generates periodic coverage and savings reports.

This Lambda:
1. Collects coverage history over the reporting period
2. Gathers savings data from active Savings Plans
3. Calculates estimated savings achieved
4. Generates HTML/JSON/CSV report with trends and metrics
5. Uploads report to S3 with timestamp-based key
6. Optionally sends email notification with S3 link
"""

from __future__ import annotations

import json
import logging
import webbrowser
from pathlib import Path
from typing import Any

import notifications as notifications_module
import report_generator
import scheduler_preview
from config import CONFIG_SCHEMA

from shared.handler_utils import (
    get_enabled_plan_types,
    initialize_clients,
    lambda_handler_wrapper,
    load_config_from_env,
    send_error_notification,
)
from shared.local_mode import is_local_mode
from shared.savings_plans_metrics import get_savings_plans_summary
from shared.spending_analyzer import SpendingAnalyzer
from shared.storage_adapter import StorageAdapter


logger = logging.getLogger()
logger.setLevel(logging.INFO)


@lambda_handler_wrapper("Reporter")
def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """
    Reporter Lambda - Generates coverage and savings reports.

    Flow:
    1. Load and validate configuration
    2. Initialize AWS clients
    3. Collect coverage data from SpendingAnalyzer
    4. Collect savings plans metrics
    5. Check for low utilization and alert if needed
    6. Generate report in requested format
    7. Upload report to storage
    8. Send email notification if enabled
    """
    from shared.config_validation import validate_reporter_config

    config = load_config_from_env(CONFIG_SCHEMA, validator=validate_reporter_config)

    clients = initialize_clients(
        config,
        "sp-autopilot-reporter",
        lambda msg: _send_error_notification(
            config["sns_topic_arn"],
            msg,
            config.get("slack_webhook_url"),
            config.get("teams_webhook_url"),
        ),
    )

    # Clear any previous AWS API responses and start fresh (if debug data collection is enabled)
    if config.get("include_debug_data", False):
        from shared.aws_debug import clear_responses

        clear_responses()

    # Collect coverage data using SpendingAnalyzer
    analyzer = SpendingAnalyzer(clients["savingsplans"], clients["ce"])
    coverage_data = analyzer.analyze_current_spending(config)
    coverage_data.pop("_unknown_services", None)

    # Collect savings plans metrics (per enabled plan type)
    savings_data = get_savings_plans_summary(
        clients["savingsplans"],
        clients["ce"],
        get_enabled_plan_types(config),
        config["lookback_days"],
        config["granularity"],
    )

    logger.info(
        f"Data collected - Coverage: {coverage_data.get('compute', {}).get('summary', {}).get('avg_coverage_total', 0):.1f}%, "
        f"Active plans: {savings_data.get('plans_count', 0)}, "
        f"Net savings: ${savings_data.get('actual_savings', {}).get('net_savings', 0):,.0f}"
    )

    # Check for low utilization and alert if needed
    notifications_module.check_and_alert_low_utilization(clients["sns"], config, savings_data)

    # Calculate scheduler preview (what would scheduler purchase + optimal analysis)
    preview_data = scheduler_preview.calculate_scheduler_preview(
        config, clients, coverage_data, savings_data
    )

    # Count total recommendations across all strategies
    total_recs = sum(
        len(s.get("purchases", [])) for s in preview_data.get("strategies", {}).values()
    )
    logger.info(
        f"Scheduler preview calculated - Configured: {preview_data.get('configured_strategy', 'unknown')}, "
        f"Total recommendations: {total_recs}"
    )

    # Prepare raw data for HTML report - reorder for better readability
    def reorder_coverage_data(data):
        """Reorder coverage data to show summary before timeseries for better readability."""
        reordered = {}
        for key, value in data.items():
            if isinstance(value, dict) and "summary" in value and "timeseries" in value:
                # Put summary first, then timeseries, then any other keys
                reordered[key] = {
                    "summary": value["summary"],
                    "timeseries": value["timeseries"],
                    **{k: v for k, v in value.items() if k not in ["summary", "timeseries"]},
                }
            else:
                reordered[key] = value
        return reordered

    def reorder_savings_data(data):
        """Reorder savings data to show plans last for better readability."""
        if not isinstance(data, dict) or "plans" not in data:
            return data
        # Put all keys except "plans" first, then "plans" last
        reordered = {k: v for k, v in data.items() if k != "plans"}
        reordered["plans"] = data["plans"]
        return reordered

    # Only include raw data section if debug data is enabled
    raw_data = None
    if config.get("include_debug_data", False):
        from shared.aws_debug import get_responses

        raw_data = {
            "coverage_data": reorder_coverage_data(coverage_data),
            "savings_data": reorder_savings_data(savings_data),
            "config": {
                "lookback_days": config["lookback_days"],
                "granularity": config["granularity"],
                "coverage_target_percent": config["coverage_target_percent"],
                "enable_compute_sp": config["enable_compute_sp"],
                "enable_database_sp": config["enable_database_sp"],
                "enable_sagemaker_sp": config["enable_sagemaker_sp"],
                "low_utilization_threshold": config["low_utilization_threshold"],
                "report_format": config["report_format"],
                "email_reports": config["email_reports"],
            },
            "aws_api_responses": get_responses(),
        }

    # Generate report
    report_content = report_generator.generate_report(
        coverage_data, savings_data, config["report_format"], config, raw_data, preview_data
    )
    logger.info(
        f"Report generated ({len(report_content)} bytes, format: {config['report_format']})"
    )

    # Upload to storage
    storage_adapter = StorageAdapter(s3_client=clients["s3"], bucket_name=config["reports_bucket"])
    s3_object_key = storage_adapter.upload_report(
        report_content=report_content, report_format=config["report_format"]
    )
    logger.info(f"Report uploaded: {s3_object_key}")

    # Send email notification if enabled
    if config["email_reports"]:
        notifications_module.send_report_email(
            clients["sns"], config, s3_object_key, coverage_data, savings_data, storage_adapter
        )
        logger.info("Report email notification sent")
    else:
        logger.info("Email notifications disabled - skipping email")

    # Auto-open report in browser if running locally (developer convenience)
    if is_local_mode() and config["report_format"] == "html":
        file_path = Path(s3_object_key)
        if file_path.exists():
            logger.info(f"Opening report in browser: {file_path}")
            webbrowser.open(f"file://{file_path.absolute()}")
        else:
            logger.warning(f"Report file not found for auto-open: {file_path}")

    return {
        "statusCode": 200,
        "body": json.dumps(
            {
                "message": "Reporter completed successfully",
                "s3_object_key": s3_object_key,
                "active_plans": savings_data.get("plans_count", 0),
            }
        ),
    }


def _send_error_notification(
    sns_topic_arn: str,
    error_msg: str,
    slack_webhook_url: str | None = None,
    teams_webhook_url: str | None = None,
) -> None:
    """Send error notification via SNS and optional Slack/Teams."""
    import boto3

    send_error_notification(
        sns_client=boto3.client("sns"),
        sns_topic_arn=sns_topic_arn,
        error_message=error_msg,
        lambda_name="Reporter",
        slack_webhook_url=slack_webhook_url,
        teams_webhook_url=teams_webhook_url,
    )


if __name__ == "__main__":
    handler({}, None)

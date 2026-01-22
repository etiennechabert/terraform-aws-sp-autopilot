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
from typing import Any

import notifications as notifications_module
import report_generator
from config import CONFIG_SCHEMA

from shared.handler_utils import (
    initialize_clients,
    lambda_handler_wrapper,
    load_config_from_env,
    send_error_notification,
)
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
    config = load_config_from_env(CONFIG_SCHEMA)

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

    # Collect coverage data using SpendingAnalyzer
    analyzer = SpendingAnalyzer(clients["savingsplans"], clients["ce"])
    coverage_data = analyzer.analyze_current_spending(config)
    coverage_data.pop("_unknown_services", None)

    # Collect savings plans metrics
    savings_data = get_savings_plans_summary(
        clients["savingsplans"], clients["ce"], lookback_days=config["lookback_days"]
    )

    logger.info(
        f"Data collected - Coverage: {coverage_data.get('compute', {}).get('summary', {}).get('avg_coverage', 0):.1f}%, "
        f"Active plans: {savings_data.get('plans_count', 0)}, "
        f"Net savings: ${savings_data.get('actual_savings', {}).get('net_savings', 0):,.0f}"
    )

    # Check for low utilization and alert if needed
    notifications_module.check_and_alert_low_utilization(clients["sns"], config, savings_data)

    # Generate report
    report_content = report_generator.generate_report(
        coverage_data, savings_data, config["report_format"]
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
            clients["sns"], config, s3_object_key, coverage_data, savings_data
        )
        logger.info("Report email notification sent")
    else:
        logger.info("Email notifications disabled - skipping email")

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

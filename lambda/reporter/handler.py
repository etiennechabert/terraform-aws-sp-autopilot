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
from config import CONFIG_SCHEMA

from shared.handler_utils import (
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

    # Calculate purchase forecast (what Scheduler would buy on next run)
    purchase_forecast = _calculate_purchase_forecast(coverage_data, config)
    logger.info(
        f"Purchase forecast: {len(purchase_forecast)} potential purchases "
        f"to reach {config['coverage_target_percent']:.0f}% target"
    )

    # Generate report
    report_content = report_generator.generate_report(
        coverage_data, savings_data, config["report_format"], config, purchase_forecast
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


def _calculate_purchase_forecast(
    coverage_data: dict[str, Any], config: dict[str, Any]
) -> list[dict[str, Any]]:
    """
    Calculate what the Scheduler would purchase on its next run.

    Uses the actual scheduler strategy implementations to ensure forecasts
    match real behavior.

    Args:
        coverage_data: Current coverage data from SpendingAnalyzer
        config: Configuration including coverage_target_percent, purchase_strategy_type, etc.

    Returns:
        list: Forecasted purchase plans with sp_type, commitment, monthly_cost, reason
    """
    import sys
    from pathlib import Path

    # Import actual scheduler strategies
    scheduler_path = Path(__file__).parent.parent / "scheduler"
    if str(scheduler_path) not in sys.path:
        sys.path.insert(0, str(scheduler_path))

    from dichotomy_strategy import calculate_purchase_need_dichotomy
    from fixed_strategy import calculate_purchase_need_fixed
    from follow_aws_strategy import calculate_purchase_need_follow_aws

    strategy = config.get("purchase_strategy_type", "fixed")

    # Add scheduler-specific config defaults that reporter doesn't normally have
    scheduler_config = config.copy()
    scheduler_config.setdefault("compute_sp_payment_option", "NO_UPFRONT")
    scheduler_config.setdefault("database_sp_payment_option", "NO_UPFRONT")
    scheduler_config.setdefault("sagemaker_sp_payment_option", "NO_UPFRONT")
    scheduler_config.setdefault("compute_sp_term", "THREE_YEAR")
    scheduler_config.setdefault("sagemaker_sp_term", "THREE_YEAR")
    scheduler_config.setdefault("min_purchase_percent", 1.0)

    # Call the actual scheduler strategy (pass spending_data directly to avoid refetching)
    if strategy == "fixed":
        purchase_plans = calculate_purchase_need_fixed(
            scheduler_config, None, spending_data=coverage_data
        )
    elif strategy == "dichotomy":
        purchase_plans = calculate_purchase_need_dichotomy(
            scheduler_config, None, spending_data=coverage_data
        )
    elif strategy == "follow_aws":
        purchase_plans = calculate_purchase_need_follow_aws(
            scheduler_config, None, spending_data=coverage_data
        )
    else:
        logger.warning(f"Unknown strategy '{strategy}', returning empty forecast")
        return []

    # Transform scheduler purchase plans to forecast format
    forecast = []
    sp_type_names = {"compute": "Compute", "database": "Database", "sagemaker": "SageMaker"}

    for plan in purchase_plans:
        sp_type_key = plan["sp_type"]
        sp_type_name = sp_type_names.get(sp_type_key, sp_type_key.capitalize())

        current_coverage = plan["details"]["coverage"]["current"]
        target_coverage = plan["details"]["coverage"]["target"]
        commitment = plan["hourly_commitment"]
        monthly_cost = commitment * 730

        # Calculate new coverage after this purchase
        summary = coverage_data.get(sp_type_key, {}).get("summary", {})
        avg_hourly_total = summary.get("avg_hourly_total", 0.0)
        new_coverage = current_coverage + (
            (commitment / avg_hourly_total * 100) if avg_hourly_total > 0 else 0
        )

        forecast.append(
            {
                "sp_type": sp_type_name,
                "sp_type_key": sp_type_key,
                "current_coverage": current_coverage,
                "target_coverage": target_coverage,
                "gap": plan["details"]["coverage"]["gap"],
                "commitment": commitment,
                "monthly_cost": monthly_cost,
                "new_coverage": min(new_coverage, 100.0),
                "strategy": strategy,
                "reason": f"Fill gap from {current_coverage:.1f}% to {min(new_coverage, target_coverage):.1f}%",
            }
        )

    return forecast


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

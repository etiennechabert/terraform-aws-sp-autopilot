"""
Notification Module for Reporter Lambda.

Handles email notifications and alerts for the Reporter Lambda.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    from mypy_boto3_sns.client import SNSClient


logger = logging.getLogger(__name__)


def _generate_s3_url(storage_adapter: Any, s3_object_key: str, bucket_name: str) -> str:
    """Generate S3 URL with pre-signed URL fallback."""
    if not storage_adapter:
        return f"https://{bucket_name}.s3.amazonaws.com/{s3_object_key}"

    try:
        url = storage_adapter.generate_presigned_url(s3_object_key, expiration=604800)
        logger.info("Using pre-signed URL for report access")
        return url
    except Exception as e:
        logger.warning(f"Failed to generate pre-signed URL, falling back to direct URL: {e}")
        return f"https://{bucket_name}.s3.amazonaws.com/{s3_object_key}"


SP_TYPE_KEYS = ["compute", "database", "sagemaker"]


def _get_min_hourly_from_timeseries(type_data: dict[str, Any]) -> float:
    """Extract minimum hourly total spend from timeseries."""
    timeseries = type_data.get("timeseries", [])
    total_costs = [point["total"] for point in timeseries if point["total"] > 0]
    return min(total_costs) if total_costs else 0.0


def _calculate_overall_coverage(coverage_data: dict[str, Any]) -> float:
    """Calculate overall coverage across all plan types."""
    total_hourly_covered = 0.0
    total_min_hourly = 0.0

    for key in SP_TYPE_KEYS:
        type_data = coverage_data[key]
        total_hourly_covered += type_data["summary"]["avg_hourly_covered"]
        total_min_hourly += _get_min_hourly_from_timeseries(type_data)

    return (total_hourly_covered / total_min_hourly * 100) if total_min_hourly > 0 else 0.0


def _send_slack_notification(config: dict[str, Any], subject: str, body_lines: list[str]) -> None:
    """Send Slack notification (non-fatal)."""
    try:
        slack_webhook_url = config.get("slack_webhook_url")
        if slack_webhook_url:
            from shared import notifications

            slack_message = notifications.format_slack_message(subject, body_lines, severity="info")
            if notifications.send_slack_notification(slack_webhook_url, slack_message):
                logger.info("Report email sent via Slack")
    except Exception as e:
        logger.warning(f"Slack notification error (non-fatal): {e}")


def _send_teams_notification(config: dict[str, Any], subject: str, body_lines: list[str]) -> None:
    """Send Teams notification (non-fatal)."""
    try:
        teams_webhook_url = config.get("teams_webhook_url")
        if teams_webhook_url:
            from shared import notifications

            teams_message = notifications.format_teams_message(subject, body_lines)
            if notifications.send_teams_notification(teams_webhook_url, teams_message):
                logger.info("Report email sent via Teams")
    except Exception as e:
        logger.warning(f"Teams notification error (non-fatal): {e}")


def check_and_alert_low_utilization(
    sns_client: SNSClient, config: dict[str, Any], savings_data: dict[str, Any]
) -> None:
    """
    Check if Savings Plans utilization is below threshold and send alert if needed.

    Args:
        sns_client: Boto3 SNS client
        config: Configuration dictionary
        savings_data: Savings Plans summary data
    """
    threshold = config["low_utilization_threshold"]
    average_utilization = savings_data["average_utilization"]
    plans_count = savings_data["plans_count"]

    if plans_count == 0:
        logger.info("No active Savings Plans - skipping low utilization check")
        return

    if average_utilization >= threshold:
        logger.info(
            f"Utilization {average_utilization:.2f}% is above threshold {threshold:.2f}% - no alert needed"
        )
        return

    logger.warning(
        f"Low utilization detected: {average_utilization:.2f}% (threshold: {threshold:.2f}%)"
    )

    subject = (
        f"Low Savings Plans Utilization Alert: {average_utilization:.1f}% "
        f"(threshold: {threshold:.0f}%)"
    )

    body_lines = [
        "Savings Plans utilization has fallen below the configured threshold.",
        "",
        f"Current Utilization: {average_utilization:.2f}%",
        f"Alert Threshold: {threshold:.2f}%",
        f"Active Plans: {plans_count}",
        f"Total Commitment: ${savings_data['total_commitment']:.4f}/hour",
        "",
        "This may indicate:",
        "• Decreased compute usage requiring plan adjustment",
        "• Over-commitment relative to actual usage",
        "• Opportunity to optimize Savings Plans portfolio",
        "",
        "Review your Savings Plans inventory and usage patterns to optimize costs.",
    ]

    try:
        sns_client.publish(
            TopicArn=config["sns_topic_arn"],
            Subject=subject,
            Message="\n".join(body_lines),
        )
        logger.info("Low utilization alert sent via SNS")
    except Exception as e:
        logger.error(f"Failed to send SNS alert: {e}")
        raise

    # Send Slack/Teams notifications (non-fatal)
    try:
        slack_webhook_url = config.get("slack_webhook_url")
        if slack_webhook_url:
            from shared import notifications

            slack_message = notifications.format_slack_message(
                subject, body_lines, severity="warning"
            )
            if notifications.send_slack_notification(slack_webhook_url, slack_message):
                logger.info("Low utilization alert sent via Slack")
    except Exception as e:
        logger.warning(f"Slack notification error (non-fatal): {e}")

    try:
        teams_webhook_url = config.get("teams_webhook_url")
        if teams_webhook_url:
            from shared import notifications

            teams_message = notifications.format_teams_message(subject, body_lines)
            if notifications.send_teams_notification(teams_webhook_url, teams_message):
                logger.info("Low utilization alert sent via Teams")
    except Exception as e:
        logger.warning(f"Teams notification error (non-fatal): {e}")


def send_report_email(
    sns_client: SNSClient,
    config: dict[str, Any],
    s3_object_key: str,
    coverage_data: dict[str, Any],
    savings_data: dict[str, Any],
    storage_adapter: Any = None,
) -> None:
    """
    Send email notification with S3 report link and summary.

    Args:
        sns_client: Boto3 SNS client
        config: Configuration dictionary
        s3_object_key: S3 object key of uploaded report
        coverage_data: Coverage data from SpendingAnalyzer
        savings_data: Savings Plans summary data
        storage_adapter: StorageAdapter instance for generating pre-signed URLs (optional)
    """
    logger.info("Sending report email notification")

    bucket_name = config["reports_bucket"]
    s3_url = _generate_s3_url(storage_adapter, s3_object_key, bucket_name)
    s3_console_url = (
        f"https://s3.console.aws.amazon.com/s3/object/{bucket_name}?prefix={s3_object_key}"
    )

    actual_savings = savings_data["actual_savings"]
    overall_coverage = _calculate_overall_coverage(coverage_data)

    net_savings_hourly = actual_savings["net_savings_hourly"]
    savings_percentage = actual_savings["savings_percentage"]
    average_utilization = savings_data["average_utilization"]
    plans_count = savings_data["plans_count"]

    subject = f"Savings Plans Report Available - {overall_coverage:.1f}% Coverage"
    report_date = datetime.now(UTC).strftime("%B %d, %Y")

    body_lines = [
        f"AWS Savings Plans Report - {report_date}",
        "=" * 60,
        "",
        "Your periodic Savings Plans coverage and savings report is ready.",
        "",
        "📊 KEY METRICS",
        "",
        f"  Hourly Savings .......... ${net_savings_hourly:.2f}",
        f"  Average Discount ........ {savings_percentage:.1f}%",
        f"  SP Coverage (min-hourly). {overall_coverage:.1f}%",
        f"  SP Utilization .......... {average_utilization:.1f}%",
        f"  Active Plans ............ {plans_count}",
        "",
        "-" * 60,
        "",
        "📄 VIEW FULL REPORT",
        "",
        "Click the link below to access your detailed report:",
        "(Link expires in 7 days)",
        "",
        s3_url,
        "",
        "-" * 60,
        "",
        "Alternative access:",
        f"  S3: s3://{bucket_name}/{s3_object_key}",
        f"  Console: {s3_console_url}",
        "",
        "This is an automated report from AWS Savings Plans Automation.",
    ]

    try:
        sns_client.publish(
            TopicArn=config["sns_topic_arn"],
            Subject=subject,
            Message="\n".join(body_lines),
        )
        logger.info("Report email sent via SNS")
    except Exception as e:
        logger.error(f"Failed to send report email: {e}")
        raise

    _send_slack_notification(config, subject, body_lines)
    _send_teams_notification(config, subject, body_lines)

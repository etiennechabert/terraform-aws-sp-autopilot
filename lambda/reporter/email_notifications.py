"""
Email notification module for Reporter Lambda.

Provides email formatting and sending functionality for Savings Plans reports.
"""

import logging
from datetime import UTC, datetime
from typing import Any

from botocore.exceptions import ClientError

from shared import notifications


# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def send_report_email(
    sns_client: Any,
    config: dict[str, Any],
    s3_object_key: str,
    coverage_summary: dict[str, Any],
    savings_summary: dict[str, Any],
) -> None:
    """
    Send email notification with S3 report link and summary.

    Args:
        sns_client: Boto3 SNS client
        config: Configuration dictionary with sns_topic_arn and reports_bucket
        s3_object_key: S3 object key of the uploaded report
        coverage_summary: Coverage summary metrics
        savings_summary: Savings data summary

    Raises:
        ClientError: If SNS publish fails
    """
    logger.info("Sending report email notification")

    # Format execution timestamp
    execution_time = datetime.now(UTC).isoformat()

    # Build S3 URL
    bucket_name = config["reports_bucket"]
    s3_url = f"https://{bucket_name}.s3.amazonaws.com/{s3_object_key}"
    s3_console_url = (
        f"https://s3.console.aws.amazon.com/s3/object/{bucket_name}?prefix={s3_object_key}"
    )

    # Extract summary metrics
    current_coverage = coverage_summary.get("current_coverage", 0.0)
    avg_coverage = coverage_summary.get("avg_coverage", 0.0)
    coverage_days = coverage_summary.get("coverage_days", 0)
    trend_direction = coverage_summary.get("trend_direction", "→")

    active_plans = savings_summary.get("plans_count", 0)
    total_commitment = savings_summary.get("total_commitment", 0.0)
    estimated_monthly_savings = savings_summary.get("estimated_monthly_savings", 0.0)
    average_utilization = savings_summary.get("average_utilization", 0.0)

    # Extract actual savings data
    actual_savings = savings_summary.get("actual_savings", {})
    actual_sp_cost = actual_savings.get("actual_sp_cost", 0.0)
    on_demand_equivalent_cost = actual_savings.get("on_demand_equivalent_cost", 0.0)
    net_savings = actual_savings.get("net_savings", 0.0)
    savings_percentage = actual_savings.get("savings_percentage", 0.0)
    breakdown_by_type = actual_savings.get("breakdown_by_type", {})

    # Build email subject
    subject = f"Savings Plans Report - {current_coverage:.1f}% Coverage, ${net_savings:,.0f}/mo Actual Savings"

    # Build email body
    body_lines = [
        "AWS Savings Plans - Coverage & Savings Report",
        "=" * 60,
        f"Report Generated: {execution_time}",
        f"Reporting Period: {coverage_days} days",
        "",
        "COVERAGE SUMMARY:",
        "-" * 60,
        f"Current Coverage: {current_coverage:.2f}%",
        f"Average Coverage ({coverage_days} days): {avg_coverage:.2f}%",
        f"Trend: {trend_direction}",
        "",
        "SAVINGS SUMMARY:",
        "-" * 60,
        f"Active Savings Plans: {active_plans}",
        f"Total Hourly Commitment: ${total_commitment:.4f}/hour (${total_commitment * 730:,.2f}/month)",
        f"Average Utilization (7 days): {average_utilization:.2f}%",
        f"Estimated Monthly Savings: ${estimated_monthly_savings:,.2f}",
        "",
        "ACTUAL SAVINGS SUMMARY (30 days):",
        "-" * 60,
        f"On-Demand Equivalent Cost: ${on_demand_equivalent_cost:,.2f}",
        f"Actual Savings Plans Cost: ${actual_sp_cost:,.2f}",
        f"Net Savings: ${net_savings:,.2f}",
        f"Savings Percentage: {savings_percentage:.2f}%",
    ]

    # Add breakdown by type if available
    if breakdown_by_type:
        body_lines.append("")
        body_lines.append("Breakdown by Plan Type:")
        for plan_type, breakdown in breakdown_by_type.items():
            plans_count = breakdown.get("plans_count", 0)
            total_commitment_type = breakdown.get("total_commitment", 0.0)
            body_lines.append(
                f"  {plan_type}: {plans_count} plan(s), ${total_commitment_type:.4f}/hr"
            )

    body_lines.extend(
        [
            "",
            "REPORT ACCESS:",
            "-" * 60,
            f"S3 Location: s3://{bucket_name}/{s3_object_key}",
            f"Direct Link: {s3_url}",
            f"Console Link: {s3_console_url}",
            "",
            "-" * 60,
            "This is an automated report from AWS Savings Plans Automation.",
        ]
    )

    # Publish to SNS
    message_body = "\n".join(body_lines)

    try:
        sns_client.publish(TopicArn=config["sns_topic_arn"], Subject=subject, Message=message_body)
        logger.info("Report email sent successfully")
    except ClientError as e:
        logger.error(f"Failed to send report email: {e!s}")
        raise

    # Notifications after SNS (errors should not break email sending)
    try:
        slack_webhook_url = config.get("slack_webhook_url")
        if slack_webhook_url:
            slack_message = notifications.format_slack_message(subject, body_lines, severity="info")
            if notifications.send_slack_notification(slack_webhook_url, slack_message):
                logger.info("Slack notification sent successfully")
            else:
                logger.warning("Slack notification failed")
    except Exception as e:
        logger.warning(f"Slack notification error (non-fatal): {e!s}")

    try:
        teams_webhook_url = config.get("teams_webhook_url")
        if teams_webhook_url:
            teams_message = notifications.format_teams_message(subject, body_lines)
            if notifications.send_teams_notification(teams_webhook_url, teams_message):
                logger.info("Teams notification sent successfully")
            else:
                logger.warning("Teams notification failed")
    except Exception as e:
        logger.warning(f"Teams notification error (non-fatal): {e!s}")

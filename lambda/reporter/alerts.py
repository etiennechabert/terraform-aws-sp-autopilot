"""
Email and webhook alert module for Reporter Lambda.

Provides alerting functionality for low Savings Plans utilization,
sending notifications via SNS, Slack, and Microsoft Teams.
"""

import logging
from typing import Any

from botocore.exceptions import ClientError

from shared import notifications


# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def check_and_alert_low_utilization(
    sns_client: Any, config: dict[str, Any], savings_data: dict[str, Any]
) -> None:
    """
    Check if Savings Plans utilization is below threshold and send alert if needed.

    Args:
        sns_client: Boto3 SNS client
        config: Configuration dictionary with threshold and notification settings
        savings_data: Savings Plans data including average_utilization

    Returns:
        None: Sends alert notifications if utilization is below threshold
    """
    # Get threshold from config
    threshold = config["low_utilization_threshold"]

    # Get average utilization from savings data
    average_utilization = savings_data.get("average_utilization", 0.0)

    # Get active plans count
    plans_count = savings_data.get("plans_count", 0)

    # Skip alert if no active plans
    if plans_count == 0:
        logger.info("No active Savings Plans - skipping low utilization check")
        return

    # Check if utilization is below threshold
    if average_utilization < threshold:
        logger.warning(
            f"Low utilization detected: {average_utilization:.2f}% (threshold: {threshold:.2f}%)"
        )

        # Build alert subject
        subject = (
            f"Low Savings Plans Utilization Alert: {average_utilization:.1f}% "
            f"(threshold: {threshold:.0f}%)"
        )

        # Build alert body
        body_lines = [
            "Savings Plans utilization has fallen below the configured threshold.",
            "",
            f"Current Utilization: {average_utilization:.2f}%",
            f"Alert Threshold: {threshold:.2f}%",
            f"Active Plans: {plans_count}",
            f"Total Commitment: ${savings_data.get('total_commitment', 0.0):.4f}/hour",
            "",
            "This may indicate:",
            "• Decreased compute usage requiring plan adjustment",
            "• Over-commitment relative to actual usage",
            "• Opportunity to optimize Savings Plans portfolio",
            "",
            "Review your Savings Plans inventory and usage patterns to optimize costs.",
        ]

        # Send SNS notification
        try:
            message_body = "\n".join(body_lines)
            sns_client.publish(
                TopicArn=config["sns_topic_arn"], Subject=subject, Message=message_body
            )
            logger.info("Low utilization alert sent via SNS")
        except ClientError as e:
            logger.error(f"Failed to send SNS alert: {e!s}")
            raise

        # Send Slack notification (non-fatal if it fails)
        try:
            slack_webhook_url = config.get("slack_webhook_url")
            if slack_webhook_url:
                slack_message = notifications.format_slack_message(
                    subject, body_lines, severity="warning"
                )
                if notifications.send_slack_notification(slack_webhook_url, slack_message):
                    logger.info("Low utilization alert sent via Slack")
                else:
                    logger.warning("Slack notification failed (non-fatal)")
        except Exception as e:
            logger.warning(f"Slack notification error (non-fatal): {e!s}")

        # Send Teams notification (non-fatal if it fails)
        try:
            teams_webhook_url = config.get("teams_webhook_url")
            if teams_webhook_url:
                teams_message = notifications.format_teams_message(subject, body_lines)
                if notifications.send_teams_notification(teams_webhook_url, teams_message):
                    logger.info("Low utilization alert sent via Teams")
                else:
                    logger.warning("Teams notification failed (non-fatal)")
        except Exception as e:
            logger.warning(f"Teams notification error (non-fatal): {e!s}")
    else:
        logger.info(
            f"Utilization {average_utilization:.2f}% is above threshold {threshold:.2f}% - no alert needed"
        )

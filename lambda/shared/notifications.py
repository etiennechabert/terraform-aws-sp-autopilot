"""
Notification module for sending Slack and Microsoft Teams webhook notifications.

Provides functions to send rich-formatted notifications to Slack and Teams channels
alongside existing SNS email notifications.

Severity Levels:
    The format_slack_message() function supports color-coded severity levels for
    visual distinction in Slack channels:

    - 'success' (Green #36a64f): For successful operations, completions
    - 'warning' (Orange #ff9900): For warnings, potential issues requiring attention
    - 'error' (Red #ff0000): For errors, failures, critical issues
    - 'info' (Blue #0078D4): For informational messages (default)

Example Usage:
    # Success notification
    msg = format_slack_message(
        "Savings Plan Purchase Complete",
        ["Account: 123456789012", "Savings: $1,234.56/month"],
        severity='success'
    )

    # Warning notification
    msg = format_slack_message(
        "Low Utilization Detected",
        ["Current utilization: 45%", "Threshold: 70%"],
        severity='warning'
    )

    # Error notification
    msg = format_slack_message(
        "Purchase Failed",
        ["Error: Insufficient permissions", "Account: 123456789012"],
        severity='error'
    )

    # Info notification (default)
    msg = format_slack_message(
        "Analysis Started",
        ["Accounts: 5", "Estimated time: 10 minutes"]
    )
"""

import json
import logging
from typing import Any

import urllib3


# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize connection pool for HTTP requests with keep-alive
# This reuses connections for better performance when sending multiple notifications
http = urllib3.PoolManager(
    num_pools=1,
    maxsize=2,
    timeout=urllib3.Timeout(connect=5.0, read=10.0),
)


def format_slack_message(
    subject: str, body_lines: list[str], severity: str = "info"
) -> dict[str, Any]:
    """
    Format message for Slack using Block Kit format with color-coded attachments.

    Creates a Slack message with a colored sidebar and emoji indicator based on the
    severity level. The color appears as a vertical bar on the left side of the message
    in Slack, and the emoji is prepended to the subject line for quick visual scanning.

    Args:
        subject: Message subject/title
        body_lines: List of message body lines to include in the message
        severity: Notification severity level. Must be one of:
            - 'success': Green (#36a64f) - use for successful operations
            - 'warning': Orange (#ff9900) - use for warnings/alerts
            - 'error': Red (#ff0000) - use for errors/failures
            - 'info': Blue (#0078D4) - use for informational messages
            Default: 'info' (also used if an invalid severity is provided)

    Returns:
        dict: Slack Block Kit formatted message with color-coded attachment

    Examples:
        >>> # Successful purchase notification
        >>> msg = format_slack_message(
        ...     "Savings Plan Purchase Complete",
        ...     ["Account: 123456789012", "Amount: $5,000", "Term: 1 year"],
        ...     severity='success'
        ... )

        >>> # Warning for low utilization
        >>> msg = format_slack_message(
        ...     "Low Utilization Alert",
        ...     ["Account: 123456789012", "Current: 45%", "Expected: >70%"],
        ...     severity='warning'
        ... )

        >>> # Error notification
        >>> msg = format_slack_message(
        ...     "Purchase Failed",
        ...     ["Error: Insufficient permissions", "Account: 123456789012"],
        ...     severity='error'
        ... )

        >>> # Info message (default severity)
        >>> msg = format_slack_message(
        ...     "Analysis Running",
        ...     ["Processing 5 accounts", "Estimated completion: 10 minutes"]
        ... )

    Note:
        The function maintains backward compatibility - calls without the severity
        parameter will default to 'info' severity with blue color.
    """
    # Map severity to color codes and emoji indicators
    severity_config = {
        "success": {"color": "#36a64f", "emoji": "✅"},  # Green
        "warning": {"color": "#ff9900", "emoji": "⚠️"},  # Orange
        "error": {"color": "#ff0000", "emoji": "❌"},  # Red
        "info": {"color": "#0078D4", "emoji": "ℹ️"},  # Blue  # noqa: RUF001
    }

    # Get config for severity level, default to info if invalid
    config = severity_config.get(severity, severity_config["info"])

    # Prepend emoji to subject for quick visual scanning
    enhanced_subject = f"{config['emoji']} {subject}"

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": enhanced_subject, "emoji": True},
        },
        {"type": "section", "text": {"type": "mrkdwn", "text": "\n".join(body_lines)}},
    ]

    return {"attachments": [{"color": config["color"], "blocks": blocks}]}


def format_slack_message_with_actions(
    subject: str,
    body_lines: list[str],
    actions: list[dict[str, Any]],
    severity: str = "info",
) -> dict[str, Any]:
    """
    Format message for Slack with interactive action buttons.

    Extends format_slack_message() to include interactive buttons for user actions
    such as approving/rejecting purchases. Uses Slack Block Kit's actions block to
    add clickable buttons to the message.

    Args:
        subject: Message subject/title
        body_lines: List of message body lines to include in the message
        actions: List of action button configurations. Each action dict should contain:
            - 'text': Button label text (str)
            - 'action_id': Unique identifier for the action (str)
            - 'value': Optional value to pass with the action (str)
            - 'style': Optional button style - 'primary' (green) or 'danger' (red) (str)
        severity: Notification severity level ('success', 'warning', 'error', 'info')
            Default: 'info'

    Returns:
        dict: Slack Block Kit formatted message with color-coded attachment and action buttons

    Examples:
        >>> # Purchase approval notification with Approve/Reject buttons
        >>> actions = [
        ...     {
        ...         "text": "Approve",
        ...         "action_id": "approve_purchase",
        ...         "value": "purchase_123",
        ...         "style": "primary"
        ...     },
        ...     {
        ...         "text": "Reject",
        ...         "action_id": "reject_purchase",
        ...         "value": "purchase_123",
        ...         "style": "danger"
        ...     }
        ... ]
        >>> msg = format_slack_message_with_actions(
        ...     "Pending Savings Plan Purchase",
        ...     ["Account: 123456789012", "Amount: $5,000", "Term: 1 year"],
        ...     actions=actions,
        ...     severity='warning'
        ... )

    Note:
        This function requires a Slack app with interactive components enabled.
        Standard webhook URLs do not support interactive buttons - you must use
        a Slack app with proper OAuth scopes and a request URL configured for
        interactivity.
    """
    # Map severity to color codes and emoji indicators
    severity_config = {
        "success": {"color": "#36a64f", "emoji": "✅"},  # Green
        "warning": {"color": "#ff9900", "emoji": "⚠️"},  # Orange
        "error": {"color": "#ff0000", "emoji": "❌"},  # Red
        "info": {"color": "#0078D4", "emoji": "ℹ️"},  # Blue  # noqa: RUF001
    }

    # Get config for severity level, default to info if invalid
    config = severity_config.get(severity, severity_config["info"])

    # Prepend emoji to subject for quick visual scanning
    enhanced_subject = f"{config['emoji']} {subject}"

    # Build blocks with header and body
    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": enhanced_subject, "emoji": True},
        },
        {"type": "section", "text": {"type": "mrkdwn", "text": "\n".join(body_lines)}},
    ]

    # Add actions block if actions are provided
    if actions:
        action_elements = []
        for action in actions:
            button = {
                "type": "button",
                "text": {"type": "plain_text", "text": action["text"], "emoji": True},
                "action_id": action["action_id"],
            }

            # Add optional value field if provided
            if "value" in action:
                button["value"] = action["value"]

            # Add optional style field if provided (primary or danger)
            if "style" in action:
                button["style"] = action["style"]

            action_elements.append(button)

        # Add actions block to the message
        blocks.append({"type": "actions", "elements": action_elements})

    return {"attachments": [{"color": config["color"], "blocks": blocks}]}


def format_teams_message(subject: str, body_lines: list[str]) -> dict[str, Any]:
    """
    Format message for Microsoft Teams using MessageCard format.

    Args:
        subject: Message subject/title
        body_lines: List of message body lines

    Returns:
        dict: Teams MessageCard formatted message
    """
    # Convert body lines to Teams format with proper line breaks
    text_content = "<br>".join(body_lines)

    return {
        "@type": "MessageCard",
        "@context": "https://schema.org/extensions",
        "summary": subject,
        "themeColor": "0078D4",
        "title": subject,
        "text": text_content,
    }


def send_slack_notification(webhook_url: str, message_data: dict[str, Any]) -> bool:
    """
    Send notification to Slack via webhook.

    Args:
        webhook_url: Slack webhook URL
        message_data: Message data (from format_slack_message or custom dict)

    Returns:
        bool: True if successful, False if failed
    """
    if not webhook_url:
        logger.warning("Slack webhook URL not configured, skipping notification")
        return False

    try:
        # Prepare request data
        data = json.dumps(message_data).encode("utf-8")
        headers = {"Content-Type": "application/json"}

        # Send request using connection pool
        response = http.request("POST", webhook_url, body=data, headers=headers)

        if response.status == 200:
            logger.info("Slack notification sent successfully")
            return True
        logger.error(f"Slack notification failed with status {response.status}")
        return False

    except urllib3.exceptions.HTTPError as e:
        logger.error(f"Slack webhook HTTP error: {e!s}")
        return False
    except urllib3.exceptions.TimeoutError as e:
        logger.error(f"Slack webhook timeout error: {e!s}")
        return False
    except Exception as e:
        logger.error(f"Slack notification failed: {e!s}")
        return False


def send_teams_notification(webhook_url: str, message_data: dict[str, Any]) -> bool:
    """
    Send notification to Microsoft Teams via webhook.

    Args:
        webhook_url: Teams webhook URL
        message_data: Message data (from format_teams_message or custom dict)

    Returns:
        bool: True if successful, False if failed
    """
    if not webhook_url:
        logger.warning("Teams webhook URL not configured, skipping notification")
        return False

    try:
        # Prepare request data
        data = json.dumps(message_data).encode("utf-8")
        headers = {"Content-Type": "application/json"}

        # Send request using connection pool
        response = http.request("POST", webhook_url, body=data, headers=headers)

        if response.status == 200:
            logger.info("Teams notification sent successfully")
            return True
        logger.error(f"Teams notification failed with status {response.status}")
        return False

    except urllib3.exceptions.HTTPError as e:
        logger.error(f"Teams webhook HTTP error: {e!s}")
        return False
    except urllib3.exceptions.TimeoutError as e:
        logger.error(f"Teams webhook timeout error: {e!s}")
        return False
    except Exception as e:
        logger.error(f"Teams notification failed: {e!s}")
        return False

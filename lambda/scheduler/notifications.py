"""
Notification module for sending Slack and Microsoft Teams webhook notifications.

Provides functions to send rich-formatted notifications to Slack and Teams channels
alongside existing SNS email notifications.
"""

import json
import logging
from typing import Dict, List, Any, Optional
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def format_slack_message(subject: str, body_lines: List[str]) -> Dict[str, Any]:
    """
    Format message for Slack using Block Kit format.

    Args:
        subject: Message subject/title
        body_lines: List of message body lines

    Returns:
        dict: Slack Block Kit formatted message
    """
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": subject,
                "emoji": True
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "\n".join(body_lines)
            }
        }
    ]

    return {"blocks": blocks}


def format_teams_message(subject: str, body_lines: List[str]) -> Dict[str, Any]:
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
        "text": text_content
    }


def send_slack_notification(webhook_url: str, message_data: Dict[str, Any]) -> bool:
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
        # Prepare request
        data = json.dumps(message_data).encode('utf-8')
        request = Request(
            webhook_url,
            data=data,
            headers={'Content-Type': 'application/json'}
        )

        # Send request
        with urlopen(request, timeout=10) as response:
            if response.status == 200:
                logger.info("Slack notification sent successfully")
                return True
            else:
                logger.error(f"Slack notification failed with status {response.status}")
                return False

    except HTTPError as e:
        logger.error(f"Slack webhook HTTP error: {e.code} - {e.reason}")
        return False
    except URLError as e:
        logger.error(f"Slack webhook URL error: {str(e.reason)}")
        return False
    except Exception as e:
        logger.error(f"Slack notification failed: {str(e)}")
        return False


def send_teams_notification(webhook_url: str, message_data: Dict[str, Any]) -> bool:
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
        # Prepare request
        data = json.dumps(message_data).encode('utf-8')
        request = Request(
            webhook_url,
            data=data,
            headers={'Content-Type': 'application/json'}
        )

        # Send request
        with urlopen(request, timeout=10) as response:
            if response.status == 200:
                logger.info("Teams notification sent successfully")
                return True
            else:
                logger.error(f"Teams notification failed with status {response.status}")
                return False

    except HTTPError as e:
        logger.error(f"Teams webhook HTTP error: {e.code} - {e.reason}")
        return False
    except URLError as e:
        logger.error(f"Teams webhook URL error: {str(e.reason)}")
        return False
    except Exception as e:
        logger.error(f"Teams notification failed: {str(e)}")
        return False

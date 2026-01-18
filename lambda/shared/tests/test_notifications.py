"""
Comprehensive unit tests for notifications.py.

Tests cover all notification functions with edge cases to achieve >= 80% coverage.
Tests focus on urllib3-based implementations with mocked HTTP connections.
"""

import json
import os
import sys
from unittest.mock import MagicMock, Mock, patch

import pytest
import urllib3


# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from shared import notifications


# ============================================================================
# format_slack_message Tests
# ============================================================================


def test_format_slack_message_success_severity():
    """Test Slack message formatting with success severity."""
    result = notifications.format_slack_message(
        "Test Success", ["Line 1", "Line 2"], severity="success"
    )

    assert "attachments" in result
    assert len(result["attachments"]) == 1
    attachment = result["attachments"][0]

    # Check color is green for success
    assert attachment["color"] == "#36a64f"

    # Check blocks structure
    assert "blocks" in attachment
    assert len(attachment["blocks"]) == 2

    # Check header block with emoji
    header_block = attachment["blocks"][0]
    assert header_block["type"] == "header"
    assert header_block["text"]["type"] == "plain_text"
    assert "✅" in header_block["text"]["text"]
    assert "Test Success" in header_block["text"]["text"]

    # Check section block with body lines
    section_block = attachment["blocks"][1]
    assert section_block["type"] == "section"
    assert section_block["text"]["type"] == "mrkdwn"
    assert "Line 1\nLine 2" == section_block["text"]["text"]


def test_format_slack_message_warning_severity():
    """Test Slack message formatting with warning severity."""
    result = notifications.format_slack_message(
        "Test Warning", ["Warning details"], severity="warning"
    )

    attachment = result["attachments"][0]

    # Check color is orange for warning
    assert attachment["color"] == "#ff9900"

    # Check emoji is warning
    header_block = attachment["blocks"][0]
    assert "⚠️" in header_block["text"]["text"]
    assert "Test Warning" in header_block["text"]["text"]


def test_format_slack_message_error_severity():
    """Test Slack message formatting with error severity."""
    result = notifications.format_slack_message(
        "Test Error", ["Error details", "Stack trace"], severity="error"
    )

    attachment = result["attachments"][0]

    # Check color is red for error
    assert attachment["color"] == "#ff0000"

    # Check emoji is error
    header_block = attachment["blocks"][0]
    assert "❌" in header_block["text"]["text"]
    assert "Test Error" in header_block["text"]["text"]


def test_format_slack_message_info_severity():
    """Test Slack message formatting with info severity."""
    result = notifications.format_slack_message(
        "Test Info", ["Info line 1", "Info line 2"], severity="info"
    )

    attachment = result["attachments"][0]

    # Check color is blue for info
    assert attachment["color"] == "#0078D4"

    # Check emoji is info
    header_block = attachment["blocks"][0]
    assert "ℹ️" in header_block["text"]["text"]
    assert "Test Info" in header_block["text"]["text"]


def test_format_slack_message_default_severity():
    """Test Slack message formatting with default severity (no parameter)."""
    result = notifications.format_slack_message("Test Default", ["Body line"])

    attachment = result["attachments"][0]

    # Default should be info (blue)
    assert attachment["color"] == "#0078D4"

    # Default emoji should be info
    header_block = attachment["blocks"][0]
    assert "ℹ️" in header_block["text"]["text"]


def test_format_slack_message_invalid_severity():
    """Test Slack message formatting with invalid severity defaults to info."""
    result = notifications.format_slack_message(
        "Test Invalid", ["Body"], severity="invalid_severity"
    )

    attachment = result["attachments"][0]

    # Invalid severity should default to info (blue)
    assert attachment["color"] == "#0078D4"

    # Should use info emoji
    header_block = attachment["blocks"][0]
    assert "ℹ️" in header_block["text"]["text"]


def test_format_slack_message_empty_body():
    """Test Slack message formatting with empty body lines."""
    result = notifications.format_slack_message("Test Empty", [], severity="info")

    attachment = result["attachments"][0]
    section_block = attachment["blocks"][1]

    # Empty body should result in empty text
    assert section_block["text"]["text"] == ""


def test_format_slack_message_single_body_line():
    """Test Slack message formatting with single body line."""
    result = notifications.format_slack_message("Test Single", ["Single line"])

    attachment = result["attachments"][0]
    section_block = attachment["blocks"][1]

    # Single line should not have newline
    assert section_block["text"]["text"] == "Single line"


def test_format_slack_message_multiple_body_lines():
    """Test Slack message formatting with multiple body lines."""
    body_lines = ["Line 1", "Line 2", "Line 3", "Line 4"]
    result = notifications.format_slack_message("Test Multiple", body_lines)

    attachment = result["attachments"][0]
    section_block = attachment["blocks"][1]

    # Lines should be joined with newlines
    assert section_block["text"]["text"] == "Line 1\nLine 2\nLine 3\nLine 4"


# ============================================================================
# format_teams_message Tests
# ============================================================================


def test_format_teams_message_basic():
    """Test Teams message formatting with basic content."""
    result = notifications.format_teams_message("Test Subject", ["Line 1", "Line 2"])

    assert result["@type"] == "MessageCard"
    assert result["@context"] == "https://schema.org/extensions"
    assert result["summary"] == "Test Subject"
    assert result["themeColor"] == "0078D4"
    assert result["title"] == "Test Subject"
    assert result["text"] == "Line 1<br>Line 2"


def test_format_teams_message_empty_body():
    """Test Teams message formatting with empty body lines."""
    result = notifications.format_teams_message("Empty Body", [])

    # Empty body should result in empty text
    assert result["text"] == ""
    assert result["title"] == "Empty Body"


def test_format_teams_message_single_line():
    """Test Teams message formatting with single body line."""
    result = notifications.format_teams_message("Single Line", ["One line only"])

    # Single line should not have <br>
    assert result["text"] == "One line only"


def test_format_teams_message_multiple_lines():
    """Test Teams message formatting with multiple body lines."""
    body_lines = ["Line 1", "Line 2", "Line 3"]
    result = notifications.format_teams_message("Multiple Lines", body_lines)

    # Lines should be joined with <br>
    assert result["text"] == "Line 1<br>Line 2<br>Line 3"


def test_format_teams_message_special_characters():
    """Test Teams message formatting with special characters in body."""
    body_lines = ["Line with <html>", "Line with & ampersand", "Line with 'quotes'"]
    result = notifications.format_teams_message("Special Chars", body_lines)

    # Special characters should be preserved (Teams handles escaping)
    assert "Line with <html>" in result["text"]
    assert "Line with & ampersand" in result["text"]
    assert "Line with 'quotes'" in result["text"]


# ============================================================================
# send_slack_notification Tests
# ============================================================================


@patch("shared.notifications.http")
def test_send_slack_notification_success(mock_http):
    """Test successful Slack notification send."""
    # Mock successful response
    mock_response = Mock()
    mock_response.status = 200
    mock_http.request.return_value = mock_response

    webhook_url = "https://hooks.slack.com/services/TEST/WEBHOOK"
    message_data = {"test": "data"}

    result = notifications.send_slack_notification(webhook_url, message_data)

    assert result is True

    # Verify request was called correctly
    mock_http.request.assert_called_once()
    call_args = mock_http.request.call_args

    assert call_args[0][0] == "POST"
    assert call_args[0][1] == webhook_url
    assert call_args[1]["headers"] == {"Content-Type": "application/json"}
    assert call_args[1]["body"] == json.dumps(message_data).encode("utf-8")


@patch("shared.notifications.http")
def test_send_slack_notification_failure_status(mock_http):
    """Test Slack notification with non-200 status code."""
    # Mock failed response
    mock_response = Mock()
    mock_response.status = 400
    mock_http.request.return_value = mock_response

    webhook_url = "https://hooks.slack.com/services/TEST/WEBHOOK"
    message_data = {"test": "data"}

    result = notifications.send_slack_notification(webhook_url, message_data)

    assert result is False
    mock_http.request.assert_called_once()


@patch("shared.notifications.http")
def test_send_slack_notification_empty_webhook_url(mock_http):
    """Test Slack notification with empty webhook URL."""
    message_data = {"test": "data"}

    result = notifications.send_slack_notification("", message_data)

    assert result is False
    # Should not attempt to send request
    mock_http.request.assert_not_called()


@patch("shared.notifications.http")
def test_send_slack_notification_none_webhook_url(mock_http):
    """Test Slack notification with None webhook URL."""
    message_data = {"test": "data"}

    result = notifications.send_slack_notification(None, message_data)

    assert result is False
    # Should not attempt to send request
    mock_http.request.assert_not_called()


@patch("shared.notifications.http")
def test_send_slack_notification_http_error(mock_http):
    """Test Slack notification with HTTP error."""
    # Mock HTTP error
    mock_http.request.side_effect = urllib3.exceptions.HTTPError("HTTP error occurred")

    webhook_url = "https://hooks.slack.com/services/TEST/WEBHOOK"
    message_data = {"test": "data"}

    result = notifications.send_slack_notification(webhook_url, message_data)

    assert result is False


@patch("shared.notifications.http")
def test_send_slack_notification_timeout_error(mock_http):
    """Test Slack notification with timeout error."""
    # Mock timeout error
    mock_http.request.side_effect = urllib3.exceptions.TimeoutError(
        None, None, "Request timeout"
    )

    webhook_url = "https://hooks.slack.com/services/TEST/WEBHOOK"
    message_data = {"test": "data"}

    result = notifications.send_slack_notification(webhook_url, message_data)

    assert result is False


@patch("shared.notifications.http")
def test_send_slack_notification_generic_exception(mock_http):
    """Test Slack notification with generic exception."""
    # Mock generic exception
    mock_http.request.side_effect = Exception("Unexpected error")

    webhook_url = "https://hooks.slack.com/services/TEST/WEBHOOK"
    message_data = {"test": "data"}

    result = notifications.send_slack_notification(webhook_url, message_data)

    assert result is False


@patch("shared.notifications.http")
def test_send_slack_notification_json_encoding(mock_http):
    """Test Slack notification properly encodes JSON."""
    mock_response = Mock()
    mock_response.status = 200
    mock_http.request.return_value = mock_response

    webhook_url = "https://hooks.slack.com/services/TEST/WEBHOOK"
    message_data = {"nested": {"data": [1, 2, 3]}, "unicode": "Hello 世界"}

    result = notifications.send_slack_notification(webhook_url, message_data)

    assert result is True

    # Verify JSON was properly encoded
    call_args = mock_http.request.call_args
    expected_body = json.dumps(message_data).encode("utf-8")
    assert call_args[1]["body"] == expected_body


# ============================================================================
# send_teams_notification Tests
# ============================================================================


@patch("shared.notifications.http")
def test_send_teams_notification_success(mock_http):
    """Test successful Teams notification send."""
    # Mock successful response
    mock_response = Mock()
    mock_response.status = 200
    mock_http.request.return_value = mock_response

    webhook_url = "https://outlook.office.com/webhook/TEST/WEBHOOK"
    message_data = {"test": "data"}

    result = notifications.send_teams_notification(webhook_url, message_data)

    assert result is True

    # Verify request was called correctly
    mock_http.request.assert_called_once()
    call_args = mock_http.request.call_args

    assert call_args[0][0] == "POST"
    assert call_args[0][1] == webhook_url
    assert call_args[1]["headers"] == {"Content-Type": "application/json"}
    assert call_args[1]["body"] == json.dumps(message_data).encode("utf-8")


@patch("shared.notifications.http")
def test_send_teams_notification_failure_status(mock_http):
    """Test Teams notification with non-200 status code."""
    # Mock failed response
    mock_response = Mock()
    mock_response.status = 500
    mock_http.request.return_value = mock_response

    webhook_url = "https://outlook.office.com/webhook/TEST/WEBHOOK"
    message_data = {"test": "data"}

    result = notifications.send_teams_notification(webhook_url, message_data)

    assert result is False
    mock_http.request.assert_called_once()


@patch("shared.notifications.http")
def test_send_teams_notification_empty_webhook_url(mock_http):
    """Test Teams notification with empty webhook URL."""
    message_data = {"test": "data"}

    result = notifications.send_teams_notification("", message_data)

    assert result is False
    # Should not attempt to send request
    mock_http.request.assert_not_called()


@patch("shared.notifications.http")
def test_send_teams_notification_none_webhook_url(mock_http):
    """Test Teams notification with None webhook URL."""
    message_data = {"test": "data"}

    result = notifications.send_teams_notification(None, message_data)

    assert result is False
    # Should not attempt to send request
    mock_http.request.assert_not_called()


@patch("shared.notifications.http")
def test_send_teams_notification_http_error(mock_http):
    """Test Teams notification with HTTP error."""
    # Mock HTTP error
    mock_http.request.side_effect = urllib3.exceptions.HTTPError("HTTP error occurred")

    webhook_url = "https://outlook.office.com/webhook/TEST/WEBHOOK"
    message_data = {"test": "data"}

    result = notifications.send_teams_notification(webhook_url, message_data)

    assert result is False


@patch("shared.notifications.http")
def test_send_teams_notification_timeout_error(mock_http):
    """Test Teams notification with timeout error."""
    # Mock timeout error
    mock_http.request.side_effect = urllib3.exceptions.TimeoutError(
        None, None, "Request timeout"
    )

    webhook_url = "https://outlook.office.com/webhook/TEST/WEBHOOK"
    message_data = {"test": "data"}

    result = notifications.send_teams_notification(webhook_url, message_data)

    assert result is False


@patch("shared.notifications.http")
def test_send_teams_notification_generic_exception(mock_http):
    """Test Teams notification with generic exception."""
    # Mock generic exception
    mock_http.request.side_effect = Exception("Unexpected error")

    webhook_url = "https://outlook.office.com/webhook/TEST/WEBHOOK"
    message_data = {"test": "data"}

    result = notifications.send_teams_notification(webhook_url, message_data)

    assert result is False


@patch("shared.notifications.http")
def test_send_teams_notification_json_encoding(mock_http):
    """Test Teams notification properly encodes JSON."""
    mock_response = Mock()
    mock_response.status = 200
    mock_http.request.return_value = mock_response

    webhook_url = "https://outlook.office.com/webhook/TEST/WEBHOOK"
    message_data = {
        "@type": "MessageCard",
        "title": "Test with unicode 世界",
        "text": "Body text",
    }

    result = notifications.send_teams_notification(webhook_url, message_data)

    assert result is True

    # Verify JSON was properly encoded
    call_args = mock_http.request.call_args
    expected_body = json.dumps(message_data).encode("utf-8")
    assert call_args[1]["body"] == expected_body


# ============================================================================
# Integration Tests - Combined formatting and sending
# ============================================================================


@patch("shared.notifications.http")
def test_slack_end_to_end_success_notification(mock_http):
    """Test end-to-end Slack notification with formatted message."""
    mock_response = Mock()
    mock_response.status = 200
    mock_http.request.return_value = mock_response

    # Format message
    message = notifications.format_slack_message(
        "Purchase Complete", ["Account: 123456", "Amount: $5000"], severity="success"
    )

    # Send notification
    result = notifications.send_slack_notification(
        "https://hooks.slack.com/test", message
    )

    assert result is True

    # Verify the formatted message structure was sent
    call_args = mock_http.request.call_args
    sent_data = json.loads(call_args[1]["body"].decode("utf-8"))

    assert "attachments" in sent_data
    assert sent_data["attachments"][0]["color"] == "#36a64f"  # Success green


@patch("shared.notifications.http")
def test_teams_end_to_end_notification(mock_http):
    """Test end-to-end Teams notification with formatted message."""
    mock_response = Mock()
    mock_response.status = 200
    mock_http.request.return_value = mock_response

    # Format message
    message = notifications.format_teams_message(
        "Analysis Complete", ["Processed: 10 accounts", "Duration: 5 minutes"]
    )

    # Send notification
    result = notifications.send_teams_notification(
        "https://outlook.office.com/webhook/test", message
    )

    assert result is True

    # Verify the formatted message structure was sent
    call_args = mock_http.request.call_args
    sent_data = json.loads(call_args[1]["body"].decode("utf-8"))

    assert sent_data["@type"] == "MessageCard"
    assert sent_data["title"] == "Analysis Complete"
    assert "Processed: 10 accounts<br>Duration: 5 minutes" == sent_data["text"]


@patch("shared.notifications.http")
def test_slack_end_to_end_error_notification(mock_http):
    """Test end-to-end Slack error notification."""
    mock_response = Mock()
    mock_response.status = 200
    mock_http.request.return_value = mock_response

    # Format error message
    message = notifications.format_slack_message(
        "Operation Failed",
        ["Error: Permission denied", "Account: 987654321"],
        severity="error",
    )

    # Send notification
    result = notifications.send_slack_notification(
        "https://hooks.slack.com/test", message
    )

    assert result is True

    # Verify error formatting
    call_args = mock_http.request.call_args
    sent_data = json.loads(call_args[1]["body"].decode("utf-8"))

    assert sent_data["attachments"][0]["color"] == "#ff0000"  # Error red
    # Check for error emoji in subject
    header_text = sent_data["attachments"][0]["blocks"][0]["text"]["text"]
    assert "❌" in header_text

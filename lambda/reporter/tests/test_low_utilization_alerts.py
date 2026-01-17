"""
Tests for low utilization alert logic in Reporter Lambda.
Covers alert triggering, notification sending, and edge cases.
"""

import os
import sys


# Set up environment variables BEFORE importing handler
os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
os.environ["AWS_SECURITY_TOKEN"] = "testing"
os.environ["AWS_SESSION_TOKEN"] = "testing"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"

from unittest.mock import Mock, patch

import pytest
from botocore.exceptions import ClientError


# Add lambda directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import handler


@pytest.fixture
def mock_sns_client():
    """Mock SNS client for testing."""
    return Mock()


@pytest.fixture
def sample_config():
    """Sample configuration with default threshold."""
    return {
        "sns_topic_arn": "arn:aws:sns:us-east-1:123456789012:test-topic",
        "low_utilization_threshold": 70.0,
    }


@pytest.fixture
def sample_savings_data_low_utilization():
    """Sample savings data with low utilization (below threshold)."""
    return {
        "plans_count": 3,
        "total_commitment": 15.50,
        "average_utilization": 65.0,
        "estimated_monthly_savings": 5000.00,
    }


@pytest.fixture
def sample_savings_data_high_utilization():
    """Sample savings data with normal utilization (above threshold)."""
    return {
        "plans_count": 3,
        "total_commitment": 15.50,
        "average_utilization": 85.0,
        "estimated_monthly_savings": 5000.00,
    }


def test_check_and_alert_low_utilization_triggers_alert(
    mock_sns_client, sample_config, sample_savings_data_low_utilization
):
    """Test that alert is triggered when utilization is below threshold."""
    handler.check_and_alert_low_utilization(
        mock_sns_client, sample_config, sample_savings_data_low_utilization
    )

    # Verify SNS publish was called
    assert mock_sns_client.publish.call_count == 1

    # Verify SNS call arguments
    call_args = mock_sns_client.publish.call_args
    assert call_args[1]["TopicArn"] == sample_config["sns_topic_arn"]
    assert "Low Savings Plans Utilization Alert" in call_args[1]["Subject"]
    assert "65.0%" in call_args[1]["Subject"]
    assert "70%" in call_args[1]["Subject"]
    assert "Current Utilization: 65.00%" in call_args[1]["Message"]
    assert "Alert Threshold: 70.00%" in call_args[1]["Message"]
    assert "Active Plans: 3" in call_args[1]["Message"]


def test_check_and_alert_no_alert_when_above_threshold(
    mock_sns_client, sample_config, sample_savings_data_high_utilization
):
    """Test that no alert is sent when utilization is above threshold."""
    handler.check_and_alert_low_utilization(
        mock_sns_client, sample_config, sample_savings_data_high_utilization
    )

    # Verify SNS publish was NOT called
    assert mock_sns_client.publish.call_count == 0


def test_check_and_alert_at_threshold_no_alert(mock_sns_client, sample_config):
    """Test that no alert is sent when utilization equals threshold."""
    savings_data = {
        "plans_count": 2,
        "total_commitment": 10.00,
        "average_utilization": 70.0,  # Exactly at threshold
        "estimated_monthly_savings": 3000.00,
    }

    handler.check_and_alert_low_utilization(mock_sns_client, sample_config, savings_data)

    # Verify SNS publish was NOT called (not below threshold)
    assert mock_sns_client.publish.call_count == 0


def test_check_and_alert_no_active_plans(mock_sns_client, sample_config):
    """Test that no alert is sent when there are no active plans."""
    savings_data = {
        "plans_count": 0,
        "total_commitment": 0.0,
        "average_utilization": 0.0,
        "estimated_monthly_savings": 0.0,
    }

    handler.check_and_alert_low_utilization(mock_sns_client, sample_config, savings_data)

    # Verify SNS publish was NOT called
    assert mock_sns_client.publish.call_count == 0


def test_check_and_alert_with_custom_threshold(
    mock_sns_client, sample_savings_data_high_utilization
):
    """Test alert with custom threshold value."""
    config = {
        "sns_topic_arn": "arn:aws:sns:us-east-1:123456789012:test-topic",
        "low_utilization_threshold": 90.0,  # Higher threshold
    }

    # Utilization is 85%, which is below 90% threshold
    handler.check_and_alert_low_utilization(
        mock_sns_client, config, sample_savings_data_high_utilization
    )

    # Verify SNS publish was called (85% < 90%)
    assert mock_sns_client.publish.call_count == 1

    # Verify threshold in message
    call_args = mock_sns_client.publish.call_args
    assert "90%" in call_args[1]["Subject"]
    assert "Alert Threshold: 90.00%" in call_args[1]["Message"]


def test_check_and_alert_default_threshold(mock_sns_client):
    """Test that default threshold is used when not specified in config."""
    config = {
        "sns_topic_arn": "arn:aws:sns:us-east-1:123456789012:test-topic",
        # No low_utilization_threshold specified
    }

    savings_data = {
        "plans_count": 2,
        "total_commitment": 8.00,
        "average_utilization": 65.0,  # Below default 70%
        "estimated_monthly_savings": 2000.00,
    }

    handler.check_and_alert_low_utilization(mock_sns_client, config, savings_data)

    # Verify SNS publish was called with default threshold
    assert mock_sns_client.publish.call_count == 1

    call_args = mock_sns_client.publish.call_args
    assert "70%" in call_args[1]["Subject"]  # Default threshold


def test_check_and_alert_sns_failure(mock_sns_client, sample_config, sample_savings_data_low_utilization):
    """Test that SNS failure raises an exception."""
    # Mock SNS to raise ClientError
    mock_sns_client.publish.side_effect = ClientError(
        {"Error": {"Code": "InvalidParameter", "Message": "Invalid topic ARN"}},
        "Publish",
    )

    # Verify exception is raised
    with pytest.raises(ClientError):
        handler.check_and_alert_low_utilization(
            mock_sns_client, sample_config, sample_savings_data_low_utilization
        )


def test_check_and_alert_with_slack_notification(
    mock_sns_client, sample_savings_data_low_utilization
):
    """Test that Slack notification is sent when webhook URL is configured."""
    config = {
        "sns_topic_arn": "arn:aws:sns:us-east-1:123456789012:test-topic",
        "low_utilization_threshold": 70.0,
        "slack_webhook_url": "https://hooks.slack.com/services/TEST/WEBHOOK/URL",
    }

    with (
        patch("shared.notifications.format_slack_message") as mock_format_slack,
        patch("shared.notifications.send_slack_notification") as mock_send_slack,
    ):
        mock_format_slack.return_value = {"text": "Test Slack message"}
        mock_send_slack.return_value = True

        handler.check_and_alert_low_utilization(
            mock_sns_client, config, sample_savings_data_low_utilization
        )

        # Verify Slack notification was attempted
        assert mock_format_slack.call_count == 1
        assert mock_send_slack.call_count == 1

        # Verify Slack message format
        format_call_args = mock_format_slack.call_args
        assert "Low Savings Plans Utilization Alert" in format_call_args[0][0]
        assert format_call_args[1]["severity"] == "warning"

        # Verify Slack send call
        send_call_args = mock_send_slack.call_args
        assert send_call_args[0][0] == "https://hooks.slack.com/services/TEST/WEBHOOK/URL"


def test_check_and_alert_with_teams_notification(
    mock_sns_client, sample_savings_data_low_utilization
):
    """Test that Teams notification is sent when webhook URL is configured."""
    config = {
        "sns_topic_arn": "arn:aws:sns:us-east-1:123456789012:test-topic",
        "low_utilization_threshold": 70.0,
        "teams_webhook_url": "https://outlook.office.com/webhook/TEST/WEBHOOK/URL",
    }

    with (
        patch("shared.notifications.format_teams_message") as mock_format_teams,
        patch("shared.notifications.send_teams_notification") as mock_send_teams,
    ):
        mock_format_teams.return_value = {"text": "Test Teams message"}
        mock_send_teams.return_value = True

        handler.check_and_alert_low_utilization(
            mock_sns_client, config, sample_savings_data_low_utilization
        )

        # Verify Teams notification was attempted
        assert mock_format_teams.call_count == 1
        assert mock_send_teams.call_count == 1

        # Verify Teams message format
        format_call_args = mock_format_teams.call_args
        assert "Low Savings Plans Utilization Alert" in format_call_args[0][0]

        # Verify Teams send call
        send_call_args = mock_send_teams.call_args
        assert send_call_args[0][0] == "https://outlook.office.com/webhook/TEST/WEBHOOK/URL"


def test_check_and_alert_slack_failure_non_fatal(
    mock_sns_client, sample_savings_data_low_utilization
):
    """Test that Slack notification failure does not break the function."""
    config = {
        "sns_topic_arn": "arn:aws:sns:us-east-1:123456789012:test-topic",
        "low_utilization_threshold": 70.0,
        "slack_webhook_url": "https://hooks.slack.com/services/TEST/WEBHOOK/URL",
    }

    with (
        patch("shared.notifications.format_slack_message") as mock_format_slack,
        patch("shared.notifications.send_slack_notification") as mock_send_slack,
    ):
        mock_format_slack.return_value = {"text": "Test Slack message"}
        mock_send_slack.return_value = False  # Slack send fails

        # Function should complete without raising exception
        handler.check_and_alert_low_utilization(
            mock_sns_client, config, sample_savings_data_low_utilization
        )

        # SNS should still have been called
        assert mock_sns_client.publish.call_count == 1


def test_check_and_alert_teams_failure_non_fatal(
    mock_sns_client, sample_savings_data_low_utilization
):
    """Test that Teams notification failure does not break the function."""
    config = {
        "sns_topic_arn": "arn:aws:sns:us-east-1:123456789012:test-topic",
        "low_utilization_threshold": 70.0,
        "teams_webhook_url": "https://outlook.office.com/webhook/TEST/WEBHOOK/URL",
    }

    with (
        patch("shared.notifications.format_teams_message") as mock_format_teams,
        patch("shared.notifications.send_teams_notification") as mock_send_teams,
    ):
        mock_format_teams.return_value = {"text": "Test Teams message"}
        mock_send_teams.return_value = False  # Teams send fails

        # Function should complete without raising exception
        handler.check_and_alert_low_utilization(
            mock_sns_client, config, sample_savings_data_low_utilization
        )

        # SNS should still have been called
        assert mock_sns_client.publish.call_count == 1


def test_check_and_alert_slack_exception_non_fatal(
    mock_sns_client, sample_savings_data_low_utilization
):
    """Test that Slack notification exception does not break the function."""
    config = {
        "sns_topic_arn": "arn:aws:sns:us-east-1:123456789012:test-topic",
        "low_utilization_threshold": 70.0,
        "slack_webhook_url": "https://hooks.slack.com/services/TEST/WEBHOOK/URL",
    }

    with patch("shared.notifications.format_slack_message") as mock_format_slack:
        mock_format_slack.side_effect = Exception("Slack formatting failed")

        # Function should complete without raising exception
        handler.check_and_alert_low_utilization(
            mock_sns_client, config, sample_savings_data_low_utilization
        )

        # SNS should still have been called
        assert mock_sns_client.publish.call_count == 1


def test_check_and_alert_teams_exception_non_fatal(
    mock_sns_client, sample_savings_data_low_utilization
):
    """Test that Teams notification exception does not break the function."""
    config = {
        "sns_topic_arn": "arn:aws:sns:us-east-1:123456789012:test-topic",
        "low_utilization_threshold": 70.0,
        "teams_webhook_url": "https://outlook.office.com/webhook/TEST/WEBHOOK/URL",
    }

    with patch("shared.notifications.format_teams_message") as mock_format_teams:
        mock_format_teams.side_effect = Exception("Teams formatting failed")

        # Function should complete without raising exception
        handler.check_and_alert_low_utilization(
            mock_sns_client, config, sample_savings_data_low_utilization
        )

        # SNS should still have been called
        assert mock_sns_client.publish.call_count == 1


def test_check_and_alert_message_content(
    mock_sns_client, sample_config, sample_savings_data_low_utilization
):
    """Test that alert message contains all required information."""
    handler.check_and_alert_low_utilization(
        mock_sns_client, sample_config, sample_savings_data_low_utilization
    )

    # Get the message body from SNS call
    call_args = mock_sns_client.publish.call_args
    message_body = call_args[1]["Message"]

    # Verify all required information is in message
    assert "Current Utilization: 65.00%" in message_body
    assert "Alert Threshold: 70.00%" in message_body
    assert "Active Plans: 3" in message_body
    assert "Total Commitment: $15.5000/hour" in message_body
    assert "Decreased compute usage requiring plan adjustment" in message_body
    assert "Over-commitment relative to actual usage" in message_body
    assert "Opportunity to optimize Savings Plans portfolio" in message_body


def test_check_and_alert_with_zero_utilization(mock_sns_client, sample_config):
    """Test alert with zero utilization."""
    savings_data = {
        "plans_count": 1,
        "total_commitment": 5.00,
        "average_utilization": 0.0,
        "estimated_monthly_savings": 0.0,
    }

    handler.check_and_alert_low_utilization(mock_sns_client, sample_config, savings_data)

    # Verify SNS publish was called (0% < 70%)
    assert mock_sns_client.publish.call_count == 1

    call_args = mock_sns_client.publish.call_args
    assert "0.0%" in call_args[1]["Subject"]
    assert "Current Utilization: 0.00%" in call_args[1]["Message"]


def test_check_and_alert_with_very_low_threshold(mock_sns_client):
    """Test alert with very low threshold (e.g., 10%)."""
    config = {
        "sns_topic_arn": "arn:aws:sns:us-east-1:123456789012:test-topic",
        "low_utilization_threshold": 10.0,
    }

    savings_data = {
        "plans_count": 2,
        "total_commitment": 8.00,
        "average_utilization": 5.0,  # Below 10%
        "estimated_monthly_savings": 1000.00,
    }

    handler.check_and_alert_low_utilization(mock_sns_client, config, savings_data)

    # Verify alert was sent
    assert mock_sns_client.publish.call_count == 1

    call_args = mock_sns_client.publish.call_args
    assert "5.0%" in call_args[1]["Subject"]
    assert "10%" in call_args[1]["Subject"]


def test_check_and_alert_with_both_slack_and_teams(
    mock_sns_client, sample_savings_data_low_utilization
):
    """Test that both Slack and Teams notifications are sent when configured."""
    config = {
        "sns_topic_arn": "arn:aws:sns:us-east-1:123456789012:test-topic",
        "low_utilization_threshold": 70.0,
        "slack_webhook_url": "https://hooks.slack.com/services/TEST/WEBHOOK/URL",
        "teams_webhook_url": "https://outlook.office.com/webhook/TEST/WEBHOOK/URL",
    }

    with (
        patch("shared.notifications.format_slack_message") as mock_format_slack,
        patch("shared.notifications.send_slack_notification") as mock_send_slack,
        patch("shared.notifications.format_teams_message") as mock_format_teams,
        patch("shared.notifications.send_teams_notification") as mock_send_teams,
    ):
        mock_format_slack.return_value = {"text": "Slack message"}
        mock_send_slack.return_value = True
        mock_format_teams.return_value = {"text": "Teams message"}
        mock_send_teams.return_value = True

        handler.check_and_alert_low_utilization(
            mock_sns_client, config, sample_savings_data_low_utilization
        )

        # Verify all notifications were sent
        assert mock_sns_client.publish.call_count == 1
        assert mock_format_slack.call_count == 1
        assert mock_send_slack.call_count == 1
        assert mock_format_teams.call_count == 1
        assert mock_send_teams.call_count == 1


def test_check_and_alert_missing_utilization_key(mock_sns_client, sample_config):
    """Test handling when average_utilization key is missing from savings_data."""
    savings_data = {
        "plans_count": 2,
        "total_commitment": 10.00,
        # average_utilization missing
        "estimated_monthly_savings": 3000.00,
    }

    handler.check_and_alert_low_utilization(mock_sns_client, sample_config, savings_data)

    # Should treat missing utilization as 0.0, which is below threshold
    assert mock_sns_client.publish.call_count == 1

    call_args = mock_sns_client.publish.call_args
    assert "0.00%" in call_args[1]["Message"]  # Default to 0.0


def test_check_and_alert_edge_case_just_below_threshold(mock_sns_client, sample_config):
    """Test alert when utilization is just below threshold (69.99%)."""
    savings_data = {
        "plans_count": 3,
        "total_commitment": 12.00,
        "average_utilization": 69.99,  # Just below 70%
        "estimated_monthly_savings": 4000.00,
    }

    handler.check_and_alert_low_utilization(mock_sns_client, sample_config, savings_data)

    # Verify alert was sent (69.99 < 70.0)
    assert mock_sns_client.publish.call_count == 1

    call_args = mock_sns_client.publish.call_args
    assert "69.99%" in call_args[1]["Message"]

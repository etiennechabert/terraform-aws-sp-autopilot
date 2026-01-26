"""Unit tests for alerts module helper functions."""

import sys
from unittest.mock import Mock, patch

import pytest


sys.path.insert(0, "../")

import alerts


@pytest.fixture
def mock_config():
    """Basic configuration for alert tests."""
    return {
        "sns_topic_arn": "arn:aws:sns:us-east-1:123456789012:test-topic",
        "slack_webhook_url": "https://hooks.slack.com/test",
        "teams_webhook_url": "https://hooks.teams.com/test",
        "low_utilization_threshold": 70.0,
    }


@pytest.fixture
def alert_data():
    """Sample alert data."""
    return {
        "subject": "Test Alert",
        "body_lines": ["Line 1", "Line 2", "Line 3"],
    }


def test_send_sns_alert_success(mock_config, alert_data):
    """Test successful SNS alert sending."""
    mock_sns = Mock()
    mock_sns.publish.return_value = {"MessageId": "test-id"}

    alerts._send_sns_alert(mock_sns, mock_config, alert_data["subject"], alert_data["body_lines"])

    mock_sns.publish.assert_called_once()
    call_args = mock_sns.publish.call_args[1]
    assert call_args["TopicArn"] == mock_config["sns_topic_arn"]
    assert call_args["Subject"] == alert_data["subject"]
    assert "Line 1" in call_args["Message"]


def test_send_sns_alert_failure(mock_config, alert_data):
    """Test SNS alert failure raises exception."""
    from botocore.exceptions import ClientError

    mock_sns = Mock()
    error = ClientError({"Error": {"Code": "AccessDenied"}}, "publish")
    mock_sns.publish.side_effect = error

    with pytest.raises(ClientError):
        alerts._send_sns_alert(
            mock_sns, mock_config, alert_data["subject"], alert_data["body_lines"]
        )


def test_send_slack_alert_success(mock_config, alert_data):
    """Test successful Slack alert sending."""
    mock_response = Mock()
    mock_response.status = 200

    with (
        patch("alerts.notifications.format_slack_message", return_value={"text": "test"}),
        patch("alerts.notifications.send_slack_notification", return_value=True),
    ):
        alerts._send_slack_alert(mock_config, alert_data["subject"], alert_data["body_lines"])


def test_send_slack_alert_no_webhook(alert_data):
    """Test Slack alert with no webhook URL configured."""
    config_no_webhook = {"slack_webhook_url": None}
    # Should return early without error
    alerts._send_slack_alert(config_no_webhook, alert_data["subject"], alert_data["body_lines"])


def test_send_slack_alert_failure(mock_config, alert_data):
    """Test Slack alert failure is handled gracefully."""
    with (
        patch("alerts.notifications.format_slack_message", return_value={"text": "test"}),
        patch(
            "alerts.notifications.send_slack_notification", side_effect=Exception("Network error")
        ),
    ):
        # Should not raise - failures are non-fatal
        alerts._send_slack_alert(mock_config, alert_data["subject"], alert_data["body_lines"])


def test_send_teams_alert_success(mock_config, alert_data):
    """Test successful Teams alert sending."""
    with (
        patch("alerts.notifications.format_teams_message", return_value={"text": "test"}),
        patch("alerts.notifications.send_teams_notification", return_value=True),
    ):
        alerts._send_teams_alert(mock_config, alert_data["subject"], alert_data["body_lines"])


def test_send_teams_alert_no_webhook(alert_data):
    """Test Teams alert with no webhook URL configured."""
    config_no_webhook = {"teams_webhook_url": None}
    # Should return early without error
    alerts._send_teams_alert(config_no_webhook, alert_data["subject"], alert_data["body_lines"])


def test_send_teams_alert_failure(mock_config, alert_data):
    """Test Teams alert failure is handled gracefully."""
    with (
        patch("alerts.notifications.format_teams_message", return_value={"text": "test"}),
        patch(
            "alerts.notifications.send_teams_notification", side_effect=Exception("Network error")
        ),
    ):
        # Should not raise - failures are non-fatal
        alerts._send_teams_alert(mock_config, alert_data["subject"], alert_data["body_lines"])


def test_check_and_alert_no_plans():
    """Test alert check with no active plans."""
    mock_sns = Mock()
    config = {"low_utilization_threshold": 70.0}
    savings_data = {"plans_count": 0, "average_utilization": 50.0}

    alerts.check_and_alert_low_utilization(mock_sns, config, savings_data)

    # SNS should not be called when no plans exist
    mock_sns.publish.assert_not_called()


def test_check_and_alert_above_threshold():
    """Test alert check with utilization above threshold."""
    mock_sns = Mock()
    config = {"low_utilization_threshold": 70.0}
    savings_data = {"plans_count": 5, "average_utilization": 85.0}

    alerts.check_and_alert_low_utilization(mock_sns, config, savings_data)

    # SNS should not be called when utilization is above threshold
    mock_sns.publish.assert_not_called()

"""
Tests for error handling and edge cases in Reporter Lambda.
Covers S3 errors, SNS errors, and email formatting edge cases.
"""

import os
import sys


# Set up environment variables BEFORE importing handler
os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
os.environ["AWS_SECURITY_TOKEN"] = "testing"
os.environ["AWS_SESSION_TOKEN"] = "testing"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["REPORTS_BUCKET"] = "test-bucket"
os.environ["SNS_TOPIC_ARN"] = "arn:aws:sns:us-east-1:123456789012:test-topic"

from unittest.mock import patch

import pytest
from botocore.exceptions import ClientError


# Add lambda directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import handler


def test_upload_report_to_s3_error():
    """Test upload_report_to_s3 with S3 error."""
    config = handler.load_configuration()

    with patch.object(handler.s3_client, "put_object") as mock_put:
        mock_put.side_effect = ClientError(
            {"Error": {"Code": "NoSuchBucket", "Message": "Bucket does not exist"}},
            "PutObject",
        )

        with pytest.raises(ClientError):
            handler.upload_report_to_s3(config, "<html>Test</html>", "html")


def test_send_report_email_error():
    """Test send_report_email with SNS error."""
    config = handler.load_configuration()

    with patch.object(handler.sns_client, "publish") as mock_publish:
        mock_publish.side_effect = ClientError(
            {"Error": {"Code": "InvalidParameter", "Message": "Invalid topic"}},
            "Publish",
        )

        coverage_summary = {"current": 75.0, "trend": "up"}
        savings_summary = {"total_commitment": 1000.0}

        with pytest.raises(ClientError):
            handler.send_report_email(config, "report.html", coverage_summary, savings_summary)


def test_send_report_email_with_breakdown():
    """Test send_report_email with savings breakdown by type."""
    config = handler.load_configuration()

    with patch.object(handler.sns_client, "publish") as mock_publish:
        mock_publish.return_value = {}

        coverage_summary = {"current": 75.0, "trend": "up"}
        savings_summary = {
            "total_commitment": 1000.0,
            "plans_count": 5,
            "actual_savings": {
                "breakdown_by_type": {
                    "ComputeSavingsPlans": {
                        "plans_count": 3,
                        "total_commitment": 750.0,
                    },
                    "DatabaseSavingsPlans": {
                        "plans_count": 2,
                        "total_commitment": 250.0,
                    },
                },
            },
        }

        handler.send_report_email(config, "report.html", coverage_summary, savings_summary)

        # Verify publish was called
        assert mock_publish.called
        call_args = mock_publish.call_args
        message = call_args[1]["Message"]

        # Verify breakdown is included in email
        assert "Breakdown by Plan Type" in message
        assert "ComputeSavingsPlans" in message
        assert "DatabaseSavingsPlans" in message


def test_send_report_email_with_slack_webhook():
    """Test send_report_email with Slack webhook configured."""
    config = handler.load_configuration()
    config["slack_webhook_url"] = "https://hooks.slack.com/test"

    with (
        patch.object(handler.sns_client, "publish") as mock_publish,
        patch("shared.notifications.send_slack_notification") as mock_slack,
    ):
        mock_publish.return_value = {}
        mock_slack.return_value = None

        coverage_summary = {"current": 75.0, "trend": "up"}
        savings_summary = {"total_commitment": 1000.0}

        handler.send_report_email(config, "report.html", coverage_summary, savings_summary)

        # Verify Slack notification was attempted
        assert mock_slack.called


def test_send_report_email_with_teams_webhook():
    """Test send_report_email with Teams webhook configured."""
    config = handler.load_configuration()
    config["teams_webhook_url"] = "https://outlook.office.com/webhook/test"

    with (
        patch.object(handler.sns_client, "publish") as mock_publish,
        patch("shared.notifications.send_teams_notification") as mock_teams,
    ):
        mock_publish.return_value = {}
        mock_teams.return_value = None

        coverage_summary = {"current": 75.0, "trend": "up"}
        savings_summary = {"total_commitment": 1000.0}

        handler.send_report_email(config, "report.html", coverage_summary, savings_summary)

        # Verify Teams notification was attempted
        assert mock_teams.called


def test_load_configuration():
    """Test configuration loading."""
    config = handler.load_configuration()

    assert "reports_bucket" in config
    assert "sns_topic_arn" in config
    assert config["reports_bucket"] == "test-bucket"


def test_upload_report_json_format():
    """Test uploading JSON report format."""
    config = handler.load_configuration()

    with patch.object(handler.s3_client, "put_object") as mock_put:
        mock_put.return_value = {}

        report_content = '{"report": "data"}'
        result = handler.upload_report_to_s3(config, report_content, "json")

        assert result.endswith(".json")
        mock_put.assert_called_once()

        # Verify content type
        call_args = mock_put.call_args
        assert call_args[1]["ContentType"] == "application/json"


def test_generate_html_report_with_no_plans():
    """Test HTML report generation with no active plans."""
    coverage_history = [
        {"date": "2026-01-14", "coverage_percentage": 0.0},
        {"date": "2026-01-15", "coverage_percentage": 0.0},
    ]

    savings_data = {
        "plans_count": 0,
        "total_commitment": 0.0,
        "estimated_monthly_savings": 0.0,
        "average_utilization": 0.0,
        "plans": [],
    }

    result = handler.generate_html_report(coverage_history, savings_data)

    # Should still generate valid HTML
    assert "<!DOCTYPE html>" in result
    assert "</html>" in result
    assert "0.0" in result or "No active" in result.lower()


def test_generate_json_report_with_no_plans():
    """Test JSON report generation with no active plans."""
    coverage_history = []
    savings_data = {
        "plans_count": 0,
        "total_commitment": 0.0,
    }

    result = handler.generate_json_report(coverage_history, savings_data)

    # Should still generate valid JSON
    assert "{" in result
    assert "}" in result
    assert "0" in result

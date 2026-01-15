"""
Essential integration tests for Reporter Lambda.
Focuses on core business logic and critical paths only.
"""

import json
import os
from datetime import datetime, timezone
from unittest.mock import MagicMock, Mock, patch

import pytest
from botocore.exceptions import ClientError

import handler


@pytest.fixture
def mock_env_vars(monkeypatch):
    """Set up required environment variables."""
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("REPORTS_BUCKET", "test-bucket")
    monkeypatch.setenv("SNS_TOPIC_ARN", "arn:aws:sns:us-east-1:123456789012:test-topic")
    monkeypatch.setenv("REPORT_FORMAT", "html")
    monkeypatch.setenv("EMAIL_REPORTS", "true")


def test_handler_success_with_email(mock_env_vars):
    """Test successful report generation and email notification."""
    with (
        patch("handler.get_coverage_history") as mock_coverage,
        patch("handler.get_savings_data") as mock_savings,
        patch("handler.generate_html_report") as mock_html,
        patch("handler.upload_report_to_s3") as mock_upload,
        patch("handler.send_report_email") as mock_email,
        patch("handler.initialize_clients") as mock_init,
    ):
        # Mock client initialization
        mock_init.return_value = {
            "ce": Mock(),
            "savingsplans": Mock(),
            "s3": Mock(),
            "sns": Mock(),
        }

        # Mock data collection
        mock_coverage.return_value = [
            {"timestamp": "2026-01-15", "coverage_percentage": 75.0}
        ]
        mock_savings.return_value = {
            "total_commitment": 1000.0,
            "plans_count": 2,
            "estimated_savings": 200.0,
        }
        mock_html.return_value = "<html>Report</html>"
        mock_upload.return_value = "report_2026-01-15.html"

        response = handler.handler({}, {})

        assert response["statusCode"] == 200
        assert "completed successfully" in response["body"]
        mock_email.assert_called_once()


def test_handler_success_without_email(mock_env_vars, monkeypatch):
    """Test successful report generation without email."""
    monkeypatch.setenv("EMAIL_REPORTS", "false")

    with (
        patch("handler.get_coverage_history") as mock_coverage,
        patch("handler.get_savings_data") as mock_savings,
        patch("handler.generate_html_report") as mock_html,
        patch("handler.upload_report_to_s3") as mock_upload,
        patch("handler.send_report_email") as mock_email,
        patch("handler.initialize_clients") as mock_init,
    ):
        mock_init.return_value = {
            "ce": Mock(),
            "savingsplans": Mock(),
            "s3": Mock(),
            "sns": Mock(),
        }
        mock_coverage.return_value = []
        mock_savings.return_value = {"total_commitment": 0, "plans_count": 0}
        mock_html.return_value = "<html>Empty Report</html>"
        mock_upload.return_value = "report_2026-01-15.html"

        response = handler.handler({}, {})

        assert response["statusCode"] == 200
        mock_email.assert_not_called()


def test_get_coverage_history_success():
    """Test successful coverage history retrieval."""
    with patch.object(handler.ce_client, "get_savings_plans_coverage") as mock_get:
        mock_get.return_value = {
            "SavingsPlansCoverages": [
                {
                    "TimePeriod": {"Start": "2026-01-10", "End": "2026-01-11"},
                    "Coverage": {
                        "CoveragePercentage": "75.5",
                        "CoverageHours": {
                            "OnDemandHours": "100",
                            "CoveredHours": "300",
                            "TotalRunningHours": "400",
                        },
                    },
                }
            ]
        }

        result = handler.get_coverage_history(lookback_days=2)

        assert len(result) == 1
        assert result[0]["coverage_percentage"] == 75.5
        assert result[0]["on_demand_hours"] == 100.0


def test_get_savings_data_with_active_plans():
    """Test savings data retrieval with active plans."""
    with (
        patch.object(handler.savingsplans_client, "describe_savings_plans") as mock_describe,
        patch.object(handler.ce_client, "get_savings_plans_utilization") as mock_util,
    ):
        mock_describe.return_value = {
            "savingsPlans": [
                {
                    "savingsPlanId": "sp-123",
                    "savingsPlanType": "Compute",
                    "commitment": "10.50",
                    "state": "active",
                }
            ]
        }
        mock_util.return_value = {
            "Total": {"Utilization": {"UtilizationPercentage": "85.5"}}
        }

        result = handler.get_savings_data()

        assert result["plans_count"] == 1
        assert result["total_commitment"] == 10.50


def test_upload_report_to_s3_success(mock_env_vars):
    """Test successful S3 upload."""
    config = handler.load_configuration()

    with patch.object(handler.s3_client, "put_object") as mock_put:
        mock_put.return_value = {}

        report_content = "<html>Test Report</html>"
        result = handler.upload_report_to_s3(config, report_content, "html")

        assert result.startswith("savings-plans-report_")
        assert result.endswith(".html")
        mock_put.assert_called_once()


def test_send_report_email_success(mock_env_vars):
    """Test successful email notification."""
    config = handler.load_configuration()

    with patch.object(handler.sns_client, "publish") as mock_publish:
        mock_publish.return_value = {}

        coverage_summary = {"current": 75.0, "trend": "up"}
        savings_summary = {"total_commitment": 1000.0}

        handler.send_report_email(
            config, "report_key.html", coverage_summary, savings_summary
        )

        mock_publish.assert_called_once()
        call_args = mock_publish.call_args[1]
        assert call_args["TopicArn"] == config["sns_topic_arn"]
        assert "Savings Plans Report" in call_args["Subject"]


def test_api_error_handling(mock_env_vars):
    """Test error handling when AWS API calls fail."""
    with (
        patch("handler.get_coverage_history") as mock_coverage,
        patch("handler.initialize_clients") as mock_init,
    ):
        mock_init.return_value = {
            "ce": Mock(),
            "savingsplans": Mock(),
            "s3": Mock(),
            "sns": Mock(),
        }

        # Simulate API error
        error_response = {"Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}}
        mock_coverage.side_effect = ClientError(error_response, "GetSavingsPlansCoverage")

        with pytest.raises(ClientError):
            handler.handler({}, {})

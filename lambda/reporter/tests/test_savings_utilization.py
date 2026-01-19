"""
Tests for savings and utilization data functions in Reporter Lambda.
Covers detailed utilization calculations and edge cases.
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


def test_get_savings_data_with_detailed_utilization(aws_mock_builder):
    """Test savings data with detailed utilization breakdown."""
    with (
        patch.object(handler.savingsplans_client, "describe_savings_plans") as mock_describe,
        patch.object(handler.ce_client, "get_savings_plans_utilization") as mock_util,
    ):
        # Use real AWS response structures
        mock_describe.return_value = aws_mock_builder.describe_savings_plans(plans_count=2)
        mock_util.return_value = aws_mock_builder.utilization(utilization_percentage=88.5, days=2)

        result = handler.get_savings_data()

        # Verify basic metrics
        assert result["plans_count"] == 2
        assert result["total_commitment"] > 0

        # Verify utilization calculation (should be average of daily values)
        assert "average_utilization" in result
        assert result["average_utilization"] > 0


def test_get_savings_data_no_utilization():
    """Test savings data when utilization data is empty."""
    with (
        patch.object(handler.savingsplans_client, "describe_savings_plans") as mock_describe,
        patch.object(handler.ce_client, "get_savings_plans_utilization") as mock_util,
    ):
        mock_describe.return_value = {
            "savingsPlans": [
                {
                    "savingsPlanId": "sp-new-123",
                    "savingsPlanType": "ComputeSavingsPlans",
                    "commitment": "8.00",
                    "state": "active",
                }
            ]
        }

        # Empty utilization response (newly created plan)
        mock_util.return_value = {"Total": {}, "SavingsPlansUtilizationsByTime": []}

        result = handler.get_savings_data()

        assert result["plans_count"] == 1
        assert result["total_commitment"] == 8.00
        assert result.get("average_utilization", 0.0) == 0.0


def test_get_savings_data_api_error():
    """Test savings data with API error."""
    with patch.object(handler.savingsplans_client, "describe_savings_plans") as mock_describe:
        mock_describe.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "Access denied"}},
            "DescribeSavingsPlans",
        )

        with pytest.raises(ClientError):
            handler.get_savings_data()


def test_get_coverage_history_with_multiple_days():
    """Test coverage history retrieval over multiple days."""
    mock_ce_client = Mock()

    # Mock response with coverage data for multiple days
    mock_ce_client.get_savings_plans_coverage.return_value = {
        "SavingsPlansCoverages": [
            {
                "TimePeriod": {"Start": "2026-01-10", "End": "2026-01-11"},
                "Coverage": {"CoveragePercentage": "65.5"},
            },
            {
                "TimePeriod": {"Start": "2026-01-11", "End": "2026-01-12"},
                "Coverage": {"CoveragePercentage": "67.2"},
            },
            {
                "TimePeriod": {"Start": "2026-01-12", "End": "2026-01-13"},
                "Coverage": {"CoveragePercentage": "68.8"},
            },
        ]
    }

    result = handler.get_coverage_history(mock_ce_client, lookback_days=3)

    assert len(result) == 3
    assert result[0]["coverage_percentage"] == 65.5
    assert result[1]["coverage_percentage"] == 67.2
    assert result[2]["coverage_percentage"] == 68.8


def test_get_coverage_history_empty():
    """Test coverage history with no data."""
    mock_ce_client = Mock()
    mock_ce_client.get_savings_plans_coverage.return_value = {"SavingsPlansCoverages": []}

    result = handler.get_coverage_history(mock_ce_client, lookback_days=30)

    assert result == []


def test_get_coverage_history_api_error():
    """Test coverage history with API error."""
    mock_ce_client = Mock()
    mock_ce_client.get_savings_plans_coverage.side_effect = ClientError(
        {"Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}},
        "GetSavingsPlansCoverage",
    )

    with pytest.raises(ClientError):
        handler.get_coverage_history(mock_ce_client, lookback_days=30)

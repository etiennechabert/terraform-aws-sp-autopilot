"""
Tests for report generation functions in Reporter Lambda.
Covers HTML and JSON report generation, and cost data fetching.
"""

import os
import sys


# Set up environment variables BEFORE importing handler
os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
os.environ["AWS_SECURITY_TOKEN"] = "testing"
os.environ["AWS_SESSION_TOKEN"] = "testing"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"

from unittest.mock import Mock

import pytest


# Add lambda directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import handler


@pytest.fixture
def sample_coverage_history():
    """Sample coverage history data."""
    return [
        {"date": "2026-01-10", "coverage_percentage": 65.5},
        {"date": "2026-01-11", "coverage_percentage": 67.2},
        {"date": "2026-01-12", "coverage_percentage": 68.8},
        {"date": "2026-01-13", "coverage_percentage": 70.1},
        {"date": "2026-01-14", "coverage_percentage": 72.3},
    ]


@pytest.fixture
def sample_savings_data():
    """Sample savings data."""
    return {
        "plans_count": 5,
        "total_commitment": 15.75,
        "estimated_monthly_savings": 8500.00,
        "average_utilization": 92.5,
        "plans": [
            {
                "savingsPlanId": "sp-12345",
                "savingsPlanType": "ComputeSavingsPlans",
                "commitment": "10.50",
                "state": "active",
                "start": "2025-01-01T00:00:00Z",
                "end": "2028-01-01T00:00:00Z",
            },
            {
                "savingsPlanId": "sp-67890",
                "savingsPlanType": "DatabaseSavingsPlans",
                "commitment": "5.25",
                "state": "active",
                "start": "2025-06-01T00:00:00Z",
                "end": "2028-06-01T00:00:00Z",
            },
        ],
        "actual_savings": {
            "actual_sp_cost": 10500.00,
            "on_demand_equivalent_cost": 19000.00,
            "net_savings": 8500.00,
            "savings_percentage": 44.74,
            "breakdown_by_type": {
                "ComputeSavingsPlans": {
                    "plans_count": 3,
                    "total_commitment": 10.50,
                },
                "DatabaseSavingsPlans": {
                    "plans_count": 2,
                    "total_commitment": 5.25,
                },
            },
        },
    }


def test_generate_html_report(sample_coverage_history, sample_savings_data):
    """Test HTML report generation."""
    result = handler.generate_html_report(sample_coverage_history, sample_savings_data)

    # Verify HTML structure
    assert result.startswith("<!DOCTYPE html>")
    assert "</html>" in result
    assert "Savings Plans Coverage & Savings Report" in result

    # Verify coverage summary is included
    assert "72.3" in result  # Current coverage

    # Verify savings data is included
    assert "15.75" in result  # Total commitment (hourly)

    # Verify HTML tags are present
    assert "<head>" in result
    assert "<body>" in result
    assert "</body>" in result


def test_generate_html_report_with_increasing_trend(sample_coverage_history, sample_savings_data):
    """Test HTML report with increasing coverage trend."""
    result = handler.generate_html_report(sample_coverage_history, sample_savings_data)

    # Coverage is increasing from 65.5 to 72.3, so trend should be upward
    assert "↑" in result or "trend" in result.lower()


def test_generate_html_report_with_empty_data():
    """Test HTML report with minimal/empty data."""
    result = handler.generate_html_report([], {"plans_count": 0, "total_commitment": 0.0})

    assert "<!DOCTYPE html>" in result
    assert "</html>" in result


def test_generate_json_report(sample_coverage_history, sample_savings_data):
    """Test JSON report generation."""
    result = handler.generate_json_report(sample_coverage_history, sample_savings_data)

    # Verify JSON structure
    assert "{" in result
    assert "}" in result
    assert "report_metadata" in result
    assert "coverage_summary" in result
    assert "savings_summary" in result
    assert "active_savings_plans" in result

    # Verify coverage data
    assert "72.3" in result  # Current coverage
    assert "68.78" in result  # Average coverage

    # Verify savings data
    assert "15.75" in result  # Hourly commitment


def test_generate_json_report_with_trend():
    """Test JSON report trend calculation."""
    coverage_data = [
        {"date": "2026-01-10", "coverage_percentage": 60.0},
        {"date": "2026-01-14", "coverage_percentage": 70.0},
    ]
    savings_data = {"plans_count": 2, "total_commitment": 5.0}

    result = handler.generate_json_report(coverage_data, savings_data)

    assert "increasing" in result  # Trend should be increasing


def test_generate_json_report_with_decreasing_trend():
    """Test JSON report with decreasing trend."""
    coverage_data = [
        {"date": "2026-01-10", "coverage_percentage": 70.0},
        {"date": "2026-01-14", "coverage_percentage": 60.0},
    ]
    savings_data = {"plans_count": 2, "total_commitment": 5.0}

    result = handler.generate_json_report(coverage_data, savings_data)

    assert "decreasing" in result


def test_get_actual_costs_success():
    """Test get_actual_cost_data with successful API response."""
    mock_ce_client = Mock()
    mock_ce_client.get_cost_and_usage.return_value = {
        "ResultsByTime": [
            {
                "TimePeriod": {"Start": "2026-01-10", "End": "2026-01-11"},
                "Groups": [
                    {
                        "Keys": ["Savings Plans"],
                        "Metrics": {"UnblendedCost": {"Amount": "100.50", "Unit": "USD"}},
                    },
                    {
                        "Keys": ["On Demand"],
                        "Metrics": {"UnblendedCost": {"Amount": "50.25", "Unit": "USD"}},
                    },
                ],
            },
            {
                "TimePeriod": {"Start": "2026-01-11", "End": "2026-01-12"},
                "Groups": [
                    {
                        "Keys": ["Savings Plans"],
                        "Metrics": {"UnblendedCost": {"Amount": "105.75", "Unit": "USD"}},
                    },
                    {
                        "Keys": ["On Demand"],
                        "Metrics": {"UnblendedCost": {"Amount": "55.50", "Unit": "USD"}},
                    },
                ],
            },
        ]
    }

    result = handler.get_actual_cost_data(mock_ce_client, lookback_days=2)

    # Verify result structure
    assert "cost_by_day" in result
    assert "total_savings_plans_cost" in result
    assert "total_on_demand_cost" in result
    assert "total_cost" in result

    # Verify calculations
    assert len(result["cost_by_day"]) == 2
    assert result["total_savings_plans_cost"] == 206.25  # 100.50 + 105.75
    assert result["total_on_demand_cost"] == 105.75  # 50.25 + 55.50
    assert result["total_cost"] == 312.0  # 206.25 + 105.75


def test_get_actual_costs_empty_response():
    """Test get_actual_cost_data with empty API response."""
    mock_ce_client = Mock()
    mock_ce_client.get_cost_and_usage.return_value = {"ResultsByTime": []}

    result = handler.get_actual_cost_data(mock_ce_client, lookback_days=30)

    # Should return empty data structure
    assert result["cost_by_day"] == []
    assert result["total_savings_plans_cost"] == 0.0
    assert result["total_on_demand_cost"] == 0.0
    assert result["total_cost"] == 0.0


def test_get_actual_costs_api_error():
    """Test get_actual_cost_data with API error."""
    from botocore.exceptions import ClientError

    mock_ce_client = Mock()
    mock_ce_client.get_cost_and_usage.side_effect = ClientError(
        {"Error": {"Code": "AccessDenied", "Message": "Access denied"}},
        "GetCostAndUsage",
    )

    with pytest.raises(ClientError):
        handler.get_actual_cost_data(mock_ce_client, lookback_days=30)

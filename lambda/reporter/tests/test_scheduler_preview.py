"""
Unit tests for scheduler_preview module.

Tests the scheduler preview calculation logic including:
- Scheduled purchase calculations for each strategy
- Coverage impact analysis
"""

import os
import sys
from unittest.mock import Mock

import pytest


# Set default environment variables before imports
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("REPORTS_BUCKET", "test-bucket")
os.environ.setdefault("SNS_TOPIC_ARN", "arn:aws:sns:us-east-1:123456789012:test-topic")
os.environ.setdefault("COVERAGE_TARGET_PERCENT", "90")

# Add lambda directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import scheduler_preview


@pytest.fixture
def sample_coverage_data():
    """Sample coverage data structure from SpendingAnalyzer."""
    return {
        "compute": {
            "summary": {
                "avg_coverage_total": 70.0,
                "avg_hourly_total": 1000.0,
                "avg_hourly_covered": 700.0,
                "avg_hourly_uncovered": 300.0,
            },
            "timeseries": [
                {"timestamp": "2026-01-20T00:00:00Z", "total": 950.0, "covered": 665.0},
                {"timestamp": "2026-01-20T01:00:00Z", "total": 1000.0, "covered": 700.0},
                {"timestamp": "2026-01-20T02:00:00Z", "total": 1050.0, "covered": 735.0},
            ],
        }
    }


@pytest.fixture
def sample_savings_data():
    """Sample savings data structure from get_savings_plans_summary."""
    return {
        "plans_count": 2,
        "actual_savings": {
            "net_savings": 10000.0,
            "breakdown_by_type": {
                "Compute": {
                    "savings_amount": 10000.0,
                    "savings_percentage": 60.0,
                }
            },
        },
    }


@pytest.fixture
def sample_config():
    """Sample reporter configuration."""
    return {
        "purchase_strategy_type": "fixed",
        "max_purchase_percent": 10.0,
        "min_purchase_percent": 1.0,
        "compute_sp_term": "THREE_YEAR",
        "compute_sp_payment_option": "ALL_UPFRONT",
        "coverage_target_percent": 90.0,
        "enable_compute_sp": True,
        "enable_database_sp": False,
        "enable_sagemaker_sp": False,
        "lookback_days": 7,
        "renewal_window_days": 7,
    }


@pytest.fixture
def mock_clients():
    """Mock AWS clients."""
    return {
        "ce": Mock(),
        "savingsplans": Mock(),
        "s3": Mock(),
        "sns": Mock(),
    }


def test_calculate_scheduler_preview_all_strategies(
    sample_config, mock_clients, sample_coverage_data, sample_savings_data, aws_mock_builder
):
    """Test scheduler preview calculates all three strategies."""
    # Setup AWS recommendation mock for follow_aws strategy
    mock_clients[
        "ce"
    ].get_savings_plans_purchase_recommendation.return_value = aws_mock_builder.recommendation(
        sp_type="compute", hourly_commitment=50.0
    )

    result = scheduler_preview.calculate_scheduler_preview(
        sample_config, mock_clients, sample_coverage_data, sample_savings_data
    )

    # Verify structure
    assert "configured_strategy" in result
    assert "strategies" in result
    assert "error" in result

    # Verify configured strategy
    assert result["configured_strategy"] == "fixed"
    assert result["error"] is None

    # Verify all three strategies are present
    assert "fixed" in result["strategies"]
    assert "dichotomy" in result["strategies"]
    assert "follow_aws" in result["strategies"]

    # Verify each strategy has the correct structure
    for strategy_name, strategy_data in result["strategies"].items():
        assert "purchases" in strategy_data
        assert "has_recommendations" in strategy_data
        assert "error" in strategy_data

        # Verify purchase structure if there are recommendations
        if strategy_data["has_recommendations"]:
            assert len(strategy_data["purchases"]) > 0
            purchase = strategy_data["purchases"][0]

            assert "sp_type" in purchase
            assert "hourly_commitment" in purchase
            assert "purchase_percent" in purchase
            assert "current_coverage" in purchase
            assert "projected_coverage" in purchase
            assert "payment_option" in purchase
            assert "term" in purchase


def test_calculate_scheduler_preview_configured_strategy_marked(
    sample_config, mock_clients, sample_coverage_data, sample_savings_data, aws_mock_builder
):
    """Test that the configured strategy is properly marked."""
    # Setup AWS recommendation mock
    mock_clients[
        "ce"
    ].get_savings_plans_purchase_recommendation.return_value = aws_mock_builder.recommendation(
        sp_type="compute", hourly_commitment=50.0
    )

    # Test with dichotomy as configured
    config = sample_config.copy()
    config["purchase_strategy_type"] = "dichotomy"
    config["dichotomy_initial_percent"] = 50.0

    result = scheduler_preview.calculate_scheduler_preview(
        config, mock_clients, sample_coverage_data, sample_savings_data
    )

    assert result["configured_strategy"] == "dichotomy"
    assert result["error"] is None

    # All strategies should still be calculated
    assert len(result["strategies"]) == 3


def test_calculate_scheduler_preview_no_recommendations(
    sample_config, mock_clients, sample_savings_data, aws_mock_builder
):
    """Test scheduler preview when already at target coverage."""
    # Setup AWS recommendation mock (empty - no recommendation)
    mock_clients[
        "ce"
    ].get_savings_plans_purchase_recommendation.return_value = aws_mock_builder.recommendation(
        sp_type="compute", empty=True
    )

    # Coverage already at 95% (above 90% target)
    coverage_data = {
        "compute": {
            "summary": {
                "avg_coverage_total": 95.0,
                "avg_hourly_total": 1000.0,
                "avg_hourly_covered": 950.0,
                "avg_hourly_uncovered": 50.0,
            },
            "timeseries": [],
        }
    }

    result = scheduler_preview.calculate_scheduler_preview(
        sample_config, mock_clients, coverage_data, sample_savings_data
    )

    assert result["configured_strategy"] == "fixed"
    assert result["error"] is None

    # Fixed and dichotomy should report no recommendations (coverage already met)
    assert result["strategies"]["fixed"]["has_recommendations"] is False
    assert result["strategies"]["dichotomy"]["has_recommendations"] is False

    # follow_aws also has no recommendations (AWS returned empty recommendation)
    assert result["strategies"]["follow_aws"]["has_recommendations"] is False


def test_calculate_scheduler_preview_strategy_error_handling(
    sample_config, mock_clients, sample_coverage_data, sample_savings_data
):
    """Test that individual strategy errors are handled gracefully."""
    # Don't setup AWS mock - follow_aws will fail but others should succeed
    result = scheduler_preview.calculate_scheduler_preview(
        sample_config, mock_clients, sample_coverage_data, sample_savings_data
    )

    assert result["error"] is None
    assert len(result["strategies"]) == 3

    # Fixed and dichotomy should work
    assert result["strategies"]["fixed"]["error"] is None
    assert result["strategies"]["dichotomy"]["error"] is None

    # follow_aws might have an error (no AWS mock), but should still be in result
    assert "follow_aws" in result["strategies"]

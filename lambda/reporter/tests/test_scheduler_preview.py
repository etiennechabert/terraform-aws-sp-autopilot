"""
Unit tests for scheduler_preview module.

Tests the scheduler preview calculation logic including:
- Scheduled purchase calculations for each target+split combination
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
    """Sample reporter configuration with new target+split strategy."""
    return {
        "target_strategy_type": "fixed",
        "split_strategy_type": "linear",
        "linear_step_percent": 10.0,
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
        "min_commitment_per_plan": 0.001,
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


def test_calculate_scheduler_preview_all_combinations(
    sample_config, mock_clients, sample_coverage_data, sample_savings_data, aws_mock_builder
):
    """Test scheduler preview calculates all strategy combinations."""
    mock_clients[
        "ce"
    ].get_savings_plans_purchase_recommendation.return_value = aws_mock_builder.recommendation(
        sp_type="compute", hourly_commitment=50.0
    )

    result = scheduler_preview.calculate_scheduler_preview(
        sample_config, mock_clients, sample_coverage_data
    )

    assert "configured_strategy" in result
    assert "strategies" in result
    assert "error" in result

    assert result["configured_strategy"] == "fixed+linear"
    assert result["error"] is None

    # Configured (fixed+linear) + 2 defaults (dynamic+dichotomy, aws+one_shot)
    # fixed+linear is both configured and a default, so 3 total
    assert "fixed+linear" in result["strategies"]
    assert "dynamic+dichotomy" in result["strategies"]
    assert "aws+one_shot" in result["strategies"]
    assert len(result["strategies"]) == 3

    for strategy_key, strategy_data in result["strategies"].items():
        assert "purchases" in strategy_data
        assert "has_recommendations" in strategy_data
        assert "error" in strategy_data
        assert "label" in strategy_data

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
    """Test that the configured strategy combination is properly identified."""
    mock_clients[
        "ce"
    ].get_savings_plans_purchase_recommendation.return_value = aws_mock_builder.recommendation(
        sp_type="compute", hourly_commitment=50.0
    )

    config = sample_config.copy()
    config["target_strategy_type"] = "fixed"
    config["split_strategy_type"] = "dichotomy"
    config["max_purchase_percent"] = 50.0

    result = scheduler_preview.calculate_scheduler_preview(
        config, mock_clients, sample_coverage_data
    )

    assert result["configured_strategy"] == "fixed+dichotomy"
    assert result["error"] is None
    # fixed+dichotomy (configured) + fixed+linear + dynamic+dichotomy + aws+one_shot = 4
    assert len(result["strategies"]) == 4


def test_calculate_scheduler_preview_no_recommendations(
    sample_config, mock_clients, sample_savings_data, aws_mock_builder
):
    """Test scheduler preview when already at target coverage."""
    mock_clients[
        "ce"
    ].get_savings_plans_purchase_recommendation.return_value = aws_mock_builder.recommendation(
        sp_type="compute", empty=True
    )

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
        sample_config, mock_clients, coverage_data
    )

    assert result["configured_strategy"] == "fixed+linear"
    assert result["error"] is None

    # Fixed+linear (configured) should report no recommendations (already at 95%)
    assert result["strategies"]["fixed+linear"]["has_recommendations"] is False


def test_calculate_scheduler_preview_strategy_error_handling(
    sample_config, mock_clients, sample_coverage_data, sample_savings_data
):
    """Test that individual strategy errors are handled gracefully."""
    result = scheduler_preview.calculate_scheduler_preview(
        sample_config, mock_clients, sample_coverage_data
    )

    assert result["error"] is None
    assert len(result["strategies"]) == 3

    # Configured strategy (fixed+linear) should work (no AWS call needed)
    assert result["strategies"]["fixed+linear"]["error"] is None


def test_coverage_is_min_hourly_based(sample_config, mock_clients, aws_mock_builder):
    """Coverage values should be expressed as percentage of min-hourly."""
    mock_clients[
        "ce"
    ].get_savings_plans_purchase_recommendation.return_value = aws_mock_builder.recommendation(
        sp_type="database", hourly_commitment=5.0
    )

    config = sample_config.copy()
    config["enable_database_sp"] = True
    config["database_sp_payment_option"] = "NO_UPFRONT"

    coverage_data = {
        "compute": {
            "summary": {
                "avg_coverage_total": 70.0,
                "avg_hourly_total": 100.0,
                "avg_hourly_covered": 70.0,
                "avg_hourly_uncovered": 30.0,
            },
            "timeseries": [
                {"timestamp": "2026-01-20T00:00:00Z", "total": 90.0, "covered": 63.0},
                {"timestamp": "2026-01-20T01:00:00Z", "total": 100.0, "covered": 70.0},
                {"timestamp": "2026-01-20T02:00:00Z", "total": 110.0, "covered": 77.0},
            ],
        },
        "database": {
            "summary": {
                "avg_coverage_total": 5.0,
                "avg_hourly_total": 30.0,
                "avg_hourly_covered": 1.5,
                "avg_hourly_uncovered": 28.5,
            },
            "timeseries": [
                {"timestamp": "2026-01-20T00:00:00Z", "total": 20.0, "covered": 1.5},
                {"timestamp": "2026-01-20T01:00:00Z", "total": 30.0, "covered": 1.5},
                {"timestamp": "2026-01-20T02:00:00Z", "total": 40.0, "covered": 1.5},
            ],
        },
    }

    savings_data = {
        "actual_savings": {
            "breakdown_by_type": {
                "Compute": {"total_commitment": 10.0, "savings_percentage": 30.0},
                "Database": {"total_commitment": 1.0, "savings_percentage": 35.0},
            },
        },
    }

    result = scheduler_preview.calculate_scheduler_preview(
        config, mock_clients, coverage_data, savings_data
    )

    # Find database purchase from fixed+linear strategy
    fixed_linear_purchases = result["strategies"]["fixed+linear"]["purchases"]
    db_purchase = next((p for p in fixed_linear_purchases if p["sp_type"] == "database"), None)
    assert db_purchase is not None

    assert db_purchase["current_coverage"] > 0
    # current_od_equiv = 1.0 / (1 - 0.35) ≈ 1.5385
    # min_hourly for database = 20.0
    # current_coverage = 1.5385 / 20.0 * 100 ≈ 7.69%
    assert db_purchase["current_coverage"] == pytest.approx(7.69, abs=0.1)

    # Step is 10% of min_hourly → added coverage should be 10%
    assert db_purchase["purchase_percent"] == pytest.approx(10.0, abs=0.1)

    # Math consistency: current + purchase = projected
    assert db_purchase["current_coverage"] + db_purchase["purchase_percent"] == pytest.approx(
        db_purchase["projected_coverage"], abs=0.01
    )

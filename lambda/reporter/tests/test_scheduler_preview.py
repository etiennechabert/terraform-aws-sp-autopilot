"""
Unit tests for scheduler_preview module.

Tests the scheduler preview calculation logic including:
- Scheduled purchase calculations for each strategy
- Optimal commitment calculations using knee-point algorithm
- Efficiency comparison and enrichment
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


def test_calculate_scheduler_preview_fixed_strategy(
    sample_config, mock_clients, sample_coverage_data, sample_savings_data
):
    """Test scheduler preview calculation with fixed strategy."""
    result = scheduler_preview.calculate_scheduler_preview(
        sample_config, mock_clients, sample_coverage_data, sample_savings_data
    )

    # Verify structure
    assert "strategy" in result
    assert "purchases" in result
    assert "has_recommendations" in result
    assert "error" in result

    # Verify strategy
    assert result["strategy"] == "fixed"
    assert result["error"] is None

    # Verify purchases
    if result["has_recommendations"]:
        assert len(result["purchases"]) > 0
        purchase = result["purchases"][0]

        # Verify purchase structure
        assert "sp_type" in purchase
        assert "scheduled" in purchase
        assert "optimal" in purchase
        assert "efficiency" in purchase

        # Verify scheduled data
        assert "hourly_commitment" in purchase["scheduled"]
        assert "purchase_percent" in purchase["scheduled"]
        assert "current_coverage" in purchase["scheduled"]
        assert "projected_coverage" in purchase["scheduled"]

        # Verify optimal data
        assert "hourly_commitment" in purchase["optimal"]
        assert "target_percentile" in purchase["optimal"]
        assert "discount_rate" in purchase["optimal"]

        # Verify efficiency data
        assert "ratio" in purchase["efficiency"]
        assert "status" in purchase["efficiency"]
        assert "message" in purchase["efficiency"]


def test_calculate_scheduler_preview_dichotomy_strategy(
    sample_config, mock_clients, sample_coverage_data, sample_savings_data
):
    """Test scheduler preview calculation with dichotomy strategy."""
    config = sample_config.copy()
    config["purchase_strategy_type"] = "dichotomy"
    config["dichotomy_initial_percent"] = 50.0

    result = scheduler_preview.calculate_scheduler_preview(
        config, mock_clients, sample_coverage_data, sample_savings_data
    )

    assert result["strategy"] == "dichotomy"
    assert result["error"] is None


def test_calculate_scheduler_preview_follow_aws_strategy(
    sample_config, mock_clients, sample_coverage_data, sample_savings_data, aws_mock_builder
):
    """Test scheduler preview calculation with follow_aws strategy."""
    config = sample_config.copy()
    config["purchase_strategy_type"] = "follow_aws"

    # Use proper AWS recommendation fixture
    mock_clients[
        "ce"
    ].get_savings_plans_purchase_recommendation.return_value = aws_mock_builder.recommendation(
        sp_type="compute", hourly_commitment=50.0
    )

    result = scheduler_preview.calculate_scheduler_preview(
        config, mock_clients, sample_coverage_data, sample_savings_data
    )

    assert result["strategy"] == "follow_aws"
    assert result["error"] is None


def test_calculate_scheduler_preview_no_recommendations(
    sample_config, mock_clients, sample_savings_data
):
    """Test scheduler preview when already at target coverage."""
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

    assert result["strategy"] == "fixed"
    assert result["has_recommendations"] is False
    assert result["error"] is None


def test_calculate_scheduler_preview_error_handling(
    sample_config, mock_clients, sample_coverage_data, sample_savings_data
):
    """Test scheduler preview error handling with graceful fallback."""
    # Provide unknown strategy type (should fallback to fixed)
    invalid_config = sample_config.copy()
    invalid_config["purchase_strategy_type"] = "unknown_strategy"

    # This should handle the error gracefully by falling back to fixed strategy
    result = scheduler_preview.calculate_scheduler_preview(
        invalid_config, mock_clients, sample_coverage_data, sample_savings_data
    )

    # Should fallback to fixed strategy and still work
    assert result["strategy"] == "unknown_strategy"
    assert result["error"] is None
    # May have recommendations depending on coverage gap
    assert "has_recommendations" in result


def test_calculate_optimal_commitment_with_active_plans(sample_coverage_data, sample_savings_data):
    """Test optimal commitment calculation with active plans (known discount)."""
    result = scheduler_preview._calculate_optimal_commitment(
        sample_coverage_data, sample_savings_data
    )

    assert "compute" in result
    compute_optimal = result["compute"]

    assert "recommended_hourly_commitment" in compute_optimal
    assert "analysis" in compute_optimal

    analysis = compute_optimal["analysis"]
    assert "target_percentile" in analysis
    assert "discount_rate" in analysis
    assert analysis["discount_rate"] == 0.60  # 60% from sample data


def test_calculate_optimal_commitment_without_active_plans(sample_coverage_data):
    """Test optimal commitment calculation without active plans (default discount)."""
    # No active plans = no discount rate data
    savings_data = {
        "plans_count": 0,
        "actual_savings": {"net_savings": 0.0, "breakdown_by_type": {}},
    }

    result = scheduler_preview._calculate_optimal_commitment(sample_coverage_data, savings_data)

    assert "compute" in result
    compute_optimal = result["compute"]

    # Should use default 30% discount rate
    analysis = compute_optimal["analysis"]
    assert analysis["discount_rate"] == 0.30


def test_enrich_with_optimization_optimal_status():
    """Test efficiency enrichment when scheduled = optimal."""
    scheduled = [
        {
            "sp_type": "compute",
            "hourly_commitment": 100.0,
            "purchase_percent": 10.0,
            "current_coverage": 70.0,
            "projected_coverage": 80.0,
            "payment_option": "ALL_UPFRONT",
            "term": "THREE_YEAR",
        }
    ]

    optimal_analysis = {
        "compute": {
            "recommended_hourly_commitment": 100.0,  # Same as scheduled
            "analysis": {
                "target_percentile": 40,
                "discount_rate": 0.60,
                "breakeven_hours_pct": 60.0,
            },
        }
    }

    coverage_data = {"compute": {"summary": {"avg_hourly_total": 1000.0}}}

    result = scheduler_preview._enrich_with_optimization(scheduled, optimal_analysis, coverage_data)

    assert len(result) == 1
    enriched = result[0]

    assert enriched["efficiency"]["status"] == "optimal"
    assert enriched["efficiency"]["ratio"] == 1.0


def test_enrich_with_optimization_over_committed_status():
    """Test efficiency enrichment when scheduled >> optimal."""
    scheduled = [
        {
            "sp_type": "compute",
            "hourly_commitment": 150.0,
            "purchase_percent": 15.0,
            "current_coverage": 70.0,
            "projected_coverage": 85.0,
            "payment_option": "ALL_UPFRONT",
            "term": "THREE_YEAR",
        }
    ]

    optimal_analysis = {
        "compute": {
            "recommended_hourly_commitment": 100.0,  # Much less than scheduled
            "analysis": {
                "target_percentile": 40,
                "discount_rate": 0.60,
                "breakeven_hours_pct": 60.0,
            },
        }
    }

    coverage_data = {"compute": {"summary": {"avg_hourly_total": 1000.0}}}

    result = scheduler_preview._enrich_with_optimization(scheduled, optimal_analysis, coverage_data)

    enriched = result[0]

    assert enriched["efficiency"]["status"] == "over_committed"
    assert enriched["efficiency"]["ratio"] == 1.5
    assert "50%" in enriched["efficiency"]["message"]

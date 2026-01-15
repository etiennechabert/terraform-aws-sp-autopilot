"""
Unit tests for purchase calculator module.

Tests purchase need calculation, purchase limits, and term splitting
for Compute, Database, and SageMaker Savings Plans.
"""

import os
import sys

import pytest


# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import purchase_calculator


@pytest.fixture
def mock_config():
    """Create a mock configuration dictionary."""
    return {
        "enable_compute_sp": True,
        "enable_database_sp": True,
        "enable_sagemaker_sp": True,
        "coverage_target_percent": 90.0,
        "max_purchase_percent": 10.0,
        "min_commitment_per_plan": 0.001,
        "compute_sp_payment_option": "ALL_UPFRONT",
        "compute_sp_term_mix": {"three_year": 0.67, "one_year": 0.33},
        "sagemaker_sp_payment_option": "ALL_UPFRONT",
        "sagemaker_sp_term_mix": {"three_year": 0.67, "one_year": 0.33},
    }


# ============================================================================
# Calculate Purchase Need Tests
# ============================================================================


def test_calculate_purchase_need_compute_gap(mock_config):
    """Test purchase calculation with coverage gap for Compute SP."""
    coverage = {"compute": 70.0, "database": 90.0, "sagemaker": 90.0}
    recommendations = {
        "compute": {"HourlyCommitmentToPurchase": "5.50", "RecommendationId": "rec-12345"},
        "database": None,
        "sagemaker": None,
    }

    result = purchase_calculator.calculate_purchase_need(mock_config, coverage, recommendations)

    assert len(result) == 1
    assert result[0]["sp_type"] == "compute"
    assert result[0]["hourly_commitment"] == 5.50
    assert result[0]["payment_option"] == "ALL_UPFRONT"
    assert result[0]["recommendation_id"] == "rec-12345"


def test_calculate_purchase_need_database_gap(mock_config):
    """Test purchase calculation with coverage gap for Database SP."""
    coverage = {"compute": 90.0, "database": 60.0, "sagemaker": 90.0}
    recommendations = {
        "compute": None,
        "database": {"HourlyCommitmentToPurchase": "2.75", "RecommendationId": "rec-db-456"},
        "sagemaker": None,
    }

    result = purchase_calculator.calculate_purchase_need(mock_config, coverage, recommendations)

    assert len(result) == 1
    assert result[0]["sp_type"] == "database"
    assert result[0]["hourly_commitment"] == 2.75
    assert result[0]["term"] == "ONE_YEAR"
    assert result[0]["payment_option"] == "NO_UPFRONT"
    assert result[0]["recommendation_id"] == "rec-db-456"


def test_calculate_purchase_need_sagemaker_gap(mock_config):
    """Test purchase calculation with coverage gap for SageMaker SP."""
    coverage = {"compute": 90.0, "database": 90.0, "sagemaker": 50.0}
    recommendations = {
        "compute": None,
        "database": None,
        "sagemaker": {"HourlyCommitmentToPurchase": "3.25", "RecommendationId": "rec-sm-789"},
    }

    result = purchase_calculator.calculate_purchase_need(mock_config, coverage, recommendations)

    assert len(result) == 1
    assert result[0]["sp_type"] == "sagemaker"
    assert result[0]["hourly_commitment"] == 3.25
    assert result[0]["payment_option"] == "ALL_UPFRONT"
    assert result[0]["recommendation_id"] == "rec-sm-789"


def test_calculate_purchase_need_multiple_gaps(mock_config):
    """Test purchase calculation with multiple coverage gaps."""
    coverage = {"compute": 70.0, "database": 60.0, "sagemaker": 50.0}
    recommendations = {
        "compute": {"HourlyCommitmentToPurchase": "5.50", "RecommendationId": "rec-compute"},
        "database": {"HourlyCommitmentToPurchase": "2.75", "RecommendationId": "rec-database"},
        "sagemaker": {"HourlyCommitmentToPurchase": "3.25", "RecommendationId": "rec-sagemaker"},
    }

    result = purchase_calculator.calculate_purchase_need(mock_config, coverage, recommendations)

    assert len(result) == 3
    sp_types = [plan["sp_type"] for plan in result]
    assert "compute" in sp_types
    assert "database" in sp_types
    assert "sagemaker" in sp_types


def test_calculate_purchase_need_no_gap(mock_config):
    """Test when coverage already meets target."""
    coverage = {"compute": 95.0, "database": 92.0, "sagemaker": 94.0}
    recommendations = {
        "compute": {"HourlyCommitmentToPurchase": "5.50", "RecommendationId": "rec-12345"},
        "database": {"HourlyCommitmentToPurchase": "2.75", "RecommendationId": "rec-db-456"},
        "sagemaker": {"HourlyCommitmentToPurchase": "3.25", "RecommendationId": "rec-sm-789"},
    }

    result = purchase_calculator.calculate_purchase_need(mock_config, coverage, recommendations)

    # No purchases should be planned
    assert len(result) == 0


def test_calculate_purchase_need_gap_but_no_recommendation(mock_config):
    """Test when there's a coverage gap but no AWS recommendation."""
    coverage = {"compute": 70.0, "database": 90.0, "sagemaker": 90.0}
    recommendations = {"compute": None, "database": None, "sagemaker": None}

    result = purchase_calculator.calculate_purchase_need(mock_config, coverage, recommendations)

    # No purchases can be planned without recommendations
    assert len(result) == 0


def test_calculate_purchase_need_zero_commitment(mock_config):
    """Test when recommendation has zero commitment."""
    coverage = {"compute": 70.0, "database": 90.0, "sagemaker": 90.0}
    recommendations = {
        "compute": {"HourlyCommitmentToPurchase": "0", "RecommendationId": "rec-12345"},
        "database": None,
        "sagemaker": None,
    }

    result = purchase_calculator.calculate_purchase_need(mock_config, coverage, recommendations)

    # Zero commitment should be skipped
    assert len(result) == 0


def test_calculate_purchase_need_sp_disabled(mock_config):
    """Test when SP type is disabled in config."""
    mock_config["enable_compute_sp"] = False

    coverage = {"compute": 70.0, "database": 90.0, "sagemaker": 90.0}
    recommendations = {
        "compute": {"HourlyCommitmentToPurchase": "5.50", "RecommendationId": "rec-12345"},
        "database": None,
        "sagemaker": None,
    }

    result = purchase_calculator.calculate_purchase_need(mock_config, coverage, recommendations)

    # Should not plan purchase for disabled SP type
    assert len(result) == 0


# ============================================================================
# Apply Purchase Limits Tests
# ============================================================================


def test_apply_purchase_limits_with_limit(mock_config):
    """Test applying max_purchase_percent limit."""
    purchase_plans = [
        {"sp_type": "compute", "hourly_commitment": 10.0, "payment_option": "ALL_UPFRONT"}
    ]

    result = purchase_calculator.apply_purchase_limits(mock_config, purchase_plans)

    # 10% of 10.0 = 1.0
    assert len(result) == 1
    assert result[0]["hourly_commitment"] == 1.0


def test_apply_purchase_limits_multiple_plans(mock_config):
    """Test applying limits to multiple plans."""
    purchase_plans = [
        {"sp_type": "compute", "hourly_commitment": 10.0, "payment_option": "ALL_UPFRONT"},
        {"sp_type": "database", "hourly_commitment": 5.0, "payment_option": "NO_UPFRONT"},
    ]

    result = purchase_calculator.apply_purchase_limits(mock_config, purchase_plans)

    # Both should be scaled to 10%
    assert len(result) == 2
    assert result[0]["hourly_commitment"] == 1.0
    assert result[1]["hourly_commitment"] == 0.5


def test_apply_purchase_limits_below_minimum(mock_config):
    """Test that plans below minimum commitment are filtered out."""
    purchase_plans = [
        {
            "sp_type": "compute",
            "hourly_commitment": 0.005,  # Will be 0.0005 after 10% limit
            "payment_option": "ALL_UPFRONT",
        }
    ]

    result = purchase_calculator.apply_purchase_limits(mock_config, purchase_plans)

    # Should be filtered out (0.0005 < 0.001 minimum)
    assert len(result) == 0


def test_apply_purchase_limits_no_plans():
    """Test applying limits with no plans."""
    config = {"max_purchase_percent": 10.0, "min_commitment_per_plan": 0.001}
    purchase_plans = []

    result = purchase_calculator.apply_purchase_limits(config, purchase_plans)

    assert len(result) == 0


def test_apply_purchase_limits_100_percent(mock_config):
    """Test with 100% purchase limit (no scaling)."""
    mock_config["max_purchase_percent"] = 100.0

    purchase_plans = [
        {"sp_type": "compute", "hourly_commitment": 5.50, "payment_option": "ALL_UPFRONT"}
    ]

    result = purchase_calculator.apply_purchase_limits(mock_config, purchase_plans)

    # Should remain unchanged
    assert len(result) == 1
    assert result[0]["hourly_commitment"] == 5.50


def test_apply_purchase_limits_mixed_filtering(mock_config):
    """Test with some plans above and some below minimum after scaling."""
    purchase_plans = [
        {
            "sp_type": "compute",
            "hourly_commitment": 1.0,  # Will be 0.1 after 10% limit (above min)
            "payment_option": "ALL_UPFRONT",
        },
        {
            "sp_type": "database",
            "hourly_commitment": 0.005,  # Will be 0.0005 after 10% limit (below min)
            "payment_option": "NO_UPFRONT",
        },
    ]

    result = purchase_calculator.apply_purchase_limits(mock_config, purchase_plans)

    # Only first plan should remain
    assert len(result) == 1
    assert result[0]["sp_type"] == "compute"
    assert result[0]["hourly_commitment"] == 0.1


# ============================================================================
# Split by Term Tests
# ============================================================================


def test_split_by_term_compute_sp(mock_config):
    """Test splitting Compute SP by term mix."""
    purchase_plans = [
        {
            "sp_type": "compute",
            "hourly_commitment": 1.0,
            "payment_option": "ALL_UPFRONT",
            "recommendation_id": "rec-12345",
        }
    ]

    result = purchase_calculator.split_by_term(mock_config, purchase_plans)

    # Should create 2 plans: 67% three_year, 33% one_year
    assert len(result) == 2

    three_year = [p for p in result if p["term"] == "THREE_YEAR"][0]
    one_year = [p for p in result if p["term"] == "ONE_YEAR"][0]

    assert three_year["hourly_commitment"] == pytest.approx(0.67)
    assert one_year["hourly_commitment"] == pytest.approx(0.33)


def test_split_by_term_sagemaker_sp(mock_config):
    """Test splitting SageMaker SP by term mix."""
    purchase_plans = [
        {
            "sp_type": "sagemaker",
            "hourly_commitment": 2.0,
            "payment_option": "ALL_UPFRONT",
            "recommendation_id": "rec-sm-789",
        }
    ]

    result = purchase_calculator.split_by_term(mock_config, purchase_plans)

    # Should create 2 plans: 67% three_year, 33% one_year
    assert len(result) == 2

    three_year = [p for p in result if p["term"] == "THREE_YEAR"][0]
    one_year = [p for p in result if p["term"] == "ONE_YEAR"][0]

    assert three_year["hourly_commitment"] == pytest.approx(1.34)
    assert one_year["hourly_commitment"] == pytest.approx(0.66)


def test_split_by_term_database_sp_unchanged(mock_config):
    """Test that Database SP is passed through unchanged."""
    purchase_plans = [
        {
            "sp_type": "database",
            "hourly_commitment": 1.5,
            "term": "ONE_YEAR",
            "payment_option": "NO_UPFRONT",
            "recommendation_id": "rec-db-456",
        }
    ]

    result = purchase_calculator.split_by_term(mock_config, purchase_plans)

    # Should remain a single plan unchanged
    assert len(result) == 1
    assert result[0]["sp_type"] == "database"
    assert result[0]["hourly_commitment"] == 1.5
    assert result[0]["term"] == "ONE_YEAR"


def test_split_by_term_mixed_types(mock_config):
    """Test splitting with mixed SP types."""
    purchase_plans = [
        {
            "sp_type": "compute",
            "hourly_commitment": 1.0,
            "payment_option": "ALL_UPFRONT",
            "recommendation_id": "rec-compute",
        },
        {
            "sp_type": "database",
            "hourly_commitment": 0.5,
            "term": "ONE_YEAR",
            "payment_option": "NO_UPFRONT",
            "recommendation_id": "rec-database",
        },
        {
            "sp_type": "sagemaker",
            "hourly_commitment": 2.0,
            "payment_option": "ALL_UPFRONT",
            "recommendation_id": "rec-sagemaker",
        },
    ]

    result = purchase_calculator.split_by_term(mock_config, purchase_plans)

    # Compute: 2 plans, Database: 1 plan, SageMaker: 2 plans = 5 total
    assert len(result) == 5

    database_plans = [p for p in result if p["sp_type"] == "database"]
    compute_plans = [p for p in result if p["sp_type"] == "compute"]
    sagemaker_plans = [p for p in result if p["sp_type"] == "sagemaker"]

    assert len(database_plans) == 1
    assert len(compute_plans) == 2
    assert len(sagemaker_plans) == 2


def test_split_by_term_below_minimum_threshold(mock_config):
    """Test that term splits below minimum are skipped."""
    # Very small commitment that when split will be below minimum
    purchase_plans = [
        {
            "sp_type": "compute",
            "hourly_commitment": 0.002,  # 67% = 0.00134, 33% = 0.00066 (below 0.001 min)
            "payment_option": "ALL_UPFRONT",
            "recommendation_id": "rec-12345",
        }
    ]

    result = purchase_calculator.split_by_term(mock_config, purchase_plans)

    # Only three_year should remain (0.00134 >= 0.001)
    # one_year should be filtered (0.00066 < 0.001)
    assert len(result) == 1
    assert result[0]["term"] == "THREE_YEAR"


def test_split_by_term_no_plans():
    """Test splitting with no plans."""
    config = {"min_commitment_per_plan": 0.001}
    purchase_plans = []

    result = purchase_calculator.split_by_term(config, purchase_plans)

    assert len(result) == 0


def test_split_by_term_preserves_fields(mock_config):
    """Test that term splitting preserves all original fields."""
    purchase_plans = [
        {
            "sp_type": "compute",
            "hourly_commitment": 1.0,
            "payment_option": "ALL_UPFRONT",
            "recommendation_id": "rec-12345",
            "custom_field": "custom_value",
        }
    ]

    result = purchase_calculator.split_by_term(mock_config, purchase_plans)

    # All plans should preserve custom fields
    for plan in result:
        assert plan["payment_option"] == "ALL_UPFRONT"
        assert plan["recommendation_id"] == "rec-12345"
        assert plan["custom_field"] == "custom_value"


def test_split_by_term_custom_term_mix(mock_config):
    """Test with custom term mix percentages."""
    mock_config["compute_sp_term_mix"] = {"three_year": 0.8, "one_year": 0.2}

    purchase_plans = [
        {
            "sp_type": "compute",
            "hourly_commitment": 10.0,
            "payment_option": "ALL_UPFRONT",
            "recommendation_id": "rec-12345",
        }
    ]

    result = purchase_calculator.split_by_term(mock_config, purchase_plans)

    assert len(result) == 2

    three_year = [p for p in result if p["term"] == "THREE_YEAR"][0]
    one_year = [p for p in result if p["term"] == "ONE_YEAR"][0]

    assert three_year["hourly_commitment"] == 8.0
    assert one_year["hourly_commitment"] == 2.0


def test_split_by_term_unknown_sp_type(mock_config):
    """Test handling of unknown SP type."""
    purchase_plans = [
        {"sp_type": "unknown", "hourly_commitment": 1.0, "payment_option": "ALL_UPFRONT"}
    ]

    result = purchase_calculator.split_by_term(mock_config, purchase_plans)

    # Should pass through unchanged with warning
    assert len(result) == 1
    assert result[0]["sp_type"] == "unknown"
    assert result[0]["hourly_commitment"] == 1.0

"""
Tests for Fixed Purchase Strategy Module.

Tests the fixed purchase strategy which applies a uniform percentage
to all AWS recommendations.

Coverage: 98% (100% statement coverage, 98% branch coverage)
"""

import pytest

from fixed_strategy import calculate_purchase_need_fixed


@pytest.fixture
def mock_config():
    """Provide basic configuration for tests."""
    return {
        "coverage_target_percent": 80.0,
        "enable_compute_sp": True,
        "enable_database_sp": True,
        "enable_sagemaker_sp": True,
        "compute_sp_payment_option": "ALL_UPFRONT",
        "compute_sp_term": "THREE_YEAR",
        "database_sp_payment_option": "NO_UPFRONT",
        "sagemaker_sp_payment_option": "ALL_UPFRONT",
        "sagemaker_sp_term": "ONE_YEAR",
    }


@pytest.fixture
def mock_coverage():
    """Provide coverage data for tests."""
    return {"compute": 50.0, "database": 60.0, "sagemaker": 40.0}


@pytest.fixture
def mock_recommendations():
    """Provide AWS recommendations for tests."""
    return {
        "compute": {
            "HourlyCommitmentToPurchase": "2.500",
            "RecommendationId": "rec-compute-123",
        },
        "database": {
            "HourlyCommitmentToPurchase": "1.250",
            "RecommendationId": "rec-database-456",
        },
        "sagemaker": {
            "HourlyCommitmentToPurchase": "0.750",
            "RecommendationId": "rec-sagemaker-789",
        },
    }


def test_calculate_purchase_need_all_types(mock_config, mock_coverage, mock_recommendations):
    """Test fixed strategy returns plans for all enabled SP types with coverage gaps."""
    plans = calculate_purchase_need_fixed(mock_config, mock_coverage, mock_recommendations)

    assert len(plans) == 3

    # Check compute plan
    compute_plan = [p for p in plans if p["sp_type"] == "compute"][0]
    assert compute_plan["hourly_commitment"] == 2.5
    assert compute_plan["payment_option"] == "ALL_UPFRONT"
    assert compute_plan["term"] == "THREE_YEAR"
    assert compute_plan["strategy"] == "fixed"
    assert compute_plan["recommendation_id"] == "rec-compute-123"

    # Check database plan
    database_plan = [p for p in plans if p["sp_type"] == "database"][0]
    assert database_plan["hourly_commitment"] == 1.25
    assert database_plan["payment_option"] == "NO_UPFRONT"
    assert database_plan["term"] == "ONE_YEAR"
    assert database_plan["strategy"] == "fixed"

    # Check sagemaker plan
    sagemaker_plan = [p for p in plans if p["sp_type"] == "sagemaker"][0]
    assert sagemaker_plan["hourly_commitment"] == 0.75
    assert sagemaker_plan["payment_option"] == "ALL_UPFRONT"
    assert sagemaker_plan["term"] == "ONE_YEAR"


def test_calculate_purchase_need_disabled_sp_type(mock_config, mock_coverage, mock_recommendations):
    """Test that disabled SP types are skipped."""
    mock_config["enable_sagemaker_sp"] = False

    plans = calculate_purchase_need_fixed(mock_config, mock_coverage, mock_recommendations)

    # Should only have compute and database
    assert len(plans) == 2
    assert all(p["sp_type"] != "sagemaker" for p in plans)


def test_calculate_purchase_need_coverage_at_target(
    mock_config, mock_coverage, mock_recommendations
):
    """Test that SP types already at or above target are skipped."""
    mock_coverage["compute"] = 85.0  # Above 80% target

    plans = calculate_purchase_need_fixed(mock_config, mock_coverage, mock_recommendations)

    # Should only have database and sagemaker
    assert len(plans) == 2
    assert all(p["sp_type"] != "compute" for p in plans)


def test_calculate_purchase_need_no_recommendation(
    mock_config, mock_coverage, mock_recommendations
):
    """Test that SP types without recommendations are skipped."""
    del mock_recommendations["database"]

    plans = calculate_purchase_need_fixed(mock_config, mock_coverage, mock_recommendations)

    # Should only have compute and sagemaker
    assert len(plans) == 2
    assert all(p["sp_type"] != "database" for p in plans)


def test_calculate_purchase_need_zero_commitment(mock_config, mock_coverage, mock_recommendations):
    """Test that recommendations with zero commitment are skipped."""
    mock_recommendations["compute"]["HourlyCommitmentToPurchase"] = "0.000"

    plans = calculate_purchase_need_fixed(mock_config, mock_coverage, mock_recommendations)

    # Should only have database and sagemaker
    assert len(plans) == 2
    assert all(p["sp_type"] != "compute" for p in plans)


def test_calculate_purchase_need_default_payment_options(
    mock_config, mock_coverage, mock_recommendations
):
    """Test that default payment options are used when not configured."""
    # Remove payment option configs
    del mock_config["compute_sp_payment_option"]
    del mock_config["database_sp_payment_option"]
    del mock_config["sagemaker_sp_payment_option"]

    plans = calculate_purchase_need_fixed(mock_config, mock_coverage, mock_recommendations)

    # Check defaults are applied
    compute_plan = [p for p in plans if p["sp_type"] == "compute"][0]
    assert compute_plan["payment_option"] == "ALL_UPFRONT"

    database_plan = [p for p in plans if p["sp_type"] == "database"][0]
    assert database_plan["payment_option"] == "NO_UPFRONT"

    sagemaker_plan = [p for p in plans if p["sp_type"] == "sagemaker"][0]
    assert sagemaker_plan["payment_option"] == "ALL_UPFRONT"


def test_calculate_purchase_need_default_terms(mock_config, mock_coverage, mock_recommendations):
    """Test that default terms are used when not configured."""
    # Remove term configs
    del mock_config["compute_sp_term"]
    del mock_config["sagemaker_sp_term"]

    plans = calculate_purchase_need_fixed(mock_config, mock_coverage, mock_recommendations)

    # Check defaults are applied
    compute_plan = [p for p in plans if p["sp_type"] == "compute"][0]
    assert compute_plan["term"] == "THREE_YEAR"

    sagemaker_plan = [p for p in plans if p["sp_type"] == "sagemaker"][0]
    assert sagemaker_plan["term"] == "THREE_YEAR"

    # Database should always be ONE_YEAR
    database_plan = [p for p in plans if p["sp_type"] == "database"][0]
    assert database_plan["term"] == "ONE_YEAR"


def test_calculate_purchase_need_no_coverage_data(mock_config, mock_recommendations):
    """Test handling of missing coverage data."""
    empty_coverage = {}

    plans = calculate_purchase_need_fixed(mock_config, empty_coverage, mock_recommendations)

    # Should create plans for all types since coverage defaults to 0
    assert len(plans) == 3


def test_calculate_purchase_need_empty_recommendations(mock_config, mock_coverage):
    """Test with no recommendations available."""
    empty_recommendations = {}

    plans = calculate_purchase_need_fixed(mock_config, mock_coverage, empty_recommendations)

    assert len(plans) == 0


def test_calculate_purchase_need_all_disabled(mock_config, mock_coverage, mock_recommendations):
    """Test with all SP types disabled."""
    mock_config["enable_compute_sp"] = False
    mock_config["enable_database_sp"] = False
    mock_config["enable_sagemaker_sp"] = False

    plans = calculate_purchase_need_fixed(mock_config, mock_coverage, mock_recommendations)

    assert len(plans) == 0


def test_calculate_purchase_need_missing_recommendation_id(
    mock_config, mock_coverage, mock_recommendations
):
    """Test handling of recommendations without IDs."""
    del mock_recommendations["compute"]["RecommendationId"]

    plans = calculate_purchase_need_fixed(mock_config, mock_coverage, mock_recommendations)

    compute_plan = [p for p in plans if p["sp_type"] == "compute"][0]
    assert compute_plan["recommendation_id"] == "unknown"

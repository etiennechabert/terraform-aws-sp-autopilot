"""
Tests for Fixed Purchase Strategy Module.

Tests the fixed purchase strategy which applies a fixed percentage
to all spending.
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
def mock_spending_data():
    """Provide spending data for tests."""
    return {
        "compute": {
            "timeseries": [],
            "summary": {
                "avg_coverage_total": 50.0,
                "avg_hourly_total": 2.5,
                "avg_hourly_covered": 1.25,
            },
        },
        "database": {
            "timeseries": [],
            "summary": {
                "avg_coverage_total": 60.0,
                "avg_hourly_total": 1.25,
                "avg_hourly_covered": 0.75,
            },
        },
        "sagemaker": {
            "timeseries": [],
            "summary": {
                "avg_coverage_total": 40.0,
                "avg_hourly_total": 0.75,
                "avg_hourly_covered": 0.30,
            },
        },
    }


def test_calculate_purchase_need_all_types(mock_config, mock_spending_data):
    """Test fixed strategy returns plans for all enabled SP types with coverage gaps."""
    mock_config["max_purchase_percent"] = 100.0  # Purchase full gap
    plans = calculate_purchase_need_fixed(mock_config, {}, mock_spending_data)

    assert len(plans) == 3

    # Check compute plan (50% -> 80% = 30% gap, 30% of $2.5 = $0.75)
    compute_plan = [p for p in plans if p["sp_type"] == "compute"][0]
    assert compute_plan["hourly_commitment"] == pytest.approx(0.75)
    assert compute_plan["payment_option"] == "ALL_UPFRONT"
    assert compute_plan["term"] == "THREE_YEAR"
    assert compute_plan["strategy"] == "fixed"

    # Check database plan (60% -> 80% = 20% gap, 20% of $1.25 = $0.25)
    database_plan = [p for p in plans if p["sp_type"] == "database"][0]
    assert database_plan["hourly_commitment"] == pytest.approx(0.25)
    assert database_plan["payment_option"] == "NO_UPFRONT"
    assert database_plan["term"] == "ONE_YEAR"
    assert database_plan["strategy"] == "fixed"

    # Check sagemaker plan (40% -> 80% = 40% gap, 40% of $0.75 = $0.30)
    sagemaker_plan = [p for p in plans if p["sp_type"] == "sagemaker"][0]
    assert sagemaker_plan["hourly_commitment"] == pytest.approx(0.30, rel=0.01)
    assert sagemaker_plan["payment_option"] == "ALL_UPFRONT"
    assert sagemaker_plan["term"] == "ONE_YEAR"


def test_calculate_purchase_need_disabled_sp_type(mock_config, mock_spending_data):
    """Test that disabled SP types are skipped."""
    mock_config["enable_sagemaker_sp"] = False

    plans = calculate_purchase_need_fixed(mock_config, {}, mock_spending_data)

    # Should only have compute and database
    assert len(plans) == 2
    assert all(p["sp_type"] != "sagemaker" for p in plans)


def test_calculate_purchase_need_coverage_at_target(mock_config, mock_spending_data):
    """Test that SP types already at or above target are skipped."""
    mock_spending_data["compute"]["summary"]["avg_coverage_total"] = 85.0  # Above 80% target

    plans = calculate_purchase_need_fixed(mock_config, {}, mock_spending_data)

    # Should only have database and sagemaker
    assert len(plans) == 2
    assert all(p["sp_type"] != "compute" for p in plans)


def test_calculate_purchase_need_no_spending_data(mock_config):
    """Test that SP types without spending data are skipped."""
    spending_data = {
        "compute": {
            "timeseries": [],
            "summary": {
                "avg_coverage_total": 50.0,
                "avg_hourly_total": 2.5,
                "avg_hourly_covered": 1.25,
            },
        }
    }

    plans = calculate_purchase_need_fixed(mock_config, {}, spending_data)

    # Should only have compute
    assert len(plans) == 1
    assert all(p["sp_type"] != "database" for p in plans)
    assert all(p["sp_type"] != "sagemaker" for p in plans)


def test_calculate_purchase_need_zero_spend(mock_config, mock_spending_data):
    """Test that SP types with zero spend are skipped."""
    mock_spending_data["compute"]["summary"]["avg_hourly_total"] = 0.0

    plans = calculate_purchase_need_fixed(mock_config, {}, mock_spending_data)

    # Should only have database and sagemaker
    assert len(plans) == 2
    assert all(p["sp_type"] != "compute" for p in plans)


@pytest.mark.skip(reason="Implementation requires payment options in config - no defaults")
def test_calculate_purchase_need_default_payment_options(mock_config, mock_spending_data):
    """Test that default payment options are used when not configured."""
    # Remove payment option configs
    del mock_config["compute_sp_payment_option"]
    del mock_config["sagemaker_sp_payment_option"]

    plans = calculate_purchase_need_fixed(mock_config, {}, mock_spending_data)

    # Check defaults are applied
    compute_plan = [p for p in plans if p["sp_type"] == "compute"][0]
    assert compute_plan["payment_option"] == "ALL_UPFRONT"

    database_plan = [p for p in plans if p["sp_type"] == "database"][0]
    assert database_plan["payment_option"] == "NO_UPFRONT"

    sagemaker_plan = [p for p in plans if p["sp_type"] == "sagemaker"][0]
    assert sagemaker_plan["payment_option"] == "ALL_UPFRONT"


@pytest.mark.skip(reason="Implementation requires terms in config - no defaults")
def test_calculate_purchase_need_default_terms(mock_config, mock_spending_data):
    """Test that default terms are used when not configured."""
    # Remove term configs
    del mock_config["compute_sp_term"]
    del mock_config["sagemaker_sp_term"]

    plans = calculate_purchase_need_fixed(mock_config, {}, mock_spending_data)

    # Check defaults are applied
    compute_plan = [p for p in plans if p["sp_type"] == "compute"][0]
    assert compute_plan["term"] == "THREE_YEAR"

    sagemaker_plan = [p for p in plans if p["sp_type"] == "sagemaker"][0]
    assert sagemaker_plan["term"] == "THREE_YEAR"

    # Database should always be ONE_YEAR
    database_plan = [p for p in plans if p["sp_type"] == "database"][0]
    assert database_plan["term"] == "ONE_YEAR"


def test_calculate_purchase_need_empty_spending_data(mock_config):
    """Test with no spending data available."""
    empty_spending_data = {}

    plans = calculate_purchase_need_fixed(mock_config, {}, empty_spending_data)

    assert len(plans) == 0


def test_calculate_purchase_need_all_disabled(mock_config, mock_spending_data):
    """Test with all SP types disabled."""
    mock_config["enable_compute_sp"] = False
    mock_config["enable_database_sp"] = False
    mock_config["enable_sagemaker_sp"] = False

    plans = calculate_purchase_need_fixed(mock_config, {}, mock_spending_data)

    assert len(plans) == 0


def test_calculate_purchase_need_with_max_purchase_percent(mock_config, mock_spending_data):
    """Test that max_purchase_percent limits the purchase."""
    mock_config["max_purchase_percent"] = 10.0

    plans = calculate_purchase_need_fixed(mock_config, {}, mock_spending_data)

    # Compute: gap=30%, max=10%, purchase=10% of $2.5 = $0.25
    compute_plan = [p for p in plans if p["sp_type"] == "compute"][0]
    assert compute_plan["hourly_commitment"] == pytest.approx(0.25, rel=0.01)
    assert compute_plan["purchase_percent"] == pytest.approx(10.0)

    # Database: gap=20%, max=10%, purchase=10% of $1.25 = $0.125
    database_plan = [p for p in plans if p["sp_type"] == "database"][0]
    assert database_plan["hourly_commitment"] == pytest.approx(0.125, rel=0.01)
    assert database_plan["purchase_percent"] == pytest.approx(10.0)

    # SageMaker: gap=40%, max=10%, purchase=10% of $0.75 = $0.075
    sagemaker_plan = [p for p in plans if p["sp_type"] == "sagemaker"][0]
    assert sagemaker_plan["hourly_commitment"] == pytest.approx(0.075, rel=0.01)
    assert sagemaker_plan["purchase_percent"] == pytest.approx(10.0)


def test_calculate_purchase_need_gap_smaller_than_max(mock_config, mock_spending_data):
    """Test that purchase percent equals gap when gap < max_purchase_percent."""
    mock_config["max_purchase_percent"] = 50.0
    # Compute has 30% gap, which is less than max 50%
    # Should purchase exactly 30%

    plans = calculate_purchase_need_fixed(mock_config, {}, mock_spending_data)

    compute_plan = [p for p in plans if p["sp_type"] == "compute"][0]
    # Gap is 30%, max is 50%, should purchase 30% of $2.5 = $0.75
    assert compute_plan["purchase_percent"] == pytest.approx(30.0)
    assert compute_plan["hourly_commitment"] == pytest.approx(0.75, rel=0.01)


def test_calculate_purchase_need_min_commitment_filter(mock_config, mock_spending_data):
    """Test that plans below min_commitment_per_plan are filtered."""
    mock_config["min_commitment_per_plan"] = 1.0
    mock_config["max_purchase_percent"] = 10.0

    plans = calculate_purchase_need_fixed(mock_config, {}, mock_spending_data)

    # Compute: 10% of $2.5 = $0.25 < $1.0 min -> filtered
    # Database: 10% of $1.25 = $0.125 < $1.0 min -> filtered
    # SageMaker: 10% of $0.75 = $0.075 < $1.0 min -> filtered
    assert len(plans) == 0

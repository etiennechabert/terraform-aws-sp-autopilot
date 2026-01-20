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
        "purchase_strategy_type": "follow_aws",
        "max_purchase_percent": 10.0,
        "min_commitment_per_plan": 0.001,
        "lookback_days": 13,
        "compute_sp_payment_option": "ALL_UPFRONT",
        "compute_sp_term": "THREE_YEAR",
        "database_sp_payment_option": "NO_UPFRONT",
        "sagemaker_sp_payment_option": "ALL_UPFRONT",
        "sagemaker_sp_term": "THREE_YEAR",
    }


# ============================================================================
# Calculate Purchase Need Tests
# ============================================================================


def test_calculate_purchase_need_compute_gap(mock_config):
    """Test purchase calculation with coverage gap for Compute SP."""
    from unittest.mock import Mock, patch

    # Only enable compute SP
    mock_config["enable_compute_sp"] = True
    mock_config["enable_database_sp"] = False
    mock_config["enable_sagemaker_sp"] = False

    # Create mock CE client
    mock_ce_client = Mock()
    mock_ce_client.get_savings_plans_purchase_recommendation.return_value = {
        "Metadata": {
            "RecommendationId": "rec-12345",
            "LookbackPeriodInDays": "13",
        },
        "SavingsPlansPurchaseRecommendation": {
            "SavingsPlansPurchaseRecommendationDetails": [{"HourlyCommitmentToPurchase": "5.50"}]
        },
    }

    clients = {"ce": mock_ce_client}

    result = purchase_calculator.calculate_purchase_need(mock_config, clients, spending_data=None)

    assert len(result) == 1
    assert result[0]["sp_type"] == "compute"
    assert result[0]["hourly_commitment"] == 5.50
    assert result[0]["payment_option"] == "ALL_UPFRONT"
    assert result[0]["recommendation_id"] == "rec-12345"


def test_calculate_purchase_need_database_gap(mock_config):
    """Test purchase calculation with coverage gap for Database SP."""
    from unittest.mock import Mock

    mock_config["enable_compute_sp"] = False
    mock_config["enable_database_sp"] = True
    mock_config["enable_sagemaker_sp"] = False
    mock_config["database_sp_payment_option"] = "NO_UPFRONT"

    # Create mock CE client
    mock_ce_client = Mock()
    mock_ce_client.get_savings_plans_purchase_recommendation.return_value = {
        "Metadata": {
            "RecommendationId": "rec-db-456",
            "LookbackPeriodInDays": "13",
        },
        "SavingsPlansPurchaseRecommendation": {
            "SavingsPlansPurchaseRecommendationDetails": [{"HourlyCommitmentToPurchase": "2.75"}]
        },
    }

    clients = {"ce": mock_ce_client}

    result = purchase_calculator.calculate_purchase_need(mock_config, clients, spending_data=None)

    assert len(result) == 1
    assert result[0]["sp_type"] == "database"
    assert result[0]["hourly_commitment"] == 2.75
    assert result[0]["term"] == "ONE_YEAR"
    assert result[0]["payment_option"] == "NO_UPFRONT"
    assert result[0]["recommendation_id"] == "rec-db-456"


def test_calculate_purchase_need_sagemaker_gap(mock_config):
    """Test purchase calculation with coverage gap for SageMaker SP."""
    from unittest.mock import Mock

    mock_config["enable_compute_sp"] = False
    mock_config["enable_database_sp"] = False
    mock_config["enable_sagemaker_sp"] = True

    # Create mock CE client
    mock_ce_client = Mock()
    mock_ce_client.get_savings_plans_purchase_recommendation.return_value = {
        "Metadata": {
            "RecommendationId": "rec-sm-789",
            "LookbackPeriodInDays": "13",
        },
        "SavingsPlansPurchaseRecommendation": {
            "SavingsPlansPurchaseRecommendationDetails": [{"HourlyCommitmentToPurchase": "3.25"}]
        },
    }

    clients = {"ce": mock_ce_client}

    result = purchase_calculator.calculate_purchase_need(mock_config, clients, spending_data=None)

    assert len(result) == 1
    assert result[0]["sp_type"] == "sagemaker"
    assert result[0]["hourly_commitment"] == 3.25
    assert result[0]["payment_option"] == "ALL_UPFRONT"
    assert result[0]["recommendation_id"] == "rec-sm-789"


def test_calculate_purchase_need_multiple_gaps(mock_config):
    """Test purchase calculation with multiple coverage gaps."""
    from unittest.mock import Mock

    mock_config["enable_compute_sp"] = True
    mock_config["enable_database_sp"] = True
    mock_config["enable_sagemaker_sp"] = True
    mock_config["database_sp_payment_option"] = "NO_UPFRONT"

    # Create mock CE client that returns different results based on SP type
    mock_ce_client = Mock()

    def mock_recommendation(*args, **kwargs):
        sp_type = kwargs.get("SavingsPlansType")
        if sp_type == "COMPUTE_SP":
            return {
                "Metadata": {"RecommendationId": "rec-compute", "LookbackPeriodInDays": "13"},
                "SavingsPlansPurchaseRecommendation": {
                    "SavingsPlansPurchaseRecommendationDetails": [
                        {"HourlyCommitmentToPurchase": "5.50"}
                    ]
                },
            }
        elif sp_type == "DATABASE_SP":
            return {
                "Metadata": {"RecommendationId": "rec-database", "LookbackPeriodInDays": "13"},
                "SavingsPlansPurchaseRecommendation": {
                    "SavingsPlansPurchaseRecommendationDetails": [
                        {"HourlyCommitmentToPurchase": "2.75"}
                    ]
                },
            }
        elif sp_type == "SAGEMAKER_SP":
            return {
                "Metadata": {"RecommendationId": "rec-sagemaker", "LookbackPeriodInDays": "13"},
                "SavingsPlansPurchaseRecommendation": {
                    "SavingsPlansPurchaseRecommendationDetails": [
                        {"HourlyCommitmentToPurchase": "3.25"}
                    ]
                },
            }

    mock_ce_client.get_savings_plans_purchase_recommendation.side_effect = mock_recommendation

    clients = {"ce": mock_ce_client}

    result = purchase_calculator.calculate_purchase_need(mock_config, clients, spending_data=None)

    assert len(result) == 3
    sp_types = [plan["sp_type"] for plan in result]
    assert "compute" in sp_types
    assert "database" in sp_types
    assert "sagemaker" in sp_types


def test_calculate_purchase_need_no_gap(mock_config):
    """Test when no recommendations are available (e.g., already at target coverage)."""
    from unittest.mock import Mock

    # Create mock CE client that returns empty recommendations
    mock_ce_client = Mock()
    mock_ce_client.get_savings_plans_purchase_recommendation.return_value = {
        "Metadata": {"RecommendationId": "rec-123", "LookbackPeriodInDays": "13"},
        "SavingsPlansPurchaseRecommendation": {"SavingsPlansPurchaseRecommendationDetails": []},
    }

    clients = {"ce": mock_ce_client}

    result = purchase_calculator.calculate_purchase_need(mock_config, clients, spending_data=None)

    # No purchases should be planned
    assert len(result) == 0


def test_calculate_purchase_need_gap_but_no_recommendation(mock_config):
    """Test when there's a coverage gap but no AWS recommendation."""
    from unittest.mock import Mock

    # Create mock CE client that returns empty recommendations
    mock_ce_client = Mock()
    mock_ce_client.get_savings_plans_purchase_recommendation.return_value = {
        "Metadata": {"RecommendationId": "rec-123", "LookbackPeriodInDays": "13"},
        "SavingsPlansPurchaseRecommendation": {"SavingsPlansPurchaseRecommendationDetails": []},
    }

    clients = {"ce": mock_ce_client}

    result = purchase_calculator.calculate_purchase_need(mock_config, clients, spending_data=None)

    # No purchases can be planned without recommendations
    assert len(result) == 0


def test_calculate_purchase_need_zero_commitment(mock_config):
    """Test when recommendation has zero commitment."""
    from unittest.mock import Mock

    # Create mock CE client that returns zero commitment
    mock_ce_client = Mock()
    mock_ce_client.get_savings_plans_purchase_recommendation.return_value = {
        "Metadata": {"RecommendationId": "rec-12345", "LookbackPeriodInDays": "13"},
        "SavingsPlansPurchaseRecommendation": {
            "SavingsPlansPurchaseRecommendationDetails": [{"HourlyCommitmentToPurchase": "0"}]
        },
    }

    clients = {"ce": mock_ce_client}

    result = purchase_calculator.calculate_purchase_need(mock_config, clients, spending_data=None)

    # Zero commitment should be skipped
    assert len(result) == 0


def test_calculate_purchase_need_sp_disabled(mock_config):
    """Test when SP type is disabled in config."""
    from unittest.mock import Mock

    mock_config["enable_compute_sp"] = False
    mock_config["enable_database_sp"] = False
    mock_config["enable_sagemaker_sp"] = False

    # Create mock CE client (shouldn't be called since all SPs disabled)
    mock_ce_client = Mock()

    clients = {"ce": mock_ce_client}

    result = purchase_calculator.calculate_purchase_need(mock_config, clients, spending_data=None)

    # Should not plan purchase for disabled SP types
    assert len(result) == 0
    # Verify CE client was not called at all
    assert mock_ce_client.get_savings_plans_purchase_recommendation.call_count == 0


# ============================================================================
# Apply Purchase Limits Tests
# ============================================================================


def test_apply_purchase_limits_with_limit(mock_config):
    """Test applying max_purchase_percent limit."""
    purchase_plans = [
        {
            "sp_type": "compute",
            "hourly_commitment": 10.0,
            "payment_option": "ALL_UPFRONT",
        }
    ]

    result = purchase_calculator.apply_purchase_limits(mock_config, purchase_plans)

    # 10% of 10.0 = 1.0
    assert len(result) == 1
    assert result[0]["hourly_commitment"] == 1.0


def test_apply_purchase_limits_multiple_plans(mock_config):
    """Test applying limits to multiple plans."""
    purchase_plans = [
        {
            "sp_type": "compute",
            "hourly_commitment": 10.0,
            "payment_option": "ALL_UPFRONT",
        },
        {
            "sp_type": "database",
            "hourly_commitment": 5.0,
            "payment_option": "NO_UPFRONT",
        },
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
        {
            "sp_type": "compute",
            "hourly_commitment": 5.50,
            "payment_option": "ALL_UPFRONT",
        }
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
# Error Handling Tests
# ============================================================================


def test_calculate_purchase_need_missing_strategy_type():
    """Test error when purchase_strategy_type is missing from config."""
    from unittest.mock import Mock

    config = {
        "enable_compute_sp": True,
        # Missing: purchase_strategy_type
    }
    clients = {"ce": Mock()}

    with pytest.raises(ValueError, match="Missing required configuration 'purchase_strategy_type'"):
        purchase_calculator.calculate_purchase_need(config, clients, spending_data=None)


def test_calculate_purchase_need_unknown_strategy():
    """Test error when purchase_strategy_type is not in registry."""
    from unittest.mock import Mock

    config = {
        "enable_compute_sp": True,
        "purchase_strategy_type": "nonexistent_strategy",
    }
    clients = {"ce": Mock()}

    with pytest.raises(ValueError, match="Unknown purchase strategy 'nonexistent_strategy'"):
        purchase_calculator.calculate_purchase_need(config, clients, spending_data=None)


# ============================================================================
# Split by Term Tests
# ============================================================================

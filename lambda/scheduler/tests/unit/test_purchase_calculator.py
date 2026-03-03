"""
Unit tests for purchase calculator module.

Tests the two-phase strategy pipeline (target + split) for
Compute, Database, and SageMaker Savings Plans.
"""

import purchase_calculator
import pytest


@pytest.fixture
def aws_config():
    """Config for AWS target strategy (follow_aws path)."""
    return {
        "enable_compute_sp": True,
        "enable_database_sp": True,
        "enable_sagemaker_sp": True,
        "target_strategy_type": "aws",
        "split_strategy_type": "one_shot",
        "coverage_target_percent": 90.0,
        "max_purchase_percent": 10.0,
        "min_commitment_per_plan": 0.001,
        "lookback_hours": 336,
        "compute_sp_payment_option": "ALL_UPFRONT",
        "compute_sp_term": "THREE_YEAR",
        "database_sp_payment_option": "NO_UPFRONT",
        "sagemaker_sp_payment_option": "ALL_UPFRONT",
        "sagemaker_sp_term": "THREE_YEAR",
        "savings_percentage": 30.0,
    }


@pytest.fixture
def fixed_gap_split_config():
    """Config for dynamic (prudent) target + gap_split split."""
    return {
        "enable_compute_sp": True,
        "enable_database_sp": False,
        "enable_sagemaker_sp": False,
        "target_strategy_type": "dynamic",
        "dynamic_risk_level": "prudent",
        "split_strategy_type": "gap_split",
        "coverage_target_percent": 90.0,
        "gap_split_divider": 2.0,
        "max_purchase_percent": 50.0,
        "min_purchase_percent": 1.0,
        "min_commitment_per_plan": 0.001,
        "compute_sp_payment_option": "ALL_UPFRONT",
        "compute_sp_term": "THREE_YEAR",
        "savings_percentage": 30.0,
        "lookback_hours": 336,
    }


# ============================================================================
# AWS Target Strategy Tests (follow_aws path)
# ============================================================================


def test_aws_target_compute_gap(aws_config):
    """Test AWS target with Compute SP recommendation."""
    from unittest.mock import Mock

    aws_config["enable_database_sp"] = False
    aws_config["enable_sagemaker_sp"] = False

    mock_ce_client = Mock()
    mock_ce_client.get_savings_plans_purchase_recommendation.return_value = {
        "Metadata": {"RecommendationId": "rec-12345", "LookbackPeriodInDays": "13"},
        "SavingsPlansPurchaseRecommendation": {
            "SavingsPlansPurchaseRecommendationDetails": [{"HourlyCommitmentToPurchase": "5.50"}]
        },
    }

    clients = {"ce": mock_ce_client}
    result = purchase_calculator.calculate_purchase_need(aws_config, clients, spending_data=None)

    assert len(result) == 1
    assert result[0]["sp_type"] == "compute"
    assert result[0]["hourly_commitment"] == pytest.approx(5.50)
    assert result[0]["payment_option"] == "ALL_UPFRONT"
    assert result[0]["recommendation_id"] == "rec-12345"


def test_aws_target_database_gap(aws_config):
    """Test AWS target with Database SP recommendation."""
    from unittest.mock import Mock

    aws_config["enable_compute_sp"] = False
    aws_config["enable_database_sp"] = True
    aws_config["enable_sagemaker_sp"] = False

    mock_ce_client = Mock()
    mock_ce_client.get_savings_plans_purchase_recommendation.return_value = {
        "Metadata": {"RecommendationId": "rec-db-456", "LookbackPeriodInDays": "13"},
        "SavingsPlansPurchaseRecommendation": {
            "SavingsPlansPurchaseRecommendationDetails": [{"HourlyCommitmentToPurchase": "2.75"}]
        },
    }

    clients = {"ce": mock_ce_client}
    result = purchase_calculator.calculate_purchase_need(aws_config, clients, spending_data=None)

    assert len(result) == 1
    assert result[0]["sp_type"] == "database"
    assert result[0]["hourly_commitment"] == pytest.approx(2.75)
    assert result[0]["term"] == "ONE_YEAR"
    assert result[0]["payment_option"] == "NO_UPFRONT"


def test_aws_target_multiple_types(aws_config):
    """Test AWS target with all SP types returning recommendations."""
    from unittest.mock import Mock

    mock_ce_client = Mock()

    def mock_recommendation(*args, **kwargs):
        sp_type = kwargs.get("SavingsPlansType")
        commitments = {"COMPUTE_SP": "5.50", "DATABASE_SP": "2.75", "SAGEMAKER_SP": "3.25"}
        ids = {
            "COMPUTE_SP": "rec-compute",
            "DATABASE_SP": "rec-database",
            "SAGEMAKER_SP": "rec-sagemaker",
        }
        return {
            "Metadata": {"RecommendationId": ids[sp_type], "LookbackPeriodInDays": "13"},
            "SavingsPlansPurchaseRecommendation": {
                "SavingsPlansPurchaseRecommendationDetails": [
                    {"HourlyCommitmentToPurchase": commitments[sp_type]}
                ]
            },
        }

    mock_ce_client.get_savings_plans_purchase_recommendation.side_effect = mock_recommendation
    clients = {"ce": mock_ce_client}

    result = purchase_calculator.calculate_purchase_need(aws_config, clients, spending_data=None)

    assert len(result) == 3
    sp_types = [plan["sp_type"] for plan in result]
    assert "compute" in sp_types
    assert "database" in sp_types
    assert "sagemaker" in sp_types


def test_aws_target_no_recommendation(aws_config):
    """Test AWS target when no recommendations available."""
    from unittest.mock import Mock

    mock_ce_client = Mock()
    mock_ce_client.get_savings_plans_purchase_recommendation.return_value = {
        "Metadata": {"RecommendationId": "rec-123", "LookbackPeriodInDays": "13"},
        "SavingsPlansPurchaseRecommendation": {"SavingsPlansPurchaseRecommendationDetails": []},
    }

    clients = {"ce": mock_ce_client}
    result = purchase_calculator.calculate_purchase_need(aws_config, clients, spending_data=None)
    assert len(result) == 0


def test_hourly_commitment_rounded_to_5_decimals_aws(aws_config):
    """AWS enforces max 5 decimal places on hourly commitment."""
    from unittest.mock import Mock

    aws_config["enable_database_sp"] = False
    aws_config["enable_sagemaker_sp"] = False

    mock_ce_client = Mock()
    mock_ce_client.get_savings_plans_purchase_recommendation.return_value = {
        "Metadata": {"RecommendationId": "rec-round", "LookbackPeriodInDays": "13"},
        "SavingsPlansPurchaseRecommendation": {
            "SavingsPlansPurchaseRecommendationDetails": [
                {"HourlyCommitmentToPurchase": "6.398646667453034"}
            ]
        },
    }

    clients = {"ce": mock_ce_client}
    result = purchase_calculator.calculate_purchase_need(aws_config, clients, spending_data=None)

    assert len(result) == 1
    commitment = result[0]["hourly_commitment"]
    decimals = str(commitment).split(".")[1] if "." in str(commitment) else ""
    assert len(decimals) <= 5


def test_hourly_commitment_rounded_to_5_decimals_fixed(fixed_gap_split_config):
    """Fixed strategy path also rounds to 5 decimal places."""
    from unittest.mock import Mock

    spending_data = {
        "compute": {
            "summary": {
                "avg_coverage_total": 50.0,
                "avg_hourly_total": 7.123456789,
                "avg_hourly_covered": 3.5,
            }
        }
    }

    clients = {"ce": Mock(), "savingsplans": Mock()}
    result = purchase_calculator.calculate_purchase_need(
        fixed_gap_split_config, clients, spending_data
    )

    assert len(result) == 1
    commitment = result[0]["hourly_commitment"]
    decimals = str(commitment).split(".")[1] if "." in str(commitment) else ""
    assert len(decimals) <= 5


def test_aws_target_sp_disabled(aws_config):
    """Test AWS target when all SP types disabled."""
    from unittest.mock import Mock

    aws_config["enable_compute_sp"] = False
    aws_config["enable_database_sp"] = False
    aws_config["enable_sagemaker_sp"] = False

    mock_ce_client = Mock()
    clients = {"ce": mock_ce_client}

    result = purchase_calculator.calculate_purchase_need(aws_config, clients, spending_data=None)
    assert len(result) == 0
    assert mock_ce_client.get_savings_plans_purchase_recommendation.call_count == 0


# ============================================================================
# Error Handling Tests
# ============================================================================


def test_missing_target_strategy_type():
    """Test error when target_strategy_type is missing."""
    from unittest.mock import Mock

    config = {"enable_compute_sp": True}
    clients = {"ce": Mock()}

    with pytest.raises(KeyError, match="target_strategy_type"):
        purchase_calculator.calculate_purchase_need(config, clients, spending_data=None)


# ============================================================================
# Fixed Target + Gap Split Split Tests
# ============================================================================


def test_fixed_gap_split_basic(fixed_gap_split_config):
    """Test fixed target + gap_split split with 50% current coverage."""
    from unittest.mock import Mock

    spending_data = {
        "compute": {
            "summary": {
                "avg_coverage_total": 50.0,
                "avg_hourly_total": 10.0,
                "avg_hourly_covered": 5.0,
            }
        }
    }

    clients = {"ce": Mock(), "savingsplans": Mock()}
    result = purchase_calculator.calculate_purchase_need(
        fixed_gap_split_config, clients, spending_data
    )

    # gap=40, divider=2 → 20.0
    # commitment = avg_hourly(10) * purchase_pct(20%) * (1 - savings(30%)) = 1.4
    assert len(result) == 1
    assert result[0]["sp_type"] == "compute"
    assert result[0]["strategy"] == "dynamic+gap_split"
    assert result[0]["purchase_percent"] == pytest.approx(20.0)
    assert result[0]["hourly_commitment"] == pytest.approx(1.4, abs=0.1)


def test_fixed_gap_split_from_zero(fixed_gap_split_config):
    """Test fixed target + gap_split split from zero coverage."""
    from unittest.mock import Mock

    spending_data = {
        "compute": {
            "summary": {
                "avg_coverage_total": 0.0,
                "avg_hourly_total": 100.0,
                "avg_hourly_covered": 0.0,
            }
        }
    }

    clients = {"ce": Mock(), "savingsplans": Mock()}
    result = purchase_calculator.calculate_purchase_need(
        fixed_gap_split_config, clients, spending_data
    )

    # gap=90, divider=2 → 45.0
    # commitment = avg_hourly(100) * purchase_pct(45%) * (1 - savings(30%)) = 31.5
    assert len(result) == 1
    assert result[0]["purchase_percent"] == pytest.approx(45.0)
    assert result[0]["hourly_commitment"] == pytest.approx(31.5, abs=0.1)


def test_fixed_gap_split_near_target(fixed_gap_split_config):
    """Test fixed target + gap_split split near target coverage."""
    from unittest.mock import Mock

    spending_data = {
        "compute": {
            "summary": {
                "avg_coverage_total": 87.5,
                "avg_hourly_total": 100.0,
                "avg_hourly_covered": 87.5,
            }
        }
    }

    clients = {"ce": Mock(), "savingsplans": Mock()}
    result = purchase_calculator.calculate_purchase_need(
        fixed_gap_split_config, clients, spending_data
    )

    # gap=2.5, divider=2 → 1.2 (rounds to 1.2), min=1 so 1.2 is fine
    # commitment = avg_hourly(100) * purchase_pct(1.2%) * (1 - savings(30%)) = 0.84
    assert len(result) == 1
    assert result[0]["purchase_percent"] == pytest.approx(1.2, abs=0.1)
    assert result[0]["hourly_commitment"] == pytest.approx(0.84, abs=0.1)


def test_fixed_gap_split_at_target(fixed_gap_split_config):
    """Test fixed target + gap_split split when already at target."""
    from unittest.mock import Mock

    spending_data = {
        "compute": {
            "summary": {
                "avg_coverage_total": 90.0,
                "avg_hourly_total": 100.0,
                "avg_hourly_covered": 90.0,
            }
        }
    }

    clients = {"ce": Mock(), "savingsplans": Mock()}
    result = purchase_calculator.calculate_purchase_need(
        fixed_gap_split_config, clients, spending_data
    )
    assert len(result) == 0


def test_fixed_gap_split_multiple_sp_types():
    """Test dynamic (prudent) target + gap_split split with multiple SP types."""
    from unittest.mock import Mock

    config = {
        "enable_compute_sp": True,
        "enable_database_sp": True,
        "enable_sagemaker_sp": True,
        "target_strategy_type": "dynamic",
        "dynamic_risk_level": "prudent",
        "split_strategy_type": "gap_split",
        "coverage_target_percent": 90.0,
        "gap_split_divider": 2.0,
        "max_purchase_percent": 50.0,
        "min_purchase_percent": 1.0,
        "min_commitment_per_plan": 0.001,
        "compute_sp_payment_option": "ALL_UPFRONT",
        "compute_sp_term": "THREE_YEAR",
        "database_sp_payment_option": "NO_UPFRONT",
        "sagemaker_sp_payment_option": "ALL_UPFRONT",
        "sagemaker_sp_term": "THREE_YEAR",
        "savings_percentage": 30.0,
        "lookback_hours": 336,
    }

    spending_data = {
        "compute": {
            "summary": {
                "avg_coverage_total": 50.0,
                "avg_hourly_total": 100.0,
                "avg_hourly_covered": 50.0,
            }
        },
        "database": {
            "summary": {
                "avg_coverage_total": 75.0,
                "avg_hourly_total": 50.0,
                "avg_hourly_covered": 37.5,
            }
        },
        "sagemaker": {
            "summary": {
                "avg_coverage_total": 0.0,
                "avg_hourly_total": 20.0,
                "avg_hourly_covered": 0.0,
            }
        },
    }

    clients = {"ce": Mock(), "savingsplans": Mock()}
    result = purchase_calculator.calculate_purchase_need(config, clients, spending_data)

    assert len(result) == 3

    compute_plan = [p for p in result if p["sp_type"] == "compute"][0]
    assert compute_plan["purchase_percent"] == pytest.approx(20.0)

    database_plan = [p for p in result if p["sp_type"] == "database"][0]
    assert database_plan["purchase_percent"] == pytest.approx(7.5)
    assert database_plan["term"] == "ONE_YEAR"

    sagemaker_plan = [p for p in result if p["sp_type"] == "sagemaker"][0]
    assert sagemaker_plan["purchase_percent"] == pytest.approx(45.0)


# ============================================================================
# Fixed Target + Fixed Step Split Tests
# ============================================================================


def test_fixed_fixed_step_basic():
    """Test dynamic (prudent) target + fixed_step split."""
    from unittest.mock import Mock

    config = {
        "enable_compute_sp": True,
        "enable_database_sp": False,
        "enable_sagemaker_sp": False,
        "target_strategy_type": "dynamic",
        "dynamic_risk_level": "prudent",
        "split_strategy_type": "fixed_step",
        "coverage_target_percent": 90.0,
        "fixed_step_percent": 10.0,
        "max_purchase_percent": 10.0,
        "min_commitment_per_plan": 0.001,
        "compute_sp_payment_option": "ALL_UPFRONT",
        "compute_sp_term": "THREE_YEAR",
        "savings_percentage": 30.0,
        "lookback_hours": 336,
    }

    spending_data = {
        "compute": {
            "summary": {
                "avg_coverage_total": 50.0,
                "avg_hourly_total": 100.0,
                "avg_hourly_covered": 50.0,
            }
        }
    }

    clients = {"ce": Mock(), "savingsplans": Mock()}
    result = purchase_calculator.calculate_purchase_need(config, clients, spending_data)

    # Gap is 40%, step is 10% → purchase 10%
    # commitment = avg_hourly(100) * purchase_pct(10%) * (1 - savings(30%)) = 7
    assert len(result) == 1
    assert result[0]["strategy"] == "dynamic+fixed_step"
    assert result[0]["purchase_percent"] == pytest.approx(10.0)
    assert result[0]["hourly_commitment"] == pytest.approx(7.0)

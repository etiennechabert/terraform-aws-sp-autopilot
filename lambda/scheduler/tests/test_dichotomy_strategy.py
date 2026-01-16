"""
Unit tests for dichotomy_strategy module.

Tests the dichotomy purchase strategy algorithm and integration with purchase planning.
"""

import pytest
from dichotomy_strategy import (
    calculate_dichotomy_purchase_percent,
    calculate_purchase_need_dichotomy,
)


class TestCalculateDichotomyPurchasePercent:
    """Test the core dichotomy algorithm for calculating purchase percentage."""

    def test_large_gap_uses_max_purchase_percent(self):
        """Test that large coverage gap uses max_purchase_percent."""
        # Gap is 90%, max is 50% -> should use 50%
        result = calculate_dichotomy_purchase_percent(90.0, 50.0, 1.0)
        assert result == 50.0

    def test_gap_smaller_than_max_triggers_halving(self):
        """Test that gap smaller than max triggers halving."""
        # Gap is 40%, max is 50% -> should halve to 25%
        result = calculate_dichotomy_purchase_percent(40.0, 50.0, 1.0)
        assert result == 25.0

        # Gap is 20%, max is 50% -> should halve to 25% then 12.5%
        result = calculate_dichotomy_purchase_percent(20.0, 50.0, 1.0)
        assert result == 12.5

        # Gap is 10%, max is 50% -> should halve to 25%, 12.5%, 6.25%
        result = calculate_dichotomy_purchase_percent(10.0, 50.0, 1.0)
        assert result == 6.25

    def test_very_small_gap_uses_exact_gap(self):
        """Test that very small gap uses exact gap amount."""
        # Gap is 2.5%, max is 50% -> halve to 25%, 12.5%, 6.25%, 3.125%, then use exact gap
        result = calculate_dichotomy_purchase_percent(2.5, 50.0, 1.0)
        assert result == 2.5

        # Gap is 0.8%, max is 50% -> use exact gap
        result = calculate_dichotomy_purchase_percent(0.8, 50.0, 1.0)
        assert result == 0.8

    def test_gap_below_min_purchase_percent(self):
        """Test behavior when gap is below min_purchase_percent."""
        # Gap is 0.5%, min is 1.0% -> should use exact gap (0.5%)
        result = calculate_dichotomy_purchase_percent(0.5, 50.0, 1.0)
        assert result == 0.5

    def test_edge_case_gap_equals_max(self):
        """Test edge case where gap exactly equals max."""
        # Gap is 50%, max is 50% -> should use 50%
        result = calculate_dichotomy_purchase_percent(50.0, 50.0, 1.0)
        assert result == 50.0

    def test_edge_case_gap_equals_halved_max(self):
        """Test edge case where gap exactly equals halved max."""
        # Gap is 25%, max is 50% -> should halve to 25%
        result = calculate_dichotomy_purchase_percent(25.0, 50.0, 1.0)
        assert result == 25.0

    def test_different_max_purchase_percents(self):
        """Test with different max_purchase_percent values."""
        # Max 100%
        # Gap 90%: Next power-of-2 would be 50, which is >= min*2, so use it
        assert calculate_dichotomy_purchase_percent(90.0, 100.0, 1.0) == 50.0
        assert calculate_dichotomy_purchase_percent(60.0, 100.0, 1.0) == 50.0
        assert calculate_dichotomy_purchase_percent(30.0, 100.0, 1.0) == 25.0

        # Max 25%
        assert calculate_dichotomy_purchase_percent(30.0, 25.0, 1.0) == 25.0
        assert calculate_dichotomy_purchase_percent(15.0, 25.0, 1.0) == 12.5
        assert calculate_dichotomy_purchase_percent(8.0, 25.0, 1.0) == 6.25

    def test_different_min_purchase_percents(self):
        """Test with different min_purchase_percent values."""
        # Min 5%: Gap 10%, next would be 6.25, which is < min*2 (10), so use gap
        assert calculate_dichotomy_purchase_percent(10.0, 50.0, 5.0) == 10.0
        assert calculate_dichotomy_purchase_percent(4.0, 50.0, 5.0) == 4.0

        # Min 0.1%: Gap 0.5%, next would be 0.390625, which is >= min*2 (0.2), so use next
        assert calculate_dichotomy_purchase_percent(0.5, 50.0, 0.1) == 0.390625
        assert calculate_dichotomy_purchase_percent(0.05, 50.0, 0.1) == 0.05

    def test_progression_sequence(self):
        """Test the expected progression sequence from 0% to 90% coverage."""
        # Simulate monthly purchases with target 90%, max 50%
        # Month 1: Gap 90% -> Purchase 50%
        assert calculate_dichotomy_purchase_percent(90.0, 50.0, 1.0) == 50.0

        # Month 2: Gap 40% (after 50% coverage) -> Purchase 25%
        assert calculate_dichotomy_purchase_percent(40.0, 50.0, 1.0) == 25.0

        # Month 3: Gap 15% (after 75% coverage) -> Purchase 12.5%
        assert calculate_dichotomy_purchase_percent(15.0, 50.0, 1.0) == 12.5

        # Month 4: Gap 2.5% (after 87.5% coverage) -> Purchase 2.5%
        assert calculate_dichotomy_purchase_percent(2.5, 50.0, 1.0) == 2.5


class TestCalculatePurchaseNeedDichotomy:
    """Test the integration of dichotomy strategy with purchase planning."""

    def test_compute_sp_large_gap(self):
        """Test Compute SP purchase with large coverage gap."""
        config = {
            "enable_compute_sp": True,
            "enable_database_sp": False,
            "enable_sagemaker_sp": False,
            "coverage_target_percent": 90.0,
            "max_purchase_percent": 50.0,
            "min_purchase_percent": 1.0,
            "compute_sp_payment_option": "ALL_UPFRONT",
        }
        coverage = {"compute": 0.0}
        recommendations = {
            "compute": {
                "HourlyCommitmentToPurchase": "10.00",
                "RecommendationId": "rec-123",
            }
        }

        result = calculate_purchase_need_dichotomy(config, coverage, recommendations)

        assert len(result) == 1
        assert result[0]["sp_type"] == "compute"
        assert result[0]["hourly_commitment"] == 5.0  # 50% of $10
        assert result[0]["payment_option"] == "ALL_UPFRONT"
        assert result[0]["strategy"] == "dichotomy"
        assert result[0]["purchase_percent"] == 50.0

    def test_compute_sp_medium_gap(self):
        """Test Compute SP purchase with medium coverage gap."""
        config = {
            "enable_compute_sp": True,
            "enable_database_sp": False,
            "enable_sagemaker_sp": False,
            "coverage_target_percent": 90.0,
            "max_purchase_percent": 50.0,
            "min_purchase_percent": 1.0,
            "compute_sp_payment_option": "ALL_UPFRONT",
        }
        coverage = {"compute": 50.0}  # Already have 50% coverage
        recommendations = {
            "compute": {
                "HourlyCommitmentToPurchase": "8.00",
                "RecommendationId": "rec-456",
            }
        }

        result = calculate_purchase_need_dichotomy(config, coverage, recommendations)

        assert len(result) == 1
        # Gap is 40%, so purchase percent should be 25%
        assert result[0]["hourly_commitment"] == 2.0  # 25% of $8
        assert result[0]["purchase_percent"] == 25.0

    def test_compute_sp_small_gap(self):
        """Test Compute SP purchase with small coverage gap."""
        config = {
            "enable_compute_sp": True,
            "enable_database_sp": False,
            "enable_sagemaker_sp": False,
            "coverage_target_percent": 90.0,
            "max_purchase_percent": 50.0,
            "min_purchase_percent": 1.0,
            "compute_sp_payment_option": "ALL_UPFRONT",
        }
        coverage = {"compute": 87.5}  # Already have 87.5% coverage
        recommendations = {
            "compute": {
                "HourlyCommitmentToPurchase": "5.00",
                "RecommendationId": "rec-789",
            }
        }

        result = calculate_purchase_need_dichotomy(config, coverage, recommendations)

        assert len(result) == 1
        # Gap is 2.5%, so purchase percent should be 2.5% (exact gap)
        assert result[0]["hourly_commitment"] == pytest.approx(0.125, rel=1e-3)  # 2.5% of $5
        assert result[0]["purchase_percent"] == 2.5

    def test_database_sp_purchase(self):
        """Test Database SP purchase with dichotomy strategy."""
        config = {
            "enable_compute_sp": False,
            "enable_database_sp": True,
            "enable_sagemaker_sp": False,
            "coverage_target_percent": 90.0,
            "max_purchase_percent": 50.0,
            "min_purchase_percent": 1.0,
        }
        coverage = {"database": 0.0}
        recommendations = {
            "database": {
                "HourlyCommitmentToPurchase": "15.00",
                "RecommendationId": "rec-db-123",
            }
        }

        result = calculate_purchase_need_dichotomy(config, coverage, recommendations)

        assert len(result) == 1
        assert result[0]["sp_type"] == "database"
        assert result[0]["hourly_commitment"] == 7.5  # 50% of $15
        assert result[0]["term"] == "ONE_YEAR"
        assert result[0]["payment_option"] == "NO_UPFRONT"
        assert result[0]["strategy"] == "dichotomy"
        assert result[0]["purchase_percent"] == 50.0

    def test_sagemaker_sp_purchase(self):
        """Test SageMaker SP purchase with dichotomy strategy."""
        config = {
            "enable_compute_sp": False,
            "enable_database_sp": False,
            "enable_sagemaker_sp": True,
            "coverage_target_percent": 90.0,
            "max_purchase_percent": 50.0,
            "min_purchase_percent": 1.0,
            "sagemaker_sp_payment_option": "PARTIAL_UPFRONT",
        }
        coverage = {"sagemaker": 30.0}
        recommendations = {
            "sagemaker": {
                "HourlyCommitmentToPurchase": "20.00",
                "RecommendationId": "rec-sm-123",
            }
        }

        result = calculate_purchase_need_dichotomy(config, coverage, recommendations)

        assert len(result) == 1
        assert result[0]["sp_type"] == "sagemaker"
        # Gap is 60%, so purchase percent should be 50%
        assert result[0]["hourly_commitment"] == 10.0  # 50% of $20
        assert result[0]["payment_option"] == "PARTIAL_UPFRONT"
        assert result[0]["purchase_percent"] == 50.0

    def test_multiple_sp_types_enabled(self):
        """Test multiple SP types enabled simultaneously."""
        config = {
            "enable_compute_sp": True,
            "enable_database_sp": True,
            "enable_sagemaker_sp": True,
            "coverage_target_percent": 90.0,
            "max_purchase_percent": 50.0,
            "min_purchase_percent": 1.0,
            "compute_sp_payment_option": "ALL_UPFRONT",
            "sagemaker_sp_payment_option": "ALL_UPFRONT",
        }
        coverage = {
            "compute": 50.0,  # Gap: 40% -> purchase 25%
            "database": 0.0,  # Gap: 90% -> purchase 50%
            "sagemaker": 75.0,  # Gap: 15% -> purchase 12.5%
        }
        recommendations = {
            "compute": {"HourlyCommitmentToPurchase": "10.00", "RecommendationId": "rec-c"},
            "database": {"HourlyCommitmentToPurchase": "5.00", "RecommendationId": "rec-d"},
            "sagemaker": {"HourlyCommitmentToPurchase": "8.00", "RecommendationId": "rec-s"},
        }

        result = calculate_purchase_need_dichotomy(config, coverage, recommendations)

        assert len(result) == 3

        # Find each plan by sp_type
        compute_plan = next(p for p in result if p["sp_type"] == "compute")
        database_plan = next(p for p in result if p["sp_type"] == "database")
        sagemaker_plan = next(p for p in result if p["sp_type"] == "sagemaker")

        # Compute: 25% of $10 = $2.50
        assert compute_plan["hourly_commitment"] == 2.5
        assert compute_plan["purchase_percent"] == 25.0

        # Database: 50% of $5 = $2.50
        assert database_plan["hourly_commitment"] == 2.5
        assert database_plan["purchase_percent"] == 50.0

        # SageMaker: 12.5% of $8 = $1.00
        assert sagemaker_plan["hourly_commitment"] == 1.0
        assert sagemaker_plan["purchase_percent"] == 12.5

    def test_no_purchase_when_coverage_exceeds_target(self):
        """Test that no purchase is made when coverage exceeds target."""
        config = {
            "enable_compute_sp": True,
            "enable_database_sp": False,
            "enable_sagemaker_sp": False,
            "coverage_target_percent": 90.0,
            "max_purchase_percent": 50.0,
            "min_purchase_percent": 1.0,
        }
        coverage = {"compute": 95.0}  # Already exceeds target
        recommendations = {
            "compute": {"HourlyCommitmentToPurchase": "10.00", "RecommendationId": "rec-123"}
        }

        result = calculate_purchase_need_dichotomy(config, coverage, recommendations)

        assert len(result) == 0

    def test_no_purchase_when_no_recommendation(self):
        """Test that no purchase is made when AWS has no recommendation."""
        config = {
            "enable_compute_sp": True,
            "enable_database_sp": False,
            "enable_sagemaker_sp": False,
            "coverage_target_percent": 90.0,
            "max_purchase_percent": 50.0,
            "min_purchase_percent": 1.0,
        }
        coverage = {"compute": 50.0}
        recommendations = {}  # No recommendation available

        result = calculate_purchase_need_dichotomy(config, coverage, recommendations)

        assert len(result) == 0

    def test_no_purchase_when_recommendation_is_zero(self):
        """Test that no purchase is made when AWS recommendation is zero."""
        config = {
            "enable_compute_sp": True,
            "enable_database_sp": False,
            "enable_sagemaker_sp": False,
            "coverage_target_percent": 90.0,
            "max_purchase_percent": 50.0,
            "min_purchase_percent": 1.0,
        }
        coverage = {"compute": 50.0}
        recommendations = {
            "compute": {"HourlyCommitmentToPurchase": "0.00", "RecommendationId": "rec-123"}
        }

        result = calculate_purchase_need_dichotomy(config, coverage, recommendations)

        assert len(result) == 0

    def test_different_max_purchase_percents_in_integration(self):
        """Test integration with different max_purchase_percent values."""
        base_config = {
            "enable_compute_sp": True,
            "enable_database_sp": False,
            "enable_sagemaker_sp": False,
            "coverage_target_percent": 90.0,
            "min_purchase_percent": 1.0,
            "compute_sp_payment_option": "ALL_UPFRONT",
        }
        coverage = {"compute": 0.0}  # Gap: 90%
        recommendations = {
            "compute": {"HourlyCommitmentToPurchase": "10.00", "RecommendationId": "rec-123"}
        }

        # Max 100%: Gap 90%, next power-of-2 is 50%
        config_100 = {**base_config, "max_purchase_percent": 100.0}
        result = calculate_purchase_need_dichotomy(config_100, coverage, recommendations)
        assert result[0]["hourly_commitment"] == 5.0  # 50% of $10
        assert result[0]["purchase_percent"] == 50.0

        # Max 25%
        config_25 = {**base_config, "max_purchase_percent": 25.0}
        result = calculate_purchase_need_dichotomy(config_25, coverage, recommendations)
        assert result[0]["hourly_commitment"] == 2.5  # 25% of $10
        assert result[0]["purchase_percent"] == 25.0

    def test_progression_simulation(self):
        """Test a simulated progression from 0% to 90% coverage."""
        config = {
            "enable_compute_sp": True,
            "enable_database_sp": False,
            "enable_sagemaker_sp": False,
            "coverage_target_percent": 90.0,
            "max_purchase_percent": 50.0,
            "min_purchase_percent": 1.0,
            "compute_sp_payment_option": "ALL_UPFRONT",
        }
        recommendations = {
            "compute": {"HourlyCommitmentToPurchase": "100.00", "RecommendationId": "rec-123"}
        }

        # Month 1: Coverage 0%, Gap 90%
        result = calculate_purchase_need_dichotomy(
            config, {"compute": 0.0}, recommendations
        )
        assert result[0]["purchase_percent"] == 50.0
        assert result[0]["hourly_commitment"] == 50.0

        # Month 2: Coverage 50%, Gap 40%
        result = calculate_purchase_need_dichotomy(
            config, {"compute": 50.0}, recommendations
        )
        assert result[0]["purchase_percent"] == 25.0
        assert result[0]["hourly_commitment"] == 25.0

        # Month 3: Coverage 75%, Gap 15%
        result = calculate_purchase_need_dichotomy(
            config, {"compute": 75.0}, recommendations
        )
        assert result[0]["purchase_percent"] == 12.5
        assert result[0]["hourly_commitment"] == 12.5

        # Month 4: Coverage 87.5%, Gap 2.5%
        result = calculate_purchase_need_dichotomy(
            config, {"compute": 87.5}, recommendations
        )
        assert result[0]["purchase_percent"] == 2.5
        assert result[0]["hourly_commitment"] == 2.5

        # Month 5: Coverage 90%, Gap 0% (target reached)
        result = calculate_purchase_need_dichotomy(
            config, {"compute": 90.0}, recommendations
        )
        assert len(result) == 0

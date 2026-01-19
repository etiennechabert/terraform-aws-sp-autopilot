"""
Unit tests for dichotomy_strategy module.

Tests the dichotomy purchase strategy algorithm and integration with purchase planning.
"""

from dichotomy_strategy import (
    calculate_dichotomy_purchase_percent,
    calculate_purchase_need_dichotomy,
)


class TestCalculateDichotomyPurchasePercent:
    """Test the core dichotomy algorithm for calculating purchase percentage."""

    def test_large_gap_uses_max_purchase_percent(self):
        """Test that when at 0% coverage, we can use max."""
        # At 0%, target 90%, max 50% -> 0% + 50% = 50% <= 90%, use 50%
        result = calculate_dichotomy_purchase_percent(0.0, 90.0, 50.0, 1.0)
        assert result == 50.0

    def test_at_50_percent_coverage(self):
        """Test user's example: at 50% coverage, try 50%, then 25%."""
        # At 50%, target 90%, max 50%
        # Try 50%: 50% + 50% = 100% > 90%, NO
        # Try 25%: 50% + 25% = 75% <= 90%, YES
        result = calculate_dichotomy_purchase_percent(50.0, 90.0, 50.0, 1.0)
        assert result == 25.0

    def test_at_75_percent_coverage(self):
        """Test user's example: at 75%, try 50%, 25%, then 12.5%."""
        # At 75%, target 90%, max 50%
        # Try 50%: 75% + 50% = 125% > 90%, NO
        # Try 25%: 75% + 25% = 100% > 90%, NO
        # Try 12.5%: 75% + 12.5% = 87.5% <= 90%, YES
        result = calculate_dichotomy_purchase_percent(75.0, 90.0, 50.0, 1.0)
        assert result == 12.5

    def test_at_87_5_percent_coverage(self):
        """Test at 87.5% coverage."""
        # At 87.5%, target 90%, max 50%, min 1%
        # Keep halving: 50 -> 25 -> 12.5 -> 6.25 -> 3.125 -> 1.5625
        # Round to 1 decimal: 1.5625% -> 1.6%
        result = calculate_dichotomy_purchase_percent(87.5, 90.0, 50.0, 1.0)
        assert result == 1.6

    def test_gap_below_min_purchase_percent(self):
        """Test behavior when gap is below min_purchase_percent."""
        # At 89.5%, target 90%, gap is 0.5% < min 1% -> still buy min 1%
        # This overshoots to 90.5% but that's OK (max_coverage_cap protects us)
        result = calculate_dichotomy_purchase_percent(89.5, 90.0, 50.0, 1.0)
        assert result == 1.0

    def test_edge_case_at_target(self):
        """Test when already at target."""
        # At 90%, target 90%, gap is 0%
        result = calculate_dichotomy_purchase_percent(90.0, 90.0, 50.0, 1.0)
        assert result == 0.0

    def test_different_max_purchase_percents(self):
        """Test with different max_purchase_percent values."""
        # At 50%, target 90%, max 100%
        # Try 100%: 50 + 100 = 150 > 90, try 50: 50 + 50 = 100 > 90, try 25: 50 + 25 = 75 <= 90
        assert calculate_dichotomy_purchase_percent(50.0, 90.0, 100.0, 1.0) == 25.0

        # At 50%, target 90%, max 25%
        # Try 25%: 50 + 25 = 75 <= 90, use 25%
        assert calculate_dichotomy_purchase_percent(50.0, 90.0, 25.0, 1.0) == 25.0

    def test_different_targets(self):
        """Test with different target coverage values."""
        # At 50%, target 80%, max 50%
        # Try 50%: 50 + 50 = 100 > 80, try 25%: 50 + 25 = 75 <= 80
        assert calculate_dichotomy_purchase_percent(50.0, 80.0, 50.0, 1.0) == 25.0

        # At 50%, target 60%, max 50%
        # Try 50%: 50 + 50 = 100 > 60, try 25%: 50 + 25 = 75 > 60, try 12.5%: 50 + 12.5 = 62.5 > 60
        # try 6.25%: 50 + 6.25 = 56.25 <= 60, round to 6.2%
        assert calculate_dichotomy_purchase_percent(50.0, 60.0, 50.0, 1.0) == 6.2

    def test_progression_sequence(self):
        """Test the expected progression sequence from 0% to 90% coverage."""
        # Month 1: At 0%, target 90% -> 0 + 50 = 50 <= 90, use 50%
        assert calculate_dichotomy_purchase_percent(0.0, 90.0, 50.0, 1.0) == 50.0

        # Month 2: At 50%, target 90% -> 50 + 25 = 75 <= 90, use 25%
        assert calculate_dichotomy_purchase_percent(50.0, 90.0, 50.0, 1.0) == 25.0

        # Month 3: At 75%, target 90% -> 75 + 12.5 = 87.5 <= 90, use 12.5%
        assert calculate_dichotomy_purchase_percent(75.0, 90.0, 50.0, 1.0) == 12.5

        # Month 4: At 87.5%, target 90% -> halve to 1.5625% -> round to 1.6%
        assert calculate_dichotomy_purchase_percent(87.5, 90.0, 50.0, 1.0) == 1.6


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
        # At 87.5%, target 90%, halve to 1.5625% -> round to 1.6%
        assert result[0]["hourly_commitment"] == 0.08  # 1.6% of $5
        assert result[0]["purchase_percent"] == 1.6

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
            "compute": {
                "HourlyCommitmentToPurchase": "10.00",
                "RecommendationId": "rec-c",
            },
            "database": {
                "HourlyCommitmentToPurchase": "5.00",
                "RecommendationId": "rec-d",
            },
            "sagemaker": {
                "HourlyCommitmentToPurchase": "8.00",
                "RecommendationId": "rec-s",
            },
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
            "compute": {
                "HourlyCommitmentToPurchase": "10.00",
                "RecommendationId": "rec-123",
            }
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
            "compute": {
                "HourlyCommitmentToPurchase": "0.00",
                "RecommendationId": "rec-123",
            }
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
            "compute": {
                "HourlyCommitmentToPurchase": "10.00",
                "RecommendationId": "rec-123",
            }
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
            "compute": {
                "HourlyCommitmentToPurchase": "100.00",
                "RecommendationId": "rec-123",
            }
        }

        # Month 1: Coverage 0%, Gap 90%
        result = calculate_purchase_need_dichotomy(config, {"compute": 0.0}, recommendations)
        assert result[0]["purchase_percent"] == 50.0
        assert result[0]["hourly_commitment"] == 50.0

        # Month 2: Coverage 50%, Gap 40%
        result = calculate_purchase_need_dichotomy(config, {"compute": 50.0}, recommendations)
        assert result[0]["purchase_percent"] == 25.0
        assert result[0]["hourly_commitment"] == 25.0

        # Month 3: Coverage 75%, Gap 15%
        result = calculate_purchase_need_dichotomy(config, {"compute": 75.0}, recommendations)
        assert result[0]["purchase_percent"] == 12.5
        assert result[0]["hourly_commitment"] == 12.5

        # Month 4: Coverage 87.5%, gap 2.5%, halve to 1.5625% -> round to 1.6%
        result = calculate_purchase_need_dichotomy(config, {"compute": 87.5}, recommendations)
        assert result[0]["purchase_percent"] == 1.6
        assert result[0]["hourly_commitment"] == 1.6

        # Month 5: Coverage 88.5%, gap 1.5%, halve to 0.78125% < min -> use min 1.0%
        result = calculate_purchase_need_dichotomy(config, {"compute": 88.5}, recommendations)
        assert result[0]["purchase_percent"] == 1.0
        assert result[0]["hourly_commitment"] == 1.0

        # Month 6: Coverage 89.5%, gap 0.5% < min -> buy min 1% (overshoots to 90.5%)
        result = calculate_purchase_need_dichotomy(config, {"compute": 89.5}, recommendations)
        assert result[0]["purchase_percent"] == 1.0
        assert result[0]["hourly_commitment"] == 1.0

        # Month 7: Coverage 90.5%, Gap -0.5% (target exceeded)
        result = calculate_purchase_need_dichotomy(config, {"compute": 90.5}, recommendations)
        assert len(result) == 0

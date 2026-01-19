"""
Unit tests for conservative_strategy module.

Tests the conservative purchase strategy which only purchases when
the coverage gap exceeds a minimum threshold, reducing churn for
stable workloads.
"""

from conservative_strategy import calculate_purchase_need_conservative


class TestCalculatePurchaseNeedConservative:
    """Test the conservative strategy for purchase planning."""

    def test_compute_sp_gap_above_threshold(self):
        """Test Compute SP purchase when gap is above threshold."""
        config = {
            "enable_compute_sp": True,
            "enable_database_sp": False,
            "enable_sagemaker_sp": False,
            "coverage_target_percent": 90.0,
            "min_gap_threshold": 5.0,
            "max_purchase_percent": 50.0,
            "compute_sp_payment_option": "ALL_UPFRONT",
        }
        coverage = {"compute": 70.0}  # Gap is 20%, above 5% threshold
        recommendations = {
            "compute": {
                "HourlyCommitmentToPurchase": "10.00",
                "RecommendationId": "rec-123",
            }
        }

        result = calculate_purchase_need_conservative(config, coverage, recommendations)

        assert len(result) == 1
        assert result[0]["sp_type"] == "compute"
        assert result[0]["hourly_commitment"] == 5.0  # 50% of $10
        assert result[0]["payment_option"] == "ALL_UPFRONT"
        assert result[0]["recommendation_id"] == "rec-123"
        assert result[0]["strategy"] == "conservative"
        assert result[0]["purchase_percent"] == 50.0

    def test_compute_sp_gap_below_threshold(self):
        """Test no purchase when gap is below threshold."""
        config = {
            "enable_compute_sp": True,
            "enable_database_sp": False,
            "enable_sagemaker_sp": False,
            "coverage_target_percent": 90.0,
            "min_gap_threshold": 5.0,
            "max_purchase_percent": 50.0,
        }
        coverage = {"compute": 88.0}  # Gap is 2%, below 5% threshold
        recommendations = {
            "compute": {
                "HourlyCommitmentToPurchase": "10.00",
                "RecommendationId": "rec-123",
            }
        }

        result = calculate_purchase_need_conservative(config, coverage, recommendations)

        assert len(result) == 0

    def test_compute_sp_gap_exactly_at_threshold(self):
        """Test purchase when gap is exactly at threshold."""
        config = {
            "enable_compute_sp": True,
            "enable_database_sp": False,
            "enable_sagemaker_sp": False,
            "coverage_target_percent": 90.0,
            "min_gap_threshold": 5.0,
            "max_purchase_percent": 50.0,
        }
        coverage = {"compute": 85.0}  # Gap is exactly 5%
        recommendations = {
            "compute": {
                "HourlyCommitmentToPurchase": "10.00",
                "RecommendationId": "rec-123",
            }
        }

        result = calculate_purchase_need_conservative(config, coverage, recommendations)

        assert len(result) == 1
        assert result[0]["sp_type"] == "compute"
        assert result[0]["hourly_commitment"] == 5.0  # 50% of $10

    def test_compute_sp_no_gap(self):
        """Test no purchase when coverage meets target."""
        config = {
            "enable_compute_sp": True,
            "enable_database_sp": False,
            "enable_sagemaker_sp": False,
            "coverage_target_percent": 90.0,
            "min_gap_threshold": 5.0,
            "max_purchase_percent": 50.0,
        }
        coverage = {"compute": 90.0}  # Gap is 0%
        recommendations = {
            "compute": {
                "HourlyCommitmentToPurchase": "10.00",
                "RecommendationId": "rec-123",
            }
        }

        result = calculate_purchase_need_conservative(config, coverage, recommendations)

        assert len(result) == 0

    def test_compute_sp_coverage_exceeds_target(self):
        """Test no purchase when coverage exceeds target."""
        config = {
            "enable_compute_sp": True,
            "enable_database_sp": False,
            "enable_sagemaker_sp": False,
            "coverage_target_percent": 90.0,
            "min_gap_threshold": 5.0,
            "max_purchase_percent": 50.0,
        }
        coverage = {"compute": 95.0}  # Coverage exceeds target
        recommendations = {
            "compute": {
                "HourlyCommitmentToPurchase": "10.00",
                "RecommendationId": "rec-123",
            }
        }

        result = calculate_purchase_need_conservative(config, coverage, recommendations)

        assert len(result) == 0

    def test_compute_sp_no_recommendation(self):
        """Test no purchase when AWS has no recommendation."""
        config = {
            "enable_compute_sp": True,
            "enable_database_sp": False,
            "enable_sagemaker_sp": False,
            "coverage_target_percent": 90.0,
            "min_gap_threshold": 5.0,
            "max_purchase_percent": 50.0,
        }
        coverage = {"compute": 50.0}  # Gap is 40%, above threshold
        recommendations = {}  # No recommendation

        result = calculate_purchase_need_conservative(config, coverage, recommendations)

        assert len(result) == 0

    def test_compute_sp_zero_commitment(self):
        """Test no purchase when AWS recommendation is zero."""
        config = {
            "enable_compute_sp": True,
            "enable_database_sp": False,
            "enable_sagemaker_sp": False,
            "coverage_target_percent": 90.0,
            "min_gap_threshold": 5.0,
            "max_purchase_percent": 50.0,
        }
        coverage = {"compute": 50.0}  # Gap is 40%, above threshold
        recommendations = {
            "compute": {
                "HourlyCommitmentToPurchase": "0.00",
                "RecommendationId": "rec-123",
            }
        }

        result = calculate_purchase_need_conservative(config, coverage, recommendations)

        assert len(result) == 0

    def test_database_sp_gap_above_threshold(self):
        """Test Database SP purchase when gap is above threshold."""
        config = {
            "enable_compute_sp": False,
            "enable_database_sp": True,
            "enable_sagemaker_sp": False,
            "coverage_target_percent": 90.0,
            "min_gap_threshold": 5.0,
            "max_purchase_percent": 50.0,
        }
        coverage = {"database": 60.0}  # Gap is 30%, above 5% threshold
        recommendations = {
            "database": {
                "HourlyCommitmentToPurchase": "8.00",
                "RecommendationId": "rec-db-456",
            }
        }

        result = calculate_purchase_need_conservative(config, coverage, recommendations)

        assert len(result) == 1
        assert result[0]["sp_type"] == "database"
        assert result[0]["hourly_commitment"] == 4.0  # 50% of $8
        assert result[0]["term"] == "ONE_YEAR"
        assert result[0]["payment_option"] == "NO_UPFRONT"
        assert result[0]["recommendation_id"] == "rec-db-456"
        assert result[0]["strategy"] == "conservative"
        assert result[0]["purchase_percent"] == 50.0

    def test_database_sp_gap_below_threshold(self):
        """Test no purchase when Database SP gap is below threshold."""
        config = {
            "enable_compute_sp": False,
            "enable_database_sp": True,
            "enable_sagemaker_sp": False,
            "coverage_target_percent": 90.0,
            "min_gap_threshold": 5.0,
            "max_purchase_percent": 50.0,
        }
        coverage = {"database": 87.0}  # Gap is 3%, below 5% threshold
        recommendations = {
            "database": {
                "HourlyCommitmentToPurchase": "8.00",
                "RecommendationId": "rec-db-456",
            }
        }

        result = calculate_purchase_need_conservative(config, coverage, recommendations)

        assert len(result) == 0

    def test_database_sp_gap_exactly_at_threshold(self):
        """Test Database SP purchase when gap is exactly at threshold."""
        config = {
            "enable_compute_sp": False,
            "enable_database_sp": True,
            "enable_sagemaker_sp": False,
            "coverage_target_percent": 90.0,
            "min_gap_threshold": 10.0,
            "max_purchase_percent": 50.0,
        }
        coverage = {"database": 80.0}  # Gap is exactly 10%
        recommendations = {
            "database": {
                "HourlyCommitmentToPurchase": "8.00",
                "RecommendationId": "rec-db-456",
            }
        }

        result = calculate_purchase_need_conservative(config, coverage, recommendations)

        assert len(result) == 1
        assert result[0]["hourly_commitment"] == 4.0

    def test_database_sp_no_gap(self):
        """Test no purchase when Database SP coverage meets target."""
        config = {
            "enable_compute_sp": False,
            "enable_database_sp": True,
            "enable_sagemaker_sp": False,
            "coverage_target_percent": 90.0,
            "min_gap_threshold": 5.0,
            "max_purchase_percent": 50.0,
        }
        coverage = {"database": 90.0}
        recommendations = {
            "database": {
                "HourlyCommitmentToPurchase": "8.00",
                "RecommendationId": "rec-db-456",
            }
        }

        result = calculate_purchase_need_conservative(config, coverage, recommendations)

        assert len(result) == 0

    def test_database_sp_zero_commitment(self):
        """Test no purchase when Database SP recommendation is zero."""
        config = {
            "enable_compute_sp": False,
            "enable_database_sp": True,
            "enable_sagemaker_sp": False,
            "coverage_target_percent": 90.0,
            "min_gap_threshold": 5.0,
            "max_purchase_percent": 50.0,
        }
        coverage = {"database": 50.0}  # Gap is 40%, above threshold
        recommendations = {
            "database": {
                "HourlyCommitmentToPurchase": "0.00",
                "RecommendationId": "rec-db-456",
            }
        }

        result = calculate_purchase_need_conservative(config, coverage, recommendations)

        assert len(result) == 0

    def test_sagemaker_sp_gap_above_threshold(self):
        """Test SageMaker SP purchase when gap is above threshold."""
        config = {
            "enable_compute_sp": False,
            "enable_database_sp": False,
            "enable_sagemaker_sp": True,
            "coverage_target_percent": 90.0,
            "min_gap_threshold": 5.0,
            "max_purchase_percent": 50.0,
            "sagemaker_sp_payment_option": "PARTIAL_UPFRONT",
        }
        coverage = {"sagemaker": 40.0}  # Gap is 50%, above 5% threshold
        recommendations = {
            "sagemaker": {
                "HourlyCommitmentToPurchase": "12.50",
                "RecommendationId": "rec-sm-789",
            }
        }

        result = calculate_purchase_need_conservative(config, coverage, recommendations)

        assert len(result) == 1
        assert result[0]["sp_type"] == "sagemaker"
        assert result[0]["hourly_commitment"] == 6.25  # 50% of $12.50
        assert result[0]["payment_option"] == "PARTIAL_UPFRONT"
        assert result[0]["recommendation_id"] == "rec-sm-789"
        assert result[0]["strategy"] == "conservative"
        assert result[0]["purchase_percent"] == 50.0

    def test_sagemaker_sp_gap_below_threshold(self):
        """Test no purchase when SageMaker SP gap is below threshold."""
        config = {
            "enable_compute_sp": False,
            "enable_database_sp": False,
            "enable_sagemaker_sp": True,
            "coverage_target_percent": 90.0,
            "min_gap_threshold": 5.0,
            "max_purchase_percent": 50.0,
        }
        coverage = {"sagemaker": 89.0}  # Gap is 1%, below 5% threshold
        recommendations = {
            "sagemaker": {
                "HourlyCommitmentToPurchase": "12.50",
                "RecommendationId": "rec-sm-789",
            }
        }

        result = calculate_purchase_need_conservative(config, coverage, recommendations)

        assert len(result) == 0

    def test_sagemaker_sp_gap_exactly_at_threshold(self):
        """Test SageMaker SP purchase when gap is exactly at threshold."""
        config = {
            "enable_compute_sp": False,
            "enable_database_sp": False,
            "enable_sagemaker_sp": True,
            "coverage_target_percent": 90.0,
            "min_gap_threshold": 7.5,
            "max_purchase_percent": 50.0,
        }
        coverage = {"sagemaker": 82.5}  # Gap is exactly 7.5%
        recommendations = {
            "sagemaker": {
                "HourlyCommitmentToPurchase": "12.50",
                "RecommendationId": "rec-sm-789",
            }
        }

        result = calculate_purchase_need_conservative(config, coverage, recommendations)

        assert len(result) == 1
        assert result[0]["hourly_commitment"] == 6.25

    def test_sagemaker_sp_no_gap(self):
        """Test no purchase when SageMaker SP coverage meets target."""
        config = {
            "enable_compute_sp": False,
            "enable_database_sp": False,
            "enable_sagemaker_sp": True,
            "coverage_target_percent": 90.0,
            "min_gap_threshold": 5.0,
            "max_purchase_percent": 50.0,
        }
        coverage = {"sagemaker": 92.0}
        recommendations = {
            "sagemaker": {
                "HourlyCommitmentToPurchase": "12.50",
                "RecommendationId": "rec-sm-789",
            }
        }

        result = calculate_purchase_need_conservative(config, coverage, recommendations)

        assert len(result) == 0

    def test_sagemaker_sp_zero_commitment(self):
        """Test no purchase when SageMaker SP recommendation is zero."""
        config = {
            "enable_compute_sp": False,
            "enable_database_sp": False,
            "enable_sagemaker_sp": True,
            "coverage_target_percent": 90.0,
            "min_gap_threshold": 5.0,
            "max_purchase_percent": 50.0,
        }
        coverage = {"sagemaker": 50.0}  # Gap is 40%, above threshold
        recommendations = {
            "sagemaker": {
                "HourlyCommitmentToPurchase": "0",
                "RecommendationId": "rec-sm-789",
            }
        }

        result = calculate_purchase_need_conservative(config, coverage, recommendations)

        assert len(result) == 0

    def test_multiple_sp_types_all_above_threshold(self):
        """Test purchasing multiple SP types when all gaps are above threshold."""
        config = {
            "enable_compute_sp": True,
            "enable_database_sp": True,
            "enable_sagemaker_sp": True,
            "coverage_target_percent": 90.0,
            "min_gap_threshold": 5.0,
            "max_purchase_percent": 50.0,
            "compute_sp_payment_option": "ALL_UPFRONT",
            "sagemaker_sp_payment_option": "PARTIAL_UPFRONT",
        }
        coverage = {
            "compute": 70.0,  # Gap 20%, above threshold
            "database": 60.0,  # Gap 30%, above threshold
            "sagemaker": 50.0,  # Gap 40%, above threshold
        }
        recommendations = {
            "compute": {
                "HourlyCommitmentToPurchase": "10.00",
                "RecommendationId": "rec-c-123",
            },
            "database": {
                "HourlyCommitmentToPurchase": "8.00",
                "RecommendationId": "rec-db-456",
            },
            "sagemaker": {
                "HourlyCommitmentToPurchase": "12.00",
                "RecommendationId": "rec-sm-789",
            },
        }

        result = calculate_purchase_need_conservative(config, coverage, recommendations)

        assert len(result) == 3

        # Check compute
        compute_plan = [p for p in result if p["sp_type"] == "compute"][0]
        assert compute_plan["hourly_commitment"] == 5.0
        assert compute_plan["payment_option"] == "ALL_UPFRONT"

        # Check database
        database_plan = [p for p in result if p["sp_type"] == "database"][0]
        assert database_plan["hourly_commitment"] == 4.0
        assert database_plan["payment_option"] == "NO_UPFRONT"

        # Check sagemaker
        sagemaker_plan = [p for p in result if p["sp_type"] == "sagemaker"][0]
        assert sagemaker_plan["hourly_commitment"] == 6.0
        assert sagemaker_plan["payment_option"] == "PARTIAL_UPFRONT"

    def test_multiple_sp_types_mixed_thresholds(self):
        """Test purchasing only SP types with gaps above threshold."""
        config = {
            "enable_compute_sp": True,
            "enable_database_sp": True,
            "enable_sagemaker_sp": True,
            "coverage_target_percent": 90.0,
            "min_gap_threshold": 5.0,
            "max_purchase_percent": 50.0,
        }
        coverage = {
            "compute": 70.0,  # Gap 20%, above threshold → purchase
            "database": 88.0,  # Gap 2%, below threshold → no purchase
            "sagemaker": 85.0,  # Gap 5%, exactly at threshold → purchase
        }
        recommendations = {
            "compute": {
                "HourlyCommitmentToPurchase": "10.00",
                "RecommendationId": "rec-c-123",
            },
            "database": {
                "HourlyCommitmentToPurchase": "8.00",
                "RecommendationId": "rec-db-456",
            },
            "sagemaker": {
                "HourlyCommitmentToPurchase": "12.00",
                "RecommendationId": "rec-sm-789",
            },
        }

        result = calculate_purchase_need_conservative(config, coverage, recommendations)

        assert len(result) == 2
        sp_types = [p["sp_type"] for p in result]
        assert "compute" in sp_types
        assert "sagemaker" in sp_types
        assert "database" not in sp_types

    def test_different_max_purchase_percents(self):
        """Test conservative strategy with different max_purchase_percent values."""
        # Test with 100%
        config_100 = {
            "enable_compute_sp": True,
            "enable_database_sp": False,
            "enable_sagemaker_sp": False,
            "coverage_target_percent": 90.0,
            "min_gap_threshold": 5.0,
            "max_purchase_percent": 100.0,
        }
        coverage = {"compute": 70.0}
        recommendations = {
            "compute": {
                "HourlyCommitmentToPurchase": "10.00",
                "RecommendationId": "rec-123",
            }
        }

        result = calculate_purchase_need_conservative(config_100, coverage, recommendations)
        assert len(result) == 1
        assert result[0]["hourly_commitment"] == 10.0  # 100% of $10

        # Test with 25%
        config_25 = {
            "enable_compute_sp": True,
            "enable_database_sp": False,
            "enable_sagemaker_sp": False,
            "coverage_target_percent": 90.0,
            "min_gap_threshold": 5.0,
            "max_purchase_percent": 25.0,
        }

        result = calculate_purchase_need_conservative(config_25, coverage, recommendations)
        assert len(result) == 1
        assert result[0]["hourly_commitment"] == 2.5  # 25% of $10

    def test_different_min_gap_thresholds(self):
        """Test conservative strategy with different min_gap_threshold values."""
        coverage = {"compute": 70.0}  # Gap is 20%
        recommendations = {
            "compute": {
                "HourlyCommitmentToPurchase": "10.00",
                "RecommendationId": "rec-123",
            }
        }

        # With threshold of 10%, gap of 20% should trigger purchase
        config_10 = {
            "enable_compute_sp": True,
            "enable_database_sp": False,
            "enable_sagemaker_sp": False,
            "coverage_target_percent": 90.0,
            "min_gap_threshold": 10.0,
            "max_purchase_percent": 50.0,
        }
        result = calculate_purchase_need_conservative(config_10, coverage, recommendations)
        assert len(result) == 1

        # With threshold of 25%, gap of 20% should NOT trigger purchase
        config_25 = {
            "enable_compute_sp": True,
            "enable_database_sp": False,
            "enable_sagemaker_sp": False,
            "coverage_target_percent": 90.0,
            "min_gap_threshold": 25.0,
            "max_purchase_percent": 50.0,
        }
        result = calculate_purchase_need_conservative(config_25, coverage, recommendations)
        assert len(result) == 0

    def test_default_config_parameters(self):
        """Test conservative strategy with default min_gap_threshold and max_purchase_percent."""
        # Should use defaults: min_gap_threshold=5.0, max_purchase_percent=50.0
        config = {
            "enable_compute_sp": True,
            "enable_database_sp": False,
            "enable_sagemaker_sp": False,
            "coverage_target_percent": 90.0,
            # min_gap_threshold and max_purchase_percent not provided
        }
        coverage = {"compute": 70.0}  # Gap is 20%, above default 5%
        recommendations = {
            "compute": {
                "HourlyCommitmentToPurchase": "10.00",
                "RecommendationId": "rec-123",
            }
        }

        result = calculate_purchase_need_conservative(config, coverage, recommendations)

        assert len(result) == 1
        assert result[0]["hourly_commitment"] == 5.0  # 50% (default) of $10
        assert result[0]["purchase_percent"] == 50.0

    def test_all_sp_types_disabled(self):
        """Test no purchases when all SP types are disabled."""
        config = {
            "enable_compute_sp": False,
            "enable_database_sp": False,
            "enable_sagemaker_sp": False,
            "coverage_target_percent": 90.0,
            "min_gap_threshold": 5.0,
            "max_purchase_percent": 50.0,
        }
        coverage = {
            "compute": 50.0,
            "database": 50.0,
            "sagemaker": 50.0,
        }
        recommendations = {
            "compute": {
                "HourlyCommitmentToPurchase": "10.00",
                "RecommendationId": "rec-c",
            },
            "database": {
                "HourlyCommitmentToPurchase": "8.00",
                "RecommendationId": "rec-db",
            },
            "sagemaker": {
                "HourlyCommitmentToPurchase": "12.00",
                "RecommendationId": "rec-sm",
            },
        }

        result = calculate_purchase_need_conservative(config, coverage, recommendations)

        assert len(result) == 0

    def test_missing_coverage_data(self):
        """Test handling of missing coverage data (should default to 0.0)."""
        config = {
            "enable_compute_sp": True,
            "enable_database_sp": False,
            "enable_sagemaker_sp": False,
            "coverage_target_percent": 90.0,
            "min_gap_threshold": 5.0,
            "max_purchase_percent": 50.0,
        }
        coverage = {}  # No coverage data
        recommendations = {
            "compute": {
                "HourlyCommitmentToPurchase": "10.00",
                "RecommendationId": "rec-123",
            }
        }

        result = calculate_purchase_need_conservative(config, coverage, recommendations)

        # Gap is 90% (target 90% - current 0%), which is above 5% threshold
        assert len(result) == 1
        assert result[0]["hourly_commitment"] == 5.0

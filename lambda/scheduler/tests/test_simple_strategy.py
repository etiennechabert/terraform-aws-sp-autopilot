"""
Unit tests for simple_strategy module.

Tests the simple purchase strategy which applies AWS recommendations
directly when there is a coverage gap.
"""

from simple_strategy import calculate_purchase_need_simple


class TestCalculatePurchaseNeedSimple:
    """Test the simple strategy for purchase planning."""

    def test_compute_sp_with_gap(self):
        """Test Compute SP purchase with coverage gap."""
        config = {
            "enable_compute_sp": True,
            "enable_database_sp": False,
            "enable_sagemaker_sp": False,
            "coverage_target_percent": 90.0,
            "compute_sp_payment_option": "ALL_UPFRONT",
        }
        coverage = {"compute": 50.0}
        recommendations = {
            "compute": {"HourlyCommitmentToPurchase": "10.00", "RecommendationId": "rec-123"}
        }

        result = calculate_purchase_need_simple(config, coverage, recommendations)

        assert len(result) == 1
        assert result[0]["sp_type"] == "compute"
        assert result[0]["hourly_commitment"] == 10.0
        assert result[0]["payment_option"] == "ALL_UPFRONT"
        assert result[0]["recommendation_id"] == "rec-123"
        assert result[0]["strategy"] == "simple"

    def test_compute_sp_no_gap(self):
        """Test no purchase when Compute SP coverage meets target."""
        config = {
            "enable_compute_sp": True,
            "enable_database_sp": False,
            "enable_sagemaker_sp": False,
            "coverage_target_percent": 90.0,
        }
        coverage = {"compute": 95.0}
        recommendations = {
            "compute": {"HourlyCommitmentToPurchase": "10.00", "RecommendationId": "rec-123"}
        }

        result = calculate_purchase_need_simple(config, coverage, recommendations)

        assert len(result) == 0

    def test_compute_sp_no_recommendation(self):
        """Test no purchase when AWS has no recommendation."""
        config = {
            "enable_compute_sp": True,
            "enable_database_sp": False,
            "enable_sagemaker_sp": False,
            "coverage_target_percent": 90.0,
        }
        coverage = {"compute": 50.0}
        recommendations = {}

        result = calculate_purchase_need_simple(config, coverage, recommendations)

        assert len(result) == 0

    def test_compute_sp_zero_commitment(self):
        """Test no purchase when AWS recommendation is zero."""
        config = {
            "enable_compute_sp": True,
            "enable_database_sp": False,
            "enable_sagemaker_sp": False,
            "coverage_target_percent": 90.0,
        }
        coverage = {"compute": 50.0}
        recommendations = {
            "compute": {"HourlyCommitmentToPurchase": "0.00", "RecommendationId": "rec-123"}
        }

        result = calculate_purchase_need_simple(config, coverage, recommendations)

        assert len(result) == 0

    def test_database_sp_with_gap(self):
        """Test Database SP purchase with coverage gap."""
        config = {
            "enable_compute_sp": False,
            "enable_database_sp": True,
            "enable_sagemaker_sp": False,
            "coverage_target_percent": 90.0,
        }
        coverage = {"database": 0.0}
        recommendations = {
            "database": {"HourlyCommitmentToPurchase": "5.50", "RecommendationId": "rec-db-456"}
        }

        result = calculate_purchase_need_simple(config, coverage, recommendations)

        assert len(result) == 1
        assert result[0]["sp_type"] == "database"
        assert result[0]["hourly_commitment"] == 5.5
        assert result[0]["term"] == "ONE_YEAR"
        assert result[0]["payment_option"] == "NO_UPFRONT"
        assert result[0]["recommendation_id"] == "rec-db-456"
        assert result[0]["strategy"] == "simple"

    def test_database_sp_no_gap(self):
        """Test no purchase when Database SP coverage meets target."""
        config = {
            "enable_compute_sp": False,
            "enable_database_sp": True,
            "enable_sagemaker_sp": False,
            "coverage_target_percent": 90.0,
        }
        coverage = {"database": 90.0}
        recommendations = {
            "database": {"HourlyCommitmentToPurchase": "5.50", "RecommendationId": "rec-db-456"}
        }

        result = calculate_purchase_need_simple(config, coverage, recommendations)

        assert len(result) == 0

    def test_database_sp_zero_commitment(self):
        """Test no purchase when Database SP recommendation is zero."""
        config = {
            "enable_compute_sp": False,
            "enable_database_sp": True,
            "enable_sagemaker_sp": False,
            "coverage_target_percent": 90.0,
        }
        coverage = {"database": 50.0}
        recommendations = {
            "database": {"HourlyCommitmentToPurchase": "0.00", "RecommendationId": "rec-db-456"}
        }

        result = calculate_purchase_need_simple(config, coverage, recommendations)

        assert len(result) == 0

    def test_sagemaker_sp_with_gap(self):
        """Test SageMaker SP purchase with coverage gap."""
        config = {
            "enable_compute_sp": False,
            "enable_database_sp": False,
            "enable_sagemaker_sp": True,
            "coverage_target_percent": 90.0,
            "sagemaker_sp_payment_option": "PARTIAL_UPFRONT",
        }
        coverage = {"sagemaker": 30.0}
        recommendations = {
            "sagemaker": {"HourlyCommitmentToPurchase": "8.75", "RecommendationId": "rec-sm-789"}
        }

        result = calculate_purchase_need_simple(config, coverage, recommendations)

        assert len(result) == 1
        assert result[0]["sp_type"] == "sagemaker"
        assert result[0]["hourly_commitment"] == 8.75
        assert result[0]["payment_option"] == "PARTIAL_UPFRONT"
        assert result[0]["recommendation_id"] == "rec-sm-789"
        assert result[0]["strategy"] == "simple"

    def test_sagemaker_sp_no_gap(self):
        """Test no purchase when SageMaker SP coverage meets target."""
        config = {
            "enable_compute_sp": False,
            "enable_database_sp": False,
            "enable_sagemaker_sp": True,
            "coverage_target_percent": 90.0,
        }
        coverage = {"sagemaker": 92.0}
        recommendations = {
            "sagemaker": {"HourlyCommitmentToPurchase": "8.75", "RecommendationId": "rec-sm-789"}
        }

        result = calculate_purchase_need_simple(config, coverage, recommendations)

        assert len(result) == 0

    def test_sagemaker_sp_zero_commitment(self):
        """Test no purchase when SageMaker SP recommendation is zero."""
        config = {
            "enable_compute_sp": False,
            "enable_database_sp": False,
            "enable_sagemaker_sp": True,
            "coverage_target_percent": 90.0,
        }
        coverage = {"sagemaker": 50.0}
        recommendations = {
            "sagemaker": {"HourlyCommitmentToPurchase": "0", "RecommendationId": "rec-sm-789"}
        }

        result = calculate_purchase_need_simple(config, coverage, recommendations)

        assert len(result) == 0

    def test_multiple_sp_types_enabled(self):
        """Test multiple SP types enabled simultaneously."""
        config = {
            "enable_compute_sp": True,
            "enable_database_sp": True,
            "enable_sagemaker_sp": True,
            "coverage_target_percent": 90.0,
            "compute_sp_payment_option": "ALL_UPFRONT",
            "sagemaker_sp_payment_option": "NO_UPFRONT",
        }
        coverage = {"compute": 50.0, "database": 60.0, "sagemaker": 70.0}
        recommendations = {
            "compute": {"HourlyCommitmentToPurchase": "10.00", "RecommendationId": "rec-c-1"},
            "database": {"HourlyCommitmentToPurchase": "5.50", "RecommendationId": "rec-d-2"},
            "sagemaker": {"HourlyCommitmentToPurchase": "8.75", "RecommendationId": "rec-s-3"},
        }

        result = calculate_purchase_need_simple(config, coverage, recommendations)

        assert len(result) == 3

        # Check compute SP
        compute_plan = [p for p in result if p["sp_type"] == "compute"][0]
        assert compute_plan["hourly_commitment"] == 10.0
        assert compute_plan["payment_option"] == "ALL_UPFRONT"
        assert compute_plan["strategy"] == "simple"

        # Check database SP
        database_plan = [p for p in result if p["sp_type"] == "database"][0]
        assert database_plan["hourly_commitment"] == 5.5
        assert database_plan["term"] == "ONE_YEAR"
        assert database_plan["payment_option"] == "NO_UPFRONT"
        assert database_plan["strategy"] == "simple"

        # Check sagemaker SP
        sagemaker_plan = [p for p in result if p["sp_type"] == "sagemaker"][0]
        assert sagemaker_plan["hourly_commitment"] == 8.75
        assert sagemaker_plan["payment_option"] == "NO_UPFRONT"
        assert sagemaker_plan["strategy"] == "simple"

    def test_all_sp_types_disabled(self):
        """Test no purchases when all SP types are disabled."""
        config = {
            "enable_compute_sp": False,
            "enable_database_sp": False,
            "enable_sagemaker_sp": False,
            "coverage_target_percent": 90.0,
        }
        coverage = {"compute": 50.0}
        recommendations = {
            "compute": {"HourlyCommitmentToPurchase": "10.00", "RecommendationId": "rec-123"}
        }

        result = calculate_purchase_need_simple(config, coverage, recommendations)

        assert len(result) == 0

    def test_uses_aws_recommendation_directly(self):
        """Test that simple strategy uses AWS recommendation amount directly."""
        config = {
            "enable_compute_sp": True,
            "enable_database_sp": False,
            "enable_sagemaker_sp": False,
            "coverage_target_percent": 90.0,
            "compute_sp_payment_option": "ALL_UPFRONT",
        }
        coverage = {"compute": 0.0}
        recommendations = {
            "compute": {"HourlyCommitmentToPurchase": "123.456", "RecommendationId": "rec-test"}
        }

        result = calculate_purchase_need_simple(config, coverage, recommendations)

        # Simple strategy should use the full AWS recommendation
        assert len(result) == 1
        assert result[0]["hourly_commitment"] == 123.456

    def test_missing_coverage_defaults_to_zero(self):
        """Test that missing coverage values default to 0%."""
        config = {
            "enable_compute_sp": True,
            "enable_database_sp": False,
            "enable_sagemaker_sp": False,
            "coverage_target_percent": 90.0,
            "compute_sp_payment_option": "ALL_UPFRONT",
        }
        coverage = {}  # No coverage data
        recommendations = {
            "compute": {"HourlyCommitmentToPurchase": "10.00", "RecommendationId": "rec-123"}
        }

        result = calculate_purchase_need_simple(config, coverage, recommendations)

        # Should create a plan since 0% coverage < 90% target
        assert len(result) == 1
        assert result[0]["hourly_commitment"] == 10.0

    def test_default_payment_options(self):
        """Test default payment options when not specified in config."""
        config = {
            "enable_compute_sp": True,
            "enable_database_sp": False,
            "enable_sagemaker_sp": True,
            "coverage_target_percent": 90.0,
            # No payment options specified
        }
        coverage = {"compute": 50.0, "sagemaker": 50.0}
        recommendations = {
            "compute": {"HourlyCommitmentToPurchase": "10.00", "RecommendationId": "rec-c-1"},
            "sagemaker": {"HourlyCommitmentToPurchase": "5.00", "RecommendationId": "rec-s-2"},
        }

        result = calculate_purchase_need_simple(config, coverage, recommendations)

        assert len(result) == 2

        # Check defaults
        compute_plan = [p for p in result if p["sp_type"] == "compute"][0]
        assert compute_plan["payment_option"] == "ALL_UPFRONT"  # Default

        sagemaker_plan = [p for p in result if p["sp_type"] == "sagemaker"][0]
        assert sagemaker_plan["payment_option"] == "ALL_UPFRONT"  # Default

    def test_missing_recommendation_id_defaults_to_unknown(self):
        """Test handling of missing recommendation ID."""
        config = {
            "enable_compute_sp": True,
            "enable_database_sp": False,
            "enable_sagemaker_sp": False,
            "coverage_target_percent": 90.0,
        }
        coverage = {"compute": 50.0}
        recommendations = {"compute": {"HourlyCommitmentToPurchase": "10.00"}}  # No ID

        result = calculate_purchase_need_simple(config, coverage, recommendations)

        assert len(result) == 1
        assert result[0]["recommendation_id"] == "unknown"

    def test_string_to_float_conversion(self):
        """Test that string commitment values are converted to float."""
        config = {
            "enable_compute_sp": True,
            "enable_database_sp": False,
            "enable_sagemaker_sp": False,
            "coverage_target_percent": 90.0,
        }
        coverage = {"compute": 50.0}
        recommendations = {
            "compute": {
                "HourlyCommitmentToPurchase": "12.3456789",  # String
                "RecommendationId": "rec-123",
            }
        }

        result = calculate_purchase_need_simple(config, coverage, recommendations)

        assert len(result) == 1
        assert isinstance(result[0]["hourly_commitment"], float)
        assert result[0]["hourly_commitment"] == 12.3456789

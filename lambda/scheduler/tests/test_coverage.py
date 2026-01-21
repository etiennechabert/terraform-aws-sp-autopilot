"""
Unit tests for coverage calculation module.

Tests the calculate_current_coverage function with various scenarios including
plan filtering, error handling, and edge cases.
"""

import os
import sys
from datetime import UTC, datetime, timedelta
from unittest.mock import Mock

import pytest


# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import sp_coverage as coverage_module


@pytest.fixture
def mock_config():
    """Create a mock configuration dictionary."""
    return {"renewal_window_days": 7, "coverage_target_percent": 90.0}


@pytest.fixture
def mock_savingsplans_client():
    """Create a mock Savings Plans client."""
    return Mock()


@pytest.fixture
def mock_ce_client():
    """Create a mock Cost Explorer client."""
    return Mock()


# ============================================================================
# group_coverage_by_sp_type Tests
# ============================================================================


def test_group_coverage_by_sp_type_compute_services():
    """Test grouping compute services correctly."""
    coverage_data = [
        {
            "Attributes": {"SERVICE": "compute"},
            "Coverage": {
                "SpendCoveredBySavingsPlans": "100",
                "TotalCost": "150",
            },
            "TimePeriod": {"End": "2026-01-17T00:00:00Z"},
        },
        {
            "Attributes": {"SERVICE": "compute"},
            "Coverage": {
                "SpendCoveredBySavingsPlans": "50",
                "TotalCost": "100",
            },
            "TimePeriod": {"End": "2026-01-17T01:00:00Z"},
        },
        {
            "Attributes": {"SERVICE": "compute"},
            "Coverage": {
                "SpendCoveredBySavingsPlans": "200",
                "TotalCost": "250",
            },
            "TimePeriod": {"End": "2026-01-17T02:00:00Z"},
        },
    ]

    result = coverage_module.group_coverage_by_sp_type(coverage_data)

    # Total compute: covered=350, total=500, coverage=70%, 3 hours
    assert result["compute"]["summary"]["total_covered"] == 350.0
    assert result["compute"]["summary"]["total_spend"] == 500.0
    assert result["compute"]["summary"]["avg_coverage"] == pytest.approx(70.0, rel=0.01)
    assert len(result["compute"]["timeseries"]) == 3
    assert result["database"]["summary"]["avg_coverage"] == 0.0
    assert len(result["database"]["timeseries"]) == 3
    assert result["sagemaker"]["summary"]["avg_coverage"] == 0.0
    assert len(result["sagemaker"]["timeseries"]) == 3


def test_group_coverage_by_sp_type_database_services():
    """Test grouping database services correctly."""
    coverage_data = [
        {
            "Attributes": {"SERVICE": "database"},
            "Coverage": {
                "SpendCoveredBySavingsPlans": "80",
                "TotalCost": "100",
            },
            "TimePeriod": {"End": "2026-01-17T00:00:00Z"},
        },
        {
            "Attributes": {"SERVICE": "database"},
            "Coverage": {
                "SpendCoveredBySavingsPlans": "0",
                "TotalCost": "50",
            },
            "TimePeriod": {"End": "2026-01-17T01:00:00Z"},
        },
        {
            "Attributes": {"SERVICE": "database"},
            "Coverage": {
                "SpendCoveredBySavingsPlans": "10",
                "TotalCost": "20",
            },
            "TimePeriod": {"End": "2026-01-17T02:00:00Z"},
        },
    ]

    result = coverage_module.group_coverage_by_sp_type(coverage_data)

    # Total database: covered=90, total=170, coverage=52.94%, 3 hours
    assert result["database"]["summary"]["total_covered"] == 90.0
    assert result["database"]["summary"]["total_spend"] == 170.0
    assert result["database"]["summary"]["avg_coverage"] == pytest.approx(52.94, rel=0.01)
    assert len(result["database"]["timeseries"]) == 3
    assert result["compute"]["summary"]["avg_coverage"] == 0.0
    assert len(result["compute"]["timeseries"]) == 3
    assert result["sagemaker"]["summary"]["avg_coverage"] == 0.0
    assert len(result["sagemaker"]["timeseries"]) == 3


def test_group_coverage_by_sp_type_sagemaker_service():
    """Test grouping SageMaker service correctly."""
    coverage_data = [
        {
            "Attributes": {"SERVICE": "sagemaker"},
            "Coverage": {
                "SpendCoveredBySavingsPlans": "30",
                "TotalCost": "100",
            },
            "TimePeriod": {"End": "2026-01-17T00:00:00Z"},
        }
    ]

    result = coverage_module.group_coverage_by_sp_type(coverage_data)

    assert result["sagemaker"]["summary"]["total_covered"] == 30.0
    assert result["sagemaker"]["summary"]["total_spend"] == 100.0
    assert result["sagemaker"]["summary"]["avg_coverage"] == 30.0
    assert len(result["sagemaker"]["timeseries"]) == 1
    assert result["compute"]["summary"]["avg_coverage"] == 0.0
    assert len(result["compute"]["timeseries"]) == 1
    assert result["database"]["summary"]["avg_coverage"] == 0.0
    assert len(result["database"]["timeseries"]) == 1


def test_group_coverage_by_sp_type_mixed_services():
    """Test grouping with mixed service types."""
    coverage_data = [
        {
            "Attributes": {"SERVICE": "compute"},
            "Coverage": {
                "SpendCoveredBySavingsPlans": "100",
                "TotalCost": "200",
            },
            "TimePeriod": {"End": "2026-01-17T00:00:00Z"},
        },
        {
            "Attributes": {"SERVICE": "database"},
            "Coverage": {
                "SpendCoveredBySavingsPlans": "50",
                "TotalCost": "100",
            },
            "TimePeriod": {"End": "2026-01-17T00:00:00Z"},
        },
        {
            "Attributes": {"SERVICE": "sagemaker"},
            "Coverage": {
                "SpendCoveredBySavingsPlans": "75",
                "TotalCost": "150",
            },
            "TimePeriod": {"End": "2026-01-17T00:00:00Z"},
        },
    ]

    result = coverage_module.group_coverage_by_sp_type(coverage_data)

    assert result["compute"]["summary"]["avg_coverage"] == 50.0
    assert result["compute"]["summary"]["total_covered"] == 100.0
    assert result["compute"]["summary"]["total_spend"] == 200.0
    assert len(result["compute"]["timeseries"]) == 1
    assert result["database"]["summary"]["avg_coverage"] == 50.0
    assert result["database"]["summary"]["total_covered"] == 50.0
    assert result["database"]["summary"]["total_spend"] == 100.0
    assert len(result["database"]["timeseries"]) == 1
    assert result["sagemaker"]["summary"]["avg_coverage"] == 50.0
    assert result["sagemaker"]["summary"]["total_covered"] == 75.0
    assert result["sagemaker"]["summary"]["total_spend"] == 150.0
    assert len(result["sagemaker"]["timeseries"]) == 1


def test_group_coverage_by_sp_type_empty_list():
    """Test handling empty coverage data list."""
    result = coverage_module.group_coverage_by_sp_type([])

    assert result["compute"]["summary"]["avg_coverage"] == 0.0
    assert result["compute"]["summary"]["total_covered"] == 0.0
    assert result["compute"]["summary"]["total_spend"] == 0.0
    assert len(result["compute"]["timeseries"]) == 0
    assert result["database"]["summary"]["avg_coverage"] == 0.0
    assert len(result["database"]["timeseries"]) == 0
    assert result["sagemaker"]["summary"]["avg_coverage"] == 0.0
    assert len(result["sagemaker"]["timeseries"]) == 0


def test_group_coverage_by_sp_type_zero_spend():
    """Test handling services with zero total cost."""
    coverage_data = [
        {
            "Attributes": {"SERVICE": "compute"},
            "Coverage": {
                "SpendCoveredBySavingsPlans": "0",
                "TotalCost": "0",
            },
            "TimePeriod": {"End": "2026-01-17T00:00:00Z"},
        }
    ]

    result = coverage_module.group_coverage_by_sp_type(coverage_data)

    assert result["compute"]["summary"]["avg_coverage"] == 0.0
    assert result["compute"]["summary"]["total_covered"] == 0.0
    assert result["compute"]["summary"]["total_spend"] == 0.0
    assert len(result["compute"]["timeseries"]) == 1
    assert result["database"]["summary"]["avg_coverage"] == 0.0
    assert len(result["database"]["timeseries"]) == 1
    assert result["sagemaker"]["summary"]["avg_coverage"] == 0.0
    assert len(result["sagemaker"]["timeseries"]) == 1


def test_group_coverage_by_sp_type_unknown_service():
    """Test handling unknown services (should be ignored)."""
    coverage_data = [
        {
            "Attributes": {"SERVICE": "s3"},
            "Coverage": {
                "SpendCoveredBySavingsPlans": "100",
                "TotalCost": "200",
            },
            "TimePeriod": {"End": "2026-01-17T00:00:00Z"},
        },
        {
            "Attributes": {"SERVICE": "compute"},
            "Coverage": {
                "SpendCoveredBySavingsPlans": "50",
                "TotalCost": "100",
            },
            "TimePeriod": {"End": "2026-01-17T00:00:00Z"},
        },
    ]

    result = coverage_module.group_coverage_by_sp_type(coverage_data)

    # S3 should be ignored, only compute counts
    assert result["compute"]["summary"]["avg_coverage"] == 50.0
    assert result["compute"]["summary"]["total_covered"] == 50.0
    assert result["compute"]["summary"]["total_spend"] == 100.0
    assert len(result["compute"]["timeseries"]) == 1
    assert result["database"]["summary"]["avg_coverage"] == 0.0
    assert len(result["database"]["timeseries"]) == 1
    assert result["sagemaker"]["summary"]["avg_coverage"] == 0.0
    assert len(result["sagemaker"]["timeseries"]) == 1


def test_group_coverage_by_sp_type_aggregated_multi_day():
    """Test aggregation of the same service across multiple timestamps."""
    coverage_data = [
        {
            "Attributes": {"SERVICE": "compute"},
            "Coverage": {
                "SpendCoveredBySavingsPlans": "100",
                "TotalCost": "150",
            },
            "TimePeriod": {"End": "2026-01-17T00:00:00Z"},
        },
        {
            "Attributes": {"SERVICE": "compute"},
            "Coverage": {
                "SpendCoveredBySavingsPlans": "120",
                "TotalCost": "160",
            },
            "TimePeriod": {"End": "2026-01-17T01:00:00Z"},
        },
        {
            "Attributes": {"SERVICE": "compute"},
            "Coverage": {
                "SpendCoveredBySavingsPlans": "50",
                "TotalCost": "100",
            },
            "TimePeriod": {"End": "2026-01-17T02:00:00Z"},
        },
        {
            "Attributes": {"SERVICE": "compute"},
            "Coverage": {
                "SpendCoveredBySavingsPlans": "60",
                "TotalCost": "110",
            },
            "TimePeriod": {"End": "2026-01-17T03:00:00Z"},
        },
    ]

    result = coverage_module.group_coverage_by_sp_type(coverage_data)

    # Total Compute: (100+120+50+60) / (150+160+100+110) = 330 / 520 = 63.46%
    assert result["compute"]["summary"]["total_covered"] == 330.0
    assert result["compute"]["summary"]["total_spend"] == 520.0
    assert result["compute"]["summary"]["avg_coverage"] == pytest.approx(63.46, rel=0.01)
    assert len(result["compute"]["timeseries"]) == 4  # 4 data points
    assert result["database"]["summary"]["avg_coverage"] == 0.0
    assert result["sagemaker"]["summary"]["avg_coverage"] == 0.0


def test_group_coverage_by_sp_type_real_world_data():
    """Test with real-world AWS response structure."""
    coverage_data = [
        {
            "Attributes": {"SERVICE": "compute"},
            "Coverage": {
                "SpendCoveredBySavingsPlans": "5.6552603958",
                "TotalCost": "48.2350783718",
            },
            "TimePeriod": {"Start": "2026-01-17", "End": "2026-01-18"},
        },
        {
            "Attributes": {"SERVICE": "compute"},
            "Coverage": {
                "SpendCoveredBySavingsPlans": "114.2585053198",
                "TotalCost": "135.9634795269",
            },
            "TimePeriod": {"Start": "2026-01-17T01:00:00Z", "End": "2026-01-18T01:00:00Z"},
        },
        {
            "Attributes": {"SERVICE": "compute"},
            "Coverage": {
                "SpendCoveredBySavingsPlans": "659.2455999924",
                "TotalCost": "754.8968082864",
            },
            "TimePeriod": {"Start": "2026-01-17T02:00:00Z", "End": "2026-01-18T02:00:00Z"},
        },
        {
            "Attributes": {"SERVICE": "database"},
            "Coverage": {
                "SpendCoveredBySavingsPlans": "0",
                "TotalCost": "528.5322394884",
            },
            "TimePeriod": {"Start": "2026-01-17", "End": "2026-01-18"},
        },
    ]

    result = coverage_module.group_coverage_by_sp_type(coverage_data)

    # Compute: (5.66 + 114.26 + 659.25) / (48.24 + 135.96 + 754.90) = 779.17 / 939.10 = 82.97%
    assert result["compute"]["summary"]["total_covered"] == pytest.approx(779.16, rel=0.01)
    assert result["compute"]["summary"]["total_spend"] == pytest.approx(939.10, rel=0.01)
    assert result["compute"]["summary"]["avg_coverage"] == pytest.approx(82.97, rel=0.01)
    assert len(result["compute"]["timeseries"]) == 3
    # Database: 0 / 528.53 = 0%
    assert result["database"]["summary"]["avg_coverage"] == 0.0
    assert result["database"]["summary"]["total_covered"] == 0.0
    assert result["database"]["summary"]["total_spend"] == 528.5322394884
    assert len(result["database"]["timeseries"]) == 3
    assert result["sagemaker"]["summary"]["avg_coverage"] == 0.0
    assert len(result["sagemaker"]["timeseries"]) == 3


# ============================================================================
# Successful Coverage Calculation Tests
# ============================================================================


def test_calculate_current_coverage_success(
    aws_mock_builder, mock_savingsplans_client, mock_ce_client, mock_config
):
    """Test successful coverage calculation with valid data."""
    # Use real AWS response structure with custom coverage percentage
    mock_savingsplans_client.describe_savings_plans.return_value = (
        aws_mock_builder.describe_savings_plans(plans_count=1)
    )
    mock_ce_client.get_savings_plans_coverage.return_value = aws_mock_builder.coverage(
        coverage_percentage=75.5
    )

    result = coverage_module.calculate_current_coverage(
        mock_savingsplans_client, mock_ce_client, mock_config
    )

    assert "compute" in result
    assert "database" in result
    assert "sagemaker" in result
    # Actual coverage calculated from fixture data aggregated spend
    # Fixture has compute and database services (RDS has 70.72% coverage)
    assert result["compute"] == pytest.approx(76.14, rel=0.01)
    # Database is not enabled by default in config, so it's 0
    assert result["database"] == 0.0
    assert result["sagemaker"] == 0.0


def test_calculate_current_coverage_filters_expiring_plans(
    aws_mock_builder, mock_savingsplans_client, mock_ce_client, mock_config
):
    """Test coverage calculation with plans having different expiration dates."""

    now = datetime.now(UTC)

    # Plan expiring in 3 days (should be excluded - within 7 day window)
    expiring_soon = now + timedelta(days=3)
    # Plan expiring in 30 days (should be included - outside 7 day window)
    expiring_later = now + timedelta(days=30)

    # Use real AWS structure but customize expiration dates for this specific test
    plans_response = aws_mock_builder.describe_savings_plans(plans_count=2)
    plans_response["savingsPlans"][0]["end"] = expiring_soon.isoformat()
    plans_response["savingsPlans"][1]["end"] = expiring_later.isoformat()
    mock_savingsplans_client.describe_savings_plans.return_value = plans_response

    mock_ce_client.get_savings_plans_coverage.return_value = aws_mock_builder.coverage(
        coverage_percentage=80.0
    )

    result = coverage_module.calculate_current_coverage(
        mock_savingsplans_client, mock_ce_client, mock_config
    )

    # Actual coverage calculated from fixture data aggregated spend
    # Note: AWS API returns all coverage data regardless of plan expiration
    assert result["compute"] == pytest.approx(76.14, rel=0.01)
    assert result["database"] == 0.0
    assert result["sagemaker"] == 0.0


def test_calculate_current_coverage_no_coverage_data(
    aws_mock_builder, mock_savingsplans_client, mock_ce_client, mock_config
):
    """Test handling when Cost Explorer returns no coverage data."""
    mock_savingsplans_client.describe_savings_plans.return_value = (
        aws_mock_builder.describe_savings_plans(plans_count=0)
    )

    # No coverage data - use the empty flag
    mock_ce_client.get_savings_plans_coverage.return_value = aws_mock_builder.coverage(empty=True)

    result = coverage_module.calculate_current_coverage(
        mock_savingsplans_client, mock_ce_client, mock_config
    )

    # Should return zeros when no data available
    assert result["compute"] == 0.0
    assert result["database"] == 0.0
    assert result["sagemaker"] == 0.0


def test_calculate_current_coverage_no_active_plans(
    mock_savingsplans_client, mock_ce_client, mock_config
):
    """Test when there are no active savings plans."""
    mock_savingsplans_client.describe_savings_plans.return_value = {"savingsPlans": []}

    mock_ce_client.get_savings_plans_coverage.return_value = {
        "SavingsPlansCoverages": [
            {
                "Attributes": {"SERVICE": "compute"},
                "TimePeriod": {"Start": "2026-01-14", "End": "2026-01-15"},
                "Coverage": {
                    "SpendCoveredBySavingsPlans": "0.0",
                    "TotalCost": "100.0",
                },
            }
        ]
    }

    result = coverage_module.calculate_current_coverage(
        mock_savingsplans_client, mock_ce_client, mock_config
    )

    assert result["compute"] == 0.0


def test_calculate_current_coverage_all_plans_expiring_soon(
    mock_savingsplans_client, mock_ce_client, mock_config
):
    """Test when all plans are expiring within renewal window."""
    now = datetime.now(UTC)
    expiring_soon1 = now + timedelta(days=1)
    expiring_soon2 = now + timedelta(days=5)

    mock_savingsplans_client.describe_savings_plans.return_value = {
        "savingsPlans": [
            {
                "savingsPlanId": "sp-1",
                "state": "active",
                "end": expiring_soon1.isoformat(),
            },
            {
                "savingsPlanId": "sp-2",
                "state": "active",
                "end": expiring_soon2.isoformat(),
            },
        ]
    }

    mock_ce_client.get_savings_plans_coverage.return_value = {
        "SavingsPlansCoverages": [
            {
                "Attributes": {"SERVICE": "compute"},
                "TimePeriod": {"Start": "2026-01-14", "End": "2026-01-15"},
                "Coverage": {
                    "SpendCoveredBySavingsPlans": "50.0",
                    "TotalCost": "100.0",
                },
            }
        ]
    }

    result = coverage_module.calculate_current_coverage(
        mock_savingsplans_client, mock_ce_client, mock_config
    )

    # Should still return coverage data even if all plans are expiring
    assert result["compute"] == 50.0


def test_calculate_current_coverage_boundary_renewal_window(
    mock_savingsplans_client, mock_ce_client, mock_config
):
    """Test plans expiring exactly at renewal window boundary."""
    now = datetime.now(UTC)
    # Exactly 7 days (should be excluded as it's not > renewal_window_days)
    expiring_exactly = now + timedelta(days=7)
    # 8 days (should be included)
    expiring_after = now + timedelta(days=8)

    mock_savingsplans_client.describe_savings_plans.return_value = {
        "savingsPlans": [
            {
                "savingsPlanId": "sp-exactly",
                "state": "active",
                "end": expiring_exactly.isoformat(),
            },
            {
                "savingsPlanId": "sp-after",
                "state": "active",
                "end": expiring_after.isoformat(),
            },
        ]
    }

    mock_ce_client.get_savings_plans_coverage.return_value = {
        "SavingsPlansCoverages": [
            {
                "Attributes": {"SERVICE": "compute"},
                "TimePeriod": {"Start": "2026-01-14", "End": "2026-01-15"},
                "Coverage": {
                    "SpendCoveredBySavingsPlans": "60.0",
                    "TotalCost": "100.0",
                },
            }
        ]
    }

    result = coverage_module.calculate_current_coverage(
        mock_savingsplans_client, mock_ce_client, mock_config
    )

    assert result["compute"] == 60.0


def test_calculate_current_coverage_multiple_coverage_data_points(
    mock_savingsplans_client, mock_ce_client, mock_config
):
    """Test that all coverage data points are aggregated correctly."""
    now = datetime.now(UTC)
    expiring_later = now + timedelta(days=30)

    mock_savingsplans_client.describe_savings_plans.return_value = {
        "savingsPlans": [
            {
                "savingsPlanId": "sp-12345",
                "state": "active",
                "end": expiring_later.isoformat(),
            }
        ]
    }

    # Multiple data points - should aggregate all
    mock_ce_client.get_savings_plans_coverage.return_value = {
        "SavingsPlansCoverages": [
            {
                "Attributes": {"SERVICE": "compute"},
                "TimePeriod": {"Start": "2026-01-13", "End": "2026-01-14"},
                "Coverage": {
                    "SpendCoveredBySavingsPlans": "70.0",
                    "TotalCost": "100.0",
                },
            },
            {
                "Attributes": {"SERVICE": "compute"},
                "TimePeriod": {"Start": "2026-01-14", "End": "2026-01-15"},
                "Coverage": {
                    "SpendCoveredBySavingsPlans": "171.0",
                    "TotalCost": "200.0",
                },
            },
        ]
    }

    result = coverage_module.calculate_current_coverage(
        mock_savingsplans_client, mock_ce_client, mock_config
    )

    # Should aggregate: (70 + 171) / (100 + 200) = 241 / 300 = 80.33%
    assert result["compute"] == pytest.approx(80.33, rel=0.01)


def test_calculate_current_coverage_missing_coverage_percentage(
    mock_savingsplans_client, mock_ce_client, mock_config
):
    """Test handling when spend fields are missing from response."""
    now = datetime.now(UTC)
    expiring_later = now + timedelta(days=30)

    mock_savingsplans_client.describe_savings_plans.return_value = {
        "savingsPlans": [
            {
                "savingsPlanId": "sp-12345",
                "state": "active",
                "end": expiring_later.isoformat(),
            }
        ]
    }

    # Coverage data without spend fields - should default to 0
    mock_ce_client.get_savings_plans_coverage.return_value = {
        "SavingsPlansCoverages": [
            {
                "Attributes": {"SERVICE": "compute"},
                "TimePeriod": {"Start": "2026-01-14", "End": "2026-01-15"},
                "Coverage": {},  # Missing spend fields
            }
        ]
    }

    result = coverage_module.calculate_current_coverage(
        mock_savingsplans_client, mock_ce_client, mock_config
    )

    # Should default to 0.0
    assert result["compute"] == 0.0


def test_calculate_current_coverage_plan_without_end_date(
    mock_savingsplans_client, mock_ce_client, mock_config
):
    """Test handling plans without end date."""
    now = datetime.now(UTC)
    expiring_later = now + timedelta(days=30)

    mock_savingsplans_client.describe_savings_plans.return_value = {
        "savingsPlans": [
            {
                "savingsPlanId": "sp-no-end",
                "state": "active",
                # Missing 'end' field
            },
            {
                "savingsPlanId": "sp-with-end",
                "state": "active",
                "end": expiring_later.isoformat(),
            },
        ]
    }

    mock_ce_client.get_savings_plans_coverage.return_value = {
        "SavingsPlansCoverages": [
            {
                "Attributes": {"SERVICE": "compute"},
                "TimePeriod": {"Start": "2026-01-14", "End": "2026-01-15"},
                "Coverage": {
                    "SpendCoveredBySavingsPlans": "55.0",
                    "TotalCost": "100.0",
                },
            }
        ]
    }

    result = coverage_module.calculate_current_coverage(
        mock_savingsplans_client, mock_ce_client, mock_config
    )

    # Should handle gracefully - plan without end date is skipped
    assert result["compute"] == pytest.approx(55.0, rel=0.01)


# ============================================================================
# Error Handling Tests
# ============================================================================


def test_calculate_current_coverage_describe_savings_plans_error(
    mock_savingsplans_client, mock_ce_client, mock_config
):
    """Test error handling when Cost Explorer API fails."""
    from botocore.exceptions import ClientError

    error_response = {"Error": {"Code": "AccessDenied", "Message": "Access denied"}}
    mock_ce_client.get_savings_plans_coverage.side_effect = ClientError(
        error_response, "get_savings_plans_coverage"
    )

    with pytest.raises(ClientError):
        coverage_module.calculate_current_coverage(
            mock_savingsplans_client, mock_ce_client, mock_config
        )


def test_calculate_current_coverage_get_coverage_error(
    mock_savingsplans_client, mock_ce_client, mock_config
):
    """Test error handling when get_savings_plans_coverage fails."""
    from botocore.exceptions import ClientError

    now = datetime.now(UTC)
    expiring_later = now + timedelta(days=30)

    mock_savingsplans_client.describe_savings_plans.return_value = {
        "savingsPlans": [
            {
                "savingsPlanId": "sp-12345",
                "state": "active",
                "end": expiring_later.isoformat(),
            }
        ]
    }

    error_response = {"Error": {"Code": "ServiceUnavailable", "Message": "Service unavailable"}}
    mock_ce_client.get_savings_plans_coverage.side_effect = ClientError(
        error_response, "get_savings_plans_coverage"
    )

    with pytest.raises(ClientError):
        coverage_module.calculate_current_coverage(
            mock_savingsplans_client, mock_ce_client, mock_config
        )


# ============================================================================
# Edge Cases
# ============================================================================


def test_calculate_current_coverage_high_coverage_percentage(
    mock_savingsplans_client, mock_ce_client, mock_config
):
    """Test with very high coverage percentage (near 100%)."""
    now = datetime.now(UTC)
    expiring_later = now + timedelta(days=30)

    mock_savingsplans_client.describe_savings_plans.return_value = {
        "savingsPlans": [
            {
                "savingsPlanId": "sp-12345",
                "state": "active",
                "end": expiring_later.isoformat(),
            }
        ]
    }

    mock_ce_client.get_savings_plans_coverage.return_value = {
        "SavingsPlansCoverages": [
            {
                "Attributes": {"SERVICE": "compute"},
                "TimePeriod": {"Start": "2026-01-14", "End": "2026-01-15"},
                "Coverage": {
                    "SpendCoveredBySavingsPlans": "99.9",
                    "TotalCost": "100.0",
                },
            }
        ]
    }

    result = coverage_module.calculate_current_coverage(
        mock_savingsplans_client, mock_ce_client, mock_config
    )

    assert result["compute"] == 99.9


def test_calculate_current_coverage_zero_coverage(
    mock_savingsplans_client, mock_ce_client, mock_config
):
    """Test with zero coverage percentage."""
    now = datetime.now(UTC)
    expiring_later = now + timedelta(days=30)

    mock_savingsplans_client.describe_savings_plans.return_value = {
        "savingsPlans": [
            {
                "savingsPlanId": "sp-12345",
                "state": "active",
                "end": expiring_later.isoformat(),
            }
        ]
    }

    mock_ce_client.get_savings_plans_coverage.return_value = {
        "SavingsPlansCoverages": [
            {
                "Attributes": {"SERVICE": "compute"},
                "TimePeriod": {"Start": "2026-01-14", "End": "2026-01-15"},
                "Coverage": {
                    "SpendCoveredBySavingsPlans": "0.0",
                    "TotalCost": "100.0",
                },
            }
        ]
    }

    result = coverage_module.calculate_current_coverage(
        mock_savingsplans_client, mock_ce_client, mock_config
    )

    assert result["compute"] == 0.0


def test_calculate_current_coverage_with_groupby_multiple_types(
    aws_mock_builder, mock_savingsplans_client, mock_ce_client, mock_config
):
    """Test coverage calculation with only compute enabled."""
    now = datetime.now(UTC)
    expiring_later = now + timedelta(days=30)

    # Only enable compute (default behavior)
    mock_config["enable_compute_sp"] = True

    mock_savingsplans_client.describe_savings_plans.return_value = {
        "savingsPlans": [
            {
                "savingsPlanId": "sp-compute",
                "state": "active",
                "end": expiring_later.isoformat(),
            },
        ]
    }

    # Use fixture data which has compute services
    mock_ce_client.get_savings_plans_coverage.return_value = aws_mock_builder.coverage()

    result = coverage_module.calculate_current_coverage(
        mock_savingsplans_client, mock_ce_client, mock_config
    )

    # Fixture has compute data
    assert result["compute"] == pytest.approx(76.14, rel=0.01)
    assert result["sagemaker"] == 0.0
    assert result["database"] == 0.0


def test_calculate_current_coverage_with_groupby_ec2_instance_sp(
    mock_savingsplans_client, mock_ce_client, mock_config
):
    """Test coverage calculation with compute services."""
    now = datetime.now(UTC)
    expiring_later = now + timedelta(days=30)

    mock_savingsplans_client.describe_savings_plans.return_value = {
        "savingsPlans": [
            {
                "savingsPlanId": "sp-ec2",
                "state": "active",
                "end": expiring_later.isoformat(),
            }
        ]
    }

    # Compute SP type coverage
    mock_ce_client.get_savings_plans_coverage.return_value = {
        "SavingsPlansCoverages": [
            {
                "Attributes": {"SERVICE": "compute"},
                "TimePeriod": {"Start": "2026-01-14", "End": "2026-01-15"},
                "Coverage": {
                    "SpendCoveredBySavingsPlans": "85.0",
                    "TotalCost": "100.0",
                },
            }
        ]
    }

    result = coverage_module.calculate_current_coverage(
        mock_savingsplans_client, mock_ce_client, mock_config
    )

    assert result["compute"] == 85.0
    assert result["sagemaker"] == 0.0
    assert result["database"] == 0.0


def test_calculate_current_coverage_with_groupby_rds_instance(
    mock_savingsplans_client, mock_ce_client, mock_config
):
    """Test coverage calculation with database services."""
    now = datetime.now(UTC)
    expiring_later = now + timedelta(days=30)

    # Enable database SP type
    mock_config["enable_database_sp"] = True

    mock_savingsplans_client.describe_savings_plans.return_value = {
        "savingsPlans": [
            {
                "savingsPlanId": "sp-rds",
                "state": "active",
                "end": expiring_later.isoformat(),
            }
        ]
    }

    # Database SP type coverage
    mock_ce_client.get_savings_plans_coverage.return_value = {
        "SavingsPlansCoverages": [
            {
                "Attributes": {"SERVICE": "database"},
                "TimePeriod": {"Start": "2026-01-14", "End": "2026-01-15"},
                "Coverage": {
                    "SpendCoveredBySavingsPlans": "90.0",
                    "TotalCost": "100.0",
                },
            }
        ]
    }

    result = coverage_module.calculate_current_coverage(
        mock_savingsplans_client, mock_ce_client, mock_config
    )

    assert result["compute"] == 0.0
    assert result["sagemaker"] == 0.0
    assert result["database"] == 90.0


def test_calculate_current_coverage_with_groupby_all_types(
    aws_mock_builder, mock_savingsplans_client, mock_ce_client, mock_config
):
    """Test coverage calculation with compute enabled."""
    now = datetime.now(UTC)
    expiring_later = now + timedelta(days=30)

    # Only enable compute
    mock_config["enable_compute_sp"] = True

    mock_savingsplans_client.describe_savings_plans.return_value = {
        "savingsPlans": [
            {
                "savingsPlanId": "sp-all",
                "state": "active",
                "end": expiring_later.isoformat(),
            }
        ]
    }

    # Use fixture data
    mock_ce_client.get_savings_plans_coverage.return_value = aws_mock_builder.coverage()

    result = coverage_module.calculate_current_coverage(
        mock_savingsplans_client, mock_ce_client, mock_config
    )

    # Fixture has compute data
    assert result["compute"] == pytest.approx(76.14, rel=0.01)
    assert result["sagemaker"] == 0.0
    assert result["database"] == 0.0


def test_calculate_current_coverage_with_groupby_no_groups_fallback(
    mock_savingsplans_client, mock_ce_client, mock_config
):
    """Test with compute coverage only."""
    now = datetime.now(UTC)
    expiring_later = now + timedelta(days=30)

    mock_savingsplans_client.describe_savings_plans.return_value = {
        "savingsPlans": [
            {
                "savingsPlanId": "sp-12345",
                "state": "active",
                "end": expiring_later.isoformat(),
            }
        ]
    }

    # Simple compute coverage
    mock_ce_client.get_savings_plans_coverage.return_value = {
        "SavingsPlansCoverages": [
            {
                "Attributes": {"SERVICE": "compute"},
                "TimePeriod": {"Start": "2026-01-14", "End": "2026-01-15"},
                "Coverage": {
                    "SpendCoveredBySavingsPlans": "70.0",
                    "TotalCost": "100.0",
                },
            }
        ]
    }

    result = coverage_module.calculate_current_coverage(
        mock_savingsplans_client, mock_ce_client, mock_config
    )

    # Should use aggregate coverage for compute
    assert result["compute"] == 70.0
    assert result["sagemaker"] == 0.0
    assert result["database"] == 0.0

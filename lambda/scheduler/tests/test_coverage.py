"""
Unit tests for coverage calculation module.

Tests the calculate_current_coverage function with various scenarios including
plan filtering, error handling, and edge cases.
"""

import os
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import pytest


# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import sp_coverage as coverage_module  # noqa: E402


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
    assert result["compute"] == 75.5
    assert result["database"] == 0.0
    assert result["sagemaker"] == 0.0


def test_calculate_current_coverage_filters_expiring_plans(
    aws_mock_builder, mock_savingsplans_client, mock_ce_client, mock_config
):
    """Test that plans expiring within renewal_window_days are excluded."""

    now = datetime.now(timezone.utc)

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

    assert result["compute"] == 80.0
    # Verify describe_savings_plans was called with correct filter
    mock_savingsplans_client.describe_savings_plans.assert_called_once()


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
                "TimePeriod": {"Start": "2026-01-14", "End": "2026-01-15"},
                "Coverage": {"CoveragePercentage": "0.0"},
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
    now = datetime.now(timezone.utc)
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
                "TimePeriod": {"Start": "2026-01-14", "End": "2026-01-15"},
                "Coverage": {"CoveragePercentage": "50.0"},
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
    now = datetime.now(timezone.utc)
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
                "TimePeriod": {"Start": "2026-01-14", "End": "2026-01-15"},
                "Coverage": {"CoveragePercentage": "60.0"},
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
    """Test that the most recent coverage data point is used."""
    now = datetime.now(timezone.utc)
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

    # Multiple data points - should use last one
    mock_ce_client.get_savings_plans_coverage.return_value = {
        "SavingsPlansCoverages": [
            {
                "TimePeriod": {"Start": "2026-01-13", "End": "2026-01-14"},
                "Coverage": {"CoveragePercentage": "70.0"},
            },
            {
                "TimePeriod": {"Start": "2026-01-14", "End": "2026-01-15"},
                "Coverage": {"CoveragePercentage": "85.5"},
            },
        ]
    }

    result = coverage_module.calculate_current_coverage(
        mock_savingsplans_client, mock_ce_client, mock_config
    )

    # Should use the latest (85.5)
    assert result["compute"] == 85.5


def test_calculate_current_coverage_missing_coverage_percentage(
    mock_savingsplans_client, mock_ce_client, mock_config
):
    """Test handling when CoveragePercentage is missing from response."""
    now = datetime.now(timezone.utc)
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

    # Coverage data without CoveragePercentage field
    mock_ce_client.get_savings_plans_coverage.return_value = {
        "SavingsPlansCoverages": [
            {
                "TimePeriod": {"Start": "2026-01-14", "End": "2026-01-15"},
                "Coverage": {},  # Missing CoveragePercentage
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
    now = datetime.now(timezone.utc)
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
                "TimePeriod": {"Start": "2026-01-14", "End": "2026-01-15"},
                "Coverage": {"CoveragePercentage": "55.0"},
            }
        ]
    }

    result = coverage_module.calculate_current_coverage(
        mock_savingsplans_client, mock_ce_client, mock_config
    )

    # Should handle gracefully - plan without end date is skipped
    assert result["compute"] == 55.0


# ============================================================================
# Error Handling Tests
# ============================================================================


def test_calculate_current_coverage_describe_savings_plans_error(
    mock_savingsplans_client, mock_ce_client, mock_config
):
    """Test error handling when describe_savings_plans fails."""
    from botocore.exceptions import ClientError

    error_response = {"Error": {"Code": "AccessDenied", "Message": "Access denied"}}
    mock_savingsplans_client.describe_savings_plans.side_effect = ClientError(
        error_response, "describe_savings_plans"
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

    now = datetime.now(timezone.utc)
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
    now = datetime.now(timezone.utc)
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
                "TimePeriod": {"Start": "2026-01-14", "End": "2026-01-15"},
                "Coverage": {"CoveragePercentage": "99.9"},
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
    now = datetime.now(timezone.utc)
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
                "TimePeriod": {"Start": "2026-01-14", "End": "2026-01-15"},
                "Coverage": {"CoveragePercentage": "0.0"},
            }
        ]
    }

    result = coverage_module.calculate_current_coverage(
        mock_savingsplans_client, mock_ce_client, mock_config
    )

    assert result["compute"] == 0.0


def test_calculate_current_coverage_with_groupby_multiple_types(
    mock_savingsplans_client, mock_ce_client, mock_config
):
    """Test coverage calculation with GroupBy returning multiple SP types."""
    now = datetime.now(timezone.utc)
    expiring_later = now + timedelta(days=30)

    mock_savingsplans_client.describe_savings_plans.return_value = {
        "savingsPlans": [
            {
                "savingsPlanId": "sp-compute",
                "state": "active",
                "end": expiring_later.isoformat(),
            },
            {
                "savingsPlanId": "sp-sagemaker",
                "state": "active",
                "end": expiring_later.isoformat(),
            },
        ]
    }

    # Mock GroupBy response with separate coverage per SP type
    mock_ce_client.get_savings_plans_coverage.return_value = {
        "SavingsPlansCoverages": [
            {
                "TimePeriod": {"Start": "2026-01-14", "End": "2026-01-15"},
                "Groups": [
                    {
                        "Attributes": {"SERVICE": "Amazon Elastic Compute Cloud - Compute"},
                        "Coverage": {"CoveragePercentage": "75.5"},
                    },
                    {
                        "Attributes": {"SERVICE": "Amazon SageMaker"},
                        "Coverage": {"CoveragePercentage": "60.0"},
                    },
                ],
            }
        ]
    }

    result = coverage_module.calculate_current_coverage(
        mock_savingsplans_client, mock_ce_client, mock_config
    )

    assert result["compute"] == 75.5
    assert result["sagemaker"] == 60.0
    assert result["database"] == 0.0


def test_calculate_current_coverage_with_groupby_ec2_instance_sp(
    mock_savingsplans_client, mock_ce_client, mock_config
):
    """Test coverage calculation with EC2InstanceSP type."""
    now = datetime.now(timezone.utc)
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

    # EC2InstanceSP should map to compute coverage
    mock_ce_client.get_savings_plans_coverage.return_value = {
        "SavingsPlansCoverages": [
            {
                "TimePeriod": {"Start": "2026-01-14", "End": "2026-01-15"},
                "Groups": [
                    {
                        "Attributes": {"SERVICE": "Amazon Elastic Compute Cloud - Compute"},
                        "Coverage": {"CoveragePercentage": "85.0"},
                    }
                ],
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
    """Test coverage calculation with RDSInstance SP type."""
    now = datetime.now(timezone.utc)
    expiring_later = now + timedelta(days=30)

    mock_savingsplans_client.describe_savings_plans.return_value = {
        "savingsPlans": [
            {
                "savingsPlanId": "sp-rds",
                "state": "active",
                "end": expiring_later.isoformat(),
            }
        ]
    }

    # RDSInstance should map to database coverage
    mock_ce_client.get_savings_plans_coverage.return_value = {
        "SavingsPlansCoverages": [
            {
                "TimePeriod": {"Start": "2026-01-14", "End": "2026-01-15"},
                "Groups": [
                    {
                        "Attributes": {"SERVICE": "Amazon Relational Database Service"},
                        "Coverage": {"CoveragePercentage": "90.0"},
                    }
                ],
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
    mock_savingsplans_client, mock_ce_client, mock_config
):
    """Test coverage calculation with all SP types present."""
    now = datetime.now(timezone.utc)
    expiring_later = now + timedelta(days=30)

    mock_savingsplans_client.describe_savings_plans.return_value = {
        "savingsPlans": [
            {
                "savingsPlanId": "sp-all",
                "state": "active",
                "end": expiring_later.isoformat(),
            }
        ]
    }

    # All SP types with coverage
    mock_ce_client.get_savings_plans_coverage.return_value = {
        "SavingsPlansCoverages": [
            {
                "TimePeriod": {"Start": "2026-01-14", "End": "2026-01-15"},
                "Groups": [
                    {
                        "Attributes": {"SERVICE": "Amazon Elastic Compute Cloud - Compute"},
                        "Coverage": {"CoveragePercentage": "75.0"},
                    },
                    {
                        "Attributes": {"SERVICE": "Amazon SageMaker"},
                        "Coverage": {"CoveragePercentage": "60.0"},
                    },
                    {
                        "Attributes": {"SERVICE": "Amazon Relational Database Service"},
                        "Coverage": {"CoveragePercentage": "80.0"},
                    },
                ],
            }
        ]
    }

    result = coverage_module.calculate_current_coverage(
        mock_savingsplans_client, mock_ce_client, mock_config
    )

    assert result["compute"] == 75.0
    assert result["sagemaker"] == 60.0
    assert result["database"] == 80.0


def test_calculate_current_coverage_with_groupby_no_groups_fallback(
    mock_savingsplans_client, mock_ce_client, mock_config
):
    """Test fallback to aggregate coverage when GroupBy returns no groups."""
    now = datetime.now(timezone.utc)
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

    # GroupBy response with no groups (empty) - should fallback to aggregate
    mock_ce_client.get_savings_plans_coverage.return_value = {
        "SavingsPlansCoverages": [
            {
                "TimePeriod": {"Start": "2026-01-14", "End": "2026-01-15"},
                "Groups": [],
                "Coverage": {"CoveragePercentage": "70.0"},
            }
        ]
    }

    result = coverage_module.calculate_current_coverage(
        mock_savingsplans_client, mock_ce_client, mock_config
    )

    # Should use aggregate coverage for compute when no groups
    assert result["compute"] == 70.0
    assert result["sagemaker"] == 0.0
    assert result["database"] == 0.0

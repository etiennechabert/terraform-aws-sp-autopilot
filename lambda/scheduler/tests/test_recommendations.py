"""
Unit tests for recommendations module.

Tests the AWS Savings Plans recommendation fetching functions including
parallel execution, error handling, and edge cases for Compute, Database,
and SageMaker Savings Plans.
"""

import os
import sys
from unittest.mock import Mock

import pytest


# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import recommendations


@pytest.fixture
def mock_config():
    """Create a mock configuration dictionary."""
    return {
        "enable_compute_sp": True,
        "enable_database_sp": True,
        "enable_sagemaker_sp": True,
        "lookback_days": 30,
        "min_data_days": 14,
    }


@pytest.fixture
def mock_ce_client():
    """Create a mock Cost Explorer client."""
    return Mock()


# ============================================================================
# Compute SP Recommendation Tests
# ============================================================================


def test_fetch_compute_sp_recommendation_success(mock_ce_client, mock_config):
    """Test successful Compute SP recommendation fetch."""
    mock_ce_client.get_savings_plans_purchase_recommendation.return_value = {
        "Metadata": {
            "RecommendationId": "rec-12345",
            "GenerationTimestamp": "2026-01-15T10:00:00Z",
            "LookbackPeriodInDays": "30",
        },
        "SavingsPlansPurchaseRecommendation": {
            "SavingsPlansPurchaseRecommendationDetails": [
                {
                    "HourlyCommitmentToPurchase": "5.50",
                    "EstimatedROI": "25.5",
                    "EstimatedSavingsAmount": "1000.00",
                }
            ]
        },
    }

    result = recommendations._fetch_compute_sp_recommendation(mock_ce_client, "THIRTY_DAYS")

    assert result is not None
    assert result["HourlyCommitmentToPurchase"] == "5.50"
    assert result["RecommendationId"] == "rec-12345"
    assert result["GenerationTimestamp"] == "2026-01-15T10:00:00Z"
    assert "Details" in result


def test_fetch_compute_sp_recommendation_no_recommendations(mock_ce_client, mock_config):
    """Test when AWS returns no Compute SP recommendations."""
    mock_ce_client.get_savings_plans_purchase_recommendation.return_value = {
        "Metadata": {
            "RecommendationId": "rec-12345",
            "GenerationTimestamp": "2026-01-15T10:00:00Z",
            "LookbackPeriodInDays": "30",
        },
        "SavingsPlansPurchaseRecommendation": {"SavingsPlansPurchaseRecommendationDetails": []},
    }

    result = recommendations._fetch_compute_sp_recommendation(
        mock_ce_client, "THIRTY_DAYS"
    )

    assert result is None


def test_fetch_compute_sp_recommendation_insufficient_data(mock_ce_client, mock_config):
    """Test Compute SP recommendation with limited lookback data (still returns result)."""
    mock_ce_client.get_savings_plans_purchase_recommendation.return_value = {
        "Metadata": {
            "RecommendationId": "rec-12345",
            "GenerationTimestamp": "2026-01-15T10:00:00Z",
            "LookbackPeriodInDays": "7",  # Limited data, but still valid
        },
        "SavingsPlansPurchaseRecommendation": {
            "SavingsPlansPurchaseRecommendationDetails": [{"HourlyCommitmentToPurchase": "5.50"}]
        },
    }

    result = recommendations._fetch_compute_sp_recommendation(mock_ce_client, "SEVEN_DAYS")

    # min_data_days validation was removed, so recommendations with any data are accepted
    assert result is not None
    assert result["HourlyCommitmentToPurchase"] == "5.50"


def test_fetch_compute_sp_recommendation_api_error(mock_ce_client, mock_config):
    """Test error handling when Compute SP API call fails."""
    from botocore.exceptions import ClientError

    error_response = {"Error": {"Code": "AccessDenied", "Message": "Access denied"}}
    mock_ce_client.get_savings_plans_purchase_recommendation.side_effect = ClientError(
        error_response, "get_savings_plans_purchase_recommendation"
    )

    with pytest.raises(ClientError):
        recommendations._fetch_compute_sp_recommendation(mock_ce_client, "THIRTY_DAYS")


# ============================================================================
# Database SP Recommendation Tests
# ============================================================================


def test_fetch_database_sp_recommendation_success(mock_ce_client, mock_config):
    """Test successful Database SP recommendation fetch."""
    mock_ce_client.get_savings_plans_purchase_recommendation.return_value = {
        "Metadata": {
            "RecommendationId": "rec-db-123",
            "GenerationTimestamp": "2026-01-15T11:00:00Z",
            "LookbackPeriodInDays": "30",
        },
        "SavingsPlansPurchaseRecommendation": {
            "SavingsPlansPurchaseRecommendationDetails": [
                {
                    "HourlyCommitmentToPurchase": "2.75",
                    "EstimatedROI": "30.0",
                    "EstimatedSavingsAmount": "500.00",
                }
            ]
        },
    }

    result = recommendations._fetch_database_sp_recommendation(
        mock_ce_client, "THIRTY_DAYS"
    )

    assert result is not None
    assert result["HourlyCommitmentToPurchase"] == "2.75"
    assert result["RecommendationId"] == "rec-db-123"


def test_fetch_database_sp_recommendation_no_recommendations(mock_ce_client, mock_config):
    """Test when AWS returns no Database SP recommendations."""
    mock_ce_client.get_savings_plans_purchase_recommendation.return_value = {
        "Metadata": {
            "RecommendationId": "rec-db-123",
            "GenerationTimestamp": "2026-01-15T11:00:00Z",
            "LookbackPeriodInDays": "30",
        },
        "SavingsPlansPurchaseRecommendation": {"SavingsPlansPurchaseRecommendationDetails": []},
    }

    result = recommendations._fetch_database_sp_recommendation(
        mock_ce_client, "THIRTY_DAYS"
    )

    assert result is None


def test_fetch_database_sp_recommendation_insufficient_data(mock_ce_client, mock_config):
    """Test Database SP recommendation with limited lookback data (still returns result)."""
    mock_ce_client.get_savings_plans_purchase_recommendation.return_value = {
        "Metadata": {
            "RecommendationId": "rec-db-123",
            "GenerationTimestamp": "2026-01-15T11:00:00Z",
            "LookbackPeriodInDays": "10",  # Limited data, but still valid
        },
        "SavingsPlansPurchaseRecommendation": {
            "SavingsPlansPurchaseRecommendationDetails": [{"HourlyCommitmentToPurchase": "2.75"}]
        },
    }

    result = recommendations._fetch_database_sp_recommendation(mock_ce_client, "SEVEN_DAYS")

    # min_data_days validation was removed, so recommendations with any data are accepted
    assert result is not None
    assert result["HourlyCommitmentToPurchase"] == "2.75"


def test_fetch_database_sp_recommendation_api_error(mock_ce_client, mock_config):
    """Test error handling when Database SP API call fails."""
    from botocore.exceptions import ClientError

    error_response = {"Error": {"Code": "ServiceUnavailable", "Message": "Service unavailable"}}
    mock_ce_client.get_savings_plans_purchase_recommendation.side_effect = ClientError(
        error_response, "get_savings_plans_purchase_recommendation"
    )

    with pytest.raises(ClientError):
        recommendations._fetch_database_sp_recommendation(
            mock_ce_client, "THIRTY_DAYS"
        )


# ============================================================================
# SageMaker SP Recommendation Tests
# ============================================================================


def test_fetch_sagemaker_sp_recommendation_success(mock_ce_client, mock_config):
    """Test successful SageMaker SP recommendation fetch."""
    mock_ce_client.get_savings_plans_purchase_recommendation.return_value = {
        "Metadata": {
            "RecommendationId": "rec-sm-456",
            "GenerationTimestamp": "2026-01-15T12:00:00Z",
            "LookbackPeriodInDays": "30",
        },
        "SavingsPlansPurchaseRecommendation": {
            "SavingsPlansPurchaseRecommendationDetails": [
                {
                    "HourlyCommitmentToPurchase": "3.25",
                    "EstimatedROI": "28.5",
                    "EstimatedSavingsAmount": "750.00",
                }
            ]
        },
    }

    result = recommendations._fetch_sagemaker_sp_recommendation(
        mock_ce_client, "THIRTY_DAYS"
    )

    assert result is not None
    assert result["HourlyCommitmentToPurchase"] == "3.25"
    assert result["RecommendationId"] == "rec-sm-456"


def test_fetch_sagemaker_sp_recommendation_no_recommendations(mock_ce_client, mock_config):
    """Test when AWS returns no SageMaker SP recommendations."""
    mock_ce_client.get_savings_plans_purchase_recommendation.return_value = {
        "Metadata": {
            "RecommendationId": "rec-sm-456",
            "GenerationTimestamp": "2026-01-15T12:00:00Z",
            "LookbackPeriodInDays": "30",
        },
        "SavingsPlansPurchaseRecommendation": {"SagingsPlansPurchaseRecommendationDetails": []},
    }

    result = recommendations._fetch_sagemaker_sp_recommendation(
        mock_ce_client, "THIRTY_DAYS"
    )

    assert result is None


def test_fetch_sagemaker_sp_recommendation_insufficient_data(mock_ce_client, mock_config):
    """Test SageMaker SP recommendation with limited lookback data (still returns result)."""
    mock_ce_client.get_savings_plans_purchase_recommendation.return_value = {
        "Metadata": {
            "RecommendationId": "rec-sm-456",
            "GenerationTimestamp": "2026-01-15T12:00:00Z",
            "LookbackPeriodInDays": "5",  # Limited data, but still valid
        },
        "SavingsPlansPurchaseRecommendation": {
            "SavingsPlansPurchaseRecommendationDetails": [{"HourlyCommitmentToPurchase": "3.25"}]
        },
    }

    result = recommendations._fetch_sagemaker_sp_recommendation(mock_ce_client, "SEVEN_DAYS")

    # min_data_days validation was removed, so recommendations with any data are accepted
    assert result is not None
    assert result["HourlyCommitmentToPurchase"] == "3.25"


def test_fetch_sagemaker_sp_recommendation_api_error(mock_ce_client, mock_config):
    """Test error handling when SageMaker SP API call fails."""
    from botocore.exceptions import ClientError

    error_response = {"Error": {"Code": "Throttling", "Message": "Rate exceeded"}}
    mock_ce_client.get_savings_plans_purchase_recommendation.side_effect = ClientError(
        error_response, "get_savings_plans_purchase_recommendation"
    )

    with pytest.raises(ClientError):
        recommendations._fetch_sagemaker_sp_recommendation(
            mock_ce_client, "THIRTY_DAYS"
        )


# ============================================================================
# Parallel Execution Tests (get_aws_recommendations)
# ============================================================================


def test_get_aws_recommendations_all_enabled(mock_ce_client, mock_config):
    """Test parallel fetching when all SP types are enabled."""

    # Mock responses for all three types
    def mock_get_recommendation(**kwargs):
        sp_type = kwargs.get("SavingsPlansType")
        if sp_type == "COMPUTE_SP":
            return {
                "Metadata": {
                    "RecommendationId": "rec-compute",
                    "GenerationTimestamp": "2026-01-15T10:00:00Z",
                    "LookbackPeriodInDays": "30",
                },
                "SavingsPlansPurchaseRecommendation": {
                    "SavingsPlansPurchaseRecommendationDetails": [
                        {"HourlyCommitmentToPurchase": "5.50"}
                    ]
                },
            }
        if sp_type == "DATABASE_SP":
            return {
                "Metadata": {
                    "RecommendationId": "rec-database",
                    "GenerationTimestamp": "2026-01-15T11:00:00Z",
                    "LookbackPeriodInDays": "30",
                },
                "SavingsPlansPurchaseRecommendation": {
                    "SavingsPlansPurchaseRecommendationDetails": [
                        {"HourlyCommitmentToPurchase": "2.75"}
                    ]
                },
            }
        if sp_type == "SAGEMAKER_SP":
            return {
                "Metadata": {
                    "RecommendationId": "rec-sagemaker",
                    "GenerationTimestamp": "2026-01-15T12:00:00Z",
                    "LookbackPeriodInDays": "30",
                },
                "SavingsPlansPurchaseRecommendation": {
                    "SavingsPlansPurchaseRecommendationDetails": [
                        {"HourlyCommitmentToPurchase": "3.25"}
                    ]
                },
            }

    mock_ce_client.get_savings_plans_purchase_recommendation.side_effect = mock_get_recommendation

    result = recommendations.get_aws_recommendations(mock_ce_client, mock_config)

    assert result["compute"] is not None
    assert result["database"] is not None
    assert result["sagemaker"] is not None
    assert result["compute"]["HourlyCommitmentToPurchase"] == "5.50"
    assert result["database"]["HourlyCommitmentToPurchase"] == "2.75"
    assert result["sagemaker"]["HourlyCommitmentToPurchase"] == "3.25"
    # Should have been called 3 times (once for each SP type)
    assert mock_ce_client.get_savings_plans_purchase_recommendation.call_count == 3


def test_get_aws_recommendations_only_compute_enabled(mock_ce_client):
    """Test when only Compute SP is enabled."""
    config = {
        "enable_compute_sp": True,
        "enable_database_sp": False,
        "enable_sagemaker_sp": False,
        "lookback_days": 30,
        "min_data_days": 14,
    }

    mock_ce_client.get_savings_plans_purchase_recommendation.return_value = {
        "Metadata": {
            "RecommendationId": "rec-compute",
            "GenerationTimestamp": "2026-01-15T10:00:00Z",
            "LookbackPeriodInDays": "30",
        },
        "SavingsPlansPurchaseRecommendation": {
            "SavingsPlansPurchaseRecommendationDetails": [{"HourlyCommitmentToPurchase": "5.50"}]
        },
    }

    result = recommendations.get_aws_recommendations(mock_ce_client, config)

    assert result["compute"] is not None
    assert result["database"] is None
    assert result["sagemaker"] is None
    # Should only be called once
    assert mock_ce_client.get_savings_plans_purchase_recommendation.call_count == 1


def test_get_aws_recommendations_lookback_period_mapping(mock_ce_client):
    """Test lookback period mapping to AWS API values."""
    config = {
        "enable_compute_sp": True,
        "enable_database_sp": False,
        "enable_sagemaker_sp": False,
        "lookback_days": 7,  # Should map to SEVEN_DAYS
        "min_data_days": 14,
    }

    mock_ce_client.get_savings_plans_purchase_recommendation.return_value = {
        "Metadata": {
            "RecommendationId": "rec-compute",
            "GenerationTimestamp": "2026-01-15T10:00:00Z",
            "LookbackPeriodInDays": "7",
        },
        "SavingsPlansPurchaseRecommendation": {
            "SavingsPlansPurchaseRecommendationDetails": [{"HourlyCommitmentToPurchase": "5.50"}]
        },
    }

    result = recommendations.get_aws_recommendations(mock_ce_client, config)

    # Verify the API was called with SEVEN_DAYS
    call_args = mock_ce_client.get_savings_plans_purchase_recommendation.call_args
    assert call_args[1]["LookbackPeriodInDays"] == "SEVEN_DAYS"


def test_get_aws_recommendations_sixty_days_lookback(mock_ce_client):
    """Test lookback period mapping for 60 days."""
    config = {
        "enable_compute_sp": True,
        "enable_database_sp": False,
        "enable_sagemaker_sp": False,
        "lookback_days": 60,  # Should map to SIXTY_DAYS
        "min_data_days": 14,
    }

    mock_ce_client.get_savings_plans_purchase_recommendation.return_value = {
        "Metadata": {
            "RecommendationId": "rec-compute",
            "GenerationTimestamp": "2026-01-15T10:00:00Z",
            "LookbackPeriodInDays": "60",
        },
        "SavingsPlansPurchaseRecommendation": {
            "SavingsPlansPurchaseRecommendationDetails": [{"HourlyCommitmentToPurchase": "5.50"}]
        },
    }

    result = recommendations.get_aws_recommendations(mock_ce_client, config)

    # Verify the API was called with SIXTY_DAYS
    call_args = mock_ce_client.get_savings_plans_purchase_recommendation.call_args
    assert call_args[1]["LookbackPeriodInDays"] == "SIXTY_DAYS"


def test_get_aws_recommendations_all_disabled(mock_ce_client):
    """Test when all SP types are disabled."""
    config = {
        "enable_compute_sp": False,
        "enable_database_sp": False,
        "enable_sagemaker_sp": False,
        "lookback_days": 30,
        "min_data_days": 14,
    }

    result = recommendations.get_aws_recommendations(mock_ce_client, config)

    assert result["compute"] is None
    assert result["database"] is None
    assert result["sagemaker"] is None
    # Should not make any API calls
    assert mock_ce_client.get_savings_plans_purchase_recommendation.call_count == 0


def test_get_aws_recommendations_one_fails_others_succeed(mock_ce_client, mock_config):
    """Test error propagation when one recommendation fetch fails."""
    from botocore.exceptions import ClientError

    def mock_get_recommendation(**kwargs):
        sp_type = kwargs.get("SavingsPlansType")
        if sp_type == "COMPUTE_SP":
            return {
                "Metadata": {
                    "RecommendationId": "rec-compute",
                    "GenerationTimestamp": "2026-01-15T10:00:00Z",
                    "LookbackPeriodInDays": "30",
                },
                "SavingsPlansPurchaseRecommendation": {
                    "SavingsPlansPurchaseRecommendationDetails": [
                        {"HourlyCommitmentToPurchase": "5.50"}
                    ]
                },
            }
        if sp_type == "DATABASE_SP":
            # Fail for database
            error_response = {
                "Error": {"Code": "ServiceUnavailable", "Message": "Service unavailable"}
            }
            raise ClientError(error_response, "get_savings_plans_purchase_recommendation")
        if sp_type == "SAGEMAKER_SP":
            return {
                "Metadata": {
                    "RecommendationId": "rec-sagemaker",
                    "GenerationTimestamp": "2026-01-15T12:00:00Z",
                    "LookbackPeriodInDays": "30",
                },
                "SavingsPlansPurchaseRecommendation": {
                    "SavingsPlansPurchaseRecommendationDetails": [
                        {"HourlyCommitmentToPurchase": "3.25"}
                    ]
                },
            }

    mock_ce_client.get_savings_plans_purchase_recommendation.side_effect = mock_get_recommendation

    # Should raise the error from the failed fetch
    with pytest.raises(ClientError):
        recommendations.get_aws_recommendations(mock_ce_client, mock_config)

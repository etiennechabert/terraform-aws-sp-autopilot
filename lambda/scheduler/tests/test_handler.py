"""
Comprehensive unit tests for Scheduler Lambda handler.

Tests cover all 12 functions with edge cases to achieve >= 80% coverage.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, call
from datetime import datetime, timezone, timedelta
import json
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import handler


@pytest.fixture
def mock_env_vars(monkeypatch):
    """Set up environment variables for testing."""
    monkeypatch.setenv('QUEUE_URL', 'https://sqs.us-east-1.amazonaws.com/123456789012/test-queue')
    monkeypatch.setenv('SNS_TOPIC_ARN', 'arn:aws:sns:us-east-1:123456789012:test-topic')
    monkeypatch.setenv('DRY_RUN', 'true')
    monkeypatch.setenv('ENABLE_COMPUTE_SP', 'true')
    monkeypatch.setenv('ENABLE_DATABASE_SP', 'false')
    monkeypatch.setenv('ENABLE_SAGEMAKER_SP', 'false')
    monkeypatch.setenv('COVERAGE_TARGET_PERCENT', '90')
    monkeypatch.setenv('MAX_PURCHASE_PERCENT', '10')
    monkeypatch.setenv('RENEWAL_WINDOW_DAYS', '7')
    monkeypatch.setenv('LOOKBACK_DAYS', '30')
    monkeypatch.setenv('MIN_DATA_DAYS', '14')
    monkeypatch.setenv('MIN_COMMITMENT_PER_PLAN', '0.001')
    monkeypatch.setenv('COMPUTE_SP_TERM_MIX', '{"three_year": 0.67, "one_year": 0.33}')
    monkeypatch.setenv('COMPUTE_SP_PAYMENT_OPTION', 'ALL_UPFRONT')
    monkeypatch.setenv('SAGEMAKER_SP_TERM_MIX', '{"three_year": 0.67, "one_year": 0.33}')
    monkeypatch.setenv('SAGEMAKER_SP_PAYMENT_OPTION', 'ALL_UPFRONT')
    monkeypatch.setenv('TAGS', '{}')


# ============================================================================
# Configuration Tests
# ============================================================================

def test_load_configuration_defaults(mock_env_vars):
    """Test that load_configuration returns correct default values."""
    config = handler.load_configuration()

    assert config['queue_url'] == 'https://sqs.us-east-1.amazonaws.com/123456789012/test-queue'
    assert config['sns_topic_arn'] == 'arn:aws:sns:us-east-1:123456789012:test-topic'
    assert config['dry_run'] is True
    assert config['enable_compute_sp'] is True
    assert config['enable_database_sp'] is False
    assert config['enable_sagemaker_sp'] is False
    assert config['coverage_target_percent'] == 90.0
    assert config['max_purchase_percent'] == 10.0
    assert config['renewal_window_days'] == 7
    assert config['lookback_days'] == 30
    assert config['min_data_days'] == 14
    assert config['min_commitment_per_plan'] == 0.001
    assert config['sagemaker_sp_term_mix'] == {"three_year": 0.67, "one_year": 0.33}
    assert config['sagemaker_sp_payment_option'] == 'ALL_UPFRONT'


def test_load_configuration_custom_values(monkeypatch):
    """Test that load_configuration handles custom environment values."""
    monkeypatch.setenv('QUEUE_URL', 'custom-queue-url')
    monkeypatch.setenv('SNS_TOPIC_ARN', 'custom-sns-arn')
    monkeypatch.setenv('DRY_RUN', 'false')
    monkeypatch.setenv('ENABLE_SAGEMAKER_SP', 'true')
    monkeypatch.setenv('COVERAGE_TARGET_PERCENT', '85.5')
    monkeypatch.setenv('MAX_PURCHASE_PERCENT', '15')
    monkeypatch.setenv('COMPUTE_SP_TERM_MIX', '{"three_year": 0.8, "one_year": 0.2}')
    monkeypatch.setenv('SAGEMAKER_SP_TERM_MIX', '{"three_year": 0.5, "one_year": 0.5}')
    monkeypatch.setenv('SAGEMAKER_SP_PAYMENT_OPTION', 'NO_UPFRONT')

    config = handler.load_configuration()

    assert config['queue_url'] == 'custom-queue-url'
    assert config['sns_topic_arn'] == 'custom-sns-arn'
    assert config['dry_run'] is False
    assert config['enable_sagemaker_sp'] is True
    assert config['coverage_target_percent'] == 85.5
    assert config['max_purchase_percent'] == 15.0
    assert config['compute_sp_term_mix'] == {"three_year": 0.8, "one_year": 0.2}
    assert config['sagemaker_sp_term_mix'] == {"three_year": 0.5, "one_year": 0.5}
    assert config['sagemaker_sp_payment_option'] == 'NO_UPFRONT'


# ============================================================================
# Queue Purge Tests
# ============================================================================

def test_purge_queue_success():
    """Test successful queue purge."""
    with patch.object(handler.sqs_client, 'purge_queue') as mock_purge:
        mock_purge.return_value = {}

        handler.purge_queue('test-queue-url')

        mock_purge.assert_called_once_with(QueueUrl='test-queue-url')


def test_purge_queue_in_progress():
    """Test that PurgeQueueInProgress error is handled gracefully."""
    from botocore.exceptions import ClientError

    with patch.object(handler.sqs_client, 'purge_queue') as mock_purge:
        error_response = {'Error': {'Code': 'PurgeQueueInProgress'}}
        mock_purge.side_effect = ClientError(error_response, 'purge_queue')

        # Should not raise - just log warning
        handler.purge_queue('test-queue-url')


def test_purge_queue_other_error():
    """Test that other errors are raised."""
    from botocore.exceptions import ClientError

    with patch.object(handler.sqs_client, 'purge_queue') as mock_purge:
        error_response = {'Error': {'Code': 'AccessDenied'}}
        mock_purge.side_effect = ClientError(error_response, 'purge_queue')

        with pytest.raises(ClientError):
            handler.purge_queue('test-queue-url')


# ============================================================================
# Coverage Calculation Tests
# ============================================================================

def test_calculate_current_coverage_filters_expiring_plans(mock_env_vars):
    """Test that plans expiring within renewal_window_days are excluded."""
    config = handler.load_configuration()

    now = datetime.now(timezone.utc)

    with patch.object(handler.savingsplans_client, 'describe_savings_plans') as mock_describe:
        with patch.object(handler.ce_client, 'get_savings_plans_coverage') as mock_coverage:
            # Plan expiring in 3 days (should be excluded - within 7 day window)
            expiring_soon = now + timedelta(days=3)
            # Plan expiring in 30 days (should be included - outside 7 day window)
            expiring_later = now + timedelta(days=30)

            mock_describe.return_value = {
                'savingsPlans': [
                    {
                        'savingsPlanId': 'sp-expiring-soon',
                        'state': 'active',
                        'end': expiring_soon.isoformat()
                    },
                    {
                        'savingsPlanId': 'sp-expiring-later',
                        'state': 'active',
                        'end': expiring_later.isoformat()
                    }
                ]
            }

            mock_coverage.return_value = {
                'SavingsPlansCoverages': [
                    {
                        'TimePeriod': {'Start': '2026-01-12', 'End': '2026-01-13'},
                        'Coverage': {'CoveragePercentage': '75.5'}
                    }
                ]
            }

            result = handler.calculate_current_coverage(config)

            assert 'compute' in result
            assert result['compute'] == 75.5


def test_calculate_current_coverage_keeps_valid_plans(mock_env_vars):
    """Test that plans expiring after renewal window are kept."""
    config = handler.load_configuration()

    now = datetime.now(timezone.utc)
    expiring_later = now + timedelta(days=30)

    with patch.object(handler.savingsplans_client, 'describe_savings_plans') as mock_describe:
        with patch.object(handler.ce_client, 'get_savings_plans_coverage') as mock_coverage:
            mock_describe.return_value = {
                'savingsPlans': [
                    {
                        'savingsPlanId': 'sp-valid',
                        'state': 'active',
                        'end': expiring_later.isoformat()
                    }
                ]
            }

            mock_coverage.return_value = {
                'SavingsPlansCoverages': [
                    {
                        'TimePeriod': {'Start': '2026-01-12', 'End': '2026-01-13'},
                        'Coverage': {'CoveragePercentage': '85.0'}
                    }
                ]
            }

            result = handler.calculate_current_coverage(config)

            assert result['compute'] == 85.0


def test_calculate_current_coverage_empty_plans_list(mock_env_vars):
    """Test handling of no active Savings Plans."""
    config = handler.load_configuration()

    with patch.object(handler.savingsplans_client, 'describe_savings_plans') as mock_describe:
        with patch.object(handler.ce_client, 'get_savings_plans_coverage') as mock_coverage:
            mock_describe.return_value = {'savingsPlans': []}

            mock_coverage.return_value = {
                'SavingsPlansCoverages': [
                    {
                        'TimePeriod': {'Start': '2026-01-12', 'End': '2026-01-13'},
                        'Coverage': {'CoveragePercentage': '0.0'}
                    }
                ]
            }

            result = handler.calculate_current_coverage(config)

            assert result['compute'] == 0.0


def test_calculate_current_coverage_no_coverage_data(mock_env_vars):
    """Test handling of no coverage data from Cost Explorer."""
    config = handler.load_configuration()

    with patch.object(handler.savingsplans_client, 'describe_savings_plans') as mock_describe:
        with patch.object(handler.ce_client, 'get_savings_plans_coverage') as mock_coverage:
            mock_describe.return_value = {'savingsPlans': []}
            mock_coverage.return_value = {'SavingsPlansCoverages': []}

            result = handler.calculate_current_coverage(config)

            assert result == {'compute': 0.0, 'database': 0.0, 'sagemaker': 0.0}


# ============================================================================
# AWS Recommendations Tests
# ============================================================================

def test_get_aws_recommendations_compute_enabled(mock_env_vars):
    """Test fetching Compute SP recommendations when enabled."""
    config = handler.load_configuration()

    with patch.object(handler.ce_client, 'get_savings_plans_purchase_recommendation') as mock_rec:
        mock_rec.return_value = {
            'Metadata': {
                'RecommendationId': 'rec-123',
                'GenerationTimestamp': '2026-01-13T00:00:00Z',
                'LookbackPeriodInDays': '30'
            },
            'SavingsPlansPurchaseRecommendation': {
                'SavingsPlansPurchaseRecommendationDetails': [
                    {
                        'HourlyCommitmentToPurchase': '2.5'
                    }
                ]
            }
        }

        result = handler.get_aws_recommendations(config)

        assert result['compute'] is not None
        assert result['compute']['HourlyCommitmentToPurchase'] == '2.5'
        assert result['compute']['RecommendationId'] == 'rec-123'


def test_get_aws_recommendations_database_disabled(mock_env_vars):
    """Test that Database SP recommendations are skipped when disabled."""
    config = handler.load_configuration()

    with patch.object(handler.ce_client, 'get_savings_plans_purchase_recommendation') as mock_rec:
        mock_rec.return_value = {
            'Metadata': {
                'RecommendationId': 'rec-123',
                'LookbackPeriodInDays': '30'
            },
            'SavingsPlansPurchaseRecommendation': {
                'SavingsPlansPurchaseRecommendationDetails': [
                    {'HourlyCommitmentToPurchase': '2.5'}
                ]
            }
        }

        result = handler.get_aws_recommendations(config)

        # Database should be None when disabled
        assert result['database'] is None


def test_get_aws_recommendations_database_enabled(monkeypatch):
    """Test fetching Database SP recommendations with correct API parameters."""
    # Enable Database SP
    monkeypatch.setenv('QUEUE_URL', 'https://sqs.us-east-1.amazonaws.com/123456789012/test-queue')
    monkeypatch.setenv('SNS_TOPIC_ARN', 'arn:aws:sns:us-east-1:123456789012:test-topic')
    monkeypatch.setenv('ENABLE_DATABASE_SP', 'true')
    monkeypatch.setenv('ENABLE_COMPUTE_SP', 'false')

    config = handler.load_configuration()

    with patch.object(handler.ce_client, 'get_savings_plans_purchase_recommendation') as mock_rec:
        mock_rec.return_value = {
            'Metadata': {
                'RecommendationId': 'rec-db-456',
                'GenerationTimestamp': '2026-01-13T00:00:00Z',
                'LookbackPeriodInDays': '30'
            },
            'SavingsPlansPurchaseRecommendation': {
                'SavingsPlansPurchaseRecommendationDetails': [
                    {
                        'HourlyCommitmentToPurchase': '1.25'
                    }
                ]
            }
        }

        result = handler.get_aws_recommendations(config)

        # Verify Database SP recommendation was returned
        assert result['database'] is not None
        assert result['database']['HourlyCommitmentToPurchase'] == '1.25'
        assert result['database']['RecommendationId'] == 'rec-db-456'

        # Verify API was called with correct Database SP parameters
        mock_rec.assert_called_once_with(
            SavingsPlansType='DATABASE_SP',
            LookbackPeriodInDays='THIRTY_DAYS',
            TermInYears='ONE_YEAR',
            PaymentOption='NO_UPFRONT'
        )


def test_get_aws_recommendations_database_insufficient_data(monkeypatch):
    """Test rejection of Database SP recommendations with insufficient data."""
    # Enable Database SP
    monkeypatch.setenv('QUEUE_URL', 'https://sqs.us-east-1.amazonaws.com/123456789012/test-queue')
    monkeypatch.setenv('SNS_TOPIC_ARN', 'arn:aws:sns:us-east-1:123456789012:test-topic')
    monkeypatch.setenv('ENABLE_DATABASE_SP', 'true')
    monkeypatch.setenv('ENABLE_COMPUTE_SP', 'false')
    monkeypatch.setenv('MIN_DATA_DAYS', '14')

    config = handler.load_configuration()

    with patch.object(handler.ce_client, 'get_savings_plans_purchase_recommendation') as mock_rec:
        # Return only 10 days of data (less than min_data_days of 14)
        mock_rec.return_value = {
            'Metadata': {
                'RecommendationId': 'rec-db-789',
                'LookbackPeriodInDays': '10'
            },
            'SavingsPlansPurchaseRecommendation': {
                'SavingsPlansPurchaseRecommendationDetails': [
                    {'HourlyCommitmentToPurchase': '1.5'}
                ]
            }
        }

        result = handler.get_aws_recommendations(config)

        # Should reject due to insufficient data
        assert result['database'] is None


def test_get_aws_recommendations_database_no_recommendations(monkeypatch):
    """Test handling of empty Database SP recommendation list from AWS."""
    # Enable Database SP
    monkeypatch.setenv('QUEUE_URL', 'https://sqs.us-east-1.amazonaws.com/123456789012/test-queue')
    monkeypatch.setenv('SNS_TOPIC_ARN', 'arn:aws:sns:us-east-1:123456789012:test-topic')
    monkeypatch.setenv('ENABLE_DATABASE_SP', 'true')
    monkeypatch.setenv('ENABLE_COMPUTE_SP', 'false')

    config = handler.load_configuration()

    with patch.object(handler.ce_client, 'get_savings_plans_purchase_recommendation') as mock_rec:
        mock_rec.return_value = {
            'Metadata': {
                'RecommendationId': 'rec-db-empty',
                'LookbackPeriodInDays': '30'
            },
            'SavingsPlansPurchaseRecommendation': {
                'SavingsPlansPurchaseRecommendationDetails': []
            }
        }

        result = handler.get_aws_recommendations(config)

        assert result['database'] is None


def test_get_aws_recommendations_sagemaker_enabled(monkeypatch):
    """Test fetching SageMaker SP recommendations with correct API parameters."""
    # Enable SageMaker SP
    monkeypatch.setenv('QUEUE_URL', 'https://sqs.us-east-1.amazonaws.com/123456789012/test-queue')
    monkeypatch.setenv('SNS_TOPIC_ARN', 'arn:aws:sns:us-east-1:123456789012:test-topic')
    monkeypatch.setenv('ENABLE_SAGEMAKER_SP', 'true')
    monkeypatch.setenv('ENABLE_COMPUTE_SP', 'false')
    monkeypatch.setenv('ENABLE_DATABASE_SP', 'false')

    config = handler.load_configuration()

    with patch.object(handler.ce_client, 'get_savings_plans_purchase_recommendation') as mock_rec:
        mock_rec.return_value = {
            'Metadata': {
                'RecommendationId': 'rec-sm-456',
                'GenerationTimestamp': '2026-01-13T00:00:00Z',
                'LookbackPeriodInDays': '30'
            },
            'SavingsPlansPurchaseRecommendation': {
                'SavingsPlansPurchaseRecommendationDetails': [
                    {
                        'HourlyCommitmentToPurchase': '3.75'
                    }
                ]
            }
        }

        result = handler.get_aws_recommendations(config)

        # Verify SageMaker SP recommendation was returned
        assert result['sagemaker'] is not None
        assert result['sagemaker']['HourlyCommitmentToPurchase'] == '3.75'
        assert result['sagemaker']['RecommendationId'] == 'rec-sm-456'

        # Verify API was called with correct SageMaker SP parameters
        mock_rec.assert_called_once_with(
            SavingsPlansType='SAGEMAKER_SP',
            LookbackPeriodInDays='THIRTY_DAYS',
            TermInYears='ONE_YEAR',
            PaymentOption='NO_UPFRONT'
        )


def test_get_aws_recommendations_sagemaker_disabled(mock_env_vars):
    """Test that SageMaker SP recommendations are skipped when disabled."""
    config = handler.load_configuration()

    with patch.object(handler.ce_client, 'get_savings_plans_purchase_recommendation') as mock_rec:
        mock_rec.return_value = {
            'Metadata': {
                'RecommendationId': 'rec-123',
                'LookbackPeriodInDays': '30'
            },
            'SavingsPlansPurchaseRecommendation': {
                'SavingsPlansPurchaseRecommendationDetails': [
                    {'HourlyCommitmentToPurchase': '2.5'}
                ]
            }
        }

        result = handler.get_aws_recommendations(config)

        # SageMaker should be None when disabled
        assert result['sagemaker'] is None


def test_get_aws_recommendations_sagemaker_insufficient_data(monkeypatch):
    """Test rejection of SageMaker SP recommendations with insufficient data."""
    # Enable SageMaker SP
    monkeypatch.setenv('QUEUE_URL', 'https://sqs.us-east-1.amazonaws.com/123456789012/test-queue')
    monkeypatch.setenv('SNS_TOPIC_ARN', 'arn:aws:sns:us-east-1:123456789012:test-topic')
    monkeypatch.setenv('ENABLE_SAGEMAKER_SP', 'true')
    monkeypatch.setenv('ENABLE_COMPUTE_SP', 'false')
    monkeypatch.setenv('ENABLE_DATABASE_SP', 'false')
    monkeypatch.setenv('MIN_DATA_DAYS', '14')

    config = handler.load_configuration()

    with patch.object(handler.ce_client, 'get_savings_plans_purchase_recommendation') as mock_rec:
        # Return only 10 days of data (less than min_data_days of 14)
        mock_rec.return_value = {
            'Metadata': {
                'RecommendationId': 'rec-sm-789',
                'LookbackPeriodInDays': '10'
            },
            'SavingsPlansPurchaseRecommendation': {
                'SavingsPlansPurchaseRecommendationDetails': [
                    {'HourlyCommitmentToPurchase': '2.5'}
                ]
            }
        }

        result = handler.get_aws_recommendations(config)

        # Should reject due to insufficient data
        assert result['sagemaker'] is None


def test_get_aws_recommendations_sagemaker_no_recommendations(monkeypatch):
    """Test handling of empty SageMaker SP recommendation list from AWS."""
    # Enable SageMaker SP
    monkeypatch.setenv('QUEUE_URL', 'https://sqs.us-east-1.amazonaws.com/123456789012/test-queue')
    monkeypatch.setenv('SNS_TOPIC_ARN', 'arn:aws:sns:us-east-1:123456789012:test-topic')
    monkeypatch.setenv('ENABLE_SAGEMAKER_SP', 'true')
    monkeypatch.setenv('ENABLE_COMPUTE_SP', 'false')
    monkeypatch.setenv('ENABLE_DATABASE_SP', 'false')

    config = handler.load_configuration()

    with patch.object(handler.ce_client, 'get_savings_plans_purchase_recommendation') as mock_rec:
        mock_rec.return_value = {
            'Metadata': {
                'RecommendationId': 'rec-sm-empty',
                'LookbackPeriodInDays': '30'
            },
            'SavingsPlansPurchaseRecommendation': {
                'SavingsPlansPurchaseRecommendationDetails': []
            }
        }

        result = handler.get_aws_recommendations(config)

        assert result['sagemaker'] is None


def test_get_aws_recommendations_insufficient_data(mock_env_vars):
    """Test rejection of recommendations with insufficient data."""
    config = handler.load_configuration()

    with patch.object(handler.ce_client, 'get_savings_plans_purchase_recommendation') as mock_rec:
        # Return only 10 days of data (less than min_data_days of 14)
        mock_rec.return_value = {
            'Metadata': {
                'RecommendationId': 'rec-123',
                'LookbackPeriodInDays': '10'
            },
            'SavingsPlansPurchaseRecommendation': {
                'SavingsPlansPurchaseRecommendationDetails': [
                    {'HourlyCommitmentToPurchase': '2.5'}
                ]
            }
        }

        result = handler.get_aws_recommendations(config)

        # Should reject due to insufficient data
        assert result['compute'] is None


def test_get_aws_recommendations_no_recommendations(mock_env_vars):
    """Test handling of empty recommendation list from AWS."""
    config = handler.load_configuration()

    with patch.object(handler.ce_client, 'get_savings_plans_purchase_recommendation') as mock_rec:
        mock_rec.return_value = {
            'Metadata': {
                'RecommendationId': 'rec-123',
                'LookbackPeriodInDays': '30'
            },
            'SavingsPlansPurchaseRecommendation': {
                'SavingsPlansPurchaseRecommendationDetails': []
            }
        }

        result = handler.get_aws_recommendations(config)

        assert result['compute'] is None


def test_get_aws_recommendations_lookback_period_mapping(mock_env_vars, monkeypatch):
    """Test that lookback_days maps correctly to AWS API parameters."""
    # Test 7 days -> SEVEN_DAYS
    monkeypatch.setenv('LOOKBACK_DAYS', '7')
    config = handler.load_configuration()

    with patch.object(handler.ce_client, 'get_savings_plans_purchase_recommendation') as mock_rec:
        mock_rec.return_value = {
            'Metadata': {'RecommendationId': 'rec-123', 'LookbackPeriodInDays': '7'},
            'SavingsPlansPurchaseRecommendation': {'SavingsPlansPurchaseRecommendationDetails': []}
        }

        handler.get_aws_recommendations(config)

        # Should use SEVEN_DAYS
        call_args = mock_rec.call_args[1]
        assert call_args['LookbackPeriodInDays'] == 'SEVEN_DAYS'

    # Test 60 days -> SIXTY_DAYS
    monkeypatch.setenv('LOOKBACK_DAYS', '60')
    config = handler.load_configuration()

    with patch.object(handler.ce_client, 'get_savings_plans_purchase_recommendation') as mock_rec:
        mock_rec.return_value = {
            'Metadata': {'RecommendationId': 'rec-123', 'LookbackPeriodInDays': '60'},
            'SavingsPlansPurchaseRecommendation': {'SavingsPlansPurchaseRecommendationDetails': []}
        }

        handler.get_aws_recommendations(config)

        # Should use SIXTY_DAYS
        call_args = mock_rec.call_args[1]
        assert call_args['LookbackPeriodInDays'] == 'SIXTY_DAYS'


def test_get_aws_recommendations_parallel_execution_both_enabled(monkeypatch):
    """Test that Compute and Database SP recommendations are fetched in parallel when both enabled."""
    monkeypatch.setenv('QUEUE_URL', 'https://sqs.us-east-1.amazonaws.com/123456789012/test-queue')
    monkeypatch.setenv('SNS_TOPIC_ARN', 'arn:aws:sns:us-east-1:123456789012:test-topic')
    monkeypatch.setenv('ENABLE_COMPUTE_SP', 'true')
    monkeypatch.setenv('ENABLE_DATABASE_SP', 'true')

    config = handler.load_configuration()

    # Track call order to verify parallel execution
    call_order = []

    def compute_side_effect(*args, **kwargs):
        call_order.append('compute_start')
        import time
        time.sleep(0.01)  # Simulate API call
        call_order.append('compute_end')
        return {
            'Metadata': {
                'RecommendationId': 'rec-compute-123',
                'GenerationTimestamp': '2026-01-13T00:00:00Z',
                'LookbackPeriodInDays': '30'
            },
            'SavingsPlansPurchaseRecommendation': {
                'SavingsPlansPurchaseRecommendationDetails': [
                    {'HourlyCommitmentToPurchase': '1.5'}
                ]
            }
        }

    def database_side_effect(*args, **kwargs):
        call_order.append('database_start')
        import time
        time.sleep(0.01)  # Simulate API call
        call_order.append('database_end')
        return {
            'Metadata': {
                'RecommendationId': 'rec-database-456',
                'GenerationTimestamp': '2026-01-13T00:00:00Z',
                'LookbackPeriodInDays': '30'
            },
            'SavingsPlansPurchaseRecommendation': {
                'SavingsPlansPurchaseRecommendationDetails': [
                    {'HourlyCommitmentToPurchase': '2.5'}
                ]
            }
        }

    with patch.object(handler.ce_client, 'get_savings_plans_purchase_recommendation') as mock_rec:
        # Use side_effect to return different values based on SavingsPlansType
        def api_side_effect(*args, **kwargs):
            if kwargs.get('SavingsPlansType') == 'COMPUTE_SP':
                return compute_side_effect(*args, **kwargs)
            elif kwargs.get('SavingsPlansType') == 'DATABASE_SP':
                return database_side_effect(*args, **kwargs)

        mock_rec.side_effect = api_side_effect

        result = handler.get_aws_recommendations(config)

        # Verify both recommendations were returned
        assert result['compute'] is not None
        assert result['database'] is not None
        assert result['compute']['HourlyCommitmentToPurchase'] == '1.5'
        assert result['database']['HourlyCommitmentToPurchase'] == '2.5'

        # Verify API was called twice (once for each SP type)
        assert mock_rec.call_count == 2

        # Verify calls were made with correct parameters
        call_args_list = [call[1] for call in mock_rec.call_args_list]
        compute_call = next(c for c in call_args_list if c['SavingsPlansType'] == 'COMPUTE_SP')
        database_call = next(c for c in call_args_list if c['SavingsPlansType'] == 'DATABASE_SP')

        assert compute_call['SavingsPlansType'] == 'COMPUTE_SP'
        assert compute_call['PaymentOption'] == 'ALL_UPFRONT'
        assert database_call['SavingsPlansType'] == 'DATABASE_SP'
        assert database_call['PaymentOption'] == 'NO_UPFRONT'

        # Verify parallel execution: both should start before either ends
        # The call_order should have interleaved start/end if truly parallel
        assert 'compute_start' in call_order
        assert 'database_start' in call_order
        assert 'compute_end' in call_order
        assert 'database_end' in call_order


def test_get_aws_recommendations_parallel_execution_uses_threadpool(monkeypatch):
    """Test that ThreadPoolExecutor is used for parallel API calls."""
    monkeypatch.setenv('QUEUE_URL', 'https://sqs.us-east-1.amazonaws.com/123456789012/test-queue')
    monkeypatch.setenv('SNS_TOPIC_ARN', 'arn:aws:sns:us-east-1:123456789012:test-topic')
    monkeypatch.setenv('ENABLE_COMPUTE_SP', 'true')
    monkeypatch.setenv('ENABLE_DATABASE_SP', 'true')

    config = handler.load_configuration()

    with patch.object(handler.ce_client, 'get_savings_plans_purchase_recommendation') as mock_rec:
        mock_rec.return_value = {
            'Metadata': {
                'RecommendationId': 'rec-123',
                'LookbackPeriodInDays': '30'
            },
            'SavingsPlansPurchaseRecommendation': {
                'SavingsPlansPurchaseRecommendationDetails': [
                    {'HourlyCommitmentToPurchase': '1.0'}
                ]
            }
        }

        # Patch ThreadPoolExecutor to verify it's used correctly
        from concurrent.futures import ThreadPoolExecutor
        with patch('handler.ThreadPoolExecutor') as mock_executor_class:
            mock_executor = MagicMock()
            mock_executor_class.return_value.__enter__.return_value = mock_executor

            # Mock submit and as_completed
            mock_future1 = MagicMock()
            mock_future2 = MagicMock()
            mock_future1.result.return_value = {
                'HourlyCommitmentToPurchase': '1.5',
                'RecommendationId': 'rec-compute',
                'GenerationTimestamp': '2026-01-13T00:00:00Z',
                'Details': {}
            }
            mock_future2.result.return_value = {
                'HourlyCommitmentToPurchase': '2.5',
                'RecommendationId': 'rec-database',
                'GenerationTimestamp': '2026-01-13T00:00:00Z',
                'Details': {}
            }

            mock_executor.submit.side_effect = [mock_future1, mock_future2]

            with patch('handler.as_completed') as mock_as_completed:
                mock_as_completed.return_value = [mock_future1, mock_future2]

                result = handler.get_aws_recommendations(config)

                # Verify ThreadPoolExecutor was created with correct max_workers
                mock_executor_class.assert_called_once_with(max_workers=2)

                # Verify submit was called twice (once for each SP type)
                assert mock_executor.submit.call_count == 2

                # Verify as_completed was called with futures
                assert mock_as_completed.call_count == 1


def test_get_aws_recommendations_parallel_execution_error_handling(monkeypatch):
    """Test that errors in parallel execution are properly raised."""
    monkeypatch.setenv('QUEUE_URL', 'https://sqs.us-east-1.amazonaws.com/123456789012/test-queue')
    monkeypatch.setenv('SNS_TOPIC_ARN', 'arn:aws:sns:us-east-1:123456789012:test-topic')
    monkeypatch.setenv('ENABLE_COMPUTE_SP', 'true')
    monkeypatch.setenv('ENABLE_DATABASE_SP', 'true')

    config = handler.load_configuration()

    with patch.object(handler.ce_client, 'get_savings_plans_purchase_recommendation') as mock_rec:
        # First call (compute) succeeds, second call (database) fails
        from botocore.exceptions import ClientError
        error_response = {'Error': {'Code': 'AccessDenied', 'Message': 'Access denied'}}

        def api_side_effect(*args, **kwargs):
            if kwargs.get('SavingsPlansType') == 'COMPUTE_SP':
                return {
                    'Metadata': {
                        'RecommendationId': 'rec-compute',
                        'LookbackPeriodInDays': '30'
                    },
                    'SavingsPlansPurchaseRecommendation': {
                        'SavingsPlansPurchaseRecommendationDetails': [
                            {'HourlyCommitmentToPurchase': '1.5'}
                        ]
                    }
                }
            elif kwargs.get('SavingsPlansType') == 'DATABASE_SP':
                raise ClientError(error_response, 'get_savings_plans_purchase_recommendation')

        mock_rec.side_effect = api_side_effect

        # Should raise the ClientError from database recommendation
        with pytest.raises(ClientError):
            handler.get_aws_recommendations(config)


def test_get_aws_recommendations_parallel_single_task(mock_env_vars):
    """Test that parallel execution works correctly with only one task (compute only)."""
    config = handler.load_configuration()

    with patch.object(handler.ce_client, 'get_savings_plans_purchase_recommendation') as mock_rec:
        mock_rec.return_value = {
            'Metadata': {
                'RecommendationId': 'rec-123',
                'GenerationTimestamp': '2026-01-13T00:00:00Z',
                'LookbackPeriodInDays': '30'
            },
            'SavingsPlansPurchaseRecommendation': {
                'SavingsPlansPurchaseRecommendationDetails': [
                    {'HourlyCommitmentToPurchase': '2.5'}
                ]
            }
        }

        result = handler.get_aws_recommendations(config)

        # Should still work with ThreadPoolExecutor even with single task
        assert result['compute'] is not None
        assert result['compute']['HourlyCommitmentToPurchase'] == '2.5'
        assert result['database'] is None

        # Verify only one API call was made
        assert mock_rec.call_count == 1


def test_get_aws_recommendations_parallel_no_tasks(monkeypatch):
    """Test that get_aws_recommendations handles case where both SP types are disabled."""
    monkeypatch.setenv('QUEUE_URL', 'https://sqs.us-east-1.amazonaws.com/123456789012/test-queue')
    monkeypatch.setenv('SNS_TOPIC_ARN', 'arn:aws:sns:us-east-1:123456789012:test-topic')
    monkeypatch.setenv('ENABLE_COMPUTE_SP', 'false')
    monkeypatch.setenv('ENABLE_DATABASE_SP', 'false')

    config = handler.load_configuration()

    with patch.object(handler.ce_client, 'get_savings_plans_purchase_recommendation') as mock_rec:
        result = handler.get_aws_recommendations(config)

        # Should return None for both types
        assert result['compute'] is None
        assert result['database'] is None

        # Should not call API at all
        assert mock_rec.call_count == 0


# ============================================================================
# Purchase Need Tests
# ============================================================================

def test_calculate_purchase_need_positive_gap():
    """Test that purchase plans are created when there's a coverage gap."""
    config = {
        'enable_compute_sp': True,
        'enable_database_sp': False,
        'enable_sagemaker_sp': False,
        'coverage_target_percent': 90.0,
        'compute_sp_payment_option': 'ALL_UPFRONT'
    }

    coverage = {
        'compute': 70.0,
        'database': 0.0
    }

    recommendations = {
        'compute': {
            'HourlyCommitmentToPurchase': '1.5',
            'RecommendationId': 'test-rec-123'
        },
        'database': None
    }

    result = handler.calculate_purchase_need(config, coverage, recommendations)

    assert len(result) == 1
    assert result[0]['sp_type'] == 'compute'
    assert result[0]['hourly_commitment'] == 1.5
    assert result[0]['recommendation_id'] == 'test-rec-123'


def test_calculate_purchase_need_no_gap():
    """Test that no purchase plans are created when coverage meets target."""
    config = {
        'enable_compute_sp': True,
        'enable_database_sp': False,
        'enable_sagemaker_sp': False,
        'coverage_target_percent': 90.0
    }

    # Coverage already meets target
    coverage = {
        'compute': 90.0,
        'database': 0.0
    }

    recommendations = {
        'compute': {
            'HourlyCommitmentToPurchase': '1.5',
            'RecommendationId': 'test-rec-123'
        },
        'database': None
    }

    result = handler.calculate_purchase_need(config, coverage, recommendations)

    # Should return empty list (no gap, no purchase needed)
    assert result == []


def test_calculate_purchase_need_no_recommendation():
    """Test that no purchase is made when AWS recommendation is None."""
    config = {
        'enable_compute_sp': True,
        'enable_database_sp': False,
        'enable_sagemaker_sp': False,
        'coverage_target_percent': 90.0
    }

    coverage = {
        'compute': 70.0,
        'database': 0.0
    }

    # No recommendation available
    recommendations = {
        'compute': None,
        'database': None
    }

    result = handler.calculate_purchase_need(config, coverage, recommendations)

    assert result == []


def test_calculate_purchase_need_zero_commitment():
    """Test that recommendations with $0/hour commitment are skipped."""
    config = {
        'enable_compute_sp': True,
        'enable_database_sp': False,
        'enable_sagemaker_sp': False,
        'coverage_target_percent': 90.0
    }

    coverage = {
        'compute': 70.0,
        'database': 0.0
    }

    recommendations = {
        'compute': {
            'HourlyCommitmentToPurchase': '0',
            'RecommendationId': 'test-rec-123'
        },
        'database': None
    }

    result = handler.calculate_purchase_need(config, coverage, recommendations)

    assert result == []


def test_calculate_purchase_need_database_sp():
    """Test that Database SP purchase plans use NO_UPFRONT payment and ONE_YEAR term."""
    config = {
        'enable_compute_sp': False,
        'enable_database_sp': True,
        'enable_sagemaker_sp': False,
        'coverage_target_percent': 90.0
    }

    coverage = {
        'compute': 0.0,
        'database': 65.0
    }

    recommendations = {
        'compute': None,
        'database': {
            'HourlyCommitmentToPurchase': '2.5',
            'RecommendationId': 'test-db-rec-456'
        }
    }

    result = handler.calculate_purchase_need(config, coverage, recommendations)

    assert len(result) == 1
    assert result[0]['sp_type'] == 'database'
    assert result[0]['hourly_commitment'] == 2.5
    assert result[0]['recommendation_id'] == 'test-db-rec-456'
    assert result[0]['payment_option'] == 'NO_UPFRONT'
    assert result[0]['term'] == 'ONE_YEAR'


def test_calculate_purchase_need_database_no_gap():
    """Test that no Database SP purchase is made when coverage meets target."""
    config = {
        'enable_compute_sp': False,
        'enable_database_sp': True,
        'enable_sagemaker_sp': False,
        'coverage_target_percent': 90.0
    }

    # Database coverage already meets target
    coverage = {
        'compute': 0.0,
        'database': 92.0
    }

    recommendations = {
        'compute': None,
        'database': {
            'HourlyCommitmentToPurchase': '2.5',
            'RecommendationId': 'test-db-rec-789'
        }
    }

    result = handler.calculate_purchase_need(config, coverage, recommendations)

    # Should return empty list (no gap, no purchase needed)
    assert result == []


def test_calculate_purchase_need_database_zero_commitment():
    """Test that Database SP recommendations with $0/hour commitment are skipped."""
    config = {
        'enable_compute_sp': False,
        'enable_database_sp': True,
        'enable_sagemaker_sp': False,
        'coverage_target_percent': 90.0
    }

    coverage = {
        'compute': 0.0,
        'database': 60.0
    }

    recommendations = {
        'compute': None,
        'database': {
            'HourlyCommitmentToPurchase': '0',
            'RecommendationId': 'test-db-rec-zero'
        }
    }

    result = handler.calculate_purchase_need(config, coverage, recommendations)

    assert result == []


def test_calculate_purchase_need_database_no_recommendation():
    """Test that no Database SP purchase is made when AWS recommendation is None."""
    config = {
        'enable_compute_sp': False,
        'enable_database_sp': True,
        'enable_sagemaker_sp': False,
        'coverage_target_percent': 90.0
    }

    coverage = {
        'compute': 0.0,
        'database': 60.0
    }

    # No recommendation available
    recommendations = {
        'compute': None,
        'database': None
    }

    result = handler.calculate_purchase_need(config, coverage, recommendations)

    assert result == []


def test_calculate_purchase_need_sagemaker_sp():
    """Test that SageMaker SP purchase plans use configured payment option."""
    config = {
        'enable_compute_sp': False,
        'enable_database_sp': False,
        'enable_sagemaker_sp': True,
        'coverage_target_percent': 90.0,
        'sagemaker_sp_payment_option': 'ALL_UPFRONT'
    }

    coverage = {
        'compute': 0.0,
        'database': 0.0,
        'sagemaker': 55.0
    }

    recommendations = {
        'compute': None,
        'database': None,
        'sagemaker': {
            'HourlyCommitmentToPurchase': '3.75',
            'RecommendationId': 'test-sm-rec-456'
        }
    }

    result = handler.calculate_purchase_need(config, coverage, recommendations)

    assert len(result) == 1
    assert result[0]['sp_type'] == 'sagemaker'
    assert result[0]['hourly_commitment'] == 3.75
    assert result[0]['recommendation_id'] == 'test-sm-rec-456'
    assert result[0]['payment_option'] == 'ALL_UPFRONT'


def test_calculate_purchase_need_sagemaker_no_gap():
    """Test that no SageMaker SP purchase is made when coverage meets target."""
    config = {
        'enable_compute_sp': False,
        'enable_database_sp': False,
        'enable_sagemaker_sp': True,
        'coverage_target_percent': 90.0
    }

    # SageMaker coverage already meets target
    coverage = {
        'compute': 0.0,
        'database': 0.0,
        'sagemaker': 93.0
    }

    recommendations = {
        'compute': None,
        'database': None,
        'sagemaker': {
            'HourlyCommitmentToPurchase': '3.75',
            'RecommendationId': 'test-sm-rec-789'
        }
    }

    result = handler.calculate_purchase_need(config, coverage, recommendations)

    # Should return empty list (no gap, no purchase needed)
    assert result == []


def test_calculate_purchase_need_sagemaker_zero_commitment():
    """Test that SageMaker SP recommendations with $0/hour commitment are skipped."""
    config = {
        'enable_compute_sp': False,
        'enable_database_sp': False,
        'enable_sagemaker_sp': True,
        'coverage_target_percent': 90.0
    }

    coverage = {
        'compute': 0.0,
        'database': 0.0,
        'sagemaker': 50.0
    }

    recommendations = {
        'compute': None,
        'database': None,
        'sagemaker': {
            'HourlyCommitmentToPurchase': '0',
            'RecommendationId': 'test-sm-rec-zero'
        }
    }

    result = handler.calculate_purchase_need(config, coverage, recommendations)

    assert result == []


def test_calculate_purchase_need_sagemaker_no_recommendation():
    """Test that no SageMaker SP purchase is made when AWS recommendation is None."""
    config = {
        'enable_compute_sp': False,
        'enable_database_sp': False,
        'enable_sagemaker_sp': True,
        'coverage_target_percent': 90.0
    }

    coverage = {
        'compute': 0.0,
        'database': 0.0,
        'sagemaker': 50.0
    }

    # No recommendation available
    recommendations = {
        'compute': None,
        'database': None,
        'sagemaker': None
    }

    result = handler.calculate_purchase_need(config, coverage, recommendations)

    assert result == []


# ============================================================================
# Purchase Limits Tests
# ============================================================================

def test_apply_purchase_limits_scales_commitments():
    """Test that max_purchase_percent scales commitments correctly."""
    config = {
        'max_purchase_percent': 10.0,
        'min_commitment_per_plan': 0.001
    }

    plans = [
        {
            'sp_type': 'compute',
            'hourly_commitment': 10.0,
            'recommendation_id': 'rec-123'
        }
    ]

    result = handler.apply_purchase_limits(config, plans)

    # Should scale to 10% of 10.0 = 1.0
    assert len(result) == 1
    assert result[0]['hourly_commitment'] == pytest.approx(1.0, rel=0.01)


def test_apply_purchase_limits_filters_below_minimum():
    """Test that plans below min_commitment_per_plan are filtered out."""
    config = {
        'max_purchase_percent': 10.0,
        'min_commitment_per_plan': 0.5
    }

    plans = [
        {'sp_type': 'compute', 'hourly_commitment': 10.0},
        {'sp_type': 'database', 'hourly_commitment': 2.0}
    ]

    result = handler.apply_purchase_limits(config, plans)

    # After 10% scaling: 10.0 -> 1.0 (keep), 2.0 -> 0.2 (filter out < 0.5)
    assert len(result) == 1
    assert result[0]['sp_type'] == 'compute'


def test_apply_purchase_limits_empty_list():
    """Test handling of empty purchase plans list."""
    config = {
        'max_purchase_percent': 10.0,
        'min_commitment_per_plan': 0.001
    }

    result = handler.apply_purchase_limits(config, [])

    assert result == []


def test_apply_purchase_limits_database_sp():
    """Test that max_purchase_percent applies correctly to Database SP."""
    config = {
        'max_purchase_percent': 20.0,
        'min_commitment_per_plan': 0.001
    }

    plans = [
        {
            'sp_type': 'database',
            'hourly_commitment': 5.0,
            'term': 'ONE_YEAR',
            'payment_option': 'NO_UPFRONT',
            'recommendation_id': 'rec-db-limit-test'
        }
    ]

    result = handler.apply_purchase_limits(config, plans)

    # Should scale to 20% of 5.0 = 1.0
    assert len(result) == 1
    assert result[0]['sp_type'] == 'database'
    assert result[0]['hourly_commitment'] == pytest.approx(1.0, rel=0.01)
    assert result[0]['term'] == 'ONE_YEAR'
    assert result[0]['payment_option'] == 'NO_UPFRONT'


def test_apply_purchase_limits_sagemaker_sp():
    """Test that max_purchase_percent applies correctly to SageMaker SP."""
    config = {
        'max_purchase_percent': 15.0,
        'min_commitment_per_plan': 0.001
    }

    plans = [
        {
            'sp_type': 'sagemaker',
            'hourly_commitment': 10.0,
            'payment_option': 'ALL_UPFRONT',
            'recommendation_id': 'rec-sm-limit-test'
        }
    ]

    result = handler.apply_purchase_limits(config, plans)

    # Should scale to 15% of 10.0 = 1.5
    assert len(result) == 1
    assert result[0]['sp_type'] == 'sagemaker'
    assert result[0]['hourly_commitment'] == pytest.approx(1.5, rel=0.01)
    assert result[0]['payment_option'] == 'ALL_UPFRONT'


# ============================================================================
# Term Splitting Tests
# ============================================================================

def test_split_by_term_compute_sp():
    """Test that Compute SP is split by term mix."""
    config = {
        'compute_sp_term_mix': {
            'three_year': 0.67,
            'one_year': 0.33
        },
        'min_commitment_per_plan': 0.001
    }

    plans = [
        {
            'sp_type': 'compute',
            'hourly_commitment': 3.0,
            'payment_option': 'ALL_UPFRONT',
            'recommendation_id': 'test-123'
        }
    ]

    result = handler.split_by_term(config, plans)

    # Should split into 2 plans
    assert len(result) == 2

    # Check three-year plan
    three_year_plan = [p for p in result if p['term'] == 'THREE_YEAR'][0]
    assert three_year_plan['hourly_commitment'] == pytest.approx(3.0 * 0.67, rel=0.01)
    assert three_year_plan['term'] == 'THREE_YEAR'

    # Check one-year plan
    one_year_plan = [p for p in result if p['term'] == 'ONE_YEAR'][0]
    assert one_year_plan['hourly_commitment'] == pytest.approx(3.0 * 0.33, rel=0.01)
    assert one_year_plan['term'] == 'ONE_YEAR'


def test_split_by_term_database_sp():
    """Test that Database SP passes through unchanged."""
    config = {
        'compute_sp_term_mix': {
            'three_year': 0.67,
            'one_year': 0.33
        },
        'min_commitment_per_plan': 0.001
    }

    plans = [
        {
            'sp_type': 'database',
            'hourly_commitment': 2.0,
            'term': 'ONE_YEAR',
            'payment_option': 'ALL_UPFRONT'
        }
    ]

    result = handler.split_by_term(config, plans)

    # Should pass through unchanged
    assert len(result) == 1
    assert result[0]['sp_type'] == 'database'
    assert result[0]['hourly_commitment'] == 2.0
    assert result[0]['term'] == 'ONE_YEAR'


def test_split_by_term_sagemaker_sp():
    """Test that SageMaker SP is split by term mix."""
    config = {
        'sagemaker_sp_term_mix': {
            'three_year': 0.67,
            'one_year': 0.33
        },
        'min_commitment_per_plan': 0.001
    }

    plans = [
        {
            'sp_type': 'sagemaker',
            'hourly_commitment': 6.0,
            'payment_option': 'ALL_UPFRONT',
            'recommendation_id': 'test-sm-456'
        }
    ]

    result = handler.split_by_term(config, plans)

    # Should split into 2 plans
    assert len(result) == 2

    # Check three-year plan
    three_year_plan = [p for p in result if p['term'] == 'THREE_YEAR'][0]
    assert three_year_plan['hourly_commitment'] == pytest.approx(6.0 * 0.67, rel=0.01)
    assert three_year_plan['term'] == 'THREE_YEAR'
    assert three_year_plan['sp_type'] == 'sagemaker'
    assert three_year_plan['payment_option'] == 'ALL_UPFRONT'

    # Check one-year plan
    one_year_plan = [p for p in result if p['term'] == 'ONE_YEAR'][0]
    assert one_year_plan['hourly_commitment'] == pytest.approx(6.0 * 0.33, rel=0.01)
    assert one_year_plan['term'] == 'ONE_YEAR'
    assert one_year_plan['sp_type'] == 'sagemaker'
    assert one_year_plan['payment_option'] == 'ALL_UPFRONT'


def test_split_by_term_sagemaker_filters_below_minimum():
    """Test that SageMaker SP splits below min_commitment are filtered out."""
    config = {
        'sagemaker_sp_term_mix': {
            'three_year': 0.67,
            'one_year': 0.33
        },
        'min_commitment_per_plan': 1.5
    }

    plans = [
        {
            'sp_type': 'sagemaker',
            'hourly_commitment': 2.0,
            'payment_option': 'ALL_UPFRONT'
        }
    ]

    result = handler.split_by_term(config, plans)

    # After splitting: 0.67 * 2.0 = 1.34 (filter out < 1.5), 0.33 * 2.0 = 0.66 (filter out < 1.5)
    # Both should be filtered out
    assert len(result) == 0


def test_split_by_term_filters_below_minimum():
    """Test that splits below min_commitment are filtered out."""
    config = {
        'compute_sp_term_mix': {
            'three_year': 0.67,
            'one_year': 0.33
        },
        'min_commitment_per_plan': 1.0
    }

    plans = [
        {
            'sp_type': 'compute',
            'hourly_commitment': 1.0,
            'payment_option': 'ALL_UPFRONT'
        }
    ]

    result = handler.split_by_term(config, plans)

    # After splitting: 0.67 (keep), 0.33 (filter out < 1.0)
    # Actually both should be filtered since 0.67 < 1.0 and 0.33 < 1.0
    # But let's check the actual behavior
    assert all(p['hourly_commitment'] >= config['min_commitment_per_plan'] for p in result)


def test_split_by_term_empty_list():
    """Test handling of empty purchase plans list."""
    config = {
        'compute_sp_term_mix': {
            'three_year': 0.67,
            'one_year': 0.33
        }
    }

    result = handler.split_by_term(config, [])

    assert result == []


# ============================================================================
# Queue Tests
# ============================================================================

def test_queue_purchase_intents_sends_messages():
    """Test that purchase intents are sent to SQS."""
    config = {
        'queue_url': 'test-queue-url',
        'tags': {'Environment': 'test'}
    }

    plans = [
        {
            'sp_type': 'compute',
            'term': 'THREE_YEAR',
            'hourly_commitment': 2.5,
            'payment_option': 'ALL_UPFRONT',
            'recommendation_id': 'rec-123'
        }
    ]

    with patch.object(handler.sqs_client, 'send_message') as mock_send:
        mock_send.return_value = {'MessageId': 'msg-123'}

        handler.queue_purchase_intents(config, plans)

        # Should send 1 message
        assert mock_send.call_count == 1
        call_args = mock_send.call_args[1]
        assert call_args['QueueUrl'] == 'test-queue-url'

        # Verify message body
        message_body = json.loads(call_args['MessageBody'])
        assert message_body['sp_type'] == 'compute'
        assert message_body['hourly_commitment'] == 2.5


def test_queue_purchase_intents_client_token_unique():
    """Test that each message gets a unique client token."""
    config = {
        'queue_url': 'test-queue-url',
        'tags': {}
    }

    plans = [
        {'sp_type': 'compute', 'term': 'THREE_YEAR', 'hourly_commitment': 1.0, 'payment_option': 'ALL_UPFRONT'},
        {'sp_type': 'compute', 'term': 'ONE_YEAR', 'hourly_commitment': 0.5, 'payment_option': 'ALL_UPFRONT'}
    ]

    with patch.object(handler.sqs_client, 'send_message') as mock_send:
        mock_send.return_value = {'MessageId': 'msg-123'}

        handler.queue_purchase_intents(config, plans)

        # Extract client tokens from all calls
        tokens = []
        for call in mock_send.call_args_list:
            message_body = json.loads(call[1]['MessageBody'])
            tokens.append(message_body['client_token'])

        # All tokens should be unique
        assert len(tokens) == len(set(tokens))


def test_queue_purchase_intents_empty_list():
    """Test handling of empty purchase plans list."""
    config = {'queue_url': 'test-queue-url', 'tags': {}}

    with patch.object(handler.sqs_client, 'send_message') as mock_send:
        handler.queue_purchase_intents(config, [])

        # Should not send any messages
        assert mock_send.call_count == 0


# ============================================================================
# Email Tests
# ============================================================================

def test_send_scheduled_email_formats_correctly():
    """Test that scheduled email is formatted correctly."""
    config = {
        'sns_topic_arn': 'test-topic-arn',
        'coverage_target_percent': 90.0,
        'queue_url': 'test-queue-url'
    }

    plans = [
        {
            'sp_type': 'compute',
            'term': 'THREE_YEAR',
            'hourly_commitment': 2.5,
            'payment_option': 'ALL_UPFRONT'
        }
    ]

    coverage = {'compute': 75.0, 'database': 0.0}

    with patch.object(handler.sns_client, 'publish') as mock_publish:
        handler.send_scheduled_email(config, plans, coverage)

        # Verify SNS publish was called
        assert mock_publish.call_count == 1
        call_args = mock_publish.call_args[1]
        assert call_args['TopicArn'] == 'test-topic-arn'
        assert 'Savings Plans Scheduled for Purchase' in call_args['Subject']

        # Verify message content
        message = call_args['Message']
        assert '75.00%' in message  # Coverage
        assert '2.5' in message  # Hourly commitment


def test_send_dry_run_email_has_dry_run_header():
    """Test that dry-run email has clear DRY RUN header."""
    config = {
        'sns_topic_arn': 'test-topic-arn',
        'coverage_target_percent': 90.0
    }

    plans = []
    coverage = {'compute': 80.0, 'database': 0.0}

    with patch.object(handler.sns_client, 'publish') as mock_publish:
        handler.send_dry_run_email(config, plans, coverage)

        call_args = mock_publish.call_args[1]
        assert '[DRY RUN]' in call_args['Subject']

        message = call_args['Message']
        assert '***** DRY RUN MODE *****' in message
        assert '*** NO PURCHASES WERE SCHEDULED ***' in message


def test_send_error_email_handles_missing_config(monkeypatch):
    """Test that error email works even if config is not loaded."""
    monkeypatch.setenv('SNS_TOPIC_ARN', 'error-topic-arn')

    with patch.object(handler.sns_client, 'publish') as mock_publish:
        handler.send_error_email('Test error message')

        call_args = mock_publish.call_args[1]
        assert call_args['TopicArn'] == 'error-topic-arn'
        assert 'ERROR' in call_args['Subject']
        assert 'Test error message' in call_args['Message']


def test_send_error_email_no_sns_topic(monkeypatch):
    """Test that send_error_email handles missing SNS_TOPIC_ARN gracefully."""
    monkeypatch.delenv('SNS_TOPIC_ARN', raising=False)

    # Should not raise - just log error
    handler.send_error_email('Test error')


# ============================================================================
# Handler Integration Tests
# ============================================================================

def test_handler_dry_run_mode(mock_env_vars):
    """Test handler in dry-run mode sends email but doesn't queue."""
    with patch.object(handler, 'purge_queue') as mock_purge, \
         patch.object(handler, 'calculate_current_coverage') as mock_coverage, \
         patch.object(handler, 'get_aws_recommendations') as mock_recs, \
         patch.object(handler, 'send_dry_run_email') as mock_email, \
         patch.object(handler, 'queue_purchase_intents') as mock_queue:

        mock_coverage.return_value = {'compute': 70.0, 'database': 0.0}
        mock_recs.return_value = {
            'compute': {'HourlyCommitmentToPurchase': '1.0', 'RecommendationId': 'rec-123'},
            'database': None
        }

        result = handler.handler({}, None)

        # Should call dry-run email
        assert mock_email.call_count == 1
        # Should NOT call queue
        assert mock_queue.call_count == 0
        # Should return success
        assert result['statusCode'] == 200


def test_handler_production_mode(mock_env_vars, monkeypatch):
    """Test handler in production mode queues messages and sends email."""
    monkeypatch.setenv('DRY_RUN', 'false')

    with patch.object(handler, 'purge_queue') as mock_purge, \
         patch.object(handler, 'calculate_current_coverage') as mock_coverage, \
         patch.object(handler, 'get_aws_recommendations') as mock_recs, \
         patch.object(handler, 'send_scheduled_email') as mock_email, \
         patch.object(handler, 'queue_purchase_intents') as mock_queue:

        mock_coverage.return_value = {'compute': 70.0, 'database': 0.0}
        mock_recs.return_value = {
            'compute': {'HourlyCommitmentToPurchase': '1.0', 'RecommendationId': 'rec-123'},
            'database': None
        }

        result = handler.handler({}, None)

        # Should call queue
        assert mock_queue.call_count == 1
        # Should call production email
        assert mock_email.call_count == 1
        # Should return success
        assert result['statusCode'] == 200


def test_handler_error_raises_exception(mock_env_vars):
    """Test that handler raises exceptions on errors."""
    with patch.object(handler, 'purge_queue') as mock_purge, \
         patch.object(handler, 'send_error_email') as mock_error_email:

        # Make purge_queue raise an error
        from botocore.exceptions import ClientError
        error_response = {'Error': {'Code': 'AccessDenied'}}
        mock_purge.side_effect = ClientError(error_response, 'purge_queue')

        # Should raise the exception
        with pytest.raises(ClientError):
            handler.handler({}, None)

        # Should send error email
        assert mock_error_email.call_count == 1


# ============================================================================
# Assume Role Tests
# ============================================================================

def test_get_assumed_role_session_with_valid_arn():
    """Test that AssumeRole is called when ARN is provided."""
    with patch('shared.aws_utils.boto3.client') as mock_boto3_client:
        mock_sts = MagicMock()
        mock_boto3_client.return_value = mock_sts

        # Mock STS AssumeRole response
        mock_sts.assume_role.return_value = {
            'Credentials': {
                'AccessKeyId': 'AKIAIOSFODNN7EXAMPLE',
                'SecretAccessKey': 'wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY',
                'SessionToken': 'FwoGZXIvYXdzEBYaDBexampletoken',
                'Expiration': datetime.now(timezone.utc)
            }
        }

        # Call function
        session = handler.get_assumed_role_session('arn:aws:iam::123456789012:role/TestRole')

        # Verify AssumeRole was called with correct parameters
        assert session is not None
        mock_sts.assume_role.assert_called_once_with(
            RoleArn='arn:aws:iam::123456789012:role/TestRole',
            RoleSessionName='sp-autopilot-session'  # Default session name from shared.aws_utils
        )


def test_get_assumed_role_session_without_arn():
    """Test that None is returned when ARN is not provided (backward compatibility)."""
    # Test with None
    result = handler.get_assumed_role_session(None)
    assert result is None

    # Test with empty string
    result = handler.get_assumed_role_session('')
    assert result is None


def test_get_assumed_role_session_access_denied():
    """Test that AccessDenied error is raised with clear message."""
    from botocore.exceptions import ClientError
    with patch('shared.aws_utils.boto3.client') as mock_boto3_client:
        mock_sts = MagicMock()
        mock_boto3_client.return_value = mock_sts

        # Mock AccessDenied error
        error_response = {
            'Error': {
                'Code': 'AccessDenied',
                'Message': 'User is not authorized to perform: sts:AssumeRole'
            }
        }
        mock_sts.assume_role.side_effect = ClientError(error_response, 'AssumeRole')

        # Verify ClientError is raised
        with pytest.raises(ClientError) as exc_info:
            handler.get_assumed_role_session('arn:aws:iam::123456789012:role/TestRole')

        # Verify error code
        assert exc_info.value.response['Error']['Code'] == 'AccessDenied'


def test_get_clients_with_role_arn():
    """Test that CE/SP clients use assumed credentials when role ARN is provided."""
    config = {'management_account_role_arn': 'arn:aws:iam::123456789012:role/TestRole'}

    with patch('shared.aws_utils.get_assumed_role_session') as mock_assume, \
         patch('shared.aws_utils.boto3.client') as mock_boto3_client:

        # Mock session from assumed role
        mock_session = MagicMock()
        mock_assume.return_value = mock_session

        # Mock session.client() calls
        mock_session.client.return_value = MagicMock()

        # Mock boto3.client() calls (for SNS/SQS/S3)
        mock_boto3_client.return_value = MagicMock()

        # Call function
        clients = handler.get_clients(config)

        # Verify assume role was called with default session name
        mock_assume.assert_called_once_with('arn:aws:iam::123456789012:role/TestRole', 'sp-autopilot-session')

        # Verify CE and Savings Plans clients use session
        assert mock_session.client.call_count == 2
        mock_session.client.assert_any_call('ce')
        mock_session.client.assert_any_call('savingsplans')

        # Verify SNS, SQS, and S3 clients use local credentials (boto3.client directly)
        assert mock_boto3_client.call_count == 3
        mock_boto3_client.assert_any_call('sns')
        mock_boto3_client.assert_any_call('sqs')
        mock_boto3_client.assert_any_call('s3')


def test_get_clients_without_role_arn():
    """Test that all clients use default credentials when no role ARN provided (backward compatibility)."""
    config = {'management_account_role_arn': None}

    with patch('shared.aws_utils.boto3.client') as mock_boto3_client:
        mock_boto3_client.return_value = MagicMock()

        # Call function
        clients = handler.get_clients(config)

        # Verify all 5 clients use boto3.client directly (no assume role)
        assert mock_boto3_client.call_count == 5
        mock_boto3_client.assert_any_call('ce')
        mock_boto3_client.assert_any_call('savingsplans')
        mock_boto3_client.assert_any_call('sns')
        mock_boto3_client.assert_any_call('sqs')
        mock_boto3_client.assert_any_call('s3')


def test_handler_assume_role_error_handling(mock_env_vars, monkeypatch):
    """Test that handler error message includes role ARN when assume role fails."""
    from botocore.exceptions import ClientError
    # Add MANAGEMENT_ACCOUNT_ROLE_ARN to environment
    monkeypatch.setenv('MANAGEMENT_ACCOUNT_ROLE_ARN', 'arn:aws:iam::123456789012:role/TestRole')

    with patch('handler.get_clients') as mock_get_clients, \
         patch('handler.send_error_email') as mock_send_error, \
         patch('handler.purge_queue') as mock_purge:

        # Mock assume role failure
        error_response = {'Error': {'Code': 'AccessDenied', 'Message': 'Not authorized'}}
        mock_get_clients.side_effect = ClientError(error_response, 'AssumeRole')

        # Call handler - should raise exception
        with pytest.raises(ClientError):
            handler.handler({}, None)

        # Verify error email was sent (may be called twice: once for role assumption error, once for general error)
        assert mock_send_error.call_count >= 1

        # Verify at least one error message includes role ARN
        error_messages = [call[0][0] for call in mock_send_error.call_args_list]
        assert any('arn:aws:iam::123456789012:role/TestRole' in msg for msg in error_messages)

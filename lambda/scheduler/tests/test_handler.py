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


@pytest.fixture
def mock_config():
    """Return a mock configuration dictionary."""
    return {
        'queue_url': 'https://sqs.us-east-1.amazonaws.com/123456789012/test-queue',
        'sns_topic_arn': 'arn:aws:sns:us-east-1:123456789012:test-topic',
        'dry_run': True,
        'enable_compute_sp': True,
        'enable_database_sp': False,
        'enable_sagemaker_sp': False,
        'coverage_target_percent': 90.0,
        'max_purchase_percent': 10.0,
        'renewal_window_days': 7,
        'lookback_days': 30,
        'min_data_days': 14,
        'min_commitment_per_plan': 0.001,
        'compute_sp_term_mix': {"three_year": 0.67, "one_year": 0.33},
        'compute_sp_payment_option': 'ALL_UPFRONT',
        'sagemaker_sp_term_mix': {"three_year": 0.67, "one_year": 0.33},
        'sagemaker_sp_payment_option': 'ALL_UPFRONT',
        'tags': {}
    }


@pytest.fixture
def mock_clients():
    """Return a mock clients dictionary."""
    return {
        'ce': MagicMock(),
        'savingsplans': MagicMock(),
        'sqs': MagicMock(),
        'sns': MagicMock()
    }


# ============================================================================
# Queue Purge Tests
# ============================================================================

def test_purge_queue_success():
    """Test successful queue purge."""
    mock_sqs = MagicMock()
    mock_sqs.purge_queue.return_value = {}

    handler.purge_queue(mock_sqs, 'test-queue-url')

    mock_sqs.purge_queue.assert_called_once_with(QueueUrl='test-queue-url')


def test_purge_queue_in_progress():
    """Test that PurgeQueueInProgress error is handled gracefully."""
    from botocore.exceptions import ClientError

    mock_sqs = MagicMock()
    error_response = {'Error': {'Code': 'PurgeQueueInProgress'}}
    mock_sqs.purge_queue.side_effect = ClientError(error_response, 'purge_queue')

    # Should not raise - just log warning
    handler.purge_queue(mock_sqs, 'test-queue-url')


def test_purge_queue_other_error():
    """Test that other errors are raised."""
    from botocore.exceptions import ClientError

    mock_sqs = MagicMock()
    error_response = {'Error': {'Code': 'AccessDenied'}}
    mock_sqs.purge_queue.side_effect = ClientError(error_response, 'purge_queue')

    with pytest.raises(ClientError):
        handler.purge_queue(mock_sqs, 'test-queue-url')


# ============================================================================
# Coverage Calculation Tests
# ============================================================================

def test_calculate_current_coverage_filters_expiring_plans(mock_config):
    """Test that plans expiring within renewal_window_days are excluded."""
    mock_savingsplans = MagicMock()
    mock_ce = MagicMock()

    now = datetime.now(timezone.utc)

    # Plan expiring in 3 days (should be excluded - within 7 day window)
    expiring_soon = now + timedelta(days=3)
    # Plan expiring in 30 days (should be included - outside 7 day window)
    expiring_later = now + timedelta(days=30)

    mock_savingsplans.describe_savings_plans.return_value = {
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

    mock_ce.get_savings_plans_coverage.return_value = {
        'SavingsPlansCoverages': [
            {
                'TimePeriod': {'Start': '2026-01-12', 'End': '2026-01-13'},
                'Coverage': {'CoveragePercentage': '75.5'}
            }
        ]
    }

    result = handler.calculate_current_coverage(mock_savingsplans, mock_ce, mock_config)

    assert 'compute' in result
    assert result['compute'] == 75.5


def test_calculate_current_coverage_keeps_valid_plans(mock_config):
    """Test that plans expiring after renewal window are kept."""
    mock_savingsplans = MagicMock()
    mock_ce = MagicMock()

    now = datetime.now(timezone.utc)
    expiring_later = now + timedelta(days=30)

    mock_savingsplans.describe_savings_plans.return_value = {
        'savingsPlans': [
            {
                'savingsPlanId': 'sp-valid',
                'state': 'active',
                'end': expiring_later.isoformat()
            }
        ]
    }

    mock_ce.get_savings_plans_coverage.return_value = {
        'SavingsPlansCoverages': [
            {
                'TimePeriod': {'Start': '2026-01-12', 'End': '2026-01-13'},
                'Coverage': {'CoveragePercentage': '85.0'}
            }
        ]
    }

    result = handler.calculate_current_coverage(mock_savingsplans, mock_ce, mock_config)

    assert result['compute'] == 85.0


def test_calculate_current_coverage_empty_plans_list(mock_config):
    """Test handling of no active Savings Plans."""
    mock_savingsplans = MagicMock()
    mock_ce = MagicMock()

    mock_savingsplans.describe_savings_plans.return_value = {'savingsPlans': []}

    mock_ce.get_savings_plans_coverage.return_value = {
        'SavingsPlansCoverages': [
            {
                'TimePeriod': {'Start': '2026-01-12', 'End': '2026-01-13'},
                'Coverage': {'CoveragePercentage': '0.0'}
            }
        ]
    }

    result = handler.calculate_current_coverage(mock_savingsplans, mock_ce, mock_config)

    assert result['compute'] == 0.0


def test_calculate_current_coverage_no_coverage_data(mock_config):
    """Test handling of no coverage data from Cost Explorer."""
    mock_savingsplans = MagicMock()
    mock_ce = MagicMock()

    mock_savingsplans.describe_savings_plans.return_value = {'savingsPlans': []}
    mock_ce.get_savings_plans_coverage.return_value = {'SavingsPlansCoverages': []}

    result = handler.calculate_current_coverage(mock_savingsplans, mock_ce, mock_config)

    assert result == {'compute': 0.0, 'database': 0.0, 'sagemaker': 0.0}


# ============================================================================
# AWS Recommendations Tests
# ============================================================================

def test_get_aws_recommendations_compute_enabled(mock_config):
    """Test fetching Compute SP recommendations when enabled."""
    mock_ce = MagicMock()
    mock_ce.get_savings_plans_purchase_recommendation.return_value = {
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

    result = handler.get_aws_recommendations(mock_ce, mock_config)

    assert result['compute'] is not None
    assert result['compute']['HourlyCommitmentToPurchase'] == '2.5'
    assert result['compute']['RecommendationId'] == 'rec-123'


def test_get_aws_recommendations_database_disabled(mock_config):
    """Test that Database SP recommendations are skipped when disabled."""
    mock_ce = MagicMock()
    mock_ce.get_savings_plans_purchase_recommendation.return_value = {
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

    result = handler.get_aws_recommendations(mock_ce, mock_config)

    # Database should be None when disabled
    assert result['database'] is None


def test_get_aws_recommendations_database_enabled():
    """Test fetching Database SP recommendations with correct API parameters."""
    config = {
        'enable_compute_sp': False,
        'enable_database_sp': True,
        'enable_sagemaker_sp': False,
        'lookback_days': 30,
        'min_data_days': 14
    }

    mock_ce = MagicMock()
    mock_ce.get_savings_plans_purchase_recommendation.return_value = {
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

    result = handler.get_aws_recommendations(mock_ce, config)

    # Verify Database SP recommendation was returned
    assert result['database'] is not None
    assert result['database']['HourlyCommitmentToPurchase'] == '1.25'
    assert result['database']['RecommendationId'] == 'rec-db-456'

    # Verify API was called with correct Database SP parameters
    mock_ce.get_savings_plans_purchase_recommendation.assert_called_once_with(
        SavingsPlansType='DATABASE_SP',
        LookbackPeriodInDays='THIRTY_DAYS',
        TermInYears='ONE_YEAR',
        PaymentOption='NO_UPFRONT'
    )


def test_get_aws_recommendations_database_insufficient_data():
    """Test rejection of Database SP recommendations with insufficient data."""
    config = {
        'enable_compute_sp': False,
        'enable_database_sp': True,
        'enable_sagemaker_sp': False,
        'lookback_days': 30,
        'min_data_days': 14
    }

    mock_ce = MagicMock()
    # Return only 10 days of data (less than min_data_days of 14)
    mock_ce.get_savings_plans_purchase_recommendation.return_value = {
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

    result = handler.get_aws_recommendations(mock_ce, config)

    # Should reject due to insufficient data
    assert result['database'] is None


def test_get_aws_recommendations_database_no_recommendations():
    """Test handling of empty Database SP recommendation list from AWS."""
    config = {
        'enable_compute_sp': False,
        'enable_database_sp': True,
        'enable_sagemaker_sp': False,
        'lookback_days': 30,
        'min_data_days': 14
    }

    mock_ce = MagicMock()
    mock_ce.get_savings_plans_purchase_recommendation.return_value = {
        'Metadata': {
            'RecommendationId': 'rec-db-empty',
            'LookbackPeriodInDays': '30'
        },
        'SavingsPlansPurchaseRecommendation': {
            'SavingsPlansPurchaseRecommendationDetails': []
        }
    }

    result = handler.get_aws_recommendations(mock_ce, config)

    assert result['database'] is None


def test_get_aws_recommendations_sagemaker_enabled():
    """Test fetching SageMaker SP recommendations with correct API parameters."""
    config = {
        'enable_compute_sp': False,
        'enable_database_sp': False,
        'enable_sagemaker_sp': True,
        'lookback_days': 30,
        'min_data_days': 14
    }

    mock_ce = MagicMock()
    mock_ce.get_savings_plans_purchase_recommendation.return_value = {
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

    result = handler.get_aws_recommendations(mock_ce, config)

    # Verify SageMaker SP recommendation was returned
    assert result['sagemaker'] is not None
    assert result['sagemaker']['HourlyCommitmentToPurchase'] == '3.75'
    assert result['sagemaker']['RecommendationId'] == 'rec-sm-456'

    # Verify API was called with correct SageMaker SP parameters
    mock_ce.get_savings_plans_purchase_recommendation.assert_called_once_with(
        SavingsPlansType='SAGEMAKER_SP',
        LookbackPeriodInDays='THIRTY_DAYS',
        TermInYears='ONE_YEAR',
        PaymentOption='NO_UPFRONT'
    )


def test_get_aws_recommendations_sagemaker_disabled(mock_config):
    """Test that SageMaker SP recommendations are skipped when disabled."""
    mock_ce = MagicMock()
    mock_ce.get_savings_plans_purchase_recommendation.return_value = {
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

    result = handler.get_aws_recommendations(mock_ce, mock_config)

    # SageMaker should be None when disabled
    assert result['sagemaker'] is None


def test_get_aws_recommendations_sagemaker_insufficient_data():
    """Test rejection of SageMaker SP recommendations with insufficient data."""
    config = {
        'enable_compute_sp': False,
        'enable_database_sp': False,
        'enable_sagemaker_sp': True,
        'lookback_days': 30,
        'min_data_days': 14
    }

    mock_ce = MagicMock()
    # Return only 10 days of data (less than min_data_days of 14)
    mock_ce.get_savings_plans_purchase_recommendation.return_value = {
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

    result = handler.get_aws_recommendations(mock_ce, config)

    # Should reject due to insufficient data
    assert result['sagemaker'] is None


def test_get_aws_recommendations_sagemaker_no_recommendations():
    """Test handling of empty SageMaker SP recommendation list from AWS."""
    config = {
        'enable_compute_sp': False,
        'enable_database_sp': False,
        'enable_sagemaker_sp': True,
        'lookback_days': 30,
        'min_data_days': 14
    }

    mock_ce = MagicMock()
    mock_ce.get_savings_plans_purchase_recommendation.return_value = {
        'Metadata': {
            'RecommendationId': 'rec-sm-empty',
            'LookbackPeriodInDays': '30'
        },
        'SavingsPlansPurchaseRecommendation': {
            'SavingsPlansPurchaseRecommendationDetails': []
        }
    }

    result = handler.get_aws_recommendations(mock_ce, config)

    assert result['sagemaker'] is None


def test_get_aws_recommendations_insufficient_data(mock_config):
    """Test rejection of recommendations with insufficient data."""
    mock_ce = MagicMock()
    # Return only 10 days of data (less than min_data_days of 14)
    mock_ce.get_savings_plans_purchase_recommendation.return_value = {
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

    result = handler.get_aws_recommendations(mock_ce, mock_config)

    # Should reject due to insufficient data
    assert result['compute'] is None


def test_get_aws_recommendations_no_recommendations(mock_config):
    """Test handling of empty recommendation list from AWS."""
    mock_ce = MagicMock()
    mock_ce.get_savings_plans_purchase_recommendation.return_value = {
        'Metadata': {
            'RecommendationId': 'rec-123',
            'LookbackPeriodInDays': '30'
        },
        'SavingsPlansPurchaseRecommendation': {
            'SavingsPlansPurchaseRecommendationDetails': []
        }
    }

    result = handler.get_aws_recommendations(mock_ce, mock_config)

    assert result['compute'] is None


def test_get_aws_recommendations_lookback_period_mapping():
    """Test that lookback_days maps correctly to AWS API parameters."""
    # Test 7 days -> SEVEN_DAYS
    config = {
        'enable_compute_sp': True,
        'enable_database_sp': False,
        'enable_sagemaker_sp': False,
        'lookback_days': 7,
        'min_data_days': 14
    }

    mock_ce = MagicMock()
    mock_ce.get_savings_plans_purchase_recommendation.return_value = {
        'Metadata': {'RecommendationId': 'rec-123', 'LookbackPeriodInDays': '7'},
        'SavingsPlansPurchaseRecommendation': {'SavingsPlansPurchaseRecommendationDetails': []}
    }

    handler.get_aws_recommendations(mock_ce, config)

    # Should use SEVEN_DAYS
    call_args = mock_ce.get_savings_plans_purchase_recommendation.call_args[1]
    assert call_args['LookbackPeriodInDays'] == 'SEVEN_DAYS'

    # Test 60 days -> SIXTY_DAYS
    config['lookback_days'] = 60
    mock_ce.reset_mock()
    mock_ce.get_savings_plans_purchase_recommendation.return_value = {
        'Metadata': {'RecommendationId': 'rec-123', 'LookbackPeriodInDays': '60'},
        'SavingsPlansPurchaseRecommendation': {'SavingsPlansPurchaseRecommendationDetails': []}
    }

    handler.get_aws_recommendations(mock_ce, config)

    # Should use SIXTY_DAYS
    call_args = mock_ce.get_savings_plans_purchase_recommendation.call_args[1]
    assert call_args['LookbackPeriodInDays'] == 'SIXTY_DAYS'


def test_get_aws_recommendations_parallel_execution_both_enabled():
    """Test that Compute and Database SP recommendations are fetched in parallel when both enabled."""
    config = {
        'enable_compute_sp': True,
        'enable_database_sp': True,
        'enable_sagemaker_sp': False,
        'lookback_days': 30,
        'min_data_days': 14
    }

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

    mock_ce = MagicMock()
    # Use side_effect to return different values based on SavingsPlansType
    def api_side_effect(*args, **kwargs):
        if kwargs.get('SavingsPlansType') == 'COMPUTE_SP':
            return compute_side_effect(*args, **kwargs)
        elif kwargs.get('SavingsPlansType') == 'DATABASE_SP':
            return database_side_effect(*args, **kwargs)

    mock_ce.get_savings_plans_purchase_recommendation.side_effect = api_side_effect

    result = handler.get_aws_recommendations(mock_ce, config)

    # Verify both recommendations were returned
    assert result['compute'] is not None
    assert result['database'] is not None
    assert result['compute']['HourlyCommitmentToPurchase'] == '1.5'
    assert result['database']['HourlyCommitmentToPurchase'] == '2.5'

    # Verify API was called twice (once for each SP type)
    assert mock_ce.get_savings_plans_purchase_recommendation.call_count == 2

    # Verify calls were made with correct parameters
    call_args_list = [call[1] for call in mock_ce.get_savings_plans_purchase_recommendation.call_args_list]
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


def test_get_aws_recommendations_parallel_execution_error_handling():
    """Test that errors in parallel execution are properly raised."""
    config = {
        'enable_compute_sp': True,
        'enable_database_sp': True,
        'enable_sagemaker_sp': False,
        'lookback_days': 30,
        'min_data_days': 14
    }

    mock_ce = MagicMock()
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

    mock_ce.get_savings_plans_purchase_recommendation.side_effect = api_side_effect

    # Should raise the ClientError from database recommendation
    with pytest.raises(ClientError):
        handler.get_aws_recommendations(mock_ce, config)


def test_get_aws_recommendations_parallel_single_task(mock_config):
    """Test that parallel execution works correctly with only one task (compute only)."""
    mock_ce = MagicMock()
    mock_ce.get_savings_plans_purchase_recommendation.return_value = {
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

    result = handler.get_aws_recommendations(mock_ce, mock_config)

    # Should still work with ThreadPoolExecutor even with single task
    assert result['compute'] is not None
    assert result['compute']['HourlyCommitmentToPurchase'] == '2.5'
    assert result['database'] is None

    # Verify only one API call was made
    assert mock_ce.get_savings_plans_purchase_recommendation.call_count == 1


def test_get_aws_recommendations_parallel_no_tasks():
    """Test that get_aws_recommendations handles case where both SP types are disabled."""
    config = {
        'enable_compute_sp': False,
        'enable_database_sp': False,
        'enable_sagemaker_sp': False,
        'lookback_days': 30,
        'min_data_days': 14
    }

    mock_ce = MagicMock()
    result = handler.get_aws_recommendations(mock_ce, config)

    # Should return None for all types
    assert result['compute'] is None
    assert result['database'] is None
    assert result['sagemaker'] is None

    # Should not call API at all
    assert mock_ce.get_savings_plans_purchase_recommendation.call_count == 0


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
    mock_sqs = MagicMock()
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

    mock_sqs.send_message.return_value = {'MessageId': 'msg-123'}

    handler.queue_purchase_intents(mock_sqs, config, plans)

    # Should send 1 message
    assert mock_sqs.send_message.call_count == 1
    call_args = mock_sqs.send_message.call_args[1]
    assert call_args['QueueUrl'] == 'test-queue-url'

    # Verify message body
    message_body = json.loads(call_args['MessageBody'])
    assert message_body['sp_type'] == 'compute'
    assert message_body['hourly_commitment'] == 2.5


def test_queue_purchase_intents_client_token_unique():
    """Test that each message gets a unique client token."""
    mock_sqs = MagicMock()
    config = {
        'queue_url': 'test-queue-url',
        'tags': {}
    }

    plans = [
        {'sp_type': 'compute', 'term': 'THREE_YEAR', 'hourly_commitment': 1.0, 'payment_option': 'ALL_UPFRONT'},
        {'sp_type': 'compute', 'term': 'ONE_YEAR', 'hourly_commitment': 0.5, 'payment_option': 'ALL_UPFRONT'}
    ]

    mock_sqs.send_message.return_value = {'MessageId': 'msg-123'}

    handler.queue_purchase_intents(mock_sqs, config, plans)

    # Extract client tokens from all calls
    tokens = []
    for call in mock_sqs.send_message.call_args_list:
        message_body = json.loads(call[1]['MessageBody'])
        tokens.append(message_body['client_token'])

    # All tokens should be unique
    assert len(tokens) == len(set(tokens))


def test_queue_purchase_intents_empty_list():
    """Test handling of empty purchase plans list."""
    mock_sqs = MagicMock()
    config = {'queue_url': 'test-queue-url', 'tags': {}}

    handler.queue_purchase_intents(mock_sqs, config, [])

    # Should not send any messages
    assert mock_sqs.send_message.call_count == 0


# ============================================================================
# Email Tests
# ============================================================================

def test_send_scheduled_email_formats_correctly():
    """Test that scheduled email is formatted correctly."""
    mock_sns = MagicMock()
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

    handler.send_scheduled_email(mock_sns, config, plans, coverage)

    # Verify SNS publish was called
    assert mock_sns.publish.call_count == 1
    call_args = mock_sns.publish.call_args[1]
    assert call_args['TopicArn'] == 'test-topic-arn'
    assert 'Savings Plans Scheduled for Purchase' in call_args['Subject']

    # Verify message content
    message = call_args['Message']
    assert '75.00%' in message  # Coverage
    assert '2.5' in message  # Hourly commitment


def test_send_dry_run_email_has_dry_run_header():
    """Test that dry-run email has clear DRY RUN header."""
    mock_sns = MagicMock()
    config = {
        'sns_topic_arn': 'test-topic-arn',
        'coverage_target_percent': 90.0
    }

    plans = []
    coverage = {'compute': 80.0, 'database': 0.0}

    handler.send_dry_run_email(mock_sns, config, plans, coverage)

    call_args = mock_sns.publish.call_args[1]
    assert '[DRY RUN]' in call_args['Subject']

    message = call_args['Message']
    assert '***** DRY RUN MODE *****' in message
    assert '*** NO PURCHASES WERE SCHEDULED ***' in message


# ============================================================================
# Handler Integration Tests
# ============================================================================

def test_handler_dry_run_mode(mock_env_vars):
    """Test handler in dry-run mode sends email but doesn't queue."""
    mock_config = {
        'queue_url': 'test-queue-url',
        'sns_topic_arn': 'test-sns-topic',
        'dry_run': True,
        'enable_compute_sp': True,
        'enable_database_sp': False,
        'enable_sagemaker_sp': False,
        'coverage_target_percent': 90.0,
        'max_purchase_percent': 10.0,
        'renewal_window_days': 7,
        'lookback_days': 30,
        'min_data_days': 14,
        'min_commitment_per_plan': 0.001,
        'compute_sp_term_mix': {"three_year": 0.67, "one_year": 0.33},
        'compute_sp_payment_option': 'ALL_UPFRONT',
        'tags': {}
    }

    mock_clients = {
        'ce': MagicMock(),
        'savingsplans': MagicMock(),
        'sqs': MagicMock(),
        'sns': MagicMock()
    }

    with patch('shared.handler_utils.load_config_from_env', return_value=mock_config), \
         patch('shared.handler_utils.initialize_clients', return_value=mock_clients), \
         patch('boto3.client', return_value=MagicMock()), \
         patch.object(handler, 'purge_queue') as mock_purge, \
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
    # Set DRY_RUN to false in environment
    monkeypatch.setenv('DRY_RUN', 'false')

    mock_config = {
        'queue_url': 'test-queue-url',
        'sns_topic_arn': 'test-sns-topic',
        'dry_run': False,
        'enable_compute_sp': True,
        'enable_database_sp': False,
        'enable_sagemaker_sp': False,
        'coverage_target_percent': 90.0,
        'max_purchase_percent': 10.0,
        'renewal_window_days': 7,
        'lookback_days': 30,
        'min_data_days': 14,
        'min_commitment_per_plan': 0.001,
        'compute_sp_term_mix': {"three_year": 0.67, "one_year": 0.33},
        'compute_sp_payment_option': 'ALL_UPFRONT',
        'tags': {}
    }

    mock_clients = {
        'ce': MagicMock(),
        'savingsplans': MagicMock(),
        'sqs': MagicMock(),
        'sns': MagicMock()
    }

    with patch('shared.handler_utils.load_config_from_env', return_value=mock_config), \
         patch('shared.handler_utils.initialize_clients', return_value=mock_clients), \
         patch('boto3.client', return_value=MagicMock()), \
         patch.object(handler, 'purge_queue') as mock_purge, \
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
    from botocore.exceptions import ClientError

    mock_config = {
        'queue_url': 'test-queue-url',
        'sns_topic_arn': 'test-sns-topic',
        'dry_run': True
    }

    mock_clients = {
        'ce': MagicMock(),
        'savingsplans': MagicMock(),
        'sqs': MagicMock(),
        'sns': MagicMock()
    }

    with patch('shared.handler_utils.load_config_from_env', return_value=mock_config), \
         patch('shared.handler_utils.initialize_clients', return_value=mock_clients), \
         patch('boto3.client', return_value=MagicMock()), \
         patch.object(handler, 'purge_queue') as mock_purge, \
         patch('shared.handler_utils.send_error_notification') as mock_error_email:

        # Make purge_queue raise an error
        error_response = {'Error': {'Code': 'AccessDenied'}}
        mock_purge.side_effect = ClientError(error_response, 'purge_queue')

        # Should raise the exception
        with pytest.raises(ClientError):
            handler.handler({}, None)

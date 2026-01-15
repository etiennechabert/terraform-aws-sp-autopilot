"""
Unit tests for email notifications module.

Tests email formatting and sending for both scheduled purchases
and dry run analysis notifications.
"""

import pytest
from unittest.mock import Mock
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import email_notifications


@pytest.fixture
def mock_sns_client():
    """Create a mock SNS client."""
    return Mock()


@pytest.fixture
def mock_config():
    """Create a mock configuration dictionary."""
    return {
        'sns_topic_arn': 'arn:aws:sns:us-east-1:123456789012:test-topic',
        'coverage_target_percent': 90.0,
        'queue_url': 'https://sqs.us-east-1.amazonaws.com/123456789012/test-queue'
    }


@pytest.fixture
def sample_coverage():
    """Create sample coverage data."""
    return {
        'compute': 75.5,
        'database': 85.0,
        'sagemaker': 60.0
    }


@pytest.fixture
def sample_purchase_plans():
    """Create sample purchase plans."""
    return [
        {
            'sp_type': 'compute',
            'hourly_commitment': 5.50,
            'term': 'THREE_YEAR',
            'payment_option': 'ALL_UPFRONT'
        },
        {
            'sp_type': 'database',
            'hourly_commitment': 2.75,
            'term': 'ONE_YEAR',
            'payment_option': 'NO_UPFRONT'
        }
    ]


# ============================================================================
# Scheduled Email Tests
# ============================================================================

def test_send_scheduled_email_success(mock_sns_client, mock_config, sample_coverage, sample_purchase_plans):
    """Test successful scheduled purchase email sending."""
    mock_sns_client.publish.return_value = {'MessageId': 'msg-12345'}

    email_notifications.send_scheduled_email(
        mock_sns_client, mock_config, sample_purchase_plans, sample_coverage
    )

    # Verify publish was called
    mock_sns_client.publish.assert_called_once()

    # Verify call arguments
    call_args = mock_sns_client.publish.call_args
    assert call_args[1]['TopicArn'] == mock_config['sns_topic_arn']
    assert call_args[1]['Subject'] == 'Savings Plans Scheduled for Purchase'
    assert 'Message' in call_args[1]


def test_send_scheduled_email_message_content(mock_sns_client, mock_config, sample_coverage, sample_purchase_plans):
    """Test that scheduled email contains expected content."""
    mock_sns_client.publish.return_value = {'MessageId': 'msg-12345'}

    email_notifications.send_scheduled_email(
        mock_sns_client, mock_config, sample_purchase_plans, sample_coverage
    )

    call_args = mock_sns_client.publish.call_args
    message = call_args[1]['Message']

    # Verify key content is present
    assert 'Savings Plans Scheduled for Purchase' in message
    assert 'Total Plans Queued: 2' in message
    assert 'Compute SP:  75.50%' in message
    assert 'Database SP: 85.00%' in message
    assert 'SageMaker SP: 60.00%' in message
    assert 'Target Coverage: 90.00%' in message
    assert 'COMPUTE Savings Plan' in message
    assert 'DATABASE Savings Plan' in message
    assert 'CANCELLATION INSTRUCTIONS' in message


def test_send_scheduled_email_calculates_annual_cost(mock_sns_client, mock_config, sample_coverage):
    """Test that email calculates and displays annual costs."""
    mock_sns_client.publish.return_value = {'MessageId': 'msg-12345'}

    purchase_plans = [
        {
            'sp_type': 'compute',
            'hourly_commitment': 1.0,  # $1/hour * 8760 hours = $8,760/year
            'term': 'THREE_YEAR',
            'payment_option': 'ALL_UPFRONT'
        }
    ]

    email_notifications.send_scheduled_email(
        mock_sns_client, mock_config, purchase_plans, sample_coverage
    )

    call_args = mock_sns_client.publish.call_args
    message = call_args[1]['Message']

    # Verify annual cost calculation (1.0 * 8760 = 8760)
    assert 'Estimated Annual Cost: $8,760.00' in message
    assert 'Total Estimated Annual Cost: $8,760.00' in message


def test_send_scheduled_email_empty_plans(mock_sns_client, mock_config, sample_coverage):
    """Test scheduled email with no purchase plans."""
    mock_sns_client.publish.return_value = {'MessageId': 'msg-12345'}

    purchase_plans = []

    email_notifications.send_scheduled_email(
        mock_sns_client, mock_config, purchase_plans, sample_coverage
    )

    call_args = mock_sns_client.publish.call_args
    message = call_args[1]['Message']

    assert 'Total Plans Queued: 0' in message
    assert 'Total Estimated Annual Cost: $0.00' in message


def test_send_scheduled_email_includes_queue_url(mock_sns_client, mock_config, sample_coverage, sample_purchase_plans):
    """Test that email includes queue URL for cancellation."""
    mock_sns_client.publish.return_value = {'MessageId': 'msg-12345'}

    email_notifications.send_scheduled_email(
        mock_sns_client, mock_config, sample_purchase_plans, sample_coverage
    )

    call_args = mock_sns_client.publish.call_args
    message = call_args[1]['Message']

    assert mock_config['queue_url'] in message
    assert 'aws sqs purge-queue' in message


def test_send_scheduled_email_api_error(mock_sns_client, mock_config, sample_coverage, sample_purchase_plans):
    """Test error handling when SNS publish fails."""
    from botocore.exceptions import ClientError

    error_response = {'Error': {'Code': 'AccessDenied', 'Message': 'Access denied'}}
    mock_sns_client.publish.side_effect = ClientError(error_response, 'publish')

    with pytest.raises(ClientError):
        email_notifications.send_scheduled_email(
            mock_sns_client, mock_config, sample_purchase_plans, sample_coverage
        )


def test_send_scheduled_email_multiple_plans_formatting(mock_sns_client, mock_config, sample_coverage):
    """Test email formatting with multiple purchase plans."""
    mock_sns_client.publish.return_value = {'MessageId': 'msg-12345'}

    purchase_plans = [
        {
            'sp_type': 'compute',
            'hourly_commitment': 5.50,
            'term': 'THREE_YEAR',
            'payment_option': 'ALL_UPFRONT'
        },
        {
            'sp_type': 'compute',
            'hourly_commitment': 2.75,
            'term': 'ONE_YEAR',
            'payment_option': 'ALL_UPFRONT'
        },
        {
            'sp_type': 'sagemaker',
            'hourly_commitment': 3.25,
            'term': 'THREE_YEAR',
            'payment_option': 'NO_UPFRONT'
        }
    ]

    email_notifications.send_scheduled_email(
        mock_sns_client, mock_config, purchase_plans, sample_coverage
    )

    call_args = mock_sns_client.publish.call_args
    message = call_args[1]['Message']

    # Verify all plans are listed with numbering
    assert '1. COMPUTE Savings Plan' in message
    assert '2. COMPUTE Savings Plan' in message
    assert '3. SAGEMAKER Savings Plan' in message
    assert 'Hourly Commitment: $5.5000/hour' in message
    assert 'Hourly Commitment: $2.7500/hour' in message
    assert 'Hourly Commitment: $3.2500/hour' in message


# ============================================================================
# Dry Run Email Tests
# ============================================================================

def test_send_dry_run_email_success(mock_sns_client, mock_config, sample_coverage, sample_purchase_plans):
    """Test successful dry run email sending."""
    mock_sns_client.publish.return_value = {'MessageId': 'msg-12345'}

    email_notifications.send_dry_run_email(
        mock_sns_client, mock_config, sample_purchase_plans, sample_coverage
    )

    # Verify publish was called
    mock_sns_client.publish.assert_called_once()

    # Verify call arguments
    call_args = mock_sns_client.publish.call_args
    assert call_args[1]['TopicArn'] == mock_config['sns_topic_arn']
    assert call_args[1]['Subject'] == '[DRY RUN] Savings Plans Analysis - No Purchases Scheduled'
    assert 'Message' in call_args[1]


def test_send_dry_run_email_message_content(mock_sns_client, mock_config, sample_coverage, sample_purchase_plans):
    """Test that dry run email contains expected content."""
    mock_sns_client.publish.return_value = {'MessageId': 'msg-12345'}

    email_notifications.send_dry_run_email(
        mock_sns_client, mock_config, sample_purchase_plans, sample_coverage
    )

    call_args = mock_sns_client.publish.call_args
    message = call_args[1]['Message']

    # Verify key content is present
    assert '***** DRY RUN MODE *****' in message
    assert '*** NO PURCHASES WERE SCHEDULED ***' in message
    assert 'Total Plans Analyzed: 2' in message
    assert 'Compute SP:  75.50%' in message
    assert 'Database SP: 85.00%' in message
    assert 'SageMaker SP: 60.00%' in message
    assert 'Target Coverage: 90.00%' in message
    assert 'WOULD BE SCHEDULED if dry_run=false' in message
    assert 'TO ENABLE ACTUAL PURCHASES' in message


def test_send_dry_run_email_calculates_annual_cost(mock_sns_client, mock_config, sample_coverage):
    """Test that dry run email calculates and displays annual costs."""
    mock_sns_client.publish.return_value = {'MessageId': 'msg-12345'}

    purchase_plans = [
        {
            'sp_type': 'database',
            'hourly_commitment': 0.5,  # $0.5/hour * 8760 hours = $4,380/year
            'term': 'ONE_YEAR',
            'payment_option': 'NO_UPFRONT'
        }
    ]

    email_notifications.send_dry_run_email(
        mock_sns_client, mock_config, purchase_plans, sample_coverage
    )

    call_args = mock_sns_client.publish.call_args
    message = call_args[1]['Message']

    # Verify annual cost calculation (0.5 * 8760 = 4380)
    assert 'Estimated Annual Cost: $4,380.00' in message
    assert 'Total Estimated Annual Cost: $4,380.00' in message


def test_send_dry_run_email_empty_plans(mock_sns_client, mock_config, sample_coverage):
    """Test dry run email with no purchase plans."""
    mock_sns_client.publish.return_value = {'MessageId': 'msg-12345'}

    purchase_plans = []

    email_notifications.send_dry_run_email(
        mock_sns_client, mock_config, purchase_plans, sample_coverage
    )

    call_args = mock_sns_client.publish.call_args
    message = call_args[1]['Message']

    assert 'Total Plans Analyzed: 0' in message
    assert 'Total Estimated Annual Cost: $0.00' in message


def test_send_dry_run_email_includes_enablement_instructions(mock_sns_client, mock_config, sample_coverage, sample_purchase_plans):
    """Test that dry run email includes instructions to enable purchases."""
    mock_sns_client.publish.return_value = {'MessageId': 'msg-12345'}

    email_notifications.send_dry_run_email(
        mock_sns_client, mock_config, sample_purchase_plans, sample_coverage
    )

    call_args = mock_sns_client.publish.call_args
    message = call_args[1]['Message']

    assert 'Set the DRY_RUN environment variable to' in message
    assert 'aws lambda update-function-configuration' in message
    assert 'Variables={DRY_RUN=false' in message
    assert 'dry_run = false' in message


def test_send_dry_run_email_api_error(mock_sns_client, mock_config, sample_coverage, sample_purchase_plans):
    """Test error handling when SNS publish fails."""
    from botocore.exceptions import ClientError

    error_response = {'Error': {'Code': 'ServiceUnavailable', 'Message': 'Service unavailable'}}
    mock_sns_client.publish.side_effect = ClientError(error_response, 'publish')

    with pytest.raises(ClientError):
        email_notifications.send_dry_run_email(
            mock_sns_client, mock_config, sample_purchase_plans, sample_coverage
        )


def test_send_dry_run_email_multiple_plans_formatting(mock_sns_client, mock_config, sample_coverage):
    """Test dry run email formatting with multiple purchase plans."""
    mock_sns_client.publish.return_value = {'MessageId': 'msg-12345'}

    purchase_plans = [
        {
            'sp_type': 'sagemaker',
            'hourly_commitment': 3.25,
            'term': 'THREE_YEAR',
            'payment_option': 'PARTIAL_UPFRONT'
        },
        {
            'sp_type': 'sagemaker',
            'hourly_commitment': 1.50,
            'term': 'ONE_YEAR',
            'payment_option': 'PARTIAL_UPFRONT'
        }
    ]

    email_notifications.send_dry_run_email(
        mock_sns_client, mock_config, purchase_plans, sample_coverage
    )

    call_args = mock_sns_client.publish.call_args
    message = call_args[1]['Message']

    # Verify all plans are listed with numbering
    assert '1. SAGEMAKER Savings Plan' in message
    assert '2. SAGEMAKER Savings Plan' in message
    assert 'Hourly Commitment: $3.2500/hour' in message
    assert 'Hourly Commitment: $1.5000/hour' in message
    assert 'Term: THREE_YEAR' in message
    assert 'Term: ONE_YEAR' in message


# ============================================================================
# Coverage Edge Cases
# ============================================================================

def test_scheduled_email_with_zero_coverage(mock_sns_client, mock_config, sample_purchase_plans):
    """Test scheduled email with zero coverage values."""
    coverage = {
        'compute': 0.0,
        'database': 0.0,
        'sagemaker': 0.0
    }

    mock_sns_client.publish.return_value = {'MessageId': 'msg-12345'}

    email_notifications.send_scheduled_email(
        mock_sns_client, mock_config, sample_purchase_plans, coverage
    )

    call_args = mock_sns_client.publish.call_args
    message = call_args[1]['Message']

    assert 'Compute SP:  0.00%' in message
    assert 'Database SP: 0.00%' in message
    assert 'SageMaker SP: 0.00%' in message


def test_dry_run_email_with_high_coverage(mock_sns_client, mock_config, sample_purchase_plans):
    """Test dry run email with high coverage values."""
    coverage = {
        'compute': 99.9,
        'database': 98.5,
        'sagemaker': 97.3
    }

    mock_sns_client.publish.return_value = {'MessageId': 'msg-12345'}

    email_notifications.send_dry_run_email(
        mock_sns_client, mock_config, sample_purchase_plans, coverage
    )

    call_args = mock_sns_client.publish.call_args
    message = call_args[1]['Message']

    assert 'Compute SP:  99.90%' in message
    assert 'Database SP: 98.50%' in message
    assert 'SageMaker SP: 97.30%' in message


def test_scheduled_email_with_very_small_commitment(mock_sns_client, mock_config, sample_coverage):
    """Test scheduled email with very small hourly commitment."""
    purchase_plans = [
        {
            'sp_type': 'compute',
            'hourly_commitment': 0.001,  # Very small
            'term': 'THREE_YEAR',
            'payment_option': 'ALL_UPFRONT'
        }
    ]

    mock_sns_client.publish.return_value = {'MessageId': 'msg-12345'}

    email_notifications.send_scheduled_email(
        mock_sns_client, mock_config, purchase_plans, sample_coverage
    )

    call_args = mock_sns_client.publish.call_args
    message = call_args[1]['Message']

    # Verify formatting handles small values
    assert 'Hourly Commitment: $0.0010/hour' in message
    # Annual: 0.001 * 8760 = 8.76
    assert 'Estimated Annual Cost: $8.76' in message


def test_dry_run_email_with_large_commitment(mock_sns_client, mock_config, sample_coverage):
    """Test dry run email with large hourly commitment."""
    purchase_plans = [
        {
            'sp_type': 'compute',
            'hourly_commitment': 1000.0,  # Large
            'term': 'THREE_YEAR',
            'payment_option': 'ALL_UPFRONT'
        }
    ]

    mock_sns_client.publish.return_value = {'MessageId': 'msg-12345'}

    email_notifications.send_dry_run_email(
        mock_sns_client, mock_config, purchase_plans, sample_coverage
    )

    call_args = mock_sns_client.publish.call_args
    message = call_args[1]['Message']

    # Verify formatting handles large values with comma separators
    # Annual: 1000 * 8760 = 8,760,000
    assert 'Estimated Annual Cost: $8,760,000.00' in message
    assert 'Total Estimated Annual Cost: $8,760,000.00' in message

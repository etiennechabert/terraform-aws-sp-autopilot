"""
Unit tests for Purchaser Lambda handler - Assume Role functionality.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone
from botocore.exceptions import ClientError
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import handler


def test_get_assumed_role_session_with_valid_arn():
    """Test that AssumeRole is called when ARN is provided."""
    with patch('handler.boto3.client') as mock_boto3_client:
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
            RoleSessionName='sp-autopilot-purchaser'
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
    with patch('handler.boto3.client') as mock_boto3_client:
        mock_sts = MagicMock()
        mock_boto3_client.return_value = mock_sts

        # Mock AccessDenied error
        error_response = {
            'Error': {
                'Code': 'AccessDenied',
                'Message': 'User: arn:aws:sts::111:assumed-role/lambda is not authorized to perform: sts:AssumeRole'
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

    with patch('handler.get_assumed_role_session') as mock_assume, \
         patch('handler.boto3.client') as mock_boto3_client:

        # Mock session from assumed role
        mock_session = MagicMock()
        mock_assume.return_value = mock_session

        # Mock session.client() calls
        mock_session.client.return_value = MagicMock()

        # Mock boto3.client() calls (for SNS/SQS)
        mock_boto3_client.return_value = MagicMock()

        # Call function
        clients = handler.get_clients(config)

        # Verify assume role was called
        mock_assume.assert_called_once_with('arn:aws:iam::123456789012:role/TestRole')

        # Verify CE and Savings Plans clients use session
        assert mock_session.client.call_count == 2
        mock_session.client.assert_any_call('ce')
        mock_session.client.assert_any_call('savingsplans')

        # Verify SNS and SQS clients use local credentials (boto3.client directly)
        assert mock_boto3_client.call_count == 2
        mock_boto3_client.assert_any_call('sns')
        mock_boto3_client.assert_any_call('sqs')


def test_get_clients_without_role_arn():
    """Test that all clients use default credentials when no role ARN provided (backward compatibility)."""
    config = {'management_account_role_arn': None}

    with patch('handler.boto3.client') as mock_boto3_client:
        mock_boto3_client.return_value = MagicMock()

        # Call function
        clients = handler.get_clients(config)

        # Verify all 4 clients use boto3.client directly (no assume role)
        assert mock_boto3_client.call_count == 4
        mock_boto3_client.assert_any_call('ce')
        mock_boto3_client.assert_any_call('savingsplans')
        mock_boto3_client.assert_any_call('sns')
        mock_boto3_client.assert_any_call('sqs')


def test_handler_assume_role_error_handling(monkeypatch):
    """Test that handler error message includes role ARN when assume role fails."""
    # Set environment variables
    monkeypatch.setenv('QUEUE_URL', 'https://sqs.us-east-1.amazonaws.com/123/queue')
    monkeypatch.setenv('SNS_TOPIC_ARN', 'arn:aws:sns:us-east-1:123:topic')
    monkeypatch.setenv('MANAGEMENT_ACCOUNT_ROLE_ARN', 'arn:aws:iam::123456789012:role/TestRole')
    monkeypatch.setenv('MAX_COVERAGE_CAP', '95')
    monkeypatch.setenv('RENEWAL_WINDOW_DAYS', '7')
    monkeypatch.setenv('TAGS', '{}')

    with patch('handler.get_clients') as mock_get_clients, \
         patch('handler.send_error_email') as mock_send_error:

        # Mock assume role failure
        error_response = {'Error': {'Code': 'AccessDenied', 'Message': 'Not authorized'}}
        mock_get_clients.side_effect = ClientError(error_response, 'AssumeRole')

        # Call handler - should raise exception
        with pytest.raises(ClientError):
            handler.handler({}, None)

        # Verify error email was sent
        assert mock_send_error.call_count == 1

        # Verify error message includes role ARN
        error_msg = mock_send_error.call_args[0][0]
        assert 'arn:aws:iam::123456789012:role/TestRole' in error_msg

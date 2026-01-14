"""
Comprehensive unit tests for Reporter Lambda handler.

Tests cover all functions with edge cases to achieve >= 80% coverage.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone, timedelta
from botocore.exceptions import ClientError
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import handler


@pytest.fixture
def mock_env_vars(monkeypatch):
    """Set up environment variables for testing."""
    monkeypatch.setenv('REPORTS_BUCKET', 'test-reports-bucket')
    monkeypatch.setenv('SNS_TOPIC_ARN', 'arn:aws:sns:us-east-1:123456789012:test-topic')
    monkeypatch.setenv('REPORT_FORMAT', 'html')
    monkeypatch.setenv('EMAIL_REPORTS', 'true')
    monkeypatch.setenv('MANAGEMENT_ACCOUNT_ROLE_ARN', '')
    monkeypatch.setenv('TAGS', '{}')


# ============================================================================
# Assume Role Tests
# ============================================================================

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
            RoleSessionName='sp-autopilot-reporter'
        )


def test_get_assumed_role_session_without_arn():
    """Test that None is returned when ARN is not provided."""
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

        # Mock boto3.client() calls (for SNS/S3)
        mock_boto3_client.return_value = MagicMock()

        # Call function
        clients = handler.get_clients(config)

        # Verify assume role was called
        mock_assume.assert_called_once_with('arn:aws:iam::123456789012:role/TestRole')

        # Verify CE and Savings Plans clients use session
        assert mock_session.client.call_count == 2
        mock_session.client.assert_any_call('ce')
        mock_session.client.assert_any_call('savingsplans')

        # Verify SNS and S3 clients use local credentials (boto3.client directly)
        assert mock_boto3_client.call_count == 2
        mock_boto3_client.assert_any_call('sns')
        mock_boto3_client.assert_any_call('s3')


def test_get_clients_without_role_arn():
    """Test that all clients use default credentials when no role ARN provided."""
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
        mock_boto3_client.assert_any_call('s3')


# ============================================================================
# Configuration Tests
# ============================================================================

def test_load_configuration_defaults(mock_env_vars):
    """Test that load_configuration returns correct default values."""
    config = handler.load_configuration()

    assert config['reports_bucket'] == 'test-reports-bucket'
    assert config['sns_topic_arn'] == 'arn:aws:sns:us-east-1:123456789012:test-topic'
    assert config['report_format'] == 'html'
    assert config['email_reports'] is True
    assert config['management_account_role_arn'] == ''
    assert config['tags'] == {}


def test_load_configuration_custom_values(monkeypatch):
    """Test that load_configuration handles custom environment values."""
    monkeypatch.setenv('REPORTS_BUCKET', 'custom-bucket')
    monkeypatch.setenv('SNS_TOPIC_ARN', 'custom-sns-arn')
    monkeypatch.setenv('REPORT_FORMAT', 'json')
    monkeypatch.setenv('EMAIL_REPORTS', 'false')
    monkeypatch.setenv('MANAGEMENT_ACCOUNT_ROLE_ARN', 'arn:aws:iam::123456789012:role/CustomRole')
    monkeypatch.setenv('TAGS', '{"env": "prod"}')

    config = handler.load_configuration()

    assert config['reports_bucket'] == 'custom-bucket'
    assert config['sns_topic_arn'] == 'custom-sns-arn'
    assert config['report_format'] == 'json'
    assert config['email_reports'] is False
    assert config['management_account_role_arn'] == 'arn:aws:iam::123456789012:role/CustomRole'
    assert config['tags'] == {"env": "prod"}


# ============================================================================
# Coverage History Tests
# ============================================================================

def test_get_coverage_history_success():
    """Test successful retrieval of coverage history."""
    with patch.object(handler.ce_client, 'get_savings_plans_coverage') as mock_get_coverage:
        mock_get_coverage.return_value = {
            'SavingsPlansCoverages': [
                {
                    'TimePeriod': {'Start': '2026-01-10', 'End': '2026-01-11'},
                    'Coverage': {
                        'CoveragePercentage': '75.5',
                        'CoverageHours': {
                            'OnDemandHours': '100',
                            'CoveredHours': '300',
                            'TotalRunningHours': '400'
                        }
                    }
                },
                {
                    'TimePeriod': {'Start': '2026-01-11', 'End': '2026-01-12'},
                    'Coverage': {
                        'CoveragePercentage': '80.0',
                        'CoverageHours': {
                            'OnDemandHours': '80',
                            'CoveredHours': '320',
                            'TotalRunningHours': '400'
                        }
                    }
                }
            ]
        }

        result = handler.get_coverage_history(lookback_days=2)

        assert len(result) == 2
        assert result[0]['date'] == '2026-01-10'
        assert result[0]['coverage_percentage'] == 75.5
        assert result[0]['on_demand_hours'] == 100.0
        assert result[0]['covered_hours'] == 300.0
        assert result[0]['total_hours'] == 400.0


def test_get_coverage_history_empty():
    """Test handling of no coverage data."""
    with patch.object(handler.ce_client, 'get_savings_plans_coverage') as mock_get_coverage:
        mock_get_coverage.return_value = {
            'SavingsPlansCoverages': []
        }

        result = handler.get_coverage_history(lookback_days=30)

        assert result == []


def test_get_coverage_history_client_error():
    """Test that ClientError is raised on API failure."""
    with patch.object(handler.ce_client, 'get_savings_plans_coverage') as mock_get_coverage:
        error_response = {
            'Error': {
                'Code': 'AccessDenied',
                'Message': 'Not authorized'
            }
        }
        mock_get_coverage.side_effect = ClientError(error_response, 'get_savings_plans_coverage')

        with pytest.raises(ClientError):
            handler.get_coverage_history(lookback_days=30)


# ============================================================================
# Savings Data Tests
# ============================================================================

def test_get_savings_data_with_active_plans():
    """Test retrieval of savings data with active plans."""
    with patch.object(handler.savingsplans_client, 'describe_savings_plans') as mock_describe, \
         patch.object(handler.ce_client, 'get_savings_plans_utilization') as mock_utilization:

        mock_describe.return_value = {
            'savingsPlans': [
                {
                    'savingsPlanId': 'sp-12345678',
                    'savingsPlanType': 'ComputeSavingsPlans',
                    'commitment': '1.5',
                    'start': '2025-01-01T00:00:00Z',
                    'end': '2026-01-01T00:00:00Z',
                    'paymentOption': 'ALL_UPFRONT',
                    'termDurationInSeconds': 31536000  # 1 year
                },
                {
                    'savingsPlanId': 'sp-87654321',
                    'savingsPlanType': 'ComputeSavingsPlans',
                    'commitment': '2.0',
                    'start': '2025-06-01T00:00:00Z',
                    'end': '2028-06-01T00:00:00Z',
                    'paymentOption': 'NO_UPFRONT',
                    'termDurationInSeconds': 94608000  # 3 years
                }
            ]
        }

        mock_utilization.return_value = {
            'SavingsPlansUtilizationsByTime': [
                {
                    'TimePeriod': {'Start': '2026-01-10', 'End': '2026-01-11'},
                    'Utilization': {'UtilizationPercentage': '95.0'}
                },
                {
                    'TimePeriod': {'Start': '2026-01-11', 'End': '2026-01-12'},
                    'Utilization': {'UtilizationPercentage': '97.0'}
                }
            ]
        }

        result = handler.get_savings_data()

        assert result['plans_count'] == 2
        assert result['total_commitment'] == 3.5
        assert result['average_utilization'] == 96.0
        assert result['estimated_monthly_savings'] == 3.5 * 730 * 0.25
        assert len(result['plans']) == 2
        assert result['plans'][0]['plan_id'] == 'sp-12345678'
        assert result['plans'][0]['term_years'] == 1
        assert result['plans'][1]['term_years'] == 3


def test_get_savings_data_no_active_plans():
    """Test handling of no active Savings Plans."""
    with patch.object(handler.savingsplans_client, 'describe_savings_plans') as mock_describe:
        mock_describe.return_value = {
            'savingsPlans': []
        }

        result = handler.get_savings_data()

        assert result['total_commitment'] == 0.0
        assert result['plans_count'] == 0
        assert result['plans'] == []
        assert result['estimated_monthly_savings'] == 0.0
        assert result['average_utilization'] == 0.0


def test_get_savings_data_utilization_error():
    """Test that utilization errors are handled gracefully."""
    with patch.object(handler.savingsplans_client, 'describe_savings_plans') as mock_describe, \
         patch.object(handler.ce_client, 'get_savings_plans_utilization') as mock_utilization:

        mock_describe.return_value = {
            'savingsPlans': [
                {
                    'savingsPlanId': 'sp-12345678',
                    'savingsPlanType': 'ComputeSavingsPlans',
                    'commitment': '1.5',
                    'start': '2025-01-01T00:00:00Z',
                    'end': '2026-01-01T00:00:00Z',
                    'paymentOption': 'ALL_UPFRONT',
                    'termDurationInSeconds': 31536000
                }
            ]
        }

        error_response = {
            'Error': {
                'Code': 'ThrottlingException',
                'Message': 'Rate exceeded'
            }
        }
        mock_utilization.side_effect = ClientError(error_response, 'get_savings_plans_utilization')

        result = handler.get_savings_data()

        # Should still return data, just with zero utilization
        assert result['plans_count'] == 1
        assert result['average_utilization'] == 0.0


def test_get_savings_data_describe_error():
    """Test that describe_savings_plans errors are raised."""
    with patch.object(handler.savingsplans_client, 'describe_savings_plans') as mock_describe:
        error_response = {
            'Error': {
                'Code': 'AccessDenied',
                'Message': 'Not authorized'
            }
        }
        mock_describe.side_effect = ClientError(error_response, 'describe_savings_plans')

        with pytest.raises(ClientError):
            handler.get_savings_data()


# ============================================================================
# HTML Report Generation Tests
# ============================================================================

def test_generate_html_report_with_data():
    """Test HTML report generation with full data."""
    coverage_history = [
        {
            'date': '2026-01-10',
            'coverage_percentage': 75.0,
            'covered_hours': 300.0,
            'on_demand_hours': 100.0,
            'total_hours': 400.0
        },
        {
            'date': '2026-01-11',
            'coverage_percentage': 80.0,
            'covered_hours': 320.0,
            'on_demand_hours': 80.0,
            'total_hours': 400.0
        }
    ]

    savings_data = {
        'total_commitment': 3.5,
        'plans_count': 2,
        'plans': [
            {
                'plan_id': 'sp-12345678901234567890',
                'plan_type': 'ComputeSavingsPlans',
                'hourly_commitment': 1.5,
                'start_date': '2025-01-01T00:00:00Z',
                'end_date': '2026-01-01T00:00:00Z',
                'payment_option': 'ALL_UPFRONT',
                'term_years': 1
            }
        ],
        'estimated_monthly_savings': 639.25,
        'average_utilization': 96.0
    }

    result = handler.generate_html_report(coverage_history, savings_data)

    assert '<!DOCTYPE html>' in result
    assert '80.0%' in result  # Current coverage
    assert '77.5%' in result  # Average coverage
    assert '2 days' in result
    assert '2026-01-10' in result
    assert 'ComputeSavingsPlans' in result
    assert '639' in result  # Estimated monthly savings
    assert 'sp-12345678901234567' in result  # Truncated plan ID


def test_generate_html_report_empty_coverage():
    """Test HTML report generation with no coverage data."""
    coverage_history = []
    savings_data = {
        'total_commitment': 0.0,
        'plans_count': 0,
        'plans': [],
        'estimated_monthly_savings': 0.0,
        'average_utilization': 0.0
    }

    result = handler.generate_html_report(coverage_history, savings_data)

    assert '<!DOCTYPE html>' in result
    assert '0.0%' in result  # Zero coverage
    assert 'No coverage data available' in result
    assert 'No active Savings Plans found' in result


def test_generate_html_report_trend_up():
    """Test HTML report shows upward trend symbol."""
    coverage_history = [
        {'date': '2026-01-10', 'coverage_percentage': 70.0, 'covered_hours': 280.0, 'on_demand_hours': 120.0, 'total_hours': 400.0},
        {'date': '2026-01-11', 'coverage_percentage': 80.0, 'covered_hours': 320.0, 'on_demand_hours': 80.0, 'total_hours': 400.0}
    ]

    savings_data = {'total_commitment': 0.0, 'plans_count': 0, 'plans': [], 'estimated_monthly_savings': 0.0, 'average_utilization': 0.0}

    result = handler.generate_html_report(coverage_history, savings_data)

    assert '↑' in result


def test_generate_html_report_trend_down():
    """Test HTML report shows downward trend symbol."""
    coverage_history = [
        {'date': '2026-01-10', 'coverage_percentage': 80.0, 'covered_hours': 320.0, 'on_demand_hours': 80.0, 'total_hours': 400.0},
        {'date': '2026-01-11', 'coverage_percentage': 70.0, 'covered_hours': 280.0, 'on_demand_hours': 120.0, 'total_hours': 400.0}
    ]

    savings_data = {'total_commitment': 0.0, 'plans_count': 0, 'plans': [], 'estimated_monthly_savings': 0.0, 'average_utilization': 0.0}

    result = handler.generate_html_report(coverage_history, savings_data)

    assert '↓' in result


# ============================================================================
# S3 Upload Tests
# ============================================================================

def test_upload_report_to_s3_success(mock_env_vars):
    """Test successful S3 upload."""
    config = handler.load_configuration()

    with patch.object(handler.s3_client, 'put_object') as mock_put_object:
        mock_put_object.return_value = {}

        report_content = '<html>Test Report</html>'
        result = handler.upload_report_to_s3(config, report_content, 'html')

        assert result.startswith('savings-plans-report_')
        assert result.endswith('.html')

        # Verify put_object was called with correct parameters
        mock_put_object.assert_called_once()
        call_args = mock_put_object.call_args[1]
        assert call_args['Bucket'] == 'test-reports-bucket'
        assert call_args['ContentType'] == 'text/html'
        assert call_args['ServerSideEncryption'] == 'AES256'


def test_upload_report_to_s3_error(mock_env_vars):
    """Test S3 upload error handling."""
    config = handler.load_configuration()

    with patch.object(handler.s3_client, 'put_object') as mock_put_object:
        error_response = {
            'Error': {
                'Code': 'AccessDenied',
                'Message': 'Not authorized'
            }
        }
        mock_put_object.side_effect = ClientError(error_response, 'put_object')

        with pytest.raises(ClientError):
            handler.upload_report_to_s3(config, '<html>Test</html>', 'html')


# ============================================================================
# Email Notification Tests
# ============================================================================

def test_send_report_email_success(mock_env_vars):
    """Test successful email notification."""
    config = handler.load_configuration()

    coverage_summary = {
        'current_coverage': 80.0,
        'avg_coverage': 77.5,
        'coverage_days': 30,
        'trend_direction': '↑'
    }

    savings_summary = {
        'plans_count': 2,
        'total_commitment': 3.5,
        'estimated_monthly_savings': 639.25,
        'average_utilization': 96.0
    }

    with patch.object(handler.sns_client, 'publish') as mock_publish:
        mock_publish.return_value = {}

        handler.send_report_email(
            config,
            'savings-plans-report_2026-01-14_12-00-00.html',
            coverage_summary,
            savings_summary
        )

        mock_publish.assert_called_once()
        call_args = mock_publish.call_args[1]
        assert call_args['TopicArn'] == 'arn:aws:sns:us-east-1:123456789012:test-topic'
        assert '80.0%' in call_args['Subject']
        assert '$639' in call_args['Subject']
        assert 's3://test-reports-bucket/' in call_args['Message']


def test_send_report_email_error(mock_env_vars):
    """Test email notification error handling."""
    config = handler.load_configuration()

    coverage_summary = {'current_coverage': 80.0, 'avg_coverage': 77.5, 'coverage_days': 30, 'trend_direction': '↑'}
    savings_summary = {'plans_count': 2, 'total_commitment': 3.5, 'estimated_monthly_savings': 639.25, 'average_utilization': 96.0}

    with patch.object(handler.sns_client, 'publish') as mock_publish:
        error_response = {
            'Error': {
                'Code': 'InvalidParameter',
                'Message': 'Invalid topic'
            }
        }
        mock_publish.side_effect = ClientError(error_response, 'publish')

        with pytest.raises(ClientError):
            handler.send_report_email(config, 's3-key', coverage_summary, savings_summary)


def test_send_error_email(mock_env_vars):
    """Test error email notification."""
    config = handler.load_configuration()

    with patch.object(handler.sns_client, 'publish') as mock_publish:
        mock_publish.return_value = {}

        handler.send_error_email(config, 'Test error message')

        mock_publish.assert_called_once()
        call_args = mock_publish.call_args[1]
        assert '[SP Autopilot] Reporter Lambda Failed' in call_args['Subject']
        assert 'Test error message' in call_args['Message']


def test_send_error_email_silent_failure(mock_env_vars):
    """Test that send_error_email doesn't raise on SNS failure."""
    config = handler.load_configuration()

    with patch.object(handler.sns_client, 'publish') as mock_publish:
        error_response = {
            'Error': {
                'Code': 'InvalidParameter',
                'Message': 'Invalid topic'
            }
        }
        mock_publish.side_effect = ClientError(error_response, 'publish')

        # Should not raise - just log error
        handler.send_error_email(config, 'Test error')


# ============================================================================
# Handler Integration Tests
# ============================================================================

def test_handler_success_with_email(mock_env_vars):
    """Test successful handler execution with email enabled."""
    with patch('handler.load_configuration') as mock_load_config, \
         patch('handler.get_clients') as mock_get_clients, \
         patch('handler.get_coverage_history') as mock_get_coverage, \
         patch('handler.get_savings_data') as mock_get_savings, \
         patch('handler.generate_html_report') as mock_generate_html, \
         patch('handler.upload_report_to_s3') as mock_upload, \
         patch('handler.send_report_email') as mock_send_email:

        mock_load_config.return_value = {
            'reports_bucket': 'test-bucket',
            'sns_topic_arn': 'test-arn',
            'report_format': 'html',
            'email_reports': True,
            'management_account_role_arn': None,
            'tags': {}
        }

        mock_get_clients.return_value = {
            'ce': MagicMock(),
            'savingsplans': MagicMock(),
            'sns': MagicMock(),
            's3': MagicMock()
        }

        mock_get_coverage.return_value = [
            {'date': '2026-01-10', 'coverage_percentage': 75.0, 'covered_hours': 300.0, 'on_demand_hours': 100.0, 'total_hours': 400.0},
            {'date': '2026-01-11', 'coverage_percentage': 80.0, 'covered_hours': 320.0, 'on_demand_hours': 80.0, 'total_hours': 400.0}
        ]

        mock_get_savings.return_value = {
            'plans_count': 2,
            'total_commitment': 3.5,
            'estimated_monthly_savings': 639.25,
            'average_utilization': 96.0
        }

        mock_generate_html.return_value = '<html>Test Report</html>'
        mock_upload.return_value = 'savings-plans-report_2026-01-14_12-00-00.html'

        result = handler.handler({}, None)

        assert result['statusCode'] == 200
        assert 'savings-plans-report_' in result['body']
        assert mock_send_email.called


def test_handler_success_without_email(mock_env_vars, monkeypatch):
    """Test successful handler execution with email disabled."""
    monkeypatch.setenv('EMAIL_REPORTS', 'false')

    with patch('handler.load_configuration') as mock_load_config, \
         patch('handler.get_clients') as mock_get_clients, \
         patch('handler.get_coverage_history') as mock_get_coverage, \
         patch('handler.get_savings_data') as mock_get_savings, \
         patch('handler.generate_html_report') as mock_generate_html, \
         patch('handler.upload_report_to_s3') as mock_upload, \
         patch('handler.send_report_email') as mock_send_email:

        mock_load_config.return_value = {
            'reports_bucket': 'test-bucket',
            'sns_topic_arn': 'test-arn',
            'report_format': 'html',
            'email_reports': False,
            'management_account_role_arn': None,
            'tags': {}
        }

        mock_get_clients.return_value = {
            'ce': MagicMock(),
            'savingsplans': MagicMock(),
            'sns': MagicMock(),
            's3': MagicMock()
        }

        mock_get_coverage.return_value = []
        mock_get_savings.return_value = {'plans_count': 0, 'total_commitment': 0.0, 'estimated_monthly_savings': 0.0, 'average_utilization': 0.0}
        mock_generate_html.return_value = '<html>Test Report</html>'
        mock_upload.return_value = 'savings-plans-report_2026-01-14_12-00-00.html'

        result = handler.handler({}, None)

        assert result['statusCode'] == 200
        assert not mock_send_email.called


def test_handler_assume_role_error(mock_env_vars, monkeypatch):
    """Test handler error handling when assume role fails."""
    monkeypatch.setenv('MANAGEMENT_ACCOUNT_ROLE_ARN', 'arn:aws:iam::123456789012:role/TestRole')

    with patch('handler.load_configuration') as mock_load_config, \
         patch('handler.get_clients') as mock_get_clients, \
         patch('handler.send_error_email') as mock_send_error:

        mock_load_config.return_value = {
            'reports_bucket': 'test-bucket',
            'sns_topic_arn': 'test-arn',
            'report_format': 'html',
            'email_reports': True,
            'management_account_role_arn': 'arn:aws:iam::123456789012:role/TestRole',
            'tags': {}
        }

        error_response = {
            'Error': {
                'Code': 'AccessDenied',
                'Message': 'Not authorized'
            }
        }
        mock_get_clients.side_effect = ClientError(error_response, 'AssumeRole')

        with pytest.raises(ClientError):
            handler.handler({}, None)

        # Verify error email was sent with role ARN in message
        assert mock_send_error.called
        error_msg = mock_send_error.call_args[0][1]
        assert 'arn:aws:iam::123456789012:role/TestRole' in error_msg


def test_handler_general_error(mock_env_vars):
    """Test handler error handling for general exceptions."""
    with patch('handler.load_configuration') as mock_load_config, \
         patch('handler.get_clients') as mock_get_clients, \
         patch('handler.get_coverage_history') as mock_get_coverage, \
         patch('handler.send_error_email') as mock_send_error:

        mock_load_config.return_value = {
            'reports_bucket': 'test-bucket',
            'sns_topic_arn': 'test-arn',
            'report_format': 'html',
            'email_reports': False,
            'management_account_role_arn': None,
            'tags': {}
        }

        mock_get_clients.return_value = {
            'ce': MagicMock(),
            'savingsplans': MagicMock(),
            'sns': MagicMock(),
            's3': MagicMock()
        }

        mock_get_coverage.side_effect = Exception('Unexpected error')

        with pytest.raises(Exception):
            handler.handler({}, None)

        # Verify error email was sent
        assert mock_send_error.called

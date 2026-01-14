"""
Comprehensive unit tests for handler_utils.py.

Tests cover all utility functions with edge cases to achieve >= 80% coverage.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, call
from datetime import datetime, timezone
import json
import sys
import os
from botocore.exceptions import ClientError

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from shared import handler_utils


# ============================================================================
# load_config_from_env Tests
# ============================================================================

def test_load_config_from_env_required_field_present(monkeypatch):
    """Test that required fields are loaded when present."""
    monkeypatch.setenv('QUEUE_URL', 'https://sqs.us-east-1.amazonaws.com/123/queue')

    schema = {
        'queue_url': {'required': True, 'type': 'str', 'env_var': 'QUEUE_URL'}
    }

    config = handler_utils.load_config_from_env(schema)

    assert config['queue_url'] == 'https://sqs.us-east-1.amazonaws.com/123/queue'


def test_load_config_from_env_required_field_missing(monkeypatch):
    """Test that missing required fields raise KeyError."""
    schema = {
        'queue_url': {'required': True, 'type': 'str', 'env_var': 'QUEUE_URL'}
    }

    with pytest.raises(KeyError):
        handler_utils.load_config_from_env(schema)


def test_load_config_from_env_optional_field_with_default(monkeypatch):
    """Test that optional fields use default values when not present."""
    schema = {
        'dry_run': {'required': False, 'type': 'bool', 'default': 'true', 'env_var': 'DRY_RUN'}
    }

    config = handler_utils.load_config_from_env(schema)

    assert config['dry_run'] is True


def test_load_config_from_env_optional_field_override_default(monkeypatch):
    """Test that environment values override defaults."""
    monkeypatch.setenv('DRY_RUN', 'false')

    schema = {
        'dry_run': {'required': False, 'type': 'bool', 'default': 'true', 'env_var': 'DRY_RUN'}
    }

    config = handler_utils.load_config_from_env(schema)

    assert config['dry_run'] is False


def test_load_config_from_env_optional_field_no_default(monkeypatch):
    """Test that optional fields without defaults are skipped when missing."""
    schema = {
        'optional_field': {'required': False, 'type': 'str', 'env_var': 'OPTIONAL_FIELD'}
    }

    config = handler_utils.load_config_from_env(schema)

    assert 'optional_field' not in config


def test_load_config_from_env_string_type(monkeypatch):
    """Test string type conversion."""
    monkeypatch.setenv('MY_STRING', 'test-value')

    schema = {
        'my_string': {'required': True, 'type': 'str', 'env_var': 'MY_STRING'}
    }

    config = handler_utils.load_config_from_env(schema)

    assert config['my_string'] == 'test-value'
    assert isinstance(config['my_string'], str)


def test_load_config_from_env_bool_type_true(monkeypatch):
    """Test boolean type conversion for true values."""
    monkeypatch.setenv('BOOL_TRUE', 'true')
    monkeypatch.setenv('BOOL_TRUE_CAPS', 'TRUE')
    monkeypatch.setenv('BOOL_TRUE_MIXED', 'TrUe')

    schema = {
        'bool_true': {'required': True, 'type': 'bool', 'env_var': 'BOOL_TRUE'},
        'bool_true_caps': {'required': True, 'type': 'bool', 'env_var': 'BOOL_TRUE_CAPS'},
        'bool_true_mixed': {'required': True, 'type': 'bool', 'env_var': 'BOOL_TRUE_MIXED'}
    }

    config = handler_utils.load_config_from_env(schema)

    assert config['bool_true'] is True
    assert config['bool_true_caps'] is True
    assert config['bool_true_mixed'] is True


def test_load_config_from_env_bool_type_false(monkeypatch):
    """Test boolean type conversion for false values."""
    monkeypatch.setenv('BOOL_FALSE', 'false')
    monkeypatch.setenv('BOOL_RANDOM', 'anything-else')
    monkeypatch.setenv('BOOL_EMPTY', '')

    schema = {
        'bool_false': {'required': True, 'type': 'bool', 'env_var': 'BOOL_FALSE'},
        'bool_random': {'required': True, 'type': 'bool', 'env_var': 'BOOL_RANDOM'},
        'bool_empty': {'required': True, 'type': 'bool', 'env_var': 'BOOL_EMPTY'}
    }

    config = handler_utils.load_config_from_env(schema)

    assert config['bool_false'] is False
    assert config['bool_random'] is False
    assert config['bool_empty'] is False


def test_load_config_from_env_int_type(monkeypatch):
    """Test integer type conversion."""
    monkeypatch.setenv('MY_INT', '42')
    monkeypatch.setenv('NEGATIVE_INT', '-10')

    schema = {
        'my_int': {'required': True, 'type': 'int', 'env_var': 'MY_INT'},
        'negative_int': {'required': True, 'type': 'int', 'env_var': 'NEGATIVE_INT'}
    }

    config = handler_utils.load_config_from_env(schema)

    assert config['my_int'] == 42
    assert config['negative_int'] == -10
    assert isinstance(config['my_int'], int)


def test_load_config_from_env_float_type(monkeypatch):
    """Test float type conversion."""
    monkeypatch.setenv('MY_FLOAT', '3.14')
    monkeypatch.setenv('NEGATIVE_FLOAT', '-2.5')
    monkeypatch.setenv('INT_AS_FLOAT', '10')

    schema = {
        'my_float': {'required': True, 'type': 'float', 'env_var': 'MY_FLOAT'},
        'negative_float': {'required': True, 'type': 'float', 'env_var': 'NEGATIVE_FLOAT'},
        'int_as_float': {'required': True, 'type': 'float', 'env_var': 'INT_AS_FLOAT'}
    }

    config = handler_utils.load_config_from_env(schema)

    assert config['my_float'] == 3.14
    assert config['negative_float'] == -2.5
    assert config['int_as_float'] == 10.0
    assert isinstance(config['my_float'], float)


def test_load_config_from_env_json_type_dict(monkeypatch):
    """Test JSON type conversion for dictionaries."""
    monkeypatch.setenv('MY_JSON', '{"key": "value", "count": 42}')

    schema = {
        'my_json': {'required': True, 'type': 'json', 'env_var': 'MY_JSON'}
    }

    config = handler_utils.load_config_from_env(schema)

    assert config['my_json'] == {"key": "value", "count": 42}
    assert isinstance(config['my_json'], dict)


def test_load_config_from_env_json_type_list(monkeypatch):
    """Test JSON type conversion for lists."""
    monkeypatch.setenv('MY_JSON', '[1, 2, 3, "test"]')

    schema = {
        'my_json': {'required': True, 'type': 'json', 'env_var': 'MY_JSON'}
    }

    config = handler_utils.load_config_from_env(schema)

    assert config['my_json'] == [1, 2, 3, "test"]
    assert isinstance(config['my_json'], list)


def test_load_config_from_env_invalid_int():
    """Test that invalid integer conversion raises ValueError."""
    schema = {
        'my_int': {'required': False, 'type': 'int', 'default': 'not-an-int', 'env_var': 'MY_INT'}
    }

    with pytest.raises(ValueError) as exc_info:
        handler_utils.load_config_from_env(schema)

    assert 'Failed to convert field' in str(exc_info.value)
    assert 'my_int' in str(exc_info.value)


def test_load_config_from_env_invalid_float():
    """Test that invalid float conversion raises ValueError."""
    schema = {
        'my_float': {'required': False, 'type': 'float', 'default': 'not-a-float', 'env_var': 'MY_FLOAT'}
    }

    with pytest.raises(ValueError) as exc_info:
        handler_utils.load_config_from_env(schema)

    assert 'Failed to convert field' in str(exc_info.value)
    assert 'my_float' in str(exc_info.value)


def test_load_config_from_env_invalid_json():
    """Test that invalid JSON raises JSONDecodeError."""
    schema = {
        'my_json': {'required': False, 'type': 'json', 'default': '{invalid json}', 'env_var': 'MY_JSON'}
    }

    with pytest.raises(json.JSONDecodeError) as exc_info:
        handler_utils.load_config_from_env(schema)

    assert 'Failed to parse JSON' in str(exc_info.value)


def test_load_config_from_env_env_var_defaults_to_uppercase(monkeypatch):
    """Test that env_var defaults to uppercase field name."""
    monkeypatch.setenv('QUEUE_URL', 'test-queue-url')

    schema = {
        'queue_url': {'required': True, 'type': 'str'}
    }

    config = handler_utils.load_config_from_env(schema)

    assert config['queue_url'] == 'test-queue-url'


def test_load_config_from_env_unknown_type_logs_warning(monkeypatch, caplog):
    """Test that unknown types log a warning and treat as string."""
    monkeypatch.setenv('MY_FIELD', 'test-value')

    schema = {
        'my_field': {'required': True, 'type': 'unknown_type', 'env_var': 'MY_FIELD'}
    }

    config = handler_utils.load_config_from_env(schema)

    assert config['my_field'] == 'test-value'
    assert 'Unknown type' in caplog.text
    assert 'unknown_type' in caplog.text


def test_load_config_from_env_complex_schema(monkeypatch):
    """Test a complex schema with multiple field types."""
    monkeypatch.setenv('QUEUE_URL', 'https://sqs.us-east-1.amazonaws.com/123/queue')
    monkeypatch.setenv('DRY_RUN', 'true')
    monkeypatch.setenv('MAX_PURCHASE', '15.5')
    monkeypatch.setenv('RENEWAL_DAYS', '7')
    monkeypatch.setenv('TAGS', '{"env": "prod", "team": "data"}')

    schema = {
        'queue_url': {'required': True, 'type': 'str', 'env_var': 'QUEUE_URL'},
        'dry_run': {'required': False, 'type': 'bool', 'default': 'false', 'env_var': 'DRY_RUN'},
        'max_purchase': {'required': False, 'type': 'float', 'default': '10.0', 'env_var': 'MAX_PURCHASE'},
        'renewal_days': {'required': False, 'type': 'int', 'default': '14', 'env_var': 'RENEWAL_DAYS'},
        'tags': {'required': False, 'type': 'json', 'default': '{}', 'env_var': 'TAGS'},
        'optional_missing': {'required': False, 'type': 'str', 'env_var': 'OPTIONAL_MISSING'}
    }

    config = handler_utils.load_config_from_env(schema)

    assert config['queue_url'] == 'https://sqs.us-east-1.amazonaws.com/123/queue'
    assert config['dry_run'] is True
    assert config['max_purchase'] == 15.5
    assert config['renewal_days'] == 7
    assert config['tags'] == {"env": "prod", "team": "data"}
    assert 'optional_missing' not in config


# ============================================================================
# initialize_clients Tests
# ============================================================================

def test_initialize_clients_success():
    """Test successful client initialization without assume role."""
    config = {}

    with patch('shared.handler_utils.get_clients') as mock_get_clients:
        mock_clients = {
            'ce': MagicMock(),
            'savingsplans': MagicMock(),
            's3': MagicMock()
        }
        mock_get_clients.return_value = mock_clients

        result = handler_utils.initialize_clients(config, 'test-session')

        assert result == mock_clients
        mock_get_clients.assert_called_once_with(config, session_name='test-session')


def test_initialize_clients_with_assume_role():
    """Test client initialization with assume role ARN."""
    config = {
        'management_account_role_arn': 'arn:aws:iam::123456789012:role/TestRole'
    }

    with patch('shared.handler_utils.get_clients') as mock_get_clients:
        mock_clients = {'ce': MagicMock(), 'savingsplans': MagicMock()}
        mock_get_clients.return_value = mock_clients

        result = handler_utils.initialize_clients(config, 'sp-autopilot-scheduler')

        assert result == mock_clients
        mock_get_clients.assert_called_once_with(config, session_name='sp-autopilot-scheduler')


def test_initialize_clients_error_without_role(caplog):
    """Test error handling when client initialization fails without role ARN."""
    config = {}
    error_response = {'Error': {'Code': 'AccessDenied', 'Message': 'Not authorized'}}

    with patch('shared.handler_utils.get_clients') as mock_get_clients:
        mock_get_clients.side_effect = ClientError(error_response, 'GetCostAndUsage')

        with pytest.raises(ClientError):
            handler_utils.initialize_clients(config, 'test-session')

        # Verify error was logged
        assert 'Failed to initialize AWS clients' in caplog.text


def test_initialize_clients_error_with_role(caplog):
    """Test error handling when assume role fails."""
    config = {
        'management_account_role_arn': 'arn:aws:iam::123456789012:role/TestRole'
    }
    error_response = {'Error': {'Code': 'AccessDenied', 'Message': 'Not authorized'}}

    with patch('shared.handler_utils.get_clients') as mock_get_clients:
        mock_get_clients.side_effect = ClientError(error_response, 'AssumeRole')

        with pytest.raises(ClientError):
            handler_utils.initialize_clients(config, 'test-session')

        # Verify error message includes role ARN
        assert 'arn:aws:iam::123456789012:role/TestRole' in caplog.text
        assert 'Failed to assume role' in caplog.text


def test_initialize_clients_with_error_callback():
    """Test that error callback is called on failure."""
    config = {}
    error_response = {'Error': {'Code': 'AccessDenied', 'Message': 'Not authorized'}}
    error_callback = Mock()

    with patch('shared.handler_utils.get_clients') as mock_get_clients:
        mock_get_clients.side_effect = ClientError(error_response, 'GetCostAndUsage')

        with pytest.raises(ClientError):
            handler_utils.initialize_clients(config, 'test-session', error_callback)

        # Verify callback was called with error message
        error_callback.assert_called_once()
        assert 'Failed to initialize AWS clients' in error_callback.call_args[0][0]


def test_initialize_clients_callback_failure_logged(caplog):
    """Test that error callback failures are logged but don't prevent re-raise."""
    config = {}
    error_response = {'Error': {'Code': 'AccessDenied', 'Message': 'Not authorized'}}

    # Error callback that raises an exception
    def failing_callback(msg):
        raise Exception("Callback failed")

    with patch('shared.handler_utils.get_clients') as mock_get_clients:
        mock_get_clients.side_effect = ClientError(error_response, 'GetCostAndUsage')

        with pytest.raises(ClientError):
            handler_utils.initialize_clients(config, 'test-session', failing_callback)

        # Verify callback failure was logged
        assert 'Error callback failed' in caplog.text
        assert 'Callback failed' in caplog.text


# ============================================================================
# lambda_handler_wrapper Tests
# ============================================================================

def test_lambda_handler_wrapper_success(caplog):
    """Test decorator logs success correctly."""
    @handler_utils.lambda_handler_wrapper('TestLambda')
    def test_handler(event, context):
        return {'statusCode': 200, 'body': 'Success'}

    result = test_handler({}, None)

    assert result == {'statusCode': 200, 'body': 'Success'}
    assert 'Starting TestLambda Lambda execution' in caplog.text
    assert 'TestLambda Lambda completed successfully' in caplog.text


def test_lambda_handler_wrapper_handles_exception(caplog):
    """Test decorator logs and re-raises exceptions."""
    @handler_utils.lambda_handler_wrapper('TestLambda')
    def test_handler(event, context):
        raise ValueError("Test error")

    with pytest.raises(ValueError) as exc_info:
        test_handler({}, None)

    assert str(exc_info.value) == "Test error"
    assert 'Starting TestLambda Lambda execution' in caplog.text
    assert 'TestLambda Lambda failed' in caplog.text
    assert 'Test error' in caplog.text


def test_lambda_handler_wrapper_preserves_event_context():
    """Test decorator passes event and context correctly."""
    @handler_utils.lambda_handler_wrapper('TestLambda')
    def test_handler(event, context):
        return {'event': event, 'context': context}

    test_event = {'key': 'value'}
    test_context = Mock()

    result = test_handler(test_event, test_context)

    assert result['event'] == test_event
    assert result['context'] == test_context


def test_lambda_handler_wrapper_different_lambda_names(caplog):
    """Test decorator works with different Lambda names."""
    @handler_utils.lambda_handler_wrapper('Scheduler')
    def scheduler_handler(event, context):
        return {'statusCode': 200}

    @handler_utils.lambda_handler_wrapper('Purchaser')
    def purchaser_handler(event, context):
        return {'statusCode': 200}

    scheduler_handler({}, None)
    purchaser_handler({}, None)

    assert 'Starting Scheduler Lambda execution' in caplog.text
    assert 'Scheduler Lambda completed successfully' in caplog.text
    assert 'Starting Purchaser Lambda execution' in caplog.text
    assert 'Purchaser Lambda completed successfully' in caplog.text


def test_lambda_handler_wrapper_exception_traceback(caplog):
    """Test decorator logs full traceback on exception."""
    @handler_utils.lambda_handler_wrapper('TestLambda')
    def test_handler(event, context):
        # Raise exception with traceback
        try:
            raise RuntimeError("Inner error")
        except RuntimeError as e:
            raise ValueError("Outer error") from e

    # Enable DEBUG level to see traceback
    caplog.set_level('ERROR')

    with pytest.raises(ValueError):
        test_handler({}, None)

    # Verify error message is in logs
    assert 'TestLambda Lambda failed' in caplog.text
    assert 'Outer error' in caplog.text


# ============================================================================
# send_error_notification Tests
# ============================================================================

def test_send_error_notification_sns_only():
    """Test error notification with SNS only."""
    mock_sns = MagicMock()

    handler_utils.send_error_notification(
        sns_client=mock_sns,
        sns_topic_arn='arn:aws:sns:us-east-1:123:topic',
        error_message='Test error',
        lambda_name='TestLambda'
    )

    # Verify SNS publish was called
    mock_sns.publish.assert_called_once()
    call_args = mock_sns.publish.call_args

    assert call_args[1]['TopicArn'] == 'arn:aws:sns:us-east-1:123:topic'
    assert '[SP Autopilot] TestLambda Lambda Failed' in call_args[1]['Subject']
    assert 'Test error' in call_args[1]['Message']
    assert 'TestLambda Lambda Error' in call_args[1]['Message']


def test_send_error_notification_includes_timestamp():
    """Test that error notification includes timestamp."""
    mock_sns = MagicMock()

    with patch('shared.handler_utils.datetime') as mock_datetime:
        mock_datetime.now.return_value.isoformat.return_value = '2026-01-14T12:00:00+00:00'
        mock_datetime.now.return_value = datetime(2026, 1, 14, 12, 0, 0, tzinfo=timezone.utc)

        handler_utils.send_error_notification(
            sns_client=mock_sns,
            sns_topic_arn='arn:aws:sns:us-east-1:123:topic',
            error_message='Test error',
            lambda_name='TestLambda'
        )

        call_args = mock_sns.publish.call_args
        assert '2026-01-14T12:00:00+00:00' in call_args[1]['Message']


def test_send_error_notification_missing_topic_arn(caplog):
    """Test graceful handling when SNS topic ARN is missing."""
    mock_sns = MagicMock()

    handler_utils.send_error_notification(
        sns_client=mock_sns,
        sns_topic_arn='',
        error_message='Test error',
        lambda_name='TestLambda'
    )

    # Verify SNS publish was NOT called
    mock_sns.publish.assert_not_called()

    # Verify error was logged
    assert 'SNS_TOPIC_ARN not provided' in caplog.text


def test_send_error_notification_sns_failure(caplog):
    """Test graceful handling of SNS publish failure."""
    mock_sns = MagicMock()
    mock_sns.publish.side_effect = Exception("SNS error")

    # Should not raise - just log warning
    handler_utils.send_error_notification(
        sns_client=mock_sns,
        sns_topic_arn='arn:aws:sns:us-east-1:123:topic',
        error_message='Test error',
        lambda_name='TestLambda'
    )

    assert 'Failed to send SNS error notification' in caplog.text
    assert 'SNS error' in caplog.text


def test_send_error_notification_with_slack(caplog):
    """Test error notification with Slack webhook."""
    mock_sns = MagicMock()

    with patch('shared.handler_utils.notifications.format_slack_message') as mock_format, \
         patch('shared.handler_utils.notifications.send_slack_notification') as mock_send:

        mock_format.return_value = {'text': 'formatted message'}
        mock_send.return_value = True

        handler_utils.send_error_notification(
            sns_client=mock_sns,
            sns_topic_arn='arn:aws:sns:us-east-1:123:topic',
            error_message='Test error',
            lambda_name='TestLambda',
            slack_webhook_url='https://hooks.slack.com/services/test'
        )

        # Verify Slack functions were called
        mock_format.assert_called_once()
        mock_send.assert_called_once_with('https://hooks.slack.com/services/test', {'text': 'formatted message'})

        # Verify success was logged
        assert 'Slack error notification sent successfully' in caplog.text


def test_send_error_notification_slack_failure(caplog):
    """Test graceful handling of Slack notification failure."""
    mock_sns = MagicMock()

    with patch('shared.handler_utils.notifications.format_slack_message') as mock_format, \
         patch('shared.handler_utils.notifications.send_slack_notification') as mock_send:

        mock_format.return_value = {'text': 'formatted message'}
        mock_send.return_value = False

        handler_utils.send_error_notification(
            sns_client=mock_sns,
            sns_topic_arn='arn:aws:sns:us-east-1:123:topic',
            error_message='Test error',
            lambda_name='TestLambda',
            slack_webhook_url='https://hooks.slack.com/services/test'
        )

        # Verify failure was logged as warning
        assert 'Slack error notification failed' in caplog.text


def test_send_error_notification_slack_exception(caplog):
    """Test graceful handling of Slack exception."""
    mock_sns = MagicMock()

    with patch('shared.handler_utils.notifications.format_slack_message') as mock_format:
        mock_format.side_effect = Exception("Slack formatting error")

        handler_utils.send_error_notification(
            sns_client=mock_sns,
            sns_topic_arn='arn:aws:sns:us-east-1:123:topic',
            error_message='Test error',
            lambda_name='TestLambda',
            slack_webhook_url='https://hooks.slack.com/services/test'
        )

        # Verify exception was logged
        assert 'Failed to send Slack error notification' in caplog.text
        assert 'Slack formatting error' in caplog.text


def test_send_error_notification_with_teams(caplog):
    """Test error notification with Teams webhook."""
    mock_sns = MagicMock()

    with patch('shared.handler_utils.notifications.format_teams_message') as mock_format, \
         patch('shared.handler_utils.notifications.send_teams_notification') as mock_send:

        mock_format.return_value = {'text': 'formatted message'}
        mock_send.return_value = True

        handler_utils.send_error_notification(
            sns_client=mock_sns,
            sns_topic_arn='arn:aws:sns:us-east-1:123:topic',
            error_message='Test error',
            lambda_name='TestLambda',
            teams_webhook_url='https://outlook.office.com/webhook/test'
        )

        # Verify Teams functions were called
        mock_format.assert_called_once()
        mock_send.assert_called_once_with('https://outlook.office.com/webhook/test', {'text': 'formatted message'})

        # Verify success was logged
        assert 'Teams error notification sent successfully' in caplog.text


def test_send_error_notification_teams_failure(caplog):
    """Test graceful handling of Teams notification failure."""
    mock_sns = MagicMock()

    with patch('shared.handler_utils.notifications.format_teams_message') as mock_format, \
         patch('shared.handler_utils.notifications.send_teams_notification') as mock_send:

        mock_format.return_value = {'text': 'formatted message'}
        mock_send.return_value = False

        handler_utils.send_error_notification(
            sns_client=mock_sns,
            sns_topic_arn='arn:aws:sns:us-east-1:123:topic',
            error_message='Test error',
            lambda_name='TestLambda',
            teams_webhook_url='https://outlook.office.com/webhook/test'
        )

        # Verify failure was logged as warning
        assert 'Teams error notification failed' in caplog.text


def test_send_error_notification_teams_exception(caplog):
    """Test graceful handling of Teams exception."""
    mock_sns = MagicMock()

    with patch('shared.handler_utils.notifications.format_teams_message') as mock_format:
        mock_format.side_effect = Exception("Teams formatting error")

        handler_utils.send_error_notification(
            sns_client=mock_sns,
            sns_topic_arn='arn:aws:sns:us-east-1:123:topic',
            error_message='Test error',
            lambda_name='TestLambda',
            teams_webhook_url='https://outlook.office.com/webhook/test'
        )

        # Verify exception was logged
        assert 'Failed to send Teams error notification' in caplog.text
        assert 'Teams formatting error' in caplog.text


def test_send_error_notification_all_channels(caplog):
    """Test error notification with all channels (SNS, Slack, Teams)."""
    mock_sns = MagicMock()

    with patch('shared.handler_utils.notifications.format_slack_message') as mock_slack_format, \
         patch('shared.handler_utils.notifications.send_slack_notification') as mock_slack_send, \
         patch('shared.handler_utils.notifications.format_teams_message') as mock_teams_format, \
         patch('shared.handler_utils.notifications.send_teams_notification') as mock_teams_send:

        mock_slack_format.return_value = {'text': 'slack message'}
        mock_slack_send.return_value = True
        mock_teams_format.return_value = {'text': 'teams message'}
        mock_teams_send.return_value = True

        handler_utils.send_error_notification(
            sns_client=mock_sns,
            sns_topic_arn='arn:aws:sns:us-east-1:123:topic',
            error_message='Test error',
            lambda_name='TestLambda',
            slack_webhook_url='https://hooks.slack.com/services/test',
            teams_webhook_url='https://outlook.office.com/webhook/test'
        )

        # Verify all channels were called
        mock_sns.publish.assert_called_once()
        mock_slack_send.assert_called_once()
        mock_teams_send.assert_called_once()

        # Verify all successes were logged
        assert 'Error notification sent via SNS' in caplog.text
        assert 'Slack error notification sent successfully' in caplog.text
        assert 'Teams error notification sent successfully' in caplog.text


def test_send_error_notification_default_lambda_name():
    """Test that lambda_name defaults to 'Lambda' if not provided."""
    mock_sns = MagicMock()

    handler_utils.send_error_notification(
        sns_client=mock_sns,
        sns_topic_arn='arn:aws:sns:us-east-1:123:topic',
        error_message='Test error'
    )

    call_args = mock_sns.publish.call_args
    assert '[SP Autopilot] Lambda Lambda Failed' in call_args[1]['Subject']

"""
Unit tests for queue_manager module.

Tests queue purging and queuing purchase intents with various scenarios
including error handling and edge cases.
"""

import json
import os
import sys
from unittest.mock import Mock, patch

import pytest


# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import queue_manager


# ============================================================================
# Queue Purge Tests
# ============================================================================


@patch("shared.local_mode.is_local_mode", return_value=False)
def test_purge_queue_success(mock_local_mode):
    """Test successful queue purge."""
    mock_sqs_client = Mock()
    mock_sqs_client.purge_queue.return_value = {}

    queue_manager.purge_queue(mock_sqs_client, "test-queue-url")

    mock_sqs_client.purge_queue.assert_called_once_with(QueueUrl="test-queue-url")


@patch("shared.local_mode.is_local_mode", return_value=False)
def test_purge_queue_in_progress(mock_local_mode):
    """Test that PurgeQueueInProgress error is handled gracefully."""
    from botocore.exceptions import ClientError

    mock_sqs_client = Mock()
    error_response = {"Error": {"Code": "PurgeQueueInProgress"}}
    mock_sqs_client.purge_queue.side_effect = ClientError(error_response, "purge_queue")

    # Should not raise - just log warning
    queue_manager.purge_queue(mock_sqs_client, "test-queue-url")


@patch("shared.local_mode.is_local_mode", return_value=False)
def test_purge_queue_other_error(mock_local_mode):
    """Test that other errors are raised."""
    from botocore.exceptions import ClientError

    mock_sqs_client = Mock()
    error_response = {"Error": {"Code": "AccessDenied"}}
    mock_sqs_client.purge_queue.side_effect = ClientError(error_response, "purge_queue")

    with pytest.raises(ClientError):
        queue_manager.purge_queue(mock_sqs_client, "test-queue-url")


# ============================================================================
# Queue Tests
# ============================================================================


@patch("shared.local_mode.is_local_mode", return_value=False)
def test_queue_purchase_intents_sends_messages(mock_local_mode):
    """Test that purchase intents are sent to SQS."""
    mock_sqs_client = Mock()
    mock_sqs_client.send_message.return_value = {"MessageId": "msg-123"}

    config = {"queue_url": "test-queue-url", "tags": {"Environment": "test"}}

    plans = [
        {
            "sp_type": "compute",
            "term": "THREE_YEAR",
            "hourly_commitment": 2.5,
            "payment_option": "ALL_UPFRONT",
            "recommendation_id": "rec-123",
        }
    ]

    queue_manager.queue_purchase_intents(mock_sqs_client, config, plans)

    # Should send 1 message
    assert mock_sqs_client.send_message.call_count == 1
    call_args = mock_sqs_client.send_message.call_args[1]
    assert call_args["QueueUrl"] == "test-queue-url"

    # Verify message body
    message_body = json.loads(call_args["MessageBody"])
    assert message_body["sp_type"] == "compute"
    assert message_body["hourly_commitment"] == pytest.approx(2.5)


@patch("shared.local_mode.is_local_mode", return_value=False)
def test_queue_purchase_intents_client_token_unique(mock_local_mode):
    """Test that each message gets a unique client token."""
    mock_sqs_client = Mock()
    mock_sqs_client.send_message.return_value = {"MessageId": "msg-123"}

    config = {"queue_url": "test-queue-url", "tags": {}}

    plans = [
        {
            "sp_type": "compute",
            "term": "THREE_YEAR",
            "hourly_commitment": 1.0,
            "payment_option": "ALL_UPFRONT",
        },
        {
            "sp_type": "compute",
            "term": "ONE_YEAR",
            "hourly_commitment": 0.5,
            "payment_option": "ALL_UPFRONT",
        },
    ]

    queue_manager.queue_purchase_intents(mock_sqs_client, config, plans)

    # Extract client tokens from all calls
    tokens = []
    for call in mock_sqs_client.send_message.call_args_list:
        message_body = json.loads(call[1]["MessageBody"])
        tokens.append(message_body["client_token"])

    # All tokens should be unique
    assert len(tokens) == len(set(tokens))


@patch("shared.local_mode.is_local_mode", return_value=False)
def test_queue_purchase_intents_empty_list(mock_local_mode):
    """Test handling of empty purchase plans list."""
    mock_sqs_client = Mock()
    config = {"queue_url": "test-queue-url", "tags": {}}

    queue_manager.queue_purchase_intents(mock_sqs_client, config, [])

    # Should not send any messages
    assert mock_sqs_client.send_message.call_count == 0

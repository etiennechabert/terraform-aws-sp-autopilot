"""
Unit tests for queue manager module.

Tests queue purging and purchase intent queuing functionality.
"""

import json
import os
import sys
from datetime import datetime
from unittest.mock import Mock

import pytest


# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import queue_manager


@pytest.fixture
def mock_sqs_client():
    """Create a mock SQS client."""
    return Mock()


@pytest.fixture
def mock_config():
    """Create a mock configuration dictionary."""
    return {
        "queue_url": "https://sqs.us-east-1.amazonaws.com/123456789012/test-queue",
        "tags": {"Environment": "test", "Application": "autopilot"},
    }


# ============================================================================
# Purge Queue Tests
# ============================================================================


def test_purge_queue_success(mock_sqs_client):
    """Test successful queue purge."""
    mock_sqs_client.purge_queue.return_value = {}

    queue_manager.purge_queue(mock_sqs_client, "test-queue-url")

    mock_sqs_client.purge_queue.assert_called_once_with(QueueUrl="test-queue-url")


def test_purge_queue_in_progress(mock_sqs_client):
    """Test that PurgeQueueInProgress error is handled gracefully."""
    from botocore.exceptions import ClientError

    error_response = {"Error": {"Code": "PurgeQueueInProgress"}}
    mock_sqs_client.purge_queue.side_effect = ClientError(error_response, "purge_queue")

    # Should not raise - just log warning
    queue_manager.purge_queue(mock_sqs_client, "test-queue-url")

    mock_sqs_client.purge_queue.assert_called_once()


def test_purge_queue_other_error(mock_sqs_client):
    """Test that other errors are raised."""
    from botocore.exceptions import ClientError

    error_response = {"Error": {"Code": "AccessDenied"}}
    mock_sqs_client.purge_queue.side_effect = ClientError(error_response, "purge_queue")

    with pytest.raises(ClientError):
        queue_manager.purge_queue(mock_sqs_client, "test-queue-url")


def test_purge_queue_network_error(mock_sqs_client):
    """Test handling of network errors during purge."""
    from botocore.exceptions import ClientError

    error_response = {"Error": {"Code": "ServiceUnavailable"}}
    mock_sqs_client.purge_queue.side_effect = ClientError(error_response, "purge_queue")

    with pytest.raises(ClientError):
        queue_manager.purge_queue(mock_sqs_client, "test-queue-url")


# ============================================================================
# Queue Purchase Intents Tests
# ============================================================================


def test_queue_purchase_intents_single_plan(mock_sqs_client, mock_config):
    """Test queuing a single purchase intent."""
    mock_sqs_client.send_message.return_value = {"MessageId": "msg-12345"}

    purchase_plans = [
        {
            "sp_type": "compute",
            "term": "THREE_YEAR",
            "hourly_commitment": 5.50,
            "payment_option": "ALL_UPFRONT",
            "recommendation_id": "rec-12345",
        }
    ]

    queue_manager.queue_purchase_intents(mock_sqs_client, mock_config, purchase_plans)

    # Verify send_message was called once
    assert mock_sqs_client.send_message.call_count == 1

    # Verify the message content
    call_args = mock_sqs_client.send_message.call_args
    assert call_args[1]["QueueUrl"] == mock_config["queue_url"]

    # Parse and verify message body
    message_body = json.loads(call_args[1]["MessageBody"])
    assert message_body["sp_type"] == "compute"
    assert message_body["term"] == "THREE_YEAR"
    assert message_body["hourly_commitment"] == 5.50
    assert message_body["payment_option"] == "ALL_UPFRONT"
    assert message_body["recommendation_id"] == "rec-12345"
    assert "client_token" in message_body
    assert "queued_at" in message_body
    assert message_body["tags"] == mock_config["tags"]


def test_queue_purchase_intents_multiple_plans(mock_sqs_client, mock_config):
    """Test queuing multiple purchase intents."""
    mock_sqs_client.send_message.return_value = {"MessageId": "msg-12345"}

    purchase_plans = [
        {
            "sp_type": "compute",
            "term": "THREE_YEAR",
            "hourly_commitment": 5.50,
            "payment_option": "ALL_UPFRONT",
            "recommendation_id": "rec-compute-3y",
        },
        {
            "sp_type": "compute",
            "term": "ONE_YEAR",
            "hourly_commitment": 2.75,
            "payment_option": "ALL_UPFRONT",
            "recommendation_id": "rec-compute-1y",
        },
        {
            "sp_type": "database",
            "term": "ONE_YEAR",
            "hourly_commitment": 1.50,
            "payment_option": "NO_UPFRONT",
            "recommendation_id": "rec-database",
        },
    ]

    queue_manager.queue_purchase_intents(mock_sqs_client, mock_config, purchase_plans)

    # Verify send_message was called three times
    assert mock_sqs_client.send_message.call_count == 3


def test_queue_purchase_intents_no_plans(mock_sqs_client, mock_config):
    """Test queuing with no purchase plans."""
    purchase_plans = []

    queue_manager.queue_purchase_intents(mock_sqs_client, mock_config, purchase_plans)

    # Should not call send_message
    assert mock_sqs_client.send_message.call_count == 0


def test_queue_purchase_intents_client_token_uniqueness(mock_sqs_client, mock_config):
    """Test that each message gets a unique client token."""
    mock_sqs_client.send_message.return_value = {"MessageId": "msg-12345"}

    purchase_plans = [
        {
            "sp_type": "compute",
            "term": "THREE_YEAR",
            "hourly_commitment": 5.50,
            "payment_option": "ALL_UPFRONT",
            "recommendation_id": "rec-12345",
        },
        {
            "sp_type": "compute",
            "term": "ONE_YEAR",
            "hourly_commitment": 2.75,
            "payment_option": "ALL_UPFRONT",
            "recommendation_id": "rec-12345",
        },
    ]

    queue_manager.queue_purchase_intents(mock_sqs_client, mock_config, purchase_plans)

    # Extract client tokens from both messages
    call_1 = mock_sqs_client.send_message.call_args_list[0]
    call_2 = mock_sqs_client.send_message.call_args_list[1]

    message_1 = json.loads(call_1[1]["MessageBody"])
    message_2 = json.loads(call_2[1]["MessageBody"])

    # Client tokens should be different (different timestamps)
    assert message_1["client_token"] != message_2["client_token"]


def test_queue_purchase_intents_message_format(mock_sqs_client, mock_config):
    """Test that queued messages have all required fields."""
    mock_sqs_client.send_message.return_value = {"MessageId": "msg-12345"}

    purchase_plans = [
        {
            "sp_type": "sagemaker",
            "term": "THREE_YEAR",
            "hourly_commitment": 3.25,
            "payment_option": "NO_UPFRONT",
            "recommendation_id": "rec-sm-789",
        }
    ]

    queue_manager.queue_purchase_intents(mock_sqs_client, mock_config, purchase_plans)

    # Verify message format
    call_args = mock_sqs_client.send_message.call_args
    message_body = json.loads(call_args[1]["MessageBody"])

    # Check all required fields are present
    required_fields = [
        "client_token",
        "sp_type",
        "term",
        "hourly_commitment",
        "payment_option",
        "recommendation_id",
        "queued_at",
        "tags",
    ]

    for field in required_fields:
        assert field in message_body, f"Missing required field: {field}"


def test_queue_purchase_intents_missing_optional_fields(mock_sqs_client, mock_config):
    """Test queuing with missing optional fields in purchase plan."""
    mock_sqs_client.send_message.return_value = {"MessageId": "msg-12345"}

    # Plan with minimal fields
    purchase_plans = [
        {
            "sp_type": "compute"
            # Missing term, hourly_commitment, payment_option, recommendation_id
        }
    ]

    queue_manager.queue_purchase_intents(mock_sqs_client, mock_config, purchase_plans)

    # Should still queue with defaults
    call_args = mock_sqs_client.send_message.call_args
    message_body = json.loads(call_args[1]["MessageBody"])

    assert message_body["sp_type"] == "compute"
    assert message_body["term"] == "unknown"
    assert message_body["hourly_commitment"] == 0.0
    assert message_body["payment_option"] == "ALL_UPFRONT"
    assert message_body["recommendation_id"] == "unknown"


def test_queue_purchase_intents_tags_missing_in_config(mock_sqs_client):
    """Test queuing when tags are missing from config."""
    config = {
        "queue_url": "https://sqs.us-east-1.amazonaws.com/123456789012/test-queue"
        # Missing 'tags'
    }

    mock_sqs_client.send_message.return_value = {"MessageId": "msg-12345"}

    purchase_plans = [
        {
            "sp_type": "compute",
            "term": "THREE_YEAR",
            "hourly_commitment": 5.50,
            "payment_option": "ALL_UPFRONT",
            "recommendation_id": "rec-12345",
        }
    ]

    queue_manager.queue_purchase_intents(mock_sqs_client, config, purchase_plans)

    # Should queue with empty tags dict
    call_args = mock_sqs_client.send_message.call_args
    message_body = json.loads(call_args[1]["MessageBody"])

    assert message_body["tags"] == {}


def test_queue_purchase_intents_api_error(mock_sqs_client, mock_config):
    """Test error handling when SQS send_message fails."""
    from botocore.exceptions import ClientError

    error_response = {"Error": {"Code": "AccessDenied", "Message": "Access denied"}}
    mock_sqs_client.send_message.side_effect = ClientError(error_response, "send_message")

    purchase_plans = [
        {
            "sp_type": "compute",
            "term": "THREE_YEAR",
            "hourly_commitment": 5.50,
            "payment_option": "ALL_UPFRONT",
            "recommendation_id": "rec-12345",
        }
    ]

    with pytest.raises(ClientError):
        queue_manager.queue_purchase_intents(mock_sqs_client, mock_config, purchase_plans)


def test_queue_purchase_intents_partial_failure(mock_sqs_client, mock_config):
    """Test that error on second message stops processing."""
    from botocore.exceptions import ClientError

    # First message succeeds, second fails
    mock_sqs_client.send_message.side_effect = [
        {"MessageId": "msg-12345"},
        ClientError({"Error": {"Code": "ServiceUnavailable"}}, "send_message"),
    ]

    purchase_plans = [
        {
            "sp_type": "compute",
            "term": "THREE_YEAR",
            "hourly_commitment": 5.50,
            "payment_option": "ALL_UPFRONT",
            "recommendation_id": "rec-1",
        },
        {
            "sp_type": "database",
            "term": "ONE_YEAR",
            "hourly_commitment": 2.75,
            "payment_option": "NO_UPFRONT",
            "recommendation_id": "rec-2",
        },
    ]

    with pytest.raises(ClientError):
        queue_manager.queue_purchase_intents(mock_sqs_client, mock_config, purchase_plans)

    # First message should have been sent
    assert mock_sqs_client.send_message.call_count == 2


def test_queue_purchase_intents_timestamp_format(mock_sqs_client, mock_config):
    """Test that queued_at timestamp is in ISO format."""
    mock_sqs_client.send_message.return_value = {"MessageId": "msg-12345"}

    purchase_plans = [
        {
            "sp_type": "compute",
            "term": "THREE_YEAR",
            "hourly_commitment": 5.50,
            "payment_option": "ALL_UPFRONT",
            "recommendation_id": "rec-12345",
        }
    ]

    queue_manager.queue_purchase_intents(mock_sqs_client, mock_config, purchase_plans)

    call_args = mock_sqs_client.send_message.call_args
    message_body = json.loads(call_args[1]["MessageBody"])

    # Verify timestamp can be parsed
    timestamp = message_body["queued_at"]
    # Should not raise exception
    datetime.fromisoformat(timestamp.replace("Z", "+00:00"))


def test_queue_purchase_intents_preserves_plan_data(mock_sqs_client, mock_config):
    """Test that all plan data is preserved in the message."""
    mock_sqs_client.send_message.return_value = {"MessageId": "msg-12345"}

    purchase_plans = [
        {
            "sp_type": "sagemaker",
            "term": "ONE_YEAR",
            "hourly_commitment": 3.14159,  # Precise float
            "payment_option": "PARTIAL_UPFRONT",
            "recommendation_id": "rec-sm-999",
        }
    ]

    queue_manager.queue_purchase_intents(mock_sqs_client, mock_config, purchase_plans)

    call_args = mock_sqs_client.send_message.call_args
    message_body = json.loads(call_args[1]["MessageBody"])

    # Verify exact values are preserved
    assert message_body["sp_type"] == "sagemaker"
    assert message_body["term"] == "ONE_YEAR"
    assert message_body["hourly_commitment"] == 3.14159
    assert message_body["payment_option"] == "PARTIAL_UPFRONT"
    assert message_body["recommendation_id"] == "rec-sm-999"

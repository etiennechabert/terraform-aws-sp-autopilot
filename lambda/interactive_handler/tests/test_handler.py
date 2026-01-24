"""
Integration tests for Interactive Handler Lambda.

All tests follow TESTING.md guidelines:
- Test through handler.handler() entry point only
- Mock only AWS client responses
- Verify behavior through handler response and AWS calls
"""

import hashlib
import hmac
import json
import os
import sys
import time
import urllib.parse
from unittest.mock import Mock, patch

import pytest


sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from interactive_handler import handler


def compute_slack_signature(signing_secret: str, timestamp: str, body: str) -> str:
    """Helper to compute valid Slack signature for testing."""
    sig_basestring = f"v0:{timestamp}:{body}"
    signature = (
        "v0="
        + hmac.new(
            signing_secret.encode("utf-8"),
            sig_basestring.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
    )
    return signature


def create_slack_payload(action_id: str, purchase_intent_id: str, user_id: str = "U123ABC", user_name: str = "john.doe", team_id: str = "T123ABC") -> dict:
    """Helper to create Slack interactive payload."""
    return {
        "type": "block_actions",
        "user": {
            "id": user_id,
            "name": user_name,
            "username": user_name,
        },
        "team": {
            "id": team_id,
        },
        "actions": [
            {
                "action_id": action_id,
                "value": purchase_intent_id,
            }
        ],
        "channel": {
            "id": "C123ABC",
        },
        "message": {
            "ts": "1234567890.123456",
        },
        "response_url": "https://hooks.slack.com/actions/T123ABC/123456/abcdef",
    }


def create_api_gateway_event(body: str, signing_secret: str, timestamp: str = None) -> dict:
    """Helper to create API Gateway event with Slack signature."""
    if timestamp is None:
        timestamp = str(int(time.time()))

    signature = compute_slack_signature(signing_secret, timestamp, body)

    return {
        "body": body,
        "headers": {
            "x-slack-request-timestamp": timestamp,
            "x-slack-signature": signature,
        },
    }


@pytest.fixture
def mock_env_vars(monkeypatch):
    """Set up environment variables for testing."""
    monkeypatch.setenv("SLACK_SIGNING_SECRET", "test-signing-secret-12345")
    monkeypatch.setenv("QUEUE_URL", "https://sqs.us-east-1.amazonaws.com/123456789012/test-queue")


@pytest.fixture
def mock_sqs_client():
    """Mock SQS client."""
    with patch("interactive_handler.handler.boto3.client") as mock_boto:
        mock_sqs = Mock()
        mock_boto.return_value = mock_sqs
        yield mock_sqs


class TestHandlerApproveAction:
    """Tests for approve action handling."""

    def test_approve_action_succeeds(self, mock_env_vars, mock_sqs_client):
        """Test that approve action returns success response."""
        payload = create_slack_payload("approve_purchase", "sp-intent-12345")
        body = f"payload={urllib.parse.quote(json.dumps(payload))}"
        event = create_api_gateway_event(body, "test-signing-secret-12345")

        response = handler.handler(event, None)

        assert response["statusCode"] == 200
        body_data = json.loads(response["body"])
        assert "approved successfully" in body_data["text"]
        assert "john.doe" in body_data["text"]

        # Approve action should NOT interact with SQS
        assert not mock_sqs_client.receive_message.called
        assert not mock_sqs_client.delete_message.called

    def test_approve_action_logs_audit_trail(self, mock_env_vars, mock_sqs_client):
        """Test that approve action is logged for audit trail."""
        payload = create_slack_payload("approve_purchase", "sp-intent-12345", user_id="U456DEF", user_name="jane.smith")
        body = f"payload={urllib.parse.quote(json.dumps(payload))}"
        event = create_api_gateway_event(body, "test-signing-secret-12345")

        with patch("interactive_handler.handler.log_approval_action") as mock_log:
            response = handler.handler(event, None)

            assert response["statusCode"] == 200
            assert mock_log.called
            call_args = mock_log.call_args[1]
            assert call_args["action"] == "approve"
            assert call_args["user_id"] == "U456DEF"
            assert call_args["user_name"] == "jane.smith"
            assert call_args["purchase_intent_id"] == "sp-intent-12345"


class TestHandlerRejectAction:
    """Tests for reject action handling."""

    def test_reject_action_deletes_from_queue(self, mock_env_vars, mock_sqs_client):
        """Test that reject action deletes purchase intent from SQS queue."""
        payload = create_slack_payload("reject_purchase", "sp-intent-12345")
        body = f"payload={urllib.parse.quote(json.dumps(payload))}"
        event = create_api_gateway_event(body, "test-signing-secret-12345")

        # Mock SQS receive_message to return matching message
        mock_sqs_client.receive_message.return_value = {
            "Messages": [
                {
                    "Body": json.dumps({"client_token": "sp-intent-12345"}),
                    "ReceiptHandle": "receipt-handle-123",
                }
            ]
        }
        mock_sqs_client.delete_message.return_value = {}

        response = handler.handler(event, None)

        assert response["statusCode"] == 200
        body_data = json.loads(response["body"])
        assert "reject" in body_data["text"].lower()
        assert "successfully" in body_data["text"]

        # Verify SQS operations
        assert mock_sqs_client.receive_message.called
        assert mock_sqs_client.delete_message.called

        delete_call = mock_sqs_client.delete_message.call_args[1]
        assert delete_call["ReceiptHandle"] == "receipt-handle-123"

    def test_reject_action_searches_multiple_messages(self, mock_env_vars, mock_sqs_client):
        """Test that reject action searches through multiple SQS messages."""
        payload = create_slack_payload("reject_purchase", "sp-intent-99999")
        body = f"payload={urllib.parse.quote(json.dumps(payload))}"
        event = create_api_gateway_event(body, "test-signing-secret-12345")

        # Mock SQS to return multiple messages, with target in the middle
        mock_sqs_client.receive_message.return_value = {
            "Messages": [
                {
                    "Body": json.dumps({"client_token": "sp-intent-11111"}),
                    "ReceiptHandle": "receipt-handle-1",
                },
                {
                    "Body": json.dumps({"client_token": "sp-intent-99999"}),
                    "ReceiptHandle": "receipt-handle-2",
                },
                {
                    "Body": json.dumps({"client_token": "sp-intent-33333"}),
                    "ReceiptHandle": "receipt-handle-3",
                },
            ]
        }
        mock_sqs_client.delete_message.return_value = {}

        response = handler.handler(event, None)

        assert response["statusCode"] == 200

        # Should delete the correct message
        delete_call = mock_sqs_client.delete_message.call_args[1]
        assert delete_call["ReceiptHandle"] == "receipt-handle-2"

    def test_reject_action_message_not_found(self, mock_env_vars, mock_sqs_client):
        """Test reject action when purchase intent not found in queue (non-fatal)."""
        payload = create_slack_payload("reject_purchase", "sp-intent-not-found")
        body = f"payload={urllib.parse.quote(json.dumps(payload))}"
        event = create_api_gateway_event(body, "test-signing-secret-12345")

        # Mock SQS to return messages without matching intent
        mock_sqs_client.receive_message.return_value = {
            "Messages": [
                {
                    "Body": json.dumps({"client_token": "sp-intent-other"}),
                    "ReceiptHandle": "receipt-handle-1",
                }
            ]
        }

        response = handler.handler(event, None)

        # Should still return success (message might have already been processed)
        assert response["statusCode"] == 200
        assert not mock_sqs_client.delete_message.called

    def test_reject_action_logs_audit_trail(self, mock_env_vars, mock_sqs_client):
        """Test that reject action is logged for audit trail."""
        payload = create_slack_payload("reject_purchase", "sp-intent-12345")
        body = f"payload={urllib.parse.quote(json.dumps(payload))}"
        event = create_api_gateway_event(body, "test-signing-secret-12345")

        mock_sqs_client.receive_message.return_value = {
            "Messages": [
                {
                    "Body": json.dumps({"client_token": "sp-intent-12345"}),
                    "ReceiptHandle": "receipt-handle-123",
                }
            ]
        }
        mock_sqs_client.delete_message.return_value = {}

        with patch("interactive_handler.handler.log_approval_action") as mock_log:
            response = handler.handler(event, None)

            assert response["statusCode"] == 200
            assert mock_log.called
            call_args = mock_log.call_args[1]
            assert call_args["action"] == "reject"
            assert call_args["purchase_intent_id"] == "sp-intent-12345"


class TestHandlerSignatureVerification:
    """Tests for Slack signature verification."""

    def test_invalid_signature_returns_401(self, mock_env_vars, mock_sqs_client):
        """Test that invalid signature returns 401 Unauthorized."""
        payload = create_slack_payload("approve_purchase", "sp-intent-12345")
        body = f"payload={urllib.parse.quote(json.dumps(payload))}"

        # Create event with invalid signature
        event = {
            "body": body,
            "headers": {
                "x-slack-request-timestamp": str(int(time.time())),
                "x-slack-signature": "v0=invalid_signature_hash",
            },
        }

        response = handler.handler(event, None)

        assert response["statusCode"] == 401
        body_data = json.loads(response["body"])
        assert "error" in body_data
        assert "Unauthorized" in body_data["error"]

        # Should not process action
        assert not mock_sqs_client.receive_message.called

    def test_expired_timestamp_returns_401(self, mock_env_vars, mock_sqs_client):
        """Test that expired timestamp returns 401 Unauthorized."""
        payload = create_slack_payload("approve_purchase", "sp-intent-12345")
        body = f"payload={urllib.parse.quote(json.dumps(payload))}"

        # Create event with timestamp from 10 minutes ago
        old_timestamp = str(int(time.time()) - 600)
        event = create_api_gateway_event(body, "test-signing-secret-12345", old_timestamp)

        response = handler.handler(event, None)

        assert response["statusCode"] == 401
        body_data = json.loads(response["body"])
        assert "error" in body_data
        assert "Unauthorized" in body_data["error"]

    def test_missing_signature_headers_returns_401(self, mock_env_vars, mock_sqs_client):
        """Test that missing signature headers returns 401 Unauthorized."""
        payload = create_slack_payload("approve_purchase", "sp-intent-12345")
        body = f"payload={urllib.parse.quote(json.dumps(payload))}"

        # Create event without signature headers
        event = {
            "body": body,
            "headers": {},
        }

        response = handler.handler(event, None)

        assert response["statusCode"] == 401


class TestHandlerPayloadParsing:
    """Tests for payload parsing and validation."""

    def test_invalid_payload_format_returns_400(self, mock_env_vars, mock_sqs_client):
        """Test that invalid payload format returns 400 Bad Request."""
        # Invalid URL-encoded format - body without "payload=" prefix
        body = "invalid_key=value"
        event = create_api_gateway_event(body, "test-signing-secret-12345")

        response = handler.handler(event, None)

        assert response["statusCode"] == 400
        body_data = json.loads(response["body"])
        assert "error" in body_data
        # Could be either "Invalid payload format" or "No actions in payload"
        # Both are valid 400 responses for malformed input
        assert body_data["error"] in ["Invalid payload format", "No actions in payload"]

    def test_malformed_json_payload_returns_400(self, mock_env_vars, mock_sqs_client):
        """Test that malformed JSON payload returns 400 Bad Request."""
        # Valid URL encoding but invalid JSON
        body = f"payload={urllib.parse.quote('{invalid_json}')}"
        event = create_api_gateway_event(body, "test-signing-secret-12345")

        response = handler.handler(event, None)

        assert response["statusCode"] == 400
        body_data = json.loads(response["body"])
        assert "error" in body_data

    def test_missing_actions_returns_400(self, mock_env_vars, mock_sqs_client):
        """Test that payload with missing actions returns 400 Bad Request."""
        payload = {
            "type": "block_actions",
            "user": {"id": "U123", "name": "user"},
            "team": {"id": "T123"},
            # Missing 'actions' field
        }
        body = f"payload={urllib.parse.quote(json.dumps(payload))}"
        event = create_api_gateway_event(body, "test-signing-secret-12345")

        response = handler.handler(event, None)

        assert response["statusCode"] == 400
        body_data = json.loads(response["body"])
        assert "error" in body_data
        assert "No actions" in body_data["error"]

    def test_unknown_action_id_returns_400(self, mock_env_vars, mock_sqs_client):
        """Test that unknown action_id returns 400 Bad Request."""
        payload = create_slack_payload("unknown_action", "sp-intent-12345")
        body = f"payload={urllib.parse.quote(json.dumps(payload))}"
        event = create_api_gateway_event(body, "test-signing-secret-12345")

        response = handler.handler(event, None)

        assert response["statusCode"] == 400
        body_data = json.loads(response["body"])
        assert "error" in body_data
        assert "Unknown action" in body_data["error"]


class TestHandlerErrorHandling:
    """Tests for error handling scenarios."""

    def test_sqs_error_returns_500(self, mock_env_vars, mock_sqs_client):
        """Test that SQS errors during reject return 500 Internal Server Error."""
        payload = create_slack_payload("reject_purchase", "sp-intent-12345")
        body = f"payload={urllib.parse.quote(json.dumps(payload))}"
        event = create_api_gateway_event(body, "test-signing-secret-12345")

        # Mock SQS to raise an error
        mock_sqs_client.receive_message.side_effect = Exception("SQS connection failed")

        response = handler.handler(event, None)

        assert response["statusCode"] == 500
        body_data = json.loads(response["body"])
        assert "error" in body_data
        assert "Failed to process action" in body_data["error"]

    def test_sqs_error_logs_error_audit(self, mock_env_vars, mock_sqs_client):
        """Test that SQS errors are logged to audit trail."""
        payload = create_slack_payload("reject_purchase", "sp-intent-12345")
        body = f"payload={urllib.parse.quote(json.dumps(payload))}"
        event = create_api_gateway_event(body, "test-signing-secret-12345")

        mock_sqs_client.receive_message.side_effect = Exception("SQS error")

        with patch("interactive_handler.handler.log_action_error") as mock_log_error:
            response = handler.handler(event, None)

            assert response["statusCode"] == 500
            assert mock_log_error.called
            call_args = mock_log_error.call_args[1]
            assert call_args["action"] == "reject"
            assert "SQS error" in call_args["error_message"]

    def test_missing_user_info_uses_defaults(self, mock_env_vars, mock_sqs_client):
        """Test that missing user info uses default values."""
        payload = {
            "type": "block_actions",
            "user": {},  # Empty user object
            "team": {},  # Empty team object
            "actions": [
                {
                    "action_id": "approve_purchase",
                    "value": "sp-intent-12345",
                }
            ],
        }
        body = f"payload={urllib.parse.quote(json.dumps(payload))}"
        event = create_api_gateway_event(body, "test-signing-secret-12345")

        with patch("interactive_handler.handler.log_approval_action") as mock_log:
            response = handler.handler(event, None)

            assert response["statusCode"] == 200

            # Check defaults were used
            call_args = mock_log.call_args[1]
            assert call_args["user_id"] == "unknown"
            assert call_args["user_name"] == "unknown"
            assert call_args["team_id"] == "unknown"


class TestHandlerResponseFormat:
    """Tests for response format."""

    def test_approve_response_format(self, mock_env_vars, mock_sqs_client):
        """Test that approve response has correct format for Slack."""
        payload = create_slack_payload("approve_purchase", "sp-intent-12345", user_name="alice")
        body = f"payload={urllib.parse.quote(json.dumps(payload))}"
        event = create_api_gateway_event(body, "test-signing-secret-12345")

        response = handler.handler(event, None)

        assert response["statusCode"] == 200
        body_data = json.loads(response["body"])
        assert "response_type" in body_data
        assert body_data["response_type"] == "ephemeral"
        assert "text" in body_data
        assert "alice" in body_data["text"]
        assert "✅" in body_data["text"]

    def test_reject_response_format(self, mock_env_vars, mock_sqs_client):
        """Test that reject response has correct format for Slack."""
        payload = create_slack_payload("reject_purchase", "sp-intent-12345", user_name="bob")
        body = f"payload={urllib.parse.quote(json.dumps(payload))}"
        event = create_api_gateway_event(body, "test-signing-secret-12345")

        mock_sqs_client.receive_message.return_value = {
            "Messages": [
                {
                    "Body": json.dumps({"client_token": "sp-intent-12345"}),
                    "ReceiptHandle": "receipt-handle-123",
                }
            ]
        }
        mock_sqs_client.delete_message.return_value = {}

        response = handler.handler(event, None)

        assert response["statusCode"] == 200
        body_data = json.loads(response["body"])
        assert "response_type" in body_data
        assert body_data["response_type"] == "ephemeral"
        assert "text" in body_data
        assert "bob" in body_data["text"]
        assert "✅" in body_data["text"]

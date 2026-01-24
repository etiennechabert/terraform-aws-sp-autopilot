"""
Unit tests for Slack signature verification module.

Tests follow TESTING.md guidelines:
- Test public API functions directly
- Mock only time.time() for timestamp validation
- Use real cryptographic operations
"""

import hashlib
import hmac
import os
import sys
import time
from unittest.mock import patch

import pytest


sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from interactive_handler.slack_signature import (
    SignatureVerificationError,
    extract_signature_headers,
    verify_slack_signature,
)


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


class TestVerifySlackSignature:
    """Tests for verify_slack_signature function."""

    def test_valid_signature_succeeds(self):
        """Test that valid signature passes verification."""
        signing_secret = "test-secret-12345"
        timestamp = str(int(time.time()))
        body = '{"type":"block_actions","user":{"id":"U123"}}'
        signature = compute_slack_signature(signing_secret, timestamp, body)

        # Should not raise exception
        verify_slack_signature(signing_secret, timestamp, signature, body)

    def test_invalid_signature_fails(self):
        """Test that invalid signature raises SignatureVerificationError."""
        signing_secret = "test-secret-12345"
        timestamp = str(int(time.time()))
        body = '{"type":"block_actions"}'
        invalid_signature = "v0=invalid_signature_hash"

        with pytest.raises(SignatureVerificationError) as exc_info:
            verify_slack_signature(signing_secret, timestamp, invalid_signature, body)

        assert "Invalid signature" in str(exc_info.value)

    def test_wrong_signing_secret_fails(self):
        """Test that signature computed with wrong secret fails verification."""
        correct_secret = "correct-secret"
        wrong_secret = "wrong-secret"
        timestamp = str(int(time.time()))
        body = '{"type":"block_actions"}'
        signature = compute_slack_signature(wrong_secret, timestamp, body)

        with pytest.raises(SignatureVerificationError) as exc_info:
            verify_slack_signature(correct_secret, timestamp, signature, body)

        assert "Invalid signature" in str(exc_info.value)

    def test_expired_timestamp_fails(self):
        """Test that expired timestamp (>5 minutes old) fails verification."""
        signing_secret = "test-secret-12345"
        # Timestamp from 10 minutes ago
        old_timestamp = str(int(time.time()) - 600)
        body = '{"type":"block_actions"}'
        signature = compute_slack_signature(signing_secret, old_timestamp, body)

        with pytest.raises(SignatureVerificationError) as exc_info:
            verify_slack_signature(signing_secret, old_timestamp, signature, body)

        assert "timestamp too old" in str(exc_info.value).lower()

    def test_future_timestamp_fails(self):
        """Test that future timestamp (>5 minutes ahead) fails verification."""
        signing_secret = "test-secret-12345"
        # Timestamp from 10 minutes in the future
        future_timestamp = str(int(time.time()) + 600)
        body = '{"type":"block_actions"}'
        signature = compute_slack_signature(signing_secret, future_timestamp, body)

        with pytest.raises(SignatureVerificationError) as exc_info:
            verify_slack_signature(signing_secret, future_timestamp, signature, body)

        assert "timestamp too old" in str(exc_info.value).lower()

    def test_timestamp_within_window_succeeds(self):
        """Test that timestamp within 5 minute window succeeds."""
        signing_secret = "test-secret-12345"
        # Timestamp from 4 minutes ago (within window)
        timestamp = str(int(time.time()) - 240)
        body = '{"type":"block_actions"}'
        signature = compute_slack_signature(signing_secret, timestamp, body)

        # Should not raise exception
        verify_slack_signature(signing_secret, timestamp, signature, body)

    def test_missing_signing_secret_fails(self):
        """Test that missing signing secret raises SignatureVerificationError."""
        timestamp = str(int(time.time()))
        body = '{"type":"block_actions"}'
        signature = "v0=somehash"

        with pytest.raises(SignatureVerificationError) as exc_info:
            verify_slack_signature("", timestamp, signature, body)

        assert "Signing secret is required" in str(exc_info.value)

    def test_missing_timestamp_fails(self):
        """Test that missing timestamp raises SignatureVerificationError."""
        signing_secret = "test-secret-12345"
        body = '{"type":"block_actions"}'
        signature = "v0=somehash"

        with pytest.raises(SignatureVerificationError) as exc_info:
            verify_slack_signature(signing_secret, "", signature, body)

        assert "Missing X-Slack-Request-Timestamp" in str(exc_info.value)

    def test_missing_signature_fails(self):
        """Test that missing signature raises SignatureVerificationError."""
        signing_secret = "test-secret-12345"
        timestamp = str(int(time.time()))
        body = '{"type":"block_actions"}'

        with pytest.raises(SignatureVerificationError) as exc_info:
            verify_slack_signature(signing_secret, timestamp, "", body)

        assert "Missing X-Slack-Signature" in str(exc_info.value)

    def test_invalid_timestamp_format_fails(self):
        """Test that non-numeric timestamp raises SignatureVerificationError."""
        signing_secret = "test-secret-12345"
        invalid_timestamp = "not-a-number"
        body = '{"type":"block_actions"}'
        signature = "v0=somehash"

        with pytest.raises(SignatureVerificationError) as exc_info:
            verify_slack_signature(signing_secret, invalid_timestamp, signature, body)

        assert "Invalid timestamp format" in str(exc_info.value)

    def test_modified_body_fails_verification(self):
        """Test that modifying body after signature computation fails."""
        signing_secret = "test-secret-12345"
        timestamp = str(int(time.time()))
        original_body = '{"type":"block_actions"}'
        modified_body = '{"type":"block_actions","modified":true}'
        signature = compute_slack_signature(signing_secret, timestamp, original_body)

        with pytest.raises(SignatureVerificationError) as exc_info:
            verify_slack_signature(signing_secret, timestamp, signature, modified_body)

        assert "Invalid signature" in str(exc_info.value)


class TestExtractSignatureHeaders:
    """Tests for extract_signature_headers function."""

    def test_extract_headers_standard_case(self):
        """Test extracting headers with standard casing."""
        headers = {
            "X-Slack-Request-Timestamp": "1531420618",
            "X-Slack-Signature": "v0=a2114d57b48eac39b9ad189dd8316235a7b4a8d21a10bd27519666489c69b503",
        }

        timestamp, signature = extract_signature_headers(headers)

        assert timestamp == "1531420618"
        assert signature == "v0=a2114d57b48eac39b9ad189dd8316235a7b4a8d21a10bd27519666489c69b503"

    def test_extract_headers_lowercase(self):
        """Test extracting headers with lowercase (API Gateway style)."""
        headers = {
            "x-slack-request-timestamp": "1531420618",
            "x-slack-signature": "v0=a2114d57b48eac39b9ad189dd8316235a7b4a8d21a10bd27519666489c69b503",
        }

        timestamp, signature = extract_signature_headers(headers)

        assert timestamp == "1531420618"
        assert signature == "v0=a2114d57b48eac39b9ad189dd8316235a7b4a8d21a10bd27519666489c69b503"

    def test_extract_headers_mixed_case(self):
        """Test extracting headers with mixed casing."""
        headers = {
            "X-SLACK-REQUEST-TIMESTAMP": "1531420618",
            "x-SlAcK-sIgNaTuRe": "v0=a2114d57b48eac39b9ad189dd8316235a7b4a8d21a10bd27519666489c69b503",
        }

        timestamp, signature = extract_signature_headers(headers)

        assert timestamp == "1531420618"
        assert signature == "v0=a2114d57b48eac39b9ad189dd8316235a7b4a8d21a10bd27519666489c69b503"

    def test_missing_timestamp_header_fails(self):
        """Test that missing timestamp header raises SignatureVerificationError."""
        headers = {
            "x-slack-signature": "v0=a2114d57b48eac39b9ad189dd8316235a7b4a8d21a10bd27519666489c69b503"
        }

        with pytest.raises(SignatureVerificationError) as exc_info:
            extract_signature_headers(headers)

        assert "Missing required Slack signature headers" in str(exc_info.value)
        assert "X-Slack-Request-Timestamp" in str(exc_info.value)

    def test_missing_signature_header_fails(self):
        """Test that missing signature header raises SignatureVerificationError."""
        headers = {"x-slack-request-timestamp": "1531420618"}

        with pytest.raises(SignatureVerificationError) as exc_info:
            extract_signature_headers(headers)

        assert "Missing required Slack signature headers" in str(exc_info.value)
        assert "X-Slack-Signature" in str(exc_info.value)

    def test_missing_both_headers_fails(self):
        """Test that missing both headers raises SignatureVerificationError."""
        headers = {"Content-Type": "application/json"}

        with pytest.raises(SignatureVerificationError) as exc_info:
            extract_signature_headers(headers)

        assert "Missing required Slack signature headers" in str(exc_info.value)
        assert "X-Slack-Request-Timestamp" in str(exc_info.value)
        assert "X-Slack-Signature" in str(exc_info.value)

    def test_empty_headers_dict_fails(self):
        """Test that empty headers dict raises SignatureVerificationError."""
        headers = {}

        with pytest.raises(SignatureVerificationError) as exc_info:
            extract_signature_headers(headers)

        assert "Missing required Slack signature headers" in str(exc_info.value)

    def test_headers_with_extra_fields(self):
        """Test extracting headers from dict with additional fields."""
        headers = {
            "x-slack-request-timestamp": "1531420618",
            "x-slack-signature": "v0=hash123",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "Slackbot 1.0",
            "Host": "example.com",
        }

        timestamp, signature = extract_signature_headers(headers)

        assert timestamp == "1531420618"
        assert signature == "v0=hash123"

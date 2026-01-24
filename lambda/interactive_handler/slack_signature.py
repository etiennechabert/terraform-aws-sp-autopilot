"""
Slack signature verification module for interactive handler.

Implements HMAC SHA256 signature verification to authenticate incoming requests
from Slack. This is critical for security - rejecting requests with invalid
signatures prevents unauthorized access to the interactive endpoint.

Security Features:
    - HMAC SHA256 verification using X-Slack-Signature header
    - Timestamp validation to prevent replay attacks (5 minute window)
    - Constant-time comparison to prevent timing attacks

Reference:
    https://api.slack.com/authentication/verifying-requests-from-slack
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import time
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    pass


# Configure logging
logger = logging.getLogger(__name__)


class SignatureVerificationError(Exception):
    """Raised when Slack signature verification fails."""

    pass


def verify_slack_signature(
    signing_secret: str,
    timestamp: str,
    signature: str,
    body: str,
) -> None:
    """
    Verify Slack request signature using HMAC SHA256.

    This function implements Slack's signature verification protocol to ensure
    that incoming requests actually originate from Slack. It validates both the
    cryptographic signature and the request timestamp to prevent replay attacks.

    The verification process:
    1. Check timestamp is recent (within 5 minutes) to prevent replay attacks
    2. Construct basestring: "v0:{timestamp}:{body}"
    3. Compute HMAC SHA256 hash using signing secret as key
    4. Compare computed signature with provided signature (constant-time)

    Args:
        signing_secret: Slack app signing secret from environment
        timestamp: Request timestamp from X-Slack-Request-Timestamp header
        signature: Request signature from X-Slack-Signature header
        body: Raw request body string (must be exact bytes as received)

    Raises:
        SignatureVerificationError: If signature is invalid or timestamp is expired

    Examples:
        >>> # Valid signature
        >>> verify_slack_signature(
        ...     signing_secret="8f742231b10e8888abcd99yyyzzz85a5",
        ...     timestamp="1531420618",
        ...     signature="v0=a2114d57b48eac39b9ad189dd8316235a7b4a8d21a10bd27519666489c69b503",
        ...     body='{"type":"block_actions","user":{"id":"U123"}}'
        ... )
        # No exception raised

        >>> # Invalid signature
        >>> verify_slack_signature(
        ...     signing_secret="8f742231b10e8888abcd99yyyzzz85a5",
        ...     timestamp="1531420618",
        ...     signature="v0=invalid_signature",
        ...     body='{"type":"block_actions"}'
        ... )
        Traceback (most recent call last):
        ...
        SignatureVerificationError: Invalid signature

        >>> # Expired timestamp (more than 5 minutes old)
        >>> verify_slack_signature(
        ...     signing_secret="secret",
        ...     timestamp="1000000000",  # Very old timestamp
        ...     signature="v0=...",
        ...     body="{}"
        ... )
        Traceback (most recent call last):
        ...
        SignatureVerificationError: Request timestamp too old

    Security Notes:
        - Uses constant-time comparison (hmac.compare_digest) to prevent timing attacks
        - Validates timestamp within 5 minute window to prevent replay attacks
        - Requires exact raw body bytes - any modification invalidates signature
        - Signing secret must never be logged or exposed in error messages
    """
    # Validate inputs
    if not signing_secret:
        raise SignatureVerificationError("Signing secret is required")

    if not timestamp:
        raise SignatureVerificationError("Missing X-Slack-Request-Timestamp header")

    if not signature:
        raise SignatureVerificationError("Missing X-Slack-Signature header")

    # Validate timestamp format
    try:
        request_timestamp = int(timestamp)
    except (ValueError, TypeError) as e:
        logger.warning(f"Invalid timestamp format: {timestamp}")
        raise SignatureVerificationError("Invalid timestamp format") from e

    # Check timestamp is recent (within 5 minutes) to prevent replay attacks
    current_timestamp = int(time.time())
    time_diff = abs(current_timestamp - request_timestamp)

    if time_diff > 60 * 5:  # 5 minutes
        logger.warning(
            f"Request timestamp too old: {time_diff}s difference "
            f"(max 300s allowed)"
        )
        raise SignatureVerificationError(
            "Request timestamp too old - possible replay attack"
        )

    # Construct the basestring for signature verification
    # Format: v0:{timestamp}:{body}
    sig_basestring = f"v0:{timestamp}:{body}"

    # Compute HMAC SHA256 hash using signing secret
    computed_signature = (
        "v0="
        + hmac.new(
            signing_secret.encode("utf-8"),
            sig_basestring.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
    )

    # Use constant-time comparison to prevent timing attacks
    if not hmac.compare_digest(computed_signature, signature):
        logger.warning("Signature verification failed - invalid signature")
        raise SignatureVerificationError("Invalid signature")

    logger.debug("Signature verification successful")


def extract_signature_headers(headers: dict[str, str]) -> tuple[str, str]:
    """
    Extract Slack signature headers from request headers.

    This helper function extracts the required signature validation headers
    from the incoming request headers. It handles case-insensitive header
    lookups as HTTP headers are case-insensitive per RFC 2616.

    Args:
        headers: Request headers dictionary (may have various casings)

    Returns:
        tuple: (timestamp, signature) extracted from headers

    Raises:
        SignatureVerificationError: If required headers are missing

    Examples:
        >>> # Standard casing
        >>> extract_signature_headers({
        ...     'X-Slack-Request-Timestamp': '1531420618',
        ...     'X-Slack-Signature': 'v0=a2114d57b48...'
        ... })
        ('1531420618', 'v0=a2114d57b48...')

        >>> # Lowercase headers (as from API Gateway)
        >>> extract_signature_headers({
        ...     'x-slack-request-timestamp': '1531420618',
        ...     'x-slack-signature': 'v0=a2114d57b48...'
        ... })
        ('1531420618', 'v0=a2114d57b48...')

        >>> # Missing headers
        >>> extract_signature_headers({'Content-Type': 'application/json'})
        Traceback (most recent call last):
        ...
        SignatureVerificationError: Missing required Slack signature headers

    Note:
        API Gateway may normalize header names to lowercase, so this function
        performs case-insensitive lookups to handle all variations.
    """
    # Create case-insensitive header lookup
    headers_lower = {k.lower(): v for k, v in headers.items()}

    # Extract headers (case-insensitive)
    timestamp = headers_lower.get("x-slack-request-timestamp")
    signature = headers_lower.get("x-slack-signature")

    # Validate both headers are present
    if not timestamp or not signature:
        missing = []
        if not timestamp:
            missing.append("X-Slack-Request-Timestamp")
        if not signature:
            missing.append("X-Slack-Signature")

        logger.warning(f"Missing required Slack headers: {', '.join(missing)}")
        raise SignatureVerificationError(
            f"Missing required Slack signature headers: {', '.join(missing)}"
        )

    return timestamp, signature

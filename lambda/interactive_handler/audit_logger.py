"""
Audit logging module for Slack interactive actions.

Provides structured audit logging for approval actions (approve/reject) with
full user attribution. Logs are written to CloudWatch in JSON format for
easy querying and compliance reporting.

This module is critical for accountability - every approval action must be
logged with complete user attribution and context for audit trail purposes.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    pass


# Configure logging
logger = logging.getLogger(__name__)


def log_approval_action(
    action: str,
    user_id: str,
    user_name: str,
    purchase_intent_id: str,
    team_id: str,
    additional_context: dict[str, Any] | None = None,
) -> None:
    """
    Log an approval action with full user attribution to CloudWatch.

    Creates a structured JSON log entry in CloudWatch containing all relevant
    information about an approval action. This provides a complete audit trail
    for compliance and accountability purposes.

    The log entry includes:
    - Action taken (approve/reject)
    - User who performed the action (ID and name)
    - Purchase intent being acted upon
    - Slack team/workspace context
    - Precise timestamp (ISO 8601 UTC)
    - Optional additional context

    Args:
        action: The action taken - must be 'approve' or 'reject'
        user_id: Slack user ID who performed the action (e.g., 'U123ABC')
        user_name: Slack username for human readability (e.g., 'john.doe')
        purchase_intent_id: ID of the purchase intent being acted upon
        team_id: Slack team/workspace ID (e.g., 'T123ABC')
        additional_context: Optional dictionary of additional context to log
                            (e.g., response_url, channel_id, message_ts)

    Raises:
        ValueError: If action is not 'approve' or 'reject'

    Examples:
        >>> # Log approval action
        >>> log_approval_action(
        ...     action='approve',
        ...     user_id='U123ABC',
        ...     user_name='john.doe',
        ...     purchase_intent_id='sp-intent-12345',
        ...     team_id='T123ABC'
        ... )
        # Logs: {"event": "approval_action", "action": "approve", ...}

        >>> # Log rejection with additional context
        >>> log_approval_action(
        ...     action='reject',
        ...     user_id='U456DEF',
        ...     user_name='jane.smith',
        ...     purchase_intent_id='sp-intent-67890',
        ...     team_id='T123ABC',
        ...     additional_context={'reason': 'budget_exceeded', 'channel_id': 'C789'}
        ... )
        # Logs: {"event": "approval_action", "action": "reject", ...}

        >>> # Invalid action raises ValueError
        >>> log_approval_action(
        ...     action='modify',
        ...     user_id='U123ABC',
        ...     user_name='john.doe',
        ...     purchase_intent_id='sp-intent-12345',
        ...     team_id='T123ABC'
        ... )
        Traceback (most recent call last):
        ...
        ValueError: Invalid action 'modify' - must be 'approve' or 'reject'

    Logging Format:
        Logs are written as JSON for easy CloudWatch Insights querying:
        {
            "event": "approval_action",
            "action": "approve|reject",
            "user_id": "U123ABC",
            "user_name": "john.doe",
            "purchase_intent_id": "sp-intent-12345",
            "team_id": "T123ABC",
            "timestamp": "2024-01-24T12:34:56.789Z",
            "additional_context": {...}  // if provided
        }

    CloudWatch Insights Query Examples:
        # Find all rejections
        fields @timestamp, user_name, purchase_intent_id
        | filter event = 'approval_action' and action = 'reject'
        | sort @timestamp desc

        # Count actions by user
        fields user_name
        | filter event = 'approval_action'
        | stats count() by user_name

        # Find actions for specific purchase intent
        fields @timestamp, action, user_name
        | filter purchase_intent_id = 'sp-intent-12345'
        | sort @timestamp desc
    """
    # Validate action
    valid_actions = {"approve", "reject"}
    if action not in valid_actions:
        raise ValueError(
            f"Invalid action '{action}' - must be 'approve' or 'reject'"
        )

    # Build structured log entry
    log_entry = {
        "event": "approval_action",
        "action": action,
        "user_id": user_id,
        "user_name": user_name,
        "purchase_intent_id": purchase_intent_id,
        "team_id": team_id,
        "timestamp": datetime.now(UTC).isoformat(),
    }

    # Add additional context if provided
    if additional_context:
        log_entry["additional_context"] = additional_context

    # Log as JSON for structured logging
    logger.info(json.dumps(log_entry))

    # Also log a human-readable message at debug level
    logger.debug(
        f"Approval action logged: {action} by {user_name} ({user_id}) "
        f"for purchase {purchase_intent_id} in team {team_id}"
    )


def log_action_error(
    action: str,
    user_id: str,
    user_name: str,
    purchase_intent_id: str,
    team_id: str,
    error_message: str,
    error_type: str | None = None,
) -> None:
    """
    Log an error that occurred during an approval action.

    Creates a structured JSON log entry for errors that occur during approval
    action processing. This helps with troubleshooting and identifying patterns
    in failures.

    Args:
        action: The action being attempted ('approve' or 'reject')
        user_id: Slack user ID who attempted the action
        user_name: Slack username for human readability
        purchase_intent_id: ID of the purchase intent being acted upon
        team_id: Slack team/workspace ID
        error_message: Description of the error that occurred
        error_type: Optional error type/category (e.g., 'sqs_error', 'timeout')

    Examples:
        >>> # Log SQS deletion error during reject
        >>> log_action_error(
        ...     action='reject',
        ...     user_id='U123ABC',
        ...     user_name='john.doe',
        ...     purchase_intent_id='sp-intent-12345',
        ...     team_id='T123ABC',
        ...     error_message='Failed to delete SQS message: QueueDoesNotExist',
        ...     error_type='sqs_error'
        ... )
        # Logs: {"event": "approval_action_error", ...}

    Logging Format:
        {
            "event": "approval_action_error",
            "action": "approve|reject",
            "user_id": "U123ABC",
            "user_name": "john.doe",
            "purchase_intent_id": "sp-intent-12345",
            "team_id": "T123ABC",
            "error_message": "Failed to delete SQS message",
            "error_type": "sqs_error",  // if provided
            "timestamp": "2024-01-24T12:34:56.789Z"
        }

    CloudWatch Insights Query Examples:
        # Find all errors
        fields @timestamp, action, user_name, error_message
        | filter event = 'approval_action_error'
        | sort @timestamp desc

        # Count errors by type
        fields error_type
        | filter event = 'approval_action_error'
        | stats count() by error_type
    """
    # Build structured error log entry
    log_entry = {
        "event": "approval_action_error",
        "action": action,
        "user_id": user_id,
        "user_name": user_name,
        "purchase_intent_id": purchase_intent_id,
        "team_id": team_id,
        "error_message": error_message,
        "timestamp": datetime.now(UTC).isoformat(),
    }

    # Add error type if provided
    if error_type:
        log_entry["error_type"] = error_type

    # Log as JSON for structured logging
    logger.error(json.dumps(log_entry))

    # Also log a human-readable message at debug level
    logger.debug(
        f"Approval action error: {action} by {user_name} ({user_id}) "
        f"for purchase {purchase_intent_id} failed: {error_message}"
    )

"""
Interactive Handler Lambda - Processes Slack button clicks for approval actions.

This Lambda handles Slack interactive component requests (button clicks) to
approve or reject pending Savings Plan purchases. It provides a user-friendly
way to interact with the purchase queue without accessing AWS Console.

Flow:
1. Receive POST request from Slack via API Gateway
2. Verify Slack signature to authenticate request
3. Parse interactive payload (URL-encoded JSON)
4. Extract action (approve/reject) and user information
5. If reject: Delete purchase intent from SQS queue
6. Log action with full user attribution to CloudWatch
7. Return 200 OK to Slack (must respond within 3 seconds)

Security:
- HMAC SHA256 signature verification prevents unauthorized access
- Timestamp validation prevents replay attacks
- All actions logged with user attribution for audit trail
"""

from __future__ import annotations

import json
import logging
import urllib.parse
from typing import TYPE_CHECKING, Any

import boto3

from .audit_logger import log_action_error, log_approval_action
from .config import load_configuration
from .slack_signature import (
    SignatureVerificationError,
    extract_signature_headers,
    verify_slack_signature,
)

from shared.handler_utils import lambda_handler_wrapper
from shared.queue_adapter import QueueAdapter


if TYPE_CHECKING:
    pass


# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)


@lambda_handler_wrapper("InteractiveHandler")
def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """
    Main handler for Slack interactive component requests.

    Processes button clicks from Slack for approve/reject actions on pending
    Savings Plan purchases. This function must respond within 3 seconds to
    avoid Slack timeout.

    Args:
        event: API Gateway event containing Slack interactive payload
        context: Lambda context

    Returns:
        dict: HTTP response with statusCode and body

    Raises:
        Exception: Raised on signature verification failure or processing errors
    """
    try:
        # Load configuration
        config = load_configuration()

        # Extract request body and headers from API Gateway event
        body = event.get("body", "")
        headers = event.get("headers", {})

        # Verify Slack signature (security-critical step)
        try:
            timestamp, signature = extract_signature_headers(headers)
            verify_slack_signature(
                signing_secret=config["slack_signing_secret"],
                timestamp=timestamp,
                signature=signature,
                body=body,
            )
        except SignatureVerificationError as e:
            logger.warning(f"Signature verification failed: {e}")
            return {
                "statusCode": 401,
                "body": json.dumps({"error": "Unauthorized"}),
            }

        # Parse URL-encoded payload
        # Slack sends interactive payloads as form data: payload={json}
        try:
            parsed_body = urllib.parse.parse_qs(body)
            payload_json = parsed_body.get("payload", ["{}"])[0]
            payload = json.loads(payload_json)
        except (ValueError, KeyError, json.JSONDecodeError) as e:
            logger.error(f"Failed to parse payload: {e}")
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "Invalid payload format"}),
            }

        # Extract user information and action from payload
        user = payload.get("user", {})
        user_id = user.get("id", "unknown")
        user_name = user.get("name", user.get("username", "unknown"))
        team_id = payload.get("team", {}).get("id", "unknown")

        # Extract action from actions array
        actions = payload.get("actions", [])
        if not actions:
            logger.error("No actions found in payload")
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "No actions in payload"}),
            }

        action_data = actions[0]
        action_id = action_data.get("action_id", "")
        purchase_intent_id = action_data.get("value", "")

        # Determine action type (approve or reject)
        if action_id == "approve_purchase":
            action = "approve"
        elif action_id == "reject_purchase":
            action = "reject"
        else:
            logger.error(f"Unknown action_id: {action_id}")
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "Unknown action"}),
            }

        logger.info(
            f"Processing {action} action by {user_name} ({user_id}) "
            f"for purchase intent {purchase_intent_id}"
        )

        # Initialize SQS client for queue operations
        sqs_client = boto3.client("sqs")

        # Process the action
        try:
            if action == "reject":
                # Delete purchase intent from queue
                process_reject_action(
                    sqs_client=sqs_client,
                    queue_url=config["queue_url"],
                    purchase_intent_id=purchase_intent_id,
                    user_id=user_id,
                    user_name=user_name,
                    team_id=team_id,
                )
            else:
                # Approve action - just log it (purchase will proceed automatically)
                logger.info(
                    f"Approve action acknowledged for purchase {purchase_intent_id}. "
                    "Purchase will proceed as scheduled."
                )

            # Log the approval action to CloudWatch for audit trail
            log_approval_action(
                action=action,
                user_id=user_id,
                user_name=user_name,
                purchase_intent_id=purchase_intent_id,
                team_id=team_id,
                additional_context={
                    "channel_id": payload.get("channel", {}).get("id"),
                    "response_url": payload.get("response_url"),
                    "message_ts": payload.get("message", {}).get("ts"),
                },
            )

        except Exception as e:
            # Log error with full context
            error_msg = f"Failed to process {action} action: {e!s}"
            logger.error(error_msg, exc_info=True)

            log_action_error(
                action=action,
                user_id=user_id,
                user_name=user_name,
                purchase_intent_id=purchase_intent_id,
                team_id=team_id,
                error_message=str(e),
                error_type=type(e).__name__,
            )

            # Return error response to Slack
            return {
                "statusCode": 500,
                "body": json.dumps({"error": "Failed to process action"}),
            }

        # Return success response to Slack
        # Must respond within 3 seconds to avoid timeout
        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "response_type": "ephemeral",
                    "text": f"✅ Purchase {action}d successfully by {user_name}",
                }
            ),
        }

    except Exception as e:
        logger.error(f"Interactive handler failed: {e!s}", exc_info=True)
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Internal server error"}),
        }


def process_reject_action(
    sqs_client: Any,
    queue_url: str,
    purchase_intent_id: str,
    user_id: str,
    user_name: str,
    team_id: str,
) -> None:
    """
    Process a reject action by deleting the purchase intent from SQS queue.

    This function searches the SQS queue for the message containing the
    purchase intent with the given ID and deletes it to prevent the purchase
    from being executed by the Purchaser Lambda.

    Args:
        sqs_client: Boto3 SQS client
        queue_url: SQS queue URL
        purchase_intent_id: Purchase intent client_token to reject
        user_id: Slack user ID performing the rejection
        user_name: Slack username for logging
        team_id: Slack team ID

    Raises:
        Exception: If queue operations fail
    """
    logger.info(f"Processing reject action for purchase intent {purchase_intent_id}")

    try:
        # Initialize queue adapter
        queue_adapter = QueueAdapter(sqs_client=sqs_client, queue_url=queue_url)

        # Receive messages from queue to find the matching purchase intent
        # We may need to check multiple messages to find the right one
        messages = queue_adapter.receive_messages(max_messages=10)

        # Search for the message containing the purchase intent
        message_found = False
        for message in messages:
            try:
                message_body = json.loads(message["Body"])
                client_token = message_body.get("client_token", "")

                if client_token == purchase_intent_id:
                    # Found the matching message - delete it
                    receipt_handle = message["ReceiptHandle"]
                    queue_adapter.delete_message(receipt_handle)

                    logger.info(
                        f"Deleted purchase intent {purchase_intent_id} from queue "
                        f"(rejected by {user_name})"
                    )
                    message_found = True
                    break

            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"Failed to parse message body: {e}")
                continue

        if not message_found:
            logger.warning(
                f"Purchase intent {purchase_intent_id} not found in queue. "
                "It may have already been processed or deleted."
            )
            # Don't raise error - this is not fatal (message might already be gone)

    except Exception as e:
        error_msg = f"Failed to delete purchase intent from queue: {e!s}"
        logger.error(error_msg, exc_info=True)

        # Log error to audit trail
        log_action_error(
            action="reject",
            user_id=user_id,
            user_name=user_name,
            purchase_intent_id=purchase_intent_id,
            team_id=team_id,
            error_message=error_msg,
            error_type="sqs_error",
        )

        raise

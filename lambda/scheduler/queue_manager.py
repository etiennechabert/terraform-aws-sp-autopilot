"""
Queue Manager - SQS operations for Scheduler Lambda.

Handles purging the queue and queuing purchase intents.
Supports both AWS SQS and local filesystem modes.
"""

from __future__ import annotations

import logging

# Import queue adapter for local/AWS mode support
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from botocore.exceptions import ClientError


if TYPE_CHECKING:
    from mypy_boto3_sqs.client import SQSClient

from shared.queue_adapter import QueueAdapter


# Configure logging
logger = logging.getLogger()


def purge_queue(sqs_client: SQSClient, queue_url: str) -> None:
    """
    Purge all existing messages from the queue.
    Supports both AWS SQS and local filesystem modes.

    Args:
        sqs_client: Boto3 SQS client (not used in local mode)
        queue_url: SQS queue URL (not used in local mode)
    """
    logger.info(f"Purging queue: {queue_url}")
    try:
        queue_adapter = QueueAdapter(sqs_client=sqs_client, queue_url=queue_url)
        queue_adapter.purge_queue()
        logger.info("Queue purged successfully")
    except ClientError as e:
        if e.response["Error"]["Code"] == "PurgeQueueInProgress":
            logger.warning("Queue purge already in progress")
        else:
            raise


def queue_purchase_intents(
    sqs_client: SQSClient, config: dict[str, Any], purchase_plans: list[dict[str, Any]]
) -> None:
    """
    Queue purchase intents to queue.
    Supports both AWS SQS and local filesystem modes.

    Args:
        sqs_client: Boto3 SQS client (not used in local mode)
        config: Configuration dictionary
        purchase_plans: List of planned purchases
    """
    logger.info(f"Queuing {len(purchase_plans)} purchase intents")

    if not purchase_plans:
        logger.info("No purchase plans to queue")
        return

    queue_url = config["queue_url"]
    queue_adapter = QueueAdapter(sqs_client=sqs_client, queue_url=queue_url)
    queued_count = 0

    for plan in purchase_plans:
        try:
            # Generate unique client token for idempotency
            timestamp = datetime.now(UTC).isoformat()
            sp_type = plan.get("sp_type", "unknown")
            term = plan.get("term", "unknown")
            commitment = plan.get("hourly_commitment", 0.0)
            client_token = f"scheduler-{sp_type}-{term}-{timestamp}"

            # Add client_token to the plan for use in notifications
            plan["client_token"] = client_token

            # Create purchase intent message
            purchase_intent = {
                "client_token": client_token,
                "sp_type": sp_type,
                "term": term,
                "hourly_commitment": commitment,
                "payment_option": plan.get("payment_option", "ALL_UPFRONT"),
                "recommendation_id": plan.get("recommendation_id", "unknown"),
                "queued_at": timestamp,
                "tags": config.get("tags", {}),
            }

            # Send message via adapter
            message_id = queue_adapter.send_message(purchase_intent)

            logger.info(
                f"Queued purchase intent: {sp_type} {term} ${commitment:.4f}/hour "
                f"(message_id: {message_id}, client_token: {client_token})"
            )
            queued_count += 1

        except ClientError as e:
            logger.error(f"Failed to queue purchase intent: {e!s}")
            raise

    logger.info(f"All {queued_count} purchase intents queued successfully")

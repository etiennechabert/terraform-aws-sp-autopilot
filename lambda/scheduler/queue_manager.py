"""
Queue Manager - SQS operations for Scheduler Lambda.

Handles purging the queue and queuing purchase intents.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

from botocore.exceptions import ClientError


# Configure logging
logger = logging.getLogger()


def purge_queue(sqs_client: Any, queue_url: str) -> None:
    """
    Purge all existing messages from the SQS queue.

    Args:
        sqs_client: Boto3 SQS client
        queue_url: SQS queue URL
    """
    logger.info(f"Purging queue: {queue_url}")
    try:
        sqs_client.purge_queue(QueueUrl=queue_url)
        logger.info("Queue purged successfully")
    except ClientError as e:
        if e.response["Error"]["Code"] == "PurgeQueueInProgress":
            logger.warning("Queue purge already in progress")
        else:
            raise


def queue_purchase_intents(
    sqs_client: Any, config: Dict[str, Any], purchase_plans: List[Dict[str, Any]]
) -> None:
    """
    Queue purchase intents to SQS.

    Args:
        sqs_client: Boto3 SQS client
        config: Configuration dictionary
        purchase_plans: List of planned purchases
    """
    logger.info(f"Queuing {len(purchase_plans)} purchase intents")

    if not purchase_plans:
        logger.info("No purchase plans to queue")
        return

    queue_url = config["queue_url"]
    queued_count = 0

    for plan in purchase_plans:
        try:
            # Generate unique client token for idempotency
            timestamp = datetime.now(timezone.utc).isoformat()
            sp_type = plan.get("sp_type", "unknown")
            term = plan.get("term", "unknown")
            commitment = plan.get("hourly_commitment", 0.0)
            client_token = f"scheduler-{sp_type}-{term}-{timestamp}"

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

            # Send message to SQS
            response = sqs_client.send_message(
                QueueUrl=queue_url, MessageBody=json.dumps(purchase_intent)
            )

            message_id = response.get("MessageId")
            logger.info(
                f"Queued purchase intent: {sp_type} {term} ${commitment:.4f}/hour "
                f"(message_id: {message_id}, client_token: {client_token})"
            )
            queued_count += 1

        except ClientError as e:
            logger.error(f"Failed to queue purchase intent: {e!s}")
            raise

    logger.info(f"All {queued_count} purchase intents queued successfully")

"""Purchaser Lambda entry point.

Orchestrates the purchase pipeline:
1. Pull queued intents from SQS.
2. Run guards (spike, cooldown) and drop messages that should not be purchased.
3. Compute post-guard current coverage (excluding expiring plans).
4. Execute each remaining purchase and aggregate results.
5. Send an SNS summary email.

Low-level work lives in coverage_calc.py, guards.py, and purchase_execution.py.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

import boto3
from botocore.exceptions import ClientError
from coverage_calc import get_current_coverage
from guards import apply_purchase_cooldown, apply_spike_guard
from purchase_execution import process_purchase_messages, send_summary_email

from shared import handler_utils
from shared.queue_adapter import QueueAdapter


if TYPE_CHECKING:
    from mypy_boto3_sqs.client import SQSClient


logger = logging.getLogger()
logger.setLevel(logging.INFO)


def load_configuration() -> dict[str, Any]:
    from config import load_configuration as config_load

    return config_load()


@handler_utils.lambda_handler_wrapper("Purchaser")
def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Purchaser Lambda entry point."""
    try:
        config = load_configuration()

        def send_error_email(error_msg: str) -> None:
            handler_utils.send_error_notification(
                sns_client=boto3.client("sns"),
                sns_topic_arn=config["sns_topic_arn"],
                error_message=error_msg,
                lambda_name="Purchaser",
                slack_webhook_url=config.get("slack_webhook_url"),
                teams_webhook_url=config.get("teams_webhook_url"),
            )

        clients = handler_utils.initialize_clients(
            config,
            session_name="sp-autopilot-purchaser",
            error_callback=send_error_email,
        )

        messages = _receive_messages(clients["sqs"], config["queue_url"])
        if not messages:
            logger.info("Queue is empty - exiting silently")
            return _ok("No purchases to process", executed=0)

        logger.info(f"Found {len(messages)} purchase intents in queue")

        if config["spike_guard_enabled"]:
            messages = apply_spike_guard(clients, config, messages)
            if not messages:
                logger.info("All messages blocked by spike guard - exiting")
                return _ok("All purchases blocked by spike guard", executed=0)

        cooldown_days = config["purchase_cooldown_days"]
        if cooldown_days > 0:
            messages = apply_purchase_cooldown(clients, config, messages, cooldown_days)
            if not messages:
                logger.info("All messages blocked by purchase cooldown - exiting")
                return _ok("All purchases blocked by cooldown", executed=0)

        coverage = get_current_coverage(clients, config)
        logger.info(
            f"Current coverage - Compute: {coverage.get('compute', 0)}%, "
            f"Database: {coverage.get('database', 0)}%, "
            f"SageMaker: {coverage.get('sagemaker', 0)}%"
        )

        results = process_purchase_messages(clients, config, messages)
        send_summary_email(clients["sns"], config, results, coverage)

        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "message": "Purchaser completed successfully",
                    "purchases_executed": results["successful_count"],
                    "purchases_skipped": results["skipped_count"],
                }
            ),
        }

    except Exception as e:
        # Best-effort notification; swallow failures so the raise still surfaces.
        try:
            config = load_configuration()
            handler_utils.send_error_notification(
                sns_client=boto3.client("sns"),
                sns_topic_arn=config["sns_topic_arn"],
                error_message=str(e),
                lambda_name="Purchaser",
                slack_webhook_url=config.get("slack_webhook_url"),
                teams_webhook_url=config.get("teams_webhook_url"),
            )
        except Exception as notification_error:
            logger.warning(f"Failed to send error notification: {notification_error}")
        raise


def _receive_messages(
    sqs_client: SQSClient, queue_url: str, max_messages: int = 10
) -> list[dict[str, Any]]:
    logger.info(f"Receiving messages from queue: {queue_url}")
    try:
        messages = QueueAdapter(sqs_client=sqs_client, queue_url=queue_url).receive_messages(
            max_messages=max_messages
        )
    except ClientError as e:
        logger.error(f"Failed to receive messages: {e!s}")
        raise
    logger.info(f"Received {len(messages)} messages from queue")
    return messages


def _ok(message: str, *, executed: int) -> dict[str, Any]:
    return {
        "statusCode": 200,
        "body": json.dumps({"message": message, "purchases_executed": executed}),
    }

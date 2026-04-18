"""Purchase-time guards: cooldown + spike guard.

Both guards filter queued SQS messages before they're processed:
- Cooldown: skip if a plan of the same SP type was bought within N days.
- Spike guard: skip if usage dropped since scheduling (the spike was temporary).

Blocked messages are deleted from the queue and a notification is published.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from botocore.exceptions import ClientError

from shared import constants
from shared.queue_adapter import QueueAdapter


if TYPE_CHECKING:
    from mypy_boto3_sns.client import SNSClient


logger = logging.getLogger(__name__)


def apply_purchase_cooldown(
    clients: dict[str, Any],
    config: dict[str, Any],
    messages: list[dict[str, Any]],
    cooldown_days: int,
) -> list[dict[str, Any]]:
    """Drop messages for SP types purchased within cooldown_days."""
    from shared.savings_plans_metrics import get_recent_purchase_sp_types

    cooldown_types = get_recent_purchase_sp_types(clients["savingsplans"], cooldown_days)
    if not cooldown_types:
        return messages

    processable, blocked = _partition_by_sp_type(messages, cooldown_types)
    if not blocked:
        return messages

    _consume_blocked(clients["sqs"], config["queue_url"], blocked)
    logger.warning(
        f"Deleted {len(blocked)} message(s) blocked by cooldown: {sorted(cooldown_types)}"
    )
    _send_cooldown_notification(clients["sns"], config, blocked, cooldown_types, cooldown_days)
    return processable


def apply_spike_guard(
    clients: dict[str, Any],
    config: dict[str, Any],
    messages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Drop messages when usage fell below scheduling-time baseline.

    The scheduler stamps the 14-day average hourly spend into each message.
    Compare against the current 14-day average; a drop confirms the earlier
    spike was transient, so those purchases should be cancelled.
    """
    first_body = json.loads(messages[0]["Body"])
    scheduling_avgs = first_body.get("scheduling_avg_hourly_total")
    if not scheduling_avgs:
        logger.info("No scheduling_avg_hourly_total in message — skipping purchasing spike guard")
        return messages

    from shared.spending_analyzer import SpendingAnalyzer
    from shared.usage_decline_check import run_purchasing_spike_guard

    analyzer = SpendingAnalyzer(clients["savingsplans"], clients["ce"])
    guard_results = run_purchasing_spike_guard(analyzer, scheduling_avgs, config)

    flagged_types = {t for t, r in guard_results.items() if r["flagged"]}
    if not flagged_types:
        return messages

    processable, blocked = _partition_by_sp_type(messages, flagged_types)
    _consume_blocked(clients["sqs"], config["queue_url"], blocked)
    logger.warning(f"Deleted {len(blocked)} blocked message(s) from queue: {flagged_types}")
    _send_spike_guard_notification(clients["sns"], config, blocked, guard_results)
    return processable


def _partition_by_sp_type(
    messages: list[dict[str, Any]], flagged: set[str]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    processable, blocked = [], []
    for msg in messages:
        body = json.loads(msg["Body"])
        sp_key = constants.SP_FILTER_TO_KEY.get(body.get("sp_type", ""), body.get("sp_type", ""))
        (blocked if sp_key in flagged else processable).append(msg)
    return processable, blocked


def _consume_blocked(sqs_client: Any, queue_url: str, blocked: list[dict[str, Any]]) -> None:
    queue_adapter = QueueAdapter(sqs_client=sqs_client, queue_url=queue_url)
    for msg in blocked:
        queue_adapter.delete_message(msg["ReceiptHandle"])


def _send_cooldown_notification(
    sns_client: SNSClient,
    config: dict[str, Any],
    blocked: list[dict[str, Any]],
    cooldown_types: set[str],
    cooldown_days: int,
) -> None:
    lines = [
        "⏳  PURCHASE COOLDOWN — Purchases Blocked at Purchase Time",
        "=" * 60,
        "",
        f"{len(blocked)} purchase intent(s) were blocked and removed from the queue.",
        f"A Savings Plan of the same type was purchased within the last {cooldown_days} days.",
        "This prevents double-purchasing while Cost Explorer data settles.",
        "",
        f"SP Types in Cooldown: {', '.join(sorted(t.upper() for t in cooldown_types))}",
        "",
        "Blocked Purchase Intents:",
        "-" * 50,
    ]
    for i, msg in enumerate(blocked, 1):
        body = json.loads(msg["Body"])
        lines.append(
            f"  {i}. {body.get('sp_type', 'unknown')} — "
            f"${float(body.get('commitment', 0)):.5f}/hour"
        )
    lines.extend(
        [
            "",
            "These messages have been consumed from the queue.",
            "The scheduler will re-evaluate on its next run.",
        ]
    )

    try:
        sns_client.publish(
            TopicArn=config["sns_topic_arn"],
            Subject="SP Autopilot — Purchases Blocked at Purchase Time (Cooldown)",
            Message="\n".join(lines),
        )
        logger.info("Cooldown notification sent")
    except ClientError as e:
        logger.error(f"Failed to send cooldown notification: {e!s}")
        raise


def _send_spike_guard_notification(
    sns_client: SNSClient,
    config: dict[str, Any],
    blocked: list[dict[str, Any]],
    guard_results: dict[str, dict[str, Any]],
) -> None:
    flagged_types = {json.loads(msg["Body"]).get("sp_type", "unknown") for msg in blocked}

    lines = [
        "⚠️  USAGE DROP SINCE SCHEDULING — Purchases Blocked",
        "=" * 60,
        "",
        f"{len(blocked)} purchase intent(s) were blocked and removed from the queue.",
        "Usage dropped between scheduling and purchase time, confirming the spike was temporary.",
        "",
        "Drop Details:",
        "-" * 50,
    ]
    for sp_type in sorted(flagged_types):
        result = guard_results.get(sp_type, {})
        lines.extend(
            [
                f"  {sp_type.upper()} Savings Plan:",
                f"    Scheduling-time avg: ${result.get('baseline_avg', 0):.4f}/hour",
                f"    Current avg: ${result.get('current_avg', 0):.4f}/hour",
                f"    Drop: -{result.get('change_percent', 0):.1f}%",
                "",
            ]
        )
    lines.extend(["Blocked Purchase Intents:", "-" * 50])
    for i, msg in enumerate(blocked, 1):
        body = json.loads(msg["Body"])
        lines.append(
            f"  {i}. {body.get('sp_type', 'unknown')} — "
            f"${float(body.get('commitment', 0)):.5f}/hour"
        )
    lines.extend(
        [
            "",
            "These messages have been consumed from the queue.",
            "The scheduler will re-evaluate on its next run.",
            "",
            "To adjust sensitivity, modify spike_guard settings in your Terraform configuration:",
            "  purchase_strategy.spike_guard.threshold_percent (currently "
            f"{config['spike_guard_threshold_percent']}%)",
            "  purchase_strategy.spike_guard.enabled = false  (to disable entirely)",
        ]
    )

    try:
        sns_client.publish(
            TopicArn=config["sns_topic_arn"],
            Subject="SP Autopilot — Purchases Blocked at Purchase Time (Usage Drop)",
            Message="\n".join(lines),
        )
        logger.info("Usage guard notification sent")
    except ClientError as e:
        logger.error(f"Failed to send spike guard notification: {e!s}")
        raise

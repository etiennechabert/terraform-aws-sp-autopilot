"""
Scheduler Lambda - Analyzes usage and queues Savings Plan purchase intents.

Supports Compute, Database, and SageMaker Savings Plans.

This Lambda:
1. Purges existing queue messages
2. Calculates current coverage (excluding plans expiring within renewal_window_days)
3. Gets AWS purchase recommendations
4. Calculates purchase need based on selected target + split strategy
5. Applies purchase limits (min_commitment_per_plan)
6. Queues purchase intents to SQS
7. Sends notification email with analysis results
"""

from __future__ import annotations

import json
import logging
from typing import Any, cast

# Import new modular components
import email_notifications as email_module
import purchase_calculator as purchase_module
import queue_manager as queue_module
from config import CONFIG_SCHEMA

from shared.config_validation import validate_scheduler_config
from shared.handler_utils import (
    initialize_clients,
    lambda_handler_wrapper,
    load_config_from_env,
    send_error_notification,
)
from shared.spending_analyzer import SpendingAnalyzer


logger = logging.getLogger()


@lambda_handler_wrapper("Scheduler")
def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """
    Scheduler Lambda - Analyzes usage and queues Savings Plan purchase intents.

    Flow:
    1. Load and validate configuration
    2. Initialize AWS clients
    3. Purge existing queue
    4. Analyze current coverage
    5. Get AWS recommendations
    6. Calculate purchases using strategy
    7. Queue purchases and send notification
    """
    config = load_config_from_env(CONFIG_SCHEMA, validator=validate_scheduler_config)

    clients = initialize_clients(
        config,
        "sp-autopilot-scheduler",
        lambda msg: _send_error_notification(config["sns_topic_arn"], msg),
    )

    # Check per-type purchase cooldown
    cooldown_days = config["purchase_cooldown_days"]
    cooldown_types: set[str] = set()
    if cooldown_days > 0:
        from shared.savings_plans_metrics import get_recent_purchase_sp_types

        cooldown_types = get_recent_purchase_sp_types(clients["savingsplans"], cooldown_days)

        # If ALL enabled types are in cooldown, skip the entire run
        enabled_types: set[str] = set()
        if config["enable_compute_sp"]:
            enabled_types.add("compute")
        if config["enable_database_sp"]:
            enabled_types.add("database")
        if config["enable_sagemaker_sp"]:
            enabled_types.add("sagemaker")

        if enabled_types <= cooldown_types:
            msg = (
                f"All enabled SP types {sorted(enabled_types)} purchased within "
                f"last {cooldown_days} days — skipping scheduling to let "
                "Cost Explorer data settle"
            )
            logger.warning(msg)
            clients["sns"].publish(
                TopicArn=config["sns_topic_arn"],
                Subject="SP Autopilot Scheduler — Skipped (cooldown)",
                Message=msg,
            )
            return {
                "statusCode": 200,
                "body": json.dumps(
                    {
                        "message": "Skipped — all enabled types within cooldown window",
                        "purchases_planned": 0,
                    }
                ),
            }

    queue_module.purge_queue(clients["sqs"], config["queue_url"])

    # Run spike guard (detect usage spikes before purchase calculation)
    analyzer = SpendingAnalyzer(clients["savingsplans"], clients["ce"])
    short_term_averages = None
    guard_results = None
    if config["spike_guard_enabled"]:
        from shared.usage_decline_check import run_scheduling_spike_guard

        short_term_averages, guard_results = run_scheduling_spike_guard(analyzer, config)

    # Conditionally analyze spending based on target strategy
    # - aws target doesn't need spending analysis (uses AWS recommendations only)
    # - fixed/dynamic targets need spending analysis for purchase calculations
    target_strategy = config["target_strategy_type"]

    if target_strategy != "aws":
        spending_data = analyzer.analyze_current_spending(config)

        # Extract coverage (as % of min-hourly) and unknown services for email notifications
        unknown_services = cast(list[str], spending_data.pop("_unknown_services", []))
        coverage = {}
        for sp_type, data in spending_data.items():
            summary = data["summary"]
            avg_cov = summary["avg_coverage_total"]
            avg_total = summary["avg_hourly_total"]
            ts = data.get("timeseries", [])
            costs = [i["total"] for i in ts if i["total"] > 0]
            min_h = min(costs) if costs else avg_total
            ratio = avg_total / min_h if min_h > 0 and avg_total > 0 else 1.0
            coverage[sp_type] = avg_cov * ratio
    else:
        # aws target strategy - no spending analysis needed
        spending_data = None
        unknown_services = None
        coverage = None

    # Calculate purchases using selected strategy (strategies handle their own limits)
    purchase_plans = purchase_module.calculate_purchase_need(config, clients, spending_data)

    # Filter out purchase plans for SP types in cooldown
    cooldown_blocked_plans = []
    if cooldown_types:
        cooldown_blocked_plans = [p for p in purchase_plans if p.get("sp_type") in cooldown_types]
        purchase_plans = [p for p in purchase_plans if p.get("sp_type") not in cooldown_types]
        if cooldown_blocked_plans:
            logger.warning(
                f"Blocked {len(cooldown_blocked_plans)} purchase plan(s) due to cooldown: "
                f"{sorted(cooldown_types)}"
            )

    # Filter out purchase plans for SP types with usage spikes
    blocked_plans = []
    if guard_results:
        flagged_types = {t for t, r in guard_results.items() if r["flagged"]}
        if flagged_types:
            blocked_plans = [p for p in purchase_plans if p.get("sp_type") in flagged_types]
            purchase_plans = [p for p in purchase_plans if p.get("sp_type") not in flagged_types]
            logger.warning(
                f"Blocked {len(blocked_plans)} purchase plan(s) due to usage spike: {flagged_types}"
            )

    queue_module.queue_purchase_intents(
        clients["sqs"],
        config,
        purchase_plans,
        short_term_averages,
        savingsplans_client=clients["savingsplans"],
    )
    email_module.send_scheduled_email(
        clients["sns"],
        config,
        purchase_plans,
        coverage,
        unknown_services if unknown_services else None,
    )

    if cooldown_blocked_plans:
        email_module.send_cooldown_email(
            clients["sns"], config, cooldown_blocked_plans, cooldown_types
        )

    if blocked_plans:
        email_module.send_spike_guard_email(clients["sns"], config, blocked_plans, guard_results)

    return {
        "statusCode": 200,
        "body": json.dumps(
            {
                "message": "Scheduler completed successfully",
                "purchases_planned": len(purchase_plans),
                "purchases_blocked_by_cooldown": len(cooldown_blocked_plans),
                "purchases_blocked_by_spike_guard": len(blocked_plans),
            }
        ),
    }


def _send_error_notification(sns_topic_arn: str, error_msg: str) -> None:
    """Send error notification via SNS."""
    import boto3

    send_error_notification(
        sns_client=boto3.client("sns"),
        sns_topic_arn=sns_topic_arn,
        error_message=error_msg,
        lambda_name="Scheduler",
    )


if __name__ == "__main__":
    handler({}, None)

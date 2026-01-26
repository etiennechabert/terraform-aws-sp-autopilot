"""
Scheduler Lambda - Analyzes usage and queues Savings Plan purchase intents.

Supports Compute, Database, and SageMaker Savings Plans.

This Lambda:
1. Purges existing queue messages
2. Calculates current coverage (excluding plans expiring within renewal_window_days)
3. Gets AWS purchase recommendations
4. Calculates purchase need based on coverage_target_percent and selected strategy
5. Applies purchase limits (max_purchase_percent, min_commitment_per_plan)
6. Queues purchase intents (or sends email only if dry_run=true)
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
    7. Queue purchases or send dry-run notification
    """
    config = load_config_from_env(CONFIG_SCHEMA, validator=validate_scheduler_config)

    clients = initialize_clients(
        config,
        "sp-autopilot-scheduler",
        lambda msg: _send_error_notification(config["sns_topic_arn"], msg),
    )

    queue_module.purge_queue(clients["sqs"], config["queue_url"])

    # Conditionally analyze spending based on strategy
    # - fixed/dichotomy strategies need spending analysis for purchase calculations
    # - follow_aws strategy doesn't need it (uses AWS recommendations only)
    strategy_type = config["purchase_strategy_type"]

    if strategy_type in ["fixed", "dichotomy"]:
        analyzer = SpendingAnalyzer(clients["savingsplans"], clients["ce"])
        spending_data = analyzer.analyze_current_spending(config)

        # Extract coverage and unknown services for email notifications
        unknown_services = cast(list[str], spending_data.pop("_unknown_services", []))
        coverage = {
            sp_type: data["summary"]["avg_coverage_total"]
            for sp_type, data in spending_data.items()
        }
    else:
        # follow_aws strategy - no spending analysis needed
        spending_data = None
        unknown_services = None
        coverage = None

    # Calculate purchases using selected strategy (strategies handle their own limits)
    purchase_plans = purchase_module.calculate_purchase_need(config, clients, spending_data)

    if config["dry_run"]:
        email_module.send_dry_run_email(
            clients["sns"],
            config,
            purchase_plans,
            coverage,
            unknown_services if unknown_services else None,
        )
    else:
        queue_module.queue_purchase_intents(clients["sqs"], config, purchase_plans)
        email_module.send_scheduled_email(
            clients["sns"],
            config,
            purchase_plans,
            coverage,
            unknown_services if unknown_services else None,
        )

    return {
        "statusCode": 200,
        "body": json.dumps(
            {
                "message": "Scheduler completed successfully",
                "dry_run": config["dry_run"],
                "purchases_planned": len(purchase_plans),
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

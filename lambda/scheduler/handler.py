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
from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    from mypy_boto3_ce.client import CostExplorerClient
    from mypy_boto3_savingsplans.client import SavingsPlansClient
    from mypy_boto3_sns.client import SNSClient
    from mypy_boto3_sqs.client import SQSClient

# Import new modular components
import email_notifications as email_module
import purchase_calculator as purchase_module
import queue_manager as queue_module
import recommendations as recommendations_module
from config import CONFIG_SCHEMA

from shared.config_validation import validate_scheduler_config
from shared.handler_utils import (
    initialize_clients,
    lambda_handler_wrapper,
    load_config_from_env,
    send_error_notification,
)
from shared.spending_analyzer import SpendingAnalyzer


# Configure logging
logger = logging.getLogger()

# Module-level boto3 clients for backward compatibility with existing tests
# These are initialized to None and tests can assign mock objects to them
# The wrapper functions below will use these if set, otherwise create real clients
ce_client: CostExplorerClient | None = None
sqs_client: SQSClient | None = None
sns_client: SNSClient | None = None
savingsplans_client: SavingsPlansClient | None = None


def _ensure_ce_client() -> CostExplorerClient:
    """Get Cost Explorer client, creating it if needed."""
    global ce_client
    if ce_client is None:
        import boto3

        ce_client = boto3.client("ce")
    return ce_client


def _ensure_sqs_client() -> SQSClient:
    """Get SQS client, creating it if needed."""
    global sqs_client
    if sqs_client is None:
        import boto3

        sqs_client = boto3.client("sqs")
    return sqs_client


def _ensure_sns_client() -> SNSClient:
    """Get SNS client, creating it if needed."""
    global sns_client
    if sns_client is None:
        import boto3

        sns_client = boto3.client("sns")
    return sns_client


def _ensure_savingsplans_client() -> SavingsPlansClient:
    """Get Savings Plans client, creating it if needed."""
    global savingsplans_client
    if savingsplans_client is None:
        import boto3

        savingsplans_client = boto3.client("savingsplans")
    return savingsplans_client


# Backward-compatible wrapper functions for existing tests
# These match the old function signatures and use lazily-initialized clients
def load_configuration() -> dict[str, Any]:
    """Load configuration - backward compatible wrapper."""
    from config import load_configuration as config_load

    return config_load()


def calculate_current_coverage(config: dict[str, Any]) -> dict[str, float]:
    """Calculate current coverage - backward compatible wrapper."""
    analyzer = SpendingAnalyzer(_ensure_savingsplans_client(), _ensure_ce_client())
    spending_data = analyzer.analyze_current_spending(config)
    return {
        sp_type: data["summary"]["avg_coverage"]
        for sp_type, data in spending_data.items()
    }


def get_aws_recommendations(config: dict[str, Any]) -> dict[str, Any]:
    """Get AWS recommendations - backward compatible wrapper."""
    return recommendations_module.get_aws_recommendations(_ensure_ce_client(), config)


def get_assumed_role_session(role_arn: str, session_name: str = "sp-autopilot-session"):
    """Get assumed role session - backward compatible wrapper."""
    from shared.aws_utils import get_assumed_role_session as aws_assume_role

    return aws_assume_role(role_arn, session_name)


def get_clients(config: dict[str, Any]):
    """Get clients - backward compatible wrapper."""
    from shared.aws_utils import get_clients as aws_get_clients

    return aws_get_clients(config)


def purge_queue(queue_url: str) -> None:
    """Purge queue - backward compatible wrapper."""
    return queue_module.purge_queue(_ensure_sqs_client(), queue_url)


def queue_purchase_intents(config: dict[str, Any], purchase_plans: list) -> None:
    """Queue purchase intents - backward compatible wrapper."""
    return queue_module.queue_purchase_intents(_ensure_sqs_client(), config, purchase_plans)


def send_scheduled_email(
    config: dict[str, Any], purchase_plans: list, coverage_data: dict[str, float]
) -> None:
    """Send scheduled email - backward compatible wrapper."""
    return email_module.send_scheduled_email(
        _ensure_sns_client(), config, purchase_plans, coverage_data
    )


def send_dry_run_email(
    config: dict[str, Any], purchase_plans: list, coverage_data: dict[str, float]
) -> None:
    """Send dry run email - backward compatible wrapper."""
    return email_module.send_dry_run_email(
        _ensure_sns_client(), config, purchase_plans, coverage_data
    )


# Re-export these functions directly as they don't need client parameters
calculate_purchase_need = purchase_module.calculate_purchase_need
apply_purchase_limits = purchase_module.apply_purchase_limits


# Backward-compatible imports for configuration and AWS utils


def send_error_email(error_msg: str, sns_topic_arn: str = None) -> None:
    """
    Send error notification email - backward compatible wrapper.

    This function provides backward compatibility for tests that expect
    send_error_email at module level.

    Args:
        error_msg: Error message to send
        sns_topic_arn: SNS topic ARN (if None, loads from env)
    """
    if sns_topic_arn is None:
        # Try to get SNS topic ARN from environment
        import os

        sns_topic_arn = os.environ.get("SNS_TOPIC_ARN")
        if not sns_topic_arn:
            logger.warning("SNS_TOPIC_ARN not found in environment")
            return

    try:
        import boto3

        sns = boto3.client("sns")
        send_error_notification(
            sns_client=sns,
            sns_topic_arn=sns_topic_arn,
            error_message=error_msg,
            lambda_name="Scheduler",
        )
    except Exception as e:
        logger.warning(f"Failed to send error notification: {e}")


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
        lambda msg: _send_error_notification(config["sns_topic_arn"], msg)
    )

    queue_module.purge_queue(clients["sqs"], config["queue_url"])

    analyzer = SpendingAnalyzer(clients["savingsplans"], clients["ce"])
    spending_data = analyzer.analyze_current_spending(config)

    purchase_plans = purchase_module.calculate_purchase_need(config, clients, spending_data)
    purchase_plans = purchase_module.apply_purchase_limits(config, purchase_plans)

    # Extract coverage percentages for email notifications
    coverage = {
        sp_type: data["summary"]["avg_coverage"]
        for sp_type, data in spending_data.items()
    }

    if config["dry_run"]:
        email_module.send_dry_run_email(clients["sns"], config, purchase_plans, coverage)
    else:
        queue_module.queue_purchase_intents(clients["sqs"], config, purchase_plans)
        email_module.send_scheduled_email(clients["sns"], config, purchase_plans, coverage)

    return {
        "statusCode": 200,
        "body": json.dumps({
            "message": "Scheduler completed successfully",
            "dry_run": config["dry_run"],
            "purchases_planned": len(purchase_plans),
        }),
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

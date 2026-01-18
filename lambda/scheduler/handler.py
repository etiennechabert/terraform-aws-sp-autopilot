"""
Scheduler Lambda - Analyzes usage and queues Savings Plan purchase intents.

Supports both Compute Savings Plans and Database Savings Plans.

This Lambda:
1. Purges existing queue messages
2. Calculates current coverage (excluding plans expiring within renewal_window_days)
3. Gets AWS purchase recommendations
4. Calculates purchase need based on coverage_target_percent
5. Applies max_purchase_percent limit
6. Splits commitment by term mix (for Compute SP) or applies Database SP term
7. Queues purchase intents (or sends email only if dry_run=true)
8. Sends notification email with analysis results
"""

# Special handling for coverage module to avoid conflict with pytest-cov
# Import it explicitly to avoid naming conflicts with pytest-cov's coverage module
import importlib.util
import json
import logging
import os as _os_for_import
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict

# Import new modular components
# Import with aliases to avoid shadowing when we create backward-compatible wrappers
from config import CONFIG_SCHEMA

from shared.handler_utils import (
    initialize_clients,
    lambda_handler_wrapper,
    load_config_from_env,
    send_error_notification,
)


_coverage_spec = importlib.util.spec_from_file_location(
    "coverage_calc",  # Use different name to avoid conflict
    _os_for_import.path.join(_os_for_import.path.dirname(__file__), "coverage_calculator.py"),
)
coverage_module = importlib.util.module_from_spec(_coverage_spec)
_coverage_spec.loader.exec_module(coverage_module)
del _coverage_spec, _os_for_import  # Clean up temporary variables

# Import concurrent.futures components for backward compatibility with tests

import email_notifications as email_module
import purchase_calculator as purchase_module
import queue_manager as queue_module
import recommendations as recommendations_module


# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Module-level boto3 clients for backward compatibility with existing tests
# These are initialized to None and tests can assign mock objects to them
# The wrapper functions below will use these if set, otherwise create real clients
ce_client = None
sqs_client = None
sns_client = None
savingsplans_client = None


def _ensure_ce_client():
    """Get Cost Explorer client, creating it if needed."""
    global ce_client
    if ce_client is None:
        import boto3

        ce_client = boto3.client("ce")
    return ce_client


def _ensure_sqs_client():
    """Get SQS client, creating it if needed."""
    global sqs_client
    if sqs_client is None:
        import boto3

        sqs_client = boto3.client("sqs")
    return sqs_client


def _ensure_sns_client():
    """Get SNS client, creating it if needed."""
    global sns_client
    if sns_client is None:
        import boto3

        sns_client = boto3.client("sns")
    return sns_client


def _ensure_savingsplans_client():
    """Get Savings Plans client, creating it if needed."""
    global savingsplans_client
    if savingsplans_client is None:
        import boto3

        savingsplans_client = boto3.client("savingsplans")
    return savingsplans_client


# Backward-compatible wrapper functions for existing tests
# These match the old function signatures and use lazily-initialized clients
def load_configuration() -> Dict[str, Any]:
    """Load configuration - backward compatible wrapper."""
    from config import load_configuration as config_load

    return config_load()


def calculate_current_coverage(config: Dict[str, Any]) -> Dict[str, float]:
    """Calculate current coverage - backward compatible wrapper."""
    return coverage_module.calculate_current_coverage(
        _ensure_savingsplans_client(), _ensure_ce_client(), config
    )


def get_aws_recommendations(config: Dict[str, Any]) -> Dict[str, Any]:
    """Get AWS recommendations - backward compatible wrapper."""
    return recommendations_module.get_aws_recommendations(_ensure_ce_client(), config)


def get_assumed_role_session(role_arn: str, session_name: str = "sp-autopilot-session"):
    """Get assumed role session - backward compatible wrapper."""
    from shared.aws_utils import get_assumed_role_session as aws_assume_role

    return aws_assume_role(role_arn, session_name)


def get_clients(config: Dict[str, Any]):
    """Get clients - backward compatible wrapper."""
    from shared.aws_utils import get_clients as aws_get_clients

    return aws_get_clients(config)


def purge_queue(queue_url: str) -> None:
    """Purge queue - backward compatible wrapper."""
    return queue_module.purge_queue(_ensure_sqs_client(), queue_url)


def queue_purchase_intents(config: Dict[str, Any], purchase_plans: list) -> None:
    """Queue purchase intents - backward compatible wrapper."""
    return queue_module.queue_purchase_intents(_ensure_sqs_client(), config, purchase_plans)


def send_scheduled_email(
    config: Dict[str, Any], purchase_plans: list, coverage_data: Dict[str, float]
) -> None:
    """Send scheduled email - backward compatible wrapper."""
    return email_module.send_scheduled_email(
        _ensure_sns_client(), config, purchase_plans, coverage_data
    )


def send_dry_run_email(
    config: Dict[str, Any], purchase_plans: list, coverage_data: Dict[str, float]
) -> None:
    """Send dry run email - backward compatible wrapper."""
    return email_module.send_dry_run_email(
        _ensure_sns_client(), config, purchase_plans, coverage_data
    )


# Re-export these functions directly as they don't need client parameters
calculate_purchase_need = purchase_module.calculate_purchase_need
apply_purchase_limits = purchase_module.apply_purchase_limits
split_by_term = purchase_module.split_by_term


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
def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Main handler for Scheduler Lambda.

    Args:
        event: EventBridge scheduled event
        context: Lambda context

    Returns:
        dict: Status and summary of analysis

    Raises:
        Exception: All errors are raised (no silent failures)
    """
    try:
        # Load configuration from environment
        config = load_config_from_env(CONFIG_SCHEMA)

        # Create error callback function
        def send_error_email(error_msg: str) -> None:
            """Send error notification using shared utility."""
            # Get SNS client directly (before full client initialization)
            import boto3

            sns = boto3.client("sns")
            send_error_notification(
                sns_client=sns,
                sns_topic_arn=config["sns_topic_arn"],
                error_message=error_msg,
                lambda_name="Scheduler",
            )

        # Initialize clients (with assume role if configured)
        clients = initialize_clients(config, "sp-autopilot-scheduler", send_error_email)
        ce_client = clients["ce"]
        savingsplans_client = clients["savingsplans"]
        sqs_client = clients["sqs"]
        sns_client = clients["sns"]

        logger.info(f"Configuration loaded: dry_run={config['dry_run']}")

        # Step 1: Purge existing queue
        queue_module.purge_queue(sqs_client, config["queue_url"])

        # Step 2 & 3: Calculate coverage and get recommendations in parallel
        with ThreadPoolExecutor(max_workers=2) as executor:
            # Submit both tasks for parallel execution
            coverage_future = executor.submit(
                coverage_module.calculate_current_coverage,
                savingsplans_client,
                ce_client,
                config,
            )
            recommendations_future = executor.submit(
                recommendations_module.get_aws_recommendations, ce_client, config
            )

            # Wait for results
            coverage = coverage_future.result()
            recommendations = recommendations_future.result()

        logger.info(
            f"Current coverage - Compute: {coverage.get('compute', 0)}%, Database: {coverage.get('database', 0)}%, SageMaker: {coverage.get('sagemaker', 0)}%"
        )

        # Step 4: Calculate purchase need
        purchase_plans = purchase_module.calculate_purchase_need(config, coverage, recommendations)

        # Step 5: Apply purchase limits
        purchase_plans = purchase_module.apply_purchase_limits(config, purchase_plans)

        # Step 6: Split by term (for Compute SP)
        purchase_plans = purchase_module.split_by_term(config, purchase_plans)

        # Step 7: Queue or notify
        if config["dry_run"]:
            logger.info("Dry run mode - sending email only, NOT queuing messages")
            email_module.send_dry_run_email(sns_client, config, purchase_plans, coverage)
        else:
            logger.info("Queuing purchase intents to SQS")
            queue_module.queue_purchase_intents(sqs_client, config, purchase_plans)
            email_module.send_scheduled_email(sns_client, config, purchase_plans, coverage)

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

    except Exception as e:
        # Try to send error notification
        try:
            config = load_config_from_env(CONFIG_SCHEMA)
            import boto3

            sns = boto3.client("sns")
            send_error_notification(
                sns_client=sns,
                sns_topic_arn=config["sns_topic_arn"],
                error_message=str(e),
                lambda_name="Scheduler",
            )
        except Exception as notification_error:
            logger.warning(f"Failed to send error notification: {notification_error}")
        raise  # Re-raise to ensure Lambda fails visibly

"""
Handler utility functions for Lambda functions.

Provides shared utilities for configuration loading, client initialization,
error handling, and standardized handler patterns across all Lambda functions.
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Callable
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from botocore.exceptions import ClientError


if TYPE_CHECKING:
    from mypy_boto3_sns.client import SNSClient

from shared import notifications
from shared.aws_utils import get_clients
from shared.constants import PLAN_TYPE_COMPUTE, PLAN_TYPE_DATABASE, PLAN_TYPE_SAGEMAKER


# Configure logging
logger = logging.getLogger()


def configure_logging() -> None:
    """Configure logging level from LOG_LEVEL environment variable."""
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, log_level, logging.INFO)

    # Configure root logger
    root = logging.getLogger()
    root.setLevel(level)

    # Configure all handlers
    if not root.handlers:
        # Add a handler if none exists (for local development)
        handler = logging.StreamHandler()
        handler.setLevel(level)
        formatter = logging.Formatter("%(levelname)s - %(name)s - %(message)s")
        handler.setFormatter(formatter)
        root.addHandler(handler)
    else:
        # Update existing handlers
        for h in root.handlers:
            h.setLevel(level)

    # Suppress verbose botocore/boto3 debug logging unless BOTO_DEBUG=true
    boto_debug = os.getenv("BOTO_DEBUG", "false").lower() == "true"
    if not boto_debug:
        logging.getLogger("botocore").setLevel(logging.INFO)
        logging.getLogger("boto3").setLevel(logging.INFO)
        logging.getLogger("urllib3").setLevel(logging.INFO)


configure_logging()


def _get_env_value(env_var: str, is_required: bool, default_value: Any) -> str | None:
    """Retrieve value from environment variable."""
    if is_required:
        return os.environ[env_var]
    if default_value is not None:
        return os.environ.get(env_var, default_value)
    value = os.environ.get(env_var)
    return value if value else None  # treat empty string as unset


def _convert_field_value(raw_value: str, field_type: str, field_name: str) -> Any:
    """Convert raw string value to the specified type."""
    if field_type == "str":
        return raw_value
    if field_type == "bool":
        return raw_value.lower() == "true"
    if field_type == "int":
        return int(raw_value)
    if field_type == "float":
        return float(raw_value)
    if field_type == "json":
        return json.loads(raw_value)

    logger.warning(f"Unknown type '{field_type}' for field '{field_name}', treating as string")
    return raw_value


def load_config_from_env(
    schema: dict[str, dict[str, Any]],
    validator: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Load config from env vars per schema, apply types, and run optional validator."""
    config = {}

    for field_name, field_spec in schema.items():
        env_var = field_spec.get("env_var", field_name.upper())
        is_required = field_spec.get("required", False)
        field_type = field_spec.get("type", "str")
        default_value = field_spec.get("default")

        raw_value = _get_env_value(env_var, is_required, default_value)

        if raw_value is None:
            continue

        try:
            config[field_name] = _convert_field_value(raw_value, field_type, field_name)
        except json.JSONDecodeError as e:
            raise json.JSONDecodeError(
                f"Failed to parse JSON for field '{field_name}' (env var '{env_var}'): {e.msg}",
                e.doc,
                e.pos,
            ) from e
        except (ValueError, TypeError) as e:
            raise ValueError(
                f"Failed to convert field '{field_name}' (env var '{env_var}') to type '{field_type}': {e}"
            ) from e

    if validator:
        validator(config)

    return config


def get_enabled_plan_types(config: dict[str, Any]) -> list[str]:
    """Enabled SP types in AWS naming, e.g. ['Compute', 'SageMaker']."""
    enabled_types = []
    if config["enable_compute_sp"]:
        enabled_types.append(PLAN_TYPE_COMPUTE)
    if config["enable_sagemaker_sp"]:
        enabled_types.append(PLAN_TYPE_SAGEMAKER)
    if config["enable_database_sp"]:
        enabled_types.append(PLAN_TYPE_DATABASE)
    return enabled_types


def initialize_clients(
    config: dict[str, Any],
    session_name: str,
    error_callback: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Build AWS clients (assumes role when management_account_role_arn is set).

    On ClientError, logs, invokes error_callback if provided, then re-raises.
    """
    try:
        clients = get_clients(config, session_name=session_name)
        logger.info(f"AWS clients initialized successfully (session: {session_name})")
        return clients
    except ClientError as e:
        # Build descriptive error message
        error_msg = f"Failed to initialize AWS clients: {e!s}"
        if config.get("management_account_role_arn"):
            error_msg = f"Failed to assume role {config['management_account_role_arn']}: {e!s}"

        # Log error with full traceback
        logger.error(error_msg, exc_info=True)

        # Call error callback if provided
        if error_callback:
            try:
                error_callback(error_msg)
            except Exception as callback_error:
                logger.warning(f"Error callback failed: {callback_error}")

        # Re-raise to ensure Lambda fails visibly
        raise


def lambda_handler_wrapper(lambda_name: str) -> Callable:
    """Log start/completion, log traceback on exception, then re-raise."""

    def decorator(handler_func: Callable) -> Callable:
        def wrapper(event: dict[str, Any], context: Any) -> dict[str, Any]:
            try:
                logger.info(f"Starting {lambda_name} Lambda execution")
                result = handler_func(event, context)
                logger.info(f"{lambda_name} Lambda completed successfully")
                return result
            except Exception as e:
                logger.error(f"{lambda_name} Lambda failed: {e!s}", exc_info=True)
                raise  # Re-raise to ensure Lambda fails visibly

        return wrapper

    return decorator


def send_error_notification(
    sns_client: SNSClient,
    sns_topic_arn: str,
    error_message: str,
    lambda_name: str = "Lambda",
    slack_webhook_url: str | None = None,
    teams_webhook_url: str | None = None,
) -> None:
    """Publish error to SNS and (if configured) Slack and Teams. Failures are logged, not raised."""
    logger.error(f"Sending error notification for {lambda_name}")

    # Get current timestamp
    timestamp = datetime.now(UTC).isoformat()

    # Validate required parameters
    if not sns_topic_arn:
        logger.error("Cannot send error notification - SNS_TOPIC_ARN not provided")
        return

    # Build SNS subject and message
    sns_subject = f"[SP Autopilot] {lambda_name} Lambda Failed"
    sns_message = f"""Savings Plans Autopilot - {lambda_name} Lambda Error

ERROR: {error_message}

Time: {timestamp}

Please check CloudWatch Logs for full details.
"""

    # Send SNS notification
    try:
        sns_client.publish(TopicArn=sns_topic_arn, Subject=sns_subject, Message=sns_message)
        logger.info(f"Error notification sent via SNS to {sns_topic_arn}")
    except Exception as e:
        # Don't raise - we're already in error handling
        logger.warning(f"Failed to send SNS error notification: {e!s}")

    # Send Slack notification (if configured)
    if slack_webhook_url:
        try:
            body_lines = [
                f"Savings Plans Autopilot - {lambda_name} Lambda Error",
                "",
                f"**ERROR:** {error_message}",
                "",
                f"**Time:** {timestamp}",
                "",
                "Please check CloudWatch Logs for full details.",
            ]
            slack_message = notifications.format_slack_message(
                sns_subject, body_lines, severity="error"
            )
            if notifications.send_slack_notification(slack_webhook_url, slack_message):
                logger.info("Slack error notification sent successfully")
            else:
                logger.warning("Slack error notification failed")
        except Exception as e:
            logger.warning(f"Failed to send Slack error notification: {e!s}")

    # Send Teams notification (if configured)
    if teams_webhook_url:
        try:
            body_lines = [
                f"Savings Plans Autopilot - {lambda_name} Lambda Error",
                "",
                f"ERROR: {error_message}",
                "",
                f"Time: {timestamp}",
                "",
                "Please check CloudWatch Logs for full details.",
            ]
            teams_message = notifications.format_teams_message(sns_subject, body_lines)
            if notifications.send_teams_notification(teams_webhook_url, teams_message):
                logger.info("Teams error notification sent successfully")
            else:
                logger.warning("Teams error notification failed")
        except Exception as e:
            logger.warning(f"Failed to send Teams error notification: {e!s}")

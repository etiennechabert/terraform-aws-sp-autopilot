"""
Handler utility functions for Lambda functions.

Provides shared utilities for configuration loading, client initialization,
error handling, and standardized handler patterns across all Lambda functions.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Callable

from botocore.exceptions import ClientError


if TYPE_CHECKING:
    from mypy_boto3_sns.client import SNSClient

from shared import notifications
from shared.aws_utils import get_clients


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


configure_logging()


def load_config_from_env(schema: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """
    Load and validate configuration from environment variables based on a schema.

    This function provides a generic way to load configuration from environment
    variables with type conversion, validation, and default values. It eliminates
    duplicate configuration loading code across Lambda handlers.

    Args:
        schema: Configuration schema dictionary where each key is a config field name
                and the value is a dict with the following properties:
                - 'required' (bool): Whether the field is required (default: False)
                - 'type' (str): Data type - 'str', 'bool', 'int', 'float', 'json'
                - 'default' (Any): Default value if not required and not present
                - 'env_var' (str): Environment variable name (defaults to uppercase field name)

    Returns:
        dict: Configuration dictionary with validated and type-converted values

    Raises:
        KeyError: If a required environment variable is missing
        ValueError: If type conversion fails
        json.JSONDecodeError: If JSON parsing fails

    Examples:
        >>> # Simple schema with required and optional fields
        >>> schema = {
        ...     'queue_url': {'required': True, 'type': 'str', 'env_var': 'QUEUE_URL'},
        ...     'dry_run': {'required': False, 'type': 'bool', 'default': 'true', 'env_var': 'DRY_RUN'},
        ...     'max_purchase_percent': {'required': False, 'type': 'float', 'default': '10'},
        ...     'tags': {'required': False, 'type': 'json', 'default': '{}'}
        ... }
        >>> config = load_config_from_env(schema)
        >>> # Returns: {'queue_url': '...', 'dry_run': True, 'max_purchase_percent': 10.0, 'tags': {}}

    Type Conversion Rules:
        - 'str': No conversion, returned as-is
        - 'bool': Converts string to bool (case-insensitive 'true' -> True, else False)
        - 'int': Converts string to integer
        - 'float': Converts string to float
        - 'json': Parses JSON string to dict/list
    """
    config = {}

    for field_name, field_spec in schema.items():
        # Get environment variable name (default to uppercase field name)
        env_var = field_spec.get("env_var", field_name.upper())

        # Check if field is required
        is_required = field_spec.get("required", False)

        # Get field type
        field_type = field_spec.get("type", "str")

        # Get default value
        default_value = field_spec.get("default")

        # Retrieve value from environment
        if is_required:
            # Required field - will raise KeyError if missing
            raw_value = os.environ[env_var]
        # Optional field - use default if missing
        elif default_value is not None:
            raw_value = os.environ.get(env_var, default_value)
        else:
            raw_value = os.environ.get(env_var)

        # Skip if value is None (optional field not provided, no default)
        if raw_value is None:
            continue

        # Type conversion
        try:
            if field_type == "str":
                config[field_name] = raw_value
            elif field_type == "bool":
                # Boolean conversion: 'true' (case-insensitive) -> True, else False
                config[field_name] = raw_value.lower() == "true"
            elif field_type == "int":
                config[field_name] = int(raw_value)
            elif field_type == "float":
                config[field_name] = float(raw_value)
            elif field_type == "json":
                config[field_name] = json.loads(raw_value)
            else:
                # Unknown type - treat as string and log warning
                logger.warning(
                    f"Unknown type '{field_type}' for field '{field_name}', treating as string"
                )
                config[field_name] = raw_value
        except (ValueError, TypeError) as e:
            raise ValueError(
                f"Failed to convert field '{field_name}' (env var '{env_var}') to type '{field_type}': {e}"
            ) from e
        except json.JSONDecodeError as e:
            raise json.JSONDecodeError(
                f"Failed to parse JSON for field '{field_name}' (env var '{env_var}'): {e.msg}",
                e.doc,
                e.pos,
            ) from e

    return config


def initialize_clients(
    config: dict[str, Any],
    session_name: str,
    error_callback: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """
    Initialize AWS clients with assume role support and standardized error handling.

    This is a wrapper around shared.aws_utils.get_clients() that provides
    consistent error handling, logging, and error notification across all
    Lambda handlers. It eliminates duplicate client initialization code.

    Args:
        config: Configuration dictionary (must contain 'management_account_role_arn'
                if using cross-account assume role)
        session_name: Session name for assume role (e.g., 'sp-autopilot-scheduler')
        error_callback: Optional callback function to call on error (e.g., send_error_email).
                        The callback receives the error message as a string parameter.

    Returns:
        dict: Dictionary of AWS client objects with the following keys:
              - 'ce': Cost Explorer client
              - 'savingsplans': Savings Plans client
              - 's3': S3 client (if needed)
              - 'sqs': SQS client (if needed)
              - 'sns': SNS client (if needed)

    Raises:
        ClientError: If client initialization or role assumption fails

    Examples:
        >>> # Basic usage with error callback
        >>> config = load_configuration()
        >>> clients = initialize_clients(config, 'sp-autopilot-scheduler', send_error_email)
        >>> ce_client = clients['ce']
        >>> savingsplans_client = clients['savingsplans']

        >>> # Usage without error callback
        >>> clients = initialize_clients(config, 'sp-autopilot-purchaser')
        >>> ce_client = clients['ce']

    Notes:
        - If management_account_role_arn is set in config, clients will use assumed role
        - Error messages automatically include role ARN if role assumption fails
        - All errors are logged with full traceback before re-raising
    """
    try:
        clients = get_clients(config, session_name=session_name)
        logger.info(f"AWS clients initialized successfully (session: {session_name})")
        return clients
    except ClientError as e:
        # Build descriptive error message
        error_msg = f"Failed to initialize AWS clients: {e!s}"
        if config.get("management_account_role_arn"):
            error_msg = (
                f"Failed to assume role {config['management_account_role_arn']}: {e!s}"
            )

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
    """
    Decorator that provides standardized error handling and logging for Lambda handlers.

    This decorator wraps Lambda handler functions to provide:
    - Consistent logging of handler start and completion
    - Centralized exception handling with full traceback logging
    - Automatic re-raising of exceptions to ensure Lambda fails visibly

    Note: Error notifications should be handled within the handler function itself
    before exceptions are raised, as the decorator does not have access to SNS
    client or configuration.

    Args:
        lambda_name: Name of the Lambda function (e.g., 'Scheduler', 'Purchaser', 'Reporter')

    Returns:
        Decorated handler function

    Raises:
        Exception: Re-raises any exception from the wrapped handler to ensure Lambda fails visibly

    Examples:
        >>> @lambda_handler_wrapper('Scheduler')
        ... def handler(event, context):
        ...     try:
        ...         # Load configuration
        ...         config = load_configuration()
        ...         # Initialize clients
        ...         clients = get_clients(config)
        ...         # Do work...
        ...         return {'statusCode': 200, 'body': 'Success'}
        ...     except Exception as e:
        ...         # Send error notification before raising
        ...         send_error_email(str(e))
        ...         raise

        >>> # The decorator automatically logs start/completion and handles errors
        >>> # Output when handler succeeds:
        >>> # INFO: Starting Scheduler Lambda execution
        >>> # INFO: Scheduler Lambda completed successfully

        >>> # Output when handler fails:
        >>> # INFO: Starting Scheduler Lambda execution
        >>> # ERROR: Scheduler Lambda failed: [error message]
        >>> # [Full exception traceback]

    Notes:
        - The decorator logs at INFO level for start and completion
        - Exceptions are logged at ERROR level with full traceback (exc_info=True)
        - All exceptions are re-raised to ensure Lambda execution fails visibly
        - Handlers should implement their own error notification before raising
    """

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
    """
    Send error notification via SNS, Slack, and Teams.

    This is a consolidated error notification utility that eliminates duplicate
    error handling code across Lambda handlers. It sends notifications through
    multiple channels (SNS, Slack, Teams) with proper error handling.

    Args:
        sns_client: Boto3 SNS client instance
        sns_topic_arn: SNS topic ARN to publish error notification
        error_message: Error message/details to include in notification
        lambda_name: Name of the Lambda function (for message context, default: 'Lambda')
        slack_webhook_url: Optional Slack webhook URL for Slack notifications
        teams_webhook_url: Optional Teams webhook URL for Teams notifications

    Returns:
        None

    Examples:
        >>> # Basic usage (SNS only)
        >>> send_error_notification(
        ...     sns_client=sns_client,
        ...     sns_topic_arn='arn:aws:sns:us-east-1:123456789012:my-topic',
        ...     error_message='Failed to process purchase intent',
        ...     lambda_name='Purchaser'
        ... )

        >>> # With Slack and Teams notifications
        >>> send_error_notification(
        ...     sns_client=sns_client,
        ...     sns_topic_arn=config['sns_topic_arn'],
        ...     error_message=str(e),
        ...     lambda_name='Scheduler',
        ...     slack_webhook_url=config.get('slack_webhook_url'),
        ...     teams_webhook_url=config.get('teams_webhook_url')
        ... )

    Notes:
        - Notification failures are logged but do not raise exceptions
        - SNS notification is always attempted first
        - Slack/Teams notifications are only sent if webhook URLs are provided
        - Errors during notification are logged as warnings (graceful degradation)
        - Timestamp is automatically included in all notifications
    """
    logger.error(f"Sending error notification for {lambda_name}")

    # Get current timestamp
    timestamp = datetime.now(timezone.utc).isoformat()

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
        sns_client.publish(
            TopicArn=sns_topic_arn, Subject=sns_subject, Message=sns_message
        )
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

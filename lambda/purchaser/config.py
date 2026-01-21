"""
Configuration schema and constants for the Purchaser Lambda.

This module defines the configuration schema used for loading environment
variables and validating configuration parameters for the Savings Plans
Autopilot Purchaser Lambda function.
"""

from typing import Any

from shared.handler_utils import load_config_from_env


# Configuration schema for environment variable loading
CONFIG_SCHEMA = {
    "queue_url": {"required": True, "type": "str", "env_var": "QUEUE_URL"},
    "sns_topic_arn": {"required": True, "type": "str", "env_var": "SNS_TOPIC_ARN"},
    "max_coverage_cap": {
        "required": False,
        "type": "float",
        "default": "95",
        "env_var": "MAX_COVERAGE_CAP",
    },
    "renewal_window_days": {
        "required": False,
        "type": "int",
        "default": "7",
        "env_var": "RENEWAL_WINDOW_DAYS",
    },
    "lookback_days": {
        "required": False,
        "type": "int",
        "default": "30",
        "env_var": "LOOKBACK_DAYS",
    },
    "management_account_role_arn": {
        "required": False,
        "type": "str",
        "env_var": "MANAGEMENT_ACCOUNT_ROLE_ARN",
    },
    "tags": {"required": False, "type": "json", "default": "{}", "env_var": "TAGS"},
    "slack_webhook_url": {
        "required": False,
        "type": "str",
        "env_var": "SLACK_WEBHOOK_URL",
    },
    "teams_webhook_url": {
        "required": False,
        "type": "str",
        "env_var": "TEAMS_WEBHOOK_URL",
    },
}


def load_configuration() -> dict[str, Any]:
    """
    Load and validate configuration from environment variables.

    Returns:
        dict: Validated configuration dictionary
    """
    from shared.config_validation import validate_purchaser_config

    return load_config_from_env(CONFIG_SCHEMA, validator=validate_purchaser_config)

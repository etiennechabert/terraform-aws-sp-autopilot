"""
Configuration schema and constants for the Reporter Lambda.

This module defines the configuration schema used for loading environment
variables and validating configuration parameters for the Savings Plans
Autopilot Reporter Lambda function.
"""

from typing import Any

from shared.handler_utils import load_config_from_env


# Configuration schema for environment variable loading
CONFIG_SCHEMA = {
    "reports_bucket": {"required": True, "type": "str", "env_var": "REPORTS_BUCKET"},
    "sns_topic_arn": {"required": True, "type": "str", "env_var": "SNS_TOPIC_ARN"},
    "report_format": {
        "required": False,
        "type": "str",
        "default": "html",
        "env_var": "REPORT_FORMAT",
    },
    "email_reports": {
        "required": False,
        "type": "bool",
        "default": "false",
        "env_var": "EMAIL_REPORTS",
    },
    "include_debug_data": {
        "required": False,
        "type": "bool",
        "default": "false",
        "env_var": "INCLUDE_DEBUG_DATA",
    },
    "enable_compute_sp": {
        "required": False,
        "type": "bool",
        "default": "true",
        "env_var": "ENABLE_COMPUTE_SP",
    },
    "enable_database_sp": {
        "required": False,
        "type": "bool",
        "default": "false",
        "env_var": "ENABLE_DATABASE_SP",
    },
    "enable_sagemaker_sp": {
        "required": False,
        "type": "bool",
        "default": "false",
        "env_var": "ENABLE_SAGEMAKER_SP",
    },
    "lookback_days": {
        "required": True,
        "type": "int",
        "env_var": "LOOKBACK_DAYS",
    },
    "granularity": {
        "required": True,
        "type": "str",
        "env_var": "GRANULARITY",
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
    "low_utilization_threshold": {
        "required": True,
        "type": "float",
        "env_var": "LOW_UTILIZATION_THRESHOLD",
    },
    "coverage_target_percent": {
        "required": False,
        "type": "str",
        "default": "balanced",
        "env_var": "COVERAGE_TARGET_PERCENT",
    },
    # Scheduler strategy parameters (for preview simulation)
    "purchase_strategy_type": {
        "required": False,
        "type": "str",
        "default": "fixed",
        "env_var": "PURCHASE_STRATEGY_TYPE",
    },
    "max_purchase_percent": {
        "required": False,
        "type": "float",
        "default": "10.0",
        "env_var": "MAX_PURCHASE_PERCENT",
    },
    "min_purchase_percent": {
        "required": False,
        "type": "float",
        "default": "1.0",
        "env_var": "MIN_PURCHASE_PERCENT",
    },
    "compute_sp_term": {
        "required": False,
        "type": "str",
        "default": "THREE_YEAR",
        "env_var": "COMPUTE_SP_TERM",
    },
    "compute_sp_payment_option": {
        "required": False,
        "type": "str",
        "default": "ALL_UPFRONT",
        "env_var": "COMPUTE_SP_PAYMENT_OPTION",
    },
    "database_sp_payment_option": {
        "required": False,
        "type": "str",
        "default": "NO_UPFRONT",
        "env_var": "DATABASE_SP_PAYMENT_OPTION",
    },
    "sagemaker_sp_term": {
        "required": False,
        "type": "str",
        "default": "THREE_YEAR",
        "env_var": "SAGEMAKER_SP_TERM",
    },
    "sagemaker_sp_payment_option": {
        "required": False,
        "type": "str",
        "default": "ALL_UPFRONT",
        "env_var": "SAGEMAKER_SP_PAYMENT_OPTION",
    },
}


def load_configuration() -> dict[str, Any]:
    """
    Load and validate configuration from environment variables.

    Returns:
        dict: Validated configuration dictionary
    """
    from shared.config_validation import validate_reporter_config

    return load_config_from_env(CONFIG_SCHEMA, validator=validate_reporter_config)

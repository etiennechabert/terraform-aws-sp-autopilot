"""
Configuration schema and constants for the Scheduler Lambda.

This module defines the configuration schema used for loading environment
variables and validating configuration parameters for the Savings Plans
Autopilot Scheduler Lambda function.
"""

from typing import Any

from shared.config_schemas import (
    AWS_COMMON,
    SP_TERM_PAYMENT_OPTIONS,
    SP_TYPE_TOGGLES,
    STRATEGY_PARAMS,
)
from shared.handler_utils import load_config_from_env


# Configuration schema for environment variable loading
CONFIG_SCHEMA = {
    "queue_url": {"required": True, "type": "str", "env_var": "QUEUE_URL"},
    "sns_topic_arn": {"required": True, "type": "str", "env_var": "SNS_TOPIC_ARN"},
    "dry_run": {
        "required": False,
        "type": "bool",
        "default": "true",
        "env_var": "DRY_RUN",
    },
    **SP_TYPE_TOGGLES,
    "coverage_target_percent": {
        "required": False,
        "type": "float",
        "default": "90",
        "env_var": "COVERAGE_TARGET_PERCENT",
    },
    **STRATEGY_PARAMS,
    "renewal_window_days": {
        "required": False,
        "type": "int",
        "default": "7",
        "env_var": "RENEWAL_WINDOW_DAYS",
    },
    "lookback_days": {
        "required": False,
        "type": "int",
        "default": "13",
        "env_var": "LOOKBACK_DAYS",
    },
    "granularity": {
        "required": False,
        "type": "str",
        "default": "DAILY",
        "env_var": "GRANULARITY",
    },
    "min_commitment_per_plan": {
        "required": False,
        "type": "float",
        "default": "0.001",
        "env_var": "MIN_COMMITMENT_PER_PLAN",
    },
    **SP_TERM_PAYMENT_OPTIONS,
    **AWS_COMMON,
}


def load_configuration() -> dict[str, Any]:
    """
    Load and validate configuration from environment variables.

    Returns:
        dict: Validated configuration dictionary
    """
    from shared.config_validation import validate_scheduler_config

    return load_config_from_env(CONFIG_SCHEMA, validator=validate_scheduler_config)

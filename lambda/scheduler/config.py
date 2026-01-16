"""
Configuration schema and constants for the Scheduler Lambda.

This module defines the configuration schema used for loading environment
variables and validating configuration parameters for the Savings Plans
Autopilot Scheduler Lambda function.
"""

from typing import Any, Dict

from shared.handler_utils import load_config_from_env


# Configuration schema for environment variable loading
CONFIG_SCHEMA = {
    "queue_url": {"required": True, "type": "str", "env_var": "QUEUE_URL"},
    "sns_topic_arn": {"required": True, "type": "str", "env_var": "SNS_TOPIC_ARN"},
    "dry_run": {"required": False, "type": "bool", "default": "true", "env_var": "DRY_RUN"},
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
    "coverage_target_percent": {
        "required": False,
        "type": "float",
        "default": "90",
        "env_var": "COVERAGE_TARGET_PERCENT",
    },
    "purchase_strategy_type": {
        "required": False,
        "type": "str",
        "default": "simple",
        "env_var": "PURCHASE_STRATEGY_TYPE",
    },
    "max_purchase_percent": {
        "required": False,
        "type": "float",
        "default": "10",
        "env_var": "MAX_PURCHASE_PERCENT",
    },
    "min_purchase_percent": {
        "required": False,
        "type": "float",
        "default": "1",
        "env_var": "MIN_PURCHASE_PERCENT",
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
    "min_data_days": {
        "required": False,
        "type": "int",
        "default": "14",
        "env_var": "MIN_DATA_DAYS",
    },
    "min_commitment_per_plan": {
        "required": False,
        "type": "float",
        "default": "0.001",
        "env_var": "MIN_COMMITMENT_PER_PLAN",
    },
    "compute_sp_term_mix": {
        "required": False,
        "type": "json",
        "default": '{"three_year": 0.67, "one_year": 0.33}',
        "env_var": "COMPUTE_SP_TERM_MIX",
    },
    "compute_sp_payment_option": {
        "required": False,
        "type": "str",
        "default": "ALL_UPFRONT",
        "env_var": "COMPUTE_SP_PAYMENT_OPTION",
    },
    "sagemaker_sp_term_mix": {
        "required": False,
        "type": "json",
        "default": '{"three_year": 0.67, "one_year": 0.33}',
        "env_var": "SAGEMAKER_SP_TERM_MIX",
    },
    "sagemaker_sp_payment_option": {
        "required": False,
        "type": "str",
        "default": "ALL_UPFRONT",
        "env_var": "SAGEMAKER_SP_PAYMENT_OPTION",
    },
    "partial_upfront_percent": {
        "required": False,
        "type": "float",
        "default": "50",
        "env_var": "PARTIAL_UPFRONT_PERCENT",
    },
    "management_account_role_arn": {
        "required": False,
        "type": "str",
        "env_var": "MANAGEMENT_ACCOUNT_ROLE_ARN",
    },
    "tags": {"required": False, "type": "json", "default": "{}", "env_var": "TAGS"},
}


def load_configuration() -> Dict[str, Any]:
    """
    Load and validate configuration from environment variables.

    Returns:
        dict: Validated configuration dictionary
    """
    return load_config_from_env(CONFIG_SCHEMA)

"""
Configuration schema and constants for the Reporter Lambda.
"""

from typing import Any

from shared.config_schemas import (
    AWS_COMMON,
    NOTIFICATION_PARAMS,
    SP_TERM_PAYMENT_OPTIONS,
    SP_TYPE_TOGGLES,
    SPIKE_GUARD_PARAMS,
    STRATEGY_PARAMS,
    TIMING_PARAMS,
)
from shared.handler_utils import load_config_from_env


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
    **SP_TYPE_TOGGLES,
    "lookback_days": {
        "required": False,
        "type": "int",
        "default": "365",
        "env_var": "LOOKBACK_DAYS",
    },
    **AWS_COMMON,
    **NOTIFICATION_PARAMS,
    "low_utilization_threshold": {
        "required": True,
        "type": "float",
        "env_var": "LOW_UTILIZATION_THRESHOLD",
    },
    **TIMING_PARAMS,
    **STRATEGY_PARAMS,
    **SP_TERM_PAYMENT_OPTIONS,
    **SPIKE_GUARD_PARAMS,
}


def load_configuration() -> dict[str, Any]:
    from shared.config_validation import validate_reporter_config

    return load_config_from_env(CONFIG_SCHEMA, validator=validate_reporter_config)

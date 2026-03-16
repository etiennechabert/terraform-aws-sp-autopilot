"""
Configuration schema and constants for the Scheduler Lambda.
"""

from typing import Any

from shared.config_schemas import (
    AWS_COMMON,
    SP_TERM_PAYMENT_OPTIONS,
    SP_TYPE_TOGGLES,
    SPIKE_GUARD_PARAMS,
    STRATEGY_PARAMS,
    TIMING_PARAMS,
)
from shared.handler_utils import load_config_from_env


CONFIG_SCHEMA = {
    "queue_url": {"required": True, "type": "str", "env_var": "QUEUE_URL"},
    "sns_topic_arn": {"required": True, "type": "str", "env_var": "SNS_TOPIC_ARN"},
    **SP_TYPE_TOGGLES,
    **STRATEGY_PARAMS,
    **TIMING_PARAMS,
    **SP_TERM_PAYMENT_OPTIONS,
    **SPIKE_GUARD_PARAMS,
    **AWS_COMMON,
}


def load_configuration() -> dict[str, Any]:
    from shared.config_validation import validate_scheduler_config

    return load_config_from_env(CONFIG_SCHEMA, validator=validate_scheduler_config)

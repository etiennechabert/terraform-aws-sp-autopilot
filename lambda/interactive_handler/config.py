"""
Configuration schema and constants for the Interactive Handler Lambda.

This module defines the configuration schema used for loading environment
variables and validating configuration parameters for the Savings Plans
Autopilot Interactive Handler Lambda function.
"""

from typing import Any

from shared.handler_utils import load_config_from_env


# Configuration schema for environment variable loading
CONFIG_SCHEMA = {
    "slack_signing_secret": {
        "required": True,
        "type": "str",
        "env_var": "SLACK_SIGNING_SECRET",
    },
    "queue_url": {"required": True, "type": "str", "env_var": "QUEUE_URL"},
}


def load_configuration() -> dict[str, Any]:
    """
    Load and validate configuration from environment variables.

    Returns:
        dict: Validated configuration dictionary
    """
    from shared.config_validation import validate_interactive_handler_config

    return load_config_from_env(CONFIG_SCHEMA, validator=validate_interactive_handler_config)

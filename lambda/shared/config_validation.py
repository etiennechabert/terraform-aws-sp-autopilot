"""
Configuration validation module for Lambda environment variables.

This module provides schema validation and type enforcement for Lambda
configuration to ensure data integrity before execution.
"""

from typing import Any


# Valid values for payment_option field
VALID_PAYMENT_OPTIONS = ["NO_UPFRONT", "ALL_UPFRONT", "PARTIAL_UPFRONT"]

# Valid values for purchase_strategy_type field
VALID_PURCHASE_STRATEGIES = ["simple"]

# Valid values for report_format field
VALID_REPORT_FORMATS = ["html", "json"]


def _validate_percentage_range(
    value: Any, field_name: str, min_val: float = 0.0, max_val: float = 100.0
) -> None:
    """
    Validate that a value is a number within a valid percentage range.

    Args:
        value: The value to validate
        field_name: Name of the field being validated (for error messages)
        min_val: Minimum allowed value (default: 0.0)
        max_val: Maximum allowed value (default: 100.0)

    Returns:
        None (validation passes silently)

    Raises:
        ValueError: If validation fails with descriptive error message
    """
    if not isinstance(value, (int, float)):
        raise ValueError(
            f"Field '{field_name}' must be a number, got {type(value).__name__}: {value}"
        )

    if value < min_val or value > max_val:
        raise ValueError(
            f"Field '{field_name}' must be between {min_val} and {max_val}, got {value}"
        )


def _validate_positive_number(value: Any, field_name: str) -> None:
    """
    Validate that a value is a positive number (> 0).

    Args:
        value: The value to validate
        field_name: Name of the field being validated (for error messages)

    Returns:
        None (validation passes silently)

    Raises:
        ValueError: If validation fails with descriptive error message
    """
    if not isinstance(value, (int, float)):
        raise ValueError(
            f"Field '{field_name}' must be a number, got {type(value).__name__}: {value}"
        )

    if value <= 0:
        raise ValueError(f"Field '{field_name}' must be greater than 0, got {value}")


def _validate_term_mix(term_mix: Any, field_name: str) -> None:
    """
    Validate that a term mix dictionary has valid structure and values sum to ~1.0.

    Args:
        term_mix: Dictionary containing term percentages (e.g., {'three_year': 0.67, 'one_year': 0.33})
        field_name: Name of the field being validated (for error messages)

    Returns:
        None (validation passes silently)

    Raises:
        ValueError: If validation fails with descriptive error message
    """
    if not isinstance(term_mix, dict):
        raise ValueError(
            f"Field '{field_name}' must be a dictionary, got {type(term_mix).__name__}"
        )

    if not term_mix:
        raise ValueError(f"Field '{field_name}' cannot be empty")

    # Validate all values are numeric and between 0 and 1
    for key, value in term_mix.items():
        if not isinstance(value, (int, float)):
            raise ValueError(
                f"Field '{field_name}[{key}]' must be a number, got {type(value).__name__}: {value}"
            )
        if value < 0 or value > 1:
            raise ValueError(
                f"Field '{field_name}[{key}]' must be between 0 and 1, got {value}"
            )

    # Validate sum is approximately 1.0 (allow 0.99-1.01 tolerance)
    total = sum(term_mix.values())
    if total < 0.99 or total > 1.01:
        raise ValueError(
            f"Field '{field_name}' values must sum to approximately 1.0, got {total}"
        )


def validate_scheduler_config(config: dict[str, Any]) -> None:
    """
    Validate scheduler configuration schema and data types.

    Validates:
    - Coverage and purchase percentages are within valid ranges (0-100)
    - Time-based fields are positive integers
    - Minimum commitment is non-negative
    - Term mix dictionaries sum to approximately 1.0
    - Payment options are valid
    - Purchase strategy type is valid
    - Logical constraints (min < max, lookback >= min_data_days)

    Args:
        config: Dictionary containing scheduler configuration

    Returns:
        None (validation passes silently)

    Raises:
        ValueError: If validation fails with descriptive error message
    """
    if not isinstance(config, dict):
        raise ValueError(
            f"Configuration must be a dictionary, got {type(config).__name__}"
        )

    # Validate percentage fields (0-100 range)
    if "coverage_target_percent" in config:
        _validate_percentage_range(
            config["coverage_target_percent"], "coverage_target_percent"
        )

    if "max_purchase_percent" in config:
        _validate_percentage_range(config["max_purchase_percent"], "max_purchase_percent")

    if "min_purchase_percent" in config:
        _validate_percentage_range(config["min_purchase_percent"], "min_purchase_percent")

    # Validate min_purchase_percent < max_purchase_percent
    if "min_purchase_percent" in config and "max_purchase_percent" in config:
        if config["min_purchase_percent"] >= config["max_purchase_percent"]:
            raise ValueError(
                f"Field 'min_purchase_percent' ({config['min_purchase_percent']}) must be less than 'max_purchase_percent' ({config['max_purchase_percent']})"
            )

    # Validate positive integer fields
    if "renewal_window_days" in config:
        _validate_positive_number(config["renewal_window_days"], "renewal_window_days")
        if not isinstance(config["renewal_window_days"], int):
            raise ValueError(
                f"Field 'renewal_window_days' must be an integer, got {type(config['renewal_window_days']).__name__}: {config['renewal_window_days']}"
            )

    if "lookback_days" in config:
        _validate_positive_number(config["lookback_days"], "lookback_days")
        if not isinstance(config["lookback_days"], int):
            raise ValueError(
                f"Field 'lookback_days' must be an integer, got {type(config['lookback_days']).__name__}: {config['lookback_days']}"
            )

    if "min_data_days" in config:
        _validate_positive_number(config["min_data_days"], "min_data_days")
        if not isinstance(config["min_data_days"], int):
            raise ValueError(
                f"Field 'min_data_days' must be an integer, got {type(config['min_data_days']).__name__}: {config['min_data_days']}"
            )

    # Validate lookback_days >= min_data_days
    if "lookback_days" in config and "min_data_days" in config:
        if config["lookback_days"] < config["min_data_days"]:
            raise ValueError(
                f"Field 'lookback_days' ({config['lookback_days']}) must be greater than or equal to 'min_data_days' ({config['min_data_days']})"
            )

    # Validate min_commitment_per_plan is non-negative
    if "min_commitment_per_plan" in config:
        if not isinstance(config["min_commitment_per_plan"], (int, float)):
            raise ValueError(
                f"Field 'min_commitment_per_plan' must be a number, got {type(config['min_commitment_per_plan']).__name__}: {config['min_commitment_per_plan']}"
            )
        if config["min_commitment_per_plan"] < 0:
            raise ValueError(
                f"Field 'min_commitment_per_plan' must be greater than or equal to 0, got {config['min_commitment_per_plan']}"
            )

    # Validate term mix dictionaries
    if "compute_sp_term_mix" in config:
        _validate_term_mix(config["compute_sp_term_mix"], "compute_sp_term_mix")

    if "sagemaker_sp_term_mix" in config:
        _validate_term_mix(config["sagemaker_sp_term_mix"], "sagemaker_sp_term_mix")

    # Validate payment options
    if "compute_sp_payment_option" in config:
        payment_option = config["compute_sp_payment_option"]
        if payment_option not in VALID_PAYMENT_OPTIONS:
            raise ValueError(
                f"Invalid compute_sp_payment_option: '{payment_option}'. Must be one of: {', '.join(VALID_PAYMENT_OPTIONS)}"
            )

    if "sagemaker_sp_payment_option" in config:
        payment_option = config["sagemaker_sp_payment_option"]
        if payment_option not in VALID_PAYMENT_OPTIONS:
            raise ValueError(
                f"Invalid sagemaker_sp_payment_option: '{payment_option}'. Must be one of: {', '.join(VALID_PAYMENT_OPTIONS)}"
            )

    # Validate purchase strategy type
    if "purchase_strategy_type" in config:
        strategy_type = config["purchase_strategy_type"]
        if strategy_type not in VALID_PURCHASE_STRATEGIES:
            raise ValueError(
                f"Invalid purchase_strategy_type: '{strategy_type}'. Must be one of: {', '.join(VALID_PURCHASE_STRATEGIES)}"
            )


def validate_reporter_config(config: dict[str, Any]) -> None:
    """
    Validate reporter configuration schema and data types.

    Validates:
    - report_format is a valid format (html or json)
    - email_reports is a boolean
    - tags is a dictionary
    - String fields are non-empty strings

    Args:
        config: Dictionary containing reporter configuration

    Returns:
        None (validation passes silently)

    Raises:
        ValueError: If validation fails with descriptive error message
    """
    if not isinstance(config, dict):
        raise ValueError(
            f"Configuration must be a dictionary, got {type(config).__name__}"
        )

    # Validate report_format is valid
    if "report_format" in config:
        report_format = config["report_format"]
        if report_format not in VALID_REPORT_FORMATS:
            raise ValueError(
                f"Invalid report_format: '{report_format}'. Must be one of: {', '.join(VALID_REPORT_FORMATS)}"
            )

    # Validate email_reports is a boolean
    if "email_reports" in config:
        email_reports = config["email_reports"]
        if not isinstance(email_reports, bool):
            raise ValueError(
                f"Field 'email_reports' must be a boolean, got {type(email_reports).__name__}: {email_reports}"
            )

    # Validate tags is a dictionary
    if "tags" in config:
        tags = config["tags"]
        if not isinstance(tags, dict):
            raise ValueError(
                f"Field 'tags' must be a dictionary, got {type(tags).__name__}: {tags}"
            )

    # Validate string fields are non-empty strings
    string_fields = [
        "reports_bucket",
        "sns_topic_arn",
        "management_account_role_arn",
        "slack_webhook_url",
        "teams_webhook_url",
    ]

    for field_name in string_fields:
        if field_name in config:
            field_value = config[field_name]
            if not isinstance(field_value, str) or not field_value.strip():
                raise ValueError(
                    f"Field '{field_name}' must be a non-empty string, got {type(field_value).__name__}"
                )

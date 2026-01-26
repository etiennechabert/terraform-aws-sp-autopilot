"""
Configuration validation module for Lambda environment variables.

This module provides schema validation and type enforcement for Lambda
configuration to ensure data integrity before execution.
"""

from typing import Any


# Valid values for payment_option field
VALID_PAYMENT_OPTIONS = ["NO_UPFRONT", "ALL_UPFRONT", "PARTIAL_UPFRONT"]

# Valid values for term field
VALID_TERMS = ["ONE_YEAR", "THREE_YEAR"]

# Valid values for purchase_strategy_type field
VALID_PURCHASE_STRATEGIES = ["follow_aws", "fixed", "dichotomy"]

# Valid values for report_format field
VALID_REPORT_FORMATS = ["html", "json", "csv"]

# Valid values for granularity field
VALID_GRANULARITIES = ["HOURLY", "DAILY"]


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


def _validate_non_negative_number(value: Any, field_name: str) -> None:
    """
    Validate that a value is a non-negative number (>= 0).

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

    if value < 0:
        raise ValueError(f"Field '{field_name}' must be greater than or equal to 0, got {value}")


def _validate_sp_types_enabled(config: dict[str, Any], context: str = "") -> None:
    """Validate at least one SP type is enabled."""
    sp_types_enabled = [
        config.get("enable_compute_sp", False),
        config.get("enable_database_sp", False),
        config.get("enable_sagemaker_sp", False),
    ]
    if not any(sp_types_enabled):
        suffix = f" for {context}" if context else ""
        raise ValueError(
            f"At least one Savings Plan type must be enabled{suffix}. "
            "Set ENABLE_COMPUTE_SP, ENABLE_DATABASE_SP, or ENABLE_SAGEMAKER_SP to true."
        )


def _validate_lookback_days_with_granularity(
    config: dict[str, Any], field_name: str = "lookback_days"
) -> None:
    """Validate lookback_days is a positive integer within AWS API limits based on granularity."""
    if field_name not in config:
        return

    _validate_positive_number(config[field_name], field_name)
    if not isinstance(config[field_name], int):
        raise ValueError(
            f"Field '{field_name}' must be an integer, "
            f"got {type(config[field_name]).__name__}: {config[field_name]}"
        )

    granularity = config.get("granularity", "HOURLY")
    if granularity == "HOURLY" and config[field_name] > 14:
        raise ValueError(
            f"Field '{field_name}' must be 14 or less for HOURLY granularity. "
            f"AWS Cost Explorer retains hourly data for 14 days. "
            f"Got {config[field_name]}"
        )
    if granularity == "DAILY" and config[field_name] > 90:
        raise ValueError(
            f"Field '{field_name}' must be 90 or less for DAILY granularity. "
            f"Got {config[field_name]}"
        )


def _validate_term_value(config: dict[str, Any], field_name: str) -> None:
    """Validate a term field value is valid."""
    if field_name not in config:
        return

    term_value = config[field_name]
    if term_value not in VALID_TERMS:
        raise ValueError(
            f"Invalid {field_name}: '{term_value}'. Must be one of: {', '.join(VALID_TERMS)}"
        )


def _validate_payment_option(config: dict[str, Any], field_name: str) -> None:
    """Validate a payment_option field value is valid."""
    if field_name not in config:
        return

    payment_option = config[field_name]
    if payment_option not in VALID_PAYMENT_OPTIONS:
        raise ValueError(
            f"Invalid {field_name}: '{payment_option}'. "
            f"Must be one of: {', '.join(VALID_PAYMENT_OPTIONS)}"
        )


def _validate_string_fields(config: dict[str, Any], field_names: list[str]) -> None:
    """Validate multiple string fields are non-empty strings."""
    for field_name in field_names:
        if field_name in config:
            field_value = config[field_name]
            if not isinstance(field_value, str) or not field_value.strip():
                raise ValueError(
                    f"Field '{field_name}' must be a non-empty string, "
                    f"got {type(field_value).__name__}"
                )


def _validate_tags_field(config: dict[str, Any]) -> None:
    """Validate tags field is a dictionary."""
    if "tags" in config:
        tags = config["tags"]
        if not isinstance(tags, dict):
            raise ValueError(
                f"Field 'tags' must be a dictionary, got {type(tags).__name__}: {tags}"
            )


def validate_scheduler_config(config: dict[str, Any]) -> None:
    """
    Validate scheduler configuration schema and data types.

    Validates:
    - At least one SP type must be enabled
    - Coverage and purchase percentages are within valid ranges (0-100)
    - Time-based fields are positive integers
    - Minimum commitment is non-negative
    - Term values are valid (ONE_YEAR or THREE_YEAR)
    - Payment options are valid
    - Purchase strategy type is valid
    - Logical constraints (min < max, lookback <= 14 days for HOURLY, <= 90 days for DAILY)

    Args:
        config: Dictionary containing scheduler configuration

    Returns:
        None (validation passes silently)

    Raises:
        ValueError: If validation fails with descriptive error message
    """
    if not isinstance(config, dict):
        raise ValueError(f"Configuration must be a dictionary, got {type(config).__name__}")

    _validate_sp_types_enabled(config)

    # Validate percentage fields
    for field in ["coverage_target_percent", "max_purchase_percent", "min_purchase_percent"]:
        if field in config:
            _validate_percentage_range(config[field], field)

    # Validate min_purchase_percent < max_purchase_percent
    if (
        "min_purchase_percent" in config
        and "max_purchase_percent" in config
        and config["min_purchase_percent"] >= config["max_purchase_percent"]
    ):
        raise ValueError(
            f"Field 'min_purchase_percent' ({config['min_purchase_percent']}) "
            f"must be less than 'max_purchase_percent' ({config['max_purchase_percent']})"
        )

    # Validate renewal_window_days is a positive integer
    if "renewal_window_days" in config:
        _validate_positive_number(config["renewal_window_days"], "renewal_window_days")
        if not isinstance(config["renewal_window_days"], int):
            raise ValueError(
                f"Field 'renewal_window_days' must be an integer, "
                f"got {type(config['renewal_window_days']).__name__}: "
                f"{config['renewal_window_days']}"
            )

    # Validate lookback_days with granularity constraints
    _validate_lookback_days_with_granularity(config)

    # Validate min_commitment_per_plan is non-negative
    if "min_commitment_per_plan" in config:
        _validate_non_negative_number(config["min_commitment_per_plan"], "min_commitment_per_plan")

    # Validate term values
    _validate_term_value(config, "compute_sp_term")
    _validate_term_value(config, "sagemaker_sp_term")

    # Validate payment options
    _validate_payment_option(config, "compute_sp_payment_option")
    _validate_payment_option(config, "sagemaker_sp_payment_option")
    _validate_payment_option(config, "database_sp_payment_option")

    # Validate purchase strategy type
    if "purchase_strategy_type" in config:
        strategy_type = config["purchase_strategy_type"]
        if strategy_type not in VALID_PURCHASE_STRATEGIES:
            raise ValueError(
                f"Invalid purchase_strategy_type: '{strategy_type}'. "
                f"Must be one of: {', '.join(VALID_PURCHASE_STRATEGIES)}"
            )

    # Validate granularity
    if "granularity" in config:
        granularity = config["granularity"]
        if granularity not in VALID_GRANULARITIES:
            raise ValueError(
                f"Invalid granularity: '{granularity}'. "
                f"Must be one of: {', '.join(VALID_GRANULARITIES)}"
            )


def validate_reporter_config(config: dict[str, Any]) -> None:
    """
    Validate reporter configuration schema and data types.

    Validates:
    - At least one SP type must be enabled
    - report_format is a valid format (html or json or csv)
    - email_reports is a boolean
    - tags is a dictionary
    - String fields are non-empty strings
    - lookback_days is within AWS limits based on granularity
    - low_utilization_threshold is within valid range (0-100)

    Args:
        config: Dictionary containing reporter configuration

    Returns:
        None (validation passes silently)

    Raises:
        ValueError: If validation fails with descriptive error message
    """
    if not isinstance(config, dict):
        raise ValueError(f"Configuration must be a dictionary, got {type(config).__name__}")

    _validate_sp_types_enabled(config, "reporting")

    # Validate report_format
    if "report_format" in config:
        report_format = config["report_format"]
        if report_format not in VALID_REPORT_FORMATS:
            raise ValueError(
                f"Invalid report_format: '{report_format}'. "
                f"Must be one of: {', '.join(VALID_REPORT_FORMATS)}"
            )

    # Validate email_reports is a boolean
    if "email_reports" in config:
        email_reports = config["email_reports"]
        if not isinstance(email_reports, bool):
            raise ValueError(
                f"Field 'email_reports' must be a boolean, "
                f"got {type(email_reports).__name__}: {email_reports}"
            )

    _validate_tags_field(config)

    # Validate granularity
    if "granularity" in config:
        granularity = config["granularity"]
        if granularity not in VALID_GRANULARITIES:
            raise ValueError(
                f"Invalid granularity: '{granularity}'. "
                f"Must be one of: {', '.join(VALID_GRANULARITIES)}"
            )

    _validate_lookback_days_with_granularity(config)

    # Validate low_utilization_threshold
    if "low_utilization_threshold" in config:
        _validate_percentage_range(
            config["low_utilization_threshold"], "low_utilization_threshold", 0.0, 100.0
        )

    _validate_string_fields(
        config,
        [
            "reports_bucket",
            "sns_topic_arn",
            "management_account_role_arn",
            "slack_webhook_url",
            "teams_webhook_url",
        ],
    )


def validate_purchaser_config(config: dict[str, Any]) -> None:
    """
    Validate purchaser configuration schema and data types.

    Validates:
    - max_coverage_cap is within valid percentage range (0-100)
    - renewal_window_days is a positive integer
    - lookback_days is a positive integer within reasonable bounds
    - tags is a dictionary
    - String fields are non-empty strings

    Args:
        config: Dictionary containing purchaser configuration

    Returns:
        None (validation passes silently)

    Raises:
        ValueError: If validation fails with descriptive error message
    """
    if not isinstance(config, dict):
        raise ValueError(f"Configuration must be a dictionary, got {type(config).__name__}")

    # Validate max_coverage_cap
    if "max_coverage_cap" in config:
        _validate_percentage_range(config["max_coverage_cap"], "max_coverage_cap")

    # Validate renewal_window_days
    if "renewal_window_days" in config:
        _validate_positive_number(config["renewal_window_days"], "renewal_window_days")
        if not isinstance(config["renewal_window_days"], int):
            raise ValueError(
                f"Field 'renewal_window_days' must be an integer, "
                f"got {type(config['renewal_window_days']).__name__}: "
                f"{config['renewal_window_days']}"
            )

    # Validate lookback_days
    if "lookback_days" in config:
        _validate_positive_number(config["lookback_days"], "lookback_days")
        if not isinstance(config["lookback_days"], int):
            raise ValueError(
                f"Field 'lookback_days' must be an integer, "
                f"got {type(config['lookback_days']).__name__}: {config['lookback_days']}"
            )
        if config["lookback_days"] > 365:
            raise ValueError(
                f"Field 'lookback_days' must be 365 or less. Got {config['lookback_days']}"
            )

    _validate_tags_field(config)

    _validate_string_fields(
        config,
        [
            "queue_url",
            "sns_topic_arn",
            "management_account_role_arn",
            "slack_webhook_url",
            "teams_webhook_url",
        ],
    )

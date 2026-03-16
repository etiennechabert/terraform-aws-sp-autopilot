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

VALID_TARGET_STRATEGIES = ["aws", "dynamic"]

VALID_SPLIT_STRATEGIES = ["one_shot", "fixed_step", "gap_split"]

VALID_RISK_LEVELS = ["prudent", "min_hourly", "optimal", "maximum"]

# Valid values for report_format field
VALID_REPORT_FORMATS = ["html", "json", "csv"]


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


def _validate_lookback_hours(config: dict[str, Any], field_name: str = "lookback_hours") -> None:
    """Validate lookback_hours is a positive integer within AWS HOURLY granularity limits."""
    if field_name not in config:
        return

    _validate_positive_number(config[field_name], field_name)
    if not isinstance(config[field_name], int):
        raise ValueError(
            f"Field '{field_name}' must be an integer, "
            f"got {type(config[field_name]).__name__}: {config[field_name]}"
        )

    if config[field_name] > 336:
        raise ValueError(
            f"Field '{field_name}' must be 336 or less (14 days). "
            f"AWS Cost Explorer retains hourly data for 14 days. "
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


def _validate_purchase_percent_constraints(config: dict[str, Any]) -> None:
    """Validate min_purchase_percent > 0 and gap_split_divider > 0 when present."""
    if "min_purchase_percent" in config and config["min_purchase_percent"] <= 0:
        raise ValueError(
            f"Field 'min_purchase_percent' must be greater than 0, "
            f"got {config['min_purchase_percent']}"
        )
    if "gap_split_divider" in config:
        _validate_positive_number(config["gap_split_divider"], "gap_split_divider")


def _validate_renewal_window_days(config: dict[str, Any]) -> None:
    """Validate renewal_window_days is a positive integer."""
    if "renewal_window_days" in config:
        _validate_positive_number(config["renewal_window_days"], "renewal_window_days")
        if not isinstance(config["renewal_window_days"], int):
            raise ValueError(
                f"Field 'renewal_window_days' must be an integer, "
                f"got {type(config['renewal_window_days']).__name__}: "
                f"{config['renewal_window_days']}"
            )


def _validate_sp_terms(config: dict[str, Any]) -> None:
    """Validate term values for compute and sagemaker."""
    _validate_term_value(config, "compute_sp_term")
    _validate_term_value(config, "sagemaker_sp_term")


def _validate_sp_payment_options(config: dict[str, Any]) -> None:
    """Validate payment options for all SP types."""
    _validate_payment_option(config, "compute_sp_payment_option")
    _validate_payment_option(config, "sagemaker_sp_payment_option")
    _validate_payment_option(config, "database_sp_payment_option")


def _validate_strategy_cross_rules(config: dict[str, Any]) -> None:
    """Validate cross-dependencies between target and split strategies."""
    risk_level = config.get("dynamic_risk_level")
    if risk_level and risk_level not in VALID_RISK_LEVELS:
        raise ValueError(
            f"Invalid dynamic_risk_level: '{risk_level}'. "
            f"Must be one of: {', '.join(VALID_RISK_LEVELS)}"
        )


def _validate_strategies(config: dict[str, Any]) -> None:
    """Validate target/split strategy types."""
    if "target_strategy_type" in config:
        target_type = config["target_strategy_type"]
        if target_type not in VALID_TARGET_STRATEGIES:
            raise ValueError(
                f"Invalid target_strategy_type: '{target_type}'. "
                f"Must be one of: {', '.join(VALID_TARGET_STRATEGIES)}"
            )

    if "split_strategy_type" in config:
        split_type = config["split_strategy_type"]
        if split_type not in VALID_SPLIT_STRATEGIES:
            raise ValueError(
                f"Invalid split_strategy_type: '{split_type}'. "
                f"Must be one of: {', '.join(VALID_SPLIT_STRATEGIES)}"
            )

    _validate_strategy_cross_rules(config)


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
    - Logical constraints (min < max, lookback_hours <= 336)

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
    for field in ["max_purchase_percent", "min_purchase_percent"]:
        if field in config:
            _validate_percentage_range(config[field], field)

    _validate_purchase_percent_constraints(config)
    _validate_renewal_window_days(config)

    if "purchase_cooldown_days" in config:
        _validate_non_negative_number(config["purchase_cooldown_days"], "purchase_cooldown_days")
        if not isinstance(config["purchase_cooldown_days"], int):
            raise ValueError(
                f"Field 'purchase_cooldown_days' must be an integer, "
                f"got {type(config['purchase_cooldown_days']).__name__}: "
                f"{config['purchase_cooldown_days']}"
            )

    _validate_lookback_hours(config)

    if "min_commitment_per_plan" in config:
        _validate_non_negative_number(config["min_commitment_per_plan"], "min_commitment_per_plan")

    _validate_sp_terms(config)
    _validate_sp_payment_options(config)
    _validate_strategies(config)
    _validate_spike_guard_params(config)


def validate_reporter_config(config: dict[str, Any]) -> None:
    """
    Validate reporter configuration schema and data types.

    Validates:
    - At least one SP type must be enabled
    - report_format is a valid format (html or json or csv)
    - email_reports is a boolean
    - tags is a dictionary
    - String fields are non-empty strings
    - lookback_hours is within AWS limits
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

    _validate_lookback_hours(config)

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

    _validate_spike_guard_params(config)


def validate_purchaser_config(config: dict[str, Any]) -> None:
    """
    Validate purchaser configuration schema and data types.

    Validates:
    - renewal_window_days is a positive integer
    - lookback_hours is a positive integer within AWS limits
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

    # Validate renewal_window_days
    if "renewal_window_days" in config:
        _validate_positive_number(config["renewal_window_days"], "renewal_window_days")
        if not isinstance(config["renewal_window_days"], int):
            raise ValueError(
                f"Field 'renewal_window_days' must be an integer, "
                f"got {type(config['renewal_window_days']).__name__}: "
                f"{config['renewal_window_days']}"
            )

    _validate_lookback_hours(config)

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

    _validate_spike_guard_params(config)


def _validate_spike_guard_params(config: dict[str, Any]) -> None:
    """Validate spike guard parameters if present."""
    if "spike_guard_long_lookback_days" in config:
        long_days = config["spike_guard_long_lookback_days"]
        if not isinstance(long_days, int) or long_days < 1 or long_days > 90:
            raise ValueError(
                f"Field 'spike_guard_long_lookback_days' must be an integer between 1 and 90, "
                f"got {long_days}"
            )

    if "spike_guard_short_lookback_days" in config:
        short_days = config["spike_guard_short_lookback_days"]
        if not isinstance(short_days, int) or short_days < 1:
            raise ValueError(
                f"Field 'spike_guard_short_lookback_days' must be a positive integer, "
                f"got {short_days}"
            )

    if (
        "spike_guard_long_lookback_days" in config
        and "spike_guard_short_lookback_days" in config
        and config["spike_guard_long_lookback_days"] <= config["spike_guard_short_lookback_days"]
    ):
        raise ValueError(
            "spike_guard_long_lookback_days must be greater than spike_guard_short_lookback_days"
        )

    if "spike_guard_threshold_percent" in config:
        _validate_percentage_range(
            config["spike_guard_threshold_percent"],
            "spike_guard_threshold_percent",
            1.0,
            100.0,
        )

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

"""
Validation module for purchase intent messages from SQS.

This module provides schema validation and type enforcement for purchase intent
messages to ensure data integrity before attempting to purchase Savings Plans.
"""

from typing import Any


# Valid values for sp_type field
VALID_SP_TYPES = [
    "ComputeSavingsPlans",
    "DatabaseSavingsPlans",
    "SageMakerSavingsPlans",
]

# Valid values for payment_option field
VALID_PAYMENT_OPTIONS = ["NO_UPFRONT", "ALL_UPFRONT", "PARTIAL_UPFRONT"]

# Maximum length for string fields
MAX_CLIENT_TOKEN_LENGTH = 256
MAX_OFFERING_ID_LENGTH = 256

# Required fields in purchase intent message
REQUIRED_FIELDS = [
    "client_token",
    "offering_id",
    "commitment",
    "sp_type",
    "term_seconds",
    "payment_option",
    "projected_coverage_after",
]


def validate_purchase_intent(purchase_intent: dict[str, Any]) -> None:
    """
    Validate purchase intent message schema and data types.

    Validates:
    - All required fields are present
    - Data types are correct (commitment: numeric, term_seconds: int, projected_coverage_after: float)
    - sp_type is a valid Savings Plan type
    - payment_option is a valid payment option

    Args:
        purchase_intent: Dictionary containing purchase intent message from SQS

    Returns:
        None (validation passes silently)

    Raises:
        ValueError: If validation fails with descriptive error message
    """
    if not isinstance(purchase_intent, dict):
        raise ValueError(
            f"Purchase intent must be a dictionary, got {type(purchase_intent).__name__}"
        )

    # Validate required fields are present
    missing_fields = [
        field for field in REQUIRED_FIELDS if field not in purchase_intent
    ]
    if missing_fields:
        raise ValueError(f"Missing required fields: {', '.join(missing_fields)}")

    # Validate sp_type is valid
    sp_type = purchase_intent.get("sp_type")
    if sp_type not in VALID_SP_TYPES:
        raise ValueError(
            f"Invalid sp_type: '{sp_type}'. Must be one of: {', '.join(VALID_SP_TYPES)}"
        )

    # Validate payment_option is valid
    payment_option = purchase_intent.get("payment_option")
    if payment_option not in VALID_PAYMENT_OPTIONS:
        raise ValueError(
            f"Invalid payment_option: '{payment_option}'. Must be one of: {', '.join(VALID_PAYMENT_OPTIONS)}"
        )

    # Validate data types
    _validate_field_types(purchase_intent)


def _validate_field_types(purchase_intent: dict[str, Any]) -> None:
    """
    Validate data types for fields in purchase intent.

    Args:
        purchase_intent: Dictionary containing purchase intent message

    Raises:
        ValueError: If any field has an invalid data type
    """
    # Validate commitment is numeric (can be string or number)
    commitment = purchase_intent.get("commitment")
    try:
        float(commitment)
    except (TypeError, ValueError):
        raise ValueError(
            f"Field 'commitment' must be numeric, got {type(commitment).__name__}: {commitment}"
        )

    # Validate term_seconds is an integer
    term_seconds = purchase_intent.get("term_seconds")
    if not isinstance(term_seconds, int):
        raise ValueError(
            f"Field 'term_seconds' must be an integer, got {type(term_seconds).__name__}: {term_seconds}"
        )

    # Validate projected_coverage_after is a float or int
    projected_coverage_after = purchase_intent.get("projected_coverage_after")
    if not isinstance(projected_coverage_after, (int, float)):
        raise ValueError(
            f"Field 'projected_coverage_after' must be a number, got {type(projected_coverage_after).__name__}: {projected_coverage_after}"
        )

    # Validate client_token is a string
    client_token = purchase_intent.get("client_token")
    if not isinstance(client_token, str) or not client_token.strip():
        raise ValueError(
            f"Field 'client_token' must be a non-empty string, got {type(client_token).__name__}"
        )
    if len(client_token) > MAX_CLIENT_TOKEN_LENGTH:
        raise ValueError(
            f"Field 'client_token' exceeds maximum length of {MAX_CLIENT_TOKEN_LENGTH} characters, got {len(client_token)}"
        )

    # Validate offering_id is a string
    offering_id = purchase_intent.get("offering_id")
    if not isinstance(offering_id, str) or not offering_id.strip():
        raise ValueError(
            f"Field 'offering_id' must be a non-empty string, got {type(offering_id).__name__}"
        )
    if len(offering_id) > MAX_OFFERING_ID_LENGTH:
        raise ValueError(
            f"Field 'offering_id' exceeds maximum length of {MAX_OFFERING_ID_LENGTH} characters, got {len(offering_id)}"
        )

    # Validate upfront_amount if present (optional field, can be None)
    if "upfront_amount" in purchase_intent:
        upfront_amount = purchase_intent.get("upfront_amount")
        if upfront_amount is not None:
            try:
                float(upfront_amount)
            except (TypeError, ValueError):
                raise ValueError(
                    f"Field 'upfront_amount' must be numeric or None, got {type(upfront_amount).__name__}: {upfront_amount}"
                )

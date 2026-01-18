"""
Essential validation tests for Purchaser Lambda.
Tests critical validation logic and error paths.
"""

import pytest
from validation import validate_purchase_intent


def test_valid_purchase_intent():
    """Test that a valid purchase intent passes validation."""
    purchase_intent = {
        "client_token": "test-token-123",
        "offering_id": "offering-abc-456",
        "commitment": "10.50",
        "sp_type": "ComputeSavingsPlans",
        "term_seconds": 94608000,
        "payment_option": "NO_UPFRONT",
        "projected_coverage_after": 85.5,
    }
    validate_purchase_intent(purchase_intent)


def test_missing_required_field():
    """Test that missing required field raises ValueError."""
    purchase_intent = {
        "client_token": "test-token-123",
        "offering_id": "offering-abc-456",
        "commitment": "10.50",
        "sp_type": "ComputeSavingsPlans",
        "term_seconds": 94608000,
        # Missing: payment_option
        "projected_coverage_after": 85.5,
    }
    with pytest.raises(ValueError, match="Missing required fields"):
        validate_purchase_intent(purchase_intent)


def test_invalid_sp_type():
    """Test that invalid SP type raises ValueError."""
    purchase_intent = {
        "client_token": "test-token-123",
        "offering_id": "offering-abc-456",
        "commitment": "10.50",
        "sp_type": "InvalidType",
        "term_seconds": 94608000,
        "payment_option": "NO_UPFRONT",
        "projected_coverage_after": 85.5,
    }
    with pytest.raises(ValueError, match="Invalid sp_type"):
        validate_purchase_intent(purchase_intent)


def test_invalid_payment_option():
    """Test that invalid payment option raises ValueError."""
    purchase_intent = {
        "client_token": "test-token-123",
        "offering_id": "offering-abc-456",
        "commitment": "10.50",
        "sp_type": "ComputeSavingsPlans",
        "term_seconds": 94608000,
        "payment_option": "INVALID_OPTION",
        "projected_coverage_after": 85.5,
    }
    with pytest.raises(ValueError, match="Invalid payment_option"):
        validate_purchase_intent(purchase_intent)


def test_empty_client_token():
    """Test that empty client token raises ValueError."""
    purchase_intent = {
        "client_token": "",
        "offering_id": "offering-abc-456",
        "commitment": "10.50",
        "sp_type": "ComputeSavingsPlans",
        "term_seconds": 94608000,
        "payment_option": "NO_UPFRONT",
        "projected_coverage_after": 85.5,
    }
    with pytest.raises(ValueError, match=r"client_token.*non-empty string"):
        validate_purchase_intent(purchase_intent)


def test_invalid_commitment_type():
    """Test that invalid commitment type raises ValueError."""
    purchase_intent = {
        "client_token": "test-token-123",
        "offering_id": "offering-abc-456",
        "commitment": None,
        "sp_type": "ComputeSavingsPlans",
        "term_seconds": 94608000,
        "payment_option": "NO_UPFRONT",
        "projected_coverage_after": 85.5,
    }
    with pytest.raises(ValueError, match="Field 'commitment' must be numeric"):
        validate_purchase_intent(purchase_intent)


def test_purchase_intent_not_dict():
    """Test that non-dict purchase intent raises ValueError."""
    with pytest.raises(ValueError, match="must be a dictionary"):
        validate_purchase_intent("not a dict")


def test_invalid_term_seconds_type():
    """Test that invalid term_seconds type raises ValueError."""
    purchase_intent = {
        "client_token": "test-token-123",
        "offering_id": "offering-abc-456",
        "commitment": "10.50",
        "sp_type": "ComputeSavingsPlans",
        "term_seconds": "94608000",  # String instead of int
        "payment_option": "NO_UPFRONT",
        "projected_coverage_after": 85.5,
    }
    with pytest.raises(ValueError, match=r"term_seconds.*must be an integer"):
        validate_purchase_intent(purchase_intent)


def test_invalid_projected_coverage_type():
    """Test that invalid projected_coverage_after type raises ValueError."""
    purchase_intent = {
        "client_token": "test-token-123",
        "offering_id": "offering-abc-456",
        "commitment": "10.50",
        "sp_type": "ComputeSavingsPlans",
        "term_seconds": 94608000,
        "payment_option": "NO_UPFRONT",
        "projected_coverage_after": "85.5",  # String instead of number
    }
    with pytest.raises(ValueError, match=r"projected_coverage_after.*must be a number"):
        validate_purchase_intent(purchase_intent)


def test_empty_offering_id():
    """Test that empty offering_id raises ValueError."""
    purchase_intent = {
        "client_token": "test-token-123",
        "offering_id": "",
        "commitment": "10.50",
        "sp_type": "ComputeSavingsPlans",
        "term_seconds": 94608000,
        "payment_option": "NO_UPFRONT",
        "projected_coverage_after": 85.5,
    }
    with pytest.raises(ValueError, match=r"offering_id.*non-empty string"):
        validate_purchase_intent(purchase_intent)


def test_invalid_upfront_amount():
    """Test that invalid upfront_amount raises ValueError."""
    purchase_intent = {
        "client_token": "test-token-123",
        "offering_id": "offering-abc-456",
        "commitment": "10.50",
        "sp_type": "ComputeSavingsPlans",
        "term_seconds": 94608000,
        "payment_option": "ALL_UPFRONT",
        "projected_coverage_after": 85.5,
        "upfront_amount": "invalid",  # Invalid type
    }
    with pytest.raises(ValueError, match=r"upfront_amount.*must be numeric"):
        validate_purchase_intent(purchase_intent)


def test_client_token_too_long():
    """Test that client_token exceeding maximum length raises ValueError."""
    purchase_intent = {
        "client_token": "a" * 257,  # Exceeds 256 character limit
        "offering_id": "offering-abc-456",
        "commitment": "10.50",
        "sp_type": "ComputeSavingsPlans",
        "term_seconds": 94608000,
        "payment_option": "NO_UPFRONT",
        "projected_coverage_after": 85.5,
    }
    with pytest.raises(ValueError, match=r"client_token.*exceeds maximum length"):
        validate_purchase_intent(purchase_intent)


def test_offering_id_too_long():
    """Test that offering_id exceeding maximum length raises ValueError."""
    purchase_intent = {
        "client_token": "test-token-123",
        "offering_id": "a" * 257,  # Exceeds 256 character limit
        "commitment": "10.50",
        "sp_type": "ComputeSavingsPlans",
        "term_seconds": 94608000,
        "payment_option": "NO_UPFRONT",
        "projected_coverage_after": 85.5,
    }
    with pytest.raises(ValueError, match=r"offering_id.*exceeds maximum length"):
        validate_purchase_intent(purchase_intent)

"""
Unit tests for validation module - Purchase Intent schema validation.
"""

import os
import sys

import pytest


# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from validation import VALID_PAYMENT_OPTIONS, VALID_SP_TYPES, validate_purchase_intent


def test_valid_purchase_intent_passes():
    """Test that a valid purchase intent passes validation."""
    purchase_intent = {
        'client_token': 'test-token-123',
        'offering_id': 'offering-abc-456',
        'commitment': '10.50',
        'sp_type': 'ComputeSavingsPlans',
        'term_seconds': 94608000,
        'payment_option': 'NO_UPFRONT',
        'projected_coverage_after': 85.5
    }

    # Should not raise any exception
    validate_purchase_intent(purchase_intent)


def test_valid_purchase_intent_with_numeric_commitment():
    """Test that numeric commitment (not string) is accepted."""
    purchase_intent = {
        'client_token': 'test-token-123',
        'offering_id': 'offering-abc-456',
        'commitment': 10.50,
        'sp_type': 'DatabaseSavingsPlans',
        'term_seconds': 31536000,
        'payment_option': 'ALL_UPFRONT',
        'projected_coverage_after': 90.0
    }

    # Should not raise any exception
    validate_purchase_intent(purchase_intent)


def test_valid_purchase_intent_with_upfront_amount():
    """Test that upfront_amount field is allowed (optional)."""
    purchase_intent = {
        'client_token': 'test-token-123',
        'offering_id': 'offering-abc-456',
        'commitment': '10.50',
        'sp_type': 'ComputeSavingsPlans',
        'term_seconds': 94608000,
        'payment_option': 'PARTIAL_UPFRONT',
        'projected_coverage_after': 85.5,
        'upfront_amount': '500.00'
    }

    # Should not raise any exception
    validate_purchase_intent(purchase_intent)


def test_upfront_amount_none_is_allowed():
    """Test that upfront_amount=None is explicitly allowed."""
    purchase_intent = {
        'client_token': 'test-token-123',
        'offering_id': 'offering-abc-456',
        'commitment': '10.50',
        'sp_type': 'ComputeSavingsPlans',
        'term_seconds': 94608000,
        'payment_option': 'NO_UPFRONT',
        'projected_coverage_after': 85.5,
        'upfront_amount': None
    }

    # Should not raise any exception
    validate_purchase_intent(purchase_intent)


def test_missing_single_required_field():
    """Test that missing a single required field raises ValueError."""
    purchase_intent = {
        'client_token': 'test-token-123',
        'offering_id': 'offering-abc-456',
        'commitment': '10.50',
        'sp_type': 'ComputeSavingsPlans',
        'term_seconds': 94608000,
        # Missing: payment_option
        'projected_coverage_after': 85.5
    }

    with pytest.raises(ValueError) as exc_info:
        validate_purchase_intent(purchase_intent)

    assert 'Missing required fields: payment_option' in str(exc_info.value)


def test_missing_multiple_required_fields():
    """Test that missing multiple required fields raises ValueError with all missing fields."""
    purchase_intent = {
        'client_token': 'test-token-123',
        # Missing: offering_id, commitment, sp_type, term_seconds, payment_option, projected_coverage_after
    }

    with pytest.raises(ValueError) as exc_info:
        validate_purchase_intent(purchase_intent)

    error_msg = str(exc_info.value)
    assert 'Missing required fields:' in error_msg
    assert 'offering_id' in error_msg
    assert 'commitment' in error_msg
    assert 'sp_type' in error_msg
    assert 'term_seconds' in error_msg
    assert 'payment_option' in error_msg
    assert 'projected_coverage_after' in error_msg


def test_invalid_sp_type():
    """Test that invalid sp_type raises ValueError."""
    purchase_intent = {
        'client_token': 'test-token-123',
        'offering_id': 'offering-abc-456',
        'commitment': '10.50',
        'sp_type': 'InvalidSavingsPlans',
        'term_seconds': 94608000,
        'payment_option': 'NO_UPFRONT',
        'projected_coverage_after': 85.5
    }

    with pytest.raises(ValueError) as exc_info:
        validate_purchase_intent(purchase_intent)

    error_msg = str(exc_info.value)
    assert "Invalid sp_type: 'InvalidSavingsPlans'" in error_msg
    assert 'ComputeSavingsPlans' in error_msg
    assert 'DatabaseSavingsPlans' in error_msg


def test_invalid_payment_option():
    """Test that invalid payment_option raises ValueError."""
    purchase_intent = {
        'client_token': 'test-token-123',
        'offering_id': 'offering-abc-456',
        'commitment': '10.50',
        'sp_type': 'ComputeSavingsPlans',
        'term_seconds': 94608000,
        'payment_option': 'INVALID_UPFRONT',
        'projected_coverage_after': 85.5
    }

    with pytest.raises(ValueError) as exc_info:
        validate_purchase_intent(purchase_intent)

    error_msg = str(exc_info.value)
    assert "Invalid payment_option: 'INVALID_UPFRONT'" in error_msg
    assert 'NO_UPFRONT' in error_msg
    assert 'ALL_UPFRONT' in error_msg
    assert 'PARTIAL_UPFRONT' in error_msg


def test_commitment_invalid_type():
    """Test that non-numeric commitment raises ValueError."""
    purchase_intent = {
        'client_token': 'test-token-123',
        'offering_id': 'offering-abc-456',
        'commitment': 'not-a-number',
        'sp_type': 'ComputeSavingsPlans',
        'term_seconds': 94608000,
        'payment_option': 'NO_UPFRONT',
        'projected_coverage_after': 85.5
    }

    with pytest.raises(ValueError) as exc_info:
        validate_purchase_intent(purchase_intent)

    assert "Field 'commitment' must be numeric" in str(exc_info.value)


def test_term_seconds_invalid_type():
    """Test that non-integer term_seconds raises ValueError."""
    purchase_intent = {
        'client_token': 'test-token-123',
        'offering_id': 'offering-abc-456',
        'commitment': '10.50',
        'sp_type': 'ComputeSavingsPlans',
        'term_seconds': '94608000',  # String instead of int
        'payment_option': 'NO_UPFRONT',
        'projected_coverage_after': 85.5
    }

    with pytest.raises(ValueError) as exc_info:
        validate_purchase_intent(purchase_intent)

    assert "Field 'term_seconds' must be an integer" in str(exc_info.value)


def test_projected_coverage_after_invalid_type():
    """Test that non-numeric projected_coverage_after raises ValueError."""
    purchase_intent = {
        'client_token': 'test-token-123',
        'offering_id': 'offering-abc-456',
        'commitment': '10.50',
        'sp_type': 'ComputeSavingsPlans',
        'term_seconds': 94608000,
        'payment_option': 'NO_UPFRONT',
        'projected_coverage_after': 'not-a-number'
    }

    with pytest.raises(ValueError) as exc_info:
        validate_purchase_intent(purchase_intent)

    assert "Field 'projected_coverage_after' must be a number" in str(exc_info.value)


def test_client_token_empty_string():
    """Test that empty client_token raises ValueError."""
    purchase_intent = {
        'client_token': '',
        'offering_id': 'offering-abc-456',
        'commitment': '10.50',
        'sp_type': 'ComputeSavingsPlans',
        'term_seconds': 94608000,
        'payment_option': 'NO_UPFRONT',
        'projected_coverage_after': 85.5
    }

    with pytest.raises(ValueError) as exc_info:
        validate_purchase_intent(purchase_intent)

    assert "Field 'client_token' must be a non-empty string" in str(exc_info.value)


def test_client_token_whitespace_only():
    """Test that whitespace-only client_token raises ValueError."""
    purchase_intent = {
        'client_token': '   ',
        'offering_id': 'offering-abc-456',
        'commitment': '10.50',
        'sp_type': 'ComputeSavingsPlans',
        'term_seconds': 94608000,
        'payment_option': 'NO_UPFRONT',
        'projected_coverage_after': 85.5
    }

    with pytest.raises(ValueError) as exc_info:
        validate_purchase_intent(purchase_intent)

    assert "Field 'client_token' must be a non-empty string" in str(exc_info.value)


def test_client_token_wrong_type():
    """Test that non-string client_token raises ValueError."""
    purchase_intent = {
        'client_token': 12345,
        'offering_id': 'offering-abc-456',
        'commitment': '10.50',
        'sp_type': 'ComputeSavingsPlans',
        'term_seconds': 94608000,
        'payment_option': 'NO_UPFRONT',
        'projected_coverage_after': 85.5
    }

    with pytest.raises(ValueError) as exc_info:
        validate_purchase_intent(purchase_intent)

    assert "Field 'client_token' must be a non-empty string" in str(exc_info.value)


def test_offering_id_empty_string():
    """Test that empty offering_id raises ValueError."""
    purchase_intent = {
        'client_token': 'test-token-123',
        'offering_id': '',
        'commitment': '10.50',
        'sp_type': 'ComputeSavingsPlans',
        'term_seconds': 94608000,
        'payment_option': 'NO_UPFRONT',
        'projected_coverage_after': 85.5
    }

    with pytest.raises(ValueError) as exc_info:
        validate_purchase_intent(purchase_intent)

    assert "Field 'offering_id' must be a non-empty string" in str(exc_info.value)


def test_offering_id_wrong_type():
    """Test that non-string offering_id raises ValueError."""
    purchase_intent = {
        'client_token': 'test-token-123',
        'offering_id': None,
        'commitment': '10.50',
        'sp_type': 'ComputeSavingsPlans',
        'term_seconds': 94608000,
        'payment_option': 'NO_UPFRONT',
        'projected_coverage_after': 85.5
    }

    with pytest.raises(ValueError) as exc_info:
        validate_purchase_intent(purchase_intent)

    assert "Field 'offering_id' must be a non-empty string" in str(exc_info.value)


def test_upfront_amount_invalid_type():
    """Test that non-numeric upfront_amount (when not None) raises ValueError."""
    purchase_intent = {
        'client_token': 'test-token-123',
        'offering_id': 'offering-abc-456',
        'commitment': '10.50',
        'sp_type': 'ComputeSavingsPlans',
        'term_seconds': 94608000,
        'payment_option': 'PARTIAL_UPFRONT',
        'projected_coverage_after': 85.5,
        'upfront_amount': 'invalid'
    }

    with pytest.raises(ValueError) as exc_info:
        validate_purchase_intent(purchase_intent)

    assert "Field 'upfront_amount' must be numeric or None" in str(exc_info.value)


def test_purchase_intent_not_dict():
    """Test that non-dictionary purchase_intent raises ValueError."""
    purchase_intent = "not a dictionary"

    with pytest.raises(ValueError) as exc_info:
        validate_purchase_intent(purchase_intent)

    assert "Purchase intent must be a dictionary" in str(exc_info.value)


def test_purchase_intent_none():
    """Test that None purchase_intent raises ValueError."""
    with pytest.raises(ValueError) as exc_info:
        validate_purchase_intent(None)

    assert "Purchase intent must be a dictionary" in str(exc_info.value)


def test_purchase_intent_list():
    """Test that list purchase_intent raises ValueError."""
    purchase_intent = ['item1', 'item2']

    with pytest.raises(ValueError) as exc_info:
        validate_purchase_intent(purchase_intent)

    assert "Purchase intent must be a dictionary" in str(exc_info.value)


def test_projected_coverage_after_accepts_int():
    """Test that projected_coverage_after accepts integer values."""
    purchase_intent = {
        'client_token': 'test-token-123',
        'offering_id': 'offering-abc-456',
        'commitment': '10.50',
        'sp_type': 'ComputeSavingsPlans',
        'term_seconds': 94608000,
        'payment_option': 'NO_UPFRONT',
        'projected_coverage_after': 85  # Integer instead of float
    }

    # Should not raise any exception
    validate_purchase_intent(purchase_intent)


def test_all_valid_sp_types():
    """Test that all valid SP types are accepted."""
    for sp_type in VALID_SP_TYPES:
        purchase_intent = {
            'client_token': 'test-token-123',
            'offering_id': 'offering-abc-456',
            'commitment': '10.50',
            'sp_type': sp_type,
            'term_seconds': 94608000,
            'payment_option': 'NO_UPFRONT',
            'projected_coverage_after': 85.5
        }

        # Should not raise any exception
        validate_purchase_intent(purchase_intent)


def test_all_valid_payment_options():
    """Test that all valid payment options are accepted."""
    for payment_option in VALID_PAYMENT_OPTIONS:
        purchase_intent = {
            'client_token': 'test-token-123',
            'offering_id': 'offering-abc-456',
            'commitment': '10.50',
            'sp_type': 'ComputeSavingsPlans',
            'term_seconds': 94608000,
            'payment_option': payment_option,
            'projected_coverage_after': 85.5
        }

        # Should not raise any exception
        validate_purchase_intent(purchase_intent)

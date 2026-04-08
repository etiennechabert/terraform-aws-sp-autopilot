"""Unit tests for offering resolver module."""

from unittest.mock import MagicMock

import offering_resolver
import pytest


@pytest.fixture
def mock_client():
    return MagicMock()


def _make_offering(offering_id="off-123", plan_type="Compute", product_types=None):
    return {
        "offeringId": offering_id,
        "planType": plan_type,
        "productTypes": product_types or ["Fargate"],
        "description": "test",
        "paymentOption": "No Upfront",
        "durationSeconds": 31536000,
        "usageType": "test",
    }


def test_resolve_single_offering(mock_client):
    mock_client.describe_savings_plans_offerings.return_value = {
        "searchResults": [_make_offering()],
    }
    result = offering_resolver.resolve_offering(mock_client, "compute", "ONE_YEAR", "NO_UPFRONT")
    assert result["id"] == "off-123"


def test_resolve_no_offering_raises(mock_client):
    mock_client.describe_savings_plans_offerings.return_value = {"searchResults": []}
    with pytest.raises(ValueError, match="No offering found"):
        offering_resolver.resolve_offering(mock_client, "compute", "ONE_YEAR", "NO_UPFRONT")


def test_resolve_ambiguous_offerings_raises(mock_client):
    mock_client.describe_savings_plans_offerings.return_value = {
        "searchResults": [_make_offering("off-1"), _make_offering("off-2")],
    }
    with pytest.raises(ValueError, match="Ambiguous offering query"):
        offering_resolver.resolve_offering(mock_client, "compute", "ONE_YEAR", "NO_UPFRONT")


def test_resolve_unknown_sp_type_raises(mock_client):
    with pytest.raises(ValueError, match="Unknown sp_type_key"):
        offering_resolver.resolve_offering(mock_client, "unknown", "ONE_YEAR", "NO_UPFRONT")


def test_resolve_unknown_term_raises(mock_client):
    with pytest.raises(ValueError, match="Unknown term"):
        offering_resolver.resolve_offering(mock_client, "compute", "FIVE_YEAR", "NO_UPFRONT")


def test_resolve_unknown_payment_option_raises(mock_client):
    with pytest.raises(ValueError, match="Unknown payment_option"):
        offering_resolver.resolve_offering(mock_client, "compute", "ONE_YEAR", "UNKNOWN")

"""
Integration tests for Purchaser Lambda.

Tests verify all required behaviors:
1. Empty queue exits silently
2. Valid purchases execute correctly
3. Cap enforcement works
4. Messages deleted appropriately
5. Emails sent correctly
6. Input validation rejects malformed messages
7. API errors are handled properly
"""

import json
import os
import sys
from unittest.mock import Mock, patch

import pytest
from botocore.exceptions import ClientError


# Add lambda directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import handler


@pytest.fixture
def mock_env_vars(monkeypatch):
    """Set up environment variables for testing."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SECURITY_TOKEN", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("QUEUE_URL", "https://sqs.us-east-1.amazonaws.com/123456789012/test-queue")
    monkeypatch.setenv("SNS_TOPIC_ARN", "arn:aws:sns:us-east-1:123456789012:test-topic")
    monkeypatch.setenv("MAX_COVERAGE_CAP", "95")
    monkeypatch.setenv("RENEWAL_WINDOW_DAYS", "7")


@pytest.fixture
def mock_clients():
    """Create mock AWS clients."""
    with patch("shared.handler_utils.initialize_clients") as mock_init:
        mock_sqs = Mock()
        mock_sns = Mock()
        mock_ce = Mock()
        mock_sp = Mock()

        mock_init.return_value = {
            "sqs": mock_sqs,
            "sns": mock_sns,
            "ce": mock_ce,
            "savingsplans": mock_sp,
        }

        yield {
            "sqs": mock_sqs,
            "sns": mock_sns,
            "ce": mock_ce,
            "savingsplans": mock_sp,
        }


def test_empty_queue(mock_env_vars, mock_clients):
    """Empty queue should exit silently without error or email."""
    # Mock empty queue
    mock_clients["sqs"].receive_message.return_value = {}

    # Execute handler
    response = handler.handler({}, {})

    # Verify
    assert response["statusCode"] == 200
    assert "No purchases to process" in response["body"]
    assert not mock_clients["sns"].publish.called, (
        "SNS publish should NOT be called for empty queue"
    )


def test_valid_purchase_success(mock_env_vars, mock_clients):
    """Valid Compute SP purchase should execute successfully."""
    # Mock SQS message with valid purchase intent
    purchase_intent = {
        "client_token": "test-token-123",
        "offering_id": "sp-offering-123",
        "commitment": "1.50",
        "sp_type": "ComputeSavingsPlans",
        "term_seconds": 94608000,  # 3 years
        "payment_option": "NO_UPFRONT",
        "upfront_amount": None,
        "projected_coverage_after": 75.0,
    }

    mock_clients["sqs"].receive_message.return_value = {
        "Messages": [{"Body": json.dumps(purchase_intent), "ReceiptHandle": "receipt-handle-123"}]
    }

    # Mock current coverage (low coverage, won't exceed cap)
    mock_clients["ce"].get_savings_plans_coverage.return_value = {
        "SavingsPlansCoverages": [
            {
                "Groups": [
                    {
                        "Attributes": {"SAVINGS_PLANS_TYPE": "ComputeSavingsPlans"},
                        "Coverage": {"CoveragePercentage": "50.0"},
                    }
                ]
            }
        ]
    }

    # Mock no expiring plans
    mock_clients["savingsplans"].describe_savings_plans.return_value = {"savingsPlans": []}

    # Mock successful purchase
    mock_clients["savingsplans"].create_savings_plan.return_value = {"savingsPlanId": "sp-12345678"}

    # Execute handler
    response = handler.handler({}, {})

    # Verify
    assert response["statusCode"] == 200
    assert mock_clients["savingsplans"].create_savings_plan.called, (
        "CreateSavingsPlan should be called"
    )
    assert mock_clients["sqs"].delete_message.called, "Message should be deleted from queue"
    assert mock_clients["sns"].publish.called, "Summary email should be sent"

    # Verify CreateSavingsPlan parameters
    create_call = mock_clients["savingsplans"].create_savings_plan.call_args
    assert create_call[1]["clientToken"] == "test-token-123"
    assert create_call[1]["savingsPlanOfferingId"] == "sp-offering-123"

    # Verify email content
    email_call = mock_clients["sns"].publish.call_args
    assert "sp-12345678" in email_call[1]["Message"]
    assert "Successful Purchases: 1" in email_call[1]["Message"]


def test_cap_enforcement(mock_env_vars, mock_clients):
    """Purchase exceeding max coverage cap should be skipped."""
    # Mock SQS message with purchase that would exceed cap
    purchase_intent = {
        "client_token": "test-token-456",
        "offering_id": "sp-offering-456",
        "commitment": "5.00",
        "sp_type": "ComputeSavingsPlans",
        "term_seconds": 94608000,
        "payment_option": "NO_UPFRONT",
        "upfront_amount": None,
        "projected_coverage_after": 98.0,  # Exceeds 95% cap
    }

    mock_clients["sqs"].receive_message.return_value = {
        "Messages": [{"Body": json.dumps(purchase_intent), "ReceiptHandle": "receipt-handle-456"}]
    }

    # Mock current coverage
    mock_clients["ce"].get_savings_plans_coverage.return_value = {
        "SavingsPlansCoverages": [
            {
                "Groups": [
                    {
                        "Attributes": {"SAVINGS_PLANS_TYPE": "ComputeSavingsPlans"},
                        "Coverage": {"CoveragePercentage": "85.0"},
                    }
                ]
            }
        ]
    }

    # Mock no expiring plans
    mock_clients["savingsplans"].describe_savings_plans.return_value = {"savingsPlans": []}

    # Execute handler
    response = handler.handler({}, {})

    # Verify
    assert response["statusCode"] == 200
    assert not mock_clients["savingsplans"].create_savings_plan.called, (
        "CreateSavingsPlan should NOT be called when exceeding cap"
    )
    assert mock_clients["sqs"].delete_message.called, (
        "Message should still be deleted even when skipped"
    )
    assert mock_clients["sns"].publish.called, "Summary email should be sent"

    # Verify email content mentions skip
    email_call = mock_clients["sns"].publish.call_args
    assert "Skipped Purchases: 1" in email_call[1]["Message"]
    assert "Would exceed max_coverage_cap" in email_call[1]["Message"]


def test_api_error_handling(mock_env_vars, mock_clients):
    """API error should send error email and raise exception."""
    with patch("boto3.client") as mock_boto_client:
        # Mock boto3.client call in error handler
        mock_boto_client.return_value = mock_clients["sns"]

        # Mock SQS message
        purchase_intent = {
            "client_token": "test-token-error",
            "offering_id": "sp-offering-error",
            "commitment": "1.00",
            "sp_type": "ComputeSavingsPlans",
            "term_seconds": 94608000,
            "payment_option": "NO_UPFRONT",
            "upfront_amount": None,
            "projected_coverage_after": 60.0,
        }

        mock_clients["sqs"].receive_message.return_value = {
            "Messages": [{"Body": json.dumps(purchase_intent), "ReceiptHandle": "receipt-error"}]
        }

        # Mock API error
        mock_clients["ce"].get_savings_plans_coverage.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "Access denied"}},
            "GetSavingsPlansCoverage",
        )

        # Execute handler - should raise exception
        with pytest.raises(ClientError) as exc_info:
            handler.handler({}, {})

        # Verify
        assert "AccessDenied" in str(exc_info.value)
        assert mock_clients["sns"].publish.called, "Error email should be sent"

        # Verify error email content
        email_call = mock_clients["sns"].publish.call_args
        assert "Failed" in email_call[1]["Subject"]
        assert "Access denied" in email_call[1]["Message"]
        assert "CloudWatch Logs" in email_call[1]["Message"]


def test_database_sp_purchase(mock_env_vars, mock_clients):
    """Database Savings Plan purchase should execute successfully."""
    # Mock SQS message with Database SP purchase intent
    purchase_intent = {
        "client_token": "test-db-token-123",
        "offering_id": "sp-db-offering-123",
        "commitment": "2.00",
        "sp_type": "DatabaseSavingsPlans",
        "term_seconds": 94608000,  # 3 years
        "payment_option": "NO_UPFRONT",
        "upfront_amount": None,
        "projected_coverage_after": 80.0,
    }

    mock_clients["sqs"].receive_message.return_value = {
        "Messages": [
            {"Body": json.dumps(purchase_intent), "ReceiptHandle": "receipt-handle-db-123"}
        ]
    }

    # Mock current coverage (low database coverage, won't exceed cap)
    mock_clients["ce"].get_savings_plans_coverage.return_value = {
        "SavingsPlansCoverages": [
            {
                "Groups": [
                    {
                        "Attributes": {"SAVINGS_PLANS_TYPE": "ComputeSavingsPlans"},
                        "Coverage": {"CoveragePercentage": "60.0"},
                    },
                    {
                        "Attributes": {"SAVINGS_PLANS_TYPE": "DatabaseSavingsPlans"},
                        "Coverage": {"CoveragePercentage": "45.0"},
                    },
                ]
            }
        ]
    }

    # Mock no expiring plans
    mock_clients["savingsplans"].describe_savings_plans.return_value = {"savingsPlans": []}

    # Mock successful purchase
    mock_clients["savingsplans"].create_savings_plan.return_value = {
        "savingsPlanId": "sp-db-12345678"
    }

    # Execute handler
    response = handler.handler({}, {})

    # Verify
    assert response["statusCode"] == 200
    assert mock_clients["savingsplans"].create_savings_plan.called, (
        "CreateSavingsPlan should be called for Database SP"
    )
    assert mock_clients["sqs"].delete_message.called, "Message should be deleted from queue"
    assert mock_clients["sns"].publish.called, "Summary email should be sent"

    # Verify CreateSavingsPlan parameters
    create_call = mock_clients["savingsplans"].create_savings_plan.call_args
    assert create_call[1]["clientToken"] == "test-db-token-123"
    assert create_call[1]["savingsPlanOfferingId"] == "sp-db-offering-123"

    # Verify email content
    email_call = mock_clients["sns"].publish.call_args
    assert "sp-db-12345678" in email_call[1]["Message"]
    assert "Successful Purchases: 1" in email_call[1]["Message"]


def test_validation_errors(mock_env_vars, mock_clients):
    """Invalid purchase intents should fail validation and not be deleted from queue."""
    # Test 1: Missing required fields
    malformed_intent = {
        # Missing client_token and offering_id
        "commitment": "1.50",
        "sp_type": "ComputeSavingsPlans",
        "term_seconds": 94608000,
        "payment_option": "NO_UPFRONT",
        "projected_coverage_after": 75.0,
    }

    mock_clients["sqs"].receive_message.return_value = {
        "Messages": [{"Body": json.dumps(malformed_intent), "ReceiptHandle": "receipt-malformed"}]
    }

    # Mock current coverage
    mock_clients["ce"].get_savings_plans_coverage.return_value = {
        "SavingsPlansCoverages": [
            {
                "Groups": [
                    {
                        "Attributes": {"SAVINGS_PLANS_TYPE": "ComputeSavingsPlans"},
                        "Coverage": {"CoveragePercentage": "50.0"},
                    }
                ]
            }
        ]
    }

    # Mock no expiring plans
    mock_clients["savingsplans"].describe_savings_plans.return_value = {"savingsPlans": []}

    # Execute handler
    response = handler.handler({}, {})

    # Verify malformed message handling
    assert response["statusCode"] == 200
    assert not mock_clients["sqs"].delete_message.called, (
        "Malformed message should NOT be deleted (kept for retry)"
    )
    assert mock_clients["sns"].publish.called, "Summary email should be sent"

    # Verify email shows failed purchase
    email_call = mock_clients["sns"].publish.call_args
    assert "Failed Purchases: 1" in email_call[1]["Message"]
    assert "Validation error" in email_call[1]["Message"]

    # Reset mocks for second test
    mock_clients["sqs"].reset_mock()
    mock_clients["sns"].reset_mock()
    mock_clients["savingsplans"].reset_mock()

    # Test 2: Invalid sp_type
    invalid_sp_type_intent = {
        "client_token": "test-token-invalid",
        "offering_id": "sp-offering-invalid",
        "commitment": "1.50",
        "sp_type": "InvalidSavingsPlans",  # Invalid type
        "term_seconds": 94608000,
        "payment_option": "NO_UPFRONT",
        "upfront_amount": None,
        "projected_coverage_after": 75.0,
    }

    mock_clients["sqs"].receive_message.return_value = {
        "Messages": [
            {"Body": json.dumps(invalid_sp_type_intent), "ReceiptHandle": "receipt-invalid"}
        ]
    }

    # Execute handler
    response = handler.handler({}, {})

    # Verify invalid sp_type handling
    assert response["statusCode"] == 200
    assert not mock_clients["sqs"].delete_message.called, (
        "Invalid sp_type message should NOT be deleted"
    )
    assert mock_clients["sns"].publish.called, "Summary email should be sent"

    # Verify email shows validation error
    email_call = mock_clients["sns"].publish.call_args
    assert "Failed Purchases: 1" in email_call[1]["Message"]
    assert "Validation error" in email_call[1]["Message"]
    assert "sp_type" in email_call[1]["Message"].lower()

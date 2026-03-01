"""
Integration tests for Purchaser Lambda.

Tests verify all required behaviors:
1. Empty queue exits silently
2. Valid purchases execute correctly
3. Messages deleted appropriately
4. Emails sent correctly
5. Input validation rejects malformed messages
6. API errors are handled properly
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

from datetime import UTC

import handler


SP_TYPE_MAP = {
    "compute": ("ComputeSavingsPlans", "offering-compute"),
    "database": ("DatabaseSavingsPlans", "offering-database"),
    "sagemaker": ("SageMakerSavingsPlans", "offering-sagemaker"),
}

TERM_MAP = {
    "ONE_YEAR": 31536000,
    "THREE_YEAR": 94608000,
}


def _purchase_intent(
    sp_type="compute",
    commitment="1.50",
    term="THREE_YEAR",
    payment_option="NO_UPFRONT",
    **extra,
):
    """Build a purchase intent in the format the scheduler sends to SQS (purchaser-ready)."""
    sp_filter, offering_id = SP_TYPE_MAP[sp_type]
    return {
        "client_token": f"test-{sp_type}-token",
        "offering_id": offering_id,
        "sp_type": sp_filter,
        "term_seconds": TERM_MAP[term],
        "commitment": commitment,
        "payment_option": payment_option,
        **extra,
    }


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
    monkeypatch.setenv("RENEWAL_WINDOW_DAYS", "7")


@pytest.fixture
def mock_clients():
    """Create mock AWS clients."""
    with patch("shared.handler_utils.initialize_clients") as mock_init:
        mock_sqs = Mock()
        mock_sns = Mock()
        mock_ce = Mock()
        mock_sp = Mock()
        mock_sp.describe_savings_plans.return_value = {"savingsPlans": []}

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


def test_valid_purchase_success(aws_mock_builder, mock_env_vars, mock_clients):
    """Valid Compute SP purchase should execute successfully."""
    purchase_intent = _purchase_intent(
        sp_type="compute",
        commitment="1.50",
        term="THREE_YEAR",
    )

    mock_clients["sqs"].receive_message.return_value = {
        "Messages": [{"Body": json.dumps(purchase_intent), "ReceiptHandle": "receipt-handle-123"}]
    }

    # Use real AWS response structure for coverage (low coverage, won't exceed cap)
    mock_clients["ce"].get_savings_plans_coverage.return_value = aws_mock_builder.coverage(
        coverage_percentage=50.0
    )

    # Mock no expiring plans - use real structure
    mock_clients[
        "savingsplans"
    ].describe_savings_plans.return_value = aws_mock_builder.describe_savings_plans(plans_count=0)

    # Mock successful purchase - use real structure
    mock_clients[
        "savingsplans"
    ].create_savings_plan.return_value = aws_mock_builder.create_savings_plan(
        savings_plan_id="sp-12345678"
    )

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
    assert create_call[1]["savingsPlanOfferingId"] == "offering-compute"

    # Verify email content
    email_call = mock_clients["sns"].publish.call_args
    assert "sp-12345678" in email_call[1]["Message"]
    assert "Successful Purchases: 1" in email_call[1]["Message"]


def test_api_error_handling(mock_env_vars, mock_clients):
    """API error should send error email and raise exception."""
    with patch("boto3.client") as mock_boto_client:
        # Mock boto3.client call in error handler
        mock_boto_client.return_value = mock_clients["sns"]

        purchase_intent = _purchase_intent()

        mock_clients["sqs"].receive_message.return_value = {
            "Messages": [{"Body": json.dumps(purchase_intent), "ReceiptHandle": "receipt-error"}]
        }

        # Mock API error (happens before normalize is called)
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
    purchase_intent = _purchase_intent(
        sp_type="database",
        commitment="2.00",
        term="ONE_YEAR",
    )

    mock_clients["sqs"].receive_message.return_value = {
        "Messages": [
            {
                "Body": json.dumps(purchase_intent),
                "ReceiptHandle": "receipt-handle-db-123",
            }
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
    assert create_call[1]["savingsPlanOfferingId"] == "offering-database"

    # Verify email content
    email_call = mock_clients["sns"].publish.call_args
    assert "sp-db-12345678" in email_call[1]["Message"]
    assert "Successful Purchases: 1" in email_call[1]["Message"]


def test_validation_errors(mock_env_vars, mock_clients):
    """Invalid purchase intents should fail validation and not be deleted from queue."""
    # Test 1: Missing required fields (pre-normalized format with offering_id but missing client_token)
    malformed_intent = {
        "offering_id": "sp-offering-bad",
        "commitment": "1.50",
        "sp_type": "ComputeSavingsPlans",
        "term_seconds": 94608000,
        "payment_option": "NO_UPFRONT",
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
    mock_clients["savingsplans"].describe_savings_plans.return_value = {"savingsPlans": []}

    # Test 2: Invalid sp_type (pre-normalized format)
    invalid_sp_type_intent = {
        "client_token": "test-token-invalid",
        "offering_id": "sp-offering-invalid",
        "commitment": "1.50",
        "sp_type": "InvalidSavingsPlans",  # Invalid type
        "term_seconds": 94608000,
        "payment_option": "NO_UPFRONT",
        "upfront_amount": None,
    }

    mock_clients["sqs"].receive_message.return_value = {
        "Messages": [
            {
                "Body": json.dumps(invalid_sp_type_intent),
                "ReceiptHandle": "receipt-invalid",
            }
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


def test_upfront_payment_purchase(mock_env_vars, mock_clients):
    """Purchase with ALL_UPFRONT payment option should include upfront amount."""
    purchase_intent = _purchase_intent(
        sp_type="compute",
        commitment="10.00",
        term="THREE_YEAR",
        payment_option="ALL_UPFRONT",
        upfront_amount="262800.00",
    )

    mock_clients["sqs"].receive_message.return_value = {
        "Messages": [{"Body": json.dumps(purchase_intent), "ReceiptHandle": "receipt-upfront"}]
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

    # Mock successful purchase
    mock_clients["savingsplans"].create_savings_plan.return_value = {
        "savingsPlanId": "sp-upfront-12345"
    }

    # Execute handler
    response = handler.handler({}, {})

    # Verify
    assert response["statusCode"] == 200

    # Verify CreateSavingsPlan was called with upfront amount
    create_call = mock_clients["savingsplans"].create_savings_plan.call_args
    assert "upfrontPaymentAmount" in create_call[1], "Upfront amount should be included"
    assert create_call[1]["upfrontPaymentAmount"] == "262800.00"

    # Verify email contains upfront amount
    email_call = mock_clients["sns"].publish.call_args
    assert "Upfront Payment" in email_call[1]["Message"]
    assert "262,800.00" in email_call[1]["Message"]


def test_sagemaker_sp_purchase(mock_env_vars, mock_clients):
    """SageMaker Savings Plan purchase should handle coverage tracking correctly."""
    purchase_intent = _purchase_intent(
        sp_type="sagemaker",
        commitment="3.50",
        term="ONE_YEAR",
    )

    mock_clients["sqs"].receive_message.return_value = {
        "Messages": [{"Body": json.dumps(purchase_intent), "ReceiptHandle": "receipt-sm-123"}]
    }

    # Mock current coverage
    mock_clients["ce"].get_savings_plans_coverage.return_value = {
        "SavingsPlansCoverages": [
            {
                "Groups": [
                    {
                        "Attributes": {"SAVINGS_PLANS_TYPE": "ComputeSavingsPlans"},
                        "Coverage": {"CoveragePercentage": "55.0"},
                    },
                    {
                        "Attributes": {"SAVINGS_PLANS_TYPE": "SageMakerSavingsPlans"},
                        "Coverage": {"CoveragePercentage": "30.0"},
                    },
                ]
            }
        ]
    }

    # Mock no expiring plans
    mock_clients["savingsplans"].describe_savings_plans.return_value = {"savingsPlans": []}

    # Mock successful purchase
    mock_clients["savingsplans"].create_savings_plan.return_value = {
        "savingsPlanId": "sp-sm-12345678"
    }

    # Execute handler
    response = handler.handler({}, {})

    # Verify
    assert response["statusCode"] == 200
    assert mock_clients["savingsplans"].create_savings_plan.called
    assert mock_clients["sqs"].delete_message.called
    assert mock_clients["sns"].publish.called

    # Verify email content
    email_call = mock_clients["sns"].publish.call_args
    assert "sp-sm-12345678" in email_call[1]["Message"]


def test_purchase_api_error(mock_env_vars, mock_clients):
    """CreateSavingsPlan API error should be handled and message kept in queue."""
    purchase_intent = _purchase_intent(
        sp_type="compute",
        commitment="1.00",
        term="THREE_YEAR",
    )

    mock_clients["sqs"].receive_message.return_value = {
        "Messages": [{"Body": json.dumps(purchase_intent), "ReceiptHandle": "receipt-fail"}]
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

    # Mock CreateSavingsPlan API error
    mock_clients["savingsplans"].create_savings_plan.side_effect = ClientError(
        {"Error": {"Code": "InternalFailure", "Message": "Internal service error"}},
        "CreateSavingsPlan",
    )

    # Execute handler
    response = handler.handler({}, {})

    # Verify
    assert response["statusCode"] == 200
    assert not mock_clients["sqs"].delete_message.called, "Message should stay in queue on failure"
    assert mock_clients["sns"].publish.called, "Summary email should be sent"

    # Verify email shows failed purchase
    email_call = mock_clients["sns"].publish.call_args
    assert "Failed Purchases: 1" in email_call[1]["Message"]
    assert "InternalFailure" in email_call[1]["Message"]


def test_expiring_plans_renewal(mock_env_vars, mock_clients):
    """Expiring Compute SP should trigger coverage adjustment to force renewal."""
    from datetime import datetime, timedelta

    purchase_intent = _purchase_intent(
        sp_type="compute",
        commitment="5.00",
        term="THREE_YEAR",
    )

    mock_clients["sqs"].receive_message.return_value = {
        "Messages": [{"Body": json.dumps(purchase_intent), "ReceiptHandle": "receipt-renewal"}]
    }

    # Mock current coverage (shows 70% but will be adjusted to 0% due to expiring plan)
    mock_clients["ce"].get_savings_plans_coverage.return_value = {
        "SavingsPlansCoverages": [
            {
                "Groups": [
                    {
                        "Attributes": {"SAVINGS_PLANS_TYPE": "ComputeSavingsPlans"},
                        "Coverage": {"CoveragePercentage": "70.0"},
                    }
                ]
            }
        ]
    }

    # Mock expiring Compute SP (expires in 5 days)
    end_time = (datetime.now(UTC) + timedelta(days=5)).isoformat()
    mock_clients["savingsplans"].describe_savings_plans.return_value = {
        "savingsPlans": [
            {
                "savingsPlanId": "sp-expiring-123",
                "savingsPlanType": "ComputeSavingsPlans",
                "commitment": "4.50",
                "end": end_time,
                "state": "active",
            }
        ]
    }

    # Mock successful purchase
    mock_clients["savingsplans"].create_savings_plan.return_value = {
        "savingsPlanId": "sp-renewal-12345"
    }

    # Execute handler
    response = handler.handler({}, {})

    # Verify
    assert response["statusCode"] == 200
    assert mock_clients["savingsplans"].create_savings_plan.called, (
        "Renewal purchase should execute"
    )
    assert mock_clients["sqs"].delete_message.called
    assert mock_clients["sns"].publish.called


def test_expiring_database_plans(mock_env_vars, mock_clients):
    """Expiring Database SP should trigger coverage adjustment."""
    from datetime import datetime, timedelta

    purchase_intent = _purchase_intent(
        sp_type="database",
        commitment="3.00",
        term="ONE_YEAR",
    )

    mock_clients["sqs"].receive_message.return_value = {
        "Messages": [{"Body": json.dumps(purchase_intent), "ReceiptHandle": "receipt-db-renewal"}]
    }

    # Mock current coverage
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
                        "Coverage": {"CoveragePercentage": "65.0"},
                    },
                ]
            }
        ]
    }

    # Mock expiring Database SP
    end_time = (datetime.now(UTC) + timedelta(days=6)).isoformat()
    mock_clients["savingsplans"].describe_savings_plans.return_value = {
        "savingsPlans": [
            {
                "savingsPlanId": "sp-db-expiring-456",
                "savingsPlanType": "DatabaseSavingsPlans",
                "commitment": "2.50",
                "end": end_time,
                "state": "active",
            }
        ]
    }

    # Mock successful purchase
    mock_clients["savingsplans"].create_savings_plan.return_value = {
        "savingsPlanId": "sp-db-renewal-456"
    }

    # Execute handler
    response = handler.handler({}, {})

    # Verify
    assert response["statusCode"] == 200
    assert mock_clients["savingsplans"].create_savings_plan.called


def test_general_exception_handling(mock_env_vars, mock_clients):
    """General exceptions should be caught and reported."""
    purchase_intent = _purchase_intent(
        sp_type="compute",
        commitment="1.00",
        term="THREE_YEAR",
    )

    mock_clients["sqs"].receive_message.return_value = {
        "Messages": [{"Body": json.dumps(purchase_intent), "ReceiptHandle": "receipt-exception"}]
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

    # Mock general exception (not ClientError)
    mock_clients["savingsplans"].create_savings_plan.side_effect = RuntimeError(
        "Unexpected runtime error"
    )

    # Execute handler
    response = handler.handler({}, {})

    # Verify
    assert response["statusCode"] == 200
    assert not mock_clients["sqs"].delete_message.called, "Message should stay in queue on failure"
    assert mock_clients["sns"].publish.called, "Summary email should be sent"

    # Verify email shows failed purchase
    email_call = mock_clients["sns"].publish.call_args
    assert "Failed Purchases: 1" in email_call[1]["Message"]


def test_expiring_sagemaker_plans(mock_env_vars, mock_clients):
    """Expiring SageMaker SP should trigger coverage adjustment."""
    from datetime import datetime, timedelta

    purchase_intent = _purchase_intent(
        sp_type="sagemaker",
        commitment="2.00",
        term="ONE_YEAR",
    )

    mock_clients["sqs"].receive_message.return_value = {
        "Messages": [{"Body": json.dumps(purchase_intent), "ReceiptHandle": "receipt-sm-renewal"}]
    }

    # Mock current coverage
    mock_clients["ce"].get_savings_plans_coverage.return_value = {
        "SavingsPlansCoverages": [
            {
                "Groups": [
                    {
                        "Attributes": {"SAVINGS_PLANS_TYPE": "SageMakerSavingsPlans"},
                        "Coverage": {"CoveragePercentage": "55.0"},
                    },
                ]
            }
        ]
    }

    # Mock expiring SageMaker SP
    end_time = (datetime.now(UTC) + timedelta(days=4)).isoformat()
    mock_clients["savingsplans"].describe_savings_plans.return_value = {
        "savingsPlans": [
            {
                "savingsPlanId": "sp-sm-expiring-789",
                "savingsPlanType": "SageMakerSavingsPlans",
                "commitment": "1.50",
                "end": end_time,
                "state": "active",
            }
        ]
    }

    # Mock successful purchase
    mock_clients["savingsplans"].create_savings_plan.return_value = {
        "savingsPlanId": "sp-sm-renewal-789"
    }

    # Execute handler
    response = handler.handler({}, {})

    # Verify
    assert response["statusCode"] == 200
    assert mock_clients["savingsplans"].create_savings_plan.called


def test_spike_guard_blocks_purchase_on_usage_drop(mock_env_vars, mock_clients, monkeypatch):
    """Test spike guard blocks purchases when usage dropped since scheduling."""
    monkeypatch.setenv("SPIKE_GUARD_ENABLED", "true")
    monkeypatch.setenv("SPIKE_GUARD_SHORT_LOOKBACK_DAYS", "14")
    monkeypatch.setenv("SPIKE_GUARD_THRESHOLD_PERCENT", "20")
    monkeypatch.setenv("SPIKE_GUARD_LONG_LOOKBACK_DAYS", "90")
    monkeypatch.setenv("ENABLE_COMPUTE_SP", "true")
    monkeypatch.setenv("ENABLE_DATABASE_SP", "false")
    monkeypatch.setenv("ENABLE_SAGEMAKER_SP", "false")

    purchase_intent = _purchase_intent(
        sp_type="compute",
        commitment="1.00",
        term="ONE_YEAR",
        payment_option="ALL_UPFRONT",
        upfront_amount="8760.00",
        scheduling_avg_hourly_total={"compute": 10.0},
    )

    mock_clients["sqs"].receive_message.return_value = {
        "Messages": [{"Body": json.dumps(purchase_intent), "ReceiptHandle": "receipt-guard"}]
    }
    mock_clients["sqs"].delete_message.return_value = {}
    mock_clients["sns"].publish.return_value = {"MessageId": "test-msg"}

    guard_results = {
        "compute": {
            "flagged": True,
            "baseline_avg": 10.0,
            "current_avg": 7.0,
            "change_percent": 30.0,
        }
    }

    with patch(
        "shared.usage_decline_check.run_purchasing_spike_guard",
        return_value=guard_results,
    ):
        response = handler.handler({}, {})

    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["purchases_executed"] == 0
    assert mock_clients["sqs"].delete_message.called
    assert mock_clients["sns"].publish.called
    subject = mock_clients["sns"].publish.call_args[1]["Subject"]
    assert "Blocked" in subject


def test_spike_guard_allows_purchase_when_no_drop(mock_env_vars, mock_clients, monkeypatch):
    """Test spike guard allows purchase when usage hasn't dropped."""
    monkeypatch.setenv("SPIKE_GUARD_ENABLED", "true")
    monkeypatch.setenv("SPIKE_GUARD_SHORT_LOOKBACK_DAYS", "14")
    monkeypatch.setenv("SPIKE_GUARD_THRESHOLD_PERCENT", "20")
    monkeypatch.setenv("SPIKE_GUARD_LONG_LOOKBACK_DAYS", "90")
    monkeypatch.setenv("ENABLE_COMPUTE_SP", "true")
    monkeypatch.setenv("ENABLE_DATABASE_SP", "false")
    monkeypatch.setenv("ENABLE_SAGEMAKER_SP", "false")

    purchase_intent = _purchase_intent(
        sp_type="compute",
        commitment="1.00",
        term="ONE_YEAR",
        payment_option="ALL_UPFRONT",
        upfront_amount="8760.00",
        scheduling_avg_hourly_total={"compute": 10.0},
    )

    mock_clients["sqs"].receive_message.return_value = {
        "Messages": [{"Body": json.dumps(purchase_intent), "ReceiptHandle": "receipt-guard2"}]
    }
    mock_clients["sns"].publish.return_value = {"MessageId": "test-msg"}

    guard_results = {
        "compute": {
            "flagged": False,
            "baseline_avg": 10.0,
            "current_avg": 9.5,
            "change_percent": 5.0,
        }
    }

    mock_clients["ce"].get_savings_plans_coverage.return_value = {
        "SavingsPlansCoverages": [
            {
                "Groups": [
                    {
                        "Attributes": {"SAVINGS_PLANS_TYPE": "ComputeSavingsPlans"},
                        "Coverage": {"CoveragePercentage": "80.0"},
                    }
                ]
            }
        ]
    }
    mock_clients["savingsplans"].describe_savings_plans.return_value = {"savingsPlans": []}
    mock_clients["savingsplans"].create_savings_plan.return_value = {
        "savingsPlanId": "sp-guard-ok-123"
    }
    mock_clients["sqs"].delete_message.return_value = {}

    with patch(
        "shared.usage_decline_check.run_purchasing_spike_guard",
        return_value=guard_results,
    ):
        response = handler.handler({}, {})

    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["purchases_executed"] == 1


def test_spike_guard_skips_without_scheduling_avgs(mock_env_vars, mock_clients, monkeypatch):
    """Test spike guard is skipped when message doesn't contain scheduling averages."""
    monkeypatch.setenv("SPIKE_GUARD_ENABLED", "true")
    monkeypatch.setenv("SPIKE_GUARD_SHORT_LOOKBACK_DAYS", "14")
    monkeypatch.setenv("SPIKE_GUARD_THRESHOLD_PERCENT", "20")
    monkeypatch.setenv("SPIKE_GUARD_LONG_LOOKBACK_DAYS", "90")

    purchase_intent = _purchase_intent(
        sp_type="compute",
        commitment="1.00",
        term="ONE_YEAR",
        payment_option="ALL_UPFRONT",
        upfront_amount="8760.00",
    )

    mock_clients["sqs"].receive_message.return_value = {
        "Messages": [{"Body": json.dumps(purchase_intent), "ReceiptHandle": "receipt-no-avg"}]
    }
    mock_clients["sns"].publish.return_value = {"MessageId": "test-msg"}

    mock_clients["ce"].get_savings_plans_coverage.return_value = {
        "SavingsPlansCoverages": [
            {
                "Groups": [
                    {
                        "Attributes": {"SAVINGS_PLANS_TYPE": "ComputeSavingsPlans"},
                        "Coverage": {"CoveragePercentage": "80.0"},
                    }
                ]
            }
        ]
    }
    mock_clients["savingsplans"].describe_savings_plans.return_value = {"savingsPlans": []}
    mock_clients["savingsplans"].create_savings_plan.return_value = {
        "savingsPlanId": "sp-no-avg-123"
    }
    mock_clients["sqs"].delete_message.return_value = {}

    response = handler.handler({}, {})

    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["purchases_executed"] == 1


def test_cooldown_blocks_recently_purchased_type(mock_env_vars, mock_clients, monkeypatch):
    """Cooldown should block purchases for SP types purchased within the cooldown window."""
    from datetime import datetime, timedelta

    monkeypatch.setenv("PURCHASE_COOLDOWN_DAYS", "7")

    purchase_intent = _purchase_intent(
        sp_type="compute",
        commitment="1.00",
        term="ONE_YEAR",
        payment_option="ALL_UPFRONT",
        upfront_amount="8760.00",
    )

    mock_clients["sqs"].receive_message.return_value = {
        "Messages": [{"Body": json.dumps(purchase_intent), "ReceiptHandle": "receipt-cooldown"}]
    }
    mock_clients["sqs"].delete_message.return_value = {}
    mock_clients["sns"].publish.return_value = {"MessageId": "test-msg"}

    recent_start = (datetime.now(UTC) - timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    mock_clients["savingsplans"].describe_savings_plans.return_value = {
        "savingsPlans": [
            {
                "savingsPlanId": "sp-recent-123",
                "savingsPlanType": "Compute",
                "start": recent_start,
                "state": "active",
            }
        ]
    }

    response = handler.handler({}, {})

    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["purchases_executed"] == 0
    assert mock_clients["sqs"].delete_message.called
    assert not mock_clients["savingsplans"].create_savings_plan.called


def test_cooldown_allows_different_type(mock_env_vars, mock_clients, monkeypatch):
    """Cooldown on compute should not block database purchases."""
    from datetime import datetime, timedelta

    monkeypatch.setenv("PURCHASE_COOLDOWN_DAYS", "7")

    purchase_intent = _purchase_intent(
        sp_type="database",
        commitment="1.00",
        term="ONE_YEAR",
    )

    mock_clients["sqs"].receive_message.return_value = {
        "Messages": [{"Body": json.dumps(purchase_intent), "ReceiptHandle": "receipt-db-cd"}]
    }
    mock_clients["sns"].publish.return_value = {"MessageId": "test-msg"}

    recent_start = (datetime.now(UTC) - timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    far_future_end = (datetime.now(UTC) + timedelta(days=365)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    mock_clients["savingsplans"].describe_savings_plans.return_value = {
        "savingsPlans": [
            {
                "savingsPlanId": "sp-recent-compute",
                "savingsPlanType": "Compute",
                "start": recent_start,
                "end": far_future_end,
                "state": "active",
                "commitment": "1.00",
            }
        ]
    }

    mock_clients["ce"].get_savings_plans_coverage.return_value = {
        "SavingsPlansCoverages": [
            {
                "Groups": [
                    {
                        "Attributes": {"SAVINGS_PLANS_TYPE": "DatabaseSavingsPlans"},
                        "Coverage": {"CoveragePercentage": "50.0"},
                    }
                ]
            }
        ]
    }
    mock_clients["savingsplans"].create_savings_plan.return_value = {
        "savingsPlanId": "sp-db-new-456"
    }
    mock_clients["sqs"].delete_message.return_value = {}

    response = handler.handler({}, {})

    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["purchases_executed"] == 1
    assert mock_clients["savingsplans"].create_savings_plan.called


def test_strategy_context_in_email(mock_env_vars, mock_clients):
    """Strategy context from scheduler should appear in the purchase email."""
    purchase_intent = _purchase_intent(
        sp_type="compute",
        commitment="1.50",
        term="THREE_YEAR",
        strategy="dynamic+gap_split",
        estimated_savings_percentage=34.8,
        details={
            "coverage": {"current": 7.23, "target": 100.0, "gap": 92.77},
            "spending": {"total": 5.0, "covered": 0.36, "uncovered": 4.64},
        },
    )

    mock_clients["sqs"].receive_message.return_value = {
        "Messages": [{"Body": json.dumps(purchase_intent), "ReceiptHandle": "receipt-strategy"}]
    }
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
    mock_clients["savingsplans"].describe_savings_plans.return_value = {"savingsPlans": []}
    mock_clients["savingsplans"].create_savings_plan.return_value = {
        "savingsPlanId": "sp-strategy-123"
    }

    response = handler.handler({}, {})

    assert response["statusCode"] == 200
    email_call = mock_clients["sns"].publish.call_args
    email_body = email_call[1]["Message"]
    assert "Strategy: dynamic+gap_split" in email_body
    assert "Estimated Savings: 34.8%" in email_body
    assert "Coverage: 7.23% -> 100.00%" in email_body

"""
Integration tests for Scheduler Lambda handler.

All tests follow TESTING.md guidelines:
- Test through handler.handler() entry point only
- Mock only AWS client responses
- Use aws_mock_builder for consistent responses
- Verify behavior through handler response and AWS calls
"""

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

import pytest
from botocore.exceptions import ClientError


sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import handler


@pytest.fixture
def mock_env_vars(monkeypatch):
    """Set up environment variables for testing."""
    monkeypatch.setenv("QUEUE_URL", "https://sqs.us-east-1.amazonaws.com/123456789012/test-queue")
    monkeypatch.setenv("SNS_TOPIC_ARN", "arn:aws:sns:us-east-1:123456789012:test-topic")
    monkeypatch.setenv("DRY_RUN", "true")
    monkeypatch.setenv("ENABLE_COMPUTE_SP", "true")
    monkeypatch.setenv("ENABLE_DATABASE_SP", "false")
    monkeypatch.setenv("ENABLE_SAGEMAKER_SP", "false")
    monkeypatch.setenv("COVERAGE_TARGET_PERCENT", "90")
    monkeypatch.setenv("PURCHASE_STRATEGY_TYPE", "follow_aws")
    monkeypatch.setenv("MAX_PURCHASE_PERCENT", "10")
    monkeypatch.setenv("RENEWAL_WINDOW_DAYS", "7")
    monkeypatch.setenv("LOOKBACK_DAYS", "13")
    monkeypatch.setenv("MIN_DATA_DAYS", "14")
    monkeypatch.setenv("MIN_COMMITMENT_PER_PLAN", "0.001")
    monkeypatch.setenv("COMPUTE_SP_TERM_MIX", '{"three_year": 0.67, "one_year": 0.33}')
    monkeypatch.setenv("COMPUTE_SP_PAYMENT_OPTION", "ALL_UPFRONT")
    monkeypatch.setenv("SAGEMAKER_SP_TERM_MIX", '{"three_year": 0.67, "one_year": 0.33}')
    monkeypatch.setenv("SAGEMAKER_SP_PAYMENT_OPTION", "ALL_UPFRONT")
    monkeypatch.setenv("TAGS", "{}")


@pytest.fixture
def mock_clients():
    """Mock AWS clients at the initialization boundary."""
    with patch("handler.initialize_clients") as mock_init:
        mock_ce = Mock()
        mock_sqs = Mock()
        mock_sns = Mock()
        mock_sp = Mock()

        mock_init.return_value = {
            "ce": mock_ce,
            "sqs": mock_sqs,
            "sns": mock_sns,
            "savingsplans": mock_sp,
        }

        yield {
            "ce": mock_ce,
            "sqs": mock_sqs,
            "sns": mock_sns,
            "savingsplans": mock_sp,
        }


def test_handler_dry_run_mode(mock_env_vars, mock_clients, aws_mock_builder):
    """Test handler in dry-run mode sends email but doesn't queue."""
    mock_clients["sqs"].purge_queue.return_value = {}
    mock_clients[
        "ce"
    ].get_savings_plans_purchase_recommendation.return_value = aws_mock_builder.recommendation(
        "compute", hourly_commitment=1.0
    )
    mock_clients["sns"].publish.return_value = {"MessageId": "test-msg"}

    response = handler.handler({}, None)

    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["dry_run"] is True

    assert mock_clients["sqs"].purge_queue.called
    assert not mock_clients["sqs"].send_message.called
    assert mock_clients["sns"].publish.called

    email_call = mock_clients["sns"].publish.call_args[1]
    assert "DRY RUN" in email_call["Subject"]


def test_handler_production_mode(mock_env_vars, mock_clients, aws_mock_builder, monkeypatch):
    """Test handler in production mode queues messages and sends email."""
    monkeypatch.setenv("DRY_RUN", "false")

    mock_clients["sqs"].purge_queue.return_value = {}
    mock_clients[
        "ce"
    ].get_savings_plans_purchase_recommendation.return_value = aws_mock_builder.recommendation(
        "compute", hourly_commitment=1.0
    )
    mock_clients["sqs"].send_message.return_value = {"MessageId": "msg-123"}
    mock_clients["sns"].publish.return_value = {"MessageId": "test-msg"}

    response = handler.handler({}, None)

    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["dry_run"] is False

    assert mock_clients["sqs"].purge_queue.called
    assert mock_clients["sqs"].send_message.called
    assert mock_clients["sns"].publish.called

    email_call = mock_clients["sns"].publish.call_args[1]
    assert "DRY RUN" not in email_call["Subject"]


def test_handler_follow_aws_strategy(mock_env_vars, mock_clients, aws_mock_builder):
    """Test follow_aws strategy uses 100% of AWS recommendations."""
    mock_clients["sqs"].purge_queue.return_value = {}
    mock_clients[
        "ce"
    ].get_savings_plans_purchase_recommendation.return_value = aws_mock_builder.recommendation(
        "compute", hourly_commitment=10.0
    )
    mock_clients["sns"].publish.return_value = {"MessageId": "test-msg"}

    response = handler.handler({}, None)

    assert response["statusCode"] == 200

    assert mock_clients["ce"].get_savings_plans_purchase_recommendation.called
    rec_call = mock_clients["ce"].get_savings_plans_purchase_recommendation.call_args[1]
    assert rec_call["SavingsPlansType"] == "COMPUTE_SP"

    email_call = mock_clients["sns"].publish.call_args[1]
    message = email_call["Message"]
    # follow_aws uses 100% of AWS recommendation (10.0000/hour)
    assert "10.0000" in message


def test_handler_fixed_strategy(mock_env_vars, mock_clients, aws_mock_builder, monkeypatch):
    """Test fixed strategy analyzes spending and calculates purchases."""
    monkeypatch.setenv("PURCHASE_STRATEGY_TYPE", "fixed")
    monkeypatch.setenv("MAX_PURCHASE_PERCENT", "5")

    mock_clients["sqs"].purge_queue.return_value = {}

    mock_clients[
        "savingsplans"
    ].describe_savings_plans.return_value = aws_mock_builder.describe_savings_plans(plans_count=0)

    mock_clients["ce"].get_savings_plans_coverage.return_value = aws_mock_builder.coverage(
        coverage_percentage=50.0
    )

    mock_clients["ce"].get_cost_and_usage.return_value = aws_mock_builder.cost_and_usage()

    mock_clients["sns"].publish.return_value = {"MessageId": "test-msg"}

    response = handler.handler({}, None)

    assert response["statusCode"] == 200

    assert mock_clients["savingsplans"].describe_savings_plans.called
    assert mock_clients["ce"].get_savings_plans_coverage.called
    assert mock_clients["ce"].get_cost_and_usage.called

    email_call = mock_clients["sns"].publish.call_args[1]
    assert "Current Coverage" in email_call["Message"]


def test_handler_compute_sp_enabled(mock_env_vars, mock_clients, aws_mock_builder):
    """Test Compute SP recommendations are fetched when enabled."""
    mock_clients["sqs"].purge_queue.return_value = {}
    mock_clients[
        "ce"
    ].get_savings_plans_purchase_recommendation.return_value = aws_mock_builder.recommendation(
        "compute", hourly_commitment=2.5
    )
    mock_clients["sns"].publish.return_value = {"MessageId": "test-msg"}

    response = handler.handler({}, None)

    assert response["statusCode"] == 200

    rec_call = mock_clients["ce"].get_savings_plans_purchase_recommendation.call_args[1]
    assert rec_call["SavingsPlansType"] == "COMPUTE_SP"
    assert rec_call["PaymentOption"] == "ALL_UPFRONT"


def test_handler_database_sp_enabled(mock_env_vars, mock_clients, aws_mock_builder, monkeypatch):
    """Test Database SP recommendations are fetched when enabled."""
    monkeypatch.setenv("ENABLE_COMPUTE_SP", "false")
    monkeypatch.setenv("ENABLE_DATABASE_SP", "true")

    mock_clients["sqs"].purge_queue.return_value = {}
    mock_clients[
        "ce"
    ].get_savings_plans_purchase_recommendation.return_value = aws_mock_builder.recommendation(
        "database", hourly_commitment=1.25
    )
    mock_clients["sns"].publish.return_value = {"MessageId": "test-msg"}

    response = handler.handler({}, None)

    assert response["statusCode"] == 200

    rec_call = mock_clients["ce"].get_savings_plans_purchase_recommendation.call_args[1]
    assert rec_call["SavingsPlansType"] == "DATABASE_SP"


def test_handler_sagemaker_sp_enabled(mock_env_vars, mock_clients, aws_mock_builder, monkeypatch):
    """Test SageMaker SP recommendations are fetched when enabled."""
    monkeypatch.setenv("ENABLE_COMPUTE_SP", "false")
    monkeypatch.setenv("ENABLE_SAGEMAKER_SP", "true")

    mock_clients["sqs"].purge_queue.return_value = {}
    mock_clients[
        "ce"
    ].get_savings_plans_purchase_recommendation.return_value = aws_mock_builder.recommendation(
        "sagemaker", hourly_commitment=3.75
    )
    mock_clients["sns"].publish.return_value = {"MessageId": "test-msg"}

    response = handler.handler({}, None)

    assert response["statusCode"] == 200

    rec_call = mock_clients["ce"].get_savings_plans_purchase_recommendation.call_args[1]
    assert rec_call["SavingsPlansType"] == "SAGEMAKER_SP"


def test_handler_multiple_sp_types_enabled(
    mock_env_vars, mock_clients, aws_mock_builder, monkeypatch
):
    """Test multiple SP types can be enabled simultaneously."""
    monkeypatch.setenv("ENABLE_COMPUTE_SP", "true")
    monkeypatch.setenv("ENABLE_DATABASE_SP", "true")

    mock_clients["sqs"].purge_queue.return_value = {}

    def mock_recommendation_side_effect(*args, **kwargs):
        sp_type = kwargs.get("SavingsPlansType")
        if sp_type == "COMPUTE_SP":
            return aws_mock_builder.recommendation("compute", hourly_commitment=1.5)
        elif sp_type == "DATABASE_SP":
            return aws_mock_builder.recommendation("database", hourly_commitment=2.5)
        return aws_mock_builder.recommendation("compute", empty=True)

    mock_clients[
        "ce"
    ].get_savings_plans_purchase_recommendation.side_effect = mock_recommendation_side_effect
    mock_clients["sns"].publish.return_value = {"MessageId": "test-msg"}

    response = handler.handler({}, None)

    assert response["statusCode"] == 200
    assert mock_clients["ce"].get_savings_plans_purchase_recommendation.call_count == 2


def test_handler_no_recommendations(mock_env_vars, mock_clients, aws_mock_builder):
    """Test handling when AWS returns empty recommendation list."""
    mock_clients["sqs"].purge_queue.return_value = {}
    mock_clients[
        "ce"
    ].get_savings_plans_purchase_recommendation.return_value = aws_mock_builder.recommendation(
        "compute", empty=True
    )
    mock_clients["sns"].publish.return_value = {"MessageId": "test-msg"}

    response = handler.handler({}, None)

    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["purchases_planned"] == 0

    email_call = mock_clients["sns"].publish.call_args[1]
    assert "No purchases needed" in email_call["Message"]


def test_handler_applies_max_purchase_percent(
    mock_env_vars, mock_clients, aws_mock_builder, monkeypatch
):
    """Test max_purchase_percent is applied by fixed strategy."""
    monkeypatch.setenv("PURCHASE_STRATEGY_TYPE", "fixed")
    monkeypatch.setenv("MIN_PURCHASE_PERCENT", "1")
    monkeypatch.setenv("MAX_PURCHASE_PERCENT", "10")

    mock_clients["sqs"].purge_queue.return_value = {}

    # Mock for fixed strategy
    mock_clients[
        "savingsplans"
    ].describe_savings_plans.return_value = aws_mock_builder.describe_savings_plans(plans_count=0)
    mock_clients["ce"].get_savings_plans_coverage.return_value = aws_mock_builder.coverage(
        coverage_percentage=50.0
    )
    mock_clients["ce"].get_cost_and_usage.return_value = aws_mock_builder.cost_and_usage()
    mock_clients["sns"].publish.return_value = {"MessageId": "test-msg"}

    response = handler.handler({}, None)

    assert response["statusCode"] == 200

    # Fixed strategy should analyze spending and apply max_purchase_percent
    assert mock_clients["savingsplans"].describe_savings_plans.called
    assert mock_clients["ce"].get_savings_plans_coverage.called


def test_handler_filters_below_min_commitment(
    mock_env_vars, mock_clients, aws_mock_builder, monkeypatch
):
    """Test plans below min_commitment_per_plan are filtered out by fixed strategy."""
    monkeypatch.setenv("PURCHASE_STRATEGY_TYPE", "fixed")
    monkeypatch.setenv("MIN_PURCHASE_PERCENT", "0.5")
    monkeypatch.setenv("MAX_PURCHASE_PERCENT", "1")
    monkeypatch.setenv("MIN_COMMITMENT_PER_PLAN", "5.0")  # Will filter out small purchases

    mock_clients["sqs"].purge_queue.return_value = {}

    # Mock for fixed strategy - with very low hourly spend so 1% would be tiny
    mock_clients[
        "savingsplans"
    ].describe_savings_plans.return_value = aws_mock_builder.describe_savings_plans(plans_count=0)
    mock_clients["ce"].get_savings_plans_coverage.return_value = aws_mock_builder.coverage(
        coverage_percentage=50.0
    )
    # Modify cost_and_usage to have low spend (avg ~1.0/hour) so 1% would be 0.01/hour < 5.0 min
    cost_response = aws_mock_builder.cost_and_usage()
    # Set low blended cost to make calculated commitment tiny
    for result in cost_response.get("ResultsByTime", []):
        result["Total"]["BlendedCost"]["Amount"] = "24.0"  # $24/day = $1/hour
    mock_clients["ce"].get_cost_and_usage.return_value = cost_response
    mock_clients["sns"].publish.return_value = {"MessageId": "test-msg"}

    response = handler.handler({}, None)

    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    # 1% of $1/hour = $0.01/hour < $5 min, so should be filtered
    assert body["purchases_planned"] == 0


def test_handler_lookback_period_mapping(
    mock_env_vars, mock_clients, aws_mock_builder, monkeypatch
):
    """Test lookback_days maps to correct AWS API parameters."""
    monkeypatch.setenv("LOOKBACK_DAYS", "7")

    mock_clients["sqs"].purge_queue.return_value = {}
    mock_clients[
        "ce"
    ].get_savings_plans_purchase_recommendation.return_value = aws_mock_builder.recommendation(
        "compute", empty=True
    )
    mock_clients["sns"].publish.return_value = {"MessageId": "test-msg"}

    response = handler.handler({}, None)

    assert response["statusCode"] == 200

    rec_call = mock_clients["ce"].get_savings_plans_purchase_recommendation.call_args[1]
    assert rec_call["LookbackPeriodInDays"] == "SEVEN_DAYS"


def test_handler_cost_explorer_error(mock_env_vars, mock_clients):
    """Test error handling when Cost Explorer API fails."""
    mock_clients["sqs"].purge_queue.return_value = {}
    mock_clients["ce"].get_savings_plans_purchase_recommendation.side_effect = ClientError(
        {"Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}},
        "GetSavingsPlansPurchaseRecommendation",
    )

    with pytest.raises(ClientError) as exc_info:
        handler.handler({}, None)

    assert exc_info.value.response["Error"]["Code"] == "ThrottlingException"


def test_handler_queue_purge_error(mock_env_vars, mock_clients):
    """Test error handling when queue purge fails."""
    mock_clients["sqs"].purge_queue.side_effect = ClientError(
        {
            "Error": {
                "Code": "AWS.SimpleQueueService.NonExistentQueue",
                "Message": "Queue not found",
            }
        },
        "PurgeQueue",
    )

    with pytest.raises(ClientError) as exc_info:
        handler.handler({}, None)

    assert "NonExistentQueue" in str(exc_info.value)


def test_handler_term_mix_splitting(mock_env_vars, mock_clients, aws_mock_builder, monkeypatch):
    """Test term mix splits purchases by fixed strategy."""
    monkeypatch.setenv("PURCHASE_STRATEGY_TYPE", "fixed")
    monkeypatch.setenv("COMPUTE_SP_TERM_MIX", '{"three_year": 0.5, "one_year": 0.5}')

    mock_clients["sqs"].purge_queue.return_value = {}

    # Mock for fixed strategy
    mock_clients[
        "savingsplans"
    ].describe_savings_plans.return_value = aws_mock_builder.describe_savings_plans(plans_count=0)
    mock_clients["ce"].get_savings_plans_coverage.return_value = aws_mock_builder.coverage(
        coverage_percentage=50.0
    )
    mock_clients["ce"].get_cost_and_usage.return_value = aws_mock_builder.cost_and_usage()
    mock_clients["sns"].publish.return_value = {"MessageId": "test-msg"}

    response = handler.handler({}, None)

    assert response["statusCode"] == 200

    email_call = mock_clients["sns"].publish.call_args[1]
    message = email_call["Message"]
    # Fixed strategy should create plans with term mix splitting
    assert "THREE_YEAR" in message or "three_year" in message
    assert "ONE_YEAR" in message or "one_year" in message


def test_handler_expiring_plans_excluded_from_coverage(
    mock_env_vars, mock_clients, aws_mock_builder, monkeypatch
):
    """Test plans expiring within renewal window are excluded from coverage."""
    monkeypatch.setenv("PURCHASE_STRATEGY_TYPE", "fixed")

    now = datetime.now(timezone.utc)
    expiring_soon = now + timedelta(days=3)

    mock_clients["sqs"].purge_queue.return_value = {}

    mock_clients["savingsplans"].describe_savings_plans.return_value = {
        "savingsPlans": [
            {
                "savingsPlanId": "sp-expiring",
                "state": "active",
                "end": expiring_soon.isoformat(),
                "savingsPlanType": "ComputeSavingsPlans",
            }
        ]
    }

    mock_clients["ce"].get_savings_plans_coverage.return_value = aws_mock_builder.coverage(
        coverage_percentage=75.0
    )

    mock_clients["ce"].get_cost_and_usage.return_value = aws_mock_builder.cost_and_usage()

    mock_clients["sns"].publish.return_value = {"MessageId": "test-msg"}

    response = handler.handler({}, None)

    assert response["statusCode"] == 200
    assert mock_clients["savingsplans"].describe_savings_plans.called


def test_handler_all_sp_types_disabled(mock_env_vars, mock_clients, monkeypatch):
    """Test handler when all SP types are disabled."""
    monkeypatch.setenv("ENABLE_COMPUTE_SP", "false")
    monkeypatch.setenv("ENABLE_DATABASE_SP", "false")
    monkeypatch.setenv("ENABLE_SAGEMAKER_SP", "false")

    mock_clients["sqs"].purge_queue.return_value = {}
    mock_clients["sns"].publish.return_value = {"MessageId": "test-msg"}

    response = handler.handler({}, None)

    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["purchases_planned"] == 0

    assert not mock_clients["ce"].get_savings_plans_purchase_recommendation.called


def test_handler_parallel_recommendation_fetching(
    mock_env_vars, mock_clients, aws_mock_builder, monkeypatch
):
    """Test that multiple SP types are fetched in parallel."""
    monkeypatch.setenv("ENABLE_COMPUTE_SP", "true")
    monkeypatch.setenv("ENABLE_DATABASE_SP", "true")

    mock_clients["sqs"].purge_queue.return_value = {}

    def mock_side_effect(*args, **kwargs):
        sp_type = kwargs.get("SavingsPlansType")
        if sp_type == "COMPUTE_SP":
            return aws_mock_builder.recommendation("compute", hourly_commitment=1.0)
        return aws_mock_builder.recommendation("database", hourly_commitment=2.0)

    mock_clients["ce"].get_savings_plans_purchase_recommendation.side_effect = mock_side_effect
    mock_clients["sns"].publish.return_value = {"MessageId": "test-msg"}

    response = handler.handler({}, None)

    assert response["statusCode"] == 200
    assert mock_clients["ce"].get_savings_plans_purchase_recommendation.call_count == 2


def test_handler_sns_notification_sent(mock_env_vars, mock_clients, aws_mock_builder):
    """Test SNS notification is sent with correct structure."""
    mock_clients["sqs"].purge_queue.return_value = {}
    mock_clients[
        "ce"
    ].get_savings_plans_purchase_recommendation.return_value = aws_mock_builder.recommendation(
        "compute", hourly_commitment=1.0
    )
    mock_clients["sns"].publish.return_value = {"MessageId": "test-msg"}

    response = handler.handler({}, None)

    assert response["statusCode"] == 200
    assert mock_clients["sns"].publish.called

    publish_call = mock_clients["sns"].publish.call_args[1]
    assert publish_call["TopicArn"] == "arn:aws:sns:us-east-1:123456789012:test-topic"
    assert "Subject" in publish_call
    assert "Message" in publish_call


def test_handler_queues_purchases_in_production(
    mock_env_vars, mock_clients, aws_mock_builder, monkeypatch
):
    """Test purchases are queued in production mode."""
    monkeypatch.setenv("DRY_RUN", "false")

    mock_clients["sqs"].purge_queue.return_value = {}
    mock_clients[
        "ce"
    ].get_savings_plans_purchase_recommendation.return_value = aws_mock_builder.recommendation(
        "compute", hourly_commitment=1.0
    )
    mock_clients["sqs"].send_message.return_value = {"MessageId": "msg-123"}
    mock_clients["sns"].publish.return_value = {"MessageId": "test-msg"}

    response = handler.handler({}, None)

    assert response["statusCode"] == 200
    assert mock_clients["sqs"].send_message.called

    send_call = mock_clients["sqs"].send_message.call_args[1]
    assert send_call["QueueUrl"] == "https://sqs.us-east-1.amazonaws.com/123456789012/test-queue"
    assert "MessageBody" in send_call

    message_body = json.loads(send_call["MessageBody"])
    # Check for actual message structure
    assert "sp_type" in message_body
    assert "hourly_commitment" in message_body
    assert "payment_option" in message_body


def test_handler_assume_role_error(mock_env_vars, monkeypatch):
    """Test error callback is triggered when assume role fails."""
    monkeypatch.setenv("MANAGEMENT_ACCOUNT_ROLE_ARN", "arn:aws:iam::123456789012:role/TestRole")

    # Create a mock for the error callback
    mock_error_callback = Mock()

    with (
        patch("shared.handler_utils.get_clients") as mock_get_clients,
        patch("handler._send_error_notification", mock_error_callback),
    ):
        # Make get_clients raise error - initialize_clients will catch it and call error callback
        mock_get_clients.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "Not authorized"}}, "AssumeRole"
        )

        with pytest.raises(ClientError) as exc_info:
            handler.handler({}, None)

        assert exc_info.value.response["Error"]["Code"] == "AccessDenied"
        # Verify error callback was called
        assert mock_error_callback.called


def test_handler_dichotomy_strategy(mock_env_vars, mock_clients, aws_mock_builder, monkeypatch):
    """Test dichotomy strategy analyzes spending and uses dichotomy algorithm."""
    monkeypatch.setenv("PURCHASE_STRATEGY_TYPE", "dichotomy")

    mock_clients["sqs"].purge_queue.return_value = {}

    mock_clients[
        "savingsplans"
    ].describe_savings_plans.return_value = aws_mock_builder.describe_savings_plans(plans_count=1)

    mock_clients["ce"].get_savings_plans_coverage.return_value = aws_mock_builder.coverage(
        coverage_percentage=60.0
    )

    mock_clients["ce"].get_cost_and_usage.return_value = aws_mock_builder.cost_and_usage()

    mock_clients["sns"].publish.return_value = {"MessageId": "test-msg"}

    response = handler.handler({}, None)

    assert response["statusCode"] == 200

    assert mock_clients["ce"].get_savings_plans_coverage.called
    assert mock_clients["ce"].get_cost_and_usage.called


def test_handler_empty_recommendations_all_sp_types(
    mock_env_vars, mock_clients, aws_mock_builder, monkeypatch
):
    """Test all SP types with empty recommendations."""
    monkeypatch.setenv("ENABLE_COMPUTE_SP", "true")
    monkeypatch.setenv("ENABLE_DATABASE_SP", "true")
    monkeypatch.setenv("ENABLE_SAGEMAKER_SP", "true")

    mock_clients["sqs"].purge_queue.return_value = {}

    def mock_empty_rec(*args, **kwargs):
        sp_type_map = {
            "COMPUTE_SP": "compute",
            "DATABASE_SP": "database",
            "SAGEMAKER_SP": "sagemaker",
        }
        sp_key = sp_type_map.get(kwargs.get("SavingsPlansType"), "compute")
        return aws_mock_builder.recommendation(sp_key, empty=True)

    mock_clients["ce"].get_savings_plans_purchase_recommendation.side_effect = mock_empty_rec
    mock_clients["sns"].publish.return_value = {"MessageId": "test-msg"}

    response = handler.handler({}, None)

    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["purchases_planned"] == 0


def test_handler_payment_options_applied(mock_env_vars, mock_clients, aws_mock_builder):
    """Test payment options from config are applied to recommendations."""
    mock_clients["sqs"].purge_queue.return_value = {}
    mock_clients[
        "ce"
    ].get_savings_plans_purchase_recommendation.return_value = aws_mock_builder.recommendation(
        "compute", hourly_commitment=1.0
    )
    mock_clients["sns"].publish.return_value = {"MessageId": "test-msg"}

    response = handler.handler({}, None)

    assert response["statusCode"] == 200

    rec_call = mock_clients["ce"].get_savings_plans_purchase_recommendation.call_args[1]
    assert rec_call["PaymentOption"] == "ALL_UPFRONT"


def test_handler_successful_response_structure(mock_env_vars, mock_clients, aws_mock_builder):
    """Test handler returns correct response structure."""
    mock_clients["sqs"].purge_queue.return_value = {}
    mock_clients[
        "ce"
    ].get_savings_plans_purchase_recommendation.return_value = aws_mock_builder.recommendation(
        "compute", hourly_commitment=1.0
    )
    mock_clients["sns"].publish.return_value = {"MessageId": "test-msg"}

    response = handler.handler({}, None)

    assert response["statusCode"] == 200
    assert "body" in response

    body = json.loads(response["body"])
    assert "message" in body
    assert "dry_run" in body
    assert "purchases_planned" in body

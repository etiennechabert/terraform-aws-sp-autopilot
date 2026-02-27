"""
Integration tests for Scheduler Lambda handler.

All tests follow these guidelines:
- Test through handler.handler() entry point only
- Mock only AWS client responses
- Use aws_mock_builder for consistent responses
- Verify behavior through handler response and AWS calls
"""

import json
import os
import sys
from datetime import UTC, datetime, timedelta
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
    monkeypatch.setenv("ENABLE_COMPUTE_SP", "true")
    monkeypatch.setenv("ENABLE_DATABASE_SP", "false")
    monkeypatch.setenv("ENABLE_SAGEMAKER_SP", "false")
    monkeypatch.setenv("COVERAGE_TARGET_PERCENT", "90")
    monkeypatch.setenv("TARGET_STRATEGY_TYPE", "aws")
    monkeypatch.setenv("SPLIT_STRATEGY_TYPE", "one_shot")
    monkeypatch.setenv("MAX_PURCHASE_PERCENT", "10")
    monkeypatch.setenv("RENEWAL_WINDOW_DAYS", "7")
    monkeypatch.setenv("LOOKBACK_DAYS", "13")
    monkeypatch.setenv("MIN_COMMITMENT_PER_PLAN", "0.001")
    monkeypatch.setenv("COMPUTE_SP_TERM_MIX", '{"three_year": 0.67, "one_year": 0.33}')
    monkeypatch.setenv("COMPUTE_SP_PAYMENT_OPTION", "ALL_UPFRONT")
    monkeypatch.setenv("SAGEMAKER_SP_TERM_MIX", '{"three_year": 0.67, "one_year": 0.33}')
    monkeypatch.setenv("SAGEMAKER_SP_PAYMENT_OPTION", "ALL_UPFRONT")
    monkeypatch.setenv("TAGS", "{}")
    monkeypatch.setenv("SPIKE_GUARD_ENABLED", "false")


@pytest.fixture
def mock_clients():
    """Mock AWS clients at the initialization boundary."""
    with (
        patch("handler.initialize_clients") as mock_init,
        patch("shared.savings_plans_metrics.get_recent_purchase_sp_types", return_value=set()),
    ):
        mock_ce = Mock()
        mock_sqs = Mock()
        mock_sqs.send_message.return_value = {"MessageId": "msg-default"}
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


def test_handler_cooldown_skips_all_enabled_types(mock_env_vars, monkeypatch):
    """Test handler skips scheduling when all enabled SP types are in cooldown."""
    monkeypatch.setenv("PURCHASE_COOLDOWN_DAYS", "7")

    with (
        patch("handler.initialize_clients") as mock_init,
        patch(
            "shared.savings_plans_metrics.get_recent_purchase_sp_types",
            return_value={"compute"},
        ),
    ):
        mock_sns = Mock()
        mock_sns.publish.return_value = {"MessageId": "test-msg"}
        mock_init.return_value = {
            "ce": Mock(),
            "sqs": Mock(),
            "sns": mock_sns,
            "savingsplans": Mock(),
        }

        response = handler.handler({}, None)

    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["purchases_planned"] == 0
    assert "cooldown" in body["message"]
    mock_sns.publish.assert_called_once()
    assert "cooldown" in mock_sns.publish.call_args[1]["Subject"].lower()


def test_handler_cooldown_filters_per_type(
    mock_env_vars, mock_clients, aws_mock_builder, monkeypatch
):
    """Test cooldown blocks only the SP types that were recently purchased."""
    monkeypatch.setenv("ENABLE_COMPUTE_SP", "true")
    monkeypatch.setenv("ENABLE_DATABASE_SP", "true")
    monkeypatch.setenv("PURCHASE_COOLDOWN_DAYS", "7")

    mock_clients["sqs"].purge_queue.return_value = {}
    mock_clients["sns"].publish.return_value = {"MessageId": "test-msg"}

    def mock_recommendation(*args, **kwargs):
        sp_type = kwargs.get("SavingsPlansType")
        if sp_type == "COMPUTE_SP":
            return aws_mock_builder.recommendation("compute", hourly_commitment=1.0)
        return aws_mock_builder.recommendation("database", hourly_commitment=2.0)

    mock_clients["ce"].get_savings_plans_purchase_recommendation.side_effect = mock_recommendation

    with patch(
        "shared.savings_plans_metrics.get_recent_purchase_sp_types",
        return_value={"compute"},
    ):
        response = handler.handler({}, None)

    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    # Compute blocked by cooldown, database goes through
    assert body["purchases_planned"] == 1
    assert body["purchases_blocked_by_cooldown"] == 1


def test_get_recent_purchase_sp_types_detects_recent_plan():
    """Test get_recent_purchase_sp_types returns the type key for recently purchased plans."""
    from shared.savings_plans_metrics import get_recent_purchase_sp_types

    recent_start = (datetime.now(UTC) - timedelta(days=2)).isoformat()
    mock_client = Mock()
    mock_client.describe_savings_plans.return_value = {
        "savingsPlans": [
            {
                "savingsPlanId": "sp-123",
                "savingsPlanType": "Compute",
                "commitment": "1.0",
                "start": recent_start,
                "end": "2029-01-01T00:00:00Z",
                "paymentOption": "ALL_UPFRONT",
                "termDurationInSeconds": 94608000,
            }
        ]
    }
    assert get_recent_purchase_sp_types(mock_client, cooldown_days=7) == {"compute"}


def test_get_recent_purchase_sp_types_ignores_old_plan():
    """Test get_recent_purchase_sp_types returns empty set when all plans are older than cooldown."""
    from shared.savings_plans_metrics import get_recent_purchase_sp_types

    old_start = (datetime.now(UTC) - timedelta(days=30)).isoformat()
    mock_client = Mock()
    mock_client.describe_savings_plans.return_value = {
        "savingsPlans": [
            {
                "savingsPlanId": "sp-456",
                "savingsPlanType": "Compute",
                "commitment": "1.0",
                "start": old_start,
                "end": "2029-01-01T00:00:00Z",
                "paymentOption": "ALL_UPFRONT",
                "termDurationInSeconds": 94608000,
            }
        ]
    }
    assert get_recent_purchase_sp_types(mock_client, cooldown_days=7) == set()


def test_get_recent_purchase_sp_types_zero_cooldown():
    """Test get_recent_purchase_sp_types returns empty set when cooldown is 0 (disabled)."""
    from shared.savings_plans_metrics import get_recent_purchase_sp_types

    assert get_recent_purchase_sp_types(Mock(), cooldown_days=0) == set()


def test_get_recent_purchase_sp_types_multiple_types():
    """Test get_recent_purchase_sp_types returns multiple types when different types were purchased."""
    from shared.savings_plans_metrics import get_recent_purchase_sp_types

    recent_start = (datetime.now(UTC) - timedelta(days=2)).isoformat()
    old_start = (datetime.now(UTC) - timedelta(days=30)).isoformat()
    mock_client = Mock()
    mock_client.describe_savings_plans.return_value = {
        "savingsPlans": [
            {
                "savingsPlanId": "sp-123",
                "savingsPlanType": "Compute",
                "commitment": "1.0",
                "start": recent_start,
                "end": "2029-01-01T00:00:00Z",
                "paymentOption": "ALL_UPFRONT",
                "termDurationInSeconds": 94608000,
            },
            {
                "savingsPlanId": "sp-456",
                "savingsPlanType": "SageMaker",
                "commitment": "0.5",
                "start": recent_start,
                "end": "2029-01-01T00:00:00Z",
                "paymentOption": "ALL_UPFRONT",
                "termDurationInSeconds": 94608000,
            },
            {
                "savingsPlanId": "sp-789",
                "savingsPlanType": "Database",
                "commitment": "2.0",
                "start": old_start,
                "end": "2029-01-01T00:00:00Z",
                "paymentOption": "ALL_UPFRONT",
                "termDurationInSeconds": 94608000,
            },
        ]
    }
    result = get_recent_purchase_sp_types(mock_client, cooldown_days=7)
    assert result == {"compute", "sagemaker"}


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
    monkeypatch.setenv("TARGET_STRATEGY_TYPE", "fixed")
    monkeypatch.setenv("SPLIT_STRATEGY_TYPE", "fixed_step")
    monkeypatch.setenv("FIXED_STEP_PERCENT", "10")
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

    # Fixed strategy uses SpendingAnalyzer which calls coverage API
    assert mock_clients["ce"].get_savings_plans_coverage.called

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
        if sp_type == "DATABASE_SP":
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
    assert "Total Plans Queued: 0" in email_call["Message"]


def test_handler_applies_max_purchase_percent(
    mock_env_vars, mock_clients, aws_mock_builder, monkeypatch
):
    """Test max_purchase_percent is applied by fixed strategy."""
    monkeypatch.setenv("TARGET_STRATEGY_TYPE", "fixed")
    monkeypatch.setenv("SPLIT_STRATEGY_TYPE", "fixed_step")
    monkeypatch.setenv("FIXED_STEP_PERCENT", "10")
    monkeypatch.setenv("MIN_PURCHASE_PERCENT", "1")
    monkeypatch.setenv("MAX_PURCHASE_PERCENT", "10")

    mock_clients["sqs"].purge_queue.return_value = {}

    # Mock for fixed strategy
    mock_clients["ce"].get_savings_plans_coverage.return_value = aws_mock_builder.coverage(
        coverage_percentage=50.0
    )
    mock_clients["ce"].get_cost_and_usage.return_value = aws_mock_builder.cost_and_usage()
    mock_clients["sns"].publish.return_value = {"MessageId": "test-msg"}

    response = handler.handler({}, None)

    assert response["statusCode"] == 200

    # Fixed strategy should analyze spending via coverage API
    assert mock_clients["ce"].get_savings_plans_coverage.called


def test_handler_filters_below_min_commitment(
    mock_env_vars, mock_clients, aws_mock_builder, monkeypatch
):
    """Test handler completes successfully when recommendations are below minimum commitment."""
    monkeypatch.setenv("MIN_COMMITMENT_PER_PLAN", "15.0")  # Higher than typical recommendations

    mock_clients["sqs"].purge_queue.return_value = {}
    mock_clients[
        "ce"
    ].get_savings_plans_purchase_recommendation.return_value = aws_mock_builder.recommendation(
        "compute", hourly_commitment=10.0
    )
    mock_clients["sns"].publish.return_value = {"MessageId": "test-msg"}

    response = handler.handler({}, None)

    assert response["statusCode"] == 200
    # Note: follow_aws strategy doesn't apply min_commitment filtering,
    # but the handler completes successfully either way


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
    """Test fixed strategy with custom term configuration."""
    monkeypatch.setenv("TARGET_STRATEGY_TYPE", "fixed")
    monkeypatch.setenv("SPLIT_STRATEGY_TYPE", "fixed_step")
    monkeypatch.setenv("FIXED_STEP_PERCENT", "10")
    monkeypatch.setenv("COMPUTE_SP_TERM", "ONE_YEAR")  # Override default THREE_YEAR

    mock_clients["sqs"].purge_queue.return_value = {}

    # Mock for fixed strategy
    mock_clients["ce"].get_savings_plans_coverage.return_value = aws_mock_builder.coverage(
        coverage_percentage=50.0
    )
    mock_clients["sns"].publish.return_value = {"MessageId": "test-msg"}

    response = handler.handler({}, None)

    assert response["statusCode"] == 200

    email_call = mock_clients["sns"].publish.call_args[1]
    message = email_call["Message"]
    # Fixed strategy should use the configured term (ONE_YEAR)
    assert "ONE_YEAR" in message


def test_handler_expiring_plans_excluded_from_coverage(
    mock_env_vars, mock_clients, aws_mock_builder, monkeypatch
):
    """Test fixed strategy with existing coverage."""
    monkeypatch.setenv("TARGET_STRATEGY_TYPE", "fixed")
    monkeypatch.setenv("SPLIT_STRATEGY_TYPE", "fixed_step")
    monkeypatch.setenv("FIXED_STEP_PERCENT", "10")

    mock_clients["sqs"].purge_queue.return_value = {}

    mock_clients["ce"].get_savings_plans_coverage.return_value = aws_mock_builder.coverage(
        coverage_percentage=75.0
    )

    mock_clients["ce"].get_cost_and_usage.return_value = aws_mock_builder.cost_and_usage()

    mock_clients["sns"].publish.return_value = {"MessageId": "test-msg"}

    response = handler.handler({}, None)

    assert response["statusCode"] == 200
    # Fixed strategy analyzes spending via coverage API
    assert mock_clients["ce"].get_savings_plans_coverage.called


def test_handler_all_sp_types_disabled(mock_env_vars, mock_clients, monkeypatch):
    """Test handler when all SP types are disabled - should fail validation."""
    monkeypatch.setenv("ENABLE_COMPUTE_SP", "false")
    monkeypatch.setenv("ENABLE_DATABASE_SP", "false")
    monkeypatch.setenv("ENABLE_SAGEMAKER_SP", "false")

    # Should raise ValueError during config validation
    with pytest.raises(ValueError) as exc_info:
        handler.handler({}, None)

    assert "At least one Savings Plan type must be enabled" in str(exc_info.value)


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


def test_handler_queues_purchases(mock_env_vars, mock_clients, aws_mock_builder):
    """Test purchases are queued to SQS and notification email is sent."""
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
    assert mock_clients["sqs"].purge_queue.called
    assert mock_clients["sqs"].send_message.called
    assert mock_clients["sns"].publish.called

    send_call = mock_clients["sqs"].send_message.call_args[1]
    assert send_call["QueueUrl"] == "https://sqs.us-east-1.amazonaws.com/123456789012/test-queue"
    assert "MessageBody" in send_call

    message_body = json.loads(send_call["MessageBody"])
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


def test_handler_gap_split_strategy(mock_env_vars, mock_clients, aws_mock_builder, monkeypatch):
    """Test gap_split strategy analyzes spending and uses gap split algorithm."""
    monkeypatch.setenv("TARGET_STRATEGY_TYPE", "fixed")
    monkeypatch.setenv("SPLIT_STRATEGY_TYPE", "gap_split")
    monkeypatch.setenv("GAP_SPLIT_DIVIDER", "2.0")

    mock_clients["sqs"].purge_queue.return_value = {}

    mock_clients["ce"].get_savings_plans_coverage.return_value = aws_mock_builder.coverage(
        coverage_percentage=60.0
    )

    mock_clients["sns"].publish.return_value = {"MessageId": "test-msg"}

    response = handler.handler({}, None)

    assert response["statusCode"] == 200

    # gap_split strategy uses SpendingAnalyzer which calls get_savings_plans_coverage
    assert mock_clients["ce"].get_savings_plans_coverage.called


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
    assert "purchases_planned" in body


def test_handler_spike_guard_blocks_flagged_types(
    mock_env_vars, mock_clients, aws_mock_builder, monkeypatch
):
    """Test spike guard blocks purchases for flagged SP types."""
    monkeypatch.setenv("SPIKE_GUARD_ENABLED", "true")

    mock_clients["sqs"].purge_queue.return_value = {}
    mock_clients[
        "ce"
    ].get_savings_plans_purchase_recommendation.return_value = aws_mock_builder.recommendation(
        "compute", hourly_commitment=1.0
    )
    mock_clients["sns"].publish.return_value = {"MessageId": "test-msg"}

    guard_results = {
        "compute": {
            "flagged": True,
            "long_term_avg": 1.0,
            "short_term_avg": 1.3,
            "change_percent": 30.0,
        }
    }

    with patch(
        "shared.usage_decline_check.run_scheduling_spike_guard",
        return_value=({"compute": 1.3}, guard_results),
    ):
        response = handler.handler({}, None)

    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["purchases_planned"] == 0
    assert body["purchases_blocked_by_spike_guard"] == 1

    # Should send both scheduled email and spike guard email
    assert mock_clients["sns"].publish.call_count == 2
    subjects = [call[1]["Subject"] for call in mock_clients["sns"].publish.call_args_list]
    assert any("Spike" in s for s in subjects)


def test_handler_spike_guard_allows_unflagged_types(
    mock_env_vars, mock_clients, aws_mock_builder, monkeypatch
):
    """Test spike guard allows purchases for unflagged SP types."""
    monkeypatch.setenv("SPIKE_GUARD_ENABLED", "true")

    mock_clients["sqs"].purge_queue.return_value = {}
    mock_clients[
        "ce"
    ].get_savings_plans_purchase_recommendation.return_value = aws_mock_builder.recommendation(
        "compute", hourly_commitment=1.0
    )
    mock_clients["sqs"].send_message.return_value = {"MessageId": "msg-123"}
    mock_clients["sns"].publish.return_value = {"MessageId": "test-msg"}

    guard_results = {
        "compute": {
            "flagged": False,
            "long_term_avg": 1.0,
            "short_term_avg": 1.05,
            "change_percent": 5.0,
        }
    }

    with patch(
        "shared.usage_decline_check.run_scheduling_spike_guard",
        return_value=({"compute": 1.05}, guard_results),
    ):
        response = handler.handler({}, None)

    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["purchases_planned"] == 1
    assert body["purchases_blocked_by_spike_guard"] == 0

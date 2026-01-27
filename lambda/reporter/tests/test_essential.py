"""
Essential integration tests for Reporter Lambda.

Tests the full handler execution path with various scenarios.
All tests follow TESTING.MD guidelines:
- Test through handler.handler() entry point only
- Mock only AWS client responses
- Use aws_mock_builder for consistent responses
"""

import json
import os
import sys
from unittest.mock import Mock, patch

import pytest
from botocore.exceptions import ClientError


# Set default environment variables before any imports
# This ensures config can be loaded when modules are imported
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("REPORTS_BUCKET", "test-bucket")
os.environ.setdefault("SNS_TOPIC_ARN", "arn:aws:sns:us-east-1:123456789012:test-topic")
os.environ.setdefault("REPORT_FORMAT", "html")
os.environ.setdefault("EMAIL_REPORTS", "true")
os.environ.setdefault("LOOKBACK_DAYS", "7")
os.environ.setdefault("GRANULARITY", "HOURLY")
os.environ.setdefault("COVERAGE_TARGET_PERCENT", "90")
os.environ.setdefault("ENABLE_COMPUTE_SP", "true")
os.environ.setdefault("ENABLE_DATABASE_SP", "false")
os.environ.setdefault("ENABLE_SAGEMAKER_SP", "false")
os.environ.setdefault("LOW_UTILIZATION_THRESHOLD", "70")
os.environ.setdefault("LOW_UTILIZATION_ALERT_ENABLED", "false")
os.environ.setdefault("INCLUDE_DEBUG_DATA", "true")  # Enable debug mode for aws_debug.py coverage

# Add lambda directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import handler


@pytest.fixture
def mock_env_vars(monkeypatch):
    """Override environment variables for specific tests if needed.

    Note: Default env vars are set at module level before imports.
    This fixture is only needed when tests require different values.
    """
    # No-op by default since env vars are set at module level
    # Tests can use monkeypatch directly if they need to override


@pytest.fixture
def mock_clients():
    """Mock AWS clients at the initialization boundary."""
    # Patch in handler module since initialize_clients is imported directly
    with patch("handler.initialize_clients") as mock_init:
        mock_ce = Mock()
        mock_sp = Mock()
        mock_s3 = Mock()
        mock_sns = Mock()

        # Mock S3 generate_presigned_url to return a string (for email notifications)
        mock_s3.generate_presigned_url.return_value = (
            "https://test-bucket.s3.amazonaws.com/test-report.html?X-Amz-Algorithm=AWS4-HMAC-SHA256"
        )

        mock_init.return_value = {
            "ce": mock_ce,
            "savingsplans": mock_sp,
            "s3": mock_s3,
            "sns": mock_sns,
        }

        yield {
            "ce": mock_ce,
            "savingsplans": mock_sp,
            "s3": mock_s3,
            "sns": mock_sns,
        }


def test_handler_success_with_active_plans(mock_env_vars, mock_clients, aws_mock_builder):
    """Test successful report generation with active Savings Plans."""
    # Mock SpendingAnalyzer - Cost Explorer coverage data
    mock_clients["ce"].get_savings_plans_coverage.return_value = aws_mock_builder.coverage(
        coverage_percentage=75.0
    )

    # Mock get_savings_plans_summary - Savings Plans data
    mock_clients[
        "savingsplans"
    ].describe_savings_plans.return_value = aws_mock_builder.describe_savings_plans(plans_count=2)

    # Mock get_savings_plans_summary - utilization and savings
    mock_clients["ce"].get_savings_plans_utilization.return_value = aws_mock_builder.utilization(
        utilization_percentage=85.0
    )

    # Mock scheduler_preview recommendations
    mock_clients[
        "ce"
    ].get_savings_plans_purchase_recommendation.return_value = aws_mock_builder.recommendation(
        sp_type="compute", hourly_commitment=5.0
    )

    # Mock S3 upload
    mock_clients["s3"].put_object.return_value = {}

    # Mock SNS email notification
    mock_clients["sns"].publish.return_value = {"MessageId": "test-message-id"}

    # Execute handler
    response = handler.handler({}, {})

    # Verify success response
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert "completed successfully" in body["message"]
    assert "s3_object_key" in body
    assert body["active_plans"] == 2

    # Verify S3 upload was called
    assert mock_clients["s3"].put_object.called
    s3_call = mock_clients["s3"].put_object.call_args[1]
    assert s3_call["Bucket"] == "test-bucket"
    assert "savings-plans-report_" in s3_call["Key"]

    # Verify email was sent (EMAIL_REPORTS=true)
    assert mock_clients["sns"].publish.called
    sns_call = mock_clients["sns"].publish.call_args[1]
    assert sns_call["TopicArn"] == "arn:aws:sns:us-east-1:123456789012:test-topic"
    assert "Savings Plans Report" in sns_call["Subject"]


def test_handler_success_without_email(mock_env_vars, mock_clients, aws_mock_builder, monkeypatch):
    """Test successful report generation without email notification."""
    monkeypatch.setenv("EMAIL_REPORTS", "false")

    # Mock AWS responses
    mock_clients["ce"].get_savings_plans_coverage.return_value = aws_mock_builder.coverage(
        coverage_percentage=50.0
    )
    mock_clients[
        "savingsplans"
    ].describe_savings_plans.return_value = aws_mock_builder.describe_savings_plans(plans_count=1)
    mock_clients["ce"].get_savings_plans_utilization.return_value = aws_mock_builder.utilization(
        utilization_percentage=80.0
    )
    mock_clients[
        "ce"
    ].get_savings_plans_purchase_recommendation.return_value = aws_mock_builder.recommendation(
        sp_type="compute", hourly_commitment=5.0
    )
    mock_clients["s3"].put_object.return_value = {}

    # Execute handler
    response = handler.handler({}, {})

    # Verify success
    assert response["statusCode"] == 200
    assert mock_clients["s3"].put_object.called

    # Verify email was NOT sent (EMAIL_REPORTS=false)
    assert not mock_clients["sns"].publish.called


def test_handler_success_with_no_active_plans(mock_env_vars, mock_clients, aws_mock_builder):
    """Test successful execution when no Savings Plans exist."""
    # Mock no coverage (no plans)
    mock_clients["ce"].get_savings_plans_coverage.return_value = aws_mock_builder.coverage(
        coverage_percentage=0.0
    )

    # Mock no active plans
    mock_clients[
        "savingsplans"
    ].describe_savings_plans.return_value = aws_mock_builder.describe_savings_plans(plans_count=0)

    # Mock utilization (no data)
    mock_clients["ce"].get_savings_plans_utilization.return_value = aws_mock_builder.utilization(
        utilization_percentage=0.0
    )

    mock_clients["s3"].put_object.return_value = {}
    mock_clients["sns"].publish.return_value = {"MessageId": "test-message-id"}

    # Execute handler
    response = handler.handler({}, {})

    # Verify success even with no plans
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["active_plans"] == 0

    # Report still generated and uploaded
    assert mock_clients["s3"].put_object.called


def test_handler_csv_format(mock_env_vars, mock_clients, aws_mock_builder, monkeypatch):
    """Test report generation in CSV format."""
    monkeypatch.setenv("REPORT_FORMAT", "csv")

    # Mock AWS responses
    mock_clients["ce"].get_savings_plans_coverage.return_value = aws_mock_builder.coverage(
        coverage_percentage=75.0
    )
    mock_clients[
        "savingsplans"
    ].describe_savings_plans.return_value = aws_mock_builder.describe_savings_plans(plans_count=1)
    mock_clients["ce"].get_savings_plans_utilization.return_value = aws_mock_builder.utilization(
        utilization_percentage=85.0
    )
    mock_clients["s3"].put_object.return_value = {}
    mock_clients["sns"].publish.return_value = {"MessageId": "test-message-id"}

    # Execute handler
    response = handler.handler({}, {})

    # Verify success
    assert response["statusCode"] == 200

    # Verify S3 upload uses .csv extension
    s3_call = mock_clients["s3"].put_object.call_args[1]
    assert s3_call["Key"].endswith(".csv")
    assert s3_call["ContentType"] == "text/csv"


def test_handler_json_format(mock_env_vars, mock_clients, aws_mock_builder, monkeypatch):
    """Test report generation in JSON format."""
    monkeypatch.setenv("REPORT_FORMAT", "json")

    # Mock AWS responses
    mock_clients["ce"].get_savings_plans_coverage.return_value = aws_mock_builder.coverage(
        coverage_percentage=75.0
    )
    mock_clients[
        "savingsplans"
    ].describe_savings_plans.return_value = aws_mock_builder.describe_savings_plans(plans_count=1)
    mock_clients["ce"].get_savings_plans_utilization.return_value = aws_mock_builder.utilization(
        utilization_percentage=85.0
    )
    mock_clients["s3"].put_object.return_value = {}
    mock_clients["sns"].publish.return_value = {"MessageId": "test-message-id"}

    # Execute handler
    response = handler.handler({}, {})

    # Verify success
    assert response["statusCode"] == 200

    # Verify S3 upload uses .json extension
    s3_call = mock_clients["s3"].put_object.call_args[1]
    assert s3_call["Key"].endswith(".json")
    assert s3_call["ContentType"] == "application/json"


def test_handler_failure_cost_explorer_unavailable(mock_env_vars, mock_clients):
    """Test error handling when Cost Explorer API fails."""
    # Mock Cost Explorer failure
    error_response = {
        "Error": {"Code": "ServiceUnavailableException", "Message": "Service unavailable"}
    }
    mock_clients["ce"].get_savings_plans_coverage.side_effect = ClientError(
        error_response, "GetSavingsPlansCoverage"
    )

    # Execute handler - should propagate error
    with pytest.raises(ClientError) as exc_info:
        handler.handler({}, {})

    assert exc_info.value.response["Error"]["Code"] == "ServiceUnavailableException"


def test_handler_failure_savings_plans_api_error(mock_env_vars, mock_clients, aws_mock_builder):
    """Test error handling when Savings Plans API fails."""
    # Mock successful Cost Explorer call
    mock_clients["ce"].get_savings_plans_coverage.return_value = aws_mock_builder.coverage(
        coverage_percentage=75.0
    )

    # Mock Savings Plans API failure
    error_response = {"Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}}
    mock_clients["savingsplans"].describe_savings_plans.side_effect = ClientError(
        error_response, "DescribeSavingsPlans"
    )

    # Execute handler - should propagate error
    with pytest.raises(ClientError) as exc_info:
        handler.handler({}, {})

    assert exc_info.value.response["Error"]["Code"] == "ThrottlingException"


def test_handler_failure_s3_upload_error(mock_env_vars, mock_clients, aws_mock_builder):
    """Test error handling when S3 upload fails."""
    # Mock successful data collection
    mock_clients["ce"].get_savings_plans_coverage.return_value = aws_mock_builder.coverage(
        coverage_percentage=75.0
    )
    mock_clients[
        "savingsplans"
    ].describe_savings_plans.return_value = aws_mock_builder.describe_savings_plans(plans_count=2)
    mock_clients["ce"].get_savings_plans_utilization.return_value = aws_mock_builder.utilization(
        utilization_percentage=85.0
    )

    # Mock S3 upload failure
    error_response = {"Error": {"Code": "NoSuchBucket", "Message": "Bucket does not exist"}}
    mock_clients["s3"].put_object.side_effect = ClientError(error_response, "PutObject")

    # Execute handler - should propagate error
    with pytest.raises(ClientError) as exc_info:
        handler.handler({}, {})

    assert exc_info.value.response["Error"]["Code"] == "NoSuchBucket"


def test_handler_low_utilization_alert_triggered(
    mock_env_vars, mock_clients, aws_mock_builder, monkeypatch
):
    """Test low utilization alert is sent when utilization below threshold."""
    monkeypatch.setenv("LOW_UTILIZATION_ALERT_ENABLED", "true")
    monkeypatch.setenv("LOW_UTILIZATION_THRESHOLD", "75")
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/test")
    monkeypatch.setenv("TEAMS_WEBHOOK_URL", "https://hooks.teams.com/test")

    # Mock AWS responses with low utilization (65%)
    mock_clients["ce"].get_savings_plans_coverage.return_value = aws_mock_builder.coverage(
        coverage_percentage=80.0
    )
    mock_clients[
        "savingsplans"
    ].describe_savings_plans.return_value = aws_mock_builder.describe_savings_plans(plans_count=2)
    mock_clients["ce"].get_savings_plans_utilization.return_value = (
        aws_mock_builder.utilization(utilization_percentage=65.0)  # Below 75% threshold
    )
    mock_clients["s3"].put_object.return_value = {}
    mock_clients["sns"].publish.return_value = {"MessageId": "test-message-id"}

    # Mock urllib3 PoolManager request to test Slack/Teams webhook code paths
    mock_response = Mock()
    mock_response.status = 200

    with patch("shared.notifications.http.request", return_value=mock_response):
        # Execute handler
        response = handler.handler({}, {})

    # Verify success
    assert response["statusCode"] == 200

    # Verify SNS was called twice: once for alert, once for report email
    assert mock_clients["sns"].publish.call_count == 2

    # Verify first call is low utilization alert
    first_call = mock_clients["sns"].publish.call_args_list[0][1]
    assert "Low Savings Plans Utilization Alert" in first_call["Subject"]
    assert "65" in first_call["Subject"]  # Current utilization
    assert "75" in first_call["Subject"]  # Threshold


def test_handler_low_utilization_alert_not_triggered(
    mock_env_vars, mock_clients, aws_mock_builder, monkeypatch
):
    """Test no low utilization alert when utilization above threshold."""
    monkeypatch.setenv("LOW_UTILIZATION_ALERT_ENABLED", "true")
    monkeypatch.setenv("LOW_UTILIZATION_THRESHOLD", "75")
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/test")
    monkeypatch.setenv("TEAMS_WEBHOOK_URL", "https://hooks.teams.com/test")

    # Mock AWS responses with high utilization (85%)
    mock_clients["ce"].get_savings_plans_coverage.return_value = aws_mock_builder.coverage(
        coverage_percentage=80.0
    )
    mock_clients[
        "savingsplans"
    ].describe_savings_plans.return_value = aws_mock_builder.describe_savings_plans(plans_count=2)
    mock_clients["ce"].get_savings_plans_utilization.return_value = (
        aws_mock_builder.utilization(utilization_percentage=85.0)  # Above 75% threshold
    )
    mock_clients["s3"].put_object.return_value = {}
    mock_clients["sns"].publish.return_value = {"MessageId": "test-message-id"}

    # Mock urllib3 PoolManager for webhook notifications (though alert won't trigger)
    mock_response = Mock()
    mock_response.status = 200

    with patch("shared.notifications.http.request", return_value=mock_response):
        # Execute handler
        response = handler.handler({}, {})

    # Verify success
    assert response["statusCode"] == 200

    # Verify SNS was called only once (for report email, not alert)
    assert mock_clients["sns"].publish.call_count == 1
    call_args = mock_clients["sns"].publish.call_args[1]
    assert "Low Utilization Alert" not in call_args["Subject"]
    assert "Report" in call_args["Subject"]


def test_handler_initialize_clients_failure_triggers_error_notification(mock_env_vars):
    """Test that initialize_clients failure triggers error notification callback."""
    # Mock the underlying get_clients (called by initialize_clients) to fail
    # This lets initialize_clients execute its error handling path
    error_response = {"Error": {"Code": "AccessDenied", "Message": "Unable to assume role"}}

    with (
        patch("shared.handler_utils.get_clients") as mock_get_clients,
        patch("boto3.client") as mock_boto3_client,
        patch("handler.send_error_notification") as mock_send_error,
    ):
        # Make get_clients raise error - initialize_clients will catch it
        mock_get_clients.side_effect = ClientError(error_response, "AssumeRole")

        # Mock boto3.client to return a mock SNS client
        mock_sns = Mock()
        mock_boto3_client.return_value = mock_sns

        # Execute handler - should raise error
        with pytest.raises(ClientError) as exc_info:
            handler.handler({}, {})

        # Verify error was raised
        assert exc_info.value.response["Error"]["Code"] == "AccessDenied"

        # Verify boto3.client was called to create SNS client
        mock_boto3_client.assert_called_with("sns")

        # Verify send_error_notification was called with correct args
        assert mock_send_error.called
        call_kwargs = mock_send_error.call_args[1]
        assert call_kwargs["sns_client"] == mock_sns
        assert call_kwargs["lambda_name"] == "Reporter"
        assert "AccessDenied" in call_kwargs["error_message"]


def test_handler_with_debug_data_enabled(monkeypatch, mock_clients, aws_mock_builder):
    """Test handler with include_debug_data enabled."""
    monkeypatch.setenv("INCLUDE_DEBUG_DATA", "true")
    monkeypatch.setenv("EMAIL_REPORTS", "false")

    # Mock SpendingAnalyzer - Cost Explorer coverage data
    mock_clients["ce"].get_savings_plans_coverage.return_value = aws_mock_builder.coverage(
        coverage_percentage=80.0
    )

    # Mock Savings Plans data
    mock_clients[
        "savingsplans"
    ].describe_savings_plans.return_value = aws_mock_builder.describe_savings_plans(plans_count=1)

    # Mock utilization and savings
    mock_clients["ce"].get_savings_plans_utilization.return_value = aws_mock_builder.utilization(
        utilization_percentage=90.0
    )

    # Mock S3 upload
    mock_clients["s3"].put_object.return_value = {}

    # Mock aws_debug module
    with (
        patch("shared.aws_debug.clear_responses") as mock_clear,
        patch("shared.aws_debug.get_responses") as mock_get_responses,
    ):
        mock_get_responses.return_value = [{"api": "test", "response": "data"}]

        result = handler.handler({}, None)

        # Verify debug functions were called
        assert mock_clear.called
        assert mock_get_responses.called

        # Verify successful execution
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert "message" in body


def test_handler_local_mode_auto_open(monkeypatch, mock_clients, aws_mock_builder):
    """Test handler in local mode with HTML auto-open."""
    monkeypatch.setenv("LOCAL_MODE", "true")
    monkeypatch.setenv("REPORT_FORMAT", "html")
    monkeypatch.setenv("EMAIL_REPORTS", "false")

    # Mock SpendingAnalyzer
    mock_clients["ce"].get_savings_plans_coverage.return_value = aws_mock_builder.coverage(
        coverage_percentage=70.0
    )

    # Mock Savings Plans data
    mock_clients[
        "savingsplans"
    ].describe_savings_plans.return_value = aws_mock_builder.describe_savings_plans(plans_count=1)

    # Mock utilization
    mock_clients["ce"].get_savings_plans_utilization.return_value = aws_mock_builder.utilization(
        utilization_percentage=85.0
    )

    # Mock scheduler_preview recommendations
    mock_clients[
        "ce"
    ].get_savings_plans_purchase_recommendation.return_value = aws_mock_builder.recommendation(
        sp_type="compute", hourly_commitment=5.0
    )

    # Mock S3 upload to return a local file path
    def mock_upload_report(*args, **kwargs):
        return "/tmp/test-report.html"

    # Mock webbrowser.open
    with (
        patch("handler.webbrowser.open") as mock_browser,
        patch("handler.Path.exists", return_value=True),
        patch.object(handler.StorageAdapter, "upload_report", side_effect=mock_upload_report),
    ):
        result = handler.handler({}, None)

        # Verify browser was opened in local mode
        assert mock_browser.called

        # Verify successful execution
        assert result["statusCode"] == 200


def test_handler_with_scheduler_preview_fixed_strategy(monkeypatch, mock_clients, aws_mock_builder):
    """Test scheduler preview with fixed strategy integration."""
    # Set scheduler strategy environment variables
    monkeypatch.setenv("PURCHASE_STRATEGY_TYPE", "fixed")
    monkeypatch.setenv("MAX_PURCHASE_PERCENT", "10")
    monkeypatch.setenv("MIN_PURCHASE_PERCENT", "1")
    monkeypatch.setenv("COMPUTE_SP_TERM", "THREE_YEAR")
    monkeypatch.setenv("COMPUTE_SP_PAYMENT_OPTION", "ALL_UPFRONT")
    monkeypatch.setenv("REPORT_FORMAT", "html")
    monkeypatch.setenv("EMAIL_REPORTS", "false")

    # Mock SpendingAnalyzer - coverage at 70% (room for improvement)
    mock_clients["ce"].get_savings_plans_coverage.return_value = aws_mock_builder.coverage(
        coverage_percentage=70.0
    )

    # Mock Savings Plans data - 2 active plans
    mock_clients[
        "savingsplans"
    ].describe_savings_plans.return_value = aws_mock_builder.describe_savings_plans(plans_count=2)

    # Mock utilization
    mock_clients["ce"].get_savings_plans_utilization.return_value = aws_mock_builder.utilization(
        utilization_percentage=85.0
    )

    # Mock AWS recommendations (needed for follow_aws strategy in preview)
    mock_clients[
        "ce"
    ].get_savings_plans_purchase_recommendation.return_value = aws_mock_builder.recommendation(
        sp_type="compute", hourly_commitment=50.0
    )

    # Mock S3 upload
    report_content_captured = {}

    def capture_report_content(*args, **kwargs):
        report_content_captured["content"] = kwargs.get("Body", "")

    mock_clients["s3"].put_object.side_effect = capture_report_content

    # Execute handler
    result = handler.handler({}, None)

    # Verify success
    assert result["statusCode"] == 200

    # Verify report was generated
    assert "content" in report_content_captured
    report_html = report_content_captured["content"]

    # Decode bytes to string if needed
    if isinstance(report_html, bytes):
        report_html = report_html.decode("utf-8")

    # Verify scheduler preview is embedded within usage tabs
    assert "Usage Over Time and Scheduler Preview" in report_html, "Section title should be updated"
    assert "Scheduler Preview - Strategy Comparison" in report_html, (
        "Preview comparison should be in HTML"
    )

    # Verify all three strategies are shown in the comparison
    assert "Fixed" in report_html, "Preview should show Fixed strategy"
    assert "Dichotomy" in report_html, "Preview should show Dichotomy strategy"
    assert "Follow AWS" in report_html, "Preview should show Follow AWS strategy"

    # Verify configured strategy is highlighted
    assert "CONFIGURED" in report_html, "Preview should mark configured strategy"

    # Verify S3 upload was called
    assert mock_clients["s3"].put_object.called


def test_handler_with_scheduler_preview_dichotomy_strategy(
    monkeypatch, mock_clients, aws_mock_builder
):
    """Test scheduler preview with dichotomy strategy integration."""
    # Set scheduler strategy environment variables for dichotomy
    monkeypatch.setenv("PURCHASE_STRATEGY_TYPE", "dichotomy")
    monkeypatch.setenv("DICHOTOMY_INITIAL_PERCENT", "50")
    monkeypatch.setenv("COMPUTE_SP_TERM", "THREE_YEAR")
    monkeypatch.setenv("COMPUTE_SP_PAYMENT_OPTION", "NO_UPFRONT")
    monkeypatch.setenv("REPORT_FORMAT", "html")
    monkeypatch.setenv("EMAIL_REPORTS", "false")

    # Mock SpendingAnalyzer - coverage at 60% (larger gap for dichotomy)
    mock_clients["ce"].get_savings_plans_coverage.return_value = aws_mock_builder.coverage(
        coverage_percentage=60.0
    )

    # Mock Savings Plans data
    mock_clients[
        "savingsplans"
    ].describe_savings_plans.return_value = aws_mock_builder.describe_savings_plans(plans_count=1)

    # Mock utilization
    mock_clients["ce"].get_savings_plans_utilization.return_value = aws_mock_builder.utilization(
        utilization_percentage=85.0
    )

    # Mock AWS recommendations (needed for follow_aws strategy in preview)
    mock_clients[
        "ce"
    ].get_savings_plans_purchase_recommendation.return_value = aws_mock_builder.recommendation(
        sp_type="compute", hourly_commitment=50.0
    )

    # Mock S3 upload
    report_content_captured = {}

    def capture_report_content(*args, **kwargs):
        report_content_captured["content"] = kwargs.get("Body", "")

    mock_clients["s3"].put_object.side_effect = capture_report_content

    # Execute handler
    result = handler.handler({}, None)

    # Verify success
    assert result["statusCode"] == 200

    # Verify report was generated
    assert "content" in report_content_captured
    report_html = report_content_captured["content"]

    # Decode bytes to string if needed
    if isinstance(report_html, bytes):
        report_html = report_html.decode("utf-8")

    # Verify scheduler preview is embedded within usage tabs
    assert "Usage Over Time and Scheduler Preview" in report_html
    assert "Scheduler Preview - Strategy Comparison" in report_html

    # Verify all three strategies are shown in the comparison
    assert "Fixed" in report_html
    assert "Dichotomy" in report_html
    assert "Follow AWS" in report_html

    # Verify configured strategy (dichotomy) is highlighted
    assert "CONFIGURED" in report_html


def test_handler_with_scheduler_preview_follow_aws_strategy(
    monkeypatch, mock_clients, aws_mock_builder
):
    """Test scheduler preview with follow_aws strategy integration."""
    # Set scheduler strategy environment variables for follow_aws
    monkeypatch.setenv("PURCHASE_STRATEGY_TYPE", "follow_aws")
    monkeypatch.setenv("COMPUTE_SP_TERM", "THREE_YEAR")
    monkeypatch.setenv("COMPUTE_SP_PAYMENT_OPTION", "ALL_UPFRONT")
    monkeypatch.setenv("REPORT_FORMAT", "html")
    monkeypatch.setenv("EMAIL_REPORTS", "false")

    # Mock SpendingAnalyzer
    mock_clients["ce"].get_savings_plans_coverage.return_value = aws_mock_builder.coverage(
        coverage_percentage=65.0
    )

    # Mock Savings Plans data
    mock_clients[
        "savingsplans"
    ].describe_savings_plans.return_value = aws_mock_builder.describe_savings_plans(plans_count=1)

    # Mock utilization
    mock_clients["ce"].get_savings_plans_utilization.return_value = aws_mock_builder.utilization(
        utilization_percentage=85.0
    )

    # Mock AWS recommendations (required for follow_aws strategy)
    mock_clients[
        "ce"
    ].get_savings_plans_purchase_recommendation.return_value = aws_mock_builder.recommendation(
        sp_type="compute"
    )

    # Mock S3 upload
    report_content_captured = {}

    def capture_report_content(*args, **kwargs):
        report_content_captured["content"] = kwargs.get("Body", "")

    mock_clients["s3"].put_object.side_effect = capture_report_content

    # Execute handler
    result = handler.handler({}, None)

    # Verify success
    assert result["statusCode"] == 200

    # Verify report was generated
    assert "content" in report_content_captured
    report_html = report_content_captured["content"]

    # Decode bytes to string if needed
    if isinstance(report_html, bytes):
        report_html = report_html.decode("utf-8")

    # Verify scheduler preview is embedded within usage tabs
    assert "Usage Over Time and Scheduler Preview" in report_html
    assert "Scheduler Preview - Strategy Comparison" in report_html

    # Verify all three strategies are shown in the comparison
    assert "Fixed" in report_html
    assert "Dichotomy" in report_html
    assert "Follow AWS" in report_html

    # Verify configured strategy (follow_aws) is highlighted
    assert "CONFIGURED" in report_html

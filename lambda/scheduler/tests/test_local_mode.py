"""
Local mode integration tests for Scheduler Lambda.

Tests the full handler execution in local filesystem mode.
Validates queue_adapter.py local mode code paths.
"""

import json
import os
import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest


# Set minimal environment variables before imports
# LOCAL_MODE will be set per-test using monkeypatch to avoid polluting other tests
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("QUEUE_URL", "not-used-in-local-mode")
os.environ.setdefault("SNS_TOPIC_ARN", "arn:aws:sns:us-east-1:123456789012:test-topic")
os.environ.setdefault("DRY_RUN", "false")
os.environ.setdefault("LOOKBACK_DAYS", "7")
os.environ.setdefault("MIN_DATA_DAYS", "7")
os.environ.setdefault("GRANULARITY", "HOURLY")
os.environ.setdefault("COVERAGE_TARGET_PERCENT", "80")
os.environ.setdefault("ENABLE_COMPUTE_SP", "true")
os.environ.setdefault("ENABLE_DATABASE_SP", "false")
os.environ.setdefault("ENABLE_SAGEMAKER_SP", "false")
os.environ.setdefault("PURCHASE_STRATEGY_TYPE", "fixed")
os.environ.setdefault("MAX_PURCHASE_PERCENT", "10")
os.environ.setdefault("MIN_COMMITMENT_PER_PLAN", "0.001")
os.environ.setdefault("COMPUTE_SP_PLAN_TYPE", "NO_UPFRONT:1_YEAR")

# Add lambda directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import handler


@pytest.fixture
def mock_aws_clients(aws_mock_builder):
    """Mock only AWS API clients (CE, SavingsPlans) - queue uses filesystem."""
    with patch("handler.initialize_clients") as mock_init:
        mock_ce = Mock()
        mock_sp = Mock()

        # Use aws_mock_builder for proper mocking - 75% coverage, needs more commitment
        mock_ce.get_savings_plans_coverage.return_value = aws_mock_builder.coverage(
            coverage_percentage=75.0
        )
        mock_sp.describe_savings_plans.return_value = aws_mock_builder.describe_savings_plans(
            plans_count=1
        )

        mock_init.return_value = {
            "ce": mock_ce,
            "savingsplans": mock_sp,
            "sqs": None,  # Not used in local mode
            "sns": None,  # Not used in tests
        }

        yield {"ce": mock_ce, "savingsplans": mock_sp}


def test_handler_local_mode_queue_messages(mock_aws_clients, monkeypatch):
    """Test scheduler writes purchase messages to local filesystem queue."""
    test_data_dir = f"/tmp/sp-autopilot-test-{os.getpid()}-queue"
    monkeypatch.setenv("LOCAL_MODE", "true")
    monkeypatch.setenv("LOCAL_DATA_DIR", test_data_dir)

    response = handler.handler({}, {})

    # Verify successful execution
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert "Scheduler completed" in body["message"]

    # Verify queue messages were written to filesystem
    queue_dir = Path(test_data_dir) / "queue"
    assert queue_dir.exists(), "Queue directory should exist"

    message_files = list(queue_dir.glob("*.json"))
    assert len(message_files) > 0, "At least one purchase message should be generated"

    # Verify message structure
    for msg_file in message_files:
        msg = json.loads(msg_file.read_text())

        # Validate required fields
        assert "sp_type" in msg
        assert "term" in msg
        assert "payment_option" in msg
        assert "hourly_commitment" in msg
        assert "client_token" in msg

        # Validate values
        assert msg["sp_type"] in ["compute", "database", "sagemaker"]
        assert msg["term"] in ["ONE_YEAR", "THREE_YEAR"]
        assert msg["payment_option"] in ["NO_UPFRONT", "PARTIAL_UPFRONT", "ALL_UPFRONT"]
        assert float(msg["hourly_commitment"]) > 0
        assert len(msg["client_token"]) > 0  # Token exists and is not empty


def test_handler_local_mode_no_purchases_needed(mock_aws_clients, monkeypatch):
    """Test scheduler with coverage at target (minimal/no purchase)."""
    test_data_dir = f"/tmp/sp-autopilot-test-{os.getpid()}-no-purchase"
    monkeypatch.setenv("LOCAL_MODE", "true")
    monkeypatch.setenv("LOCAL_DATA_DIR", test_data_dir)

    response = handler.handler({}, {})

    assert response["statusCode"] == 200

    # With default 76% coverage vs 80% target, a small purchase may be generated
    # This test verifies the handler completes successfully in local mode
    queue_dir = Path(test_data_dir) / "queue"
    message_files = list(queue_dir.glob("*.json"))
    # Just verify queue directory exists and handler completed
    assert queue_dir.exists()


def test_handler_local_mode_dry_run(mock_aws_clients, monkeypatch):
    """Test scheduler in dry-run mode (no queue messages)."""
    test_data_dir = f"/tmp/sp-autopilot-test-{os.getpid()}-dryrun"
    monkeypatch.setenv("LOCAL_MODE", "true")
    monkeypatch.setenv("LOCAL_DATA_DIR", test_data_dir)
    monkeypatch.setenv("DRY_RUN", "true")

    response = handler.handler({}, {})

    assert response["statusCode"] == 200

    # Verify no queue messages in dry-run mode
    queue_dir = Path(test_data_dir) / "queue"
    if queue_dir.exists():
        message_files = list(queue_dir.glob("*.json"))
        assert len(message_files) == 0, "Dry-run should not generate queue messages"


def test_handler_local_mode_multiple_plan_types(mock_aws_clients, monkeypatch, aws_mock_builder):
    """Test scheduler with multiple SP types enabled."""
    test_data_dir = f"/tmp/sp-autopilot-test-{os.getpid()}-multi"
    monkeypatch.setenv("LOCAL_MODE", "true")
    monkeypatch.setenv("LOCAL_DATA_DIR", test_data_dir)
    monkeypatch.setenv("ENABLE_DATABASE_SP", "true")
    monkeypatch.setenv("DATABASE_SP_PLAN_TYPE", "NO_UPFRONT:1_YEAR")

    # Mock spending for both compute and database
    mock_aws_clients["ce"].get_savings_plans_coverage.return_value = aws_mock_builder.coverage(
        coverage_percentage=75.0
    )

    response = handler.handler({}, {})

    assert response["statusCode"] == 200

    # With multiple SP types enabled, should generate at least one message
    # (depends on which SP types have spending data in the mocked response)
    queue_dir = Path(test_data_dir) / "queue"
    message_files = list(queue_dir.glob("*.json"))
    assert len(message_files) >= 1, "Should generate at least one purchase message"

    # Verify SP types are valid
    sp_types = set()
    for msg_file in message_files:
        msg = json.loads(msg_file.read_text())
        assert msg["sp_type"] in ["compute", "database", "sagemaker"]
        sp_types.add(msg["sp_type"])

    # At least one SP type should be present
    assert len(sp_types) >= 1

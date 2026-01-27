"""
Local mode integration tests for Reporter Lambda.

Tests the full handler execution in local filesystem mode.
Validates storage_adapter.py local mode code paths.
"""

import json
import os
import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest


# Set environment variables before any imports
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["LOCAL_MODE"] = "true"
os.environ["REPORTS_BUCKET"] = "not-used-in-local-mode"
os.environ["SNS_TOPIC_ARN"] = "arn:aws:sns:us-east-1:123456789012:test-topic"
os.environ["REPORT_FORMAT"] = "html"
os.environ["EMAIL_REPORTS"] = "false"  # Skip SNS in local mode
os.environ["LOOKBACK_DAYS"] = "7"
os.environ["GRANULARITY"] = "HOURLY"
os.environ["COVERAGE_TARGET_PERCENT"] = "90"
os.environ["ENABLE_COMPUTE_SP"] = "true"
os.environ["ENABLE_DATABASE_SP"] = "false"
os.environ["ENABLE_SAGEMAKER_SP"] = "false"
os.environ["LOW_UTILIZATION_THRESHOLD"] = "70"
os.environ["LOW_UTILIZATION_ALERT_ENABLED"] = "false"
os.environ["INCLUDE_DEBUG_DATA"] = "true"
os.environ["AUTO_OPEN_REPORTS"] = "false"  # Disable browser auto-open during tests

# Add lambda directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import handler


@pytest.fixture
def mock_aws_clients(aws_mock_builder):
    """Mock only AWS API clients (CE, SavingsPlans) - storage uses filesystem."""
    with patch("handler.initialize_clients") as mock_init:
        mock_ce = Mock()
        mock_sp = Mock()

        # Use aws_mock_builder for proper mocking
        mock_ce.get_savings_plans_coverage.return_value = aws_mock_builder.coverage(
            coverage_percentage=75.0
        )
        mock_sp.describe_savings_plans.return_value = aws_mock_builder.describe_savings_plans(
            plans_count=1
        )
        mock_ce.get_savings_plans_utilization.return_value = aws_mock_builder.utilization(
            utilization_percentage=85.5
        )

        # Mock recommendations for scheduler_preview
        mock_ce.get_savings_plans_purchase_recommendation.return_value = (
            aws_mock_builder.recommendation(sp_type="compute", hourly_commitment=5.0)
        )

        mock_init.return_value = {
            "ce": mock_ce,
            "savingsplans": mock_sp,
            "s3": None,  # Not used in local mode
            "sns": None,  # Not used when EMAIL_REPORTS=false
        }

        yield {"ce": mock_ce, "savingsplans": mock_sp}


def test_handler_local_mode_html_report(mock_aws_clients, monkeypatch):
    """Test reporter generates HTML report to local filesystem."""
    # Set unique local data directory for this test
    test_data_dir = f"/tmp/sp-autopilot-test-{os.getpid()}-html"
    monkeypatch.setenv("LOCAL_DATA_DIR", test_data_dir)

    response = handler.handler({}, {})

    # Verify successful execution
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["message"] == "Reporter completed successfully"

    # Verify HTML report was written to filesystem
    reports_dir = Path(test_data_dir) / "reports"
    assert reports_dir.exists(), "Reports directory should exist"

    report_files = list(reports_dir.glob("savings-plans-report_*.html"))
    assert len(report_files) == 1, "Exactly one HTML report should be generated"

    # Verify report content
    content = report_files[0].read_text()
    assert "Savings Plans" in content
    assert "Coverage" in content or "Report" in content

    # Verify metadata file
    metadata_files = list(reports_dir.glob("*.html.meta.json"))
    assert len(metadata_files) == 1, "Metadata file should exist"

    metadata = json.loads(metadata_files[0].read_text())
    assert metadata["generator"] == "sp-autopilot-reporter"
    assert metadata["format"] == "html"


def test_handler_local_mode_json_report(mock_aws_clients, monkeypatch):
    """Test reporter generates JSON report to local filesystem."""
    test_data_dir = f"/tmp/sp-autopilot-test-{os.getpid()}-json"
    monkeypatch.setenv("LOCAL_DATA_DIR", test_data_dir)
    monkeypatch.setenv("REPORT_FORMAT", "json")

    response = handler.handler({}, {})

    assert response["statusCode"] == 200

    # Verify JSON report (exclude .meta.json files)
    reports_dir = Path(test_data_dir) / "reports"
    report_files = [
        f for f in reports_dir.glob("savings-plans-report_*.json") if ".meta.json" not in f.name
    ]
    assert len(report_files) == 1

    # Parse and verify JSON structure
    report_data = json.loads(report_files[0].read_text())
    assert "report_metadata" in report_data
    assert "coverage_summary" in report_data
    assert "coverage_history" in report_data
    assert report_data["report_metadata"]["generator"] == "sp-autopilot-reporter"


def test_handler_local_mode_with_debug_data(mock_aws_clients, monkeypatch):
    """Test reporter includes debug data in local mode."""
    test_data_dir = f"/tmp/sp-autopilot-test-{os.getpid()}-debug"
    monkeypatch.setenv("LOCAL_DATA_DIR", test_data_dir)
    monkeypatch.setenv("INCLUDE_DEBUG_DATA", "true")

    response = handler.handler({}, {})

    assert response["statusCode"] == 200

    # Verify HTML report contains debug section
    reports_dir = Path(test_data_dir) / "reports"
    report_files = list(reports_dir.glob("*.html"))
    content = report_files[0].read_text()

    # Debug section should be present (Raw AWS Data section)
    assert "Raw" in content or "Debug" in content

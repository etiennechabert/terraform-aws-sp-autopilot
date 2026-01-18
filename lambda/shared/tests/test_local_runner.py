"""
Integration tests for the local_runner.py script.

These tests verify that the local runner can execute Lambda functions
in local mode with filesystem I/O.
"""

import json
import os
import tempfile
from pathlib import Path
from unittest import mock

import pytest


class TestLocalRunner:
    """Integration tests for local_runner.py."""

    @pytest.fixture
    def temp_data_dir(self):
        """Create a temporary data directory for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def mock_env(self, temp_data_dir):
        """Set up environment variables for local mode."""
        env = {
            "LOCAL_MODE": "true",
            "LOCAL_DATA_DIR": str(temp_data_dir),
            "QUEUE_URL": "local://queue",
            "SNS_TOPIC_ARN": "arn:aws:sns:us-east-1:123456789012:test",
            "REPORTS_BUCKET": "local://reports",
            "DRY_RUN": "true",
            "ENABLE_COMPUTE_SP": "true",
            "COVERAGE_TARGET_PERCENT": "90",
            "REPORT_FORMAT": "html"
        }
        with mock.patch.dict(os.environ, env):
            yield env

    def test_local_data_dir_structure(self, temp_data_dir, mock_env):
        """Test that local data directories are created correctly."""
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from local_mode import get_queue_dir, get_reports_dir

        queue_dir = get_queue_dir()
        reports_dir = get_reports_dir()

        assert queue_dir.exists()
        assert reports_dir.exists()
        assert queue_dir.parent == temp_data_dir
        assert reports_dir.parent == temp_data_dir

    def test_queue_message_flow(self, temp_data_dir, mock_env):
        """Test complete flow: send message, receive message, delete message."""
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from queue_adapter import QueueAdapter

        adapter = QueueAdapter()

        # Send a message
        message = {
            "client_token": "test-flow-123",
            "sp_type": "ComputeSavingsPlans",
            "hourly_commitment": 1.5
        }
        adapter.send_message(message)

        # Receive the message
        messages = adapter.receive_messages(max_messages=1)
        assert len(messages) == 1

        received_body = json.loads(messages[0]["Body"])
        assert received_body["client_token"] == "test-flow-123"

        # Delete the message
        adapter.delete_message(messages[0]["ReceiptHandle"])

        # Verify deletion
        messages_after = adapter.receive_messages(max_messages=10)
        assert len(messages_after) == 0

    def test_report_upload_flow(self, temp_data_dir, mock_env):
        """Test complete flow: upload report, verify file exists."""
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from storage_adapter import StorageAdapter

        adapter = StorageAdapter()

        # Upload a report
        report_content = "<html><body>Test Report</body></html>"
        file_path = adapter.upload_report(report_content, report_format="html")

        # Verify file exists
        assert Path(file_path).exists()

        # Verify content
        with open(file_path, "r", encoding="utf-8") as f:
            saved_content = f.read()
        assert saved_content == report_content

        # Verify metadata file
        metadata_file = Path(file_path).with_suffix(".html.meta.json")
        assert metadata_file.exists()

        with open(metadata_file, "r") as f:
            metadata = json.load(f)
        assert metadata["generator"] == "sp-autopilot-reporter"

    def test_mock_context_creation(self):
        """Test MockContext class from local_runner."""
        import sys
        local_runner_path = Path(__file__).parent.parent / "local_runner.py"

        # Import local_runner module
        import importlib.util
        spec = importlib.util.spec_from_file_location("local_runner", local_runner_path)
        local_runner = importlib.util.module_from_spec(spec)

        # Mock environment to prevent actual loading
        with mock.patch.dict(os.environ, {"LOCAL_MODE": "true"}):
            with mock.patch("sys.path"):
                spec.loader.exec_module(local_runner)

        # Test MockContext
        context = local_runner.MockContext("test-function")
        assert context.function_name == "local-test-function"
        assert context.memory_limit_in_mb == 512
        assert "local" in context.invoked_function_arn
        assert "local" in context.aws_request_id


class TestQueuePersistence:
    """Test that queue messages persist across adapter instances."""

    @pytest.fixture
    def temp_data_dir(self):
        """Create a temporary data directory for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_message_persistence(self, temp_data_dir):
        """Test that messages persist between adapter instances."""
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from queue_adapter import QueueAdapter

        with mock.patch.dict(os.environ, {
            "LOCAL_MODE": "true",
            "LOCAL_DATA_DIR": str(temp_data_dir)
        }):
            # Create first adapter and send message
            adapter1 = QueueAdapter()
            message = {"client_token": "persist-test", "data": "test"}
            adapter1.send_message(message)

            # Create second adapter and receive message
            adapter2 = QueueAdapter()
            messages = adapter2.receive_messages(max_messages=1)

            assert len(messages) == 1
            received_body = json.loads(messages[0]["Body"])
            assert received_body["client_token"] == "persist-test"


class TestReportGeneration:
    """Test report generation and storage."""

    @pytest.fixture
    def temp_data_dir(self):
        """Create a temporary data directory for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_multiple_reports(self, temp_data_dir):
        """Test uploading multiple reports and listing them."""
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from storage_adapter import StorageAdapter
        import time

        with mock.patch.dict(os.environ, {
            "LOCAL_MODE": "true",
            "LOCAL_DATA_DIR": str(temp_data_dir)
        }):
            adapter = StorageAdapter()

            # Upload multiple reports with slight delays
            for i in range(3):
                report_content = f"<html><body>Report {i}</body></html>"
                adapter.upload_report(report_content, report_format="html")
                time.sleep(0.01)  # Small delay to ensure different timestamps

            # List reports
            reports = adapter.list_reports(max_items=10)
            assert len(reports) == 3

            # Verify they're sorted by modification time (newest first)
            report_files = [Path(r) for r in reports]
            mtimes = [f.stat().st_mtime for f in report_files]
            assert mtimes == sorted(mtimes, reverse=True)

    def test_report_formats(self, temp_data_dir):
        """Test uploading reports in different formats."""
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from storage_adapter import StorageAdapter

        with mock.patch.dict(os.environ, {
            "LOCAL_MODE": "true",
            "LOCAL_DATA_DIR": str(temp_data_dir)
        }):
            adapter = StorageAdapter()

            # Upload HTML report
            html_path = adapter.upload_report("<html>HTML</html>", report_format="html")
            assert Path(html_path).suffix == ".html"

            # Upload JSON report
            json_path = adapter.upload_report('{"test": "json"}', report_format="json")
            assert Path(json_path).suffix == ".json"

            # List reports (should include both)
            reports = adapter.list_reports(max_items=10)
            assert len(reports) == 2

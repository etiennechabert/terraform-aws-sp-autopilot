"""
Unit tests for local mode functionality.

Tests the abstraction layers for SQS (queue_adapter) and S3 (storage_adapter)
in both local and AWS modes.
"""

import json
import os

# Import from parent directory (lambda/shared)
import sys
import tempfile
from pathlib import Path
from unittest import mock

import pytest


sys.path.insert(0, str(Path(__file__).parent.parent))

from local_mode import get_local_data_dir, get_queue_dir, get_reports_dir, is_local_mode
from queue_adapter import QueueAdapter
from storage_adapter import StorageAdapter


class TestLocalModeUtils:
    """Test local mode utility functions."""

    def test_is_local_mode_true(self):
        """Test is_local_mode returns True when LOCAL_MODE=true."""
        with mock.patch.dict(os.environ, {"LOCAL_MODE": "true"}):
            assert is_local_mode() is True

    def test_is_local_mode_false(self):
        """Test is_local_mode returns False when LOCAL_MODE=false."""
        with mock.patch.dict(os.environ, {"LOCAL_MODE": "false"}):
            assert is_local_mode() is False

    def test_is_local_mode_default(self):
        """Test is_local_mode returns False by default."""
        with mock.patch.dict(os.environ, {}, clear=True):
            os.environ.pop("LOCAL_MODE", None)
            assert is_local_mode() is False

    def test_get_local_data_dir_default(self):
        """Test get_local_data_dir returns default directory."""
        with mock.patch.dict(os.environ, {}, clear=True):
            os.environ.pop("LOCAL_DATA_DIR", None)
            with tempfile.TemporaryDirectory() as tmpdir:
                with mock.patch.dict(os.environ, {"LOCAL_DATA_DIR": tmpdir}):
                    data_dir = get_local_data_dir()
                    assert data_dir.exists()
                    assert str(data_dir) == tmpdir

    def test_get_queue_dir(self):
        """Test get_queue_dir creates queue directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with mock.patch.dict(os.environ, {"LOCAL_DATA_DIR": tmpdir}):
                queue_dir = get_queue_dir()
                assert queue_dir.exists()
                assert queue_dir.name == "queue"

    def test_get_reports_dir(self):
        """Test get_reports_dir creates reports directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with mock.patch.dict(os.environ, {"LOCAL_DATA_DIR": tmpdir}):
                reports_dir = get_reports_dir()
                assert reports_dir.exists()
                assert reports_dir.name == "reports"


class TestQueueAdapterLocal:
    """Test QueueAdapter in local mode."""

    @pytest.fixture
    def local_queue_dir(self):
        """Create a temporary directory for local queue operations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with mock.patch.dict(
                os.environ, {"LOCAL_MODE": "true", "LOCAL_DATA_DIR": tmpdir}
            ):
                yield Path(tmpdir) / "queue"

    def test_queue_adapter_local_init(self, local_queue_dir):
        """Test QueueAdapter initializes in local mode."""
        adapter = QueueAdapter()
        assert adapter.is_local is True
        assert adapter.queue_dir.exists()

    def test_send_message_local(self, local_queue_dir):
        """Test sending a message in local mode."""
        adapter = QueueAdapter()
        message = {"client_token": "test-123", "sp_type": "ComputeSavingsPlans"}

        message_id = adapter.send_message(message)
        assert message_id is not None

        # Verify file was created
        queue_files = list(adapter.queue_dir.glob("*.json"))
        assert len(queue_files) == 1
        assert queue_files[0].stem == "test-123"

        # Verify content
        with open(queue_files[0]) as f:
            saved_message = json.load(f)
        assert saved_message == message

    def test_receive_messages_local(self, local_queue_dir):
        """Test receiving messages in local mode."""
        adapter = QueueAdapter()

        # Send some messages
        message1 = {"client_token": "msg-1", "data": "first"}
        message2 = {"client_token": "msg-2", "data": "second"}
        adapter.send_message(message1)
        adapter.send_message(message2)

        # Receive messages
        messages = adapter.receive_messages(max_messages=10)
        assert len(messages) == 2

        # Verify message structure
        assert "MessageId" in messages[0]
        assert "Body" in messages[0]
        assert "ReceiptHandle" in messages[0]

        # Verify message content
        body1 = json.loads(messages[0]["Body"])
        assert body1["client_token"] in ["msg-1", "msg-2"]

    def test_delete_message_local(self, local_queue_dir):
        """Test deleting a message in local mode."""
        adapter = QueueAdapter()

        # Send a message
        message = {"client_token": "delete-me", "data": "test"}
        adapter.send_message(message)

        # Receive it
        messages = adapter.receive_messages(max_messages=1)
        assert len(messages) == 1

        # Delete it
        receipt_handle = messages[0]["ReceiptHandle"]
        adapter.delete_message(receipt_handle)

        # Verify it's gone
        messages_after = adapter.receive_messages(max_messages=10)
        assert len(messages_after) == 0

    def test_purge_queue_local(self, local_queue_dir):
        """Test purging queue in local mode."""
        adapter = QueueAdapter()

        # Send multiple messages
        for i in range(5):
            adapter.send_message({"client_token": f"msg-{i}", "data": i})

        # Verify messages exist
        messages = adapter.receive_messages(max_messages=10)
        assert len(messages) == 5

        # Purge queue
        adapter.purge_queue()

        # Verify all messages are gone
        messages_after = adapter.receive_messages(max_messages=10)
        assert len(messages_after) == 0


class TestQueueAdapterAWS:
    """Test QueueAdapter in AWS mode."""

    @pytest.fixture
    def mock_sqs_client(self):
        """Create a mock SQS client."""
        client = mock.MagicMock()
        client.send_message.return_value = {"MessageId": "aws-msg-123"}
        client.receive_message.return_value = {
            "Messages": [
                {
                    "MessageId": "aws-msg-123",
                    "Body": '{"test": "data"}',
                    "ReceiptHandle": "receipt-123",
                }
            ]
        }
        return client

    def test_queue_adapter_aws_init(self, mock_sqs_client):
        """Test QueueAdapter initializes in AWS mode."""
        with mock.patch.dict(os.environ, {"LOCAL_MODE": "false"}):
            adapter = QueueAdapter(
                sqs_client=mock_sqs_client, queue_url="https://sqs.example.com/queue"
            )
            assert adapter.is_local is False

    def test_send_message_aws(self, mock_sqs_client):
        """Test sending a message in AWS mode."""
        with mock.patch.dict(os.environ, {"LOCAL_MODE": "false"}):
            adapter = QueueAdapter(
                sqs_client=mock_sqs_client, queue_url="https://sqs.example.com/queue"
            )
            message = {"client_token": "test-123", "data": "test"}

            message_id = adapter.send_message(message)
            assert message_id == "aws-msg-123"

            # Verify SQS client was called
            mock_sqs_client.send_message.assert_called_once()

    def test_receive_messages_aws(self, mock_sqs_client):
        """Test receiving messages in AWS mode."""
        with mock.patch.dict(os.environ, {"LOCAL_MODE": "false"}):
            adapter = QueueAdapter(
                sqs_client=mock_sqs_client, queue_url="https://sqs.example.com/queue"
            )

            messages = adapter.receive_messages(max_messages=10)
            assert len(messages) == 1
            assert messages[0]["MessageId"] == "aws-msg-123"

            # Verify SQS client was called
            mock_sqs_client.receive_message.assert_called_once()


class TestStorageAdapterLocal:
    """Test StorageAdapter in local mode."""

    @pytest.fixture
    def local_reports_dir(self):
        """Create a temporary directory for local storage operations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with mock.patch.dict(
                os.environ, {"LOCAL_MODE": "true", "LOCAL_DATA_DIR": tmpdir}
            ):
                yield Path(tmpdir) / "reports"

    def test_storage_adapter_local_init(self, local_reports_dir):
        """Test StorageAdapter initializes in local mode."""
        adapter = StorageAdapter()
        assert adapter.is_local is True
        assert adapter.reports_dir.exists()

    def test_upload_report_local_html(self, local_reports_dir):
        """Test uploading an HTML report in local mode."""
        adapter = StorageAdapter()
        report_content = "<html><body>Test Report</body></html>"

        file_path = adapter.upload_report(report_content, report_format="html")
        assert file_path is not None

        # Verify file was created
        report_file = Path(file_path)
        assert report_file.exists()
        assert report_file.suffix == ".html"

        # Verify content
        with open(report_file, encoding="utf-8") as f:
            saved_content = f.read()
        assert saved_content == report_content

        # Verify metadata file
        metadata_file = report_file.with_suffix(".html.meta.json")
        assert metadata_file.exists()
        with open(metadata_file) as f:
            metadata = json.load(f)
        assert "generated-at" in metadata
        assert metadata["generator"] == "sp-autopilot-reporter"

    def test_upload_report_local_json(self, local_reports_dir):
        """Test uploading a JSON report in local mode."""
        adapter = StorageAdapter()
        report_content = '{"test": "data"}'

        file_path = adapter.upload_report(report_content, report_format="json")
        assert file_path is not None

        # Verify file was created
        report_file = Path(file_path)
        assert report_file.exists()
        assert report_file.suffix == ".json"

    def test_list_reports_local(self, local_reports_dir):
        """Test listing reports in local mode."""
        adapter = StorageAdapter()

        # Upload multiple reports
        for i in range(3):
            adapter.upload_report(f"<html>Report {i}</html>", report_format="html")

        # List reports
        reports = adapter.list_reports(max_items=10)
        assert len(reports) == 3


class TestStorageAdapterAWS:
    """Test StorageAdapter in AWS mode."""

    @pytest.fixture
    def mock_s3_client(self):
        """Create a mock S3 client."""
        client = mock.MagicMock()
        client.put_object.return_value = {"ETag": "test-etag"}
        client.list_objects_v2.return_value = {
            "Contents": [{"Key": "report1.html"}, {"Key": "report2.html"}]
        }
        return client

    def test_storage_adapter_aws_init(self, mock_s3_client):
        """Test StorageAdapter initializes in AWS mode."""
        with mock.patch.dict(os.environ, {"LOCAL_MODE": "false"}):
            adapter = StorageAdapter(
                s3_client=mock_s3_client, bucket_name="test-bucket"
            )
            assert adapter.is_local is False

    def test_upload_report_aws(self, mock_s3_client):
        """Test uploading a report in AWS mode."""
        with mock.patch.dict(os.environ, {"LOCAL_MODE": "false"}):
            adapter = StorageAdapter(
                s3_client=mock_s3_client, bucket_name="test-bucket"
            )
            report_content = "<html>Test Report</html>"

            object_key = adapter.upload_report(report_content, report_format="html")
            assert object_key is not None
            assert object_key.endswith(".html")

            # Verify S3 client was called
            mock_s3_client.put_object.assert_called_once()

    def test_list_reports_aws(self, mock_s3_client):
        """Test listing reports in AWS mode."""
        with mock.patch.dict(os.environ, {"LOCAL_MODE": "false"}):
            adapter = StorageAdapter(
                s3_client=mock_s3_client, bucket_name="test-bucket"
            )

            reports = adapter.list_reports(max_items=10)
            assert len(reports) == 2
            assert "report1.html" in reports

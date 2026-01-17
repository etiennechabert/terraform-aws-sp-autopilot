"""
Queue adapter that supports both AWS SQS and local filesystem operations.

This module provides an abstraction layer over queue operations, allowing
Lambdas to work with either real SQS queues or local filesystem-based queues.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from .local_mode import is_local_mode, get_queue_dir

logger = logging.getLogger(__name__)


class QueueAdapter:
    """
    Adapter class for queue operations supporting both SQS and local filesystem.
    """

    def __init__(self, sqs_client: Optional[Any] = None, queue_url: Optional[str] = None):
        """
        Initialize the queue adapter.

        Args:
            sqs_client: Boto3 SQS client (required for AWS mode, ignored in local mode)
            queue_url: SQS queue URL (required for AWS mode, ignored in local mode)
        """
        self.is_local = is_local_mode()
        self.sqs_client = sqs_client
        self.queue_url = queue_url

        if not self.is_local and (not sqs_client or not queue_url):
            raise ValueError("sqs_client and queue_url are required for AWS mode")

        if self.is_local:
            self.queue_dir = get_queue_dir()
            logger.info(f"Queue adapter initialized in LOCAL mode (directory: {self.queue_dir})")
        else:
            logger.info(f"Queue adapter initialized in AWS mode (queue: {queue_url})")

    def purge_queue(self) -> None:
        """
        Purge all messages from the queue.

        In AWS mode: Calls SQS PurgeQueue API.
        In local mode: Deletes all JSON files from the queue directory.
        """
        if self.is_local:
            self._purge_queue_local()
        else:
            self._purge_queue_aws()

    def _purge_queue_local(self) -> None:
        """Purge queue in local mode by deleting all message files."""
        deleted_count = 0
        for file_path in self.queue_dir.glob("*.json"):
            try:
                file_path.unlink()
                deleted_count += 1
                logger.debug(f"Deleted local queue message: {file_path.name}")
            except Exception as e:
                logger.error(f"Failed to delete queue file {file_path}: {e}")

        logger.info(f"Purged local queue: deleted {deleted_count} message(s)")

    def _purge_queue_aws(self) -> None:
        """Purge queue in AWS mode using SQS API."""
        try:
            self.sqs_client.purge_queue(QueueUrl=self.queue_url)
            logger.info(f"Initiated purge for SQS queue: {self.queue_url}")
        except Exception as e:
            logger.error(f"Failed to purge SQS queue: {e}")
            raise

    def send_message(self, message_body: Dict[str, Any]) -> str:
        """
        Send a message to the queue.

        Args:
            message_body: Dictionary containing the message payload.

        Returns:
            str: Message ID (AWS) or filename (local mode).

        Raises:
            Exception: If sending the message fails.
        """
        if self.is_local:
            return self._send_message_local(message_body)
        else:
            return self._send_message_aws(message_body)

    def _send_message_local(self, message_body: Dict[str, Any]) -> str:
        """Send message in local mode by writing to a JSON file."""
        # Generate a unique filename from client_token or timestamp
        client_token = message_body.get("client_token", f"msg-{datetime.now(timezone.utc).timestamp()}")
        # Sanitize filename
        safe_filename = client_token.replace("/", "-").replace(":", "-")
        file_path = self.queue_dir / f"{safe_filename}.json"

        try:
            with open(file_path, "w") as f:
                json.dump(message_body, f, indent=2, default=str)

            logger.info(f"Sent local queue message: {file_path.name}")
            return file_path.name
        except Exception as e:
            logger.error(f"Failed to write local queue message: {e}")
            raise

    def _send_message_aws(self, message_body: Dict[str, Any]) -> str:
        """Send message in AWS mode using SQS API."""
        try:
            response = self.sqs_client.send_message(
                QueueUrl=self.queue_url,
                MessageBody=json.dumps(message_body, default=str)
            )
            message_id = response["MessageId"]
            logger.info(f"Sent SQS message: {message_id}")
            return message_id
        except Exception as e:
            logger.error(f"Failed to send SQS message: {e}")
            raise

    def receive_messages(self, max_messages: int = 10, wait_time_seconds: int = 5) -> List[Dict[str, Any]]:
        """
        Receive messages from the queue.

        Args:
            max_messages: Maximum number of messages to receive.
            wait_time_seconds: Long polling wait time (AWS mode only).

        Returns:
            List of message dictionaries with keys: MessageId, Body, ReceiptHandle.
        """
        if self.is_local:
            return self._receive_messages_local(max_messages)
        else:
            return self._receive_messages_aws(max_messages, wait_time_seconds)

    def _receive_messages_local(self, max_messages: int) -> List[Dict[str, Any]]:
        """Receive messages in local mode by reading JSON files."""
        messages = []

        # Get all message files sorted by modification time (oldest first)
        message_files = sorted(
            self.queue_dir.glob("*.json"),
            key=lambda p: p.stat().st_mtime
        )

        for file_path in message_files[:max_messages]:
            try:
                with open(file_path, "r") as f:
                    message_body = json.load(f)

                messages.append({
                    "MessageId": file_path.stem,
                    "Body": json.dumps(message_body),
                    "ReceiptHandle": str(file_path)  # Use file path as receipt handle
                })
                logger.debug(f"Received local queue message: {file_path.name}")
            except Exception as e:
                logger.error(f"Failed to read queue file {file_path}: {e}")

        logger.info(f"Received {len(messages)} message(s) from local queue")
        return messages

    def _receive_messages_aws(self, max_messages: int, wait_time_seconds: int) -> List[Dict[str, Any]]:
        """Receive messages in AWS mode using SQS API."""
        try:
            response = self.sqs_client.receive_message(
                QueueUrl=self.queue_url,
                MaxNumberOfMessages=max_messages,
                WaitTimeSeconds=wait_time_seconds
            )

            messages = response.get("Messages", [])
            logger.info(f"Received {len(messages)} message(s) from SQS queue")
            return messages
        except Exception as e:
            logger.error(f"Failed to receive SQS messages: {e}")
            raise

    def delete_message(self, receipt_handle: str) -> None:
        """
        Delete a message from the queue.

        Args:
            receipt_handle: SQS receipt handle (AWS) or file path (local mode).
        """
        if self.is_local:
            self._delete_message_local(receipt_handle)
        else:
            self._delete_message_aws(receipt_handle)

    def _delete_message_local(self, receipt_handle: str) -> None:
        """Delete message in local mode by removing the file."""
        try:
            file_path = Path(receipt_handle)
            if file_path.exists():
                file_path.unlink()
                logger.info(f"Deleted local queue message: {file_path.name}")
            else:
                logger.warning(f"Message file not found: {receipt_handle}")
        except Exception as e:
            logger.error(f"Failed to delete local queue message: {e}")
            raise

    def _delete_message_aws(self, receipt_handle: str) -> None:
        """Delete message in AWS mode using SQS API."""
        try:
            self.sqs_client.delete_message(
                QueueUrl=self.queue_url,
                ReceiptHandle=receipt_handle
            )
            logger.info("Deleted SQS message")
        except Exception as e:
            logger.error(f"Failed to delete SQS message: {e}")
            raise

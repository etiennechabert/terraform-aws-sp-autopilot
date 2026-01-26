"""
Storage adapter that supports both AWS S3 and local filesystem operations.

This module provides an abstraction layer over storage operations, allowing
Lambdas to work with either real S3 buckets or local filesystem storage.
"""

import json
import logging
from datetime import UTC, datetime
from typing import Any

from . import local_mode


logger = logging.getLogger(__name__)


class StorageAdapter:
    """
    Adapter class for storage operations supporting both S3 and local filesystem.
    """

    def __init__(self, s3_client: Any | None = None, bucket_name: str | None = None):
        """
        Initialize the storage adapter.

        Args:
            s3_client: Boto3 S3 client (required for AWS mode, ignored in local mode)
            bucket_name: S3 bucket name (required for AWS mode, ignored in local mode)
        """
        self.is_local = local_mode.is_local_mode()
        self.s3_client = s3_client
        self.bucket_name = bucket_name

        if not self.is_local and (not s3_client or not bucket_name):
            raise ValueError("s3_client and bucket_name are required for AWS mode")

        if self.is_local:
            self.reports_dir = local_mode.get_reports_dir()
            logger.info(
                f"Storage adapter initialized in LOCAL mode (directory: {self.reports_dir})"
            )
        else:
            logger.info(f"Storage adapter initialized in AWS mode (bucket: {bucket_name})")

    def upload_report(
        self,
        report_content: str,
        report_format: str = "html",
        metadata: dict[str, str] | None = None,
    ) -> str:
        """
        Upload a report to storage.

        Args:
            report_content: The report content as a string.
            report_format: The format of the report (html, json, etc.).
            metadata: Optional metadata dictionary to attach to the object.

        Returns:
            str: Object key (AWS) or file path (local mode).

        Raises:
            Exception: If upload fails.
        """
        if self.is_local:
            return self._upload_report_local(report_content, report_format, metadata)
        return self._upload_report_aws(report_content, report_format, metadata)

    def _upload_report_local(
        self,
        report_content: str,
        report_format: str,
        metadata: dict[str, str] | None,
    ) -> str:
        """Upload report in local mode by writing to a file."""
        timestamp = datetime.now(UTC).strftime("%Y-%m-%d_%H-%M-%S")
        file_name = f"savings-plans-report_{timestamp}.{report_format}"
        file_path = self.reports_dir / file_name

        try:
            # Write the report content
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(report_content)

            # Write metadata to a separate file
            if metadata is None:
                metadata = {}

            metadata_with_defaults = {
                "generated-at": datetime.now(UTC).isoformat(),
                "generator": "sp-autopilot-reporter",
                "format": report_format,
                **metadata,
            }

            metadata_file = file_path.with_suffix(f".{report_format}.meta.json")
            with open(metadata_file, "w", encoding="utf-8") as f:
                json.dump(metadata_with_defaults, f, indent=2)

            logger.info(f"Uploaded local report: {file_path}")
            return str(file_path)
        except Exception as e:
            logger.error(f"Failed to write local report: {e}")
            raise

    def _upload_report_aws(
        self,
        report_content: str,
        report_format: str,
        metadata: dict[str, str] | None,
    ) -> str:
        """Upload report in AWS mode using S3 API."""
        timestamp = datetime.now(UTC).strftime("%Y-%m-%d_%H-%M-%S")
        object_key = f"savings-plans-report_{timestamp}.{report_format}"

        # Determine content type
        if report_format == "html":
            content_type = "text/html"
        elif report_format == "csv":
            content_type = "text/csv"
        else:
            content_type = "application/json"

        # Prepare metadata
        if metadata is None:
            metadata = {}

        metadata_with_defaults = {
            "generated-at": datetime.now(UTC).isoformat(),
            "generator": "sp-autopilot-reporter",
            **metadata,
        }

        try:
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=object_key,
                Body=report_content.encode("utf-8"),
                ContentType=content_type,
                ServerSideEncryption="AES256",
                Metadata=metadata_with_defaults,
            )

            logger.info(f"Uploaded report to S3: s3://{self.bucket_name}/{object_key}")
            return object_key
        except Exception as e:
            logger.error(f"Failed to upload report to S3: {e}")
            raise

    def get_report_url(self, object_key: str) -> str:
        """
        Get the URL or path to a report.

        Args:
            object_key: S3 object key (AWS) or file path (local mode).

        Returns:
            str: S3 URL (AWS) or local file path (local mode).
        """
        if self.is_local:
            return object_key  # Already a file path
        return f"s3://{self.bucket_name}/{object_key}"

    def generate_presigned_url(self, object_key: str, expiration: int = 604800) -> str:
        """
        Generate a pre-signed URL for accessing a report.

        Args:
            object_key: S3 object key
            expiration: URL expiration time in seconds (default: 7 days = 604800)

        Returns:
            str: Pre-signed URL for accessing the object

        Raises:
            ValueError: If called in local mode (pre-signed URLs only work with S3)
        """
        if self.is_local:
            raise ValueError("Pre-signed URLs are not supported in local mode")

        try:
            url = self.s3_client.generate_presigned_url(
                ClientMethod="get_object",
                Params={"Bucket": self.bucket_name, "Key": object_key},
                ExpiresIn=expiration,
            )
            logger.info(f"Generated pre-signed URL for {object_key} (expires in {expiration}s)")
            return url
        except Exception as e:
            logger.error(f"Failed to generate pre-signed URL: {e}")
            raise

    def list_reports(self, max_items: int = 100) -> list:
        """
        List available reports.

        Args:
            max_items: Maximum number of reports to return.

        Returns:
            List of report keys/paths.
        """
        if self.is_local:
            return self._list_reports_local(max_items)
        return self._list_reports_aws(max_items)

    def _list_reports_local(self, max_items: int) -> list:
        """List reports in local mode."""
        reports = []
        # Look for HTML, JSON, and CSV reports, exclude metadata files
        for pattern in ["*.html", "*.json", "*.csv"]:
            for file_path in sorted(
                self.reports_dir.glob(pattern),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            ):
                # Skip metadata files
                if ".meta.json" not in file_path.name:
                    reports.append(str(file_path))
                    if len(reports) >= max_items:
                        break
            if len(reports) >= max_items:
                break

        logger.info(f"Listed {len(reports)} local report(s)")
        return reports

    def _list_reports_aws(self, max_items: int) -> list:
        """List reports in AWS mode using S3 API."""
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix="savings-plans-report_",
                MaxKeys=max_items,
            )

            reports = [obj["Key"] for obj in response.get("Contents", [])]
            logger.info(f"Listed {len(reports)} S3 report(s)")
            return reports
        except Exception as e:
            logger.error(f"Failed to list S3 reports: {e}")
            raise

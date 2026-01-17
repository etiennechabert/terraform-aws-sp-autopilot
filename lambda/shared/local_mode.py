"""
Local mode utilities for running Lambdas locally with filesystem I/O.

This module provides utilities to detect local mode and manage local data directories
for debugging and development purposes.
"""

import os
from pathlib import Path


def is_local_mode() -> bool:
    """
    Check if Lambda is running in local mode.

    Returns:
        bool: True if LOCAL_MODE environment variable is set to 'true', False otherwise.
    """
    return os.getenv("LOCAL_MODE", "false").lower() == "true"


def get_local_data_dir() -> Path:
    """
    Get the local data directory for filesystem I/O operations.

    Returns:
        Path: Path object pointing to the local data directory.
              Defaults to './local_data' if LOCAL_DATA_DIR is not set.
    """
    data_dir = Path(os.getenv("LOCAL_DATA_DIR", "./local_data"))
    # Ensure directory exists
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def get_queue_dir() -> Path:
    """
    Get the local queue directory for SQS message simulation.

    Returns:
        Path: Path object pointing to the queue directory.
    """
    queue_dir = get_local_data_dir() / "queue"
    queue_dir.mkdir(parents=True, exist_ok=True)
    return queue_dir


def get_reports_dir() -> Path:
    """
    Get the local reports directory for S3 simulation.

    Returns:
        Path: Path object pointing to the reports directory.
    """
    reports_dir = get_local_data_dir() / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    return reports_dir


def get_logs_dir() -> Path:
    """
    Get the local logs directory for Lambda logs.

    Returns:
        Path: Path object pointing to the logs directory.
    """
    logs_dir = get_local_data_dir() / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    return logs_dir

"""
Tests for Email Notifications Module.

Tests the email notification functionality for both scheduled purchases
and dry run analysis.
"""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError


# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from email_notifications import send_dry_run_email, send_scheduled_email


@pytest.fixture
def mock_sns_client():
    """Provide mock SNS client."""
    return MagicMock()


@pytest.fixture
def mock_config():
    """Provide basic configuration."""
    return {
        "coverage_target_percent": 80.0,
        "queue_url": "https://sqs.us-east-1.amazonaws.com/123456789/purchase-queue",
        "sns_topic_arn": "arn:aws:sns:us-east-1:123456789:sp-notifications",
    }


@pytest.fixture
def mock_coverage():
    """Provide coverage data."""
    return {"compute": 50.0, "database": 60.0, "sagemaker": 40.0}


@pytest.fixture
def mock_purchase_plans():
    """Provide purchase plans data."""
    return [
        {
            "sp_type": "compute",
            "hourly_commitment": 2.5,
            "term": "THREE_YEAR",
            "payment_option": "ALL_UPFRONT",
        },
        {
            "sp_type": "database",
            "hourly_commitment": 1.25,
            "term": "ONE_YEAR",
            "payment_option": "NO_UPFRONT",
        },
        {
            "sp_type": "sagemaker",
            "hourly_commitment": 0.75,
            "term": "ONE_YEAR",
            "payment_option": "ALL_UPFRONT",
        },
    ]


def test_send_scheduled_email_success(
    mock_sns_client, mock_config, mock_purchase_plans, mock_coverage
):
    """Test sending scheduled email successfully."""
    with patch("email_notifications.local_mode.is_local_mode", return_value=False):
        send_scheduled_email(mock_sns_client, mock_config, mock_purchase_plans, mock_coverage)

    # Verify SNS publish was called
    assert mock_sns_client.publish.called
    call_args = mock_sns_client.publish.call_args[1]

    # Verify SNS parameters
    assert call_args["TopicArn"] == mock_config["sns_topic_arn"]
    assert call_args["Subject"] == "Savings Plans Scheduled for Purchase"
    assert "Total Plans Queued: 3" in call_args["Message"]
    assert "COMPUTE" in call_args["Message"]
    assert "DATABASE" in call_args["Message"]
    assert "SAGEMAKER" in call_args["Message"]


def test_send_scheduled_email_local_mode(
    mock_sns_client, mock_config, mock_purchase_plans, mock_coverage
):
    """Test that email is not sent in local mode."""
    with patch("email_notifications.local_mode.is_local_mode", return_value=True):
        send_scheduled_email(mock_sns_client, mock_config, mock_purchase_plans, mock_coverage)

    # Verify SNS publish was NOT called
    assert not mock_sns_client.publish.called


def test_send_scheduled_email_calculates_costs(
    mock_sns_client, mock_config, mock_purchase_plans, mock_coverage
):
    """Test that email includes cost calculations."""
    with patch("email_notifications.local_mode.is_local_mode", return_value=False):
        send_scheduled_email(mock_sns_client, mock_config, mock_purchase_plans, mock_coverage)

    message = mock_sns_client.publish.call_args[1]["Message"]

    # Verify annual cost calculation (2.5 * 8760 = 21900)
    assert "21,900.00" in message
    # Verify total (2.5 + 1.25 + 0.75) * 8760 = 39420
    assert "39,420.00" in message


def test_send_scheduled_email_includes_coverage(
    mock_sns_client, mock_config, mock_purchase_plans, mock_coverage
):
    """Test that email includes current coverage information."""
    with patch("email_notifications.local_mode.is_local_mode", return_value=False):
        send_scheduled_email(mock_sns_client, mock_config, mock_purchase_plans, mock_coverage)

    message = mock_sns_client.publish.call_args[1]["Message"]

    # Verify coverage is included
    assert "50.00%" in message  # compute coverage
    assert "60.00%" in message  # database coverage
    assert "40.00%" in message  # sagemaker coverage
    assert "Target Coverage: 80.00%" in message


def test_send_scheduled_email_includes_cancellation_instructions(
    mock_sns_client, mock_config, mock_purchase_plans, mock_coverage
):
    """Test that email includes cancellation instructions."""
    with patch("email_notifications.local_mode.is_local_mode", return_value=False):
        send_scheduled_email(mock_sns_client, mock_config, mock_purchase_plans, mock_coverage)

    message = mock_sns_client.publish.call_args[1]["Message"]

    # Verify cancellation instructions
    assert "CANCELLATION INSTRUCTIONS" in message
    assert "aws sqs purge-queue" in message
    assert mock_config["queue_url"] in message


def test_send_scheduled_email_sns_error(
    mock_sns_client, mock_config, mock_purchase_plans, mock_coverage
):
    """Test handling of SNS client errors."""
    mock_sns_client.publish.side_effect = ClientError(
        {"Error": {"Code": "InvalidParameter", "Message": "Invalid topic ARN"}},
        "Publish",
    )

    with (
        patch("email_notifications.local_mode.is_local_mode", return_value=False),
        pytest.raises(ClientError),
    ):
        send_scheduled_email(mock_sns_client, mock_config, mock_purchase_plans, mock_coverage)


def test_send_scheduled_email_empty_plans(mock_sns_client, mock_config, mock_coverage):
    """Test sending email with no purchase plans."""
    with patch("email_notifications.local_mode.is_local_mode", return_value=False):
        send_scheduled_email(mock_sns_client, mock_config, [], mock_coverage)

    message = mock_sns_client.publish.call_args[1]["Message"]
    assert "Total Plans Queued: 0" in message
    assert "Total Estimated Annual Cost: $0.00" in message


def test_send_dry_run_email_success(
    mock_sns_client, mock_config, mock_purchase_plans, mock_coverage
):
    """Test sending dry run email successfully."""
    with patch("email_notifications.local_mode.is_local_mode", return_value=False):
        send_dry_run_email(mock_sns_client, mock_config, mock_purchase_plans, mock_coverage)

    # Verify SNS publish was called
    assert mock_sns_client.publish.called
    call_args = mock_sns_client.publish.call_args[1]

    # Verify SNS parameters
    assert call_args["TopicArn"] == mock_config["sns_topic_arn"]
    assert call_args["Subject"] == "[DRY RUN] Savings Plans Analysis - No Purchases Scheduled"
    assert "***** DRY RUN MODE *****" in call_args["Message"]
    assert "NO PURCHASES WERE SCHEDULED" in call_args["Message"]
    assert "Total Plans Analyzed: 3" in call_args["Message"]


def test_send_dry_run_email_local_mode(
    mock_sns_client, mock_config, mock_purchase_plans, mock_coverage
):
    """Test that dry run email is not sent in local mode."""
    with patch("email_notifications.local_mode.is_local_mode", return_value=True):
        send_dry_run_email(mock_sns_client, mock_config, mock_purchase_plans, mock_coverage)

    # Verify SNS publish was NOT called
    assert not mock_sns_client.publish.called


def test_send_dry_run_email_includes_instructions(
    mock_sns_client, mock_config, mock_purchase_plans, mock_coverage
):
    """Test that dry run email includes enabling instructions."""
    with patch("email_notifications.local_mode.is_local_mode", return_value=False):
        send_dry_run_email(mock_sns_client, mock_config, mock_purchase_plans, mock_coverage)

    message = mock_sns_client.publish.call_args[1]["Message"]

    # Verify instructions are included
    assert "TO ENABLE ACTUAL PURCHASES" in message
    assert "DRY_RUN=false" in message
    assert "aws lambda update-function-configuration" in message
    assert "terraform.tfvars" in message


def test_send_dry_run_email_calculates_costs(
    mock_sns_client, mock_config, mock_purchase_plans, mock_coverage
):
    """Test that dry run email includes cost calculations."""
    with patch("email_notifications.local_mode.is_local_mode", return_value=False):
        send_dry_run_email(mock_sns_client, mock_config, mock_purchase_plans, mock_coverage)

    message = mock_sns_client.publish.call_args[1]["Message"]

    # Verify annual cost calculation
    assert "21,900.00" in message
    # Verify total cost
    assert "39,420.00" in message


def test_send_dry_run_email_sns_error(
    mock_sns_client, mock_config, mock_purchase_plans, mock_coverage
):
    """Test handling of SNS client errors in dry run."""
    mock_sns_client.publish.side_effect = ClientError(
        {"Error": {"Code": "InvalidParameter", "Message": "Invalid topic ARN"}},
        "Publish",
    )

    with (
        patch("email_notifications.local_mode.is_local_mode", return_value=False),
        pytest.raises(ClientError),
    ):
        send_dry_run_email(mock_sns_client, mock_config, mock_purchase_plans, mock_coverage)


def test_send_dry_run_email_empty_plans(mock_sns_client, mock_config, mock_coverage):
    """Test sending dry run email with no purchase plans."""
    with patch("email_notifications.local_mode.is_local_mode", return_value=False):
        send_dry_run_email(mock_sns_client, mock_config, [], mock_coverage)

    message = mock_sns_client.publish.call_args[1]["Message"]
    assert "Total Plans Analyzed: 0" in message
    assert "Total Estimated Annual Cost: $0.00" in message


def test_send_scheduled_email_missing_coverage_keys(
    mock_sns_client, mock_config, mock_purchase_plans
):
    """Test handling of missing coverage data keys."""
    empty_coverage = {}

    with patch("email_notifications.local_mode.is_local_mode", return_value=False):
        send_scheduled_email(mock_sns_client, mock_config, mock_purchase_plans, empty_coverage)

    message = mock_sns_client.publish.call_args[1]["Message"]
    # Should default to 0.00%
    assert "0.00%" in message


def test_send_dry_run_email_missing_coverage_keys(
    mock_sns_client, mock_config, mock_purchase_plans
):
    """Test handling of missing coverage data keys in dry run."""
    empty_coverage = {}

    with patch("email_notifications.local_mode.is_local_mode", return_value=False):
        send_dry_run_email(mock_sns_client, mock_config, mock_purchase_plans, empty_coverage)

    message = mock_sns_client.publish.call_args[1]["Message"]
    # Should default to 0.00%
    assert "0.00%" in message

"""
Unit tests for configuration module.

Tests the load_configuration function with default values and custom environment
variables to ensure proper configuration loading.
"""

import os
import sys

import pytest


# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import config


@pytest.fixture
def mock_env_vars(monkeypatch):
    """Set up environment variables for testing."""
    monkeypatch.setenv("QUEUE_URL", "https://sqs.us-east-1.amazonaws.com/123456789012/test-queue")
    monkeypatch.setenv("SNS_TOPIC_ARN", "arn:aws:sns:us-east-1:123456789012:test-topic")
    monkeypatch.setenv("DRY_RUN", "true")
    monkeypatch.setenv("ENABLE_COMPUTE_SP", "true")
    monkeypatch.setenv("ENABLE_DATABASE_SP", "false")
    monkeypatch.setenv("ENABLE_SAGEMAKER_SP", "false")
    monkeypatch.setenv("COVERAGE_TARGET_PERCENT", "90")
    monkeypatch.setenv("PURCHASE_STRATEGY_TYPE", "follow_aws")
    monkeypatch.setenv("MAX_PURCHASE_PERCENT", "10")
    monkeypatch.setenv("MIN_PURCHASE_PERCENT", "1")
    monkeypatch.setenv("RENEWAL_WINDOW_DAYS", "7")
    monkeypatch.setenv("LOOKBACK_DAYS", "30")
    monkeypatch.setenv("MIN_COMMITMENT_PER_PLAN", "0.001")
    monkeypatch.setenv("COMPUTE_SP_TERM", "THREE_YEAR")
    monkeypatch.setenv("COMPUTE_SP_PAYMENT_OPTION", "ALL_UPFRONT")
    monkeypatch.setenv("SAGEMAKER_SP_TERM", "THREE_YEAR")
    monkeypatch.setenv("SAGEMAKER_SP_PAYMENT_OPTION", "ALL_UPFRONT")
    monkeypatch.setenv("TAGS", "{}")


# ============================================================================
# Configuration Tests
# ============================================================================


def test_load_configuration_defaults(mock_env_vars):
    """Test that load_configuration returns correct default values."""
    cfg = config.load_configuration()

    assert cfg["queue_url"] == "https://sqs.us-east-1.amazonaws.com/123456789012/test-queue"
    assert cfg["sns_topic_arn"] == "arn:aws:sns:us-east-1:123456789012:test-topic"
    assert cfg["dry_run"] is True
    assert cfg["enable_compute_sp"] is True
    assert cfg["enable_database_sp"] is False
    assert cfg["enable_sagemaker_sp"] is False
    assert cfg["coverage_target_percent"] == 90.0
    assert cfg["purchase_strategy_type"] == "follow_aws"
    assert cfg["max_purchase_percent"] == 10.0
    assert cfg["min_purchase_percent"] == 1.0
    assert cfg["renewal_window_days"] == 7
    assert cfg["lookback_days"] == 30
    assert cfg["min_commitment_per_plan"] == 0.001
    assert cfg["compute_sp_term"] == "THREE_YEAR"
    assert cfg["sagemaker_sp_term"] == "THREE_YEAR"
    assert cfg["sagemaker_sp_payment_option"] == "ALL_UPFRONT"


def test_load_configuration_custom_values(monkeypatch):
    """Test that load_configuration handles custom environment values."""
    monkeypatch.setenv("QUEUE_URL", "custom-queue-url")
    monkeypatch.setenv("SNS_TOPIC_ARN", "custom-sns-arn")
    monkeypatch.setenv("DRY_RUN", "false")
    monkeypatch.setenv("ENABLE_SAGEMAKER_SP", "true")
    monkeypatch.setenv("COVERAGE_TARGET_PERCENT", "85.5")
    monkeypatch.setenv("PURCHASE_STRATEGY_TYPE", "dichotomy")
    monkeypatch.setenv("MAX_PURCHASE_PERCENT", "15")
    monkeypatch.setenv("MIN_PURCHASE_PERCENT", "2")
    monkeypatch.setenv("COMPUTE_SP_TERM", "ONE_YEAR")
    monkeypatch.setenv("SAGEMAKER_SP_TERM", "ONE_YEAR")
    monkeypatch.setenv("SAGEMAKER_SP_PAYMENT_OPTION", "NO_UPFRONT")

    cfg = config.load_configuration()

    assert cfg["queue_url"] == "custom-queue-url"
    assert cfg["sns_topic_arn"] == "custom-sns-arn"
    assert cfg["dry_run"] is False
    assert cfg["enable_sagemaker_sp"] is True
    assert cfg["coverage_target_percent"] == 85.5
    assert cfg["purchase_strategy_type"] == "dichotomy"
    assert cfg["max_purchase_percent"] == 15.0
    assert cfg["min_purchase_percent"] == 2.0
    assert cfg["compute_sp_term"] == "ONE_YEAR"
    assert cfg["sagemaker_sp_term"] == "ONE_YEAR"
    assert cfg["sagemaker_sp_payment_option"] == "NO_UPFRONT"

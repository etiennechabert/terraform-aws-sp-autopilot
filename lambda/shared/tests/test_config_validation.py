"""
Essential validation tests for configuration validation module.
Tests critical validation logic and error paths.
"""

import pytest

from shared.config_validation import (
    VALID_PAYMENT_OPTIONS,
    VALID_PURCHASE_STRATEGIES,
    VALID_REPORT_FORMATS,
    validate_purchaser_config,
    validate_reporter_config,
    validate_scheduler_config,
)


# ============================================================================
# SCHEDULER CONFIG VALIDATION TESTS
# ============================================================================


def test_valid_scheduler_config():
    """Test that a valid scheduler config passes validation."""
    config = {
        "coverage_target_percent": 90.0,
        "max_purchase_percent": 10.0,
        "min_purchase_percent": 1.0,
        "renewal_window_days": 7,
        "lookback_days": 30,
        "min_data_days": 14,
        "min_commitment_per_plan": 0.001,
        "compute_sp_term_mix": {"three_year": 0.67, "one_year": 0.33},
        "compute_sp_payment_option": "ALL_UPFRONT",
        "sagemaker_sp_term_mix": {"three_year": 0.67, "one_year": 0.33},
        "sagemaker_sp_payment_option": "ALL_UPFRONT",
        "purchase_strategy_type": "simple",
    }
    validate_scheduler_config(config)


def test_scheduler_config_not_dict():
    """Test that non-dict scheduler config raises ValueError."""
    with pytest.raises(ValueError, match="must be a dictionary"):
        validate_scheduler_config("not a dict")


def test_scheduler_invalid_coverage_target_percent_type():
    """Test that invalid coverage_target_percent type raises ValueError."""
    config = {
        "coverage_target_percent": "90.0",  # String instead of number
    }
    with pytest.raises(ValueError, match=r"coverage_target_percent.*must be a number"):
        validate_scheduler_config(config)


def test_scheduler_coverage_target_percent_below_range():
    """Test that coverage_target_percent below 0 raises ValueError."""
    config = {
        "coverage_target_percent": -10.0,
    }
    with pytest.raises(
        ValueError, match=r"coverage_target_percent.*must be between 0\.0 and 100\.0"
    ):
        validate_scheduler_config(config)


def test_scheduler_coverage_target_percent_above_range():
    """Test that coverage_target_percent above 100 raises ValueError."""
    config = {
        "coverage_target_percent": 150.0,
    }
    with pytest.raises(
        ValueError, match=r"coverage_target_percent.*must be between 0\.0 and 100\.0"
    ):
        validate_scheduler_config(config)


def test_scheduler_invalid_max_purchase_percent_type():
    """Test that invalid max_purchase_percent type raises ValueError."""
    config = {
        "max_purchase_percent": "10.0",  # String instead of number
    }
    with pytest.raises(ValueError, match=r"max_purchase_percent.*must be a number"):
        validate_scheduler_config(config)


def test_scheduler_max_purchase_percent_out_of_range():
    """Test that max_purchase_percent out of range raises ValueError."""
    config = {
        "max_purchase_percent": 200.0,
    }
    with pytest.raises(
        ValueError, match=r"max_purchase_percent.*must be between 0\.0 and 100\.0"
    ):
        validate_scheduler_config(config)


def test_scheduler_invalid_min_purchase_percent_type():
    """Test that invalid min_purchase_percent type raises ValueError."""
    config = {
        "min_purchase_percent": None,  # None instead of number
    }
    with pytest.raises(ValueError, match=r"min_purchase_percent.*must be a number"):
        validate_scheduler_config(config)


def test_scheduler_min_purchase_percent_below_range():
    """Test that min_purchase_percent below 0 raises ValueError."""
    config = {
        "min_purchase_percent": -5.0,
    }
    with pytest.raises(
        ValueError, match=r"min_purchase_percent.*must be between 0\.0 and 100\.0"
    ):
        validate_scheduler_config(config)


def test_scheduler_min_greater_than_max():
    """Test that min_purchase_percent >= max_purchase_percent raises ValueError."""
    config = {
        "min_purchase_percent": 20.0,
        "max_purchase_percent": 10.0,
    }
    with pytest.raises(
        ValueError,
        match=r"min_purchase_percent.*must be less than.*max_purchase_percent",
    ):
        validate_scheduler_config(config)


def test_scheduler_min_equals_max():
    """Test that min_purchase_percent == max_purchase_percent raises ValueError."""
    config = {
        "min_purchase_percent": 10.0,
        "max_purchase_percent": 10.0,
    }
    with pytest.raises(
        ValueError,
        match=r"min_purchase_percent.*must be less than.*max_purchase_percent",
    ):
        validate_scheduler_config(config)


def test_scheduler_invalid_renewal_window_days_type():
    """Test that invalid renewal_window_days type raises ValueError."""
    config = {
        "renewal_window_days": 7.5,  # Float instead of int
    }
    with pytest.raises(ValueError, match=r"renewal_window_days.*must be an integer"):
        validate_scheduler_config(config)


def test_scheduler_renewal_window_days_zero():
    """Test that renewal_window_days of 0 raises ValueError."""
    config = {
        "renewal_window_days": 0,
    }
    with pytest.raises(ValueError, match=r"renewal_window_days.*must be greater than 0"):
        validate_scheduler_config(config)


def test_scheduler_renewal_window_days_negative():
    """Test that negative renewal_window_days raises ValueError."""
    config = {
        "renewal_window_days": -7,
    }
    with pytest.raises(ValueError, match=r"renewal_window_days.*must be greater than 0"):
        validate_scheduler_config(config)


def test_scheduler_invalid_lookback_days_type():
    """Test that invalid lookback_days type raises ValueError."""
    config = {
        "lookback_days": "30",  # String instead of int
    }
    with pytest.raises(ValueError, match=r"lookback_days.*must be a number"):
        validate_scheduler_config(config)


def test_scheduler_lookback_days_not_integer():
    """Test that non-integer lookback_days raises ValueError."""
    config = {
        "lookback_days": 30.5,  # Float instead of int
    }
    with pytest.raises(ValueError, match=r"lookback_days.*must be an integer"):
        validate_scheduler_config(config)


def test_scheduler_lookback_days_zero():
    """Test that lookback_days of 0 raises ValueError."""
    config = {
        "lookback_days": 0,
    }
    with pytest.raises(ValueError, match=r"lookback_days.*must be greater than 0"):
        validate_scheduler_config(config)


def test_scheduler_invalid_min_data_days_type():
    """Test that invalid min_data_days type raises ValueError."""
    config = {
        "min_data_days": None,
    }
    with pytest.raises(ValueError, match=r"min_data_days.*must be a number"):
        validate_scheduler_config(config)


def test_scheduler_min_data_days_not_integer():
    """Test that non-integer min_data_days raises ValueError."""
    config = {
        "min_data_days": 14.5,
    }
    with pytest.raises(ValueError, match=r"min_data_days.*must be an integer"):
        validate_scheduler_config(config)


def test_scheduler_min_data_days_negative():
    """Test that negative min_data_days raises ValueError."""
    config = {
        "min_data_days": -1,
    }
    with pytest.raises(ValueError, match=r"min_data_days.*must be greater than 0"):
        validate_scheduler_config(config)


def test_scheduler_lookback_less_than_min_data():
    """Test that lookback_days < min_data_days raises ValueError."""
    config = {
        "lookback_days": 10,
        "min_data_days": 14,
    }
    with pytest.raises(
        ValueError,
        match=r"lookback_days.*must be greater than or equal to.*min_data_days",
    ):
        validate_scheduler_config(config)


def test_scheduler_invalid_min_commitment_type():
    """Test that invalid min_commitment_per_plan type raises ValueError."""
    config = {
        "min_commitment_per_plan": "0.001",  # String instead of number
    }
    with pytest.raises(ValueError, match=r"min_commitment_per_plan.*must be a number"):
        validate_scheduler_config(config)


def test_scheduler_negative_min_commitment():
    """Test that negative min_commitment_per_plan raises ValueError."""
    config = {
        "min_commitment_per_plan": -1.0,
    }
    with pytest.raises(
        ValueError,
        match=r"min_commitment_per_plan.*must be greater than or equal to 0",
    ):
        validate_scheduler_config(config)


def test_scheduler_invalid_compute_term_mix_not_dict():
    """Test that non-dict compute_sp_term_mix raises ValueError."""
    config = {
        "compute_sp_term_mix": [0.67, 0.33],  # List instead of dict
    }
    with pytest.raises(ValueError, match=r"compute_sp_term_mix.*must be a dictionary"):
        validate_scheduler_config(config)


def test_scheduler_empty_compute_term_mix():
    """Test that empty compute_sp_term_mix raises ValueError."""
    config = {
        "compute_sp_term_mix": {},
    }
    with pytest.raises(ValueError, match=r"compute_sp_term_mix.*cannot be empty"):
        validate_scheduler_config(config)


def test_scheduler_compute_term_mix_invalid_value_type():
    """Test that non-numeric compute_sp_term_mix value raises ValueError."""
    config = {
        "compute_sp_term_mix": {"three_year": "0.67", "one_year": 0.33},
    }
    with pytest.raises(
        ValueError, match=r"compute_sp_term_mix\[three_year\].*must be a number"
    ):
        validate_scheduler_config(config)


def test_scheduler_compute_term_mix_value_below_range():
    """Test that compute_sp_term_mix value below 0 raises ValueError."""
    config = {
        "compute_sp_term_mix": {"three_year": -0.5, "one_year": 1.5},
    }
    with pytest.raises(
        ValueError, match=r"compute_sp_term_mix\[three_year\].*must be between 0 and 1"
    ):
        validate_scheduler_config(config)


def test_scheduler_compute_term_mix_value_above_range():
    """Test that compute_sp_term_mix value above 1 raises ValueError."""
    config = {
        "compute_sp_term_mix": {"three_year": 0.5, "one_year": 1.5},
    }
    with pytest.raises(
        ValueError, match=r"compute_sp_term_mix\[one_year\].*must be between 0 and 1"
    ):
        validate_scheduler_config(config)


def test_scheduler_compute_term_mix_sum_too_low():
    """Test that compute_sp_term_mix sum < 0.99 raises ValueError."""
    config = {
        "compute_sp_term_mix": {"three_year": 0.3, "one_year": 0.2},
    }
    with pytest.raises(
        ValueError, match=r"compute_sp_term_mix.*values must sum to approximately 1.0"
    ):
        validate_scheduler_config(config)


def test_scheduler_compute_term_mix_sum_too_high():
    """Test that compute_sp_term_mix sum > 1.01 raises ValueError."""
    config = {
        "compute_sp_term_mix": {"three_year": 0.7, "one_year": 0.7},
    }
    with pytest.raises(
        ValueError, match=r"compute_sp_term_mix.*values must sum to approximately 1.0"
    ):
        validate_scheduler_config(config)


def test_scheduler_invalid_sagemaker_term_mix_not_dict():
    """Test that non-dict sagemaker_sp_term_mix raises ValueError."""
    config = {
        "sagemaker_sp_term_mix": "invalid",
    }
    with pytest.raises(ValueError, match=r"sagemaker_sp_term_mix.*must be a dictionary"):
        validate_scheduler_config(config)


def test_scheduler_sagemaker_term_mix_sum_invalid():
    """Test that sagemaker_sp_term_mix sum not ~1.0 raises ValueError."""
    config = {
        "sagemaker_sp_term_mix": {"three_year": 0.5, "one_year": 0.1},
    }
    with pytest.raises(
        ValueError, match=r"sagemaker_sp_term_mix.*values must sum to approximately 1.0"
    ):
        validate_scheduler_config(config)


def test_scheduler_invalid_compute_payment_option():
    """Test that invalid compute_sp_payment_option raises ValueError."""
    config = {
        "compute_sp_payment_option": "INVALID_OPTION",
    }
    with pytest.raises(
        ValueError, match=r"Invalid compute_sp_payment_option.*Must be one of"
    ):
        validate_scheduler_config(config)


def test_scheduler_invalid_sagemaker_payment_option():
    """Test that invalid sagemaker_sp_payment_option raises ValueError."""
    config = {
        "sagemaker_sp_payment_option": "NOT_VALID",
    }
    with pytest.raises(
        ValueError, match=r"Invalid sagemaker_sp_payment_option.*Must be one of"
    ):
        validate_scheduler_config(config)


def test_scheduler_invalid_purchase_strategy_type():
    """Test that invalid purchase_strategy_type raises ValueError."""
    config = {
        "purchase_strategy_type": "complex",
    }
    with pytest.raises(
        ValueError, match=r"Invalid purchase_strategy_type.*Must be one of"
    ):
        validate_scheduler_config(config)


# ============================================================================
# REPORTER CONFIG VALIDATION TESTS
# ============================================================================


def test_valid_reporter_config():
    """Test that a valid reporter config passes validation."""
    config = {
        "report_format": "html",
        "email_reports": True,
        "tags": {"Environment": "production"},
        "reports_bucket": "my-reports-bucket",
        "sns_topic_arn": "arn:aws:sns:us-east-1:123456789012:my-topic",
    }
    validate_reporter_config(config)


def test_reporter_config_not_dict():
    """Test that non-dict reporter config raises ValueError."""
    with pytest.raises(ValueError, match="must be a dictionary"):
        validate_reporter_config([])


def test_reporter_invalid_report_format():
    """Test that invalid report_format raises ValueError."""
    config = {
        "report_format": "pdf",
    }
    with pytest.raises(ValueError, match=r"Invalid report_format.*Must be one of"):
        validate_reporter_config(config)


def test_reporter_invalid_email_reports_type():
    """Test that invalid email_reports type raises ValueError."""
    config = {
        "email_reports": "true",  # String instead of boolean
    }
    with pytest.raises(ValueError, match=r"email_reports.*must be a boolean"):
        validate_reporter_config(config)


def test_reporter_invalid_tags_type():
    """Test that invalid tags type raises ValueError."""
    config = {
        "tags": ["tag1", "tag2"],  # List instead of dict
    }
    with pytest.raises(ValueError, match=r"tags.*must be a dictionary"):
        validate_reporter_config(config)


def test_reporter_empty_reports_bucket():
    """Test that empty reports_bucket raises ValueError."""
    config = {
        "reports_bucket": "",
    }
    with pytest.raises(ValueError, match=r"reports_bucket.*must be a non-empty string"):
        validate_reporter_config(config)


def test_reporter_whitespace_reports_bucket():
    """Test that whitespace-only reports_bucket raises ValueError."""
    config = {
        "reports_bucket": "   ",
    }
    with pytest.raises(ValueError, match=r"reports_bucket.*must be a non-empty string"):
        validate_reporter_config(config)


def test_reporter_invalid_reports_bucket_type():
    """Test that non-string reports_bucket raises ValueError."""
    config = {
        "reports_bucket": 123,
    }
    with pytest.raises(ValueError, match=r"reports_bucket.*must be a non-empty string"):
        validate_reporter_config(config)


def test_reporter_empty_sns_topic_arn():
    """Test that empty sns_topic_arn raises ValueError."""
    config = {
        "sns_topic_arn": "",
    }
    with pytest.raises(ValueError, match=r"sns_topic_arn.*must be a non-empty string"):
        validate_reporter_config(config)


def test_reporter_invalid_sns_topic_arn_type():
    """Test that non-string sns_topic_arn raises ValueError."""
    config = {
        "sns_topic_arn": None,
    }
    with pytest.raises(ValueError, match=r"sns_topic_arn.*must be a non-empty string"):
        validate_reporter_config(config)


def test_reporter_empty_management_account_role_arn():
    """Test that empty management_account_role_arn raises ValueError."""
    config = {
        "management_account_role_arn": "",
    }
    with pytest.raises(
        ValueError, match=r"management_account_role_arn.*must be a non-empty string"
    ):
        validate_reporter_config(config)


def test_reporter_empty_slack_webhook_url():
    """Test that empty slack_webhook_url raises ValueError."""
    config = {
        "slack_webhook_url": "",
    }
    with pytest.raises(
        ValueError, match=r"slack_webhook_url.*must be a non-empty string"
    ):
        validate_reporter_config(config)


def test_reporter_empty_teams_webhook_url():
    """Test that empty teams_webhook_url raises ValueError."""
    config = {
        "teams_webhook_url": "",
    }
    with pytest.raises(
        ValueError, match=r"teams_webhook_url.*must be a non-empty string"
    ):
        validate_reporter_config(config)


# ============================================================================
# PURCHASER CONFIG VALIDATION TESTS
# ============================================================================


def test_valid_purchaser_config():
    """Test that a valid purchaser config passes validation."""
    config = {
        "max_coverage_cap": 95.0,
        "renewal_window_days": 7,
        "tags": {"Environment": "production"},
        "queue_url": "https://sqs.us-east-1.amazonaws.com/123456789012/my-queue",
        "sns_topic_arn": "arn:aws:sns:us-east-1:123456789012:my-topic",
    }
    validate_purchaser_config(config)


def test_purchaser_config_not_dict():
    """Test that non-dict purchaser config raises ValueError."""
    with pytest.raises(ValueError, match="must be a dictionary"):
        validate_purchaser_config(None)


def test_purchaser_invalid_max_coverage_cap_type():
    """Test that invalid max_coverage_cap type raises ValueError."""
    config = {
        "max_coverage_cap": "95.0",  # String instead of number
    }
    with pytest.raises(ValueError, match=r"max_coverage_cap.*must be a number"):
        validate_purchaser_config(config)


def test_purchaser_max_coverage_cap_below_range():
    """Test that max_coverage_cap below 0 raises ValueError."""
    config = {
        "max_coverage_cap": -10.0,
    }
    with pytest.raises(ValueError, match=r"max_coverage_cap.*must be between 0\.0 and 100\.0"):
        validate_purchaser_config(config)


def test_purchaser_max_coverage_cap_above_range():
    """Test that max_coverage_cap above 100 raises ValueError."""
    config = {
        "max_coverage_cap": 150.0,
    }
    with pytest.raises(ValueError, match=r"max_coverage_cap.*must be between 0\.0 and 100\.0"):
        validate_purchaser_config(config)


def test_purchaser_invalid_renewal_window_days_type():
    """Test that invalid renewal_window_days type raises ValueError."""
    config = {
        "renewal_window_days": "7",  # String instead of int
    }
    with pytest.raises(ValueError, match=r"renewal_window_days.*must be a number"):
        validate_purchaser_config(config)


def test_purchaser_renewal_window_days_not_integer():
    """Test that non-integer renewal_window_days raises ValueError."""
    config = {
        "renewal_window_days": 7.5,
    }
    with pytest.raises(ValueError, match=r"renewal_window_days.*must be an integer"):
        validate_purchaser_config(config)


def test_purchaser_renewal_window_days_zero():
    """Test that renewal_window_days of 0 raises ValueError."""
    config = {
        "renewal_window_days": 0,
    }
    with pytest.raises(ValueError, match=r"renewal_window_days.*must be greater than 0"):
        validate_purchaser_config(config)


def test_purchaser_renewal_window_days_negative():
    """Test that negative renewal_window_days raises ValueError."""
    config = {
        "renewal_window_days": -1,
    }
    with pytest.raises(ValueError, match=r"renewal_window_days.*must be greater than 0"):
        validate_purchaser_config(config)


def test_purchaser_invalid_tags_type():
    """Test that invalid tags type raises ValueError."""
    config = {
        "tags": "invalid",
    }
    with pytest.raises(ValueError, match=r"tags.*must be a dictionary"):
        validate_purchaser_config(config)


def test_purchaser_empty_queue_url():
    """Test that empty queue_url raises ValueError."""
    config = {
        "queue_url": "",
    }
    with pytest.raises(ValueError, match=r"queue_url.*must be a non-empty string"):
        validate_purchaser_config(config)


def test_purchaser_whitespace_queue_url():
    """Test that whitespace-only queue_url raises ValueError."""
    config = {
        "queue_url": "   ",
    }
    with pytest.raises(ValueError, match=r"queue_url.*must be a non-empty string"):
        validate_purchaser_config(config)


def test_purchaser_invalid_queue_url_type():
    """Test that non-string queue_url raises ValueError."""
    config = {
        "queue_url": 12345,
    }
    with pytest.raises(ValueError, match=r"queue_url.*must be a non-empty string"):
        validate_purchaser_config(config)


def test_purchaser_empty_sns_topic_arn():
    """Test that empty sns_topic_arn raises ValueError."""
    config = {
        "sns_topic_arn": "",
    }
    with pytest.raises(ValueError, match=r"sns_topic_arn.*must be a non-empty string"):
        validate_purchaser_config(config)


def test_purchaser_invalid_sns_topic_arn_type():
    """Test that non-string sns_topic_arn raises ValueError."""
    config = {
        "sns_topic_arn": None,
    }
    with pytest.raises(ValueError, match=r"sns_topic_arn.*must be a non-empty string"):
        validate_purchaser_config(config)


def test_purchaser_empty_management_account_role_arn():
    """Test that empty management_account_role_arn raises ValueError."""
    config = {
        "management_account_role_arn": "",
    }
    with pytest.raises(
        ValueError, match=r"management_account_role_arn.*must be a non-empty string"
    ):
        validate_purchaser_config(config)


def test_purchaser_empty_slack_webhook_url():
    """Test that empty slack_webhook_url raises ValueError."""
    config = {
        "slack_webhook_url": "",
    }
    with pytest.raises(
        ValueError, match=r"slack_webhook_url.*must be a non-empty string"
    ):
        validate_purchaser_config(config)


def test_purchaser_empty_teams_webhook_url():
    """Test that empty teams_webhook_url raises ValueError."""
    config = {
        "teams_webhook_url": "",
    }
    with pytest.raises(
        ValueError, match=r"teams_webhook_url.*must be a non-empty string"
    ):
        validate_purchaser_config(config)


# ============================================================================
# CONSTANTS VALIDATION TESTS
# ============================================================================


def test_valid_payment_options_constant():
    """Test that VALID_PAYMENT_OPTIONS contains expected values."""
    assert VALID_PAYMENT_OPTIONS == ["NO_UPFRONT", "ALL_UPFRONT", "PARTIAL_UPFRONT"]


def test_valid_purchase_strategies_constant():
    """Test that VALID_PURCHASE_STRATEGIES contains expected values."""
    assert VALID_PURCHASE_STRATEGIES == ["simple"]


def test_valid_report_formats_constant():
    """Test that VALID_REPORT_FORMATS contains expected values."""
    assert VALID_REPORT_FORMATS == ["html", "json"]

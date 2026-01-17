#!/usr/bin/env python3
"""
Manual Validation Test Script

Tests each Lambda handler with intentionally invalid configuration values
to verify validation catches them with descriptive error messages.
"""

import sys
from typing import Any


def test_validation(test_name: str, config: dict[str, Any], validation_func, expected_error: str) -> bool:
    """
    Test a validation function with invalid config and verify error message.

    Args:
        test_name: Name of the test
        config: Configuration to test
        validation_func: Validation function to call
        expected_error: Expected substring in error message

    Returns:
        True if test passed, False otherwise
    """
    try:
        validation_func(config)
        print(f"❌ FAIL: {test_name}")
        print(f"   Expected ValueError but validation passed")
        return False
    except ValueError as e:
        error_msg = str(e)
        if expected_error.lower() in error_msg.lower():
            print(f"✅ PASS: {test_name}")
            print(f"   Error message: {error_msg}")
            return True
        else:
            print(f"❌ FAIL: {test_name}")
            print(f"   Expected error containing: '{expected_error}'")
            print(f"   Got error: {error_msg}")
            return False
    except Exception as e:
        print(f"❌ FAIL: {test_name}")
        print(f"   Unexpected exception: {type(e).__name__}: {e}")
        return False


def main():
    """Run all manual validation tests."""
    # Import validation functions
    sys.path.insert(0, './lambda')
    from shared.config_validation import (
        validate_scheduler_config,
        validate_reporter_config,
        validate_purchaser_config
    )

    print("=" * 80)
    print("MANUAL VALIDATION TESTING")
    print("=" * 80)
    print()

    results = []

    # ========================================================================
    # SCHEDULER VALIDATION TESTS
    # ========================================================================
    print("SCHEDULER VALIDATION TESTS")
    print("-" * 80)

    # Test 1: Invalid coverage_target_percent (negative)
    results.append(test_validation(
        "Scheduler: coverage_target_percent = -10 (negative)",
        {"coverage_target_percent": -10},
        validate_scheduler_config,
        "must be between 0"
    ))

    # Test 2: Invalid coverage_target_percent (too high)
    results.append(test_validation(
        "Scheduler: coverage_target_percent = 150 (too high)",
        {"coverage_target_percent": 150},
        validate_scheduler_config,
        "must be between 0 and 100"
    ))

    # Test 3: Invalid max_purchase_percent (too high)
    results.append(test_validation(
        "Scheduler: max_purchase_percent = 150 (too high)",
        {"max_purchase_percent": 150},
        validate_scheduler_config,
        "must be between 0 and 100"
    ))

    # Test 4: Invalid min_purchase_percent >= max_purchase_percent
    results.append(test_validation(
        "Scheduler: min_purchase_percent >= max_purchase_percent",
        {"min_purchase_percent": 15, "max_purchase_percent": 10},
        validate_scheduler_config,
        "must be less than"
    ))

    # Test 5: Invalid term_mix (sum to 0.5)
    results.append(test_validation(
        "Scheduler: compute_sp_term_mix sum = 0.5 (invalid)",
        {"compute_sp_term_mix": {"three_year": 0.3, "one_year": 0.2}},
        validate_scheduler_config,
        "must sum to approximately 1.0"
    ))

    # Test 6: Invalid term_mix (sum to 1.5)
    results.append(test_validation(
        "Scheduler: sagemaker_sp_term_mix sum = 1.5 (invalid)",
        {"sagemaker_sp_term_mix": {"three_year": 0.8, "one_year": 0.7}},
        validate_scheduler_config,
        "must sum to approximately 1.0"
    ))

    # Test 7: Invalid payment_option
    results.append(test_validation(
        "Scheduler: compute_sp_payment_option = 'INVALID'",
        {"compute_sp_payment_option": "INVALID"},
        validate_scheduler_config,
        "Invalid compute_sp_payment_option"
    ))

    # Test 8: Invalid payment_option for sagemaker
    results.append(test_validation(
        "Scheduler: sagemaker_sp_payment_option = 'MONTHLY_PAYMENT'",
        {"sagemaker_sp_payment_option": "MONTHLY_PAYMENT"},
        validate_scheduler_config,
        "Invalid sagemaker_sp_payment_option"
    ))

    # Test 9: Invalid purchase_strategy_type
    results.append(test_validation(
        "Scheduler: purchase_strategy_type = 'advanced'",
        {"purchase_strategy_type": "advanced"},
        validate_scheduler_config,
        "Invalid purchase_strategy_type"
    ))

    # Test 10: Invalid renewal_window_days (negative)
    results.append(test_validation(
        "Scheduler: renewal_window_days = -5 (negative)",
        {"renewal_window_days": -5},
        validate_scheduler_config,
        "must be greater than 0"
    ))

    # Test 11: Invalid renewal_window_days (float instead of int)
    results.append(test_validation(
        "Scheduler: renewal_window_days = 7.5 (float)",
        {"renewal_window_days": 7.5},
        validate_scheduler_config,
        "must be an integer"
    ))

    # Test 12: Invalid lookback_days < min_data_days
    results.append(test_validation(
        "Scheduler: lookback_days < min_data_days",
        {"lookback_days": 10, "min_data_days": 20},
        validate_scheduler_config,
        "must be greater than or equal to"
    ))

    # Test 13: Invalid min_commitment_per_plan (negative)
    results.append(test_validation(
        "Scheduler: min_commitment_per_plan = -0.5 (negative)",
        {"min_commitment_per_plan": -0.5},
        validate_scheduler_config,
        "must be greater than or equal to 0"
    ))

    # Test 14: Invalid term_mix with negative value
    results.append(test_validation(
        "Scheduler: term_mix with negative value",
        {"compute_sp_term_mix": {"three_year": 1.2, "one_year": -0.2}},
        validate_scheduler_config,
        "must be between 0 and 1"
    ))

    # Test 15: Invalid term_mix with value > 1
    results.append(test_validation(
        "Scheduler: term_mix with value > 1",
        {"sagemaker_sp_term_mix": {"three_year": 1.5, "one_year": -0.5}},
        validate_scheduler_config,
        "must be between 0 and 1"
    ))

    print()

    # ========================================================================
    # REPORTER VALIDATION TESTS
    # ========================================================================
    print("REPORTER VALIDATION TESTS")
    print("-" * 80)

    # Test 16: Invalid report_format
    results.append(test_validation(
        "Reporter: report_format = 'pdf'",
        {"report_format": "pdf"},
        validate_reporter_config,
        "Invalid report_format"
    ))

    # Test 17: Invalid report_format (xml)
    results.append(test_validation(
        "Reporter: report_format = 'xml'",
        {"report_format": "xml"},
        validate_reporter_config,
        "Invalid report_format"
    ))

    # Test 18: Invalid email_reports (string instead of bool)
    results.append(test_validation(
        "Reporter: email_reports = 'true' (string)",
        {"email_reports": "true"},
        validate_reporter_config,
        "must be a boolean"
    ))

    # Test 19: Invalid tags (list instead of dict)
    results.append(test_validation(
        "Reporter: tags = ['tag1', 'tag2'] (list)",
        {"tags": ["tag1", "tag2"]},
        validate_reporter_config,
        "must be a dictionary"
    ))

    # Test 20: Invalid reports_bucket (empty string)
    results.append(test_validation(
        "Reporter: reports_bucket = '' (empty)",
        {"reports_bucket": ""},
        validate_reporter_config,
        "must be a non-empty string"
    ))

    # Test 21: Invalid sns_topic_arn (integer)
    results.append(test_validation(
        "Reporter: sns_topic_arn = 123 (integer)",
        {"sns_topic_arn": 123},
        validate_reporter_config,
        "must be a non-empty string"
    ))

    print()

    # ========================================================================
    # PURCHASER VALIDATION TESTS
    # ========================================================================
    print("PURCHASER VALIDATION TESTS")
    print("-" * 80)

    # Test 22: Invalid max_coverage_cap (too high)
    results.append(test_validation(
        "Purchaser: max_coverage_cap = 150 (too high)",
        {"max_coverage_cap": 150},
        validate_purchaser_config,
        "must be between 0 and 100"
    ))

    # Test 23: Invalid max_coverage_cap (negative)
    results.append(test_validation(
        "Purchaser: max_coverage_cap = -10 (negative)",
        {"max_coverage_cap": -10},
        validate_purchaser_config,
        "must be between 0"
    ))

    # Test 24: Invalid renewal_window_days (zero)
    results.append(test_validation(
        "Purchaser: renewal_window_days = 0 (zero)",
        {"renewal_window_days": 0},
        validate_purchaser_config,
        "must be greater than 0"
    ))

    # Test 25: Invalid renewal_window_days (float)
    results.append(test_validation(
        "Purchaser: renewal_window_days = 3.14 (float)",
        {"renewal_window_days": 3.14},
        validate_purchaser_config,
        "must be an integer"
    ))

    # Test 26: Invalid tags (string instead of dict)
    results.append(test_validation(
        "Purchaser: tags = 'tag-value' (string)",
        {"tags": "tag-value"},
        validate_purchaser_config,
        "must be a dictionary"
    ))

    # Test 27: Invalid queue_url (empty)
    results.append(test_validation(
        "Purchaser: queue_url = '   ' (whitespace)",
        {"queue_url": "   "},
        validate_purchaser_config,
        "must be a non-empty string"
    ))

    # Test 28: Invalid management_account_role_arn (None)
    results.append(test_validation(
        "Purchaser: management_account_role_arn = None",
        {"management_account_role_arn": None},
        validate_purchaser_config,
        "must be a non-empty string"
    ))

    print()

    # ========================================================================
    # SUMMARY
    # ========================================================================
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    total = len(results)
    passed = sum(results)
    failed = total - passed

    print(f"Total Tests: {total}")
    print(f"Passed:      {passed}")
    print(f"Failed:      {failed}")
    print()

    if failed == 0:
        print("✅ All manual validation tests PASSED!")
        print()
        print("VERIFICATION RESULTS:")
        print("- All invalid configurations were properly caught by validation")
        print("- All error messages are descriptive and actionable")
        print("- Validation prevents invalid configs from reaching execution")
        return 0
    else:
        print(f"❌ {failed} manual validation tests FAILED!")
        return 1


if __name__ == "__main__":
    sys.exit(main())

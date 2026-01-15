# AWS Savings Plans Automation Module
# Variable Validation Tests - Testing all validation rules and edge cases

# ============================================================================
# Mock Provider Configuration
# ============================================================================

mock_provider "aws" {
  mock_data "aws_caller_identity" {
    defaults = {
      account_id = "123456789012"
      arn        = "arn:aws:iam::123456789012:user/test"
      user_id    = "AIDAEXAMPLE"
    }
  }

  mock_data "aws_region" {
    defaults = {
      name = "us-east-1"
    }
  }
}

# ============================================================================
# 7.2 Coverage Strategy - Variable Validations
# ============================================================================

# Test: coverage_target_percent - valid minimum value (1)
run "test_coverage_target_percent_valid_min" {
  command = plan

  variables {
    coverage_target_percent = 1
    max_coverage_cap       = 2
  }
}

# Test: coverage_target_percent - valid maximum value (100)
run "test_coverage_target_percent_valid_max" {
  command = plan

  variables {
    coverage_target_percent = 100
    max_coverage_cap       = 100
  }
}

# Test: coverage_target_percent - invalid value below minimum
run "test_coverage_target_percent_invalid_below_min" {
  command = plan

  variables {
    coverage_target_percent = 0
  }

  expect_failures = [
    var.coverage_target_percent,
  ]
}

# Test: coverage_target_percent - invalid value above maximum
run "test_coverage_target_percent_invalid_above_max" {
  command = plan

  variables {
    coverage_target_percent = 101
  }

  expect_failures = [
    var.coverage_target_percent,
  ]
}

# Test: coverage_target_percent - invalid negative value
run "test_coverage_target_percent_invalid_negative" {
  command = plan

  variables {
    coverage_target_percent = -10
  }

  expect_failures = [
    var.coverage_target_percent,
  ]
}

# Test: max_coverage_cap - valid at boundary (100)
run "test_max_coverage_cap_valid_at_100" {
  command = plan

  variables {
    coverage_target_percent = 90
    max_coverage_cap       = 100
  }
}

# Test: max_coverage_cap - invalid above 100
run "test_max_coverage_cap_invalid_above_100" {
  command = plan

  variables {
    coverage_target_percent = 90
    max_coverage_cap       = 101
  }

  expect_failures = [
    var.max_coverage_cap,
  ]
}

# Test: max_coverage_cap - invalid when less than coverage_target_percent
run "test_max_coverage_cap_invalid_less_than_target" {
  command = plan

  variables {
    coverage_target_percent = 90
    max_coverage_cap       = 85
  }

  expect_failures = [
    terraform_data.validate_max_coverage_cap,
  ]
}

# ============================================================================
# 7.3 Risk Management - Variable Validations
# ============================================================================

# Test: min_commitment_per_plan - valid at AWS minimum (0.001)
run "test_min_commitment_per_plan_valid_at_aws_min" {
  command = plan

  variables {
    min_commitment_per_plan = 0.001
  }
}

# Test: min_commitment_per_plan - valid above AWS minimum
run "test_min_commitment_per_plan_valid_above_min" {
  command = plan

  variables {
    min_commitment_per_plan = 1.5
  }
}

# Test: min_commitment_per_plan - invalid below AWS minimum
run "test_min_commitment_per_plan_invalid_below_min" {
  command = plan

  variables {
    min_commitment_per_plan = 0.0009
  }

  expect_failures = [
    var.min_commitment_per_plan,
  ]
}

# Test: min_commitment_per_plan - invalid at zero
run "test_min_commitment_per_plan_invalid_zero" {
  command = plan

  variables {
    min_commitment_per_plan = 0
  }

  expect_failures = [
    var.min_commitment_per_plan,
  ]
}

# Test: min_commitment_per_plan - invalid negative
run "test_min_commitment_per_plan_invalid_negative" {
  command = plan

  variables {
    min_commitment_per_plan = -0.001
  }

  expect_failures = [
    var.min_commitment_per_plan,
  ]
}

# ============================================================================
# 7.5 Compute SP Options - Variable Validations
# ============================================================================

# Test: compute_sp_term_mix - valid equal split
run "test_compute_sp_term_mix_valid_equal_split" {
  command = plan

  variables {
    compute_sp_term_mix = {
      three_year = 0.5
      one_year   = 0.5
    }
  }
}

# Test: compute_sp_term_mix - valid all three-year
run "test_compute_sp_term_mix_valid_all_three_year" {
  command = plan

  variables {
    compute_sp_term_mix = {
      three_year = 1.0
      one_year   = 0.0
    }
  }
}

# Test: compute_sp_term_mix - valid all one-year
run "test_compute_sp_term_mix_valid_all_one_year" {
  command = plan

  variables {
    compute_sp_term_mix = {
      three_year = 0.0
      one_year   = 1.0
    }
  }
}

# Test: compute_sp_term_mix - invalid sum less than 1
run "test_compute_sp_term_mix_invalid_sum_less_than_1" {
  command = plan

  variables {
    compute_sp_term_mix = {
      three_year = 0.4
      one_year   = 0.4
    }
  }

  expect_failures = [
    var.compute_sp_term_mix,
  ]
}

# Test: compute_sp_term_mix - invalid sum greater than 1
run "test_compute_sp_term_mix_invalid_sum_greater_than_1" {
  command = plan

  variables {
    compute_sp_term_mix = {
      three_year = 0.6
      one_year   = 0.6
    }
  }

  expect_failures = [
    var.compute_sp_term_mix,
  ]
}

# Test: compute_sp_term_mix - invalid negative three_year
run "test_compute_sp_term_mix_invalid_negative_three_year" {
  command = plan

  variables {
    compute_sp_term_mix = {
      three_year = -0.5
      one_year   = 1.5
    }
  }

  expect_failures = [
    var.compute_sp_term_mix,
  ]
}

# Test: compute_sp_term_mix - invalid negative one_year
run "test_compute_sp_term_mix_invalid_negative_one_year" {
  command = plan

  variables {
    compute_sp_term_mix = {
      three_year = 1.5
      one_year   = -0.5
    }
  }

  expect_failures = [
    var.compute_sp_term_mix,
  ]
}

# Test: compute_sp_payment_option - valid ALL_UPFRONT
run "test_compute_sp_payment_option_valid_all_upfront" {
  command = plan

  variables {
    compute_sp_payment_option = "ALL_UPFRONT"
  }
}

# Test: compute_sp_payment_option - valid PARTIAL_UPFRONT
run "test_compute_sp_payment_option_valid_partial_upfront" {
  command = plan

  variables {
    compute_sp_payment_option = "PARTIAL_UPFRONT"
  }
}

# Test: compute_sp_payment_option - valid NO_UPFRONT
run "test_compute_sp_payment_option_valid_no_upfront" {
  command = plan

  variables {
    compute_sp_payment_option = "NO_UPFRONT"
  }
}

# Test: compute_sp_payment_option - invalid value
run "test_compute_sp_payment_option_invalid" {
  command = plan

  variables {
    compute_sp_payment_option = "INVALID_OPTION"
  }

  expect_failures = [
    var.compute_sp_payment_option,
  ]
}

# Test: compute_sp_payment_option - invalid lowercase
run "test_compute_sp_payment_option_invalid_lowercase" {
  command = plan

  variables {
    compute_sp_payment_option = "all_upfront"
  }

  expect_failures = [
    var.compute_sp_payment_option,
  ]
}

# ============================================================================
# 7.5.1 Database SP Options - Variable Validations
# ============================================================================

# Test: database_sp_term - valid ONE_YEAR
run "test_database_sp_term_valid" {
  command = plan

  variables {
    database_sp_term = "ONE_YEAR"
  }
}

# Test: database_sp_term - invalid THREE_YEAR
run "test_database_sp_term_invalid_three_year" {
  command = plan

  variables {
    database_sp_term = "THREE_YEAR"
  }

  expect_failures = [
    var.database_sp_term,
  ]
}

# Test: database_sp_term - invalid empty string
run "test_database_sp_term_invalid_empty" {
  command = plan

  variables {
    database_sp_term = ""
  }

  expect_failures = [
    var.database_sp_term,
  ]
}

# Test: database_sp_payment_option - valid NO_UPFRONT
run "test_database_sp_payment_option_valid" {
  command = plan

  variables {
    database_sp_payment_option = "NO_UPFRONT"
  }
}

# Test: database_sp_payment_option - invalid ALL_UPFRONT
run "test_database_sp_payment_option_invalid_all_upfront" {
  command = plan

  variables {
    database_sp_payment_option = "ALL_UPFRONT"
  }

  expect_failures = [
    var.database_sp_payment_option,
  ]
}

# Test: database_sp_payment_option - invalid PARTIAL_UPFRONT
run "test_database_sp_payment_option_invalid_partial_upfront" {
  command = plan

  variables {
    database_sp_payment_option = "PARTIAL_UPFRONT"
  }

  expect_failures = [
    var.database_sp_payment_option,
  ]
}

# ============================================================================
# 7.5.2 SageMaker SP Options - Variable Validations
# ============================================================================

# Test: sagemaker_sp_term_mix - valid equal split
run "test_sagemaker_sp_term_mix_valid_equal_split" {
  command = plan

  variables {
    sagemaker_sp_term_mix = {
      three_year = 0.5
      one_year   = 0.5
    }
  }
}

# Test: sagemaker_sp_term_mix - valid all three-year
run "test_sagemaker_sp_term_mix_valid_all_three_year" {
  command = plan

  variables {
    sagemaker_sp_term_mix = {
      three_year = 1.0
      one_year   = 0.0
    }
  }
}

# Test: sagemaker_sp_term_mix - valid all one-year
run "test_sagemaker_sp_term_mix_valid_all_one_year" {
  command = plan

  variables {
    sagemaker_sp_term_mix = {
      three_year = 0.0
      one_year   = 1.0
    }
  }
}

# Test: sagemaker_sp_term_mix - invalid sum less than 1
run "test_sagemaker_sp_term_mix_invalid_sum_less_than_1" {
  command = plan

  variables {
    sagemaker_sp_term_mix = {
      three_year = 0.3
      one_year   = 0.3
    }
  }

  expect_failures = [
    var.sagemaker_sp_term_mix,
  ]
}

# Test: sagemaker_sp_term_mix - invalid sum greater than 1
run "test_sagemaker_sp_term_mix_invalid_sum_greater_than_1" {
  command = plan

  variables {
    sagemaker_sp_term_mix = {
      three_year = 0.7
      one_year   = 0.7
    }
  }

  expect_failures = [
    var.sagemaker_sp_term_mix,
  ]
}

# Test: sagemaker_sp_term_mix - invalid negative three_year
run "test_sagemaker_sp_term_mix_invalid_negative_three_year" {
  command = plan

  variables {
    sagemaker_sp_term_mix = {
      three_year = -0.3
      one_year   = 1.3
    }
  }

  expect_failures = [
    var.sagemaker_sp_term_mix,
  ]
}

# Test: sagemaker_sp_term_mix - invalid negative one_year
run "test_sagemaker_sp_term_mix_invalid_negative_one_year" {
  command = plan

  variables {
    sagemaker_sp_term_mix = {
      three_year = 1.3
      one_year   = -0.3
    }
  }

  expect_failures = [
    var.sagemaker_sp_term_mix,
  ]
}

# Test: sagemaker_sp_payment_option - valid ALL_UPFRONT
run "test_sagemaker_sp_payment_option_valid_all_upfront" {
  command = plan

  variables {
    sagemaker_sp_payment_option = "ALL_UPFRONT"
  }
}

# Test: sagemaker_sp_payment_option - valid PARTIAL_UPFRONT
run "test_sagemaker_sp_payment_option_valid_partial_upfront" {
  command = plan

  variables {
    sagemaker_sp_payment_option = "PARTIAL_UPFRONT"
  }
}

# Test: sagemaker_sp_payment_option - valid NO_UPFRONT
run "test_sagemaker_sp_payment_option_valid_no_upfront" {
  command = plan

  variables {
    sagemaker_sp_payment_option = "NO_UPFRONT"
  }
}

# Test: sagemaker_sp_payment_option - invalid value
run "test_sagemaker_sp_payment_option_invalid" {
  command = plan

  variables {
    sagemaker_sp_payment_option = "INVALID_OPTION"
  }

  expect_failures = [
    var.sagemaker_sp_payment_option,
  ]
}

# ============================================================================
# 7.12 Report Configuration - Variable Validations
# ============================================================================

# Test: report_retention_days - valid minimum value (1)
run "test_report_retention_days_valid_min" {
  command = plan

  variables {
    report_retention_days = 1
  }
}

# Test: report_retention_days - valid large value
run "test_report_retention_days_valid_large" {
  command = plan

  variables {
    report_retention_days = 3650
  }
}

# Test: report_retention_days - invalid zero
run "test_report_retention_days_invalid_zero" {
  command = plan

  variables {
    report_retention_days = 0
  }

  expect_failures = [
    var.report_retention_days,
  ]
}

# Test: report_retention_days - invalid negative
run "test_report_retention_days_invalid_negative" {
  command = plan

  variables {
    report_retention_days = -30
  }

  expect_failures = [
    var.report_retention_days,
  ]
}

# Test: s3_lifecycle_transition_ia_days - valid minimum value (1)
run "test_s3_lifecycle_transition_ia_days_valid_min" {
  command = plan

  variables {
    s3_lifecycle_transition_ia_days      = 1
    s3_lifecycle_transition_glacier_days = 2
  }
}

# Test: s3_lifecycle_transition_ia_days - valid typical value
run "test_s3_lifecycle_transition_ia_days_valid_typical" {
  command = plan

  variables {
    s3_lifecycle_transition_ia_days      = 90
    s3_lifecycle_transition_glacier_days = 180
  }
}

# Test: s3_lifecycle_transition_ia_days - invalid zero
run "test_s3_lifecycle_transition_ia_days_invalid_zero" {
  command = plan

  variables {
    s3_lifecycle_transition_ia_days = 0
  }

  expect_failures = [
    var.s3_lifecycle_transition_ia_days,
  ]
}

# Test: s3_lifecycle_transition_ia_days - invalid negative
run "test_s3_lifecycle_transition_ia_days_invalid_negative" {
  command = plan

  variables {
    s3_lifecycle_transition_ia_days = -10
  }

  expect_failures = [
    var.s3_lifecycle_transition_ia_days,
  ]
}

# Test: s3_lifecycle_transition_glacier_days - valid minimum value (1)
run "test_s3_lifecycle_transition_glacier_days_valid_min" {
  command = plan

  variables {
    s3_lifecycle_transition_ia_days      = 1
    s3_lifecycle_transition_glacier_days = 2
  }
}

# Test: s3_lifecycle_transition_glacier_days - invalid zero
run "test_s3_lifecycle_transition_glacier_days_invalid_zero" {
  command = plan

  variables {
    s3_lifecycle_transition_glacier_days = 0
  }

  expect_failures = [
    var.s3_lifecycle_transition_glacier_days,
  ]
}

# Test: s3_lifecycle_transition_glacier_days - invalid equal to IA days
run "test_s3_lifecycle_transition_glacier_days_invalid_equal_to_ia" {
  command = plan

  variables {
    s3_lifecycle_transition_ia_days      = 90
    s3_lifecycle_transition_glacier_days = 90
  }

  expect_failures = [
    terraform_data.validate_s3_lifecycle_glacier_days,
  ]
}

# Test: s3_lifecycle_transition_glacier_days - invalid less than IA days
run "test_s3_lifecycle_transition_glacier_days_invalid_less_than_ia" {
  command = plan

  variables {
    s3_lifecycle_transition_ia_days      = 90
    s3_lifecycle_transition_glacier_days = 60
  }

  expect_failures = [
    terraform_data.validate_s3_lifecycle_glacier_days,
  ]
}

# Test: s3_lifecycle_expiration_days - valid minimum value (1)
run "test_s3_lifecycle_expiration_days_valid_min" {
  command = plan

  variables {
    s3_lifecycle_transition_ia_days      = 1
    s3_lifecycle_transition_glacier_days = 2
    s3_lifecycle_expiration_days         = 2
  }
}

# Test: s3_lifecycle_expiration_days - valid equal to glacier days
run "test_s3_lifecycle_expiration_days_valid_equal_to_glacier" {
  command = plan

  variables {
    s3_lifecycle_transition_ia_days      = 90
    s3_lifecycle_transition_glacier_days = 180
    s3_lifecycle_expiration_days         = 180
  }
}

# Test: s3_lifecycle_expiration_days - valid greater than glacier days
run "test_s3_lifecycle_expiration_days_valid_greater_than_glacier" {
  command = plan

  variables {
    s3_lifecycle_transition_ia_days      = 90
    s3_lifecycle_transition_glacier_days = 180
    s3_lifecycle_expiration_days         = 365
  }
}

# Test: s3_lifecycle_expiration_days - invalid zero
run "test_s3_lifecycle_expiration_days_invalid_zero" {
  command = plan

  variables {
    s3_lifecycle_expiration_days = 0
  }

  expect_failures = [
    var.s3_lifecycle_expiration_days,
  ]
}

# Test: s3_lifecycle_expiration_days - invalid less than glacier days
run "test_s3_lifecycle_expiration_days_invalid_less_than_glacier" {
  command = plan

  variables {
    s3_lifecycle_transition_ia_days      = 90
    s3_lifecycle_transition_glacier_days = 180
    s3_lifecycle_expiration_days         = 150
  }

  expect_failures = [
    terraform_data.validate_s3_lifecycle_expiration_days,
  ]
}

# Test: s3_lifecycle_noncurrent_expiration_days - valid minimum value (1)
run "test_s3_lifecycle_noncurrent_expiration_days_valid_min" {
  command = plan

  variables {
    s3_lifecycle_noncurrent_expiration_days = 1
  }
}

# Test: s3_lifecycle_noncurrent_expiration_days - valid typical value
run "test_s3_lifecycle_noncurrent_expiration_days_valid_typical" {
  command = plan

  variables {
    s3_lifecycle_noncurrent_expiration_days = 90
  }
}

# Test: s3_lifecycle_noncurrent_expiration_days - invalid zero
run "test_s3_lifecycle_noncurrent_expiration_days_invalid_zero" {
  command = plan

  variables {
    s3_lifecycle_noncurrent_expiration_days = 0
  }

  expect_failures = [
    var.s3_lifecycle_noncurrent_expiration_days,
  ]
}

# Test: s3_lifecycle_noncurrent_expiration_days - invalid negative
run "test_s3_lifecycle_noncurrent_expiration_days_invalid_negative" {
  command = plan

  variables {
    s3_lifecycle_noncurrent_expiration_days = -30
  }

  expect_failures = [
    var.s3_lifecycle_noncurrent_expiration_days,
  ]
}

# Test: report_format - valid html
run "test_report_format_valid_html" {
  command = plan

  variables {
    report_format = "html"
  }
}

# Test: report_format - valid pdf
run "test_report_format_valid_pdf" {
  command = plan

  variables {
    report_format = "pdf"
  }
}

# Test: report_format - valid json
run "test_report_format_valid_json" {
  command = plan

  variables {
    report_format = "json"
  }
}

# Test: report_format - invalid value
run "test_report_format_invalid" {
  command = plan

  variables {
    report_format = "xml"
  }

  expect_failures = [
    var.report_format,
  ]
}

# Test: report_format - invalid uppercase
run "test_report_format_invalid_uppercase" {
  command = plan

  variables {
    report_format = "HTML"
  }

  expect_failures = [
    var.report_format,
  ]
}

# ============================================================================
# Edge Cases - Complex Validation Scenarios
# ============================================================================

# Test: All lifecycle days at minimum boundaries
run "test_lifecycle_days_all_min_boundaries" {
  command = plan

  variables {
    s3_lifecycle_transition_ia_days         = 1
    s3_lifecycle_transition_glacier_days    = 2
    s3_lifecycle_expiration_days            = 2
    s3_lifecycle_noncurrent_expiration_days = 1
  }
}

# Test: Complex valid configuration with all custom values
run "test_complex_valid_configuration" {
  command = plan

  variables {
    coverage_target_percent             = 85
    max_coverage_cap                   = 95
    min_commitment_per_plan            = 0.01
    compute_sp_term_mix = {
      three_year = 0.75
      one_year   = 0.25
    }
    compute_sp_payment_option          = "PARTIAL_UPFRONT"
    sagemaker_sp_term_mix = {
      three_year = 0.8
      one_year   = 0.2
    }
    sagemaker_sp_payment_option        = "NO_UPFRONT"
    report_retention_days              = 730
    s3_lifecycle_transition_ia_days    = 30
    s3_lifecycle_transition_glacier_days = 90
    s3_lifecycle_expiration_days       = 730
    s3_lifecycle_noncurrent_expiration_days = 30
    report_format                      = "pdf"
  }
}

# Test: Term mix with very small but valid values (close to 0)
run "test_term_mix_small_valid_values" {
  command = plan

  variables {
    compute_sp_term_mix = {
      three_year = 0.0001
      one_year   = 0.9999
    }
  }
}

# Test: Multiple validation failures simultaneously
run "test_multiple_validation_failures" {
  command = plan

  variables {
    coverage_target_percent = 101
    max_coverage_cap       = 50
    min_commitment_per_plan = 0.0005
  }

  expect_failures = [
    var.coverage_target_percent,
    terraform_data.validate_max_coverage_cap,
    var.min_commitment_per_plan,
  ]
}

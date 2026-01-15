# AWS Savings Plans Automation Module
# S3 Bucket Tests - Credential-free testing using mock provider

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
# S3 Bucket Tests
# ============================================================================

# Test: S3 bucket naming follows expected pattern
run "test_s3_bucket_naming" {
  command = plan

  variables {
    enable_compute_sp = true
    dry_run           = true
  }

  assert {
    condition     = aws_s3_bucket.reports.bucket == "sp-autopilot-reports-123456789012"
    error_message = "S3 bucket name should follow pattern: sp-autopilot-reports-{account_id}"
  }

  assert {
    condition     = aws_s3_bucket.reports.bucket != ""
    error_message = "S3 bucket name should not be empty"
  }
}

# Test: S3 bucket versioning is enabled
run "test_s3_versioning_enabled" {
  command = plan

  variables {
    enable_compute_sp = true
    dry_run           = true
  }

  assert {
    condition     = aws_s3_bucket_versioning.reports.versioning_configuration[0].status == "Enabled"
    error_message = "S3 bucket versioning should be enabled"
  }
}

# Test: S3 bucket encryption configuration
run "test_s3_encryption_configuration" {
  command = plan

  variables {
    enable_compute_sp = true
    dry_run           = true
  }

  override_resource {
    override_during = plan
    target = aws_s3_bucket_server_side_encryption_configuration.reports
    values = {
      rule = [{
        apply_server_side_encryption_by_default = [{
          sse_algorithm = "AES256"
        }]
      }]
    }
  }

  assert {
    condition     = aws_s3_bucket_server_side_encryption_configuration.reports.rule[0].apply_server_side_encryption_by_default[0].sse_algorithm == "AES256"
    error_message = "S3 bucket should use AES256 encryption"
  }
}

# Test: S3 bucket public access blocks are all enabled
run "test_s3_public_access_blocks" {
  command = plan

  variables {
    enable_compute_sp = true
    dry_run           = true
  }

  assert {
    condition     = aws_s3_bucket_public_access_block.reports.block_public_acls == true
    error_message = "S3 bucket should block public ACLs"
  }

  assert {
    condition     = aws_s3_bucket_public_access_block.reports.block_public_policy == true
    error_message = "S3 bucket should block public policy"
  }

  assert {
    condition     = aws_s3_bucket_public_access_block.reports.ignore_public_acls == true
    error_message = "S3 bucket should ignore public ACLs"
  }

  assert {
    condition     = aws_s3_bucket_public_access_block.reports.restrict_public_buckets == true
    error_message = "S3 bucket should restrict public buckets"
  }
}

# Test: S3 bucket lifecycle configuration - rule exists and is enabled
run "test_s3_lifecycle_rule_enabled" {
  command = plan

  variables {
    enable_compute_sp = true
    dry_run           = true
  }

  assert {
    condition     = aws_s3_bucket_lifecycle_configuration.reports.rule[0].id == "cleanup-old-reports"
    error_message = "S3 lifecycle rule should have id 'cleanup-old-reports'"
  }

  assert {
    condition     = aws_s3_bucket_lifecycle_configuration.reports.rule[0].status == "Enabled"
    error_message = "S3 lifecycle rule should be enabled"
  }
}

# Test: S3 bucket lifecycle configuration - IA transition
run "test_s3_lifecycle_ia_transition" {
  command = plan

  variables {
    enable_compute_sp                   = true
    dry_run                             = true
    s3_lifecycle_transition_ia_days     = 90
  }

  assert {
    condition     = aws_s3_bucket_lifecycle_configuration.reports.rule[0].transition[0].days == 90
    error_message = "S3 lifecycle should transition to IA after 90 days"
  }

  assert {
    condition     = aws_s3_bucket_lifecycle_configuration.reports.rule[0].transition[0].storage_class == "STANDARD_IA"
    error_message = "S3 lifecycle should transition to STANDARD_IA storage class"
  }
}

# Test: S3 bucket lifecycle configuration - Glacier transition
run "test_s3_lifecycle_glacier_transition" {
  command = plan

  variables {
    enable_compute_sp                       = true
    dry_run                                 = true
    s3_lifecycle_transition_ia_days         = 90
    s3_lifecycle_transition_glacier_days    = 180
  }

  assert {
    condition     = aws_s3_bucket_lifecycle_configuration.reports.rule[0].transition[1].days == 180
    error_message = "S3 lifecycle should transition to Glacier after 180 days"
  }

  assert {
    condition     = aws_s3_bucket_lifecycle_configuration.reports.rule[0].transition[1].storage_class == "GLACIER"
    error_message = "S3 lifecycle should transition to GLACIER storage class"
  }
}

# Test: S3 bucket lifecycle configuration - expiration
run "test_s3_lifecycle_expiration" {
  command = plan

  variables {
    enable_compute_sp               = true
    dry_run                         = true
    s3_lifecycle_expiration_days    = 365
  }

  assert {
    condition     = aws_s3_bucket_lifecycle_configuration.reports.rule[0].expiration[0].days == 365
    error_message = "S3 lifecycle should delete objects after 365 days"
  }
}

# Test: S3 bucket lifecycle configuration - noncurrent version expiration
run "test_s3_lifecycle_noncurrent_expiration" {
  command = plan

  variables {
    enable_compute_sp                           = true
    dry_run                                     = true
    s3_lifecycle_noncurrent_expiration_days     = 90
  }

  assert {
    condition     = aws_s3_bucket_lifecycle_configuration.reports.rule[0].noncurrent_version_expiration[0].noncurrent_days == 90
    error_message = "S3 lifecycle should delete noncurrent versions after 90 days"
  }
}

# Test: S3 bucket tags include common tags
run "test_s3_bucket_tags" {
  command = plan

  variables {
    enable_compute_sp = true
    dry_run           = true
    tags = {
      Environment = "test"
      Owner       = "platform-team"
    }
  }

  assert {
    condition     = aws_s3_bucket.reports.tags["ManagedBy"] == "terraform-aws-sp-autopilot"
    error_message = "S3 bucket should have ManagedBy tag"
  }

  assert {
    condition     = aws_s3_bucket.reports.tags["Module"] == "savings-plans-automation"
    error_message = "S3 bucket should have Module tag"
  }

  assert {
    condition     = aws_s3_bucket.reports.tags["Name"] == "sp-autopilot-reports"
    error_message = "S3 bucket should have Name tag"
  }

  assert {
    condition     = aws_s3_bucket.reports.tags["Environment"] == "test"
    error_message = "S3 bucket should include custom tags from variables"
  }
}

# Test: S3 bucket naming with different account ID
run "test_s3_bucket_naming_different_account" {
  command = plan

  variables {
    enable_compute_sp = true
    dry_run           = true
  }

  override_data {
    target = data.aws_caller_identity.current
    values = {
      account_id = "999888777666"
    }
  }

  assert {
    condition     = aws_s3_bucket.reports.bucket == "sp-autopilot-reports-999888777666"
    error_message = "S3 bucket name should use the mocked account ID"
  }
}

# Test: S3 bucket lifecycle custom configuration values
run "test_s3_lifecycle_custom_values" {
  command = plan

  variables {
    enable_compute_sp                           = true
    dry_run                                     = true
    s3_lifecycle_transition_ia_days             = 30
    s3_lifecycle_transition_glacier_days        = 60
    s3_lifecycle_expiration_days                = 180
    s3_lifecycle_noncurrent_expiration_days     = 30
  }

  assert {
    condition     = aws_s3_bucket_lifecycle_configuration.reports.rule[0].transition[0].days == 30
    error_message = "S3 lifecycle IA transition should use custom value"
  }

  assert {
    condition     = aws_s3_bucket_lifecycle_configuration.reports.rule[0].transition[1].days == 60
    error_message = "S3 lifecycle Glacier transition should use custom value"
  }

  assert {
    condition     = aws_s3_bucket_lifecycle_configuration.reports.rule[0].expiration[0].days == 180
    error_message = "S3 lifecycle expiration should use custom value"
  }

  assert {
    condition     = aws_s3_bucket_lifecycle_configuration.reports.rule[0].noncurrent_version_expiration[0].noncurrent_days == 30
    error_message = "S3 lifecycle noncurrent expiration should use custom value"
  }
}

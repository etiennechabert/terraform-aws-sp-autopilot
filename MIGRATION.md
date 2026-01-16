# Migration Guide: v1.x to v2.0

This guide helps you migrate from the flat variable structure (v1.x) to the new nested variable structure (v2.0).

## Overview of Changes

Version 2.0 introduces a **major refactoring** of the module's variable interface:
- **From**: 40+ flat variables
- **To**: 10 logical, nested variable objects

This makes the module more intuitive, self-documenting, and easier to use.

## Benefits of the New Structure

- **Intuitive grouping**: Related settings are organized together
- **Self-documenting**: Structure tells you what belongs together
- **Flexible**: Easy to add new options without cluttering the interface
- **Type-safe**: Nested objects catch configuration errors earlier
- **Less verbose**: Optional fields with sensible defaults
- **Better UX**: Can disable individual Lambda functions for extended dry-run testing

## Breaking Changes

All variable names have changed. You **must** update your module block.

## Migration Steps

### Step 1: Update Module Version

```hcl
module "savings_plans" {
  source  = "etiennechabert/sp-autopilot/aws"
  version = "~> 2.0"  # Update from "~> 1.0"

  # ... your variables
}
```

### Step 2: Restructure Variables

Use the mapping table below to convert your v1.x variables to v2.0 format.

## Complete Variable Mapping

### Lambda Configuration

**v1.x:**
```hcl
lambda_scheduler_memory_size = 256
lambda_scheduler_timeout     = 300
lambda_purchaser_memory_size = 256
lambda_purchaser_timeout     = 300
lambda_reporter_memory_size  = 256
lambda_reporter_timeout      = 300
```

**v2.0:**
```hcl
lambda_config = {
  scheduler = {
    enabled   = true  # NEW: Can disable for testing
    memory_mb = 256
    timeout   = 300
  }
  purchaser = {
    enabled   = true  # NEW: Can disable for extended dry-run
    memory_mb = 256
    timeout   = 300
  }
  reporter = {
    enabled   = true  # NEW: Can disable if not needed
    memory_mb = 256
    timeout   = 300
  }
}
```

### Purchase Strategy

**v1.x:**
```hcl
coverage_target_percent = 90
max_coverage_cap        = 95
max_purchase_percent    = 10
lookback_days           = 30
min_data_days           = 14
renewal_window_days     = 7
min_commitment_per_plan = 0.001
```

**v2.0:**
```hcl
purchase_strategy = {
  coverage_target_percent = 90
  max_coverage_cap        = 95
  lookback_days           = 30
  min_data_days           = 14
  renewal_window_days     = 7
  min_commitment_per_plan = 0.001

  simple = {
    max_purchase_percent = 10
  }

  # Future: dichotomy strategy for adaptive purchasing
  # dichotomy = {
  #   max_purchase_percent = 15
  #   min_purchase_percent = 5
  # }
}
```

### Savings Plans Configuration

**v1.x:**
```hcl
enable_compute_sp  = true
enable_database_sp = false
enable_sagemaker_sp = false

compute_sp_term_mix = {
  three_year = 0.67
  one_year   = 0.33
}
compute_sp_payment_option = "ALL_UPFRONT"
partial_upfront_percent = 50

sagemaker_sp_term_mix = {
  three_year = 0.7
  one_year   = 0.3
}
sagemaker_sp_payment_option = "ALL_UPFRONT"

# Database SP fixed: ONE_YEAR, NO_UPFRONT only
```

**v2.0:**
```hcl
sp_plans = {
  compute = {
    enabled                = true
    all_upfront_three_year = 0.67  # 67% in 3-year all-upfront
    all_upfront_one_year   = 0.33  # 33% in 1-year all-upfront
    # Other options: partial_upfront_three_year, partial_upfront_one_year,
    #                no_upfront_three_year, no_upfront_one_year
    partial_upfront_percent = 50   # Only used if partial_upfront_* > 0
  }

  database = {
    enabled             = false
    no_upfront_one_year = 1  # AWS constraint: only 1-year NO_UPFRONT available
  }

  sagemaker = {
    enabled                = false
    all_upfront_three_year = 0.70
    all_upfront_one_year   = 0.30
    partial_upfront_percent = 50
  }
}
```

### Scheduling

**v1.x:**
```hcl
scheduler_schedule = "cron(0 8 1 * ? *)"
purchaser_schedule = "cron(0 8 4 * ? *)"
report_schedule    = "cron(0 9 1 * ? *)"
```

**v2.0:**
```hcl
scheduler = {
  scheduler = "cron(0 8 1 * ? *)"
  purchaser = "cron(0 8 4 * ? *)"
  reporter  = "cron(0 9 1 * ? *)"
  # NEW: Set to null to disable a schedule
}
```

### Notifications

**v1.x:**
```hcl
notification_emails = ["ops@example.com"]
slack_webhook_url   = "https://hooks.slack.com/..."
teams_webhook_url   = null
send_no_action_email = true
```

**v2.0:**
```hcl
notifications = {
  emails         = ["ops@example.com"]
  slack_webhook  = "https://hooks.slack.com/..."  # Optional
  teams_webhook  = null                            # Optional
  send_no_action = true
}
```

### Reporting

**v1.x:**
```hcl
enable_reports              = true
report_format               = "html"
email_reports               = false
report_retention_days       = 365
s3_lifecycle_transition_ia_days = 90
s3_lifecycle_transition_glacier_days = 180
s3_lifecycle_expiration_days = 365
s3_lifecycle_noncurrent_expiration_days = 90
```

**v2.0:**
```hcl
reporting = {
  enabled        = true
  format         = "html"
  email_reports  = false
  retention_days = 365

  s3_lifecycle = {
    transition_ia_days         = 90
    transition_glacier_days    = 180
    expiration_days            = 365
    noncurrent_expiration_days = 90
  }
}
```

### Monitoring

**v1.x:**
```hcl
enable_lambda_error_alarm = true
enable_dlq_alarm          = true
lambda_error_threshold    = 1
```

**v2.0:**
```hcl
monitoring = {
  lambda_error_alarm = true
  dlq_alarm          = true
  error_threshold    = 1
}
```

### Operations

**v1.x:**
```hcl
dry_run                     = true
enable_cost_forecasting     = true
management_account_role_arn = null
```

**v2.0:**
```hcl
operations = {
  dry_run                     = true
  enable_cost_forecasting     = true
  management_account_role_arn = null  # Optional
}
```

### Tags & Security

**v1.x:**
```hcl
tags = {
  Environment = "production"
}

enable_sns_kms_encryption = false
```

**v2.0:**
```hcl
tags = {
  Environment = "production"
}

enable_sns_kms_encryption = false  # Remains top-level
```

## Complete Migration Example

### Before (v1.x)

```hcl
module "savings_plans" {
  source  = "etiennechabert/sp-autopilot/aws"
  version = "~> 1.0"

  enable_compute_sp  = true
  enable_database_sp = false

  coverage_target_percent = 80
  max_coverage_cap        = 90
  max_purchase_percent    = 5
  lookback_days           = 30
  min_data_days           = 14

  compute_sp_term_mix = {
    three_year = 0.70
    one_year   = 0.30
  }
  compute_sp_payment_option = "ALL_UPFRONT"

  scheduler_schedule = "cron(0 8 1 * ? *)"
  purchaser_schedule = "cron(0 8 4 * ? *)"

  notification_emails = ["ops@example.com"]
  dry_run            = true

  tags = {
    Environment = "production"
  }
}
```

### After (v2.0)

```hcl
module "savings_plans" {
  source  = "etiennechabert/sp-autopilot/aws"
  version = "~> 2.0"

  purchase_strategy = {
    coverage_target_percent = 80
    max_coverage_cap        = 90
    lookback_days           = 30
    min_data_days           = 14

    simple = {
      max_purchase_percent = 5
    }
  }

  sp_plans = {
    compute = {
      enabled                = true
      all_upfront_three_year = 0.70
      all_upfront_one_year   = 0.30
    }
    database = {
      enabled = false
    }
    sagemaker = {
      enabled = false
    }
  }

  scheduler = {
    scheduler = "cron(0 8 1 * ? *)"
    purchaser = "cron(0 8 4 * ? *)"
    reporter  = "cron(0 9 1 * ? *)"
  }

  notifications = {
    emails = ["ops@example.com"]
  }

  operations = {
    dry_run = true
  }

  tags = {
    Environment = "production"
  }
}
```

## New Features in v2.0

### 1. Individual Lambda Control

You can now disable individual Lambda functions:

```hcl
lambda_config = {
  scheduler = { enabled = true }
  purchaser = { enabled = false }  # Disable for extended dry-run testing
  reporter  = { enabled = true }
}
```

### 2. Disable Individual Schedules

Set schedules to `null` to disable them:

```hcl
scheduler = {
  scheduler = "cron(0 8 1 * ? *)"
  purchaser = null  # Disable automatic purchasing
  reporter  = "cron(0 9 1 * ? *)"
}
```

### 3. Mixed Payment Options (Future)

The new structure supports mixed payment options (currently picks dominant option):

```hcl
sp_plans = {
  compute = {
    enabled                = true
    all_upfront_three_year = 0.50
    partial_upfront_one_year = 0.50  # Mix payment types
  }
}
```

### 4. Clearer Validation

Variable validations now provide clearer error messages and catch misconfigurations earlier.

## Testing Your Migration

1. Update your Terraform code using the mapping above
2. Run `terraform plan` to see what will change
3. Review the plan carefully - infrastructure resources should not be recreated
4. Apply in a non-production environment first
5. Validate that Lambda functions still work correctly

## Getting Help

- Check the [examples/](./examples/) directory for complete working examples
- Review variable definitions in [variables.tf](./variables.tf)
- Open an issue on GitHub if you encounter problems

## Rollback

If you need to rollback to v1.x:

1. Revert your module version to `~> 1.0`
2. Restore your old variable structure
3. Run `terraform apply`

The module infrastructure is designed to be compatible across versions - only the variable interface changed.

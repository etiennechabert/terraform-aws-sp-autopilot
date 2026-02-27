# AWS Savings Plans Automation Module

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
![Terraform Version](https://img.shields.io/badge/Terraform-%3E%3D%201.7-623CE4.svg)
![AWS Provider Version](https://img.shields.io/badge/AWS%20Provider-%3E%3D%205.0-FF9900.svg)
![Python Runtime](https://img.shields.io/badge/Python-3.14-3776AB.svg)

[![Security Rating](https://sonarcloud.io/api/project_badges/measure?project=etiennechabert_terraform-aws-sp-autopilot&metric=security_rating)](https://sonarcloud.io/summary/new_code?id=etiennechabert_terraform-aws-sp-autopilot)
[![Reliability Rating](https://sonarcloud.io/api/project_badges/measure?project=etiennechabert_terraform-aws-sp-autopilot&metric=reliability_rating)](https://sonarcloud.io/summary/new_code?id=etiennechabert_terraform-aws-sp-autopilot)
[![Maintainability Rating](https://sonarcloud.io/api/project_badges/measure?project=etiennechabert_terraform-aws-sp-autopilot&metric=sqale_rating)](https://sonarcloud.io/summary/new_code?id=etiennechabert_terraform-aws-sp-autopilot)

[![PR Checks](https://github.com/etiennechabert/terraform-aws-sp-autopilot/actions/workflows/pr-checks.yml/badge.svg)](https://github.com/etiennechabert/terraform-aws-sp-autopilot/actions/workflows/pr-checks.yml)
[![codecov](https://codecov.io/gh/etiennechabert/terraform-aws-sp-autopilot/branch/main/graph/badge.svg)](https://codecov.io/gh/etiennechabert/terraform-aws-sp-autopilot)
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-support-yellow?logo=buymeacoffee&logoColor=white)](https://buymeacoffee.com/etiennechak)

Automates AWS Savings Plans purchases based on usage analysis, maintaining consistent coverage while limiting financial exposure through incremental commitments.

[**Try the interactive simulator**](https://etiennechabert.github.io/terraform-aws-sp-autopilot/) — Visualize strategies and find the optimal Savings Plan for your workload before deploying.

## Key Features

- **Automated Savings Plans purchasing** — Maintains target coverage without manual intervention
- **Three purchase strategies** — Fixed Step, Gap Split, and Follow-AWS for different workload patterns
- **Three SP types supported** — Compute, Database, and SageMaker independently tracked
- **Human review window** — Configurable delay between scheduling and purchasing allows cancellation
- **Risk management** — Spreads financial commitments over time with configurable purchase limits
- **Email & webhook notifications** — SNS, Slack, and Microsoft Teams integration

### Savings Plan Types

| Type | Coverage | Terms | Payment Options | Max Discount |
|------|----------|-------|-----------------|--------------|
| **Compute** | EC2, Lambda, Fargate | 1-year, 3-year | All/Partial/No Upfront | Up to 66% |
| **Database** | RDS, Aurora, DynamoDB, ElastiCache, DocumentDB, Neptune, Keyspaces, Timestream, DMS | 1-year only | No Upfront only | Up to 35% |
| **SageMaker** | Training, Inference, Notebooks | 1-year, 3-year | All/Partial/No Upfront | Up to 64% |

> **Database Savings Plans** have fixed AWS constraints: 1-year term, No Upfront payment only.

## Quick Start

```hcl
module "savings_plans" {
  source  = "etiennechabert/sp-autopilot/aws"
  version = "~> 1.0"

  purchase_strategy = {
    lookback_days    = 13       # Max for HOURLY granularity
    granularity      = "HOURLY" # Recommended (requires Cost Explorer hourly data)

    target = { fixed = { coverage_percent = 90 } }
    split  = { fixed_step = { step_percent = 10 } }
  }

  sp_plans = {
    compute   = { enabled = true, plan_type = "all_upfront_one_year" }
    database  = { enabled = false }
    sagemaker = { enabled = false }
  }

  cron_schedules = {
    scheduler = "cron(0 8 1 * ? *)"  # 1st of month at 8 AM UTC
    purchaser = "cron(0 8 4 * ? *)"  # 4th of month (3-day review window)
    reporter  = "cron(0 9 20 * ? *)" # 20th of month
  }

  notifications = {
    emails = ["devops@example.com"]
  }

  lambda_config = {
    scheduler = { dry_run = true } # Start in dry-run mode (recommended)
  }
}
```

### Examples

See the [`examples/`](examples/) directory for complete, working examples:

- **[single-account-compute](examples/single-account-compute/)** — Basic single-account Compute SP deployment
- **[organizations](examples/organizations/)** — AWS Organizations multi-account setup
- **[dynamic-strategy](examples/dynamic-strategy/)** — Dynamic target with gap split

## Interactive Simulator

The module includes an interactive **[Savings Plan Simulator](https://etiennechabert.github.io/terraform-aws-sp-autopilot/)** to visualize coverage strategies and their cost impact before deploying anything. Generated reports link to the simulator pre-loaded with your data, allowing stakeholders to explore "what-if" scenarios across different target/split combinations.

[![AWS Savings Plan Simulator](docs/images/simulator-preview.png)](https://etiennechabert.github.io/terraform-aws-sp-autopilot/)

## Configuration

### Purchase Strategies

Strategy is configured with two orthogonal dimensions: **target** (what coverage to aim for) and **split** (how to reach the target). Both must be specified.

#### Targets

- **`fixed`** — Target a fixed coverage percentage you define (`coverage_percent`).
- **`dynamic`** — Automatically determines the optimal coverage target based on usage patterns using a knee-point algorithm (`risk_level`: `prudent`, `min_hourly`, `optimal`, `maximum`).
- **`aws`** — Uses AWS Cost Explorer recommendations directly without modification.

#### Splits

- **`one_shot`** — Purchases the entire gap to the target in a single cycle.
- **`fixed_step`** — Purchases a fixed percentage of spend per cycle (`step_percent`).
- **`gap_split`** — Divides the remaining coverage gap by a configurable divider each cycle (`divider`), with optional `min_purchase_percent` and `max_purchase_percent` bounds.

#### Recommended Combinations

##### Dynamic Target + Gap Split (Recommended)

Automatically determines the optimal coverage target based on usage patterns, dividing the coverage gap by a configurable divider each cycle.

```hcl
purchase_strategy = {
  target = { dynamic = { risk_level = "min_hourly" } }
  split  = { gap_split = { divider = 2 } }
}
```

##### Fixed Target + Fixed Step Split

Target a fixed coverage percentage, purchasing a fixed step each cycle.

```hcl
purchase_strategy = {
  target = { fixed = { coverage_percent = 100 } }
  split  = { fixed_step = { step_percent = 10 } }
}
```

##### AWS Target + One Shot

Uses AWS Cost Explorer recommendations directly without modification.

```hcl
purchase_strategy = {
  target = { aws = {} }
  split  = { one_shot = {} }
}
```

**Use with caution:** AWS recommendations can be aggressive.

### Scheduling

```hcl
cron_schedules = {
  scheduler = "cron(0 8 1 * ? *)"   # When to analyze and schedule purchases
  purchaser = "cron(0 8 4 * ? *)"   # When to execute purchases
  reporter  = "cron(0 9 20 * ? *)"  # When to generate monthly reports
}
```

**Review Window:** Time between `scheduler` and `purchaser` runs allows canceling unwanted purchases.

### Notifications

#### Email

```hcl
notifications = {
  emails         = ["devops@example.com", "finops@example.com"]
  send_no_action = true # Get notified even when no purchases needed
}
```

#### Slack & Microsoft Teams

```hcl
notifications = {
  emails        = ["devops@example.com"]
  slack_webhook = var.slack_webhook_url  # Mark as sensitive
  teams_webhook = var.teams_webhook_url  # Mark as sensitive
}
```

### Data Granularity

#### HOURLY (Recommended)

Savings Plans are purchased as hourly commitments ($/hour). Analyzing data at hourly granularity provides accurate purchase sizing.

```hcl
purchase_strategy = {
  lookback_days = 14      # Max for HOURLY
  granularity   = "HOURLY" # Recommended
}
```

**Requirement:** Enable "Hourly and resource level granularity" in Cost Explorer settings. Cost: ~$0.10-$1.00/month.

#### DAILY (Compatibility)

Use only if hourly data isn't available. Supports up to 90 `lookback_days`. Less accurate analysis, potentially suboptimal purchases.

## Architecture

The module consists of three Lambda functions with SQS queue coordination:

![Architecture Diagram](docs/architecture.svg)

**Workflow:**

1. **Scheduler Lambda** (e.g., 1st of month)
   - Purges stale queue messages
   - Analyzes current coverage (separate for Compute/Database/SageMaker)
   - Gets AWS recommendations
   - Applies purchase strategy
   - Queues purchase intents to SQS (or emails only if `dry_run = true`)

2. **SQS Queue** (review window)
   - Holds purchase intents
   - Users can delete messages to cancel purchases
   - Messages include full details and idempotency tokens

3. **Purchaser Lambda** (e.g., 4th of month)
   - Processes queue messages
   - Executes purchases via AWS CreateSavingsPlan API
   - Sends email summary

4. **Reporter Lambda** (e.g., 20th of month)
   - Generates HTML spending reports
   - Stores in S3
   - Optionally emails stakeholders

## Advanced Topics

### AWS Organizations Setup

For AWS Organizations, Savings Plans must be purchased from the **management account**. Deploy this module in a secondary account and configure cross-account roles.

```hcl
lambda_config = {
  reporter  = { assume_role_arn = "arn:aws:iam::123456789012:role/SPReadOnlyRole" }
  scheduler = { assume_role_arn = "arn:aws:iam::123456789012:role/SPReadOnlyRole" }
  purchaser = { assume_role_arn = "arn:aws:iam::123456789012:role/SPPurchaserRole" }
}
```

**IAM Setup in Management Account:**

1. **Read-Only Role** (Scheduler + Reporter):
   - `ce:GetSavingsPlansPurchaseRecommendation`
   - `ce:GetSavingsPlansCoverage`
   - `savingsplans:DescribeSavingsPlans`

2. **Purchaser Role** (write access):
   - `savingsplans:CreateSavingsPlan`
   - `savingsplans:DescribeSavingsPlans`
   - `ce:GetSavingsPlansCoverage`

See [organizations example](examples/organizations/README.md) for complete setup.

### Recommended Rollout

Start with **1-year No Upfront** commitments to validate the automation with minimal risk. Once comfortable after the first year, switch to **3-year All Upfront** for maximum savings — expiring 1Y plans will naturally get replaced by 3Y over time.

| Phase | `plan_type` | `dry_run` | Purpose |
|-------|-------------|-----------|---------|
| **Week 1** | — | `true` | Review recommendations only |
| **Year 1** | `no_upfront_one_year` | `false` | Validate with low-risk commitments |
| **Year 2+** | `all_upfront_three_year` | `false` | Maximize savings as 1Y plans expire |

When switching to 3Y, consider slowing down purchases since each commitment lasts longer: increase the `divider` with gap_split (though it naturally purchases less as coverage grows, as long as `min_purchase_percent` isn't set too high), or reduce `step_percent` with fixed_step.

### Canceling Purchases

To cancel scheduled purchases before execution:

1. Navigate to AWS Console → SQS → `sp-autopilot-purchase-intents` queue
2. View messages in queue
3. Delete messages for unwanted purchases
4. Purchaser Lambda will skip deleted messages

**Timing:** Must be done between Scheduler and Purchaser runs (during review window).

### Spike Guard

Prevents over-committing to Savings Plans during temporary usage spikes (e.g. Black Friday, seasonal peaks, one-off migrations). Enabled by default, it compares recent average hourly spend against historical baselines and blocks purchases when recent usage is abnormally high.

Two independent checks run automatically:
- **At scheduling time** — compares 14-day avg vs 90-day avg. Blocks scheduling if recent usage spiked above the threshold.
- **At purchase time** — compares current 14-day avg vs the 14-day avg recorded at scheduling time. Blocks purchase if usage dropped since scheduling (confirming the spike was temporary).

Only the specific SP types showing anomalies are blocked — other types proceed normally.

```hcl
purchase_strategy = {
  # ...
  spike_guard = {           # optional, defaults to enabled
    enabled             = true
    long_lookback_days  = 90  # historical baseline period
    short_lookback_days = 14  # recent usage period
    threshold_percent   = 20  # block if recent avg is >= 20% above baseline
  }
}
```

Disable with `spike_guard = { enabled = false }`. The reporter includes a yellow warning banner when a spike is detected.

## Reference

### Configuration Variables

Complete variable documentation: **[variables.tf](variables.tf)**

Main configuration objects:
- `purchase_strategy` — Coverage targets, purchase limits, strategy selection
- `sp_plans` — Enable/configure Compute, Database, SageMaker
- `cron_schedules` — Cron schedules for Scheduler, Purchaser, Reporter
- `notifications` — Email addresses, webhook URLs
- `lambda_config` — Per-Lambda settings (dry-run, assume roles, alarms)
- `monitoring` — CloudWatch alarms, error thresholds
- `reporting` — Report format, S3 storage, email delivery

### Outputs

**Queue:** `queue_url`, `queue_arn`, `dlq_url`, `dlq_arn`

**Lambdas:** `scheduler_lambda_arn`, `purchaser_lambda_arn`, `reporter_lambda_arn` (+ `_name` variants)

**Notifications:** `sns_topic_arn`

**Configuration:** `module_configuration`, `database_sp_configuration`

### Supported Services

**Compute Savings Plans:** EC2 (any family/size/region/OS/tenancy), Lambda, Fargate

**Database Savings Plans:** RDS, Aurora, DynamoDB, ElastiCache (Valkey), DocumentDB, Neptune, Keyspaces, Timestream, DMS

**SageMaker Savings Plans:** Training, Real-Time Inference, Serverless Inference, Notebook Instances

Coverage is tracked independently for each SP type.

### Requirements

- **Terraform:** >= 1.0
- **AWS Provider:** >= 5.0
- **IAM Permissions:**
  - Cost Explorer: `ce:GetSavingsPlansPurchaseRecommendation`, `ce:GetSavingsPlansCoverage`
  - Savings Plans: `savingsplans:CreateSavingsPlan`, `savingsplans:DescribeSavingsPlans`
  - SQS: `sqs:SendMessage`, `sqs:ReceiveMessage`, `sqs:DeleteMessage`, `sqs:PurgeQueue`
  - SNS: `sns:Publish`
  - CloudWatch Logs: Lambda logging

## Contributing

Contributions welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for branch naming, commit conventions, and PR process. See [DEVELOPMENT.md](DEVELOPMENT.md) for local setup and testing.

## Support

For questions, issues, or feature requests, please open a [GitHub issue](https://github.com/etiennechabert/terraform-aws-sp-autopilot/issues).

## License

This module is open-source software licensed under the [Apache License 2.0](LICENSE).

---

## Terraform Reference

<!-- BEGIN_TF_DOCS -->
## Requirements

| Name | Version |
|------|---------|
| <a name="requirement_terraform"></a> [terraform](#requirement\_terraform) | >= 1.7 |
| <a name="requirement_aws"></a> [aws](#requirement\_aws) | >= 5.0, < 6.34 |

## Providers

| Name | Version |
|------|---------|
| <a name="provider_archive"></a> [archive](#provider\_archive) | 2.7.1 |
| <a name="provider_aws"></a> [aws](#provider\_aws) | 6.33.0 |

## Resources

| Name | Type |
|------|------|
| [aws_cloudwatch_event_rule.purchaser](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/cloudwatch_event_rule) | resource |
| [aws_cloudwatch_event_rule.reporter](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/cloudwatch_event_rule) | resource |
| [aws_cloudwatch_event_rule.scheduler](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/cloudwatch_event_rule) | resource |
| [aws_cloudwatch_event_target.purchaser](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/cloudwatch_event_target) | resource |
| [aws_cloudwatch_event_target.reporter](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/cloudwatch_event_target) | resource |
| [aws_cloudwatch_event_target.scheduler](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/cloudwatch_event_target) | resource |
| [aws_cloudwatch_log_group.purchaser](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/cloudwatch_log_group) | resource |
| [aws_cloudwatch_log_group.reporter](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/cloudwatch_log_group) | resource |
| [aws_cloudwatch_log_group.scheduler](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/cloudwatch_log_group) | resource |
| [aws_cloudwatch_metric_alarm.dlq_alarm](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/cloudwatch_metric_alarm) | resource |
| [aws_cloudwatch_metric_alarm.purchaser_error_alarm](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/cloudwatch_metric_alarm) | resource |
| [aws_cloudwatch_metric_alarm.reporter_error_alarm](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/cloudwatch_metric_alarm) | resource |
| [aws_cloudwatch_metric_alarm.scheduler_error_alarm](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/cloudwatch_metric_alarm) | resource |
| [aws_iam_role.purchaser](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_role) | resource |
| [aws_iam_role.reporter](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_role) | resource |
| [aws_iam_role.scheduler](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_role) | resource |
| [aws_iam_role_policy.purchaser_assume_role](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_role_policy) | resource |
| [aws_iam_role_policy.purchaser_cloudwatch_logs](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_role_policy) | resource |
| [aws_iam_role_policy.purchaser_cost_explorer](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_role_policy) | resource |
| [aws_iam_role_policy.purchaser_savingsplans](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_role_policy) | resource |
| [aws_iam_role_policy.purchaser_sns](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_role_policy) | resource |
| [aws_iam_role_policy.purchaser_sqs](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_role_policy) | resource |
| [aws_iam_role_policy.reporter_assume_role](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_role_policy) | resource |
| [aws_iam_role_policy.reporter_cloudwatch_logs](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_role_policy) | resource |
| [aws_iam_role_policy.reporter_cost_explorer](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_role_policy) | resource |
| [aws_iam_role_policy.reporter_s3](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_role_policy) | resource |
| [aws_iam_role_policy.reporter_savingsplans](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_role_policy) | resource |
| [aws_iam_role_policy.reporter_sns](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_role_policy) | resource |
| [aws_iam_role_policy.scheduler_assume_role](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_role_policy) | resource |
| [aws_iam_role_policy.scheduler_cloudwatch_logs](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_role_policy) | resource |
| [aws_iam_role_policy.scheduler_cost_explorer](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_role_policy) | resource |
| [aws_iam_role_policy.scheduler_savingsplans](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_role_policy) | resource |
| [aws_iam_role_policy.scheduler_sns](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_role_policy) | resource |
| [aws_iam_role_policy.scheduler_sqs](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_role_policy) | resource |
| [aws_lambda_function.purchaser](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/lambda_function) | resource |
| [aws_lambda_function.reporter](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/lambda_function) | resource |
| [aws_lambda_function.scheduler](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/lambda_function) | resource |
| [aws_lambda_permission.purchaser_eventbridge](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/lambda_permission) | resource |
| [aws_lambda_permission.reporter_eventbridge](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/lambda_permission) | resource |
| [aws_lambda_permission.scheduler_eventbridge](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/lambda_permission) | resource |
| [aws_s3_bucket.reports](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_bucket) | resource |
| [aws_s3_bucket.reports_logs](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_bucket) | resource |
| [aws_s3_bucket_lifecycle_configuration.reports](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_bucket_lifecycle_configuration) | resource |
| [aws_s3_bucket_lifecycle_configuration.reports_logs](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_bucket_lifecycle_configuration) | resource |
| [aws_s3_bucket_logging.reports](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_bucket_logging) | resource |
| [aws_s3_bucket_policy.reports_https_only](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_bucket_policy) | resource |
| [aws_s3_bucket_public_access_block.reports](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_bucket_public_access_block) | resource |
| [aws_s3_bucket_public_access_block.reports_logs](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_bucket_public_access_block) | resource |
| [aws_s3_bucket_server_side_encryption_configuration.reports](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_bucket_server_side_encryption_configuration) | resource |
| [aws_s3_bucket_versioning.reports](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_bucket_versioning) | resource |
| [aws_sns_topic.notifications](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/sns_topic) | resource |
| [aws_sns_topic_subscription.email_notifications](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/sns_topic_subscription) | resource |
| [aws_sqs_queue.purchase_intents](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/sqs_queue) | resource |
| [aws_sqs_queue.purchase_intents_dlq](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/sqs_queue) | resource |
| [aws_sqs_queue_policy.purchase_intents](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/sqs_queue_policy) | resource |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_notifications"></a> [notifications](#input\_notifications) | Notification configuration for email, Slack, and Teams | <pre>object({<br/>    emails         = list(string)<br/>    slack_webhook  = optional(string)<br/>    teams_webhook  = optional(string)<br/>    send_no_action = optional(bool, true)<br/>  })</pre> | n/a | yes |
| <a name="input_purchase_strategy"></a> [purchase\_strategy](#input\_purchase\_strategy) | Purchase strategy configuration with orthogonal target + split dimensions | <pre>object({<br/>    lookback_days           = optional(number, 13)<br/>    min_data_days           = optional(number, 14)<br/>    granularity             = optional(string, "HOURLY")<br/>    renewal_window_days     = optional(number, 7)<br/>    purchase_cooldown_days  = optional(number, 7)<br/>    min_commitment_per_plan = optional(number, 0.001)<br/><br/>    target = object({<br/>      fixed   = optional(object({ coverage_percent = number }))<br/>      aws     = optional(object({}))<br/>      dynamic = optional(object({ risk_level = string }))<br/>    })<br/><br/>    split = object({<br/>      one_shot   = optional(object({}))<br/>      fixed_step = optional(object({ step_percent = number }))<br/>      gap_split = optional(object({<br/>        divider              = number<br/>        min_purchase_percent = optional(number, 1)<br/>        max_purchase_percent = optional(number)<br/>      }))<br/>    })<br/><br/>    spike_guard = optional(object({<br/>      enabled             = optional(bool, true)<br/>      long_lookback_days  = optional(number, 90)<br/>      short_lookback_days = optional(number, 14)<br/>      threshold_percent   = optional(number, 20)<br/>    }), {})<br/>  })</pre> | n/a | yes |
| <a name="input_sp_plans"></a> [sp\_plans](#input\_sp\_plans) | Savings Plans configuration for Compute, Database, and SageMaker | <pre>object({<br/>    compute = object({<br/>      enabled   = bool<br/>      plan_type = optional(string)<br/>    })<br/><br/>    database = object({<br/>      enabled   = bool<br/>      plan_type = optional(string) # AWS only supports "no_upfront_one_year" for Database SPs<br/>    })<br/><br/>    sagemaker = object({<br/>      enabled   = bool<br/>      plan_type = optional(string)<br/>    })<br/>  })</pre> | n/a | yes |
| <a name="input_cron_schedules"></a> [cron\_schedules](#input\_cron\_schedules) | EventBridge cron schedules for each Lambda function. Set to null to disable a schedule. | <pre>object({<br/>    scheduler = optional(string) # Set to null to disable, defaults to "cron(0 8 1 * ? *)"<br/>    purchaser = optional(string) # Set to null to disable, defaults to "cron(0 8 10 * ? *)"<br/>    reporter  = optional(string) # Set to null to disable, defaults to "cron(0 9 20 * ? *)"<br/>  })</pre> | <pre>{<br/>  "purchaser": "cron(0 8 10-17 * MON *)",<br/>  "reporter": "cron(0 8 20-27 * MON *)",<br/>  "scheduler": "cron(0 8 1-7 * MON *)"<br/>}</pre> | no |
| <a name="input_encryption"></a> [encryption](#input\_encryption) | Encryption configuration for SNS, SQS, and S3 | <pre>object({<br/>    sns_kms_key = optional(string, "alias/aws/sns") # Default: AWS managed KMS key. Set to null to disable.<br/>    sqs_kms_key = optional(string, "alias/aws/sqs") # Default: AWS managed KMS key. Set to null to disable.<br/>    s3 = optional(object({<br/>      enabled = optional(bool, true) # Enable/disable S3 encryption<br/>      kms_key = optional(string)     # null = AES256 (SSE-S3, free), set to KMS key ARN for SSE-KMS<br/>    }), {})<br/>  })</pre> | `{}` | no |
| <a name="input_lambda_config"></a> [lambda\_config](#input\_lambda\_config) | Lambda function configuration including enable/disable controls, performance settings, cross-account role ARNs, and error alarms | <pre>object({<br/>    scheduler = optional(object({<br/>      enabled         = optional(bool, true)<br/>      dry_run         = optional(bool, false) # If true, sends email only (no SQS queueing)<br/>      memory_mb       = optional(number, 128)<br/>      timeout         = optional(number, 300)<br/>      assume_role_arn = optional(string)     # Role to assume for Cost Explorer and Savings Plans APIs (AWS Orgs)<br/>      error_alarm     = optional(bool, true) # Enable CloudWatch error alarm for this Lambda<br/>    }), {})<br/><br/>    purchaser = optional(object({<br/>      enabled         = optional(bool, true)<br/>      memory_mb       = optional(number, 128)<br/>      timeout         = optional(number, 300)<br/>      assume_role_arn = optional(string)     # Role to assume for Savings Plans purchase APIs (AWS Orgs)<br/>      error_alarm     = optional(bool, true) # Enable CloudWatch error alarm for this Lambda<br/>    }), {})<br/><br/>    reporter = optional(object({<br/>      enabled         = optional(bool, true)<br/>      memory_mb       = optional(number, 128)<br/>      timeout         = optional(number, 300)<br/>      assume_role_arn = optional(string)     # Role to assume for Cost Explorer and Savings Plans APIs (AWS Orgs)<br/>      error_alarm     = optional(bool, true) # Enable CloudWatch error alarm for this Lambda<br/>    }), {})<br/>  })</pre> | `{}` | no |
| <a name="input_monitoring"></a> [monitoring](#input\_monitoring) | CloudWatch monitoring and alarm configuration | <pre>object({<br/>    dlq_alarm                 = optional(bool, true)<br/>    error_threshold           = optional(number, 1)  # Threshold for Lambda error alarms (configured per-Lambda in lambda_config)<br/>    low_utilization_threshold = optional(number, 70) # Alert when Savings Plans utilization falls below this percentage<br/>  })</pre> | `{}` | no |
| <a name="input_name_prefix"></a> [name\_prefix](#input\_name\_prefix) | Prefix for all resource names. Allows multiple module deployments in the same AWS account. | `string` | `"sp-autopilot"` | no |
| <a name="input_reporting"></a> [reporting](#input\_reporting) | Report generation and storage configuration | <pre>object({<br/>    enabled            = optional(bool, true)<br/>    format             = optional(string, "html")<br/>    email_reports      = optional(bool, false)<br/>    retention_days     = optional(number, 365)<br/>    include_debug_data = optional(bool, false)<br/><br/>    s3_lifecycle = optional(object({<br/>      transition_ia_days         = optional(number, 90)<br/>      transition_glacier_days    = optional(number, 180)<br/>      expiration_days            = optional(number, 365)<br/>      noncurrent_expiration_days = optional(number, 90)<br/>    }), {})<br/>  })</pre> | `{}` | no |
| <a name="input_s3_access_logging"></a> [s3\_access\_logging](#input\_s3\_access\_logging) | Enable S3 access logging for the reports bucket (for compliance/auditing) | <pre>object({<br/>    enabled         = optional(bool, false)<br/>    target_prefix   = optional(string, "access-logs/")<br/>    expiration_days = optional(number, 90)<br/>  })</pre> | `{}` | no |
| <a name="input_tags"></a> [tags](#input\_tags) | Additional tags to apply to all resources | `map(string)` | `{}` | no |

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_database_sp_configuration"></a> [database\_sp\_configuration](#output\_database\_sp\_configuration) | Database Savings Plans configuration for monitoring |
| <a name="output_dlq_alarm_arn"></a> [dlq\_alarm\_arn](#output\_dlq\_alarm\_arn) | ARN of the DLQ depth alarm |
| <a name="output_dlq_arn"></a> [dlq\_arn](#output\_dlq\_arn) | ARN of the dead letter queue |
| <a name="output_dlq_url"></a> [dlq\_url](#output\_dlq\_url) | URL of the dead letter queue |
| <a name="output_lambda_environment_database_sp"></a> [lambda\_environment\_database\_sp](#output\_lambda\_environment\_database\_sp) | Database SP enablement flag for Lambda functions |
| <a name="output_lambda_environment_sagemaker_sp"></a> [lambda\_environment\_sagemaker\_sp](#output\_lambda\_environment\_sagemaker\_sp) | SageMaker SP enablement flag for Lambda functions |
| <a name="output_module_configuration"></a> [module\_configuration](#output\_module\_configuration) | Module configuration summary |
| <a name="output_purchaser_error_alarm_arn"></a> [purchaser\_error\_alarm\_arn](#output\_purchaser\_error\_alarm\_arn) | ARN of the Purchaser Lambda error alarm |
| <a name="output_purchaser_lambda_arn"></a> [purchaser\_lambda\_arn](#output\_purchaser\_lambda\_arn) | ARN of the Purchaser Lambda function |
| <a name="output_purchaser_lambda_name"></a> [purchaser\_lambda\_name](#output\_purchaser\_lambda\_name) | Name of the Purchaser Lambda function |
| <a name="output_purchaser_role_arn"></a> [purchaser\_role\_arn](#output\_purchaser\_role\_arn) | ARN of the Purchaser Lambda execution role |
| <a name="output_purchaser_rule_arn"></a> [purchaser\_rule\_arn](#output\_purchaser\_rule\_arn) | ARN of the EventBridge rule for Purchaser Lambda |
| <a name="output_purchaser_rule_name"></a> [purchaser\_rule\_name](#output\_purchaser\_rule\_name) | Name of the EventBridge rule for Purchaser Lambda |
| <a name="output_queue_arn"></a> [queue\_arn](#output\_queue\_arn) | ARN of the purchase intents queue |
| <a name="output_queue_url"></a> [queue\_url](#output\_queue\_url) | URL of the purchase intents queue |
| <a name="output_reporter_error_alarm_arn"></a> [reporter\_error\_alarm\_arn](#output\_reporter\_error\_alarm\_arn) | ARN of the Reporter Lambda error alarm |
| <a name="output_reporter_lambda_arn"></a> [reporter\_lambda\_arn](#output\_reporter\_lambda\_arn) | ARN of the Reporter Lambda function |
| <a name="output_reporter_lambda_name"></a> [reporter\_lambda\_name](#output\_reporter\_lambda\_name) | Name of the Reporter Lambda function |
| <a name="output_reporter_role_arn"></a> [reporter\_role\_arn](#output\_reporter\_role\_arn) | ARN of the Reporter Lambda execution role |
| <a name="output_reporter_rule_arn"></a> [reporter\_rule\_arn](#output\_reporter\_rule\_arn) | ARN of the EventBridge rule for Reporter Lambda |
| <a name="output_reporter_rule_name"></a> [reporter\_rule\_name](#output\_reporter\_rule\_name) | Name of the EventBridge rule for Reporter Lambda |
| <a name="output_reports_bucket_arn"></a> [reports\_bucket\_arn](#output\_reports\_bucket\_arn) | ARN of the reports bucket |
| <a name="output_reports_bucket_name"></a> [reports\_bucket\_name](#output\_reports\_bucket\_name) | Name of the reports bucket |
| <a name="output_sagemaker_sp_configuration"></a> [sagemaker\_sp\_configuration](#output\_sagemaker\_sp\_configuration) | SageMaker Savings Plans configuration for monitoring |
| <a name="output_scheduler_error_alarm_arn"></a> [scheduler\_error\_alarm\_arn](#output\_scheduler\_error\_alarm\_arn) | ARN of the Scheduler Lambda error alarm |
| <a name="output_scheduler_lambda_arn"></a> [scheduler\_lambda\_arn](#output\_scheduler\_lambda\_arn) | ARN of the Scheduler Lambda function |
| <a name="output_scheduler_lambda_name"></a> [scheduler\_lambda\_name](#output\_scheduler\_lambda\_name) | Name of the Scheduler Lambda function |
| <a name="output_scheduler_role_arn"></a> [scheduler\_role\_arn](#output\_scheduler\_role\_arn) | ARN of the Scheduler Lambda execution role |
| <a name="output_scheduler_rule_arn"></a> [scheduler\_rule\_arn](#output\_scheduler\_rule\_arn) | ARN of the EventBridge rule for Scheduler Lambda |
| <a name="output_scheduler_rule_name"></a> [scheduler\_rule\_name](#output\_scheduler\_rule\_name) | Name of the EventBridge rule for Scheduler Lambda |
| <a name="output_sns_topic_arn"></a> [sns\_topic\_arn](#output\_sns\_topic\_arn) | ARN of the SNS topic for notifications |
<!-- END_TF_DOCS -->

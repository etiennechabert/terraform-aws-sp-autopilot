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
    lookback_days = 13 # Max 13 days (AWS HOURLY granularity limit)

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

### Hourly Granularity (Required)

Savings Plans are purchased as hourly commitments ($/hour). This module always analyzes data at hourly granularity for accurate purchase sizing.

**Prerequisite:** You must enable **"Hourly and resource level granularity"** in [AWS Cost Explorer settings](https://console.aws.amazon.com/cost-management/home#/settings). Cost: ~$0.10-$1.00/month. The module will return a clear error if this setting is not enabled.

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
- **Cost Explorer:** [Hourly and resource level granularity](https://console.aws.amazon.com/cost-management/home#/settings) must be enabled
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

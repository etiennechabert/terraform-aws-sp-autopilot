# AWS Savings Plans Automation Module

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
![Terraform Version](https://img.shields.io/badge/Terraform-%3E%3D%201.0-623CE4.svg)
![AWS Provider Version](https://img.shields.io/badge/AWS%20Provider-%3E%3D%205.0-FF9900.svg)

[![PR Checks](https://github.com/etiennechabert/terraform-aws-sp-autopilot/actions/workflows/pr-checks.yml/badge.svg)](https://github.com/etiennechabert/terraform-aws-sp-autopilot/actions/workflows/pr-checks.yml)
[![Security Scan](https://github.com/etiennechabert/terraform-aws-sp-autopilot/actions/workflows/security-scan.yml/badge.svg)](https://github.com/etiennechabert/terraform-aws-sp-autopilot/actions/workflows/security-scan.yml)
[![codecov](https://codecov.io/gh/etiennechabert/terraform-aws-sp-autopilot/branch/main/graph/badge.svg)](https://codecov.io/gh/etiennechabert/terraform-aws-sp-autopilot)

An open-source Terraform module that automates AWS Savings Plans purchases based on usage analysis. The module maintains consistent coverage while limiting financial exposure through incremental, spread-out commitments.

## Table of Contents

- [Features](#features)
- [Supported Savings Plan Types](#supported-savings-plan-types)
- [Architecture](#architecture)
- [Quick Start](#quick-start)
- [Configuration Variables](#configuration-variables)
- [Supported Services](#supported-services)
- [Coverage Tracking](#coverage-tracking)
- [Outputs](#outputs)
- [Advanced Usage](#advanced-usage)
- [Cross-Account Setup for AWS Organizations](#cross-account-setup-for-aws-organizations)
- [Requirements](#requirements)
- [Error Reference](ERROR_REFERENCE.md)
- [License](#license)
- [Contributing](#contributing)
- [Support](#support)

## Features

- **Automated Savings Plans purchasing** — Maintains target coverage levels without manual intervention
- **Triple SP type support** — Supports Compute, Database, and SageMaker Savings Plans independently
- **Human review window** — Configurable delay between scheduling and purchasing allows cancellation
- **Risk management** — Spread financial commitments over time with configurable purchase limits
- **Coverage cap enforcement** — Hard ceiling prevents over-commitment if usage shrinks
- **Email notifications** — SNS-based alerts for all scheduling and purchasing activities
- **Auditable and transparent** — All decisions logged, all purchases tracked with idempotency

## Supported Savings Plan Types

### Compute Savings Plans

| Attribute | Details |
|-----------|---------|
| **Coverage** | EC2, Lambda, Fargate |
| **Terms** | 1-year, 3-year (configurable mix) |
| **Payment Options** | All Upfront, Partial Upfront, No Upfront |
| **Max Discount** | Up to 66% |
| **Configuration** | Fully configurable term mix and payment options |

### Database Savings Plans

| Attribute | Details |
|-----------|---------|
| **Coverage** | RDS, Aurora, DynamoDB, ElastiCache (Valkey), DocumentDB, Neptune, Keyspaces, Timestream, DMS |
| **Terms** | **1-year only** *(AWS constraint)* |
| **Payment Options** | **No Upfront only** *(AWS constraint)* |
| **Max Discount** | Up to 35% (serverless), up to 20% (provisioned) |
| **Configuration** | Enable via `enable_database_sp = true` |

> **⚠️ Important:** Database Savings Plans have fixed AWS constraints. The `database_sp_term` and `database_sp_payment_option` variables exist for validation only — they cannot be changed from `ONE_YEAR` and `NO_UPFRONT` respectively.

### SageMaker Savings Plans

| Attribute | Details |
|-----------|---------|
| **Coverage** | SageMaker training, inference (real-time and serverless), and notebook instances |
| **Terms** | 1-year, 3-year (configurable mix) |
| **Payment Options** | All Upfront, Partial Upfront, No Upfront |
| **Max Discount** | Up to 64% |
| **Configuration** | Enable via `enable_sagemaker_sp = true` |

> **✓ Fully Configurable:** SageMaker Savings Plans offer complete flexibility in term and payment options, similar to Compute Savings Plans. You can customize the term mix (e.g., 70% 3-year, 30% 1-year) via `sagemaker_sp_term_mix` and select any payment option via `sagemaker_sp_payment_option` (`ALL_UPFRONT`, `PARTIAL_UPFRONT`, or `NO_UPFRONT`).

## Architecture

The module consists of two Lambda functions with an SQS queue between them:

![Architecture Diagram](docs/architecture.svg)

**Workflow:**

1. **Scheduler Lambda** runs on configurable schedule (e.g., 1st of month)
   - Purges any stale queue messages
   - Fetches current coverage and AWS recommendations (separate calls for Compute, Database, and SageMaker)
   - Calculates purchase need to reach target coverage
   - Queues purchase intents to SQS (or sends email only if `dry_run = true`)

2. **SQS Queue** holds purchase intents during review window
   - Users can delete messages from queue to cancel unwanted purchases
   - Messages include full purchase details and idempotency tokens

3. **Purchaser Lambda** runs on separate schedule (e.g., 4th of month)
   - Processes each message from queue
   - Validates purchase won't exceed `max_coverage_cap` (checked separately for Compute, Database, and SageMaker)
   - Executes purchase via AWS CreateSavingsPlan API
   - Sends aggregated email summary of all purchases

## Quick Start

> **💡 Module Source:** This module is published to the [Terraform Registry](https://registry.terraform.io/modules/etiennechabert/sp-autopilot/aws). Use the registry source format shown below for automatic version management.

### Basic Usage

```hcl
module "savings_plans" {
  source  = "etiennechabert/sp-autopilot/aws"
  version = "~> 1.0"

  coverage_target_percent = 90
  max_coverage_cap        = 95
  max_purchase_percent    = 10
  notification_emails     = ["devops@example.com"]

  dry_run = true  # Start in dry-run mode (recommended)
}
```

This enables **Compute Savings Plans** (default). For other configurations:

<details>
<summary><b>Database Savings Plans Only</b></summary>

```hcl
module "savings_plans" {
  source  = "etiennechabert/sp-autopilot/aws"
  version = "~> 1.0"

  enable_compute_sp  = false
  enable_database_sp = true

  coverage_target_percent = 90
  notification_emails     = ["database-team@example.com"]
  dry_run                 = true
}
```
</details>

<details>
<summary><b>SageMaker Savings Plans Only</b></summary>

```hcl
module "savings_plans" {
  source  = "etiennechabert/sp-autopilot/aws"
  version = "~> 1.0"

  enable_compute_sp  = false
  enable_sagemaker_sp = true

  coverage_target_percent = 90
  notification_emails     = ["ml-team@example.com"]
  dry_run                 = true

  # SageMaker SP customization (optional)
  sagemaker_sp_term_mix = {
    three_year = 0.70
    one_year   = 0.30
  }
  sagemaker_sp_payment_option = "ALL_UPFRONT"
}
```
</details>

<details>
<summary><b>All Three SP Types (Production Example)</b></summary>

```hcl
module "savings_plans" {
  source  = "etiennechabert/sp-autopilot/aws"
  version = "~> 1.0"

  enable_compute_sp   = true
  enable_database_sp  = true
  enable_sagemaker_sp = true

  coverage_target_percent = 90
  max_coverage_cap        = 95
  max_purchase_percent    = 10

  # Compute SP customization
  compute_sp_term_mix = {
    three_year = 0.67
    one_year   = 0.33
  }
  compute_sp_payment_option = "ALL_UPFRONT"

  # SageMaker SP customization
  sagemaker_sp_term_mix = {
    three_year = 0.70
    one_year   = 0.30
  }
  sagemaker_sp_payment_option = "ALL_UPFRONT"

  # Schedule with 3-day review window
  scheduler_schedule = "cron(0 8 1 * ? *)"  # 1st of month
  purchaser_schedule = "cron(0 8 4 * ? *)"  # 4th of month

  notification_emails = ["devops@example.com", "finops@example.com", "ml-team@example.com"]
  dry_run             = false
}
```
</details>

<details>
<summary><b>With Slack and Teams Webhook Notifications</b></summary>

```hcl
# Store webhook URLs in variables and mark as sensitive
variable "slack_webhook_url" {
  type      = string
  sensitive = true
  description = "Slack webhook URL for notifications"
}

variable "teams_webhook_url" {
  type      = string
  sensitive = true
  description = "Microsoft Teams webhook URL for notifications"
}

module "savings_plans" {
  source  = "etiennechabert/sp-autopilot/aws"
  version = "~> 1.0"

  coverage_target_percent = 90
  max_coverage_cap        = 95
  max_purchase_percent    = 10

  # Notification configuration
  notification_emails = ["devops@example.com"]
  slack_webhook_url   = var.slack_webhook_url
  teams_webhook_url   = var.teams_webhook_url

  dry_run = true
}
```

> **🔒 Security Note:** Webhook URLs contain sensitive credentials. Always mark webhook URL variables as `sensitive = true` to prevent them from appearing in Terraform logs and output. Store webhook URLs in AWS Secrets Manager, HashiCorp Vault, or environment variables — never commit them directly to version control.

</details>

## Configuration Variables

### Savings Plan Types

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `enable_compute_sp` | `bool` | `true` | Enable Compute Savings Plans automation |
| `enable_database_sp` | `bool` | `false` | Enable Database Savings Plans automation (see [Supported Savings Plan Types](#supported-savings-plan-types) for coverage and constraints) |
| `enable_sagemaker_sp` | `bool` | `false` | Enable SageMaker Savings Plans automation for ML/AI workloads |

> **Note:** At least one of `enable_compute_sp`, `enable_database_sp`, or `enable_sagemaker_sp` must be `true`.

### Coverage Strategy

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `coverage_target_percent` | `number` | `90` | Target hourly coverage percentage (applies to each SP type separately) |
| `max_coverage_cap` | `number` | `95` | Hard cap — never exceed this coverage (enforced separately per SP type) |
| `lookback_days` | `number` | `30` | Days of usage history for AWS recommendations |

### Risk Management

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `max_purchase_percent` | `number` | `10` | Maximum purchase as percentage of current monthly on-demand spend |
| `min_data_days` | `number` | `14` | Skip recommendations if insufficient usage history |
| `min_commitment_per_plan` | `number` | `0.001` | Minimum commitment per SP (AWS minimum: $0.001/hr) |

### Expiring Plans

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `renewal_window_days` | `number` | `7` | Savings Plans expiring within X days are excluded from coverage calculation (forces renewal) |

### Compute SP Options

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `compute_sp_term_mix` | `object` | `{three_year: 0.67, one_year: 0.33}` | Split of commitment between 3-year and 1-year terms (must sum to 1.0) |
| `compute_sp_payment_option` | `string` | `"ALL_UPFRONT"` | Payment option: `ALL_UPFRONT`, `PARTIAL_UPFRONT`, `NO_UPFRONT` |
| `partial_upfront_percent` | `number` | `50` | Percentage paid upfront for `PARTIAL_UPFRONT` option |

### Database SP Options

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `database_sp_term` | `string` | `"ONE_YEAR"` | Must be `ONE_YEAR` (AWS constraint — validation only) |
| `database_sp_payment_option` | `string` | `"NO_UPFRONT"` | Must be `NO_UPFRONT` (AWS constraint — validation only) |

> **Note:** These variables exist for validation only. See [Database Savings Plans](#database-savings-plans) for AWS constraint details.

### SageMaker SP Options

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `sagemaker_sp_term_mix` | `object` | `{three_year: 0.67, one_year: 0.33}` | Split of commitment between 3-year and 1-year terms (must sum to 1.0) |
| `sagemaker_sp_payment_option` | `string` | `"ALL_UPFRONT"` | Payment option: `ALL_UPFRONT`, `PARTIAL_UPFRONT`, `NO_UPFRONT` |

### Scheduling

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `scheduler_schedule` | `string` | `"cron(0 8 1 * ? *)"` | When scheduler runs (EventBridge cron expression) — Default: 1st of month |
| `purchaser_schedule` | `string` | `"cron(0 8 4 * ? *)"` | When purchaser runs (EventBridge cron expression) — Default: 4th of month |

> **Tip:** Set different schedules to create a review window. Set same schedule for immediate purchases (no review).

### Operations

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `dry_run` | `bool` | `true` | If `true`, scheduler sends email only (no queue) — **Start here!** |
| `send_no_action_email` | `bool` | `true` | Send email when no purchases needed |

### Notifications

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `notification_emails` | `list(string)` | `[]` | Email addresses for SNS notifications (must confirm subscription) |
| `slack_webhook_url` | `string` | `null` | Slack webhook URL for posting notifications to a Slack channel |
| `teams_webhook_url` | `string` | `null` | Microsoft Teams webhook URL for posting notifications to a Teams channel |

### Monitoring

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `enable_lambda_error_alarm` | `bool` | `true` | CloudWatch alarm on Lambda function errors |
| `enable_dlq_alarm` | `bool` | `true` | CloudWatch alarm on Dead Letter Queue depth |
| `lambda_error_threshold` | `number` | `1` | Number of Lambda errors to trigger alarm |

### AWS Organizations

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `management_account_role_arn` | `string` | `null` | IAM role ARN to assume in management account (for Organization-level SPs) |

### Tagging

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `tags` | `map(string)` | `{}` | Additional tags to apply to purchased Savings Plans |

## Supported Services

### Compute Savings Plans Cover:

- **Amazon EC2** — Elastic Compute Cloud instances (any family, size, region, OS, tenancy)
- **AWS Lambda** — Serverless compute
- **AWS Fargate** — Serverless containers for ECS and EKS

### Database Savings Plans Cover:

- **Amazon RDS** — Relational Database Service (MySQL, PostgreSQL, MariaDB, Oracle, SQL Server)
- **Amazon Aurora** — MySQL and PostgreSQL-compatible relational database
- **Amazon DynamoDB** — NoSQL key-value and document database
- **Amazon ElastiCache (Valkey)** — In-memory caching service
- **Amazon DocumentDB** — MongoDB-compatible document database
- **Amazon Neptune** — Graph database service
- **Amazon Keyspaces** — Cassandra-compatible database service
- **Amazon Timestream** — Time series database service
- **AWS Database Migration Service (DMS)** — Database migration workloads

### SageMaker Savings Plans Cover:

- **Amazon SageMaker Training** — ML model training jobs
- **Amazon SageMaker Real-Time Inference** — Hosted model endpoints
- **Amazon SageMaker Serverless Inference** — On-demand inference endpoints
- **Amazon SageMaker Notebook Instances** — Jupyter notebook environments

## Coverage Tracking

**Important:** Coverage for Compute, Database, and SageMaker Savings Plans is tracked **separately**.

- **Separate Recommendations:** Scheduler fetches separate AWS recommendations for Compute, Database, and SageMaker
- **Independent Targets:** All SP types work toward the same `coverage_target_percent`, but separately
- **Independent Caps:** The `max_coverage_cap` is enforced independently for each SP type
- **Separate Email Sections:** Notifications show coverage percentages for each SP type separately

When multiple SP types are enabled, email notifications show coverage and recommendations separately for each type, ensuring independent purchasing decisions and flexible workload management.

## Outputs

The module provides the following outputs for monitoring and integration:

### Queue Outputs
- `queue_url` — SQS queue URL for purchase intents
- `queue_arn` — SQS queue ARN
- `dlq_url` — Dead Letter Queue URL
- `dlq_arn` — Dead Letter Queue ARN

### Lambda Outputs
- `scheduler_lambda_arn` — Scheduler Lambda function ARN
- `scheduler_lambda_name` — Scheduler Lambda function name
- `purchaser_lambda_arn` — Purchaser Lambda function ARN
- `purchaser_lambda_name` — Purchaser Lambda function name

### Notification Outputs
- `sns_topic_arn` — SNS topic ARN for notifications

### Configuration Outputs
- `module_configuration` — Summary of current configuration
- `database_sp_configuration` — Database SP specific configuration with supported services and AWS constraints
- `lambda_environment_database_sp` — Database SP enable flag passed to Lambda functions

### Example Usage

```hcl
output "sp_config" {
  value = module.savings_plans.module_configuration
}
```

## Advanced Usage

### Gradual Rollout Strategy

Recommended approach for new deployments:

| Phase | Settings | Purpose |
|-------|----------|---------|
| **Week 1** | `dry_run = true` | Review email recommendations only |
| **Week 2-4** | `dry_run = false`<br>`coverage_target_percent = 70`<br>`max_purchase_percent = 5` | Small purchases, monitor results |
| **Month 2+** | `coverage_target_percent = 90`<br>`max_purchase_percent = 10` | Scale up as confidence grows |

### Purchase Strategies

The module supports two purchase strategies: **Simple** (default) and **Dichotomy** (adaptive).

#### Simple Strategy

Applies a fixed percentage to AWS recommendations. Best for stable workloads with predictable growth.

```hcl
purchase_strategy = {
  coverage_target_percent = 90
  max_coverage_cap        = 95

  simple = {
    max_purchase_percent = 10 # Purchase 10% of AWS recommendation each cycle
  }
}
```

**Characteristics:**
- Fixed purchase percentage every cycle
- Linear ramp to target coverage
- Predictable, easy to understand
- Recommended for: Stable workloads, small adjustments

#### Dichotomy Strategy

Adaptively sizes purchases using exponential halving based on coverage gap. Best for new deployments and variable workloads.

```hcl
purchase_strategy = {
  coverage_target_percent = 90
  max_coverage_cap        = 95

  dichotomy = {
    max_purchase_percent = 50 # Maximum purchase size
    min_purchase_percent = 1  # Minimum purchase threshold
  }
}
```

**How it works:**
- Calculates purchase as largest power-of-2 fraction of `max_purchase_percent` that doesn't exceed coverage gap
- Example progression (max 50%, target 90%):
  - Month 1: Gap 90% → Purchase 50% (max)
  - Month 2: Gap 40% → Purchase 25% (halved)
  - Month 3: Gap 15% → Purchase 12.5% (halved)
  - Month 4: Gap 2.5% → Purchase 2.5% (exact gap)

**Characteristics:**
- Adaptive purchase sizing (fast initially, slows near target)
- Creates distributed, smaller commitments over time
- Natural replacement of large expiring plans
- Prevents over-commitment through exponential halving
- Recommended for: New deployments, variable workloads, risk management

**Comparison:**

| Aspect | Simple | Dichotomy |
|--------|--------|-----------|
| Purchase sizing | Fixed % | Exponentially decreasing |
| Adaptation | Static | Dynamic based on gap |
| Ramp-up speed | Linear | Fast initially, slows near target |
| Coverage stability | Moderate | High (distributed purchases) |
| Over-commitment risk | Higher | Lower |
| Complexity | Very simple | Simple (automatic) |

**See also:** [Dichotomy Strategy Example](examples/dichotomy-strategy/) for detailed usage guide.

### Canceling Purchases

To cancel a scheduled purchase before it executes:

1. Navigate to AWS Console → SQS → Select queue `sp-autopilot-purchase-intents`
2. View messages in queue
3. Delete messages for purchases you want to cancel
4. Purchaser Lambda will skip deleted messages

**Note:** This must be done between scheduler run and purchaser run (during review window).

## Notification Setup

### Slack Webhooks

1. Go to `https://[workspace].slack.com/apps` → "Incoming Webhooks" → "Add to Slack"
2. Select channel and copy webhook URL
3. Configure: `slack_webhook_url = "https://hooks.slack.com/services/..."`

**Security:** Store webhook URLs in AWS Secrets Manager — never commit to version control.

### Microsoft Teams Webhooks

1. Teams channel → **•••** → **Connectors** → "Incoming Webhook" → **Configure**
2. Copy webhook URL (only shown once)
3. Configure: `teams_webhook_url = "https://[org].webhook.office.com/webhookb2/..."`

**Security:** Store webhook URLs in AWS Secrets Manager — never commit to version control.

## Cross-Account Setup for AWS Organizations

When using AWS Organizations, Savings Plans must be purchased from the **management account**. Deploy this module in a secondary account and configure cross-account access.

### Configuration

```hcl
module "savings_plans" {
  source  = "etiennechabert/sp-autopilot/aws"
  version = "~> 1.0"

  management_account_role_arn = "arn:aws:iam::123456789012:role/SavingsPlansAutomationRole"
  # ... other configuration
}
```

### IAM Role Setup in Management Account

Create role with trust policy allowing Lambda execution roles from secondary account:

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {"AWS": "arn:aws:iam::SECONDARY_ACCOUNT_ID:root"},
    "Action": "sts:AssumeRole"
  }]
}
```

Attach permissions policy:

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": [
      "ce:GetSavingsPlansPurchaseRecommendation",
      "ce:GetSavingsPlansCoverage",
      "savingsplans:CreateSavingsPlan",
      "savingsplans:DescribeSavingsPlans"
    ],
    "Resource": "*"
  }]
}
```

See [Organizations example](examples/organizations/README.md) for detailed setup instructions.

## Requirements

- **Terraform**: >= 1.0
- **AWS Provider**: >= 5.0
- **IAM Permissions**: Lambda functions require permissions for:
  - Cost Explorer API (GetSavingsPlansPurchaseRecommendation)
  - Savings Plans API (CreateSavingsPlan, DescribeSavingsPlans)
  - SQS (SendMessage, ReceiveMessage, DeleteMessage, PurgeQueue)
  - SNS (Publish)
  - CloudWatch Logs (for Lambda logging)

## License

This module is open-source software licensed under the MIT License.

## Contributing

Contributions are welcome! Please open an issue or pull request on GitHub.

## Support

For questions, issues, or feature requests, please open a GitHub issue.

---

**Generated with ❤️ by the AWS Savings Plans Autopilot Team**

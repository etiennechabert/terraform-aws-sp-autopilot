# AWS Savings Plans Automation Module

An open-source Terraform module that automates AWS Savings Plans purchases based on usage analysis. The module maintains consistent coverage while limiting financial exposure through incremental, spread-out commitments.

## Features

- **Automated Savings Plans purchasing** — Maintains target coverage levels without manual intervention
- **Dual SP type support** — Supports both Compute and Database Savings Plans independently
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

## Architecture

The module consists of two Lambda functions with an SQS queue between them:

```
EventBridge Schedule (1st of month)
        │
        ▼
┌─────────────────┐
│ Scheduler Lambda │ ──► Analyzes usage, calculates needed purchases
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│    SQS Queue    │ ◄── Human review window (delete messages to cancel)
└────────┬────────┘
         │
EventBridge Schedule (4th of month)
         │
         ▼
┌─────────────────┐
│ Purchaser Lambda │ ──► Executes queued purchases, validates coverage cap
└─────────────────┘
```

**Workflow:**

1. **Scheduler Lambda** runs on configurable schedule (e.g., 1st of month)
   - Purges any stale queue messages
   - Fetches current coverage and AWS recommendations (separate calls for Compute and Database)
   - Calculates purchase need to reach target coverage
   - Queues purchase intents to SQS (or sends email only if `dry_run = true`)

2. **SQS Queue** holds purchase intents during review window
   - Users can delete messages from queue to cancel unwanted purchases
   - Messages include full purchase details and idempotency tokens

3. **Purchaser Lambda** runs on separate schedule (e.g., 4th of month)
   - Processes each message from queue
   - Validates purchase won't exceed `max_coverage_cap` (checked separately for Compute and Database)
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
<summary><b>Both Compute and Database (Production Example)</b></summary>

```hcl
module "savings_plans" {
  source  = "etiennechabert/sp-autopilot/aws"
  version = "~> 1.0"

  enable_compute_sp  = true
  enable_database_sp = true

  coverage_target_percent = 90
  max_coverage_cap        = 95
  max_purchase_percent    = 10

  # Compute SP customization
  compute_sp_term_mix = {
    three_year = 0.67
    one_year   = 0.33
  }
  compute_sp_payment_option = "ALL_UPFRONT"

  # Schedule with 3-day review window
  scheduler_schedule = "cron(0 8 1 * ? *)"  # 1st of month
  purchaser_schedule = "cron(0 8 4 * ? *)"  # 4th of month

  notification_emails = ["devops@example.com", "finops@example.com"]
  dry_run             = false
}
```
</details>

## Configuration Variables

### Savings Plan Types

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `enable_compute_sp` | `bool` | `true` | Enable Compute Savings Plans automation |
| `enable_database_sp` | `bool` | `false` | Enable Database Savings Plans automation (see [Supported Savings Plan Types](#supported-savings-plan-types) for coverage and constraints) |

> **Note:** At least one of `enable_compute_sp` or `enable_database_sp` must be `true`.

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

### Compute Savings Plans Cover:

- **Amazon EC2** — Elastic Compute Cloud instances (any family, size, region, OS, tenancy)
- **AWS Lambda** — Serverless compute
- **AWS Fargate** — Serverless containers for ECS and EKS

## Coverage Tracking

**Important:** Coverage for Compute and Database Savings Plans is tracked **separately**.

- **Separate Recommendations:** Scheduler fetches separate AWS recommendations for Compute and Database
- **Independent Targets:** Both SP types work toward the same `coverage_target_percent`, but separately
- **Independent Caps:** The `max_coverage_cap` is enforced independently for each SP type
- **Separate Email Sections:** Notifications show coverage percentages for each SP type separately

When both SP types are enabled, email notifications show coverage and recommendations separately for each type, ensuring independent purchasing decisions and flexible workload management.

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

### Canceling Purchases

To cancel a scheduled purchase before it executes:

1. Navigate to AWS Console → SQS → Select queue `sp-autopilot-purchase-intents`
2. View messages in queue
3. Delete messages for purchases you want to cancel
4. Purchaser Lambda will skip deleted messages

**Note:** This must be done between scheduler run and purchaser run (during review window).

## Cross-Account Setup for AWS Organizations

When using AWS Organizations, Savings Plans purchases must be made from the **management account** (formerly master account), but you may want to deploy this module in a **secondary account** for security or organizational reasons.

The module supports cross-account operation by allowing Lambda functions to assume an IAM role in the management account before making Cost Explorer and Savings Plans API calls.

### Configuration

Set the `management_account_role_arn` variable to the ARN of a role in your management account:

```hcl
module "savings_plans" {
  source = "etiennechabert/sp-autopilot/aws"
  version = "~> 1.0"

  # Cross-account role assumption
  management_account_role_arn = "arn:aws:iam::123456789012:role/SavingsPlansAutomationRole"

  # ... other configuration
}
```

### IAM Role Setup in Management Account

Create an IAM role in your **management account** with the following configuration:

#### 1. Trust Policy

The role must trust the Lambda execution roles from your secondary account:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::SECONDARY_ACCOUNT_ID:role/sp-autopilot-scheduler"
      },
      "Action": "sts:AssumeRole"
    },
    {
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::SECONDARY_ACCOUNT_ID:role/sp-autopilot-purchaser"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
```

Replace `SECONDARY_ACCOUNT_ID` with your secondary account ID where the Lambda functions are deployed.

#### 2. Required Permissions

Attach a policy to the role with the following permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ce:GetSavingsPlansPurchaseRecommendation",
        "ce:GetSavingsPlansUtilization",
        "ce:GetSavingsPlansCoverage",
        "ce:GetCostAndUsage"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "savingsplans:DescribeSavingsPlans",
        "savingsplans:DescribeSavingsPlansOfferingRates",
        "savingsplans:DescribeSavingsPlansOfferings",
        "savingsplans:CreateSavingsPlan"
      ],
      "Resource": "*"
    }
  ]
}
```

### How It Works

When `management_account_role_arn` is configured:

1. **Scheduler Lambda** assumes the role before calling Cost Explorer APIs
2. **Purchaser Lambda** assumes the role before calling Savings Plans APIs
3. All Savings Plans operations execute with management account credentials
4. SQS and SNS operations continue using the Lambda execution role (local account)

### Verification

Test the cross-account setup:

```bash
aws lambda invoke --function-name sp-autopilot-scheduler output.json
```

Check CloudWatch Logs (`/aws/lambda/sp-autopilot-scheduler`) for successful role assumption and API calls.

### Troubleshooting

| Error | Cause | Solution |
|-------|-------|----------|
| `AccessDenied` during AssumeRole | Trust policy missing or incorrect | Verify trust policy includes Lambda execution role ARNs |
| `AccessDenied` during API calls | Insufficient permissions on assumed role | Add missing permissions to role policy |
| `InvalidClientTokenId` | Role ARN is invalid | Verify role ARN format and that role exists |
| No role assumption in logs | Variable not set correctly | Check `management_account_role_arn` in Terraform state |

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

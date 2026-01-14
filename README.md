# AWS Savings Plans Automation Module

An open-source Terraform module that automates AWS Savings Plans purchases based on usage analysis. The module maintains consistent coverage while limiting financial exposure through incremental, spread-out commitments.

[![PR Checks](https://github.com/your-org/terraform-aws-sp-autopilot/actions/workflows/pr-checks.yml/badge.svg)](https://github.com/your-org/terraform-aws-sp-autopilot/actions/workflows/pr-checks.yml)
[![Security Scan](https://github.com/your-org/terraform-aws-sp-autopilot/actions/workflows/security-scan.yml/badge.svg)](https://github.com/your-org/terraform-aws-sp-autopilot/actions/workflows/security-scan.yml)
[![Tests](https://github.com/your-org/terraform-aws-sp-autopilot/actions/workflows/tests.yml/badge.svg)](https://github.com/your-org/terraform-aws-sp-autopilot/actions/workflows/tests.yml)
[![Release](https://github.com/your-org/terraform-aws-sp-autopilot/actions/workflows/release.yml/badge.svg)](https://github.com/your-org/terraform-aws-sp-autopilot/actions/workflows/release.yml)

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
                    ┌─────────────────────┐
                    │  AWS Cost Explorer  │◄────┐
                    │        API          │     │
                    └─────────────────────┘     │
                                                │ Query coverage
                    ┌─────────────────────┐     │ & recommendations
                    │ AWS Savings Plans   │◄────┤
                    │        API          │     │
                    └─────────────────────┘     │
                                                │
EventBridge Schedule (1st of month)            │
        │                                       │
        ▼                                       │
┌─────────────────┐                             │
│ Scheduler Lambda │─────────────────────────────┘
│                 │
│  • Purge queue  │
│  • Get coverage │
│  • Calculate    │
│  • Queue intents│
└────────┬────────┘
         │
         ├──────────────────────────────┐
         │                              │
         ▼                              ▼
┌─────────────────┐            ┌───────────────┐
│    SQS Queue    │            │   SNS Topic   │──► Email: Analysis summary
│                 │            │               │    & queued purchases
│ Human Review    │            └───────────────┘
│ Window (3 days) │
│                 │
│ 👤 Delete msgs  │
│   to cancel     │
└────────┬────────┘
         │
EventBridge Schedule (4th of month)
         │
         ▼
┌─────────────────┐            ┌─────────────────────┐
│ Purchaser Lambda│───────────►│ AWS Savings Plans   │
│                 │  Execute   │        API          │
│  • Read queue   │  purchases │                     │
│  • Validate cap │            └─────────────────────┘
│  • Execute      │
│  • Send summary │
└────────┬────────┘
         │
         ▼
┌───────────────┐
│   SNS Topic   │──► Email: Purchase results
│               │    & updated coverage
└───────────────┘
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

**⏱️ Estimated time: 30 minutes** (includes AWS provider setup, Terraform apply, SNS email confirmation, and first dry-run email verification)

### Prerequisites

Before deploying this module, ensure you have:

- **Terraform** >= 1.0 installed ([Download](https://www.terraform.io/downloads))
- **AWS CLI** configured with credentials ([Setup Guide](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-quickstart.html))
- **AWS Account** with permissions to create:
  - Lambda functions and IAM roles
  - SQS queues
  - SNS topics and subscriptions
  - EventBridge rules
  - CloudWatch alarms and log groups
- **Active AWS workloads** running for at least 14 days (Compute or Database services)
- **Email access** to confirm SNS subscription

### Step 1: Configure AWS Provider (2 minutes)

Create a new directory and configure your AWS provider:

```hcl
# provider.tf
terraform {
  required_version = ">= 1.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }
}

provider "aws" {
  region = "us-east-1"  # Change to your preferred region
}
```

### Step 2: Create Module Configuration (5 minutes)

Create a `main.tf` file with your desired configuration:

**Option A: Compute Savings Plans Only (Most Common)**

```hcl
# main.tf
module "savings_plans" {
  source = "github.com/your-org/terraform-aws-sp-autopilot"

  # Enable Compute Savings Plans (covers EC2, Lambda, Fargate)
  enable_compute_sp = true
  enable_database_sp = false

  # Coverage targets
  coverage_target_percent = 90  # Target 90% coverage
  max_coverage_cap        = 95  # Never exceed 95% (safety limit)

  # Risk management
  max_purchase_percent = 10  # Max 10% of monthly spend per purchase cycle

  # Notifications (REPLACE with your email)
  notification_emails = ["devops@example.com"]

  # Start in dry-run mode (recommended for first deployment)
  dry_run = true
}
```

**Option B: Database Savings Plans Only**

```hcl
# main.tf
module "savings_plans" {
  source = "github.com/your-org/terraform-aws-sp-autopilot"

  # Enable Database Savings Plans (covers RDS, Aurora, DynamoDB, etc.)
  enable_database_sp = true
  enable_compute_sp = false

  # Coverage targets
  coverage_target_percent = 90
  max_coverage_cap        = 95

  # Risk management
  max_purchase_percent = 10

  # Notifications (REPLACE with your email)
  notification_emails = ["database-team@example.com"]

  # Start in dry-run mode
  dry_run = true
}
```

**Option C: Both Compute and Database Savings Plans**

```hcl
# main.tf
module "savings_plans" {
  source = "github.com/your-org/terraform-aws-sp-autopilot"

  # Enable both SP types (tracked independently)
  enable_compute_sp  = true
  enable_database_sp = true

  # Coverage targets (applies separately to each SP type)
  coverage_target_percent = 90
  max_coverage_cap        = 95

  # Risk management
  max_purchase_percent = 10

  # Compute SP configuration
  compute_sp_term_mix = {
    three_year = 0.67  # 67% of commitment in 3-year terms (max discount)
    one_year   = 0.33  # 33% in 1-year terms (more flexibility)
  }
  compute_sp_payment_option = "ALL_UPFRONT"  # Maximum savings

  # Database SP uses fixed AWS constraints (1-year, No Upfront only)

  # Scheduling
  scheduler_schedule = "cron(0 8 1 * ? *)"  # 1st of month, 8:00 AM UTC
  purchaser_schedule = "cron(0 8 4 * ? *)"  # 4th of month, 8:00 AM UTC

  # Notifications (REPLACE with your emails)
  notification_emails = [
    "devops@example.com",
    "finops@example.com"
  ]

  # Start in dry-run mode
  dry_run = true
}
```

> **💡 Tip:** Start with **Option A** (Compute SP only) and `dry_run = true` for your first deployment. You can enable Database SP and disable dry-run later.

### Step 3: Initialize and Apply Terraform (10 minutes)

```bash
# Initialize Terraform (downloads providers and modules)
terraform init

# Preview changes (verify what will be created)
terraform plan

# Apply configuration (creates AWS resources)
terraform apply
# Type 'yes' when prompted
```

**Expected resources created:**
- 2 Lambda functions (scheduler, purchaser)
- 2 SQS queues (main queue, dead letter queue)
- 1 SNS topic
- Email subscriptions (pending confirmation)
- 2 EventBridge schedules
- IAM roles and policies
- CloudWatch alarms and log groups

### Step 4: Confirm SNS Email Subscription (5 minutes)

**Immediately after Terraform apply:**

1. **Check your email inbox** (and spam folder!) for each address in `notification_emails`
2. Look for email with subject: **"AWS Notification - Subscription Confirmation"**
3. **Click "Confirm subscription"** link in the email
4. You should see **"Subscription confirmed!"** in your browser

**Verify subscription status:**

```bash
# Get SNS topic ARN from Terraform
terraform output sns_topic_arn

# Check subscription status (should show "Confirmed")
aws sns list-subscriptions-by-topic --topic-arn <sns-topic-arn>
```

> **⚠️ Important:** You will **not** receive automation emails until you confirm the subscription!

### Step 5: Verify Deployment (3 minutes)

Check that all components are working:

```bash
# Verify Lambda functions exist
aws lambda list-functions --query 'Functions[?contains(FunctionName, `sp-autopilot`)].FunctionName'

# Verify SQS queue exists
aws sqs list-queues --queue-name-prefix sp-autopilot

# Check CloudWatch Alarms status (should be OK)
aws cloudwatch describe-alarms --alarm-name-prefix sp-autopilot
```

### Step 6: Test with Manual Invocation (5 minutes)

Trigger the scheduler manually to get immediate feedback (don't wait for scheduled run):

```bash
# Get Lambda function name
SCHEDULER_FUNCTION=$(terraform output -raw scheduler_lambda_name)

# Manually invoke scheduler
aws lambda invoke \
  --function-name $SCHEDULER_FUNCTION \
  --payload '{}' \
  response.json

# Check response
cat response.json
```

**Within 1-2 minutes**, you should receive an email with:
- Current coverage percentage
- Target coverage
- Recommended purchase details (or "No action needed" if coverage is already sufficient)
- **[DRY RUN]** notice (since `dry_run = true`)

### Step 7: Review Email and Next Steps

**If you received the dry-run email successfully:**

✅ **Deployment complete!** The module is working correctly.

**What happens next:**

- **Scheduler** runs on 1st of month (or your configured schedule)
- Sends email with recommendations
- In dry-run mode: **No purchases made** (email only)
- When `dry_run = false`: Queues purchases to SQS for review

**To enable real purchases:**

1. Review dry-run emails for 2-3 cycles (2-3 months)
2. Verify recommendations align with your expectations
3. Update configuration:
   ```hcl
   dry_run = false  # Enable actual purchases
   ```
4. Apply changes:
   ```bash
   terraform apply
   ```

**Next scheduled run:** Check your `scheduler_schedule` (default: 1st of month, 8:00 AM UTC)

---

### Configuration Examples

For more advanced configurations, see the examples below:

#### Database-Only Deployment

For organizations that only want Database Savings Plans automation:

```hcl
module "database_savings_plans" {
  source = "github.com/your-org/terraform-aws-sp-autopilot"

  # Database SP only
  enable_compute_sp  = false
  enable_database_sp = true

  # Lower coverage target for databases (more conservative)
  coverage_target_percent = 70
  max_coverage_cap        = 80

  # Smaller purchase increments for DB workloads
  max_purchase_percent = 5

  # Notifications to database team
  notification_emails = ["database-ops@example.com"]

  dry_run = false
}
```

#### Gradual Rollout Strategy

For risk-averse deployments:

```hcl
# Week 1: Dry-run mode (email recommendations only)
module "savings_plans" {
  source = "github.com/your-org/terraform-aws-sp-autopilot"

  enable_compute_sp  = true
  enable_database_sp = true

  coverage_target_percent = 70   # Start conservative
  max_coverage_cap        = 75   # Low ceiling
  max_purchase_percent    = 5    # Small increments

  notification_emails = ["finops@example.com"]

  dry_run = true  # Week 1: Review recommendations only
}

# Week 2-4: Enable purchases with conservative limits
# (Uncomment and apply after reviewing dry-run emails)
# dry_run = false
# coverage_target_percent = 75
# max_purchase_percent = 7

# Month 2+: Increase targets as confidence grows
# coverage_target_percent = 85
# max_purchase_percent = 10
```

## Configuration Variables

### Savings Plan Types

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `enable_compute_sp` | `bool` | `true` | Enable Compute Savings Plans automation |
| `enable_database_sp` | `bool` | `false` | Enable Database Savings Plans automation<br/>**Covers:** RDS, Aurora, DynamoDB, ElastiCache (Valkey), DocumentDB, Neptune, Keyspaces, Timestream, DMS<br/>**AWS Constraints:** 1-year term and No Upfront payment (not configurable) |

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
| `database_sp_term` | `string` | `"ONE_YEAR"` | **⚠️ Fixed AWS constraint** — Must be `ONE_YEAR` (validation only) |
| `database_sp_payment_option` | `string` | `"NO_UPFRONT"` | **⚠️ Fixed AWS constraint** — Must be `NO_UPFRONT` (validation only) |

> **⚠️ AWS Constraints:** Database Savings Plans ALWAYS use 1-year terms and No Upfront payment. These variables exist only for validation and cannot be changed to other values.

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

## AWS Constraints for Database Savings Plans

Database Savings Plans have restrictions imposed by AWS that differ from Compute Savings Plans:

| Constraint | Compute SP | Database SP |
|------------|------------|-------------|
| **Term Options** | 1-year or 3-year | **1-year only** |
| **Payment Options** | All Upfront, Partial Upfront, No Upfront | **No Upfront only** |
| **Configurability** | Fully configurable | Fixed (not configurable) |

This module enforces these constraints through Terraform validation. Attempting to set invalid values will fail at plan time:

```hcl
# ❌ This will FAIL validation:
database_sp_term = "THREE_YEAR"  # Error: must be ONE_YEAR

# ❌ This will FAIL validation:
database_sp_payment_option = "ALL_UPFRONT"  # Error: must be NO_UPFRONT

# ✅ This is correct (uses defaults):
enable_database_sp = true  # Automatically uses ONE_YEAR and NO_UPFRONT
```

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

### Example Email Notification

When both SP types are enabled, emails will show:

```
=== Compute Savings Plans ===
Current Coverage: 85.2%
Target Coverage: 90.0%
Coverage Gap: 4.8%
Recommended Purchase: $5.50/hour (1-year and 3-year mix)

=== Database Savings Plans ===
Current Coverage: 72.3%
Target Coverage: 90.0%
Coverage Gap: 17.7%
Recommended Purchase: $8.25/hour (1-year, No Upfront)
```

This separation ensures that:
- Database coverage doesn't affect Compute SP purchasing decisions
- You can have different coverage levels for each workload type
- You can enable/disable each SP type independently without affecting the other

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

### Example Output Usage

```hcl
output "database_sp_status" {
  value = module.savings_plans.database_sp_configuration
}

# Output:
# {
#   enabled = true
#   term = "ONE_YEAR"
#   payment_option = "NO_UPFRONT"
#   supported_services = ["RDS", "Aurora", "DynamoDB", "ElastiCache (Valkey)", ...]
#   aws_constraints = {
#     term_fixed = "ONE_YEAR only"
#     payment_option_fixed = "NO_UPFRONT only"
#     configurable = false
#   }
# }
```

## Advanced Usage

### Database-Only Deployment

For organizations that only want Database Savings Plans automation:

```hcl
module "database_savings_plans" {
  source = "github.com/your-org/terraform-aws-sp-autopilot"

  # Database SP only
  enable_compute_sp  = false
  enable_database_sp = true

  # Lower coverage target for databases (more conservative)
  coverage_target_percent = 70
  max_coverage_cap        = 80

  # Smaller purchase increments for DB workloads
  max_purchase_percent = 5

  # Notifications to database team
  notification_emails = ["database-ops@example.com"]

  dry_run = false
}
```

### Gradual Rollout Strategy

1. **Start with Dry Run (Week 1)**
   ```hcl
   dry_run = true
   enable_database_sp = true
   ```
   Review email recommendations without purchasing

2. **Enable Purchases with Conservative Limits (Week 2-4)**
   ```hcl
   dry_run = false
   coverage_target_percent = 70
   max_purchase_percent = 5
   ```
   Make small purchases, monitor results

3. **Increase Targets (Month 2+)**
   ```hcl
   coverage_target_percent = 90
   max_purchase_percent = 10
   ```
   Scale up as confidence grows

### Canceling Purchases

To cancel a scheduled purchase before it executes:

1. Navigate to AWS Console → SQS → Select queue `sp-autopilot-purchase-intents`
2. View messages in queue
3. Delete messages for purchases you want to cancel
4. Purchaser Lambda will skip deleted messages

**Note:** This must be done between scheduler run and purchaser run (during review window).

## Frequently Asked Questions (FAQ)

### 1. How much does this module cost to run?

**AWS costs consist of:**
- **Lambda execution:** ~$0.20/month (based on 2 invocations per month with default memory/timeout)
- **SQS requests:** ~$0.01/month (minimal queue operations)
- **SNS notifications:** ~$0.01/month for email delivery
- **CloudWatch Logs:** ~$0.50-$2/month depending on retention settings

**Total infrastructure cost: ~$1-$3/month**

This is negligible compared to Savings Plans savings (typically thousands of dollars per month). The module does **not** charge any fees — it only automates AWS native Savings Plans purchases that you would make manually anyway.

**Important:** The actual Savings Plans commitments you purchase will appear on your AWS bill as separate line items (e.g., "$500/month for 1-year Compute SP"). These are the actual savings commitments, not the module's cost.

### 2. What are good coverage target percentages to start with?

**Recommended starting configuration:**

```hcl
coverage_target_percent = 70   # Start conservative
max_coverage_cap        = 80   # Prevent over-commitment
max_purchase_percent    = 5    # Small incremental purchases
dry_run                 = true # Test first!
```

**Coverage strategy by workload stability:**

- **Stable workloads (production, steady traffic):** 85-90% target, 95% cap
- **Growing workloads (scaling up):** 70-80% target, 85% cap
- **Variable workloads (dev/test, seasonal):** 50-60% target, 70% cap
- **New deployments (< 3 months old):** 40-50% target, 60% cap

**Why not 100% coverage?**
- Leave headroom for usage spikes and growth
- On-demand pricing provides flexibility for variable portions of workload
- Avoid over-commitment if usage decreases

**Gradual approach:** Start at 70%, monitor for 2-3 months, then increase to 85-90% as confidence grows.

### 3. What's the difference between Compute and Database Savings Plans?

| Aspect | Compute Savings Plans | Database Savings Plans |
|--------|----------------------|------------------------|
| **Services Covered** | EC2, Lambda, Fargate | RDS, Aurora, DynamoDB, ElastiCache, DocumentDB, Neptune, Keyspaces, Timestream, DMS |
| **Flexibility** | Covers any instance family, size, region, OS, tenancy | Covers specific database services only |
| **Term Options** | 1-year or 3-year (configurable mix) | 1-year only (AWS constraint) |
| **Payment Options** | All Upfront, Partial Upfront, No Upfront | No Upfront only (AWS constraint) |
| **Max Discount** | Up to 66% vs On-Demand | Up to 35% (serverless), 20% (provisioned) |
| **Configuration** | Fully customizable term mix and payment | Fixed AWS constraints |
| **Coverage Tracking** | Independent | Independent (separate from Compute) |

**Key takeaway:** Both SP types are tracked **separately** by this module. You can enable one, both, or neither. Each works toward the same `coverage_target_percent` but independently.

**Which should I use?**
- **Compute SP:** If you run EC2, Lambda, or Fargate workloads
- **Database SP:** If you run RDS, Aurora, DynamoDB, or other AWS database services
- **Both:** Most organizations benefit from enabling both (recommended)

### 4. How does dry-run mode work?

**Dry-run mode (`dry_run = true`) is the safest way to test the module:**

**What happens in dry-run mode:**
1. Scheduler Lambda runs on schedule
2. Analyzes current coverage and calculates recommendations
3. Sends email with detailed purchase recommendations
4. **Does NOT queue purchases to SQS**
5. **Does NOT make any actual purchases**
6. Purchaser Lambda runs but finds no messages (no action)

**What you get:**
- Full visibility into what the module *would* purchase
- Coverage analysis and gap calculations
- Cost projections and commitment details
- Zero financial risk

**Recommended workflow:**
```hcl
# Week 1: Enable dry-run, review emails
dry_run = true

# Week 2-3: Disable dry-run, monitor small purchases
dry_run = false
max_purchase_percent = 5  # Start small

# Month 2+: Increase purchase limits as confidence grows
max_purchase_percent = 10
```

**When to disable dry-run:** After reviewing 2-3 email recommendations and confirming they align with your expectations.

### 5. How does the human review window work?

**The review window is the time gap between scheduler and purchaser runs:**

**Default configuration:**
```hcl
scheduler_schedule = "cron(0 8 1 * ? *)"  # 1st of month at 8:00 AM UTC
purchaser_schedule = "cron(0 8 4 * ? *)"  # 4th of month at 8:00 AM UTC
# Review window: 3 days
```

**How it works:**

1. **Day 1 (8:00 AM UTC):** Scheduler runs
   - Analyzes usage and calculates purchases
   - Queues purchase intents to SQS
   - Sends email notification with purchase details

2. **Days 1-3:** Human review period
   - Review the email notification
   - Navigate to SQS console if you want to cancel
   - Delete messages from queue to cancel specific purchases
   - Messages remain in queue if no action taken (purchases will proceed)

3. **Day 4 (8:00 AM UTC):** Purchaser runs
   - Processes remaining messages in queue
   - Validates purchases won't exceed `max_coverage_cap`
   - Executes approved purchases
   - Sends confirmation email

**To cancel a purchase during review window:**
```bash
# Via AWS Console:
AWS Console → SQS → sp-autopilot-purchase-intents → Receive messages → Delete

# Via AWS CLI:
aws sqs receive-message --queue-url <queue-url> --max-number-of-messages 10
aws sqs delete-message --queue-url <queue-url> --receipt-handle <receipt-handle>
```

**To remove review window (immediate purchases):**
```hcl
# Set both to same schedule
scheduler_schedule = "cron(0 8 1 * ? *)"
purchaser_schedule = "cron(0 8 1 * ? *)"
```

**Not recommended for production** — always maintain at least a 1-2 day review window.

### 6. Can I use this with AWS Organizations and multiple accounts?

**Yes, this module supports AWS Organizations with cross-account role assumption:**

**Deployment options:**

**Option 1: Deploy in Management Account (Recommended for Organization-level SPs)**
```hcl
# Deploy module directly in AWS Organizations management account
# Purchases apply to entire Organization
module "savings_plans" {
  source = "github.com/your-org/terraform-aws-sp-autopilot"

  enable_compute_sp  = true
  enable_database_sp = true

  coverage_target_percent = 90
  notification_emails = ["finops-team@example.com"]
}
```

**Option 2: Deploy in Member Account with Cross-Account Role**
```hcl
# Deploy in member account, assume role in management account
module "savings_plans" {
  source = "github.com/your-org/terraform-aws-sp-autopilot"

  management_account_role_arn = "arn:aws:iam::123456789012:role/SavingsPlansAutomationRole"

  enable_compute_sp  = true
  enable_database_sp = true
}
```

**Cross-account IAM role (in management account):**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ce:GetSavingsPlansCoverage",
        "ce:GetSavingsPlansPurchaseRecommendation",
        "savingsplans:CreateSavingsPlan",
        "savingsplans:DescribeSavingsPlans"
      ],
      "Resource": "*"
    }
  ]
}
```

**Trust relationship:**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::MEMBER-ACCOUNT-ID:role/sp-autopilot-scheduler-role"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
```

**Multi-account considerations:**
- Organization-level Savings Plans provide maximum flexibility (apply to all accounts)
- Single account SPs only apply to that specific account
- Coverage calculations differ between Organization-level and single-account
- Stagger schedules across accounts to avoid API throttling

### 7. How do I cancel purchases that are already scheduled?

**To cancel scheduled purchases BEFORE they execute:**

**Method 1: AWS Console (Easiest)**
1. Navigate to **AWS Console** → **SQS**
2. Select queue: `sp-autopilot-purchase-intents`
3. Click **"Send and receive messages"**
4. Click **"Poll for messages"**
5. Review messages — each contains purchase details (commitment, term, type)
6. Select messages you want to cancel
7. Click **"Delete"**

**Method 2: AWS CLI**
```bash
# View messages without deleting (inspect first)
aws sqs receive-message \
  --queue-url https://sqs.us-east-1.amazonaws.com/123456789012/sp-autopilot-purchase-intents \
  --max-number-of-messages 10 \
  --visibility-timeout 0

# Delete specific message to cancel purchase
aws sqs delete-message \
  --queue-url https://sqs.us-east-1.amazonaws.com/123456789012/sp-autopilot-purchase-intents \
  --receipt-handle <receipt-handle-from-above>

# Purge entire queue (cancel ALL scheduled purchases)
aws sqs purge-queue \
  --queue-url https://sqs.us-east-1.amazonaws.com/123456789012/sp-autopilot-purchase-intents
```

**Important timing:**
- **Can cancel:** Between scheduler run and purchaser run (review window)
- **Cannot cancel:** After purchaser has processed the message and created the Savings Plan
- **AWS Savings Plans are commitments:** Once purchased, they cannot be canceled or refunded

**Preventing unwanted purchases:**
1. Start with `dry_run = true` to review recommendations first
2. Use conservative `max_purchase_percent` (e.g., 5-10%)
3. Maintain a reasonable review window (3-7 days recommended)
4. Monitor email notifications closely during first few cycles

### 8. Can I customize the schedule for my organization?

**Yes, both scheduler and purchaser schedules are fully customizable using EventBridge cron expressions:**

**Common scheduling patterns:**

**Monthly (Default):**
```hcl
scheduler_schedule = "cron(0 8 1 * ? *)"   # 1st of month, 8:00 AM UTC
purchaser_schedule = "cron(0 8 4 * ? *)"   # 4th of month, 8:00 AM UTC
# Review window: 3 days
```

**Bi-weekly:**
```hcl
scheduler_schedule = "cron(0 8 1,15 * ? *)"  # 1st and 15th of month
purchaser_schedule = "cron(0 8 3,17 * ? *)"  # 3rd and 17th of month
# Review window: 2 days, twice per month
```

**Weekly:**
```hcl
scheduler_schedule = "cron(0 8 ? * MON *)"   # Every Monday
purchaser_schedule = "cron(0 8 ? * WED *)"   # Every Wednesday
# Review window: 2 days
```

**Immediate purchases (no review window):**
```hcl
scheduler_schedule = "cron(0 8 1 * ? *)"     # 1st of month
purchaser_schedule = "cron(0 8 1 * ? *)"     # Same time as scheduler
# Review window: 0 (not recommended for production)
```

**Timezone considerations:**
```hcl
# EventBridge cron uses UTC timezone
# Convert your local time to UTC:

# 9:00 AM EST = 14:00 UTC
scheduler_schedule = "cron(0 14 1 * ? *)"

# 6:00 AM PST = 14:00 UTC
scheduler_schedule = "cron(0 14 1 * ? *)"
```

**EventBridge cron format:**
```
cron(Minutes Hours Day-of-month Month Day-of-week Year)

Examples:
cron(0 8 1 * ? *)        → 1st of month at 8:00 AM UTC
cron(0 8 ? * MON *)      → Every Monday at 8:00 AM UTC
cron(0 14 1,15 * ? *)    → 1st and 15th at 2:00 PM UTC
cron(0 8 L * ? *)        → Last day of month at 8:00 AM UTC
```

**Best practices:**
- **Monthly purchases:** Sufficient for most organizations (default recommendation)
- **Maintain review window:** 2-3 days minimum for human oversight
- **Avoid weekends:** Schedule for weekdays when teams are available to review
- **Stagger across accounts:** Prevent API throttling by scheduling different accounts on different days

**Testing schedules:**
```bash
# Manually trigger scheduler (doesn't wait for schedule)
aws lambda invoke \
  --function-name sp-autopilot-scheduler \
  --payload '{}' \
  response.json

# Manually trigger purchaser
aws lambda invoke \
  --function-name sp-autopilot-purchaser \
  --payload '{}' \
  response.json
```

### 9. How do I set up email notifications?

**Email notifications are sent via AWS SNS and require subscription confirmation:**

**Step 1: Configure emails in Terraform**
```hcl
module "savings_plans" {
  source = "github.com/your-org/terraform-aws-sp-autopilot"

  notification_emails = [
    "devops@example.com",
    "finops@example.com",
    "cloud-team@example.com"
  ]

  # ... other configuration
}
```

**Step 2: Apply Terraform**
```bash
terraform apply
```

**Step 3: Confirm subscriptions**
Each email address will receive an **"AWS Notification - Subscription Confirmation"** email:
1. Check inbox (and spam folder!)
2. Click **"Confirm subscription"** link in email
3. You'll see "Subscription confirmed!" in browser

**Step 4: Verify subscriptions**
```bash
# Check SNS topic subscriptions
aws sns list-subscriptions-by-topic \
  --topic-arn $(terraform output -raw sns_topic_arn)

# Should show status: "Confirmed" (not "PendingConfirmation")
```

**Email notification triggers:**

| Event | When Sent | Contains |
|-------|-----------|----------|
| **Scheduler Success** | After scheduler analyzes coverage | Current coverage, recommendations, purchase details (or dry-run notice) |
| **Scheduler No Action** | When coverage already meets target | Coverage status, no purchases needed |
| **Purchaser Success** | After purchases complete | Aggregated summary of all purchases made, final coverage |
| **Purchaser Skipped** | When validation prevents purchase | Reason for skip (e.g., would exceed cap) |
| **Lambda Error** | On any Lambda failure | Error details and stack trace |

**Email content example (scheduler):**
```
Subject: [SP Autopilot] Savings Plans Scheduled for Purchase

=== Compute Savings Plans ===
Current Coverage: 85.2%
Target Coverage: 90.0%
Coverage Gap: 4.8%
Recommended Purchase: $5.50/hour

Purchase Details:
- 3-year term: $3.67/hour (All Upfront: $32,164)
- 1-year term: $1.83/hour (All Upfront: $16,033)

Scheduled for purchase on: 2026-01-04 08:00 UTC
To cancel: Delete messages from SQS queue before purchaser runs
```

**Troubleshooting notifications:**

**Not receiving emails?**
1. Check spam/junk folder
2. Verify subscription confirmed (not pending)
3. Test SNS manually:
   ```bash
   aws sns publish \
     --topic-arn <sns-topic-arn> \
     --subject "Test" \
     --message "Test notification"
   ```
4. Check Lambda logs for SNS publish errors

**Suppress "no action" emails:**
```hcl
send_no_action_email = false  # Only send when purchases are needed
```

**Add more recipients later:**
```bash
# Subscribe additional email manually
aws sns subscribe \
  --topic-arn <sns-topic-arn> \
  --protocol email \
  --notification-endpoint new-user@example.com
```

### 10. What IAM permissions are required?

**The module automatically creates IAM roles with necessary permissions, but here's what's required:**

**Scheduler Lambda requires:**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "CostExplorerAccess",
      "Effect": "Allow",
      "Action": [
        "ce:GetSavingsPlansCoverage",
        "ce:GetSavingsPlansPurchaseRecommendation"
      ],
      "Resource": "*"
    },
    {
      "Sid": "SavingsPlansRead",
      "Effect": "Allow",
      "Action": [
        "savingsplans:DescribeSavingsPlans"
      ],
      "Resource": "*"
    },
    {
      "Sid": "SQSQueueAccess",
      "Effect": "Allow",
      "Action": [
        "sqs:SendMessage",
        "sqs:PurgeQueue",
        "sqs:GetQueueAttributes"
      ],
      "Resource": "arn:aws:sqs:*:*:sp-autopilot-purchase-intents"
    },
    {
      "Sid": "SNSPublish",
      "Effect": "Allow",
      "Action": ["sns:Publish"],
      "Resource": "arn:aws:sns:*:*:sp-autopilot-notifications"
    }
  ]
}
```

**Purchaser Lambda requires:**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "SavingsPlansWrite",
      "Effect": "Allow",
      "Action": [
        "savingsplans:CreateSavingsPlan",
        "savingsplans:DescribeSavingsPlans"
      ],
      "Resource": "*"
    },
    {
      "Sid": "CostExplorerCoverage",
      "Effect": "Allow",
      "Action": ["ce:GetSavingsPlansCoverage"],
      "Resource": "*"
    },
    {
      "Sid": "SQSQueueAccess",
      "Effect": "Allow",
      "Action": [
        "sqs:ReceiveMessage",
        "sqs:DeleteMessage",
        "sqs:GetQueueAttributes"
      ],
      "Resource": [
        "arn:aws:sqs:*:*:sp-autopilot-purchase-intents",
        "arn:aws:sqs:*:*:sp-autopilot-purchase-intents-dlq"
      ]
    },
    {
      "Sid": "SNSPublish",
      "Effect": "Allow",
      "Action": ["sns:Publish"],
      "Resource": "arn:aws:sns:*:*:sp-autopilot-notifications"
    }
  ]
}
```

**For AWS Organizations (cross-account):**

**In member account (where module is deployed):**
```json
{
  "Sid": "AssumeManagementAccountRole",
  "Effect": "Allow",
  "Action": "sts:AssumeRole",
  "Resource": "arn:aws:iam::MGMT-ACCOUNT-ID:role/SavingsPlansAutomationRole"
}
```

**In management account (trusted role):**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ce:GetSavingsPlansCoverage",
        "ce:GetSavingsPlansPurchaseRecommendation",
        "savingsplans:CreateSavingsPlan",
        "savingsplans:DescribeSavingsPlans"
      ],
      "Resource": "*"
    }
  ]
}
```

**Trust policy (management account role):**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::MEMBER-ACCOUNT-ID:role/sp-autopilot-scheduler-role"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
```

**Additional CloudWatch Logs permissions (automatic):**
```json
{
  "Sid": "CloudWatchLogs",
  "Effect": "Allow",
  "Action": [
    "logs:CreateLogGroup",
    "logs:CreateLogStream",
    "logs:PutLogEvents"
  ],
  "Resource": "arn:aws:logs:*:*:log-group:/aws/lambda/sp-autopilot-*"
}
```

**Security best practices:**
- ✅ Module uses least-privilege IAM policies (only necessary permissions)
- ✅ No broad wildcards on sensitive actions
- ✅ SQS and SNS resources scoped to module-created resources
- ✅ Supports AWS Organizations cross-account roles (not cross-account keys)
- ✅ No hardcoded credentials (uses IAM roles exclusively)

**Viewing actual IAM policies:**
```bash
# Get scheduler role name
aws lambda get-function --function-name sp-autopilot-scheduler \
  --query 'Configuration.Role' --output text

# List attached policies
aws iam list-attached-role-policies --role-name <role-name>

# View inline policy
aws iam get-role-policy --role-name <role-name> --policy-name <policy-name>
```

### 11. What happens if my usage drops and I'm over-committed?

**The module includes protection mechanisms to prevent over-commitment:**

**Max Coverage Cap Protection:**
```hcl
coverage_target_percent = 90  # Try to reach this level
max_coverage_cap        = 95  # NEVER exceed this level
```

**How it works:**

1. **Scheduler calculates** purchases based on current usage (Day 1)
2. **Usage decreases** between scheduler and purchaser (Days 1-4)
3. **Purchaser validates** before executing:
   ```
   Projected Coverage = Current Coverage + New Purchase

   IF Projected Coverage > max_coverage_cap:
     Skip purchase (send email explaining why)
   ELSE:
     Execute purchase
   ```

**Example scenario:**
```
Day 1 (Scheduler):
- Current usage: $10,000/month
- Current coverage: 85%
- Scheduler calculates: Purchase $5/hour to reach 90%

Day 2-3 (Review Window):
- Usage drops to $8,000/month (services scaled down)

Day 4 (Purchaser):
- Recalculates: Current coverage now 88% (existing SPs didn't change)
- Projects: 88% + new purchase = 96% coverage
- Decision: 96% > max_coverage_cap (95%) → SKIP PURCHASE
- Sends email: "Purchase skipped - would exceed max coverage cap"
```

**Additional protections:**

**Gradual purchases:**
```hcl
max_purchase_percent = 10  # Only buy 10% of monthly spend per cycle
```
This spreads commitments over time (takes 5-6 months to reach 90% from 0%).

**Expiring plans exclusion:**
```hcl
renewal_window_days = 7  # Plans expiring within 7 days excluded from coverage
```
Forces renewal of expiring plans, prevents coverage gaps.

**What if you're already over-committed?**
- Module will **NOT** purchase additional plans
- Existing plans will naturally expire over time (1-year or 3-year terms)
- Continue running module — it will resume purchases when coverage drops below target
- Monitor emails for "No action needed - coverage above target" notifications

**Manual intervention (if needed):**
```bash
# List active Savings Plans
aws savingsplans describe-savings-plans \
  --filters name=state,values=active \
  --query 'savingsPlans[*].[savingsPlanId,end,commitment]' \
  --output table

# Savings Plans cannot be canceled, but you can:
# 1. Wait for 1-year plans to expire
# 2. Reduce usage (right-size resources)
# 3. Temporarily disable module (set dry_run=true)
```

**Best practice:** Start with conservative targets (70-80%) and gradually increase as usage patterns stabilize.

### 12. How do I know if the module is working correctly?

**Monitoring and verification checklist:**

**1. Check Email Notifications**
- Scheduler should send email after each run (monthly by default)
- Email shows current coverage, target, and recommendations
- Purchaser sends confirmation email after executing purchases

**2. Verify CloudWatch Logs**
```bash
# View scheduler logs
aws logs tail /aws/lambda/sp-autopilot-scheduler --follow

# View purchaser logs
aws logs tail /aws/lambda/sp-autopilot-purchaser --follow

# Search for errors
aws logs filter-log-events \
  --log-group-name /aws/lambda/sp-autopilot-scheduler \
  --filter-pattern "ERROR"
```

**3. Monitor SQS Queue**
```bash
# Check queue depth (should be 0 after purchaser runs)
aws sqs get-queue-attributes \
  --queue-url $(terraform output -raw queue_url) \
  --attribute-names ApproximateNumberOfMessages

# Check Dead Letter Queue (should always be 0)
aws sqs get-queue-attributes \
  --queue-url $(terraform output -raw dlq_url) \
  --attribute-names ApproximateNumberOfMessages
```

**4. Verify Savings Plans Purchases**
```bash
# List recent Savings Plans (sorted by start date)
aws savingsplans describe-savings-plans \
  --filters name=state,values=active \
  --query 'reverse(sort_by(savingsPlans, &start))[:5].[start,commitment,savingsPlanType]' \
  --output table

# Check if new plans were created today
aws savingsplans describe-savings-plans \
  --filters name=state,values=active \
  --query "savingsPlans[?starts_with(start,'$(date -I)')].{ID:savingsPlanId,Commitment:commitment,Type:savingsPlanType}" \
  --output table
```

**5. Monitor CloudWatch Alarms**
```bash
# Check alarm status
aws cloudwatch describe-alarms \
  --alarm-name-prefix sp-autopilot \
  --query 'MetricAlarms[*].[AlarmName,StateValue]' \
  --output table

# Should show:
# sp-autopilot-scheduler-errors    OK
# sp-autopilot-purchaser-errors    OK
# sp-autopilot-dlq-depth          OK
```

**6. Validate Coverage Trends**
```bash
# Get coverage over last 30 days
aws ce get-savings-plans-coverage \
  --time-period Start=$(date -d '30 days ago' -I),End=$(date -I) \
  --granularity DAILY \
  --group-by Type=DIMENSION,Key=SAVINGS_PLAN_TYPE
```

**7. Review Terraform Outputs**
```bash
terraform output module_configuration
terraform output database_sp_configuration
```

**Success indicators:**
- ✅ Email received after each scheduler run
- ✅ Coverage gradually increases toward target over time
- ✅ New Savings Plans appear in AWS console
- ✅ No errors in CloudWatch Logs
- ✅ Queue depth returns to 0 after purchaser runs
- ✅ CloudWatch alarms remain in OK state

**Warning signs:**
- ⚠️ No emails received (check SNS subscriptions)
- ⚠️ Coverage not increasing (check logs for recommendations)
- ⚠️ Errors in CloudWatch Logs (check IAM permissions)
- ⚠️ Messages stuck in queue (check purchaser Lambda)
- ⚠️ Alarms in ALARM state (investigate specific failure)

**Testing in dry-run mode:**
```hcl
dry_run = true  # Safe to test — no purchases made

# Expected behavior:
# 1. Scheduler sends email with recommendations
# 2. No messages queued to SQS
# 3. Purchaser runs but finds no work
# 4. Zero Savings Plans purchased (as expected)
```

**First month after deployment:**
1. Week 1: Dry-run mode, review email recommendations
2. Week 2: Disable dry-run, wait for first scheduler run
3. Week 3: Review queued purchases in SQS, optionally cancel
4. Week 4: Verify purchaser executed and Savings Plans created
5. Month 2: Monitor coverage increase, verify costs on bill

**Ongoing monitoring:**
- Set up SNS email notifications (already configured)
- Review scheduler emails monthly
- Check CloudWatch dashboards for Lambda metrics
- Verify Savings Plans purchases in AWS Console monthly
- Monitor AWS Cost Explorer for coverage trends

## Requirements

- **Terraform**: >= 1.0
- **AWS Provider**: >= 5.0
- **IAM Permissions**: Lambda functions require permissions for:
  - Cost Explorer API (GetSavingsPlansPurchaseRecommendation)
  - Savings Plans API (CreateSavingsPlan, DescribeSavingsPlans)
  - SQS (SendMessage, ReceiveMessage, DeleteMessage, PurgeQueue)
  - SNS (Publish)
  - CloudWatch Logs (for Lambda logging)

## CI/CD Pipeline

This module uses GitHub Actions for continuous integration and deployment, ensuring code quality, security, and reliability.

### Automated Workflows

#### 🔍 PR Checks (`pr-checks.yml`)

Comprehensive validation for all pull requests:

- **Terraform Validation** — Runs `terraform fmt -check` and `terraform validate` on all `.tf` and `.tfvars` files
- **Security Scanning** — Executes tfsec to identify HIGH and CRITICAL security issues
- **Lambda Testing** — Runs pytest with 80% code coverage requirement for scheduler Lambda and integration tests for purchaser Lambda
- **Smart Triggers** — Only runs relevant jobs based on changed files (Terraform changes trigger validation/security, Python changes trigger tests)
- **PR Comments** — Automatically comments on PRs with detailed failure information

**Triggers:** All pull requests to `main` or `develop` branches

#### ✅ Terraform Validation (`terraform-validation.yml`)

Validates Terraform configuration integrity:

- **Format Check** — Ensures consistent code formatting across all Terraform files
- **Initialization** — Validates module can be initialized (backend-less mode for CI)
- **Validation** — Checks syntax, references, and configuration validity
- **PR Feedback** — Comments on pull requests with validation results

**Triggers:** Push/PR on `.tf` or `.tfvars` files, manual workflow dispatch

#### 🧪 Python Tests (`tests.yml`)

Comprehensive testing for Lambda functions:

- **Scheduler Lambda Tests** — Runs pytest with coverage analysis (minimum 80% coverage required)
- **Purchaser Lambda Tests** — Executes integration tests for purchase workflow validation
- **Dependency Caching** — Uses pip cache for faster test execution
- **Coverage Reporting** — Displays line-by-line coverage with `--cov-report=term-missing`
- **PR Feedback** — Comments on PRs when tests fail or coverage drops below threshold

**Triggers:** Push/PR on `lambda/**/*.py` files, manual workflow dispatch

#### 🔒 Security Scan (`security-scan.yml`)

Automated security analysis with tfsec:

- **tfsec Analysis** — Scans Terraform code for security vulnerabilities and misconfigurations
- **Severity Filtering** — Enforces minimum severity of HIGH (fails on HIGH or CRITICAL issues)
- **SARIF Integration** — Uploads results to GitHub Security tab for tracking
- **Security Recommendations** — Provides actionable fixes in PR comments (encryption, security groups, logging)
- **Always Reports** — Uploads SARIF results even on failures for comprehensive security tracking

**Triggers:** Push/PR on `.tf` or `.tfvars` files, manual workflow dispatch

#### 🚀 Release Management (`release.yml`)

Automated semantic versioning and release creation:

- **Release Please** — Uses Google's release-please-action for automated releases
- **Conventional Commits** — Parses commit messages to determine version bumps and generate changelogs
- **Version Tagging** — Creates semantic version tags (e.g., `v1.2.3`) plus major (`v1`) and minor (`v1.2`) tags for flexible module pinning
- **Release Notes** — Auto-generates comprehensive release notes from commit history
- **Terraform Module Type** — Configured specifically for Terraform module release patterns

**Triggers:** Push to `main` branch (after PR merge), manual workflow dispatch

**Version Tag Strategy:**
- Full version: `v1.2.3` (exact version)
- Minor version: `v1.2` (latest patch for minor version) — **Recommended for production**
- Major version: `v1` (latest minor/patch for major version) — Use with caution

### Workflow Integration

The CI/CD pipeline follows this flow:

```
Pull Request Created
       │
       ├─► PR Checks (all validations)
       │   ├─► Terraform validation
       │   ├─► Security scanning (tfsec)
       │   └─► Lambda tests (if Python changed)
       │
       ├─► Individual workflow triggers
       │   ├─► Terraform Validation (on .tf changes)
       │   ├─► Security Scan (on .tf changes)
       │   └─► Python Tests (on .py changes)
       │
       ▼
   All Checks Pass ✅
       │
       ▼
   PR Merged to main
       │
       ▼
   Release Please Workflow
       │
       ├─► Analyzes commits
       ├─► Creates/Updates Release PR
       │   (if unreleased changes exist)
       │
       └─► On Release PR Merge:
           ├─► Creates GitHub Release
           ├─► Tags version (v1.2.3, v1.2, v1)
           └─► Generates changelog
```

### Quality Gates

All PRs must pass these gates before merging:

| Check | Requirement | Enforced By |
|-------|-------------|-------------|
| **Terraform Format** | All `.tf` files must be formatted with `terraform fmt` | `terraform-validation.yml` |
| **Terraform Validation** | Module must pass `terraform validate` | `terraform-validation.yml` |
| **Security Scan** | No HIGH or CRITICAL security issues | `security-scan.yml` |
| **Scheduler Tests** | All tests pass with ≥80% code coverage | `tests.yml` |
| **Purchaser Tests** | All integration tests pass | `tests.yml` |

### Running Workflows Manually

All workflows support manual triggering via `workflow_dispatch`:

```bash
# Via GitHub UI
Actions → Select Workflow → Run workflow

# Via GitHub CLI
gh workflow run terraform-validation.yml
gh workflow run tests.yml
gh workflow run security-scan.yml
gh workflow run pr-checks.yml
gh workflow run release.yml
```

### Local Development Validation

Run these commands locally before pushing to avoid CI failures:

```bash
# Terraform validation
terraform fmt -recursive
terraform init -backend=false
terraform validate

# Security scanning
docker run --rm -v $(pwd):/src aquasec/tfsec:latest /src --minimum-severity HIGH

# Python tests (scheduler)
cd lambda/scheduler
pip install -r requirements.txt
pytest -v --cov=. --cov-report=term-missing --cov-fail-under=80

# Python tests (purchaser)
cd lambda/purchaser
pip install -r requirements.txt
python test_integration.py
```

## License

This module is open-source software licensed under the MIT License.

## Contributing

Contributions are welcome! Please open an issue or pull request on GitHub.

## Troubleshooting

This section provides solutions to common issues you may encounter when running the Savings Plans Autopilot module.

### Lambda Function Errors

#### Permission Errors

**Symptom:** Lambda function fails with `AccessDenied` or permission-related errors

**Common Causes:**
- Missing IAM permissions for Cost Explorer, Savings Plans, SQS, or SNS
- Cross-account role assumption failures (when using `management_account_role_arn`)
- SNS topic publish permissions missing

**Investigation:**

```bash
# Check Lambda function role permissions
aws lambda get-function --function-name <scheduler-lambda-name> \
  --query 'Configuration.Role' --output text

# Get the role's policies
aws iam list-attached-role-policies --role-name <role-name>
aws iam list-role-policies --role-name <role-name>

# View inline policy details
aws iam get-role-policy --role-name <role-name> --policy-name <policy-name>
```

**Solution:**

Ensure the Lambda execution role has the following permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ce:GetSavingsPlansCoverage",
        "ce:GetSavingsPlansPurchaseRecommendation"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "savingsplans:DescribeSavingsPlans",
        "savingsplans:CreateSavingsPlan"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "sqs:SendMessage",
        "sqs:ReceiveMessage",
        "sqs:DeleteMessage",
        "sqs:PurgeQueue",
        "sqs:GetQueueAttributes"
      ],
      "Resource": "arn:aws:sqs:*:*:sp-autopilot-*"
    },
    {
      "Effect": "Allow",
      "Action": ["sns:Publish"],
      "Resource": "arn:aws:sns:*:*:sp-autopilot-notifications"
    }
  ]
}
```

#### Timeout Errors

**Symptom:** Lambda function times out before completion

**Common Causes:**
- Large number of Savings Plans to analyze (100+ active plans)
- AWS API latency or throttling
- Insufficient timeout configuration

**Investigation:**

```bash
# Check Lambda timeout configuration
aws lambda get-function-configuration \
  --function-name <scheduler-lambda-name> \
  --query 'Timeout'

# Check CloudWatch Logs for timeout patterns
aws logs filter-log-events \
  --log-group-name /aws/lambda/<scheduler-lambda-name> \
  --filter-pattern "Task timed out" \
  --max-items 10
```

**Solution:**

Increase Lambda timeout in your Terraform configuration:

```hcl
# The module uses reasonable defaults, but you can override if needed
# Current defaults: Scheduler 300s (5 min), Purchaser 300s (5 min)
# Contact module maintainers if timeouts persist
```

#### Memory Errors

**Symptom:** Lambda function fails with out-of-memory errors

**Common Causes:**
- Processing large recommendation datasets
- Many concurrent Savings Plans
- Memory leaks in custom code (if forked)

**Investigation:**

```bash
# Check memory configuration
aws lambda get-function-configuration \
  --function-name <scheduler-lambda-name> \
  --query 'MemorySize'

# Check actual memory usage in CloudWatch
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name MemoryUtilization \
  --dimensions Name=FunctionName,Value=<scheduler-lambda-name> \
  --start-time 2026-01-01T00:00:00Z \
  --end-time 2026-01-14T23:59:59Z \
  --period 3600 \
  --statistics Maximum
```

**Solution:**

The module uses 512 MB memory by default, which should be sufficient. If issues persist, file a GitHub issue with your account details (number of active SPs, number of recommendations).

### SQS Queue Issues

#### Messages Stuck in Queue

**Symptom:** Messages remain in queue after purchaser runs, or accumulate over time

**Common Causes:**
- Purchaser Lambda failing to process messages
- Visibility timeout too short
- Dead Letter Queue not configured

**Investigation:**

```bash
# Check queue depth
aws sqs get-queue-attributes \
  --queue-url <queue-url> \
  --attribute-names ApproximateNumberOfMessages,ApproximateNumberOfMessagesNotVisible

# Check Dead Letter Queue
aws sqs get-queue-attributes \
  --queue-url <dlq-url> \
  --attribute-names ApproximateNumberOfMessages

# Receive messages without deleting (inspect only)
aws sqs receive-message \
  --queue-url <queue-url> \
  --max-number-of-messages 10 \
  --visibility-timeout 0
```

**Solution:**

1. Check CloudWatch Logs for purchaser Lambda errors
2. Manually purge queue if needed:
   ```bash
   aws sqs purge-queue --queue-url <queue-url>
   ```
3. Verify DLQ alarm is enabled (`enable_dlq_alarm = true`)

#### Duplicate Messages

**Symptom:** Same purchase intent appears multiple times in queue

**Common Causes:**
- Scheduler Lambda invoked multiple times (manual or duplicate EventBridge rules)
- SQS standard queue behavior (at-least-once delivery)

**Investigation:**

```bash
# Check EventBridge rules
aws events list-rules --name-prefix sp-autopilot

# Check rule targets
aws events list-targets-by-rule --rule sp-autopilot-scheduler

# Check scheduler invocation history
aws logs filter-log-events \
  --log-group-name /aws/lambda/<scheduler-lambda-name> \
  --filter-pattern "Purging queue" \
  --start-time $(($(date +%s) - 86400))000  # Last 24 hours
```

**Solution:**

- Purchaser uses idempotency tokens — duplicate messages won't create duplicate purchases
- Scheduler purges queue before running — clears any stale messages
- If manually testing, wait for scheduler's next purge cycle

### Notification Problems

#### Not Receiving Emails

**Symptom:** No email notifications arrive, even though Lambda succeeds

**Common Causes:**
- SNS subscription not confirmed
- Email in spam/junk folder
- SNS topic publish permissions missing
- Wrong email addresses configured

**Investigation:**

```bash
# Check SNS topic subscriptions
aws sns list-subscriptions-by-topic --topic-arn <sns-topic-arn>

# Check subscription status (should be "Confirmed", not "PendingConfirmation")
aws sns get-subscription-attributes \
  --subscription-arn <subscription-arn> \
  --query 'Attributes.PendingConfirmation'

# Test SNS publish manually
aws sns publish \
  --topic-arn <sns-topic-arn> \
  --subject "Test Notification" \
  --message "This is a test message from SP Autopilot troubleshooting"
```

**Solution:**

1. **Check spam folder** — SNS emails may be filtered
2. **Confirm subscription:**
   - Check inbox for "AWS Notification - Subscription Confirmation" email
   - Click confirmation link
   - Or use AWS CLI:
     ```bash
     # Resend confirmation
     aws sns subscribe \
       --topic-arn <sns-topic-arn> \
       --protocol email \
       --notification-endpoint your-email@example.com
     ```
3. **Verify email addresses** in Terraform configuration:
   ```hcl
   notification_emails = ["correct-email@example.com"]
   ```

#### Email Missing Expected Content

**Symptom:** Email arrives but doesn't show purchase details or coverage information

**Common Causes:**
- Dry-run mode enabled (expected behavior)
- No coverage gap (no purchases needed)
- AWS returned no recommendations

**Investigation:**

```bash
# Check dry-run configuration
aws lambda get-function-configuration \
  --function-name <scheduler-lambda-name> \
  --query 'Environment.Variables.DRY_RUN'

# Check CloudWatch Logs for coverage calculation
aws logs filter-log-events \
  --log-group-name /aws/lambda/<scheduler-lambda-name> \
  --filter-pattern "Coverage" \
  --max-items 20
```

**Solution:**

- **Dry-run mode:** Email will state `[DRY RUN]` and show recommendations without queuing
- **No gap:** Email will show coverage at or above target (no action needed)
- **No recommendations:** Check logs for "no AWS recommendation available"

### Coverage Calculation Discrepancies

#### Coverage Percentage Doesn't Match AWS Console

**Symptom:** Module reports different coverage than Cost Explorer UI

**Common Causes:**
- Different time granularity (hourly vs daily)
- Expiring plans included in console but excluded by module
- Regional differences in coverage calculation
- Separate tracking for Compute vs Database SP

**Investigation:**

```bash
# Get coverage as module sees it
aws ce get-savings-plans-coverage \
  --time-period Start=2026-01-01,End=2026-01-14 \
  --granularity DAILY \
  --group-by Type=DIMENSION,Key=SAVINGS_PLAN_TYPE

# Check active Savings Plans
aws savingsplans describe-savings-plans \
  --filters name=state,values=active \
  --query 'savingsPlans[*].[savingsPlanId,savingsPlanType,commitment,end]' \
  --output table

# Check for plans expiring soon (excluded from coverage)
aws savingsplans describe-savings-plans \
  --filters name=state,values=active \
  --query "savingsPlans[?end<'$(date -d '+7 days' -I)'].[savingsPlanId,end,commitment]" \
  --output table
```

**Solution:**

Module behavior (by design):
- Uses **hourly coverage** (more precise than daily)
- **Excludes plans expiring within `renewal_window_days`** (default 7 days) from coverage calculation
  - Forces renewal of expiring plans
  - Prevents gap when plans expire
- **Tracks Compute and Database SP separately**
  - Check email for separate coverage percentages
  - Each SP type works toward target independently

To match console behavior, set `renewal_window_days = 0`, but this is **not recommended** (may cause coverage gaps).

#### Recommendations Show Zero Commitment

**Symptom:** AWS returns recommendations but with $0.00/hour commitment

**Common Causes:**
- Insufficient usage data (less than `min_data_days`)
- Usage pattern too volatile for AWS to recommend
- All usage already covered by Reserved Instances or Savings Plans

**Investigation:**

```bash
# Check recommendation API response
aws ce get-savings-plans-purchase-recommendation \
  --savings-plans-type COMPUTE_SP \
  --lookback-period-in-days 30 \
  --payment-option ALL_UPFRONT \
  --term-in-years ONE_YEAR \
  --query 'SavingsPlansPurchaseRecommendation.SavingsPlansPurchaseRecommendationDetails[0:3]'

# Check for insufficient data message
aws logs filter-log-events \
  --log-group-name /aws/lambda/<scheduler-lambda-name> \
  --filter-pattern "insufficient data"
```

**Solution:**

- **Wait for more usage data:** Ensure at least `min_data_days` of steady usage
- **Check usage patterns:** Highly variable usage may not benefit from SPs
- **Verify SP type enabled:** Ensure `enable_compute_sp` or `enable_database_sp` is `true`
- Module filters out zero-commitment plans automatically (no action needed)

### Purchase Validation Failures

#### Purchaser Skips Valid-Looking Purchases

**Symptom:** Purchaser skips purchases with reason "Would exceed max_coverage_cap"

**Common Causes:**
- Coverage cap protection working as designed
- Usage decreased since scheduler ran
- Multiple purchases would push coverage too high

**Investigation:**

```bash
# Check purchaser logs for skip reasons
aws logs filter-log-events \
  --log-group-name /aws/lambda/<purchaser-lambda-name> \
  --filter-pattern "Skipping purchase" \
  --max-items 20

# Check current coverage at purchase time
aws logs filter-log-events \
  --log-group-name /aws/lambda/<purchaser-lambda-name> \
  --filter-pattern "projected_coverage" \
  --max-items 20
```

**Solution:**

This is **expected behavior** — the module protects against over-commitment:
- Scheduler calculates purchases based on coverage at scheduling time
- Purchaser validates purchases won't exceed `max_coverage_cap` at purchase time
- If usage decreased in the meantime, purchaser skips to prevent over-commitment

**To adjust:**
```hcl
max_coverage_cap = 95  # Increase if you want more headroom
```

#### CreateSavingsPlan API Errors

**Symptom:** Purchaser fails with AWS API errors (e.g., `InvalidParameterValue`, `LimitExceeded`)

**Common Causes:**
- Invalid offering ID (AWS changed available offerings)
- Account-level purchase limits reached
- Payment method issues (for upfront payment options)

**Investigation:**

```bash
# Check CloudWatch Logs for API error details
aws logs filter-log-events \
  --log-group-name /aws/lambda/<purchaser-lambda-name> \
  --filter-pattern "ClientError" \
  --max-items 10

# Verify offering ID is still valid
aws savingsplans describe-savings-plans-offerings \
  --offering-ids <offering-id-from-message>

# Check account limits
aws service-quotas get-service-quota \
  --service-code savingsplans \
  --quota-code L-XXXXXXXX  # Quota code for SP purchases
```

**Solution:**

1. **Invalid offering ID:** Scheduler and Purchaser may have run days apart, offerings changed
   - Reduce time between scheduler and purchaser runs
   - Delete stale messages from queue
2. **Account limits:** Contact AWS Support to increase Savings Plans purchase limits
3. **Payment issues:** Verify AWS account payment method is valid

### AWS API Throttling

#### Scheduler or Purchaser Fails with Rate Limit Errors

**Symptom:** Lambda fails with `ThrottlingException` or `TooManyRequestsException`

**Common Causes:**
- High volume of Cost Explorer API calls
- Multiple accounts/regions calling APIs simultaneously
- AWS service-side throttling during peak times

**Investigation:**

```bash
# Check for throttling errors in logs
aws logs filter-log-events \
  --log-group-name /aws/lambda/<scheduler-lambda-name> \
  --filter-pattern "ThrottlingException" \
  --start-time $(($(date +%s) - 86400))000

# Check API call frequency
aws logs filter-log-events \
  --log-group-name /aws/lambda/<scheduler-lambda-name> \
  --filter-pattern "GetSavingsPlansPurchaseRecommendation" \
  --start-time $(($(date +%s) - 3600))000 | grep -c "GetSavingsPlansPurchaseRecommendation"
```

**Solution:**

Module includes exponential backoff, but if throttling persists:

1. **Reduce call frequency:**
   - Run scheduler less frequently (e.g., monthly instead of weekly)
   - Disable one SP type if both are enabled and not needed
2. **Stagger execution across accounts:**
   ```hcl
   # Account A: 1st of month
   scheduler_schedule = "cron(0 8 1 * ? *)"

   # Account B: 2nd of month
   scheduler_schedule = "cron(0 8 2 * ? *)"
   ```
3. **Request limit increase:** Contact AWS Support for Cost Explorer API quota increase

### Database SP Constraint Violations

#### Terraform Plan Fails with Database SP Variable Errors

**Symptom:** `terraform plan` or `terraform apply` fails with validation error for `database_sp_term` or `database_sp_payment_option`

**Error Messages:**
```
Error: Invalid value for variable

  on variables.tf line X:
  X: variable "database_sp_term" {

Database Savings Plans must use ONE_YEAR term. Received: THREE_YEAR
```

**Cause:**
- Attempting to set `database_sp_term` to anything other than `ONE_YEAR`
- Attempting to set `database_sp_payment_option` to anything other than `NO_UPFRONT`

**Solution:**

Database Savings Plans have **fixed AWS constraints** that cannot be changed:

```hcl
# ❌ WRONG - Will fail validation
enable_database_sp = true
database_sp_term = "THREE_YEAR"  # Not allowed!
database_sp_payment_option = "ALL_UPFRONT"  # Not allowed!

# ✅ CORRECT - Use defaults (or explicitly set to allowed values)
enable_database_sp = true
# database_sp_term = "ONE_YEAR"  # Optional, this is the default
# database_sp_payment_option = "NO_UPFRONT"  # Optional, this is the default
```

**Why these constraints exist:**
- AWS imposed these restrictions on Database Savings Plans
- Compute Savings Plans have flexible terms and payment options
- Database Savings Plans are always 1-year, No Upfront

**Reference:** See [AWS Constraints for Database Savings Plans](#aws-constraints-for-database-savings-plans) section above.

#### Database SP Purchases Not Happening

**Symptom:** Scheduler recommends Database SP purchases, but purchaser doesn't execute them

**Common Causes:**
- `enable_database_sp = false` in Terraform (not passed to Lambdas)
- Coverage already meets or exceeds target
- No Database service usage in account

**Investigation:**

```bash
# Check Lambda environment variables
aws lambda get-function-configuration \
  --function-name <scheduler-lambda-name> \
  --query 'Environment.Variables.ENABLE_DATABASE_SP'

# Check for Database SP recommendations in logs
aws logs filter-log-events \
  --log-group-name /aws/lambda/<scheduler-lambda-name> \
  --filter-pattern "Database Savings Plans" \
  --max-items 10

# Check for Database service usage
aws ce get-savings-plans-coverage \
  --time-period Start=2026-01-01,End=2026-01-14 \
  --granularity DAILY \
  --group-by Type=DIMENSION,Key=SAVINGS_PLAN_TYPE \
  --filter '{
    "Dimensions": {
      "Key": "SAVINGS_PLAN_TYPE",
      "Values": ["SageMaker SP", "Compute SP"]
    }
  }'
```

**Solution:**

1. **Enable in Terraform:**
   ```hcl
   enable_database_sp = true
   ```
2. **Apply changes:**
   ```bash
   terraform apply
   ```
3. **Verify environment variable updated:**
   ```bash
   aws lambda get-function-configuration \
     --function-name <scheduler-lambda-name> \
     --query 'Environment.Variables.ENABLE_DATABASE_SP'
   ```

### General Troubleshooting Tips

#### Enable Detailed Logging

CloudWatch Logs contain detailed execution information:

```bash
# Tail scheduler logs in real-time
aws logs tail /aws/lambda/<scheduler-lambda-name> --follow

# Tail purchaser logs in real-time
aws logs tail /aws/lambda/<purchaser-lambda-name> --follow

# Search logs for specific errors
aws logs filter-log-events \
  --log-group-name /aws/lambda/<scheduler-lambda-name> \
  --filter-pattern "ERROR" \
  --start-time $(($(date +%s) - 86400))000  # Last 24 hours
```

#### Manual Lambda Invocation (Testing)

Test Lambda functions manually without waiting for schedules:

```bash
# Invoke scheduler manually
aws lambda invoke \
  --function-name <scheduler-lambda-name> \
  --payload '{}' \
  --cli-binary-format raw-in-base64-out \
  response.json

# Check response
cat response.json

# Invoke purchaser manually
aws lambda invoke \
  --function-name <purchaser-lambda-name> \
  --payload '{}' \
  --cli-binary-format raw-in-base64-out \
  response.json
```

#### Verify Module Outputs

Check Terraform outputs to confirm configuration:

```bash
# Show all module outputs
terraform output

# Show specific output
terraform output queue_url
terraform output database_sp_configuration

# Show sensitive output (if any)
terraform output -json | jq '.module_configuration.value'
```

#### Check CloudWatch Alarms

Module creates alarms for Lambda errors and DLQ depth:

```bash
# List all alarms
aws cloudwatch describe-alarms --alarm-name-prefix sp-autopilot

# Check alarm state
aws cloudwatch describe-alarms \
  --alarm-names sp-autopilot-scheduler-errors sp-autopilot-purchaser-errors \
  --query 'MetricAlarms[*].[AlarmName,StateValue,StateReason]' \
  --output table
```

#### Dry-Run Mode for Safe Testing

Always test changes in dry-run mode first:

```hcl
dry_run = true  # Scheduler sends email only, no queue, no purchases
```

Workflow:
1. Deploy with `dry_run = true`
2. Trigger scheduler manually or wait for schedule
3. Review email — verify recommendations look correct
4. Set `dry_run = false` and apply
5. Monitor first real execution closely

#### Idempotency Verification

Verify purchases aren't duplicated:

```bash
# List recent Savings Plans purchases
aws savingsplans describe-savings-plans \
  --filters name=state,values=active \
  --query 'savingsPlans[*].[savingsPlanId,start,commitment,savingsPlanType]' \
  --output table

# Check for duplicate purchases (same offering, commitment, timestamp)
aws savingsplans describe-savings-plans \
  --filters name=state,values=active \
  --query 'savingsPlans[*].[commitment,savingsPlanType,start]' \
  --output table | sort | uniq -c | sort -rn
```

#### Common AWS CLI Setup Issues

If AWS CLI commands fail:

```bash
# Verify AWS CLI is installed and configured
aws --version

# Check configured credentials
aws sts get-caller-identity

# Verify region is set
aws configure get region

# Set region if needed
export AWS_DEFAULT_REGION=us-east-1
```

#### When to Contact Support

Open a GitHub issue if:
- Lambda consistently times out with default configuration
- Throttling persists after implementing suggested solutions
- Coverage calculations are consistently incorrect
- Purchases fail with unclear AWS API errors
- You encounter bugs in the module logic

Include in your issue:
- CloudWatch Logs excerpts (redact account IDs)
- Terraform version and module version
- Configuration (sanitized)
- AWS region
- Approximate number of active Savings Plans
- Whether both Compute and Database SP are enabled

## Support

For questions, issues, or feature requests, please open a GitHub issue.

---

**Generated with ❤️ by the AWS Savings Plans Autopilot Team**

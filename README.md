# AWS Savings Plans Automation Module

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
![Terraform Version](https://img.shields.io/badge/Terraform-%3E%3D%201.0-623CE4.svg)
![AWS Provider Version](https://img.shields.io/badge/AWS%20Provider-%3E%3D%205.0-FF9900.svg)

[![PR Checks](https://github.com/etiennechabert/terraform-aws-sp-autopilot/actions/workflows/pr-checks.yml/badge.svg)](https://github.com/etiennechabert/terraform-aws-sp-autopilot/actions/workflows/pr-checks.yml)
[![Security Scan](https://github.com/etiennechabert/terraform-aws-sp-autopilot/actions/workflows/security-scan.yml/badge.svg)](https://github.com/etiennechabert/terraform-aws-sp-autopilot/actions/workflows/security-scan.yml)
[![codecov](https://codecov.io/gh/etiennechabert/terraform-aws-sp-autopilot/branch/main/graph/badge.svg)](https://codecov.io/gh/etiennechabert/terraform-aws-sp-autopilot)

Automates AWS Savings Plans purchases based on usage analysis, maintaining consistent coverage while limiting financial exposure through incremental commitments.

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
- [License](#license)
- [Development](#development)
- [Contributing](#contributing)
- [Support](#support)

**Additional Guides:**
- [Error Patterns & Troubleshooting](ERROR_PATTERNS.md)
- [Testing Guide](TESTING.md)

## Features

- **Automated Savings Plans purchasing** — Maintains target coverage without manual intervention
- **Three Savings Plans types supported** — Compute, Database, and SageMaker independently tracked
- **Human review window** — Configurable delay between scheduling and purchasing allows cancellation
- **Risk management** — Spreads financial commitments over time with configurable purchase limits
- **Coverage cap enforcement** — Hard ceiling prevents over-commitment if usage shrinks
- **Email notifications** — SNS-based alerts for scheduling and purchasing activities
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

### Basic Usage

```hcl
module "savings_plans" {
  source  = "etiennechabert/sp-autopilot/aws"
  # version = "~> 1.0"  # Pin to version when using in production

  purchase_strategy = {
    coverage_target_percent = 90
    max_coverage_cap        = 95
    simple = {
      max_purchase_percent = 10
    }
  }

  sp_plans = {
    compute = {
      enabled              = true
      all_upfront_one_year = 1
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
  }

  notifications = {
    emails = ["devops@example.com"]
  }

  lambda_config = {
    scheduler = {
      dry_run = true  # Start in dry-run mode (recommended)
    }
  }
}
```

This enables **Compute Savings Plans** (default). For other configurations:

<details>
<summary><b>Database Savings Plans Only</b></summary>

```hcl
module "savings_plans" {
  source  = "etiennechabert/sp-autopilot/aws"
  # version = "~> 1.0"  # Pin to version when using in production

  purchase_strategy = {
    coverage_target_percent = 90
    max_coverage_cap        = 95
    simple = {
      max_purchase_percent = 10
    }
  }

  sp_plans = {
    compute = {
      enabled = false
    }
    database = {
      enabled             = true
      no_upfront_one_year = 1
    }
    sagemaker = {
      enabled = false
    }
  }

  notifications = {
    emails = ["database-team@example.com"]
  }

  lambda_config = {
    scheduler = {
      dry_run = true
    }
  }
}
```
</details>

<details>
<summary><b>SageMaker Savings Plans Only</b></summary>

```hcl
module "savings_plans" {
  source  = "etiennechabert/sp-autopilot/aws"
  # version = "~> 1.0"  # Pin to version when using in production

  purchase_strategy = {
    coverage_target_percent = 90
    max_coverage_cap        = 95
    simple = {
      max_purchase_percent = 10
    }
  }

  sp_plans = {
    compute = {
      enabled = false
    }
    database = {
      enabled = false
    }
    sagemaker = {
      enabled                  = true
      all_upfront_three_year   = 0.7
      all_upfront_one_year     = 0.3
    }
  }

  notifications = {
    emails = ["ml-team@example.com"]
  }

  lambda_config = {
    scheduler = {
      dry_run = true
    }
  }
}
```
</details>

<details>
<summary><b>All Three SP Types (Production Example)</b></summary>

```hcl
module "savings_plans" {
  source  = "etiennechabert/sp-autopilot/aws"
  # version = "~> 1.0"  # Pin to version when using in production

  purchase_strategy = {
    coverage_target_percent = 90
    max_coverage_cap        = 95
    simple = {
      max_purchase_percent = 10
    }
  }

  sp_plans = {
    compute = {
      enabled                = true
      all_upfront_three_year = 0.67
      all_upfront_one_year   = 0.33
    }
    database = {
      enabled             = true
      no_upfront_one_year = 1
    }
    sagemaker = {
      enabled                = true
      all_upfront_three_year = 0.7
      all_upfront_one_year   = 0.3
    }
  }

  scheduler = {
    scheduler = "cron(0 8 1 * ? *)"  # 1st of month
    purchaser = "cron(0 8 4 * ? *)"  # 4th of month - 3-day review window
  }

  notifications = {
    emails = ["devops@example.com", "finops@example.com", "ml-team@example.com"]
  }

  lambda_config = {
    scheduler = {
      dry_run = false  # Production mode
    }
  }
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
  # version = "~> 1.0"  # Pin to version when using in production

  purchase_strategy = {
    coverage_target_percent = 90
    max_coverage_cap        = 95
    simple = {
      max_purchase_percent = 10
    }
  }

  sp_plans = {
    compute = {
      enabled              = true
      all_upfront_one_year = 1
    }
    database = {
      enabled = false
    }
    sagemaker = {
      enabled = false
    }
  }

  notifications = {
    emails        = ["devops@example.com"]
    slack_webhook = var.slack_webhook_url
    teams_webhook = var.teams_webhook_url
  }

  lambda_config = {
    scheduler = {
      dry_run = true
    }
  }
}
```

> **🔒 Security Note:** Webhook URLs contain sensitive credentials. Always mark webhook URL variables as `sensitive = true` to prevent them from appearing in Terraform logs and output. Store webhook URLs in AWS Secrets Manager, HashiCorp Vault, or environment variables — never commit them directly to version control.

</details>

## Configuration Variables

For complete variable documentation including `lambda_config`, `purchase_strategy`, `sp_plans`, `scheduler`, `notifications`, `monitoring`, and `reporting` configuration objects, see:

- **[variables.tf](variables.tf)** — Full variable definitions with types, defaults, and validation rules
- **[examples/](examples/)** — Working examples for common deployment scenarios

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
    min_purchase_percent = 1  # Minimum purchase granularity (never buy less than this)
  }
}
```

**How it works:**
- Always starts with `max_purchase_percent`, halves until purchase doesn't exceed target
- Example progression (max 50%, target 90%):
  - Month 1: At 0% → Try 50% → 0+50=50% ✓ → Purchase 50%
  - Month 2: At 50% → Try 50% (would be 100%) ✗ → Try 25% (would be 75%) ✓ → Purchase 25%
  - Month 3: At 75% → Try 50% ✗ → Try 25% (would be 100%) ✗ → Try 12.5% (would be 87.5%) ✓ → Purchase 12.5%
  - Month 4: At 87.5% → Keep halving until fits → Purchase 1.5625% (reaches 89.0625%)

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
3. Configure: `notifications.slack_webhook = "https://hooks.slack.com/services/..."`

### Microsoft Teams Webhooks

1. Teams channel → **•••** → **Connectors** → "Incoming Webhook" → **Configure**
2. Copy webhook URL (only shown once)
3. Configure: `notifications.teams_webhook = "https://[org].webhook.office.com/webhookb2/..."`

**Security:** Store webhook URLs in AWS Secrets Manager or HashiCorp Vault. Mark variables as `sensitive = true` to prevent exposure in Terraform logs. Never commit webhook URLs to version control.

## Cross-Account Setup for AWS Organizations

When using AWS Organizations, Savings Plans must be purchased from the **management account**. Deploy this module in a secondary account and configure cross-account access using per-Lambda roles for least privilege.

### Configuration

```hcl
module "savings_plans" {
  source  = "etiennechabert/sp-autopilot/aws"
  # version = "~> 1.0"  # Pin to version when using in production

  # Per-Lambda roles for least privilege access
  lambda_config = {
    scheduler = {
      assume_role_arn = "arn:aws:iam::123456789012:role/SavingsPlansReadOnlyRole"
    }
    purchaser = {
      assume_role_arn = "arn:aws:iam::123456789012:role/SavingsPlansPurchaserRole"
    }
    reporter = {
      assume_role_arn = "arn:aws:iam::123456789012:role/SavingsPlansReadOnlyRole"
    }
  }
  # ... other configuration
}
```

### IAM Roles Setup in Management Account

Two roles provide least privilege access: a shared read-only role for Scheduler and Reporter, and a unique Purchaser role with write permissions.

#### 1. Read-Only Role (Scheduler and Reporter)

**Trust Policy:**
```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {
      "AWS": [
        "arn:aws:iam::SECONDARY_ACCOUNT_ID:role/sp-autopilot-scheduler-role",
        "arn:aws:iam::SECONDARY_ACCOUNT_ID:role/sp-autopilot-reporter-role"
      ]
    },
    "Action": "sts:AssumeRole"
  }]
}
```

**Permissions Policy:**
```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": [
      "ce:GetSavingsPlansPurchaseRecommendation",
      "ce:GetSavingsPlansCoverage",
      "ce:GetSavingsPlansUtilization",
      "savingsplans:DescribeSavingsPlans"
    ],
    "Resource": "*"
  }]
}
```

#### 2. Purchaser Role (Write Permissions)

**Trust Policy:**
```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {
      "AWS": "arn:aws:iam::SECONDARY_ACCOUNT_ID:role/sp-autopilot-purchaser-role"
    },
    "Action": "sts:AssumeRole"
  }]
}
```

**Permissions Policy:**
```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": [
      "savingsplans:CreateSavingsPlan",
      "savingsplans:DescribeSavingsPlans",
      "ce:GetSavingsPlansCoverage"
    ],
    "Resource": "*"
  }]
}
```

**Security Note:** Only the Purchaser Lambda has `CreateSavingsPlan` permissions. Scheduler and Reporter share a read-only role, simplifying management while maintaining least privilege.

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

This module is open-source software licensed under the Apache License 2.0.

## Used By

Using this module in production? We'd love to hear from you!

**Add your company logo:**
1. Fork this repo
2. Add your logo to `docs/users/` (PNG/SVG, max 200px width)
3. Submit a PR updating this section

Your company here:
<!-- Add your company logo and link below -->
<!-- Example: [![Company Name](docs/users/company-logo.png)](https://company.com) -->

*Be the first to showcase your use of terraform-aws-sp-autopilot!*

## Development

### Local Development and Debugging

You can run and debug the Lambda functions locally on your development machine using the local runner.

**Quick start using Make:**

```bash
# Setup local environment
make setup-local

# Edit .env.local with your AWS credentials

# Run Lambdas
make run-scheduler    # Analyzes coverage, queues intents (dry-run)
make run-purchaser    # Processes queued intents
make run-reporter     # Generates HTML report
```

**Or use Python directly:**

```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Configure local environment
cp .env.local.example .env.local
# Edit .env.local with your AWS credentials

# Run Lambdas locally with filesystem I/O
python local_runner.py scheduler --dry-run
python local_runner.py purchaser
python local_runner.py reporter --format html
```

In local mode:
- **SQS messages** → JSON files in `local_data/queue/`
- **S3 reports** → Files in `local_data/reports/`
- **AWS APIs** → Real Cost Explorer and Savings Plans APIs (read-only unless purchasing)

This enables:
- Fast iteration without AWS deployments
- IDE breakpoint debugging
- Inspection of queue messages and reports
- Testing without AWS costs

**See [LOCAL_DEVELOPMENT.md](LOCAL_DEVELOPMENT.md) for detailed instructions.**

### Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run local mode tests
pytest tests/test_local_mode.py tests/test_local_runner.py -v

# Run with coverage
pytest tests/ --cov=lambda --cov-report=html
```

## Contributing

Contributions are welcome! Please open an issue or pull request on GitHub.

## Support

For questions, issues, or feature requests, please open a GitHub issue.

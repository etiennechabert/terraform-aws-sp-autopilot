# AWS Savings Plans Automation Module

An open-source Terraform module that automates AWS Savings Plans purchases based on usage analysis. The module maintains consistent coverage while limiting financial exposure through incremental, spread-out commitments.

[![Terraform Validation](https://github.com/your-org/terraform-aws-sp-autopilot/actions/workflows/terraform-validation.yml/badge.svg)](https://github.com/your-org/terraform-aws-sp-autopilot/actions/workflows/terraform-validation.yml)
[![Python Tests](https://github.com/your-org/terraform-aws-sp-autopilot/actions/workflows/python-tests.yml/badge.svg)](https://github.com/your-org/terraform-aws-sp-autopilot/actions/workflows/python-tests.yml)
[![Security Scan](https://github.com/your-org/terraform-aws-sp-autopilot/actions/workflows/security-scan.yml/badge.svg)](https://github.com/your-org/terraform-aws-sp-autopilot/actions/workflows/security-scan.yml)
[![PR Checks](https://github.com/your-org/terraform-aws-sp-autopilot/actions/workflows/pr-checks.yml/badge.svg)](https://github.com/your-org/terraform-aws-sp-autopilot/actions/workflows/pr-checks.yml)

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

### Basic Usage (Compute SP Only)

```hcl
module "savings_plans" {
  source = "github.com/your-org/terraform-aws-sp-autopilot"

  # Enable Compute Savings Plans (enabled by default)
  enable_compute_sp = true
  enable_database_sp = false

  # Coverage targets
  coverage_target_percent = 90
  max_coverage_cap        = 95

  # Risk management
  max_purchase_percent = 10  # Max 10% of monthly spend per cycle

  # Notifications
  notification_emails = ["devops@example.com"]

  # Start in dry-run mode (recommended)
  dry_run = true
}
```

### Database Savings Plans Configuration

To enable Database Savings Plans automation:

```hcl
module "savings_plans" {
  source = "github.com/your-org/terraform-aws-sp-autopilot"

  # Enable Database Savings Plans
  enable_database_sp = true

  # Optionally disable Compute SP if you only want Database coverage
  enable_compute_sp = false

  # Coverage targets (applies to both SP types independently)
  coverage_target_percent = 90
  max_coverage_cap        = 95

  # Risk management
  max_purchase_percent = 10

  # Notifications
  notification_emails = ["database-team@example.com"]

  # Start in dry-run mode
  dry_run = true
}
```

### Mixed Configuration (Both SP Types)

Run both Compute and Database Savings Plans automation:

```hcl
module "savings_plans" {
  source = "github.com/your-org/terraform-aws-sp-autopilot"

  # Enable both SP types
  enable_compute_sp  = true
  enable_database_sp = true

  # Coverage targets (separate tracking per SP type)
  coverage_target_percent = 90
  max_coverage_cap        = 95

  # Risk management
  max_purchase_percent = 10

  # Compute SP configuration
  compute_sp_term_mix = {
    three_year = 0.67
    one_year   = 0.33
  }
  compute_sp_payment_option = "ALL_UPFRONT"

  # Database SP uses fixed AWS constraints
  # database_sp_term = "ONE_YEAR"           # Fixed (cannot change)
  # database_sp_payment_option = "NO_UPFRONT"  # Fixed (cannot change)

  # Scheduling
  scheduler_schedule = "cron(0 8 1 * ? *)"  # 1st of month at 8:00 AM UTC
  purchaser_schedule = "cron(0 8 4 * ? *)"  # 4th of month at 8:00 AM UTC (3-day review window)

  # Notifications
  notification_emails = [
    "devops@example.com",
    "finops@example.com"
  ]

  dry_run = false  # Enable actual purchases
}
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

#### 🧪 Python Tests (`python-tests.yml`)

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
| **Scheduler Tests** | All tests pass with ≥80% code coverage | `python-tests.yml` |
| **Purchaser Tests** | All integration tests pass | `python-tests.yml` |

### Running Workflows Manually

All workflows support manual triggering via `workflow_dispatch`:

```bash
# Via GitHub UI
Actions → Select Workflow → Run workflow

# Via GitHub CLI
gh workflow run terraform-validation.yml
gh workflow run python-tests.yml
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

## Support

For questions, issues, or feature requests, please open a GitHub issue.

---

**Generated with ❤️ by the AWS Savings Plans Autopilot Team**

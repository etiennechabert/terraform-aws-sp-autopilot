# Security Policy

This document outlines security best practices, vulnerability reporting procedures, and security considerations for the AWS Savings Plans Automation Module. Given that this module automates financial commitments (potentially thousands of dollars in AWS Savings Plans purchases), security is a critical concern.

## Table of Contents

- [Supported Versions](#supported-versions)
- [Reporting a Vulnerability](#reporting-a-vulnerability)
- [Security Best Practices](#security-best-practices)
  - [IAM Permissions and Least Privilege](#iam-permissions-and-least-privilege)
  - [Financial Risk Controls](#financial-risk-controls)
  - [Secrets Management](#secrets-management)
  - [Network Security](#network-security)
  - [Monitoring and Auditing](#monitoring-and-auditing)
- [Dependency Management](#dependency-management)
- [Known Security Considerations](#known-security-considerations)
- [Security Updates](#security-updates)

## Supported Versions

We provide security updates for the following versions:

| Version | Support Status | Security Updates |
|---------|---------------|------------------|
| 1.x.x (latest) | ✅ Supported | Active security patching |
| < 1.0.0 | ❌ Not supported | Please upgrade to 1.x.x |

**Recommendation:** Always use the latest stable release and pin to a specific version in production:

```hcl
module "savings_plans" {
  source  = "etiennechabert/sp-autopilot/aws"
  version = "~> 1.0"  # Pin to 1.x.x minor version range

  # ... configuration
}
```

## Reporting a Vulnerability

We take security vulnerabilities seriously. If you discover a security issue, please follow these steps:

### 🔒 Responsible Disclosure Process

1. **DO NOT** open a public GitHub issue for security vulnerabilities
2. **Email** security details to: **security@example.com**
3. **Include** the following information:
   - Description of the vulnerability
   - Steps to reproduce the issue
   - Potential impact and severity assessment
   - Suggested fix (if available)

### What to Expect

| Timeline | Action |
|----------|--------|
| **Within 48 hours** | Acknowledgment of your report |
| **Within 7 days** | Initial assessment and severity classification |
| **Within 30 days** | Fix developed, tested, and released (for critical issues) |
| **After fix release** | Public disclosure in release notes and security advisory |

### Severity Classification

- **Critical** — Unauthorized purchase capability, credential exposure, or financial risk escalation
- **High** — IAM privilege escalation, data exposure, or purchase limit bypass
- **Medium** — Information disclosure, denial of service, or configuration weaknesses
- **Low** — Minor security improvements with limited impact

## Security Best Practices

### IAM Permissions and Least Privilege

The module follows AWS IAM best practices with **minimal, scoped permissions** for each Lambda function.

#### Scheduler Lambda Permissions

The scheduler Lambda has **read-only** permissions and **cannot make purchases**:

```hcl
# Read-only access to Cost Explorer
ce:GetSavingsPlansPurchaseRecommendation
ce:GetSavingsPlansUtilization
ce:GetSavingsPlansCoverage
ce:GetCostAndUsage

# Write access only to SQS queue (queuing purchase intents)
sqs:SendMessage
sqs:PurgeQueue
sqs:GetQueueAttributes

# Write access to CloudWatch Logs and SNS notifications
logs:CreateLogStream
logs:PutLogEvents
sns:Publish
```

#### Purchaser Lambda Permissions

The purchaser Lambda has **write permissions** for purchases but is **restricted** to specific resources:

```hcl
# Purchase capability (requires explicit opt-in via dry_run = false)
savingsplans:CreateSavingsPlan
savingsplans:DescribeSavingsPlans

# Read access from SQS queue
sqs:ReceiveMessage
sqs:DeleteMessage
sqs:GetQueueAttributes

# Notifications and logging
sns:Publish
logs:CreateLogStream
logs:PutLogEvents
```

**⚠️ Security Note:** The `savingsplans:CreateSavingsPlan` permission is the most sensitive permission in this module. It allows the Lambda function to create financial commitments. This is why the module includes multiple safeguards:

- **Dry-run mode by default** (`dry_run = true`)
- **Human review window** (configurable delay between scheduling and purchasing)
- **Coverage cap enforcement** (`max_coverage_cap` prevents over-commitment)
- **Incremental purchase limits** (`max_purchase_percent` limits exposure per run)

#### Deployment Recommendations

✅ **DO:**
- Use IAM roles with session policies to further restrict permissions during deployment
- Enable CloudTrail logging for all `savingsplans:*` API calls
- Use AWS Organizations SCPs to enforce coverage caps across the organization
- Implement AWS Config rules to monitor Savings Plans purchases
- Review CloudWatch Logs for all Lambda executions

❌ **DO NOT:**
- Grant `savingsplans:*` wildcard permissions to human users
- Deploy with `dry_run = false` until you've validated the module behavior in your environment
- Disable SQS queue encryption or CloudWatch Logs
- Share IAM roles between environments (dev, staging, prod)

### Financial Risk Controls

The module includes **multiple layers of financial protection** to prevent unintended or excessive commitments:

#### 1. Dry-Run Mode (Default Protection)

```hcl
lambda_config = {
  scheduler = {
    dry_run = true  # ✅ DEFAULT: No purchases will be made
  }
}
```

When `dry_run = true`:
- Scheduler analyzes usage and sends **email notifications only**
- **No messages are queued** to the purchase queue
- Purchaser Lambda never executes purchases
- **Zero financial risk** — use this mode to validate recommendations

**⚠️ Warning:** Only set `dry_run = false` after validating recommendations in your environment.

#### 2. Coverage Cap (Hard Ceiling)

```hcl
purchase_strategy = {
  max_coverage_cap = 95  # ✅ HARD LIMIT: Never exceed 95% coverage
  # ...
}
```

- Enforced **at purchase time** by the purchaser Lambda
- Prevents over-commitment even if usage patterns change
- Independently tracked for Compute, Database, and SageMaker Savings Plans
- Protects against coverage exceeding target if workloads shrink

#### 3. Incremental Purchase Limits

```hcl
purchase_strategy = {
  simple = {
    max_purchase_percent = 10  # ✅ INCREMENTAL: Max 10% of uncovered spend per run
  }
}
```

- Spreads financial commitments over time
- Limits exposure per scheduler execution
- Allows gradual ramp-up to target coverage
- Reduces risk of committing to volatile workloads

#### 4. Human Review Window

```hcl
scheduler = {
  scheduler  = "cron(0 8 1 * ? *)"   # 1st of month - schedule purchases
  purchaser  = "cron(0 8 4 * ? *)"   # 4th of month - execute purchases (3-day review window)
}
```

- Configurable delay between scheduling and purchasing
- Review purchase intents in SQS queue before execution
- **Cancel unwanted purchases** by deleting SQS messages
- Receive email notifications with full purchase details

#### 5. Idempotency Protection

- All purchase requests include unique idempotency tokens
- Prevents duplicate purchases if Lambda retries
- AWS guarantees idempotent `CreateSavingsPlan` API calls within 24 hours

### Secrets Management

**✅ This module does NOT require secrets or credentials to be stored.**

- Lambda functions use **IAM roles** for AWS API authentication
- No hardcoded credentials in Terraform code
- No API keys, passwords, or tokens needed
- Environment variables used only for configuration (not secrets)

#### Best Practices for Related AWS Services

If integrating with external systems (e.g., Slack, PagerDuty):

```hcl
# ✅ RECOMMENDED: Use AWS Secrets Manager
resource "aws_secretsmanager_secret" "slack_webhook" {
  name = "${var.project_name}-slack-webhook"
}

# Reference secret in Lambda environment variables
environment {
  variables = {
    SLACK_WEBHOOK_SECRET_ARN = aws_secretsmanager_secret.slack_webhook.arn
  }
}
```

- **Never** commit secrets to version control
- Use AWS Secrets Manager or Parameter Store for sensitive data
- Rotate secrets regularly (90-day rotation recommended)
- Grant Lambda IAM roles `secretsmanager:GetSecretValue` permissions only for specific secret ARNs

### Network Security

#### VPC Deployment (Optional)

By default, Lambda functions run in AWS-managed VPC with public internet access. For enhanced security:

```hcl
lambda_config = {
  scheduler = {
    vpc_config = {
      subnet_ids         = var.private_subnet_ids
      security_group_ids = [aws_security_group.lambda.id]
    }
  }
  purchaser = {
    vpc_config = {
      subnet_ids         = var.private_subnet_ids
      security_group_ids = [aws_security_group.lambda.id]
    }
  }
}
```

**VPC Deployment Considerations:**

✅ **Benefits:**
- Isolated network environment
- Control egress traffic with security groups and NACLs
- Use VPC endpoints for AWS service API calls (no internet gateway needed)

⚠️ **Requirements:**
- NAT Gateway or VPC endpoints for AWS API access (`ce:*`, `savingsplans:*`, `sqs:*`, `sns:*`)
- Additional AWS costs for NAT Gateway or VPC endpoints
- Increased cold start latency for Lambda functions

#### Encryption in Transit

- **All AWS API calls use TLS 1.2+** (enforced by AWS SDK)
- SNS notifications and SQS messages transmitted over HTTPS
- No unencrypted network communication

### Monitoring and Auditing

#### CloudWatch Logs

All Lambda executions are logged to CloudWatch Logs:

```hcl
# Logs retention configured by module
resource "aws_cloudwatch_log_group" "scheduler" {
  retention_in_days = var.log_retention_days  # Default: 30 days
}
```

**Audit Logging Best Practices:**

✅ **Enable:**
- CloudWatch Logs Insights queries for purchase audit trails
- CloudWatch Alarms for unexpected purchase patterns
- Log export to S3 for long-term retention (compliance requirements)

❌ **Do NOT:**
- Disable CloudWatch Logs (required for security auditing)
- Log sensitive data (account IDs, ARNs are masked automatically)
- Reduce retention below 30 days for production environments

#### CloudTrail Monitoring

Enable AWS CloudTrail to audit all `savingsplans:*` API calls:

```hcl
# Example CloudTrail configuration (not included in module)
resource "aws_cloudtrail" "savings_plans_audit" {
  name           = "savings-plans-audit"
  s3_bucket_name = aws_s3_bucket.cloudtrail_logs.id

  event_selector {
    read_write_type = "WriteOnly"

    data_resource {
      type   = "AWS::SavingsPlans::SavingsPlan"
      values = ["arn:aws:savingsplans:*:${data.aws_caller_identity.current.account_id}:*"]
    }
  }
}
```

**What to Monitor:**

| Event | Why It Matters | Alert Threshold |
|-------|----------------|-----------------|
| `CreateSavingsPlan` | Financial commitment made | Every occurrence (low volume) |
| `DescribeSavingsPlans` | Coverage calculation | Unexpected spike in API calls |
| SQS message deletions | Purchase cancellations | Manual intervention detected |
| Lambda execution failures | Purchase workflow broken | Any failure in purchaser Lambda |

## Dependency Management

### Terraform Providers

```hcl
terraform {
  required_version = ">= 1.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }
}
```

**Security Scanning:**

- All Terraform code is scanned with **tfsec** (minimum severity: HIGH)
- GitHub Actions automatically run security scans on every PR
- SARIF results uploaded to GitHub Security tab

### Python Lambda Dependencies

| Lambda | Key Dependencies | Security Scanning |
|--------|------------------|-------------------|
| Scheduler | `boto3`, `botocore` | Dependabot enabled |
| Purchaser | `boto3`, `botocore` | Dependabot enabled |
| Reporter | `boto3`, `botocore` | Dependabot enabled |

**Dependency Update Policy:**

- **Critical vulnerabilities:** Patched within 7 days
- **High vulnerabilities:** Patched within 30 days
- **Medium/Low vulnerabilities:** Addressed in next minor release

### Automated Security Checks (CI/CD)

The project uses GitHub Actions for continuous security validation:

```yaml
# .github/workflows/pr-checks.yml
jobs:
  tfsec-scan:
    name: tfsec Security Scan
    runs-on: ubuntu-latest
    steps:
      - name: Run tfsec
        uses: aquasecurity/tfsec-action@v1.0.3
        with:
          minimum-severity: HIGH
```

**Scans Performed:**

| Tool | Purpose | Enforcement |
|------|---------|-------------|
| **tfsec** | Terraform security and best practices | ✅ Blocking (HIGH/CRITICAL issues fail PR) |
| **Ruff** | Python linting and security patterns | ✅ Blocking |
| **Dependabot** | Dependency vulnerability scanning | 🔔 Alerting (auto-PR for updates) |
| **CodeQL** | Static code analysis (future) | 🔔 Alerting |

## Known Security Considerations

### 1. AWS Savings Plans Purchase Authority

**Risk:** The purchaser Lambda function has `savingsplans:CreateSavingsPlan` permission, which allows it to create financial commitments.

**Mitigations:**
- Dry-run mode enabled by default (`dry_run = true`)
- Human review window before purchases execute
- Coverage cap enforcement (`max_coverage_cap`)
- Incremental purchase limits (`max_purchase_percent`)
- CloudWatch Logs and CloudTrail auditing
- Idempotency protection against duplicate purchases

**Recommendation:** Use AWS Organizations Service Control Policies (SCPs) to enforce maximum coverage caps across your organization:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Deny",
      "Action": "savingsplans:CreateSavingsPlan",
      "Resource": "*",
      "Condition": {
        "NumericGreaterThan": {
          "savingsplans:Coverage": "0.95"
        }
      }
    }
  ]
}
```

### 2. Cost Explorer API Rate Limits

**Risk:** The scheduler Lambda calls Cost Explorer APIs (`ce:GetSavingsPlansCoverage`, `ce:GetSavingsPlansPurchaseRecommendation`), which have AWS rate limits.

**Mitigations:**
- Exponential backoff and retry logic in Lambda code
- Scheduler runs on low-frequency schedule (e.g., monthly)
- Separate API calls for Compute, Database, and SageMaker (spread over time)

**Recommendation:** Do not run the scheduler more frequently than daily to avoid rate limit errors.

### 3. SQS Queue Message Tampering

**Risk:** If an attacker gains access to the SQS queue, they could modify purchase intent messages.

**Mitigations:**
- SQS queue uses server-side encryption (SSE-SQS by default)
- IAM policies restrict queue access to scheduler and purchaser Lambda functions only
- Message attributes include integrity checks (idempotency token, timestamp)
- Purchaser Lambda validates message structure and recalculates coverage before purchase

**Recommendation:** Enable SQS encryption with AWS KMS for additional protection:

```hcl
# Example: Use KMS encryption for SQS queue
resource "aws_sqs_queue" "purchase_intents" {
  # ... existing configuration

  kms_master_key_id                 = aws_kms_key.sqs_encryption.id
  kms_data_key_reuse_period_seconds = 300
}
```

### 4. Lambda Environment Variable Exposure

**Risk:** Lambda environment variables are stored encrypted at rest but visible in the AWS Console to users with `lambda:GetFunction` permissions.

**Mitigations:**
- Module does not use environment variables for sensitive data
- All configuration passed via Terraform variables or IAM role permissions
- No secrets, API keys, or credentials stored in environment variables

**Recommendation:** If extending the module with custom integrations, use AWS Secrets Manager for sensitive data.

## Security Updates

### How We Handle Security Vulnerabilities

1. **Detection**
   - Dependabot alerts for dependency vulnerabilities
   - Community reports via security@example.com
   - Regular tfsec and security scanning in CI/CD

2. **Assessment**
   - Severity classification (Critical, High, Medium, Low)
   - Impact analysis on users and financial commitments
   - Exploit feasibility assessment

3. **Patching**
   - Develop and test fix in private repository fork
   - Create security advisory (GitHub Security Advisories)
   - Release patch version with security fix

4. **Disclosure**
   - Publish security advisory with CVE (if applicable)
   - Update CHANGELOG.md with security fix details
   - Notify users via GitHub release notes

### Staying Informed

- **Watch this repository** on GitHub for security advisories
- **Subscribe to release notifications** for security patches
- **Review CHANGELOG.md** before upgrading versions
- **Check GitHub Security tab** for known vulnerabilities

### Upgrading for Security Patches

When a security update is released:

```bash
# Update module version in your Terraform configuration
module "savings_plans" {
  source  = "etiennechabert/sp-autopilot/aws"
  version = "~> 1.0.5"  # Update to patched version

  # ... configuration
}

# Apply the update
terraform init -upgrade
terraform plan
terraform apply
```

**Important:** Always review the CHANGELOG.md and release notes before applying security updates to understand the impact.

---

## Contact

- **Security Vulnerabilities:** security@example.com
- **General Questions:** Open a [GitHub Discussion](https://github.com/etiennechabert/terraform-aws-sp-autopilot/discussions)
- **Bug Reports:** Open a [GitHub Issue](https://github.com/etiennechabert/terraform-aws-sp-autopilot/issues)

**Thank you for helping keep this project secure!**

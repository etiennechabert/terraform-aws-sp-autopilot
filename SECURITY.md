# Security Policy

This module automates AWS Savings Plans purchases, which involve financial commitments. Security is critical.

## Reporting a Vulnerability

**DO NOT** open public GitHub issues for security vulnerabilities.

**Email:** etienne.chabert@gmail.com

**Include:**
- Vulnerability description
- Reproduction steps
- Impact assessment
- Suggested fix (if available)

**Response timeline:**
- Within 48 hours: Acknowledgment
- Within 7 days: Assessment and severity classification
- Within 30 days: Fix for critical issues

## Supported Versions

| Version | Security Updates |
|---------|-----------------|
| 1.x.x (latest) | ✅ Active patching |
| < 1.0.0 | ❌ Unsupported - upgrade required |

Always pin to a specific version:
```hcl
version = "~> 1.0"  # 1.x.x range
```

## Security Best Practices

### IAM Permissions

**Scheduler Lambda** (Read-only):
- Cost Explorer API access for recommendations
- SQS SendMessage to queue purchase intents
- SNS Publish for notifications

**Purchaser Lambda** (Purchase capability):
- `savingsplans:CreateSavingsPlan` - most sensitive permission
- SQS ReceiveMessage/DeleteMessage
- SNS Publish for notifications

**⚠️ Critical:** The `CreateSavingsPlan` permission enables financial commitments. Protected by:
- Dry-run mode (default: enabled)
- Coverage cap enforcement
- Incremental purchase limits
- Human review window

### Financial Risk Controls

**1. Dry-Run Mode (Default)**
```hcl
dry_run = true  # No actual purchases
```

**2. Coverage Cap**
```hcl
max_coverage_cap = 95  # Hard limit
```

**3. Incremental Limits**
```hcl
max_purchase_percent = 10  # Max 10% per run
```

**4. Human Review Window**
Schedule purchases and execute them days later for review:
```hcl
scheduler  = "cron(0 8 1 * ? *)"  # 1st of month
purchaser  = "cron(0 8 4 * ? *)"  # 4th of month (3-day review)
```

### Secrets Management

No secrets required. Lambda functions use IAM roles for authentication.

For external integrations, use AWS Secrets Manager - never commit credentials.

### Network Security

**Default:** Lambda runs in AWS-managed VPC with TLS 1.2+ for all API calls.

**Optional VPC deployment** for isolation requires NAT Gateway or VPC endpoints for AWS API access.

### Monitoring

**CloudWatch Logs:** All executions logged (default 30-day retention).

**CloudTrail:** Monitor `savingsplans:CreateSavingsPlan` API calls.

**Key events to monitor:**
- Every `CreateSavingsPlan` call (financial commitment)
- Lambda execution failures
- Unexpected SQS deletions (purchase cancellations)

## Dependency Management

**Terraform:** `>= 1.0`, AWS provider `>= 5.0`

**Python:** `boto3`, `botocore` (Dependabot enabled)

**Security scanning:** tfsec (blocking on HIGH/CRITICAL), Ruff linting

**Update policy:**
- Critical vulnerabilities: 7 days
- High vulnerabilities: 30 days
- Medium/Low: Next minor release

## Known Security Considerations

### 1. Purchase Authority Risk
The purchaser Lambda can create financial commitments.

**Mitigations:** Dry-run mode, coverage caps, incremental limits, audit logging, idempotency protection.

**Additional control:** Use AWS Organizations SCPs to enforce coverage limits org-wide.

### 2. Cost Explorer Rate Limits
Scheduler calls CE APIs with AWS rate limits.

**Mitigations:** Exponential backoff, low-frequency schedule (monthly recommended).

### 3. SQS Message Integrity
Queue uses SSE-SQS encryption. For enhanced protection, use KMS encryption.

**Validation:** Purchaser recalculates coverage before purchase to detect tampering.

### 4. Environment Variables
No sensitive data stored in Lambda environment variables. Use Secrets Manager for custom integrations.

## Security Updates

**Stay informed:**
- Watch this repository for security advisories
- Review CHANGELOG.md before upgrades
- Check GitHub Security tab

**Applying updates:**
```bash
# Update version
terraform init -upgrade
terraform plan
terraform apply
```

---

**Security contact:** etienne.chabert@gmail.com
**General questions:** [GitHub Discussions](https://github.com/etiennechabert/terraform-aws-sp-autopilot/discussions)
**Bug reports:** [GitHub Issues](https://github.com/etiennechabert/terraform-aws-sp-autopilot/issues)

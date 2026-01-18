# AWS Cost Estimation Guide

Understanding the infrastructure costs of running this Savings Plans automation module.

## Cost Summary

**Typical Monthly Cost:** $2-5 for standard usage scenarios

The module deploys serverless infrastructure with pay-per-use pricing. Actual costs scale with usage patterns and configuration choices. Most costs come from Lambda invocations and CloudWatch Logs storage.

## AWS Service Breakdown

### Lambda Functions

**3 Lambda Functions Deployed:**
- **Scheduler** — Analyzes usage and queues purchase recommendations
- **Purchaser** — Executes Savings Plans purchases from queue
- **Reporter** — Generates periodic coverage and savings reports

#### Pricing Factors

| Component | Configuration | AWS Pricing |
|-----------|---------------|-------------|
| **Requests** | Per invocation | $0.20 per 1M requests |
| **Compute Duration** | GB-seconds | $0.0000166667 per GB-second |
| **Memory** | Scheduler/Reporter: 512 MB<br>Purchaser: 256 MB | Included in duration cost |
| **Timeout** | 300 seconds (5 minutes) | Max duration if function runs full timeout |

#### Monthly Cost Estimate

**Default Schedule (Monthly Execution):**
- Scheduler: 1st of month
- Purchaser: 4th of month
- Reporter: 1st of month (same as Scheduler)

| Function | Invocations/Month | Avg Duration | Memory | Compute (GB-sec) | Cost |
|----------|-------------------|--------------|--------|------------------|------|
| **Scheduler** | 1 | 30s | 512 MB | 15 | $0.00025 |
| **Purchaser** | 1-10* | 10s each | 256 MB | 2.5 per invocation | $0.00004-0.0004 |
| **Reporter** | 1 | 45s | 512 MB | 22.5 | $0.00037 |

*Purchaser invocations depend on number of purchase intents queued. Typically 1-5 per month.

**Request costs:** ~$0.000001 (negligible)

**Total Lambda costs:** **~$0.001-0.002/month** ($0.01-0.02/year)

**Weekly Schedule:**
If using weekly schedules (4x per month):
- **Total Lambda costs:** **~$0.005-0.01/month** ($0.06-0.12/year)

### SQS Queues

**2 Queues Deployed:**
- **Main Queue** — Purchase intents queue
- **Dead Letter Queue** — Failed message handling

#### Pricing

| Metric | AWS Pricing | Monthly Estimate |
|--------|-------------|------------------|
| **Requests** | $0.40 per 1M requests (after 1M free tier) | $0.00 |
| **Data Transfer** | Included | $0.00 |
| **KMS Encryption** | $0.03 per 10,000 API calls (if enabled) | $0.00 |

**Typical Usage:**
- Scheduler sends 1-10 messages/month
- Purchaser receives 1-10 messages/month
- ~20-100 total API calls/month (well within free tier)

**Total SQS costs:** **$0.00/month** (free tier covers usage)

### S3 Bucket

**1 Bucket Deployed:** Report storage

#### Pricing

| Component | Configuration | AWS Pricing | Monthly Estimate |
|-----------|---------------|-------------|------------------|
| **Storage** | STANDARD class | $0.023 per GB/month | $0.001-0.01 |
| **Requests** | PUT/GET operations | $0.005 per 1,000 PUT<br>$0.0004 per 1,000 GET | $0.00 |
| **Lifecycle Transitions** | STANDARD → IA → Glacier | $0.01 per 1,000 transitions | $0.00 |
| **Versioning** | Enabled | Stored as separate objects | Included in storage |

**Storage Lifecycle (Default):**
- Day 0-30: STANDARD storage
- Day 30-90: STANDARD_IA storage ($0.0125/GB/month)
- Day 90-365: GLACIER storage ($0.004/GB/month)
- Day 365+: Deleted

**Typical Report Storage:**
- Monthly reports: ~100-500 KB each
- Annual storage: ~1-5 MB total (with lifecycle transitions)

**Total S3 costs:** **$0.001-0.01/month** ($0.01-0.12/year)

### SNS Topic

**1 Topic Deployed:** Email notifications

#### Pricing

| Component | AWS Pricing | Monthly Estimate |
|-----------|-------------|------------------|
| **Publish Requests** | $0.50 per 1M requests | $0.00 |
| **Email Notifications** | $2.00 per 100,000 emails | $0.00 |
| **HTTP/HTTPS Delivery** | $0.60 per 1M notifications | $0.00 |

**Typical Usage:**
- 2-5 emails per month (scheduler + purchaser + reporter)
- 5-10 publish requests per month

**Total SNS costs:** **$0.00/month** (well within free tier)

### CloudWatch

**Resources Deployed:**
- **3 Log Groups** — Lambda function logs (30-day retention)
- **4 CloudWatch Alarms** — Error monitoring (optional)

#### Pricing

| Component | Configuration | AWS Pricing | Monthly Estimate |
|-----------|---------------|-------------|------------------|
| **Log Ingestion** | Lambda logs | $0.50 per GB ingested | $0.10-0.50 |
| **Log Storage** | 30-day retention | $0.03 per GB/month | $0.01-0.05 |
| **CloudWatch Alarms** | 4 alarms (optional) | $0.10 per alarm/month | $0.40 |
| **Logs Insights Queries** | Manual queries | $0.005 per GB scanned | $0.00-0.01 |

**Log Volume Estimates:**
- Scheduler: ~1-5 MB per execution
- Purchaser: ~0.5-2 MB per execution
- Reporter: ~2-10 MB per execution
- Monthly total: ~10-50 MB

**Total CloudWatch costs:**
- **Without alarms:** **$0.15-0.60/month**
- **With alarms:** **$0.55-1.00/month**

### EventBridge

**Resources Deployed:**
- **Scheduler Lambda schedule** — Triggers monthly/weekly
- **Purchaser Lambda schedule** — Triggers monthly/weekly
- **Reporter Lambda schedule** — Triggers monthly/weekly

#### Pricing

| Component | AWS Pricing | Monthly Estimate |
|-----------|-------------|------------------|
| **Event Bus Invocations** | Free for default event bus rules | $0.00 |
| **Scheduled Events** | Free for first 14M events/month | $0.00 |

**Total EventBridge costs:** **$0.00/month**

### IAM Roles and Policies

**No charges** — IAM is free.

### Cost Explorer API

**Usage by Scheduler Lambda:**
- `GetSavingsPlansPurchaseRecommendation` API calls
- `GetSavingsPlansCoverage` API calls
- `GetSavingsPlansUtilization` API calls (Reporter)

#### Pricing

| API Call | AWS Pricing | Monthly Estimate |
|----------|-------------|------------------|
| **Cost Explorer APIs** | Included in Cost Explorer service | $0.00 |

**Note:** Cost Explorer service itself may have costs (~$0.01/API call), but basic Savings Plans APIs are typically included with Cost Management tools access. Verify with AWS for your specific account.

## Total Monthly Cost Summary

| Scenario | Lambda | SQS | S3 | SNS | CloudWatch | EventBridge | **Total** |
|----------|--------|-----|----|----|------------|-------------|-----------|
| **Minimal (Monthly + No Alarms)** | $0.001 | $0.00 | $0.001 | $0.00 | $0.15 | $0.00 | **~$0.15/month** |
| **Standard (Monthly + Alarms)** | $0.002 | $0.00 | $0.01 | $0.00 | $0.70 | $0.00 | **~$0.71/month** |
| **Active (Weekly + Alarms)** | $0.01 | $0.00 | $0.01 | $0.00 | $1.50 | $0.00 | **~$1.52/month** |
| **High Usage (Daily + Alarms)** | $0.03 | $0.00 | $0.05 | $0.00 | $4.00 | $0.00 | **~$4.08/month** |

**Annual Estimates:**
- **Standard usage:** **$8-10/year**
- **Active usage:** **$18-20/year**

## Cost Optimization Tips

### 1. Adjust CloudWatch Log Retention

Reduce log retention from 30 days to 7 or 14 days:

```hcl
# Not currently configurable via module variables
# Modify cloudwatch.tf if shorter retention is acceptable
retention_in_days = 7  # Reduces storage costs by ~75%
```

**Savings:** ~$0.05-0.15/month

### 2. Disable CloudWatch Alarms

If using external monitoring (e.g., Datadog, New Relic):

```hcl
lambda_config = {
  scheduler = {
    error_alarm_enabled = false
  }
  purchaser = {
    error_alarm_enabled = false
  }
  reporter = {
    error_alarm_enabled = false
  }
}
```

**Savings:** ~$0.40/month

### 3. Reduce Lambda Memory

Lower memory reduces duration costs (use sparingly — may increase execution time):

```hcl
lambda_config = {
  scheduler = {
    memory_size = 256  # Default: 512 MB
  }
  reporter = {
    memory_size = 256  # Default: 512 MB
  }
}
```

**Savings:** ~$0.0001-0.001/month (minimal — not recommended unless necessary)

### 4. Optimize S3 Lifecycle Policy

Transition reports to cheaper storage faster:

```hcl
s3_config = {
  lifecycle = {
    transition_ia_days     = 14  # Default: 30
    transition_glacier_days = 30 # Default: 90
    expiration_days        = 180 # Default: 365
  }
}
```

**Savings:** ~$0.005-0.01/month

### 5. Run Less Frequently

Monthly schedule instead of weekly:

```hcl
scheduler = {
  scheduler = "cron(0 8 1 * ? *)"   # 1st of month at 8 AM UTC
  purchaser = "cron(0 8 4 * ? *)"   # 4th of month at 8 AM UTC
  reporter  = "cron(0 8 1 * ? *)"   # 1st of month at 8 AM UTC
}
```

**Savings:** ~$0.50-1.00/month (from reduced Lambda and CloudWatch costs)

## Hidden Costs to Consider

### 1. Savings Plans Purchase Costs

**Not an infrastructure cost** — This module facilitates purchasing AWS Savings Plans, which are separate financial commitments. The infrastructure costs (~$0.71/month) are minimal compared to typical Savings Plans commitments ($100s-$1000s/month).

### 2. Cost Explorer API

Some AWS accounts may incur charges for Cost Explorer API calls. Verify your account's pricing:

```bash
aws ce get-cost-and-usage help
```

**Typical costs:** $0.01 per API call (check AWS pricing for your region)

### 3. Cross-Account IAM Role Assumption

If using AWS Organizations with cross-account role assumption (`assume_role_arn`), verify that `sts:AssumeRole` calls are free (they typically are, but verify for your account type).

### 4. KMS Encryption

If using customer-managed KMS keys for S3 or SQS encryption:

```hcl
s3_config = {
  encryption = {
    kms_key_arn = "arn:aws:kms:region:account:key/key-id"
  }
}
```

**KMS costs:**
- $1/month per customer-managed key
- $0.03 per 10,000 encryption/decryption requests

**Note:** Using AWS-managed keys (`alias/aws/s3`, `alias/aws/sqs`) is free.

### 5. Data Transfer

**Free tier:** 100 GB outbound per month

This module's data transfer is negligible (<1 MB/month) and well within free tier.

## Cost Monitoring

### Track Module Costs

Use AWS Cost Explorer with resource tags:

```hcl
tags = {
  Module      = "terraform-aws-sp-autopilot"
  Environment = "production"
  CostCenter  = "finops"
}
```

**Filter by tag in Cost Explorer:**

```bash
aws ce get-cost-and-usage \
  --time-period Start=2024-01-01,End=2024-01-31 \
  --granularity MONTHLY \
  --metrics BlendedCost \
  --filter file://filter.json
```

**filter.json:**
```json
{
  "Tags": {
    "Key": "Module",
    "Values": ["terraform-aws-sp-autopilot"]
  }
}
```

### CloudWatch Cost Anomaly Detection

Enable AWS Cost Anomaly Detection for the module's resources to catch unexpected cost increases.

## ROI Calculation

**Infrastructure Cost:** ~$8-10/year

**Typical Savings Plans Savings:** 20-66% on compute spend

**Break-even:** If this module helps you maintain just **$50/year in additional Savings Plans coverage**, the ROI is **5:1 or better**.

**Example:**
- EC2 spend: $10,000/month
- Savings Plans discount: 40%
- Coverage increase: 5% (from 85% → 90%)
- Additional annual savings: ~$2,400
- Module cost: ~$10/year
- **ROI: 240:1**

## FAQ

### Why is CloudWatch the largest cost component?

CloudWatch Logs ingestion and storage dominate costs due to:
- Lambda function logs (verbose by design for auditability)
- 30-day retention period
- CloudWatch Alarms ($0.10 each)

**Solution:** Reduce log retention or disable alarms if not needed.

### Can I run this module for free?

Nearly — with optimizations:
- Monthly schedules only
- Disable CloudWatch Alarms
- 7-day log retention (requires code modification)
- Estimated cost: **~$0.20-0.40/month** ($2.40-4.80/year)

AWS Free Tier covers some costs, but CloudWatch Logs ingestion typically exceeds free tier limits.

### What if I enable all three SP types (Compute, Database, SageMaker)?

Minimal cost increase:
- Same Lambda invocations (combined logic)
- Slightly more log data (~20% increase)
- Same infrastructure

**Estimated increase:** ~$0.10-0.20/month

### Does dry-run mode cost less?

Slightly — Purchaser Lambda won't execute in dry-run mode, saving ~1-2 invocations/month:

**Savings:** ~$0.0001/month (negligible)

## Cost Comparison

### vs. Manual Savings Plans Management

**Manual process:**
- DevOps engineer time: 2 hours/month at $100/hour = **$200/month**
- Module cost: **$0.71/month**

**Savings: $199/month** ($2,388/year)

### vs. Third-Party SaaS Tools

Many FinOps SaaS platforms charge:
- 3-5% of cloud spend, or
- $500-5,000/month flat fee

**Module cost:** **$0.71/month** (one-time setup + ongoing infrastructure)

**Savings: $500-5,000/month**

## Next Steps

- [Deploy in dry-run mode](examples/dry-run/README.md) to evaluate before committing
- [Monitor costs with tags](#cost-monitoring) to track actual spend
- [Optimize settings](#cost-optimization-tips) based on your usage patterns
- See [Testing Guide](TESTING.md) for cost-effective testing strategies

---

**Questions about costs?** Open an issue or check the [main README](README.md) for support options.

# Operations Runbook

Day-to-day operational procedures for managing AWS Savings Plans Autopilot after initial deployment.

## Table of Contents

- [Overview](#overview)
- [Quick Reference](#quick-reference)
  - [Common AWS CLI Commands](#common-aws-cli-commands)
  - [Important Terraform Outputs](#important-terraform-outputs)
  - [Key Lambda Functions](#key-lambda-functions)
- [Daily Operations](#daily-operations)
  - [Monitoring Email Notifications](#monitoring-email-notifications)
  - [Checking CloudWatch Alarms](#checking-cloudwatch-alarms)
- [Weekly Operations](#weekly-operations)
  - [Reviewing Coverage Trends](#reviewing-coverage-trends)
  - [Checking S3 Coverage Reports](#checking-s3-coverage-reports)
  - [Monitoring Lambda Execution Success](#monitoring-lambda-execution-success)
- [Monthly Operations](#monthly-operations)
  - [Verifying Purchase Cycle](#verifying-purchase-cycle)
  - [Reviewing Queued Purchases](#reviewing-queued-purchases)
  - [Validating Coverage Progress](#validating-coverage-progress)
  - [Monthly Operations Checklist](#monthly-operations-checklist)
- [Purchase Review and Management](#purchase-review-and-management)
  - [Viewing Queued Purchases](#viewing-queued-purchases)
  - [Canceling Specific Purchases](#canceling-specific-purchases)
  - [Understanding the Review Window](#understanding-the-review-window)
  - [Queue Message Format](#queue-message-format)
- [Automation Control](#automation-control)
  - [Temporarily Pausing Automation](#temporarily-pausing-automation)
  - [Disabling Specific Lambda Functions](#disabling-specific-lambda-functions)
  - [Re-enabling Automation](#re-enabling-automation)
  - [Impact of Disabling Components](#impact-of-disabling-components)
- [Configuration Adjustments](#configuration-adjustments)
  - [Adjusting Coverage Targets](#adjusting-coverage-targets)
  - [Changing Purchase Limits](#changing-purchase-limits)
  - [Modifying Term Mix](#modifying-term-mix)
  - [Using Dry Run Mode](#using-dry-run-mode)
  - [Applying Configuration Changes](#applying-configuration-changes)
- [Monitoring and Alerting](#monitoring-and-alerting)
  - [CloudWatch Alarm Reference](#cloudwatch-alarm-reference)
  - [Investigating Lambda Errors](#investigating-lambda-errors)
  - [Checking Dead Letter Queue](#checking-dead-letter-queue)
  - [Interpreting SNS Notifications](#interpreting-sns-notifications)
- [Troubleshooting Common Scenarios](#troubleshooting-common-scenarios)
  - [Coverage Not Reaching Target](#coverage-not-reaching-target)
  - [Unexpected Purchase Amounts](#unexpected-purchase-amounts)
  - [No Purchases Scheduled](#no-purchases-scheduled)
  - [Failed Purchase Execution](#failed-purchase-execution)
  - [Missing Email Notifications](#missing-email-notifications)
- [Advanced Operations](#advanced-operations)
  - [Manual Lambda Invocation](#manual-lambda-invocation)
  - [Emergency Pause Procedure](#emergency-pause-procedure)
  - [Adjusting Strategy Mid-Month](#adjusting-strategy-mid-month)
  - [Recovering from Failed Purchases](#recovering-from-failed-purchases)
  - [Cross-Account Operations](#cross-account-operations)
- [Operational Workflows](#operational-workflows)
  - [Monthly Purchase Verification Workflow](#monthly-purchase-verification-workflow)
  - [Investigating Coverage Trends Workflow](#investigating-coverage-trends-workflow)
  - [Emergency Pause Workflow](#emergency-pause-workflow)
  - [Strategy Adjustment Workflow](#strategy-adjustment-workflow)

## Overview

This runbook provides operational guidance for managing AWS Savings Plans Autopilot after initial deployment. It covers routine verification tasks, monitoring procedures, configuration adjustments, and troubleshooting common scenarios.

**Target Audience:** DevOps engineers, cloud operations teams, FinOps practitioners

**Prerequisites:**
- Module successfully deployed via Terraform
- AWS CLI configured with appropriate credentials
- Access to AWS Console (CloudWatch, SQS, Lambda, Cost Explorer)
- Terraform workspace access for configuration changes

**Operational Lifecycle:**
1. **Daily**: Monitor email notifications and CloudWatch alarms
2. **Weekly**: Review coverage trends and Lambda execution logs
3. **Monthly**: Verify purchase cycle, review queued purchases before execution
4. **As Needed**: Adjust configuration, investigate issues, pause automation

---

## Quick Reference

### Common AWS CLI Commands

```bash
# View pending purchases in queue
aws sqs receive-message \
  --queue-url $(terraform output -raw queue_url) \
  --max-number-of-messages 10

# Check current coverage (Compute)
aws ce get-savings-plans-coverage \
  --time-period Start=$(date -u -d '1 day ago' +%Y-%m-%d),End=$(date -u +%Y-%m-%d) \
  --granularity DAILY

# List recent Savings Plans purchases
aws savingsplans describe-savings-plans \
  --filters name=start,values=$(date -u -d '30 days ago' +%Y-%m-%d) \
  --max-results 20

# Check Lambda execution logs
aws logs tail /aws/lambda/sp-autopilot-scheduler --follow

# View CloudWatch alarm status
aws cloudwatch describe-alarms \
  --alarm-name-prefix sp-autopilot

# Download latest coverage report from S3
aws s3 cp s3://$(terraform output -raw reports_bucket)/coverage-reports/latest.json ./
```

### Important Terraform Outputs

| Output | Purpose | Usage |
|--------|---------|-------|
| `queue_url` | SQS queue for purchase intents | Review/cancel pending purchases |
| `dlq_url` | Dead letter queue for failed messages | Investigate persistent failures |
| `reports_bucket` | S3 bucket for coverage reports | Access detailed coverage data |
| `sns_topic_arn` | SNS topic for notifications | Verify subscription status |
| `scheduler_function_name` | Scheduler Lambda name | Manual invocation, log access |
| `purchaser_function_name` | Purchaser Lambda name | Manual invocation, log access |
| `reporter_function_name` | Reporter Lambda name | Manual invocation, log access |
| `scheduler_rule_name` | EventBridge scheduler rule | Pause/resume automation |
| `purchaser_rule_name` | EventBridge purchaser rule | Pause/resume automation |
| `reporter_rule_name` | EventBridge reporter rule | Pause/resume automation |

### Key Lambda Functions

| Function | Schedule | Purpose | Dry Run Impact |
|----------|----------|---------|----------------|
| **Scheduler** | 1st of month (default) | Analyzes coverage, queues purchases | Sends email only, no SQS messages |
| **Purchaser** | 4th of month (default) | Executes queued purchases | N/A (always live) |
| **Reporter** | 15th of month (default) | Generates coverage reports | N/A (read-only) |

---

## Daily Operations

### Monitoring Email Notifications

**Frequency:** Check inbox daily for SNS notifications

**Email Types:**
1. **Purchase Scheduled** (from Scheduler Lambda)
   - Subject: `[SP Autopilot] Purchase Scheduled - {YYYY-MM-DD}`
   - Contains: Recommended purchases queued to SQS
   - Action: Review recommendations, cancel unwanted purchases before Purchaser runs

2. **Purchase Executed** (from Purchaser Lambda)
   - Subject: `[SP Autopilot] Purchase Summary - {YYYY-MM-DD}`
   - Contains: Completed purchases with hourly commitments
   - Action: Verify expected purchases executed successfully

3. **Coverage Report** (from Reporter Lambda)
   - Subject: `[SP Autopilot] Coverage Report - {YYYY-MM-DD}`
   - Contains: Current coverage percentages, savings utilization
   - Action: Review coverage trends, validate progress toward target

**⚠️ Alert Conditions:**
- **No email after scheduled run** - Check CloudWatch Logs for Lambda errors
- **Unexpected purchase amounts** - Review queue before next Purchaser run
- **Coverage declining** - Investigate expiring Savings Plans or usage changes

### Checking CloudWatch Alarms

**Frequency:** Daily via AWS Console or CLI

```bash
# View all alarms for the module
aws cloudwatch describe-alarms \
  --alarm-name-prefix sp-autopilot \
  --state-value ALARM

# Get alarm details
aws cloudwatch describe-alarm-history \
  --alarm-name sp-autopilot-scheduler-errors \
  --max-records 10
```

**Expected State:** All alarms in `OK` state

**Alarm Thresholds:**
- **Lambda Errors**: ≥1 error triggers alarm
- **DLQ Depth**: ≥1 message in DLQ triggers alarm

**Response Actions:**
- **Scheduler Errors**: Check CloudWatch Logs, verify IAM permissions
- **Purchaser Errors**: Review SQS messages, check service quotas
- **DLQ Messages**: Investigate failed purchases, may require manual retry

---

## Weekly Operations

### Reviewing Coverage Trends

**Frequency:** Weekly (e.g., every Monday)

**Objective:** Validate coverage is progressing toward target or maintaining steady state

**Procedure:**

1. **Check Cost Explorer Dashboard:**
   ```bash
   # Open Cost Explorer - Savings Plans Coverage
   # AWS Console > Cost Explorer > Savings Plans > Coverage
   ```

2. **Review Coverage Percentage:**
   - **Compute Savings Plans**: Compare current % to `coverage_target_percent`
   - **Database Savings Plans**: Check if enabled and trending correctly
   - **SageMaker Savings Plans**: Check if enabled and trending correctly

3. **Analyze Trends:**
   - **Increasing**: Good - automation working as expected
   - **Flat at target**: Good - steady state maintenance
   - **Decreasing**: Investigate - usage drop or expiring plans

4. **Expected Coverage Progression:**
   - **Monthly increase**: ~`max_purchase_percent` of gap
   - **Example**: Target 90%, current 70%, max_purchase 10%
     - Gap = 20%, purchase = 10% of gap = 2%
     - Expected next month: 72%

### Checking S3 Coverage Reports

**Frequency:** Weekly

**Objective:** Access detailed coverage data beyond Cost Explorer

**Procedure:**

1. **List Available Reports:**
   ```bash
   aws s3 ls s3://$(terraform output -raw reports_bucket)/coverage-reports/
   ```

2. **Download Latest Report:**
   ```bash
   aws s3 cp s3://$(terraform output -raw reports_bucket)/coverage-reports/latest.json ./coverage-report.json
   ```

3. **Review Report Contents:**
   - **Coverage by service**: EC2, Lambda, Fargate, RDS, etc.
   - **Utilization percentage**: How much of purchased commitment is being used
   - **On-Demand spend**: Remaining uncovered spend
   - **Total covered spend**: Spend covered by Savings Plans

4. **Report Structure:**
   ```json
   {
     "timestamp": "2024-01-15T12:00:00Z",
     "compute_sp": {
       "coverage_percent": 85.5,
       "on_demand_spend": "1234.56",
       "covered_spend": "5678.90"
     },
     "database_sp": { ... },
     "sagemaker_sp": { ... }
   }
   ```

### Monitoring Lambda Execution Success

**Frequency:** Weekly

**Objective:** Verify all Lambda functions executing without errors

**Procedure:**

1. **Check Recent Executions:**
   ```bash
   # Scheduler Lambda
   aws logs tail /aws/lambda/$(terraform output -raw scheduler_function_name) --since 7d | grep ERROR

   # Purchaser Lambda
   aws logs tail /aws/lambda/$(terraform output -raw purchaser_function_name) --since 7d | grep ERROR

   # Reporter Lambda
   aws logs tail /aws/lambda/$(terraform output -raw reporter_function_name) --since 7d | grep ERROR
   ```

2. **Review Lambda Metrics:**
   ```bash
   # Check invocation count and errors
   aws cloudwatch get-metric-statistics \
     --namespace AWS/Lambda \
     --metric-name Errors \
     --dimensions Name=FunctionName,Value=$(terraform output -raw scheduler_function_name) \
     --start-time $(date -u -d '7 days ago' +%Y-%m-%dT%H:%M:%S) \
     --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
     --period 86400 \
     --statistics Sum
   ```

3. **Expected Results:**
   - **Invocations**: Match EventBridge schedule (e.g., 1/month for Scheduler)
   - **Errors**: 0
   - **Duration**: Consistent with baseline (typically <30s)

---

## Monthly Operations

### Verifying Purchase Cycle

**Frequency:** Monthly (after Scheduler runs, before Purchaser runs)

**Objective:** Confirm purchase recommendations are correct before execution

**Timeline Example:**
- **1st of month**: Scheduler runs, queues purchases
- **1st-3rd**: Review window (cancel unwanted purchases)
- **4th of month**: Purchaser runs, executes remaining purchases
- **5th onwards**: Verify purchases completed successfully

**Procedure:**

1. **After Scheduler Runs (Day 1):**
   - Check email for "Purchase Scheduled" notification
   - Review recommended purchases and amounts
   - Verify recommendations align with coverage gap

2. **During Review Window (Days 1-3):**
   - View queued purchases (see [Viewing Queued Purchases](#viewing-queued-purchases))
   - Cancel any unexpected purchases (see [Canceling Specific Purchases](#canceling-specific-purchases))

3. **After Purchaser Runs (Day 4+):**
   - Check email for "Purchase Summary" notification
   - Verify purchases executed successfully
   - Confirm coverage increased as expected

4. **Validate in AWS Console:**
   ```bash
   # List Savings Plans purchased in last 7 days
   aws savingsplans describe-savings-plans \
     --filters name=start,values=$(date -u -d '7 days ago' +%Y-%m-%d)
   ```

### Reviewing Queued Purchases

**Frequency:** Monthly (during review window)

**Objective:** Review and potentially cancel purchases before execution

See [Purchase Review and Management](#purchase-review-and-management) section for detailed procedures.

### Validating Coverage Progress

**Frequency:** Monthly (end of month)

**Objective:** Confirm coverage increased toward target after purchase

**Procedure:**

1. **Check Current Coverage:**
   - AWS Console > Cost Explorer > Savings Plans > Coverage
   - Compare to previous month's coverage

2. **Calculate Expected Increase:**
   - **Coverage gap** = `coverage_target_percent` - current coverage
   - **Expected purchase** = gap × `max_purchase_percent`
   - **New coverage** ≈ current + expected purchase

3. **Validate Results:**
   - ✅ Coverage increased by ~expected amount
   - ✅ Coverage at or below `max_coverage_cap`
   - ✅ No unexpected purchases

4. **Investigate Discrepancies:**
   - Coverage increased less than expected → Check if purchases executed
   - Coverage increased more than expected → Review purchase history
   - Coverage decreased → Investigate expiring plans or usage drop

### Monthly Operations Checklist

**Day 1 (Scheduler Run Day):**
- [ ] Verify "Purchase Scheduled" email received
- [ ] Review recommended purchase amounts
- [ ] Check queue for pending purchases

**Days 1-3 (Review Window):**
- [ ] Review all queued purchases
- [ ] Cancel any unwanted purchases
- [ ] Confirm queue contains expected purchases

**Day 4 (Purchaser Run Day):**
- [ ] Verify "Purchase Summary" email received
- [ ] Confirm expected purchases executed
- [ ] Check for any purchase errors in CloudWatch

**Day 5+ (Post-Purchase):**
- [ ] Validate new Savings Plans in AWS Console
- [ ] Check coverage increased as expected
- [ ] Review Cost Explorer for updated coverage %

**End of Month:**
- [ ] Compare month-over-month coverage trends
- [ ] Review S3 coverage reports
- [ ] Update coverage targets if needed

---

## Purchase Review and Management

### Viewing Queued Purchases

**When:** During review window (between Scheduler and Purchaser runs)

**Objective:** See all pending purchases before execution

**Procedure:**

```bash
# Receive messages from queue (without deleting)
aws sqs receive-message \
  --queue-url $(terraform output -raw queue_url) \
  --max-number-of-messages 10 \
  --attribute-names All \
  --message-attribute-names All

# Pretty-print message bodies
aws sqs receive-message \
  --queue-url $(terraform output -raw queue_url) \
  --max-number-of-messages 10 \
  | jq -r '.Messages[].Body' \
  | jq '.'
```

**Message Contents:**
- `savingsPlanType`: "COMPUTE_SP" | "DATABASE_SP" | "SAGEMAKER_SP"
- `commitment`: Hourly commitment in USD (e.g., "1.234")
- `term`: "ONE_YEAR" | "THREE_YEARS"
- `paymentOption`: "ALL_UPFRONT" | "PARTIAL_UPFRONT" | "NO_UPFRONT"
- `clientToken`: Idempotency token for purchase

**Example Output:**
```json
{
  "savingsPlanType": "COMPUTE_SP",
  "commitment": "5.67",
  "term": "THREE_YEARS",
  "paymentOption": "NO_UPFRONT",
  "clientToken": "sp-autopilot-compute-2024-01-01-abc123"
}
```

### Canceling Specific Purchases

**When:** During review window, before Purchaser runs

**Objective:** Remove unwanted purchases from queue

**Procedure:**

1. **Receive Message with Receipt Handle:**
   ```bash
   aws sqs receive-message \
     --queue-url $(terraform output -raw queue_url) \
     --max-number-of-messages 10
   ```

2. **Identify Message to Cancel:**
   - Review message body for purchase details
   - Note the `ReceiptHandle` from message

3. **Delete Message from Queue:**
   ```bash
   aws sqs delete-message \
     --queue-url $(terraform output -raw queue_url) \
     --receipt-handle "AQEB...receipt-handle-here..."
   ```

4. **Confirm Deletion:**
   ```bash
   # Verify message no longer in queue
   aws sqs get-queue-attributes \
     --queue-url $(terraform output -raw queue_url) \
     --attribute-names ApproximateNumberOfMessages
   ```

**⚠️ Important:**
- Deleted messages **cannot** be recovered
- Purchaser Lambda will **not** execute deleted purchases
- Next Scheduler run may re-queue similar purchases if coverage gap persists

### Understanding the Review Window

**Default Schedule:**
- **Scheduler**: 1st of month at 08:00 UTC
- **Purchaser**: 4th of month at 08:00 UTC
- **Review Window**: ~3 days

**Purpose:**
- Allows human review of automated recommendations
- Provides time to cancel unwanted purchases
- Prevents accidental over-commitment

**Customizing Review Window:**

```hcl
# Extend review window to 5 days
module "savings_plans" {
  scheduler = {
    scheduler  = "cron(0 8 1 * ? *)"   # 1st of month
    purchaser  = "cron(0 8 6 * ? *)"   # 6th of month (5-day window)
    reporter   = "cron(0 8 15 * ? *)"  # 15th of month
  }
}
```

**Best Practices:**
- **Minimum**: 1 day (allows same-day review)
- **Recommended**: 3-5 days (accounts for weekends/holidays)
- **Maximum**: 14 days (balances review time with timely purchases)

### Queue Message Format

**Complete Message Structure:**

```json
{
  "Messages": [
    {
      "MessageId": "12345678-1234-1234-1234-123456789012",
      "ReceiptHandle": "AQEB...long-receipt-handle...",
      "MD5OfBody": "abc123...",
      "Body": "{\"savingsPlanType\":\"COMPUTE_SP\",\"commitment\":\"5.67\",\"term\":\"THREE_YEARS\",\"paymentOption\":\"NO_UPFRONT\",\"clientToken\":\"sp-autopilot-compute-2024-01-01-abc123\"}",
      "Attributes": {
        "SentTimestamp": "1704096000000",
        "ApproximateReceiveCount": "0",
        "ApproximateFirstReceiveTimestamp": "0"
      }
    }
  ]
}
```

**Key Fields:**
- **MessageId**: Unique SQS message identifier
- **ReceiptHandle**: Required for deleting message (canceling purchase)
- **Body**: JSON string containing purchase details
- **SentTimestamp**: When Scheduler queued the purchase
- **ApproximateReceiveCount**: How many times message was received (0 = not processed)

---

## Automation Control

### Temporarily Pausing Automation

**Use Case:** Temporarily stop automation during organizational changes, budget freezes, or investigations

**Procedure:**

1. **Disable Scheduler (Prevents New Purchases):**
   ```bash
   aws events disable-rule \
     --name $(terraform output -raw scheduler_rule_name)
   ```

2. **Disable Purchaser (Prevents Execution of Queued Purchases):**
   ```bash
   aws events disable-rule \
     --name $(terraform output -raw purchaser_rule_name)
   ```

3. **Verify Rules Disabled:**
   ```bash
   aws events describe-rule --name $(terraform output -raw scheduler_rule_name)
   aws events describe-rule --name $(terraform output -raw purchaser_rule_name)
   ```

4. **Expected Output:**
   ```json
   {
     "State": "DISABLED",
     ...
   }
   ```

**⚠️ Impact:**
- Scheduler disabled: No new purchases queued
- Purchaser disabled: Queued purchases remain in SQS but won't execute
- Reporter disabled: Coverage reports not generated (no financial impact)

### Disabling Specific Lambda Functions

**Use Cases:**
- **Disable Scheduler only**: Stop new purchases while allowing queued purchases to execute
- **Disable Purchaser only**: Review purchases indefinitely before manual execution
- **Disable Reporter only**: Reduce operational noise during incidents

**Procedure:**

```bash
# Disable Scheduler only
aws events disable-rule --name $(terraform output -raw scheduler_rule_name)

# Disable Purchaser only
aws events disable-rule --name $(terraform output -raw purchaser_rule_name)

# Disable Reporter only
aws events disable-rule --name $(terraform output -raw reporter_rule_name)
```

**Alternative - Lambda Function Configuration:**

```bash
# Add environment variable to Lambda to skip execution
aws lambda update-function-configuration \
  --function-name $(terraform output -raw scheduler_function_name) \
  --environment Variables={SKIP_EXECUTION=true}
```

**Note:** EventBridge rule disabling is preferred - cleaner and doesn't modify Lambda configuration.

### Re-enabling Automation

**Procedure:**

```bash
# Re-enable Scheduler
aws events enable-rule --name $(terraform output -raw scheduler_rule_name)

# Re-enable Purchaser
aws events enable-rule --name $(terraform output -raw purchaser_rule_name)

# Re-enable Reporter
aws events enable-rule --name $(terraform output -raw reporter_rule_name)
```

**Verify:**

```bash
# Check all rules enabled
aws events describe-rule --name $(terraform output -raw scheduler_rule_name) | jq -r '.State'
aws events describe-rule --name $(terraform output -raw purchaser_rule_name) | jq -r '.State'
aws events describe-rule --name $(terraform output -raw reporter_rule_name) | jq -r '.State'
```

**Expected Output:** `ENABLED` for all rules

**⚠️ Important:**
- Re-enabling during the month will **not** trigger missed runs
- Scheduler will run on next scheduled date (e.g., 1st of next month)
- Purchaser will process any messages still in queue on next scheduled date

### Impact of Disabling Components

| Component Disabled | Impact | Coverage Growth | Financial Risk | Notifications |
|-------------------|--------|-----------------|----------------|---------------|
| **Scheduler Only** | No new purchases queued | Stops | None (existing queue safe) | Purchase Scheduled emails stop |
| **Purchaser Only** | Queued purchases not executed | Stops | None (no purchases made) | Purchase Summary emails stop |
| **Reporter Only** | No coverage reports generated | Unchanged | None (read-only) | Coverage Report emails stop |
| **All Three** | Full automation pause | Stops | None | All emails stop |

**Best Practice:** Disable Scheduler + Purchaser together for complete pause, keep Reporter running for visibility.

---

## Configuration Adjustments

### Adjusting Coverage Targets

**Use Case:** Change target coverage percentage based on cost optimization goals

**Current Value:** Check `coverage_target_percent` in Terraform configuration

**Procedure:**

1. **Edit Terraform Configuration:**
   ```hcl
   # terraform.tfvars or main.tf
   module "savings_plans" {
     purchase_strategy = {
       coverage_target_percent = 85  # Changed from 90
       max_coverage_cap        = 95
       simple = {
         max_purchase_percent = 10
       }
     }
   }
   ```

2. **Review Change Impact:**
   - **Increasing target**: More aggressive purchases, faster coverage growth
   - **Decreasing target**: Slower purchases, may stop if already above new target

3. **Apply Configuration:**
   ```bash
   terraform plan
   terraform apply
   ```

4. **Verify Update:**
   - Next Scheduler run will use new target
   - Check CloudWatch Logs after next run to confirm

**⚠️ Important:**
- Target must be ≤ `max_coverage_cap`
- Target must be > current coverage for purchases to continue
- Changes take effect on next Scheduler run (not immediate)

### Changing Purchase Limits

**Use Case:** Adjust purchase pace (faster or slower coverage growth)

**Current Value:** Check `max_purchase_percent` in Terraform configuration

**Procedure:**

1. **Edit Terraform Configuration:**
   ```hcl
   module "savings_plans" {
     purchase_strategy = {
       coverage_target_percent = 90
       max_coverage_cap        = 95
       simple = {
         max_purchase_percent = 15  # Changed from 10 (faster growth)
       }
     }
   }
   ```

2. **Calculate Impact:**
   - **Coverage gap**: 20% (target 90%, current 70%)
   - **Old limit (10%)**: Purchase 2% coverage
   - **New limit (15%)**: Purchase 3% coverage
   - **Result**: 50% faster growth per month

3. **Apply Configuration:**
   ```bash
   terraform plan
   terraform apply
   ```

**⚠️ Constraints:**
- `max_purchase_percent` must be between 1-100
- Higher values = faster growth but higher monthly financial commitment
- Lower values = slower growth but more conservative spending

### Modifying Term Mix

**Use Case:** Change proportion of 1-year vs 3-year Savings Plans

**Current Value:** Check term mix weights in Terraform configuration

**Procedure:**

1. **Edit Terraform Configuration (Compute SP):**
   ```hcl
   module "savings_plans" {
     sp_plans = {
       compute = {
         enabled              = true
         all_upfront_one_year   = 0.5  # 50% 1-year
         all_upfront_three_year = 0.5  # 50% 3-year
       }
     }
   }
   ```

2. **Edit Terraform Configuration (SageMaker SP):**
   ```hcl
   module "savings_plans" {
     sp_plans = {
       sagemaker = {
         enabled              = true
         all_upfront_one_year   = 0.7  # 70% 1-year
         all_upfront_three_year = 0.3  # 30% 3-year
       }
     }
   }
   ```

3. **Considerations:**
   - **More 3-year**: Higher discounts (up to 66%), less flexibility
   - **More 1-year**: Lower discounts, more flexibility for changing workloads

4. **Apply Configuration:**
   ```bash
   terraform plan
   terraform apply
   ```

**Note:** Database Savings Plans only support 1-year terms (AWS constraint).

### Using Dry Run Mode

**Use Case:** Test configuration changes without making actual purchases

**When to Enable:**
- Testing new coverage targets or purchase limits
- After major configuration changes
- Before re-enabling automation after pause
- Monthly purchase review (see recommendations without queueing)

**Procedure:**

1. **Enable Dry Run:**
   ```hcl
   module "savings_plans" {
     lambda_config = {
       scheduler = {
         dry_run = true
       }
     }
   }
   ```

2. **Apply Configuration:**
   ```bash
   terraform apply
   ```

3. **Test Scheduler Run:**
   ```bash
   # Manual invocation to test immediately
   aws lambda invoke \
     --function-name $(terraform output -raw scheduler_function_name) \
     --payload '{}' \
     output.json
   ```

4. **Review Results:**
   - Check email for "Purchase Scheduled" notification
   - Verify recommendations look correct
   - **No messages in SQS queue** (dry run doesn't queue purchases)

5. **Disable Dry Run (Go Live):**
   ```hcl
   module "savings_plans" {
     lambda_config = {
       scheduler = {
         dry_run = false
       }
     }
   }
   ```

**⚠️ Important:**
- Dry run **only affects Scheduler** Lambda
- Purchaser always executes (processes real queue messages)
- Reporter always runs (read-only, no dry run mode)

### Applying Configuration Changes

**Standard Workflow:**

1. **Edit Terraform Configuration:**
   - Modify `terraform.tfvars` or module block in `main.tf`

2. **Review Changes:**
   ```bash
   terraform plan
   ```

3. **Validate Plan Output:**
   - Check which resources will change
   - Verify Lambda environment variables updated
   - Confirm EventBridge schedules if changed

4. **Apply Changes:**
   ```bash
   terraform apply
   ```

5. **Verify Update:**
   ```bash
   # Check Lambda configuration
   aws lambda get-function-configuration \
     --function-name $(terraform output -raw scheduler_function_name) \
     | jq -r '.Environment.Variables'
   ```

**⚠️ Important:**
- Configuration changes take effect **immediately** for Lambda functions
- EventBridge schedule changes don't affect already-scheduled runs
- Use dry run mode to test configuration before going live

---

## Monitoring and Alerting

### CloudWatch Alarm Reference

| Alarm Name | Metric | Threshold | Meaning |
|------------|--------|-----------|---------|
| `{name_prefix}-scheduler-errors` | Lambda Errors | ≥1 in 5 min | Scheduler Lambda failed |
| `{name_prefix}-purchaser-errors` | Lambda Errors | ≥1 in 5 min | Purchaser Lambda failed |
| `{name_prefix}-reporter-errors` | Lambda Errors | ≥1 in 5 min | Reporter Lambda failed |
| `{name_prefix}-dlq-messages` | SQS Messages | ≥1 message | Purchase failed after retries |

**Default Actions:**
- Alarm state: SNS notification sent to configured emails
- OK state: SNS notification sent (alarm recovered)

**Viewing Alarms:**

```bash
# List all alarms
aws cloudwatch describe-alarms --alarm-name-prefix sp-autopilot

# Get alarm state
aws cloudwatch describe-alarms \
  --alarm-names sp-autopilot-scheduler-errors \
  | jq -r '.MetricAlarms[].StateValue'
```

### Investigating Lambda Errors

**Procedure:**

1. **Identify Failed Lambda:**
   - Check CloudWatch alarm notification email
   - Note Lambda function name (Scheduler, Purchaser, or Reporter)

2. **View Recent Logs:**
   ```bash
   # Tail logs in real-time
   aws logs tail /aws/lambda/$(terraform output -raw scheduler_function_name) --follow

   # View last 100 lines
   aws logs tail /aws/lambda/$(terraform output -raw scheduler_function_name) --since 1h

   # Filter for errors
   aws logs tail /aws/lambda/$(terraform output -raw scheduler_function_name) --since 24h --filter ERROR
   ```

3. **Common Error Patterns:**
   - **AccessDeniedException**: IAM permission missing → Review IAM policies
   - **ValidationException**: Invalid purchase parameters → Check configuration
   - **ServiceQuotaExceededException**: AWS limit reached → Request quota increase
   - **ThrottlingException**: API rate limit → Wait and retry

4. **Get Full Stack Trace:**
   ```bash
   aws logs filter-log-events \
     --log-group-name /aws/lambda/$(terraform output -raw scheduler_function_name) \
     --start-time $(date -u -d '1 hour ago' +%s)000 \
     --filter-pattern "ERROR"
   ```

**See Also:** [ERROR_PATTERNS.md](../../ERROR_PATTERNS.md) for detailed error handling guide.

### Checking Dead Letter Queue

**When:** DLQ alarm triggered (message failed after max retries)

**Procedure:**

1. **Check DLQ Depth:**
   ```bash
   aws sqs get-queue-attributes \
     --queue-url $(terraform output -raw dlq_url) \
     --attribute-names ApproximateNumberOfMessages
   ```

2. **Receive Messages from DLQ:**
   ```bash
   aws sqs receive-message \
     --queue-url $(terraform output -raw dlq_url) \
     --max-number-of-messages 10 \
     --attribute-names All
   ```

3. **Analyze Failed Message:**
   - Review purchase details in message body
   - Check `ApproximateReceiveCount` (how many times Purchaser tried)
   - Identify failure reason from CloudWatch Logs

4. **Resolution Options:**

   **Option A: Fix Issue and Retry**
   ```bash
   # Fix underlying issue (e.g., add IAM permission)
   # Move message back to main queue for retry
   aws sqs send-message \
     --queue-url $(terraform output -raw queue_url) \
     --message-body "$(aws sqs receive-message --queue-url $(terraform output -raw dlq_url) | jq -r '.Messages[0].Body')"

   # Delete from DLQ
   aws sqs delete-message \
     --queue-url $(terraform output -raw dlq_url) \
     --receipt-handle "RECEIPT_HANDLE"
   ```

   **Option B: Abandon Failed Purchase**
   ```bash
   # Delete message from DLQ (give up on purchase)
   aws sqs delete-message \
     --queue-url $(terraform output -raw dlq_url) \
     --receipt-handle "RECEIPT_HANDLE"
   ```

**⚠️ Important:**
- Messages in DLQ won't be processed automatically
- Investigate root cause before retrying
- Next Scheduler run may re-queue similar purchases

### Interpreting SNS Notifications

**Purchase Scheduled Notification:**

```
Subject: [SP Autopilot] Purchase Scheduled - 2024-01-01

Scheduled Compute Savings Plans purchases:
- 3-year, No Upfront: $5.67/hour
- 1-year, All Upfront: $2.34/hour

Total queued: 2 plans
Review window: Until 2024-01-04 08:00 UTC
Queue URL: https://sqs.us-east-1.amazonaws.com/.../sp-autopilot-queue
```

**Action:**
- Verify amounts reasonable given coverage gap
- Cancel unwanted purchases via SQS before Purchaser runs

**Purchase Summary Notification:**

```
Subject: [SP Autopilot] Purchase Summary - 2024-01-04

Successfully purchased 2 Savings Plans:
- Compute SP (3-year): $5.67/hour
- Compute SP (1-year): $2.34/hour

Total commitment: $8.01/hour ($70,168/year)
```

**Action:**
- Verify expected purchases executed
- Confirm coverage increased in Cost Explorer

**Coverage Report Notification:**

```
Subject: [SP Autopilot] Coverage Report - 2024-01-15

Current Coverage:
- Compute SP: 87.5% (target: 90%)
- Database SP: N/A (disabled)
- SageMaker SP: N/A (disabled)

Utilization: 95.2%
On-Demand Spend: $1,234.56/day
```

**Action:**
- Review coverage progress
- Investigate if coverage not trending toward target

---

## Troubleshooting Common Scenarios

### Coverage Not Reaching Target

**Symptoms:**
- Coverage not increasing despite monthly purchases
- Coverage stuck below `coverage_target_percent`

**Possible Causes:**

1. **Usage Increasing Faster Than Purchases:**
   - **Check:** Compare month-over-month usage trends in Cost Explorer
   - **Fix:** Increase `max_purchase_percent` to purchase faster

2. **Savings Plans Expiring:**
   - **Check:** List Savings Plans ending soon
     ```bash
     aws savingsplans describe-savings-plans \
       --filters name=end,values=$(date -u -d '30 days' +%Y-%m-%d)
     ```
   - **Fix:** Purchases will account for expirations in recommendations

3. **Purchase Blocked by `max_coverage_cap`:**
   - **Check:** Current coverage near `max_coverage_cap`?
   - **Fix:** Increase `max_coverage_cap` if appropriate

4. **Insufficient Recommendations:**
   - **Check:** Scheduler email shows small purchase amounts
   - **Fix:** Review `purchase_strategy.min_data_days` - may need more usage history

**Diagnostic Workflow:**

```bash
# 1. Check current coverage
aws ce get-savings-plans-coverage \
  --time-period Start=$(date -u -d '1 day ago' +%Y-%m-%d),End=$(date -u +%Y-%m-%d) \
  --granularity DAILY

# 2. List recent purchases
aws savingsplans describe-savings-plans \
  --filters name=start,values=$(date -u -d '30 days ago' +%Y-%m-%d)

# 3. Check Scheduler logs for recommendations
aws logs tail /aws/lambda/$(terraform output -raw scheduler_function_name) --since 7d
```

### Unexpected Purchase Amounts

**Symptoms:**
- Purchase amounts different from expected
- More/less commitment than anticipated

**Possible Causes:**

1. **Term Mix Not as Expected:**
   - **Check:** Review term weights in Terraform configuration
   - **Fix:** Adjust weights to desired distribution

2. **Multiple Savings Plan Types Enabled:**
   - **Check:** Verify only expected types enabled (Compute, Database, SageMaker)
   - **Fix:** Disable unwanted types in `sp_plans` configuration

3. **Usage Fluctuations:**
   - **Check:** Review Cost Explorer usage trends
   - **Fix:** Expected behavior - recommendations based on recent usage

4. **Payment Option Impact:**
   - **Check:** Payment option affects upfront cost, not hourly commitment
   - **Fix:** Hourly commitment is correct metric, not upfront payment

**Validation:**

```bash
# View exact purchase details from queue
aws sqs receive-message \
  --queue-url $(terraform output -raw queue_url) \
  --max-number-of-messages 10 \
  | jq -r '.Messages[].Body' | jq '.'
```

### No Purchases Scheduled

**Symptoms:**
- Scheduler ran but didn't queue any purchases
- "Purchase Scheduled" email shows zero plans

**Possible Causes:**

1. **Already at Target Coverage:**
   - **Check:** Current coverage ≥ `coverage_target_percent`
   - **Fix:** None needed - automation working correctly

2. **Insufficient Usage Data:**
   - **Check:** Scheduler logs show "Insufficient data" warning
   - **Fix:** Wait for more usage history (check `min_data_days` setting)

3. **Dry Run Mode Enabled:**
   - **Check:** Verify `lambda_config.scheduler.dry_run = false`
   - **Fix:** Disable dry run mode if ready for live purchases

4. **AWS Recommendations Below Minimum:**
   - **Check:** Scheduler logs show recommendations below `min_commitment_per_plan`
   - **Fix:** Lower minimum or wait for higher usage

**Diagnostic Workflow:**

```bash
# Check current coverage vs target
echo "Current coverage vs target"

# Review Scheduler logs for decision reasoning
aws logs tail /aws/lambda/$(terraform output -raw scheduler_function_name) --since 24h | grep "recommendation\|coverage\|decision"
```

### Failed Purchase Execution

**Symptoms:**
- Purchaser Lambda errors in CloudWatch
- Messages in Dead Letter Queue
- "Purchase Summary" email shows failures

**Possible Causes:**

1. **IAM Permission Missing:**
   - **Error:** `AccessDeniedException`
   - **Fix:** Add `savingsplans:CreateSavingsPlan` permission to Purchaser role

2. **Service Quota Exceeded:**
   - **Error:** `ServiceQuotaExceededException`
   - **Fix:** Request quota increase or clean up expired Savings Plans

3. **Invalid Purchase Parameters:**
   - **Error:** `ValidationException`
   - **Fix:** Review queue message format, check configuration

4. **Duplicate Purchase (Idempotency):**
   - **Error:** `DuplicateSavingsPlanException`
   - **Fix:** None needed - purchase already completed successfully

**Resolution Steps:**

```bash
# 1. Check DLQ for failed messages
aws sqs receive-message --queue-url $(terraform output -raw dlq_url)

# 2. Review Purchaser logs
aws logs tail /aws/lambda/$(terraform output -raw purchaser_function_name) --since 1h --filter ERROR

# 3. Check IAM permissions
aws iam get-role-policy \
  --role-name $(terraform output -raw purchaser_role_name) \
  --policy-name sp-autopilot-purchaser-policy

# 4. Verify service quotas
aws service-quotas get-service-quota \
  --service-code savingsplans \
  --quota-code L-A1F9B7B0  # Active Savings Plans quota
```

**See Also:** [ERROR_PATTERNS.md](../../ERROR_PATTERNS.md) for detailed error reference.

### Missing Email Notifications

**Symptoms:**
- Expected email not received
- SNS notification silence

**Possible Causes:**

1. **Email Subscription Not Confirmed:**
   - **Check:** SNS subscription status
     ```bash
     aws sns list-subscriptions-by-topic \
       --topic-arn $(terraform output -raw sns_topic_arn)
     ```
   - **Fix:** Confirm pending subscriptions from confirmation email

2. **Email Filtered as Spam:**
   - **Check:** Spam/junk folder
   - **Fix:** Whitelist sender (SNS no-reply address)

3. **Lambda Failed Before Sending:**
   - **Check:** CloudWatch Logs for Lambda errors
   - **Fix:** Resolve Lambda execution errors

4. **SNS Topic Misconfigured:**
   - **Check:** Verify topic exists and has subscriptions
   - **Fix:** Re-run `terraform apply` to fix SNS configuration

**Validation:**

```bash
# Check SNS topic subscriptions
aws sns list-subscriptions-by-topic \
  --topic-arn $(terraform output -raw sns_topic_arn) \
  | jq -r '.Subscriptions[] | "\(.Protocol): \(.Endpoint) (\(.SubscriptionArn))"'

# Expected output includes confirmed email subscriptions
```

---

## Advanced Operations

### Manual Lambda Invocation

**Use Case:** Test Lambda functions outside scheduled runs

**Procedure:**

```bash
# Invoke Scheduler manually
aws lambda invoke \
  --function-name $(terraform output -raw scheduler_function_name) \
  --payload '{}' \
  output.json

# Invoke Purchaser manually (processes current queue)
aws lambda invoke \
  --function-name $(terraform output -raw purchaser_function_name) \
  --payload '{}' \
  output.json

# Invoke Reporter manually
aws lambda invoke \
  --function-name $(terraform output -raw reporter_function_name) \
  --payload '{}' \
  output.json

# View output
cat output.json | jq '.'
```

**⚠️ Warning:**
- **Scheduler**: Will queue real purchases (unless dry_run=true)
- **Purchaser**: Will execute real purchases from queue
- **Reporter**: Safe to invoke anytime (read-only)

**Safe Testing:**

```bash
# Enable dry run before manual Scheduler invocation
aws lambda update-function-configuration \
  --function-name $(terraform output -raw scheduler_function_name) \
  --environment Variables={DRY_RUN=true}

# Invoke safely
aws lambda invoke \
  --function-name $(terraform output -raw scheduler_function_name) \
  --payload '{}' \
  output.json

# Disable dry run afterward
aws lambda update-function-configuration \
  --function-name $(terraform output -raw scheduler_function_name) \
  --environment Variables={DRY_RUN=false}
```

### Emergency Pause Procedure

**Use Case:** Immediate halt of all automation (e.g., budget overrun, organizational change)

**Procedure:**

1. **Disable All EventBridge Rules:**
   ```bash
   aws events disable-rule --name $(terraform output -raw scheduler_rule_name)
   aws events disable-rule --name $(terraform output -raw purchaser_rule_name)
   aws events disable-rule --name $(terraform output -raw reporter_rule_name)
   ```

2. **Purge SQS Queue (Cancel All Pending Purchases):**
   ```bash
   aws sqs purge-queue --queue-url $(terraform output -raw queue_url)
   ```

3. **Verify Queue Empty:**
   ```bash
   aws sqs get-queue-attributes \
     --queue-url $(terraform output -raw queue_url) \
     --attribute-names ApproximateNumberOfMessages
   ```

4. **Send Notification:**
   ```bash
   aws sns publish \
     --topic-arn $(terraform output -raw sns_topic_arn) \
     --subject "[SP Autopilot] EMERGENCY PAUSE ACTIVATED" \
     --message "All automation disabled. Queue purged. Manual intervention required before re-enabling."
   ```

**⚠️ Critical:**
- Purging queue is **irreversible** - all pending purchases lost
- Use only in true emergencies
- Document reason for pause in incident log

**Recovery:**

1. **Investigate Issue:**
   - Why was emergency pause needed?
   - What needs to change before resuming?

2. **Fix Root Cause:**
   - Adjust configuration if needed
   - Enable dry run mode for testing

3. **Re-enable Automation:**
   ```bash
   aws events enable-rule --name $(terraform output -raw scheduler_rule_name)
   aws events enable-rule --name $(terraform output -raw purchaser_rule_name)
   aws events enable-rule --name $(terraform output -raw reporter_rule_name)
   ```

### Adjusting Strategy Mid-Month

**Use Case:** Need to change purchase strategy between Scheduler runs

**Scenario:** Scheduler already ran (purchases queued), but strategy needs adjustment before Purchaser runs

**Options:**

**Option A: Cancel Queued Purchases, Adjust, Re-run Scheduler**

1. **Purge Queue:**
   ```bash
   aws sqs purge-queue --queue-url $(terraform output -raw queue_url)
   ```

2. **Update Configuration:**
   ```hcl
   module "savings_plans" {
     purchase_strategy = {
       coverage_target_percent = 85  # Adjusted
       max_coverage_cap        = 90  # Adjusted
       simple = {
         max_purchase_percent = 5   # Adjusted
       }
     }
   }
   ```

3. **Apply Changes:**
   ```bash
   terraform apply
   ```

4. **Manually Re-run Scheduler:**
   ```bash
   aws lambda invoke \
     --function-name $(terraform output -raw scheduler_function_name) \
     --payload '{}' \
     output.json
   ```

**Option B: Selectively Cancel Purchases, Keep Others**

1. **View Queued Purchases:**
   ```bash
   aws sqs receive-message \
     --queue-url $(terraform output -raw queue_url) \
     --max-number-of-messages 10
   ```

2. **Delete Specific Messages:**
   ```bash
   # Delete unwanted purchases by receipt handle
   aws sqs delete-message \
     --queue-url $(terraform output -raw queue_url) \
     --receipt-handle "RECEIPT_HANDLE"
   ```

3. **Update Configuration (Optional):**
   - Changes won't affect current queue
   - Will apply to next month's Scheduler run

**Option C: Wait Until Next Month**

1. **Disable Purchaser:**
   ```bash
   aws events disable-rule --name $(terraform output -raw purchaser_rule_name)
   ```

2. **Let Queued Purchases Expire:**
   - SQS message retention: 4 days (default)
   - Messages auto-delete after retention period

3. **Update Configuration:**
   ```bash
   terraform apply
   ```

4. **Re-enable Purchaser:**
   ```bash
   aws events enable-rule --name $(terraform output -raw purchaser_rule_name)
   ```

### Recovering from Failed Purchases

**Scenario:** Purchaser Lambda failed, purchases didn't execute

**Procedure:**

1. **Identify Failure Reason:**
   ```bash
   aws logs tail /aws/lambda/$(terraform output -raw purchaser_function_name) --since 1h --filter ERROR
   ```

2. **Fix Underlying Issue:**
   - **IAM Permissions**: Add missing policies
   - **Service Quota**: Request increase
   - **Invalid Parameters**: Update configuration

3. **Check Message Location:**

   **Case A: Messages Still in Main Queue (Failure Before Processing)**
   ```bash
   # Messages will auto-retry on next Purchaser run
   # Or invoke Purchaser manually after fix
   aws lambda invoke \
     --function-name $(terraform output -raw purchaser_function_name) \
     --payload '{}' \
     output.json
   ```

   **Case B: Messages in DLQ (Failed After Retries)**
   ```bash
   # Move messages back to main queue
   aws sqs receive-message --queue-url $(terraform output -raw dlq_url) | \
     jq -r '.Messages[].Body' | \
     xargs -I {} aws sqs send-message --queue-url $(terraform output -raw queue_url) --message-body '{}'

   # Delete from DLQ
   aws sqs purge-queue --queue-url $(terraform output -raw dlq_url)

   # Invoke Purchaser to process
   aws lambda invoke \
     --function-name $(terraform output -raw purchaser_function_name) \
     --payload '{}' \
     output.json
   ```

4. **Verify Success:**
   ```bash
   # Check for new Savings Plans
   aws savingsplans describe-savings-plans \
     --filters name=start,values=$(date -u +%Y-%m-%d)
   ```

### Cross-Account Operations

**Use Case:** Module deployed in central account, purchasing Savings Plans for organization

**Key Differences:**
- Scheduler/Purchaser assume role in management account
- Reporter may aggregate coverage across accounts
- IAM permissions span multiple accounts

**Verifying Cross-Account Setup:**

```bash
# Check assume role configuration
aws lambda get-function-configuration \
  --function-name $(terraform output -raw scheduler_function_name) \
  | jq -r '.Environment.Variables.ASSUME_ROLE_ARN'

# Test assume role
aws sts assume-role \
  --role-arn "arn:aws:iam::MGMT_ACCOUNT:role/sp-autopilot-cross-account" \
  --role-session-name test
```

**Troubleshooting Cross-Account Issues:**

1. **AccessDenied on Assume Role:**
   - Verify trust policy in management account role
   - Check Lambda execution role has `sts:AssumeRole` permission

2. **Coverage Not Aggregating:**
   - Verify Reporter Lambda has access to member accounts
   - Check Cost Explorer consolidated billing setup

**See Also:** [README.md Cross-Account Setup](../../README.md#cross-account-setup-for-aws-organizations)

---

## Operational Workflows

### Monthly Purchase Verification Workflow

**Objective:** Ensure monthly purchase cycle completed successfully

**Timeline:** 1st-5th of each month

**Workflow:**

```
Day 1 (Scheduler Run)
  ↓
[1] Check inbox for "Purchase Scheduled" email
  ↓
[2] Review recommended purchases and amounts
  ↓
[3] View SQS queue to confirm messages
  ↓
[4] Decide: Cancel any purchases? (Days 1-3)
  |
  ├─ Yes → Delete messages from queue
  └─ No → Wait for Purchaser run
  ↓
Day 4 (Purchaser Run)
  ↓
[5] Check inbox for "Purchase Summary" email
  ↓
[6] Verify expected purchases executed
  ↓
[7] Check AWS Console for new Savings Plans
  ↓
[8] Validate coverage increased
  ↓
✅ Cycle Complete
```

**Commands:**

```bash
# [1] Wait for email (no command)

# [2-3] View queued purchases
aws sqs receive-message \
  --queue-url $(terraform output -raw queue_url) \
  --max-number-of-messages 10 \
  | jq -r '.Messages[].Body' | jq '.'

# [4] Cancel purchase (if needed)
aws sqs delete-message \
  --queue-url $(terraform output -raw queue_url) \
  --receipt-handle "RECEIPT_HANDLE"

# [5] Wait for email (no command)

# [6-7] Verify purchases
aws savingsplans describe-savings-plans \
  --filters name=start,values=$(date -u +%Y-%m-%d)

# [8] Check coverage
aws ce get-savings-plans-coverage \
  --time-period Start=$(date -u -d '1 day ago' +%Y-%m-%d),End=$(date -u +%Y-%m-%d) \
  --granularity DAILY
```

### Investigating Coverage Trends Workflow

**Objective:** Understand why coverage is not trending as expected

**When:** Coverage flat, declining, or not reaching target

**Workflow:**

```
Coverage Issue Detected
  ↓
[1] Check Cost Explorer for current coverage %
  ↓
[2] Compare to target (coverage_target_percent)
  ↓
[3] Review recent purchases (last 30 days)
  ↓
[4] Check for expiring Savings Plans
  ↓
[5] Analyze usage trends (increasing/decreasing)
  ↓
[6] Review Scheduler logs for recommendations
  ↓
[7] Identify root cause:
  |
  ├─ Usage increasing → Increase max_purchase_percent
  ├─ Plans expiring → Wait (automation accounts for this)
  ├─ At coverage cap → Increase max_coverage_cap
  ├─ No purchases → Check dry_run mode, usage data
  └─ Other → Investigate further
  ↓
[8] Adjust configuration if needed
  ↓
[9] Monitor next month's cycle
  ↓
✅ Issue Resolved
```

**Commands:**

```bash
# [1] Check current coverage
aws ce get-savings-plans-coverage \
  --time-period Start=$(date -u -d '7 days ago' +%Y-%m-%d),End=$(date -u +%Y-%m-%d) \
  --granularity DAILY

# [3] Recent purchases
aws savingsplans describe-savings-plans \
  --filters name=start,values=$(date -u -d '30 days ago' +%Y-%m-%d)

# [4] Expiring plans
aws savingsplans describe-savings-plans \
  --filters name=end,values=$(date -u -d '60 days' +%Y-%m-%d)

# [5] Usage trends (via Cost Explorer console)

# [6] Scheduler logs
aws logs tail /aws/lambda/$(terraform output -raw scheduler_function_name) --since 7d | grep "recommendation\|coverage"
```

### Emergency Pause Workflow

**Objective:** Immediately stop all automation

**When:** Budget overrun, organizational change, critical issue

**Workflow:**

```
Emergency Detected
  ↓
[1] Disable all EventBridge rules
  ↓
[2] Purge SQS queue (cancel pending purchases)
  ↓
[3] Verify queue empty
  ↓
[4] Send notification to team
  ↓
[5] Document reason for pause
  ↓
Investigation & Fix
  ↓
[6] Test with dry_run mode enabled
  ↓
[7] Re-enable automation when ready
  ↓
[8] Monitor first post-pause run
  ↓
✅ Automation Resumed
```

**Commands:**

```bash
# [1] Disable automation
aws events disable-rule --name $(terraform output -raw scheduler_rule_name)
aws events disable-rule --name $(terraform output -raw purchaser_rule_name)
aws events disable-rule --name $(terraform output -raw reporter_rule_name)

# [2] Purge queue
aws sqs purge-queue --queue-url $(terraform output -raw queue_url)

# [3] Verify empty
aws sqs get-queue-attributes \
  --queue-url $(terraform output -raw queue_url) \
  --attribute-names ApproximateNumberOfMessages

# [4] Send notification
aws sns publish \
  --topic-arn $(terraform output -raw sns_topic_arn) \
  --subject "[SP Autopilot] EMERGENCY PAUSE" \
  --message "Automation paused. See incident log for details."

# [7] Re-enable
aws events enable-rule --name $(terraform output -raw scheduler_rule_name)
aws events enable-rule --name $(terraform output -raw purchaser_rule_name)
aws events enable-rule --name $(terraform output -raw reporter_rule_name)
```

### Strategy Adjustment Workflow

**Objective:** Change purchase strategy mid-month

**When:** Need to adjust targets, limits, or term mix before next Scheduler run

**Workflow:**

```
Need Strategy Change
  ↓
[1] Decide: Affect current month or next month?
  |
  ├─ Next month only → Go to [6]
  └─ Current month → Continue
  ↓
[2] Check if Scheduler already ran this month
  |
  ├─ Not yet → Go to [6]
  └─ Already ran → Continue
  ↓
[3] Check if Purchaser already ran
  |
  ├─ Already ran → Go to [6] (too late for current month)
  └─ Not yet → Continue
  ↓
[4] Purge queue (cancel queued purchases)
  ↓
[5] Update Terraform configuration
  ↓
[6] Apply configuration changes
  ↓
[7] If current month affected: Manually invoke Scheduler
  ↓
[8] Review new queued purchases
  ↓
[9] Wait for Purchaser run or invoke manually
  ↓
✅ Strategy Updated
```

**Commands:**

```bash
# [4] Purge queue
aws sqs purge-queue --queue-url $(terraform output -raw queue_url)

# [5-6] Update configuration
terraform apply

# [7] Re-run Scheduler
aws lambda invoke \
  --function-name $(terraform output -raw scheduler_function_name) \
  --payload '{}' \
  output.json

# [8] Review queue
aws sqs receive-message \
  --queue-url $(terraform output -raw queue_url) \
  --max-number-of-messages 10

# [9] Invoke Purchaser (optional)
aws lambda invoke \
  --function-name $(terraform output -raw purchaser_function_name) \
  --payload '{}' \
  output.json
```

---

**Related Documentation:**
- [README.md](../../README.md) - Module setup and configuration
- [ERROR_PATTERNS.md](../../ERROR_PATTERNS.md) - Detailed error reference
- [TESTING.md](../../TESTING.md) - Testing procedures

**Support:**
- GitHub Issues: [terraform-aws-sp-autopilot/issues](https://github.com/etiennechabert/terraform-aws-sp-autopilot/issues)
- AWS Cost Explorer: [Console Link](https://console.aws.amazon.com/cost-management/home#/savings-plans)

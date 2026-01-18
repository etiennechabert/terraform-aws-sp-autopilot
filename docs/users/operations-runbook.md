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
- [Verification Procedures](#verification-procedures)
  - [Verifying Last Month's Purchase](#verifying-last-months-purchase)
  - [Checking Current Coverage](#checking-current-coverage)
  - [Accessing Coverage Reports in S3](#accessing-coverage-reports-in-s3)
  - [Interpreting CloudWatch Logs](#interpreting-cloudwatch-logs)
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
  - [Troubleshooting Decision Tree](#troubleshooting-decision-tree)
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
  - [Recovering from Failed Purchases Workflow](#recovering-from-failed-purchases-workflow)

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

## Verification Procedures

Comprehensive procedures for verifying the automation is working correctly and purchases are executing as expected.

### Verifying Last Month's Purchase

**Objective:** Confirm Savings Plans purchased last month executed successfully and are active

**When:** 5-7 days after Purchaser runs (typically 5th-7th of month)

**Procedure:**

1. **List Recent Savings Plans Purchases:**
   ```bash
   # List all Savings Plans purchased in last 30 days
   aws savingsplans describe-savings-plans \
     --filters name=start,values=$(date -u -d '30 days ago' +%Y-%m-%d) \
     --max-results 50
   ```

2. **Filter to Last Month's Purchases:**
   ```bash
   # More precise: purchases from specific date range
   aws savingsplans describe-savings-plans \
     --filters name=start,values=$(date -u -d '7 days ago' +%Y-%m-%d) \
     --max-results 20 \
     | jq -r '.savingsPlans[] | "\(.savingsPlanType) | \(.commitment) USD/hour | \(.term) | \(.paymentOption) | Started: \(.start)"'
   ```

3. **Verify Purchase Details:**
   - **savingsPlanId**: Unique identifier for the plan
   - **savingsPlanType**: COMPUTE_SP, DATABASE_SP, or SAGEMAKER_SP
   - **commitment**: Hourly commitment in USD (e.g., "5.67")
   - **term**: ONE_YEAR or THREE_YEARS
   - **paymentOption**: ALL_UPFRONT, PARTIAL_UPFRONT, or NO_UPFRONT
   - **start**: Start date (should match purchase date)
   - **state**: ACTIVE (healthy), RETIRED (expired)

4. **Cross-Reference with Email Notification:**
   - Find "Purchase Summary" email from Purchaser Lambda
   - Compare hourly commitments between email and AWS Console
   - Verify expected number of plans purchased

5. **Expected Output Example:**
   ```
   COMPUTE_SP | 5.67 USD/hour | THREE_YEARS | NO_UPFRONT | Started: 2024-01-04T08:15:23Z
   COMPUTE_SP | 2.34 USD/hour | ONE_YEAR | ALL_UPFRONT | Started: 2024-01-04T08:15:45Z
   ```

**✅ Success Criteria:**
- All expected Savings Plans appear in list
- State = ACTIVE for all plans
- Hourly commitments match email notification
- Start date within expected window

**❌ Failure Indicators:**
- Missing Savings Plans → Check Purchaser CloudWatch Logs for errors
- State ≠ ACTIVE → Contact AWS Support (plan issue)
- Commitment mismatch → Review purchase messages in SQS (may have been modified)

**Troubleshooting:**

```bash
# If no purchases found, check Purchaser logs
aws logs tail /aws/lambda/$(terraform output -raw purchaser_function_name) \
  --since 7d --filter ERROR

# Check DLQ for failed purchases
aws sqs receive-message \
  --queue-url $(terraform output -raw dlq_url) \
  --max-number-of-messages 10

# Verify email was sent (check SNS topic)
aws sns list-subscriptions-by-topic \
  --topic-arn $(terraform output -raw sns_topic_arn)
```

### Checking Current Coverage

**Objective:** Validate current Savings Plans coverage percentage and compare to target

**When:**
- Weekly (routine monitoring)
- After purchases execute (verify impact)
- When investigating coverage trends

**Procedure:**

1. **Get Current Coverage (Cost Explorer API):**
   ```bash
   # Coverage for last 7 days (most accurate)
   aws ce get-savings-plans-coverage \
     --time-period Start=$(date -u -d '7 days ago' +%Y-%m-%d),End=$(date -u +%Y-%m-%d) \
     --granularity DAILY \
     --group-by Type=DIMENSION,Key=INSTANCE_TYPE_FAMILY
   ```

2. **Calculate Average Coverage:**
   ```bash
   # Get coverage summary for yesterday (most recent complete day)
   aws ce get-savings-plans-coverage \
     --time-period Start=$(date -u -d '1 day ago' +%Y-%m-%d),End=$(date -u +%Y-%m-%d) \
     --granularity DAILY \
     | jq -r '.Total.CoveragePercentage'
   ```

3. **Interpret Coverage Output:**
   ```json
   {
     "ResultsByTime": [
       {
         "TimePeriod": {
           "Start": "2024-01-10",
           "End": "2024-01-11"
         },
         "Total": {
           "CoveragePercentage": "87.5",
           "OnDemandCost": "1234.56",
           "CoveredCost": "5678.90",
           "TotalCost": "6913.46"
         }
       }
     ]
   }
   ```

   **Key Metrics:**
   - **CoveragePercentage**: % of eligible spend covered by Savings Plans
   - **OnDemandCost**: Spend not covered by Savings Plans (uncovered)
   - **CoveredCost**: Spend covered by Savings Plans
   - **TotalCost**: OnDemandCost + CoveredCost

4. **Compare to Target:**
   ```bash
   # Get target from Terraform configuration
   terraform output -json module_configuration | jq -r '.coverage_target'

   # Manual comparison:
   # Current Coverage: 87.5%
   # Target Coverage: 90%
   # Gap: 2.5%
   ```

5. **Check Coverage by Service (Detailed View):**
   ```bash
   # Break down coverage by service (EC2, Lambda, Fargate, etc.)
   aws ce get-savings-plans-coverage \
     --time-period Start=$(date -u -d '1 day ago' +%Y-%m-%d),End=$(date -u +%Y-%m-%d) \
     --granularity DAILY \
     --group-by Type=DIMENSION,Key=SERVICE \
     | jq -r '.ResultsByTime[].Groups[] | "\(.Keys[0]): \(.Metrics.CoveragePercentage)%"'
   ```

**✅ Healthy Coverage Indicators:**
- Coverage trending toward target (increasing monthly)
- Coverage at or above target
- Coverage stable (±2% variation) if at target
- OnDemandCost decreasing over time

**❌ Warning Signs:**
- Coverage declining month-over-month
- Coverage stuck >5% below target after multiple purchases
- Large day-to-day coverage variation (>10%)
- OnDemandCost increasing despite purchases

**Coverage Interpretation Guide:**

| Current Coverage | Target | Status | Action |
|------------------|--------|--------|--------|
| 92% | 90% | ✅ At target | Monitor monthly, may reduce purchases |
| 87% | 90% | ⚠️ Below target | Normal - automation purchasing monthly |
| 85% | 90% | ⚠️ Below target | Verify purchases executing, check logs |
| 78% | 90% | ❌ Far below | Investigate - may need higher max_purchase_percent |
| 70% (declining) | 90% | ❌ Critical | Check for expiring plans, usage changes |

**Detailed Investigation:**

```bash
# 1. Check for expiring Savings Plans
aws savingsplans describe-savings-plans \
  --filters name=end,values=$(date -u -d '60 days' +%Y-%m-%d) \
  | jq -r '.savingsPlans[] | "\(.savingsPlanType): \(.commitment) USD/hour expires \(.end)"'

# 2. Review recent purchases (verify automation working)
aws savingsplans describe-savings-plans \
  --filters name=start,values=$(date -u -d '30 days ago' +%Y-%m-%d) \
  | jq -r '.savingsPlans | length'

# 3. Check Scheduler recommendations (last run)
aws logs tail /aws/lambda/$(terraform output -raw scheduler_function_name) \
  --since 7d | grep "recommendation\|purchase"

# 4. Check configuration
terraform output -json module_configuration | jq '{
  coverage_target: .coverage_target,
  max_coverage_cap: .max_coverage_cap,
  dry_run: .dry_run
}'
```

### Accessing Coverage Reports in S3

**Objective:** Access detailed coverage reports generated by Reporter Lambda

**When:**
- Monthly (after Reporter runs, typically 15th of month)
- When Cost Explorer API isn't providing enough detail
- For historical coverage analysis

**Procedure:**

1. **List Available Reports:**
   ```bash
   # List all coverage reports
   aws s3 ls s3://$(terraform output -raw reports_bucket_name)/coverage-reports/

   # Expected output:
   # 2024-01-15T12:00:00Z-coverage.json
   # 2024-02-15T12:00:00Z-coverage.json
   # latest.json -> symlink to most recent
   ```

2. **Download Latest Report:**
   ```bash
   # Download most recent report
   aws s3 cp \
     s3://$(terraform output -raw reports_bucket_name)/coverage-reports/latest.json \
     ./coverage-report.json

   # Download specific date
   aws s3 cp \
     s3://$(terraform output -raw reports_bucket_name)/coverage-reports/2024-01-15T12:00:00Z-coverage.json \
     ./coverage-report-jan.json
   ```

3. **View Report in Terminal:**
   ```bash
   # Pretty-print report
   cat coverage-report.json | jq '.'

   # Extract key metrics only
   cat coverage-report.json | jq '{
     timestamp: .timestamp,
     compute_coverage: .compute_sp.coverage_percent,
     database_coverage: .database_sp.coverage_percent,
     sagemaker_coverage: .sagemaker_sp.coverage_percent
   }'
   ```

4. **Report Structure and Interpretation:**
   ```json
   {
     "timestamp": "2024-01-15T12:00:00Z",
     "report_date": "2024-01-15",
     "compute_sp": {
       "enabled": true,
       "coverage_percent": 87.5,
       "on_demand_spend": "1234.56",
       "covered_spend": "5678.90",
       "total_spend": "6913.46",
       "utilization_percent": 95.2,
       "active_plans": [
         {
           "savingsPlanId": "sp-12345678",
           "commitment": "5.67",
           "term": "THREE_YEARS",
           "start": "2024-01-04",
           "end": "2027-01-04"
         }
       ],
       "services": {
         "EC2": {"coverage": 92.3, "spend": 4500.00},
         "Lambda": {"coverage": 78.5, "spend": 890.90},
         "Fargate": {"coverage": 85.0, "spend": 288.00}
       }
     },
     "database_sp": {
       "enabled": false,
       "coverage_percent": null
     },
     "sagemaker_sp": {
       "enabled": false,
       "coverage_percent": null
     }
   }
   ```

   **Key Fields Explained:**
   - **timestamp**: When report was generated
   - **coverage_percent**: Overall coverage % for this SP type
   - **on_demand_spend**: Uncovered spend (opportunity for more SPs)
   - **covered_spend**: Spend covered by Savings Plans
   - **utilization_percent**: How much of purchased commitment is being used
   - **active_plans**: List of all active Savings Plans
   - **services**: Coverage breakdown by AWS service

5. **Analyze Report Metrics:**

   **Coverage Analysis:**
   ```bash
   # Compare coverage across SP types
   cat coverage-report.json | jq '{
     compute: .compute_sp.coverage_percent,
     database: .database_sp.coverage_percent,
     sagemaker: .sagemaker_sp.coverage_percent
   }'
   ```

   **Utilization Analysis:**
   ```bash
   # Check if SPs are fully utilized
   cat coverage-report.json | jq '{
     compute_utilization: .compute_sp.utilization_percent,
     database_utilization: .database_sp.utilization_percent,
     sagemaker_utilization: .sagemaker_sp.utilization_percent
   }'
   ```

   **Service-Level Coverage:**
   ```bash
   # Which services have lowest coverage?
   cat coverage-report.json | jq -r '
     .compute_sp.services |
     to_entries |
     sort_by(.value.coverage) |
     .[] |
     "\(.key): \(.value.coverage)% coverage, $\(.value.spend) spend"
   '
   ```

6. **Compare Month-over-Month:**
   ```bash
   # Download last 2 months
   aws s3 cp s3://$(terraform output -raw reports_bucket_name)/coverage-reports/2024-01-15T12:00:00Z-coverage.json ./jan.json
   aws s3 cp s3://$(terraform output -raw reports_bucket_name)/coverage-reports/2024-02-15T12:00:00Z-coverage.json ./feb.json

   # Compare coverage
   echo "January: $(cat jan.json | jq -r '.compute_sp.coverage_percent')%"
   echo "February: $(cat feb.json | jq -r '.compute_sp.coverage_percent')%"
   ```

**Interpretation Guidelines:**

| Metric | Healthy Range | Warning | Action |
|--------|---------------|---------|--------|
| **Coverage %** | At or near target | >5% below target | Verify purchases executing |
| **Utilization %** | 90-100% | <80% | Over-committed, reduce purchases |
| **Utilization %** | 90-100% | >100% | Under-committed, increase purchases |
| **On-Demand Spend** | Decreasing | Increasing | Usage growing, coverage not keeping up |

**✅ Healthy Report Indicators:**
- Coverage trending toward target
- Utilization 90-100% (not wasting purchased commitment)
- On-Demand spend stable or decreasing
- Service coverage balanced (no service <70%)

**❌ Warning Signs:**
- Utilization <80% (over-committed - purchased too much)
- Utilization >100% (under-committed - need more SPs)
- Coverage declining month-over-month
- Large service coverage variance (one service 95%, another 60%)

### Interpreting CloudWatch Logs

**Objective:** Understand Lambda execution logs to verify successful runs and diagnose issues

**When:**
- After scheduled Lambda runs (verify success)
- When investigating errors or unexpected behavior
- When email notifications are missing
- During troubleshooting

**Procedure:**

1. **Access Lambda Logs:**
   ```bash
   # Tail Scheduler logs (real-time)
   aws logs tail /aws/lambda/$(terraform output -raw scheduler_function_name) --follow

   # Tail Purchaser logs
   aws logs tail /aws/lambda/$(terraform output -raw purchaser_function_name) --follow

   # Tail Reporter logs
   aws logs tail /aws/lambda/$(terraform output -raw reporter_function_name) --follow
   ```

2. **View Recent Logs (Last 24 Hours):**
   ```bash
   # Last 100 lines
   aws logs tail /aws/lambda/$(terraform output -raw scheduler_function_name) --since 24h

   # Filter for specific time range
   aws logs tail /aws/lambda/$(terraform output -raw scheduler_function_name) \
     --since 2024-01-01T08:00:00 \
     --until 2024-01-01T09:00:00
   ```

3. **Filter Logs by Level:**
   ```bash
   # Show only errors
   aws logs tail /aws/lambda/$(terraform output -raw scheduler_function_name) \
     --since 7d --filter ERROR

   # Show warnings and errors
   aws logs tail /aws/lambda/$(terraform output -raw scheduler_function_name) \
     --since 7d --filter '"WARN\|ERROR"'

   # Show info, warnings, and errors (exclude debug)
   aws logs tail /aws/lambda/$(terraform output -raw scheduler_function_name) \
     --since 7d --filter '"INFO\|WARN\|ERROR"'
   ```

4. **Understanding Log Patterns:**

   **✅ Successful Scheduler Run Example:**
   ```
   [INFO] 2024-01-01T08:00:05Z START RequestId: abc-123
   [INFO] 2024-01-01T08:00:06Z Fetching current Savings Plans coverage
   [INFO] 2024-01-01T08:00:07Z Current Compute SP coverage: 87.5%
   [INFO] 2024-01-01T08:00:08Z Coverage target: 90%, Gap: 2.5%
   [INFO] 2024-01-01T08:00:09Z Fetching AWS purchase recommendations
   [INFO] 2024-01-01T08:00:12Z Received 3 recommendations from AWS
   [INFO] 2024-01-01T08:00:13Z Applying max_purchase_percent limit: 10%
   [INFO] 2024-01-01T08:00:14Z Calculated purchase: $2.50/hour
   [INFO] 2024-01-01T08:00:15Z Splitting by term mix: 50% 1-year, 50% 3-year
   [INFO] 2024-01-01T08:00:16Z Queued 2 purchase intents to SQS
   [INFO] 2024-01-01T08:00:17Z Sending notification email
   [INFO] 2024-01-01T08:00:18Z END RequestId: abc-123 Duration: 13000ms
   ```

   **Key Success Indicators:**
   - START and END messages present (complete execution)
   - Coverage fetched successfully
   - Recommendations received
   - Messages queued to SQS
   - Email sent
   - No ERROR or WARN messages

   **✅ Successful Purchaser Run Example:**
   ```
   [INFO] 2024-01-04T08:00:05Z START RequestId: def-456
   [INFO] 2024-01-04T08:00:06Z Receiving messages from SQS
   [INFO] 2024-01-04T08:00:07Z Received 2 purchase intents
   [INFO] 2024-01-04T08:00:08Z Processing purchase 1/2: COMPUTE_SP $5.67/hour
   [INFO] 2024-01-04T08:00:09Z Current coverage: 87.5%, max_coverage_cap: 95%
   [INFO] 2024-01-04T08:00:10Z Projected coverage after purchase: 90.2%
   [INFO] 2024-01-04T08:00:11Z Coverage check passed
   [INFO] 2024-01-04T08:00:12Z Executing CreateSavingsPlan API call
   [INFO] 2024-01-04T08:00:15Z Purchase successful: sp-12345678
   [INFO] 2024-01-04T08:00:16Z Deleting message from queue
   [INFO] 2024-01-04T08:00:17Z Processing purchase 2/2: COMPUTE_SP $2.34/hour
   [INFO] 2024-01-04T08:00:20Z Purchase successful: sp-87654321
   [INFO] 2024-01-04T08:00:21Z Sending purchase summary email
   [INFO] 2024-01-04T08:00:22Z END RequestId: def-456 Duration: 17000ms
   ```

   **Key Success Indicators:**
   - Messages received from SQS
   - Coverage cap validation passed
   - CreateSavingsPlan succeeded for all purchases
   - Messages deleted from queue
   - Summary email sent

   **✅ Successful Reporter Run Example:**
   ```
   [INFO] 2024-01-15T12:00:05Z START RequestId: ghi-789
   [INFO] 2024-01-15T12:00:06Z Fetching Savings Plans coverage
   [INFO] 2024-01-15T12:00:08Z Fetching active Savings Plans
   [INFO] 2024-01-15T12:00:10Z Found 5 active Compute SPs
   [INFO] 2024-01-15T12:00:11Z Generating coverage report
   [INFO] 2024-01-15T12:00:12Z Uploading report to S3: coverage-reports/2024-01-15T12:00:00Z-coverage.json
   [INFO] 2024-01-15T12:00:14Z Updating latest.json symlink
   [INFO] 2024-01-15T12:00:15Z Sending coverage report email
   [INFO] 2024-01-15T12:00:16Z END RequestId: ghi-789 Duration: 11000ms
   ```

5. **Common Error Patterns and Interpretation:**

   **❌ IAM Permission Error:**
   ```
   [ERROR] 2024-01-01T08:00:10Z AccessDeniedException: User is not authorized to perform: savingsplans:DescribeSavingsPlans
   [ERROR] 2024-01-01T08:00:11Z Lambda execution failed
   ```
   **Action:** Add missing IAM permission to Lambda execution role

   **❌ Service Quota Error:**
   ```
   [ERROR] 2024-01-04T08:00:12Z ServiceQuotaExceededException: You have reached the maximum number of active Savings Plans (50)
   [ERROR] 2024-01-04T08:00:13Z Purchase failed, moving to DLQ
   ```
   **Action:** Request quota increase or wait for plans to expire

   **❌ Coverage Cap Exceeded:**
   ```
   [WARN] 2024-01-04T08:00:10Z Projected coverage (96.2%) exceeds max_coverage_cap (95%)
   [INFO] 2024-01-04T08:00:11Z Skipping purchase to avoid over-commitment
   [INFO] 2024-01-04T08:00:12Z Deleting message from queue
   ```
   **Action:** Expected behavior - purchase skipped safely

   **❌ No Recommendations:**
   ```
   [WARN] 2024-01-01T08:00:12Z AWS returned 0 purchase recommendations
   [INFO] 2024-01-01T08:00:13Z Skipping purchase cycle
   [INFO] 2024-01-01T08:00:14Z Sending dry-run notification email
   ```
   **Action:** Check if usage data sufficient (min_data_days), may be at target coverage

   **❌ Dry Run Mode:**
   ```
   [INFO] 2024-01-01T08:00:15Z DRY_RUN mode enabled
   [INFO] 2024-01-01T08:00:16Z Skipping SQS queue operation
   [INFO] 2024-01-01T08:00:17Z Would have queued: 2 purchase intents
   [INFO] 2024-01-01T08:00:18Z Sending dry-run email only
   ```
   **Action:** Expected in dry-run mode, disable to go live

6. **Log Investigation Workflow:**

   ```bash
   # Step 1: Check if Lambda ran recently
   aws logs tail /aws/lambda/$(terraform output -raw scheduler_function_name) \
     --since 7d --filter START | tail -1

   # Step 2: Check for errors in last run
   aws logs tail /aws/lambda/$(terraform output -raw scheduler_function_name) \
     --since 7d --filter ERROR

   # Step 3: If errors found, get full context
   aws logs filter-log-events \
     --log-group-name /aws/lambda/$(terraform output -raw scheduler_function_name) \
     --start-time $(date -u -d '1 hour ago' +%s)000 \
     --filter-pattern "ERROR"

   # Step 4: Get complete execution trace
   aws logs tail /aws/lambda/$(terraform output -raw scheduler_function_name) \
     --since 2h | grep "RequestId: abc-123"  # Use actual RequestId
   ```

7. **Log Retention and Management:**
   ```bash
   # Check log retention setting
   aws logs describe-log-groups \
     --log-group-name-prefix /aws/lambda/sp-autopilot \
     | jq -r '.logGroups[] | "\(.logGroupName): \(.retentionInDays) days"'

   # Search across multiple Lambda functions
   for func in scheduler purchaser reporter; do
     echo "=== $func ==="
     aws logs tail /aws/lambda/$(terraform output -raw ${func}_function_name) \
       --since 24h --filter ERROR
   done
   ```

**Log Interpretation Quick Reference:**

| Log Pattern | Meaning | Action |
|-------------|---------|--------|
| `START ... END` | Successful execution | ✅ No action needed |
| `ERROR AccessDenied` | IAM permission missing | Add required permission |
| `ERROR ServiceQuota` | AWS limit reached | Request quota increase |
| `ERROR ValidationException` | Invalid parameters | Check configuration |
| `WARN Coverage cap exceeded` | Safety limit triggered | Expected - preventing over-commitment |
| `INFO DRY_RUN mode` | Test mode active | Disable dry_run to go live |
| `WARN 0 recommendations` | No purchases needed | Expected at target coverage |
| No logs in 7 days | Lambda not running | Check EventBridge schedule enabled |

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
- `client_token`: Idempotency token for purchase (format: `scheduler-{sp_type}-{term}-{timestamp}`)
- `sp_type`: "compute" | "database" | "sagemaker"
- `term`: "ONE_YEAR" | "THREE_YEAR"
- `hourly_commitment`: Hourly commitment in USD (e.g., 1.234)
- `payment_option`: "ALL_UPFRONT" | "PARTIAL_UPFRONT" | "NO_UPFRONT"
- `recommendation_id`: AWS recommendation ID (or "unknown")
- `queued_at`: ISO 8601 timestamp when queued
- `tags`: Resource tags to apply to the Savings Plan

**Example Output:**
```json
{
  "client_token": "scheduler-compute-THREE_YEAR-2024-01-01T08:00:00+00:00",
  "sp_type": "compute",
  "term": "THREE_YEAR",
  "hourly_commitment": 5.67,
  "payment_option": "NO_UPFRONT",
  "recommendation_id": "12345678-1234-1234-1234-123456789012",
  "queued_at": "2024-01-01T08:00:00+00:00",
  "tags": {
    "ManagedBy": "sp-autopilot",
    "Environment": "production"
  }
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
      "Body": "{\"client_token\":\"scheduler-compute-THREE_YEAR-2024-01-01T08:00:00+00:00\",\"sp_type\":\"compute\",\"term\":\"THREE_YEAR\",\"hourly_commitment\":5.67,\"payment_option\":\"NO_UPFRONT\",\"recommendation_id\":\"12345678-1234-1234-1234-123456789012\",\"queued_at\":\"2024-01-01T08:00:00+00:00\",\"tags\":{\"ManagedBy\":\"sp-autopilot\"}}",
      "Attributes": {
        "SentTimestamp": "1704096000000",
        "ApproximateReceiveCount": "0",
        "ApproximateFirstReceiveTimestamp": "0"
      }
    }
  ]
}
```

**SQS Wrapper Fields:**
- **MessageId**: Unique SQS message identifier
- **ReceiptHandle**: Required for deleting message (canceling purchase)
- **Body**: JSON string containing purchase intent details (see below)
- **SentTimestamp**: Unix epoch when Scheduler queued the purchase
- **ApproximateReceiveCount**: How many times message was received (0 = not processed)

**Body (Purchase Intent) Fields:**
- **client_token**: Idempotency token preventing duplicate purchases
- **sp_type**: Savings Plan type ("compute", "database", or "sagemaker")
- **term**: Commitment term ("ONE_YEAR" or "THREE_YEAR")
- **hourly_commitment**: Dollar amount per hour to commit
- **payment_option**: Payment structure for the commitment
- **recommendation_id**: AWS-generated recommendation identifier
- **queued_at**: ISO 8601 timestamp when intent was queued
- **tags**: Key-value pairs to tag the Savings Plan resource

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

The module creates CloudWatch alarms to monitor Lambda function errors and DLQ depth. All alarms have:
- **Evaluation Period**: 1 minute (period = 60 seconds)
- **Evaluation Periods**: 1
- **Threshold**: ≥1 error or message
- **Actions**: SNS notification to configured emails on ALARM and OK states

**Alarm Definitions:**

| Alarm Name | Metric | Description |
|------------|--------|-------------|
| `{name_prefix}-scheduler-errors` | Lambda Errors (AWS/Lambda) | Triggers when Scheduler Lambda function errors exceed threshold, indicating failures in usage analysis |
| `{name_prefix}-purchaser-errors` | Lambda Errors (AWS/Lambda) | Triggers when Purchaser Lambda function errors exceed threshold, indicating failures in Savings Plans purchases |
| `{name_prefix}-reporter-errors` | Lambda Errors (AWS/Lambda) | Triggers when Reporter Lambda function errors exceed threshold, indicating failures in report generation |
| `{name_prefix}-purchase-intents-dlq-depth` | SQS Messages Visible (AWS/SQS) | Triggers when messages land in the purchase intents DLQ, indicating repeated processing failures |

**What Each Alarm Monitors:**

- **Scheduler Errors**: Indicates issues with analyzing coverage and queuing purchase recommendations
  - **Impact**: New purchases won't be scheduled this month
  - **Common Causes**: IAM permissions, Cost Explorer API issues, insufficient usage data

- **Purchaser Errors**: Indicates issues with executing Savings Plans purchases
  - **Impact**: Queued purchases won't complete, coverage won't increase
  - **Common Causes**: IAM permissions, service quotas, invalid parameters, payment method issues

- **Reporter Errors**: Indicates issues with generating coverage reports
  - **Impact**: No coverage reports in S3, missing email notifications
  - **Common Causes**: IAM permissions, S3 bucket access, Cost Explorer API issues

- **DLQ Depth**: Indicates purchase messages failed after maximum retries
  - **Impact**: Specific purchases abandoned, coverage gap persists
  - **Common Causes**: Persistent IAM issues, invalid message format, repeated API failures

**Viewing Alarms:**

```bash
# List all alarms
aws cloudwatch describe-alarms --alarm-name-prefix sp-autopilot

# Get alarm state
aws cloudwatch describe-alarms \
  --alarm-names sp-autopilot-scheduler-errors \
  | jq -r '.MetricAlarms[].StateValue'

# View all alarm states at once
aws cloudwatch describe-alarms --alarm-name-prefix sp-autopilot \
  | jq -r '.MetricAlarms[] | "\(.AlarmName): \(.StateValue)"'

# Check alarm history (recent state changes)
aws cloudwatch describe-alarm-history \
  --alarm-name sp-autopilot-scheduler-errors \
  --max-records 10 \
  --history-item-type StateUpdate
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

The SNS topic sends two types of notifications: **CloudWatch Alarms** (monitoring issues) and **Operational Notifications** (Lambda function results).

---

#### CloudWatch Alarm Notifications

**Alarm ALARM State Notification:**

```
Subject: ALARM: "sp-autopilot-scheduler-errors" in US East (N. Virginia)

You are receiving this email because your Amazon CloudWatch Alarm "sp-autopilot-scheduler-errors" in the US East (N. Virginia) region has entered the ALARM state.

Alarm Details:
- Name: sp-autopilot-scheduler-errors
- Description: Triggers when Scheduler Lambda function errors exceed threshold, indicating failures in usage analysis
- State Change: OK -> ALARM
- Reason for State Change: Threshold Crossed: 1 datapoint [1.0 (18/01/26 08:05:00)] was greater than or equal to the threshold (1.0).

View this alarm in the AWS Console:
https://console.aws.amazon.com/cloudwatch/...
```

**Action:**
- **Immediate**: Investigate Lambda function logs for error details
- **Within 24h**: Resolve underlying issue (IAM permissions, API errors, etc.)
- **Follow-up**: Monitor for OK state recovery notification

**Alarm OK State Notification:**

```
Subject: OK: "sp-autopilot-scheduler-errors" in US East (N. Virginia)

You are receiving this email because your Amazon CloudWatch Alarm "sp-autopilot-scheduler-errors" in the US East (N. Virginia) region has entered the OK state.

Alarm Details:
- Name: sp-autopilot-scheduler-errors
- Description: Triggers when Scheduler Lambda function errors exceed threshold, indicating failures in usage analysis
- State Change: ALARM -> OK
- Reason for State Change: Threshold Crossed: 1 datapoint [0.0 (18/01/26 09:05:00)] was less than the threshold (1.0).
```

**Action:**
- ✅ Issue resolved, no action needed
- Review what fixed the issue for future reference

**Alarm Interpretation Guide:**

| Alarm Name | When Triggered | First Response |
|------------|----------------|----------------|
| `scheduler-errors` | Scheduler Lambda failed | Check CloudWatch Logs, verify IAM permissions, ensure Cost Explorer API accessible |
| `purchaser-errors` | Purchaser Lambda failed | Check CloudWatch Logs, verify IAM permissions, check service quotas, review SQS messages |
| `reporter-errors` | Reporter Lambda failed | Check CloudWatch Logs, verify S3 bucket access, ensure Cost Explorer API accessible |
| `purchase-intents-dlq-depth` | Messages in DLQ | Check DLQ messages, review Purchaser logs, identify why purchases failed repeatedly |

---

#### Operational Notifications

These notifications are sent by Lambda functions after successful execution to inform you of actions taken.

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

**When:** Sent by Scheduler Lambda after analyzing coverage and queuing purchases

**Action:**
- Verify amounts reasonable given coverage gap
- Cancel unwanted purchases via SQS before Purchaser runs
- Review coverage target alignment

**Purchase Summary Notification:**

```
Subject: [SP Autopilot] Purchase Summary - 2024-01-04

Successfully purchased 2 Savings Plans:
- Compute SP (3-year): $5.67/hour
- Compute SP (1-year): $2.34/hour

Total commitment: $8.01/hour ($70,168/year)
```

**When:** Sent by Purchaser Lambda after executing queued purchases

**Action:**
- Verify expected purchases executed
- Confirm coverage increased in Cost Explorer
- Cross-reference with AWS Savings Plans console

**Coverage Report Notification:**

```
Subject: [SP Autopilot] Coverage Report - 2024-01-15

Current Coverage:
- Compute SP: 87.5% (target: 90%)
- Database SP: N/A (disabled)
- SageMaker SP: N/A (disabled)

Utilization: 95.2%
On-Demand Spend: $1,234.56/day

Full report available in S3: s3://sp-autopilot-reports/coverage-reports/latest.json
```

**When:** Sent by Reporter Lambda after generating monthly coverage report

**Action:**
- Review coverage progress toward target
- Check utilization percentage (should be 90-100%)
- Investigate if coverage not trending toward target
- Download full S3 report for detailed analysis

**Notification Frequency Guide:**

| Notification Type | Frequency | Expected Timing |
|------------------|-----------|-----------------|
| Purchase Scheduled | Monthly | 1st of month (default) after Scheduler runs |
| Purchase Summary | Monthly | 4th of month (default) after Purchaser runs |
| Coverage Report | Monthly | 15th of month (default) after Reporter runs |
| CloudWatch Alarms | As needed | Only when alarms trigger or recover |

---

## Troubleshooting Common Scenarios

### Troubleshooting Decision Tree

Use this decision tree to quickly diagnose and resolve common operational issues.

#### Issue: Received CloudWatch Alarm

```
START: CloudWatch Alarm Notification Received
│
├─ Alarm: "scheduler-errors" ?
│  ├─ YES → Check Scheduler Lambda Logs
│  │       ├─ Error: AccessDeniedException ?
│  │       │  └─ YES → Add missing IAM permissions to Scheduler role
│  │       │          → See: ERROR_PATTERNS.md for required permissions
│  │       │
│  │       ├─ Error: Cost Explorer API failure ?
│  │       │  └─ YES → Verify Cost Explorer enabled in account
│  │       │          → Check AWS service health dashboard
│  │       │
│  │       └─ Error: Insufficient usage data ?
│  │          └─ YES → Wait for more usage history
│  │                  → Check purchase_strategy.min_data_days setting
│  │
├─ Alarm: "purchaser-errors" ?
│  ├─ YES → Check Purchaser Lambda Logs
│  │       ├─ Error: AccessDeniedException ?
│  │       │  └─ YES → Add savingsplans:CreateSavingsPlan permission
│  │       │
│  │       ├─ Error: ServiceQuotaExceededException ?
│  │       │  └─ YES → Request Savings Plans quota increase via AWS Support
│  │       │          → OR wait for expired plans to free up quota
│  │       │
│  │       ├─ Error: ValidationException ?
│  │       │  └─ YES → Check message parameters in SQS queue
│  │       │          → Verify term and payment_option are valid
│  │       │
│  │       └─ Error: ThrottlingException ?
│  │          └─ YES → Messages will auto-retry with backoff
│  │                  → No action needed unless persistent
│  │
├─ Alarm: "reporter-errors" ?
│  ├─ YES → Check Reporter Lambda Logs
│  │       ├─ Error: S3 access denied ?
│  │       │  └─ YES → Add s3:PutObject permission to Reporter role
│  │       │
│  │       └─ Error: Cost Explorer API failure ?
│  │          └─ YES → Check AWS service health dashboard
│  │
└─ Alarm: "purchase-intents-dlq-depth" ?
     └─ YES → Messages in Dead Letter Queue
             ├─ Check DLQ messages: aws sqs receive-message --queue-url $(terraform output -raw dlq_url)
             ├─ Review Purchaser logs for failure reason
             ├─ Fix underlying issue (IAM, quotas, etc.)
             └─ Move messages back to main queue for retry
                 → See: Recovering from Failed Purchases section
```

#### Issue: No Email Received After Scheduled Run

```
START: Expected Email Not Received
│
├─ Email Type: "Purchase Scheduled" (from Scheduler) ?
│  ├─ YES → Check Scheduler Lambda
│  │       ├─ Did Lambda execute?
│  │       │  ├─ NO → Check EventBridge schedule enabled
│  │       │  │      └─ aws events describe-rule --name $(terraform output -raw scheduler_rule_name)
│  │       │  │
│  │       │  └─ YES → Check CloudWatch Logs for execution
│  │       │           ├─ Logs show "DRY_RUN mode" ?
│  │       │           │  └─ YES → Disable dry_run in Terraform config
│  │       │           │
│  │       │           ├─ Logs show "0 recommendations" ?
│  │       │           │  └─ YES → Already at target coverage (expected)
│  │       │           │
│  │       │           └─ Logs show SNS publish failed ?
│  │       │              └─ YES → Verify SNS topic subscription confirmed
│  │       │                      → Check email spam/junk folder
│  │       │
│  ├─ Email Type: "Purchase Summary" (from Purchaser) ?
│  │  ├─ YES → Check Purchaser Lambda
│  │  │       ├─ Did Lambda execute?
│  │  │       │  ├─ NO → Check EventBridge schedule enabled
│  │  │       │  │
│  │  │       │  └─ YES → Check SQS queue depth
│  │  │       │           ├─ Queue empty?
│  │  │       │           │  └─ YES → No purchases to process (expected if none queued)
│  │  │       │           │
│  │  │       │           └─ Messages in queue?
│  │  │       │              └─ YES → Check Purchaser logs for errors
│  │  │       │                      → See: Failed Purchase Execution section
│  │  │
│  └─ Email Type: "Coverage Report" (from Reporter) ?
│     └─ YES → Check Reporter Lambda
│             ├─ Did Lambda execute?
│             │  ├─ NO → Check EventBridge schedule enabled
│             │  │
│             │  └─ YES → Check CloudWatch Logs
│             │           └─ Logs show errors?
│             │              └─ YES → Review error details
│             │                      → Common: S3 permissions, Cost Explorer access
│
└─ Check SNS Subscription Status
    └─ aws sns list-subscriptions-by-topic --topic-arn $(terraform output -raw sns_topic_arn)
        └─ Subscription "PendingConfirmation" ?
           └─ YES → Check email for confirmation link

```

#### Issue: Coverage Not Increasing

```
START: Coverage Not Reaching Target
│
├─ Are purchases being scheduled?
│  ├─ NO → Check Scheduler Lambda
│  │      ├─ Logs show "Already at target coverage" ?
│  │      │  └─ YES → But coverage is below target?
│  │      │          → Verify coverage_target_percent in Terraform config
│  │      │          → Check if multiple SP types (Compute/Database/SageMaker) tracked separately
│  │      │
│  │      ├─ Logs show "Coverage cap would be exceeded" ?
│  │      │  └─ YES → Increase max_coverage_cap in Terraform config
│  │      │          → OR review if cap is intentionally set low
│  │      │
│  │      └─ Logs show "Insufficient usage data" ?
│  │         └─ YES → Wait for more usage history
│  │                 → Check purchase_strategy.min_data_days setting
│  │
│  └─ YES → Are purchases being executed?
│           ├─ NO → Check SQS queue
│           │      ├─ Messages stuck in queue?
│           │      │  └─ YES → Check Purchaser Lambda logs
│           │      │          → Check for errors/alarms
│           │      │          → See: Failed Purchase Execution section
│           │      │
│           │      └─ Messages in DLQ?
│           │         └─ YES → See: Recovering from Failed Purchases section
│           │
│           └─ YES → Coverage still not increasing?
│                   ├─ Check usage trends
│                   │  └─ Usage growing faster than purchases?
│                   │     └─ YES → Increase max_purchase_percent
│                   │             → Current purchases can't keep up with growth
│                   │
│                   ├─ Check Savings Plans expiring
│                   │  └─ aws savingsplans describe-savings-plans \
│                   │      --filters name=end,values=$(date -u -d '30 days' +%Y-%m-%d)
│                   │     └─ Plans expiring soon?
│                   │        └─ YES → Expected - purchases account for expirations
│                   │                → May need higher max_purchase_percent
│                   │
│                   └─ Check purchase amounts
│                      └─ Purchases very small?
│                         └─ YES → Review max_purchase_percent
│                                 → May be too conservative for coverage gap
```

#### Issue: Unexpected Purchase Amounts

```
START: Purchase Amount Higher/Lower Than Expected
│
├─ Amount HIGHER than expected?
│  ├─ Check term mix configuration
│  │  └─ Review sp_plans.[type].term_weights in Terraform
│  │      └─ More weight on 3-year plans?
│  │         └─ YES → 3-year plans have higher hourly commitment
│  │                 → Check if this aligns with intended strategy
│  │
│  ├─ Check if multiple SP types enabled
│  │  └─ Review sp_plans.compute/database/sagemaker.enabled
│  │      └─ Multiple types enabled?
│  │         └─ YES → Each type calculated separately
│  │                 → Total commitment = sum of all types
│  │
│  └─ Check usage spike
│     └─ Review Cost Explorer for usage trends
│         └─ Recent usage increase?
│            └─ YES → Recommendations based on recent usage
│                    → Higher usage = higher recommendations
│
└─ Amount LOWER than expected?
   ├─ Check max_coverage_cap
   │  └─ Current coverage near max_coverage_cap?
   │     └─ YES → Purchases limited to avoid exceeding cap
   │             → Review if cap should be increased
   │
   ├─ Check max_purchase_percent
   │  └─ Review purchase_strategy.simple.max_purchase_percent
   │      └─ Low percentage?
   │         └─ YES → Limits how much can be purchased per cycle
   │                 → Increase if coverage growth too slow
   │
   └─ Check usage trends
      └─ Recent usage decrease?
         └─ YES → Recommendations based on recent usage
                 → Lower usage = lower recommendations
```

**Quick Reference: Common Commands for Troubleshooting**

| Scenario | Command | Purpose |
|----------|---------|---------|
| Check if Lambda ran | `aws logs tail /aws/lambda/$(terraform output -raw scheduler_function_name) --since 24h \| grep START` | Verify Lambda execution |
| View Lambda errors | `aws logs tail /aws/lambda/$(terraform output -raw scheduler_function_name) --since 7d --filter ERROR` | Find error messages |
| Check queue depth | `aws sqs get-queue-attributes --queue-url $(terraform output -raw queue_url) --attribute-names ApproximateNumberOfMessages` | See pending purchases |
| Check DLQ depth | `aws sqs get-queue-attributes --queue-url $(terraform output -raw dlq_url) --attribute-names ApproximateNumberOfMessages` | See failed purchases |
| View current coverage | `aws ce get-savings-plans-coverage --time-period Start=$(date -u -d '1 day ago' +%Y-%m-%d),End=$(date -u +%Y-%m-%d) --granularity DAILY` | Check coverage % |
| List recent purchases | `aws savingsplans describe-savings-plans --filters name=start,values=$(date -u -d '30 days ago' +%Y-%m-%d)` | Verify purchases executed |
| Check alarm status | `aws cloudwatch describe-alarms --alarm-name-prefix sp-autopilot --state-value ALARM` | Find active alarms |
| Check EventBridge schedule | `aws events describe-rule --name $(terraform output -raw scheduler_rule_name) \| jq -r '.State'` | Verify schedule enabled |

---

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

### Recovering from Failed Purchases Workflow

**Objective:** Restore failed purchases and ensure coverage gap is addressed

**When:** Purchaser Lambda failed, CloudWatch alarm triggered, or messages in DLQ

**Workflow:**

```
Failure Detected (Alarm or Email)
  ↓
[1] Identify failure type and location
  ↓
[2] Check CloudWatch Logs for error details
  ↓
[3] Determine message location:
  |
  ├─ Main Queue → Go to [4]
  └─ Dead Letter Queue → Go to [6]
  ↓
[4] Messages in Main Queue (Partial Failure)
  ↓
  • Fix underlying issue (IAM, quota, etc.)
  ↓
  • Messages will auto-retry on next Purchaser schedule
  ↓
  • OR invoke Purchaser manually for immediate retry
  ↓
  Go to [10]
  ↓
[6] Messages in DLQ (Complete Failure After Retries)
  ↓
[7] Fix root cause:
  |
  ├─ IAM Permissions → Add missing policies
  ├─ Service Quota → Request increase or cleanup
  ├─ Invalid Parameters → Fix configuration
  └─ Duplicate Purchase → No action (idempotency success)
  ↓
[8] Move messages from DLQ back to main queue
  ↓
[9] Invoke Purchaser Lambda to process recovered messages
  ↓
[10] Verify purchases completed successfully
  ↓
[11] Check coverage increased as expected
  ↓
[12] Clear DLQ if recovery successful
  ↓
✅ Recovery Complete
```

**Commands:**

```bash
# [1-2] Identify failure and check logs
aws logs tail /aws/lambda/$(terraform output -raw purchaser_function_name) \
  --since 2h --filter ERROR

# [3] Check main queue
aws sqs get-queue-attributes \
  --queue-url $(terraform output -raw queue_url) \
  --attribute-names ApproximateNumberOfMessages

# [3] Check DLQ
aws sqs get-queue-attributes \
  --queue-url $(terraform output -raw dlq_url) \
  --attribute-names ApproximateNumberOfMessages

# [4] Manual Purchaser invocation (if messages in main queue)
aws lambda invoke \
  --function-name $(terraform output -raw purchaser_function_name) \
  --payload '{}' \
  output.json

# [7] Example: Add IAM permission
aws iam attach-role-policy \
  --role-name $(terraform output -raw purchaser_role_name) \
  --policy-arn arn:aws:iam::aws:policy/AWSSavingsPlansFullAccess

# [8] Move messages from DLQ to main queue
aws sqs receive-message \
  --queue-url $(terraform output -raw dlq_url) \
  --max-number-of-messages 10 \
  | jq -r '.Messages[] | @json' \
  | while read msg; do
      body=$(echo $msg | jq -r '.Body')
      aws sqs send-message \
        --queue-url $(terraform output -raw queue_url) \
        --message-body "$body"
      receipt=$(echo $msg | jq -r '.ReceiptHandle')
      aws sqs delete-message \
        --queue-url $(terraform output -raw dlq_url) \
        --receipt-handle "$receipt"
    done

# [9] Invoke Purchaser to process recovered messages
aws lambda invoke \
  --function-name $(terraform output -raw purchaser_function_name) \
  --payload '{}' \
  output.json

# [10] Verify new Savings Plans
aws savingsplans describe-savings-plans \
  --filters name=start,values=$(date -u +%Y-%m-%d) \
  | jq -r '.savingsPlans[] | "\(.savingsPlanType): \(.commitment) USD/hour"'

# [11] Check coverage
aws ce get-savings-plans-coverage \
  --time-period Start=$(date -u -d '1 day ago' +%Y-%m-%d),End=$(date -u +%Y-%m-%d) \
  --granularity DAILY \
  | jq -r '.Total.CoveragePercentage'

# [12] Clear DLQ (if all recovered successfully)
aws sqs purge-queue --queue-url $(terraform output -raw dlq_url)
```

**Decision Tree:**

| Error Type | Root Cause | Fix | Retry Location |
|------------|-----------|-----|----------------|
| **AccessDeniedException** | Missing IAM permission | Add `savingsplans:CreateSavingsPlan` to Purchaser role | Main queue (auto-retry) or DLQ (manual) |
| **ServiceQuotaExceededException** | AWS Savings Plans limit reached | Request quota increase or cleanup expired plans | DLQ → Main queue after fix |
| **ValidationException** | Invalid purchase parameters | Fix configuration and redeploy | DLQ → Main queue after fix |
| **DuplicateSavingsPlanException** | Idempotency token reused (success) | None - purchase already exists | Delete from DLQ (already successful) |
| **ThrottlingException** | AWS API rate limit | Wait or reduce call frequency | Main queue (auto-retry with backoff) |
| **InternalServerException** | AWS service temporary issue | Wait for AWS recovery | Main queue (auto-retry) |

**Common Scenarios:**

1. **IAM Permission Missing (Most Common):**
   - **Symptom**: `AccessDeniedException` in logs
   - **Fix**: Add missing permission to Purchaser IAM role
   - **Recovery**: Messages auto-retry from main queue or move from DLQ

2. **Service Quota Exceeded:**
   - **Symptom**: `ServiceQuotaExceededException` in logs
   - **Fix**: Request quota increase via AWS Support or cleanup expired plans
   - **Recovery**: After quota increased, move messages from DLQ and retry

3. **Transient AWS Errors:**
   - **Symptom**: `InternalServerException` or `ThrottlingException`
   - **Fix**: Wait for AWS service recovery (no code changes needed)
   - **Recovery**: Messages auto-retry from main queue

4. **Configuration Issues:**
   - **Symptom**: `ValidationException` for invalid commitment or term
   - **Fix**: Update Terraform configuration and redeploy
   - **Recovery**: After fix, move messages from DLQ and retry

**⚠️ Important Notes:**

- **Always fix root cause before retrying** - repeated failures waste API calls and delay recovery
- **Idempotency protection**: Duplicate purchase errors are success (plan already exists), not failures
- **DLQ messages don't expire by default** - must be manually cleared after recovery
- **Next Scheduler run will re-queue** similar purchases if coverage gap persists
- **Don't retry invalid purchases indefinitely** - if configuration is wrong, cancel and wait for next month

---

**Related Documentation:**
- [README.md](../../README.md) - Module setup and configuration
- [ERROR_PATTERNS.md](../../ERROR_PATTERNS.md) - Detailed error reference
- [TESTING.md](../../TESTING.md) - Testing procedures

**Support:**
- GitHub Issues: [terraform-aws-sp-autopilot/issues](https://github.com/etiennechabert/terraform-aws-sp-autopilot/issues)
- AWS Cost Explorer: [Console Link](https://console.aws.amazon.com/cost-management/home#/savings-plans)

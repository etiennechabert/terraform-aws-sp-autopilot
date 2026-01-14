# Reporter Lambda

Generates periodic coverage and savings reports with metrics, trends, and email notifications.

## Overview

The Reporter Lambda is an optional component that provides visibility into Savings Plans performance. It runs on a configurable schedule (default: weekly on Mondays) to collect coverage history, gather savings data from active Savings Plans, and generate comprehensive reports uploaded to S3.

## How It Works

```
EventBridge Schedule
        │
        ▼
┌─────────────────────────────────────────────────────────────┐
│                      Reporter Lambda                         │
│                                                              │
│  1. Load configuration from environment                      │
│  2. Collect coverage history (last 30 days)                  │
│  3. Gather savings data from active Savings Plans            │
│  4. Calculate summary metrics and trends                     │
│  5. Generate HTML or JSON report                             │
│  6. Upload report to S3 with timestamp                       │
│  7. Send email notification with summary (if enabled)        │
└─────────────────────────────────────────────────────────────┘
        │
        ▼
   S3 Report + Email Notification
```

## Execution Steps

### Step 1: Load Configuration

Reads configuration from environment variables including S3 bucket name, report format, and email notification settings.

### Step 2: Collect Coverage History

Queries AWS Cost Explorer for Savings Plans coverage over the last 30 days:
- Daily coverage percentages
- Covered vs on-demand hours
- Total running hours per day

Plans expiring within the renewal window are included in coverage calculations for accurate historical reporting.

### Step 3: Gather Savings Data

Queries AWS Savings Plans API for active plan details:
- Total hourly commitment across all plans
- Individual plan information (type, term, payment option, dates)
- Average utilization over the last 7 days
- Estimated monthly savings (based on typical 25% discount rate)

### Step 4: Calculate Summary Metrics

Computes key performance indicators:
- **Current Coverage**: Most recent day's coverage percentage
- **Average Coverage**: Mean coverage over the reporting period
- **Trend Direction**: Whether coverage is increasing, decreasing, or stable
- **Utilization**: How efficiently Savings Plans are being used

### Step 5: Generate Report

Creates a report in the configured format:

- **HTML format** (default): Styled report with summary cards, coverage trend table, and active plans list
- **JSON format**: Structured data suitable for programmatic consumption and integration with other tools

### Step 6: Upload to S3

Uploads the report to the configured S3 bucket with:
- Timestamp-based object key: `savings-plans-report_YYYY-MM-DD_HH-MM-SS.{html|json}`
- Server-side encryption (AES256)
- Metadata including generation timestamp and generator name

### Step 7: Send Email Notification

When `EMAIL_REPORTS=true`, publishes a summary email to SNS containing:
- Current and average coverage percentages
- Trend indicator
- Active plan count and total commitment
- Estimated monthly savings
- Links to the S3 report (direct and console URLs)

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `REPORTS_BUCKET` | Yes | — | S3 bucket name for report storage |
| `SNS_TOPIC_ARN` | Yes | — | SNS topic ARN for notifications |
| `REPORT_FORMAT` | No | `html` | Report format: `html` or `json` |
| `EMAIL_REPORTS` | No | `false` | Send email notification with report link |
| `MANAGEMENT_ACCOUNT_ROLE_ARN` | No | — | IAM role ARN for cross-account access |
| `TAGS` | No | `{}` | Additional metadata tags (JSON) |

## IAM Permissions Required

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ce:GetSavingsPlansCoverage",
        "ce:GetSavingsPlansUtilization"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "savingsplans:DescribeSavingsPlans"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject"
      ],
      "Resource": "arn:aws:s3:::BUCKET_NAME/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "sns:Publish"
      ],
      "Resource": "arn:aws:sns:*:*:sp-autopilot-*"
    }
  ]
}
```

For cross-account setups, also requires `sts:AssumeRole` permission.

## Report Formats

### HTML Report

A styled, human-readable report containing:

- **Summary Cards**: Current coverage, average coverage, active plan count, estimated monthly savings
- **Coverage Trends Table**: Daily coverage history with hours breakdown
- **Active Plans Table**: Details of all active Savings Plans (ID, type, commitment, term, dates)
- **Visual Styling**: AWS-themed colors and responsive design

### JSON Report

A structured report for programmatic access:

```json
{
  "report_metadata": {
    "generated_at": "2024-01-15T08:00:00+00:00",
    "report_type": "savings_plans_coverage_and_savings",
    "generator": "sp-autopilot-reporter",
    "reporting_period_days": 30
  },
  "coverage_summary": {
    "current_coverage_percentage": 85.5,
    "average_coverage_percentage": 82.3,
    "trend_direction": "increasing",
    "trend_value": 3.2,
    "data_points": 30
  },
  "coverage_history": [...],
  "savings_summary": {
    "active_plans_count": 5,
    "total_hourly_commitment": 2.5,
    "total_monthly_commitment": 1825.0,
    "estimated_monthly_savings": 456.25,
    "average_utilization_percentage": 92.5
  },
  "active_savings_plans": [...]
}
```

## S3 Object Structure

Reports are stored with predictable naming:

```
s3://BUCKET_NAME/savings-plans-report_2024-01-15_08-00-00.html
s3://BUCKET_NAME/savings-plans-report_2024-01-15_08-00-00.json
```

Object metadata includes:
- `generated-at`: ISO 8601 timestamp
- `generator`: `sp-autopilot-reporter`
- Content-Type: `text/html` or `application/json`
- Server-side encryption: AES256

## Email Notifications

### Report Email

Subject: `Savings Plans Report - 85.5% Coverage, $456/mo Est. Savings`

Contains:
- Report generation timestamp
- Reporting period duration
- Coverage summary with current/average percentages and trend
- Savings summary with plan count, commitment, and utilization
- Direct and console links to S3 report

### Error Email

Subject: `[SP Autopilot] Reporter Lambda Failed`

Contains:
- Error message details
- Execution timestamp
- Guidance to check CloudWatch Logs

## Cross-Account Support

When `MANAGEMENT_ACCOUNT_ROLE_ARN` is set, the Lambda assumes the specified IAM role before calling Cost Explorer and Savings Plans APIs. This enables deployment in a secondary account while reading data from the AWS Organizations management account.

API calls made with assumed credentials:
- Cost Explorer: `GetSavingsPlansCoverage`, `GetSavingsPlansUtilization`
- Savings Plans: `DescribeSavingsPlans`

API calls made with local credentials:
- S3: `PutObject`
- SNS: `Publish`

See the [main README](../../README.md#cross-account-setup-for-aws-organizations) for setup instructions.

## Error Handling

All errors are:
1. Logged to CloudWatch Logs with full stack traces
2. Sent as email notifications via SNS (if topic is configured)
3. Re-raised to ensure Lambda failure is visible

The Lambda does not silently fail — all errors result in visible Lambda execution failures.

## Testing

### Manual Invocation

```bash
aws lambda invoke \
  --function-name sp-autopilot-reporter \
  --payload '{}' \
  output.json

cat output.json
```

### Report Generation Verification

1. Invoke Lambda manually
2. Check S3 bucket for new report file
3. Download and verify report content
4. If `EMAIL_REPORTS=true`, check email for notification

### JSON Format Verification

1. Set `REPORT_FORMAT=json` in Lambda environment
2. Invoke Lambda manually
3. Verify S3 object has `.json` extension
4. Download and validate JSON structure

### HTML Format Verification

1. Set `REPORT_FORMAT=html` in Lambda environment (or leave default)
2. Invoke Lambda manually
3. Verify S3 object has `.html` extension
4. Open report in browser to verify styling

## Related Components

- [Scheduler Lambda](../scheduler/README.md) — Analyzes usage and queues purchase intents
- [Purchaser Lambda](../purchaser/README.md) — Executes queued Savings Plan purchases
- [Main README](../../README.md) — Module overview and configuration

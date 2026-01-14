# Reporter Lambda

Generates periodic coverage and savings reports with metrics, trends, and email notifications.

## Overview

Optional component for Savings Plans performance visibility. Runs on schedule (default: weekly) to collect coverage history, gather savings data, and generate comprehensive reports uploaded to S3.

## Workflow

1. Load configuration from environment
2. Collect coverage history (last 30 days)
3. Gather savings data from active Savings Plans
4. Calculate summary metrics and trends
5. Generate HTML or JSON report
6. Upload report to S3 with timestamp
7. Send email notification with summary (if enabled)

## Key Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `REPORTS_BUCKET` | — | S3 bucket for reports (required) |
| `SNS_TOPIC_ARN` | — | SNS topic ARN (required) |
| `REPORT_FORMAT` | `html` | Report format (`html` or `json`) |
| `EMAIL_REPORTS` | `false` | Send email notification |
| `MANAGEMENT_ACCOUNT_ROLE_ARN` | — | Cross-account role ARN |

See [main README](../../README.md#configuration-variables) for complete variable reference.

## Report Formats

### HTML Report
- Summary cards (coverage, plan count, savings)
- Coverage trends table (30-day history)
- Active plans table
- AWS-themed styling

### JSON Report
Structured data for programmatic access with metadata, coverage summary, and active plans.

## S3 Object Structure

```
s3://BUCKET_NAME/savings-plans-report_2024-01-15_08-00-00.{html|json}
```

Objects include metadata: generation timestamp, generator name, server-side encryption (AES256).

## Testing

```bash
aws lambda invoke \
  --function-name sp-autopilot-reporter \
  --payload '{}' \
  output.json
```

Verify report created in S3 bucket.

## Related Components

- [Scheduler Lambda](../scheduler/README.md) — Analyzes usage and queues purchases
- [Purchaser Lambda](../purchaser/README.md) — Executes queued purchases
- [Main README](../../README.md) — Complete documentation

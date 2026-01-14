# Scheduler Lambda

Analyzes AWS Savings Plans usage and queues purchase intents based on coverage gaps and AWS recommendations.

## Overview

The Scheduler Lambda is the first component in the Savings Plans automation workflow. It runs on a configurable schedule (default: 1st of month) to analyze current Savings Plans coverage, fetch AWS purchase recommendations, and queue purchase intents for later execution by the [Purchaser Lambda](../purchaser/README.md).

## How It Works

```
EventBridge Schedule
        │
        ▼
┌─────────────────────────────────────────────────────────────┐
│                     Scheduler Lambda                        │
│                                                             │
│  1. Purge stale queue messages                              │
│  2. Calculate current coverage (excluding expiring plans)   │
│  3. Fetch AWS purchase recommendations                      │
│  4. Calculate purchase need based on coverage gap           │
│  5. Apply max_purchase_percent limit                        │
│  6. Split by term mix (Compute SP only)                     │
│  7. Queue purchase intents OR send dry-run email            │
│  8. Send notification email with analysis results           │
└─────────────────────────────────────────────────────────────┘
        │
        ▼
   SQS Queue (purchase intents)
```

## Execution Steps

### Step 1: Purge Queue

Clears any stale messages from the SQS queue to ensure a clean slate for the current scheduling cycle.

### Step 2: Calculate Current Coverage

Queries AWS Cost Explorer to determine current Savings Plans coverage. Plans expiring within `renewal_window_days` are excluded from the calculation to force renewal before expiration.

### Step 3: Get AWS Recommendations

Fetches purchase recommendations from AWS Cost Explorer for enabled SP types:
- **Compute SP**: Uses `COMPUTE_SP` recommendation type
- **Database SP**: Uses `DATABASE_SP` recommendation type

Recommendations are skipped if usage history is less than `min_data_days`.

### Step 4: Calculate Purchase Need

For each enabled SP type, calculates the coverage gap:
```
coverage_gap = coverage_target_percent - current_coverage
```

Only generates purchase plans if:
- Coverage gap is positive (current coverage below target)
- AWS provides a non-zero recommendation

### Step 5: Apply Purchase Limits

Scales down planned purchases based on `max_purchase_percent` to limit financial exposure per cycle. Plans below `min_commitment_per_plan` threshold are filtered out.

### Step 6: Split by Term

For **Compute Savings Plans** only, splits the total commitment according to `compute_sp_term_mix`:
```python
# Example: 67% 3-year, 33% 1-year
compute_sp_term_mix = {"three_year": 0.67, "one_year": 0.33}
```

**Database Savings Plans** always use 1-year term with no upfront payment (AWS constraint).

### Step 7: Queue or Notify

- **Normal mode** (`dry_run = false`): Queues purchase intents to SQS with idempotency tokens
- **Dry-run mode** (`dry_run = true`): Sends analysis email only, no messages queued

### Step 8: Send Notification

Publishes email notification to SNS topic with:
- Current coverage percentages
- Target coverage
- Planned purchases with estimated annual costs
- Cancellation instructions (for normal mode)

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `QUEUE_URL` | Yes | — | SQS queue URL for purchase intents |
| `SNS_TOPIC_ARN` | Yes | — | SNS topic ARN for notifications |
| `DRY_RUN` | No | `true` | If `true`, send email only (no queue) |
| `ENABLE_COMPUTE_SP` | No | `true` | Enable Compute SP analysis |
| `ENABLE_DATABASE_SP` | No | `false` | Enable Database SP analysis |
| `COVERAGE_TARGET_PERCENT` | No | `90` | Target coverage percentage |
| `MAX_PURCHASE_PERCENT` | No | `10` | Max purchase as % of recommendation |
| `RENEWAL_WINDOW_DAYS` | No | `7` | Days before expiry to exclude plans |
| `LOOKBACK_DAYS` | No | `30` | Days of usage history for recommendations |
| `MIN_DATA_DAYS` | No | `14` | Skip if insufficient usage history |
| `MIN_COMMITMENT_PER_PLAN` | No | `0.001` | Minimum hourly commitment ($) |
| `COMPUTE_SP_TERM_MIX` | No | `{"three_year": 0.67, "one_year": 0.33}` | Term split for Compute SP (JSON) |
| `COMPUTE_SP_PAYMENT_OPTION` | No | `ALL_UPFRONT` | Payment option for Compute SP |
| `PARTIAL_UPFRONT_PERCENT` | No | `50` | Upfront % for partial payment option |
| `MANAGEMENT_ACCOUNT_ROLE_ARN` | No | — | IAM role ARN for cross-account access |
| `TAGS` | No | `{}` | Tags to apply to purchased SPs (JSON) |

## IAM Permissions Required

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
        "savingsplans:DescribeSavingsPlans"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "sqs:SendMessage",
        "sqs:PurgeQueue"
      ],
      "Resource": "arn:aws:sqs:*:*:sp-autopilot-*"
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

## Queue Message Format

Purchase intents are queued as JSON messages:

```json
{
  "client_token": "scheduler-compute-THREE_YEAR-2024-01-01T08:00:00+00:00",
  "sp_type": "compute",
  "term": "THREE_YEAR",
  "hourly_commitment": 0.5,
  "payment_option": "ALL_UPFRONT",
  "recommendation_id": "abc123",
  "queued_at": "2024-01-01T08:00:00+00:00",
  "tags": {"Environment": "production"}
}
```

| Field | Description |
|-------|-------------|
| `client_token` | Unique idempotency token for purchase |
| `sp_type` | `compute` or `database` |
| `term` | `ONE_YEAR` or `THREE_YEAR` |
| `hourly_commitment` | Hourly commitment in USD |
| `payment_option` | `ALL_UPFRONT`, `PARTIAL_UPFRONT`, or `NO_UPFRONT` |
| `recommendation_id` | AWS recommendation ID for audit trail |
| `queued_at` | ISO 8601 timestamp when queued |
| `tags` | Tags to apply to the Savings Plan |

## Email Notifications

### Dry-Run Mode Email

Subject: `[DRY RUN] Savings Plans Analysis - No Purchases Scheduled`

Contains:
- Current coverage by SP type
- Recommended purchases (would be scheduled)
- Estimated annual costs
- Instructions to enable actual purchases

### Normal Mode Email

Subject: `Savings Plans Scheduled for Purchase`

Contains:
- Current coverage by SP type
- Scheduled purchases
- Estimated annual costs
- Cancellation instructions with queue URL and AWS CLI command

### Error Email

Subject: `ERROR: Savings Plans Scheduler Failed`

Contains:
- Error message details
- Troubleshooting steps
- CloudWatch Logs reference

## Cross-Account Support

When `MANAGEMENT_ACCOUNT_ROLE_ARN` is set, the Lambda assumes the specified IAM role before calling Cost Explorer and Savings Plans APIs. This enables deployment in a secondary account while making purchases from the AWS Organizations management account.

See the [main README](../../README.md#cross-account-setup-for-aws-organizations) for setup instructions.

## Error Handling

All errors are:
1. Logged to CloudWatch Logs with full stack traces
2. Sent as email notifications via SNS
3. Re-raised to ensure Lambda failure is visible

The Lambda does not silently fail — all errors result in visible Lambda execution failures.

## Testing

### Manual Invocation

```bash
aws lambda invoke \
  --function-name sp-autopilot-scheduler \
  --payload '{}' \
  output.json

cat output.json
```

### Dry-Run Verification

1. Set `DRY_RUN=true` in Lambda environment
2. Invoke Lambda manually or wait for scheduled run
3. Check email for analysis results
4. Verify no messages in SQS queue

### Normal Mode Verification

1. Set `DRY_RUN=false` in Lambda environment
2. Invoke Lambda manually
3. Check email for scheduled purchases
4. Verify messages in SQS queue match email content

## Related Components

- [Purchaser Lambda](../purchaser/README.md) — Executes queued purchase intents
- [Main README](../../README.md) — Module overview and configuration

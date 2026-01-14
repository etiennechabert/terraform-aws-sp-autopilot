# Purchaser Lambda

Executes queued Savings Plan purchases from SQS, validates coverage caps, and sends consolidated purchase summaries.

## Overview

The Purchaser Lambda is the second component in the Savings Plans automation workflow. It runs on a configurable schedule (default: 4th of month) to process purchase intents queued by the [Scheduler Lambda](../scheduler/README.md), execute the actual AWS Savings Plan purchases, and send a consolidated summary email.

## How It Works

```
EventBridge Schedule
        │
        ▼
┌─────────────────────────────────────────────────────────────┐
│                     Purchaser Lambda                         │
│                                                              │
│  1. Check SQS queue for purchase intents                     │
│  2. Get current coverage (excluding expiring plans)          │
│  3. For each message:                                        │
│     a. Validate against max_coverage_cap                     │
│     b. Execute purchase via CreateSavingsPlan API            │
│     c. Delete message on success                             │
│  4. Send aggregated email with all results                   │
│  5. Handle errors with immediate notification                │
└─────────────────────────────────────────────────────────────┘
        │
        ▼
   Savings Plans Created + Email Notification
```

## Execution Steps

### Step 1: Check Queue

Receives messages from the SQS queue. If the queue is empty, the Lambda exits silently without sending any email — this is expected behavior when no purchases were scheduled.

### Step 2: Get Current Coverage

Queries AWS Cost Explorer and Savings Plans APIs to calculate current coverage:
- Gets coverage percentages from Cost Explorer (last 7 days average)
- Identifies Savings Plans expiring within `renewal_window_days`
- Adjusts coverage to exclude expiring plans (forces renewal)

### Step 3: Process Purchase Messages

For each message in the queue:

1. **Parse purchase intent** — Extracts commitment, term, payment option, and idempotency token
2. **Validate coverage cap** — Checks if projected coverage would exceed `max_coverage_cap`
3. **Execute or skip** — Either creates the Savings Plan or skips with reason logged
4. **Update tracking** — Updates in-memory coverage for accurate subsequent cap validation
5. **Delete message** — Removes message from queue (even if skipped to prevent retry loops)

### Step 4: Send Summary Email

Publishes an aggregated email to SNS with:
- Execution timestamp
- Total purchases processed, executed, and skipped
- Current coverage after execution
- Details for each successful purchase (SP ID, commitment, term)
- Details for each skipped purchase with reason

### Step 5: Handle Errors

Any errors during execution:
- Are logged with full stack traces
- Trigger an immediate error notification email
- Are re-raised to ensure Lambda failure is visible

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `QUEUE_URL` | Yes | — | SQS queue URL for purchase intents |
| `SNS_TOPIC_ARN` | Yes | — | SNS topic ARN for notifications |
| `MAX_COVERAGE_CAP` | No | `95` | Hard cap — never exceed this coverage |
| `RENEWAL_WINDOW_DAYS` | No | `7` | Days before expiry to exclude plans |
| `MANAGEMENT_ACCOUNT_ROLE_ARN` | No | — | IAM role ARN for cross-account access |
| `TAGS` | No | `{}` | Additional tags for purchased SPs (JSON) |

## IAM Permissions Required

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ce:GetSavingsPlansCoverage"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "savingsplans:DescribeSavingsPlans",
        "savingsplans:CreateSavingsPlan"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "sqs:ReceiveMessage",
        "sqs:DeleteMessage"
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

The Purchaser expects messages in this format (created by Scheduler Lambda):

```json
{
  "client_token": "scheduler-compute-THREE_YEAR-2024-01-01T08:00:00+00:00",
  "sp_type": "ComputeSavingsPlans",
  "term_seconds": 94608000,
  "commitment": "0.50",
  "payment_option": "ALL_UPFRONT",
  "upfront_amount": "4380.00",
  "offering_id": "abc123def456",
  "projected_coverage_after": 85.5,
  "queued_at": "2024-01-01T08:00:00+00:00"
}
```

| Field | Description |
|-------|-------------|
| `client_token` | Unique idempotency token for purchase |
| `sp_type` | `ComputeSavingsPlans` or `DatabaseSavingsPlans` |
| `term_seconds` | Term duration in seconds (31536000 = 1yr, 94608000 = 3yr) |
| `commitment` | Hourly commitment in USD (string) |
| `payment_option` | `ALL_UPFRONT`, `PARTIAL_UPFRONT`, or `NO_UPFRONT` |
| `upfront_amount` | Upfront payment amount (if applicable) |
| `offering_id` | AWS Savings Plan offering ID |
| `projected_coverage_after` | Expected coverage after this purchase |
| `queued_at` | ISO 8601 timestamp when queued |

## Coverage Cap Validation

Before executing each purchase, the Purchaser validates:

```
projected_coverage_after <= max_coverage_cap
```

If the projected coverage would exceed the cap:
- Purchase is **skipped** (not executed)
- Message is **deleted** from queue (no retry)
- Reason is logged and included in summary email

This provides a safety net even if usage decreases between scheduling and purchasing.

## Email Notifications

### Success Email

Subject: `AWS Savings Plans Purchase Complete - X Executed, Y Skipped`

Contains:
- Execution timestamp
- Total intents processed
- Counts of successful and skipped purchases
- Current coverage after execution (Compute and Database)
- Detailed list of each purchase with SP ID, commitment, term
- Detailed list of skipped purchases with reason

### Error Email

Subject: `AWS Savings Plans Purchaser - ERROR`

Contains:
- Error message details
- Queue URL for investigation
- Guidance that messages remain in queue for retry
- Next steps for troubleshooting

## Cross-Account Support

When `MANAGEMENT_ACCOUNT_ROLE_ARN` is set, the Lambda assumes the specified IAM role before calling Cost Explorer and Savings Plans APIs. This enables deployment in a secondary account while making purchases from the AWS Organizations management account.

API calls made with assumed credentials:
- Cost Explorer: `GetSavingsPlansCoverage`
- Savings Plans: `DescribeSavingsPlans`, `CreateSavingsPlan`

API calls made with local credentials:
- SQS: `ReceiveMessage`, `DeleteMessage`
- SNS: `Publish`

See the [main README](../../README.md#cross-account-setup-for-aws-organizations) for setup instructions.

## Error Handling

All errors are:
1. Logged to CloudWatch Logs with full stack traces
2. Sent as email notifications via SNS
3. Re-raised to ensure Lambda failure is visible

Failed purchases leave messages in queue for retry on next execution. The Lambda does not silently fail — all errors result in visible Lambda execution failures.

## Idempotency

Purchases are idempotent via AWS's `clientToken` parameter:
- Each purchase intent includes a unique `client_token`
- AWS CreateSavingsPlan API returns existing SP if token was already used
- Safe to retry failed executions without risk of duplicate purchases

## Testing

### Manual Invocation

```bash
aws lambda invoke \
  --function-name sp-autopilot-purchaser \
  --payload '{}' \
  output.json

cat output.json
```

### Empty Queue Verification

1. Ensure SQS queue is empty
2. Invoke Lambda manually
3. Verify Lambda succeeds with `purchases_executed: 0`
4. Verify no email is sent (expected behavior)

### Purchase Execution Verification

1. Run Scheduler Lambda with `DRY_RUN=false` to queue intents
2. Verify messages appear in SQS queue
3. Invoke Purchaser Lambda manually
4. Check email for purchase summary
5. Verify Savings Plans created in AWS Console
6. Verify SQS queue is empty

### Coverage Cap Verification

1. Queue a purchase intent with high `projected_coverage_after`
2. Set `MAX_COVERAGE_CAP` below the projected coverage
3. Invoke Purchaser Lambda
4. Verify purchase is skipped in summary email
5. Verify message is deleted from queue

## Tagging

All purchased Savings Plans are tagged with:

| Tag | Value |
|-----|-------|
| `ManagedBy` | `terraform-aws-sp-autopilot` |
| `PurchaseDate` | ISO 8601 timestamp of purchase |
| `ClientToken` | Idempotency token for audit trail |

Additional custom tags from the `TAGS` environment variable are merged in.

## Related Components

- [Scheduler Lambda](../scheduler/README.md) — Analyzes usage and queues purchase intents
- [Main README](../../README.md) — Module overview and configuration

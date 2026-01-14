# Scheduler Lambda

Analyzes AWS Savings Plans usage and queues purchase intents based on coverage gaps and AWS recommendations.

## Overview

First component in the automation workflow. Runs on schedule (default: 1st of month) to analyze coverage, fetch AWS recommendations, and queue purchase intents for the [Purchaser Lambda](../purchaser/README.md).

## Workflow

1. Purge stale queue messages
2. Calculate current coverage (excluding expiring plans)
3. Fetch AWS purchase recommendations
4. Calculate purchase need based on coverage gap
5. Apply `max_purchase_percent` limit
6. Split by term mix (Compute SP only)
7. Queue purchase intents OR send dry-run email
8. Send notification email with results

## Key Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `QUEUE_URL` | — | SQS queue URL (required) |
| `SNS_TOPIC_ARN` | — | SNS topic ARN (required) |
| `DRY_RUN` | `true` | Email only, no queue |
| `COVERAGE_TARGET_PERCENT` | `90` | Target coverage % |
| `MAX_PURCHASE_PERCENT` | `10` | Max purchase limit |
| `MANAGEMENT_ACCOUNT_ROLE_ARN` | — | Cross-account role ARN |

See [main README](../../README.md#configuration-variables) for complete variable reference.

## Queue Message Format

```json
{
  "client_token": "scheduler-compute-THREE_YEAR-2024-01-01T08:00:00+00:00",
  "sp_type": "compute",
  "term": "THREE_YEAR",
  "hourly_commitment": 0.5,
  "payment_option": "ALL_UPFRONT",
  "queued_at": "2024-01-01T08:00:00+00:00"
}
```

## Testing

```bash
aws lambda invoke \
  --function-name sp-autopilot-scheduler \
  --payload '{}' \
  output.json
```

In dry-run mode, verify no messages queued to SQS.

## Related Components

- [Purchaser Lambda](../purchaser/README.md) — Executes queued purchases
- [Reporter Lambda](../reporter/README.md) — Generates coverage reports
- [Main README](../../README.md) — Complete documentation

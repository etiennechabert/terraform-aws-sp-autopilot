# Purchaser Lambda

Executes queued Savings Plan purchases from SQS, validates coverage caps, and sends consolidated purchase summaries.

## Overview

Second component in the automation workflow. Runs on schedule (default: 4th of month) to process purchase intents queued by the [Scheduler Lambda](../scheduler/README.md), execute purchases, and send summary emails.

## Workflow

1. Receive messages from SQS queue
2. Get current coverage (excluding expiring plans)
3. For each message:
   - Validate against `max_coverage_cap`
   - Execute purchase via CreateSavingsPlan API
   - Delete message on success
4. Send aggregated email with all results
5. Handle errors with immediate notification

## Key Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `QUEUE_URL` | — | SQS queue URL (required) |
| `SNS_TOPIC_ARN` | — | SNS topic ARN (required) |
| `MAX_COVERAGE_CAP` | `95` | Hard coverage ceiling |
| `RENEWAL_WINDOW_DAYS` | `7` | Days before expiry to exclude |
| `MANAGEMENT_ACCOUNT_ROLE_ARN` | — | Cross-account role ARN |

See [main README](../../README.md#configuration-variables) for complete variable reference.

## Coverage Cap Validation

Before executing each purchase:

```
projected_coverage_after <= max_coverage_cap
```

If exceeded, purchase is skipped and message deleted (no retry).

## Idempotency

Purchases use AWS's `clientToken` parameter for idempotency. Safe to retry failed executions without risk of duplicate purchases.

## Testing

```bash
aws lambda invoke \
  --function-name sp-autopilot-purchaser \
  --payload '{}' \
  output.json
```

If queue is empty, Lambda exits silently (no email sent).

## Related Components

- [Scheduler Lambda](../scheduler/README.md) — Queues purchase intents
- [Reporter Lambda](../reporter/README.md) — Generates coverage reports
- [Main README](../../README.md) — Complete documentation

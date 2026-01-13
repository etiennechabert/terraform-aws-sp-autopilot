# AWS Savings Plans Automation Module — Requirements Specification

**Version**: 1.0  
**Date**: January 2026  
**Status**: Final Draft

---

## 1. Overview

### 1.1 Purpose

An open-source Terraform module that automates AWS Savings Plans purchases based on usage analysis. The module targets consistent coverage while limiting financial exposure through incremental, spread-out commitments.

### 1.2 Goals

- Automate Savings Plans purchasing to maintain target coverage levels
- Spread financial risk over time with configurable purchase limits
- Provide human review window before purchases execute
- Support both Compute and Database Savings Plans
- Be simple, auditable, and open-source friendly

### 1.3 Non-Goals (v1)

- SageMaker Savings Plans (separate SP type, out of scope)
- EC2 Instance Savings Plans (Compute SP provides sufficient flexibility)
- Selling or exchanging existing commitments
- Multi-cloud support

---

## 2. Supported Savings Plan Types

### 2.1 Compute Savings Plans

| Attribute | Details |
|-----------|---------|
| Coverage | EC2, Lambda, Fargate |
| Terms | 1-year, 3-year |
| Payment Options | All Upfront, Partial Upfront, No Upfront |
| Max Discount | Up to 66% |

### 2.2 Database Savings Plans

| Attribute | Details |
|-----------|---------|
| Coverage | RDS, Aurora, DynamoDB, ElastiCache (Valkey), DocumentDB, Neptune, Keyspaces, Timestream, DMS |
| Terms | 1-year only (AWS limitation) |
| Payment Options | No Upfront only (AWS limitation) |
| Max Discount | Up to 35% (serverless), up to 20% (provisioned) |

---

## 3. Architecture

### 3.1 Components

The module consists of two Lambda functions with an SQS queue between them:

1. **Scheduler Lambda**: Analyzes usage, calculates needed purchases, queues purchase intents
2. **SQS Queue**: Holds purchase intents during human review window
3. **Purchaser Lambda**: Executes queued purchases after review window

### 3.2 Flow

```
EventBridge Schedule
        │
        ▼
┌─────────────────┐
│ Scheduler Lambda │ ──► Purges queue, analyzes, queues new intents
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│    SQS Queue    │ ◄── Human review window (users can delete messages)
└────────┬────────┘
         │
EventBridge Schedule (separate, later date)
         │
         ▼
┌─────────────────┐
│ Purchaser Lambda │ ──► Executes purchases, validates coverage cap
└─────────────────┘
```

---

## 4. Scheduler Lambda Requirements

### 4.1 Trigger

- Runs on configurable EventBridge schedule (e.g., 1st of month)

### 4.2 Behavior

1. **Purge existing queue** — Clear any stale messages from previous runs
2. **Calculate current coverage** — Exclude SPs expiring within `renewal_window_days`
3. **Get AWS recommendations** — Use Cost Explorer API for recommendation data
4. **Calculate purchase need** — Determine commitment needed to reach `coverage_target_percent`
5. **Apply limits** — Respect `max_purchase_percent` constraint
6. **Split by term** — For Compute SP, split commitment according to `term_mix`
7. **Queue or notify**:
   - If `dry_run = true`: Send email only, do NOT queue messages
   - If `dry_run = false`: Queue messages to SQS AND send email
8. **Error handling** — Any error must raise an exception (no silent failures)

### 4.3 Coverage Calculation

- Current coverage is obtained from AWS Cost Explorer
- SPs expiring within `renewal_window_days` are EXCLUDED from current coverage
- This forces recalculation of their coverage need (they are treated as if already expired)

### 4.4 Purchase Sizing

- `max_purchase_percent`: Maximum single purchase cycle as percentage of current monthly on-demand spend
- Example: 10% max with $10,000/month spend → max $1,000/month commitment per cycle
- This spreads risk over multiple purchase cycles

### 4.5 Term Split (Compute SP Only)

- Total commitment is split according to `term_mix` configuration
- Example: $10/hr commitment with `{three_year: 0.67, one_year: 0.33}` produces:
  - One 3-year SP at $6.67/hr
  - One 1-year SP at $3.33/hr
- Database SP: Always 1-year (term_mix does not apply)

---

## 5. SQS Queue Requirements

### 5.1 Message Content

Each message must contain:

- `client_token`: Unique idempotency key for the purchase
- `sp_type`: Type of Savings Plan (ComputeSavingsPlans, DatabaseSavingsPlans)
- `offering_id`: AWS offering ID for the specific SP
- `commitment`: Hourly commitment amount (string, e.g., "5.50")
- `term_seconds`: Term duration in seconds
- `payment_option`: Payment option (ALL_UPFRONT, PARTIAL_UPFRONT, NO_UPFRONT)
- `upfront_amount`: Upfront payment amount (if applicable)
- `analysis_timestamp`: When the analysis was performed
- `coverage_at_analysis`: Coverage percentage at time of analysis
- `projected_coverage_after`: Expected coverage after this purchase

### 5.2 Cancellation

- Users cancel planned purchases by deleting messages from the SQS queue
- This is documented as the cancellation mechanism (no UI provided)

---

## 6. Purchaser Lambda Requirements

### 6.1 Trigger

- Runs on configurable EventBridge schedule (e.g., 4th of month)
- Separate schedule from Scheduler Lambda (allows review window)
- If schedules are set to same time, purchases execute immediately (no review)

### 6.2 Behavior

1. **Check queue** — If empty, exit silently (no email, no error)
2. **Get current coverage** — Exclude SPs expiring within `renewal_window_days`
3. **Process each message**:
   - Calculate if purchase would exceed `max_coverage_cap`
   - If YES: Skip purchase, record reason, delete message
   - If NO: Execute purchase via CreateSavingsPlan API, delete message on success
4. **Send aggregated email** — One email summarizing all purchases/skips for this run
5. **Error handling**:
   - On API error: Send error email immediately, raise exception
   - Message stays in queue for retry
   - `client_token` ensures idempotency (no duplicate purchases)

### 6.3 Coverage Cap Enforcement

- `max_coverage_cap`: Hard ceiling that must never be exceeded
- Purchaser REFUSES to execute any purchase that would bring total coverage above this cap
- This protects against over-commitment if usage shrinks between scheduling and purchasing

### 6.4 Empty Queue Behavior

- If no messages in queue, purchaser exits silently
- No email sent, no error raised

---

## 7. Configuration Parameters

### 7.1 Savings Plan Types

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `enable_compute_sp` | bool | true | Enable Compute Savings Plans automation |
| `enable_database_sp` | bool | false | Enable Database Savings Plans automation |

### 7.2 Coverage Strategy

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `coverage_target_percent` | number | 90 | Target hourly coverage percentage |
| `max_coverage_cap` | number | 95 | Hard cap — never exceed this coverage |
| `lookback_days` | number | 30 | Days of usage history for AWS recommendations |

### 7.3 Risk Management

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `max_purchase_percent` | number | 10 | Max purchase as % of monthly spend |
| `min_data_days` | number | 14 | Skip if insufficient usage history |
| `min_commitment_per_plan` | number | 0.001 | Minimum commitment per SP (AWS min: $0.001/hr) |

### 7.4 Expiring Plans

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `renewal_window_days` | number | 7 | SPs expiring within X days excluded from coverage calculation |

### 7.5 Compute SP Options

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `compute_sp_term_mix` | object | `{three_year: 0.67, one_year: 0.33}` | Split of commitment between terms |
| `compute_sp_payment_option` | string | "ALL_UPFRONT" | Payment option |
| `partial_upfront_percent` | number | 50 | Percentage paid upfront for PARTIAL_UPFRONT |

### 7.6 Scheduling

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `scheduler_schedule` | string | `cron(0 8 1 * ? *)` | When scheduler runs |
| `purchaser_schedule` | string | `cron(0 8 4 * ? *)` | When purchaser runs |

### 7.7 Operations

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `dry_run` | bool | true | If true, scheduler sends email only (no queue) |
| `send_no_action_email` | bool | true | Send email when no purchases needed |

### 7.8 Notifications

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `notification_emails` | list(string) | [] | Email addresses for notifications |

### 7.9 Monitoring

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `enable_lambda_error_alarm` | bool | true | CloudWatch alarm on Lambda errors |
| `enable_dlq_alarm` | bool | true | CloudWatch alarm on DLQ depth |

### 7.10 AWS Organizations

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `management_account_role_arn` | string | null | Role ARN to assume in management account |

### 7.11 Tagging

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `tags` | map(string) | {} | Additional tags to apply to purchased SPs |

---

## 8. Validation Rules

### 8.1 Term Mix

- `compute_sp_term_mix.three_year + compute_sp_term_mix.one_year` must equal 1
- Both values must be non-negative

### 8.2 Coverage

- `max_coverage_cap` must be greater than `coverage_target_percent`
- `max_coverage_cap` must be ≤ 100
- `coverage_target_percent` must be between 1 and 100

### 8.3 Payment Option

- `compute_sp_payment_option` must be one of: ALL_UPFRONT, PARTIAL_UPFRONT, NO_UPFRONT

### 8.4 Minimum Commitment

- `min_commitment_per_plan` must be ≥ 0.001 (AWS minimum)

### 8.5 Database SP

- Database SP only supports 1-year term and no-upfront payment (AWS limitation)
- Module must validate and/or document this constraint

---

## 9. Notifications

### 9.1 Mechanism

- SNS topic with email subscriptions
- Recipients receive confirmation email and must click to confirm subscription
- Lambda publishes to SNS topic

### 9.2 Email Events

| Event | Sent By | Behavior |
|-------|---------|----------|
| Purchases scheduled | Scheduler | Always sent when purchases queued |
| Dry run analysis | Scheduler | Sent instead of above when `dry_run = true` |
| No action needed | Scheduler | Sent if coverage already at target (configurable) |
| Purchases completed | Purchaser | Aggregated summary of all purchases/skips |
| Purchase error | Purchaser | Immediate email on API failure |
| Empty queue | Purchaser | No email (silent exit) |

### 9.3 Email Content Requirements

**Scheduler Email (purchases scheduled):**
- Analysis timestamp
- Current coverage (Compute and Database separately)
- List of planned purchases with details
- Projected coverage after purchases
- Instructions for cancellation (queue URL)
- Execution date

**Scheduler Email (dry run):**
- Same as above
- Clear indication that no purchases were scheduled
- Instruction to set `dry_run = false` to enable

**Scheduler Email (no action needed):**
- Analysis timestamp
- Current coverage
- Confirmation that coverage meets/exceeds target

**Purchaser Email (completed):**
- Execution timestamp
- List of successful purchases with SP IDs
- List of skipped purchases with reasons
- Current coverage after execution

**Purchaser Email (error):**
- Execution timestamp
- Failed purchase details
- Error message and context
- Queue URL for investigation

---

## 10. Error Handling

### 10.1 Principle

**No silent failures.** All errors must raise exceptions. The Lambda must fail visibly so CloudWatch alarms trigger.

### 10.2 Error Categories

| Category | Behavior | Retry |
|----------|----------|-------|
| Insufficient data | Raise exception | No |
| Configuration error | Raise exception | No |
| Coverage cap exceeded | Skip purchase, delete message | No (expected) |
| AWS API error | Send email, raise exception | Yes |

### 10.3 Idempotency

- All purchases use `client_token` parameter
- Token format ensures uniqueness per analysis run
- Safe to retry on transient failures — duplicate calls return existing SP

---

## 11. Monitoring

### 11.1 CloudWatch Alarms

| Alarm | Condition | Configurable |
|-------|-----------|--------------|
| Scheduler Lambda errors | Errors ≥ 1 | Yes (`enable_lambda_error_alarm`) |
| Purchaser Lambda errors | Errors ≥ 1 | Yes (`enable_lambda_error_alarm`) |
| DLQ message count | Messages ≥ 1 | Yes (`enable_dlq_alarm`) |

### 11.2 Alarm Actions

- Alarms publish to the same SNS topic used for notifications

---

## 12. Tagging

### 12.1 Default Tags

All purchased Savings Plans are tagged with:

- `ManagedBy`: Identifier for this automation module
- `AnalysisTimestamp`: When the purchase was planned

### 12.2 Custom Tags

User-provided tags via `tags` parameter are merged with defaults.

### 12.3 SP Naming

Purchased SPs should have identifiable names indicating they were created by automation.

---

## 13. AWS Organizations Support

### 13.1 Behavior

- If `management_account_role_arn` is provided, Lambdas assume this role for SP operations
- Coverage data and purchases apply at the organization level
- Module can be deployed in any account with appropriate cross-account role

### 13.2 No Role Provided

- If `management_account_role_arn` is null, Lambdas use their execution role directly
- Assumes deployment is in the management account

---

## 14. IAM Requirements

### 14.1 Cost Explorer Permissions

- `ce:GetSavingsPlansCoverage`
- `ce:GetSavingsPlansUtilization`
- `ce:GetSavingsPlansPurchaseRecommendation`
- `ce:GetCostAndUsage`

### 14.2 Savings Plans Permissions

- `savingsplans:DescribeSavingsPlans`
- `savingsplans:DescribeSavingsPlansOfferings`
- `savingsplans:DescribeSavingsPlansOfferingRates`
- `savingsplans:CreateSavingsPlan`

### 14.3 SQS Permissions

- `sqs:SendMessage`
- `sqs:ReceiveMessage`
- `sqs:DeleteMessage`
- `sqs:PurgeQueue`
- `sqs:GetQueueAttributes`

### 14.4 SNS Permissions

- `sns:Publish`

### 14.5 Cross-Account (if applicable)

- `sts:AssumeRole` on `management_account_role_arn`

---

## 15. Constraints & Limitations

### 15.1 AWS Limitations

- Database Savings Plans: 1-year term only, no-upfront only
- Minimum commitment: $0.001/hr
- Maximum commitment: $1,000,000/hr
- Savings Plans cannot be modified or cancelled after purchase (except within 7-day return window for plans ≤$100/hr)

### 15.2 Module Limitations

- No support for SageMaker Savings Plans (v1)
- No support for EC2 Instance Savings Plans (Compute SP used instead)
- No automated selling/exchange of existing commitments
- No approval workflow UI (users manage queue directly)

---

## 16. Open Source Considerations

### 16.1 Code Quality

- Simple, readable Python code
- Easy to audit and review
- Minimal dependencies
- Well-documented functions

### 16.2 Licensing

- Open source license (to be determined)
- Clear contribution guidelines

### 16.3 Documentation

- README with quick start
- Full configuration reference
- Architecture explanation
- Troubleshooting guide

---

## Appendix A: Glossary

| Term | Definition |
|------|------------|
| Coverage | Percentage of eligible on-demand spend covered by Savings Plans |
| Commitment | Hourly spend amount pledged for a Savings Plan ($/hr) |
| Term | Duration of Savings Plan commitment (1 or 3 years) |
| Offering ID | AWS identifier for a specific Savings Plan configuration |
| Client Token | Idempotency key to prevent duplicate purchases |
| DLQ | Dead Letter Queue — holds failed messages after retry exhaustion |

---

## Appendix B: Related AWS APIs

- `ce:GetSavingsPlansPurchaseRecommendation` — Get purchase recommendations
- `ce:GetSavingsPlansCoverage` — Get current coverage metrics
- `savingsplans:CreateSavingsPlan` — Purchase a new Savings Plan
- `savingsplans:DescribeSavingsPlans` — List existing Savings Plans
- `savingsplans:DescribeSavingsPlansOfferings` — List available SP offerings

---

## Appendix C: Revision History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | January 2026 | Initial specification |

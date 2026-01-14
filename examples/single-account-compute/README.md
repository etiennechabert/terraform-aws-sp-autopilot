# Single Account - Compute Savings Plans Only

Simplest deployment scenario: single AWS account, Compute Savings Plans only (EC2, Lambda, Fargate), conservative targets, dry-run mode enabled.

## Features

- ✅ Automated Compute Savings Plans purchasing
- ✅ Conservative 5% monthly spend limit
- ✅ 3-day human review window
- ✅ Email notifications and CloudWatch alarms
- ✅ Starts in dry-run mode for safety

## Deployment

### 1. Configure

Update `notification_emails` in `main.tf`:

```hcl
notification_emails = ["your-email@example.com"]
```

### 2. Deploy

```bash
terraform init
terraform plan
terraform apply
```

### 3. Confirm SNS Subscription

Check email for SNS confirmation and click the link.

## Testing

### Dry-Run Mode (Default)

Module starts with `dry_run = true`:
- Scheduler analyzes usage monthly
- Sends email with recommendations
- **Does NOT queue purchases**
- No actual Savings Plans purchased

### Manual Test

```bash
aws lambda invoke \
  --function-name $(terraform output -raw scheduler_lambda_name) \
  --payload '{}' \
  response.json
```

Expected email includes current coverage, recommended purchases, and "DRY RUN" notice.

## Enabling Real Purchases

### 1. Update Configuration

Edit `main.tf`:

```hcl
dry_run = false
```

### 2. Apply and Monitor

```bash
terraform apply
```

After enabling:
1. Wait for next scheduler run (1st of month)
2. Review email with purchase recommendations
3. Check SQS queue for queued purchases
4. To cancel, delete messages from queue before purchaser runs (4th of month)

## Configuration Examples

### Adjust Coverage Targets

```hcl
coverage_target_percent = 80  # Lower = more conservative
max_coverage_cap        = 90  # Hard ceiling
```

### Control Spending Velocity

```hcl
max_purchase_percent = 5  # Lower = slower commitment growth
```

### Balance Discount vs Flexibility

```hcl
compute_sp_term_mix = {
  three_year = 0.70  # Higher = more discount, less flexibility
  one_year   = 0.30
}
```

### Adjust Review Window

```hcl
scheduler_schedule = "cron(0 8 1 * ? *)"   # 1st of month
purchaser_schedule = "cron(0 8 10 * ? *)"  # 10th = 9-day window
```

## Monitoring

### CloudWatch Logs

```bash
aws logs tail /aws/lambda/$(terraform output -raw scheduler_lambda_name) --follow
```

### SQS Queue

```bash
aws sqs get-queue-attributes \
  --queue-url $(terraform output -raw queue_url) \
  --attribute-names ApproximateNumberOfMessages
```

## Cleanup

```bash
terraform destroy
```

**Note:** Does NOT cancel existing Savings Plans. Active plans continue until term expires.

## Next Steps

- Add Database SP: `enable_database_sp = true`
- AWS Organizations: Set `management_account_role_arn`
- Increase targets as confidence grows

See [main README](../../README.md) for complete documentation.

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

Update `notifications.emails` in `main.tf`:

```hcl
notifications = {
  emails = ["your-email@example.com"]
}
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

Module starts with `lambda_config.scheduler.dry_run = true`:
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
lambda_config = {
  scheduler = {
    dry_run = false
  }
}
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
purchase_strategy = {
  max_coverage_cap = 90  # Hard ceiling

  target = {
    fixed = { coverage_percent = 80 }  # Lower = more conservative
  }

  split = {
    linear = { step_percent = 5 }  # Lower = slower commitment growth
  }
}
```

### Choose Plan Type

```hcl
sp_plans = {
  compute = {
    enabled   = true
    plan_type = "all_upfront_three_year"  # Higher discount, less flexibility
    # Other options: "all_upfront_one_year", "partial_upfront_three_year", etc.
  }
}
```

### Adjust Review Window

```hcl
scheduler = {
  scheduler = "cron(0 8 1 * ? *)"   # 1st of month
  purchaser = "cron(0 8 10 * ? *)"  # 10th = 9-day window
}
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

- Add Database SP: `sp_plans.database.enabled = true`
- AWS Organizations: Set per-Lambda `assume_role_arn` in `lambda_config`
- Increase targets as confidence grows

See [main README](../../README.md) for complete documentation.

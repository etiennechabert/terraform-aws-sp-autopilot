# Single Account - Database Savings Plans Only

Database Savings Plans automation for RDS, Aurora, DynamoDB, ElastiCache, DocumentDB, Neptune, Keyspaces, Timestream, and DMS.

## Features

- ✅ Automated Database Savings Plans purchasing
- ✅ Covers all eligible database services
- ✅ Conservative 5% monthly spend limit, 3-day review window
- ✅ Email notifications and CloudWatch alarms
- ✅ Starts in dry-run mode for safety

## Covered Database Services

| Service | Coverage Type |
|---------|---------------|
| **RDS** | All instance types |
| **Aurora** | Serverless v2 and provisioned |
| **DynamoDB** | On-demand and provisioned |
| **ElastiCache** | Valkey and Redis |
| **DocumentDB, Neptune** | All instances |
| **Keyspaces, Timestream, DMS** | All usage |

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

```bash
aws lambda invoke \
  --function-name $(terraform output -raw scheduler_lambda_name) \
  --payload '{}' \
  response.json
```

Expected email: current Database SP coverage, recommended purchase, "DRY RUN" notice.

## Enabling Real Purchases

Edit `main.tf`:

```hcl
lambda_config = {
  scheduler = {
    dry_run = false
  }
}
```

Then `terraform apply` and monitor first cycle.

## Database SP Constraints

⚠️ **AWS-mandated constraints:**
- **Term:** 1-year only (no 3-year option)
- **Payment:** No Upfront only (no All/Partial Upfront)

These cannot be changed.

## Monitoring

```bash
# Scheduler logs
aws logs tail /aws/lambda/$(terraform output -raw scheduler_lambda_name) --follow

# SQS queue status
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

- Add Compute SP: `sp_plans.compute.enabled = true`
- AWS Organizations: Set per-Lambda `assume_role_arn` in `lambda_config`
- Increase `purchase_strategy.coverage_target_percent` as confidence grows

See [main README](../../README.md) for complete documentation.

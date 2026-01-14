# Single Account - Database Savings Plans Only

This example demonstrates Database Savings Plans automation for AWS database services:

- **Single AWS account** (no Organizations integration)
- **Database Savings Plans only** (RDS, Aurora, DynamoDB, ElastiCache, DocumentDB, Neptune, Keyspaces, Timestream, DMS)
- **AWS-mandated constraints** (1-year term, No Upfront payment)
- **Conservative coverage targets** (80% target, 90% cap)
- **Dry-run mode enabled** for safe initial deployment

## Features

✅ Automated Database Savings Plans purchasing
✅ Covers all eligible database services
✅ Conservative 5% monthly spend limit
✅ 3-day human review window
✅ Email notifications
✅ CloudWatch alarms for monitoring
✅ Starts in dry-run mode for safety

## Covered Database Services

Database Savings Plans automatically cover usage from:

| Service | Coverage Type |
|---------|---------------|
| **RDS** | All instance types |
| **Aurora** | Serverless v2 and provisioned |
| **DynamoDB** | On-demand and provisioned |
| **ElastiCache** | Valkey and Redis |
| **DocumentDB** | All instances |
| **Neptune** | All instances |
| **Amazon Keyspaces** | Cassandra-compatible |
| **Timestream** | Time series database |
| **DMS** | Database Migration Service |

## AWS Database SP Constraints

⚠️ **Important:** Database Savings Plans have fixed AWS constraints that cannot be changed:

- **Term:** Must be 1-year (cannot use 3-year)
- **Payment:** Must be No Upfront (cannot use All Upfront or Partial Upfront)
- **Discount:** Up to 35% for serverless, up to 20% for provisioned

These constraints are enforced by AWS and apply to all Database Savings Plans regardless of configuration.

## Architecture

This configuration deploys:

- **Scheduler Lambda** — Analyzes database usage monthly
- **Purchaser Lambda** — Executes approved purchases after review window
- **SQS Queue** — Holds purchase intents (review = 3 days)
- **SNS Topic** — Sends email notifications
- **CloudWatch Alarms** — Monitors Lambda errors and DLQ depth

## Prerequisites

1. **AWS Account** with appropriate permissions
2. **Terraform** >= 1.0
3. **AWS Provider** >= 5.0
4. **Email address** for SNS notifications
5. **Database workloads** running on supported services (RDS, Aurora, DynamoDB, etc.)

## Required IAM Permissions

The deploying user/role needs permissions to create:

- Lambda functions and execution roles
- SQS queues
- SNS topics and subscriptions
- EventBridge rules
- CloudWatch log groups and alarms
- IAM roles and policies

The Lambda execution role (created by the module) will have permissions for:

- `ce:GetSavingsPlansPurchaseRecommendation` (for Database SP type)
- `savingsplans:CreateSavingsPlan`
- `savingsplans:DescribeSavingsPlans`
- `sqs:SendMessage`, `sqs:ReceiveMessage`, `sqs:DeleteMessage`, `sqs:PurgeQueue`
- `sns:Publish`
- `logs:CreateLogGroup`, `logs:CreateLogStream`, `logs:PutLogEvents`

## Deployment Steps

### 1. Configure Variables

Update the `notification_emails` list in `main.tf`:

```hcl
notification_emails = [
  "your-email@example.com"  # Replace with your email
]
```

### 2. Initialize Terraform

```bash
terraform init
```

### 3. Review Plan

```bash
terraform plan
```

Expected resources: ~20-25 resources including Lambda functions, SQS queues, SNS topics, IAM roles, EventBridge rules, and CloudWatch alarms.

### 4. Deploy

```bash
terraform apply
```

### 5. Confirm SNS Subscription

After deployment:

1. Check your email for SNS subscription confirmation
2. Click the confirmation link
3. You'll receive notifications when the scheduler runs

## Testing the Deployment

### Dry-Run Mode (Default)

The module starts with `dry_run = true`:

- Scheduler runs monthly (1st at 8:00 AM UTC by default)
- Analyzes database usage and calculates recommendations
- **Sends email with recommendations**
- **Does NOT queue purchases**
- No actual Savings Plans purchased

### Manual Test Trigger

To test immediately without waiting for the schedule:

```bash
# Get the scheduler Lambda function name
terraform output scheduler_lambda_name

# Invoke the Lambda function manually
aws lambda invoke \
  --function-name $(terraform output -raw scheduler_lambda_name) \
  --payload '{}' \
  response.json

# Check the response
cat response.json
```

You should receive an email with:
- Current Database SP coverage percentage
- Recommended purchase amount
- Database services breakdown
- "DRY RUN" notice

## Enabling Real Purchases

Once you've validated the recommendations in dry-run mode:

### 1. Update Configuration

Edit `main.tf`:

```hcl
dry_run = false  # Enable actual purchases
```

### 2. Apply Changes

```bash
terraform apply
```

### 3. Monitor First Cycle

After enabling purchases:

1. Wait for next scheduler run (1st of month)
2. Review email with purchase recommendations
3. Check SQS queue for queued purchases:
   ```bash
   aws sqs get-queue-attributes \
     --queue-url $(terraform output -raw queue_url) \
     --attribute-names ApproximateNumberOfMessages
   ```
4. To cancel a purchase, delete the message from the queue before the purchaser runs (4th of month)
5. Purchaser executes approved purchases on the 4th

## Configuration Options

### Coverage Targets

Adjust risk tolerance by modifying coverage percentages:

```hcl
coverage_target_percent = 80  # Lower = more conservative
max_coverage_cap        = 90  # Hard ceiling
```

### Purchase Limits

Control spending velocity:

```hcl
max_purchase_percent = 5  # Lower = slower commitment growth
```

### Review Window

Adjust time between scheduling and purchasing:

```hcl
scheduler_schedule = "cron(0 8 1 * ? *)"   # 1st of month
purchaser_schedule = "cron(0 8 10 * ? *)"  # 10th of month (9-day window)
```

## Monitoring

### CloudWatch Logs

View Lambda execution logs:

```bash
# Scheduler logs
aws logs tail /aws/lambda/$(terraform output -raw scheduler_lambda_name) --follow

# Purchaser logs
aws logs tail /aws/lambda/$(terraform output -raw purchaser_lambda_name) --follow
```

### CloudWatch Alarms

The module creates alarms for:

- **Lambda Errors** — Triggers on any Lambda function error
- **Dead Letter Queue** — Triggers when messages fail processing

Alarms publish to the same SNS topic used for notifications.

### SQS Queue Monitoring

Check queued purchases:

```bash
# Number of messages in queue
aws sqs get-queue-attributes \
  --queue-url $(terraform output -raw queue_url) \
  --attribute-names ApproximateNumberOfMessages

# View messages (without deleting)
aws sqs receive-message \
  --queue-url $(terraform output -raw queue_url) \
  --max-number-of-messages 10
```

### Checking Database SP Coverage

View current Database Savings Plans coverage:

```bash
# Get coverage for current month
aws ce get-savings-plans-coverage \
  --time-period Start=$(date -d "$(date +%Y-%m-01)" +%Y-%m-%d),End=$(date +%Y-%m-%d) \
  --granularity MONTHLY \
  --filter file://<(echo '{"Dimensions":{"Key":"SAVINGS_PLAN_TYPE","Values":["DATABASE"]}}')
```

## Canceling Purchases

To cancel a scheduled purchase before execution:

1. Navigate to AWS Console → SQS
2. Open queue: `sp-autopilot-purchase-intents`
3. Select "Send and receive messages"
4. Poll for messages
5. Delete unwanted purchase messages
6. Purchaser will skip deleted messages

## Cost Estimate

### Infrastructure Costs

Monthly AWS infrastructure costs (approximate):

- **Lambda** — ~$0.20 (2 executions/month, minimal runtime)
- **SQS** — ~$0.01 (minimal message volume)
- **SNS** — $0.00 (free tier covers usage)
- **CloudWatch Logs** — ~$0.50 (log retention)
- **CloudWatch Alarms** — ~$0.20 (2 alarms)

**Total infrastructure: ~$1/month**

### Savings Plans Costs

Actual Savings Plans purchases depend on your database usage:

- `max_purchase_percent = 5` limits purchases to 5% of monthly on-demand spend
- Example: $5,000/month database spend → max $250/month in new SP commitments
- Savings range: 10-35% depending on service type

## Troubleshooting

### No Email Received

1. Check SNS subscription confirmation in email
2. Verify email in `notification_emails` list
3. Check spam folder

### Scheduler Not Running

1. Verify EventBridge rule is enabled:
   ```bash
   aws events list-rules --name-prefix sp-autopilot
   ```
2. Check Lambda execution role permissions
3. Review CloudWatch logs for errors

### Purchases Not Executing

1. Verify `dry_run = false` in configuration
2. Check SQS queue has messages between scheduler and purchaser runs
3. Ensure purchaser schedule is AFTER scheduler schedule
4. Review purchaser Lambda logs for errors

### No Recommendations Generated

If the scheduler finds no Database SP recommendations:

1. Verify you have eligible database workloads running (RDS, Aurora, DynamoDB, etc.)
2. Check that services have been running for at least `min_data_days` (default: 14 days)
3. Verify current coverage is below `coverage_target_percent`
4. Check CloudWatch logs for API errors

### Coverage Cap Exceeded

If purchases are blocked by coverage cap:

1. Check current coverage:
   ```bash
   aws ce get-savings-plans-coverage \
     --time-period Start=$(date -d "$(date +%Y-%m-01)" +%Y-%m-%d),End=$(date +%Y-%m-%d) \
     --filter file://<(echo '{"Dimensions":{"Key":"SAVINGS_PLAN_TYPE","Values":["DATABASE"]}}')
   ```
2. Adjust `max_coverage_cap` if appropriate
3. Review expiring plans (may be excluded from coverage calculation)

## Cleanup

To remove all resources:

```bash
terraform destroy
```

**Note:** This does NOT cancel existing Savings Plans commitments. Active Savings Plans will continue until their term expires.

## Next Steps

After validating this database-only setup, consider:

- **Add Compute SP** — Enable `enable_compute_sp = true` for EC2/Lambda/Fargate coverage
- **AWS Organizations** — Set `management_account_role_arn` for org-wide SPs
- **Increase Targets** — Raise `coverage_target_percent` as confidence grows
- **Optimize Coverage** — Monitor which database services benefit most from SPs

## Database-Specific Considerations

### When to Use Database SPs

Database Savings Plans are most effective for:

- **Steady-state workloads** — RDS/Aurora instances running 24/7
- **DynamoDB provisioned capacity** — Predictable read/write throughput
- **Production databases** — Long-running mission-critical databases
- **ElastiCache clusters** — Persistent caching layers

### When NOT to Use Database SPs

Consider on-demand pricing for:

- **Development/test databases** — Frequently stopped/started instances
- **Spiky workloads** — Highly variable usage patterns
- **Short-lived projects** — Databases with uncertain lifespan
- **Aurora Serverless v1** — Already cost-optimized for variable workloads

### Mixing with Reserved Instances

Database Savings Plans can complement Reserved Instances:

- **RI-first strategy** — Use existing RIs, fill gaps with Database SPs
- **SP-first strategy** — Use Database SPs for flexibility across services
- **Hybrid approach** — RIs for predictable workloads, SPs for dynamic coverage

AWS applies discounts in this order: Reserved Instances → Savings Plans → On-Demand

## Support

For issues or questions:

- Review CloudWatch logs for detailed error messages
- Check the [main module README](../../README.md) for detailed documentation
- Open an issue on the GitHub repository

---

**⚠️ Important:** Always start with `dry_run = true` and validate recommendations before enabling actual purchases. Database Savings Plans are 1-year commitments with no upfront discount, so ensure your workloads are stable before committing.

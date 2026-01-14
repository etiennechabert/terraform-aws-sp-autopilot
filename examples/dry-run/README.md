# Conservative Dry-Run Evaluation

This example demonstrates the **safest way to evaluate** the AWS Savings Plans Autopilot module before making any financial commitments:

- **100% risk-free** — Dry-run mode means ZERO purchases
- **Email-only reports** — Receive recommendations without any action
- **Ultra-conservative targets** — 60% coverage target, 70% cap
- **Perfect for evaluation** — Understand your usage and potential savings

## What is Dry-Run Mode?

When `dry_run = true`, the module operates in **evaluation-only mode**:

✅ **What It Does:**
- Analyzes your EC2, Lambda, and Fargate usage
- Fetches AWS Savings Plans recommendations
- Calculates how much to purchase to reach coverage targets
- Sends detailed email reports with recommendations
- Logs all analysis to CloudWatch

❌ **What It Doesn't Do:**
- No purchases queued to SQS
- No Savings Plans purchased
- No financial commitments made
- No changes to your AWS spend

**Bottom line:** You receive all the insights with zero risk.

## Use Cases

This example is perfect for:

1. **Initial Evaluation** — "Should we use Savings Plans automation?"
2. **Usage Analysis** — "What's our current coverage and usage patterns?"
3. **Savings Estimation** — "How much could we save?"
4. **Confidence Building** — "Does the module make sensible recommendations?"
5. **Stakeholder Buy-In** — "Let's review recommendations for 2-3 months first"

## Prerequisites

1. **AWS Account** with compute workloads (EC2, Lambda, or Fargate)
2. **Terraform** >= 1.0
3. **AWS Provider** >= 5.0
4. **Email address** for receiving evaluation reports

## Required IAM Permissions

The deploying user/role needs permissions to create:

- Lambda functions and execution roles
- SQS queues
- SNS topics and subscriptions
- EventBridge rules
- CloudWatch log groups and alarms
- IAM roles and policies

**Note:** In dry-run mode, the module NEVER calls `savingsplans:CreateSavingsPlan`.

## Deployment Steps

### 1. Configure Variables

Update the `notification_emails` list in `main.tf`:

```hcl
notification_emails = [
  "your-email@example.com"  # Replace with your email
]
```

### 2. Deploy

```bash
terraform init
terraform plan
terraform apply
```

### 3. Confirm SNS Subscription

After deployment:

1. Check your email for SNS subscription confirmation
2. Click the confirmation link
3. You'll receive evaluation reports when the scheduler runs

## Testing the Evaluation

### Manual Test Trigger

To test immediately without waiting for the schedule:

```bash
# Invoke the scheduler Lambda function manually
aws lambda invoke \
  --function-name $(terraform output -raw scheduler_lambda_name) \
  --payload '{}' \
  response.json

# Check the response
cat response.json
```

You should receive an email with:
- Current Compute SP coverage percentage
- Recommended purchase amount
- Breakdown by term (1-year vs 3-year)
- "DRY RUN" notice

## Understanding the Email Reports

### Example Email Structure

```
========================================
AWS SAVINGS PLANS RECOMMENDATION
DRY RUN MODE - NO PURCHASES WILL BE MADE
========================================

=== Compute Savings Plans ===
Current Coverage: 45.2%
Target Coverage: 60.0%
Coverage Gap: 14.8%

Current Monthly On-Demand Spend: $12,450.00
Current Hourly On-Demand Rate: $17.29/hour

Recommended Purchase: $2.56/hour
  - 3-Year Plans: $1.28/hour (50%)
  - 1-Year Plans: $1.28/hour (50%)

Maximum Allowed Purchase: $5.18/hour (3% of monthly spend)
Recommendation Status: Within limits ✓

Estimated Annual Savings: $8,200 - $13,400
  (Depends on term mix and actual usage patterns)

========================================
THIS IS A DRY RUN
No purchases have been queued or made.
Review these recommendations and adjust
configuration as needed.
========================================
```

### Key Metrics to Monitor

1. **Coverage Gap** — How far below target you are
2. **Recommended Purchase** — Hourly commitment suggested
3. **Current Coverage** — Your existing SP coverage
4. **Estimated Savings** — Potential annual savings

### Evaluation Recommendations

Run the evaluation for 2-3 monthly cycles before enabling purchases. Watch for:

✅ **Good Signs:**
- Recommendations are sensible relative to your spend
- Coverage gaps align with your usage patterns
- No dramatic month-to-month swings

⚠️ **Red Flags:**
- Recommendations vastly exceed your comfort level → Lower `max_purchase_percent`
- No recommendations despite known EC2/Lambda usage → Check IAM permissions
- Wildly varying recommendations → Usage may be too variable for automation

## Transitioning to Real Purchases

Once you're confident in the recommendations:

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
3. Check SQS queue for queued purchases (see [single-account-compute example](../single-account-compute/README.md#monitoring))
4. To cancel a purchase, delete the message from the queue before the purchaser runs
5. Purchaser executes approved purchases on the scheduled date

## Monitoring

View scheduler execution logs:

```bash
aws logs tail /aws/lambda/$(terraform output -raw scheduler_lambda_name) --follow
```

For detailed monitoring guidance, see the [single-account-compute example](../single-account-compute/README.md#monitoring).

## Troubleshooting

**No Email Received:** Check spam folder, verify SNS subscription confirmed, review CloudWatch logs.

**Email Says "No Action Needed":** Current coverage already exceeds target, or insufficient usage data.

**Lambda Errors:** Check IAM role has Cost Explorer access, ensure EC2/Lambda/Fargate usage exists.

For detailed troubleshooting, see the [main module README](../../README.md).

## Cleanup

To remove evaluation infrastructure:

```bash
terraform destroy
```

**Note:** In dry-run mode, no Savings Plans were created, so there are no commitments to worry about.

## Next Steps

After successful evaluation, consider:

- **Enable Purchases** — Set `dry_run = false` with conservative limits
- **Add Database SP** — Enable `enable_database_sp = true` for RDS/DynamoDB coverage
- **Increase Targets** — Gradually raise coverage goals as confidence grows
- **AWS Organizations** — Set `management_account_role_arn` for org-wide SPs

## Support

For issues or questions:

- Review CloudWatch logs for detailed execution traces
- Check the [main module README](../../README.md) for detailed documentation
- Compare your email reports to the expected format above

---

**💡 Pro Tip:** Run in dry-run mode for at least 2-3 monthly cycles before enabling purchases. This builds confidence and helps you understand your usage patterns.

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
- SQS queues (created but not used in dry-run)
- SNS topics and subscriptions
- EventBridge rules
- CloudWatch log groups and alarms
- IAM roles and policies

The Lambda execution role (created by the module) will have permissions for:

- `ce:GetSavingsPlansPurchaseRecommendation` — Read AWS recommendations
- `savingsplans:DescribeSavingsPlans` — Read current coverage
- `sqs:SendMessage`, `sqs:PurgeQueue` — (not used in dry-run)
- `sns:Publish` — Send email reports
- `logs:CreateLogGroup`, `logs:CreateLogStream`, `logs:PutLogEvents` — Logging

**Note:** In dry-run mode, the module NEVER calls `savingsplans:CreateSavingsPlan`.

## Deployment Steps

### 1. Configure Email Address

Update `notification_emails` in `main.tf`:

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

Expected resources: ~20-25 resources (Lambda, SQS, SNS, IAM, EventBridge, CloudWatch).

### 4. Deploy

```bash
terraform apply
```

### 5. Confirm SNS Subscription

After deployment:

1. Check your email for "AWS Notification - Subscription Confirmation"
2. Click the confirmation link
3. You're subscribed to evaluation reports

## Testing Immediately

Don't wait for the monthly schedule — trigger an evaluation now:

### Get Lambda Function Name

```bash
terraform output scheduler_lambda_name
```

### Invoke Scheduler Manually

```bash
aws lambda invoke \
  --function-name $(terraform output -raw scheduler_lambda_name) \
  --payload '{}' \
  response.json

cat response.json
```

### Expected Result

Within 1-2 minutes, you'll receive an email with:

- **Subject:** "AWS Savings Plans Recommendation - DRY RUN"
- **Current Coverage:** Your Compute SP coverage percentage
- **Target Coverage:** 60% (configured in this example)
- **Coverage Gap:** How far below target you are
- **Recommended Purchase:** Suggested $/hour commitment
- **Term Breakdown:** Split between 1-year and 3-year plans
- **Financial Impact:** Estimated monthly spend vs savings

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
   - Large gap (>20%) → Significant savings opportunity
   - Small gap (<5%) → Close to target, minimal action needed
   - Negative gap → Already above target (no action)

2. **Recommended Purchase** — Hourly commitment suggested
   - Compare to your monthly spend
   - Verify it's within your `max_purchase_percent` limit
   - Check if term mix matches your preferences

3. **Current Coverage** — Your existing SP coverage
   - 0-30% → Low coverage, high savings potential
   - 30-60% → Moderate coverage
   - 60%+ → Good coverage, diminishing returns

4. **Estimated Savings** — Potential annual savings
   - Savings range depends on service mix (EC2 vs Lambda vs Fargate)
   - Higher percentages with longer terms and upfront payment

## What to Look For

### ✅ Good Signs

- Recommendations are sensible relative to your spend
- Coverage gaps align with your usage patterns
- Recommended purchases stay under `max_purchase_percent` limit
- No dramatic month-to-month swings in recommendations

### ⚠️ Red Flags

- Recommendations vastly exceed your comfort level → Lower `max_purchase_percent`
- Coverage already exceeds target → Check if `coverage_target_percent` is too high
- No recommendations despite known EC2/Lambda usage → Check IAM permissions
- Wildly varying recommendations → Usage may be too variable for aggressive automation

## Evaluation Period Recommendations

### Week 1: Initial Review
- Deploy with `dry_run = true`
- Review first email report
- Verify numbers make sense relative to your usage
- Check CloudWatch logs for any errors

### Month 1-2: Pattern Analysis
- Let scheduler run monthly (or trigger manually)
- Watch for consistency in recommendations
- Compare recommendations to actual usage trends
- Adjust `coverage_target_percent` if needed

### Month 3: Decision Point
- If recommendations are consistently sensible → Consider enabling purchases
- If recommendations seem off → Adjust configuration or investigate further
- If usage is too variable → May not be suitable for automation

## Adjusting Configuration

Based on evaluation results, you may want to tune:

### More Conservative

```hcl
coverage_target_percent = 50   # Lower target
max_coverage_cap        = 60   # Lower ceiling
max_purchase_percent    = 2    # Smaller purchases
min_data_days          = 30    # Require more data
```

### More Aggressive

```hcl
coverage_target_percent = 80   # Higher target
max_coverage_cap        = 90   # Higher ceiling
max_purchase_percent    = 10   # Larger purchases
compute_sp_term_mix = {
  three_year = 0.70            # More 3-year for higher discount
  one_year   = 0.30
}
compute_sp_payment_option = "ALL_UPFRONT"  # Maximum savings
```

### Add Database Coverage

```hcl
enable_database_sp = true  # Add RDS, DynamoDB, etc.
```

## Transitioning to Real Purchases

Once you're confident in the recommendations:

### 1. Update Configuration

Edit `main.tf`:

```hcl
dry_run = false  # Enable actual purchases
```

### 2. Consider Increasing Targets

If staying conservative:

```hcl
coverage_target_percent = 70   # Still conservative
max_coverage_cap        = 80
max_purchase_percent    = 5    # Slightly higher
```

### 3. Apply Changes

```bash
terraform apply
```

### 4. Monitor First Real Cycle

1. Scheduler runs (1st of month) → Queues purchases to SQS
2. Review email → Check if recommendations still make sense
3. **Review window (1st-8th)** → Cancel if needed by deleting SQS messages
4. Purchaser runs (8th of month) → Executes approved purchases
5. Verify purchases in AWS Console → Savings Plans dashboard

## Cost Estimate

### Infrastructure Costs (Dry-Run)

Monthly AWS costs for evaluation infrastructure:

- **Lambda** — ~$0.20 (scheduler runs only, minimal runtime)
- **SQS** — $0.00 (no messages in dry-run mode)
- **SNS** — $0.00 (free tier covers email notifications)
- **CloudWatch Logs** — ~$0.50 (log retention)
- **CloudWatch Alarms** — ~$0.20 (2 alarms)

**Total: ~$1/month for evaluation infrastructure**

### Savings Plans Costs

In dry-run mode: **$0** (no purchases made)

## Monitoring

### CloudWatch Logs

View scheduler execution logs:

```bash
aws logs tail /aws/lambda/$(terraform output -raw scheduler_lambda_name) --follow
```

Look for:
- Successful recommendation fetches
- Coverage calculations
- Email sending confirmations
- Any error messages

### Manual Testing Schedule

Recommended testing frequency during evaluation:

- **Week 1:** Manual trigger 2-3 times to verify functionality
- **Week 2-4:** Manual trigger weekly to see consistency
- **Month 2+:** Let monthly schedule run automatically

## Troubleshooting

### No Email Received

1. Check spam/junk folder
2. Verify SNS subscription confirmed (check email for confirmation link)
3. Check `notification_emails` list in `main.tf`
4. Review CloudWatch logs for SNS publish errors

### Email Says "No Action Needed"

This is normal if:
- Current coverage already exceeds `coverage_target_percent`
- Coverage gap is too small to meet `min_commitment_per_plan` threshold
- Insufficient usage data (less than `min_data_days`)

To force recommendations for testing:
- Lower `coverage_target_percent` to 30-40%
- Lower `min_commitment_per_plan` to `0.001`

### Lambda Errors in Logs

Common issues:
- **Insufficient permissions** → Check IAM role has Cost Explorer access
- **No usage data** → Ensure you have EC2/Lambda/Fargate usage
- **API throttling** → Rare, but can happen with frequent manual triggers

### Module Says "Insufficient Data"

This happens when:
- Your account hasn't had compute usage for `min_data_days`
- Cost Explorer data isn't yet available for new accounts (can take 24 hours)

Solution: Wait for usage data to accumulate, or lower `min_data_days`

## Cleanup

To remove evaluation infrastructure:

```bash
terraform destroy
```

**Note:** In dry-run mode, no Savings Plans were created, so there are no commitments to worry about.

## Next Steps

After successful evaluation, consider:

1. **Continue Dry-Run** — Run for 2-3 months to build confidence
2. **Enable Purchases** — Set `dry_run = false` with conservative limits
3. **Add Database SP** — Enable `enable_database_sp = true` for DB workloads
4. **Increase Targets** — Gradually raise coverage goals as comfort grows
5. **Adjust Term Mix** — Optimize based on workload stability
6. **AWS Organizations** — Set `management_account_role_arn` for org-wide SPs

## Comparison to Other Examples

| Example | Coverage Target | Max Purchase % | Dry-Run | Best For |
|---------|----------------|----------------|---------|----------|
| **dry-run** | 60% | 3% | ✅ Yes | Initial evaluation, building confidence |
| single-account-compute | 80% | 5% | ✅ Yes | Production-ready single account |
| database-only | 70% | 5% | ❌ No | Database-focused workloads |
| organizations | 90% | 10% | ❌ No | AWS Organizations deployments |

## Support

For issues or questions:

- Review CloudWatch logs for detailed execution traces
- Check the [main module README](../../README.md) for detailed documentation
- Compare your email reports to expected format above
- Verify IAM permissions include Cost Explorer access

---

**💡 Pro Tip:** Run in dry-run mode for at least 2-3 monthly cycles before enabling purchases. This builds confidence and helps you understand your usage patterns.

**⚠️ Remember:** This example is intentionally ultra-conservative. Once comfortable, you can increase targets for greater savings.

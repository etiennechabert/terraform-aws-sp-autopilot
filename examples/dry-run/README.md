# Conservative Dry-Run Evaluation

**Safest way to evaluate** the module before making any financial commitments: 100% risk-free with email-only reports.

## What is Dry-Run Mode?

When `lambda_config.scheduler.dry_run = true`, the module operates in **evaluation-only mode**:

✅ **What It Does:**
- Analyzes EC2, Lambda, and Fargate usage
- Fetches AWS Savings Plans recommendations
- Calculates purchases needed to reach targets
- Sends detailed email reports
- Logs all analysis to CloudWatch

❌ **What It Doesn't Do:**
- No purchases queued to SQS
- No Savings Plans purchased
- No financial commitments made
- No changes to AWS spend

**Bottom line:** All insights with zero risk.

## Use Cases

Perfect for:
1. **Initial Evaluation** — "Should we use Savings Plans automation?"
2. **Usage Analysis** — "What's our current coverage?"
3. **Savings Estimation** — "How much could we save?"
4. **Confidence Building** — "Does the module make sensible recommendations?"
5. **Stakeholder Buy-In** — "Let's review for 2-3 months first"

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

Check email for confirmation and click the link.

## Testing

### Manual Trigger

```bash
aws lambda invoke \
  --function-name $(terraform output -raw scheduler_lambda_name) \
  --payload '{}' \
  response.json
```

Expected email:
- Current Compute SP coverage percentage
- Recommended purchase amount
- Breakdown by term (1-year vs 3-year)
- "DRY RUN" notice

## Understanding Email Reports

### Key Metrics

1. **Coverage Gap** — How far below target
2. **Recommended Purchase** — Hourly commitment suggested
3. **Current Coverage** — Existing SP coverage
4. **Estimated Savings** — Potential annual savings

### Evaluation Recommendations

Run for 2-3 monthly cycles before enabling purchases. Watch for:

✅ **Good Signs:**
- Recommendations sensible relative to spend
- Coverage gaps align with usage patterns
- No dramatic month-to-month swings

⚠️ **Red Flags:**
- Recommendations vastly exceed comfort level → Lower `purchase_strategy.simple.max_purchase_percent`
- No recommendations despite known usage → Check IAM permissions
- Wildly varying recommendations → Usage too variable for automation

## Transitioning to Real Purchases

Once confident:

```hcl
lambda_config = {
  scheduler = {
    dry_run = false
  }
}
```

Then `terraform apply` and monitor first cycle (see [single-account-compute example](../single-account-compute/README.md#monitoring)).

## Cleanup

```bash
terraform destroy
```

**Note:** No Savings Plans created in dry-run mode, so no commitments to worry about.

## Next Steps

- Enable purchases with `lambda_config.scheduler.dry_run = false`
- Add Database SP: `sp_plans.database.enabled = true`
- Increase targets as confidence grows
- AWS Organizations: Set per-Lambda `assume_role_arn` in `lambda_config`

See [main README](../../README.md) for complete documentation.

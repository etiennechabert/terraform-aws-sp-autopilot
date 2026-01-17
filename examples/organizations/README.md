# AWS Organizations - Enterprise Deployment

Organization-wide Savings Plans automation with centralized purchasing and multi-stakeholder notifications.

## Features

- ✅ Organization-wide Compute and Database Savings Plans
- ✅ Centralized purchasing from management account
- ✅ 8% monthly spend limit, 5-day review window
- ✅ Multi-team email notifications
- ✅ CloudWatch alarms and cross-account role
- ✅ Starts in dry-run mode for safety

## Prerequisites

### 1. AWS Organization

- Active AWS Organization with consolidated billing
- At least one member account with eligible workloads
- Management account accessible for role creation

### 2. IAM Roles in Management Account

Create two roles for least privilege access:

#### Read-Only Role (Scheduler and Reporter)

**Trust Policy:**

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {
      "AWS": [
        "arn:aws:iam::DELEGATED_ACCOUNT_ID:role/sp-autopilot-scheduler-role",
        "arn:aws:iam::DELEGATED_ACCOUNT_ID:role/sp-autopilot-reporter-role"
      ]
    },
    "Action": "sts:AssumeRole"
  }]
}
```

**Permissions Policy:**

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": [
      "ce:GetSavingsPlansPurchaseRecommendation",
      "ce:GetSavingsPlansCoverage",
      "ce:GetSavingsPlansUtilization",
      "savingsplans:DescribeSavingsPlans"
    ],
    "Resource": "*"
  }]
}
```

#### Purchaser Role (Write Permissions)

**Trust Policy:**

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {
      "AWS": "arn:aws:iam::DELEGATED_ACCOUNT_ID:role/sp-autopilot-purchaser-role"
    },
    "Action": "sts:AssumeRole"
  }]
}
```

**Permissions Policy:**

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": [
      "savingsplans:CreateSavingsPlan",
      "savingsplans:DescribeSavingsPlans",
      "ce:GetSavingsPlansCoverage"
    ],
    "Resource": "*"
  }]
}
```

**Create via AWS CLI:**

```bash
# In management account

# 1. Create Read-Only Role
cat > readonly-trust.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {
      "AWS": [
        "arn:aws:iam::DELEGATED_ACCOUNT_ID:role/sp-autopilot-scheduler-role",
        "arn:aws:iam::DELEGATED_ACCOUNT_ID:role/sp-autopilot-reporter-role"
      ]
    },
    "Action": "sts:AssumeRole"
  }]
}
EOF

cat > readonly-permissions.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": [
      "ce:GetSavingsPlansPurchaseRecommendation",
      "ce:GetSavingsPlansCoverage",
      "ce:GetSavingsPlansUtilization",
      "savingsplans:DescribeSavingsPlans"
    ],
    "Resource": "*"
  }]
}
EOF

aws iam create-role \
  --role-name SavingsPlansReadOnlyRole \
  --assume-role-policy-document file://readonly-trust.json

aws iam put-role-policy \
  --role-name SavingsPlansReadOnlyRole \
  --policy-name ReadOnlyPermissions \
  --policy-document file://readonly-permissions.json

# 2. Create Purchaser Role
cat > purchaser-trust.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {
      "AWS": "arn:aws:iam::DELEGATED_ACCOUNT_ID:role/sp-autopilot-purchaser-role"
    },
    "Action": "sts:AssumeRole"
  }]
}
EOF

cat > purchaser-permissions.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": [
      "savingsplans:CreateSavingsPlan",
      "savingsplans:DescribeSavingsPlans",
      "ce:GetSavingsPlansCoverage"
    ],
    "Resource": "*"
  }]
}
EOF

aws iam create-role \
  --role-name SavingsPlansPurchaserRole \
  --assume-role-policy-document file://purchaser-trust.json

aws iam put-role-policy \
  --role-name SavingsPlansPurchaserRole \
  --policy-name PurchaserPermissions \
  --policy-document file://purchaser-permissions.json

# Get role ARNs for Terraform
aws iam get-role --role-name SavingsPlansReadOnlyRole --query 'Role.Arn' --output text
aws iam get-role --role-name SavingsPlansPurchaserRole --query 'Role.Arn' --output text
```

## Deployment

### 1. Configure

Update `main.tf`:

```hcl
lambda_config = {
  scheduler = {
    assume_role_arn = "arn:aws:iam::123456789012:role/SavingsPlansReadOnlyRole"
  }
  purchaser = {
    assume_role_arn = "arn:aws:iam::123456789012:role/SavingsPlansPurchaserRole"
  }
  reporter = {
    assume_role_arn = "arn:aws:iam::123456789012:role/SavingsPlansReadOnlyRole"
  }
}

notifications = {
  emails = [
    "finops@your-company.com",
    "cloud-governance@your-company.com",
    "aws-admins@your-company.com"
  ]
}

purchase_strategy = {
  coverage_target_percent = 85
  max_coverage_cap        = 95
  simple = {
    max_purchase_percent = 8
  }
}
```

### 2. Deploy

```bash
terraform init
terraform plan
terraform apply
```

### 3. Confirm SNS Subscriptions

All email recipients receive confirmation emails. Each must click their link.

## Testing

### Dry-Run Mode (Default)

```bash
aws lambda invoke \
  --function-name $(terraform output -raw scheduler_lambda_name) \
  --payload '{}' \
  response.json
```

Expected email:
- Org-wide Compute SP coverage
- Org-wide Database SP coverage
- Recommended purchases for each type
- "DRY RUN" notice

### Verify Cross-Account Access

Check Lambda logs for successful role assumption:

```bash
aws logs tail /aws/lambda/$(terraform output -raw scheduler_lambda_name) --follow
```

Look for: `Successfully assumed role in management account`

## Enabling Real Purchases

### 1. Update Configuration

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
1. Wait for scheduler run (1st of month)
2. Review email (sent to all recipients)
3. Check SQS queue for queued purchases
4. **IMPORTANT:** During 5-day review window, any stakeholder can delete messages to cancel purchases
5. Purchaser executes approved purchases on 6th
6. Verify new SPs in AWS Cost Management console

## Configuration Options

### Coverage Targets

```hcl
purchase_strategy = {
  coverage_target_percent = 85  # Higher for stable orgs
  max_coverage_cap        = 95  # Hard ceiling
  simple = {
    max_purchase_percent = 8  # % of monthly on-demand spend
  }
}
```

### Review Window

```hcl
scheduler = {
  scheduler = "cron(0 8 1 * ? *)"   # 1st of month
  purchaser = "cron(0 8 10 * ? *)"  # 10th = 9-day window
}
```

## Monitoring

### CloudWatch Logs

```bash
# Check role assumption and API calls
aws logs tail /aws/lambda/$(terraform output -raw scheduler_lambda_name) --follow
```

### Organization-Wide Coverage

```bash
# Compute SP coverage
aws ce get-savings-plans-coverage \
  --time-period Start=2024-01-01,End=2024-01-31 \
  --granularity MONTHLY \
  --filter '{"Dimensions":{"Key":"SAVINGS_PLAN_TYPE","Values":["COMPUTE_SP"]}}'
```

### Active Savings Plans

```bash
aws savingsplans describe-savings-plans --filters name=scope,values=organization
```

## Canceling Purchases

**Best Practice:** Establish review process where FinOps team checks queue between 1st and 6th of each month.

**Via AWS Console:**
1. SQS → `sp-autopilot-purchase-intents`
2. Send and receive messages
3. Review and delete unwanted purchases

**Via AWS CLI:**

```bash
# View messages
aws sqs receive-message \
  --queue-url $(terraform output -raw queue_url) \
  --max-number-of-messages 10

# Delete specific message
aws sqs delete-message \
  --queue-url $(terraform output -raw queue_url) \
  --receipt-handle "RECEIPT_HANDLE"
```

## Multi-Account Considerations

- **Member accounts:** SPs automatically benefit all linked accounts
- **Cost allocation:** SP costs appear in management account; use Cost Allocation Tags for chargeback
- **Account isolation:** Not supported; org-level SPs apply to all member accounts

## Cleanup

```bash
terraform destroy
```

**⚠️ IMPORTANT:** Does NOT cancel existing Savings Plans. Active org-level Savings Plans continue until terms expire.

View active commitments:

```bash
aws savingsplans describe-savings-plans --filters name=scope,values=organization
```

## Next Steps

- Optimize coverage targets based on usage patterns
- Fine-tune term mix in `sp_plans.compute`
- Implement cost allocation tags for chargeback
- Create dashboards for SP coverage trends
- Formalize multi-team review procedures

See [main README](../../README.md) for complete documentation.

---

**⚠️ Important:**
- Start with `lambda_config.scheduler.dry_run = true` and validate org-wide recommendations
- Coordinate with FinOps, governance, and finance teams before enabling
- Establish review process for purchase queue during review window
- Org-level SPs automatically benefit all member accounts

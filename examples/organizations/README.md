# AWS Organizations - Enterprise Deployment

This example demonstrates deploying AWS Savings Plans automation across an AWS Organization:

- **Organization-wide Savings Plans** — Centralized purchasing for all member accounts
- **Both Compute and Database SPs** — Comprehensive coverage across EC2, Lambda, Fargate, RDS, DynamoDB, etc.
- **Production-grade targets** — 85% coverage target with 95% cap
- **Multi-stakeholder notifications** — FinOps, governance, and admin teams
- **Extended review window** — 5 days for organization-level changes

## Features

✅ Organization-wide Compute and Database Savings Plans
✅ Centralized purchasing from management account
✅ 8% monthly spend limit for controlled growth
✅ 5-day human review window
✅ Multi-team email notifications
✅ CloudWatch alarms for monitoring
✅ Starts in dry-run mode for safety

## Architecture

This configuration deploys:

- **Scheduler Lambda** — Analyzes org-wide usage monthly (Compute + Database)
- **Purchaser Lambda** — Executes approved purchases after review window
- **SQS Queue** — Holds purchase intents (review = 5 days)
- **SNS Topic** — Sends email notifications to multiple stakeholders
- **CloudWatch Alarms** — Monitors Lambda errors and DLQ depth
- **Cross-Account Role** — Assumes role in management account for org-wide access

## AWS Organizations Setup

### Organization Structure

This module should be deployed in one of these accounts:

1. **Management Account** (recommended for smaller orgs)
   - Direct access to organization-level Cost Explorer and Savings Plans APIs
   - No cross-account role assumption needed (set `management_account_role_arn = null`)

2. **Delegated Administrator Account** (recommended for larger orgs)
   - Deploy infrastructure in a dedicated FinOps/governance account
   - Use `management_account_role_arn` to assume role in management account
   - Better separation of concerns and security

### Why Organization-Level SPs?

Organization-level Savings Plans provide benefits across all linked accounts:

- **Automatic sharing** — SPs automatically apply to eligible usage in any member account
- **Centralized management** — One place to view and purchase all SPs
- **Better pricing** — Aggregate org-wide usage for more accurate recommendations
- **Simplified governance** — Central FinOps team controls all SP purchasing

## Prerequisites

### 1. AWS Organization

- Active AWS Organization with consolidated billing enabled
- At least one member account with eligible workloads
- Management account accessible for role creation

### 2. IAM Role in Management Account

Create a role in the **management account** that the Lambda functions can assume:

**Role Name:** `SavingsPlansAutomationRole` (customizable)

**Trust Policy:**

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::DELEGATED_ACCOUNT_ID:root"
      },
      "Action": "sts:AssumeRole",
      "Condition": {
        "StringEquals": {
          "sts:ExternalId": "savings-plans-automation"
        }
      }
    }
  ]
}
```

**Permissions Policy:**

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ce:GetSavingsPlansPurchaseRecommendation",
        "ce:GetSavingsPlansCoverage"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "savingsplans:CreateSavingsPlan",
        "savingsplans:DescribeSavingsPlans"
      ],
      "Resource": "*"
    }
  ]
}
```

### 3. Terraform Requirements

- **Terraform** >= 1.0
- **AWS Provider** >= 5.0
- Credentials for the delegated administrator account (or management account)

### 4. Email Addresses

Email addresses for:
- FinOps team
- Cloud governance team
- AWS administrators

## Deployment Steps

### 1. Create IAM Role in Management Account

Using AWS CLI in the **management account**:

```bash
# Create trust policy file
cat > trust-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::DELEGATED_ACCOUNT_ID:root"
      },
      "Action": "sts:AssumeRole",
      "Condition": {
        "StringEquals": {
          "sts:ExternalId": "savings-plans-automation"
        }
      }
    }
  ]
}
EOF

# Create permissions policy file
cat > permissions-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ce:GetSavingsPlansPurchaseRecommendation",
        "ce:GetSavingsPlansCoverage"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "savingsplans:CreateSavingsPlan",
        "savingsplans:DescribeSavingsPlans"
      ],
      "Resource": "*"
    }
  ]
}
EOF

# Create the role
aws iam create-role \
  --role-name SavingsPlansAutomationRole \
  --assume-role-policy-document file://trust-policy.json

# Attach inline policy
aws iam put-role-policy \
  --role-name SavingsPlansAutomationRole \
  --policy-name SavingsPlansPermissions \
  --policy-document file://permissions-policy.json

# Get the role ARN (you'll need this for Terraform)
aws iam get-role --role-name SavingsPlansAutomationRole --query 'Role.Arn' --output text
```

### 2. Configure Terraform Variables

Update `main.tf` with your organization's details:

```hcl
# Update with your management account role ARN
management_account_role_arn = "arn:aws:iam::123456789012:role/SavingsPlansAutomationRole"

# Update with your notification emails
notification_emails = [
  "finops@your-company.com",
  "cloud-governance@your-company.com",
  "aws-admins@your-company.com"
]

# Adjust coverage targets based on your org's risk tolerance
coverage_target_percent = 85  # Your target
max_coverage_cap        = 95  # Your hard cap
```

### 3. Initialize Terraform

From the **delegated administrator account** (or management account if deploying there):

```bash
terraform init
```

### 4. Review Plan

```bash
terraform plan
```

Expected resources: ~20-25 resources including Lambda functions, SQS queues, SNS topics, IAM roles, EventBridge rules, and CloudWatch alarms.

### 5. Deploy

```bash
terraform apply
```

### 6. Confirm SNS Subscriptions

After deployment, each email address in `notification_emails` will receive a confirmation email:

1. Check inboxes for all notification recipients
2. Click confirmation links
3. All recipients will receive notifications when the scheduler runs

## Testing the Deployment

### Dry-Run Mode (Default)

The module starts with `dry_run = true`:

- Scheduler runs monthly (1st at 8:00 AM UTC by default)
- Analyzes org-wide usage for both Compute and Database SPs
- Assumes role in management account to fetch recommendations
- **Sends email with organization-wide recommendations**
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
- Current Compute SP coverage percentage (org-wide)
- Current Database SP coverage percentage (org-wide)
- Recommended purchase amounts for each SP type
- Breakdown by term (1-year vs 3-year for Compute, 1-year for Database)
- "DRY RUN" notice

### Verify Cross-Account Access

Check Lambda logs to confirm role assumption is working:

```bash
aws logs tail /aws/lambda/$(terraform output -raw scheduler_lambda_name) --follow
```

Look for log entries indicating successful role assumption:
```
Assuming role: arn:aws:iam::123456789012:role/SavingsPlansAutomationRole
Successfully assumed role in management account
```

## Enabling Real Purchases

Once you've validated the recommendations in dry-run mode:

### 1. Review with Stakeholders

Organization-level purchases affect all accounts. Before enabling:

1. Share dry-run email results with FinOps, governance, and finance teams
2. Confirm coverage targets align with organizational goals
3. Verify purchase limits (`max_purchase_percent = 8`) are acceptable
4. Ensure review window (5 days) provides adequate time for oversight

### 2. Update Configuration

Edit `main.tf`:

```hcl
dry_run = false  # Enable actual purchases
```

### 3. Apply Changes

```bash
terraform apply
```

### 4. Monitor First Cycle

After enabling purchases:

1. Wait for next scheduler run (1st of month)
2. Review email with purchase recommendations (sent to all recipients)
3. Check SQS queue for queued purchases:
   ```bash
   aws sqs get-queue-attributes \
     --queue-url $(terraform output -raw queue_url) \
     --attribute-names ApproximateNumberOfMessages
   ```
4. **IMPORTANT:** During the 5-day review window, any stakeholder can delete messages from the queue to cancel purchases
5. Purchaser executes approved purchases on the 6th
6. Verify new SPs in AWS Cost Management console

## Multi-Account Considerations

### Member Account Visibility

Savings Plans purchased at the organization level automatically benefit all member accounts:

- No configuration needed in member accounts
- SP discount automatically applies to eligible usage
- Member accounts see SP coverage in their Cost Explorer
- Central team maintains full control

### Account-Specific Exclusions

If certain accounts should not benefit from organization SPs:

1. This is not supported by AWS Savings Plans
2. Consider using separate SPs purchased within those accounts
3. Contact AWS support for advanced scenarios

### Cost Allocation

Organization-level SP costs appear in the management account:

- Use AWS Cost Allocation Tags for chargeback/showback
- Configure cost allocation in Billing console
- Consider AWS Cost Categories for department/team allocation

## Monitoring

### CloudWatch Logs

View Lambda execution logs:

```bash
# Scheduler logs (check for role assumption and API calls)
aws logs tail /aws/lambda/$(terraform output -raw scheduler_lambda_name) --follow

# Purchaser logs (check for purchase execution)
aws logs tail /aws/lambda/$(terraform output -raw purchaser_lambda_name) --follow
```

### CloudWatch Alarms

The module creates alarms for:

- **Lambda Errors** — Triggers on any Lambda function error (including role assumption failures)
- **Dead Letter Queue** — Triggers when messages fail processing

Alarms publish to the SNS topic shared with notifications.

### Organization-Wide Coverage Tracking

Monitor Savings Plans coverage across the organization:

```bash
# Compute SP coverage
aws ce get-savings-plans-coverage \
  --time-period Start=2024-01-01,End=2024-01-31 \
  --granularity MONTHLY \
  --filter '{"Dimensions":{"Key":"SAVINGS_PLAN_TYPE","Values":["COMPUTE_SP"]}}'

# Database SP coverage
aws ce get-savings-plans-coverage \
  --time-period Start=2024-01-01,End=2024-01-31 \
  --granularity MONTHLY \
  --filter '{"Dimensions":{"Key":"SAVINGS_PLAN_TYPE","Values":["DATABASE_SP"]}}'
```

### Active Savings Plans

List all organization-level Savings Plans:

```bash
aws savingsplans describe-savings-plans \
  --filters name=scope,values=organization
```

## Canceling Purchases

To cancel a scheduled purchase before execution:

### Via AWS Console

1. Navigate to AWS Console → SQS
2. Open queue: `sp-autopilot-purchase-intents`
3. Select "Send and receive messages"
4. Poll for messages
5. Review purchase details in message body
6. Delete unwanted purchase messages

### Via AWS CLI

```bash
# Receive messages from queue
aws sqs receive-message \
  --queue-url $(terraform output -raw queue_url) \
  --max-number-of-messages 10 \
  --visibility-timeout 0

# Delete specific message (use ReceiptHandle from above)
aws sqs delete-message \
  --queue-url $(terraform output -raw queue_url) \
  --receipt-handle "RECEIPT_HANDLE_HERE"
```

**Best Practice:** Establish a review process where FinOps team checks the queue between the 1st and 6th of each month.

## Configuration Options

### Coverage Targets

Adjust for organization size and risk tolerance:

```hcl
coverage_target_percent = 85  # Higher for stable orgs, lower for growing orgs
max_coverage_cap        = 95  # Hard ceiling to maintain flexibility
```

### Purchase Limits

Control org-wide spending velocity:

```hcl
max_purchase_percent = 8  # Percentage of monthly on-demand spend
# Lower for cautious approach, higher for aggressive savings
```

### Review Window

Adjust time between scheduling and purchasing:

```hcl
scheduler_schedule = "cron(0 8 1 * ? *)"   # 1st of month
purchaser_schedule = "cron(0 8 10 * ? *)"  # 10th of month (9-day window)
# Longer window for organizations with more stakeholders
```

### SP Type Mix

Enable/disable SP types based on your workloads:

```hcl
enable_compute_sp  = true   # EC2, Lambda, Fargate
enable_database_sp = true   # RDS, DynamoDB, etc.

# Or disable one if not applicable:
enable_compute_sp  = true
enable_database_sp = false  # No database workloads in org
```

## Cost Estimate

### Infrastructure Costs

Monthly AWS infrastructure costs (approximate):

- **Lambda** — ~$0.20 (2 executions/month, minimal runtime)
- **SQS** — ~$0.01 (minimal message volume)
- **SNS** — ~$0.10 (multiple subscribers, still within free tier)
- **CloudWatch Logs** — ~$0.50 (log retention)
- **CloudWatch Alarms** — ~$0.20 (2 alarms)

**Total infrastructure: ~$1/month**

### Savings Plans Costs

Actual Savings Plans purchases depend on organization-wide usage:

- `max_purchase_percent = 8` limits purchases to 8% of monthly org on-demand spend
- Example: $100,000/month org-wide on-demand → max $8,000/month in new SP commitments
- Typical savings: 10-66% depending on services and terms
- ROI typically positive within 1-2 months

## Troubleshooting

### Role Assumption Failures

If Lambda cannot assume the management account role:

1. Verify role exists in management account:
   ```bash
   aws iam get-role --role-name SavingsPlansAutomationRole
   ```
2. Check trust policy allows delegation from your account
3. Verify external ID is configured correctly (if using one)
4. Review Lambda CloudWatch logs for specific error messages

### No Organization-Level Recommendations

If Cost Explorer doesn't return organization-level data:

1. Verify consolidated billing is enabled
2. Check that Cost Explorer is enabled in management account
3. Ensure at least 14 days of usage data exists
4. Confirm role has `ce:GetSavingsPlansPurchaseRecommendation` permission

### Purchases Applied to Wrong Accounts

Organization-level SPs automatically apply to all accounts:

1. This is expected behavior - SPs share across all linked accounts
2. Use AWS Cost Categories for cost allocation
3. Consider account-level SPs for isolation (deploy module per account)

### Multi-Team Coordination

For large organizations with many stakeholders:

1. Set up a shared Slack/Teams channel for SP notifications
2. Use SNS to trigger webhooks instead of/in addition to email
3. Increase review window to allow time for distributed teams
4. Document escalation process for urgent cancellations

## Security Considerations

### Least Privilege

The cross-account role should have minimal permissions:

- Only Cost Explorer and Savings Plans actions
- No access to EC2, RDS, or other service APIs
- Consider adding condition keys to further restrict

### Audit Trail

All Savings Plans purchases are logged:

- Lambda CloudWatch logs contain full purchase details
- AWS CloudTrail logs all `CreateSavingsPlan` API calls
- SQS messages include idempotency tokens for tracking

### Access Control

Limit who can modify the infrastructure:

- Restrict Terraform state access
- Use separate IAM roles for deploying vs operating
- Enable MFA for management account access

## Cleanup

To remove all infrastructure:

```bash
terraform destroy
```

**⚠️ IMPORTANT:** This does NOT cancel existing Savings Plans commitments. Active organization-level Savings Plans will continue to apply until their terms expire.

To view active commitments after cleanup:

```bash
aws savingsplans describe-savings-plans --filters name=scope,values=organization
```

## Next Steps

After validating this organization-wide setup:

- **Optimize Coverage Targets** — Adjust `coverage_target_percent` based on actual usage patterns
- **Fine-Tune Term Mix** — Analyze workload stability and adjust `compute_sp_term_mix`
- **Implement Cost Allocation** — Set up cost allocation tags for chargeback
- **Automate Reporting** — Create dashboards for SP coverage and savings trends
- **Scale Review Process** — Formalize multi-team review procedures
- **Consider RI Automation** — Evaluate adding Reserved Instance automation for EC2

## Support

For issues or questions:

- Review CloudWatch logs for detailed error messages
- Check AWS CloudTrail for API call history
- Verify cross-account role permissions and trust policy
- Check the [main module README](../../README.md) for detailed documentation
- Open an issue on the GitHub repository

---

**⚠️ Important:**
- Always start with `dry_run = true` and validate organization-wide recommendations
- Coordinate with FinOps, governance, and finance teams before enabling purchases
- Establish a review process for the purchase queue during the review window
- Organization-level SPs automatically benefit all member accounts

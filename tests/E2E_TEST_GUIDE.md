# End-to-End Testing Guide: Slack Interactive Approvals

This guide explains how to perform end-to-end integration testing of the Slack Interactive Approval Actions feature.

## Overview

The E2E test verifies the complete workflow:

1. **Scheduler** queues a purchase intent and sends Slack notification with buttons
2. **Slack** displays notification with Approve/Reject buttons
3. **User** clicks Reject button in Slack
4. **API Gateway** receives the request and routes to Interactive Handler Lambda
5. **Interactive Handler** verifies signature, deletes SQS message, logs action
6. **Audit Log** records the action with user attribution in CloudWatch
7. **Purchaser** finds empty queue (purchase was rejected)

## Prerequisites

### 1. Infrastructure Deployment

Deploy the Terraform infrastructure to a development/test environment:

```bash
cd terraform/

# Initialize Terraform
terraform init

# Set required variables
export TF_VAR_slack_webhook_url="https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
export TF_VAR_slack_signing_secret="YOUR_SLACK_SIGNING_SECRET"

# Deploy
terraform apply
```

### 2. Slack App Configuration

1. **Create Slack App** (if not already created):
   - Go to https://api.slack.com/apps
   - Click "Create New App" → "From scratch"
   - Name: "Savings Plan Autopilot"
   - Select your workspace

2. **Get Signing Secret**:
   - Navigate to: Settings → Basic Information → App Credentials
   - Copy the "Signing Secret"
   - This is your `SLACK_SIGNING_SECRET`

3. **Configure Interactivity**:
   - Navigate to: Features → Interactivity & Shortcuts
   - Enable "Interactivity"
   - Set Request URL to the API Gateway endpoint from Terraform output:
     ```bash
     terraform output slack_interactive_endpoint
     ```
   - Save changes

4. **Install App to Workspace**:
   - Navigate to: Settings → Install App
   - Click "Install to Workspace"
   - Authorize the app

### 3. Environment Variables

Set up environment variables for the E2E test script:

```bash
# AWS Configuration
export AWS_REGION="us-east-1"
export AWS_PROFILE="your-profile"  # Optional

# From Terraform outputs
export QUEUE_URL=$(terraform output -raw queue_url)
export SLACK_INTERACTIVE_ENDPOINT=$(terraform output -raw slack_interactive_endpoint)

# Lambda function names (from your Terraform)
export SCHEDULER_LAMBDA_NAME="sp-autopilot-scheduler"
export PURCHASER_LAMBDA_NAME="sp-autopilot-purchaser"

# Slack configuration
export SLACK_SIGNING_SECRET="your_slack_signing_secret"
```

### 4. Python Dependencies

Install required Python packages:

```bash
pip install boto3 requests
```

## Running the E2E Test

### Option 1: Automated Test (Recommended)

Run the fully automated E2E test:

```bash
cd tests/
python e2e_slack_interactive.py --mode full
```

This will:
- Invoke scheduler to queue a purchase
- Verify the message is in the queue
- Simulate a Slack Reject button click
- Verify the message was deleted
- Check CloudWatch audit logs
- Verify purchaser finds empty queue

**Note:** Slack notification verification still requires manual check.

### Option 2: Manual Interactive Test

Run with manual verification prompts:

```bash
python e2e_slack_interactive.py --mode manual
```

This mode will:
- Prompt you to manually verify the Slack notification
- Wait for your confirmation before proceeding
- Useful for first-time testing or debugging

### Option 3: Verification Only

If you've already run the scheduler and received a Slack notification, you can verify just the deletion and logging:

```bash
python e2e_slack_interactive.py --mode verify-only
```

## Manual Testing (Alternative)

If you prefer to test manually without the script:

### Step 1: Deploy Infrastructure

```bash
terraform apply
```

### Step 2: Trigger Scheduler

Invoke the scheduler Lambda to create a test purchase:

```bash
aws lambda invoke \
  --function-name sp-autopilot-scheduler \
  --output json \
  response.json

cat response.json
```

### Step 3: Verify Slack Notification

1. Check your Slack workspace for a notification
2. Verify it contains:
   - Purchase details (commitment, sp_type, etc.)
   - A unique `client_token` identifier
   - Two buttons: "Approve ✓" (green) and "Reject ✗" (red)

### Step 4: Check SQS Queue

Verify the purchase intent is in the queue:

```bash
aws sqs receive-message \
  --queue-url $(terraform output -raw queue_url) \
  --max-number-of-messages 1
```

Save the `client_token` from the message body for later verification.

### Step 5: Click Reject Button

In Slack:
1. Click the "Reject ✗" button on the notification
2. The button should show a loading indicator
3. After ~1-2 seconds, you should see success feedback

### Step 6: Verify Message Deleted

Check that the queue is now empty:

```bash
aws sqs receive-message \
  --queue-url $(terraform output -raw queue_url) \
  --max-number-of-messages 10
```

Expected: No messages (or the message with your `client_token` is gone)

### Step 7: Verify Audit Log

Query CloudWatch Logs for the audit entry:

```bash
aws logs start-query \
  --log-group-name "/aws/lambda/interactive-handler" \
  --start-time $(date -u -d '5 minutes ago' +%s)000 \
  --end-time $(date -u +%s)000 \
  --query-string 'fields @timestamp, @message | filter event = "approval_action" | filter action = "reject" | sort @timestamp desc'
```

Get the query results:

```bash
aws logs get-query-results --query-id <query-id-from-previous-command>
```

Expected log entry structure:
```json
{
  "event": "approval_action",
  "action": "reject",
  "user_id": "U123ABC456",
  "user_name": "your.username",
  "purchase_intent_id": "test-token-123",
  "team_id": "T123ABC456",
  "timestamp": "2024-01-24T12:34:56.789Z"
}
```

### Step 8: Run Purchaser

Invoke the purchaser Lambda to verify it finds no purchases:

```bash
aws lambda invoke \
  --function-name sp-autopilot-purchaser \
  --output json \
  purchaser-response.json

cat purchaser-response.json
```

Expected: Response should indicate "No purchases to process"

## Verification Checklist

Use this checklist to confirm all aspects of the feature work correctly:

- [ ] **Infrastructure**
  - [ ] Terraform apply succeeds with no errors
  - [ ] API Gateway endpoint is created and accessible
  - [ ] Interactive handler Lambda is deployed
  - [ ] IAM roles and policies are created correctly
  - [ ] CloudWatch log group exists

- [ ] **Slack Configuration**
  - [ ] Slack app is created and installed to workspace
  - [ ] Signing secret is configured in Terraform
  - [ ] Interactive endpoint URL is configured in Slack app
  - [ ] App has necessary permissions

- [ ] **Notification Flow**
  - [ ] Scheduler sends Slack notification
  - [ ] Notification contains purchase details
  - [ ] Notification shows Approve and Reject buttons
  - [ ] Buttons have correct styling (green/red)
  - [ ] `client_token` is included in button value

- [ ] **Interactive Handler**
  - [ ] API Gateway receives POST requests from Slack
  - [ ] Signature verification accepts valid requests
  - [ ] Signature verification rejects invalid requests
  - [ ] Handler responds within 3 seconds
  - [ ] Handler returns 200 OK to Slack

- [ ] **Reject Action**
  - [ ] SQS message is deleted from queue
  - [ ] Queue deletion is idempotent (clicking twice doesn't error)
  - [ ] Audit log entry is created in CloudWatch
  - [ ] User attribution is captured (user_id, user_name, team_id)
  - [ ] Slack shows success feedback to user

- [ ] **Approve Action**
  - [ ] Clicking Approve logs the action
  - [ ] Purchase intent remains in queue (for purchaser to process)
  - [ ] Audit log captures approval action
  - [ ] Slack shows success feedback

- [ ] **Security**
  - [ ] Invalid signatures are rejected (401 Unauthorized)
  - [ ] Expired timestamps are rejected (>5 minutes old)
  - [ ] SLACK_SIGNING_SECRET is not logged or exposed
  - [ ] API Gateway has throttling configured
  - [ ] IAM role has least privilege permissions

- [ ] **Error Handling**
  - [ ] Missing SQS message is handled gracefully
  - [ ] SQS errors are caught and logged
  - [ ] Malformed Slack payloads return 400
  - [ ] All errors are logged to CloudWatch

- [ ] **Audit Trail**
  - [ ] CloudWatch Logs contain structured JSON
  - [ ] Logs include all required fields
  - [ ] CloudWatch Insights queries work
  - [ ] Timestamp is in ISO 8601 UTC format
  - [ ] Action type (approve/reject) is captured

## Troubleshooting

### Slack Returns "dispatch_failed"

**Cause:** API Gateway endpoint is not accessible or returning errors

**Solution:**
1. Check API Gateway is deployed: `terraform output slack_interactive_endpoint`
2. Test endpoint manually: `curl -X POST <endpoint>`
3. Check Lambda function logs: `aws logs tail /aws/lambda/interactive-handler --follow`

### Signature Verification Fails

**Cause:** Signing secret mismatch or timestamp issues

**Solution:**
1. Verify signing secret matches: Check Slack app settings vs. Terraform variable
2. Check system clock synchronization (timestamp validation requires accurate time)
3. Review Lambda logs for specific verification error

### Message Not Deleted from Queue

**Cause:** Handler can't find message with matching client_token

**Solution:**
1. Check button value includes correct client_token
2. Verify queue URL is correct in Lambda environment
3. Check SQS permissions in IAM role
4. Review Lambda logs for SQS API errors

### No Audit Logs in CloudWatch

**Cause:** Logs haven't propagated yet or log group doesn't exist

**Solution:**
1. Wait 1-2 minutes for logs to appear
2. Check log group exists: `aws logs describe-log-groups --log-group-name-prefix "/aws/lambda/interactive"`
3. Verify Lambda has CloudWatch Logs permissions
4. Check Lambda execution role has `logs:PutLogEvents`

### Test Script Fails on Prerequisites

**Cause:** Missing environment variables

**Solution:**
1. Review "Environment Variables" section above
2. Ensure all required variables are set: `env | grep -E "QUEUE_URL|SLACK|LAMBDA"`
3. Run `terraform output` to get correct values

## CloudWatch Insights Queries

Use these queries to analyze audit logs:

### All Approval Actions (Last Hour)

```
fields @timestamp, user_name, action, purchase_intent_id
| filter event = "approval_action"
| sort @timestamp desc
| limit 100
```

### Rejections by User

```
fields @timestamp, user_name, purchase_intent_id
| filter event = "approval_action" and action = "reject"
| sort @timestamp desc
```

### Actions for Specific Purchase

```
fields @timestamp, user_name, action, user_id, team_id
| filter event = "approval_action" and purchase_intent_id = "your-client-token"
| sort @timestamp desc
```

### Count Actions by User

```
filter event = "approval_action"
| stats count() by user_name, action
| sort count desc
```

## Success Criteria

The E2E test is considered successful when:

1. ✅ Scheduler queues purchase and sends Slack notification
2. ✅ Slack notification displays with Approve/Reject buttons
3. ✅ Clicking Reject sends request to API Gateway
4. ✅ API Gateway invokes Interactive Handler Lambda
5. ✅ Handler verifies signature successfully
6. ✅ Handler deletes message from SQS queue
7. ✅ Handler creates audit log in CloudWatch
8. ✅ Handler returns 200 OK to Slack within 3 seconds
9. ✅ Purchaser finds empty queue

## Next Steps

After successful E2E testing:

1. **Document Results**: Record test execution date, environment, and results
2. **Staging Deployment**: Deploy to staging environment for final validation
3. **Production Deployment**: Deploy to production with monitoring enabled
4. **Monitor**: Watch CloudWatch dashboards for first production approvals
5. **Train Users**: Provide documentation on using Slack buttons

## Support

For issues or questions:

- Check Lambda logs: `/aws/lambda/interactive-handler`
- Review Terraform plan: `terraform plan`
- Consult README.md for Slack app setup
- Check security scan results: `bandit -r lambda/interactive_handler/`

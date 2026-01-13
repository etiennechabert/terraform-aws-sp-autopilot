# Scheduler Lambda Integration Test - Dry Run Mode

This document describes the manual verification steps for testing the complete scheduler flow with dry-run mode enabled.

## Prerequisites

1. AWS environment with Cost Explorer access
2. IAM permissions for:
   - Cost Explorer (ce:GetSavingsPlansCoverage, ce:GetSavingsPlansPurchaseRecommendation)
   - Savings Plans (savingsplans:DescribeSavingsPlans)
   - SQS (sqs:SendMessage, sqs:PurgeQueue, sqs:GetQueueAttributes)
   - SNS (sns:Publish)
   - Lambda (lambda:InvokeFunction)
3. Deployed scheduler Lambda function
4. SQS queue created
5. SNS topic with email subscription

## Test Setup

### 1. Configure Lambda Environment Variables

Set the following environment variables on the Lambda function:

```bash
DRY_RUN=true
ENABLE_COMPUTE_SP=true
ENABLE_DATABASE_SP=false
COVERAGE_TARGET_PERCENT=90
MAX_PURCHASE_PERCENT=10
RENEWAL_WINDOW_DAYS=7
LOOKBACK_DAYS=30
MIN_DATA_DAYS=14
MIN_COMMITMENT_PER_PLAN=0.001
COMPUTE_SP_TERM_MIX={"three_year": 0.67, "one_year": 0.33}
COMPUTE_SP_PAYMENT_OPTION=ALL_UPFRONT
QUEUE_URL=<your-sqs-queue-url>
SNS_TOPIC_ARN=<your-sns-topic-arn>
TAGS={"Environment": "test", "ManagedBy": "AutoPilot"}
```

### 2. Verify SNS Email Subscription

Ensure you have confirmed the email subscription to the SNS topic:

```bash
aws sns list-subscriptions-by-topic --topic-arn <your-sns-topic-arn>
```

### 3. Check SQS Queue Status

Verify the queue is empty before starting:

```bash
aws sqs get-queue-attributes \
  --queue-url <your-sqs-queue-url> \
  --attribute-names ApproximateNumberOfMessages
```

Expected: `"ApproximateNumberOfMessages": "0"`

## Manual Invocation

### Option 1: Invoke via AWS Console

1. Navigate to Lambda → Functions → scheduler-function
2. Click "Test" tab
3. Create a test event with empty payload: `{}`
4. Click "Test" button
5. Review execution results

### Option 2: Invoke via AWS CLI

```bash
aws lambda invoke \
  --function-name scheduler-function \
  --payload '{}' \
  --log-type Tail \
  response.json

# View the response
cat response.json

# Decode and view execution logs
aws lambda invoke \
  --function-name scheduler-function \
  --payload '{}' \
  --log-type Tail \
  response.json | jq -r '.LogResult' | base64 --decode
```

### Option 3: Trigger via EventBridge (if configured)

```bash
# Create a test event
aws events put-events \
  --entries '[
    {
      "Source": "test",
      "DetailType": "Manual Test",
      "Detail": "{}"
    }
  ]'
```

## Verification Checklist

### ✅ 1. Email Notification Received

- [ ] Email received within 2 minutes of invocation
- [ ] Subject line: `[DRY RUN] Savings Plans Analysis - No Purchases Scheduled`
- [ ] Email body contains dry-run header: `***** DRY RUN MODE *****`
- [ ] Email clearly states: `*** NO PURCHASES WERE SCHEDULED ***`
- [ ] Email includes current coverage statistics
- [ ] Email includes target coverage percentage
- [ ] Email lists purchase plans that would be scheduled
- [ ] Email includes total estimated annual cost
- [ ] Email provides instructions to disable dry_run mode

### ✅ 2. No Messages in SQS Queue

Verify the queue remains empty after execution:

```bash
aws sqs get-queue-attributes \
  --queue-url <your-sqs-queue-url> \
  --attribute-names ApproximateNumberOfMessages
```

Expected result:
```json
{
  "Attributes": {
    "ApproximateNumberOfMessages": "0"
  }
}
```

- [ ] Queue has 0 messages (dry-run should NOT queue anything)

### ✅ 3. CloudWatch Logs - Successful Execution

View logs:

```bash
aws logs tail /aws/lambda/scheduler-function --follow
```

Check for the following log entries:

- [ ] `Starting Scheduler Lambda execution`
- [ ] `Configuration loaded: dry_run=True`
- [ ] `Purging queue: <queue-url>`
- [ ] `Queue purged successfully`

### ✅ 4. Coverage Calculation Logged

- [ ] `Calculating current coverage`
- [ ] `Found X active Savings Plans`
- [ ] Log shows filtering of plans expiring within renewal window (if applicable)
- [ ] `Valid plans after filtering: X`
- [ ] `Overall Savings Plans coverage: X.XX%`
- [ ] `Coverage calculated: {'compute': X.XX, 'database': X.XX}`
- [ ] `Current coverage - Compute: X.XX%, Database: X.XX%`

### ✅ 5. Recommendations Retrieved

- [ ] `Getting AWS recommendations`
- [ ] `Using lookback period: THIRTY_DAYS (config: 30 days)`
- [ ] `Fetching Compute Savings Plan recommendations` (if enabled)
- [ ] Either:
  - [ ] `Compute SP recommendation: $X.XXXX/hour (recommendation_id: ..., generated: ...)`
  - OR [ ] `No Compute SP recommendations available from AWS`
  - OR [ ] `Compute SP recommendation has insufficient data`
- [ ] `Recommendations retrieved: {...}`

### ✅ 6. Purchase Plans Calculated

- [ ] `Calculating purchase need`
- [ ] `Compute SP - Current: X.XX%, Target: X.XX%, Gap: X.XX%`
- [ ] Either:
  - [ ] `Compute SP purchase planned: $X.XXXX/hour (recommendation_id: ...)`
  - OR [ ] `Compute SP coverage already meets or exceeds target - no purchase needed`
  - OR [ ] `Compute SP has coverage gap but no AWS recommendation available`
- [ ] `Purchase need calculated: X plans`

### ✅ 7. Limits Applied

- [ ] `Applying purchase limits`
- [ ] `Total hourly commitment before limits: $X.XXXX/hour`
- [ ] `Applying X.X% purchase limit (scaling factor: X.XXXX)`
- [ ] `Purchase limits applied: X plans remain, $X.XXXX/hour total commitment`

### ✅ 8. Term Splitting

- [ ] `Splitting purchases by term`
- [ ] If compute SP planned:
  - [ ] `Splitting Compute SP: $X.XXXX/hour across 2 terms`
  - [ ] `Created THREE_YEAR plan: $X.XXXX/hour (67.0% of base commitment)`
  - [ ] `Created ONE_YEAR plan: $X.XXXX/hour (33.0% of base commitment)`
- [ ] `Term splitting complete: X plans -> X plans`

### ✅ 9. Dry-Run Email Sent

- [ ] `Dry run mode - sending email only, NOT queuing messages`
- [ ] `Sending dry run email`
- [ ] `Dry run email sent successfully to <sns-topic-arn>`

### ✅ 10. Successful Completion

- [ ] `Scheduler Lambda completed successfully`
- [ ] Lambda execution status: `Succeeded`
- [ ] No errors in CloudWatch Logs
- [ ] Return value includes:
  ```json
  {
    "statusCode": 200,
    "body": "{\"message\": \"Scheduler completed successfully\", \"dry_run\": true, \"purchases_planned\": X}"
  }
  ```

## Edge Cases to Test

### Test Case 1: No Coverage Gap

If current coverage already meets target:

- [ ] Log shows: `coverage already meets or exceeds target - no purchase needed`
- [ ] Email shows 0 purchase plans
- [ ] Email still sent with dry-run header
- [ ] No errors

### Test Case 2: No AWS Recommendations Available

If AWS has no recommendations:

- [ ] Log shows: `No Compute SP recommendations available from AWS`
- [ ] Email shows 0 purchase plans
- [ ] Email still sent with analysis results
- [ ] No errors

### Test Case 3: Insufficient Data

If AWS recommendation has insufficient data (< min_data_days):

- [ ] Log shows: `recommendation has insufficient data: X days < Y days minimum`
- [ ] Recommendation is skipped
- [ ] No errors

## Troubleshooting

### No Email Received

1. Check SNS subscription status:
   ```bash
   aws sns list-subscriptions-by-topic --topic-arn <your-sns-topic-arn>
   ```

2. Check CloudWatch Logs for SNS errors:
   ```bash
   aws logs tail /aws/lambda/scheduler-function --follow --filter "Failed to send"
   ```

3. Verify Lambda has `sns:Publish` permission

### Lambda Execution Failed

1. Check CloudWatch Logs for errors:
   ```bash
   aws logs tail /aws/lambda/scheduler-function --follow
   ```

2. Common issues:
   - Missing environment variables
   - IAM permission errors
   - Cost Explorer API access denied
   - Invalid queue URL or SNS topic ARN

### Queue Has Messages After Dry-Run

This indicates a bug - dry-run mode should NOT queue messages.

1. Purge the queue:
   ```bash
   aws sqs purge-queue --queue-url <your-sqs-queue-url>
   ```

2. Check the code logic in `handler.py` lines 76-82
3. Verify `DRY_RUN=true` in Lambda environment variables

## Cleanup

After testing:

1. Review and archive test emails
2. Check that queue is empty
3. Review CloudWatch Logs for any warnings
4. Document any issues found

## Next Steps

Once dry-run mode verification is complete:

1. Review all logs and email notifications
2. Validate coverage calculations are accurate
3. Validate purchase plans match expectations
4. If all tests pass, proceed to production testing with `DRY_RUN=false`

## Sign-Off

- [ ] All verification steps completed
- [ ] No errors encountered
- [ ] Email notifications formatted correctly
- [ ] No SQS messages queued (dry-run mode working)
- [ ] CloudWatch logs show expected flow
- [ ] Ready for production testing

**Verified by:** _______________
**Date:** _______________
**Notes:** _______________

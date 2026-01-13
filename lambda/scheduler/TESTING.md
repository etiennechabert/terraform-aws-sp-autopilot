# Scheduler Lambda Testing Guide

This document provides an overview of testing strategies for the Scheduler Lambda function.

## Test Artifacts

### Integration Testing (Dry-Run Mode)

The following test artifacts have been created for integration testing:

1. **integration_test_dry_run.md** - Comprehensive manual verification guide
   - Detailed prerequisites and setup instructions
   - 10-step verification checklist
   - Edge case testing scenarios
   - Troubleshooting guide
   - Sign-off checklist

2. **test_dry_run.sh** - Automated test script
   - Prerequisites verification (AWS CLI, credentials)
   - Lambda configuration validation
   - Automated Lambda invocation
   - SQS queue status verification
   - CloudWatch Logs retrieval
   - Manual verification checklist

## Running Integration Tests

### Quick Start

```bash
# Set your Lambda function name
export LAMBDA_FUNCTION_NAME=scheduler-function

# Run the automated test script
./lambda/scheduler/test_dry_run.sh
```

### Manual Testing

Follow the detailed guide in `integration_test_dry_run.md` for step-by-step manual verification.

## What Gets Tested

### 1. Dry-Run Mode Verification

The integration tests verify that dry-run mode works correctly:

- ✅ Email notification sent with dry-run header
- ✅ Subject line clearly marked `[DRY RUN]`
- ✅ Email body states "NO PURCHASES WERE SCHEDULED"
- ✅ No messages queued to SQS (dry-run mode prevents queuing)
- ✅ CloudWatch logs show successful execution

### 2. Functional Flow Verification

The tests verify the complete scheduler flow:

- ✅ **Configuration Loading** - Environment variables loaded correctly
- ✅ **Queue Purging** - Existing queue messages purged before analysis
- ✅ **Coverage Calculation** - Current Savings Plans coverage calculated
  - Active Savings Plans retrieved
  - Plans expiring within renewal window excluded
  - Coverage percentages calculated by SP type
- ✅ **Recommendations Retrieval** - AWS Cost Explorer recommendations fetched
  - Compute SP recommendations (if enabled)
  - Database SP recommendations (if enabled)
  - Minimum data days validation
- ✅ **Purchase Planning** - Purchase needs calculated based on coverage gap
  - Coverage gap calculated (target - current)
  - AWS recommendations mapped to purchase plans
  - Zero-commitment plans filtered out
- ✅ **Limits Application** - Purchase limits applied correctly
  - Total commitment calculated
  - Max purchase percent scaling applied
  - Minimum commitment threshold enforced
- ✅ **Term Splitting** - Compute SP split by term mix
  - Three-year term allocation
  - One-year term allocation
  - Database SP pass-through (no splitting)
- ✅ **Notification** - Email sent with analysis results
  - Dry-run email in dry-run mode
  - Scheduled email in production mode

### 3. Error Handling Verification

The tests verify error handling:

- ✅ Exceptions raised (no silent failures)
- ✅ Error email sent on failure
- ✅ CloudWatch logs contain error details
- ✅ Lambda execution fails visibly

## Test Environment Requirements

### AWS Permissions

The Lambda function requires the following IAM permissions for testing:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ce:GetSavingsPlansCoverage",
        "ce:GetSavingsPlansPurchaseRecommendation"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "savingsplans:DescribeSavingsPlans"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "sqs:SendMessage",
        "sqs:PurgeQueue",
        "sqs:GetQueueAttributes"
      ],
      "Resource": "arn:aws:sqs:*:*:savings-plans-queue"
    },
    {
      "Effect": "Allow",
      "Action": [
        "sns:Publish"
      ],
      "Resource": "arn:aws:sns:*:*:savings-plans-notifications"
    }
  ]
}
```

### Environment Variables

Configure the following environment variables for testing:

```bash
DRY_RUN=true                                    # Enable dry-run mode
ENABLE_COMPUTE_SP=true                          # Enable Compute SP analysis
ENABLE_DATABASE_SP=false                        # Enable Database SP analysis
COVERAGE_TARGET_PERCENT=90                      # Target coverage percentage
MAX_PURCHASE_PERCENT=10                         # Max purchase as % of spend
RENEWAL_WINDOW_DAYS=7                           # Days before expiry to exclude
LOOKBACK_DAYS=30                                # Days to analyze usage
MIN_DATA_DAYS=14                                # Minimum data requirement
MIN_COMMITMENT_PER_PLAN=0.001                   # Minimum hourly commitment
COMPUTE_SP_TERM_MIX={"three_year":0.67,"one_year":0.33}  # Term allocation
COMPUTE_SP_PAYMENT_OPTION=ALL_UPFRONT           # Payment option
QUEUE_URL=https://sqs.us-east-1.amazonaws.com/...  # SQS queue URL
SNS_TOPIC_ARN=arn:aws:sns:us-east-1:...:...    # SNS topic ARN
TAGS={"Environment":"test","ManagedBy":"AutoPilot"}  # Resource tags
```

## Test Scenarios

### Scenario 1: Coverage Gap Exists

**Setup:**
- Current coverage: 75%
- Target coverage: 90%
- AWS has recommendations available

**Expected Results:**
- Gap calculated: 15%
- Purchase plans created based on recommendations
- Limits applied according to max_purchase_percent
- Term splitting performed for Compute SP
- Dry-run email sent with purchase details
- No messages in SQS queue

### Scenario 2: Coverage Meets Target

**Setup:**
- Current coverage: 90%
- Target coverage: 90%

**Expected Results:**
- Gap calculated: 0%
- No purchase plans created
- Dry-run email sent showing 0 plans
- No messages in SQS queue

### Scenario 3: No AWS Recommendations

**Setup:**
- Coverage gap exists
- AWS returns no recommendations

**Expected Results:**
- Gap identified but no recommendations available
- No purchase plans created
- Dry-run email sent explaining no recommendations
- Log shows "has coverage gap but no AWS recommendation available"

### Scenario 4: Insufficient Data

**Setup:**
- AWS recommendation has < min_data_days of lookback

**Expected Results:**
- Recommendation rejected due to insufficient data
- Log shows "has insufficient data: X days < Y days minimum"
- No purchase plans created

## Troubleshooting

### Email Not Received

1. Check SNS subscription status
2. Verify email address is confirmed
3. Check CloudWatch Logs for SNS publish errors
4. Verify Lambda has `sns:Publish` permission

### Lambda Execution Failed

1. Check CloudWatch Logs for error details
2. Verify environment variables are set correctly
3. Verify IAM permissions
4. Check AWS service quotas (Cost Explorer, SQS, SNS)

### Queue Has Messages After Dry-Run

This indicates a bug - dry-run should NOT queue messages.

1. Purge the queue immediately
2. Verify `DRY_RUN=true` in Lambda configuration
3. Check code logic in handler.py lines 76-82
4. Review CloudWatch Logs for "Dry run mode" message

## Next Steps

After successful dry-run testing:

1. ✅ Review all logs and email notifications
2. ✅ Validate coverage calculations are accurate
3. ✅ Validate purchase plans match expectations
4. ✅ Document any issues or edge cases found
5. ⚠️ Disable dry-run mode: `DRY_RUN=false`
6. ⚠️ Run production test with small limits
7. ⚠️ Monitor first few actual purchases closely

## Production Testing Checklist

Before enabling in production:

- [ ] Dry-run tests passed completely
- [ ] Email notifications working correctly
- [ ] Coverage calculations validated
- [ ] Purchase limits set appropriately
- [ ] Term mix configured correctly
- [ ] SNS topic has correct subscriptions
- [ ] SQS queue configured with dead-letter queue
- [ ] CloudWatch alarms configured for errors
- [ ] Budget alerts configured
- [ ] Runbook created for incident response
- [ ] Team trained on cancellation procedure

## Support

For issues or questions:

1. Check CloudWatch Logs: `/aws/lambda/scheduler-function`
2. Review integration test documentation
3. Check troubleshooting guide
4. Review code comments in `handler.py`

# Lambda Error Patterns

Common AWS API errors across all Lambda functions and how they're handled.

## IAM Permission Errors

### InvalidClientTokenId

**Error:** `The security token included in the request is invalid.`

**Affected:** All Lambdas

**Cause:** IAM role doesn't exist or incorrect assume role ARN in cross-account setup.

**Fix:** Verify IAM role ARN in `lambda_config.{scheduler|purchaser|reporter}.assume_role_arn`.

### AccessDeniedException

**Error:** `User is not authorized to perform: {action}`

**Affected:** All Lambdas

**Cause:** Missing IAM permissions.

**Fix:** Add required permissions to Lambda execution role:
- **Scheduler**: `ce:GetSavingsPlansPurchaseRecommendation`, `ce:GetSavingsPlansCoverage`, `savingsplans:DescribeSavingsPlans`
- **Purchaser**: `savingsplans:CreateSavingsPlan`, `ce:GetSavingsPlansCoverage`, `savingsplans:DescribeSavingsPlans`
- **Reporter**: `ce:GetSavingsPlansCoverage`, `ce:GetSavingsPlansUtilization`, `savingsplans:DescribeSavingsPlans`

### InsufficientPermissionsException

**Error:** `InsufficientPermissionsException`

**Affected:** All Lambdas

**Cause:** IAM policy missing required actions.

**Fix:** Review IAM policy and add missing Cost Explorer or Savings Plans permissions.

## Purchaser-Specific Errors

### DuplicateSavingsPlanException

**Error:** `Duplicate Savings Plan request`

**Cause:** Purchase with same `clientToken` already exists (idempotency working correctly).

**Handling:** Warning logged, SQS message deleted. **This is success** - plan already purchased.

### ValidationException

**Error:** `Invalid hourly commitment value`

**Cause:** Commitment below AWS minimum ($0.001/hour) or invalid parameters.

**Handling:** Error logged, SQS message deleted (no retry - data is invalid).

**Fix:** Check `purchase_strategy.min_commitment_per_plan` setting.

### ServiceQuotaExceededException

**Error:** `Maximum number of Savings Plans reached`

**Cause:** AWS account limit exceeded (default: 500 active plans).

**Handling:** Lambda fails, SQS message returns to queue for retry.

**Fix:** Request quota increase via AWS Support or clean up expired Savings Plans.

## Scheduler-Specific Errors

### DataUnavailableException

**Error:** `Insufficient data to generate recommendation`

**Cause:** Not enough usage history (< `min_data_days`).

**Handling:** Warning logged, no purchase recommended.

**Fix:** Wait for more usage history or reduce `purchase_strategy.min_data_days`.

## All Lambdas - Queue/SNS Errors

### SQS.QueueDoesNotExist

**Error:** `The specified queue does not exist`

**Cause:** SQS queue deleted or wrong region.

**Fix:** Verify queue exists and Lambda is in correct region.

### SNS.TopicNotFound

**Error:** `Topic does not exist`

**Cause:** SNS topic deleted or wrong region.

**Fix:** Verify SNS topic ARN and region.

## Transient AWS Errors

### InternalServerException

**Error:** `Internal service error`

**Affected:** All Lambdas

**Cause:** AWS service temporary issue.

**Handling:** Lambda fails, operation retried automatically.

**Fix:** Wait for AWS service recovery. Check [AWS Service Health Dashboard](https://status.aws.amazon.com/).

### ThrottlingException

**Error:** `Rate exceeded`

**Affected:** All Lambdas

**Cause:** Too many API calls to AWS services.

**Handling:** Lambda fails, operation retried with backoff.

**Fix:** Reduce EventBridge schedule frequency or contact AWS Support for higher limits.

## Error Handling Summary

| Error Type | Retry? | Action Required |
|------------|--------|-----------------|
| **IAM Permissions** | No | Fix IAM role/policy |
| **Duplicate Purchase** | No | None (idempotency success) |
| **Validation Errors** | No | Fix configuration |
| **Service Quotas** | Yes | Increase quota |
| **AWS Internal Errors** | Yes | Wait for recovery |
| **Throttling** | Yes | Reduce API call rate |
| **Missing Data** | No | Wait for usage history |

## Monitoring Errors

### CloudWatch Logs

View Lambda errors:

```bash
# Scheduler
aws logs tail /aws/lambda/sp-autopilot-scheduler --follow --filter ERROR

# Purchaser
aws logs tail /aws/lambda/sp-autopilot-purchaser --follow --filter ERROR

# Reporter
aws logs tail /aws/lambda/sp-autopilot-reporter --follow --filter ERROR
```

### CloudWatch Alarms

Errors trigger alarms (if enabled):
- `{name_prefix}-scheduler-errors`
- `{name_prefix}-purchaser-errors`
- `{name_prefix}-reporter-errors`
- `{name_prefix}-dlq-messages` (DLQ alarm)

### Dead Letter Queue

Failed messages after max retries go to DLQ:

```bash
aws sqs receive-message \
  --queue-url $(terraform output -raw dlq_url) \
  --max-number-of-messages 10
```

## Debugging Workflow

1. **Check CloudWatch Logs** - Find specific error message
2. **Identify Error Type** - Permissions vs transient vs validation
3. **Review IAM Permissions** - Most common issue
4. **Check AWS Service Health** - For transient errors
5. **Verify Configuration** - For validation errors
6. **Monitor DLQ** - For persistent failures

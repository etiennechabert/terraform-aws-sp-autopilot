# Error Reference Guide

Quick reference for common errors in the AWS Savings Plans Automation Module.

## Table of Contents

- [IAM and Authentication Errors](#iam-and-authentication-errors)
- [SQS Errors](#sqs-errors)
- [Savings Plans API Errors](#savings-plans-api-errors)
- [Cost Explorer Errors](#cost-explorer-errors)
- [S3 Errors](#s3-errors)
- [SNS Errors](#sns-errors)
- [CloudWatch Logs](#cloudwatch-logs)

## IAM and Authentication Errors

### AccessDenied / AccessDeniedException

The Lambda execution role lacks required IAM permissions.

**Common Causes:**
- Missing `savingsplans:*`, `ce:*`, `sqs:*`, or `sns:*` permissions
- Using custom IAM role without proper policies
- Service Control Policies (SCPs) blocking actions

**Solution:**
- Verify Lambda role has all required permissions in the module's IAM policy
- Check `aws iam get-role-policy` output for missing permissions
- Use module's default IAM role configuration or ensure custom role includes all required actions
- Run `terraform apply` to update IAM policies

---

### InvalidClientTokenId

AWS access key ID doesn't exist in AWS records.

**Common Causes:**
- Access key was deleted
- Using access keys from wrong AWS account
- Typo in AWS credentials configuration

**Solution:**
- Verify credentials with `aws sts get-caller-identity`
- Rotate and update access keys if compromised
- Ensure Lambda execution role uses IAM role, not hardcoded access keys

---

### ExpiredToken / ExpiredTokenException

Security token or temporary credentials have expired.

**Common Causes:**
- Assumed role session exceeded maximum duration
- STS token expired (default: 1 hour)
- Lambda execution timeout causing credential expiration

**Solution:**
- Lambda automatically handles credential refresh via execution role
- For manual testing, re-authenticate with `aws sts assume-role`
- Check if Lambda timeout is too long (max: 15 minutes recommended)

---

### SignatureDoesNotMatch

AWS API request signature doesn't match calculated signature.

**Common Causes:**
- System clock drift (>5 minutes difference from AWS servers)
- Incorrect AWS secret access key
- Network proxy modifying requests

**Solution:**
- Sync system clock: `ntpdate -u pool.ntp.org` or enable NTP
- Verify credentials are correct
- Check for proxy or network middleware modifying requests

---

### UnrecognizedClientException

AWS doesn't recognize the security credentials.

**Common Causes:**
- Credentials belong to different AWS partition (e.g., commercial vs. GovCloud)
- Invalid or malformed credentials
- Credentials not yet propagated (if recently created)

**Solution:**
- Verify credentials match the correct AWS partition and region
- Wait 5-10 minutes if credentials were just created
- Re-create and configure new credentials

---

### InvalidAccessKeyId

Access key ID is malformed or doesn't exist.

**Common Causes:**
- Typo in access key ID
- Access key deleted but still configured
- Whitespace in environment variable

**Solution:**
- Verify access key format: starts with `AKIA` (long-term) or `ASIA` (temporary)
- Check for hidden whitespace in configuration files
- Create new access keys if deleted

---

### MissingAuthenticationToken

No authentication credentials provided in request.

**Common Causes:**
- Lambda execution role not attached to function
- IAM role trust policy doesn't allow Lambda service
- Terraform deployment incomplete

**Solution:**
- Verify Lambda function has execution role: `aws lambda get-function-configuration`
- Check IAM role trust policy allows `lambda.amazonaws.com`
- Re-apply Terraform configuration

---

### CredentialRetrievalError

Unable to retrieve credentials from the credential chain.

**Common Causes:**
- EC2 instance metadata service unreachable (if testing on EC2)
- Lambda execution role misconfigured
- Network connectivity issues

**Solution:**
- For Lambda, ensure execution role is properly attached
- Check Lambda VPC configuration if using VPC
- Verify no network policies blocking AWS API access

---

## SQS Errors

### PurgeQueueInProgress

Queue purge operation already in progress (only one allowed per 60 seconds).

**Common Causes:**
- EventBridge schedule interval < 60 seconds
- Multiple concurrent Scheduler Lambda invocations
- Manual queue purge during automated execution

**Solution:**
- Use recommended schedule: weekly or daily (not sub-minute)
- Wait 60 seconds before retrying
- This is **non-fatal** - Scheduler logs warning and continues

---

### QueueDoesNotExist

SQS queue referenced in `QUEUE_URL` environment variable doesn't exist.

**Common Causes:**
- Queue manually deleted after deployment
- Terraform failed to create queue
- Wrong queue URL in Lambda environment variable
- Queue in different AWS region

**Solution:**
- Verify queue exists: `aws sqs list-queues`
- Check Lambda environment variable: `aws lambda get-function-configuration`
- Run `terraform apply` to recreate missing queue
- Verify region matches between queue and Lambda

---

### SQS Access Denied

Lambda lacks permissions to send/receive/delete SQS messages.

**Common Causes:**
- Missing `sqs:SendMessage`, `sqs:ReceiveMessage`, or `sqs:DeleteMessage` permissions
- Queue resource policy denying access
- VPC endpoint policy blocking SQS

**Solution:**
- Add required SQS permissions to Lambda execution role
- Check queue policy: `aws sqs get-queue-attributes --attribute-names Policy`
- Verify VPC endpoint policies if Lambda is in VPC

---

### InvalidMessageContents

SQS message contains invalid characters or format.

**Common Causes:**
- Message body too large (>256 KB)
- Invalid UTF-8 characters in JSON
- Binary data not base64-encoded
- Message contains restricted XML characters

**Solution:**
- Verify purchase intent JSON is valid and < 256 KB
- Ensure all string values use valid UTF-8
- Check for special characters in offering IDs or commitment values

---

### OverLimit / TooManyMessagesInFlight

Too many messages in-flight (received but not deleted).

**Common Causes:**
- Purchaser Lambda failing repeatedly without deleting messages
- Default in-flight limit: 120,000 messages
- Messages not deleted after processing

**Solution:**
- Check Purchaser Lambda logs for processing errors
- Verify messages are deleted after successful/failed processing
- Purge queue if messages are stuck: `aws sqs purge-queue`
- Enable Dead Letter Queue to handle failed messages

---

### EmptyBatchRequest / ReceiptHandleIsInvalid

Batch request is empty or receipt handle is invalid/expired.

**Common Causes:**
- Receipt handle expired (default visibility timeout: 30 seconds)
- Message already deleted by another consumer
- Receipt handle malformed

**Solution:**
- Increase SQS visibility timeout if processing takes > 30 seconds
- Ensure messages are processed and deleted before visibility timeout
- Check for duplicate message processing

---

### SQS ServiceUnavailable / RequestTimeout

SQS service temporarily unavailable or request timed out.

**Common Causes:**
- AWS service outage
- Network connectivity issues
- Lambda in VPC without NAT or VPC endpoints

**Solution:**
- Check AWS Health Dashboard for service status
- Implement retry logic (AWS SDK does this automatically)
- Add VPC endpoints for SQS if Lambda is in VPC
- Verify network connectivity

---

## Savings Plans API Errors

### ValidationException

Invalid parameters in CreateSavingsPlan API call.

**Common Causes:**
- Offering ID expired (offerings typically valid for 30 days)
- Commitment amount below minimum ($0.001/hour)
- Invalid payment option or upfront amount mismatch
- Invalid tag keys/values

**Solution:**
- Re-run Scheduler Lambda to get fresh offering IDs
- Verify commitment amount ≥ $0.001/hour
- Ensure payment option matches upfront amount (NO_UPFRONT = no upfront payment)
- Validate tag keys/values meet AWS requirements

---

### DuplicateRequestException

Request with same client token already submitted recently.

**Common Causes:**
- Purchaser Lambda retried with same client token
- Message processed multiple times from SQS
- Concurrent Purchaser invocations

**Solution:**
- This is typically **harmless** - indicates idempotency protection working
- If unintended, check SQS message deduplication is working
- Review Purchaser Lambda retry logic

---

### ResourceNotFoundException

Savings Plan offering or resource not found.

**Common Causes:**
- Offering ID no longer available
- Savings Plan ID doesn't exist (when querying existing plans)
- Regional offering accessed from wrong region

**Solution:**
- Get fresh recommendations with current offering IDs
- Verify Savings Plan exists: `aws savingsplans describe-savings-plans`
- Check region matches offering region

---

### InternalServerException

AWS internal server error on Savings Plans API.

**Common Causes:**
- Temporary AWS service issue
- API backend problem
- Rare transient error

**Solution:**
- Retry after a few minutes (AWS SDK retries automatically)
- Check AWS Health Dashboard for service issues
- Contact AWS Support if persists

---

### ServiceQuotaExceededException

Exceeded Savings Plans service quota.

**Common Causes:**
- Too many concurrent CreateSavingsPlan requests
- Exceeded account limits for Savings Plans
- Regional quota limits

**Solution:**
- Check quotas: `aws service-quotas list-service-quotas --service-code savingsplans`
- Request quota increase via AWS Support
- Slow down purchase rate in module configuration

---

### ThrottlingException

Too many API requests in short time period.

**Common Causes:**
- Purchaser processing too many messages concurrently
- Multiple Lambda invocations running simultaneously
- API rate limit exceeded

**Solution:**
- Reduce Lambda concurrency: set reserved concurrent executions
- Add delay between API calls in Purchaser Lambda
- Implement exponential backoff (AWS SDK does this)
- Adjust EventBridge schedule to reduce frequency

---

### InvalidParameterException

One or more parameters in API request are invalid.

**Common Causes:**
- Invalid Savings Plan type (must be COMPUTE_SP, EC2_INSTANCE_SP, or SAGEMAKER_SP)
- Invalid term (must be ONE_YEAR or THREE_YEAR)
- Invalid payment option
- Malformed parameter values

**Solution:**
- Verify Savings Plan type matches module configuration
- Check term and payment option are valid enum values
- Validate all parameter formats match AWS API requirements

---

## Cost Explorer Errors

### DataUnavailableException

Cost data not available for requested time period.

**Common Causes:**
- Requesting data for future dates
- Cost Explorer data not yet available (24-48 hour delay)
- New AWS account without billing data

**Solution:**
- Wait 24-48 hours for cost data to become available
- Check requested date range is in the past
- Verify Cost Explorer is enabled: AWS Console → Cost Explorer

---

### AccessDeniedException

Insufficient permissions to access Cost Explorer data.

**Common Causes:**
- Missing `ce:GetSavingsPlansPurchaseRecommendation` or `ce:GetSavingsPlansCoverage`
- Cost Explorer not enabled for account
- Organizational policies blocking Cost Explorer

**Solution:**
- Add required Cost Explorer permissions to Lambda execution role
- Enable Cost Explorer: AWS Console → Cost Explorer → Enable
- Check AWS Organizations SCPs for restrictions

---

### LimitExceededException / ThrottlingException

Exceeded Cost Explorer API rate limits.

**Common Causes:**
- Too many GetSavingsPlansPurchaseRecommendation calls
- Scheduler Lambda running too frequently
- Multiple concurrent API requests

**Solution:**
- Reduce EventBridge schedule frequency (use weekly instead of daily)
- Implement rate limiting in Scheduler Lambda
- Use exponential backoff for retries

---

### InvalidNextTokenException

Pagination token is invalid or expired.

**Common Causes:**
- Token expired (typically valid for 24 hours)
- Token from different API call
- Malformed token

**Solution:**
- Don't cache pagination tokens - use immediately
- Restart pagination from beginning if token expired
- Ensure token matches the API endpoint

---

### InvalidParameterException

Invalid parameter in Cost Explorer API request.

**Common Causes:**
- Invalid lookback period (must be SEVEN_DAYS, THIRTY_DAYS, or SIXTY_DAYS)
- Invalid term or payment option
- Invalid date range format

**Solution:**
- Use valid enum values for all parameters
- Verify date formats: YYYY-MM-DD
- Check lookback period matches allowed values

---

### BillNotAvailableException

Billing data not available for requested period.

**Common Causes:**
- New AWS account without billing history
- Requested billing period not yet closed
- Billing data still processing

**Solution:**
- Wait until billing period is closed (after month end)
- Use current month's data with caution (incomplete)
- Check account age and billing history

---

### UnresolvableUsageUnitException

Cannot resolve usage unit for cost calculation.

**Common Causes:**
- Mixed usage types in query
- Invalid usage type specified
- Cost Explorer internal calculation error

**Solution:**
- Simplify query to single usage type
- Use default module parameters (don't override usage types)
- Contact AWS Support if persists

---

## S3 Errors

### NoSuchBucket

S3 bucket doesn't exist or is in different region.

**Common Causes:**
- Bucket deleted after module deployment
- Bucket in different region than Lambda
- Typo in bucket name

**Solution:**
- Verify bucket exists: `aws s3 ls s3://bucket-name`
- Check bucket region matches Lambda region
- Run `terraform apply` to recreate bucket

---

### AccessDenied

Lambda lacks permissions to access S3 bucket.

**Common Causes:**
- Missing `s3:PutObject`, `s3:GetObject` permissions
- Bucket policy denying access
- Bucket encryption requiring KMS permissions

**Solution:**
- Add S3 permissions to Lambda execution role
- Check bucket policy: `aws s3api get-bucket-policy`
- Add KMS permissions if bucket uses SSE-KMS encryption

---

### InvalidBucketName

Bucket name doesn't meet S3 naming requirements.

**Common Causes:**
- Uppercase letters in bucket name
- Invalid characters (only lowercase, numbers, hyphens allowed)
- Name too short (<3) or too long (>63)
- Starts/ends with hyphen

**Solution:**
- Use only lowercase letters, numbers, and hyphens
- Ensure name is 3-63 characters
- Don't start/end with hyphen
- Update Terraform configuration with valid bucket name

---

### SlowDown

Too many requests to S3 bucket.

**Common Causes:**
- Exceeded S3 request rate limits (3,500 PUT/5,500 GET per prefix per second)
- Multiple Lambdas writing to same prefix
- High-frequency EventBridge schedule

**Solution:**
- Implement exponential backoff (AWS SDK does this)
- Use unique prefixes for each Lambda invocation
- Reduce EventBridge schedule frequency
- Enable S3 request metrics to monitor rate

---

### RequestTimeout

S3 request timed out.

**Common Causes:**
- Large file upload/download
- Network connectivity issues
- Lambda in VPC without S3 VPC endpoint

**Solution:**
- Add S3 VPC endpoint if Lambda is in VPC
- Increase Lambda timeout for large files
- Implement retry logic for transient failures

---

## SNS Errors

### NotFound / NotFoundException

SNS topic doesn't exist.

**Common Causes:**
- Topic deleted after deployment
- Topic in different region
- Wrong topic ARN in Lambda environment variable

**Solution:**
- Verify topic exists: `aws sns list-topics`
- Check topic ARN matches region
- Run `terraform apply` to recreate topic

---

### AuthorizationError

Lambda lacks permissions to publish to SNS topic.

**Common Causes:**
- Missing `sns:Publish` permission
- Topic policy denying access
- Topic encrypted with KMS and missing KMS permissions

**Solution:**
- Add `sns:Publish` to Lambda execution role
- Check topic policy: `aws sns get-topic-attributes`
- Add KMS permissions if topic uses encryption

---

### InvalidParameter

Invalid parameter in SNS publish request.

**Common Causes:**
- Message too large (>256 KB)
- Invalid message attributes
- Invalid subject line
- Malformed JSON in message

**Solution:**
- Ensure message < 256 KB
- Validate JSON structure
- Check message attributes format
- Keep subject line < 100 characters

---

### KMSAccessDeniedException / KMSDisabledException

Cannot access KMS key for encrypted SNS topic.

**Common Causes:**
- Missing KMS permissions (`kms:Decrypt`, `kms:GenerateDataKey`)
- KMS key disabled or deleted
- Key policy doesn't allow Lambda role

**Solution:**
- Add KMS permissions to Lambda execution role
- Check key status: `aws kms describe-key`
- Update key policy to allow Lambda role
- Enable key if disabled

---

### EndpointDisabled

SNS subscription endpoint is disabled.

**Common Causes:**
- Email endpoint not confirmed
- HTTP/HTTPS endpoint returned errors multiple times
- SMS endpoint opted out
- Endpoint manually disabled

**Solution:**
- Confirm subscription: check email for confirmation link
- Fix HTTP endpoint to return 200 status
- Re-enable endpoint: `aws sns set-subscription-attributes`
- Verify endpoint is reachable

---

## CloudWatch Logs

### Log Group Names

| Lambda Function | Log Group | Purpose |
|----------------|-----------|---------|
| Scheduler | `/aws/lambda/savings-plans-scheduler` | Usage analysis, coverage calculations, purchase intents |
| Purchaser | `/aws/lambda/savings-plans-purchaser` | Purchase execution, validation, coverage cap checks |

### Finding Errors

**AWS Console:**
- CloudWatch → Logs → Log groups → Select log group
- Search Log Group → Filter patterns: `[ERROR]`, `Exception`, `AccessDenied`, `Traceback`

**AWS CLI:**
```bash
# Tail recent logs
aws logs tail /aws/lambda/savings-plans-scheduler --follow --filter-pattern "[ERROR]"

# Search for specific error
aws logs filter-log-events \
  --log-group-name /aws/lambda/savings-plans-scheduler \
  --filter-pattern "AccessDenied"
```

**Common Filter Patterns:**
- `[ERROR]` - All errors
- `Exception` - Python exceptions
- `AccessDenied` - IAM permission errors
- `Traceback` - Stack traces
- `Failed to purchase` - Purchase failures

### Troubleshooting Steps

1. **Check recent logs** in CloudWatch for error messages
2. **Verify IAM permissions** - Most errors are permission-related
3. **Confirm resources exist** - Check SQS queue, SNS topic, S3 bucket
4. **Review EventBridge schedule** - Ensure appropriate frequency
5. **Test in dry run mode** - Set `dry_run = true` to test without purchases
6. **Check AWS service health** - AWS Health Dashboard for outages
7. **Verify network connectivity** - VPC endpoints if Lambda in VPC

### Common Log Patterns

**Successful Execution:**
```
[INFO] Calculating current coverage
[INFO] Current coverage: 45.2%
[INFO] Target coverage: 80.0%
[INFO] Queued 3 purchase intents
```

**Permission Error:**
```
[ERROR] ClientError: An error occurred (AccessDeniedException) when calling the CreateSavingsPlan operation
```

**Coverage Cap:**
```
[INFO] Current coverage (81.2%) exceeds target (80.0%). Skipping purchase.
```

**Dry Run Mode:**
```
[DRY RUN] Would purchase Savings Plan: offering_id=abc123, commitment=$5.00/hour
```

---

For additional help, see [README.md](README.md) troubleshooting section or open a GitHub issue.

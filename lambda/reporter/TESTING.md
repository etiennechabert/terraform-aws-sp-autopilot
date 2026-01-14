# Reporter Lambda Testing Guide

This document provides an overview of testing strategies for the Reporter Lambda function.

## Test Artifacts

### Unit Testing

The following test artifacts have been created for unit testing:

1. **test_handler.py** - Comprehensive unit test suite
   - Assume role functionality tests
   - Client initialization tests
   - Configuration loading tests
   - Coverage history retrieval tests
   - Savings data collection tests
   - HTML report generation tests
   - S3 upload tests
   - Email notification tests
   - Handler integration tests
   - Edge case and error handling tests
   - Target: >= 80% code coverage

## Running Tests

### Unit Tests

```bash
# Install test dependencies
pip install pytest pytest-cov

# Run all tests with coverage report
pytest lambda/reporter/test_handler.py -v --cov=lambda/reporter/handler --cov-report=term-missing

# Run specific test function
pytest lambda/reporter/test_handler.py::test_get_coverage_history_success -v

# Run tests for specific category
pytest lambda/reporter/test_handler.py -k "coverage" -v
```

### Manual Integration Testing

For manual integration testing, you can invoke the Lambda function directly:

```bash
# Set your Lambda function name
export LAMBDA_FUNCTION_NAME=reporter-function

# Invoke the Lambda function
aws lambda invoke \
  --function-name $LAMBDA_FUNCTION_NAME \
  --payload '{}' \
  response.json

# Check the response
cat response.json

# Check CloudWatch Logs
aws logs tail /aws/lambda/$LAMBDA_FUNCTION_NAME --follow
```

## What Gets Tested

### 1. Coverage History Collection

The tests verify that coverage history is correctly collected:

- ✅ **API Call Success** - Cost Explorer API called with correct date range
- ✅ **Data Parsing** - Coverage percentages and hours parsed correctly
- ✅ **Date Range Calculation** - Lookback period calculated correctly (default 30 days)
- ✅ **Empty Data Handling** - Empty coverage data handled gracefully
- ✅ **Error Handling** - ClientError raised on API failure
- ✅ **Data Structure** - Returns list of dictionaries with date, coverage_percentage, hours

### 2. Savings Data Collection

The tests verify that savings data is correctly gathered:

- ✅ **Active Plans Retrieval** - Savings Plans with 'active' state retrieved
- ✅ **Commitment Calculation** - Total hourly commitment calculated correctly
- ✅ **Plan Details Collection** - Plan ID, type, term, payment option captured
- ✅ **Utilization Data** - Average utilization calculated from last 7 days
- ✅ **Savings Estimation** - Monthly savings estimated (commitment × 730 hours × 25%)
- ✅ **No Plans Handling** - Returns zero values when no active plans exist
- ✅ **Utilization Error Handling** - Gracefully handles utilization API failures (returns 0%)
- ✅ **Error Handling** - ClientError raised on describe_savings_plans failure

### 3. HTML Report Generation

The tests verify that HTML reports are correctly generated:

- ✅ **HTML Structure** - Valid HTML with proper DOCTYPE and structure
- ✅ **Coverage Summary** - Current and average coverage displayed correctly
- ✅ **Trend Calculation** - Trend symbol (↑/↓/→) calculated based on first vs last coverage
- ✅ **Savings Metrics** - Active plans count, commitment, estimated savings displayed
- ✅ **Coverage Table** - Daily coverage data rendered in table format
- ✅ **Plans Table** - Active Savings Plans details rendered with all fields
- ✅ **Empty Data Handling** - "No data available" messages shown when appropriate
- ✅ **Date Formatting** - ISO timestamps formatted to date-only format
- ✅ **Report Timestamp** - Generation timestamp included in UTC

### 4. S3 Upload

The tests verify that reports are correctly uploaded to S3:

- ✅ **Object Key Format** - Timestamp-based key: `savings-plans-report_YYYY-MM-DD_HH-MM-SS.html`
- ✅ **Content Type** - Correct Content-Type header (text/html for HTML format)
- ✅ **Encryption** - Server-side encryption enabled (AES256)
- ✅ **Metadata** - Generated-at timestamp and generator metadata included
- ✅ **Error Handling** - ClientError raised on S3 upload failure
- ✅ **Return Value** - S3 object key returned for reference

### 5. Email Notifications

The tests verify that email notifications work correctly:

- ✅ **Email Enabled** - Email sent when email_reports=true
- ✅ **Email Disabled** - Email skipped when email_reports=false
- ✅ **Subject Line** - Includes current coverage and estimated monthly savings
- ✅ **Email Body** - Contains coverage summary, savings summary, and S3 links
- ✅ **S3 Links** - Direct URL and Console URL included
- ✅ **Metrics Formatting** - Percentages, dollar amounts, and counts formatted correctly
- ✅ **Error Handling** - ClientError raised on SNS publish failure

### 6. Cross-Account Access (Assume Role)

The tests verify that cross-account access works correctly:

- ✅ **Role Assumption** - AssumeRole called when management_account_role_arn provided
- ✅ **Session Creation** - Boto3 session created with temporary credentials
- ✅ **Client Separation** - CE/Savings Plans use assumed credentials, SNS/S3 use local
- ✅ **No Role Handling** - All clients use default credentials when no role ARN
- ✅ **Access Denied** - ClientError raised with clear message on assume role failure
- ✅ **Error Email** - Error notification sent with role ARN in message on failure

### 7. Error Handling

The tests verify error handling across all scenarios:

- ✅ **Exceptions Raised** - All errors raised (no silent failures)
- ✅ **Error Email Sent** - Error notification sent via SNS on failure
- ✅ **CloudWatch Logs** - Errors logged with stack traces
- ✅ **Lambda Failure** - Lambda execution fails visibly on error
- ✅ **Error Email Resilience** - send_error_email doesn't raise on SNS failure

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
        "ce:GetSavingsPlansUtilization"
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
        "s3:PutObject"
      ],
      "Resource": "arn:aws:s3:::reports-bucket/*"
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

### Cross-Account Permissions (Optional)

If using cross-account access, add AssumeRole permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "sts:AssumeRole"
      ],
      "Resource": "arn:aws:iam::MANAGEMENT_ACCOUNT_ID:role/sp-autopilot-access"
    }
  ]
}
```

### Environment Variables

Configure the following environment variables for testing:

```bash
REPORTS_BUCKET=savings-plans-reports             # S3 bucket for report storage
SNS_TOPIC_ARN=arn:aws:sns:us-east-1:...:...     # SNS topic for notifications
REPORT_FORMAT=html                               # Report format (default: html)
EMAIL_REPORTS=true                               # Enable/disable email notifications
MANAGEMENT_ACCOUNT_ROLE_ARN=                     # Optional cross-account role ARN
TAGS={"Environment":"test","ManagedBy":"AutoPilot"}  # Resource tags
```

## Test Scenarios

### Scenario 1: Full Report with Active Plans

**Setup:**
- Active Savings Plans exist in account
- Coverage data available for last 30 days
- Email notifications enabled

**Expected Results:**
- Coverage history collected (30 data points)
- Savings data collected with active plans count
- HTML report generated with full data
- Report uploaded to S3 with timestamp-based key
- Email notification sent with:
  - Current coverage percentage in subject
  - Estimated monthly savings in subject
  - Coverage summary (current, average, trend)
  - Savings summary (plans count, commitment, utilization)
  - S3 direct link and console link

### Scenario 2: No Active Plans

**Setup:**
- No active Savings Plans in account
- Coverage data may be empty or zero

**Expected Results:**
- Coverage history collected (may be empty)
- Savings data returns zero values
- HTML report generated showing:
  - "No coverage data available" (if no coverage)
  - "No active Savings Plans found"
  - Zero commitment and savings
- Report uploaded to S3
- Email notification sent (if enabled) showing zero metrics

### Scenario 3: Email Disabled

**Setup:**
- EMAIL_REPORTS=false
- Active plans and coverage data exist

**Expected Results:**
- Coverage history collected
- Savings data collected
- HTML report generated
- Report uploaded to S3
- Email notification skipped (logged as "Email notifications disabled")

### Scenario 4: Cross-Account Access

**Setup:**
- MANAGEMENT_ACCOUNT_ROLE_ARN set to valid role
- Role has trust relationship with Lambda execution role
- Role has ce:* and savingsplans:* permissions in management account

**Expected Results:**
- AssumeRole called with provided ARN
- Temporary credentials obtained
- CE and Savings Plans clients use assumed credentials
- SNS and S3 clients use local credentials
- Report generated successfully with cross-account data

### Scenario 5: Coverage Trend - Improving

**Setup:**
- Coverage data shows upward trend (e.g., 70% → 80%)

**Expected Results:**
- Trend symbol: ↑
- Trend color: green (#28a745)
- Email shows upward trend indicator

### Scenario 6: Coverage Trend - Declining

**Setup:**
- Coverage data shows downward trend (e.g., 80% → 70%)

**Expected Results:**
- Trend symbol: ↓
- Trend color: red (#dc3545)
- Email shows downward trend indicator

### Scenario 7: Coverage Trend - Stable

**Setup:**
- Coverage data shows no significant change or single data point

**Expected Results:**
- Trend symbol: →
- Trend color: gray (#6c757d)
- Email shows stable trend indicator

## Edge Cases

### Edge Case 1: Partial Utilization Data

**Scenario:** Utilization API fails but plan data succeeds

**Expected Behavior:**
- Warning logged about utilization failure
- Savings data returns with average_utilization=0.0
- Report generation continues successfully
- Plans table shows plan details without utilization

### Edge Case 2: Single Day Coverage Data

**Scenario:** Only one day of coverage data available

**Expected Behavior:**
- Average coverage equals current coverage
- Trend direction: → (no comparison possible)
- Report shows 1 row in coverage table

### Edge Case 3: Very Large Commitment Values

**Scenario:** Total hourly commitment > $1000/hour

**Expected Behavior:**
- Values formatted with thousand separators (e.g., $1,234.56)
- Monthly commitment calculated correctly ($1000 × 730 = $730,000)
- Estimated monthly savings calculated correctly
- Report displays all values with proper formatting

### Edge Case 4: S3 Bucket Access Denied

**Scenario:** Lambda lacks PutObject permission on S3 bucket

**Expected Behavior:**
- ClientError raised during upload_report_to_s3
- Error logged with bucket name and error code
- Error email sent via SNS
- Lambda execution fails visibly

### Edge Case 5: SNS Topic Not Found

**Scenario:** SNS topic ARN invalid or deleted

**Expected Behavior:**
- Report generated and uploaded successfully
- Email send fails with ClientError
- Error logged
- Lambda execution fails (email failure is critical)

### Edge Case 6: Cross-Account Role Access Denied

**Scenario:** Lambda execution role cannot assume management account role

**Expected Behavior:**
- AssumeRole fails with AccessDenied
- Error caught during client initialization
- Error email sent with role ARN in message
- Lambda execution fails before any data collection

## Troubleshooting

### Issue: "No coverage data available"

**Possible Causes:**
- No EC2/Fargate/Lambda usage in the account
- Cost Explorer not enabled
- Insufficient data days

**Resolution:**
- Verify usage exists in the account
- Enable Cost Explorer in AWS console
- Wait 24-48 hours for data to populate

### Issue: "No active Savings Plans found"

**Possible Causes:**
- No Savings Plans purchased
- All plans expired
- Wrong account (if using cross-account)

**Resolution:**
- Verify Savings Plans exist in Savings Plans console
- Check plan states (should be 'active')
- Verify MANAGEMENT_ACCOUNT_ROLE_ARN if using cross-account

### Issue: S3 Upload Fails with "AccessDenied"

**Possible Causes:**
- Lambda execution role lacks s3:PutObject permission
- Bucket policy blocks Lambda
- Bucket does not exist

**Resolution:**
- Add s3:PutObject permission to Lambda execution role
- Verify bucket exists in correct region
- Check bucket policy for explicit Deny statements

### Issue: Email Not Received

**Possible Causes:**
- EMAIL_REPORTS=false
- SNS topic has no subscriptions
- Email subscription not confirmed
- SNS publish permission missing

**Resolution:**
- Verify EMAIL_REPORTS=true
- Check SNS topic subscriptions in console
- Confirm email subscription (check spam folder for confirmation)
- Add sns:Publish permission to Lambda execution role

### Issue: Assume Role Fails

**Possible Causes:**
- Role ARN invalid or typo
- Trust relationship missing
- Insufficient permissions on role

**Resolution:**
- Verify role ARN is correct
- Add Lambda execution role to trust relationship:
  ```json
  {
    "Effect": "Allow",
    "Principal": {
      "AWS": "arn:aws:iam::LAMBDA_ACCOUNT:role/lambda-execution-role"
    },
    "Action": "sts:AssumeRole"
  }
  ```
- Verify role has ce:* and savingsplans:* permissions

### Issue: Utilization Shows 0%

**Possible Causes:**
- Plans recently purchased (< 7 days)
- Utilization API throttled
- Cost Explorer data lag

**Resolution:**
- Wait 7 days after plan purchase for utilization data
- Check CloudWatch Logs for throttling warnings
- Utilization = 0% is not critical, report will still generate

## Monitoring

### CloudWatch Metrics to Monitor

- **Lambda Duration** - Should complete in < 30 seconds
- **Lambda Errors** - Should be zero under normal conditions
- **Lambda Invocations** - Should match EventBridge schedule

### CloudWatch Logs to Review

- **INFO logs** - Normal execution flow and metrics
- **WARNING logs** - Utilization failures (non-critical)
- **ERROR logs** - Critical failures requiring attention

### S3 Bucket Monitoring

- **Object Count** - Should increase by 1 per Lambda execution
- **Bucket Size** - Monitor for cost management (consider lifecycle policies)
- **Object Age** - Consider archiving or deleting old reports

### SNS Topic Monitoring

- **NumberOfMessagesPublished** - Should match Lambda invocations
- **NumberOfNotificationsFailed** - Should be zero

## Best Practices

1. **Test with Real Data** - Unit tests use mocks; validate with actual AWS data
2. **Monitor First Execution** - Watch CloudWatch Logs for first scheduled run
3. **Verify Email Delivery** - Confirm SNS subscription and check email
4. **Check S3 Reports** - Download and view HTML report to verify formatting
5. **Review Utilization** - Compare utilization % with Cost Explorer console
6. **Set Up Alerts** - Create CloudWatch alarms for Lambda errors
7. **Lifecycle Policies** - Configure S3 lifecycle rules to archive/delete old reports
8. **Cost Awareness** - Monitor Cost Explorer API costs (free tier: 50 requests/day)

## Security Considerations

1. **S3 Encryption** - Reports encrypted at rest with AES256
2. **IAM Permissions** - Use least-privilege permissions
3. **Cross-Account Trust** - Limit AssumeRole to specific principal ARNs
4. **SNS Encryption** - Consider enabling SNS topic encryption
5. **Email Security** - Reports contain AWS account metadata; ensure SNS subscribers are authorized
6. **S3 Bucket Policy** - Restrict access to authorized IAM roles only
7. **CloudWatch Logs** - Retention period configured to balance cost vs audit requirements

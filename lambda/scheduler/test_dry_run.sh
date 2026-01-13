#!/bin/bash
# Integration test script for Scheduler Lambda (Dry-Run Mode)
# This script helps verify the complete scheduler flow

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
LAMBDA_FUNCTION_NAME="${LAMBDA_FUNCTION_NAME:-scheduler-function}"
QUEUE_URL="${QUEUE_URL:-}"
SNS_TOPIC_ARN="${SNS_TOPIC_ARN:-}"

echo "=========================================="
echo "Scheduler Lambda Integration Test"
echo "Dry-Run Mode Verification"
echo "=========================================="
echo ""

# Check prerequisites
echo "Checking prerequisites..."

if ! command -v aws &> /dev/null; then
    echo -e "${RED}ERROR: AWS CLI not found${NC}"
    exit 1
fi

if ! aws sts get-caller-identity &> /dev/null; then
    echo -e "${RED}ERROR: AWS credentials not configured${NC}"
    exit 1
fi

echo -e "${GREEN}✓ AWS CLI configured${NC}"

# Check Lambda function exists
echo "Checking Lambda function: $LAMBDA_FUNCTION_NAME"
if ! aws lambda get-function --function-name "$LAMBDA_FUNCTION_NAME" &> /dev/null; then
    echo -e "${RED}ERROR: Lambda function '$LAMBDA_FUNCTION_NAME' not found${NC}"
    echo "Set LAMBDA_FUNCTION_NAME environment variable to your function name"
    exit 1
fi

echo -e "${GREEN}✓ Lambda function found${NC}"

# Get Lambda configuration
echo "Getting Lambda configuration..."
CONFIG=$(aws lambda get-function-configuration --function-name "$LAMBDA_FUNCTION_NAME")

# Extract environment variables
DRY_RUN=$(echo "$CONFIG" | jq -r '.Environment.Variables.DRY_RUN // "not set"')
QUEUE_URL=$(echo "$CONFIG" | jq -r '.Environment.Variables.QUEUE_URL // "not set"')
SNS_TOPIC_ARN=$(echo "$CONFIG" | jq -r '.Environment.Variables.SNS_TOPIC_ARN // "not set"')

echo "Current configuration:"
echo "  DRY_RUN: $DRY_RUN"
echo "  QUEUE_URL: $QUEUE_URL"
echo "  SNS_TOPIC_ARN: $SNS_TOPIC_ARN"
echo ""

# Verify dry-run mode is enabled
if [ "$DRY_RUN" != "true" ]; then
    echo -e "${YELLOW}WARNING: DRY_RUN is not set to 'true'${NC}"
    echo "This test should be run with DRY_RUN=true"
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Check SQS queue
if [ "$QUEUE_URL" != "not set" ]; then
    echo "Checking SQS queue status..."
    QUEUE_ATTRS=$(aws sqs get-queue-attributes \
        --queue-url "$QUEUE_URL" \
        --attribute-names ApproximateNumberOfMessages 2>/dev/null || echo "{}")

    QUEUE_MESSAGES=$(echo "$QUEUE_ATTRS" | jq -r '.Attributes.ApproximateNumberOfMessages // "unknown"')
    echo "  Messages in queue: $QUEUE_MESSAGES"

    if [ "$QUEUE_MESSAGES" != "0" ] && [ "$QUEUE_MESSAGES" != "unknown" ]; then
        echo -e "${YELLOW}WARNING: Queue is not empty (has $QUEUE_MESSAGES messages)${NC}"
    else
        echo -e "${GREEN}✓ Queue is empty${NC}"
    fi
else
    echo -e "${YELLOW}WARNING: QUEUE_URL not configured${NC}"
fi

# Check SNS topic
if [ "$SNS_TOPIC_ARN" != "not set" ]; then
    echo "Checking SNS topic..."
    if aws sns get-topic-attributes --topic-arn "$SNS_TOPIC_ARN" &> /dev/null; then
        echo -e "${GREEN}✓ SNS topic accessible${NC}"

        # List subscriptions
        SUBS=$(aws sns list-subscriptions-by-topic --topic-arn "$SNS_TOPIC_ARN" | jq -r '.Subscriptions | length')
        echo "  Subscriptions: $SUBS"

        if [ "$SUBS" == "0" ]; then
            echo -e "${YELLOW}WARNING: No email subscriptions configured${NC}"
        fi
    else
        echo -e "${RED}ERROR: Cannot access SNS topic${NC}"
    fi
else
    echo -e "${YELLOW}WARNING: SNS_TOPIC_ARN not configured${NC}"
fi

echo ""
echo "=========================================="
echo "Invoking Lambda function..."
echo "=========================================="
echo ""

# Invoke Lambda
INVOCATION_TIME=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
aws lambda invoke \
    --function-name "$LAMBDA_FUNCTION_NAME" \
    --payload '{}' \
    --log-type Tail \
    response.json > invocation_result.json

# Check invocation result
INVOCATION_STATUS=$(cat invocation_result.json | jq -r '.StatusCode')
FUNCTION_ERROR=$(cat invocation_result.json | jq -r '.FunctionError // "none"')

if [ "$INVOCATION_STATUS" == "200" ] && [ "$FUNCTION_ERROR" == "none" ]; then
    echo -e "${GREEN}✓ Lambda invocation successful${NC}"
else
    echo -e "${RED}ERROR: Lambda invocation failed${NC}"
    echo "Status Code: $INVOCATION_STATUS"
    echo "Function Error: $FUNCTION_ERROR"
    cat invocation_result.json | jq -r '.LogResult' | base64 --decode
    exit 1
fi

# Show response
echo ""
echo "Lambda Response:"
cat response.json | jq '.'
echo ""

# Show execution logs
echo "Lambda Execution Logs:"
echo "----------------------------------------"
cat invocation_result.json | jq -r '.LogResult' | base64 --decode
echo "----------------------------------------"
echo ""

# Wait a moment for logs to be available
echo "Waiting for CloudWatch Logs to be available..."
sleep 5

# Get CloudWatch Logs
echo "Fetching detailed CloudWatch Logs..."
LOG_GROUP="/aws/lambda/$LAMBDA_FUNCTION_NAME"

# Get the most recent log stream
LATEST_STREAM=$(aws logs describe-log-streams \
    --log-group-name "$LOG_GROUP" \
    --order-by LastEventTime \
    --descending \
    --max-items 1 | jq -r '.logStreams[0].logStreamName')

if [ "$LATEST_STREAM" != "null" ] && [ -n "$LATEST_STREAM" ]; then
    echo "Latest log stream: $LATEST_STREAM"
    echo ""

    # Get logs from the stream
    aws logs get-log-events \
        --log-group-name "$LOG_GROUP" \
        --log-stream-name "$LATEST_STREAM" \
        --start-time $(date -d "5 minutes ago" +%s000) \
        | jq -r '.events[].message'
else
    echo -e "${YELLOW}Could not fetch CloudWatch Logs${NC}"
fi

echo ""
echo "=========================================="
echo "Verification Checklist"
echo "=========================================="
echo ""

# Check queue again
if [ "$QUEUE_URL" != "not set" ]; then
    echo "Checking SQS queue after execution..."
    QUEUE_ATTRS=$(aws sqs get-queue-attributes \
        --queue-url "$QUEUE_URL" \
        --attribute-names ApproximateNumberOfMessages 2>/dev/null || echo "{}")

    QUEUE_MESSAGES=$(echo "$QUEUE_ATTRS" | jq -r '.Attributes.ApproximateNumberOfMessages // "unknown"')
    echo "  Messages in queue: $QUEUE_MESSAGES"

    if [ "$QUEUE_MESSAGES" == "0" ]; then
        echo -e "${GREEN}✓ Queue is still empty (dry-run working correctly)${NC}"
    elif [ "$QUEUE_MESSAGES" == "unknown" ]; then
        echo -e "${YELLOW}⚠ Could not verify queue status${NC}"
    else
        echo -e "${RED}✗ Queue has $QUEUE_MESSAGES messages (dry-run may not be working!)${NC}"
    fi
else
    echo -e "${YELLOW}⚠ QUEUE_URL not configured - cannot verify${NC}"
fi

echo ""
echo "=========================================="
echo "Manual Verification Required"
echo "=========================================="
echo ""
echo "Please verify the following:"
echo ""
echo "1. Email Notification:"
echo "   □ Email received with subject: [DRY RUN] Savings Plans Analysis"
echo "   □ Email contains dry-run header"
echo "   □ Email states 'NO PURCHASES WERE SCHEDULED'"
echo "   □ Email includes coverage statistics"
echo "   □ Email includes purchase plan details"
echo ""
echo "2. CloudWatch Logs:"
echo "   □ Coverage calculation logged"
echo "   □ Recommendations retrieved"
echo "   □ Purchase plans calculated"
echo "   □ Limits applied correctly"
echo "   □ Term splitting performed"
echo "   □ Dry-run email sent"
echo "   □ No errors in logs"
echo ""
echo "3. SQS Queue:"
echo "   □ Queue remains empty (0 messages)"
echo ""
echo "For detailed verification steps, see:"
echo "  lambda/scheduler/integration_test_dry_run.md"
echo ""

# Cleanup
rm -f response.json invocation_result.json

echo "=========================================="
echo "Test Complete"
echo "=========================================="

# Testing Documentation

This directory contains testing resources for the Slack Interactive Approval Actions feature.

## Files

### E2E Testing

- **`e2e_slack_interactive.py`** - Automated end-to-end integration test script
  - Tests complete workflow from scheduler to purchaser
  - Supports 3 modes: full, manual, verify-only
  - Validates signature verification, SQS operations, and audit logging
  - Run with: `python tests/e2e_slack_interactive.py --mode full`

- **`E2E_TEST_GUIDE.md`** - Comprehensive E2E testing guide
  - Prerequisites and setup instructions
  - Step-by-step manual testing procedures
  - Verification checklist with 50+ checkpoints
  - Troubleshooting guide
  - CloudWatch Insights query examples

## Quick Start

### Prerequisites

1. Deploy Terraform infrastructure:
   ```bash
   terraform apply
   ```

2. Set environment variables:
   ```bash
   export QUEUE_URL=$(terraform output -raw queue_url)
   export SLACK_INTERACTIVE_ENDPOINT=$(terraform output -raw slack_interactive_endpoint)
   export SLACK_SIGNING_SECRET="your_secret"
   export SCHEDULER_LAMBDA_NAME="sp-autopilot-scheduler"
   export PURCHASER_LAMBDA_NAME="sp-autopilot-purchaser"
   ```

3. Install Python dependencies:
   ```bash
   pip install boto3 requests
   ```

### Run Automated E2E Test

```bash
python tests/e2e_slack_interactive.py --mode full
```

### Run Manual Interactive Test

```bash
python tests/e2e_slack_interactive.py --mode manual
```

## Verification Steps

The E2E test validates:

1. ✅ Scheduler queues purchase and sends Slack notification
2. ✅ Slack message contains Approve/Reject buttons
3. ✅ Reject button triggers API Gateway request
4. ✅ Interactive handler verifies HMAC SHA256 signature
5. ✅ SQS message is deleted from queue
6. ✅ Audit log entry created in CloudWatch
7. ✅ Slack receives 200 OK within 3 seconds
8. ✅ Purchaser finds empty queue

## Documentation

For detailed testing instructions, see:
- **E2E_TEST_GUIDE.md** - Complete testing guide
- **../README.md** - Main project documentation
- **../lambda/interactive_handler/tests/** - Unit tests

## Support

If you encounter issues:
1. Check Lambda logs: `/aws/lambda/interactive-handler`
2. Review troubleshooting section in E2E_TEST_GUIDE.md
3. Verify environment variables are set correctly
4. Ensure Slack app is configured properly

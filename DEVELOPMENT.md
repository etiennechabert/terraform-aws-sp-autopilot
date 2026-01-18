# Development Guide

This guide explains how to set up your local development environment for debugging and testing the Lambda functions.

## Prerequisites

- Python 3.11
- VSCode with Python extension
- AWS CLI configured with credentials
- ruff (Python linter/formatter)

## Quick Start

### 1. Install Dependencies

```bash
# Install dependencies for each Lambda function
cd lambda/scheduler && pip install -r requirements.txt
cd ../purchaser && pip install -r requirements.txt
cd ../reporter && pip install -r requirements.txt
cd ../shared && pip install -r requirements.txt
```

### 2. Configure AWS Credentials

Create a `.env` file in the project root:

```bash
cp .env.example .env
```

Edit `.env` and add your AWS credentials and test resource ARNs.

### 3. VSCode Debugging

The project includes pre-configured VSCode launch configurations:

#### Debug Lambda Functions

- **Debug Scheduler Lambda** - Debug the scheduler Lambda handler
- **Debug Purchaser Lambda** - Debug the purchaser Lambda handler
- **Debug Reporter Lambda** - Debug the reporter Lambda handler
- **Debug Local Mode Runner** - Run Lambda functions locally using the local_runner.py utility

#### Run Tests

- **Run Scheduler Tests** - Run scheduler Lambda unit tests
- **Run Purchaser Tests** - Run purchaser Lambda unit tests
- **Run Reporter Tests** - Run reporter Lambda unit tests
- **Run Shared Module Tests** - Run shared module tests

### 4. Using the Debugger

1. Open VSCode
2. Press `F5` or go to Run → Start Debugging
3. Select a configuration from the dropdown
4. Set breakpoints in your code
5. The debugger will stop at breakpoints

## Local Lambda Execution

### Using local_runner.py

The `local_runner.py` utility simulates AWS Lambda execution locally:

```bash
# Run scheduler locally
python lambda/shared/local_runner.py scheduler

# Run purchaser locally
python lambda/shared/local_runner.py purchaser

# Run reporter locally
python lambda/shared/local_runner.py reporter
```

This reads environment variables from `.env` and executes the Lambda handler with mock AWS context.

### Testing with Real AWS Resources

To test with real AWS infrastructure:

1. Deploy the Terraform module to a test AWS account
2. Update `.env` with the actual resource ARNs (SQS queue, SNS topic, S3 bucket)
3. **Keep `DRY_RUN=true`** to prevent actual Savings Plans purchases
4. Run the Lambda functions locally

## Running Tests

### Unit Tests

```bash
# Run all tests for a Lambda function
cd lambda/scheduler
pytest tests/ -v

# Run specific test file
pytest tests/test_handler.py -v

# Run specific test
pytest tests/test_handler.py::test_handler_success -v

# Run with coverage
pytest tests/ -v --cov=. --cov-report=html
```

### Integration Tests

```bash
cd terraform-tests/integration

# Run all integration tests
go test -v -timeout 30m

# Run specific test
go test -v -run TestFullDeploymentAndCleanup
```

## Code Quality

### Linting and Formatting

```bash
# Check code quality
ruff check lambda/

# Fix auto-fixable issues
ruff check lambda/ --fix

# Format code
ruff format lambda/

# Check formatting without changes
ruff format lambda/ --check
```

VSCode is configured to auto-format on save using ruff.

## Common Tasks

### Adding a New Feature

1. Create a feature branch
2. Add your code changes
3. Add unit tests
4. Run tests locally: `pytest tests/ -v`
5. Run linting: `ruff check . && ruff format --check .`
6. Test with debugger in VSCode
7. Commit and push

### Debugging a Failing Test

1. Set breakpoint in test file
2. Use "Run Scheduler Tests" (or other) configuration
3. VSCode will stop at breakpoint
4. Inspect variables and step through code

### Testing Coverage Calculation

1. Use "Debug Scheduler Lambda" configuration
2. Set breakpoint in `coverage_calculator.py`
3. Mock boto3 clients will be used (from tests)
4. Or use real AWS credentials to test against real data

### Testing Purchase Logic

1. **IMPORTANT:** Always keep `DRY_RUN=true` in `.env`
2. Use "Debug Purchaser Lambda" configuration
3. Set breakpoints in `handler.py`
4. Inspect purchase intent messages from SQS

## Environment Variables Reference

See `.env.example` for all available environment variables with descriptions.

### Critical Variables

- `DRY_RUN` - **ALWAYS** set to `true` for local testing
- `QUEUE_URL` - SQS queue URL for purchase intents
- `SNS_TOPIC_ARN` - SNS topic for notifications
- `REPORTS_BUCKET` - S3 bucket for reports (reporter only)

### Coverage Configuration

- `COVERAGE_TARGET_PERCENT` - Target coverage percentage (default: 90)
- `MAX_COVERAGE_CAP` - Hard limit on coverage (default: 95)
- `ENABLE_COMPUTE_SP` - Enable Compute Savings Plans (default: true)
- `ENABLE_SAGEMAKER_SP` - Enable SageMaker Savings Plans (default: false)

## Troubleshooting

### Import Errors

If you get import errors, ensure `PYTHONPATH` includes the project root:

```bash
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

VSCode launch configurations already set this.

### AWS Credentials Not Found

Ensure your AWS credentials are configured:

```bash
aws configure
# OR
export AWS_PROFILE=your-profile-name
```

### Boto3 Type Stubs Not Found

Install boto3 type stubs:

```bash
pip install 'boto3-stubs[ce,savingsplans,sns,sqs,s3]'
```

### Coverage Data Not Available

This is normal for new AWS accounts. Cost Explorer needs 24-48 hours of usage data. The Lambda functions handle this gracefully by returning 0% coverage.

## CI/CD

The project uses GitHub Actions for CI:

- **Python Linting** - Ruff check and format validation
- **Lambda Tests** - Unit tests for scheduler, purchaser, reporter
- **Terraform Unit Tests** - Mock-based Terraform tests
- **Terraform Integration Tests** - Real AWS infrastructure tests

All checks must pass before merging PRs.

## Resources

- [AWS Savings Plans Documentation](https://docs.aws.amazon.com/savingsplans/)
- [Cost Explorer API Reference](https://docs.aws.amazon.com/aws-cost-management/latest/APIReference/API_Operations_AWS_Cost_Explorer_Service.html)
- [VSCode Python Debugging](https://code.visualstudio.com/docs/python/debugging)
- [pytest Documentation](https://docs.pytest.org/)

# Testing Guide

Comprehensive testing guide for Lambda functions, Terraform configurations, and integration tests.

## Lambda Function Tests

All Lambda functions use pytest with moto for AWS service mocking.

### Running Tests

```bash
# Test all Lambda functions
cd lambda/scheduler && pytest
cd lambda/purchaser && pytest
cd lambda/reporter && pytest
cd lambda/shared && pytest

# Run with coverage
pytest --cov=. --cov-report=term-missing --cov-report=html

# Run specific test file
pytest tests/test_handler.py -v

# Run specific test
pytest tests/test_handler.py::test_function_name -v
```

### Test Structure

#### Scheduler Lambda
- `test_handler.py` - Main handler logic, purchase recommendations
- `test_coverage.py` - Coverage calculation, expiring plan exclusion
- `test_purchase_calculator.py` - Purchase need calculation
- `test_recommendations.py` - AWS recommendation parsing
- `test_simple_strategy.py` - Simple purchase strategy
- `test_dichotomy_strategy.py` - Dichotomy purchase strategy

#### Purchaser Lambda
- `test_integration.py` - End-to-end purchase workflow
- `test_validation.py` - Input validation, coverage cap checks

#### Reporter Lambda
- `test_essential.py` - Core reporting functionality
- `test_report_generation.py` - HTML/JSON report generation
- `test_savings_utilization.py` - Savings calculation
- `test_error_handling.py` - Error scenarios

#### Shared Library
- `test_email_templates.py` - Email notification formatting
- `test_handler_utils.py` - Common Lambda utilities

### Coverage Requirements

- **Scheduler**: ≥80% coverage (enforced in CI)
- **Purchaser**: No specific threshold (integration tests)
- **Reporter**: No specific threshold
- **Shared**: ≥80% coverage recommended

### Mocking AWS Services

Tests use `moto` for AWS service mocking:

```python
from moto import mock_aws

@mock_aws
def test_function():
    # AWS API calls are intercepted and mocked
    pass
```

## Terraform Tests

### Unit Tests

Run without AWS credentials using mock providers:

```bash
cd terraform-tests/unit
terraform init
terraform test
```

Test coverage:
- `s3.tftest.hcl` - S3 bucket configuration
- `sqs.tftest.hcl` - SQS queue and DLQ
- `sns.tftest.hcl` - SNS topic and subscriptions
- `iam.tftest.hcl` - IAM roles and policies
- `cloudwatch.tftest.hcl` - CloudWatch alarms
- `eventbridge.tftest.hcl` - EventBridge schedules
- `variables.tftest.hcl` - Variable validation

### Integration Tests

Deploy real infrastructure to AWS (requires credentials):

```bash
cd terraform-tests/integration
go test -v -timeout 30m

# Specific test
go test -v -run TestFullDeploymentAndCleanup
go test -v -run TestExampleSingleAccountCompute
```

Test coverage:
- `terraform_aws_sp_autopilot_test.go` - Full module deployment with comprehensive resource validation
- `examples_integration_test.go` - Example configurations deploy successfully

**Note:** Integration tests use temporary resources with `sp-autopilot-test-*` prefix and automatic cleanup.

## CI/CD Pipeline

### PR Checks Workflow

Runs on all pull requests:

1. **Terraform Validation** - Format check, init, validate
2. **Security Scan** - tfsec for HIGH/CRITICAL issues
3. **Python Linting** - ruff check and format
4. **Lambda Tests** - pytest for all Lambda functions
5. **Terraform Unit Tests** - Mock provider tests
6. **Terraform Integration Tests** - Real AWS deployment

### Required Checks

All checks must pass before merge:
- ✅ Terraform format (`terraform fmt -check`)
- ✅ Terraform validate
- ✅ tfsec security scan
- ✅ Python linting (ruff)
- ✅ Scheduler Lambda tests (≥80% coverage)
- ✅ Terraform unit tests
- ✅ Terraform integration tests

## Local Development

### Prerequisites

```bash
# Python dependencies
pip install pytest pytest-cov moto boto3 ruff

# Terraform
terraform >= 1.11

# Go (for integration tests)
go >= 1.21

# AWS CLI (for manual testing)
aws --version
```

### Pre-commit Validation

Before committing:

```bash
# Format Terraform
terraform fmt -recursive

# Lint Python
ruff check lambda/
ruff format lambda/

# Run tests
cd lambda/scheduler && pytest
cd lambda/purchaser && pytest
cd lambda/reporter && pytest

# Terraform unit tests
cd terraform-tests/unit && terraform test
```

### Manual Lambda Testing

Invoke deployed Lambda functions:

```bash
# Scheduler Lambda
aws lambda invoke \
  --function-name sp-autopilot-scheduler \
  --payload '{}' \
  output.json

# Purchaser Lambda
aws lambda invoke \
  --function-name sp-autopilot-purchaser \
  --payload '{}' \
  output.json

# Reporter Lambda
aws lambda invoke \
  --function-name sp-autopilot-reporter \
  --payload '{}' \
  output.json
```

## Troubleshooting

### Common Issues

**Import errors in tests:**
```bash
export PYTHONPATH=$(pwd)
```

**AWS credential errors:**
- Unit tests should NOT require credentials (use mocks)
- Integration tests require valid AWS credentials

**Coverage not meeting threshold:**
```bash
pytest --cov=. --cov-report=html
open htmlcov/index.html  # View coverage report
```

**Terraform test failures:**
```bash
# Clean up test state
rm -rf .terraform terraform.tfstate*
terraform init
```

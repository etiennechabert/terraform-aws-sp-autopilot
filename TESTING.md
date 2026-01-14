# Testing the CI/CD Pipeline

## Purpose
Instructions for testing and verifying the GitHub Actions CI/CD workflows.

## PR Workflow Verification

Create a pull request to verify automated checks:

**Expected Checks:**
- [ ] PR Checks workflow triggers automatically
- [ ] Terraform Validation (fmt, init, validate)
- [ ] Security Scan (tfsec with SARIF upload)
- [ ] Python Tests (scheduler unit tests, purchaser integration tests)
- [ ] Conditional jobs run only for changed files
- [ ] All status checks pass with green ✓

Monitor workflow execution in the GitHub Actions tab and PR checks section.

## Running Tests Locally

```bash
# Terraform
terraform fmt -check -recursive
terraform init -backend=false
terraform validate

# Security scanning (requires tfsec)
tfsec .

# Python tests
cd lambda/scheduler && pytest --cov=. --cov-report=term-missing --cov-fail-under=80
cd lambda/purchaser && pytest tests/integration/
```

## Troubleshooting

**Workflow not triggering**: Check workflow files in `.github/workflows/`, verify YAML syntax, ensure GitHub Actions enabled

**Security scan false positives**: Add tfsec ignore comments for legitimate exceptions

**Python test coverage**: Scheduler requires 80% minimum coverage

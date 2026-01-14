# Testing the CI/CD Pipeline

## Purpose
This document provides instructions for testing and verifying the GitHub Actions CI/CD workflows.

## PR Checks Workflow Verification

### Test Setup
A test branch `test/verify-pr-checks-workflow` has been created with a simple test file to verify that the PR checks workflow triggers correctly.

### Manual Verification Steps

#### Step 1: Push Branches to GitHub
```bash
# Push the feature branch with all workflows
git push -u origin auto-claude/013-ci-cd-pipeline-with-github-actions

# Push the test branch
git push -u origin test/verify-pr-checks-workflow
```

#### Step 2: Create Test Pull Request
1. Go to the GitHub repository
2. Click "Pull Requests" tab
3. Click "New Pull Request"
4. Set base branch: `auto-claude/013-ci-cd-pipeline-with-github-actions`
5. Set compare branch: `test/verify-pr-checks-workflow`
6. Create the PR with title: "test: verify PR checks workflow"
7. Add description: "Testing PR checks workflow triggers (subtask-7-2)"

#### Step 3: Verify Workflow Execution
In the GitHub Actions tab and/or PR checks section, verify:

- [ ] **PR Checks workflow** triggers automatically
- [ ] **Terraform Validation** job runs and passes:
  - terraform fmt -check -recursive
  - terraform init -backend=false
  - terraform validate
- [ ] **Security Scan** job runs and passes:
  - tfsec security scanning
  - SARIF upload to Security tab
- [ ] **Python Tests** job runs and passes:
  - Scheduler tests with pytest
  - Purchaser integration tests
- [ ] All status checks show green ✓
- [ ] PR shows "All checks have passed"

#### Step 4: Verify Conditional Job Execution
The workflow should intelligently run only relevant jobs based on changed files.

#### Step 5: Check Workflow Artifacts
- [ ] Verify workflow run shows in Actions tab
- [ ] Check workflow logs are accessible
- [ ] Verify PR comments (if any checks fail)

#### Step 6: Cleanup
After successful verification:
```bash
# Delete the test branch locally
git checkout auto-claude/013-ci-cd-pipeline-with-github-actions
git branch -D test/verify-pr-checks-workflow

# Delete the test branch remotely
git push origin --delete test/verify-pr-checks-workflow

# Close the test PR without merging
```

## Local Testing

### Terraform Validation
```bash
# Format check
terraform fmt -check -recursive

# Initialize (without backend)
terraform init -backend=false

# Validate
terraform validate
```

### Security Scanning
```bash
# Install tfsec
brew install tfsec  # macOS
# or
curl -s https://raw.githubusercontent.com/aquasecurity/tfsec/master/scripts/install_linux.sh | bash

# Run security scan
tfsec .
```

### Python Tests
```bash
# Scheduler tests
cd lambda/scheduler
pip install -r requirements.txt -r requirements-dev.txt
pytest --cov=. --cov-report=term-missing --cov-fail-under=80

# Purchaser integration tests
cd lambda/purchaser
pip install -r requirements.txt
pytest tests/integration/
```

## Troubleshooting

### Workflow Not Triggering
- Verify workflow files are in `.github/workflows/` directory
- Check YAML syntax is valid
- Ensure branch protections don't block workflows
- Verify GitHub Actions is enabled for the repository

### Failed Terraform Validation
- Run `terraform fmt` locally to format files
- Check for syntax errors with `terraform validate`
- Ensure all required providers are specified

### Failed Security Scan
- Review tfsec output for specific issues
- Check if issues are false positives (can be ignored with comments)
- Fix security vulnerabilities in Terraform code

### Failed Python Tests
- Check test logs for specific failures
- Verify dependencies are installed correctly
- Run tests locally to reproduce issues
- Check coverage requirements (80% for scheduler)

## Expected Outcomes

### ✅ Success Criteria
- All workflow jobs complete without errors
- PR shows green checkmarks for all required checks
- Workflow logs show proper execution of all validation steps
- No unexpected failures or errors

### ❌ Potential Issues
- YAML syntax errors in workflow files
- Missing permissions for GitHub Actions
- Incorrect trigger conditions
- Validation failures (terraform, security, tests)
- Timeout issues

## Notes
- Individual workflow validations are tested separately before PR integration
- The test branch uses a simple file to avoid triggering validation failures
- This verifies workflow triggering and execution, not validation logic itself

# Subtask 6-1 Verification Instructions

## Status: BLOCKED - Terraform Not Available

This verification requires Terraform >= 1.7 to be installed, but it is not available in the current Git Bash environment.

## What Has Been Completed

✅ **All prerequisites are in place:**
1. Terraform version constraint upgraded from >= 1.4 to >= 1.7 in `versions.tf`
2. All 7 test files created in `tests/` directory:
   - `tests/s3.tftest.hcl` (8.5 KB)
   - `tests/sqs.tftest.hcl` (10.6 KB)
   - `tests/sns.tftest.hcl` (6.8 KB)
   - `tests/iam.tftest.hcl` (27.5 KB)
   - `tests/cloudwatch.tftest.hcl` (14.6 KB)
   - `tests/eventbridge.tftest.hcl` (18.8 KB)
   - `tests/variables.tftest.hcl` (21.5 KB)
3. Verification script created: `verify-tests.sh`

## What Needs To Be Done

When Terraform >= 1.7 becomes available, run the verification:

### Option 1: Automated Verification Script

```bash
# Run the comprehensive verification script
./verify-tests.sh
```

This script will:
1. Check Terraform version >= 1.7
2. Unset AWS environment variables
3. Run `terraform init`
4. Run `terraform test`
5. Verify exit code is 0
6. Check for credential-related errors
7. Verify all test files are present

### Option 2: Manual Verification Steps

```bash
# Step 1: Unset AWS credentials
unset AWS_ACCESS_KEY_ID
unset AWS_SECRET_ACCESS_KEY
unset AWS_SESSION_TOKEN

# Step 2: Initialize Terraform
terraform init

# Step 3: Run all tests
terraform test

# Step 4: Verify no credential errors
terraform test 2>&1 | grep -i -E 'credential|authentication|NoCredentialProviders' && echo "ERROR: Found credential errors" || echo "SUCCESS: No credential errors"

# Step 5: Check exit code (should be 0)
echo $?  # Should output: 0
```

## Expected Results

When verification runs successfully, you should see:

1. **Terraform Init:** Success without credential errors
2. **Terraform Test:** All tests pass (0 failures)
3. **Exit Code:** 0
4. **Output:** No mentions of:
   - "credential"
   - "authentication"
   - "NoCredentialProviders"
   - "InvalidClientTokenId"
   - "AccessDenied"

## Test Coverage Summary

The test suite includes 100+ test runs covering:

- **S3 Tests (13 runs):** Bucket naming, versioning, encryption, public access blocks, lifecycle
- **SQS Tests (14 runs):** Queue naming, DLQ configuration, visibility timeout, redrive policy, alarms
- **SNS Tests (8 runs):** Topic naming, email subscriptions, tagging
- **IAM Tests (30 runs):** All three Lambda roles, policies, assume role configurations
- **CloudWatch Tests (20+ runs):** Log groups, error alarms, conditional creation
- **EventBridge Tests (20+ runs):** Schedule rules, Lambda targets, permissions
- **Variable Validation Tests (70+ runs):** All validation rules, edge cases, expect_failures

## Installing Terraform

If Terraform is not installed:

### Windows (via Chocolatey)
```powershell
choco install terraform
```

### Windows (Manual)
1. Download from https://www.terraform.io/downloads
2. Extract `terraform.exe` to a directory in PATH (e.g., `C:\Program Files\Terraform\`)
3. Verify: `terraform version`

### Linux/macOS
```bash
# Using tfenv (recommended)
tfenv install 1.7.0
tfenv use 1.7.0

# Or download directly
wget https://releases.hashicorp.com/terraform/1.7.0/terraform_1.7.0_linux_amd64.zip
unzip terraform_1.7.0_linux_amd64.zip
sudo mv terraform /usr/local/bin/
```

## Next Steps After Verification Passes

1. Commit the verification results to build-progress.txt
2. Update implementation_plan.json: Set subtask-6-1 status to "completed"
3. Run QA acceptance criteria validation
4. Proceed to QA sign-off

## Troubleshooting

### If tests fail:
- Check Terraform version: `terraform version` (must be >= 1.7)
- Ensure AWS credentials are unset
- Review test output for specific failures
- Check test files for syntax errors: `terraform fmt -check tests/`

### If credential errors appear:
- Verify AWS environment variables are unset: `env | grep AWS`
- Check for AWS credential files: `~/.aws/credentials`
- Ensure mock_provider blocks are present in all test files
- Verify override_data blocks for aws_caller_identity and aws_region

## Contact

If Terraform cannot be installed or verification continues to fail, escalate to:
- Project lead for CI/CD environment setup
- DevOps team for Terraform installation

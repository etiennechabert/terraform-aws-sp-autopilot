# Terratest Integration Tests

This directory contains comprehensive integration tests for the AWS Savings Plans Automation module using [Terratest](https://terratest.gruntwork.io/). The tests validate complete module deployment, resource creation, Lambda function execution, and proper cleanup in a real AWS account.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Setup Instructions](#setup-instructions)
- [AWS Credentials Configuration](#aws-credentials-configuration)
- [Running Tests Locally](#running-tests-locally)
- [Test Descriptions](#test-descriptions)
- [CI/CD Integration](#cicd-integration)
- [Troubleshooting](#troubleshooting)
- [Cost Considerations](#cost-considerations)

## Prerequisites

Before running the integration tests, ensure you have the following installed:

### Required Tools

| Tool | Minimum Version | Purpose |
|------|----------------|---------|
| **Go** | 1.21+ | Test execution runtime |
| **Terraform** | 1.6.0+ | Infrastructure provisioning |
| **AWS CLI** | 2.x | AWS credential verification |

### Installation

#### macOS (Homebrew)
```bash
brew install go terraform awscli
```

#### Linux (Ubuntu/Debian)
```bash
# Go
wget https://go.dev/dl/go1.21.0.linux-amd64.tar.gz
sudo tar -C /usr/local -xzf go1.21.0.linux-amd64.tar.gz
export PATH=$PATH:/usr/local/go/bin

# Terraform
wget https://releases.hashicorp.com/terraform/1.6.0/terraform_1.6.0_linux_amd64.zip
unzip terraform_1.6.0_linux_amd64.zip
sudo mv terraform /usr/local/bin/

# AWS CLI
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install
```

#### Windows
```powershell
# Install using Chocolatey
choco install golang terraform awscli

# Or download installers from:
# - Go: https://go.dev/dl/
# - Terraform: https://www.terraform.io/downloads
# - AWS CLI: https://aws.amazon.com/cli/
```

### AWS Account Requirements

- **Active AWS Account** with permissions to create:
  - Lambda functions
  - SQS queues
  - SNS topics
  - IAM roles and policies
  - EventBridge rules
  - CloudWatch alarms
  - CloudWatch Log groups

- **Test Account Recommended**: Use a dedicated test/sandbox AWS account to avoid conflicts with production resources

## Setup Instructions

### 1. Clone the Repository

```bash
git clone https://github.com/your-org/terraform-aws-sp-autopilot.git
cd terraform-aws-sp-autopilot/test
```

### 2. Download Go Dependencies

```bash
# Navigate to test directory
cd test

# Download and verify Go modules
go mod download
go mod verify
```

**Alternative: Use Helper Scripts**

If you encounter issues or prefer a guided setup, use the provided helper scripts:

```bash
# Linux/macOS/Git Bash
./generate-go-sum.sh

# Windows PowerShell
.\generate-go-sum.ps1
```

These scripts will:
- Verify Go is installed and accessible
- Download all required modules
- Generate the `go.sum` checksum file
- Provide next-step guidance

This will install:
- `terratest` v0.46.8 - Testing framework
- `testify` v1.8.4 - Assertion library
- AWS SDK for Go (transitive dependency)

### 3. Verify Installation

```bash
# Check Go version
go version  # Should be 1.21+

# Check Terraform version
terraform version  # Should be 1.6.0+

# Check AWS CLI
aws --version  # Should be 2.x
```

## AWS Credentials Configuration

Terratest requires valid AWS credentials to deploy and test infrastructure. Choose one of the following methods:

### Method 1: Environment Variables (Recommended for CI/CD)

```bash
export AWS_ACCESS_KEY_ID="your-access-key-id"
export AWS_SECRET_ACCESS_KEY="your-secret-access-key"
export AWS_DEFAULT_REGION="us-east-1"

# Optional: Session token for temporary credentials
export AWS_SESSION_TOKEN="your-session-token"
```

**Verify credentials:**
```bash
aws sts get-caller-identity
```

### Method 2: AWS Profile

Configure a named profile in `~/.aws/credentials`:

```ini
[terratest]
aws_access_key_id = your-access-key-id
aws_secret_access_key = your-secret-access-key
region = us-east-1
```

**Use the profile:**
```bash
export AWS_PROFILE=terratest
go test -v -timeout 30m
```

### Method 3: AWS SSO

```bash
# Configure SSO
aws configure sso

# Login to SSO session
aws sso login --profile my-sso-profile

# Use the SSO profile
export AWS_PROFILE=my-sso-profile
go test -v -timeout 30m
```

### Method 4: IAM Role (EC2/ECS/Lambda)

If running tests from an EC2 instance, ECS task, or Lambda function with an attached IAM role, credentials will be automatically obtained from the instance metadata service. No additional configuration needed.

### Required IAM Permissions

The AWS credentials must have the following permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "lambda:*",
        "sqs:*",
        "sns:*",
        "iam:*",
        "events:*",
        "cloudwatch:*",
        "logs:*",
        "ce:GetSavingsPlansPurchaseRecommendation",
        "ce:GetSavingsPlansUtilization",
        "ce:GetSavingsPlansCoverage",
        "ce:GetCostAndUsage",
        "savingsplans:Describe*"
      ],
      "Resource": "*"
    }
  ]
}
```

> **Note:** For production use, restrict permissions to specific resource ARNs and use least privilege principle.

## Running Tests Locally

### Performance Measurement

To measure test execution time and validate performance targets:

**Linux/macOS/Git Bash:**
```bash
cd test

# Measure performance with detailed report
./measure-performance.sh

# Save performance report for tracking
./measure-performance.sh --save

# Compare with previous run
./measure-performance.sh --compare
```

**Windows PowerShell:**
```powershell
cd test

# Measure performance with detailed report
.\measure-performance.ps1

# Save performance report for tracking
.\measure-performance.ps1 -Save

# Compare with previous run
.\measure-performance.ps1 -Compare
```

**Target**: Full test suite completes in under 15 minutes (900 seconds)

See [PERFORMANCE.md](./PERFORMANCE.md) for detailed performance documentation, benchmarks, and optimization tips.

### Recommended: Use Test Runner Scripts

For the easiest experience, use the provided test runner scripts which validate prerequisites, download dependencies automatically, and provide clear error messages:

**Linux/macOS/Git Bash:**
```bash
cd test

# Run all tests
./run-test.sh

# Run specific test
./run-test.sh TestTerraformBasicDeployment

# Run with verbose output
./run-test.sh --verbose

# Custom timeout
./run-test.sh --timeout 45m
```

**Windows PowerShell:**
```powershell
cd test

# Run all tests
.\run-test.ps1

# Run specific test
.\run-test.ps1 -TestName TestTerraformBasicDeployment

# Run with verbose output
.\run-test.ps1 -Verbose

# Custom timeout
.\run-test.ps1 -Timeout "45m"
```

**What the scripts do:**
- ✅ Verify Go 1.21+ is installed
- ✅ Check Terraform is available
- ✅ Validate AWS credentials are configured
- ✅ Automatically download dependencies if needed
- ✅ Run tests with proper timeout and error handling
- ✅ Provide clear error messages and troubleshooting guidance

### Alternative: Run Tests Directly with Go

### Run All Tests

Execute the complete test suite (takes ~15 minutes):

```bash
cd test
go test -v -timeout 30m
```

**Expected output:**
```
=== RUN   TestTerraformBasicDeployment
=== PAUSE TestTerraformBasicDeployment
=== RUN   TestSQSQueueConfiguration
=== PAUSE TestSQSQueueConfiguration
...
--- PASS: TestTerraformBasicDeployment (245.32s)
--- PASS: TestSQSQueueConfiguration (198.45s)
...
PASS
ok      terraform-aws-sp-autopilot/test    891.234s
```

### Run Specific Test

Run a single test by name:

```bash
# Run basic deployment test
go test -v -run TestTerraformBasicDeployment -timeout 10m

# Run SQS configuration test
go test -v -run TestSQSQueueConfiguration -timeout 5m

# Run Lambda deployment test
go test -v -run TestLambdaDeployment -timeout 10m

# Run end-to-end test
go test -v -run TestFullDeploymentAndCleanup -timeout 15m
```

### Run Tests with Pattern Matching

Run all Lambda-related tests:

```bash
go test -v -run TestLambda -timeout 15m
```

This will execute:
- `TestLambdaDeployment`
- `TestLambdaIAMPermissions`
- `TestSchedulerLambdaInvocation`

### Run Tests in Parallel

Terratest tests use `t.Parallel()` to run concurrently (except `TestFullDeploymentAndCleanup`):

```bash
# Tests will automatically run in parallel
go test -v -timeout 30m -parallel 4
```

> **Warning:** Running multiple tests in parallel will create multiple AWS resources simultaneously, increasing costs. Use with caution.

### Verbose Output

For detailed debugging information:

```bash
# Maximum verbosity
go test -v -timeout 30m

# With test binary output
go test -v -timeout 30m 2>&1 | tee test-output.log
```

### Clean Test Run

Clear Go test cache before running:

```bash
go clean -testcache
go test -v -timeout 30m
```

## Test Descriptions

### TestTerraformBasicDeployment

**Duration:** ~4 minutes
**Purpose:** Validates successful deployment of all core resources

**What it tests:**
- ✅ SQS queue and DLQ creation
- ✅ SNS topic and email subscriptions
- ✅ Lambda functions (Scheduler and Purchaser)
- ✅ IAM roles and policies
- ✅ EventBridge scheduled rules
- ✅ CloudWatch alarms
- ✅ Module configuration outputs

**Use case:** Quick validation that module deploys successfully

```bash
go test -v -run TestTerraformBasicDeployment -timeout 10m
```

---

### TestSQSQueueConfiguration

**Duration:** ~3 minutes
**Purpose:** Validates SQS queue attributes and redrive policy

**What it tests:**
- ✅ DLQ message retention period (14 days)
- ✅ Main queue visibility timeout (5 minutes)
- ✅ Redrive policy configuration (maxReceiveCount=3)
- ✅ DLQ ARN mapping correctness

**Use case:** Verify queue configuration matches module specifications

```bash
go test -v -run TestSQSQueueConfiguration -timeout 5m
```

---

### TestSNSTopicConfiguration

**Duration:** ~3 minutes
**Purpose:** Validates SNS topic and email subscription setup

**What it tests:**
- ✅ SNS topic display name
- ✅ Email subscription protocol
- ✅ Multiple email subscription support
- ✅ Subscription-to-topic association

**Use case:** Verify notification system is correctly configured

```bash
go test -v -run TestSNSTopicConfiguration -timeout 5m
```

---

### TestLambdaDeployment

**Duration:** ~4 minutes
**Purpose:** Validates Lambda function deployment configuration

**What it tests:**
- ✅ Python 3.11 runtime
- ✅ Handler configuration (handler.handler)
- ✅ Timeout (300 seconds)
- ✅ Memory allocation (≥256 MB)
- ✅ IAM role attachment
- ✅ Environment variables (all 15+ required vars)
- ✅ Environment variable value correctness

**Use case:** Verify Lambda functions are deployed with correct configuration

```bash
go test -v -run TestLambdaDeployment -timeout 10m
```

---

### TestSchedulerLambdaInvocation

**Duration:** ~4 minutes
**Purpose:** Validates Scheduler Lambda invocation in dry-run mode

**What it tests:**
- ✅ Lambda invocation returns status 200
- ✅ No function errors
- ✅ Valid JSON response payload
- ✅ Dry-run mode: no messages queued to SQS
- ✅ Execution logs are generated

**Use case:** Verify Scheduler Lambda executes successfully without side effects

```bash
go test -v -run TestSchedulerLambdaInvocation -timeout 10m
```

---

### TestLambdaIAMPermissions

**Duration:** ~3 minutes
**Purpose:** Validates IAM roles and policies with principle of least privilege

**What it tests:**
- ✅ Scheduler Lambda role has correct policies (CloudWatch Logs, Cost Explorer, SQS, SNS, Savings Plans)
- ✅ Purchaser Lambda role has correct policies
- ✅ CloudWatch Logs permissions (CreateLogStream, PutLogEvents)
- ✅ Cost Explorer permissions (GetSavingsPlansPurchaseRecommendation, etc.)
- ✅ SQS permissions (Scheduler: SendMessage, Purchaser: ReceiveMessage)
- ✅ Savings Plans permissions (Scheduler: Describe only, Purchaser: CreateSavingsPlan)
- ✅ Least privilege validation (no excessive permissions)

**Use case:** Security audit of Lambda IAM permissions

```bash
go test -v -run TestLambdaIAMPermissions -timeout 5m
```

---

### TestEventBridgeSchedules

**Duration:** ~3 minutes
**Purpose:** Validates EventBridge scheduled rule configuration

**What it tests:**
- ✅ Rule state is ENABLED
- ✅ Cron schedule expressions are correct
- ✅ Rule descriptions reference correct Lambda functions
- ✅ Lambda targets are correctly mapped
- ✅ Scheduler and Purchaser schedules are different (prevent concurrent execution)

**Use case:** Verify automation scheduling is correctly configured

```bash
go test -v -run TestEventBridgeSchedules -timeout 5m
```

---

### TestFullDeploymentAndCleanup

**Duration:** ~7 minutes
**Purpose:** End-to-end integration test of complete module lifecycle

**What it tests:**
- ✅ **Phase 1:** Infrastructure deployment
- ✅ **Phase 2:** Comprehensive resource validation (all resource types)
- ✅ **Phase 3:** Functional testing (Lambda invocation, dry-run verification)
- ✅ **Phase 4:** Cleanup validation (resource identifiers available for destruction)

**Use case:** Complete end-to-end validation before release

**Note:** This test does NOT run in parallel to ensure sequential lifecycle validation

```bash
go test -v -run TestFullDeploymentAndCleanup -timeout 15m
```

---

## CI/CD Integration

### GitHub Actions

The repository includes a GitHub Actions workflow at `.github/workflows/terratest.yml` that automatically runs tests on:

- **Pull requests** to `main` or `develop` branches
- **Manual workflow dispatch** with optional test filtering

**Workflow features:**
- ✅ Go 1.21 setup with dependency caching
- ✅ Terraform 1.6.0 installation
- ✅ AWS credentials from GitHub secrets
- ✅ Automatic cleanup on failure
- ✅ PR comments with test results

### Required GitHub Secrets

Configure the following secrets in your repository:

| Secret Name | Description |
|------------|-------------|
| `AWS_ACCESS_KEY_ID` | AWS access key for test account |
| `AWS_SECRET_ACCESS_KEY` | AWS secret key for test account |

**Configure secrets:**
1. Navigate to repository **Settings** → **Secrets and variables** → **Actions**
2. Click **New repository secret**
3. Add `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`

### Manual Workflow Trigger

Run tests manually with custom parameters:

1. Navigate to **Actions** tab in GitHub
2. Select **Terratest Integration Tests** workflow
3. Click **Run workflow**
4. Optionally specify:
   - **Test filter pattern** (e.g., `TestLambda`)
   - **AWS region** (default: `us-east-1`)

### Local CI Simulation

Simulate the GitHub Actions workflow locally:

```bash
# Set up environment
export GO_VERSION=1.21
export TERRAFORM_VERSION=1.6.0
export AWS_DEFAULT_REGION=us-east-1

# Verify AWS credentials
aws sts get-caller-identity

# Download Go modules
cd test
go mod download
go mod verify

# Run tests
go test -v -timeout 30m
```

## Troubleshooting

### Common Issues

#### 1. AWS Credentials Error

**Error:**
```
Error: error configuring Terraform AWS Provider: no valid credential sources for Terraform AWS Provider found
```

**Solution:**
```bash
# Verify credentials are set
aws sts get-caller-identity

# Check environment variables
echo $AWS_ACCESS_KEY_ID
echo $AWS_SECRET_ACCESS_KEY
echo $AWS_DEFAULT_REGION

# If using profile, ensure it's exported
export AWS_PROFILE=your-profile-name
```

---

#### 2. Test Timeout

**Error:**
```
panic: test timed out after 10m0s
```

**Solution:**
```bash
# Increase timeout for long-running tests
go test -v -run TestFullDeploymentAndCleanup -timeout 30m

# Or increase timeout for all tests
go test -v -timeout 45m
```

---

#### 3. Resource Already Exists

**Error:**
```
Error: error creating Lambda function: ResourceConflictException: Function already exists
```

**Solution:**
```bash
# Clean up orphaned resources from previous failed test
cd test/fixtures/basic
terraform destroy -auto-approve

# Or use AWS Console to manually delete resources with prefix "sp-autopilot-test"
```

---

#### 4. Insufficient IAM Permissions

**Error:**
```
Error: error creating IAM role: AccessDenied: User is not authorized to perform: iam:CreateRole
```

**Solution:**
- Ensure your AWS credentials have the [required IAM permissions](#required-iam-permissions)
- Contact your AWS administrator to grant necessary permissions
- Use an AWS account where you have administrative access for testing

---

#### 5. Go Module Download Failure

**Error:**
```
go: github.com/gruntwork-io/terratest@v0.46.8: Get "https://proxy.golang.org/...": dial tcp: lookup proxy.golang.org: no such host
```

**Solution:**
```bash
# Check internet connectivity
ping proxy.golang.org

# Clear Go module cache
go clean -modcache

# Try downloading again
go mod download

# If behind corporate proxy, configure GOPROXY
export GOPROXY=https://your-corporate-proxy.com,direct
```

---

#### 6. Terraform Not Found

**Error:**
```
exec: "terraform": executable file not found in $PATH
```

**Solution:**
```bash
# Verify Terraform installation
which terraform
terraform version

# Install Terraform if missing
# macOS
brew install terraform

# Linux
wget https://releases.hashicorp.com/terraform/1.6.0/terraform_1.6.0_linux_amd64.zip
unzip terraform_1.6.0_linux_amd64.zip
sudo mv terraform /usr/local/bin/

# Windows
choco install terraform
```

---

#### 7. Test Cache Issues

**Error:**
```
Tests pass locally but fail in CI, or vice versa
```

**Solution:**
```bash
# Clear test cache
go clean -testcache

# Clear build cache
go clean -cache

# Re-run tests
go test -v -timeout 30m
```

---

#### 8. Parallel Test Conflicts

**Error:**
```
Error: error creating SQS queue: QueueAlreadyExists
```

**Solution:**
```bash
# Run tests sequentially
go test -v -timeout 30m -parallel 1

# Or run specific test in isolation
go test -v -run TestSQSQueueConfiguration -timeout 5m
```

---

### Debug Mode

Enable detailed Terraform logging for debugging:

```bash
# Enable Terraform debug logs
export TF_LOG=DEBUG
export TF_LOG_PATH=./terraform-debug.log

# Run test
go test -v -run TestTerraformBasicDeployment -timeout 10m

# Review logs
cat terraform-debug.log
```

### Clean Up Orphaned Resources

If tests fail and leave resources in AWS:

```bash
# Option 1: Terraform destroy
cd test/fixtures/basic
terraform init
terraform destroy -auto-approve

# Option 2: AWS CLI cleanup (replace with your prefix)
aws sqs delete-queue --queue-url $(aws sqs list-queues --queue-name-prefix sp-autopilot | jq -r '.QueueUrls[0]')
aws sns delete-topic --topic-arn $(aws sns list-topics | jq -r '.Topics[] | select(.TopicArn | contains("sp-autopilot")) | .TopicArn')
aws lambda delete-function --function-name sp-autopilot-scheduler-test
aws lambda delete-function --function-name sp-autopilot-purchaser-test

# Option 3: Use AWS Console
# Navigate to each service and delete resources with "sp-autopilot" prefix
```

### Getting Help

- **Terratest Documentation:** https://terratest.gruntwork.io/docs/
- **AWS Provider Errors:** https://registry.terraform.io/providers/hashicorp/aws/latest/docs
- **Module Issues:** Open an issue at https://github.com/your-org/terraform-aws-sp-autopilot/issues

## Cost Considerations

### Estimated Test Costs

Running the full test suite once incurs minimal AWS costs:

| Service | Usage | Estimated Cost |
|---------|-------|----------------|
| Lambda | ~10 invocations × 256MB × 5s | $0.000001 |
| SQS | ~100 requests | $0.00004 |
| SNS | ~10 notifications | $0.0005 |
| CloudWatch Logs | ~10 MB | $0.005 |
| EventBridge | ~5 rule evaluations | $0.00 (free tier) |
| **Total per test run** | | **~$0.01** |

**Notes:**
- Free tier covers most usage
- Tests clean up all resources after completion
- No long-running resources (Lambda, queues are ephemeral)
- Costs may vary by region

### Cost Optimization Tips

1. **Use AWS Free Tier:** Run tests in a new AWS account to maximize free tier benefits
2. **Run Tests Selectively:** Use `-run` flag to run only necessary tests during development
3. **Avoid Parallel Runs:** Running tests in parallel increases resource usage
4. **Monitor Test Failures:** Failed tests may leave orphaned resources that continue to incur costs
5. **Set Billing Alerts:** Configure AWS Budgets to alert on unexpected costs

---

## Contributing

When adding new tests:

1. Follow existing test patterns and naming conventions
2. Use `t.Parallel()` for independent tests
3. Add comprehensive assertions with descriptive messages
4. Include cleanup with `defer terraform.Destroy()`
5. Update this README with test descriptions
6. Ensure tests pass locally before opening a PR

---

**Last Updated:** 2026-01-14
**Terratest Version:** v0.46.8
**Go Version:** 1.21+
**Terraform Version:** 1.6.0+

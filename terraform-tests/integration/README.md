# Terratest Integration Tests

Comprehensive integration tests for the AWS Savings Plans Automation module using [Terratest](https://terratest.gruntwork.io/). Tests validate complete module deployment, resource creation, Lambda execution, and cleanup in a real AWS account.

## Prerequisites

| Tool | Minimum Version | Installation |
|------|----------------|--------------|
| **Go** | 1.21+ | `brew install go` (macOS) / [go.dev/dl](https://go.dev/dl/) |
| **Terraform** | 1.6.0+ | `brew install terraform` (macOS) / [terraform.io](https://www.terraform.io/downloads) |
| **AWS CLI** | 2.x | `brew install awscli` (macOS) / [AWS CLI](https://aws.amazon.com/cli/) |

**AWS Account:** Active account with permissions to create Lambda, SQS, SNS, IAM, EventBridge, and CloudWatch resources. Use a dedicated test/sandbox account.

## Setup

### 1. Clone Repository

```bash
git clone https://github.com/your-org/terraform-aws-sp-autopilot.git
cd terraform-aws-sp-autopilot/test
```

### 2. Download Dependencies

```bash
go mod download
go mod verify
```

**Helper Scripts** (if needed):

```bash
# Linux/macOS/Git Bash
./generate-go-sum.sh

# Windows PowerShell
.\generate-go-sum.ps1
```

### 3. Verify Installation

```bash
go version      # Should be 1.21+
terraform version  # Should be 1.6.0+
aws --version   # Should be 2.x
```

## AWS Credentials

Choose one method:

### Environment Variables (CI/CD)

```bash
export AWS_ACCESS_KEY_ID="your-access-key-id"
export AWS_SECRET_ACCESS_KEY="your-secret-access-key"
export AWS_DEFAULT_REGION="us-east-1"

# Verify
aws sts get-caller-identity
```

### AWS Profile

```bash
export AWS_PROFILE=terratest
go test -v -timeout 30m
```

### AWS SSO

```bash
aws configure sso
aws sso login --profile my-sso-profile
export AWS_PROFILE=my-sso-profile
```

**Required IAM Permissions:** `lambda:*`, `sqs:*`, `sns:*`, `iam:*`, `events:*`, `cloudwatch:*`, `logs:*`, `ce:Get*`, `savingsplans:Describe*`

## Running Tests

### Recommended: Use Test Runner Scripts

**Linux/macOS/Git Bash:**

```bash
./run-test.sh                  # Run all tests
./run-test.sh TestTerraformBasicDeployment  # Run specific test
./run-test.sh --verbose        # Verbose output
./run-test.sh --timeout 45m    # Custom timeout
```

**Windows PowerShell:**

```powershell
.\run-test.ps1                 # Run all tests
.\run-test.ps1 -TestName TestTerraformBasicDeployment
.\run-test.ps1 -Verbose
.\run-test.ps1 -Timeout "45m"
```

Scripts automatically verify prerequisites, download dependencies, and provide clear error messages.

### Alternative: Direct Go Execution

```bash
# Run all tests (~15 minutes)
go test -v -timeout 30m

# Run specific test
go test -v -run TestTerraformBasicDeployment -timeout 10m

# Run with pattern matching
go test -v -run TestLambda -timeout 15m

# Clean cache first
go clean -testcache
go test -v -timeout 30m
```

### Performance Measurement

```bash
# Linux/macOS
./measure-performance.sh
./measure-performance.sh --save
./measure-performance.sh --compare

# Windows
.\measure-performance.ps1
.\measure-performance.ps1 -Save
.\measure-performance.ps1 -Compare
```

**Target:** Full test suite completes in under 15 minutes (900 seconds). See [PERFORMANCE.md](./PERFORMANCE.md) for details.

## Test Descriptions

### TestTerraformBasicDeployment (~4 min)

Validates successful deployment of all core resources: SQS, SNS, Lambda, IAM, EventBridge, CloudWatch.

```bash
go test -v -run TestTerraformBasicDeployment -timeout 10m
```

### TestSQSQueueConfiguration (~3 min)

Validates SQS queue attributes: DLQ retention (14 days), visibility timeout (5 min), redrive policy (maxReceiveCount=3).

### TestSNSTopicConfiguration (~3 min)

Validates SNS topic and email subscriptions: display name, protocol, multi-email support.

### TestLambdaDeployment (~4 min)

Validates Lambda configuration: Python 3.11 runtime, handler, timeout (300s), memory (≥256MB), IAM role, environment variables.

### TestSchedulerLambdaInvocation (~4 min)

Validates Scheduler Lambda execution: status 200, no errors, valid JSON response, dry-run mode (no SQS messages).

### TestLambdaIAMPermissions (~3 min)

Validates IAM roles and policies: CloudWatch Logs, Cost Explorer, SQS, SNS, Savings Plans permissions with least privilege.

### TestEventBridgeSchedules (~3 min)

Validates EventBridge rules: ENABLED state, correct cron expressions, Lambda targets, different scheduler/purchaser schedules.

### TestFullDeploymentAndCleanup (~7 min)

End-to-end integration test: infrastructure deployment, resource validation, functional testing, cleanup verification. Does NOT run in parallel.

```bash
go test -v -run TestFullDeploymentAndCleanup -timeout 15m
```

## CI/CD Integration

### GitHub Actions

Workflow at `.github/workflows/terratest.yml` runs tests on:
- Pull requests to `main` or `develop`
- Manual workflow dispatch with optional test filtering

**Required GitHub Secrets:**
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`

Configure: Repository Settings → Secrets and variables → Actions → New repository secret

### Manual Workflow Trigger

1. Actions tab → Terratest Integration Tests → Run workflow
2. Specify test filter pattern (e.g., `TestLambda`) and AWS region

## Troubleshooting

### AWS Credentials Error

```bash
# Verify credentials
aws sts get-caller-identity
echo $AWS_ACCESS_KEY_ID
echo $AWS_DEFAULT_REGION
export AWS_PROFILE=your-profile-name
```

### Test Timeout

```bash
# Increase timeout
go test -v -run TestFullDeploymentAndCleanup -timeout 30m
```

### Resource Already Exists

```bash
# Clean up orphaned resources
cd test/fixtures/basic
terraform destroy -auto-approve
```

### Insufficient IAM Permissions

Ensure credentials have [required IAM permissions](#aws-credentials).

### Go Module Download Failure

```bash
# Check connectivity
ping proxy.golang.org

# Clear cache
go clean -modcache
go mod download

# Configure proxy
export GOPROXY=https://your-corporate-proxy.com,direct
```

### Terraform Not Found

```bash
# Verify installation
which terraform
terraform version

# Install if missing
brew install terraform  # macOS
```

### Test Cache Issues

```bash
go clean -testcache
go clean -cache
go test -v -timeout 30m
```

### Parallel Test Conflicts

```bash
# Run sequentially
go test -v -timeout 30m -parallel 1
```

### Debug Mode

```bash
export TF_LOG=DEBUG
export TF_LOG_PATH=./terraform-debug.log
go test -v -run TestTerraformBasicDeployment -timeout 10m
cat terraform-debug.log
```

### Clean Up Orphaned Resources

```bash
# Option 1: Terraform
cd test/fixtures/basic
terraform init
terraform destroy -auto-approve

# Option 2: AWS CLI
aws sqs delete-queue --queue-url $(aws sqs list-queues --queue-name-prefix sp-autopilot | jq -r '.QueueUrls[0]')
aws lambda delete-function --function-name sp-autopilot-scheduler-test
```

## Cost Considerations

Running full test suite once: **~$0.01**

| Service | Usage | Cost |
|---------|-------|------|
| Lambda | ~10 invocations × 256MB × 5s | $0.000001 |
| SQS | ~100 requests | $0.00004 |
| SNS | ~10 notifications | $0.0005 |
| CloudWatch Logs | ~10 MB | $0.005 |
| EventBridge | ~5 evaluations | Free tier |

**Notes:**
- Free tier covers most usage
- Tests clean up all resources after completion
- No long-running resources

**Cost Optimization Tips:**
1. Use AWS Free Tier account
2. Run tests selectively with `-run` flag
3. Avoid parallel runs to reduce resource usage
4. Monitor test failures (orphaned resources)
5. Set AWS Budgets alerts

## Contributing

When adding tests:
1. Follow existing patterns and naming conventions
2. Use `t.Parallel()` for independent tests
3. Add comprehensive assertions with descriptive messages
4. Include cleanup with `defer terraform.Destroy()`
5. Update this README with test descriptions
6. Ensure tests pass locally before opening PR

---

**Last Updated:** 2026-01-14
**Terratest Version:** v0.46.8
**Go Version:** 1.21+
**Terraform Version:** 1.6.0+

For detailed help:
- [Terratest Documentation](https://terratest.gruntwork.io/docs/)
- [AWS Provider Errors](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)
- [Module Issues](https://github.com/your-org/terraform-aws-sp-autopilot/issues)

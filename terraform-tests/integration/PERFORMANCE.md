# Terratest Performance Measurement

This document describes how to measure and track the performance of the Terratest integration test suite for the AWS Savings Plans Automation module.

## Table of Contents

- [Overview](#overview)
- [Performance Target](#performance-target)
- [Measurement Tools](#measurement-tools)
- [Running Performance Tests](#running-performance-tests)
- [Understanding Results](#understanding-results)
- [Performance Benchmarks](#performance-benchmarks)
- [Optimization Tips](#optimization-tips)
- [Troubleshooting Slow Tests](#troubleshooting-slow-tests)

## Overview

The integration test suite includes 7 comprehensive tests that deploy real AWS infrastructure, validate functionality, and clean up resources. Measuring execution time is critical to ensure:

1. **Developer Productivity**: Tests should complete quickly enough for iterative development
2. **CI/CD Efficiency**: Fast tests enable rapid feedback on pull requests
3. **Cost Control**: Longer test runs increase AWS resource costs
4. **Quality Assurance**: Performance regressions may indicate infrastructure issues

## Performance Target

**Target**: Complete all 7 tests in **under 15 minutes (900 seconds)**

This target balances:
- Comprehensive integration testing
- Reasonable CI/CD pipeline duration
- Developer iteration speed
- AWS cost optimization

## Measurement Tools

### 1. Performance Measurement Scripts

Dedicated scripts that run the full test suite with detailed timing:

**Linux/macOS/Git Bash:**
```bash
cd test
./measure-performance.sh
```

**Windows PowerShell:**
```powershell
cd test
.\measure-performance.ps1
```

**Features:**
- ✅ Validates prerequisites (Go, Terraform, AWS credentials)
- ✅ Measures total execution time with start/end timestamps
- ✅ Extracts individual test timings from output
- ✅ Compares against 15-minute performance target
- ✅ Saves detailed results to `test-results.log`
- ✅ Optionally generates performance report for tracking

### 2. Manual Timing with `time` Command

For quick measurements without scripts:

**Linux/macOS/Git Bash:**
```bash
cd test
time go test -v -timeout 30m | tee test-results.log
```

**Windows PowerShell:**
```powershell
cd test
Measure-Command { go test -v -timeout 30m | Tee-Object -FilePath test-results.log }
```

### 3. Go Built-in Timing

Go test framework automatically reports individual test durations:

```bash
go test -v -timeout 30m
```

Example output:
```
--- PASS: TestTerraformBasicDeployment (245.32s)
--- PASS: TestSQSQueueConfiguration (198.45s)
--- PASS: TestLambdaDeployment (234.12s)
...
PASS
ok      terraform-aws-sp-autopilot/test    891.234s
```

## Running Performance Tests

### Quick Measurement

Run the performance script to get a complete measurement:

```bash
# Linux/macOS/Git Bash
./measure-performance.sh

# Windows PowerShell
.\measure-performance.ps1
```

**Output:**
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Terratest Performance Measurement
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

This script measures the execution time of the full Terratest suite
Target: Complete all 7 tests in under 15 minutes (900 seconds)

▶ Checking prerequisites...
✓ Go 1.21.5
✓ Terraform 1.6.0
✓ AWS credentials configured

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Running Full Test Suite
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[Test output...]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Performance Summary
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Start Time:                        2026-01-14 10:00:00
End Time:                          2026-01-14 10:12:45
Total Duration:                    12m 45s (765 seconds)

✓ Performance target MET! ✓
Target:                            < 15 minutes (900 seconds)
Under target by:                   2m 15s

✓ All tests PASSED
```

### Save Performance Report

Save results for tracking over time:

```bash
# Linux/macOS/Git Bash
./measure-performance.sh --save

# Windows PowerShell
.\measure-performance.ps1 -Save
```

This creates `performance-report.txt` with:
- Execution date and environment details
- Total duration and target comparison
- Individual test timings
- Pass/fail status

### Compare with Previous Run

Compare against the last saved report:

```bash
# Linux/macOS/Git Bash
./measure-performance.sh --compare

# Windows PowerShell
.\measure-performance.ps1 -Compare
```

## Understanding Results

### Total Duration

The most important metric - total time from test start to completion:

```
Total Duration: 12m 45s (765 seconds)
```

**Good**: < 900 seconds (15 minutes) ✓
**Warning**: 900-1200 seconds (15-20 minutes) ⚠️
**Bad**: > 1200 seconds (20+ minutes) ✗

### Individual Test Timings

Each test's duration helps identify bottlenecks:

```
✓ TestTerraformBasicDeployment        245.32s
✓ TestSQSQueueConfiguration           198.45s
✓ TestSNSTopicConfiguration           189.23s
✓ TestLambdaDeployment                234.12s
✓ TestSchedulerLambdaInvocation       187.56s
✓ TestLambdaIAMPermissions            195.34s
✓ TestEventBridgeSchedules            178.92s
```

**Typical breakdown:**
- Resource-heavy tests (Lambda, full deployment): 200-300s
- Configuration tests (SQS, SNS, IAM): 150-250s
- Validation tests (EventBridge): 150-200s

### Parallel Execution

Tests use `t.Parallel()` to run concurrently (except `TestFullDeploymentAndCleanup`):

```bash
go test -v -timeout 30m -parallel 4
```

**Note**: Parallelism can reduce total time but increases AWS resource usage and costs.

### Performance Factors

Test execution time varies based on:

1. **AWS Region**: Some regions have faster provisioning times
   - Fastest: us-east-1, us-west-2
   - Slower: eu-north-1, ap-southeast-3

2. **Network Latency**: Distance to AWS region affects Terraform API calls

3. **AWS Service Performance**: Service provisioning times vary
   - Fast: Lambda, SQS, SNS (seconds)
   - Medium: IAM, EventBridge (10-30 seconds)
   - Slow: CloudWatch Alarms (30-60 seconds)

4. **Go/Terraform Versions**: Newer versions may have performance improvements

5. **System Resources**: CPU, memory, network bandwidth

6. **AWS Account Limits**: Throttling if limits are approached

## Performance Benchmarks

### Expected Performance

Based on typical execution in `us-east-1`:

| Test | Expected Duration | Description |
|------|-------------------|-------------|
| TestTerraformBasicDeployment | 200-300s | Full infrastructure deployment |
| TestSQSQueueConfiguration | 150-250s | Queue attributes validation |
| TestSNSTopicConfiguration | 150-250s | Topic and subscription validation |
| TestLambdaDeployment | 200-300s | Lambda configuration validation |
| TestSchedulerLambdaInvocation | 150-250s | Lambda execution validation |
| TestLambdaIAMPermissions | 150-250s | IAM policy validation |
| TestEventBridgeSchedules | 150-200s | EventBridge rule validation |
| **Total (with parallelism)** | **700-900s** | **11-15 minutes** |

### Baseline Performance

To establish a baseline for your environment:

1. Run performance measurement 3 times:
   ```bash
   ./measure-performance.sh --save
   # Wait, then run again
   ./measure-performance.sh --save
   # Wait, then run again
   ./measure-performance.sh --save
   ```

2. Calculate average duration:
   ```bash
   # Example: 765s, 782s, 758s
   # Average: 768.3 seconds (~12.8 minutes)
   ```

3. Use this as your baseline for detecting regressions

### Performance Regression Detection

Compare new runs against baseline:

- **< 5% slower**: Normal variance ✓
- **5-10% slower**: Investigate potential issues ⚠️
- **> 10% slower**: Performance regression - investigate! ✗

Example:
- Baseline: 768s
- New run: 845s
- Change: +77s (+10%)
- **Action**: Investigate slow tests

## Optimization Tips

### 1. Use Faster AWS Region

Deploy tests to the geographically closest AWS region:

```bash
export AWS_DEFAULT_REGION=us-east-1  # Usually fastest
go test -v -timeout 30m
```

### 2. Run Tests in Parallel

Enable parallel execution (increases costs):

```bash
go test -v -timeout 30m -parallel 4
```

**Warning**: This creates multiple AWS resource sets simultaneously.

### 3. Run Specific Tests During Development

Avoid running the full suite during active development:

```bash
# Run only the test you're working on
go test -v -run TestTerraformBasicDeployment -timeout 10m
```

### 4. Use Go Test Caching

Go caches test results for unchanged tests:

```bash
# First run: Full execution
go test -v -timeout 30m

# Second run: Cached (instant)
go test -v -timeout 30m

# Clear cache to force re-run
go clean -testcache
```

**Note**: Terratest tests are typically never cached because they create real resources.

### 5. Optimize Terraform Operations

In test fixtures, use `-parallelism` flag:

```go
terraform.InitAndApply(t, &terraform.Options{
    TerraformDir: fixturePath,
    Parallelism:  10,  // Increase parallelism
})
```

### 6. Reduce Terraform Retries

For faster failures during development:

```go
terraform.InitAndApply(t, &terraform.Options{
    TerraformDir: fixturePath,
    MaxRetries:   1,      // Reduce retries
    TimeBetweenRetries: 2 * time.Second,
})
```

**Warning**: Only use this during development, not in CI/CD.

### 7. Pre-warm Go Modules

Download dependencies before timing:

```bash
go mod download
go mod verify
time go test -v -timeout 30m
```

## Troubleshooting Slow Tests

### Identify Slow Tests

Run with verbose output to see individual timings:

```bash
go test -v -timeout 30m | grep "^--- PASS:"
```

### Debug Slow Test

Enable Terraform debug logging:

```bash
export TF_LOG=DEBUG
export TF_LOG_PATH=./terraform-debug.log
go test -v -run TestSlowTest -timeout 10m
```

Review `terraform-debug.log` for slow operations.

### Common Causes of Slowness

1. **Network Issues**
   - Check internet connectivity
   - Verify AWS region latency: `ping dynamodb.us-east-1.amazonaws.com`

2. **AWS Service Throttling**
   - Review CloudTrail logs for throttling errors
   - Increase time between API calls

3. **Resource Dependencies**
   - Some resources wait for others (e.g., Lambda needs IAM role)
   - Terraform parallelism may help

4. **CloudWatch Alarm Delays**
   - Alarms can take 60+ seconds to create
   - Consider removing alarm tests during development

5. **Terraform State Locking**
   - Check for stuck state locks
   - Clear locks: `terraform force-unlock <lock-id>`

### Performance Testing Checklist

Before reporting performance issues:

- [ ] Run tests 3 times to establish baseline
- [ ] Try a different AWS region (us-east-1 recommended)
- [ ] Clear Go test cache: `go clean -testcache`
- [ ] Update Go to latest 1.21+ version
- [ ] Update Terraform to latest 1.6+ version
- [ ] Check AWS service health: https://status.aws.amazon.com/
- [ ] Verify no AWS throttling in CloudTrail logs
- [ ] Check system resources (CPU, memory, network)

---

## Example Performance Report

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Terratest Performance Report
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Execution Date:    2026-01-14 10:00:00
Go Version:        1.21.5
Terraform Version: 1.6.0

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Performance Metrics
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Total Duration:    12m 45s (765 seconds)
Target Duration:   15 minutes (900 seconds)
Status:            PASS ✓
Test Result:       PASS ✓

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Individual Test Timings
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✓ TestTerraformBasicDeployment        245.32s
✓ TestSQSQueueConfiguration           198.45s
✓ TestSNSTopicConfiguration           189.23s
✓ TestLambdaDeployment                234.12s
✓ TestSchedulerLambdaInvocation       187.56s
✓ TestLambdaIAMPermissions            195.34s
✓ TestEventBridgeSchedules            178.92s

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Full test output saved to: test-results.log
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## Contributing

When making changes that might affect test performance:

1. Run performance measurement before changes
2. Make your changes
3. Run performance measurement after changes
4. Compare results and document any significant changes (> 5%)
5. Include performance notes in pull request description

---

**Last Updated:** 2026-01-14
**Target Performance:** < 15 minutes (900 seconds)
**Typical Performance:** 12-13 minutes in us-east-1

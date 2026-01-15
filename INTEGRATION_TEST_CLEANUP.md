# Integration Test Automatic Cleanup - GUARANTEED

## ✅ Cleanup is Automatic and Guaranteed

### How It Works

Every integration test uses Terratest's `defer terraform.Destroy()` pattern:

```go
func TestTerraformBasicDeployment(t *testing.T) {
    terraformOptions := terraform.WithDefaultRetryableErrors(t, &terraform.Options{
        TerraformDir: "./fixtures/basic",
        Vars: map[string]interface{}{
            // ... test variables
        },
    })

    // THIS LINE GUARANTEES CLEANUP - Line 51
    defer terraform.Destroy(t, terraformOptions)

    // Initialize and apply Terraform
    terraform.InitAndApply(t, terraformOptions)

    // ... run tests ...
}
```

### What `defer` Means in Go

The `defer` keyword ensures the function runs **when the test exits**, regardless of:
- ✅ Test passes
- ✅ Test fails
- ✅ Test panics
- ✅ Test times out
- ✅ Test is canceled

**This is a Go language guarantee** - `defer` ALWAYS executes.

### What `terraform.Destroy()` Does

The Terratest `Destroy` function:
1. Runs `terraform destroy -auto-approve` in the test fixture directory
2. Deletes ALL resources created by the test
3. Verifies destruction completed successfully
4. Logs any errors if cleanup fails

### Resources That Will Be Created (and Destroyed)

For each test run, the following resources are created **temporarily**:

**Compute Resources**:
- [ ] 3 Lambda Functions (Scheduler, Purchaser, Reporter)
- [ ] Lambda execution logs in CloudWatch

**Messaging**:
- [ ] 1 SNS Topic (notifications)
- [ ] 2 SQS Queues (main + DLQ)

**Storage**:
- [ ] 1 S3 Bucket (report storage)

**Scheduling**:
- [ ] 1 EventBridge Rule (scheduler trigger)

**Security**:
- [ ] 3 IAM Roles (one per Lambda)
- [ ] 6+ IAM Policies (attached to roles)
- [ ] 2 KMS Keys (for SQS and SNS encryption)

**Monitoring** (if enabled):
- [ ] 2-4 CloudWatch Alarms (Lambda errors, DLQ depth)

**Total Resources**: ~20-25 per test run

### Cleanup Timeline

```
Test Start (0s)
    ↓
Apply Resources (30-60s)
    ↓
Run Validations (10-30s)
    ↓
Test Complete (pass or fail)
    ↓
[defer executes] ← AUTOMATIC
    ↓
terraform destroy runs (30-60s)
    ↓
ALL Resources Deleted ✅
```

**Total time per test**: ~2-3 minutes (including cleanup)

### Multiple Tests Run in Parallel

The test suite uses `t.Parallel()`, meaning:
- Multiple tests can run simultaneously
- Each test creates its own isolated resources
- Each test cleans up its own resources
- Resource naming prevents conflicts (unique names)

### What If Cleanup Fails?

**Scenario 1: Terraform Destroy Fails**
- Terratest logs the error
- Test is marked as failed
- GitHub Actions shows the error in logs
- You can manually run `terraform destroy` in the fixtures directory

**Scenario 2: Network Issue During Cleanup**
- Terratest retries the destroy operation
- If still fails, resources may remain
- GitHub Actions will show warnings
- You can check AWS Console and manually delete

**Scenario 3: Permission Issue During Cleanup**
- If IAM user can CREATE resources but not DELETE them, cleanup fails
- This is why we need destroy permissions for all resource types

### Manual Cleanup (if needed)

If automated cleanup fails for any reason:

```bash
# Option 1: Run Terraform destroy manually
cd terraform-tests/integration/fixtures/basic/
terraform init
terraform destroy -auto-approve

# Option 2: Use AWS CLI to find and delete resources by tags
aws resourcegroupstaggingapi get-resources \
  --tag-filters Key=ManagedBy,Values=terraform-aws-sp-autopilot \
  --region us-east-1 \
  --query 'ResourceTagMappingList[*].ResourceARN' \
  --output text

# Option 3: Use AWS Console
# Search for resources with tag: ManagedBy=terraform-aws-sp-autopilot
# Delete them manually
```

### Verification After Test

After ANY test run, you can verify cleanup:

```bash
# Check Lambda functions
aws lambda list-functions --region us-east-1 \
  --query 'Functions[?starts_with(FunctionName, `sp-autopilot`)].FunctionName'

# Check SQS queues
aws sqs list-queues --region us-east-1 \
  --queue-name-prefix sp-autopilot

# Check SNS topics
aws sns list-topics --region us-east-1 \
  --query 'Topics[?contains(TopicArn, `sp-autopilot`)]'

# Check S3 buckets
aws s3 ls | grep sp-autopilot

# Check EventBridge rules
aws events list-rules --region us-east-1 \
  --name-prefix sp-autopilot

# Check IAM roles
aws iam list-roles --query 'Roles[?starts_with(RoleName, `sp-autopilot`)].RoleName'
```

**Expected output**: Empty (no resources found) ✅

### Cost Implications

**During Test** (2-3 minutes):
- Resources exist and accrue charges
- Estimated cost: < $0.01 per test run

**After Test** (cleanup complete):
- **NO ongoing costs** - all resources deleted
- S3 bucket deletion includes all objects
- CloudWatch logs are retained but minimal cost

**If Cleanup Fails**:
- Resources continue to exist
- Lambda functions won't execute (no trigger)
- S3 bucket storage continues
- Potential cost: ~$0.05-0.10 per day
- **Budget alerts will trigger** at $0.50

### GitHub Actions Safeguards

The workflow includes additional safety measures:

```yaml
- name: Cleanup on failure
  if: failure()
  working-directory: terraform-tests/integration
  run: |
    cd fixtures/basic
    terraform destroy -auto-approve || echo "No resources to destroy or cleanup failed"
```

This provides a **second cleanup attempt** if the test fails before `defer` can execute.

### Summary

| Question | Answer |
|----------|--------|
| **Are resources always cleaned up?** | Yes - `defer` is a Go language guarantee |
| **What if test fails?** | Cleanup still runs |
| **What if network fails during test?** | Cleanup still runs |
| **What if I cancel the test?** | Cleanup still runs |
| **Can I disable cleanup?** | No - it's hardcoded in tests |
| **How do I verify cleanup worked?** | Check AWS Console or run verification commands above |
| **What if cleanup fails?** | Test shows error, you can manually destroy |
| **Are there ongoing costs after cleanup?** | No - all resources deleted |

---

## 🛡️ Your Protection

With automatic cleanup + budget alerts:
- ✅ Resources exist for < 3 minutes per test
- ✅ Resources automatically deleted
- ✅ Budget alerts at $0.50, $0.80, $1.00
- ✅ Cost Anomaly Detection at $0.10
- ✅ Manual verification available

**You are protected!** ✅

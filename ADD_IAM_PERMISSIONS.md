# How to Add IAM Permissions for Integration Tests

## Step-by-Step Instructions

### 1. Go to IAM Console
1. Open AWS Console: https://console.aws.amazon.com/iam/
2. Click **"Users"** in the left sidebar
3. Find and click on your user: `sp-autopilot-ci` (or whatever you named it)

### 2. Add Inline Policy

1. Click the **"Permissions"** tab
2. Click **"Add permissions"** → **"Create inline policy"**
3. Click the **"JSON"** tab
4. Delete the example JSON
5. Copy the entire contents of `IAM_MINIMAL_PERMISSIONS.json` (in this directory)
6. Paste it into the JSON editor
7. Click **"Next"**
8. Policy name: `TerraformIntegrationTestPermissions`
9. Click **"Create policy"**

### 3. Verify Permissions Added

You should now see:
- Policy name: `TerraformIntegrationTestPermissions`
- Type: Inline policy
- Attached to: `sp-autopilot-ci`

### What These Permissions Allow

✅ **Create/Delete Resources** (for testing):
- Lambda functions (3)
- IAM roles (3)
- S3 buckets (1)
- SQS queues (2)
- SNS topics (1)
- EventBridge rules (1)
- CloudWatch alarms (2-4)
- CloudWatch log groups
- KMS keys (2)

✅ **Read/List Resources** (for validation):
- All of the above service types

❌ **DENIED** (cost protection):
- EC2 instances
- RDS databases
- Redshift clusters
- ElastiCache clusters
- Elasticsearch domains
- EMR clusters
- SageMaker jobs
- Glue jobs

### Security Features

🔒 **Region Restriction**:
- All actions restricted to `us-east-1` only
- Cannot create resources in other regions

🔒 **Resource Naming**:
- IAM roles must start with `sp-autopilot-*`
- S3 buckets must start with `sp-autopilot-*`
- Prevents accidental modification of other resources

🔒 **Deny List**:
- Explicitly denies expensive services
- Even if permissions accidentally granted, these are blocked

### Next Steps

After adding permissions:

1. **Merge PR #26** (directory refactoring) to main
   - This updates the workflow paths
   - Without this, tests will fail with "directory not found"

2. **Trigger Integration Tests** manually:
   ```bash
   gh workflow run "Terraform Integration Tests"
   ```

3. **Watch the test run**:
   ```bash
   gh run watch --exit-status
   ```

4. **If tests fail with permission errors**:
   - Check the logs for "AccessDenied" or "UnauthorizedOperation"
   - Add ONLY the specific permission that failed
   - Principle of least privilege - add incrementally

5. **After tests complete successfully**:
   - Verify cleanup worked (check AWS Console)
   - Check AWS Billing Dashboard
   - Should show < $0.01 in charges

### Troubleshooting

**"AccessDenied" errors during test**:
- Add the specific permission to the policy
- Re-run the workflow

**"Directory not found" error**:
- PR #26 needs to be merged first
- Or run workflow from `refactor-directory-structure` branch

**Tests pass but resources not cleaned up**:
- Check test logs for `terraform destroy` errors
- Manually run: `cd terraform-tests/integration/fixtures/basic && terraform destroy`
- Verify user has DELETE permissions for all resource types

**Budget alert received**:
- Check AWS Cost Explorer for the service causing charges
- Verify resources were cleaned up
- Check for orphaned resources in AWS Console

### Verification Commands

After tests complete, verify cleanup:

```bash
# Check Lambda functions
aws lambda list-functions --region us-east-1 \
  --query 'Functions[?starts_with(FunctionName, `sp-autopilot`)].FunctionName'

# Check SQS queues
aws sqs list-queues --region us-east-1 --queue-name-prefix sp-autopilot

# Check SNS topics
aws sns list-topics --region us-east-1 \
  --query 'Topics[?contains(TopicArn, `sp-autopilot`)]'

# Check S3 buckets
aws s3 ls | grep sp-autopilot

# Check EventBridge rules
aws events list-rules --region us-east-1 --name-prefix sp-autopilot

# Check IAM roles
aws iam list-roles --query 'Roles[?starts_with(RoleName, `sp-autopilot`)].RoleName'
```

**Expected output**: Empty (no resources found) ✅

---

## Summary

| Step | Action | Status |
|------|--------|--------|
| 1 | Add IAM permissions policy | ⏳ |
| 2 | Merge PR #26 to main | ⏳ |
| 3 | Trigger integration test workflow | ⏳ |
| 4 | Monitor test execution | ⏳ |
| 5 | Verify resource cleanup | ⏳ |
| 6 | Check AWS billing (< $0.01 expected) | ⏳ |

Once all steps complete successfully, integration tests are ready for ongoing use! 🎉

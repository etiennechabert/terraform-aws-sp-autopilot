# IAM Permissions Setup - Under 2048 Character Limit

AWS has a **2048 character limit** for inline IAM policies. We have two options:

---

## ✅ Option 1: Compact Inline Policy (RECOMMENDED for Testing)

**File**: `IAM_MINIMAL_PERMISSIONS_COMPACT.json` (1,095 characters)

This is a simplified policy using wildcards that fits within the 2048 char limit.

### Trade-offs:
- ✅ **Simple**: Single inline policy
- ✅ **Works**: Has all permissions needed for tests
- ⚠️ **Less granular**: Uses wildcards (`lambda:*`, `s3:*`, etc.)
- ✅ **Safe**: Still blocks expensive services
- ✅ **Region-locked**: Only us-east-1

### How to Add:

1. Go to IAM Console: https://console.aws.amazon.com/iam/
2. Click **Users** → Find `sp-autopilot-ci`
3. Click **Permissions** tab → **Add permissions** → **Create inline policy**
4. Click **JSON** tab
5. Copy entire contents of `IAM_MINIMAL_PERMISSIONS_COMPACT.json`
6. Paste into JSON editor
7. Click **Next**
8. Policy name: `TerraformTestPermissions`
9. Click **Create policy**

---

## ✅ Option 2: AWS Managed Policies (More Secure)

Use AWS's pre-built managed policies (don't count against 2048 limit).

### Policies to Attach:

1. **AWSLambda_FullAccess** (managed by AWS)
2. **AmazonS3FullAccess** (managed by AWS)
3. **AmazonSQSFullAccess** (managed by AWS)
4. **AmazonSNSFullAccess** (managed by AWS)
5. **CloudWatchFullAccess** (managed by AWS)
6. **IAMFullAccess** (managed by AWS) - ⚠️ Very powerful
7. **AmazonEventBridgeFullAccess** (managed by AWS)

**PLUS** this small inline policy for KMS and deny rules:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "kms:*",
      "Resource": "*",
      "Condition": {
        "StringEquals": {
          "aws:RequestedRegion": "us-east-1"
        }
      }
    },
    {
      "Effect": "Deny",
      "Action": [
        "ec2:RunInstances",
        "rds:Create*",
        "redshift:Create*",
        "elasticache:Create*"
      ],
      "Resource": "*"
    }
  ]
}
```

### How to Add:

**Attach Managed Policies:**
1. Go to IAM Console → Users → `sp-autopilot-ci`
2. Click **Permissions** → **Add permissions** → **Attach policies directly**
3. Search for and select each managed policy above
4. Click **Add permissions**

**Add Small Inline Policy:**
1. Click **Add permissions** → **Create inline policy**
2. Use JSON above
3. Name: `TestDenyRules`

### Trade-offs:
- ✅ **More secure**: Granular AWS-maintained policies
- ⚠️ **More permissions**: Managed policies are broader
- ✅ **No char limit**: Managed policies don't count
- ⚠️ **More setup**: Multiple policies to attach

---

## 🎯 Recommendation

**For Integration Testing**: Use **Option 1** (Compact Inline Policy)

**Why:**
- ✅ Single policy, simple setup
- ✅ Under 2048 char limit (1,095 chars)
- ✅ Sufficient for tests
- ✅ Still has DENY rules for cost protection
- ✅ Region-locked to us-east-1

**After tests work**, you can optionally switch to Option 2 for production use.

---

## Comparison

| Feature | Option 1: Compact | Option 2: Managed |
|---------|------------------|-------------------|
| **Setup time** | 2 minutes | 5-10 minutes |
| **Number of policies** | 1 inline | 7 managed + 1 inline |
| **Character count** | 1,095 | N/A (managed) |
| **Granularity** | Wildcards | More specific |
| **Maintenance** | Manual updates | AWS maintains |
| **For testing** | ✅ Perfect | ⚠️ Overkill |
| **For production** | ⚠️ Too broad | ✅ Better |

---

## Security Notes

Both options include:
- ✅ Region lock (us-east-1 only)
- ✅ DENY expensive services (EC2, RDS, etc.)
- ✅ Only what tests need

Option 1 uses wildcards (`lambda:*`) which is acceptable for:
- ✅ Dedicated test account
- ✅ Temporary testing
- ✅ IAM user with no other permissions

**NOT recommended for production or shared accounts!**

---

## What's the Difference?

**Original `IAM_MINIMAL_PERMISSIONS.json`** (6,678 chars):
- Very granular: `lambda:CreateFunction`, `lambda:DeleteFunction`, etc.
- ❌ Too large for inline policy (>2048 limit)
- ✅ Most secure (explicit permissions only)

**Compact `IAM_MINIMAL_PERMISSIONS_COMPACT.json`** (1,095 chars):
- Uses wildcards: `lambda:*` instead of 20+ specific actions
- ✅ Fits inline policy limit
- ⚠️ Slightly less secure (allows all Lambda actions)
- ✅ Still safe for testing (DENY rules + region lock)

---

## Next Steps

1. **Choose Option 1** (recommended for testing)
2. Follow the "How to Add" steps above
3. Verify it works: `aws sts get-caller-identity`
4. Run integration tests
5. After tests work, optionally refine permissions

---

**Ready to proceed with Option 1?** 🚀

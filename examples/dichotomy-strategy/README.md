# Dichotomy Purchase Strategy Example

This example demonstrates the **dichotomy purchase strategy**, an adaptive approach to Savings Plans purchases that creates a stable, long-term coverage profile through exponentially decreasing purchase sizes.

## Strategy Overview

### How It Works

The dichotomy strategy calculates purchase size as the **largest power-of-2 fraction** of `max_purchase_percent` that doesn't exceed the coverage gap.

**Example progression** (max 50%, target 90%):

| Month | Coverage | Gap  | Purchase % | Logic                          |
|-------|----------|------|------------|--------------------------------|
| 1     | 0%       | 90%  | 50%        | Gap ≥ max, use max            |
| 2     | 50%      | 40%  | 25%        | Gap < 50%, halve to 25%       |
| 3     | 75%      | 15%  | 12.5%      | Gap < 25%, halve to 12.5%     |
| 4     | 87.5%    | 2.5% | 2.5%       | Gap < 6.25%, use exact gap    |
| 5     | 90%      | 0%   | 0%         | Target reached, stop          |

### Key Benefits

✅ **Adaptive** - Purchase size automatically adjusts based on coverage gap
✅ **Stable** - Creates distributed, smaller commitments over time
✅ **Resilient** - When large plans expire, naturally replaced by multiple smaller purchases
✅ **Safe** - Prevents over-commitment through exponential halving
✅ **Stateless** - No iteration tracking needed - gap determines purchase size

### When to Use

The dichotomy strategy is ideal for:

- **New deployments** - Ramp from 0% to target coverage efficiently
- **Variable workloads** - Adapt to changing usage patterns
- **Risk management** - Avoid large single commitments
- **Long-term planning** - Build stable coverage profile

## Configuration

### Required Parameters

```hcl
purchase_strategy = {
  coverage_target_percent = 90 # Target coverage percentage
  max_coverage_cap        = 95 # Safety cap to prevent over-commitment

  dichotomy = {
    max_purchase_percent = 50 # Maximum purchase as % of AWS recommendation
    min_purchase_percent = 1  # Minimum purchase threshold
  }
}
```

### Parameter Guidelines

**max_purchase_percent**: 25-75%
- Higher (50-75%): Faster ramp to target, larger initial commitments
- Lower (25-50%): Slower ramp, more conservative approach

**min_purchase_percent**: 0.5-5%
- Prevents tiny purchases below threshold
- Recommended: 1% for most use cases

## Comparison with Simple Strategy

| Aspect                | Simple Strategy         | Dichotomy Strategy           |
|-----------------------|-------------------------|------------------------------|
| Purchase sizing       | Fixed percentage        | Exponentially decreasing     |
| Adaptation            | Static                  | Dynamic based on gap         |
| Ramp-up speed         | Linear                  | Fast initially, slows near target |
| Coverage stability    | Moderate                | High (distributed purchases) |
| Over-commitment risk  | Higher                  | Lower (halving approach)     |
| Complexity            | Very simple             | Simple (automatic)           |

## Deployment

### Prerequisites

- AWS account with Savings Plans permissions
- Terraform >= 1.4
- AWS provider >= 5.0

### Deploy

```bash
cd examples/dichotomy-strategy
terraform init
terraform plan
terraform apply
```

### Verify

1. Check Lambda functions created:
   ```bash
   aws lambda list-functions --query 'Functions[?contains(FunctionName, `sp-autopilot`)].FunctionName'
   ```

2. View scheduler configuration:
   ```bash
   terraform output module_configuration
   ```

3. Manually trigger scheduler (first run):
   ```bash
   aws lambda invoke --function-name sp-autopilot-scheduler /tmp/output.json
   cat /tmp/output.json
   ```

## Expected Behavior

### First Month

- Scheduler analyzes current coverage: 0%
- Coverage gap: 90%
- Dichotomy algorithm: 90% > 50%, use max 50%
- AWS recommends: $X/hour
- Purchase queued: $X * 0.50 /hour
- Purchaser executes (if enabled)

### Second Month

- Current coverage: ~50%
- Coverage gap: ~40%
- Dichotomy algorithm: 40% < 50%, halve to 25%
- AWS recommends: $Y/hour
- Purchase queued: $Y * 0.25 /hour

### Subsequent Months

- Purchase percentage continues halving: 12.5%, 6.25%, 3.125%, ...
- When purchase would be < min_purchase_percent (1%), uses exact gap
- Stops when coverage >= target (90%)

## Monitoring

Watch CloudWatch Logs for strategy in action:

```bash
# View scheduler logs
aws logs tail /aws/lambda/sp-autopilot-scheduler --follow

# Look for these log messages:
# "Using purchase strategy: dichotomy"
# "Dichotomy algorithm: gap=40.0% -> purchase_percent=25.0%"
# "Scaling by 25.0% -> $X.XX/hour"
```

## Customization

### More Aggressive (faster ramp)

```hcl
dichotomy = {
  max_purchase_percent = 75 # Higher max
  min_purchase_percent = 0.5 # Lower min
}
```

### More Conservative (slower ramp)

```hcl
dichotomy = {
  max_purchase_percent = 25 # Lower max
  min_purchase_percent = 2 # Higher min
}
```

### Enable All SP Types

```hcl
sp_plans = {
  compute = {
    enabled = true
    all_upfront_three_year = 0.7
    all_upfront_one_year = 0.3
  }
  database = {
    enabled = true
    no_upfront_one_year = 1
  }
  sagemaker = {
    enabled = true
    all_upfront_one_year = 1
  }
}
```

## Cleanup

```bash
terraform destroy
```

**Note**: This will not automatically cancel active Savings Plans commitments. Those continue until their term expires.

## Learn More

- [Main README](../../README.md) - Full module documentation
- [Simple Strategy Example](../single-account-compute/) - Compare with simple strategy
- [AWS Savings Plans Documentation](https://docs.aws.amazon.com/savingsplans/latest/userguide/)

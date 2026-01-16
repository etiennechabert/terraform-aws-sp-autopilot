# Dichotomy Purchase Strategy Example

This example demonstrates the **dichotomy purchase strategy**, an adaptive approach to Savings Plans purchases that creates a stable, long-term coverage profile through exponentially decreasing purchase sizes.

## Strategy Overview

### How It Works

The dichotomy strategy **always starts with `max_purchase_percent`** and halves until the purchase doesn't cause coverage to exceed the target.

**Example progression** (max 50%, target 90%):

| Month | Coverage | Try Sequence | Purchase % | Result |
|-------|----------|--------------|------------|--------|
| 1     | 0%       | 50% → 0+50=50% ✓ | 50%        | Coverage → 50% |
| 2     | 50%      | 50% (100%) ✗ → 25% (75%) ✓ | 25%        | Coverage → 75% |
| 3     | 75%      | 50% ✗ → 25% (100%) ✗ → 12.5% (87.5%) ✓ | 12.5%      | Coverage → 87.5% |
| 4     | 87.5%    | 50% ✗ → 25% ✗ → 12.5% ✗ → 6.25% ✗ → 3.125% ✗ → 1.5625% (89.0625%) ✓ | 1.5625%    | Coverage → 89.0625% |
| 5     | 89.0625% | 50% ✗ → ... → 0.78125% (89.84375%) ✓ | 0.78125%   | Coverage → 89.84375% |

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
    min_purchase_percent = 1  # Minimum purchase granularity
  }
}
```

### Parameter Guidelines

**max_purchase_percent**: 25-75%
- Higher (50-75%): Faster ramp to target, larger initial commitments
- Lower (25-50%): Slower ramp, more conservative approach

**min_purchase_percent**: 0.5-5%
- Minimum purchase granularity - **never purchase less than this amount**
- When halved amount is close to this threshold (<2x), rounds to this value
- Examples with min=1%:
  - At 87.5% (target 90%): halve to 1.5625% < 2% → purchase 1%
  - At 88.5% (gap 1.5%): halve to 0.78% < 1% → purchase 1%
  - At 89.5% (gap 0.5%): gap < 1% → **still purchase 1%** (overshoots to 90.5%)
- Slight overshoot is acceptable - max_coverage_cap (95%) provides safety
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
- Try 50%: 0 + 50 = 50% ✓
- AWS recommends: $X/hour
- Purchase queued: $X * 0.50 /hour
- Purchaser executes (if enabled)

### Second Month

- Current coverage: 50%
- Try 50%: 50 + 50 = 100% > 90% ✗
- Try 25%: 50 + 25 = 75% ✓
- AWS recommends: $Y/hour
- Purchase queued: $Y * 0.25 /hour

### Subsequent Months

- Always starts with max_purchase_percent (50%)
- Halves until current + purchase <= target
- Example at 87.5%: Try 50% ✗ → 25% ✗ → 12.5% ✗ → 6.25% ✗ → 3.125% ✗ → 1.5625% ✓
- Stops when coverage >= target (90%)

## Monitoring

Watch CloudWatch Logs for strategy in action:

```bash
# View scheduler logs
aws logs tail /aws/lambda/sp-autopilot-scheduler --follow

# Look for these log messages:
# "Using purchase strategy: dichotomy"
# "Dichotomy algorithm: current=50.0%, target=90.0%, purchase_percent=25.0%"
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

# Conservative Purchase Strategy Example

This example demonstrates the **conservative purchase strategy**, a threshold-based approach to Savings Plans purchases that minimizes churn for stable workloads by only purchasing when coverage gaps exceed a minimum threshold.

## Strategy Overview

### How It Works

The conservative strategy **only purchases when the coverage gap meets or exceeds `min_gap_threshold`**, then purchases a fixed percentage (`max_purchase_percent`) of the AWS recommendation.

**Example progression** (threshold 5%, max 50%, target 90%):

| Month | Coverage | Gap (Target - Current) | Gap >= 5%? | Purchase % | Result |
|-------|----------|------------------------|------------|------------|--------|
| 1     | 0%       | 90%                    | ✓ YES      | 50%        | Coverage → 50% |
| 2     | 50%      | 40%                    | ✓ YES      | 50%        | Coverage → 75% |
| 3     | 75%      | 15%                    | ✓ YES      | 50%        | Coverage → 87% |
| 4     | 87%      | 3%                     | ✗ NO       | 0% (skip)  | Coverage → 87% (no change) |
| 5     | 84%*     | 6%                     | ✓ YES      | 50%        | Coverage → 89% |
| 6     | 89%      | 1%                     | ✗ NO       | 0% (skip)  | Coverage → 89% (no change) |

*Some plans expired between months 4-5

### Key Benefits

✅ **Low Churn** - Skips small purchases when close to target, reducing administrative overhead
✅ **Stable** - Coverage naturally stabilizes around target ± threshold
✅ **Simple** - Clear threshold-based decision: purchase or skip
✅ **Predictable** - Fixed purchase percentage when buying
✅ **Flexible** - Easy to tune via min_gap_threshold

### When to Use

The conservative strategy is ideal for:

- **Stable workloads** - Predictable usage patterns with minimal variation
- **Mature deployments** - Already near target coverage, need maintenance mode
- **Reducing overhead** - Minimize purchase frequency and review burden
- **Preventing micro-purchases** - Avoid frequent small purchases that don't materially impact coverage
- **Coverage near target** - When coverage naturally fluctuates slightly around target

## Configuration

### Required Parameters

```hcl
purchase_strategy = {
  coverage_target_percent = 90 # Target coverage percentage
  max_coverage_cap        = 95 # Safety cap to prevent over-commitment

  conservative = {
    min_gap_threshold    = 5.0 # Only purchase if gap >= this percentage
    max_purchase_percent = 50  # Purchase percentage when threshold is met
  }
}
```

### Parameter Guidelines

**min_gap_threshold**: 3-10%
- Higher (7-10%): Very conservative - fewer, larger purchases
  - Pros: Minimal churn, lower overhead
  - Cons: Coverage may drift further from target
- Medium (5%): Balanced approach (recommended default)
  - Pros: Good balance of stability and accuracy
  - Cons: May skip purchases for several months
- Lower (3-4%): More responsive - purchases more often
  - Pros: Stays closer to target coverage
  - Cons: More frequent purchases, higher overhead

**max_purchase_percent**: 25-100%
- Higher (75-100%): Aggressive - close gap quickly when purchasing
  - Use when: Large gaps need to be filled fast
- Medium (50%): Balanced - gradual gap closing
  - Use when: Standard stable workloads (recommended)
- Lower (25-40%): Cautious - incremental purchases
  - Use when: Very conservative risk management needed

## Strategy Comparison

### Conservative vs. Simple Strategy

| Aspect                | Simple Strategy         | Conservative Strategy           |
|-----------------------|-------------------------|---------------------------------|
| Purchase trigger      | Every evaluation        | Only when gap >= threshold      |
| Purchase sizing       | Fixed percentage        | Fixed percentage (when buying)  |
| Purchase frequency    | High (monthly)          | Low (threshold-dependent)       |
| Coverage stability    | Moderate                | High (around target ± threshold)|
| Administrative burden | Higher                  | Lower                           |
| Best for              | Growing workloads       | Stable workloads                |
| Complexity            | Very simple             | Very simple                     |

### Conservative vs. Dichotomy Strategy

| Aspect                | Dichotomy Strategy           | Conservative Strategy           |
|-----------------------|------------------------------|---------------------------------|
| Purchase trigger      | Every evaluation             | Only when gap >= threshold      |
| Purchase sizing       | Exponentially decreasing     | Fixed percentage                |
| Ramp-up speed         | Fast initially, slows        | Consistent when triggered       |
| Purchase frequency    | High (monthly)               | Low (threshold-dependent)       |
| Coverage stability    | High (distributed purchases) | High (around target ± threshold)|
| Administrative burden | Higher                       | Lower                           |
| Best for              | New deployments, variable    | Stable, mature deployments      |
| Complexity            | Simple (automatic)           | Very simple                     |

### Which Strategy Should I Use?

**Choose Conservative if:**
- Your workload is stable and predictable
- You're already near target coverage (maintenance mode)
- You want to minimize purchase frequency and overhead
- Coverage naturally stays within a few percent of target

**Choose Dichotomy if:**
- You're ramping from low coverage to target
- Your workload is variable or growing
- You want adaptive purchase sizing
- You prefer distributed, smaller commitments

**Choose Simple if:**
- You want the most straightforward approach
- You're okay with consistent monthly purchases
- Your workload is steadily growing
- You don't need sophisticated purchase logic

## Deployment

### Prerequisites

- AWS account with Savings Plans permissions
- Terraform >= 1.4
- AWS provider >= 5.0

### Deploy

```bash
cd examples/conservative-strategy
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

### First Month (Coverage: 0%)

- Scheduler analyzes current coverage: 0%
- Coverage gap: 90% (target 90% - current 0%)
- Gap (90%) >= threshold (5%)? **YES**
- AWS recommends: $90/hour (for 90% coverage)
- Purchase queued: $45/hour (50% of $90)
- Purchaser executes (if enabled)
- **Result: Coverage → 50%**

### Second Month (Coverage: 50%)

- Current coverage: 50%
- Coverage gap: 40% (target 90% - current 50%)
- Gap (40%) >= threshold (5%)? **YES**
- AWS recommends: $40/hour
- Purchase queued: $20/hour (50% of $40)
- **Result: Coverage → 75%**

### Third Month (Coverage: 75%)

- Current coverage: 75%
- Coverage gap: 15% (target 90% - current 75%)
- Gap (15%) >= threshold (5%)? **YES**
- AWS recommends: $15/hour
- Purchase queued: $7.50/hour (50% of $15)
- **Result: Coverage → 87%**

### Fourth Month (Coverage: 87%)

- Current coverage: 87%
- Coverage gap: 3% (target 90% - current 87%)
- Gap (3%) >= threshold (5%)? **NO**
- Action: **Skip purchase** (gap below threshold)
- **Result: Coverage → 87% (no change)**

### Steady State

- Coverage stabilizes around 85-92%
- Purchases only occur when plans expire and gap exceeds 5%
- Typically results in quarterly or less frequent purchases
- Low administrative overhead with stable coverage

## Monitoring

Watch CloudWatch Logs for strategy in action:

```bash
# View scheduler logs
aws logs tail /aws/lambda/sp-autopilot-scheduler --follow

# Look for these log messages:
# "Using purchase strategy: conservative"
# "Conservative strategy parameters: target=90%, min_gap_threshold=5.0%, max_purchase_percent=50.0%"
# "Coverage gap (3.0%) below threshold (5.0%) - skipping purchase"
# "Coverage gap (6.0%) meets threshold (5.0%) - proceeding with purchase"
# "Scaling by 50.0% -> $X.XX/hour"
```

## Customization

### More Conservative (fewer purchases)

```hcl
conservative = {
  min_gap_threshold    = 10.0 # Higher threshold - only purchase when gap >= 10%
  max_purchase_percent = 75   # Higher purchase - close gap faster when buying
}
```

**Effect:** Very stable, minimal churn. Might have coverage drift from 80-92%.

### More Responsive (more frequent purchases)

```hcl
conservative = {
  min_gap_threshold    = 3.0 # Lower threshold - purchase when gap >= 3%
  max_purchase_percent = 30  # Lower purchase - more incremental approach
}
```

**Effect:** Stays closer to target (87-92%), but purchases more frequently.

### Balanced Default (recommended)

```hcl
conservative = {
  min_gap_threshold    = 5.0 # Purchase when gap >= 5%
  max_purchase_percent = 50  # 50% of AWS recommendation
}
```

**Effect:** Good balance - stable coverage (85-92%) with quarterly-ish purchases.

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

## Real-World Example

**Scenario:** E-commerce platform with stable baseline traffic

- **On-demand spend:** $10,000/month ($333/hour)
- **Target coverage:** 90% ($300/hour)
- **Strategy:** Conservative (threshold 5%, purchase 50%)

**Month-by-Month:**

| Month | Event | Coverage | Gap | Action | Purchase | Notes |
|-------|-------|----------|-----|--------|----------|-------|
| 1 | Initial | 0% | 90% | Buy | $150/hr | First purchase |
| 2 | Ramp | 50% | 40% | Buy | $100/hr | Building coverage |
| 3 | Ramp | 75% | 15% | Buy | $50/hr | Near target |
| 4 | Stable | 87% | 3% | Skip | - | Below threshold |
| 5 | Stable | 87% | 3% | Skip | - | Below threshold |
| 6 | Minor expire | 84% | 6% | Buy | $25/hr | Crossed threshold |
| 7-9 | Stable | 89% | 1% | Skip | - | Maintenance mode |
| 10 | Major expire | 83% | 7% | Buy | $30/hr | Replacement needed |

**Outcome:**
- **Purchases:** 5 purchases over 10 months (vs. 10 with simple/dichotomy)
- **Coverage:** Stable at 85-90%
- **Overhead:** Minimal - reviews only quarterly

## Cleanup

```bash
terraform destroy
```

**Note:** Active Savings Plans will continue until their term expires. Only the automation infrastructure is removed.

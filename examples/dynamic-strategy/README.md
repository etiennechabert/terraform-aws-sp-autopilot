# Dynamic Target + Dichotomy Split Example

This example demonstrates the **dynamic target + dichotomy split** strategy, which automatically determines the optimal coverage target based on your usage patterns and uses exponentially decreasing purchase sizes to reach it.

## Strategy Overview

### Dynamic Target (balanced)

The dynamic target uses the **knee-point algorithm** to find the optimal coverage level where marginal savings efficiency starts dropping significantly. This adapts automatically to your workload patterns — no manual coverage target tuning needed.

Available risk levels:
- `too_prudent` — 80% of min-hourly (very conservative)
- `min_hourly` — 100% of min-hourly (always-safe baseline)
- `balanced` — Knee-point (where efficiency drops to 30% of peak)
- `aggressive` — Maximum net savings point

### Dichotomy Split

The dichotomy split **always starts with `max_purchase_percent`** and halves until the purchase doesn't cause coverage to exceed the target.

**Example progression** (max 50%, dynamically computed target ~85%, min 1%):

| Month | Coverage | Try Sequence | Purchase % | Result |
|-------|----------|--------------|------------|--------|
| 1     | 0%       | 50% → 0+50=50% ✓ | 50%        | Coverage → 50% |
| 2     | 50%      | 50% (100%) ✗ → 25% (75%) ✓ | 25%        | Coverage → 75% |
| 3     | 75%      | 50% ✗ → 25% (100%) ✗ → 12.5% ✗ → 6.25% (81.25%) ✓ | 6.25%      | Coverage → 81.25% |
| 4     | 81.25%   | 50% ✗ → ... → 3.125% (84.4%) ✓ | 3.125%     | Coverage → 84.4% |
| 5     | 84.4%    | Gap < min → done | 0%         | At target |

## Configuration

```hcl
purchase_strategy = {
  max_coverage_cap = 95

  target = {
    dynamic = { risk_level = "balanced" }
  }

  split = {
    dichotomy = {
      max_purchase_percent = 50
      min_purchase_percent = 1
    }
  }
}
```

### Parameter Guidelines

**risk_level**: Controls target aggressiveness
- `balanced` (recommended): Best tradeoff between savings and risk
- `aggressive`: Maximizes savings but may over-commit
- `min_hourly`: Never exceeds your minimum observed usage
- `too_prudent`: Very conservative, 80% of minimum usage

**max_purchase_percent**: 25-75%
- Higher (50-75%): Faster ramp to target, larger initial commitments
- Lower (25-50%): Slower ramp, more conservative approach

**min_purchase_percent**: 0.5-5%
- Minimum purchase granularity

## Deployment

### Prerequisites

- AWS account with Savings Plans permissions
- Terraform >= 1.4
- AWS provider >= 5.0

### Deploy

```bash
cd examples/dynamic-strategy
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

## Cleanup

```bash
terraform destroy
```

**Note**: This will not automatically cancel active Savings Plans commitments. Those continue until their term expires.

## Learn More

- [Main README](../../README.md) - Full module documentation
- [Fixed + Linear Example](../single-account-compute/) - Simple fixed target strategy
- [AWS Target Example](../organizations/) - Follow AWS recommendations directly
- [AWS Savings Plans Documentation](https://docs.aws.amazon.com/savingsplans/latest/userguide/)

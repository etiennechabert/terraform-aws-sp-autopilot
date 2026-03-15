# Dynamic Target + Gap Split Example

This example demonstrates the **dynamic target + gap split** strategy, which automatically determines the optimal coverage target based on your usage patterns and divides the coverage gap by a configurable divider each cycle.

## Strategy Overview

### Dynamic Target (optimal)

The dynamic target uses the **knee-point algorithm** to find the optimal coverage level where marginal savings efficiency starts dropping significantly. This adapts automatically to your workload patterns — no manual coverage target tuning needed.

Available risk levels:
- `prudent` — Configurable % of min-hourly (default: 85%, conservative). Best for flat/stable workloads where any usage reduction would cause over-commitment.
- `min_hourly` — 100% of min-hourly. Good starting point when workloads have some variation (e.g. autoscaling), since the gap between min and max hourly provides a natural margin for change.
- `optimal` — Knee-point (where efficiency drops to 30% of peak). Makes sense for workloads with significant variation, where spill-over from low-usage hours is offset by savings during high-usage hours.
- `maximum` — Maximum net savings point

### Gap Split

The gap split divides the remaining coverage gap by the configured divider each cycle, clamped between min and max purchase percent.

**Example progression** (dynamically computed target ~90%, divider = 2):

| Month | Coverage | Gap  | Gap / 2 | Purchase % | Result |
|-------|----------|------|---------|------------|--------|
| 1     | 0%       | 90%  | 45.0%   | 45.0%      | Coverage → 45.0% |
| 2     | 45.0%    | 45%  | 22.5%   | 22.5%      | Coverage → 67.5% |
| 3     | 67.5%    | 22.5% | 11.2%  | 11.2%      | Coverage → 78.8% |
| 4     | 78.8%    | 11.2% | 5.6%   | 5.6%       | Coverage → 84.4% |
| 5     | 84.4%    | 5.6% | 2.8%    | 2.8%       | Coverage → 87.2% |

## Configuration

```hcl
purchase_strategy = {
  target = { dynamic = { risk_level = "optimal" } } # Knee-point: best savings/risk tradeoff
  split  = { gap_split = { divider = 2 } }          # Halve the gap each cycle
}
```

### Parameter Guidelines

**risk_level**: Controls target aggressiveness
- `optimal` (recommended): Best tradeoff between savings and risk
- `maximum`: Maximizes savings but may over-commit
- `min_hourly`: Never exceeds your minimum observed usage
- `prudent`: Conservative, configurable % of minimum usage (default: 85%, set via `prudent_percentage`). Ideal for stable workloads with little variation.

**divider**: How much to divide the gap each cycle (required)
- `2` (recommended): Halves the gap each cycle — good balance of speed and safety
- `3`: More conservative — takes more cycles to reach target
- `1`: Purchases the entire gap at once (equivalent to one_shot)

**min_purchase_percent**: Minimum purchase size (default: 1%)
- If the divided gap falls below this, the minimum is used instead
- If the remaining gap is smaller than the minimum, purchases exactly the gap

**max_purchase_percent**: Maximum purchase size (default: unlimited)
- Caps the purchase at this percentage regardless of the divided gap

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
- [Prudent + Fixed Step Example](../single-account-compute/) - Conservative prudent target strategy
- [AWS Target Example](../organizations/) - Follow AWS recommendations directly
- [AWS Savings Plans Documentation](https://docs.aws.amazon.com/savingsplans/latest/userguide/)

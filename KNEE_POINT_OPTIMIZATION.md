# Knee-Point Optimization Feature Proposal

## Overview

Add knee-point optimization analysis to the Scheduler Preview tab in the Reporter Lambda. This would show users the mathematically optimal commitment level based on their actual discount rate, and compare it against what each scheduler strategy would purchase.

## Problem Statement

Currently, the Scheduler Preview shows what each strategy (Fixed, Dichotomy, Follow AWS) would purchase, but doesn't tell users if those purchases are optimal. Users need guidance on:

1. **What is the optimal commitment level?** Based on spending patterns and discount rate
2. **Are my strategies efficient?** Is Fixed too conservative? Is Follow AWS over-committing?
3. **Where is the "knee" of the curve?** The point where additional coverage provides diminishing returns

## The Knee-Point Algorithm

The knee-point optimization algorithm already exists in `shared/purchase_optimizer.py` and is used by the Dichotomy strategy. It works as follows:

### Core Concept

Given a discount rate (e.g., 60% for Compute Savings Plans), the optimal commitment is at the percentile where you save money more often than you waste it:

```
Target Percentile = 100 - (discount_rate × 100)
```

**Examples:**
- 60% discount → P40 target (save money 60% of hours, waste 40%)
- 30% discount → P70 target (save money 30% of hours, waste 70%)
- 20% discount → P80 target (more conservative)

### Why This Works

Committing at the target percentile maximizes net savings by finding the "knee" where:
- **Below the knee**: Each additional $/hr committed yields high marginal savings
- **Above the knee**: Each additional $/hr committed yields diminishing returns (more waste than savings)

### Implementation in Code

```python
from shared.purchase_optimizer import PurchaseOptimizer

optimizer = PurchaseOptimizer()
result = optimizer.calculate_optimal_commitment(
    hourly_costs=[...],  # Timeseries data
    discount_rate=0.60   # 60% discount
)

# Returns:
{
    "optimal_commitment": 12.50,  # $/hr
    "target_percentile": 40,      # P40
    "discount_rate": 0.60,
    "breakeven_hours_pct": 60.0,  # Save money 60% of the time
    "net_savings": 8403.50        # Total savings at this commitment
}
```

## Proposed UI Enhancement

### Current Scheduler Preview Table

Currently shows 3 strategies side-by-side:

| Strategy | Hourly Commitment | Purchase % | Current Coverage | Projected Coverage | Coverage Increase |
|----------|-------------------|------------|------------------|-------------------|-------------------|
| Fixed | $3.30/hr | 8.3% | 81.7% | 90.0% | +8.3% |
| Dichotomy | $1.99/hr | 5.0% | 81.7% | 86.7% | +5.0% |
| Follow AWS | $15.69/hr | 58.5% | 0.0% | 58.5% | +58.5% |

### Enhanced Version with Knee-Point Analysis

Add a fourth "strategy" showing the optimal knee-point:

| Strategy | Hourly Commitment | Purchase % | Current Coverage | Projected Coverage | Efficiency |
|----------|-------------------|------------|------------------|-------------------|------------|
| Fixed 🔧 | $3.30/hr | 8.3% | 81.7% | 90.0% | ✅ Optimal |
| Dichotomy 📉 | $1.99/hr | 5.0% | 81.7% | 86.7% | ✅ Near-optimal |
| Follow AWS 📊 | $15.69/hr | 58.5% | 0.0% | 58.5% | ⚠️ 32% over-committed |
| **Knee-Point 🎯** | **$10.50/hr** | **at P40** | **81.7%** | **92.2%** | **Maximum efficiency** |

### Info Box

```
💡 Knee-Point Optimization

The knee-point represents the optimal commitment level where marginal savings
start to diminish. Based on your 60% discount rate, the optimal commitment is
at P40 (save money 60% of hours, minimal waste 40% of hours).

Comparison:
• Fixed: 69% below optimal (too conservative, leaving savings on table)
• Dichotomy: 81% below optimal (adaptive but still conservative)
• Follow AWS: 49% above optimal (over-committed, high waste risk)
```

## Implementation Plan

### Phase 1: Data Collection

Modify `lambda/reporter/scheduler_preview.py`:

```python
def calculate_optimal_commitment_analysis(
    coverage_data: dict[str, Any],
    savings_data: dict[str, Any]
) -> dict[str, Any]:
    """
    Calculate knee-point optimal commitment for each SP type.

    Returns:
        {
            "compute": {
                "optimal_commitment": 10.50,
                "target_percentile": 40,
                "discount_rate": 0.60,
                "current_coverage": 81.7,
                "projected_coverage": 92.2
            },
            "database": {...},
            "sagemaker": {...}
        }
    """
    from shared.purchase_optimizer import PurchaseOptimizer

    optimizer = PurchaseOptimizer()
    results = {}

    for sp_type in ["compute", "database", "sagemaker"]:
        # Extract discount rate from active plans
        discount_rate = _get_discount_rate_for_type(savings_data, sp_type)

        # Get hourly spending timeseries
        timeseries = coverage_data.get(sp_type, {}).get("timeseries", [])
        hourly_costs = [point["total"] for point in timeseries]

        # Calculate optimal commitment
        optimal = optimizer.calculate_optimal_commitment(
            hourly_costs=hourly_costs,
            discount_rate=discount_rate or 0.30  # Default 30% if unknown
        )

        # Calculate coverage impact
        summary = coverage_data.get(sp_type, {}).get("summary", {})
        current_coverage = summary.get("avg_coverage_total", 0.0)
        avg_hourly_uncovered = summary.get("avg_hourly_uncovered", 0.0)

        if avg_hourly_uncovered > 0:
            coverage_increase = (optimal["optimal_commitment"] / avg_hourly_uncovered) * 100
            projected_coverage = min(current_coverage + coverage_increase, 100.0)
        else:
            projected_coverage = current_coverage

        results[sp_type] = {
            "optimal_commitment": optimal["optimal_commitment"],
            "target_percentile": optimal["target_percentile"],
            "discount_rate": optimal["discount_rate"],
            "current_coverage": current_coverage,
            "projected_coverage": projected_coverage
        }

    return results
```

### Phase 2: Efficiency Comparison

Add efficiency calculation comparing each strategy to knee-point:

```python
def calculate_efficiency(scheduled_commitment, optimal_commitment):
    """Calculate efficiency ratio and status."""
    if optimal_commitment == 0:
        return {"ratio": 0, "status": "unknown", "message": ""}

    ratio = scheduled_commitment / optimal_commitment

    if 0.9 <= ratio <= 1.1:
        status = "optimal"
        message = "At optimal commitment level"
    elif 0.8 <= ratio < 0.9 or 1.1 < ratio <= 1.2:
        status = "near_optimal"
        if ratio < 1.0:
            pct_below = (1.0 - ratio) * 100
            message = f"{pct_below:.0f}% below optimal (leaving savings on table)"
        else:
            pct_above = (ratio - 1.0) * 100
            message = f"{pct_above:.0f}% above optimal (minor waste risk)"
    else:
        status = "inefficient"
        if ratio < 0.8:
            pct_below = (1.0 - ratio) * 100
            message = f"{pct_below:.0f}% below optimal (significant savings missed)"
        else:
            pct_above = (ratio - 1.0) * 100
            message = f"{pct_above:.0f}% above optimal (high waste risk)"

    return {"ratio": ratio, "status": status, "message": message}
```

### Phase 3: UI Rendering

Update `lambda/reporter/report_generator.py` to add knee-point row to table:

```python
# After rendering strategy rows, add knee-point row
optimal_data = preview_data.get("optimal_analysis", {}).get(sp_type, {})
if optimal_data:
    opt_commit = optimal_data["optimal_commitment"]
    target_p = optimal_data["target_percentile"]
    discount = optimal_data["discount_rate"]
    current_cov = optimal_data["current_coverage"]
    projected_cov = optimal_data["projected_coverage"]
    cov_increase = projected_cov - current_cov

    html += f"""
        <tr style="background: #e8f5e9; border-top: 2px solid #4caf50; font-weight: 600;">
            <td><strong>🎯 Knee-Point Optimal</strong></td>
            <td class="metric" style="color: #4caf50; font-weight: bold;">
                ${opt_commit:.4f}/hr
            </td>
            <td class="metric">at P{target_p}</td>
            <td class="metric">{current_cov:.1f}%</td>
            <td class="metric green" style="font-weight: bold;">
                {projected_cov:.1f}%
            </td>
            <td class="metric" style="color: #4caf50;">+{cov_increase:.1f}%</td>
            <td colspan="2" style="font-size: 0.9em;">
                Maximum efficiency ({discount * 100:.0f}% discount)
            </td>
        </tr>
    """
```

## Benefits

1. **Educational**: Users learn about the knee-point concept and why it matters
2. **Decision Support**: Shows if configured strategy is efficient or needs adjustment
3. **Risk Awareness**: Highlights when Follow AWS recommendations are over-committed
4. **Data-Driven**: Uses actual discount rates and spending patterns, not assumptions
5. **Actionable**: Clear guidance on whether to increase/decrease commitments

## Edge Cases

1. **No active plans (unknown discount)**: Use default 30% and note it's estimated
2. **Insufficient spending data**: Show "Unable to calculate" with explanation
3. **All strategies disabled**: Don't show knee-point row
4. **At/above target coverage**: Show knee-point but note it's already exceeded

## Testing Strategy

1. **Unit tests**: Test knee-point calculation logic
2. **Integration tests**: Verify knee-point row appears in HTML report
3. **Manual testing**: Compare against PurchaseOptimizer calculations
4. **Edge case testing**: No plans, no data, disabled types

## Future Enhancements

1. **Interactive slider**: Let users adjust commitment in UI and see efficiency change
2. **Historical tracking**: Show if past purchases were at/near knee-point
3. **Multi-month projection**: Show how knee-point evolves over time
4. **Savings curve visualization**: Graph showing diminishing returns past knee-point
5. **GitHub pages integration**: Add knee-point to interactive simulator

## Related Files

- `shared/purchase_optimizer.py` - Knee-point algorithm implementation
- `lambda/scheduler/dichotomy_strategy.py` - Uses knee-point for adaptive sizing
- `lambda/reporter/scheduler_preview.py` - Would integrate knee-point analysis
- `lambda/reporter/report_generator.py` - Would render knee-point in UI
- `docs/index.html` - GitHub pages simulator (already has percentile display)

## References

- Original plan: `.claude/plans/swirling-watching-gray.md`
- Purchase optimizer: `shared/purchase_optimizer.py`
- Scheduler preview: `lambda/reporter/scheduler_preview.py`

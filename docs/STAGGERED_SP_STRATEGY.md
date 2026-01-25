# Staggered Savings Plan Purchase Strategy

## Overview

This document outlines advanced strategies for purchasing AWS Savings Plans with staggered expirations to maximize savings while maintaining flexibility. These strategies enable safely pushing coverage beyond the conservative min-hourly baseline (100%) to capture additional savings.

## Two-Level Coverage Strategy

### Level 1: Safe Coverage (Min-Hourly Baseline)

**Target:** ≤100% of minimum hourly cost

**Characteristics:**
- Zero waste guaranteed - usage always exceeds commitment
- Safe for any commitment length (1Y or 3Y)
- Lower total savings potential
- Recommended for initial deployment

**Risk Profile:** None - this is the "always safe" baseline

### Level 2: Advanced Coverage (Optimal Coverage)

**Target:** 100-135% of minimum hourly cost (varies by usage pattern)

**Characteristics:**
- Higher total savings (baseline + extra savings beyond min-hourly)
- Some commitment may go unused (waste) during low periods
- Risk mitigated through staggered expirations
- Requires ongoing monitoring and adjustment

**Risk Profile:** Medium - requires discipline and staggered distribution

**Example:**
```
Min-hourly cost: $30/hour
Optimal coverage: $37.83/hour (127% of min-hourly)

Savings breakdown:
- Baseline (at min-hourly): $3,494/week
- Extra (min to optimal): +$259/week
- Total savings: $3,754/week

Trade-off: Some waste possible if usage drops, but overall net savings higher
```

## The Clustering Problem with 3Y Plans

### The Issue

When transitioning from 1Y to 3Y plans, naive renewal creates clustering:

**Year 1:** Purchase 12 monthly 1Y plans (Jan-Dec)
**Year 2:** Each 1Y plan expires and is renewed with a 3Y plan (Jan-Dec)
**Year 5:** All 12 3Y plans expire in the same year!

Result: Loss of continuous monthly flexibility, all decisions cluster every 3 years.

### Solutions

#### Solution 1: Hybrid Approach (Recommended)

Maintain a mix of 1Y and 3Y plans:
- **50% as 1Y plans** - Continuous monthly flexibility
- **50% as 3Y plans** - Better discount, less management overhead

Benefits:
- Always have some commitment renewing soon
- Balance between savings (3Y discount) and flexibility (1Y terms)
- Safer for optimal coverage (>100%) scenarios

#### Solution 2: Accept Yearly Clustering

Purchase 3Y plans monthly, accept that renewals cluster yearly:
- Year 1: Buy 3Y plan in January
- Year 1: Buy 3Y plan in February
- etc.
- Year 4: All plans expire in their respective months

Benefits:
- Maximum 3Y discount
- Monthly granularity during renewal years
- Simpler to manage than hybrid

Drawbacks:
- No flexibility in Years 2-3
- Must wait until Year 4 to adjust

#### Solution 3: 3-Cohort System

Spread purchases across 3 years to maintain annual renewal opportunities:
- **Year 1:** Buy 4 monthly 3Y plans (Jan, Feb, Mar, Apr)
- **Year 2:** Buy 4 monthly 3Y plans (Jan, Feb, Mar, Apr)
- **Year 3:** Buy 4 monthly 3Y plans (Jan, Feb, Mar, Apr)

Result: 4 plans renew every year, continuous adjustment possible

## Dynamic Dichotomy Purchase Strategy

### Concept

Instead of buying equal monthly amounts, use a dichotomy approach where the initial purchase size depends on your target coverage level, and plans automatically subdivide over time through renewal splitting.

### Initial Purchase Calculation

**Formula:** `X = (Target% / 100) × Min-Hourly / 2`

Then purchase: X, X/2, X/4, X/8, ... until negligible

**Example - Targeting 135% of min-hourly ($40/hour):**
```
Min-hourly: $30/hour
Target: $40.50/hour (135%)

Initial purchases:
Month 1: $20.25/hour (X = 50% of target)
Month 2: $10.125/hour (X/2)
Month 3: $5.0625/hour (X/4)
Month 4: $2.53125/hour (X/8)
Month 5: $1.265625/hour (X/16)
Month 6: $0.6328125/hour (X/32)
...continue until < 1% of min-hourly ($0.30/hour)

Total: ≈ $40.50/hour (135% coverage)
```

**Example - Targeting 100% of min-hourly ($30/hour):**
```
Min-hourly: $30/hour
Target: $30/hour (100%)

Initial purchases:
Month 1: $15/hour (X = 50% of target)
Month 2: $7.5/hour (X/2)
Month 3: $3.75/hour (X/4)
Month 4: $1.875/hour (X/8)
...continue until < 1% of min-hourly ($0.30/hour)

Total: ≈ $30/hour (100% coverage)
```

### Renewal Split Strategy

**Core Principle:** When a plan expires, replace it with **two smaller plans** purchased in separate months.

**Algorithm:**
```
When plan of amount A expires:
1. Calculate split_amount = A / 2
2. Find the 2 months with lowest existing coverage over the next term
3. Purchase split_amount in each of those months
```

**Example Timeline:**

**Year 1 - Initial Purchases (1Y plans, targeting 135%):**
```
Month 01: Purchase $20.25/hr (expires Month 13)
Month 02: Purchase $10.125/hr (expires Month 14)
Month 03: Purchase $5.0625/hr (expires Month 15)
Month 04: Purchase $2.53125/hr (expires Month 16)
...
```

**Year 2 - First Renewal Cycle:**
```
Month 13: $20.25/hr expires
  → Purchase $10.125/hr in Month 13 (expires Month 25)
  → Purchase $10.125/hr in Month 19 (expires Month 31) [spread across year]

Month 14: $10.125/hr expires
  → Purchase $5.0625/hr in Month 14 (expires Month 26)
  → Purchase $5.0625/hr in Month 20 (expires Month 32)

Month 15: $5.0625/hr expires
  → Purchase $2.53125/hr in Month 15 (expires Month 27)
  → Purchase $2.53125/hr in Month 21 (expires Month 33)
...
```

**Result After 3-4 Cycles:**
- Large initial chunks progressively split
- Coverage becomes increasingly granular
- Converges toward even monthly distribution
- Maintains flexibility to adjust at each renewal

### Convergence to Even Distribution

Over time, this strategy naturally creates even monthly distribution:

**After 1 cycle (Year 2):** Doubling of purchase frequency
**After 2 cycles (Year 3):** 4x original frequency
**After 3 cycles (Year 4):** 8x original frequency
**After 4 cycles (Year 5):** Near-continuous monthly distribution

## Implementation Considerations

### 1. Split Placement Algorithm

**Question:** Where exactly should the 2 split purchases be placed?

**Options:**

**A. Maximize Gap (Recommended for 1Y plans)**
```python
def find_split_months(expiring_month, term_years):
    """Place splits to maximize time gap between renewals."""
    months_in_term = term_years * 12
    # Place second purchase at midpoint of term
    month1 = expiring_month
    month2 = expiring_month + (months_in_term // 2)
    return [month1, month2]
```

**B. Fill Gaps in Existing Coverage (Recommended for 3Y plans)**
```python
def find_least_covered_months(coverage_by_month, horizon_years):
    """Find months with lowest coverage in the renewal horizon."""
    future_months = list(range(current_month, current_month + horizon_years * 12))
    coverage_amounts = [(month, coverage_by_month.get(month, 0))
                        for month in future_months]
    sorted_by_coverage = sorted(coverage_amounts, key=lambda x: x[1])
    return [sorted_by_coverage[0][0], sorted_by_coverage[1][0]]
```

**C. Round-Robin Distribution**
```python
def round_robin_split(expiring_month, existing_renewals):
    """Distribute splits across months with fewest existing renewals."""
    # Count renewals per month
    renewals_per_month = Counter(r.month for r in existing_renewals)
    # Pick 2 months with fewest renewals
    least_busy = sorted(renewals_per_month.items(), key=lambda x: x[1])[:2]
    return [month for month, count in least_busy]
```

### 2. Stopping Threshold

**Question:** When should we stop splitting and start consolidating?

**Options:**

**A. Absolute Threshold**
```python
MIN_PLAN_SIZE = 0.01 * min_hourly  # 1% of min-hourly
if plan.amount < MIN_PLAN_SIZE:
    # Renew as-is, don't split further
    return [{'amount': plan.amount, 'month': plan.month}]
```

**B. Percentage of Total**
```python
MIN_PLAN_PERCENTAGE = 0.5  # 0.5% of total coverage
if plan.amount < total_coverage * MIN_PLAN_PERCENTAGE / 100:
    # Consolidate with smallest existing plan in same month
    return consolidate_with_smallest(plan)
```

**C. Never Stop (Infinite Granularity)**
```python
# Always split, even tiny amounts
# Let AWS handle small SP amounts
```

### 3. 3Y Plan Redistribution

**Challenge:** With 3Y plans, it takes 9-12 years to achieve full redistribution.

**Example:**
- Year 1: Buy $20/hr (expires Year 4)
- Year 4: Split to 2x $10/hr (expire Year 7)
- Year 7: Split to 4x $5/hr (expire Year 10)
- Year 10: Split to 8x $2.50/hr (expire Year 13)

**Mitigation:** Use hybrid approach (50% 1Y / 50% 3Y) for faster redistribution

### 4. Adjustment on Renewal

**Question:** Should renewal amounts adjust based on new optimal calculations?

**Conservative Approach:**
```python
def renew_plan(expiring_plan, latest_optimal):
    """Renew at same amount, just split into 2 purchases."""
    split_amount = expiring_plan.amount / 2
    return [split_amount, split_amount]
```

**Adaptive Approach:**
```python
def renew_plan_adaptive(expiring_plan, current_optimal, current_total):
    """Adjust renewal amount based on gap to new optimal."""
    gap = current_optimal - current_total
    if gap > 0:
        # Under-covered: increase renewal
        split_amount = (expiring_plan.amount + gap / 2) / 2
    elif gap < 0:
        # Over-covered: decrease renewal
        split_amount = max(0, (expiring_plan.amount + gap / 2) / 2)
    else:
        # At optimal: renew as-is
        split_amount = expiring_plan.amount / 2
    return [split_amount, split_amount]
```

### 5. Tracking and Automation

**Data Structure Needed:**
```python
{
    "plans": [
        {
            "id": "sp-abc123",
            "purchase_date": "2024-01-15",
            "amount_per_hour": 20.25,
            "term_years": 1,
            "expiration_date": "2025-01-15",
            "parent_plan_id": null,  # Initial purchase
            "generation": 0  # How many splits from original
        },
        {
            "id": "sp-def456",
            "purchase_date": "2025-01-15",
            "amount_per_hour": 10.125,
            "term_years": 1,
            "expiration_date": "2026-01-15",
            "parent_plan_id": "sp-abc123",  # Split from this
            "generation": 1
        }
    ],
    "metadata": {
        "target_coverage_pct": 135,
        "min_hourly": 30.00,
        "strategy": "dynamic_dichotomy",
        "split_algorithm": "maximize_gap"
    }
}
```

## Recommended Implementation Phases

### Phase 1: Build Foundation (Months 1-12)
- **Goal:** Reach min-hourly coverage (100%)
- **Strategy:** Dynamic dichotomy with 1Y plans
- **Risk:** None - staying at 100% is always safe

### Phase 2: Stabilize and Observe (Months 13-24)
- **Goal:** Maintain 100%, monitor usage patterns
- **Strategy:** Begin renewal splits, keep at min-hourly
- **Risk:** None - still at 100%

### Phase 3: Optimize Coverage (Months 25-36)
- **Goal:** Push to optimal coverage (110-135%)
- **Strategy:** Gradually increase renewals using adaptive approach
- **Risk:** Medium - mitigated by staggered distribution from splits

### Phase 4: Introduce 3Y Plans (Months 37-48)
- **Goal:** Start transitioning to 3Y for better discount
- **Strategy:** Hybrid 50/50 mix (1Y for flexibility, 3Y for savings)
- **Risk:** Low - continuous monthly renewals maintained through 1Y portion

### Phase 5: Steady State (Year 5+)
- **Goal:** Maintain optimal coverage with minimal management
- **Strategy:** Auto-renew with splits, quarterly reviews
- **Risk:** Low - fully staggered, adaptive adjustments

## Open Questions for Implementation

1. **Should the tool recommend specific purchase amounts per month?**
   - Or just show the dichotomy sequence and let users decide timing?

2. **How to handle existing non-staggered SPs?**
   - Strategy to gradually migrate to staggered distribution?

3. **What if optimal coverage changes significantly during build-up?**
   - Restart dichotomy at new target?
   - Adjust future purchases proportionally?

4. **Integration with Spot.io Eco or other SP management tools?**
   - Can we export recommended purchase schedules?
   - API to track actual vs recommended?

5. **Visualization of the distribution over time?**
   - Timeline showing current plans and future renewals?
   - Heatmap of coverage by month/year?

6. **Alert/reminder system for upcoming renewals?**
   - Email notifications X days before expiration?
   - Suggested renewal amounts based on latest data?

## Success Metrics

Track these metrics to validate the strategy:

1. **Distribution Evenness**
   - Standard deviation of coverage by month
   - Goal: Decrease over time as splits take effect

2. **Waste Percentage**
   - Unused commitment / Total commitment
   - Goal: <5% even at optimal coverage

3. **Total Savings vs On-Demand**
   - (On-Demand Cost - SP Cost) / On-Demand Cost
   - Goal: >30% at optimal coverage

4. **Adjustment Frequency**
   - How often coverage needs manual adjustment
   - Goal: Quarterly reviews sufficient after Year 3

5. **Time to Target Coverage**
   - Months to reach optimal from zero
   - Goal: <12 months for initial build

## Next Steps

- [ ] Implement dichotomy calculator in Python
- [ ] Build renewal split algorithm with placement strategies
- [ ] Create SP tracking database schema
- [ ] Add staggered purchase visualization to GH-Page
- [ ] Generate recommended purchase schedule in reporter
- [ ] Build renewal reminder/notification system
- [ ] Add metrics dashboard to track distribution health

## References

- Main README: [Core concepts and quick start](../README.md)
- Optimal Coverage Algorithm: [lambda/shared/optimal_coverage.py](../lambda/shared/optimal_coverage.py)
- Interactive Simulator: [GH-Page](https://etiennechabert.github.io/terraform-aws-sp-autopilot/)

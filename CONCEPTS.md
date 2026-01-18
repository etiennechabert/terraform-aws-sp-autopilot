# Concepts and Glossary

Key terminology and concepts used throughout the AWS Savings Plans Automation Module. This glossary provides quick reference for configuration parameters and operational concepts.

## Table of Contents

- [Coverage Concepts](#coverage-concepts)
- [Purchase Strategy Concepts](#purchase-strategy-concepts)
- [Operational Concepts](#operational-concepts)
- [Configuration Concepts](#configuration-concepts)
- [Savings Plan Types](#savings-plan-types)

## Coverage Concepts

### Coverage Percentage

**Definition:** The percentage of eligible compute, database, or SageMaker usage that is covered by active Savings Plans.

**Tracked Separately:** Coverage for Compute, Database, and SageMaker Savings Plans is calculated and tracked independently.

**Calculation:**
```
Coverage % = (Usage covered by Savings Plans / Total eligible usage) × 100
```

**Example:**
- Total eligible EC2 usage: $10,000/month
- Amount covered by Compute Savings Plans: $8,500/month
- **Coverage percentage: 85%**

**AWS API:** Retrieved via `ce:GetSavingsPlansCoverage` Cost Explorer API call.

**Related:**
- [coverage_target_percent](#coverage_target_percent)
- [max_coverage_cap](#max_coverage_cap)

---

### coverage_target_percent

**Type:** Configuration parameter

**Definition:** The target coverage percentage the module works toward achieving through automated purchases.

**Range:** 1-100 (must be ≤ `max_coverage_cap`)

**Purpose:** Sets the goal for Savings Plans coverage. The module calculates purchase recommendations to gradually reach this target while respecting purchase limits.

**Example:**
```hcl
purchase_strategy = {
  coverage_target_percent = 90  # Target 90% coverage
  max_coverage_cap        = 95
}
```

**Behavior:**
- **Below target:** Module recommends purchases to increase coverage
- **At or above target:** No purchases recommended (unless below cap after expiring plans)
- **Applied independently** to Compute, Database, and SageMaker SP types

**Common Values:**
| Value | Use Case |
|-------|----------|
| 70-80% | Conservative approach, new deployments |
| 85-90% | Standard production workloads |
| 90-95% | Maximum savings, stable workloads |

---

### max_coverage_cap

**Type:** Configuration parameter

**Definition:** Hard ceiling that prevents the module from purchasing Savings Plans if coverage would exceed this limit.

**Range:** 1-100 (must be ≥ `coverage_target_percent`)

**Purpose:** Risk management safeguard that prevents over-commitment even if AWS recommendations suggest higher coverage. Protects against usage decreases.

**Example:**
```hcl
purchase_strategy = {
  coverage_target_percent = 90
  max_coverage_cap        = 95  # Never exceed 95% coverage
}
```

**Behavior:**
- **Below cap:** Purchases allowed (subject to other strategy rules)
- **At or above cap:** **All purchases blocked**, even if below target
- **Enforced independently** for Compute, Database, and SageMaker SP types

**Why It Matters:**
Savings Plans are **long-term commitments** (1-3 years). If usage decreases unexpectedly (e.g., workload migration, service deprecation), high coverage becomes a financial liability. The cap provides a safety margin.

**Recommended Gap:**
```
max_coverage_cap - coverage_target_percent ≥ 5-10%
```

**Example Scenario:**
```
coverage_target_percent = 90
max_coverage_cap        = 95

Month 1: Coverage 85% → Purchase allowed (aiming for 90%)
Month 2: Coverage 94% → Purchase allowed if it stays ≤95%
Month 3: Coverage 96% → Purchase BLOCKED (exceeds cap)
```

---

### Renewal Window

**Type:** Operational concept

**Configuration:** `purchase_strategy.renewal_window_days` (default: 7 days)

**Definition:** Time period before a Savings Plan expires during which the module **excludes** that plan from coverage calculations.

**Purpose:** Prevents over-purchasing by accounting for plans about to expire. Without this, the module would see artificially high coverage and skip purchases, then coverage would drop sharply when plans expire.

**Example:**
```hcl
purchase_strategy = {
  renewal_window_days = 7  # Exclude plans expiring within 7 days
}
```

**How It Works:**

| Plan Status | Included in Coverage? |
|-------------|-----------------------|
| Active, expires in 30 days | ✓ Yes |
| Active, expires in 8 days | ✓ Yes |
| Active, expires in 6 days | ✗ No (within renewal window) |
| Active, expires tomorrow | ✗ No (within renewal window) |
| Expired | ✗ No |

**Calculation Impact:**
```
Current coverage = 90% (includes plan expiring in 5 days worth 10%)
Adjusted coverage = 80% (plan excluded from calculation)
Module recommends purchase to reach target of 90%
```

**Recommended Values:**
| Days | Use Case |
|------|----------|
| 7 | Default, monthly purchase cycles |
| 14 | Conservative, bi-weekly cycles |
| 30 | Proactive replacement for large plans |

---

## Purchase Strategy Concepts

### Simple Strategy

**Type:** Purchase strategy

**Definition:** Purchases a fixed percentage of AWS Cost Explorer recommendations each cycle, regardless of coverage gap.

**Configuration:**
```hcl
purchase_strategy = {
  coverage_target_percent = 90
  max_coverage_cap        = 95

  simple = {
    max_purchase_percent = 10  # Purchase 10% of AWS recommendation
  }
}
```

**Characteristics:**
- **Fixed percentage** every cycle
- **Linear progression** to target coverage
- **Predictable** purchase amounts
- **Easy to understand** and forecast

**How It Works:**
```
AWS recommendation: $1,000/hour commitment needed
max_purchase_percent: 10
→ Purchase: $100/hour ($1,000 × 10%)
```

**Progression Example:**

| Month | Coverage | AWS Rec | Purchase (10%) | Result |
|-------|----------|---------|----------------|--------|
| 1 | 0% | $1,000 | $100 | 10% coverage |
| 2 | 10% | $900 | $90 | 19% coverage |
| 3 | 19% | $810 | $81 | 27.1% coverage |
| 4 | 27.1% | $729 | $72.90 | 34.4% coverage |

**Best For:**
- Stable workloads with predictable growth
- Small adjustments to existing coverage
- Simple, easy-to-forecast budgeting

**Not Ideal For:**
- New deployments starting from 0% coverage (slow ramp-up)
- Highly variable workloads

---

### Dichotomy Strategy

**Type:** Purchase strategy

**Definition:** Adaptively sizes purchases using exponential halving (binary search approach) based on coverage gap. Purchases the largest percentage that won't exceed the target.

**Configuration:**
```hcl
purchase_strategy = {
  coverage_target_percent = 90
  max_coverage_cap        = 95

  dichotomy = {
    max_purchase_percent = 50  # Start halving from 50%
    min_purchase_percent = 1   # Never purchase less than 1%
  }
}
```

**Algorithm:**
1. Start with `max_purchase_percent` (e.g., 50%)
2. If purchase would exceed target, halve the percentage (50% → 25% → 12.5% → ...)
3. Keep halving until purchase fits within target
4. Stop if percentage drops below `min_purchase_percent`

**Progression Example:**

| Month | Coverage | Gap to 90% | Try Purchase | Result | Actual Purchase |
|-------|----------|------------|--------------|--------|-----------------|
| 1 | 0% | 90% | 50% ✓ | 50% | **50%** |
| 2 | 50% | 40% | 50% ✗ (→100%)<br>25% ✓ | 75% | **25%** |
| 3 | 75% | 15% | 50% ✗<br>25% ✗ (→100%)<br>12.5% ✓ | 87.5% | **12.5%** |
| 4 | 87.5% | 2.5% | 50%/25%/12.5% ✗<br>6.25%/3.125%/1.5625% ✓ | 89.06% | **1.5625%** |

**Characteristics:**
- **Adaptive sizing** — Large purchases initially, smaller as target approaches
- **Fast ramp-up** — Reaches high coverage quickly
- **Distributed commitments** — Creates many smaller plans over time
- **Lower over-commitment risk** — Halving prevents overshoot
- **Automatic** — No manual adjustment needed

**Benefits Over Simple:**

| Aspect | Simple (10%) | Dichotomy (50% max) |
|--------|--------------|---------------------|
| Time to 90% from 0% | ~22 months | ~4 months |
| Purchase distribution | Uniform | Front-loaded |
| Plan replacement | Manual concern | Natural distribution |
| Over-commitment risk | Moderate | Low (halving prevents) |

**Best For:**
- **New deployments** starting from low coverage
- **Variable workloads** with fluctuating usage
- **Risk-conscious** deployments wanting distributed commitments
- **Faster ramp-up** to target coverage

**See Also:** [examples/dichotomy-strategy/](examples/dichotomy-strategy/) for detailed usage guide.

---

### Conservative Strategy

**Type:** Purchase strategy

**Definition:** Only purchases when the coverage gap exceeds a minimum threshold, then purchases up to a maximum percentage. Prevents tiny, frequent purchases.

**Configuration:**
```hcl
purchase_strategy = {
  coverage_target_percent = 90
  max_coverage_cap        = 95

  conservative = {
    min_gap_threshold    = 5   # Only purchase if gap ≥ 5%
    max_purchase_percent = 15  # Purchase up to 15% of recommendation
  }
}
```

**How It Works:**
```
Coverage gap = coverage_target_percent - current_coverage

If gap < min_gap_threshold:
  → No purchase (gap too small)
Else:
  → Purchase up to max_purchase_percent of AWS recommendation
```

**Behavior Example:**

| Current Coverage | Gap to 90% | Action |
|------------------|------------|--------|
| 88% | 2% | **No purchase** (gap < 5% threshold) |
| 84% | 6% | Purchase 15% of recommendation |
| 70% | 20% | Purchase 15% of recommendation |

**Best For:**
- Avoiding frequent small purchases
- Reducing API calls and operational overhead
- Workloads with stable coverage near target

**See Also:** [examples/conservative-strategy/](examples/conservative-strategy/)

---

### Term Mix

**Type:** Configuration concept

**Definition:** The distribution of 1-year and 3-year Savings Plans as percentages that sum to 1.0 (100%).

**Applies To:** Compute and SageMaker Savings Plans (Database is 1-year only per AWS constraint)

**Configuration:**
```hcl
sp_plans = {
  compute = {
    enabled                = true
    all_upfront_three_year = 0.67  # 67% of purchases are 3-year plans
    all_upfront_one_year   = 0.33  # 33% of purchases are 1-year plans
  }
}
```

**Payment Option Combinations:**

Each term can have multiple payment options. All percentages **must sum to 1.0**:

```hcl
sp_plans = {
  compute = {
    enabled                    = true
    all_upfront_three_year     = 0.5   # 50%
    partial_upfront_three_year = 0.2   # 20%
    all_upfront_one_year       = 0.2   # 20%
    no_upfront_one_year        = 0.1   # 10%
    # Total = 1.0 ✓
  }
}
```

**Why It Matters:**

| Term | Discount | Flexibility | Risk |
|------|----------|-------------|------|
| **3-year** | Higher (up to 66%) | Low (3-year commitment) | Higher if usage changes |
| **1-year** | Lower (up to 40%) | Higher (1-year commitment) | Lower if usage changes |

**Common Strategies:**

| Mix | Use Case |
|-----|----------|
| 100% 1-year | Maximum flexibility, new workloads |
| 67% 3-year, 33% 1-year | Balanced savings + flexibility |
| 100% 3-year | Maximum savings, stable workloads |

**Execution:**
When purchasing $100/hour commitment with 70% 3-year, 30% 1-year:
- Creates 3-year plan: $70/hour commitment
- Creates 1-year plan: $30/hour commitment

---

## Operational Concepts

### Review Window

**Type:** Operational workflow

**Definition:** Time period between when purchases are **scheduled** (Scheduler Lambda) and when they are **executed** (Purchaser Lambda).

**Configuration:**
```hcl
scheduler = {
  scheduler = "cron(0 8 1 * ? *)"   # 1st of month - Schedule purchases
  purchaser = "cron(0 8 4 * ? *)"   # 4th of month - Execute purchases
}
# Review window = 3 days
```

**Purpose:**
Allows human review and cancellation of scheduled purchases before financial commitment.

**Workflow:**

```
Day 1 (Scheduler runs):
  ↓ Analyzes coverage
  ↓ Queues purchase intents to SQS
  ↓ Sends email notification

Days 1-3 (Review window):
  → Humans review scheduled purchases
  → Delete SQS messages to cancel unwanted purchases

Day 4 (Purchaser runs):
  ↓ Processes remaining SQS messages
  ↓ Executes purchases
  ↓ Sends confirmation email
```

**How to Cancel Purchases:**
1. AWS Console → SQS → `sp-autopilot-purchase-intents` queue
2. View messages
3. Delete messages for purchases to cancel
4. Purchaser Lambda skips deleted messages

**Recommended Windows:**

| Schedule Gap | Use Case |
|--------------|----------|
| 1-2 days | Fast iteration, frequent reviews |
| 3-5 days | Standard production (recommended) |
| 7-14 days | Conservative, manual approval process |

**Example Schedules:**

```hcl
# 3-day review window
scheduler = {
  scheduler = "cron(0 8 1 * ? *)"   # 1st
  purchaser = "cron(0 8 4 * ? *)"   # 4th
}

# 7-day review window
scheduler = {
  scheduler = "cron(0 8 1 * ? *)"   # 1st
  purchaser = "cron(0 8 8 * ? *)"   # 8th
}
```

---

### dry_run

**Type:** Configuration parameter

**Definition:** When enabled, Scheduler Lambda sends email notifications with purchase recommendations but does **not** queue purchases to SQS. No purchases are executed.

**Configuration:**
```hcl
lambda_config = {
  scheduler = {
    dry_run = true  # Email only, no purchases
  }
}
```

**Behavior:**

| dry_run | Email Sent? | SQS Queued? | Purchases Executed? |
|---------|-------------|-------------|---------------------|
| `true` | ✓ Yes | ✗ No | ✗ No |
| `false` | ✓ Yes | ✓ Yes | ✓ Yes (if Purchaser runs) |

**Use Cases:**

**1. Initial Testing**
```hcl
# Week 1: Validate recommendations
lambda_config = {
  scheduler = { dry_run = true }
}
```

**2. Gradual Rollout**
```hcl
# Week 1-2: Dry run to review recommendations
# Week 3+: Enable purchases
lambda_config = {
  scheduler = { dry_run = false }
}
```

**3. Temporary Pause**
```hcl
# Pause purchases during major infrastructure changes
lambda_config = {
  scheduler = { dry_run = true }
}
```

**Email Notification:**
Dry-run emails include a clear header indicating no purchases were scheduled:

```
Subject: [DRY RUN] Savings Plans Recommendations - No Purchases Scheduled

This is a dry-run execution. Recommendations shown below,
but no purchases were queued.
```

**Recommended Practice:**
Always start new deployments with `dry_run = true` to validate recommendations before enabling automated purchases.

---

### Idempotency

**Type:** Operational safeguard

**Definition:** Ensures duplicate purchases are prevented even if the same request is submitted multiple times.

**Implementation:**
Each purchase intent includes a unique `clientToken` (UUID) generated by Scheduler Lambda. AWS Savings Plans API rejects duplicate tokens.

**How It Works:**

```
Scheduler Lambda:
  ↓ Generates purchase intent
  ↓ Assigns UUID: "a1b2c3d4-e5f6-..."
  ↓ Sends to SQS queue

Purchaser Lambda (first attempt):
  ↓ Calls CreateSavingsPlan API with clientToken
  ✓ Purchase succeeds

Purchaser Lambda (retry/duplicate):
  ↓ Calls CreateSavingsPlan API with SAME clientToken
  ✗ AWS returns DuplicateSavingsPlanException
  ✓ Purchaser logs as warning, deletes message (success)
```

**Scenarios Prevented:**

**1. Lambda Retry**
```
Purchaser timeout → Lambda retries → Same clientToken → Duplicate rejected
```

**2. Manual Re-Run**
```
Operator re-runs Purchaser manually → Same SQS messages → Duplicate rejected
```

**3. SQS Visibility Timeout**
```
Message returns to queue → Processed again → Duplicate rejected
```

**Error Handling:**
```
DuplicateSavingsPlanException → Warning logged → Message deleted → No retry
```

This is **expected behavior** and indicates idempotency working correctly.

**CloudWatch Logs:**
```
[WARNING] Duplicate Savings Plan request:
clientToken=a1b2c3d4-e5f6-... already exists.
This is normal - plan already purchased.
```

**Related:** [ERROR_PATTERNS.md - DuplicateSavingsPlanException](ERROR_PATTERNS.md#duplicatesavingsplanexception)

---

## Configuration Concepts

### lookback_days

**Type:** Configuration parameter

**Definition:** Number of days of historical usage data AWS Cost Explorer uses to generate Savings Plans recommendations.

**Configuration:**
```hcl
purchase_strategy = {
  lookback_days = 30  # Default: 30 days
}
```

**AWS API:** Used in `ce:GetSavingsPlansPurchaseRecommendation` API call.

**Range:** 7, 30, or 60 days (AWS Cost Explorer constraint)

**Impact:**
- **7 days** → Recommendations based on recent usage (more reactive)
- **30 days** → Balanced view (recommended default)
- **60 days** → Long-term trends (more conservative)

**Use Cases:**

| Days | Use Case |
|------|----------|
| 7 | Rapidly changing workloads, new services |
| 30 | Standard production workloads (default) |
| 60 | Seasonal workloads, long-term trends |

---

### min_data_days

**Type:** Configuration parameter

**Definition:** Minimum number of days of usage data required before generating purchase recommendations. Prevents purchases based on insufficient data.

**Configuration:**
```hcl
purchase_strategy = {
  min_data_days = 14  # Default: 14 days minimum required
}
```

**Behavior:**
```
If usage history < min_data_days:
  → Warning logged
  → No purchase recommended
  → Email sent: "Insufficient data for recommendation"

If usage history ≥ min_data_days:
  → Proceed with normal purchase logic
```

**Recommended Values:**

| Days | Use Case |
|------|----------|
| 7 | Fast iteration, testing |
| 14 | Standard (default, 2 weeks minimum) |
| 30 | Conservative, mature workloads only |

**Related Error:** [ERROR_PATTERNS.md - DataUnavailableException](ERROR_PATTERNS.md#dataunavailableexception)

---

### min_commitment_per_plan

**Type:** Configuration parameter

**Definition:** Minimum hourly commitment per individual Savings Plan. AWS enforces a minimum of $0.001/hour.

**Configuration:**
```hcl
purchase_strategy = {
  min_commitment_per_plan = 0.001  # Default: AWS minimum
}
```

**Purpose:**
Prevents creation of tiny Savings Plans that provide negligible savings but increase management overhead.

**AWS Constraint:** Cannot be less than $0.001/hour (~$0.73/month)

**Common Values:**

| Value | Monthly Cost | Use Case |
|-------|--------------|----------|
| $0.001 | ~$0.73 | AWS minimum (default) |
| $0.01 | ~$7.30 | Small workloads |
| $0.10 | ~$73 | Standard minimum |
| $1.00 | ~$730 | Large-scale only |

**Validation:**
If calculated purchase is below minimum:
```
Calculated commitment: $0.0005/hour
min_commitment_per_plan: $0.001/hour
→ ValidationException: "Invalid hourly commitment value"
→ Purchase skipped, message deleted
```

**Related Error:** [ERROR_PATTERNS.md - ValidationException](ERROR_PATTERNS.md#validationexception)

---

## Savings Plan Types

### Compute Savings Plans

**Coverage:** EC2 instances, AWS Lambda, AWS Fargate

**Terms Available:** 1-year, 3-year

**Payment Options:** All Upfront, Partial Upfront, No Upfront

**Max Discount:** Up to 66%

**Flexibility:** Highest (any instance family, size, region, OS, tenancy)

**Configuration:**
```hcl
sp_plans = {
  compute = {
    enabled              = true
    all_upfront_one_year = 1  # 100% 1-year All Upfront
  }
}
```

**Use Case:** General compute workloads with flexibility requirements

---

### Database Savings Plans

**Coverage:** RDS, Aurora, DynamoDB, ElastiCache (Valkey), DocumentDB, Neptune, Keyspaces, Timestream, DMS

**Terms Available:** **1-year ONLY** (AWS constraint)

**Payment Options:** **No Upfront ONLY** (AWS constraint)

**Max Discount:** Up to 35% (serverless), up to 20% (provisioned)

**Flexibility:** Covers multiple database services

**Configuration:**
```hcl
sp_plans = {
  database = {
    enabled             = true
    no_upfront_one_year = 1  # Must be 1.0 (AWS constraint)
  }
}
```

**⚠️ Important:** Database Savings Plans have fixed constraints. The term and payment option cannot be changed.

**Use Case:** Database workloads across multiple AWS database services

---

### SageMaker Savings Plans

**Coverage:** SageMaker training, real-time inference, serverless inference, notebook instances

**Terms Available:** 1-year, 3-year

**Payment Options:** All Upfront, Partial Upfront, No Upfront

**Max Discount:** Up to 64%

**Flexibility:** High (covers multiple SageMaker workload types)

**Configuration:**
```hcl
sp_plans = {
  sagemaker = {
    enabled                = true
    all_upfront_three_year = 0.7  # 70% 3-year
    all_upfront_one_year   = 0.3  # 30% 1-year
  }
}
```

**Use Case:** Machine learning workloads on Amazon SageMaker

---

## Quick Reference

### Configuration Hierarchy

```
purchase_strategy
  ├── coverage_target_percent    → Goal to reach
  ├── max_coverage_cap           → Hard ceiling (safety)
  ├── lookback_days              → Historical data window
  ├── min_data_days              → Minimum data required
  ├── renewal_window_days        → Exclude expiring plans
  ├── min_commitment_per_plan    → Minimum plan size
  └── Strategy Type
      ├── simple                 → Fixed % purchases
      ├── dichotomy              → Adaptive halving
      └── conservative           → Gap threshold purchases

sp_plans
  ├── compute
  │   ├── enabled
  │   └── term_mix (must sum to 1.0)
  ├── database
  │   ├── enabled
  │   └── no_upfront_one_year = 1 (AWS constraint)
  └── sagemaker
      ├── enabled
      └── term_mix (must sum to 1.0)

lambda_config
  └── scheduler
      └── dry_run                → Email only (no purchases)

scheduler
  ├── scheduler                  → When to schedule purchases
  └── purchaser                  → When to execute purchases
      └── Gap = Review window
```

---

## See Also

- **[README.md](README.md)** — Module overview and quick start
- **[variables.tf](variables.tf)** — Complete variable documentation
- **[ERROR_PATTERNS.md](ERROR_PATTERNS.md)** — Common errors and troubleshooting
- **[examples/](examples/)** — Working configuration examples
- **[CONTRIBUTING.md](CONTRIBUTING.md)** — Development and contribution guide

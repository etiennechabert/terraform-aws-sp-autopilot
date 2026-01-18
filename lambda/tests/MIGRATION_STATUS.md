# Test Fixture Migration Status

This document tracks the migration of tests from inline AWS API mocks to the `aws_mock_builder` fixture system.

## Benefits of Migration

✅ **Real AWS structure** - Tests use complete AWS API response formats (not 10% of fields)
✅ **Easier to maintain** - Update one fixture file instead of many inline mocks
✅ **Catches structural bugs** - Real responses expose issues like wrong GroupBy dimensions
✅ **Better test quality** - Tests verify against realistic data structures

## Migration Progress

### Completed Migrations

#### Scheduler Lambda (`lambda/scheduler/tests/`)

**test_coverage.py** - ✅ 3/3 tests migrated
- `test_calculate_current_coverage_success`
- `test_calculate_current_coverage_filters_expiring_plans`
- `test_calculate_current_coverage_no_coverage_data`

**test_recommendations.py** - ✅ 2/2 high-priority tests migrated
- `test_fetch_compute_sp_recommendation_success`
- `test_fetch_compute_sp_recommendation_no_recommendations`

**test_handler.py** - ✅ 3/12 tests migrated
- `test_get_aws_recommendations_compute_enabled`
- `test_get_aws_recommendations_database_enabled`
- `test_get_aws_recommendations_sagemaker_enabled`

#### Reporter Lambda (`lambda/reporter/tests/`)

**test_savings_utilization.py** - ✅ 1/8 tests migrated
- `test_get_savings_data_with_detailed_utilization`

#### Purchaser Lambda (`lambda/purchaser/tests/`)

**test_integration.py** - ✅ 1/15 tests migrated
- `test_valid_purchase_success`

**Total: 10 tests migrated across all 3 lambdas**

---

## Remaining High-Priority Migrations

### Scheduler Lambda

**test_handler.py** (9 more tests recommended):
- `test_calculate_current_coverage_with_expiring_plans` - Line ~93
- `test_get_aws_recommendations_parallel_execution_both_enabled` - Line ~520
- `test_handler_dry_run_mode` - Line ~1463
- `test_handler_integration_success` - Multiple coverage/recommendation mocks
- `test_handler_no_recommendations` - Coverage mocking
- `test_handler_coverage_api_error` - Error handling tests
- Plus 3-4 more integration tests with AWS API mocking

### Reporter Lambda

**test_essential.py** (2 tests recommended):
- `test_get_coverage_history_success` - Line ~104
- `test_get_savings_data_with_active_plans` - Line ~130

**test_savings_utilization.py** (3 more tests):
- `test_get_coverage_history_with_multiple_days` - Line ~148
- `test_get_savings_data_no_utilization` - Line ~109
- `test_calculate_average_utilization` - Utilization data mocking

**test_report_generation.py** (1 test):
- `test_get_actual_costs_success` - Line ~169

### Purchaser Lambda

**test_integration.py** (2 more tests):
- `test_cap_enforcement` - Line ~144
- `test_expiring_plans_renewal` - Line ~567

---

## Migration Pattern

### Before (Inline Mock)
```python
def test_coverage(mock_ce_client):
    mock_ce_client.get_savings_plans_coverage.return_value = {
        "SavingsPlansCoverages": [{
            "TimePeriod": {"Start": "2026-01-14", "End": "2026-01-15"},
            "Coverage": {"CoveragePercentage": "75.5"},  # Missing 90% of AWS fields!
        }]
    }
```

### After (Fixture Builder)
```python
def test_coverage(aws_mock_builder, mock_ce_client):
    # Real AWS structure with all fields, easy customization
    mock_ce_client.get_savings_plans_coverage.return_value = (
        aws_mock_builder.coverage(coverage_percentage=75.5)
    )
```

---

## Quick Reference for Migration

### Common Migrations

**Coverage Responses:**
```python
# Before
mock_ce.get_savings_plans_coverage.return_value = {
    "SavingsPlansCoverages": [{"Coverage": {"CoveragePercentage": "75.5"}}]
}

# After
mock_ce.get_savings_plans_coverage.return_value = aws_mock_builder.coverage(
    coverage_percentage=75.5
)
```

**Recommendations:**
```python
# Before
mock_ce.get_savings_plans_purchase_recommendation.return_value = {
    "Metadata": {"RecommendationId": "rec-123"},
    "SavingsPlansPurchaseRecommendation": {
        "SavingsPlansPurchaseRecommendationDetails": [{"HourlyCommitmentToPurchase": "5.50"}]
    }
}

# After
mock_ce.get_savings_plans_purchase_recommendation.return_value = (
    aws_mock_builder.recommendation('database', hourly_commitment=5.50)
)
```

**Describe Savings Plans:**
```python
# Before
mock_sp.describe_savings_plans.return_value = {
    "savingsPlans": [{"savingsPlanId": "sp-123", "state": "active"}]
}

# After
mock_sp.describe_savings_plans.return_value = (
    aws_mock_builder.describe_savings_plans(plans_count=1)
)
```

**Create Savings Plan:**
```python
# Before
mock_sp.create_savings_plan.return_value = {"savingsPlanId": "sp-12345678"}

# After
mock_sp.create_savings_plan.return_value = (
    aws_mock_builder.create_savings_plan(savings_plan_id="sp-12345678")
)
```

---

## Available Builder Methods

See `lambda/tests/fixtures/aws_responses/README.md` for complete documentation.

**Quick list:**
- `describe_savings_plans(plans_count=2, state='active')`
- `coverage(coverage_percentage=None, services=None, empty=False)`
- `coverage_history(coverage_percentage=None, days=None)`
- `recommendation(sp_type='database', hourly_commitment=None, empty=False)`
- `utilization(utilization_percentage=None, days=None)`
- `cost_and_usage(days=None)`
- `create_savings_plan(savings_plan_id=None)`

---

## Tests NOT Recommended for Migration

These tests don't use AWS API mocks or use minimal simple mocks:

- **Strategy tests** (simple_strategy, conservative_strategy, dichotomy_strategy)
- **Pure validation tests** (purchaser validation tests)
- **Queue management tests** (SQS mocking is simple enough)
- **Pure business logic tests** (work with processed data, not raw AWS responses)

---

## How to Continue Migration

1. Pick a test from "Remaining High-Priority Migrations" above
2. Add `aws_mock_builder` to the test function parameters
3. Replace inline AWS API mocks with `aws_mock_builder.*()` calls
4. Remove hardcoded IDs/metadata (RecommendationId, GenerationTimestamp) from assertions - use `assert "RecommendationId" in result` instead
5. Test still passes with real AWS response structure

---

## Questions?

See:
- `lambda/tests/conftest.py` - Fixture implementation
- `lambda/tests/fixtures/aws_responses/README.md` - Complete usage guide
- Migrated tests above - Working examples

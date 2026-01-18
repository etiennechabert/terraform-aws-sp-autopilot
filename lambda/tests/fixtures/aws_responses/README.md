# AWS API Response Fixtures

This directory contains anonymized AWS Cost Explorer and Savings Plans API responses used for testing.

## Files

- `describe_savings_plans.json` - Response from `savingsplans:DescribeSavingsPlans`
- `create_savings_plan.json` - Response from `savingsplans:CreateSavingsPlan`
- `get_cost_and_usage.json` - Response from `ce:GetCostAndUsage` grouped by PURCHASE_TYPE
- `get_savings_plans_coverage_grouped.json` - Response from `ce:GetSavingsPlansCoverage` grouped by SERVICE
- `get_savings_plans_coverage_history.json` - Response from `ce:GetSavingsPlansCoverage` ungrouped (30 days)
- `get_savings_plans_utilization.json` - Response from `ce:GetSavingsPlansUtilization`
- `recommendation_compute_sp.json` - Response from `ce:GetSavingsPlansPurchaseRecommendation` for Compute SP (empty)
- `recommendation_database_sp.json` - Response from `ce:GetSavingsPlansPurchaseRecommendation` for Database SP
- `recommendation_sagemaker_sp.json` - Response from `ce:GetSavingsPlansPurchaseRecommendation` for SageMaker SP

## Anonymization

All sensitive data has been anonymized:
- Account IDs changed to `123456789012`
- All UUIDs randomized
- All cost values randomized but kept realistic
- Dates changed to generic 2026 timestamps

## Structure Preserved

The JSON structure, field names, data types, and relationships exactly match real AWS API responses.

## Usage in Tests

### Option 1: Use aws_mock_builder (Recommended)

The `aws_mock_builder` fixture provides real AWS response structures with easy customization:

```python
def test_coverage_calculation(aws_mock_builder, mock_ce_client):
    # Use real AWS structure with custom coverage percentage
    mock_ce_client.get_savings_plans_coverage.return_value = aws_mock_builder.coverage(
        coverage_percentage=85.5
    )

    # Test your code...
    result = calculate_coverage(mock_ce_client)
    assert result['compute'] == 85.5
```

#### Available Builder Methods

**describe_savings_plans(plans_count=2, state='active')**
```python
# Get 1 active plan
response = aws_mock_builder.describe_savings_plans(plans_count=1)

# Get 0 plans (no SPs)
response = aws_mock_builder.describe_savings_plans(plans_count=0)
```

**coverage(coverage_percentage=None, services=None, empty=False)**
```python
# Custom coverage percentage across all services
response = aws_mock_builder.coverage(coverage_percentage=75.0)

# Empty coverage (no data)
response = aws_mock_builder.coverage(empty=True)

# Filter to specific services
response = aws_mock_builder.coverage(services=["AWS Lambda", "Amazon EC2"])
```

**coverage_history(coverage_percentage=None, days=None)**
```python
# 7 days of coverage history
response = aws_mock_builder.coverage_history(days=7)

# Custom coverage percentage for all days
response = aws_mock_builder.coverage_history(coverage_percentage=90.0, days=14)
```

**recommendation(sp_type='database', hourly_commitment=None, empty=False)**
```python
# Database SP recommendation with custom commitment
response = aws_mock_builder.recommendation('database', hourly_commitment=20.0)

# Empty recommendation (AWS has no recommendations)
response = aws_mock_builder.recommendation('compute', empty=True)

# SageMaker SP recommendation
response = aws_mock_builder.recommendation('sagemaker', hourly_commitment=8.95)
```

**utilization(utilization_percentage=None, days=None)**
```python
# 30 days of utilization data
response = aws_mock_builder.utilization(days=30)

# Custom utilization percentage
response = aws_mock_builder.utilization(utilization_percentage=95.0)
```

**cost_and_usage(days=None)**
```python
# 7 days of cost data
response = aws_mock_builder.cost_and_usage(days=7)
```

**create_savings_plan(savings_plan_id=None)**
```python
# Default response with anonymized SP ID
response = aws_mock_builder.create_savings_plan()

# Custom Savings Plan ID
response = aws_mock_builder.create_savings_plan(savings_plan_id='sp-custom-12345')
```

#### Advanced Customization

For fields not covered by builder methods, customize after loading:

```python
def test_expiring_plans(aws_mock_builder):
    plans = aws_mock_builder.describe_savings_plans(plans_count=2)

    # Customize specific fields
    plans['savingsPlans'][0]['end'] = '2026-02-01T00:00:00Z'
    plans['savingsPlans'][1]['end'] = '2026-03-01T00:00:00Z'

    mock_client.describe_savings_plans.return_value = plans
```

### Option 2: Load Fixture Files Directly

Load raw fixture files for read-only use:

```python
def test_something(aws_response):
    # Load any fixture by filename
    response = aws_response('describe_savings_plans.json')
    mock_client.describe_savings_plans.return_value = response
```

### Option 3: Use Pre-loaded Fixtures

Use named fixtures for common responses:

```python
def test_coverage(aws_get_savings_plans_coverage_grouped, mock_ce_client):
    # Fixture is already loaded
    mock_ce_client.get_savings_plans_coverage.return_value = (
        aws_get_savings_plans_coverage_grouped
    )
```

Available pre-loaded fixtures:
- `aws_describe_savings_plans`
- `aws_create_savings_plan`
- `aws_get_cost_and_usage`
- `aws_get_savings_plans_coverage_grouped`
- `aws_get_savings_plans_coverage_history`
- `aws_get_savings_plans_utilization`
- `aws_recommendation_compute_sp`
- `aws_recommendation_database_sp`
- `aws_recommendation_sagemaker_sp`

## Benefits of Using Fixtures

✅ **Real AWS structure** - Tests use actual AWS API response formats
✅ **Complete field coverage** - All AWS fields included (not just 2-3 like inline mocks)
✅ **Easy customization** - Builder methods make common changes simple
✅ **Single source of truth** - Update one fixture file instead of many test mocks
✅ **Catches structural bugs** - Real responses expose issues like wrong GroupBy dimensions

## Migration Examples

**Before (Inline Mock):**
```python
def test_coverage(mock_ce_client):
    mock_ce_client.get_savings_plans_coverage.return_value = {
        "SavingsPlansCoverages": [{
            "TimePeriod": {"Start": "2026-01-14", "End": "2026-01-15"},
            "Coverage": {"CoveragePercentage": "75.5"},  # Missing 90% of fields!
        }]
    }
```

**After (Fixture Builder):**
```python
def test_coverage(aws_mock_builder, mock_ce_client):
    # Real AWS structure with all fields, easy customization
    mock_ce_client.get_savings_plans_coverage.return_value = (
        aws_mock_builder.coverage(coverage_percentage=75.5)
    )
```

See `lambda/tests/conftest.py` for fixture implementation details.

# Testing Guidelines

**MANDATORY READING FOR ALL CONTRIBUTORS**

This document defines strict testing requirements for the project. All tests MUST follow these guidelines. Non-compliant tests will be rejected in code review.

---

## Core Testing Principles (MANDATORY)

### 1. Test Through Handler Entry Point ONLY

**Rule:** Every Lambda test MUST call `handler.handler(event, context)` as the entry point.

**Why:**
- Reflects real AWS invocation behavior
- Catches integration issues between modules
- **Prevents dead code** - unused code will never be called and tests will fail
- Tests the actual execution path users/AWS will invoke

**Forbidden:**
```python
# ❌ WRONG - Testing internal functions directly
def test_get_coverage_data():
    result = handler.get_coverage_data(client, config)
    assert result is not None

# ❌ WRONG - Mocking internal functions
with patch("handler.get_coverage_data") as mock:
    mock.return_value = {...}
    handler.handler({}, {})
```

**Required:**
```python
# ✅ CORRECT - Testing through handler entry point
def test_handler_success(mock_clients):
    mock_clients["ce"].get_savings_plans_coverage.return_value = {...}

    response = handler.handler({}, {})

    assert response["statusCode"] == 200
```

### 2. Mock at AWS Boundary ONLY

**Rule:** Mock ONLY boto3 client responses. Never mock internal functions, classes, or shared modules.

**Why:**
- Tests your business logic, not AWS
- Allows refactoring internals without breaking tests
- Prevents brittle tests coupled to implementation
- **Forces code to be called through handler** - if it's not, tests fail

**Forbidden:**
```python
# ❌ WRONG - Mocking internal implementation
with patch("handler.calculate_coverage") as mock:
    ...

# ❌ WRONG - Mocking shared modules
with patch("shared.spending_analyzer.SpendingAnalyzer") as mock:
    ...

# ❌ WRONG - Mocking helper functions
with patch("handler.format_email") as mock:
    ...
```

**Required:**
```python
# ✅ CORRECT - Mocking AWS client responses only
mock_clients["ce"].get_cost_and_usage.return_value = aws_mock_builder.cost_data(...)
mock_clients["savingsplans"].describe_savings_plans.return_value = aws_mock_builder.describe_savings_plans(...)
```

### 3. Dead Code Detection

**Rule:** If code is not called by the handler during tests, it MUST be detected and removed.

**Why:**
- Prevents accumulation of unused code
- Ensures test coverage is meaningful
- Forces cleanup during refactoring

**How it works:**
- Tests call `handler()` → handler calls internal code → internal code gets tested
- Unused code never gets called → tests can't accidentally pass
- Coverage reports show uncovered code → must be deleted or made reachable

**Example:**
```python
# If you have a function that's never imported/called:
def get_savings_data():  # This function exists but nothing calls it
    ...

# Your tests will NEVER test it (because they only call handler)
# Coverage will show it as uncovered
# Result: You must either use it or delete it
```

---

## Required Test Structure

### Fixtures (Every Lambda Must Have)

```python
@pytest.fixture
def mock_env_vars(monkeypatch):
    """Set up ALL required environment variables."""
    monkeypatch.setenv("QUEUE_URL", "https://sqs.us-east-1.amazonaws.com/123456789012/test")
    monkeypatch.setenv("SNS_TOPIC_ARN", "arn:aws:sns:us-east-1:123456789012:test")
    # ... ALL env vars required by your lambda

@pytest.fixture
def mock_clients():
    """Mock AWS clients at the initialization boundary."""
    with patch("shared.handler_utils.initialize_clients") as mock_init:
        mock_sqs = Mock()
        mock_sns = Mock()
        mock_ce = Mock()
        mock_sp = Mock()

        mock_init.return_value = {
            "sqs": mock_sqs,
            "sns": mock_sns,
            "ce": mock_ce,
            "savingsplans": mock_sp,
        }

        yield {
            "sqs": mock_sqs,
            "sns": mock_sns,
            "ce": mock_ce,
            "savingsplans": mock_sp,
        }
```

### Test Pattern (MANDATORY)

```python
def test_<feature>_<scenario>(mock_env_vars, mock_clients, aws_mock_builder):
    """Clear description of what scenario is being tested."""

    # 1. Configure environment (if needed beyond fixture defaults)
    # monkeypatch.setenv("SOME_VAR", "value")

    # 2. Mock AWS client responses using aws_mock_builder
    mock_clients["ce"].get_savings_plans_coverage.return_value = (
        aws_mock_builder.coverage(coverage_percentage=75.0)
    )
    mock_clients["savingsplans"].describe_savings_plans.return_value = (
        aws_mock_builder.describe_savings_plans(plans_count=2)
    )

    # 3. Call handler entry point
    response = handler.handler({}, {})

    # 4. Verify outputs and side effects
    assert response["statusCode"] == 200
    assert "success" in response["body"]

    # 5. Verify AWS calls made
    assert mock_clients["savingsplans"].create_savings_plan.called
    assert mock_clients["sqs"].delete_message.call_count == 2
```

### Test Naming Convention

```
test_<feature>_<scenario>()
```

**Examples:**
- `test_handler_success_with_active_plans()`
- `test_handler_empty_queue_exits_silently()`
- `test_purchase_skipped_when_exceeds_coverage_cap()`
- `test_handler_failure_when_cost_explorer_unavailable()`

---

## Required Test Scenarios

Every Lambda MUST test these scenarios:

### 1. Success Path
```python
def test_handler_success_normal_execution(mock_env_vars, mock_clients):
    """Test successful execution with valid data."""
    # Mock valid AWS responses
    # Call handler
    # Verify success response
```

### 2. Empty/No Data
```python
def test_handler_success_with_no_data(mock_env_vars, mock_clients):
    """Test graceful handling when AWS returns no data."""
    mock_clients["sqs"].receive_message.return_value = {}  # Empty
    # Call handler
    # Verify appropriate handling
```

### 3. AWS Errors
```python
def test_handler_failure_when_aws_api_fails(mock_env_vars, mock_clients):
    """Test error handling when AWS API fails."""
    from botocore.exceptions import ClientError

    mock_clients["ce"].get_cost_and_usage.side_effect = ClientError(
        {"Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}},
        "GetCostAndUsage"
    )

    # Handler should handle gracefully or fail appropriately
```

### 4. Configuration Variations
```python
def test_handler_with_different_config(mock_env_vars, mock_clients, monkeypatch):
    """Test behavior with different configuration."""
    monkeypatch.setenv("DRY_RUN", "true")
    # Verify dry-run behavior
```

### 5. Edge Cases
```python
def test_purchase_not_made_when_at_coverage_cap(mock_env_vars, mock_clients):
    """Test cap enforcement at boundary."""
    # Mock coverage at exactly the cap
    # Verify purchase is skipped
```

---

## Using aws_mock_builder

The `aws_mock_builder` fixture provides consistent AWS response structures from real API responses.

**Location:** `lambda/tests/conftest.py`

**Available Builders:**

```python
# Savings Plans API
aws_mock_builder.describe_savings_plans(plans_count=2, state="active")
aws_mock_builder.create_savings_plan(savings_plan_id="sp-12345")

# Cost Explorer API
aws_mock_builder.coverage(coverage_percentage=75.0)
aws_mock_builder.cost_data(total_cost=1000.0, num_days=30)
aws_mock_builder.get_savings_plans_utilization(utilization_percentage=85.0)

# See lambda/tests/conftest.py for complete list
```

**Usage:**
```python
mock_clients["ce"].get_savings_plans_coverage.return_value = (
    aws_mock_builder.coverage(coverage_percentage=50.0)
)
```

**Why use it:**
- Guarantees response structure matches real AWS API
- Makes tests more maintainable
- Easier to understand test setup

---

## Verification Patterns

### Verify Handler Response
```python
response = handler.handler({}, {})

assert response["statusCode"] == 200
assert "expected_value" in json.loads(response["body"])
```

### Verify AWS Calls Made
```python
# Verify call was made
assert mock_clients["savingsplans"].create_savings_plan.called

# Verify call count
assert mock_clients["sqs"].delete_message.call_count == 3

# Verify call arguments
call_args = mock_clients["sns"].publish.call_args
assert call_args[1]["TopicArn"] == "arn:aws:sns:..."
assert "expected content" in call_args[1]["Message"]
```

### Verify AWS Calls NOT Made
```python
assert not mock_clients["sns"].publish.called
```

---

## Coverage Requirements

- **Minimum:** 80% coverage per Lambda
- **Coverage MUST come from handler invocation**
- **Uncovered code indicates:**
  - Dead code that should be deleted, OR
  - Missing test scenarios

### Running Coverage

```bash
cd lambda/scheduler
pytest --cov=. --cov-report=term-missing --cov-report=html

# View HTML report
open htmlcov/index.html
```

### Interpreting Coverage

- **Uncovered lines in handler.py:** Missing test scenarios
- **Uncovered lines in internal modules:** Either dead code OR test scenarios don't exercise that path
- **100% coverage of dead code:** Impossible if testing through handler only

---

## Integration Tests vs Unit Tests

**We write Integration Tests for Lambdas:**
- Test full Lambda execution path
- Mock only AWS (external boundary)
- Test integration between internal modules
- Test through handler entry point

**We do NOT write Unit Tests for internal functions:**
- Internal functions are tested via handler invocation
- Refactoring internals does not break tests
- Focus on behavior, not implementation

---

## Red Flags in Tests (REJECT IN CODE REVIEW)

If you see these patterns, the test is **WRONG** and must be rewritten:

| Pattern | Why It's Wrong |
|---------|----------------|
| `patch("handler.internal_func")` | Mocking internal implementation |
| `patch("shared.module.Class")` | Mocking shared code |
| `result = handler.internal_func()` | Testing internals directly |
| No `handler.handler()` call | Not testing the entry point |
| Test passes when function is deleted | Testing dead code or wrong layer |
| Mocking non-AWS code | Coupled to implementation |

---

## Examples

### ✅ GOOD Example (Purchaser)

**Reference:** `lambda/purchaser/tests/test_integration.py`

```python
def test_valid_purchase_success(aws_mock_builder, mock_env_vars, mock_clients):
    """Valid purchase executes successfully."""
    # SQS message with purchase intent
    mock_clients["sqs"].receive_message.return_value = {
        "Messages": [{"Body": json.dumps({...}), "ReceiptHandle": "..."}]
    }

    # Mock AWS responses
    mock_clients["ce"].get_savings_plans_coverage.return_value = (
        aws_mock_builder.coverage(coverage_percentage=50.0)
    )
    mock_clients["savingsplans"].describe_savings_plans.return_value = (
        aws_mock_builder.describe_savings_plans(plans_count=0)
    )
    mock_clients["savingsplans"].create_savings_plan.return_value = (
        aws_mock_builder.create_savings_plan(savings_plan_id="sp-123")
    )

    # Execute
    response = handler.handler({}, {})

    # Verify
    assert response["statusCode"] == 200
    assert mock_clients["savingsplans"].create_savings_plan.called
    assert mock_clients["sqs"].delete_message.called
```

**Why it's good:**
- ✅ Calls `handler.handler()` as entry point
- ✅ Mocks only AWS clients
- ✅ Uses `aws_mock_builder` for consistent responses
- ✅ Verifies outputs and AWS calls

### ❌ BAD Example (Reporter - OLD)

```python
def test_handler_success(mock_env_vars):
    """Test report generation."""
    with (
        patch("handler.get_coverage_history") as mock_coverage,
        patch("handler.get_savings_data") as mock_savings,
        patch("handler.generate_html_report") as mock_html,
    ):
        mock_coverage.return_value = [...]
        mock_savings.return_value = {...}
        mock_html.return_value = "<html>..."

        response = handler.handler({}, {})
        assert response["statusCode"] == 200
```

**Why it's bad:**
- ❌ Mocks internal functions that may not even exist
- ❌ These functions could be deleted and test still passes
- ❌ Doesn't test the actual code path
- ❌ Doesn't test integration between modules
- ❌ Coupled to implementation details

---

## Migration Checklist for Existing Tests

If updating old tests to follow these guidelines:

- [ ] Remove ALL `patch()` calls for internal functions
- [ ] Remove ALL `patch()` calls for shared modules
- [ ] Remove ALL direct tests of internal functions
- [ ] Ensure EVERY test calls `handler.handler(event, context)`
- [ ] Mock ONLY AWS client responses
- [ ] Use `aws_mock_builder` for AWS response structures
- [ ] Verify behavior through handler response + AWS calls
- [ ] Run coverage - delete any code that's not covered
- [ ] Verify tests fail if you delete internal code being "tested"

---

## Running Tests

```bash
# Run all tests for a Lambda
cd lambda/scheduler
pytest

# Run with coverage
pytest --cov=. --cov-report=term-missing

# Run specific test file
pytest tests/test_handler.py -v

# Run specific test
pytest tests/test_handler.py::test_handler_success -v

# Run with output
pytest -v -s
```

---

## Enforcement

These guidelines are enforced through:

1. **Code Review** - All PRs must follow these patterns
2. **Coverage Checks** - Dead code shows as uncovered
3. **This Document** - Mandatory reading for contributors
4. **Test Templates** - Use `lambda/purchaser/tests/test_integration.py` as template

---

## Quick Validation Checklist

Before submitting tests, verify:

✅ Does this test call `handler.handler()`?
✅ Am I mocking ONLY AWS clients?
✅ Am I using `aws_mock_builder` for AWS responses?
✅ Would this test FAIL if I deleted unused internal code?
✅ Does this test verify behavior through outputs/AWS calls?

If you answer NO to any question, the test is wrong.

---

## Questions?

**"Should I test this internal function directly?"**
→ No. Test it through `handler.handler()`.

**"Should I mock this shared module?"**
→ No. Mock only AWS clients.

**"This internal function is complex, shouldn't I unit test it?"**
→ No. Test it indirectly through different handler scenarios.

**"The test passes but the code isn't used anywhere."**
→ Delete the code. If tests pass without it, it's dead code.

**"How do I test error handling in an internal function?"**
→ Mock AWS to return errors, then verify handler behavior.

---

## Reference Implementations

| Lambda | Status | Notes |
|--------|--------|-------|
| `purchaser/tests/test_integration.py` | ✅ **GOLD STANDARD** | Use as template |
| `scheduler/tests/test_handler.py` | ⚠️ Mostly good | Some improvements needed |
| `reporter/tests/test_essential.py` | ❌ Needs rewrite | Violates all rules |

---

**Remember:** If your test can pass when the code it's "testing" is deleted, the test is worthless.

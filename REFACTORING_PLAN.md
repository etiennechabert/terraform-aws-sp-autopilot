# Directory Structure Refactoring Plan

## Executive Summary

This plan reorganizes the project's test directory structure for clarity and consistency:
1. **Root-level**: Rename both test directories with descriptive names
2. **Lambda folders**: Standardize all lambda functions to use `tests/` subdirectories

**Current State**: Inconsistent structure with confusing naming
**Target State**: Clean, consistent, and self-documenting structure

---

## Part 1: Root-Level Test Directory Refactoring

### Current Structure (Confusing)
```
/
├── test/                    # Terratest (Go) integration tests
│   ├── terraform_aws_sp_autopilot_test.go
│   ├── go.mod
│   ├── fixtures/
│   └── README.md
└── tests/                   # Terraform native tests
    ├── s3.tftest.hcl
    ├── sqs.tftest.hcl
    ├── sns.tftest.hcl
    ├── iam.tftest.hcl
    ├── cloudwatch.tftest.hcl
    ├── eventbridge.tftest.hcl
    └── variables.tftest.hcl
```

### Target Structure (Clear & Semantic)
```
/
└── terraform-tests/                    # All Terraform tests grouped together
    ├── unit/                          # Unit tests with mock provider (renamed from tests/)
    │   ├── s3.tftest.hcl
    │   ├── sqs.tftest.hcl
    │   ├── sns.tftest.hcl
    │   ├── iam.tftest.hcl
    │   ├── cloudwatch.tftest.hcl
    │   ├── eventbridge.tftest.hcl
    │   └── variables.tftest.hcl
    └── integration/                   # Integration tests with real AWS (renamed from test/)
        ├── terraform_aws_sp_autopilot_test.go
        ├── go.mod
        ├── fixtures/
        └── README.md
```

### Changes Required

#### 1.1 Directory Structure Creation
```bash
# Create the new structure
mkdir -p terraform-tests/unit
mkdir -p terraform-tests/integration

# Move files from old locations
mv tests/* terraform-tests/unit/
mv test/* terraform-tests/integration/

# Remove old empty directories
rmdir test/
rmdir tests/
```

#### 1.2 Workflow File Renames (for semantic clarity)

Rename workflow files to match the semantic structure:

```bash
# Rename workflow files
mv .github/workflows/terraform-tests.yml .github/workflows/terraform-unit-tests.yml
mv .github/workflows/terratest.yml .github/workflows/terraform-integration-tests.yml
```

**Current workflow names**:
- ❌ `terraform-tests.yml` → "Terraform Native Tests" (vague)
- ❌ `terratest.yml` → "Terratest Integration Tests" (tool-focused)

**New workflow names**:
- ✅ `terraform-unit-tests.yml` → "Terraform Unit Tests" (semantic)
- ✅ `terraform-integration-tests.yml` → "Terraform Integration Tests" (semantic)

#### 1.3 Workflow File Content Updates

**`.github/workflows/terraform-integration-tests.yml`** (renamed from terratest.yml):
```yaml
# Line 1 - BEFORE
name: Terratest Integration Tests

# Line 1 - AFTER
name: Terraform Integration Tests

# Line 48 - BEFORE
cache-dependency-path: test/go.mod

# Line 48 - AFTER
cache-dependency-path: terraform-tests/integration/go.mod
```

**`.github/workflows/terraform-unit-tests.yml`** (renamed from terraform-tests.yml):
```yaml
# Line 1 - BEFORE
name: Terraform Native Tests

# Line 1 - AFTER
name: Terraform Unit Tests

# Lines 93-99 - BEFORE
"tests/s3.tftest.hcl"
"tests/sqs.tftest.hcl"
"tests/sns.tftest.hcl"
"tests/iam.tftest.hcl"
"tests/cloudwatch.tftest.hcl"
"tests/eventbridge.tftest.hcl"
"tests/variables.tftest.hcl"

# Lines 93-99 - AFTER
"terraform-tests/unit/s3.tftest.hcl"
"terraform-tests/unit/sqs.tftest.hcl"
"terraform-tests/unit/sns.tftest.hcl"
"terraform-tests/unit/iam.tftest.hcl"
"terraform-tests/unit/cloudwatch.tftest.hcl"
"terraform-tests/unit/eventbridge.tftest.hcl"
"terraform-tests/unit/variables.tftest.hcl"
```

**Documentation Files** (to be identified):
- README.md - Update references from `test/` to `terraform-tests/integration/` and `tests/` to `terraform-tests/unit/`
- Any other markdown files referencing these directories

---

## Part 2: Lambda Folder Structure Standardization

### Current Structure (Inconsistent)

```
lambda/
├── purchaser/
│   ├── handler.py                   ✅ Source
│   ├── validation.py                ✅ Source
│   ├── test_handler.py              ❌ Test mixed with source
│   ├── test_integration.py          ❌ Test mixed with source
│   ├── test_notifications.py        ❌ Test mixed with source
│   └── test_validation.py           ❌ Test mixed with source
│
├── reporter/
│   ├── handler.py                   ✅ Source
│   ├── test_handler.py              ❌ Test mixed with source
│   └── test_notifications.py        ❌ Test mixed with source
│
├── scheduler/
│   ├── handler.py                   ✅ Source
│   ├── config.py                    ✅ Source
│   ├── coverage.py                  ✅ Source
│   ├── email_notifications.py       ✅ Source
│   ├── purchase_calculator.py       ✅ Source
│   ├── queue_manager.py             ✅ Source
│   ├── recommendations.py           ✅ Source
│   └── tests/                       ✅ Organized tests
│       ├── __init__.py
│       ├── test_coverage.py
│       ├── test_email_notifications.py
│       ├── test_handler.py
│       ├── test_notifications.py
│       ├── test_purchase_calculator.py
│       ├── test_queue_manager.py
│       └── test_recommendations.py
│
└── shared/
    ├── __init__.py                  ✅ Source
    ├── aws_utils.py                 ✅ Source
    ├── email_templates.py           ✅ Source
    ├── handler_utils.py             ✅ Source
    ├── notifications.py             ✅ Source
    ├── test_email_templates.py      ❌ Test mixed with source
    └── tests/                       ✅ Mostly organized
        ├── __init__.py
        └── test_handler_utils.py
```

### Target Structure (Consistent)

```
lambda/
├── purchaser/
│   ├── handler.py                   ✅ Source only
│   ├── validation.py                ✅ Source only
│   └── tests/                       ✅ All tests organized
│       ├── __init__.py              🆕 New file
│       ├── test_handler.py          📦 Moved
│       ├── test_integration.py      📦 Moved
│       ├── test_notifications.py    📦 Moved
│       └── test_validation.py       📦 Moved
│
├── reporter/
│   ├── handler.py                   ✅ Source only
│   └── tests/                       ✅ All tests organized
│       ├── __init__.py              🆕 New file
│       ├── test_handler.py          📦 Moved
│       └── test_notifications.py    📦 Moved
│
├── scheduler/
│   ├── handler.py                   ✅ No change
│   ├── config.py                    ✅ No change
│   ├── coverage.py                  ✅ No change
│   ├── email_notifications.py       ✅ No change
│   ├── purchase_calculator.py       ✅ No change
│   ├── queue_manager.py             ✅ No change
│   ├── recommendations.py           ✅ No change
│   └── tests/                       ✅ No change
│       ├── __init__.py
│       ├── test_coverage.py
│       ├── test_email_notifications.py
│       ├── test_handler.py
│       ├── test_notifications.py
│       ├── test_purchase_calculator.py
│       ├── test_queue_manager.py
│       └── test_recommendations.py
│
└── shared/
    ├── __init__.py                  ✅ No change
    ├── aws_utils.py                 ✅ No change
    ├── email_templates.py           ✅ No change
    ├── handler_utils.py             ✅ No change
    ├── notifications.py             ✅ No change
    └── tests/                       ✅ All tests organized
        ├── __init__.py              ✅ Already exists
        ├── test_email_templates.py  📦 Moved
        └── test_handler_utils.py    ✅ Already exists
```

### Changes Required

#### 2.1 Create New Directories
```bash
mkdir -p lambda/purchaser/tests
mkdir -p lambda/reporter/tests
```

#### 2.2 Create __init__.py Files
```bash
touch lambda/purchaser/tests/__init__.py
touch lambda/reporter/tests/__init__.py
```

#### 2.3 Move Test Files

**Purchaser**:
```bash
mv lambda/purchaser/test_handler.py lambda/purchaser/tests/
mv lambda/purchaser/test_integration.py lambda/purchaser/tests/
mv lambda/purchaser/test_notifications.py lambda/purchaser/tests/
mv lambda/purchaser/test_validation.py lambda/purchaser/tests/
```

**Reporter**:
```bash
mv lambda/reporter/test_handler.py lambda/reporter/tests/
mv lambda/reporter/test_notifications.py lambda/reporter/tests/
```

**Shared**:
```bash
mv lambda/shared/test_email_templates.py lambda/shared/tests/
```

#### 2.4 Update Import Statements in Test Files

All moved test files need their `sys.path.insert()` statement updated to add one more `dirname()`:

**Purchaser Tests** (4 files):
- `lambda/purchaser/tests/test_handler.py`
- `lambda/purchaser/tests/test_integration.py`
- `lambda/purchaser/tests/test_notifications.py`
- `lambda/purchaser/tests/test_validation.py`

```python
# BEFORE (when in lambda/purchaser/)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# AFTER (when in lambda/purchaser/tests/)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
```

**Reporter Tests** (2 files):
- `lambda/reporter/tests/test_handler.py`
- `lambda/reporter/tests/test_notifications.py`

```python
# BEFORE (when in lambda/reporter/)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# AFTER (when in lambda/reporter/tests/)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
```

**Shared Tests** (1 file):
- `lambda/shared/tests/test_email_templates.py`

```python
# BEFORE (when in lambda/shared/)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# AFTER (when in lambda/shared/tests/)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
```

---

## Impact Analysis

### Part 1: Root Directory & Workflow Renames

**Directories Renamed**: 2
- `test/` → `terraform-tests/integration/`
- `tests/` → `terraform-tests/unit/`

**Workflow Files Renamed**: 2
- `terraform-tests.yml` → `terraform-unit-tests.yml`
- `terratest.yml` → `terraform-integration-tests.yml`

**Workflow Content Updates**: 2 files
- `terraform-integration-tests.yml` (name field + 1 path)
- `terraform-unit-tests.yml` (name field + 7 paths)

**Documentation Files**: TBD (varies)

**Risk Level**: LOW-MEDIUM
- Straightforward rename operations
- Workflow renames require GitHub to recognize new files
- Limited number of path references
- Easy to validate with CI runs
- May require PR status check updates if workflows are required checks

### Part 2: Lambda Folder Standardization

**Files Requiring Moves**: 7
- 4 purchaser test files
- 2 reporter test files
- 1 shared test file

**Files Requiring Code Changes**: 7
- All moved test files need `sys.path.insert()` updated

**Risk Level**: LOW-MEDIUM
- Standard refactoring pattern
- Changes are mechanical and repetitive
- Tests will validate correctness immediately
- Python linting will catch any import errors

### Testing Strategy

After refactoring:
1. Run Python linting: `pytest lambda/` should work
2. Run Terraform tests: Should work with updated paths
3. Run Terratest: Should work with updated paths
4. Check CI workflows: Should pass with updated paths

---

## Rollback Plan

If issues arise, rollback is simple:
```bash
# Part 1 rollback - directories
mkdir -p test/
mkdir -p tests/
mv terraform-tests/integration/* test/
mv terraform-tests/unit/* tests/
rm -rf terraform-tests/

# Part 1 rollback - workflows
mv .github/workflows/terraform-unit-tests.yml .github/workflows/terraform-tests.yml
mv .github/workflows/terraform-integration-tests.yml .github/workflows/terratest.yml
git restore .github/workflows/terraform-tests.yml
git restore .github/workflows/terratest.yml

# Part 2 rollback - lambda folders
git restore lambda/
```

**Note**: If workflows are configured as required PR status checks in GitHub settings, you may need to update the required checks from the old names to the new names after merging.

---

## Benefits

### Part 1: Root Directory Clarity
- ✅ Semantic organization (`terraform-tests/unit/` vs `terraform-tests/integration/`)
- ✅ Groups all Terraform tests together under one parent directory
- ✅ Crystal clear distinction: unit tests (mock) vs integration tests (real AWS)
- ✅ Eliminates confusion - the directory name tells you exactly what it contains
- ✅ Clearer for new contributors - hierarchy shows relationship
- ✅ Aligns with industry testing conventions (unit/integration split)

### Part 2: Lambda Folder Consistency
- ✅ All lambda functions follow same structure
- ✅ Source and tests clearly separated
- ✅ Easier to navigate codebase
- ✅ Matches scheduler/ pattern (already working well)
- ✅ Cleaner `git status` output (tests grouped together)

---

## Execution Order

**Recommended sequence**:
1. ✅ Part 2 first (Lambda folders) - More mechanical, easier to validate
2. ✅ Part 1 second (Root directories) - Requires coordination with CI

**Reasoning**:
- Lambda refactoring doesn't affect CI workflows
- Can validate Python tests immediately
- Root directory refactoring touches CI, better to do separately

---

## Questions for Approval

1. ✅ Confirm directory structure: `terraform-tests/unit/` and `terraform-tests/integration/` (approved by user)
2. ❓ Should we do both parts in one PR or separate PRs?
3. ❓ Should we update documentation references in the same PR or separately?
4. ❓ Any specific concerns about the lambda folder changes?
5. ❓ Ready to proceed with execution?

---

**Summary**:
- **Workflow Files Renamed**: 2
- **Workflow Files Content Updated**: 2
- **Test Files Moved**: 7 (lambda tests)
- **Test Files Content Updated**: 7 (sys.path changes)
- **New Directories Created**: 4 (terraform-tests/unit, terraform-tests/integration, purchaser/tests, reporter/tests)
- **Old Directories Removed**: 2 (test/, tests/)
- **New __init__.py Files**: 2

**Total Files Changed**: ~18
**Estimated Time**: 30-45 minutes
**Testing Time**: 15-20 minutes

# Contributing to AWS Savings Plans Automation Module

Thank you for your interest in contributing to the AWS Savings Plans Automation Module! This document provides guidelines for contributing code, documentation, and other improvements.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Workflow](#development-workflow)
- [Commit Message Guidelines](#commit-message-guidelines)
- [Pull Request Process](#pull-request-process)
- [Testing Requirements](#testing-requirements)
- [Code Quality Standards](#code-quality-standards)
- [Release Process](#release-process)

## Code of Conduct

This project follows a standard code of conduct. Please be respectful and constructive in all interactions with the community.

## Getting Started

### Prerequisites

- **Terraform** >= 1.0
- **Python** >= 3.9 (for Lambda development)
- **AWS CLI** (for testing)
- **Docker** (for security scanning)
- **Git**

### Initial Setup

1. **Fork the repository** on GitHub
2. **Clone your fork**:
   ```bash
   git clone https://github.com/your-username/terraform-aws-sp-autopilot.git
   cd terraform-aws-sp-autopilot
   ```
3. **Add upstream remote**:
   ```bash
   git remote add upstream https://github.com/your-org/terraform-aws-sp-autopilot.git
   ```
4. **Install development dependencies**:
   ```bash
   # Python dependencies for Lambda testing
   cd lambda/scheduler
   pip install -r requirements.txt
   pip install pytest pytest-cov moto boto3

   cd ../purchaser
   pip install -r requirements.txt
   ```
5. **Install pre-commit hooks**:
   ```bash
   # Install pre-commit (if not already installed)
   pip install pre-commit

   # Install the git hooks
   pre-commit install
   ```

## Development Workflow

### Creating a Branch

Always create a feature branch from the latest `develop` branch:

```bash
# Update your local develop branch
git checkout develop
git pull upstream develop

# Create a feature branch
git checkout -b feature/your-feature-name
```

Branch naming conventions:
- `feature/` — New features or enhancements
- `fix/` — Bug fixes
- `docs/` — Documentation updates
- `refactor/` — Code refactoring without behavior changes
- `test/` — Adding or updating tests
- `chore/` — Maintenance tasks, dependency updates

### Local Validation

Before committing, validate your changes locally:

```bash
# Terraform validation
terraform fmt -recursive
terraform init -backend=false
terraform validate

# Security scanning
docker run --rm -v $(pwd):/src aquasec/tfsec:latest /src --minimum-severity HIGH

# Python linting and formatting
ruff check .                    # Check for linting issues
ruff format --check .           # Check formatting without making changes
ruff format .                   # Auto-format Python code

# Python tests (scheduler)
cd lambda/scheduler
pytest -v --cov=. --cov-report=term-missing --cov-fail-under=80

# Python tests (purchaser)
cd lambda/purchaser
python test_integration.py
```

## Commit Message Guidelines

This project uses [**Conventional Commits**](https://www.conventionalcommits.org/) for clear, structured commit messages that enable automated versioning and changelog generation.

### Commit Message Format

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Commit Types

| Type | Description | Version Impact |
|------|-------------|----------------|
| `feat` | New feature or functionality | Minor version bump (1.x.0) |
| `fix` | Bug fix | Patch version bump (1.0.x) |
| `docs` | Documentation only changes | No version bump |
| `style` | Code style changes (formatting, whitespace) | No version bump |
| `refactor` | Code refactoring without behavior changes | No version bump |
| `perf` | Performance improvements | Patch version bump |
| `test` | Adding or updating tests | No version bump |
| `chore` | Maintenance tasks, dependency updates | No version bump |
| `ci` | CI/CD configuration changes | No version bump |
| `build` | Build system or dependency changes | No version bump |
| `revert` | Reverting a previous commit | Depends on reverted commit |

### Breaking Changes

For breaking changes that require a major version bump (x.0.0):

```
feat(api)!: change coverage calculation to exclude expiring plans

BREAKING CHANGE: The coverage calculation now excludes Savings Plans
expiring within the renewal window. This may result in different
coverage percentages and purchase recommendations.
```

**Note:** Add `!` after the type/scope AND include a `BREAKING CHANGE:` footer.

### Scope (Optional)

Scope indicates the area of the codebase affected:

- `scheduler` — Scheduler Lambda function
- `purchaser` — Purchaser Lambda function
- `terraform` — Terraform configuration
- `ci` — CI/CD workflows
- `docs` — Documentation
- `database-sp` — Database Savings Plans functionality
- `compute-sp` — Compute Savings Plans functionality

### Examples

#### Feature Addition
```
feat(database-sp): add support for Database Savings Plans

Adds configuration options for Database Savings Plans automation
with AWS-enforced constraints (1-year term, No Upfront payment).
Includes separate coverage tracking and email notifications.
```

#### Breaking Change
```
feat(purchaser)!: enforce separate coverage caps per SP type

BREAKING CHANGE: The max_coverage_cap is now enforced separately
for Compute and Database Savings Plans. Organizations using both
SP types may need to adjust their cap settings.
```

### Commit Message Best Practices

- **Use imperative mood** in the subject line ("add" not "added")
- **Limit subject line to 72 characters**
- **Use the body to explain what and why, not how**
- **Reference issues in the footer** (`Fixes #123`, `Closes #456`)

## Pull Request Process

### Before Submitting

1. **Sync with upstream**:
   ```bash
   git fetch upstream
   git rebase upstream/develop
   ```

2. **Run all validations locally** (see [Local Validation](#local-validation))

3. **Ensure tests pass**:
   - All existing tests still pass
   - New features include tests
   - Code coverage remains ≥80% for scheduler Lambda

4. **Update documentation**:
   - Update README.md if adding features or changing behavior
   - Add/update code comments for complex logic
   - Update variables.tf descriptions if adding/modifying variables

### Submitting a Pull Request

1. **Push your branch**:
   ```bash
   git push origin feature/your-feature-name
   ```

2. **Open a pull request** on GitHub:
   - Base: `develop` (not `main`)
   - Title: Use conventional commit format (e.g., `feat(scheduler): add Database SP support`)
   - Description: Include:
     - **Summary** of changes
     - **Motivation** for the change
     - **Testing** performed
     - **Screenshots** (if UI/output changes)
     - **Breaking changes** (if any)
     - **Related issues** (`Closes #123`)

3. **Include in PR description**:
   - Summary of changes
   - Motivation for the change
   - Testing performed (all validations, tests, manual testing)
   - Breaking changes (if any)
   - Related issues (`Closes #45`)

### Automated PR Checks

All pull requests trigger automated checks via GitHub Actions:

| Check | Description | Must Pass |
|-------|-------------|-----------|
| **Terraform Validation** | `terraform fmt -check` and `terraform validate` | ✅ Yes |
| **Security Scan** | tfsec scanning for HIGH/CRITICAL issues | ✅ Yes |
| **Scheduler Tests** | pytest with ≥80% coverage | ✅ Yes |
| **Purchaser Tests** | Integration tests | ✅ Yes |

If any check fails, the PR will be commented with detailed error information. Fix issues and push updates to re-trigger checks.

### Code Review Process

1. **Maintainer review** — At least one maintainer must approve
2. **Address feedback** — Respond to all review comments
3. **Resolve conversations** — Ensure all discussions are resolved
4. **Squash commits** (optional) — Maintainers may request squashing multiple commits
5. **Approval** — Once approved, a maintainer will merge your PR

### After Merge

- Your PR will be merged to `develop` branch
- Changes will be included in the next release
- Release automation will create version tags and changelogs

## Testing Requirements

### Terraform Testing

All Terraform code must:
- Pass `terraform fmt -check -recursive`
- Pass `terraform init -backend=false`
- Pass `terraform validate`
- Have no tfsec HIGH or CRITICAL issues

### Python Testing

#### Scheduler Lambda
- **Unit tests** with pytest required for all new functions
- **Code coverage** ≥80% required (enforced by CI)
- **Mocking** AWS API calls using moto or boto3 stubs
- **Test file location**: `lambda/scheduler/test_*.py`

#### Purchaser Lambda
- **Integration tests** for purchase workflow validation
- **Idempotency testing** for duplicate purchase prevention
- **Test file location**: `lambda/purchaser/test_integration.py`

### Running Tests

```bash
# Scheduler tests with coverage
cd lambda/scheduler
pytest -v --cov=. --cov-report=term-missing --cov-report=html --cov-fail-under=80

# View HTML coverage report
open htmlcov/index.html

# Purchaser integration tests
cd lambda/purchaser
python test_integration.py
```

### Adding New Tests

When adding new functionality:
1. Write tests **before** or **alongside** implementation (TDD encouraged)
2. Test both **success** and **failure** scenarios
3. Test **edge cases** (e.g., zero coverage, 100% coverage, missing data)
4. Mock external AWS API calls to avoid real API charges
5. Use descriptive test names: `test_<function>_<scenario>_<expected_outcome>`

## Code Quality Standards

### Terraform Standards

- **Formatting**: Use `terraform fmt -recursive` before committing
- **Naming**: Use snake_case for all resources, variables, and outputs
- **Variables**: Include `description`, `type`, and `default` (if applicable) with validation where appropriate
- **Outputs**: Include `description` and `value`
- **Comments**: Add comments for complex logic or non-obvious decisions
- **Modules**: Follow HashiCorp's [Terraform Module Standards](https://www.terraform.io/docs/registry/modules/publish.html)

### Python Standards

- **Style**: Follow PEP 8 (enforced by ruff)
- **Linting**: Use `ruff check .` to identify code quality issues
- **Formatting**: Use `ruff format .` to auto-format code
- **Pre-commit hooks**: Run `pre-commit install` to automatically check code before commits
- **Docstrings**: Required for all functions
- **Type hints**: Encouraged for function signatures
- **Error handling**: Use try/except with specific exception types
- **Logging**: Use Python logging module (not print statements)
- **Constants**: Use UPPER_CASE for constants

### Security Standards

- **No hardcoded credentials** — Use IAM roles and environment variables
- **No sensitive data in logs** — Mask account IDs, ARNs, and amounts when logging
- **Least privilege IAM** — Request minimum permissions needed
- **Input validation** — Validate all user inputs and API responses
- **Dependency scanning** — Keep dependencies updated

## Release Process

This project uses automated release management via GitHub Actions and [Release Please](https://github.com/googleapis/release-please).

### How Releases Work

1. **Commits to `main`** trigger Release Please workflow
2. **Release Please analyzes** commit messages using Conventional Commits
3. **Release PR is created/updated** with:
   - Version bump (major.minor.patch)
   - Auto-generated CHANGELOG.md
   - Updated version references
4. **Merging the Release PR** creates:
   - GitHub Release with notes
   - Git tags: `v1.2.3`, `v1.2`, `v1`
   - CHANGELOG.md update

### Version Bumping Rules

Based on Conventional Commits:

| Commit Type | Version Bump | Example |
|-------------|--------------|---------|
| `fix:` | Patch (1.0.x) | `1.0.0` → `1.0.1` |
| `feat:` | Minor (1.x.0) | `1.0.0` → `1.1.0` |
| `feat!:` or `BREAKING CHANGE:` | Major (x.0.0) | `1.0.0` → `2.0.0` |
| `docs:`, `chore:`, `ci:` | No bump | No release |

### Release Cadence

- **Major releases** (x.0.0) — Breaking changes, major features (as needed)
- **Minor releases** (1.x.0) — New features, enhancements (monthly or as needed)
- **Patch releases** (1.0.x) — Bug fixes, security updates (as needed)

### Using Released Versions

Users can pin to specific version tags:

```hcl
# Exact version (recommended for production)
module "savings_plans" {
  source = "github.com/your-org/terraform-aws-sp-autopilot?ref=v1.2.3"
  # ...
}

# Latest patch for minor version (auto-updates patches)
module "savings_plans" {
  source = "github.com/your-org/terraform-aws-sp-autopilot?ref=v1.2"
  # ...
}

# Latest minor for major version (auto-updates minor + patches)
module "savings_plans" {
  source = "github.com/your-org/terraform-aws-sp-autopilot?ref=v1"
  # ...
}
```

## Questions or Issues?

- **Bug reports** — Open a GitHub issue with `bug` label
- **Feature requests** — Open a GitHub issue with `enhancement` label
- **Questions** — Open a GitHub discussion or issue with `question` label
- **Security issues** — Email security@example.com (do not open public issues)

---

Thank you for contributing to the AWS Savings Plans Automation Module! 🎉

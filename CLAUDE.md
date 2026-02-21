# CLAUDE.md

This file provides context for AI assistants working on this codebase.

## Project Overview

**terraform-aws-sp-autopilot** is a Terraform module that automates AWS Savings Plans purchases. It analyzes usage via Cost Explorer, recommends purchases based on configurable strategies, and executes them through a three-Lambda architecture coordinated by SQS.

- **Repository**: `etiennechabert/terraform-aws-sp-autopilot`
- **License**: Apache 2.0
- **Terraform**: >= 1.7, AWS Provider >= 5.0, < 6.33
- **Lambda Runtime**: Python 3.14
- **Published to**: Terraform Registry as `etiennechabert/sp-autopilot/aws`

## Architecture

Three Lambda functions orchestrated via EventBridge schedules and SQS:

1. **Scheduler** (`lambda/scheduler/`) - Analyzes current SP coverage, gets AWS recommendations, applies purchase strategy, queues purchase intents to SQS (or emails only in dry-run mode)
2. **Purchaser** (`lambda/purchaser/`) - Reads purchase intents from SQS, validates against `max_coverage_cap`, executes purchases via `CreateSavingsPlan` API
3. **Reporter** (`lambda/reporter/`) - Generates HTML/PDF/JSON spending and coverage reports, stores in S3, optionally emails stakeholders

**Supporting infrastructure**: SNS (notifications), SQS (purchase intent queue + DLQ), S3 (report storage), CloudWatch (logs + alarms), EventBridge (cron schedules), IAM (least-privilege roles per Lambda).

**Shared code** (`lambda/shared/`) - Common utilities used by all three Lambdas: AWS helpers, config validation, notifications, SP calculations, local mode support.

### Purchase Strategy Model

Two orthogonal dimensions:
- **Target strategy** (what coverage to aim for): `fixed` (explicit %), `dynamic` (risk-level based), `aws` (follow AWS recommendations)
- **Split strategy** (how to reach target): `linear` (fixed step %), `dichotomy` (exponentially decreasing), `one_shot` (all at once)

## Repository Structure

```
.
├── main.tf                    # Data sources, locals (strategy parsing, config extraction)
├── variables.tf               # All module input variables with extensive validations
├── outputs.tf                 # Module outputs (ARNs, URLs, config summaries)
├── versions.tf                # Terraform/provider version constraints
├── lambda.tf                  # Lambda functions + archive_file data sources for packaging
├── iam.tf                     # IAM roles and policies (per-Lambda, least privilege)
├── sns.tf                     # SNS topic + email subscriptions
├── sqs.tf                     # SQS queue + DLQ + DLQ alarm
├── s3.tf                      # S3 bucket (reports) + lifecycle + access logging
├── cloudwatch.tf              # CloudWatch log groups + error alarms
├── eventbridge.tf             # EventBridge rules + targets + Lambda permissions
├── lambda/
│   ├── scheduler/             # Scheduler Lambda (handler.py, config.py, strategies)
│   │   ├── target_strategies/ # fixed_target.py, dynamic_target.py, aws_target.py
│   │   ├── split_strategies/  # linear_split.py, dichotomy_split.py, one_shot_split.py
│   │   └── tests/             # Unit + integration tests
│   ├── purchaser/             # Purchaser Lambda (handler.py, config.py, validation.py)
│   │   └── tests/
│   ├── reporter/              # Reporter Lambda (handler.py, report_generator.py)
│   │   └── tests/
│   ├── shared/                # Shared modules (aws_utils, notifications, sp_calculations)
│   │   └── tests/
│   ├── tests/                 # Cross-lambda tests (packaging validation, algorithm parity)
│   └── local_runner.py        # Local execution utility (reads .env.local)
├── examples/
│   ├── single-account-compute/  # Basic single-account Compute SP
│   ├── organizations/           # AWS Organizations multi-account
│   └── dynamic-strategy/        # Dynamic target + dichotomy split
├── terraform-tests/
│   ├── unit/                  # Terraform native tests (.tftest.hcl) with mock providers
│   └── integration/           # Terratest Go tests (real AWS resources)
├── docs/                      # GitHub Pages simulator (HTML/JS/CSS + Playwright tests)
├── .github/
│   ├── workflows/             # CI/CD pipelines
│   └── hooks/pre-commit       # Pre-commit hook (runs make lint)
├── Makefile                   # lint, test, coverage, format, install-hooks
├── pyproject.toml             # Ruff config, pytest config, coverage config
└── codecov.yml                # Coverage thresholds
```

## Development Commands

### Linting & Formatting

```bash
make lint          # Ruff check --fix + ruff format (auto-fix mode)
make lint-check    # Ruff check + format --check (CI mode, no modifications)
make format        # Ruff format only
```

Ruff is configured in `pyproject.toml`. Key settings:
- Line length: 100
- Target: Python 3.13
- Quote style: double quotes
- Import sorting: `shared` is a known first-party package

### Testing

```bash
# All Lambda tests (scheduler + purchaser + reporter + packaging)
make test

# Individual Lambda tests (run from project root)
cd lambda/scheduler && python3 -m pytest tests/ -v
cd lambda/purchaser && python3 -m pytest tests/ -v
cd lambda/reporter && python3 -m pytest tests/ -v

# Packaging validation (verifies ZIP archives include all dependencies)
python3 -m pytest lambda/tests/test_lambda_packaging.py -v

# Aggregated coverage report
make coverage

# Terraform unit tests (requires Terraform >= 1.11 for mock providers)
terraform init && terraform test terraform-tests/unit/<name>.tftest.hcl

# Terraform integration tests (requires AWS credentials, Go 1.24+)
cd terraform-tests/integration && go test -v -timeout 30m
```

**PYTHONPATH**: Tests expect `PYTHONPATH` to include the `lambda/` directory so `shared` imports resolve. CI sets `PYTHONPATH=$GITHUB_WORKSPACE/lambda`. Locally, run from each Lambda's directory where `pytest.ini` handles paths.

Each Lambda has its own `pytest.ini` configuring:
- `testpaths`: `tests` (and `../shared/tests` for reporter)
- Coverage: `--cov=. --cov=../shared --cov-report=term-missing --cov-report=html --cov-report=xml`

### Terraform Validation

```bash
# Format check (.tf files only, not .tftest.hcl)
find . -name "*.tf" -not -path "*/.terraform/*" -exec terraform fmt -check {} +

# Init + validate
terraform init -backend=false && terraform validate
```

### Pre-commit Hooks

```bash
make install-hooks  # Copies .github/hooks/pre-commit to .git/hooks/
```

The hook runs `make lint` on staged Python files and re-stages auto-fixed files.

## CI/CD Pipeline

### PR Checks (`.github/workflows/pr-checks.yml`)

Multi-stage pipeline:

1. **Stage 1 (parallel)**: Terraform fmt/validate, tfsec security scan (HIGH+ severity), Python ruff lint/format
2. **Stage 2** (after Stage 1): Scheduler/Purchaser/Reporter Lambda pytest (parallel jobs, Python 3.13)
3. **Stage 3a**: Terraform unit tests (matrix of 8 test files, mock providers, no AWS credentials needed)
4. **Stage 3b**: Terraform integration tests (Terratest, real AWS, requires `aws-integration` environment approval)

### Other Workflows

- **terraform-validation.yml**: Triggered on `.tf`/`.tfvars` changes, runs fmt + validate
- **frontend-tests.yml**: Playwright tests for `docs/` simulator, triggered on `docs/**` changes
- **sonarcloud.yml**: Static analysis with coverage upload
- **release.yml**: Creates GitHub Release on `v*.*.*` tags

### Coverage Requirements

- Codecov: patch target 80%, project target auto with 1% threshold (informational)
- pyproject.toml: `--cov-fail-under=80`

## Code Conventions

### Terraform

- All `.tf` files must pass `terraform fmt`
- Domain-specific file organization: `sns.tf`, `sqs.tf`, `s3.tf`, `lambda.tf`, `iam.tf`, `cloudwatch.tf`, `eventbridge.tf`
- Resource naming: `${local.module_name}-<resource-type>` (e.g., `sp-autopilot-scheduler`)
- Conditional resources use `count` with local boolean flags (e.g., `local.lambda_scheduler_enabled`)
- All resources tagged with `local.common_tags` (merged from `ManagedBy` + `Module` + user `tags`)
- Variables use complex `object()` types with `optional()` fields and defaults
- Extensive `validation` blocks on variables (see `variables.tf`)

### Python (Lambda)

- Formatter/linter: ruff (configured in `pyproject.toml`)
- Line length: 100 characters
- Double quotes for strings
- Import order: stdlib, third-party, first-party (`shared`)
- Each Lambda has: `handler.py` (entry point, `handler(event, context)`), `config.py` (env var parsing)
- Shared code in `lambda/shared/` is packaged into each Lambda's ZIP via `archive_file` data sources in `lambda.tf`
- Test framework: pytest with pytest-cov, pytest-mock, moto (AWS mocking)
- Handler pattern: each Lambda entry point is `handler.handler`
- Runtime: Python 3.14

### Commit Messages

[Conventional Commits](https://www.conventionalcommits.org/) format:

```
<type>(<scope>): <subject>
```

Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`
Scopes: `scheduler`, `purchaser`, `terraform`, `ci`, `docs`, `database-sp`, `compute-sp`

### Branch Naming

- `feature/` - New features
- `fix/` - Bug fixes
- `docs/` - Documentation
- `refactor/` - Refactoring
- `test/` - Tests
- `chore/` - Maintenance

## Key Variables

The module uses deeply nested object variables. The main ones:

- **`purchase_strategy`** - Target strategy (fixed/aws/dynamic), split strategy (linear/dichotomy/one_shot), coverage caps, lookback period
- **`sp_plans`** - Enable/configure Compute, Database, SageMaker SP types with plan_type (term + payment)
- **`scheduler`** - EventBridge cron expressions for each Lambda
- **`notifications`** - Email list, Slack/Teams webhooks
- **`lambda_config`** - Per-Lambda: enabled, dry_run, memory, timeout, assume_role_arn, error_alarm
- **`reporting`** - Format, S3 lifecycle, email delivery
- **`monitoring`** - DLQ alarm, error threshold, utilization threshold
- **`encryption`** - KMS keys for SNS, SQS, S3

## Testing Architecture

### Python Tests

- **Unit tests**: Each Lambda has `tests/` with pytest. Scheduler also has `tests/unit/` for strategy-level tests.
- **Cross-platform tests**: `lambda/tests/cross_platform/test_algorithm_parity.py` validates algorithm consistency.
- **Packaging tests**: `lambda/tests/test_lambda_packaging.py` verifies ZIP archives contain all required modules.
- **Mocking**: Uses `moto` for AWS service mocking and `pytest-mock` for general mocking.

### Terraform Tests

- **Unit tests** (`terraform-tests/unit/*.tftest.hcl`): Native Terraform test framework with `mock_provider "aws"`. Tests variable validations, resource configurations, conditional creation. No AWS credentials needed. Requires Terraform >= 1.11 for `override_during` support.
- **Integration tests** (`terraform-tests/integration/`): Go-based Terratest. Creates real AWS resources, validates configuration, then destroys. Requires AWS credentials and `aws-integration` environment approval in CI.

## Local Development

```bash
# Install dependencies
pip install -r requirements-dev.txt

# Run Lambda locally (reads .env.local, uses local filesystem instead of SQS/S3)
python lambda/local_runner.py scheduler --dry-run
python lambda/local_runner.py purchaser
python lambda/local_runner.py reporter --format html
```

Local mode writes purchase intents to `local_data/queue/` and reports to `local_data/reports/`. Always keep `DRY_RUN=true` locally to prevent actual Savings Plans purchases.

## Security Notes

- tfsec scans enforce HIGH+ severity (excluded: `aws-s3-encryption-customer-key`, `aws-sqs-queue-encryption-use-cmk`, `aws-iam-no-policy-wildcards`)
- S3 bucket has public access block, HTTPS-only policy, versioning enabled
- SQS uses KMS encryption (configurable: AWS managed or customer managed)
- IAM policies are least-privilege per Lambda (scheduler: read CE + write SQS; purchaser: read SQS + write SP; reporter: read CE + write S3)
- Cross-account via `sts:AssumeRole` for AWS Organizations setups
- Sensitive values (webhook URLs) should be marked as `sensitive` in Terraform

## Dependencies

### Python (per-Lambda `requirements.txt`)
- `boto3~=1.42`, `botocore~=1.42`
- `pytest~=9.0`, `pytest-cov~=7.0`, `pytest-mock~=3.15`
- `moto~=5.1` (AWS mocking)
- `boto3-stubs` (type stubs)

### Dev (`requirements-dev.txt`)
- Above plus `python-dotenv~=1.2`, `black~=26.1`, `flake8~=7.3`, `mypy~=1.19`

### Terraform Integration Tests
- Go 1.24+, Terratest (`github.com/gruntwork-io/terratest`)

### Frontend (docs simulator)
- Node.js 22, Playwright (for testing)

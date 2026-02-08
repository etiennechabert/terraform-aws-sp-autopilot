# Development Guide

## Prerequisites

- Python 3.11+
- AWS CLI configured with credentials
- ruff (Python linter/formatter) — installed via `uvx` by Makefile targets

## Quick Start

```bash
# Install dependencies
pip install -r requirements-dev.txt

# Or install per-Lambda
cd lambda/scheduler && pip install -r requirements.txt
cd ../purchaser && pip install -r requirements.txt
cd ../reporter && pip install -r requirements.txt

# Configure AWS credentials
cp .env.local.example .env.local
# Edit .env.local with your AWS profile

# Run Lambda functions locally
python lambda/local_runner.py scheduler --dry-run
python lambda/local_runner.py purchaser
python lambda/local_runner.py reporter --format html
```

## Local Lambda Execution

The `local_runner.py` utility simulates Lambda execution locally. It reads environment variables from `.env.local` and uses the local filesystem instead of SQS/S3:

- Purchase intents are written to `local_data/queue/` (JSON files)
- Reports are written to `local_data/reports/`
- Cost Explorer APIs are still called (read-only)
- SNS notifications are logged but not sent

```bash
python lambda/local_runner.py scheduler --dry-run   # Analyze coverage, queue intents
python lambda/local_runner.py purchaser              # Process queued intents
python lambda/local_runner.py reporter --format html # Generate HTML report
```

**Always keep `DRY_RUN=true`** in `.env.local` to prevent actual Savings Plans purchases.

### Key Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `AWS_PROFILE` | AWS profile to use | (required) |
| `DRY_RUN` | Skip actual purchases | `true` |
| `COVERAGE_TARGET_PERCENT` | Target coverage | `90.0` |
| `REPORT_FORMAT` | Report format | `html` |

See `.env.local.example` for all options.

## Running Tests

```bash
make test              # Run all Lambda tests
make coverage          # Run tests with aggregated coverage report (opens in browser)
```

Or run tests directly:

```bash
cd lambda/scheduler && python3 -m pytest tests/ -v
cd lambda/purchaser && python3 -m pytest tests/ -v
cd lambda/reporter && python3 -m pytest tests/ -v
```

## Code Quality

```bash
make lint              # Lint and auto-fix + format
make lint-check        # Check only (CI mode)
make format            # Format Python code only
make install-hooks     # Install git pre-commit hooks
```

## Troubleshooting

### ModuleNotFoundError: No module named 'shared'

Run from the project root directory, or set:

```bash
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

### AWS credentials not found

```bash
aws configure --profile your-profile-name
# Or set AWS_PROFILE in .env.local
```

### Coverage data not available

Normal for new AWS accounts. Cost Explorer needs 24-48 hours of usage data. The Lambda functions handle this gracefully by returning 0% coverage.

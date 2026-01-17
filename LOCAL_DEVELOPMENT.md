# Local Development Guide

This guide explains how to run and debug the SP-Autopilot Lambda functions locally on your development machine.

## Overview

Local mode allows you to run the Lambda functions without deploying to AWS. Instead of SQS and S3, the functions use your local filesystem for message queuing and report storage. This enables:

- Fast iteration and debugging
- Local testing without AWS infrastructure
- IDE breakpoint debugging
- Inspection of queue messages and reports
- Testing without incurring AWS costs

## Prerequisites

1. **Python 3.11+** installed on your machine
2. **AWS credentials** configured (the Lambdas still call AWS Cost Explorer and other APIs)
3. **Python dependencies** installed:
   ```bash
   pip install boto3 python-dotenv pytest
   ```

## Quick Start

### 1. Configure Environment

Copy the example environment file and customize it:

```bash
cp .env.local.example .env.local
```

Edit `.env.local` and set your AWS credentials:

```bash
# Use your AWS profile
AWS_PROFILE=your-profile-name
AWS_REGION=us-east-1
```

### 2. Run a Lambda Function

Use the `local_runner.py` script to execute any Lambda:

```bash
# Run the Scheduler Lambda (analyzes coverage and queues purchase intents)
python local_runner.py scheduler --dry-run

# Run the Purchaser Lambda (processes queued intents)
python local_runner.py purchaser

# Run the Reporter Lambda (generates coverage report)
python local_runner.py reporter --format html
```

### 3. Inspect Local Data

All local data is stored in `./local_data/`:

```
local_data/
├── queue/                    # Purchase intent messages (JSON files)
│   ├── scheduler-Compute-ONE_YEAR-2026-01-17T10:30:00.json
│   └── scheduler-Compute-THREE_YEAR-2026-01-17T10:30:00.json
├── reports/                  # Generated reports
│   ├── savings-plans-report_2026-01-17_10-30-00.html
│   └── savings-plans-report_2026-01-17_10-30-00.html.meta.json
└── logs/                     # Optional log files
```

## How It Works

### Architecture

The local mode implementation uses **adapter pattern** to abstract AWS services:

- **`queue_adapter.py`**: Abstracts SQS operations
  - AWS mode: Uses `boto3` SQS client
  - Local mode: Reads/writes JSON files to `local_data/queue/`

- **`storage_adapter.py`**: Abstracts S3 operations
  - AWS mode: Uses `boto3` S3 client
  - Local mode: Reads/writes files to `local_data/reports/`

- **`local_mode.py`**: Utilities for detecting and configuring local mode

### Data Flow

**Scheduler Lambda**:
1. Calls AWS Cost Explorer API (real API call)
2. Calculates purchase recommendations
3. Writes purchase intents to `local_data/queue/*.json` (local filesystem)
4. Logs summary to console

**Purchaser Lambda**:
1. Reads purchase intents from `local_data/queue/*.json` (local filesystem)
2. Validates each intent
3. Executes purchases via AWS API (can be disabled with DRY_RUN)
4. Deletes processed messages from local queue
5. Logs results to console

**Reporter Lambda**:
1. Calls AWS Cost Explorer API (real API call)
2. Generates HTML or JSON report
3. Writes report to `local_data/reports/*.html` (local filesystem)
4. Logs report location to console

## Usage Examples

### Example 1: Test Scheduler

Analyze current coverage and see what would be purchased:

```bash
python local_runner.py scheduler --dry-run
```

This will:
- Call AWS Cost Explorer to get current coverage
- Calculate purchase recommendations
- Queue purchase intents to `local_data/queue/`
- Show what would be purchased in the console

Inspect the queued intents:

```bash
cat local_data/queue/scheduler-Compute-*.json
```

### Example 2: Test Purchaser

Process the queued purchase intents (without actually purchasing):

```bash
# Make sure DISABLE_PURCHASES=true in .env.local for safety
python local_runner.py purchaser
```

This will:
- Read intents from `local_data/queue/`
- Validate each intent
- Log what would be purchased (if DRY_RUN=false and DISABLE_PURCHASES=false)
- Delete processed intents from queue

### Example 3: Generate Report

Generate a coverage report:

```bash
python local_runner.py reporter --format html
```

This will:
- Call AWS Cost Explorer to get coverage history
- Generate an HTML report
- Save to `local_data/reports/savings-plans-report_*.html`

Open the report in your browser:

```bash
# On macOS
open local_data/reports/savings-plans-report_*.html

# On Linux
xdg-open local_data/reports/savings-plans-report_*.html

# On Windows
start local_data/reports/savings-plans-report_*.html
```

### Example 4: Full Workflow

Simulate a complete workflow:

```bash
# 1. Analyze and queue purchase intents
python local_runner.py scheduler --dry-run

# 2. Process the queue (dry-run, no actual purchases)
python local_runner.py purchaser

# 3. Generate a report
python local_runner.py reporter --format html
```

## Debugging with IDE

### VS Code

1. Create `.vscode/launch.json`:

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Local Runner - Scheduler",
      "type": "python",
      "request": "launch",
      "program": "${workspaceFolder}/local_runner.py",
      "args": ["scheduler", "--dry-run"],
      "console": "integratedTerminal",
      "envFile": "${workspaceFolder}/.env.local"
    },
    {
      "name": "Local Runner - Purchaser",
      "type": "python",
      "request": "launch",
      "program": "${workspaceFolder}/local_runner.py",
      "args": ["purchaser"],
      "console": "integratedTerminal",
      "envFile": "${workspaceFolder}/.env.local"
    },
    {
      "name": "Local Runner - Reporter",
      "type": "python",
      "request": "launch",
      "program": "${workspaceFolder}/local_runner.py",
      "args": ["reporter", "--format", "html"],
      "console": "integratedTerminal",
      "envFile": "${workspaceFolder}/.env.local"
    }
  ]
}
```

2. Set breakpoints in Lambda handler files
3. Press F5 to start debugging

### PyCharm

1. Right-click `local_runner.py` → "Modify Run Configuration"
2. Set script parameters: `scheduler --dry-run`
3. Set environment variables file: `.env.local`
4. Set breakpoints in Lambda handler files
5. Click Debug button

## Configuration

### Environment Variables

Key environment variables in `.env.local`:

| Variable | Description | Default |
|----------|-------------|---------|
| `LOCAL_MODE` | Enable local mode | `true` (set by runner) |
| `LOCAL_DATA_DIR` | Directory for local data | `./local_data` |
| `AWS_PROFILE` | AWS profile to use | (required) |
| `DRY_RUN` | Skip actual purchases/queueing | `true` |
| `COVERAGE_TARGET_PERCENT` | Target coverage percentage | `90.0` |
| `REPORT_FORMAT` | Report format (html/json) | `html` |

See `.env.local.example` for all available options.

### Safety Features

To prevent accidental purchases or modifications:

1. **DRY_RUN mode**: Set `DRY_RUN=true` to skip queueing/purchasing
2. **Local queue**: Messages never go to real SQS
3. **Local storage**: Reports never go to real S3
4. **Read-only APIs**: Cost Explorer and Savings Plans APIs are only queried, not modified (unless purchasing)

## Testing

Run the test suite to verify local mode functionality:

```bash
# Run all tests
pytest tests/test_local_mode.py tests/test_local_runner.py -v

# Run specific test class
pytest tests/test_local_mode.py::TestQueueAdapterLocal -v

# Run with coverage
pytest tests/test_local_mode.py tests/test_local_runner.py --cov=lambda/shared --cov-report=html
```

## Troubleshooting

### Issue: "ModuleNotFoundError: No module named 'shared'"

**Solution**: Make sure you're running from the project root directory.

### Issue: AWS credentials not found

**Solution**: Set `AWS_PROFILE` in `.env.local` or configure AWS credentials:

```bash
aws configure --profile your-profile-name
```

### Issue: "Permission denied" errors on local_data/

**Solution**: Ensure the `local_data/` directory has write permissions:

```bash
chmod -R u+w local_data/
```

### Issue: Queue messages not being processed

**Solution**: Check that files exist in `local_data/queue/`:

```bash
ls -la local_data/queue/
```

If empty, run the scheduler first:

```bash
python local_runner.py scheduler --dry-run
```

### Issue: Reports not generating

**Solution**: Check AWS credentials have Cost Explorer permissions. Test with:

```bash
aws ce get-cost-and-usage \
  --time-period Start=2026-01-01,End=2026-01-17 \
  --granularity MONTHLY \
  --metrics BlendedCost
```

## File Structure

```
terraform-aws-sp-autopilot/
├── local_runner.py              # Main script for running Lambdas locally
├── .env.local.example           # Example environment configuration
├── .env.local                   # Your local configuration (git-ignored)
├── local_data/                  # Local data directory (git-ignored)
│   ├── queue/                   # SQS queue simulation
│   ├── reports/                 # S3 reports simulation
│   └── logs/                    # Optional logs
├── lambda/
│   ├── shared/
│   │   ├── local_mode.py        # Local mode utilities
│   │   ├── queue_adapter.py     # SQS abstraction layer
│   │   └── storage_adapter.py   # S3 abstraction layer
│   ├── scheduler/
│   │   ├── handler.py           # Updated for local mode
│   │   └── queue_manager.py     # Uses queue_adapter
│   ├── purchaser/
│   │   └── handler.py           # Updated for local mode
│   └── reporter/
│       └── handler.py           # Updated for local mode
└── tests/
    ├── test_local_mode.py       # Unit tests for adapters
    └── test_local_runner.py     # Integration tests
```

## Best Practices

1. **Always use DRY_RUN=true** for initial testing
2. **Review queued intents** before processing with purchaser
3. **Backup local_data/** before major changes
4. **Use version control** for `.env.local` (add to `.gitignore`)
5. **Test in local mode** before deploying to AWS
6. **Clear queue directory** between test runs if needed: `rm local_data/queue/*.json`

## Limitations

- **Real AWS API calls**: Cost Explorer, Savings Plans APIs are still called (read-only)
- **No SNS notifications**: Email/Slack/Teams notifications are logged but not sent
- **No Lambda limits**: Memory/timeout limits are not enforced locally
- **No concurrent execution**: Only one Lambda runs at a time

## Next Steps

After testing locally:

1. Deploy to AWS using Terraform
2. Verify Lambda execution in CloudWatch Logs
3. Check SQS queue and S3 bucket
4. Monitor purchases and coverage

See the main [README.md](README.md) for deployment instructions.

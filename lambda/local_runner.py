#!/usr/bin/env python3
"""
Local runner for Lambda functions in debug mode.

This script allows you to run the Lambda functions locally with filesystem I/O
instead of SQS and S3. This is useful for debugging and development.

Usage:
    python lambda/local_runner.py scheduler  [--dry-run]
    python lambda/local_runner.py purchaser
    python lambda/local_runner.py reporter [--format html|json]

Environment:
    Set environment variables in .env.local file or via command line.
    Key variables:
    - LOCAL_MODE=true (automatically set by this script)
    - LOCAL_DATA_DIR=./local_data (default)
    - DRY_RUN=true (for scheduler, prevents actual queueing)
    - AWS credentials (AWS_PROFILE or AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY)

Example:
    # Run scheduler in dry-run mode
    python lambda/local_runner.py scheduler --dry-run

    # Run purchaser (processes local queue files)
    python lambda/local_runner.py purchaser

    # Generate HTML report locally
    python lambda/local_runner.py reporter --format html
"""

import argparse
import os
import sys
from pathlib import Path


# Load environment variables from .env.local if it exists (in project root)
try:
    from dotenv import load_dotenv

    env_file = Path(__file__).parent.parent / ".env.local"
    if env_file.exists():
        print(f"Loading environment from {env_file}")
        load_dotenv(env_file)
    else:
        print(f"No .env.local file found at {env_file}")
        print("Using environment variables from shell")
except ImportError:
    print("python-dotenv not installed, using environment variables from shell")
    print("Install with: pip install python-dotenv")

# Set LOCAL_MODE before importing Lambda modules
os.environ["LOCAL_MODE"] = "true"

# Set default local data directory if not already set (in project root)
if "LOCAL_DATA_DIR" not in os.environ:
    default_data_dir = Path(__file__).parent.parent / "local_data"
    os.environ["LOCAL_DATA_DIR"] = str(default_data_dir)
    print(f"LOCAL_DATA_DIR not set, using default: {default_data_dir}")

# Add lambda directories to Python path (now sibling directories)
lambda_dir = Path(__file__).parent
sys.path.insert(0, str(lambda_dir / "scheduler"))
sys.path.insert(0, str(lambda_dir / "purchaser"))
sys.path.insert(0, str(lambda_dir / "reporter"))
sys.path.insert(0, str(lambda_dir / "shared"))


class MockContext:
    """Mock Lambda context for local execution."""

    def __init__(self, function_name: str):
        self.function_name = f"local-{function_name}"
        self.memory_limit_in_mb = 512
        self.invoked_function_arn = (
            f"arn:aws:lambda:local:000000000000:function:local-{function_name}"
        )
        self.aws_request_id = f"local-request-{function_name}"


def run_scheduler(args):
    """Run the Scheduler Lambda locally."""
    print("\n" + "=" * 60)
    print("Running Scheduler Lambda in LOCAL mode")
    print("=" * 60 + "\n")

    # Set DRY_RUN if requested
    if args.dry_run:
        os.environ["DRY_RUN"] = "true"
        print("DRY_RUN mode enabled - no messages will be queued\n")

    # Import and run scheduler handler
    from scheduler.handler import handler

    event = {}  # EventBridge events are typically empty for scheduled triggers
    context = MockContext("scheduler")

    try:
        result = handler(event, context)
        print("\n" + "=" * 60)
        print("Scheduler Lambda completed successfully")
        print("=" * 60)
        print(f"\nResult: {result}")

        # Show queue directory contents
        local_data_dir = Path(os.environ["LOCAL_DATA_DIR"])
        queue_dir = local_data_dir / "queue"
        if queue_dir.exists():
            queue_files = list(queue_dir.glob("*.json"))
            print(f"\nQueue directory: {queue_dir}")
            print(f"Queued messages: {len(queue_files)}")
            for file in queue_files:
                print(f"  - {file.name}")
        else:
            print(f"\nQueue directory not found: {queue_dir}")

        return result
    except Exception as e:
        print("\n" + "=" * 60)
        print("Scheduler Lambda FAILED")
        print("=" * 60)
        print(f"\nError: {e}")
        raise


def run_purchaser(args):
    """Run the Purchaser Lambda locally."""
    print("\n" + "=" * 60)
    print("Running Purchaser Lambda in LOCAL mode")
    print("=" * 60 + "\n")

    # Check for queue files
    local_data_dir = Path(os.environ["LOCAL_DATA_DIR"])
    queue_dir = local_data_dir / "queue"
    if queue_dir.exists():
        queue_files = list(queue_dir.glob("*.json"))
        print(f"Found {len(queue_files)} message(s) in queue: {queue_dir}\n")
    else:
        print(f"Queue directory not found: {queue_dir}")
        print("No messages to process\n")

    # Import and run purchaser handler
    from purchaser.handler import handler

    event = {}
    context = MockContext("purchaser")

    try:
        result = handler(event, context)
        print("\n" + "=" * 60)
        print("Purchaser Lambda completed successfully")
        print("=" * 60)
        print(f"\nResult: {result}")
        return result
    except Exception as e:
        print("\n" + "=" * 60)
        print("Purchaser Lambda FAILED")
        print("=" * 60)
        print(f"\nError: {e}")
        raise


def run_reporter(args):
    """Run the Reporter Lambda locally."""
    print("\n" + "=" * 60)
    print("Running Reporter Lambda in LOCAL mode")
    print("=" * 60 + "\n")

    # Set report format if specified
    if args.format:
        os.environ["REPORT_FORMAT"] = args.format
        print(f"Report format: {args.format}\n")

    # Import and run reporter handler
    from reporter.handler import handler

    event = {}
    context = MockContext("reporter")

    try:
        result = handler(event, context)
        print("\n" + "=" * 60)
        print("Reporter Lambda completed successfully")
        print("=" * 60)
        print(f"\nResult: {result}")

        # Show reports directory contents
        local_data_dir = Path(os.environ["LOCAL_DATA_DIR"])
        reports_dir = local_data_dir / "reports"
        if reports_dir.exists():
            report_files = sorted(
                [f for f in reports_dir.glob("*") if not f.name.endswith(".meta.json")],
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            print(f"\nReports directory: {reports_dir}")
            print(f"Total reports: {len(report_files)}")
            if report_files:
                print("\nMost recent reports:")
                for file in report_files[:5]:
                    print(f"  - {file.name}")
        else:
            print(f"\nReports directory not found: {reports_dir}")

        return result
    except Exception as e:
        print("\n" + "=" * 60)
        print("Reporter Lambda FAILED")
        print("=" * 60)
        print(f"\nError: {e}")
        raise


def main():
    """Main entry point for local runner."""
    parser = argparse.ArgumentParser(
        description="Run Lambda functions locally in debug mode",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "lambda_name",
        choices=["scheduler", "purchaser", "reporter"],
        help="Name of the Lambda function to run",
    )

    parser.add_argument(
        "--dry-run", action="store_true", help="Run scheduler in dry-run mode (no queueing)"
    )

    parser.add_argument(
        "--format",
        choices=["html", "json"],
        help="Report format for reporter Lambda (default: html)",
    )

    args = parser.parse_args()

    # Display environment info
    print("\n" + "=" * 60)
    print("Local Runner Configuration")
    print("=" * 60)
    print(f"Lambda: {args.lambda_name}")
    print(f"LOCAL_MODE: {os.environ.get('LOCAL_MODE')}")
    print(f"LOCAL_DATA_DIR: {os.environ.get('LOCAL_DATA_DIR')}")
    print(f"AWS_PROFILE: {os.environ.get('AWS_PROFILE', 'not set')}")
    print(
        f"AWS_REGION: {os.environ.get('AWS_REGION', os.environ.get('AWS_DEFAULT_REGION', 'not set'))}"
    )

    # Run the selected Lambda
    if args.lambda_name == "scheduler":
        result = run_scheduler(args)
    elif args.lambda_name == "purchaser":
        result = run_purchaser(args)
    elif args.lambda_name == "reporter":
        result = run_reporter(args)
    else:
        print(f"Unknown Lambda: {args.lambda_name}")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("Local execution completed")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nFatal error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)

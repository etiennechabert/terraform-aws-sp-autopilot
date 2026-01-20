#!/usr/bin/env python3
"""
Discover AWS Services with Savings Plans Coverage Data.

This script queries AWS Cost Explorer to identify all services in your account
that have Savings Plans coverage data. Use this to customize the service lists
in lambda/shared/spending_analyzer.py for your specific AWS usage.

Usage:
    python3 scripts/discover_services.py

Requirements:
    - AWS credentials configured (via environment variables or ~/.aws/credentials)
    - Cost Explorer API access
    - At least 30 days of usage data in your account
"""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add lambda directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "lambda"))

from shared.aws_utils import get_clients


def discover_services(lookback_days: int = 30) -> dict[str, dict[str, float]]:
    """
    Query Cost Explorer to discover all services with SP coverage data.

    Args:
        lookback_days: Number of days to look back (default: 30)

    Returns:
        dict: Service names mapped to {covered, total} spend amounts
    """
    config = {
        "management_account_role_arn": None,  # Uses default credentials
    }

    clients = get_clients(config, session_name="discover-services")
    ce_client = clients["ce"]

    now = datetime.now(timezone.utc)
    end_date = (now - timedelta(days=1)).date()
    start_date = end_date - timedelta(days=lookback_days)

    params = {
        "TimePeriod": {
            "Start": start_date.isoformat(),
            "End": end_date.isoformat(),
        },
        "Granularity": "DAILY",
        "GroupBy": [{"Type": "DIMENSION", "Key": "SERVICE"}],
    }

    print(f"Querying Cost Explorer for last {lookback_days} days...")
    print(f"Date range: {start_date} to {end_date}")
    print()

    all_coverages = []
    next_token = None

    while True:
        if next_token:
            params["NextPageToken"] = next_token

        response = ce_client.get_savings_plans_coverage(**params)
        page_coverages = response.get("SavingsPlansCoverages", [])
        all_coverages.extend(page_coverages)

        next_token = response.get("NextPageToken")
        if not next_token:
            break

    print(f"Fetched {len(all_coverages)} coverage data points")
    print()

    # Aggregate by service
    services_data = {}

    for item in all_coverages:
        service_name = item.get("Attributes", {}).get("SERVICE", "Unknown")
        coverage_info = item.get("Coverage", {})

        covered = float(coverage_info.get("SpendCoveredBySavingsPlans", "0"))
        total = float(coverage_info.get("TotalCost", "0"))

        if service_name not in services_data:
            services_data[service_name] = {"covered": 0.0, "total": 0.0}

        services_data[service_name]["covered"] += covered
        services_data[service_name]["total"] += total

    return services_data


def print_results(services_data: dict[str, dict[str, float]]) -> None:
    """Print discovered services in a formatted table."""
    # Sort by total spend
    sorted_services = sorted(
        services_data.items(), key=lambda x: x[1]["total"], reverse=True
    )

    print("=" * 90)
    print("ALL SERVICES WITH SAVINGS PLANS COVERAGE DATA (sorted by spend)")
    print("=" * 90)
    print()
    print(f"{'Service Name':<60} {'Total Spend':>12} {'Covered':>12} {'%':>6}")
    print("-" * 90)

    for service_name, data in sorted_services:
        total = data["total"]
        covered = data["covered"]
        coverage_pct = (covered / total * 100) if total > 0 else 0

        print(f"{service_name:<60} ${total:>11.2f} ${covered:>11.2f} {coverage_pct:>5.1f}%")

    print()
    print("=" * 90)
    print("PYTHON CONSTANTS FORMAT")
    print("=" * 90)
    print()
    print("# Add these SERVICE names to lambda/shared/spending_analyzer.py constants:")
    print()

    # Categorize services
    compute_keywords = ["ec2", "lambda", "fargate", "container", "kubernetes", "eks", "ecs"]
    database_keywords = ["rds", "database", "dynamodb", "aurora", "elasticache", "neptune", "documentdb", "keyspaces", "timestream", "memorydb"]
    sagemaker_keywords = ["sagemaker"]

    compute_services = []
    database_services = []
    sagemaker_services = []
    unknown_services = []

    for service_name, _ in sorted_services:
        service_lower = service_name.lower()

        if any(kw in service_lower for kw in sagemaker_keywords):
            sagemaker_services.append(service_name)
        elif any(kw in service_lower for kw in compute_keywords):
            compute_services.append(service_name)
        elif any(kw in service_lower for kw in database_keywords):
            database_services.append(service_name)
        else:
            unknown_services.append(service_name)

    if compute_services:
        print("# Compute SP Services:")
        print("COMPUTE_SP_SERVICES = [")
        for svc in compute_services:
            print(f'    "{svc}",')
        print("]")
        print()

    if database_services:
        print("# Database Services (for tracking only - no Database SP exists):")
        print("DATABASE_SP_SERVICES = [")
        for svc in database_services:
            print(f'    "{svc}",')
        print("]")
        print()

    if sagemaker_services:
        print("# SageMaker SP Services:")
        print("SAGEMAKER_SP_SERVICES = [")
        for svc in sagemaker_services:
            print(f'    "{svc}",')
        print("]")
        print()

    if unknown_services:
        print("# Unknown/Uncategorized Services:")
        print("# Please categorize these manually:")
        for svc in unknown_services:
            print(f'# "{svc}",')
        print()

    print(f"Total unique services: {len(sorted_services)}")
    print()
    print("Next steps:")
    print("1. Copy the relevant service names to lambda/shared/spending_analyzer.py")
    print("2. Uncomment any commented services in the constants")
    print("3. Test your configuration with actual AWS data")


def main():
    """Main entry point."""
    print("=" * 90)
    print("AWS SAVINGS PLANS COVERAGE - SERVICE DISCOVERY")
    print("=" * 90)
    print()

    try:
        services_data = discover_services(lookback_days=30)
        print_results(services_data)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

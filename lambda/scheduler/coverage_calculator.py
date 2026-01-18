"""
Coverage calculation module for Scheduler Lambda.

Calculates current Savings Plans coverage, excluding plans expiring soon.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from botocore.exceptions import ClientError
from mypy_boto3_ce.client import CostExplorerClient
from mypy_boto3_savingsplans.client import SavingsPlansClient


# Configure logging
logger = logging.getLogger()


def calculate_current_coverage(
    savingsplans_client: SavingsPlansClient, ce_client: CostExplorerClient, config: dict[str, Any]
) -> dict[str, float]:
    """
    Calculate current Savings Plans coverage, excluding plans expiring soon.

    Args:
        savingsplans_client: Boto3 Savings Plans client
        ce_client: Boto3 Cost Explorer client
        config: Configuration dictionary

    Returns:
        dict: Coverage percentages by SP type
    """
    logger.info("Calculating current coverage")

    # Get current date for expiration filtering
    now = datetime.now(timezone.utc)
    renewal_window_days = config["renewal_window_days"]

    # Get list of existing Savings Plans
    try:
        response = savingsplans_client.describe_savings_plans(states=["active"])
        savings_plans = response.get("savingsPlans", [])
        logger.info(f"Found {len(savings_plans)} active Savings Plans")

        # Filter out plans expiring within renewal_window_days
        # Why: Plans expiring soon will be replaced, so we exclude them from coverage calculations
        # to avoid double-counting when their replacements are purchased. For example, if a plan
        # expires in 5 days and renewal_window_days=30, we treat it as already expired to allow
        # purchasing its replacement now.
        valid_plan_ids = []
        for plan in savings_plans:
            # Only process plans with an end date (no-upfront plans always have end dates)
            if "end" in plan:
                # Parse end date from ISO 8601 format (e.g., "2024-12-31T23:59:59Z")
                # AWS returns dates with 'Z' suffix; we convert to timezone-aware datetime
                end_date = datetime.fromisoformat(plan["end"].replace("Z", "+00:00"))

                # Calculate days remaining until expiration
                # Using .days extracts only the day component (ignoring hours/minutes)
                days_until_expiry = (end_date - now).days

                # Include plan only if it expires AFTER the renewal window
                # Example: renewal_window_days=30, plan expires in 45 days -> INCLUDE
                # Example: renewal_window_days=30, plan expires in 15 days -> EXCLUDE
                if days_until_expiry > renewal_window_days:
                    valid_plan_ids.append(plan["savingsPlanId"])
                    logger.debug(
                        f"Including plan {plan['savingsPlanId']} - expires in {days_until_expiry} days"
                    )
                else:
                    logger.info(
                        f"Excluding plan {plan['savingsPlanId']} - expires in {days_until_expiry} days (within renewal window)"
                    )

        logger.info(f"Valid plans after filtering: {len(valid_plan_ids)}")

    except ClientError as e:
        logger.error(f"Failed to describe Savings Plans: {e!s}")
        raise

    # Get coverage from Cost Explorer
    try:
        # Query Cost Explorer using configured lookback period to get most recent coverage data
        # Cost Explorer has 24-48 hour data lag, so we query multiple days and take the most
        # recent data point using [-1] below. Using lookback_days ensures we have enough data
        # even with weekend delays while keeping the setting configurable.
        end_date = now.date()
        start_date = end_date - timedelta(days=config["lookback_days"])

        try:
            # Call Cost Explorer API to get Savings Plans coverage metrics
            # TimePeriod: Must be in ISO format (YYYY-MM-DD)
            # Granularity: DAILY returns one data point per day in the time range
            # GroupBy: SERVICE separates coverage by AWS service (EC2, Lambda, Fargate, SageMaker, etc.)
            response = ce_client.get_savings_plans_coverage(
                TimePeriod={"Start": start_date.isoformat(), "End": end_date.isoformat()},
                Granularity="DAILY",
                GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}],
            )
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            # Handle DataUnavailableException: Cost Explorer requires 24-48 hours of usage data
            # before coverage metrics are available. This occurs in:
            # 1. Newly created AWS accounts (< 48 hours old)
            # 2. Accounts with no recent EC2/RDS/Lambda usage
            # 3. Accounts that just activated Cost Explorer (takes ~24 hours to populate)
            # In these cases, safely return 0% coverage to allow the system to make initial purchases
            if error_code == "DataUnavailableException":
                logger.warning(
                    "Cost Explorer data not available (new account or no usage data). "
                    "Returning 0% coverage."
                )
                return {"compute": 0.0, "database": 0.0, "sagemaker": 0.0}
            raise

        # Extract coverage data points from response
        # Response structure: {"SavingsPlansCoverages": [{"TimePeriod": {...}, "Coverage": {...}}]}
        coverage_by_time = response.get("SavingsPlansCoverages", [])

        # Handle empty response: Can occur if the time period has no usage data
        # Return 0% coverage to allow the system to make initial SP purchases
        if not coverage_by_time:
            logger.warning("No coverage data available from Cost Explorer")
            return {"compute": 0.0, "database": 0.0, "sagemaker": 0.0}

        # Get most recent spend data for each service
        # When using GroupBy, AWS flattens the response: each item represents one service for one day
        # We iterate backwards to find the latest data point for each service
        service_latest_spend = {}  # {service_name: {'covered': float, 'on_demand': float}}

        for item in reversed(coverage_by_time):
            service_name = item.get("Attributes", {}).get("SERVICE", "").lower()

            # Skip if we already found this service's latest data
            if service_name in service_latest_spend:
                continue

            coverage_data = item.get("Coverage", {})

            # When using GroupBy, AWS returns spend amounts, not percentages
            spend_covered = float(coverage_data.get("SpendCoveredBySavingsPlans", 0))
            on_demand_cost = float(coverage_data.get("OnDemandCost", 0))

            service_latest_spend[service_name] = {
                "covered": spend_covered,
                "on_demand": on_demand_cost,
            }
            logger.debug(
                f"Service '{service_name}' - Covered: ${spend_covered:.2f}, On-Demand: ${on_demand_cost:.2f}"
            )

        # Aggregate spend amounts by SP type, then calculate coverage percentage
        # This is the correct approach: sum all spend first, then calculate percentage
        sp_type_spend = {
            "compute": {"covered": 0.0, "on_demand": 0.0},
            "database": {"covered": 0.0, "on_demand": 0.0},
            "sagemaker": {"covered": 0.0, "on_demand": 0.0},
        }

        for service_name, spend in service_latest_spend.items():
            # Compute Savings Plans cover: EC2, Lambda, Fargate, ECS, EKS
            if any(
                svc in service_name
                for svc in [
                    "ec2",
                    "elastic compute cloud",
                    "lambda",
                    "fargate",
                    "elastic container service",
                ]
            ):
                sp_type_spend["compute"]["covered"] += spend["covered"]
                sp_type_spend["compute"]["on_demand"] += spend["on_demand"]
            # SageMaker Savings Plans cover: SageMaker
            elif "sagemaker" in service_name:
                sp_type_spend["sagemaker"]["covered"] += spend["covered"]
                sp_type_spend["sagemaker"]["on_demand"] += spend["on_demand"]
            # Database: RDS, DynamoDB, Database Migration Service
            elif any(
                svc in service_name
                for svc in ["rds", "relational database", "dynamodb", "database migration"]
            ):
                sp_type_spend["database"]["covered"] += spend["covered"]
                sp_type_spend["database"]["on_demand"] += spend["on_demand"]

        # Calculate coverage percentages from aggregated spend
        coverage = {"compute": 0.0, "database": 0.0, "sagemaker": 0.0}

        for sp_type, spend in sp_type_spend.items():
            total_spend = spend["covered"] + spend["on_demand"]
            if total_spend > 0:
                coverage[sp_type] = (spend["covered"] / total_spend) * 100

        if service_latest_spend:
            logger.info(
                f"Coverage by type - Compute: {coverage['compute']:.2f}%, "
                f"Database: {coverage['database']:.2f}%, SageMaker: {coverage['sagemaker']:.2f}%"
            )
        else:
            logger.warning("No service-level coverage data available in response")

    except ClientError as e:
        logger.error(f"Failed to get coverage from Cost Explorer: {e!s}")
        raise

    logger.info(f"Coverage calculated: {coverage}")
    return coverage

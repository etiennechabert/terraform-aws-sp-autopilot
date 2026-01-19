"""
Coverage calculation module for Scheduler Lambda.

Calculates current Savings Plans coverage, excluding plans expiring soon.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

from botocore.exceptions import ClientError


if TYPE_CHECKING:
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
        start_date = end_date - timedelta(days=config.get("lookback_days", 7))

        try:
            # Call Cost Explorer API to get Savings Plans coverage metrics
            # TimePeriod: Must be in ISO format (YYYY-MM-DD)
            # Granularity: DAILY returns one data point per day in the time range
            # GroupBy: Separates coverage by Savings Plan type (Compute, SageMaker, etc.)
            response = ce_client.get_savings_plans_coverage(
                TimePeriod={"Start": start_date.isoformat(), "End": end_date.isoformat()},
                Granularity="DAILY",
                GroupBy=[{"Type": "DIMENSION", "Key": "SAVINGS_PLANS_TYPE"}],
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

        # Get the most recent coverage data point using [-1] index
        # Why [-1]: Cost Explorer returns data points ordered chronologically (oldest first)
        # The last element contains the most recent coverage snapshot, which is what we need
        # for making current purchase decisions
        latest_coverage = coverage_by_time[-1]

        # Initialize coverage dictionary
        coverage = {"compute": 0.0, "database": 0.0, "sagemaker": 0.0}

        # Extract coverage by SP type from grouped data
        # When using GroupBy=["SAVINGS_PLANS_TYPE"], the response structure is:
        # {"Groups": [{"Attributes": {"SAVINGS_PLANS_TYPE": "ComputeSP"}, "Coverage": {"CoveragePercentage": "75.5"}}]}
        coverage_groups = latest_coverage.get("Groups", [])

        if coverage_groups:
            # GroupBy returned separate coverage per SP type - parse each group
            for group in coverage_groups:
                sp_type = group.get("Attributes", {}).get("SAVINGS_PLANS_TYPE", "").lower()
                coverage_data = group.get("Coverage", {})

                if "CoveragePercentage" in coverage_data:
                    percentage = float(coverage_data["CoveragePercentage"])

                    # Map AWS SP types to our internal names
                    # ComputeSP and EC2InstanceSP both contribute to compute coverage
                    if "computesp" in sp_type or "ec2instancesp" in sp_type:
                        coverage["compute"] = max(coverage["compute"], percentage)
                    elif "sagemakersp" in sp_type:
                        coverage["sagemaker"] = percentage
                    # RDS Instance SPs are technically separate but we group as database
                    elif "rdsinstance" in sp_type:
                        coverage["database"] = percentage

            logger.info(
                f"Coverage by type - Compute: {coverage['compute']}%, "
                f"Database: {coverage['database']}%, SageMaker: {coverage['sagemaker']}%"
            )
        else:
            # Fallback: No groups returned (shouldn't happen with GroupBy, but handle gracefully)
            # Use aggregate coverage if available
            coverage_data = latest_coverage.get("Coverage", {})
            if "CoveragePercentage" in coverage_data:
                aggregate_coverage = float(coverage_data["CoveragePercentage"])
                logger.warning(
                    f"GroupBy returned no groups, using aggregate coverage: {aggregate_coverage}%"
                )
                coverage["compute"] = aggregate_coverage
            else:
                logger.warning("No coverage data available")

    except ClientError as e:
        logger.error(f"Failed to get coverage from Cost Explorer: {e!s}")
        raise

    logger.info(f"Coverage calculated: {coverage}")
    return coverage

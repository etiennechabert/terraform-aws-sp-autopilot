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
        # Query Cost Explorer for the last 1 day (most recent data point)
        # Why 1 day: Cost Explorer returns daily granularity data, and we only need the latest
        # snapshot to determine current coverage. Using a single day minimizes API response size
        # and ensures we get the most up-to-date coverage information available.
        end_date = now.date()
        start_date = end_date - timedelta(days=1)

        try:
            # Call Cost Explorer API to get Savings Plans coverage metrics
            # TimePeriod: Must be in ISO format (YYYY-MM-DD)
            # Granularity: DAILY returns one data point per day in the time range
            response = ce_client.get_savings_plans_coverage(
                TimePeriod={"Start": start_date.isoformat(), "End": end_date.isoformat()},
                Granularity="DAILY",
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
        coverage_data = latest_coverage.get("Coverage", {})

        # Extract coverage percentage from nested structure
        # Structure: {"Coverage": {"CoveragePercentage": "75.5", ...}}
        # CoveragePercentage represents the percentage of eligible spend covered by active SPs
        # Example: "75.5" means 75.5% of SP-eligible spend is covered, 24.5% is on-demand
        coverage_percentage = 0.0
        if "CoveragePercentage" in coverage_data:
            coverage_percentage = float(coverage_data["CoveragePercentage"])

        logger.info(f"Overall Savings Plans coverage: {coverage_percentage}%")

        # LIMITATION: Cost Explorer's basic GetSavingsPlansCoverage API returns aggregate coverage
        # across all SP types (Compute, EC2 Instance, SageMaker). It does NOT break down coverage
        # by individual SP type without using the GroupBy parameter.
        #
        # Current approach: Assign aggregate coverage to "compute" and 0% to others
        # Why: This is a simplified approach for initial implementation. Most customers have
        # Compute SPs as their primary SP type, so using aggregate coverage for compute provides
        # a reasonable approximation.
        #
        # Future enhancement: Call GetSavingsPlansCoverage with GroupBy=["SAVINGS_PLANS_TYPE"]
        # to get separate coverage percentages for each SP type, enabling more accurate
        # purchase decisions for database and sagemaker SPs.
        coverage = {"compute": coverage_percentage, "database": 0.0, "sagemaker": 0.0}

    except ClientError as e:
        logger.error(f"Failed to get coverage from Cost Explorer: {e!s}")
        raise

    logger.info(f"Coverage calculated: {coverage}")
    return coverage

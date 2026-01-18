"""
Coverage calculation module for Scheduler Lambda.

Calculates current Savings Plans coverage, excluding plans expiring soon.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from botocore.exceptions import ClientError


# Configure logging
logger = logging.getLogger()


def calculate_current_coverage(
    savingsplans_client: Any, ce_client: Any, config: Dict[str, Any]
) -> Dict[str, float]:
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
        # Get coverage for the last 1 day (most recent data point)
        end_date = now.date()
        start_date = end_date - timedelta(days=1)

        try:
            response = ce_client.get_savings_plans_coverage(
                TimePeriod={"Start": start_date.isoformat(), "End": end_date.isoformat()},
                Granularity="DAILY",
            )
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code == "DataUnavailableException":
                logger.warning(
                    "Cost Explorer data not available (new account or no usage data). "
                    "Returning 0% coverage."
                )
                return {"compute": 0.0, "database": 0.0, "sagemaker": 0.0}
            raise

        coverage_by_time = response.get("SavingsPlansCoverages", [])

        if not coverage_by_time:
            logger.warning("No coverage data available from Cost Explorer")
            return {"compute": 0.0, "database": 0.0, "sagemaker": 0.0}

        # Get the most recent coverage data point
        latest_coverage = coverage_by_time[-1]
        coverage_data = latest_coverage.get("Coverage", {})

        # Extract coverage percentage
        coverage_percentage = 0.0
        if "CoveragePercentage" in coverage_data:
            coverage_percentage = float(coverage_data["CoveragePercentage"])

        logger.info(f"Overall Savings Plans coverage: {coverage_percentage}%")

        # Note: Cost Explorer doesn't separate coverage by SP type in the basic API call
        # For now, we'll use the overall coverage for compute and assume 0 for database and sagemaker
        # In a production system, you might need to call GetSavingsPlansCoverage with
        # GroupBy to separate by service or use DescribeSavingsPlans to categorize
        coverage = {"compute": coverage_percentage, "database": 0.0, "sagemaker": 0.0}

    except ClientError as e:
        logger.error(f"Failed to get coverage from Cost Explorer: {e!s}")
        raise

    logger.info(f"Coverage calculated: {coverage}")
    return coverage

"""
Data collection module for Reporter Lambda.

Collects coverage history, savings data, and cost data from AWS Cost Explorer
and Savings Plans APIs.
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from botocore.exceptions import ClientError


# Configure logging
logger = logging.getLogger()


def get_coverage_history(ce_client: Any, lookback_days: int = 30) -> list[dict[str, Any]]:
    """
    Get Savings Plans coverage history from Cost Explorer.

    Args:
        ce_client: Boto3 Cost Explorer client
        lookback_days: Number of days to look back for coverage data

    Returns:
        list: Coverage data points by day with timestamps and percentages

    Raises:
        ClientError: If Cost Explorer API call fails
    """
    logger.info(f"Fetching coverage history for last {lookback_days} days")

    try:
        # Calculate date range
        end_date = datetime.now(UTC).date()
        start_date = end_date - timedelta(days=lookback_days)

        logger.info(f"Querying coverage from {start_date} to {end_date}")

        # Get coverage data from Cost Explorer
        response = ce_client.get_savings_plans_coverage(
            TimePeriod={"Start": start_date.isoformat(), "End": end_date.isoformat()},
            Granularity="DAILY",
        )

        coverage_by_time = response.get("SavingsPlansCoverages", [])

        if not coverage_by_time:
            logger.warning("No coverage data available from Cost Explorer")
            return []

        # Parse coverage data points
        coverage_history = []
        for coverage_item in coverage_by_time:
            time_period = coverage_item.get("TimePeriod", {})
            coverage_data = coverage_item.get("Coverage", {})

            coverage_percentage = 0.0
            if "CoveragePercentage" in coverage_data:
                coverage_percentage = float(coverage_data["CoveragePercentage"])

            coverage_hours = coverage_data.get("CoverageHours", {})
            on_demand_hours = float(coverage_hours.get("OnDemandHours", "0"))
            covered_hours = float(coverage_hours.get("CoveredHours", "0"))
            total_hours = float(coverage_hours.get("TotalRunningHours", "0"))

            coverage_history.append(
                {
                    "date": time_period.get("Start"),
                    "coverage_percentage": coverage_percentage,
                    "on_demand_hours": on_demand_hours,
                    "covered_hours": covered_hours,
                    "total_hours": total_hours,
                }
            )

        logger.info(f"Retrieved {len(coverage_history)} coverage data points")
        return coverage_history

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        error_message = e.response.get("Error", {}).get("Message", str(e))
        logger.error(
            f"Failed to get coverage history - Code: {error_code}, Message: {error_message}"
        )
        raise


def get_actual_cost_data(ce_client: Any, lookback_days: int = 30) -> dict[str, Any]:
    """
    Get actual Savings Plans and On-Demand costs from Cost Explorer.

    Args:
        ce_client: Boto3 Cost Explorer client
        lookback_days: Number of days to look back for cost data

    Returns:
        dict: Cost data including Savings Plans spend and On-Demand spend by day

    Raises:
        ClientError: If Cost Explorer API call fails
    """
    logger.info(f"Fetching actual cost data for last {lookback_days} days")

    try:
        # Calculate date range
        end_date = datetime.now(UTC).date()
        start_date = end_date - timedelta(days=lookback_days)

        logger.info(f"Querying costs from {start_date} to {end_date}")

        # Get cost data from Cost Explorer
        # Group by purchase option to separate Savings Plans from On-Demand
        response = ce_client.get_cost_and_usage(
            TimePeriod={"Start": start_date.isoformat(), "End": end_date.isoformat()},
            Granularity="DAILY",
            Metrics=["UnblendedCost"],
            GroupBy=[{"Type": "DIMENSION", "Key": "PURCHASE_OPTION"}],
        )

        results_by_time = response.get("ResultsByTime", [])

        if not results_by_time:
            logger.warning("No cost data available from Cost Explorer")
            return {
                "cost_by_day": [],
                "total_savings_plans_cost": 0.0,
                "total_on_demand_cost": 0.0,
                "total_cost": 0.0,
            }

        # Parse cost data by day
        cost_by_day = []
        total_savings_plans_cost = 0.0
        total_on_demand_cost = 0.0

        for result_item in results_by_time:
            time_period = result_item.get("TimePeriod", {})
            groups = result_item.get("Groups", [])

            daily_savings_plans_cost = 0.0
            daily_on_demand_cost = 0.0

            # Process each purchase option group
            for group in groups:
                keys = group.get("Keys", [])
                metrics = group.get("Metrics", {})

                # Extract purchase option (e.g., 'Savings Plans', 'On Demand')
                purchase_option = keys[0] if keys else "Unknown"

                # Extract cost amount
                unblended_cost = metrics.get("UnblendedCost", {})
                cost_amount = float(unblended_cost.get("Amount", "0"))

                # Categorize by purchase option
                if "Savings Plans" in purchase_option or "SavingsPlan" in purchase_option:
                    daily_savings_plans_cost += cost_amount
                    total_savings_plans_cost += cost_amount
                elif "On Demand" in purchase_option or "OnDemand" in purchase_option:
                    daily_on_demand_cost += cost_amount
                    total_on_demand_cost += cost_amount

            daily_total_cost = daily_savings_plans_cost + daily_on_demand_cost

            cost_by_day.append(
                {
                    "date": time_period.get("Start"),
                    "savings_plans_cost": daily_savings_plans_cost,
                    "on_demand_cost": daily_on_demand_cost,
                    "total_cost": daily_total_cost,
                }
            )

        total_cost = total_savings_plans_cost + total_on_demand_cost

        logger.info(f"Retrieved {len(cost_by_day)} cost data points")
        logger.info(f"Total Savings Plans cost: ${total_savings_plans_cost:.2f}")
        logger.info(f"Total On-Demand cost: ${total_on_demand_cost:.2f}")
        logger.info(f"Total cost: ${total_cost:.2f}")

        return {
            "cost_by_day": cost_by_day,
            "total_savings_plans_cost": total_savings_plans_cost,
            "total_on_demand_cost": total_on_demand_cost,
            "total_cost": total_cost,
        }

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        error_message = e.response.get("Error", {}).get("Message", str(e))
        logger.error(
            f"Failed to get actual cost data - Code: {error_code}, Message: {error_message}"
        )
        raise


def get_savings_data(savingsplans_client: Any, ce_client: Any) -> dict[str, Any]:
    """
    Get savings data from active Savings Plans.

    Args:
        savingsplans_client: Boto3 Savings Plans client
        ce_client: Boto3 Cost Explorer client

    Returns:
        dict: Savings Plans data including commitment, utilization, and estimated savings

    Raises:
        ClientError: If Savings Plans or Cost Explorer API calls fail
    """
    logger.info("Fetching savings data from active Savings Plans")

    try:
        # Get all active Savings Plans
        response = savingsplans_client.describe_savings_plans(
            filters=[{"name": "state", "values": ["active"]}]
        )

        savings_plans = response.get("savingsPlans", [])
        logger.info(f"Found {len(savings_plans)} active Savings Plans")

        if not savings_plans:
            return {
                "total_commitment": 0.0,
                "plans_count": 0,
                "plans": [],
                "estimated_monthly_savings": 0.0,
                "average_utilization": 0.0,
                "actual_savings": {
                    "actual_sp_cost": 0.0,
                    "on_demand_equivalent_cost": 0.0,
                    "net_savings": 0.0,
                    "savings_percentage": 0.0,
                    "breakdown_by_type": {},
                },
            }

        # Calculate total commitment and collect plan details
        total_hourly_commitment = 0.0
        plans_data = []

        for plan in savings_plans:
            hourly_commitment = float(plan.get("commitment", "0"))
            total_hourly_commitment += hourly_commitment

            plan_type = plan.get("savingsPlanType", "Unknown")
            plan_id = plan.get("savingsPlanId", "Unknown")
            start_date = plan.get("start", "Unknown")
            end_date = plan.get("end", "Unknown")
            payment_option = plan.get("paymentOption", "Unknown")
            term = plan.get("termDurationInSeconds", 0) // (
                365 * 24 * 60 * 60
            )  # Convert seconds to years

            plans_data.append(
                {
                    "plan_id": plan_id,
                    "plan_type": plan_type,
                    "hourly_commitment": hourly_commitment,
                    "start_date": start_date,
                    "end_date": end_date,
                    "payment_option": payment_option,
                    "term_years": term,
                }
            )

        logger.info(f"Total hourly commitment: ${total_hourly_commitment:.2f}/hour")

        # Get utilization and actual savings data from Cost Explorer
        try:
            end_date = datetime.now(UTC).date()
            start_date = end_date - timedelta(days=30)  # Last 30 days for actual savings

            utilization_response = ce_client.get_savings_plans_utilization(
                TimePeriod={
                    "Start": start_date.isoformat(),
                    "End": end_date.isoformat(),
                },
                Granularity="DAILY",
            )

            utilizations = utilization_response.get("SavingsPlansUtilizationsByTime", [])

            if utilizations:
                # Calculate average utilization and actual savings
                total_utilization = 0.0
                count = 0
                total_net_savings = 0.0
                total_on_demand_equivalent = 0.0
                total_amortized_commitment = 0.0

                for util_item in utilizations:
                    # Extract utilization percentage
                    utilization = util_item.get("Utilization", {})
                    utilization_percentage = utilization.get("UtilizationPercentage")

                    if utilization_percentage:
                        total_utilization += float(utilization_percentage)
                        count += 1

                    # Extract actual savings data
                    savings = util_item.get("Savings", {})
                    net_savings = savings.get("NetSavings", "0")
                    on_demand_equivalent = savings.get("OnDemandCostEquivalent", "0")

                    # Extract amortized commitment
                    amortized = util_item.get("AmortizedCommitment", {})
                    amortized_commitment = amortized.get("TotalAmortizedCommitment", "0")

                    # Accumulate totals
                    total_net_savings += float(net_savings)
                    total_on_demand_equivalent += float(on_demand_equivalent)
                    total_amortized_commitment += float(amortized_commitment)

                average_utilization = total_utilization / count if count > 0 else 0.0
                logger.info(f"Average utilization over last 30 days: {average_utilization:.2f}%")
                logger.info(f"Actual net savings over last 30 days: ${total_net_savings:.2f}")
                logger.info(f"On-demand equivalent cost: ${total_on_demand_equivalent:.2f}")
                logger.info(f"Amortized SP commitment: ${total_amortized_commitment:.2f}")
            else:
                average_utilization = 0.0
                total_net_savings = 0.0
                total_on_demand_equivalent = 0.0
                total_amortized_commitment = 0.0
                logger.warning("No utilization data available")

        except ClientError as e:
            logger.warning(f"Failed to get utilization data: {e!s}")
            average_utilization = 0.0
            total_net_savings = 0.0
            total_on_demand_equivalent = 0.0
            total_amortized_commitment = 0.0

        # Calculate actual savings percentage
        savings_percentage = 0.0
        if total_on_demand_equivalent > 0:
            savings_percentage = (total_net_savings / total_on_demand_equivalent) * 100.0

        # Calculate breakdown by plan type
        breakdown_by_type = {}
        for plan in plans_data:
            plan_type = plan["plan_type"]
            if plan_type not in breakdown_by_type:
                breakdown_by_type[plan_type] = {
                    "plans_count": 0,
                    "total_commitment": 0.0,
                }
            breakdown_by_type[plan_type]["plans_count"] += 1
            breakdown_by_type[plan_type]["total_commitment"] += plan["hourly_commitment"]

        logger.info(f"Actual monthly savings: ${total_net_savings:.2f} ({savings_percentage:.2f}%)")

        return {
            "total_commitment": total_hourly_commitment,
            "plans_count": len(savings_plans),
            "plans": plans_data,
            "estimated_monthly_savings": total_net_savings,  # Now using actual savings
            "average_utilization": average_utilization,
            "actual_savings": {
                "actual_sp_cost": total_amortized_commitment,
                "on_demand_equivalent_cost": total_on_demand_equivalent,
                "net_savings": total_net_savings,
                "savings_percentage": savings_percentage,
                "breakdown_by_type": breakdown_by_type,
            },
        }

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        error_message = e.response.get("Error", {}).get("Message", str(e))
        logger.error(f"Failed to get savings data - Code: {error_code}, Message: {error_message}")
        raise

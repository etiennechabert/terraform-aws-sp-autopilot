"""
Savings Plans Metrics.

Shared module for collecting Savings Plans metrics including active plans,
utilization, and actual savings calculations. Used by Reporter and potentially
other lambdas for metrics and analysis.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from botocore.exceptions import ClientError


if TYPE_CHECKING:
    from mypy_boto3_ce.client import CostExplorerClient
    from mypy_boto3_savingsplans.client import SavingsPlansClient


logger = logging.getLogger(__name__)


def get_active_savings_plans(
    savingsplans_client: SavingsPlansClient,
) -> list[dict[str, Any]]:
    """
    Get all active Savings Plans with details.

    Args:
        savingsplans_client: Boto3 Savings Plans client

    Returns:
        list: Active Savings Plans with details:
            [
                {
                    "plan_id": "...",
                    "plan_type": "Compute" | "SageMaker" | "EC2Instance",
                    "hourly_commitment": 1.234,
                    "start_date": "2024-01-01T00:00:00Z",
                    "end_date": "2027-01-01T00:00:00Z",
                    "payment_option": "NO_UPFRONT" | "PARTIAL_UPFRONT" | "ALL_UPFRONT",
                    "term_years": 1 | 3
                },
                ...
            ]

    Raises:
        ClientError: If Savings Plans API call fails
    """
    logger.info("Fetching active Savings Plans")

    try:
        response = savingsplans_client.describe_savings_plans(states=["active"])

        savings_plans = response.get("savingsPlans", [])
        logger.info(f"Found {len(savings_plans)} active Savings Plans")

        plans_data = []
        for plan in savings_plans:
            hourly_commitment = float(plan.get("commitment", "0"))
            plan_type = plan.get("savingsPlanType", "Unknown")
            plan_id = plan.get("savingsPlanId", "Unknown")
            start_date = plan.get("start", "Unknown")
            end_date = plan.get("end", "Unknown")
            payment_option = plan.get("paymentOption", "Unknown")
            term_seconds = plan.get("termDurationInSeconds", 0)
            term_years = term_seconds // (365 * 24 * 60 * 60)

            plans_data.append(
                {
                    "plan_id": plan_id,
                    "plan_type": plan_type,
                    "hourly_commitment": hourly_commitment,
                    "start_date": start_date,
                    "end_date": end_date,
                    "payment_option": payment_option,
                    "term_years": term_years,
                }
            )

        return plans_data

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        error_message = e.response.get("Error", {}).get("Message", str(e))
        logger.error(
            f"Failed to get active Savings Plans - Code: {error_code}, Message: {error_message}"
        )
        raise


def get_savings_plans_utilization(
    ce_client: CostExplorerClient, lookback_days: int = 30
) -> dict[str, Any]:
    """
    Get Savings Plans utilization metrics.

    Args:
        ce_client: Boto3 Cost Explorer client
        lookback_days: Number of days to analyze (default: 30)

    Returns:
        dict: Utilization metrics:
            {
                "average_utilization": 85.5,  # percentage
                "utilization_by_day": [
                    {"date": "2024-01-01", "utilization": 85.0},
                    ...
                ]
            }

    Raises:
        ClientError: If Cost Explorer API call fails
    """
    logger.info(f"Fetching Savings Plans utilization for last {lookback_days} days")

    try:
        end_date = datetime.now(UTC).date()
        start_date = end_date - timedelta(days=lookback_days)

        response = ce_client.get_savings_plans_utilization(
            TimePeriod={
                "Start": start_date.isoformat(),
                "End": end_date.isoformat(),
            },
            Granularity="DAILY",
        )

        utilizations = response.get("SavingsPlansUtilizationsByTime", [])

        if not utilizations:
            logger.warning("No utilization data available")
            return {
                "average_utilization": 0.0,
                "utilization_by_day": [],
            }

        total_utilization = 0.0
        count = 0
        utilization_by_day = []

        for util_item in utilizations:
            time_period = util_item.get("TimePeriod", {})
            utilization = util_item.get("Utilization", {})
            utilization_percentage = utilization.get("UtilizationPercentage")

            if utilization_percentage:
                util_pct = float(utilization_percentage)
                total_utilization += util_pct
                count += 1

                utilization_by_day.append(
                    {
                        "date": time_period.get("Start"),
                        "utilization": util_pct,
                    }
                )

        average_utilization = total_utilization / count if count > 0 else 0.0
        logger.info(f"Average utilization: {average_utilization:.2f}%")

        return {
            "average_utilization": average_utilization,
            "utilization_by_day": utilization_by_day,
        }

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        error_message = e.response.get("Error", {}).get("Message", str(e))
        logger.error(
            f"Failed to get utilization data - Code: {error_code}, Message: {error_message}"
        )
        raise


def get_actual_savings(ce_client: CostExplorerClient, lookback_days: int = 30) -> dict[str, Any]:
    """
    Get actual Savings Plans savings metrics.

    Args:
        ce_client: Boto3 Cost Explorer client
        lookback_days: Number of days to analyze (default: 30)

    Returns:
        dict: Actual savings metrics:
            {
                "actual_sp_cost": 1000.00,  # What you actually paid with SPs
                "on_demand_equivalent_cost": 1200.00,  # What you would have paid
                "net_savings": 200.00,  # Actual savings
                "savings_percentage": 16.67,  # Savings as % of on-demand equivalent
                "breakdown_by_type": {
                    "Compute": {"plans_count": 2, "total_commitment": 0.5},
                    ...
                }
            }

    Raises:
        ClientError: If Cost Explorer API call fails
    """
    logger.info(f"Fetching actual savings data for last {lookback_days} days")

    try:
        end_date = datetime.now(UTC).date()
        start_date = end_date - timedelta(days=lookback_days)

        response = ce_client.get_savings_plans_utilization(
            TimePeriod={
                "Start": start_date.isoformat(),
                "End": end_date.isoformat(),
            },
            Granularity="DAILY",
        )

        utilizations = response.get("SavingsPlansUtilizationsByTime", [])

        if not utilizations:
            logger.warning("No savings data available")
            return {
                "actual_sp_cost": 0.0,
                "on_demand_equivalent_cost": 0.0,
                "net_savings": 0.0,
                "savings_percentage": 0.0,
                "breakdown_by_type": {},
            }

        total_net_savings = 0.0
        total_on_demand_equivalent = 0.0
        total_amortized_commitment = 0.0

        for util_item in utilizations:
            savings = util_item.get("Savings", {})
            net_savings = savings.get("NetSavings", "0")
            on_demand_equivalent = savings.get("OnDemandCostEquivalent", "0")

            amortized = util_item.get("AmortizedCommitment", {})
            amortized_commitment = amortized.get("TotalAmortizedCommitment", "0")

            total_net_savings += float(net_savings)
            total_on_demand_equivalent += float(on_demand_equivalent)
            total_amortized_commitment += float(amortized_commitment)

        savings_percentage = 0.0
        if total_on_demand_equivalent > 0:
            savings_percentage = (total_net_savings / total_on_demand_equivalent) * 100.0

        logger.info(
            f"Actual savings: ${total_net_savings:.2f} ({savings_percentage:.2f}% of "
            f"${total_on_demand_equivalent:.2f} on-demand equivalent)"
        )

        return {
            "actual_sp_cost": total_amortized_commitment,
            "on_demand_equivalent_cost": total_on_demand_equivalent,
            "net_savings": total_net_savings,
            "savings_percentage": savings_percentage,
            "breakdown_by_type": {},  # Populated by caller if needed
        }

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        error_message = e.response.get("Error", {}).get("Message", str(e))
        logger.error(
            f"Failed to get actual savings data - Code: {error_code}, Message: {error_message}"
        )
        raise


def get_savings_plans_summary(
    savingsplans_client: SavingsPlansClient,
    ce_client: CostExplorerClient,
    lookback_days: int = 30,
) -> dict[str, Any]:
    """
    Get comprehensive Savings Plans summary combining all metrics.

    This is a convenience function that combines active plans, utilization,
    and actual savings into a single summary.

    Args:
        savingsplans_client: Boto3 Savings Plans client
        ce_client: Boto3 Cost Explorer client
        lookback_days: Number of days to analyze for utilization/savings (default: 30)

    Returns:
        dict: Complete summary:
            {
                "plans_count": 5,
                "total_commitment": 2.5,  # hourly
                "plans": [...],  # from get_active_savings_plans()
                "average_utilization": 85.5,
                "estimated_monthly_savings": 200.0,  # net_savings from actual_savings
                "actual_savings": {...}  # from get_actual_savings()
            }

    Raises:
        ClientError: If any AWS API calls fail
    """
    logger.info("Fetching comprehensive Savings Plans summary")

    # Get active plans
    plans = get_active_savings_plans(savingsplans_client)
    total_commitment = sum(plan["hourly_commitment"] for plan in plans)

    # Get utilization
    utilization_data = get_savings_plans_utilization(ce_client, lookback_days)

    # Get actual savings
    actual_savings = get_actual_savings(ce_client, lookback_days)

    # Calculate breakdown by type
    breakdown_by_type = {}
    for plan in plans:
        plan_type = plan["plan_type"]
        if plan_type not in breakdown_by_type:
            breakdown_by_type[plan_type] = {
                "plans_count": 0,
                "total_commitment": 0.0,
            }
        breakdown_by_type[plan_type]["plans_count"] += 1
        breakdown_by_type[plan_type]["total_commitment"] += plan["hourly_commitment"]

    # Add breakdown to actual_savings
    actual_savings["breakdown_by_type"] = breakdown_by_type

    return {
        "plans_count": len(plans),
        "total_commitment": total_commitment,
        "plans": plans,
        "average_utilization": utilization_data["average_utilization"],
        "estimated_monthly_savings": actual_savings["net_savings"],
        "actual_savings": actual_savings,
    }

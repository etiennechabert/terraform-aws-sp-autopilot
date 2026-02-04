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

from shared.aws_debug import add_response
from shared.constants import DIMENSION_SAVINGS_PLANS_TYPE, PLAN_TYPE_TO_API_FILTER


if TYPE_CHECKING:
    from mypy_boto3_ce.client import CostExplorerClient
    from mypy_boto3_savingsplans.client import SavingsPlansClient


logger = logging.getLogger(__name__)


def _initialize_breakdown_by_type(plans: list[dict[str, Any]]) -> dict[str, Any]:
    """Initialize breakdown_by_type structure from active plans."""
    breakdown = {}
    for plan in plans:
        aws_plan_type = plan["plan_type"]
        if aws_plan_type not in breakdown:
            breakdown[aws_plan_type] = {
                "plans_count": 0,
                "total_commitment": 0.0,
            }
        breakdown[aws_plan_type]["plans_count"] += 1
        breakdown[aws_plan_type]["total_commitment"] += plan["hourly_commitment"]
    return breakdown


def _aggregate_type_metrics(
    ce_client: CostExplorerClient,
    enabled_plan_types: list[str],
    breakdown_by_type: dict[str, Any],
    lookback_days: int,
    granularity: str,
) -> tuple[float, float, float]:
    """Fetch and aggregate per-type metrics. Returns (net_savings, on_demand_equivalent, sp_cost)."""
    total_net_savings = 0.0
    total_on_demand_equivalent = 0.0
    total_actual_sp_cost = 0.0

    for plan_type in enabled_plan_types:
        type_metrics = get_savings_plans_metrics(ce_client, plan_type, lookback_days, granularity)

        if plan_type in breakdown_by_type:
            breakdown_by_type[plan_type]["average_utilization"] = type_metrics[
                "average_utilization"
            ]
            breakdown_by_type[plan_type]["net_savings_hourly"] = type_metrics["net_savings_hourly"]
            breakdown_by_type[plan_type]["on_demand_equivalent_hourly"] = type_metrics[
                "on_demand_equivalent_hourly"
            ]
            breakdown_by_type[plan_type]["actual_sp_cost_hourly"] = type_metrics[
                "actual_sp_cost_hourly"
            ]
            breakdown_by_type[plan_type]["savings_percentage"] = type_metrics["savings_percentage"]

            total_net_savings += type_metrics["net_savings_hourly"]
            total_on_demand_equivalent += type_metrics["on_demand_equivalent_hourly"]
            total_actual_sp_cost += type_metrics["actual_sp_cost_hourly"]

    return total_net_savings, total_on_demand_equivalent, total_actual_sp_cost


def _calculate_weighted_utilization(breakdown_by_type: dict[str, Any]) -> float:
    """Calculate overall utilization as weighted average by commitment."""
    weighted_utilization_sum = sum(
        breakdown_by_type[t]["average_utilization"] * breakdown_by_type[t]["total_commitment"]
        for t in breakdown_by_type
        if "average_utilization" in breakdown_by_type[t]
    )
    commitment_with_utilization_data = sum(
        breakdown_by_type[t]["total_commitment"]
        for t in breakdown_by_type
        if "average_utilization" in breakdown_by_type[t]
    )
    return (
        weighted_utilization_sum / commitment_with_utilization_data
        if commitment_with_utilization_data > 0
        else 0.0
    )


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
        params = {"states": ["active"]}
        response = savingsplans_client.describe_savings_plans(states=["active"])

        # Capture raw AWS response for debugging
        add_response(
            api="describe_savings_plans",
            params=params,
            response=response,
            context="get_active_savings_plans",
        )

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


def _round_start_time_for_hourly(start_time: datetime) -> datetime:
    """Round start time UP to next midnight for HOURLY granularity."""
    if (
        start_time.hour != 0
        or start_time.minute != 0
        or start_time.second != 0
        or start_time.microsecond != 0
    ):
        return start_time.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    return start_time.replace(hour=0, minute=0, second=0, microsecond=0)


def _process_utilization_data(utilizations: list[dict[str, Any]]) -> dict[str, Any]:
    """Process utilization data from API response."""
    total_utilization = 0.0
    count = 0
    utilization_by_day = []
    total_net_savings = 0.0
    total_on_demand_equivalent = 0.0
    total_amortized_commitment = 0.0
    total_used_commitment = 0.0

    for util_item in utilizations:
        time_period = util_item.get("TimePeriod", {})

        utilization = util_item.get("Utilization", {})
        utilization_percentage = utilization.get("UtilizationPercentage")
        used_commitment = utilization.get("UsedCommitment", "0")

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

        savings = util_item.get("Savings", {})
        net_savings = savings.get("NetSavings", "0")
        on_demand_equivalent = savings.get("OnDemandCostEquivalent", "0")

        amortized = util_item.get("AmortizedCommitment", {})
        amortized_commitment = amortized.get("TotalAmortizedCommitment", "0")

        total_net_savings += float(net_savings)
        total_on_demand_equivalent += float(on_demand_equivalent)
        total_amortized_commitment += float(amortized_commitment)
        total_used_commitment += float(used_commitment)

    return {
        "total_utilization": total_utilization,
        "count": count,
        "utilization_by_day": utilization_by_day,
        "total_net_savings": total_net_savings,
        "total_on_demand_equivalent": total_on_demand_equivalent,
        "total_amortized_commitment": total_amortized_commitment,
        "total_used_commitment": total_used_commitment,
    }


def get_savings_plans_metrics(
    ce_client: CostExplorerClient,
    plan_type: str,
    lookback_days: int,
    granularity: str = "HOURLY",
) -> dict[str, Any]:
    """
    Get Savings Plans utilization and savings metrics for a specific plan type.

    Single API call to get_savings_plans_utilization returns both utilization AND savings data.

    Args:
        ce_client: Boto3 Cost Explorer client
        plan_type: Plan type to filter by ("compute", "sagemaker", "database")
        lookback_days: Number of days to analyze
        granularity: API granularity - "HOURLY" or "DAILY" (default: "HOURLY")

    Returns:
        dict: Combined metrics:
            {
                "average_utilization": 85.5,
                "utilization_by_day": [...],
                "actual_sp_cost_hourly": 1.39,
                "on_demand_equivalent_hourly": 1.67,
                "net_savings_hourly": 0.28,
                "savings_percentage": 16.67,
            }
            Returns zeros if no data available (e.g., no active plans of this type)

    Raises:
        ClientError: If Cost Explorer API call fails (except DataUnavailableException)
    """
    logger.info(
        f"Fetching Savings Plans metrics for {plan_type} for last {lookback_days} days (granularity: {granularity})"
    )

    if plan_type not in PLAN_TYPE_TO_API_FILTER:
        raise ValueError(
            f"Invalid plan_type '{plan_type}'. Must be one of: {list(PLAN_TYPE_TO_API_FILTER.keys())}"
        )

    try:
        end_time = datetime.now(UTC)
        start_time = end_time - timedelta(days=lookback_days)

        if granularity == "HOURLY":
            start_time = _round_start_time_for_hourly(start_time)

        # Format dates based on granularity
        # HOURLY requires ISO 8601 (yyyy-MM-ddTHH:mm:ssZ)
        # DAILY requires date only (yyyy-MM-dd)
        date_format = "%Y-%m-%d" if granularity == "DAILY" else "%Y-%m-%dT%H:%M:%SZ"

        params = {
            "TimePeriod": {
                "Start": start_time.strftime(date_format),
                "End": end_time.strftime(date_format),
            },
            "Granularity": granularity,
            "Filter": {
                "Dimensions": {
                    "Key": DIMENSION_SAVINGS_PLANS_TYPE,
                    "Values": [PLAN_TYPE_TO_API_FILTER[plan_type]],
                }
            },
        }

        response = ce_client.get_savings_plans_utilization(**params)

        # Capture raw AWS response for debugging
        add_response(
            api="get_savings_plans_utilization",
            params=params,
            response=response,
            plan_type=plan_type,
            context="get_savings_plans_metrics",
        )

        utilizations = response.get("SavingsPlansUtilizationsByTime", [])

        if not utilizations:
            logger.warning("No metrics data available")
            return {
                "average_utilization": 0.0,
                "utilization_by_day": [],
                "actual_sp_cost_hourly": 0.0,
                "on_demand_equivalent_hourly": 0.0,
                "net_savings_hourly": 0.0,
                "savings_percentage": 0.0,
            }

        processed = _process_utilization_data(utilizations)
        total_utilization = processed["total_utilization"]
        count = processed["count"]
        utilization_by_day = processed["utilization_by_day"]
        total_net_savings = processed["total_net_savings"]
        total_on_demand_equivalent = processed["total_on_demand_equivalent"]
        total_amortized_commitment = processed["total_amortized_commitment"]
        total_used_commitment = processed["total_used_commitment"]

        # Calculate averages
        average_utilization = total_utilization / count if count > 0 else 0.0

        # Calculate SP discount rate using used commitment (excludes waste from underutilization)
        # This gives the inherent discount rate of the SP plan
        # Formula: (OnDemandCost - UsedCommitment) / OnDemandCost
        # vs old formula that included waste: NetSavings / OnDemandCost
        savings_percentage = (
            (
                (total_on_demand_equivalent - total_used_commitment)
                / total_on_demand_equivalent
                * 100.0
            )
            if total_on_demand_equivalent > 0
            else 0.0
        )

        # Convert totals to hourly averages using actual number of periods returned by AWS
        # (AWS may return fewer hours than requested due to data lag)
        actual_hours = len(utilizations)
        actual_sp_cost_hourly = (
            total_amortized_commitment / actual_hours if actual_hours > 0 else 0.0
        )
        on_demand_equivalent_hourly = (
            total_on_demand_equivalent / actual_hours if actual_hours > 0 else 0.0
        )
        net_savings_hourly = total_net_savings / actual_hours if actual_hours > 0 else 0.0

        logger.info(
            f"Metrics for {plan_type}: {actual_hours} hours of data (requested {lookback_days * 24}), "
            f"utilization={average_utilization:.2f}%, savings=${net_savings_hourly:.2f}/hr ({savings_percentage:.2f}%)"
        )

        return {
            "average_utilization": average_utilization,
            "utilization_by_day": utilization_by_day,
            "actual_sp_cost_hourly": actual_sp_cost_hourly,
            "on_demand_equivalent_hourly": on_demand_equivalent_hourly,
            "net_savings_hourly": net_savings_hourly,
            "savings_percentage": savings_percentage,
        }

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        error_message = e.response.get("Error", {}).get("Message", str(e))

        # Handle expected case: no data available for this plan type yet
        if error_code == "DataUnavailableException":
            logger.info(
                f"No metrics data available for {plan_type} - "
                f"no active plans of this type or insufficient data"
            )
            return {
                "average_utilization": 0.0,
                "utilization_by_day": [],
                "actual_sp_cost_hourly": 0.0,
                "on_demand_equivalent_hourly": 0.0,
                "net_savings_hourly": 0.0,
                "savings_percentage": 0.0,
            }

        logger.error(
            f"Failed to get metrics data for {plan_type} - Code: {error_code}, Message: {error_message}"
        )
        raise


def get_savings_plans_summary(
    savingsplans_client: SavingsPlansClient,
    ce_client: CostExplorerClient,
    enabled_plan_types: list[str],
    lookback_days: int,
    granularity: str = "HOURLY",
) -> dict[str, Any]:
    """
    Get comprehensive Savings Plans summary combining all metrics.

    Calls AWS APIs efficiently:
    - describe_savings_plans (once for all plans)
    - get_savings_plans_utilization (once per enabled plan type for metrics)

    Args:
        savingsplans_client: Boto3 Savings Plans client
        ce_client: Boto3 Cost Explorer client
        enabled_plan_types: List of enabled plan types (e.g., ["compute", "sagemaker"])
        lookback_days: Number of days to analyze for utilization/savings
        granularity: API granularity - "HOURLY" or "DAILY" (default: "HOURLY")

    Returns:
        dict: Complete summary (all cost values are hourly averages):
            {
                "plans_count": 5,
                "total_commitment": 2.5,  # hourly commitment
                "plans": [...],  # from get_active_savings_plans()
                "average_utilization": 85.5,
                "net_savings_hourly": 0.28,  # avg hourly savings
                "actual_savings": {...},  # with hourly values
                "breakdown_by_type": {
                    "Compute": {
                        "plans_count": 3,
                        "total_commitment": 2.0,
                        "average_utilization": 85.5,
                        "net_savings_hourly": 0.21,
                        "actual_sp_cost_hourly": 1.39,
                        "on_demand_equivalent_hourly": 1.67,
                        "savings_percentage": 16.67,
                    },
                    ...
                }
            }

    Raises:
        ClientError: If any AWS API calls fail
    """
    logger.info("Fetching comprehensive Savings Plans summary")

    plans = get_active_savings_plans(savingsplans_client)
    total_commitment = sum(plan["hourly_commitment"] for plan in plans)

    logger.info(f"Fetching metrics for enabled plan types: {enabled_plan_types}")

    breakdown_by_type = _initialize_breakdown_by_type(plans)

    total_net_savings, total_on_demand_equivalent, total_actual_sp_cost = _aggregate_type_metrics(
        ce_client, enabled_plan_types, breakdown_by_type, lookback_days, granularity
    )

    overall_utilization = _calculate_weighted_utilization(breakdown_by_type)

    overall_savings_percentage = (
        (total_net_savings / total_on_demand_equivalent * 100.0)
        if total_on_demand_equivalent > 0
        else 0.0
    )

    actual_savings = {
        "actual_sp_cost_hourly": total_actual_sp_cost,
        "on_demand_equivalent_hourly": total_on_demand_equivalent,
        "net_savings_hourly": total_net_savings,
        "savings_percentage": overall_savings_percentage,
        "breakdown_by_type": breakdown_by_type,
    }

    return {
        "plans_count": len(plans),
        "total_commitment": total_commitment,
        "plans": plans,
        "average_utilization": overall_utilization,
        "net_savings_hourly": total_net_savings,
        "actual_savings": actual_savings,
    }

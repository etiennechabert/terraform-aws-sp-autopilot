"""Coverage calculation for the Purchaser Lambda.

Fetches hourly coverage from Cost Explorer, discovers plans that are about to
expire, and treats expiring plans' coverage as 0 so the purchaser queues a
replacement.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from botocore.exceptions import ClientError

from shared import constants


if TYPE_CHECKING:
    from mypy_boto3_ce.client import CostExplorerClient
    from mypy_boto3_savingsplans.client import SavingsPlansClient


logger = logging.getLogger(__name__)


# Service keywords that map to each SP type in Cost Explorer output.
_COMPUTE_SERVICES = (
    "ec2",
    "elastic compute cloud",
    "lambda",
    "fargate",
    "elastic container service",
)
_DATABASE_SERVICES = ("rds", "relational database", "dynamodb", "database migration")


def get_current_coverage(clients: dict[str, Any], config: dict[str, Any]) -> dict[str, float]:
    """Current coverage % per SP type, zeroed out for any type with expiring plans."""
    logger.info("Calculating current coverage")

    today = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    start_time = today - timedelta(hours=config["lookback_hours"])

    try:
        raw_coverage = _get_ce_coverage(clients["ce"], start_time, today)
        expiring_plans = _get_expiring_plans(clients["savingsplans"], config)
        adjusted = _zero_out_expiring(raw_coverage, expiring_plans)
    except ClientError as e:
        logger.error(f"Failed to calculate coverage: {e!s}")
        raise

    logger.info(
        f"Coverage calculated: Compute={adjusted['compute']:.2f}%, "
        f"Database={adjusted['database']:.2f}%, SageMaker={adjusted['sagemaker']:.2f}%"
    )
    logger.info(f"Expiring plans excluded: {len(expiring_plans)} plans")
    return adjusted


def _get_ce_coverage(
    ce_client: CostExplorerClient, start_time: datetime, end_time: datetime
) -> dict[str, float]:
    """Raw coverage % per SP type from Cost Explorer, grouped by service."""
    logger.info(f"Getting coverage from Cost Explorer for {start_time.date()} to {end_time.date()}")

    response = ce_client.get_savings_plans_coverage(
        TimePeriod={
            "Start": start_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "End": end_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
        Granularity="HOURLY",
        GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}],
    )

    # AWS flattens per-service-per-hour entries; iterate back-to-front to
    # capture the latest point for each service.
    service_latest: dict[str, dict[str, float]] = {}
    for item in reversed(response.get("SavingsPlansCoverages", [])):
        service_name = item.get("Attributes", {}).get("SERVICE", "").lower()
        if service_name in service_latest:
            continue
        coverage = item.get("Coverage", {})
        service_latest[service_name] = {
            "covered": float(coverage.get("SpendCoveredBySavingsPlans", 0)),
            "on_demand": float(coverage.get("OnDemandCost", 0)),
        }

    sp_spend = {k: {"covered": 0.0, "on_demand": 0.0} for k in ("compute", "database", "sagemaker")}
    for service_name, spend in service_latest.items():
        sp_type = _classify_service(service_name)
        if sp_type is None:
            continue
        sp_spend[sp_type]["covered"] += spend["covered"]
        sp_spend[sp_type]["on_demand"] += spend["on_demand"]

    coverage = dict.fromkeys(sp_spend, 0.0)
    for sp_type, spend in sp_spend.items():
        total = spend["covered"] + spend["on_demand"]
        if total > 0:
            coverage[sp_type] = (spend["covered"] / total) * 100

    logger.info(
        f"Raw coverage from CE: Compute={coverage['compute']:.2f}%, "
        f"Database={coverage['database']:.2f}%, SageMaker={coverage['sagemaker']:.2f}%"
    )
    return coverage


def _classify_service(service_name: str) -> str | None:
    if any(s in service_name for s in _COMPUTE_SERVICES):
        return "compute"
    if "sagemaker" in service_name:
        return "sagemaker"
    if any(s in service_name for s in _DATABASE_SERVICES):
        return "database"
    return None


def _get_expiring_plans(
    savingsplans_client: SavingsPlansClient, config: dict[str, Any]
) -> list[dict[str, Any]]:
    """Active plans whose end date falls within renewal_window_days."""
    renewal_window_days = config["renewal_window_days"]
    logger.info(f"Getting Savings Plans expiring within {renewal_window_days} days")

    response = savingsplans_client.describe_savings_plans(states=["active"])
    threshold = datetime.now(UTC) + timedelta(days=renewal_window_days)

    expiring = []
    for plan in response.get("savingsPlans", []):
        end_time = datetime.fromisoformat(plan["end"].replace("Z", "+00:00"))
        if end_time <= threshold:
            expiring.append(
                {
                    "savingsPlanId": plan["savingsPlanId"],
                    "savingsPlanType": plan["savingsPlanType"],
                    "commitment": float(plan["commitment"]),
                    "end": plan["end"],
                }
            )

    logger.info(f"Found {len(expiring)} plans expiring within {renewal_window_days} days")
    return expiring


def _zero_out_expiring(
    raw_coverage: dict[str, float], expiring_plans: list[dict[str, Any]]
) -> dict[str, float]:
    """Treat coverage of any SP type with an expiring plan as 0 to force renewal."""
    adjusted = raw_coverage.copy()
    type_mapping = {
        constants.SP_FILTER_COMPUTE: ("compute", "Compute"),
        constants.SP_FILTER_DATABASE: ("database", "Database"),
        constants.SP_FILTER_SAGEMAKER: ("sagemaker", "SageMaker"),
    }
    for plan_type, (key, label) in type_mapping.items():
        if any(p["savingsPlanType"] == plan_type for p in expiring_plans):
            logger.info(f"{label} Savings Plans expiring - setting coverage to 0% to force renewal")
            adjusted[key] = 0.0
    return adjusted

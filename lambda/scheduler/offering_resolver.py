"""
Resolves a Savings Plan offering ID by querying the AWS DescribeSavingsPlansOfferings API.

The scheduler queues purchases with human-readable keys (sp_type="compute", term="ONE_YEAR"),
but CreateSavingsPlan requires an offering ID. This module bridges that gap.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from mypy_boto3_savingsplans.client import SavingsPlansClient

logger = logging.getLogger()

SP_TYPE_TO_PLAN_TYPE = {
    "compute": "Compute",
    "database": "Database",
    "sagemaker": "SageMaker",
}

SP_TYPE_TO_PRODUCT_TYPE = {
    "compute": "Fargate",
    "database": "RDS",
    "sagemaker": "SageMaker",
}

TERM_TO_DURATION = {
    "ONE_YEAR": 31536000,
    "THREE_YEAR": 94608000,
}

PAYMENT_OPTION_MAP = {
    "NO_UPFRONT": "No Upfront",
    "ALL_UPFRONT": "All Upfront",
    "PARTIAL_UPFRONT": "Partial Upfront",
}


def resolve_offering_id(
    savingsplans_client: SavingsPlansClient,
    sp_type_key: str,
    term: str,
    payment_option: str,
) -> str:
    """Resolve a Savings Plan offering ID from human-readable parameters.

    Args:
        savingsplans_client: Boto3 Savings Plans client
        sp_type_key: Lowercase SP type key ("compute", "database", "sagemaker")
        term: Term string ("ONE_YEAR" or "THREE_YEAR")
        payment_option: Payment option ("NO_UPFRONT", "ALL_UPFRONT", "PARTIAL_UPFRONT")

    Returns:
        The offering ID string

    Raises:
        ValueError: If no matching offering is found or inputs are invalid
    """
    plan_type = SP_TYPE_TO_PLAN_TYPE.get(sp_type_key)
    if not plan_type:
        raise ValueError(f"Unknown sp_type_key: {sp_type_key}")

    duration = TERM_TO_DURATION.get(term)
    if not duration:
        raise ValueError(f"Unknown term: {term}")

    api_payment_option = PAYMENT_OPTION_MAP.get(payment_option)
    if not api_payment_option:
        raise ValueError(f"Unknown payment_option: {payment_option}")

    product_type = SP_TYPE_TO_PRODUCT_TYPE[sp_type_key]

    logger.info(
        f"Resolving offering: planType={plan_type}, duration={duration}, "
        f"paymentOption={api_payment_option}, productType={product_type}"
    )

    response = savingsplans_client.describe_savings_plans_offerings(
        planTypes=[plan_type],
        durations=[duration],
        paymentOptions=[api_payment_option],
        productType=product_type,
        currencies=["USD"],
    )

    results = response.get("searchResults", [])
    if not results:
        raise ValueError(f"No offering found for {sp_type_key} / {term} / {payment_option}")

    offering_id = results[0]["offeringId"]
    logger.info(f"Resolved offering ID: {offering_id}")
    return offering_id

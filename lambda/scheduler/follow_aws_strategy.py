"""Follow AWS Strategy — purchases exactly what Cost Explorer recommends."""

import logging
from typing import Any

import recommendations as recommendations_module
from sp_types import SP_TYPES, get_term


logger = logging.getLogger()


def calculate_purchase_need_follow_aws(
    config: dict[str, Any], clients: dict[str, Any], spending_data: dict[str, Any] | None = None
) -> list[dict[str, Any]]:
    logger.info("Calculating purchase need using FOLLOW_AWS strategy")

    recommendations = recommendations_module.get_aws_recommendations(clients["ce"], config)

    purchase_plans = []

    for sp_type in SP_TYPES:
        if not config[sp_type["enabled_config"]]:
            continue

        key = sp_type["key"]
        recommendation = recommendations.get(key)
        if not recommendation:
            logger.info(
                f"{sp_type['name']} SP has coverage gap but no AWS recommendation available"
            )
            continue

        hourly_commitment_float = float(recommendation["HourlyCommitmentToPurchase"])
        if hourly_commitment_float <= 0:
            logger.info(f"{sp_type['name']} SP recommendation has zero commitment - skipping")
            continue

        details = recommendation["Details"]
        estimated_savings_pct = float(details.get("EstimatedSavingsPercentage", "0"))

        purchase_plan = {
            "sp_type": key,
            "hourly_commitment": hourly_commitment_float,
            "payment_option": config[sp_type["payment_option_config"]],
            "recommendation_id": recommendation["RecommendationId"],
            "strategy": "follow_aws",
            "estimated_savings_percentage": estimated_savings_pct,
            "term": get_term(key, config),
        }

        purchase_plans.append(purchase_plan)
        logger.info(
            "%s SP purchase planned: $%s/hour (100%% of AWS recommendation, recommendation_id: %s)",
            sp_type["name"],
            hourly_commitment_float,
            purchase_plan["recommendation_id"],
        )

    logger.info(f"Follow AWS strategy purchase need calculated: {len(purchase_plans)} plans")
    return purchase_plans

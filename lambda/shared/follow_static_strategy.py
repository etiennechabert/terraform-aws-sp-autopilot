"""Static Strategy — user sets a target commitment in $/h, splits divide the gap."""

import logging
from typing import Any

from shared.constants import AWS_TYPE_TO_KEY
from shared.savings_plans_metrics import get_active_savings_plans
from shared.sp_types import SP_TYPES, get_term
from shared.split_strategies import calculate_split


logger = logging.getLogger()


def _get_current_commitments(savingsplans_client: Any) -> dict[str, float]:
    """Get total hourly commitment per SP type from active plans."""
    plans = get_active_savings_plans(savingsplans_client)
    commitments: dict[str, float] = {}
    for plan in plans:
        key = AWS_TYPE_TO_KEY.get(plan["plan_type"])
        if key:
            commitments[key] = commitments.get(key, 0.0) + plan["hourly_commitment"]
    return commitments


def calculate_purchase_need_static(
    config: dict[str, Any],
    clients: dict[str, Any],
) -> list[dict[str, Any]]:
    target_commitment = config["static_commitment"]
    split_type = config["split_strategy_type"]

    logger.info(
        f"Calculating purchase need using STATIC strategy "
        f"(target: ${target_commitment:.5f}/h, split: {split_type})"
    )

    current_commitments = _get_current_commitments(clients["savingsplans"])

    purchase_plans = []
    for sp_type in SP_TYPES:
        if not config[sp_type["enabled_config"]]:
            continue

        key = sp_type["key"]
        current_commitment = current_commitments.get(key, 0.0)
        commitment_gap = target_commitment - current_commitment

        logger.info(
            f"{sp_type['name']} SP - Current: ${current_commitment:.5f}/h, "
            f"Target: ${target_commitment:.5f}/h, Gap: ${commitment_gap:.5f}/h"
        )

        if commitment_gap <= 0:
            logger.info(f"{sp_type['name']} SP commitment already meets or exceeds target")
            continue

        purchase_commitment = round(
            calculate_split(current_commitment, target_commitment, config), 5
        )

        min_commitment = config["min_commitment_per_plan"]
        if purchase_commitment < min_commitment:
            logger.info(
                f"{sp_type['name']} SP commitment ${purchase_commitment:.5f}/h "
                f"is below minimum ${min_commitment:.5f}/h - skipping"
            )
            continue

        logger.info(
            f"{sp_type['name']} SP purchase planned: ${purchase_commitment:.5f}/h "
            f"(static target: ${target_commitment:.5f}/h)"
        )

        purchase_plans.append(
            {
                "strategy": f"static+{split_type}",
                "sp_type": key,
                "hourly_commitment": purchase_commitment,
                "payment_option": config[sp_type["payment_option_config"]],
                "term": get_term(key, config),
                "details": {
                    "commitment": {
                        "current": current_commitment,
                        "target": target_commitment,
                        "gap": commitment_gap,
                    },
                },
            }
        )

    logger.info(f"Static strategy purchase need calculated: {len(purchase_plans)} plans")
    return purchase_plans

"""Static Strategy — user sets a target commitment in $/h, splits divide the gap.

WARNING: This strategy has no automatic safety against over-commitment.
The target is a fixed $/h value that does not adapt to changing usage patterns.
Consider the 'dynamic' strategy for production workloads — it derives targets
from actual spend and adjusts automatically as usage changes.
"""

import logging
from typing import Any

from sp_types import SP_TYPES, get_term
from split_strategies import calculate_split

from shared.constants import AWS_TYPE_TO_KEY
from shared.savings_plans_metrics import get_active_savings_plans
from shared.spending_analyzer import SpendingAnalyzer


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


def check_over_commitment(
    config: dict[str, Any],
    clients: dict[str, Any],
    target_commitment: float,
) -> list[dict[str, Any]]:
    """Check if the static target exceeds actual usage. Returns a list of warnings."""
    warnings: list[dict[str, Any]] = []
    try:
        analyzer = SpendingAnalyzer(clients["savingsplans"], clients["ce"])
        spending_data = analyzer.analyze_current_spending(config)
        spending_data.pop("_unknown_services", None)
    except Exception:
        logger.warning(
            "Could not fetch spending data to validate static target — "
            "proceeding without over-commitment check"
        )
        return warnings

    for sp_type in SP_TYPES:
        if not config[sp_type["enabled_config"]]:
            continue
        key = sp_type["key"]
        data = spending_data.get(key)
        if not data:
            continue

        avg_hourly = data["summary"].get("avg_hourly_total", 0.0)
        if avg_hourly <= 0:
            continue

        if target_commitment > avg_hourly:
            warnings.append(
                {
                    "sp_type": key,
                    "level": "critical",
                    "target": target_commitment,
                    "avg_hourly": avg_hourly,
                    "ratio": target_commitment / avg_hourly,
                }
            )
            logger.warning(
                f"OVER-COMMITMENT RISK: {sp_type['name']} SP static target "
                f"(${target_commitment:.4f}/h) exceeds average spend "
                f"(${avg_hourly:.4f}/h) by {target_commitment / avg_hourly:.1f}x"
            )
        elif target_commitment > avg_hourly * 0.9:
            warnings.append(
                {
                    "sp_type": key,
                    "level": "warning",
                    "target": target_commitment,
                    "avg_hourly": avg_hourly,
                    "ratio": target_commitment / avg_hourly,
                }
            )
            logger.warning(
                f"{sp_type['name']} SP static target (${target_commitment:.4f}/h) "
                f"is near average spend (${avg_hourly:.4f}/h)"
            )

    return warnings


def calculate_purchase_need_static(
    config: dict[str, Any],
    clients: dict[str, Any],
) -> list[dict[str, Any]]:
    target_commitment = config["static_commitment"]
    split_type = config["split_strategy_type"]

    logger.warning(
        "Static strategy selected — target commitment is a fixed $/h value "
        "with no automatic safety against over-commitment. "
        "The 'dynamic' strategy is recommended for production workloads "
        "as it adapts to actual usage patterns."
    )

    logger.info(
        f"Calculating purchase need using STATIC strategy "
        f"(target: ${target_commitment:.5f}/h, split: {split_type})"
    )

    over_commitment_warnings = check_over_commitment(config, clients, target_commitment)

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

    # Attach over-commitment warnings to all purchase plans for email notifications
    if over_commitment_warnings:
        for plan in purchase_plans:
            plan["static_warnings"] = over_commitment_warnings

    logger.info(f"Static strategy purchase need calculated: {len(purchase_plans)} plans")
    return purchase_plans

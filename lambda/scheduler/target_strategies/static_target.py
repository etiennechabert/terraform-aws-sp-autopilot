import logging
from typing import Any

from sp_types import SP_TYPES, get_term
from split_strategies import calculate_split

from shared import sp_calculations


logger = logging.getLogger()


def calculate_purchase_need_static(
    config: dict[str, Any],
    clients: dict[str, Any],
    spending_data: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """
    Static target: user sets a total commitment target in $/h.

    Splits operate directly in $/h (current vs target commitment),
    no coverage percentage conversion needed.
    """
    if spending_data is None:
        from shared.spending_analyzer import SpendingAnalyzer

        analyzer = SpendingAnalyzer(clients["savingsplans"], clients["ce"])
        spending_data = analyzer.analyze_current_spending(config)
        spending_data.pop("_unknown_services", None)

    target_commitment = config["static_commitment"]
    split_type = config["split_strategy_type"]

    purchase_plans = []
    for sp_type in SP_TYPES:
        if not config[sp_type["enabled_config"]]:
            continue

        key = sp_type["key"]
        data = spending_data.get(key)
        if not data:
            logger.info(f"{sp_type['name']} SP - No spending data available")
            continue

        summary = data["summary"]
        avg_hourly_covered = summary["avg_hourly_covered"]
        avg_hourly_total = summary["avg_hourly_total"]

        savings_pct = config.get(f"{key}_savings_percentage", config["savings_percentage"])
        current_commitment = sp_calculations.commitment_from_coverage(
            avg_hourly_covered, savings_pct
        )

        commitment_gap = target_commitment - current_commitment
        logger.info(
            f"{sp_type['name']} SP - Current commitment: ${current_commitment:.5f}/h, "
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
                    "spending": {
                        "total": avg_hourly_total,
                        "covered": avg_hourly_covered,
                        "uncovered": avg_hourly_total - avg_hourly_covered,
                    },
                },
            }
        )

    logger.info(f"Static purchase need calculated: {len(purchase_plans)} plans")
    return purchase_plans

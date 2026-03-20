"""
Demo Mode - Randomizes financial data for safe public sharing.

Applies a random multiplier to all dollar amounts while preserving
percentages, ratios, and chart shapes. Plan IDs are anonymized.

Enabled via DEMO_MODE=true environment variable (local dev only).
"""

from __future__ import annotations

import hashlib
import logging
import math
import os
import random
from copy import deepcopy
from datetime import datetime
from typing import Any


logger = logging.getLogger(__name__)


def is_demo_mode() -> bool:
    return os.getenv("DEMO_MODE", "false").lower() == "true"


def randomize_report_data(
    coverage_data: dict[str, Any],
    daily_coverage_data: dict[str, Any],
    savings_data: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """
    Apply random scaling to all financial data for demo/screenshot purposes.

    Uses a single log-uniform random multiplier (0.3x - 3x) so all dollar
    amounts are scaled consistently. This preserves:
    - Coverage percentages (covered/total ratio unchanged)
    - Utilization percentages
    - Savings percentages
    - Chart shapes and trends

    Returns deep copies - originals are not modified.
    """
    factor = _random_factor()
    logger.info("Demo mode active - applying random scaling factor (data is not real)")

    coverage_out = _scale_coverage_data(deepcopy(coverage_data), factor, is_daily=False)
    daily_out = _scale_coverage_data(deepcopy(daily_coverage_data), factor, is_daily=True)

    coverage_pcts = _apply_fake_coverage(coverage_out)
    _apply_fake_coverage(daily_out, coverage_pcts=coverage_pcts)

    savings_out = _scale_savings_data(deepcopy(savings_data), factor)

    return coverage_out, daily_out, savings_out


def _random_factor() -> float:
    """Generate a log-uniform random factor between 0.3 and 3.0, excluding 0.8-1.2 deadzone."""
    while True:
        factor = math.exp(random.uniform(math.log(0.3), math.log(3.0)))
        if factor < 0.5 or factor > 2.0:
            return factor


def _scale(value: float, factor: float) -> float:
    return round(value * factor, 6)


def _time_multiplier(timestamp_str: str, is_daily: bool) -> float:
    """Generate a deterministic random multiplier (1.5-2.5) based on time.

    For daily data: varies by day of the week (0=Monday .. 6=Sunday).
    For hourly data: varies by hour of the day (0-23).
    """
    dt = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
    seed = dt.isoweekday() if is_daily else dt.hour
    rng = random.Random(seed)
    return rng.uniform(1.5, 2.5)


def _scale_coverage_data(data: dict[str, Any], factor: float, *, is_daily: bool) -> dict[str, Any]:
    """Scale dollar amounts in coverage data (hourly or daily)."""
    for sp_type in ("compute", "database", "sagemaker"):
        if sp_type not in data:
            continue

        type_data = data[sp_type]

        # Scale timeseries with time-based multiplier
        for point in type_data.get("timeseries", []):
            tm = _time_multiplier(point["timestamp"], is_daily)
            point["covered"] = _scale(point["covered"], factor * tm)
            point["total"] = _scale(point["total"], factor * tm)

        # Scale summary dollar amounts (not percentages)
        summary = type_data.get("summary", {})
        for key in (
            "avg_hourly_covered",
            "avg_hourly_total",
            "min_hourly_total",
            "max_hourly_total",
            "est_monthly_covered",
            "est_monthly_total",
        ):
            if key in summary:
                summary[key] = _scale(summary[key], factor)

    return data


def _apply_fake_coverage(
    data: dict[str, Any],
    coverage_pcts: dict[str, float] | None = None,
) -> dict[str, float]:
    """Set SP coverage as a flat line at a random 25-75% of min-hourly total.

    If coverage_pcts is provided, reuse those percentages (so hourly and daily
    data share the same coverage ratio per SP type). Returns the percentages used.
    """
    generated_pcts: dict[str, float] = {}
    for sp_type in ("compute", "database", "sagemaker"):
        if sp_type not in data:
            continue

        type_data = data[sp_type]
        timeseries = type_data.get("timeseries", [])
        totals = [p["total"] for p in timeseries if p["total"] > 0]
        if not totals:
            continue

        min_total = min(totals)

        if coverage_pcts and sp_type in coverage_pcts:
            pct = coverage_pcts[sp_type]
        else:
            pct = random.uniform(0.25, 0.75)
        generated_pcts[sp_type] = pct

        flat_covered = round(min_total * pct, 6)
        for point in timeseries:
            point["covered"] = flat_covered

        summary = type_data.get("summary", {})
        if "avg_hourly_covered" in summary:
            summary["avg_hourly_covered"] = flat_covered
        if "est_monthly_covered" in summary:
            summary["est_monthly_covered"] = round(flat_covered * 720, 6)

    return generated_pcts


def _scale_savings_data(data: dict[str, Any], factor: float) -> dict[str, Any]:
    """Scale dollar amounts in savings data and anonymize plan IDs."""

    # Scale top-level dollar amounts
    data["total_commitment"] = _scale(data.get("total_commitment", 0), factor)
    data["net_savings_hourly"] = _scale(data.get("net_savings_hourly", 0), factor)

    # Scale actual_savings
    actual = data.get("actual_savings", {})
    for key in (
        "actual_sp_cost_hourly",
        "on_demand_equivalent_hourly",
        "net_savings_hourly",
    ):
        if key in actual:
            actual[key] = _scale(actual[key], factor)

    # Scale breakdown_by_type
    for type_info in actual.get("breakdown_by_type", {}).values():
        for key in (
            "total_commitment",
            "net_savings_hourly",
            "on_demand_equivalent_hourly",
            "actual_sp_cost_hourly",
        ):
            if key in type_info:
                type_info[key] = _scale(type_info[key], factor)

    # Scale and anonymize individual plans
    for plan in data.get("plans", []):
        plan["hourly_commitment"] = _scale(plan.get("hourly_commitment", 0), factor)
        plan["plan_id"] = _anonymize_id(plan.get("plan_id", ""))

    return data


def _anonymize_id(plan_id: str) -> str:
    """Replace plan ID with a deterministic but unrecognizable hash prefix."""
    h = hashlib.sha256(plan_id.encode()).hexdigest()[:12]
    return f"demo-{h}"

"""
Demo Mode - Randomizes financial data for safe public sharing.

Applies a random multiplier to all dollar amounts while preserving
percentages and ratios. Additionally applies per-hour-of-day (24 values)
and per-day-of-week (7 values) series multipliers to reshape usage patterns
so the original firm's pattern cannot be recognized. Plan IDs are anonymized.

Enabled via DEMO_MODE=true environment variable (local dev only).
"""

from __future__ import annotations

import hashlib
import logging
import math
import os
import random
from copy import deepcopy
from datetime import UTC, datetime, timedelta
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

    Uses a base log-uniform multiplier (0.3x - 3x) plus per-hour-of-day (24)
    and per-day-of-week (7) series multipliers to reshape the usage pattern.
    This preserves coverage percentages (covered/total ratio) but disguises
    the firm's actual usage pattern.

    Returns deep copies - originals are not modified.
    """
    factor = _random_factor()
    hourly_series = _generate_hourly_multipliers()
    daily_series = _generate_daily_multipliers()
    coverage_pcts = {sp: random.uniform(0.5, 0.85) for sp in ("compute", "database", "sagemaker")}
    logger.info("Demo mode active - applying random scaling factor (data is not real)")

    coverage_out = _scale_coverage_data(
        deepcopy(coverage_data), factor, hourly_series, daily_series, coverage_pcts
    )
    daily_out = _scale_coverage_data(
        deepcopy(daily_coverage_data), factor, hourly_series, daily_series, coverage_pcts
    )
    savings_out = _scale_savings_data(deepcopy(savings_data), factor)

    return coverage_out, daily_out, savings_out


def _random_factor() -> float:
    """Generate a log-uniform random factor between 0.3 and 3.0, excluding 0.8-1.2 deadzone."""
    while True:
        factor = math.exp(random.uniform(math.log(0.3), math.log(3.0)))
        if factor < 0.5 or factor > 2.0:
            return factor


def _generate_hourly_multipliers() -> list[float]:
    """Generate 24 hourly multipliers mimicking a business-hours pattern.

    Business hours (8-18): random in [1.0, 2.0]
    Off hours: random in [0.25, 0.75]
    Adjacent values stay close for smooth transitions.
    """
    multipliers = []
    for hour in range(24):
        base = random.uniform(1.0, 2.0) if 8 <= hour < 18 else random.uniform(0.25, 0.75)
        multipliers.append(base)

    # Smooth transitions at boundaries (hours 7-8 and 17-18)
    multipliers[7] = random.uniform(0.6, 1.0)
    multipliers[18] = random.uniform(0.6, 1.0)

    return [round(v, 6) for v in multipliers]


def _generate_daily_multipliers() -> list[float]:
    """Generate 7 daily multipliers (Mon=0 .. Sun=6) mimicking a business-week pattern.

    Business days (Mon-Fri): random in [1.0, 2.0]
    Weekend (Sat-Sun): random in [0.25, 0.75]
    """
    multipliers = []
    for day in range(7):
        if day < 5:
            multipliers.append(round(random.uniform(1.0, 2.0), 6))
        else:
            multipliers.append(round(random.uniform(0.25, 0.75), 6))
    return multipliers


def _point_multiplier(
    timestamp_str: str,
    hourly_series: list[float],
    daily_series: list[float],
) -> float:
    """Get the combined hour-of-day * day-of-week multiplier for a timestamp."""
    try:
        dt = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return 1.0
    return hourly_series[dt.hour] * daily_series[dt.weekday()]


def _scale(value: float, factor: float) -> float:
    return round(value * factor, 6)


def _scale_coverage_data(
    data: dict[str, Any],
    factor: float,
    hourly_series: list[float],
    daily_series: list[float],
    coverage_pcts: dict[str, float],
) -> dict[str, Any]:
    """Scale dollar amounts in coverage data with per-point pattern reshaping."""
    for sp_type in ("compute", "database", "sagemaker"):
        if sp_type not in data:
            continue

        type_data = data[sp_type]
        timeseries = type_data.get("timeseries", [])

        # First pass: reshape total spend with hourly/daily multipliers
        for point in timeseries:
            pm = _point_multiplier(point.get("timestamp", ""), hourly_series, daily_series)
            point["total"] = _scale(point["total"], factor * pm)

        # Set covered as a flat commitment = shared coverage % of min total
        if timeseries:
            min_total = min(p["total"] for p in timeseries)
            flat_covered = round(min_total * coverage_pcts[sp_type], 6)
            for point in timeseries:
                point["covered"] = flat_covered

        # Recalculate summary from modified timeseries
        summary = type_data.get("summary", {})
        if timeseries and summary:
            totals = [p["total"] for p in timeseries]
            covereds = [p["covered"] for p in timeseries]
            n = len(timeseries)
            avg_total = sum(totals) / n
            avg_covered = sum(covereds) / n
            summary["avg_hourly_total"] = round(avg_total, 6)
            summary["avg_hourly_covered"] = round(avg_covered, 6)
            summary["min_hourly_total"] = round(min(totals), 6)
            summary["max_hourly_total"] = round(max(totals), 6)
            summary["est_monthly_total"] = round(avg_total * 720, 6)
            summary["est_monthly_covered"] = round(avg_covered * 720, 6)

    return data


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

    # Scale, anonymize, and randomize dates of individual plans
    for plan in data.get("plans", []):
        plan["hourly_commitment"] = _scale(plan.get("hourly_commitment", 0), factor)
        plan["plan_id"] = _anonymize_id(plan.get("plan_id", ""))
        _randomize_plan_dates(plan)

    return data


def _randomize_plan_dates(plan: dict[str, Any]) -> None:
    """Shift plan start/end dates by a random offset to disguise timing."""
    offset_days = random.randint(-180, 180)
    for key in ("start_date", "end_date"):
        date_str = plan.get(key, "")
        if not date_str or date_str == "Unknown":
            continue
        try:
            if "T" in date_str:
                dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                dt += timedelta(days=offset_days)
                plan[key] = dt.strftime("%Y-%m-%dT%H:%M:%S") + "Z"
            else:
                dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=UTC)
                dt += timedelta(days=offset_days)
                plan[key] = dt.strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            continue


def _anonymize_id(plan_id: str) -> str:
    """Replace plan ID with a deterministic but unrecognizable hash prefix."""
    h = hashlib.sha256(plan_id.encode()).hexdigest()[:12]
    return f"demo-{h}"

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

    Uses a base log-uniform multiplier (0.3x - 3x) plus per-hour-of-day (24)
    and per-day-of-week (7) series multipliers to reshape the usage pattern.
    This preserves coverage percentages (covered/total ratio) but disguises
    the firm's actual usage pattern.

    Returns deep copies - originals are not modified.
    """
    factor = _random_factor()
    hourly_series = _generate_series_multipliers(24)
    daily_series = _generate_series_multipliers(7)
    logger.info("Demo mode active - applying random scaling factor (data is not real)")

    coverage_out = _scale_coverage_data(
        deepcopy(coverage_data), factor, hourly_series, daily_series
    )
    daily_out = _scale_coverage_data(
        deepcopy(daily_coverage_data), factor, hourly_series, daily_series
    )
    savings_out = _scale_savings_data(deepcopy(savings_data), factor)

    return coverage_out, daily_out, savings_out


def _random_factor() -> float:
    """Generate a log-uniform random factor between 0.3 and 3.0, excluding 0.8-1.2 deadzone."""
    while True:
        factor = math.exp(random.uniform(math.log(0.3), math.log(3.0)))
        if factor < 0.5 or factor > 2.0:
            return factor


def _generate_series_multipliers(n: int) -> list[float]:
    """Generate n random multipliers (0.3-2.5) that average to ~1.0.

    Uses smooth random walk with large steps to create a convincing
    but completely different usage pattern from the original.
    """
    raw = [1.0]
    for _ in range(n - 1):
        raw.append(raw[-1] + random.gauss(0, 0.4))

    # Normalize to average 1.0 and clamp to [0.3, 2.5]
    avg = sum(raw) / len(raw)
    normalized = [r / avg for r in raw]
    clamped = [max(0.3, min(2.5, v)) for v in normalized]

    # Re-normalize after clamping
    avg2 = sum(clamped) / len(clamped)
    return [round(v / avg2, 6) for v in clamped]


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
) -> dict[str, Any]:
    """Scale dollar amounts in coverage data with per-point pattern reshaping."""
    for sp_type in ("compute", "database", "sagemaker"):
        if sp_type not in data:
            continue

        type_data = data[sp_type]
        timeseries = type_data.get("timeseries", [])

        # Scale timeseries: SP coverage gets uniform factor only (flat commitment),
        # on-demand portion gets reshaped by hourly/daily multipliers
        for point in timeseries:
            pm = _point_multiplier(point.get("timestamp", ""), hourly_series, daily_series)
            covered = point["covered"]
            on_demand = point["total"] - covered
            point["covered"] = _scale(covered, factor)
            point["total"] = _scale(covered, factor) + _scale(on_demand, factor * pm)

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

    # Scale and anonymize individual plans
    for plan in data.get("plans", []):
        plan["hourly_commitment"] = _scale(plan.get("hourly_commitment", 0), factor)
        plan["plan_id"] = _anonymize_id(plan.get("plan_id", ""))

    return data


def _anonymize_id(plan_id: str) -> str:
    """Replace plan ID with a deterministic but unrecognizable hash prefix."""
    h = hashlib.sha256(plan_id.encode()).hexdigest()[:12]
    return f"demo-{h}"

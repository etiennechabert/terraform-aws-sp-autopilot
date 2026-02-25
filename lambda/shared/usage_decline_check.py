"""
Spike Guard module.

Detects usage spikes by comparing short-term vs long-term average hourly spend.
Prevents over-committing to Savings Plans based on temporarily elevated usage
(e.g. Black Friday, seasonal peaks, one-off migrations).

Two checks:
- Scheduling: blocks if recent (14d) avg is abnormally high vs long-term (90d) avg
- Purchasing: blocks if usage dropped since scheduling (confirming the spike was temporary)
"""

from __future__ import annotations

import logging
from typing import Any

from shared.spending_analyzer import SpendingAnalyzer


logger = logging.getLogger(__name__)


def check_usage_spike(
    long_term_avgs: dict[str, float],
    short_term_avgs: dict[str, float],
    threshold_percent: float,
) -> dict[str, dict[str, Any]]:
    """
    Detect if short-term usage is abnormally high compared to long-term baseline.

    Args:
        long_term_avgs: {sp_type: avg_hourly_total} for the longer lookback (baseline)
        short_term_avgs: {sp_type: avg_hourly_total} for the shorter lookback (recent)
        threshold_percent: Spike percentage threshold (e.g. 20 means flag if 20% above baseline)

    Returns:
        {sp_type: {flagged: bool, long_term_avg, short_term_avg, change_percent}}
    """
    results = {}
    for sp_type, long_avg in long_term_avgs.items():
        short_avg = short_term_avgs.get(sp_type, 0.0)
        spike_pct = (short_avg - long_avg) / long_avg * 100 if long_avg > 0 else 0.0

        flagged = spike_pct >= threshold_percent
        results[sp_type] = {
            "flagged": flagged,
            "long_term_avg": long_avg,
            "short_term_avg": short_avg,
            "change_percent": round(spike_pct, 2),
        }

        if flagged:
            logger.warning(
                f"Usage spike detected for {sp_type}: "
                f"${long_avg:.4f}/h (baseline) -> ${short_avg:.4f}/h (recent) "
                f"(+{spike_pct:.1f}%, threshold: {threshold_percent}%)"
            )

    return results


def check_usage_drop(
    baseline_avgs: dict[str, float],
    current_avgs: dict[str, float],
    threshold_percent: float,
) -> dict[str, dict[str, Any]]:
    """
    Detect if current usage dropped significantly from baseline (scheduling-time avg).

    Catches the case where a spike subsided between scheduling and purchasing,
    confirming the scheduled SP amounts would be oversized.

    Args:
        baseline_avgs: {sp_type: avg_hourly_total} from scheduling time
        current_avgs: {sp_type: avg_hourly_total} current
        threshold_percent: Drop percentage threshold

    Returns:
        {sp_type: {flagged: bool, baseline_avg, current_avg, change_percent}}
    """
    results = {}
    for sp_type, baseline in baseline_avgs.items():
        current = current_avgs.get(sp_type, 0.0)
        drop_pct = (baseline - current) / baseline * 100 if baseline > 0 else 0.0

        flagged = drop_pct >= threshold_percent
        results[sp_type] = {
            "flagged": flagged,
            "baseline_avg": baseline,
            "current_avg": current,
            "change_percent": round(drop_pct, 2),
        }

        if flagged:
            logger.warning(
                f"Usage drop since scheduling for {sp_type}: "
                f"${baseline:.4f}/h (scheduling) -> ${current:.4f}/h (current) "
                f"(-{drop_pct:.1f}%, threshold: {threshold_percent}%)"
            )

    return results


def fetch_averages(
    analyzer: SpendingAnalyzer, lookback_days: int, config: dict[str, Any]
) -> dict[str, float]:
    """
    Fetch average hourly totals per SP type using SpendingAnalyzer.

    Always uses DAILY granularity since lookback may exceed 14 days (HOURLY limit).
    """
    guard_config = {
        **config,
        "granularity": "DAILY",
        "lookback_days": lookback_days,
    }
    spending_data = analyzer.analyze_current_spending(guard_config)
    spending_data.pop("_unknown_services", None)

    return {sp_type: data["summary"]["avg_hourly_total"] for sp_type, data in spending_data.items()}


def run_scheduling_spike_guard(
    analyzer: SpendingAnalyzer, config: dict[str, Any]
) -> tuple[dict[str, float], dict[str, dict[str, Any]]]:
    """
    Run spike guard at scheduling time: detect if recent usage is spiking vs baseline.

    Returns:
        (short_term_averages, guard_results) — short_term_averages is embedded in SQS messages
    """
    long_days = config["spike_guard_long_lookback_days"]
    short_days = config["spike_guard_short_lookback_days"]
    threshold = config["spike_guard_threshold_percent"]

    logger.info(
        f"Running scheduling spike guard: {short_days}d avg vs {long_days}d baseline, "
        f"threshold={threshold}%"
    )

    long_term_avgs = fetch_averages(analyzer, long_days, config)
    short_term_avgs = fetch_averages(analyzer, short_days, config)

    guard_results = check_usage_spike(long_term_avgs, short_term_avgs, threshold)

    flagged_types = [t for t, r in guard_results.items() if r["flagged"]]
    if flagged_types:
        logger.warning(f"Usage spike detected for SP types: {flagged_types}")
    else:
        logger.info("No usage spike detected")

    return short_term_avgs, guard_results


def run_purchasing_spike_guard(
    analyzer: SpendingAnalyzer,
    scheduling_avgs: dict[str, float],
    config: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """
    Run spike guard at purchase time: detect if usage dropped since scheduling.

    If the scheduler ran during a spike and usage has since normalized, the scheduled
    SP amounts would be oversized — block the purchase.

    Returns:
        {sp_type: {flagged: bool, baseline_avg, current_avg, change_percent}}
    """
    short_days = config["spike_guard_short_lookback_days"]
    threshold = config["spike_guard_threshold_percent"]

    logger.info(
        f"Running purchasing spike guard: scheduling avg vs current {short_days}d avg, "
        f"threshold={threshold}%"
    )

    current_avgs = fetch_averages(analyzer, short_days, config)
    guard_results = check_usage_drop(scheduling_avgs, current_avgs, threshold)

    flagged_types = [t for t, r in guard_results.items() if r["flagged"]]
    if flagged_types:
        logger.warning(f"Usage dropped since scheduling for SP types: {flagged_types}")
    else:
        logger.info("No usage drop since scheduling")

    return guard_results

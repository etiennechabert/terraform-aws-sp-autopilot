"""
Coverage calculation module for Scheduler Lambda.

This module provides backward-compatible wrapper functions for the shared
SpendingAnalyzer class. New code should use SpendingAnalyzer directly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from shared.spending_analyzer import (
    SpendingAnalyzer,
    group_coverage_by_sp_type,
)


if TYPE_CHECKING:
    from mypy_boto3_ce.client import CostExplorerClient
    from mypy_boto3_savingsplans.client import SavingsPlansClient


def calculate_current_coverage(
    savingsplans_client: SavingsPlansClient,
    ce_client: CostExplorerClient,
    config: dict[str, Any],
) -> dict[str, float]:
    """
    Calculate current Savings Plans coverage (backward compatible).

    This is a wrapper around the shared SpendingAnalyzer class for backward
    compatibility. New code should use SpendingAnalyzer directly.

    Args:
        savingsplans_client: Boto3 Savings Plans client
        ce_client: Boto3 Cost Explorer client
        config: Configuration dictionary

    Returns:
        dict: Coverage percentages by SP type:
              {"compute": 82.97, "database": 0.0, "sagemaker": 0.0}
    """
    analyzer = SpendingAnalyzer(savingsplans_client, ce_client)
    spending_data = analyzer.analyze_current_spending(config)
    return {
        sp_type: data["summary"]["avg_coverage"]
        for sp_type, data in spending_data.items()
    }

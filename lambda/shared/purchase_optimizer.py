"""
Savings Plans Purchase Optimizer.

Shared module for calculating optimal Savings Plans purchase commitments based on
spending patterns, discount rates, and risk tolerance.

Used by:
- Scheduler: Make optimal purchase decisions
- Reporter: Display recommendations and help users understand the economics
"""

from __future__ import annotations

import logging
from typing import Any


logger = logging.getLogger(__name__)


class PurchaseOptimizer:
    """
    Calculates optimal Savings Plans purchase commitments.

    The optimizer analyzes spending patterns and discount rates to determine the
    ideal hourly commitment that maximizes savings while minimizing waste from
    unused commitments.

    Key concept: The break-even percentile is inversely related to the discount rate.
    - High discount (60%) = Low waste cost → Can commit at higher percentiles (P40)
    - Low discount (20%) = High waste cost → Must commit at lower percentiles (P80)

    The aggressiveness factor allows fine-tuning the recommendation (e.g., 95% = slightly
    conservative, 100% = full recommended amount).
    """

    def calculate_optimal_commitment(
        self,
        spending_data: dict[str, dict[str, Any]],
        discount_rate: float,
        aggressiveness: float = 1.0,
    ) -> dict[str, dict[str, Any]]:
        """
        Calculate optimal hourly commitment for each SP type.

        Args:
            spending_data: Output from SpendingAnalyzer.analyze_current_spending()
                {
                    "compute": {
                        "timeseries": [{"timestamp": ..., "total": 15.2, ...}, ...],
                        "summary": {...}
                    },
                    ...
                }
            discount_rate: Savings rate as decimal (e.g., 0.60 for 60% savings)
            aggressiveness: Multiplier for recommendation (0.0-1.0)
                - 1.0 = Full recommended amount (default)
                - 0.95 = 95% of recommended (slightly conservative)
                - 0.90 = 90% of recommended (conservative)

        Returns:
            dict: Optimal commitment analysis by SP type:
                {
                    "compute": {
                        "recommended_hourly_commitment": 12.5,
                        "analysis": {
                            "percentiles": {
                                "p10": 8.5,
                                "p20": 10.2,
                                "p30": 11.8,
                                "p40": 13.15,
                                "p50": 15.3,
                                "p60": 17.2,
                                "p70": 19.1,
                                "p80": 22.1,
                                "p90": 28.4,
                                "p99": 35.2
                            },
                            "target_percentile": 40,
                            "target_percentile_value": 13.15,
                            "aggressiveness_factor": 0.95,
                            "adjusted_commitment": 12.5,
                            "discount_rate": 0.60,
                            "breakeven_hours_pct": 60.0
                        }
                    },
                    "database": {...},
                    "sagemaker": {...}
                }

        Raises:
            ValueError: If discount_rate or aggressiveness are out of valid range
        """
        # Validate inputs
        if not 0.0 <= discount_rate <= 1.0:
            raise ValueError(f"discount_rate must be between 0.0 and 1.0, got {discount_rate}")
        if not 0.0 <= aggressiveness <= 1.0:
            raise ValueError(f"aggressiveness must be between 0.0 and 1.0, got {aggressiveness}")

        result = {}

        for sp_type in ["compute", "database", "sagemaker"]:
            sp_data = spending_data.get(sp_type, {})
            timeseries = sp_data.get("timeseries", [])

            if not timeseries:
                # No data for this SP type
                result[sp_type] = {
                    "recommended_hourly_commitment": 0.0,
                    "analysis": {
                        "percentiles": {},
                        "target_percentile": None,
                        "target_percentile_value": 0.0,
                        "aggressiveness_factor": aggressiveness,
                        "adjusted_commitment": 0.0,
                        "discount_rate": discount_rate,
                        "breakeven_hours_pct": 0.0,
                    },
                }
                continue

            # Extract total spend values from timeseries
            total_values = [point["total"] for point in timeseries]

            # Calculate percentiles
            percentiles = self._calculate_percentiles(total_values)

            # Determine target percentile based on discount rate
            # Formula: target_percentile = 100 - (discount_rate * 100)
            # Example: 60% discount → P40 (will save money 60% of the time)
            target_percentile = int(100 - (discount_rate * 100))
            target_percentile_key = f"p{target_percentile}"

            # Get the value at the target percentile
            target_value = percentiles.get(target_percentile_key, 0.0)

            # Apply aggressiveness factor
            adjusted_commitment = target_value * aggressiveness

            # Calculate breakeven hours percentage
            # This is the percentage of hours where usage >= commitment (we save money)
            breakeven_hours_pct = 100 - target_percentile

            logger.info(
                f"{sp_type.capitalize()} optimization: "
                f"Discount={discount_rate*100:.0f}% → Target={target_percentile_key} "
                f"(${target_value:.2f}/hour) → "
                f"Adjusted=${adjusted_commitment:.2f}/hour (aggressiveness={aggressiveness})"
            )

            result[sp_type] = {
                "recommended_hourly_commitment": adjusted_commitment,
                "analysis": {
                    "percentiles": percentiles,
                    "target_percentile": target_percentile,
                    "target_percentile_value": target_value,
                    "aggressiveness_factor": aggressiveness,
                    "adjusted_commitment": adjusted_commitment,
                    "discount_rate": discount_rate,
                    "breakeven_hours_pct": breakeven_hours_pct,
                },
            }

        return result

    def _calculate_percentiles(self, values: list[float]) -> dict[str, float]:
        """
        Calculate percentiles from a list of values.

        Args:
            values: List of numeric values (e.g., hourly spend amounts)

        Returns:
            dict: Percentile values:
                {"p10": 8.5, "p20": 10.2, ..., "p99": 35.2}
        """
        if not values:
            return {}

        # Filter out zero values for more meaningful percentiles
        non_zero_values = sorted([v for v in values if v > 0])
        if not non_zero_values:
            return {}

        # Calculate percentiles: 10, 20, 30, ..., 90, 99
        percentile_levels = [*list(range(10, 100, 10)), 99]
        percentiles = {}

        n = len(non_zero_values)
        for p in percentile_levels:
            # Linear interpolation percentile calculation
            rank = (p / 100.0) * (n - 1)
            lower_index = int(rank)
            upper_index = min(lower_index + 1, n - 1)
            fraction = rank - lower_index

            value = non_zero_values[lower_index] + fraction * (
                non_zero_values[upper_index] - non_zero_values[lower_index]
            )
            percentiles[f"p{p}"] = float(value)

        return percentiles

    def calculate_next_purchase_amount(
        self,
        current_commitment: float,
        target_commitment: float,
        strategy_percent: float,
    ) -> float:
        """
        Calculate next purchase amount using strategy percentage.

        IMPORTANT: The percentage is applied to the TARGET, not to the gap.
        This ensures consistent incremental steps regardless of current position.

        Args:
            current_commitment: Current hourly commitment ($/hour)
            target_commitment: Target hourly commitment from optimization ($/hour)
            strategy_percent: Strategy percentage (e.g., 0.10 for 10%)

        Returns:
            float: Amount to purchase ($/hour)

        Examples:
            >>> # Current: $50/hour, Target: $100/hour, Strategy: 10%
            >>> calculate_next_purchase_amount(50, 100, 0.10)
            10.0  # Purchase $10 (10% of $100 target, not 10% of $50 gap)

            >>> # Next iteration: Current: $60/hour (after first purchase)
            >>> calculate_next_purchase_amount(60, 100, 0.10)
            10.0  # Still purchase $10 (consistent increments)
        """
        if target_commitment <= current_commitment:
            # Already at or above target
            return 0.0

        # Calculate purchase amount as percentage of TARGET (not gap)
        purchase_amount = target_commitment * strategy_percent

        # Don't exceed the remaining gap
        remaining_gap = target_commitment - current_commitment
        return min(purchase_amount, remaining_gap)

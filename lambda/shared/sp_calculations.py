"""
Central repository for all Savings Plan calculation formulas.

This module is the single source of truth for conversion logic between:
- Commitment (what you pay)
- Coverage (what on-demand workload it covers)
- Savings percentage (discount rate)

All other modules should import these functions rather than duplicating the formulas.

IMPORTANT: JavaScript equivalents exist in docs/js/spCalculations.js and must stay in sync.
Cross-platform parity is verified by tests/cross_platform/test_algorithm_parity.py
"""


def coverage_from_commitment(commitment: float, savings_percentage: float) -> float:
    """
    Convert SP commitment to on-demand coverage capacity.

    This calculates how much on-demand workload a given commitment can cover,
    based on the discount rate. For example, a $1.00/hr commitment with 34.8%
    savings can cover $1.53/hr of on-demand usage.

    Args:
        commitment: Hourly commitment amount (what you pay)
        savings_percentage: Discount rate (e.g., 34.8 for 34.8% discount)

    Returns:
        On-demand coverage capacity (what workload it covers)

    Example:
        >>> coverage_from_commitment(1.00, 34.8)
        1.5337...  # $1.00 commitment covers $1.53 of on-demand

    Formula:
        coverage = commitment / (1 - discount_rate)
        where discount_rate = savings_percentage / 100

    Note:
        - If savings >= 100%, returns commitment unchanged (edge case protection)
        - Returns 0 if commitment is 0
    """
    if savings_percentage >= 100:
        # Edge case: 100%+ savings would cause division by zero
        return commitment

    discount_rate = savings_percentage / 100
    return commitment / (1 - discount_rate)


def commitment_from_coverage(coverage: float, savings_percentage: float) -> float:
    """
    Convert on-demand coverage to SP commitment cost.

    This calculates how much you need to commit to cover a given amount of
    on-demand workload. For example, to cover $1.53/hr of on-demand with 34.8%
    savings requires a $1.00/hr commitment.

    Args:
        coverage: On-demand workload to cover ($/hour)
        savings_percentage: Discount rate (e.g., 34.8 for 34.8% discount)

    Returns:
        Required hourly commitment (what you'll pay)

    Example:
        >>> commitment_from_coverage(1.53, 34.8)
        0.998...  # Need ~$1.00 commitment to cover $1.53 on-demand

    Formula:
        commitment = coverage * discount_factor
        where discount_factor = (1 - savings_percentage / 100)

    Note:
        - Returns 0 if coverage is 0
        - Result is always <= coverage (you pay less than on-demand)
    """
    discount_factor = 1 - (savings_percentage / 100)
    return coverage * discount_factor


def calculate_savings_percentage(on_demand_cost: float, used_commitment: float) -> float:
    """
    Calculate discount rate from actual usage.

    This determines what percentage discount you're getting based on how much
    on-demand workload you used vs how much you paid (used commitment). This is
    the "discount rate" - what percentage off you get.

    IMPORTANT: This does NOT include waste from unused commitment. If you have
    unused commitment, that waste is tracked separately in utilization metrics.

    Args:
        on_demand_cost: What the workload would have cost at on-demand rates
        used_commitment: Amount of commitment actually used (not total commitment)

    Returns:
        Savings percentage (0-100)

    Example:
        >>> calculate_savings_percentage(1.53, 1.00)
        34.64...  # You saved ~34.6% vs on-demand

    Formula:
        savings_percentage = ((on_demand - used_commitment) / on_demand) * 100

    Note:
        - Returns 0.0 if on_demand_cost <= 0 (no usage to calculate savings from)
        - Can theoretically return >100% if used_commitment > on_demand_cost,
          but this shouldn't happen in practice with valid AWS data
    """
    if on_demand_cost <= 0:
        return 0.0

    return ((on_demand_cost - used_commitment) / on_demand_cost) * 100.0


def average_to_hourly(total: float, num_hours: int) -> float:
    """
    Convert total amount to hourly average.

    Simple utility for converting period totals (weekly, monthly, etc.) to
    per-hour averages. Used extensively for normalizing metrics across
    different time periods.

    Args:
        total: Total amount over the period
        num_hours: Number of hours in the period

    Returns:
        Hourly average, or 0.0 if num_hours is 0

    Example:
        >>> average_to_hourly(168.0, 168)  # Weekly total to hourly
        1.0
        >>> average_to_hourly(0, 0)  # Edge case: no hours
        0.0

    Note:
        - Returns 0.0 for division by zero (num_hours = 0)
        - Handles negative totals correctly (returns negative hourly)
    """
    return total / num_hours if num_hours > 0 else 0.0


def calculate_effective_savings_rate(
    on_demand_cost: float,
    total_commitment: float,
    utilization_percentage: float,
) -> float:
    """
    Calculate effective savings rate including waste from unused commitment.

    This differs from calculate_savings_percentage() by including the impact of
    unused commitment (waste). If you have low utilization, your effective
    savings rate will be lower than the discount rate because you're paying
    for unused capacity.

    Args:
        on_demand_cost: What the workload would have cost at on-demand rates
        total_commitment: Total commitment amount (includes unused portion)
        utilization_percentage: What % of commitment was actually used (0-100)

    Returns:
        Effective savings percentage including waste (0-100, can be negative)

    Example:
        >>> # 50% off but only 80% utilization
        >>> calculate_effective_savings_rate(100.0, 50.0, 80.0)
        40.0  # You saved $40 net: paid $50, would have paid $100, but $10 was waste

    Formula:
        effective_savings = ((on_demand - total_commitment) / on_demand) * 100

    Note:
        - Can return negative values if you paid more than on-demand (over-committed)
        - Returns 0.0 if on_demand_cost <= 0
        - This is your "actual" savings rate after accounting for waste
    """
    if on_demand_cost <= 0:
        return 0.0

    return ((on_demand_cost - total_commitment) / on_demand_cost) * 100.0


def commitment_to_percentage_of_coverage(commitment: float, current_coverage: float) -> float:
    """
    Express commitment as percentage of current coverage.

    Useful for understanding how much of your workload is covered by SP vs on-demand.

    Args:
        commitment: Your SP commitment ($/hour)
        current_coverage: Current coverage capacity from that commitment ($/hour)

    Returns:
        Percentage (0-100)

    Example:
        >>> commitment_to_percentage_of_coverage(0.80, 1.00)
        80.0  # Your commitment covers 80% of your on-demand capacity
    """
    if current_coverage <= 0:
        return 0.0

    return (commitment / current_coverage) * 100.0

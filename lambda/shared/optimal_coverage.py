"""
Optimal Savings Plan Coverage Calculator.

KEEP IN SYNC with docs/js/costCalculator.js — verified by tests/cross_platform/test_algorithm_parity.py.
"""

from typing import TypedDict


class OptimalCoverageResult(TypedDict):
    """Result of optimal coverage calculation"""

    coverage_hourly: float  # Optimal coverage in $/hour
    coverage_percentage: float  # Coverage as % of max hourly cost
    max_net_savings: float  # Maximum net savings achievable (weekly)
    percentiles: dict[str, float]  # P50, P75, P90 as % of max cost


def calculate_optimal_coverage(
    hourly_costs: list[float], savings_percentage: float
) -> OptimalCoverageResult:
    """
    Calculate optimal Savings Plan coverage that maximizes net savings.

    This is a pure Python port of the JavaScript implementation in
    docs/js/costCalculator.js. Both implementations should produce
    identical results for the same inputs.

    Algorithm:
    1. Test 100 coverage levels from $0 to max hourly cost
    2. For each level, calculate total cost:
       - Commitment cost: coverage * discount * hours
       - Spillover cost: sum of (actual_cost - coverage) when actual > coverage
    3. Compare to baseline on-demand cost
    4. Return the coverage level with maximum net savings

    Args:
        hourly_costs: List of hourly costs (typically 168 hours = 1 week)
        savings_percentage: Savings plan discount percentage (e.g., 30 for 30%)

    Returns:
        OptimalCoverageResult with optimal coverage and savings analysis

    Example:
        >>> hourly_costs = [45.2, 52.1, 48.7, ...] # 168 hours
        >>> result = calculate_optimal_coverage(hourly_costs, 30)
        >>> print(f"Optimal: ${result['coverage_hourly']:.2f}/hr")
        Optimal: $58.50/hr
    """
    if not hourly_costs:
        raise ValueError("hourly_costs cannot be empty")

    if not 0 <= savings_percentage <= 99:
        raise ValueError("savings_percentage must be between 0 and 99")

    sorted_costs = sorted(hourly_costs)
    max_cost = max(hourly_costs)
    min_cost = min(hourly_costs)

    # Discount factor: if 30% savings, you pay 70% of on-demand price
    # NOTE: This is equivalent to shared.sp_calculations.commitment_from_coverage()
    # Kept as a variable here for performance (reused in loop below)
    discount_factor = 1 - (savings_percentage / 100)

    best_net_savings = float("-inf")
    best_coverage = min_cost  # Start at min-hourly as baseline
    best_coverage_percentage = 0.0

    # Test coverage levels from min to max (min is always safe)
    # Use 100 increments for granularity
    range_to_test = max_cost - min_cost
    if range_to_test == 0:
        # All costs are the same, optimal is at min (= max)
        return {
            "coverage_hourly": min_cost,
            "coverage_percentage": 100.0,
            "max_net_savings": sum(hourly_costs) * (savings_percentage / 100),
            "percentiles": {"p50": 100.0, "p75": 100.0, "p90": 100.0},
        }

    increment = range_to_test / 100
    coverage_cost = min_cost

    # TODO: Optimization - could implement early stopping when savings decrease
    # Since this is a convex optimization problem, once savings start decreasing,
    # we've passed the optimal point and can stop testing.
    # Current implementation tests all 100 points for simplicity and robustness.

    while coverage_cost <= max_cost:
        commitment_cost = 0.0
        spillover_cost = 0.0

        # Calculate cost for this coverage level across all hours (e.g., 336 hours = 14 days)
        for hour_cost in hourly_costs:
            # For this hour:
            # - Commitment: You pay for coverage at discounted rate (e.g., 70% if 30% discount)
            #   This is paid regardless of whether you use it or not
            commitment_cost += coverage_cost * discount_factor

            # - Spillover: Usage above coverage is paid at full on-demand rate
            #   If actual usage is $80 and coverage is $50, you pay $30 at on-demand
            spillover_cost += max(0, hour_cost - coverage_cost)

        # Total cost with this SP coverage across all hours
        total_cost = commitment_cost + spillover_cost

        # Baseline: what you'd pay without any SP (full on-demand for everything)
        baseline_cost = sum(hourly_costs)

        # Net savings: baseline - total_with_sp (can be negative if coverage too high)
        net_savings = baseline_cost - total_cost

        # Track best result
        if net_savings > best_net_savings:
            best_net_savings = net_savings
            best_coverage = coverage_cost
            best_coverage_percentage = (coverage_cost / max_cost * 100) if max_cost > 0 else 0

        coverage_cost += increment

    # Calculate baseline savings at min-hourly (100% safe coverage)
    min_hourly_savings = min_cost * len(hourly_costs) * (savings_percentage / 100)

    # Calculate extra savings beyond min-hourly baseline
    extra_savings = best_net_savings - min_hourly_savings

    # Calculate percentile-based reference points
    n = len(sorted_costs)
    p50 = sorted_costs[int(n * 0.50)]
    p75 = sorted_costs[int(n * 0.75)]
    p90 = sorted_costs[int(n * 0.90)]

    return {
        "coverage_hourly": best_coverage,
        "coverage_percentage": best_coverage_percentage,
        "max_net_savings": best_net_savings,
        "min_hourly_savings": min_hourly_savings,  # Baseline savings at 100%
        "extra_savings": extra_savings,  # Additional savings beyond min-hourly
        "min_cost": min_cost,  # For reference
        "percentiles": {
            "p50": (p50 / max_cost * 100) if max_cost > 0 else 0,
            "p75": (p75 / max_cost * 100) if max_cost > 0 else 0,
            "p90": (p90 / max_cost * 100) if max_cost > 0 else 0,
        },
    }


def get_min_hourly_coverage(hourly_costs: list[float]) -> float:
    """
    Get the minimum hourly cost (100% safe coverage level).

    This is the baseline "always safe" coverage where you never waste
    commitment since actual usage always exceeds this amount.

    Args:
        hourly_costs: List of hourly costs

    Returns:
        Minimum hourly cost ($/hour)
    """
    if not hourly_costs:
        return 0.0

    return min(hourly_costs)


def coverage_as_percentage_of_min(hourly_coverage: float, min_hourly: float) -> float:
    """
    Express coverage as percentage of min-hourly baseline.

    This provides intuitive scaling where:
    - 100% = min-hourly (always safe)
    - >100% = beyond min-hourly (requires optimization analysis)
    - <100% = below min-hourly (unusual, likely misconfigured)

    Args:
        hourly_coverage: Actual coverage in $/hour
        min_hourly: Minimum hourly cost (baseline)

    Returns:
        Coverage as percentage of min-hourly (e.g., 112.5 for 12.5% above min)
    """
    if min_hourly <= 0:
        return 0.0

    return (hourly_coverage / min_hourly) * 100


def _build_savings_curve(
    hourly_costs: list[float],
    discount_factor: float,
    min_cost: float,
    max_coverage: float,
    num_points: int = 200,
) -> list[dict]:
    """Build the savings curve by simulating coverage at different levels."""
    baseline_cost = sum(hourly_costs)
    step = (max_coverage - min_cost) / num_points
    curve_points = []

    for i in range(num_points + 1):
        coverage = min_cost + (i * step)

        commitment_cost = 0.0
        spillover_cost = 0.0

        for hour_cost in hourly_costs:
            commitment_cost += coverage * discount_factor
            spillover_cost += max(0, hour_cost - coverage)

        total_cost = commitment_cost + spillover_cost
        net_savings = baseline_cost - total_cost
        savings_pct = (net_savings / baseline_cost) * 100 if baseline_cost > 0 else 0

        curve_points.append(
            {
                "coverage": coverage,
                "savings_percent": savings_pct,
                "net_savings": net_savings,
            }
        )

    return curve_points


def _compute_marginal_rates(
    curve_points: list[dict], min_cost: float, optimal_coverage: float
) -> list[dict]:
    """Compute marginal savings rates between curve points."""
    marginal_rates = []
    for i in range(1, len(curve_points)):
        if (
            curve_points[i]["coverage"] <= min_cost
            or curve_points[i]["coverage"] > optimal_coverage
        ):
            continue
        coverage_delta = curve_points[i]["coverage"] - curve_points[i - 1]["coverage"]
        savings_delta = curve_points[i]["savings_percent"] - curve_points[i - 1]["savings_percent"]
        marginal_rate = savings_delta / coverage_delta if coverage_delta > 0 else 0

        marginal_rates.append(
            {
                "index": i,
                "coverage": curve_points[i]["coverage"],
                "marginal_rate": marginal_rate,
                "savings_percent": curve_points[i]["savings_percent"],
            }
        )
    return marginal_rates


def calculate_knee_point(
    hourly_costs: list[float],
    savings_percentage: float,
    min_cost: float,
    optimal_coverage: float,
) -> float:
    """
    Calculate the knee point on the savings curve.

    This is the "balanced" strategy — where marginal efficiency drops to 40%
    of its peak. Direct port of docs/js/main.js calculateKneePoint().

    CROSS-LANGUAGE SYNCHRONIZATION: Keep in sync with docs/js/main.js:696-776.

    Args:
        hourly_costs: List of hourly costs
        savings_percentage: Savings plan discount percentage (e.g., 30 for 30%)
        min_cost: Minimum hourly cost (baseline)
        optimal_coverage: Optimal coverage from calculate_optimal_coverage()

    Returns:
        Knee point coverage in $/hour
    """
    discount_factor = 1 - (savings_percentage / 100)
    max_coverage = optimal_coverage * 1.2

    curve_points = _build_savings_curve(hourly_costs, discount_factor, min_cost, max_coverage)
    marginal_rates = _compute_marginal_rates(curve_points, min_cost, optimal_coverage)

    if not marginal_rates:
        return min_cost

    max_marginal_rate = max(r["marginal_rate"] for r in marginal_rates)
    threshold = max_marginal_rate * 0.40

    knee_index = 0
    for i, rate in enumerate(marginal_rates):
        if rate["marginal_rate"] < threshold:
            knee_index = marginal_rates[i - 1]["index"] if i > 0 else marginal_rates[0]["index"]
            break

    if knee_index == 0:
        return min_cost + (optimal_coverage - min_cost) * 0.60

    return curve_points[knee_index]["coverage"]


def calculate_strategies(hourly_costs: list[float], savings_percentage: float) -> dict[str, float]:
    """
    Calculate all dynamic target strategy levels.

    Direct port of docs/js/main.js calculateStrategies().

    CROSS-LANGUAGE SYNCHRONIZATION: Keep in sync with docs/js/main.js:635-687.

    Args:
        hourly_costs: List of hourly costs
        savings_percentage: Savings plan discount percentage (e.g., 30 for 30%)

    Returns:
        Dict with keys: too_prudent, min_hourly, balanced, aggressive (all in $/hour)
    """
    if not hourly_costs:
        return {
            "too_prudent": 0.0,
            "min_hourly": 0.0,
            "balanced": 0.0,
            "aggressive": 0.0,
        }

    min_hourly = min(hourly_costs)
    too_prudent = min_hourly * 0.80

    optimal_result = calculate_optimal_coverage(hourly_costs, savings_percentage)
    optimal = optimal_result["coverage_hourly"]

    balanced = calculate_knee_point(hourly_costs, savings_percentage, min_hourly, optimal)
    aggressive = optimal

    return {
        "too_prudent": too_prudent,
        "min_hourly": min_hourly,
        "balanced": balanced,
        "aggressive": aggressive,
    }

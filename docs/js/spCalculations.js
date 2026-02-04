/**
 * Central repository for Savings Plan calculations.
 *
 * CRITICAL: These formulas must match lambda/shared/sp_calculations.py
 * Any changes here MUST be synchronized with Python backend.
 * Cross-platform parity is verified by lambda/tests/cross_platform/test_algorithm_parity.py
 *
 * This module provides the single source of truth for conversion logic between:
 * - Commitment (what you pay)
 * - Coverage (what on-demand workload it covers)
 * - Savings percentage (discount rate)
 */

/**
 * Convert SP commitment to on-demand coverage capacity.
 *
 * This calculates how much on-demand workload a given commitment can cover,
 * based on the discount rate. For example, a $1.00/hr commitment with 34.8%
 * savings can cover $1.53/hr of on-demand usage.
 *
 * @param {number} commitment - Hourly commitment amount (what you pay)
 * @param {number} savingsPercentage - Discount rate (0-100, e.g., 34.8 for 34.8% discount)
 * @returns {number} On-demand coverage capacity (what workload it covers)
 *
 * @example
 * // $1.00 commitment with 34.8% savings covers $1.53 of on-demand
 * coverageFromCommitment(1.00, 34.8); // Returns ~1.53
 *
 * Formula: coverage = commitment / (1 - discount_rate)
 * where discount_rate = savingsPercentage / 100
 *
 * Note:
 * - If savings >= 100%, returns commitment unchanged (edge case protection)
 * - Returns 0 if commitment is 0
 */
function coverageFromCommitment(commitment, savingsPercentage) {
    if (savingsPercentage >= 100) {
        // Edge case: 100%+ savings would cause division by zero
        return commitment;
    }
    const discountRate = savingsPercentage / 100;
    return commitment / (1 - discountRate);
}

/**
 * Convert on-demand coverage to SP commitment cost.
 *
 * This calculates how much you need to commit to cover a given amount of
 * on-demand workload. For example, to cover $1.53/hr of on-demand with 34.8%
 * savings requires a $1.00/hr commitment.
 *
 * @param {number} coverage - On-demand workload to cover ($/hour)
 * @param {number} savingsPercentage - Discount rate (0-100)
 * @returns {number} Required hourly commitment (what you'll pay)
 *
 * @example
 * // To cover $1.53 on-demand with 34.8% savings, need ~$1.00 commitment
 * commitmentFromCoverage(1.53, 34.8); // Returns ~1.00
 *
 * Formula: commitment = coverage * discount_factor
 * where discount_factor = (1 - savingsPercentage / 100)
 *
 * Note:
 * - Returns 0 if coverage is 0
 * - Result is always <= coverage (you pay less than on-demand)
 */
function commitmentFromCoverage(coverage, savingsPercentage) {
    const discountFactor = 1 - (savingsPercentage / 100);
    return coverage * discountFactor;
}

/**
 * Calculate discount rate from actual usage.
 *
 * This determines what percentage discount you're getting based on how much
 * on-demand workload you used vs how much you paid (used commitment). This is
 * the "discount rate" - what percentage off you get.
 *
 * IMPORTANT: This does NOT include waste from unused commitment. If you have
 * unused commitment, that waste is tracked separately in utilization metrics.
 *
 * @param {number} onDemandCost - What the workload would have cost at on-demand rates
 * @param {number} usedCommitment - Amount of commitment actually used (not total commitment)
 * @returns {number} Savings percentage (0-100)
 *
 * @example
 * // Used $1.00 to cover $1.53 on-demand = ~34.6% savings
 * calculateSavingsPercentage(1.53, 1.00); // Returns ~34.6
 *
 * Formula: savings_percentage = ((on_demand - used_commitment) / on_demand) * 100
 *
 * Note:
 * - Returns 0 if on_demand_cost <= 0 (no usage to calculate savings from)
 * - Can theoretically return >100% if used_commitment > on_demand_cost,
 *   but this shouldn't happen in practice with valid AWS data
 */
function calculateSavingsPercentage(onDemandCost, usedCommitment) {
    if (onDemandCost <= 0) {
        return 0;
    }
    return ((onDemandCost - usedCommitment) / onDemandCost) * 100;
}

/**
 * Calculate effective savings rate including waste from unused commitment.
 *
 * This differs from calculateSavingsPercentage() by including the impact of
 * unused commitment (waste). If you have low utilization, your effective
 * savings rate will be lower than the discount rate because you're paying
 * for unused capacity.
 *
 * @param {number} onDemandCost - What the workload would have cost at on-demand rates
 * @param {number} totalCommitment - Total commitment amount (includes unused portion)
 * @returns {number} Effective savings percentage including waste (0-100, can be negative)
 *
 * @example
 * // 50% discount but only 80% utilization
 * // On-demand: $100, Paid: $50 total (includes $10 waste)
 * calculateEffectiveSavingsRate(100.0, 50.0); // Returns 50.0
 * // You saved $50 net (on-demand - total paid)
 *
 * Formula: effective_savings = ((on_demand - total_commitment) / on_demand) * 100
 *
 * Note:
 * - Can return negative values if you paid more than on-demand (over-committed)
 * - Returns 0 if on_demand_cost <= 0
 * - This is your "actual" savings rate after accounting for waste
 * - The waste is already included in totalCommitment (used + unused)
 */
function calculateEffectiveSavingsRate(onDemandCost, totalCommitment) {
    if (onDemandCost <= 0) {
        return 0;
    }
    return ((onDemandCost - totalCommitment) / onDemandCost) * 100;
}

// Export for module systems (Node.js, bundlers)
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        coverageFromCommitment,
        commitmentFromCoverage,
        calculateSavingsPercentage,
        calculateEffectiveSavingsRate
    };
}

// Also make available globally for browser usage
if (typeof window !== 'undefined') {
    window.SPCalculations = {
        coverageFromCommitment,
        commitmentFromCoverage,
        calculateSavingsPercentage,
        calculateEffectiveSavingsRate
    };
}

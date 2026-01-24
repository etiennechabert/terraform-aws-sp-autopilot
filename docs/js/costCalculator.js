/**
 * Cost Calculation Engine
 * Calculates Savings Plan vs On-Demand costs with detailed breakdowns
 */

const CostCalculator = (function() {
    'use strict';

    /**
     * Calculate comprehensive cost comparison
     * @param {Object} config - Configuration object
     * @param {Array<number>} config.hourlyCosts - 168-hour actual costs ($/hour)
     * @param {number} config.coverageCost - Coverage commitment ($/hour)
     * @param {number} config.savingsPercentage - Savings percentage (0-99)
     * @param {number} config.onDemandRate - On-Demand rate per unit-hour (for reference)
     * @returns {Object} Detailed cost breakdown
     */
    function calculateCosts(config) {
        const {
            hourlyCosts = [],
            coverageCost = 0,
            savingsPercentage = 30,
            onDemandRate = 0.10
        } = config;

        // Calculate the discounted rate (as a fraction of on-demand)
        const discountFactor = (1 - savingsPercentage / 100);

        // Coverage commitment cost per hour (at discounted rate)
        const commitmentCostPerHour = coverageCost * discountFactor;

        // Initialize accumulators
        let totalOnDemandCost = 0;
        let totalSavingsPlanCost = 0;
        let totalSpilloverCost = 0;
        let totalWastedCommitment = 0;

        // Hourly breakdowns for visualization
        const hourlyBreakdown = [];

        // Calculate costs for each hour
        for (let hour = 0; hour < 168; hour++) {
            // Actual on-demand cost for this hour
            const onDemandCost = hourlyCosts[hour] || 0;
            totalOnDemandCost += onDemandCost;

            // Savings Plan scenario
            // If actual cost is above coverage, we have spillover
            const spilloverCost = Math.max(0, onDemandCost - coverageCost);

            // Cost covered by SP (up to the coverage limit, at discounted rate)
            const coveredAmount = Math.min(onDemandCost, coverageCost);
            const coveredCost = coveredAmount * discountFactor;

            // Wasted commitment (when usage is below commitment)
            const wastedAmount = Math.max(0, coverageCost - onDemandCost);
            const wasteCost = wastedAmount * discountFactor;

            // Total with SP: full commitment (at discounted rate) + any spillover (at on-demand rate)
            const savingsPlanCost = commitmentCostPerHour + spilloverCost;

            totalSavingsPlanCost += savingsPlanCost;
            totalSpilloverCost += spilloverCost;
            totalWastedCommitment += wasteCost;

            // Store hourly breakdown
            hourlyBreakdown.push({
                hour,
                onDemandCost,
                savingsPlanCost,
                commitmentCost: commitmentCostPerHour,
                coveredCost,
                spilloverCost,
                wasteCost,
                coverageUnits: coverageCost,  // For display
                actualUsage: onDemandCost / onDemandRate,  // For display
                coveredUsage: coveredAmount / onDemandRate,
                spilloverUsage: spilloverCost / onDemandRate,
                wastedUnits: wastedAmount / onDemandRate
            });
        }

        // Calculate savings
        const totalSavings = totalOnDemandCost - totalSavingsPlanCost;
        const savingsPercentageActual = totalOnDemandCost > 0
            ? (totalSavings / totalOnDemandCost) * 100
            : 0;

        // Calculate optimal coverage
        const optimalCoverage = calculateOptimalCoverage(
            hourlyCosts,
            savingsPercentage
        );

        // Calculate efficiency metrics
        const totalCommitmentCost = commitmentCostPerHour * 168;
        const totalCoveredCost = totalCommitmentCost - totalWastedCommitment;

        const spilloverPercentage = totalSavingsPlanCost > 0
            ? (totalSpilloverCost / totalSavingsPlanCost) * 100
            : 0;

        const wastePercentage = totalCommitmentCost > 0
            ? (totalWastedCommitment / totalCommitmentCost) * 100
            : 0;

        return {
            // Cost totals
            onDemandCost: totalOnDemandCost,
            savingsPlanCost: totalSavingsPlanCost,
            savings: totalSavings,
            savingsPercentageActual,

            // Breakdown
            commitmentCost: totalCommitmentCost,
            spilloverCost: totalSpilloverCost,
            wastedCommitment: totalWastedCommitment,
            coveredCost: totalCoveredCost,

            // Metrics
            spilloverPercentage,
            wastePercentage,

            // Optimization
            optimalCoverage,
            optimalCoverageUnits: optimalCoverage.coverageUnits,
            optimalCoveragePercentage: optimalCoverage.coveragePercentage,

            // Hourly data for charts
            hourlyBreakdown,

            // Configuration used
            config: {
                coverageUnits: coverageCost,
                savingsPercentage,
                onDemandRate,
                savingsPlanRate: onDemandRate * discountFactor
            }
        };
    }

    /**
     * Calculate optimal coverage level to maximize net savings
     * @param {Array<number>} hourlyCosts - Actual hourly costs ($/hour)
     * @param {number} savingsPercentage - Savings percentage (0-99)
     * @returns {Object} Optimal coverage recommendation
     */
    function calculateOptimalCoverage(hourlyCosts, savingsPercentage) {
        // Sort costs to analyze percentiles
        const sortedCosts = [...hourlyCosts].sort((a, b) => a - b);
        const maxCost = Math.max(...hourlyCosts);

        const discountFactor = (1 - savingsPercentage / 100);

        let bestNetSavings = -Infinity;
        let bestCoverage = 0;
        let bestCoveragePercentage = 0;

        // Test coverage levels from $0 to max cost in small increments
        const increment = maxCost / 100; // Test 100 different coverage levels

        for (let coverageCost = 0; coverageCost <= maxCost; coverageCost += increment) {
            let commitmentCost = 0;
            let spilloverCost = 0;

            for (let hour = 0; hour < 168; hour++) {
                const onDemandCost = hourlyCosts[hour];

                // Full commitment cost (at discounted rate)
                commitmentCost += coverageCost * discountFactor;

                // Spillover (usage above coverage, at on-demand rate)
                spilloverCost += Math.max(0, onDemandCost - coverageCost);
            }

            const totalCost = commitmentCost + spilloverCost;

            // Calculate baseline on-demand cost
            const baselineCost = hourlyCosts.reduce((sum, cost) => sum + cost, 0);

            const netSavings = baselineCost - totalCost;

            if (netSavings > bestNetSavings) {
                bestNetSavings = netSavings;
                bestCoverage = coverageCost;
                bestCoveragePercentage = maxCost > 0 ? (coverageCost / maxCost) * 100 : 0;
            }
        }

        // Calculate percentile-based recommendations
        const p50 = sortedCosts[Math.floor(sortedCosts.length * 0.50)];
        const p75 = sortedCosts[Math.floor(sortedCosts.length * 0.75)];
        const p90 = sortedCosts[Math.floor(sortedCosts.length * 0.90)];

        return {
            coverageUnits: bestCoverage,  // Now in $/hour
            coveragePercentage: bestCoveragePercentage,
            maxNetSavings: bestNetSavings,
            percentiles: {
                p50: maxCost > 0 ? (p50 / maxCost) * 100 : 0,
                p75: maxCost > 0 ? (p75 / maxCost) * 100 : 0,
                p90: maxCost > 0 ? (p90 / maxCost) * 100 : 0
            }
        };
    }

    /**
     * Get optimization suggestion based on current vs optimal coverage
     * @param {number} currentCoverage - Current coverage percentage
     * @param {number} optimalCoverage - Optimal coverage percentage
     * @returns {Object} Suggestion with status and message
     */
    function getOptimizationSuggestion(currentCoverage, optimalCoverage) {
        const difference = Math.abs(currentCoverage - optimalCoverage);

        let status = 'optimal'; // 'optimal', 'warning', 'danger'
        let message = '';
        let icon = '✅';

        if (difference <= 5) {
            status = 'optimal';
            icon = '✅';
            message = `Your coverage is optimal (within 5% of ideal). Current: ${currentCoverage.toFixed(1)}%, Optimal: ${optimalCoverage.toFixed(1)}%`;
        } else if (difference <= 10) {
            status = 'warning';
            icon = '⚠️';
            if (currentCoverage < optimalCoverage) {
                message = `Consider increasing coverage to ${optimalCoverage.toFixed(1)}% (current: ${currentCoverage.toFixed(1)}%) to maximize savings while minimizing waste.`;
            } else {
                message = `Consider decreasing coverage to ${optimalCoverage.toFixed(1)}% (current: ${currentCoverage.toFixed(1)}%) to reduce wasted commitment.`;
            }
        } else {
            status = 'danger';
            icon = '🔴';
            if (currentCoverage < optimalCoverage) {
                message = `Coverage is significantly below optimal. Increase to ${optimalCoverage.toFixed(1)}% (current: ${currentCoverage.toFixed(1)}%) to unlock ${difference.toFixed(1)}% more savings potential.`;
            } else {
                message = `Coverage is significantly above optimal. Decrease to ${optimalCoverage.toFixed(1)}% (current: ${currentCoverage.toFixed(1)}%) to reduce ${difference.toFixed(1)}% wasted commitment.`;
            }
        }

        return {
            status,
            icon,
            message,
            difference,
            recommendation: optimalCoverage
        };
    }

    /**
     * Format currency value
     * @param {number} value - Dollar amount
     * @returns {string} Formatted currency
     */
    function formatCurrency(value) {
        return new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: 'USD',
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        }).format(value);
    }

    /**
     * Format percentage value
     * @param {number} value - Percentage (0-100)
     * @param {number} decimals - Decimal places (default: 1)
     * @returns {string} Formatted percentage
     */
    function formatPercentage(value, decimals = 1) {
        return `${value.toFixed(decimals)}%`;
    }

    /**
     * Calculate cost impact of changing coverage
     * @param {Object} currentResults - Current cost results
     * @param {number} newCoverageLevel - New coverage level to simulate
     * @param {Object} config - Original configuration
     * @returns {Object} Impact analysis
     */
    function calculateCoverageImpact(currentResults, newCoverageLevel, config) {
        const newConfig = { ...config, coverageLevel: newCoverageLevel };
        const newResults = calculateCosts(newConfig);

        return {
            costChange: newResults.savingsPlanCost - currentResults.savingsPlanCost,
            savingsChange: newResults.savings - currentResults.savings,
            spilloverChange: newResults.spilloverCost - currentResults.spilloverCost,
            wasteChange: newResults.wastedCommitment - currentResults.wastedCommitment,
            newResults
        };
    }

    // Public API
    return {
        calculateCosts,
        calculateOptimalCoverage,
        getOptimizationSuggestion,
        formatCurrency,
        formatPercentage,
        calculateCoverageImpact
    };
})();

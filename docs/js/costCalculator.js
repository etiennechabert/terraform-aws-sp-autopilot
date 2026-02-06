/**
 * Cost Calculation Engine
 * Calculates Savings Plan vs On-Demand costs with detailed breakdowns
 */

const CostCalculator = (function() {
    'use strict';

    /**
     * Calculate comprehensive cost comparison
     * @param {Object} config - Configuration object
     * @param {Array<number>} config.hourlyCosts - 168-hour actual costs ($/h)
     * @param {number} config.coverageCost - Coverage commitment ($/h)
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
        // NOTE: This is equivalent to commitmentFromCoverage() in spCalculations.js
        // Kept as variables here for performance (reused throughout function)
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

        // Calculate costs for each hour in the actual data
        const numHours = hourlyCosts.length || 168;
        for (let hour = 0; hour < numHours; hour++) {
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

        // Calculate effective savings rate using centralized function
        const totalSavings = totalOnDemandCost - totalSavingsPlanCost;
        const savingsPercentageActual = calculateEffectiveSavingsRate(
            totalOnDemandCost,
            totalSavingsPlanCost
        );

        // Calculate optimal coverage
        const optimalCoverage = calculateOptimalCoverage(
            hourlyCosts,
            savingsPercentage
        );

        // Calculate efficiency metrics
        const totalCommitmentCost = commitmentCostPerHour * numHours;
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
     * Calculate net savings at different coverage levels for graphing
     * @param {Array<number>} hourlyCosts - Actual hourly costs ($/h)
     * @param {number} savingsPercentage - Savings percentage (0-99)
     * @returns {Object} Savings curve data with coverage levels and corresponding savings
     */
    function calculateSavingsCurve(hourlyCosts, savingsPercentage) {
        const minCost = Math.min(...hourlyCosts);
        const maxCost = Math.max(...hourlyCosts);
        const baselineCost = hourlyCosts.reduce((sum, cost) => sum + cost, 0);
        const discountFactor = (1 - savingsPercentage / 100);

        // Calculate savings at min-hourly (100% baseline)
        const minHourlySavings = minCost * hourlyCosts.length * (savingsPercentage / 100);

        const savingsCurve = [];
        const rangeToTest = maxCost - minCost;
        if (rangeToTest === 0) {
            const baselineCost = hourlyCosts.reduce((sum, cost) => sum + cost, 0);
            const savingsPercent = baselineCost > 0 ? (minHourlySavings / baselineCost) * 100 : 0;
            return {
                curve: [{
                    coverage: minCost,
                    commitment: minCost * discountFactor,
                    netSavings: minHourlySavings,
                    extraSavings: 0,
                    savingsPercent: savingsPercent,
                    percentOfMin: 100
                }],
                minHourly: minCost,
                minHourlySavings: minHourlySavings
            };
        }

        const increment = rangeToTest / 100;

        for (let coverageCost = minCost; coverageCost <= maxCost; coverageCost += increment) {
            let commitmentCost = 0;
            let spilloverCost = 0;

            for (let hour = 0; hour < hourlyCosts.length; hour++) {
                const onDemandCost = hourlyCosts[hour];
                commitmentCost += coverageCost * discountFactor;
                spilloverCost += Math.max(0, onDemandCost - coverageCost);
            }

            const totalCost = commitmentCost + spilloverCost;
            const netSavings = baselineCost - totalCost;
            const extraSavings = netSavings - minHourlySavings; // Savings beyond min-hourly baseline
            const savingsPercent = baselineCost > 0 ? (netSavings / baselineCost) * 100 : 0;
            const hourlyCommitment = coverageCost * discountFactor;

            savingsCurve.push({
                coverage: coverageCost,
                commitment: hourlyCommitment,
                netSavings: netSavings,
                extraSavings: extraSavings,
                savingsPercent: savingsPercent,
                percentOfMin: (coverageCost / minCost) * 100
            });
        }

        return {
            curve: savingsCurve,
            minHourly: minCost,
            minHourlySavings: minHourlySavings
        };
    }

    /**
     * Calculate optimal coverage level to maximize net savings
     *
     * CRITICAL - CROSS-LANGUAGE SYNCHRONIZATION:
     * ===========================================
     * WARNING: This algorithm is implemented in BOTH Python and JavaScript:
     *     - Python: lambda/shared/optimal_coverage.py
     *     - JavaScript: docs/js/costCalculator.js (this file)
     *
     * Changes to this algorithm MUST be synchronized across both languages!
     *
     * The cross-platform parity is verified by:
     *     - lambda/tests/cross_platform/test_algorithm_parity.py
     *
     * If you modify the algorithm, you MUST:
     *     1. Update both Python and JavaScript implementations
     *     2. Run cross-platform tests to verify parity
     *     3. Document any intentional differences in behavior
     *
     * @param {Array<number>} hourlyCosts - Actual hourly costs ($/h)
     * @param {number} savingsPercentage - Savings percentage (0-99)
     * @returns {Object} Optimal coverage recommendation
     */
    function calculateOptimalCoverage(hourlyCosts, savingsPercentage) {
        // Sort costs to analyze percentiles
        const sortedCosts = [...hourlyCosts].sort((a, b) => a - b);
        const maxCost = Math.max(...hourlyCosts);
        const minCost = Math.min(...hourlyCosts);

        const discountFactor = (1 - savingsPercentage / 100);

        // Calculate savings at min-hourly baseline
        const minHourlySavings = minCost * hourlyCosts.length * (savingsPercentage / 100);

        // Test coverage levels from min to max (min is always safe)
        const rangeToTest = maxCost - minCost;
        if (rangeToTest === 0) {
            // All costs are the same, optimal is at min (= max)
            const totalCost = hourlyCosts.reduce((sum, cost) => sum + cost, 0);
            return {
                coverageUnits: minCost,
                commitmentUnits: minCost * discountFactor,
                lastOptimalCoverage: minCost,
                coveragePercentage: 100.0,
                maxNetSavings: totalCost * (savingsPercentage / 100),
                minHourlySavings: minHourlySavings,
                extraSavings: 0,
                percentiles: { p50: 100.0, p75: 100.0, p90: 100.0 }
            };
        }

        const increment = rangeToTest / 100; // Test 100 different coverage levels
        const baselineCost = hourlyCosts.reduce((sum, cost) => sum + cost, 0);

        // Start tracking from 0
        let bestNetSavings = -Infinity;
        let bestCoverage = minCost;
        let bestCoveragePercentage = 0;

        for (let coverageCost = minCost; coverageCost <= maxCost; coverageCost += increment) {
            let commitmentCost = 0;
            let spilloverCost = 0;

            for (let hour = 0; hour < hourlyCosts.length; hour++) {
                const onDemandCost = hourlyCosts[hour];
                commitmentCost += coverageCost * discountFactor;
                spilloverCost += Math.max(0, onDemandCost - coverageCost);
            }

            const totalCost = commitmentCost + spilloverCost;
            const netSavings = baselineCost - totalCost;

            // If we found a new maximum, remember it and continue
            if (netSavings > bestNetSavings) {
                bestNetSavings = netSavings;
                bestCoverage = coverageCost;
                bestCoveragePercentage = maxCost > 0 ? (coverageCost / maxCost) * 100 : 0;
            }
            // If savings dropped below the best we've seen, we've passed optimal
            // Return the best point we found (first point at maximum)
            else if (netSavings < bestNetSavings) {
                break;
            }
            // If savings are equal, continue (we're at a plateau)
        }

        // Calculate extra savings beyond min-hourly
        const extraSavings = bestNetSavings - minHourlySavings;

        // Calculate percentile-based recommendations
        const p50 = sortedCosts[Math.floor(sortedCosts.length * 0.50)];
        const p75 = sortedCosts[Math.floor(sortedCosts.length * 0.75)];
        const p90 = sortedCosts[Math.floor(sortedCosts.length * 0.90)];

        return {
            coverageUnits: bestCoverage,  // On-demand equivalent coverage at maximum savings
            commitmentUnits: bestCoverage * discountFactor,  // Actual commitment cost
            coveragePercentage: bestCoveragePercentage,
            maxNetSavings: bestNetSavings,
            minHourlySavings: minHourlySavings,  // Baseline savings at min-hourly
            extraSavings: extraSavings,  // Additional savings beyond min-hourly
            minCost: minCost,  // For reference
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
     * Detect which savings curve zone the current coverage is in
     * @param {number} currentCoverage - Current coverage in $/h
     * @param {Array<number>} hourlyCosts - Hourly costs
     * @param {number} savingsPercentage - Savings percentage (0-99)
     * @returns {Object} Zone information with name and thresholds
     */
    function detectCoverageZone(currentCoverage, hourlyCosts, savingsPercentage) {
        if (!hourlyCosts || hourlyCosts.length === 0) {
            return { zone: 'building', zoneName: 'Building to baseline' };
        }

        const minCost = Math.min(...hourlyCosts);
        const baselineCost = hourlyCosts.reduce((sum, cost) => sum + cost, 0);
        const discountFactor = (1 - savingsPercentage / 100);

        // Calculate optimal coverage
        const optimalResult = calculateOptimalCoverage(hourlyCosts, savingsPercentage);
        const optimalCoverage = optimalResult.coverageUnits;

        // Calculate min-hourly savings baseline
        const minHourlySavings = minCost * hourlyCosts.length * (savingsPercentage / 100);

        // Calculate net savings at current coverage
        let commitmentCost = 0;
        let spilloverCost = 0;
        for (let i = 0; i < hourlyCosts.length; i++) {
            commitmentCost += currentCoverage * discountFactor;
            spilloverCost += Math.max(0, hourlyCosts[i] - currentCoverage);
        }
        const totalCost = commitmentCost + spilloverCost;
        const currentNetSavings = baselineCost - totalCost;
        const currentSavingsPercent = baselineCost > 0 ? (currentNetSavings / baselineCost) * 100 : 0;

        // Determine zone based on coverage and savings
        // Zone 5 (Red): Negative savings - losing money vs on-demand
        if (currentSavingsPercent <= 0) {
            return {
                zone: 'losing-money',
                zoneName: 'Worse than on-demand: Losing money',
                netSavings: currentNetSavings,
                savingsPercent: currentSavingsPercent
            };
        }

        // Zone 1 (Blue): Below min-hourly - building to baseline
        if (currentCoverage < minCost) {
            return {
                zone: 'building',
                zoneName: '0-Min: Building to baseline',
                netSavings: currentNetSavings,
                savingsPercent: currentSavingsPercent
            };
        }

        // Zone 2 (Green): Between min and optimal - gaining
        if (currentCoverage <= optimalCoverage) {
            return {
                zone: 'gaining',
                zoneName: 'Min → Optimal: Gaining',
                netSavings: currentNetSavings,
                savingsPercent: currentSavingsPercent
            };
        }

        // For zones 3 and 4, we need to check if savings dropped below min-hourly level
        // Zone 4 (Purple): Savings dropped below min-hourly baseline - very bad
        if (currentNetSavings < minHourlySavings) {
            return {
                zone: 'very-bad',
                zoneName: 'Below min-hourly: Very bad',
                netSavings: currentNetSavings,
                savingsPercent: currentSavingsPercent
            };
        }

        // Zone 3 (Orange): Past optimal but still above min-hourly - wasting
        return {
            zone: 'wasting',
            zoneName: 'Optimal → Min-hourly: Wasting',
            netSavings: currentNetSavings,
            savingsPercent: currentSavingsPercent
        };
    }

    /**
     * Get optimization suggestion with dollar values using zone-based logic
     * @param {number} currentCost - Current commitment in $/h
     * @param {number} optimalCost - Optimal commitment in $/h
     * @param {number} minCost - Minimum cost for percentage calculation
     * @param {number} additionalSavings - Additional savings gained by reaching optimal ($/h)
     * @param {Object} zoneInfo - Zone information from detectCoverageZone (optional)
     * @returns {Object} Suggestion with status and message
     */
    function getOptimizationSuggestionDollars(currentCost, optimalCost, minCost, additionalSavings = 0, zoneInfo = null) {
        const difference = Math.abs(currentCost - optimalCost);
        const percentDiff = minCost > 0 ? (difference / minCost) * 100 : 0;

        // Use zone-based status if zoneInfo provided
        let status = 'optimal';
        let message = '';
        let icon = '✅';

        if (zoneInfo && zoneInfo.zone) {
            // Map zones to status for backward compatibility with CSS
            const zoneToStatus = {
                'building': 'building',
                'gaining': 'gaining',
                'wasting': 'wasting',
                'very-bad': 'very-bad',
                'losing-money': 'losing-money'
            };
            status = zoneToStatus[zoneInfo.zone] || 'optimal';

            // Zone-specific messages and icons
            switch (zoneInfo.zone) {
                case 'building':
                    icon = '🔵';
                    message = `Building to baseline. Increase commitment by ${formatCurrency(difference)}/h to reach optimal coverage and unlock ${formatCurrency(additionalSavings)}/h more savings.`;
                    break;
                case 'gaining':
                    if (percentDiff <= 5) {
                        icon = '✅';
                        message = `At optimal! Maximizing savings while minimizing waste.`;
                    } else {
                        icon = '🟢';
                        message = `Gaining efficiency. Increase by ${formatCurrency(difference)}/h to reach optimal and unlock ${formatCurrency(additionalSavings)}/h more savings.`;
                    }
                    break;
                case 'wasting':
                    icon = '🟠';
                    message = `Over-committed. Decrease by ${formatCurrency(difference)}/h to optimal (${formatCurrency(optimalCost)}/h) to reduce waste.`;
                    break;
                case 'very-bad':
                    icon = '🟣';
                    message = `Severely over-committed. Savings dropped below min-hourly baseline. Decrease to ${formatCurrency(optimalCost)}/h immediately.`;
                    break;
                case 'losing-money':
                    icon = '🔴';
                    message = `LOSING MONEY vs on-demand! Commitment too high. Decrease to ${formatCurrency(optimalCost)}/h to stop losses.`;
                    break;
            }
        } else {
            // Fallback to old logic if no zone info
            if (percentDiff <= 5) {
                status = 'optimal';
                icon = '✅';
                message = `Commitment is optimal (within 5%). Current: ${formatCurrency(currentCost)}/h`;
            } else if (percentDiff <= 10) {
                status = 'warning';
                icon = '⚠️';
                if (currentCost < optimalCost) {
                    message = `Increase commitment by ${formatCurrency(difference)}/h to reach optimal coverage and unlock ${formatCurrency(additionalSavings)}/h more savings.`;
                } else {
                    message = `Decrease to ${formatCurrency(optimalCost)}/h (current: ${formatCurrency(currentCost)}/h) to reduce waste.`;
                }
            } else {
                status = 'danger';
                icon = '🔴';
                if (currentCost < optimalCost) {
                    message = `Increase commitment by ${formatCurrency(difference)}/h to reach optimal coverage and unlock ${formatCurrency(additionalSavings)}/h more savings.`;
                } else {
                    message = `Commitment significantly above optimal. Decrease to ${formatCurrency(optimalCost)}/h (current: ${formatCurrency(currentCost)}/h) to reduce waste.`;
                }
            }
        }

        return {
            status,
            icon,
            message,
            difference,
            recommendation: optimalCost,
            zone: zoneInfo ? zoneInfo.zone : null
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
        calculateSavingsCurve,
        getOptimizationSuggestion,
        getOptimizationSuggestionDollars,
        detectCoverageZone,
        formatCurrency,
        formatPercentage,
        calculateCoverageImpact
    };
})();

/**
 * Chart Manager
 * Manages Chart.js instances for load pattern and cost visualization
 */

const ChartManager = (function() {
    'use strict';

    let loadChart = null;
    let costChart = null;
    let savingsCurveChart = null;
    let currentHoverIndex = null;

    /**
     * Initialize the load pattern chart
     * @param {string} canvasId - Canvas element ID
     * @returns {Chart} Chart.js instance
     */
    function initLoadChart(canvasId) {
        const ctx = document.getElementById(canvasId);
        if (!ctx) {
            console.error(`Canvas element ${canvasId} not found`);
            return null;
        }

        // Destroy existing chart if it exists
        if (loadChart) {
            loadChart.destroy();
        }

        // Get current theme colors
        const themeColors = ColorThemes.getThemeColors();

        loadChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: generateTimeLabels(),
                datasets: [{
                    label: 'Compute Usage',
                    data: [],
                    borderColor: themeColors.loadPattern.border,
                    backgroundColor: themeColors.loadPattern.background,
                    borderWidth: 2,
                    fill: true,
                    tension: 0.4,
                    pointRadius: 0,
                    pointHoverRadius: 6,
                    pointHoverBackgroundColor: themeColors.loadPattern.border,
                    pointHoverBorderColor: '#ffffff',
                    pointHoverBorderWidth: 2
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    mode: 'index',
                    intersect: false
                },
                plugins: {
                    legend: {
                        display: false
                    },
                    tooltip: {
                        backgroundColor: 'rgba(26, 31, 58, 0.95)',
                        titleColor: '#00d4ff',
                        bodyColor: '#e0e6ed',
                        borderColor: '#4d9fff',
                        borderWidth: 1,
                        padding: 12,
                        displayColors: false,
                        callbacks: {
                            title: function(context) {
                                const hour = context[0].dataIndex;
                                return LoadPatterns.formatTimeLabel(hour);
                            },
                            label: function(context) {
                                return `Hourly Cost: ${CostCalculator.formatCurrency(context.parsed.y)}`;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        title: {
                            display: true,
                            text: 'Time (Weekly Cycle)',
                            color: '#e0e6ed',
                            font: { size: 12, weight: 'bold' }
                        },
                        ticks: {
                            color: '#8b95a8',
                            maxTicksLimit: 14,
                            autoSkip: false,
                            callback: function(value, index) {
                                return LoadPatterns.formatXAxisLabel(index);
                            }
                        },
                        grid: {
                            color: 'rgba(139, 149, 168, 0.1)',
                            drawBorder: false
                        }
                    },
                    y: {
                        title: {
                            display: true,
                            text: 'Hourly Cost ($)',
                            color: '#e0e6ed',
                            font: { size: 12, weight: 'bold' }
                        },
                        ticks: {
                            color: '#8b95a8',
                            callback: function(value) {
                                return '$' + value.toFixed(0);
                            }
                        },
                        grid: {
                            color: 'rgba(139, 149, 168, 0.1)',
                            drawBorder: false
                        },
                        beginAtZero: true
                    }
                }
            }
        });

        return loadChart;
    }

    /**
     * Initialize the cost comparison chart
     * @param {string} canvasId - Canvas element ID
     * @returns {Chart} Chart.js instance
     */
    function initCostChart(canvasId) {
        const ctx = document.getElementById(canvasId);
        if (!ctx) {
            console.error(`Canvas element ${canvasId} not found`);
            return null;
        }

        // Destroy existing chart if it exists
        if (costChart) {
            costChart.destroy();
        }

        // Get current theme colors
        const themeColors = ColorThemes.getThemeColors();

        costChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: generateTimeLabels(),
                datasets: [
                    {
                        label: 'Covered by SP (at discounted rate)',
                        data: [],
                        borderColor: themeColors.covered.border,
                        backgroundColor: themeColors.covered.background,
                        borderWidth: 0,
                        fill: 'origin',
                        tension: 0.4,
                        pointRadius: 0,
                        pointHoverRadius: 4,
                        order: 3
                    },
                    {
                        label: 'Spillover (at On-Demand rate)',
                        data: [],
                        borderColor: themeColors.spillover.border,
                        backgroundColor: themeColors.spillover.background,
                        borderWidth: 0,
                        fill: 0,  // Fill from dataset 0 (covered costs)
                        tension: 0.4,
                        pointRadius: 0,
                        pointHoverRadius: 4,
                        order: 2
                    },
                    {
                        label: 'Total On-Demand Cost (baseline)',
                        data: [],
                        borderColor: themeColors.baseline.border,
                        backgroundColor: themeColors.baseline.background,
                        borderWidth: 2,
                        borderDash: [5, 5],
                        fill: false,
                        tension: 0.4,
                        pointRadius: 0,
                        pointHoverRadius: 4,
                        order: 0
                    },
                    {
                        label: 'SP Commitment Level',
                        data: [],
                        borderColor: themeColors.commitment.border,
                        backgroundColor: themeColors.commitment.background,
                        borderWidth: 3,
                        borderDash: [10, 5],
                        fill: false,
                        tension: 0,
                        pointRadius: 0,
                        pointHoverRadius: 6,
                        order: 1
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    mode: 'index',
                    intersect: false
                },
                plugins: {
                    legend: {
                        display: true,
                        position: 'top',
                        labels: {
                            color: '#e0e6ed',
                            usePointStyle: true,
                            padding: 8,
                            font: { size: 11 }
                        }
                    },
                    tooltip: {
                        backgroundColor: 'rgba(26, 31, 58, 0.95)',
                        titleColor: '#00d4ff',
                        bodyColor: '#e0e6ed',
                        borderColor: '#4d9fff',
                        borderWidth: 1,
                        padding: 12,
                        callbacks: {
                            title: function(context) {
                                const hour = context[0].dataIndex;
                                return LoadPatterns.formatTimeLabel(hour);
                            },
                            label: function(context) {
                                const hour = context.dataIndex;
                                const breakdown = getCurrentHourlyBreakdown(hour);
                                if (!breakdown) return null;

                                const datasetIndex = context.datasetIndex;

                                // For spillover dataset (index 1), show actual spillover amount, not cumulative
                                if (datasetIndex === 1) {
                                    if (breakdown.spilloverCost === 0) return null;
                                    return `${context.dataset.label}: ${CostCalculator.formatCurrency(breakdown.spilloverCost)}`;
                                }

                                // For other datasets, show the value as is
                                const value = context.parsed.y;
                                if (value === 0 || value === null) return null;
                                return `${context.dataset.label}: ${CostCalculator.formatCurrency(value)}`;
                            },
                            footer: function(context) {
                                const hour = context[0].dataIndex;
                                const breakdown = getCurrentHourlyBreakdown(hour);
                                if (!breakdown) return '';

                                const lines = [
                                    '',
                                    `Usage: ${CostCalculator.formatCurrency(breakdown.onDemandCost)}/hour`,
                                    `Total with SP: ${CostCalculator.formatCurrency(breakdown.savingsPlanCost)}`,
                                    `Savings: ${CostCalculator.formatCurrency(breakdown.onDemandCost - breakdown.savingsPlanCost)}`
                                ];

                                return lines;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        title: {
                            display: true,
                            text: 'Time (Weekly Cycle)',
                            color: '#e0e6ed',
                            font: { size: 12, weight: 'bold' }
                        },
                        ticks: {
                            color: '#8b95a8',
                            maxTicksLimit: 14,
                            autoSkip: false,
                            callback: function(value, index) {
                                return LoadPatterns.formatXAxisLabel(index);
                            }
                        },
                        grid: {
                            color: 'rgba(139, 149, 168, 0.1)',
                            drawBorder: false
                        }
                    },
                    y: {
                        stacked: false,
                        title: {
                            display: true,
                            text: 'Hourly Cost ($)',
                            color: '#e0e6ed',
                            font: { size: 12, weight: 'bold' }
                        },
                        ticks: {
                            color: '#8b95a8',
                            callback: function(value) {
                                return '$' + value.toFixed(2);
                            }
                        },
                        grid: {
                            color: 'rgba(139, 149, 168, 0.1)',
                            drawBorder: false
                        },
                        beginAtZero: true
                    }
                }
            }
        });

        return costChart;
    }

    /**
     * Generate time labels for 168 hours
     * @returns {Array<string>} Time labels
     */
    function generateTimeLabels() {
        const labels = [];
        for (let i = 0; i < 168; i++) {
            labels.push(LoadPatterns.formatTimeLabel(i));
        }
        return labels;
    }

    /**
     * Update load chart with new data
     * @param {Array<number>} usageData - Scaled usage data (168 values)
     */
    function updateLoadChart(usageData) {
        if (!loadChart) return;

        loadChart.data.datasets[0].data = usageData;
        loadChart.update('none'); // No animation for smoother updates
    }

    /**
     * Update cost chart with cost breakdown
     * @param {Object} costResults - Results from CostCalculator
     */
    function updateCostChart(costResults) {
        if (!costChart) return;

        const { hourlyBreakdown, config } = costResults;
        const coverageUnits = config.coverageUnits;

        // Extract data for each series
        // Dataset 0: Covered cost (at savings plan rate) - from origin
        const coveredCosts = hourlyBreakdown.map(h => h.coveredCost);

        // Dataset 1: Spillover stacked on top (cumulative: covered + spillover)
        // This creates the stacking effect since fill is set to dataset 0
        const spilloverStackedCosts = hourlyBreakdown.map(h => h.coveredCost + h.spilloverCost);

        // Dataset 2: Total on-demand baseline (dashed line)
        const onDemandCosts = hourlyBreakdown.map(h => h.onDemandCost);

        // Dataset 3: Commitment level (horizontal line showing coverage in $/hr)
        // This represents the on-demand cost equivalent you're committing to cover
        const commitmentLine = new Array(168).fill(coverageUnits);

        // Update datasets
        costChart.data.datasets[0].data = coveredCosts;
        costChart.data.datasets[1].data = spilloverStackedCosts;
        costChart.data.datasets[2].data = onDemandCosts;
        costChart.data.datasets[3].data = commitmentLine;

        costChart.update('none');
    }

    /**
     * Sync hover effect from load chart to cost chart
     * @param {number} index - Hour index
     */
    function syncCostChartHover(index) {
        if (!costChart) return;

        // Trigger tooltip on cost chart
        costChart.setActiveElements([
            { datasetIndex: 0, index },
            { datasetIndex: 1, index },
            { datasetIndex: 2, index }
        ]);
        costChart.tooltip.setActiveElements([
            { datasetIndex: 0, index }
        ]);
        costChart.update('none');
    }

    /**
     * Sync hover effect from cost chart to load chart
     * @param {number} index - Hour index
     */
    function syncLoadChartHover(index) {
        if (!loadChart) return;

        loadChart.setActiveElements([
            { datasetIndex: 0, index }
        ]);
        loadChart.tooltip.setActiveElements([
            { datasetIndex: 0, index }
        ]);
        loadChart.update('none');
    }

    /**
     * Get hourly breakdown for tooltip
     * Stored in a closure to be accessible by tooltip callbacks
     */
    let currentCostResults = null;

    function setCurrentCostResults(results) {
        currentCostResults = results;
    }

    function getCurrentHourlyBreakdown(hour) {
        if (!currentCostResults || !currentCostResults.hourlyBreakdown) {
            return null;
        }
        return currentCostResults.hourlyBreakdown[hour];
    }

    /**
     * Reset hover synchronization
     */
    function resetHover() {
        currentHoverIndex = null;
    }

    /**
     * Get chart instances
     */
    function getCharts() {
        return {
            loadChart,
            costChart
        };
    }

    /**
     * Destroy all charts
     */
    function destroyCharts() {
        if (loadChart) {
            loadChart.destroy();
            loadChart = null;
        }
        if (costChart) {
            costChart.destroy();
            costChart = null;
        }
    }

    /**
     * Update chart colors based on current theme
     * @param {string} themeName - Optional theme name (uses current if not specified)
     */
    function updateChartColors(themeName = null) {
        const themeColors = ColorThemes.getThemeColors(themeName);

        // Update cost chart colors
        if (costChart) {
            costChart.data.datasets[0].borderColor = themeColors.covered.border;
            costChart.data.datasets[0].backgroundColor = themeColors.covered.background;

            costChart.data.datasets[1].borderColor = themeColors.spillover.border;
            costChart.data.datasets[1].backgroundColor = themeColors.spillover.background;

            costChart.data.datasets[2].borderColor = themeColors.baseline.border;
            costChart.data.datasets[2].backgroundColor = themeColors.baseline.background;

            costChart.data.datasets[3].borderColor = themeColors.commitment.border;
            costChart.data.datasets[3].backgroundColor = themeColors.commitment.background;

            costChart.update('none');
        }

        // Update load chart colors
        if (loadChart) {
            loadChart.data.datasets[0].borderColor = themeColors.loadPattern.border;
            loadChart.data.datasets[0].backgroundColor = themeColors.loadPattern.background;
            loadChart.update('none');
        }

        // Update savings curve chart colors
        if (savingsCurveChart) {
            savingsCurveChart.data.datasets[0].borderColor = themeColors.savingsCurve.building.border;
            savingsCurveChart.data.datasets[0].backgroundColor = themeColors.savingsCurve.building.background;

            savingsCurveChart.data.datasets[1].borderColor = themeColors.savingsCurve.gaining.border;
            savingsCurveChart.data.datasets[1].backgroundColor = themeColors.savingsCurve.gaining.background;

            savingsCurveChart.data.datasets[2].borderColor = themeColors.savingsCurve.wasting.border;
            savingsCurveChart.data.datasets[2].backgroundColor = themeColors.savingsCurve.wasting.background;

            savingsCurveChart.data.datasets[3].borderColor = themeColors.savingsCurve.veryBad.border;
            savingsCurveChart.data.datasets[3].backgroundColor = themeColors.savingsCurve.veryBad.background;

            savingsCurveChart.data.datasets[4].borderColor = themeColors.savingsCurve.losingMoney.border;
            savingsCurveChart.data.datasets[4].backgroundColor = themeColors.savingsCurve.losingMoney.background;

            savingsCurveChart.update('none');
        }
    }

    /**
     * Initialize the savings curve chart
     * @param {string} canvasId - Canvas element ID
     * @returns {Chart} Chart.js instance
     */
    function initSavingsCurveChart(canvasId) {
        const ctx = document.getElementById(canvasId);
        if (!ctx) {
            console.error(`Canvas element ${canvasId} not found`);
            return null;
        }

        // Destroy existing chart if it exists
        if (savingsCurveChart) {
            savingsCurveChart.destroy();
        }

        // Get current theme colors
        const themeColors = ColorThemes.getThemeColors();

        savingsCurveChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [
                    {
                        label: '0-Min: Building to baseline',
                        data: [],
                        borderColor: themeColors.savingsCurve.building.border,
                        backgroundColor: themeColors.savingsCurve.building.background,
                        borderWidth: 2,
                        fill: 'origin',
                        tension: 0.4,
                        pointRadius: 0,
                        pointHoverRadius: 8
                    },
                    {
                        label: 'Min → Optimal: Gaining',
                        data: [],
                        borderColor: themeColors.savingsCurve.gaining.border,
                        backgroundColor: themeColors.savingsCurve.gaining.background,
                        borderWidth: 2,
                        fill: 'origin',
                        tension: 0.4,
                        pointRadius: 0,
                        pointHoverRadius: 8
                    },
                    {
                        label: 'Optimal → Min-hourly: Wasting',
                        data: [],
                        borderColor: themeColors.savingsCurve.wasting.border,
                        backgroundColor: themeColors.savingsCurve.wasting.background,
                        borderWidth: 2,
                        fill: 'origin',
                        tension: 0.4,
                        pointRadius: 0,
                        pointHoverRadius: 8
                    },
                    {
                        label: 'Below min-hourly: Very bad',
                        data: [],
                        borderColor: themeColors.savingsCurve.veryBad.border,
                        backgroundColor: themeColors.savingsCurve.veryBad.background,
                        borderWidth: 2,
                        fill: 'origin',
                        tension: 0.4,
                        pointRadius: 0,
                        pointHoverRadius: 8
                    },
                    {
                        label: 'Worse than on-demand: Losing money',
                        data: [],
                        borderColor: themeColors.savingsCurve.losingMoney.border,
                        backgroundColor: themeColors.savingsCurve.losingMoney.background,
                        borderWidth: 2,
                        fill: 'origin',
                        tension: 0.4,
                        pointRadius: 0,
                        pointHoverRadius: 8
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    mode: 'nearest',
                    intersect: false,
                    axis: 'x'
                },
                hover: {
                    mode: 'nearest',
                    intersect: false
                },
                plugins: {
                    legend: {
                        display: false
                    },
                    tooltip: {
                        backgroundColor: 'rgba(26, 31, 58, 0.95)',
                        titleColor: '#00d4ff',
                        bodyColor: '#e0e6ed',
                        borderColor: '#4d9fff',
                        borderWidth: 1,
                        padding: 12,
                        mode: 'nearest',
                        intersect: false,
                        callbacks: {
                            title: function(context) {
                                const coverage = context[0].parsed.x;
                                const minCost = context[0].chart.$minCost || 0;
                                const percentOfMin = minCost > 0 ? (coverage / minCost * 100).toFixed(0) : 0;
                                return `Coverage: ${CostCalculator.formatCurrency(coverage)}/hour (${percentOfMin}% of min)`;
                            },
                            label: function(context) {
                                const savingsPercent = context.parsed.y;
                                const coverage = context.parsed.x;
                                const curveData = context.chart.$curveData || [];

                                // Find the data point closest to this coverage
                                const point = curveData.reduce((prev, curr) => {
                                    return Math.abs(curr.coverage - coverage) < Math.abs(prev.coverage - coverage) ? curr : prev;
                                });

                                const netSavingsDollars = point?.netSavings || 0;
                                const netSavingsMonthly = netSavingsDollars * 4.33; // Convert weekly to monthly
                                return `Savings: ${savingsPercent.toFixed(1)}% (${CostCalculator.formatCurrency(netSavingsMonthly)}/month)`;
                            },
                            afterLabel: function(context) {
                                const coverage = context.parsed.x;
                                const curveData = context.chart.$curveData || [];

                                // Find the data point closest to this coverage
                                const point = curveData.reduce((prev, curr) => {
                                    return Math.abs(curr.coverage - coverage) < Math.abs(prev.coverage - coverage) ? curr : prev;
                                });

                                if (!point) return null;

                                const extraSavings = point.extraSavings || 0;
                                const extraSavingsMonthly = extraSavings * 4.33; // Convert weekly to monthly

                                if (extraSavings > 0.01) {
                                    return `vs Optimal: +${CostCalculator.formatCurrency(extraSavingsMonthly)}/month`;
                                } else if (extraSavings < -0.01) {
                                    return `vs Optimal: ${CostCalculator.formatCurrency(extraSavingsMonthly)}/month`;
                                }
                                return 'At optimal';
                            },
                            footer: function(context) {
                                const savingsPercent = context[0].parsed.y;
                                if (savingsPercent < 0) {
                                    return '\n⚠️ Over-committed: Losing money vs on-demand';
                                }
                                return null;
                            }
                        }
                    },
                    annotation: {
                        annotations: {}
                    }
                },
                scales: {
                    x: {
                        type: 'linear',
                        min: 0,
                        title: {
                            display: true,
                            text: 'Coverage Level ($/hour)',
                            color: '#e0e6ed',
                            font: { size: 12, weight: 'bold' }
                        },
                        ticks: {
                            color: '#8b95a8',
                            callback: function(value) {
                                return '$' + value.toFixed(0);
                            }
                        },
                        grid: {
                            color: 'rgba(255, 255, 255, 0.05)'
                        }
                    },
                    y: {
                        type: 'linear',
                        title: {
                            display: true,
                            text: 'Net Savings (% of baseline on-demand cost)',
                            color: '#e0e6ed',
                            font: { size: 12, weight: 'bold' }
                        },
                        ticks: {
                            color: '#8b95a8',
                            callback: function(value) {
                                return value.toFixed(0) + '%';
                            }
                        },
                        grid: {
                            color: function(context) {
                                // Highlight zero line
                                if (context.tick.value === 0) {
                                    return 'rgba(255, 255, 255, 0.3)';
                                }
                                return 'rgba(255, 255, 255, 0.05)';
                            },
                            lineWidth: function(context) {
                                if (context.tick.value === 0) {
                                    return 2;
                                }
                                return 1;
                            }
                        }
                    }
                }
            }
        });

        return savingsCurveChart;
    }

    /**
     * Update savings curve chart with new data
     * @param {Array} curveData - Savings curve data points
     * @param {number} minHourlySavings - Baseline savings at min-hourly (dollars)
     * @param {number} optimalCoverage - Optimal coverage in $/hour
     * @param {number} minCost - Min-hourly cost
     * @param {number} maxCost - Max-hourly cost
     * @param {number} baselineCost - Total baseline on-demand cost
     * @param {number} currentCoverage - Current actual coverage in $/hour (optional)
     */
    function updateSavingsCurveChart(curveData, minHourlySavings, optimalCoverage, minCost, maxCost, baselineCost, currentCoverage) {
        if (!savingsCurveChart) return;

        // Store values for tooltip access
        savingsCurveChart.$minHourlySavings = minHourlySavings;
        savingsCurveChart.$minCost = minCost;
        savingsCurveChart.$maxCost = maxCost;
        savingsCurveChart.$curveData = curveData; // Store full curve data for tooltip access

        // Set x-axis max to max-hourly cost
        savingsCurveChart.options.scales.x.max = maxCost;

        // Find indices for transitions
        let minCostIndex = -1;
        let optimalIndex = -1;
        let breakevenIndex = -1;

        for (let i = 0; i < curveData.length; i++) {
            // Find min-hourly crossing
            if (curveData[i].coverage >= minCost && minCostIndex === -1) {
                minCostIndex = i;
            }
            // Find optimal crossing
            if (curveData[i].coverage >= optimalCoverage && optimalIndex === -1) {
                optimalIndex = i;
            }
        }

        // Ensure indices are valid
        if (minCostIndex === -1) minCostIndex = 0;
        if (optimalIndex === -1) optimalIndex = minCostIndex;

        // Calculate min-hourly savings percentage
        const minHourlySavingsPercent = baselineCost > 0 ? (minHourlySavings / baselineCost) * 100 : 0;

        // Find where savings decline back to min-hourly level (not optimal anymore)
        let minHourlyReturnIndex = -1;
        for (let i = optimalIndex + 1; i < curveData.length; i++) {
            const point = curveData[i];
            if (point.netSavings <= minHourlySavings) {
                minHourlyReturnIndex = i;
                break;
            }
        }

        // Find where savings go to 0 or negative (worse than on-demand)
        for (let i = optimalIndex + 1; i < curveData.length; i++) {
            if (curveData[i].savingsPercent <= 0) {
                breakevenIndex = i;
                break;
            }
        }

        // Set defaults if not found
        if (breakevenIndex === -1) breakevenIndex = curveData.length - 1;

        console.log('Dataset boundaries:', {
            minCostIndex,
            optimalIndex,
            minHourlyReturnIndex,
            breakevenIndex,
            totalPoints: curveData.length,
            minHourlySavingsPercent: minHourlySavingsPercent.toFixed(2) + '%',
            declineDetected: minHourlyReturnIndex !== -1
        });

        // Split data into five datasets based on coverage ranges
        // Blue: 0 to min-hourly (building up)
        const dataset1 = curveData.slice(0, minCostIndex + 1).map(d => ({ x: d.coverage, y: d.savingsPercent }));

        // Green: min-hourly to optimal (or to end if no decline detected)
        const greenEndIndex = minHourlyReturnIndex !== -1 ? minHourlyReturnIndex : curveData.length - 1;
        const dataset2 = curveData.slice(minCostIndex, Math.min(optimalIndex + 1, greenEndIndex + 1)).map(d => ({ x: d.coverage, y: d.savingsPercent }));

        // If green extends beyond optimal (no decline), extend it all the way
        const dataset2Extended = minHourlyReturnIndex === -1 && optimalIndex < curveData.length - 1
            ? curveData.slice(minCostIndex, curveData.length).map(d => ({ x: d.coverage, y: d.savingsPercent }))
            : dataset2;

        // Orange: optimal to min-hourly-return (only if decline detected)
        const dataset3 = minHourlyReturnIndex !== -1 && optimalIndex < minHourlyReturnIndex
            ? curveData.slice(optimalIndex, minHourlyReturnIndex + 1).map(d => ({ x: d.coverage, y: d.savingsPercent }))
            : [];

        // Purple: min-hourly-return to breakeven (only if we found min-hourly return point)
        const dataset4 = minHourlyReturnIndex !== -1 && minHourlyReturnIndex < breakevenIndex
            ? curveData.slice(minHourlyReturnIndex, breakevenIndex + 1).map(d => ({ x: d.coverage, y: d.savingsPercent }))
            : [];

        // Red: beyond breakeven (negative savings, losing money)
        const dataset5 = breakevenIndex < curveData.length - 1 && curveData[breakevenIndex].savingsPercent <= 0
            ? curveData.slice(breakevenIndex).map(d => ({ x: d.coverage, y: d.savingsPercent }))
            : [];

        console.log('Dataset sizes:', {
            blue: dataset1.length,
            green: dataset2.length,
            orange: dataset3.length,
            purple: dataset4.length,
            red: dataset5.length
        });

        savingsCurveChart.data.datasets[0].data = dataset1;
        savingsCurveChart.data.datasets[1].data = dataset2Extended;
        savingsCurveChart.data.datasets[2].data = dataset3;
        savingsCurveChart.data.datasets[3].data = dataset4;
        savingsCurveChart.data.datasets[4].data = dataset5;

        // Find breakeven point (where savings return to 0%)
        let breakevenCoverage = null;
        for (let i = curveData.length - 1; i >= 0; i--) {
            if (curveData[i].savingsPercent >= 0) {
                breakevenCoverage = curveData[i].coverage;
                break;
            }
        }

        // Build annotations - only show current coverage line
        const annotations = {};

        // Add current coverage line if provided and within range
        if (currentCoverage && currentCoverage > 0 && currentCoverage <= maxCost) {
            // Calculate percentage of min-hourly
            const percentOfMin = minCost > 0 ? (currentCoverage / minCost * 100).toFixed(0) : 0;

            annotations.currentLine = {
                type: 'line',
                xMin: currentCoverage,
                xMax: currentCoverage,
                borderColor: 'rgba(0, 212, 255, 0.9)',
                borderWidth: 3,
                borderDash: [10, 5],
                label: {
                    display: true,
                    content: `📍 ${CostCalculator.formatCurrency(currentCoverage)}/hr (${percentOfMin}% of min)`,
                    position: 'start',
                    backgroundColor: 'rgba(0, 212, 255, 0.9)',
                    color: '#1a1f3a',
                    font: { size: 13, weight: 'bold' }
                }
            };
        }

        savingsCurveChart.options.plugins.annotation.annotations = annotations;

        savingsCurveChart.update();
    }

    // Public API
    return {
        initLoadChart,
        initCostChart,
        initSavingsCurveChart,
        updateLoadChart,
        updateCostChart,
        updateSavingsCurveChart,
        setCurrentCostResults,
        updateChartColors,
        resetHover,
        getCharts,
        destroyCharts
    };
})();

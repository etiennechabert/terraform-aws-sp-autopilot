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
                                if (!breakdown) return [];

                                const lines = [
                                    '',
                                    `Usage: ${CostCalculator.formatCurrency(breakdown.onDemandCost)}/h`,
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
     * Generate time labels for N hours
     * @param {number} count - Number of hours
     * @returns {Array<string>} Time labels
     */
    function generateTimeLabels(count = 168) {
        const labels = [];
        for (let i = 0; i < count; i++) {
            labels.push(LoadPatterns.formatTimeLabel(i));
        }
        return labels;
    }

    /**
     * Update load chart with new data
     * @param {Array<number>} usageData - Scaled usage data
     */
    function updateLoadChart(usageData) {
        if (!loadChart) return;

        if (loadChart.data.labels.length !== usageData.length) {
            loadChart.data.labels = generateTimeLabels(usageData.length);
        }
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

        // Dataset 3: Commitment level (horizontal line showing coverage in $/h)
        // This represents the on-demand cost equivalent you're committing to cover
        const numHours = hourlyBreakdown.length;
        const commitmentLine = new Array(numHours).fill(coverageUnits);

        if (costChart.data.labels.length !== numHours) {
            costChart.data.labels = generateTimeLabels(numHours);
        }

        // Update datasets
        costChart.data.datasets[0].data = coveredCosts;
        costChart.data.datasets[1].data = spilloverStackedCosts;
        costChart.data.datasets[2].data = onDemandCosts;
        costChart.data.datasets[3].data = commitmentLine;

        costChart.update('none');
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
        if (!currentCostResults?.hourlyBreakdown) {
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
                                const commitment = context[0].parsed.x;
                                const curveData = context[0].chart.$curveData || [];

                                // Find the data point for this commitment to get the coverage
                                const point = curveData.reduce((prev, curr) => {
                                    return Math.abs(curr.commitment - commitment) < Math.abs(prev.commitment - commitment) ? curr : prev;
                                });

                                const coverage = point?.coverage || 0;
                                const minCost = context[0].chart.$minCost || 0;
                                const percentOfMin = minCost > 0 ? (coverage / minCost * 100).toFixed(1) : 0;
                                return `${percentOfMin}% of min-hourly`;
                            },
                            label: function(context) {
                                const savingsPercent = context.parsed.y;
                                return `Savings: ${savingsPercent.toFixed(1)}%`;
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
                            text: 'Commitment Level ($/h)',
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
                        position: 'left',
                        title: {
                            display: false
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
                    },
                    y1: {
                        type: 'linear',
                        position: 'right',
                        title: {
                            display: false
                        },
                        ticks: {
                            color: '#8b95a8',
                            callback: function(value) {
                                return '$' + value.toFixed(2);
                            }
                        },
                        grid: {
                            drawOnChartArea: false
                        }
                    }
                }
            }
        });

        return savingsCurveChart;
    }

    function toXY(d) {
        return { x: d.commitment, y: d.savingsPercent };
    }

    function findCurveIndices(curveData, minCost, minHourlySavings) {
        let minCostIndex = -1;
        let optimalIndex = -1;
        let breakevenIndex = -1;
        let maxSavings = -Infinity;

        for (let i = 0; i < curveData.length; i++) {
            if (curveData[i].coverage >= minCost && minCostIndex === -1) {
                minCostIndex = i;
            }
            if (curveData[i].netSavings > maxSavings) {
                maxSavings = curveData[i].netSavings;
                optimalIndex = i;
            }
        }

        if (minCostIndex === -1) minCostIndex = 0;
        if (optimalIndex === -1) optimalIndex = minCostIndex;

        let minHourlyReturnIndex = -1;
        for (let i = optimalIndex + 1; i < curveData.length; i++) {
            if (curveData[i].netSavings <= minHourlySavings) {
                minHourlyReturnIndex = i;
                break;
            }
        }

        for (let i = optimalIndex + 1; i < curveData.length; i++) {
            if (curveData[i].savingsPercent <= 0) {
                breakevenIndex = i;
                break;
            }
        }

        if (breakevenIndex === -1) breakevenIndex = curveData.length - 1;

        return { minCostIndex, optimalIndex, breakevenIndex, minHourlyReturnIndex };
    }

    function splitCurveDatasets(curveData, indices) {
        const { minCostIndex, optimalIndex, breakevenIndex, minHourlyReturnIndex } = indices;

        const dataset1 = curveData.slice(0, minCostIndex + 1).map(toXY);

        const dataset2 = curveData.slice(minCostIndex, Math.min(optimalIndex + 1, (minHourlyReturnIndex === -1 ? curveData.length - 1 : minHourlyReturnIndex) + 1)).map(toXY);

        const dataset2Extended = minHourlyReturnIndex === -1 && optimalIndex < curveData.length - 1
            ? curveData.slice(minCostIndex, curveData.length).map(toXY)
            : dataset2;

        const dataset3 = minHourlyReturnIndex !== -1 && optimalIndex < minHourlyReturnIndex
            ? curveData.slice(optimalIndex, minHourlyReturnIndex + 1).map(toXY)
            : [];

        const dataset4 = minHourlyReturnIndex !== -1 && minHourlyReturnIndex < breakevenIndex
            ? curveData.slice(minHourlyReturnIndex, breakevenIndex + 1).map(toXY)
            : [];

        const dataset5 = breakevenIndex < curveData.length - 1 && curveData[breakevenIndex].savingsPercent <= 0
            ? curveData.slice(breakevenIndex).map(toXY)
            : [];

        return [dataset1, dataset2Extended, dataset3, dataset4, dataset5];
    }

    function buildCoverageAnnotation(currentCoverage, maxCost, minCost, savingsPercentage) {
        if (!currentCoverage || currentCoverage <= 0 || currentCoverage > maxCost) {
            return {};
        }

        const currentCommitment = commitmentFromCoverage(currentCoverage, savingsPercentage || 0);
        const percentOfMin = minCost > 0 ? (currentCoverage / minCost * 100).toFixed(1) : '0.0';

        return {
            currentLine: {
                type: 'line',
                xMin: currentCommitment,
                xMax: currentCommitment,
                borderColor: 'rgba(0, 212, 255, 0.9)',
                borderWidth: 3,
                borderDash: [10, 5],
                label: {
                    display: true,
                    content: `📍 ${CostCalculator.formatCurrency(currentCommitment)}/h (${percentOfMin}% of min)`,
                    position: 'start',
                    backgroundColor: 'rgba(0, 212, 255, 0.9)',
                    color: '#1a1f3a',
                    font: { size: 13, weight: 'bold' }
                }
            }
        };
    }

    function updateSavingsCurveChart(opts) {
        const { curveData, minHourlySavings, minCost, maxCost, baselineCost, currentCoverage, savingsPercentage, numHours } = opts;
        if (!savingsCurveChart) return;

        savingsCurveChart.$minHourlySavings = minHourlySavings;
        savingsCurveChart.$minCost = minCost;
        savingsCurveChart.$maxCost = maxCost;
        savingsCurveChart.$curveData = curveData;

        const maxCommitment = curveData.length > 0 ? curveData.at(-1).commitment : maxCost;
        savingsCurveChart.options.scales.x.max = maxCommitment;

        const baselineHourly = baselineCost / numHours;
        const savingsPercentages = curveData.map(d => d.savingsPercent);
        let minSavingsPercent = Math.min(...savingsPercentages);
        let maxSavingsPercent = Math.max(...savingsPercentages);

        if (maxSavingsPercent - minSavingsPercent < 0.1) {
            const midpoint = (minSavingsPercent + maxSavingsPercent) / 2;
            minSavingsPercent = midpoint - 0.05;
            maxSavingsPercent = midpoint + 0.05;
        }

        savingsCurveChart.options.scales.y1.min = baselineHourly * (minSavingsPercent / 100);
        savingsCurveChart.options.scales.y1.max = baselineHourly * (maxSavingsPercent / 100);

        const indices = findCurveIndices(curveData, minCost, minHourlySavings);
        const datasets = splitCurveDatasets(curveData, indices);

        for (let i = 0; i < datasets.length; i++) {
            savingsCurveChart.data.datasets[i].data = datasets[i];
        }

        savingsCurveChart.options.plugins.annotation.annotations = buildCoverageAnnotation(currentCoverage, maxCost, minCost, savingsPercentage);
        savingsCurveChart.update('none');
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

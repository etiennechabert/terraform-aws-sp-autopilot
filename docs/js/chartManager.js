/**
 * Chart Manager
 * Manages Chart.js instances for load pattern and cost visualization
 */

const ChartManager = (function() {
    'use strict';

    let loadChart = null;
    let costChart = null;
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
                            callback: function(value, index) {
                                // Show tick every 12 hours
                                if (index % 12 === 0) {
                                    return LoadPatterns.formatTimeLabel(index);
                                }
                                return '';
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
                },
                onHover: function(event, activeElements) {
                    if (activeElements.length > 0) {
                        const index = activeElements[0].index;
                        if (currentHoverIndex !== index) {
                            currentHoverIndex = index;
                            syncCostChartHover(index);
                        }
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
                            callback: function(value, index) {
                                if (index % 12 === 0) {
                                    return LoadPatterns.formatTimeLabel(index);
                                }
                                return '';
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
                },
                onHover: function(event, activeElements) {
                    if (activeElements.length > 0) {
                        const index = activeElements[0].index;
                        if (currentHoverIndex !== index) {
                            currentHoverIndex = index;
                            syncLoadChartHover(index);
                        }
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
    }

    // Public API
    return {
        initLoadChart,
        initCostChart,
        updateLoadChart,
        updateCostChart,
        setCurrentCostResults,
        updateChartColors,
        resetHover,
        getCharts,
        destroyCharts
    };
})();

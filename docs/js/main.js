/**
 * Main Application
 * Orchestrates the AWS Savings Plan Simulator
 */

(function() {
    'use strict';

    // Application state
    let appState = {
        pattern: 'ecommerce',
        minCost: 15,          // Min $/hour
        maxCost: 100,         // Max $/hour (peak)
        coverageCost: 50,     // Coverage commitment in $/hour
        savingsPercentage: 30,
        onDemandRate: 0.10,
        currentLoadPattern: [],
        customCurve: null
    };

    let currentCostResults = null;

    /**
     * Initialize the application
     */
    function init() {
        console.log('Initializing AWS Savings Plan Simulator...');

        // Check for URL state
        const urlState = URLState.decodeState();
        if (urlState) {
            console.log('Restoring state from URL:', urlState);

            // Check if we have usage data from reporter
            if (urlState.usageData) {
                console.log('Loading real usage data from reporter');
                loadUsageData(urlState.usageData);
            } else {
                appState = { ...appState, ...urlState };
            }
        }

        // Initialize charts
        ChartManager.initLoadChart('load-chart');
        ChartManager.initCostChart('cost-chart');
        ChartManager.initSavingsCurveChart('savings-curve-chart');

        // Setup event listeners
        setupEventListeners();

        // Initialize UI from state
        updateUIFromState();

        // Generate initial pattern and calculate costs
        updateLoadPattern();
        calculateAndUpdateCosts();

        console.log('Initialization complete');
    }

    /**
     * Load real usage data from reporter
     * @param {Object} usageData - Usage data from reporter
     */
    function loadUsageData(usageData) {
        console.log('Processing usage data:', usageData);

        const hourlyCosts = usageData.hourly_costs;
        const stats = usageData.stats;

        // Extract min/max from actual data
        const minCost = Math.min(...hourlyCosts);
        const maxCost = Math.max(...hourlyCosts);

        // Create normalized curve (0-100) from real costs
        const range = maxCost - minCost;
        const customCurve = hourlyCosts.map(cost => {
            if (range === 0) return 50; // All same value
            return ((cost - minCost) / range) * 100;
        });

        // Validate optimal coverage calculation (Python vs JavaScript)
        // Round to 2 decimals to avoid excessive precision in UI
        const savingsPercentage = Math.round((usageData.savings_percentage || 30) * 100) / 100;
        if (usageData.optimal_from_python && Object.keys(usageData.optimal_from_python).length > 0) {
            validateOptimalCoverage(hourlyCosts, usageData.optimal_from_python, savingsPercentage);
        }

        // Use current coverage from user's actual commitment, or default to min-hourly
        const currentCoverage = usageData.current_coverage || minCost;

        // Update app state with real data
        appState = {
            ...appState,
            pattern: 'custom',
            minCost: minCost,
            maxCost: maxCost,
            coverageCost: currentCoverage,  // Set to user's actual current coverage
            customCurve: customCurve,
            savingsPercentage: savingsPercentage,  // Use actual discount from user's SPs
            usageDataLoaded: true,
            usageData: usageData,  // Store full usage data for banner
            usageStats: stats,
            currentCoverage: currentCoverage,
            optimalFromPython: usageData.optimal_from_python
        };

        // Show indicator that real data is loaded
        showUsageDataBanner();
    }

    /**
     * Validate that Python and JavaScript calculate the same optimal coverage
     * @param {Array<number>} hourlyCosts - Hourly costs from reporter
     * @param {Object} pythonResult - Optimal coverage calculated by Python
     * @param {number} savingsPercentage - Actual savings percentage from user's SPs
     */
    function validateOptimalCoverage(hourlyCosts, pythonResult, savingsPercentage) {
        // Calculate using JavaScript implementation with the same savings percentage
        const jsResult = CostCalculator.calculateOptimalCoverage(hourlyCosts, savingsPercentage);

        // Compare coverage values (allow 1% tolerance for floating point differences)
        const pythonCoverage = pythonResult.coverage_hourly || 0;
        const jsCoverage = jsResult.coverageUnits || 0;
        const difference = Math.abs(pythonCoverage - jsCoverage);
        const tolerance = Math.max(pythonCoverage, jsCoverage) * 0.01; // 1% tolerance

        if (difference > tolerance) {
            console.warn('⚠️ Mismatch detected between Python and JavaScript optimal coverage calculations!');
            console.warn(`Python: $${pythonCoverage.toFixed(2)}/hr`);
            console.warn(`JavaScript: $${jsCoverage.toFixed(2)}/hr`);
            console.warn(`Difference: $${difference.toFixed(2)}/hr`);

            showMismatchWarning(pythonCoverage, jsCoverage);
        } else {
            console.log('✓ Python and JavaScript optimal coverage calculations match');
            console.log(`Optimal: $${jsCoverage.toFixed(2)}/hr`);
        }
    }

    /**
     * Show warning banner when Python and JavaScript calculations mismatch
     * @param {number} pythonValue - Python calculated value
     * @param {number} jsValue - JavaScript calculated value
     */
    function showMismatchWarning(pythonValue, jsValue) {
        const header = document.querySelector('.header-content');
        if (!header) return;

        const warning = document.createElement('div');
        warning.className = 'mismatch-warning';
        warning.innerHTML = `
            <div class="warning-content">
                <span class="warning-icon">⚠️</span>
                <span class="warning-text">
                    <strong>Algorithm Mismatch Detected</strong><br>
                    Python calculated: $${pythonValue.toFixed(2)}/hr | JavaScript calculated: $${jsValue.toFixed(2)}/hr<br>
                    <small>The Python and JavaScript implementations may be out of sync. Please report this issue.</small>
                </span>
            </div>
        `;

        header.appendChild(warning);
    }

    /**
     * Show banner indicating real usage data is loaded
     */
    function showUsageDataBanner() {
        const header = document.querySelector('.header-content');
        if (!header) return;

        const spType = appState.usageDataLoaded && appState.usageData?.sp_type
            ? appState.usageData.sp_type
            : 'All Types';

        const savingsPct = appState.savingsPercentage || 30;

        const banner = document.createElement('div');
        banner.className = 'usage-data-banner';
        banner.innerHTML = `
            <div class="banner-content">
                <span class="banner-icon">📊</span>
                <span class="banner-text">
                    <strong>Real Usage Data Loaded</strong> - ${spType} Savings Plans<br>
                    <small>Using your actual ${savingsPct.toFixed(1)}% discount rate</small>
                </span>
            </div>
        `;

        header.appendChild(banner);
    }

    /**
     * Setup all event listeners
     */
    function setupEventListeners() {
        // Pattern selector
        const patternSelect = document.getElementById('pattern-select');
        if (patternSelect) {
            patternSelect.value = appState.pattern;
            patternSelect.addEventListener('change', handlePatternChange);
        }

        // Min cost input
        const minCostInput = document.getElementById('min-cost');
        if (minCostInput) {
            minCostInput.value = appState.minCost;
            minCostInput.addEventListener('input', handleMinCostChange);
        }

        // Max cost input
        const maxCostInput = document.getElementById('max-cost');
        if (maxCostInput) {
            maxCostInput.value = appState.maxCost;
            maxCostInput.addEventListener('input', handleMaxCostChange);
        }

        // Coverage slider
        const coverageSlider = document.getElementById('coverage-slider');
        if (coverageSlider) {
            // Set slider max to match maxCost
            coverageSlider.max = appState.maxCost;
            // Set step to 1% of max cost
            coverageSlider.step = appState.maxCost / 100;
            coverageSlider.value = appState.coverageCost;
            coverageSlider.addEventListener('input', handleCoverageChange);
        }

        // Savings percentage slider
        const savingsSlider = document.getElementById('savings-percentage');
        if (savingsSlider) {
            savingsSlider.value = appState.savingsPercentage;
            savingsSlider.addEventListener('input', handleSavingsChange);
        }

        // On-demand rate input (advanced)
        const onDemandRateInput = document.getElementById('on-demand-rate');
        if (onDemandRateInput) {
            onDemandRateInput.value = appState.onDemandRate;
            onDemandRateInput.addEventListener('input', handleOnDemandRateChange);
        }

        // Share button
        const shareButton = document.getElementById('share-button');
        if (shareButton) {
            shareButton.addEventListener('click', handleShare);
        }

        // Toggle load pattern section
        const toggleLoadPatternButton = document.getElementById('toggle-load-pattern');
        if (toggleLoadPatternButton) {
            toggleLoadPatternButton.addEventListener('click', handleToggleLoadPattern);
        }

        // Color theme selector
        const colorThemeSelect = document.getElementById('color-theme');
        if (colorThemeSelect) {
            colorThemeSelect.addEventListener('change', handleColorThemeChange);
        }

        // Clickable optimal suggestion (applies optimal coverage when clicked)
        const optimalSuggestion = document.getElementById('optimal-suggestion');
        if (optimalSuggestion) {
            optimalSuggestion.addEventListener('click', handleApplyOptimal);
        }
    }

    /**
     * Update UI elements from current state
     */
    function updateUIFromState() {
        // Pattern selector
        const patternSelect = document.getElementById('pattern-select');
        if (patternSelect) {
            patternSelect.value = appState.pattern;
        }

        // Min cost
        const minCostInput = document.getElementById('min-cost');
        if (minCostInput) {
            minCostInput.value = appState.minCost;
        }

        // Max cost
        const maxCostInput = document.getElementById('max-cost');
        if (maxCostInput) {
            maxCostInput.value = appState.maxCost;
        }

        // Coverage slider
        const coverageSlider = document.getElementById('coverage-slider');
        if (coverageSlider) {
            coverageSlider.max = appState.maxCost;
            coverageSlider.step = appState.maxCost / 100;
            coverageSlider.value = appState.coverageCost;
        }
        updateCoverageDisplay(appState.coverageCost);

        // Savings percentage slider
        const savingsSlider = document.getElementById('savings-percentage');
        if (savingsSlider) {
            savingsSlider.value = appState.savingsPercentage;
        }
        updateSavingsDisplay(appState.savingsPercentage);

        // On-demand rate
        const onDemandRateInput = document.getElementById('on-demand-rate');
        if (onDemandRateInput) {
            onDemandRateInput.value = appState.onDemandRate;
        }
    }

    /**
     * Handle pattern type change
     */
    function handlePatternChange(event) {
        appState.pattern = event.target.value;

        // If switching to custom and we don't have a custom curve, copy current pattern
        if (appState.pattern === 'custom' && !appState.customCurve) {
            appState.customCurve = [...appState.currentLoadPattern];
        }

        updateLoadPattern();
        calculateAndUpdateCosts();
        URLState.debouncedUpdateURL(appState);
    }

    /**
     * Handle min cost change
     */
    function handleMinCostChange(event) {
        const value = parseFloat(event.target.value);
        if (!isNaN(value) && value >= 0 && value <= 10000) {
            appState.minCost = value;
            if (appState.minCost > appState.maxCost) {
                appState.maxCost = appState.minCost;
                const maxCostInput = document.getElementById('max-cost');
                if (maxCostInput) maxCostInput.value = appState.maxCost;
            }
            updateLoadPattern();
            calculateAndUpdateCosts();
            URLState.debouncedUpdateURL(appState);
        }
    }

    /**
     * Handle max cost change
     */
    function handleMaxCostChange(event) {
        const value = parseFloat(event.target.value);
        if (!isNaN(value) && value > 0 && value <= 10000) {
            appState.maxCost = value;
            if (appState.maxCost < appState.minCost) {
                appState.minCost = appState.maxCost;
                const minCostInput = document.getElementById('min-cost');
                if (minCostInput) minCostInput.value = appState.minCost;
            }

            // Update coverage slider max and step
            const coverageSlider = document.getElementById('coverage-slider');
            if (coverageSlider) {
                coverageSlider.max = appState.maxCost;
                coverageSlider.step = appState.maxCost / 100; // 1% of max cost
                // Cap coverage if it exceeds new max
                if (appState.coverageCost > appState.maxCost) {
                    appState.coverageCost = appState.maxCost;
                    coverageSlider.value = appState.coverageCost;
                    updateCoverageDisplay(appState.coverageCost);
                }
            }

            updateLoadPattern();
            calculateAndUpdateCosts();
            URLState.debouncedUpdateURL(appState);
        }
    }

    /**
     * Handle coverage level change
     */
    function handleCoverageChange(event) {
        const value = parseFloat(event.target.value);
        if (!isNaN(value) && value >= 0 && value <= appState.maxCost) {
            appState.coverageCost = value;
            updateCoverageDisplay(value);
            calculateAndUpdateCosts();
            URLState.debouncedUpdateURL(appState);
        }
    }

    /**
     * Handle savings percentage change
     */
    function handleSavingsChange(event) {
        const value = parseInt(event.target.value, 10);
        if (!isNaN(value) && value >= 0 && value <= 99) {
            appState.savingsPercentage = value;
            updateSavingsDisplay(value);
            calculateAndUpdateCosts();
            URLState.debouncedUpdateURL(appState);
        }
    }

    /**
     * Handle on-demand rate change
     */
    function handleOnDemandRateChange(event) {
        const value = parseFloat(event.target.value);
        if (!isNaN(value) && value > 0 && value <= 10) {
            appState.onDemandRate = value;
            updateSavingsDisplay(appState.savingsPercentage);
            calculateAndUpdateCosts();
            URLState.debouncedUpdateURL(appState);
        }
    }

    /**
     * Handle share button click
     */
    async function handleShare() {
        // Ensure URL is updated with current state (bypass debounce)
        URLState.updateURL(appState);

        const success = await URLState.copyURLToClipboard();

        if (success) {
            showToast('Configuration URL copied to clipboard!');
        } else {
            showToast('Failed to copy URL. Please copy manually from address bar.', 'error');
        }
    }

    /**
     * Handle apply optimal coverage button click
     */
    function handleApplyOptimal() {
        if (!currentCostResults || !currentCostResults.optimalCoverage) {
            showToast('Unable to apply optimal coverage. Please try again.', 'error');
            return;
        }

        // Get optimal coverage in $/hour
        const optimalCoverageCost = currentCostResults.optimalCoverage.coverageUnits;

        // Update state
        appState.coverageCost = optimalCoverageCost;

        // Update slider
        const coverageSlider = document.getElementById('coverage-slider');
        if (coverageSlider) {
            coverageSlider.value = optimalCoverageCost;
        }

        // Update display
        updateCoverageDisplay(optimalCoverageCost);

        // Recalculate
        calculateAndUpdateCosts();

        // Update URL
        URLState.debouncedUpdateURL(appState);

        // Show success message
        showToast(`Optimal coverage applied: ${CostCalculator.formatCurrency(optimalCoverageCost)}/hour`);
    }

    /**
     * Handle toggle load pattern section
     */
    function handleToggleLoadPattern() {
        const content = document.getElementById('load-pattern-content');
        const button = document.getElementById('toggle-load-pattern');

        if (!content || !button) return;

        // Toggle collapsed class
        content.classList.toggle('collapsed');
        button.classList.toggle('collapsed');
    }

    /**
     * Handle color theme change
     */
    function handleColorThemeChange(event) {
        const themeName = event.target.value;

        // Update theme in ColorThemes module
        ColorThemes.setTheme(themeName);

        // Update all chart colors
        ChartManager.updateChartColors(themeName);

        // Show toast notification
        const themeColors = ColorThemes.getThemeColors(themeName);
        showToast(`Color theme changed to: ${themeColors.name || themeName}`);
    }

    /**
     * Update load pattern based on current state
     */
    function updateLoadPattern() {
        // Generate or retrieve pattern
        let normalizedPattern;

        if (appState.pattern === 'custom' && appState.customCurve) {
            normalizedPattern = appState.customCurve;
        } else {
            normalizedPattern = LoadPatterns.generatePattern(appState.pattern);
        }

        appState.currentLoadPattern = normalizedPattern;

        // Find the actual min/max in the pattern
        const patternMin = Math.min(...normalizedPattern);
        const patternMax = Math.max(...normalizedPattern);
        const patternRange = patternMax - patternMin;

        // Scale pattern so its min = minCost and its max = maxCost
        const costRange = appState.maxCost - appState.minCost;
        const costPattern = normalizedPattern.map(normalized => {
            if (patternRange === 0) {
                // If pattern is flat, use average of min and max costs
                return (appState.minCost + appState.maxCost) / 2;
            }
            // Map pattern's [patternMin, patternMax] to [minCost, maxCost]
            const normalizedInRange = (normalized - patternMin) / patternRange;
            return appState.minCost + (normalizedInRange * costRange);
        });

        // Store the actual hourly costs for use in cost calculations
        appState.hourlyCosts = costPattern;

        // Update load chart with cost data
        ChartManager.updateLoadChart(costPattern);

        // Update savings rate hint to reflect new average usage
        updateSavingsRateHint();
    }

    /**
     * Calculate costs and update all visualizations
     */
    function calculateAndUpdateCosts() {
        // Use the actual hourly costs we're displaying in the load chart
        const hourlyCosts = appState.hourlyCosts || [];

        // Prepare configuration with actual costs
        const config = {
            hourlyCosts: hourlyCosts,  // Actual $/hour for each hour
            coverageCost: appState.coverageCost,  // Coverage commitment in $/hour
            savingsPercentage: appState.savingsPercentage,
            onDemandRate: appState.onDemandRate
        };

        // Calculate costs
        currentCostResults = CostCalculator.calculateCosts(config);

        // Store results for chart tooltips
        ChartManager.setCurrentCostResults(currentCostResults);

        // Update cost chart
        ChartManager.updateCostChart(currentCostResults);

        // Update metrics display
        updateMetricsDisplay(currentCostResults);

        // Update optimal suggestion
        updateOptimalSuggestion(currentCostResults);

        // Calculate and update savings curve (0-200% of min-hourly)
        updateSavingsCurveDisplay(hourlyCosts);
    }

    /**
     * Update savings curve chart display
     * @param {Array<number>} hourlyCosts - Hourly costs
     */
    function updateSavingsCurveDisplay(hourlyCosts) {
        if (!hourlyCosts || hourlyCosts.length === 0) return;

        const minCost = Math.min(...hourlyCosts);
        const maxCost = Math.max(...hourlyCosts);
        const savingsPercentage = appState.savingsPercentage;
        const baselineCost = hourlyCosts.reduce((sum, cost) => sum + cost, 0);

        // First pass: find breakeven point by testing coverage levels
        let breakevenCoverage = maxCost;
        const discountFactor = (1 - savingsPercentage / 100);
        const testIncrement = maxCost / 500; // Fine granularity for finding breakeven

        for (let coverageCost = 0; coverageCost <= maxCost; coverageCost += testIncrement) {
            let commitmentCost = 0;
            let spilloverCost = 0;

            for (let i = 0; i < hourlyCosts.length; i++) {
                commitmentCost += coverageCost * discountFactor;
                spilloverCost += Math.max(0, hourlyCosts[i] - coverageCost);
            }

            const totalCost = commitmentCost + spilloverCost;
            const netSavings = baselineCost - totalCost;

            // Found where we cross back to negative savings
            if (netSavings < 0) {
                breakevenCoverage = coverageCost - testIncrement;
                break;
            }
        }

        // Set chart range to breakeven + 10% buffer (or max if breakeven is close to max)
        const bufferMultiplier = 1.1;
        const chartMaxCost = Math.min(breakevenCoverage * bufferMultiplier, maxCost);

        // Generate curve data from $0 to chartMaxCost with high resolution
        const curveData = [];
        const increment = chartMaxCost / 500; // 500 data points for smooth curve

        for (let coverageCost = 0; coverageCost <= chartMaxCost; coverageCost += increment) {
            let commitmentCost = 0;
            let spilloverCost = 0;

            for (let i = 0; i < hourlyCosts.length; i++) {
                commitmentCost += coverageCost * discountFactor;
                spilloverCost += Math.max(0, hourlyCosts[i] - coverageCost);
            }

            const totalCost = commitmentCost + spilloverCost;
            const netSavings = baselineCost - totalCost;
            const savingsPercent = baselineCost > 0 ? (netSavings / baselineCost) * 100 : 0;

            curveData.push({
                coverage: coverageCost,
                netSavings: netSavings,
                savingsPercent: savingsPercent,
                extraSavings: 0  // Will be calculated below
            });
        }

        // Calculate min-hourly baseline savings (find point closest to min-hourly)
        const minHourlyPoint = curveData.reduce((prev, curr) => {
            return Math.abs(curr.coverage - minCost) < Math.abs(prev.coverage - minCost) ? curr : prev;
        });
        const minHourlySavings = minHourlyPoint.netSavings;

        // Find optimal point directly from curve data (point with maximum savings)
        const optimalPoint = curveData.reduce((prev, curr) => {
            return curr.netSavings > prev.netSavings ? curr : prev;
        });
        const optimalCoverage = optimalPoint.coverage;
        const optimalNetSavings = optimalPoint.netSavings;

        // Also get the optimal from calculator for validation
        const optimalResult = CostCalculator.calculateOptimalCoverage(hourlyCosts, savingsPercentage);

        // Calculate extra savings for each point
        // - Below optimal: extra savings vs min-hourly (positive gain)
        // - Past optimal: waste vs optimal (negative)
        curveData.forEach(point => {
            if (point.coverage <= optimalCoverage) {
                point.extraSavings = point.netSavings - minHourlySavings;
            } else {
                point.extraSavings = point.netSavings - optimalNetSavings;
            }
        });

        // Always use the current slider position for the vertical line
        const currentCoverageFromData = appState.coverageCost;

        // Update chart (use optimal from curve data for consistency)
        ChartManager.updateSavingsCurveChart(
            curveData,
            minHourlySavings,
            optimalCoverage,
            minCost,
            chartMaxCost,
            baselineCost,
            currentCoverageFromData
        );
    }

    /**
     * Update coverage display
     */
    function updateCoverageDisplay(coverageCost) {
        // Calculate percentage of min-hourly
        const minCost = appState.minCost || 1;
        const percentOfMin = (coverageCost / minCost) * 100;

        const displayElement = document.getElementById('coverage-display');
        if (displayElement) {
            displayElement.textContent = `$${coverageCost.toFixed(2)}/hour (${percentOfMin.toFixed(0)}%)`;
        }

        const unitsElement = document.getElementById('coverage-units');
        if (unitsElement) {
            // Calculate actual commitment cost with discount applied
            const discountFactor = (1 - appState.savingsPercentage / 100);
            const actualCost = coverageCost * discountFactor;

            unitsElement.textContent = `Cost ${CostCalculator.formatCurrency(actualCost)}/hour vs ${CostCalculator.formatCurrency(coverageCost)}/hour On-Demand`;
        }

        // Update savings rate hint to reflect coverage commitment
        updateSavingsRateHint();
    }

    /**
     * Update savings rate hint to show coverage commitment vs average usage
     */
    function updateSavingsRateHint() {
        const rateElement = document.getElementById('savings-rate');
        if (rateElement) {
            // Calculate average usage from hourly costs
            const hourlyCosts = appState.hourlyCosts || [];
            const avgUsage = hourlyCosts.length > 0
                ? hourlyCosts.reduce((sum, cost) => sum + cost, 0) / hourlyCosts.length
                : 0;

            const coverageCommitment = appState.coverageCost || 0;
            rateElement.textContent = `Coverage $${coverageCommitment.toFixed(3)}/hr vs $${avgUsage.toFixed(3)}/hr Avg Usage`;
        }
    }

    /**
     * Update savings percentage display
     */
    function updateSavingsDisplay(value) {
        const displayElement = document.getElementById('savings-display');
        if (displayElement) {
            displayElement.textContent = `${value}%`;
        }

        // Update the hint text
        updateSavingsRateHint();
    }

    /**
     * Update metrics display
     */
    function updateMetricsDisplay(results) {
        // Convert weekly costs to hourly rates (divide by 168 hours)
        const hoursPerWeek = 168;

        // Pure On-Demand cost (baseline)
        const onDemandElement = document.getElementById('metric-ondemand');
        if (onDemandElement) {
            onDemandElement.textContent = CostCalculator.formatCurrency(results.onDemandCost / hoursPerWeek) + '/hr';
        }

        // Total Cost with SP (commitment + spillover)
        const savingsPlanElement = document.getElementById('metric-savingsplan');
        if (savingsPlanElement) {
            savingsPlanElement.textContent = CostCalculator.formatCurrency(results.savingsPlanCost / hoursPerWeek) + '/hr';
        }

        // Net Savings
        const savingsElement = document.getElementById('metric-savings');
        if (savingsElement) {
            savingsElement.textContent = CostCalculator.formatCurrency(results.savings / hoursPerWeek) + '/hr';

            // Change color based on positive/negative savings
            const savingsContainer = savingsElement.closest('.metric-item');
            if (savingsContainer) {
                if (results.savings < 0) {
                    savingsContainer.classList.remove('success');
                    savingsContainer.classList.add('danger');
                } else {
                    savingsContainer.classList.remove('danger');
                    savingsContainer.classList.add('success');
                }
            }
        }

        const savingsPctElement = document.getElementById('metric-savings-pct');
        if (savingsPctElement) {
            savingsPctElement.textContent = CostCalculator.formatPercentage(results.savingsPercentageActual);
        }

        // SP Commitment Cost
        const commitmentElement = document.getElementById('metric-commitment');
        if (commitmentElement) {
            commitmentElement.textContent = CostCalculator.formatCurrency(results.commitmentCost / hoursPerWeek) + '/hr';
        }

        const commitmentPctElement = document.getElementById('metric-commitment-pct');
        if (commitmentPctElement) {
            const commitmentPct = results.savingsPlanCost > 0
                ? (results.commitmentCost / results.savingsPlanCost) * 100
                : 0;
            commitmentPctElement.textContent = `${commitmentPct.toFixed(1)}% of total`;
        }

        // Spillover Cost
        const spilloverElement = document.getElementById('metric-spillover');
        if (spilloverElement) {
            spilloverElement.textContent = CostCalculator.formatCurrency(results.spilloverCost / hoursPerWeek) + '/hr';
        }

        const spilloverPctElement = document.getElementById('metric-spillover-pct');
        if (spilloverPctElement) {
            spilloverPctElement.textContent = `${CostCalculator.formatPercentage(results.spilloverPercentage)} of total`;
        }

        // Wasted commitment
        const wasteElement = document.getElementById('metric-waste');
        if (wasteElement) {
            wasteElement.textContent = CostCalculator.formatCurrency(results.wastedCommitment / hoursPerWeek) + '/hr';
        }

        const wastePctElement = document.getElementById('metric-waste-pct');
        if (wastePctElement) {
            wastePctElement.textContent = `${CostCalculator.formatPercentage(results.wastePercentage)} of commitment`;
        }
    }

    /**
     * Update optimal suggestion display
     */
    function updateOptimalSuggestion(results) {
        const suggestionElement = document.getElementById('optimal-suggestion');
        const textElement = document.getElementById('suggestion-text');
        const titleElement = suggestionElement?.querySelector('.suggestion-title');

        if (!suggestionElement || !textElement || !titleElement) return;

        // Convert current coverage cost to percentage for comparison
        const currentCoveragePercent = (appState.coverageCost / appState.maxCost) * 100;

        const suggestion = CostCalculator.getOptimizationSuggestion(
            currentCoveragePercent,
            results.optimalCoveragePercentage
        );

        // Use optimal coverage directly (in $/hour), not recalculated from percentage
        const optimalCost = results.optimalCoverageUnits;
        const currentCost = appState.coverageCost;

        // Calculate min-hourly percentage
        const minCost = appState.minCost;
        const optimalPercentOfMin = (optimalCost / minCost) * 100;

        // Update status class
        suggestionElement.classList.remove('status-optimal', 'status-warning', 'status-danger');
        suggestionElement.classList.add(`status-${suggestion.status}`);

        // Update title with optimal dollar amount and potential savings
        const totalSavings = results.optimalCoverage.maxNetSavings || 0;
        const monthlySavings = totalSavings * 4.33; // Convert weekly to monthly (~30 days / 7 days)

        titleElement.innerHTML = `Optimal: ${CostCalculator.formatCurrency(optimalCost)}/hour<br>
            <small style="font-weight: normal; opacity: 0.9;">
                Potential savings: ${CostCalculator.formatCurrency(monthlySavings)}/month
            </small>`;

        // Update text with dollar amounts
        let message = suggestion.message;
        // Replace percentage values with dollar values
        message = message.replace(/\d+\.\d+%/g, (match) => {
            const percent = parseFloat(match);
            const dollarValue = (percent / 100) * appState.maxCost;
            return `$${dollarValue.toFixed(2)}/hour`;
        });

        textElement.textContent = `${suggestion.icon} ${message}`;
    }

    /**
     * Show toast notification
     */
    function showToast(message, type = 'success') {
        const toast = document.getElementById('toast');
        if (!toast) return;

        toast.textContent = message;
        toast.classList.add('show');

        setTimeout(() => {
            toast.classList.remove('show');
        }, 3000);
    }

    /**
     * Get current application state
     */
    function getState() {
        return { ...appState };
    }

    /**
     * Set application state (useful for testing)
     */
    function setState(newState) {
        appState = { ...appState, ...newState };
        updateUIFromState();
        updateLoadPattern();
        calculateAndUpdateCosts();
    }

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    // Expose for debugging and testing
    window.SavingsPlanSimulator = {
        getState,
        setState,
        calculateAndUpdateCosts,
        updateLoadPattern
    };

})();

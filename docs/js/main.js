/**
 * Main Application
 * Orchestrates the AWS Savings Plan Simulator
 */

(function() {
    'use strict';

    // Application state
    let appState = {
        pattern: 'ecommerce',
        minCost: 15,          // Min $/h
        maxCost: 100,         // Max $/h (peak)
        coverageCost: 50,     // Coverage commitment in $/h
        savingsPercentage: 30,
        loadFactor: 100,      // Load factor percentage (50-200%)
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

        // Initialize legend colors
        updateLegendColors();

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
            console.warn(`Python: $${pythonCoverage.toFixed(2)}/h`);
            console.warn(`JavaScript: $${jsCoverage.toFixed(2)}/h`);
            console.warn(`Difference: $${difference.toFixed(2)}/h`);

            showMismatchWarning(pythonCoverage, jsCoverage);
        } else {
            console.log('✓ Python and JavaScript optimal coverage calculations match');
            console.log(`Optimal: $${jsCoverage.toFixed(2)}/h`);
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
                    Python calculated: $${pythonValue.toFixed(2)}/h | JavaScript calculated: $${jsValue.toFixed(2)}/h<br>
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
            // Set step to 0.1% of max cost for precise control
            coverageSlider.step = appState.maxCost / 1000;
            coverageSlider.value = appState.coverageCost;
            coverageSlider.addEventListener('input', handleCoverageChange);
        }

        // Savings percentage slider
        const savingsSlider = document.getElementById('savings-percentage');
        if (savingsSlider) {
            savingsSlider.value = appState.savingsPercentage;
            savingsSlider.addEventListener('input', handleSavingsChange);
        }

        // Load factor slider
        const loadFactorSlider = document.getElementById('load-factor');
        if (loadFactorSlider) {
            loadFactorSlider.value = appState.loadFactor;
            loadFactorSlider.addEventListener('input', handleLoadFactorChange);
        }

        // Reset load factor button
        const resetLoadFactorButton = document.getElementById('reset-load-factor');
        if (resetLoadFactorButton) {
            resetLoadFactorButton.addEventListener('click', () => {
                if (loadFactorSlider) {
                    loadFactorSlider.value = 100;
                    handleLoadFactorChange({ target: { value: '100' } });
                }
            });
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

        // Strategy button click handlers
        const strategyButtons = document.querySelectorAll('.strategy-button');
        strategyButtons.forEach(button => {
            button.addEventListener('click', handleStrategyClick);
        });
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
            coverageSlider.step = appState.maxCost / 1000;
            coverageSlider.value = appState.coverageCost;
        }
        updateCoverageDisplay(appState.coverageCost);

        // Savings percentage slider
        const savingsSlider = document.getElementById('savings-percentage');
        if (savingsSlider) {
            savingsSlider.value = appState.savingsPercentage;
        }
        updateSavingsDisplay(appState.savingsPercentage);

        // Load factor slider
        const loadFactorSlider = document.getElementById('load-factor');
        if (loadFactorSlider) {
            loadFactorSlider.value = appState.loadFactor;
        }
        updateLoadFactorDisplay(appState.loadFactor);

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
                coverageSlider.step = appState.maxCost / 1000; // 0.1% of max cost for precise control
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
     * Handle load factor change
     */
    function handleLoadFactorChange(event) {
        const value = parseInt(event.target.value, 10);
        if (!isNaN(value) && value >= 1 && value <= 150) {
            appState.loadFactor = value;
            updateLoadFactorDisplay(value);
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
     * Calculate all strategy coverage values
     * All strategies based on the knee point algorithm
     * @returns {Object} Strategy values with coverage amounts
     */
    function calculateStrategies() {
        const baseHourlyCosts = appState.hourlyCosts || [];
        if (baseHourlyCosts.length === 0) {
            return {
                tooPrudent: 0,
                minHourly: 0,
                balanced: 0,
                aggressive: 0,
                tooAggressive: 0
            };
        }

        // Apply load factor to scale usage
        const loadFactor = appState.loadFactor / 100;
        const hourlyCosts = baseHourlyCosts.map(cost => cost * loadFactor);

        // Min-Hourly: Baseline only (minimum cost with load factor)
        const minHourly = Math.min(...hourlyCosts);

        // Too Prudent: 80% of min-hourly (under-committed - for educational purposes)
        const tooPrudent = minHourly * 0.80;

        // Optimal: Maximum savings (the peak)
        const optimalResult = CostCalculator.calculateOptimalCoverage(
            hourlyCosts,
            appState.savingsPercentage
        );
        const optimal = optimalResult.coverageUnits;

        // Balanced: The knee point (sweet spot)
        const balanced = calculateKneePoint(hourlyCosts, appState.savingsPercentage, minHourly, optimal);

        // Aggressive: The exact optimal point (maximum savings)
        const aggressive = optimal;

        // Too Aggressive: 125% of optimal (into the declining zone - for educational purposes)
        const tooAggressive = optimal * 1.25;

        return {
            tooPrudent,
            minHourly,
            balanced,
            aggressive,
            tooAggressive
        };
    }

    /**
     * Calculate the knee point on the savings curve
     * This is the "balanced" strategy - where you get most of the savings
     * without committing all the way to optimal
     *
     * Uses perpendicular distance method to find the elbow of the curve
     */
    function calculateKneePoint(hourlyCosts, savingsPercentage, minCost, optimalCoverage) {
        const baselineCost = hourlyCosts.reduce((sum, cost) => sum + cost, 0);
        const discountFactor = (1 - savingsPercentage / 100);

        // Generate curve data from minCost to 120% past optimal (to see the decline)
        const maxCoverage = optimalCoverage * 1.2;
        const numPoints = 200; // More points for accurate derivative calculation
        const step = (maxCoverage - minCost) / numPoints;
        const curvePoints = [];

        for (let i = 0; i <= numPoints; i++) {
            const coverage = minCost + (i * step);

            let commitmentCost = 0;
            let spilloverCost = 0;

            for (let j = 0; j < hourlyCosts.length; j++) {
                commitmentCost += coverage * discountFactor;
                spilloverCost += Math.max(0, hourlyCosts[j] - coverage);
            }

            const totalCost = commitmentCost + spilloverCost;
            const netSavings = baselineCost - totalCost;
            const savingsPercent = baselineCost > 0 ? (netSavings / baselineCost) * 100 : 0;

            curvePoints.push({
                coverage: coverage,
                savingsPercent: savingsPercent,
                netSavings: netSavings
            });
        }

        // Find knee by analyzing marginal efficiency: where additional commitment
        // stops providing good returns (diminishing returns threshold)

        // Calculate marginal savings rate for each point (change in savings / change in coverage)
        const marginalRates = [];

        for (let i = 1; i < curvePoints.length; i++) {
            if (curvePoints[i].coverage > minCost && curvePoints[i].coverage <= optimalCoverage) {
                const coverageDelta = curvePoints[i].coverage - curvePoints[i - 1].coverage;
                const savingsDelta = curvePoints[i].savingsPercent - curvePoints[i - 1].savingsPercent;
                const marginalRate = coverageDelta > 0 ? savingsDelta / coverageDelta : 0;

                marginalRates.push({
                    index: i,
                    coverage: curvePoints[i].coverage,
                    marginalRate: marginalRate,
                    savingsPercent: curvePoints[i].savingsPercent
                });
            }
        }

        if (marginalRates.length === 0) {
            return minCost;
        }

        // Find the peak marginal rate (usually early in the curve)
        const maxMarginalRate = Math.max(...marginalRates.map(r => r.marginalRate));

        // Find where marginal rate drops to 30% of its peak
        // This is the "knee" - still good returns but not peak efficiency
        const threshold = maxMarginalRate * 0.30;

        let kneeIndex = 0;
        for (let i = 0; i < marginalRates.length; i++) {
            if (marginalRates[i].marginalRate < threshold) {
                // Found where efficiency drops below threshold
                // Use the previous point (last point above threshold)
                kneeIndex = i > 0 ? marginalRates[i - 1].index : marginalRates[0].index;
                break;
            }
        }

        // If we never dropped below threshold, use a point 60% of the way to optimal
        if (kneeIndex === 0) {
            return minCost + (optimalCoverage - minCost) * 0.60;
        }

        return curvePoints[kneeIndex].coverage;
    }

    /**
     * Handle strategy button click
     */
    function handleStrategyClick(event) {
        const button = event.currentTarget;
        const strategy = button.dataset.strategy;

        const strategies = calculateStrategies();
        let coverageCost;

        switch (strategy) {
            case 'too-prudent':
                coverageCost = strategies.tooPrudent;
                break;
            case 'min-hourly':
                coverageCost = strategies.minHourly;
                break;
            case 'balanced':
                coverageCost = strategies.balanced;
                break;
            case 'aggressive':
                coverageCost = strategies.aggressive;
                break;
            case 'too-aggressive':
                coverageCost = strategies.tooAggressive;
                break;
            default:
                showToast('Unknown strategy', 'error');
                return;
        }

        // Update state
        appState.coverageCost = coverageCost;

        // Update slider
        const coverageSlider = document.getElementById('coverage-slider');
        if (coverageSlider) {
            coverageSlider.value = coverageCost;
        }

        // Update display
        updateCoverageDisplay(coverageCost);

        // Recalculate
        calculateAndUpdateCosts();

        // Update URL
        URLState.debouncedUpdateURL(appState);

        // Show success message
        const strategyNames = {
            'too-prudent': 'Prudent 🐔',
            'min-hourly': 'Min-Hourly',
            'balanced': 'Balanced',
            'aggressive': 'Risky',
            'too-aggressive': 'Aggressive 💀'
        };
        showToast(`${strategyNames[strategy]} strategy applied: ${CostCalculator.formatCurrency(coverageCost)}/h`);
    }

    /**
     * Update strategy button displays with calculated values
     */
    function updateStrategyButtons() {
        const strategies = calculateStrategies();

        // Get current coverage to detect which strategy is active
        const currentCoverage = appState.coverageCost;

        // Convert coverage to commitment for display
        const savingsPercentage = appState.savingsPercentage;

        // Get scaled hourly costs for savings calculation
        const baseHourlyCosts = appState.hourlyCosts || [];
        const loadFactor = appState.loadFactor / 100;
        const scaledHourlyCosts = baseHourlyCosts.map(cost => cost * loadFactor);

        // Use actual array length for division, same as updateMetricsDisplay
        const numHours = appState.hourlyCosts?.length || 168;

        // Calculate baseline on-demand cost for all 168 hours
        let baselineCost = 0;
        for (let hour = 0; hour < numHours; hour++) {
            baselineCost += scaledHourlyCosts[hour] || 0;
        }
        const hourlyOnDemand = baselineCost / numHours;

        // Helper function to calculate savings for a strategy
        const calculateStrategySavings = (coverageUnits) => {
            const discountFactor = (1 - savingsPercentage / 100);
            let commitmentCost = 0;
            let spilloverCost = 0;

            // Always loop 168 hours like CostCalculator.calculateCosts
            for (let hour = 0; hour < numHours; hour++) {
                const onDemandCost = scaledHourlyCosts[hour] || 0;
                commitmentCost += coverageUnits * discountFactor;
                spilloverCost += Math.max(0, onDemandCost - coverageUnits);
            }

            const totalCost = commitmentCost + spilloverCost;
            const netSavings = baselineCost - totalCost;
            const netSavingsHourly = netSavings / numHours;

            // Calculate effective savings rate (same as in cost calculator)
            const savingsPercentageActual = SPCalculations.calculateEffectiveSavingsRate(
                baselineCost,
                totalCost
            );

            return {
                hourly: netSavingsHourly,
                percentage: savingsPercentageActual
            };
        };

        // Calculate min-hourly commitment for percentage calculations
        const minHourlyCommitment = SPCalculations.commitmentFromCoverage(strategies.minHourly, savingsPercentage);

        // Update Too Prudent
        const tooPrudentValue = document.getElementById('strategy-too-prudent-value');
        const tooPrudentSavings = document.getElementById('strategy-too-prudent-savings');
        const tooPrudentSavingsPct = document.getElementById('strategy-too-prudent-savings-pct');
        const tooPrudentMinHourlyPct = document.getElementById('strategy-too-prudent-min-hourly-pct');
        if (tooPrudentValue && tooPrudentSavings && tooPrudentSavingsPct && tooPrudentMinHourlyPct) {
            const commitment = SPCalculations.commitmentFromCoverage(strategies.tooPrudent, savingsPercentage);
            const savingsData = calculateStrategySavings(strategies.tooPrudent);
            const minHourlyPct = minHourlyCommitment > 0 ? (commitment / minHourlyCommitment) * 100 : 100;
            tooPrudentValue.textContent = `${CostCalculator.formatCurrency(commitment)}`;
            tooPrudentSavings.textContent = `${CostCalculator.formatCurrency(savingsData.hourly)}/h`;
            tooPrudentSavingsPct.textContent = `${savingsData.percentage.toFixed(1)}%`;
            tooPrudentMinHourlyPct.textContent = `${minHourlyPct.toFixed(1)}% Min-Hourly`;
        }

        // Update Min-Hourly
        const minValue = document.getElementById('strategy-min-value');
        const minSavings = document.getElementById('strategy-min-savings');
        const minSavingsPct = document.getElementById('strategy-min-savings-pct');
        const minMinHourlyPct = document.getElementById('strategy-min-min-hourly-pct');
        if (minValue && minSavings && minSavingsPct && minMinHourlyPct) {
            const commitment = SPCalculations.commitmentFromCoverage(strategies.minHourly, savingsPercentage);
            const savingsData = calculateStrategySavings(strategies.minHourly);
            const minHourlyPct = minHourlyCommitment > 0 ? (commitment / minHourlyCommitment) * 100 : 100;
            minValue.textContent = `${CostCalculator.formatCurrency(commitment)}`;
            minSavings.textContent = `${CostCalculator.formatCurrency(savingsData.hourly)}/h`;
            minSavingsPct.textContent = `${savingsData.percentage.toFixed(1)}%`;
            minMinHourlyPct.textContent = `${minHourlyPct.toFixed(1)}% Min-Hourly`;
        }

        // Update Balanced
        const balancedValue = document.getElementById('strategy-balanced-value');
        const balancedSavings = document.getElementById('strategy-balanced-savings');
        const balancedSavingsPct = document.getElementById('strategy-balanced-savings-pct');
        const balancedMinHourlyPct = document.getElementById('strategy-balanced-min-hourly-pct');
        if (balancedValue && balancedSavings && balancedSavingsPct && balancedMinHourlyPct) {
            const commitment = SPCalculations.commitmentFromCoverage(strategies.balanced, savingsPercentage);
            const savingsData = calculateStrategySavings(strategies.balanced);
            const minHourlyPct = minHourlyCommitment > 0 ? (commitment / minHourlyCommitment) * 100 : 100;
            balancedValue.textContent = `${CostCalculator.formatCurrency(commitment)}`;
            balancedSavings.textContent = `${CostCalculator.formatCurrency(savingsData.hourly)}/h`;
            balancedSavingsPct.textContent = `${savingsData.percentage.toFixed(1)}%`;
            balancedMinHourlyPct.textContent = `${minHourlyPct.toFixed(1)}% Min-Hourly`;
        }

        // Update Aggressive
        const aggressiveValue = document.getElementById('strategy-aggressive-value');
        const aggressiveSavings = document.getElementById('strategy-aggressive-savings');
        const aggressiveSavingsPct = document.getElementById('strategy-aggressive-savings-pct');
        const aggressiveMinHourlyPct = document.getElementById('strategy-aggressive-min-hourly-pct');
        if (aggressiveValue && aggressiveSavings && aggressiveSavingsPct && aggressiveMinHourlyPct) {
            const commitment = SPCalculations.commitmentFromCoverage(strategies.aggressive, savingsPercentage);
            const savingsData = calculateStrategySavings(strategies.aggressive);
            const minHourlyPct = minHourlyCommitment > 0 ? (commitment / minHourlyCommitment) * 100 : 100;
            aggressiveValue.textContent = `${CostCalculator.formatCurrency(commitment)}`;
            aggressiveSavings.textContent = `${CostCalculator.formatCurrency(savingsData.hourly)}/h`;
            aggressiveSavingsPct.textContent = `${savingsData.percentage.toFixed(1)}%`;
            aggressiveMinHourlyPct.textContent = `${minHourlyPct.toFixed(1)}% Min-Hourly`;
        }

        // Update Too Aggressive
        const tooAggressiveValue = document.getElementById('strategy-too-aggressive-value');
        const tooAggressiveSavings = document.getElementById('strategy-too-aggressive-savings');
        const tooAggressiveSavingsPct = document.getElementById('strategy-too-aggressive-savings-pct');
        const tooAggressiveMinHourlyPct = document.getElementById('strategy-too-aggressive-min-hourly-pct');
        if (tooAggressiveValue && tooAggressiveSavings && tooAggressiveSavingsPct && tooAggressiveMinHourlyPct) {
            const commitment = SPCalculations.commitmentFromCoverage(strategies.tooAggressive, savingsPercentage);
            const savingsData = calculateStrategySavings(strategies.tooAggressive);
            const minHourlyPct = minHourlyCommitment > 0 ? (commitment / minHourlyCommitment) * 100 : 100;
            tooAggressiveValue.textContent = `${CostCalculator.formatCurrency(commitment)}`;
            tooAggressiveSavings.textContent = `${CostCalculator.formatCurrency(savingsData.hourly)}/h`;
            tooAggressiveSavingsPct.textContent = `${savingsData.percentage.toFixed(1)}%`;
            tooAggressiveMinHourlyPct.textContent = `${minHourlyPct.toFixed(1)}% Min-Hourly`;
        }

        // Detect and highlight active strategy
        const allButtons = document.querySelectorAll('.strategy-button');
        allButtons.forEach(btn => btn.classList.remove('active'));

        // Compare with tolerance for floating point comparison (2%)
        const tolerance = 0.02;
        let activeButton = null;

        const tooPrudentDiff = Math.abs(currentCoverage - strategies.tooPrudent);
        const minDiff = Math.abs(currentCoverage - strategies.minHourly);
        const balancedDiff = Math.abs(currentCoverage - strategies.balanced);
        const aggressiveDiff = Math.abs(currentCoverage - strategies.aggressive);
        const tooAggressiveDiff = Math.abs(currentCoverage - strategies.tooAggressive);

        // Find closest match
        const minDistance = Math.min(tooPrudentDiff, minDiff, balancedDiff, aggressiveDiff, tooAggressiveDiff);

        if (minDistance / Math.max(currentCoverage, 0.01) < tolerance) {
            if (minDistance === tooPrudentDiff) {
                activeButton = document.getElementById('strategy-too-prudent');
            } else if (minDistance === minDiff) {
                activeButton = document.getElementById('strategy-min');
            } else if (minDistance === balancedDiff) {
                activeButton = document.getElementById('strategy-balanced');
            } else if (minDistance === aggressiveDiff) {
                activeButton = document.getElementById('strategy-aggressive');
            } else if (minDistance === tooAggressiveDiff) {
                activeButton = document.getElementById('strategy-too-aggressive');
            }
        }

        // Apply active class to matching button
        if (activeButton) {
            activeButton.classList.add('active');
        }
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

        // Update legend colors
        updateLegendColors(themeName);

        // Show toast notification
        const themeColors = ColorThemes.getThemeColors(themeName);
        showToast(`Color theme changed to: ${themeColors.name || themeName}`);
    }

    /**
     * Update savings curve legend colors based on theme
     */
    function updateLegendColors(themeName = null) {
        const themeColors = ColorThemes.getThemeColors(themeName);
        const curves = themeColors.savingsCurve;

        // Helper to extract RGB from rgba string
        function rgbaToGradient(borderColor, bgColor) {
            // Extract RGB values from background color (rgba format)
            const match = bgColor.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*([\d.]+))?\)/);
            if (match) {
                const r = match[1];
                const g = match[2];
                const b = match[3];
                return `linear-gradient(90deg, rgba(${r},${g},${b},0.3), rgba(${r},${g},${b},0.6))`;
            }
            return bgColor;
        }

        // Update each legend color
        const legendBuilding = document.getElementById('legend-building');
        const legendGaining = document.getElementById('legend-gaining');
        const legendWasting = document.getElementById('legend-wasting');
        const legendVeryBad = document.getElementById('legend-veryBad');
        const legendLosingMoney = document.getElementById('legend-losingMoney');

        if (legendBuilding) legendBuilding.style.background = rgbaToGradient(curves.building.border, curves.building.background);
        if (legendGaining) legendGaining.style.background = rgbaToGradient(curves.gaining.border, curves.gaining.background);
        if (legendWasting) legendWasting.style.background = rgbaToGradient(curves.wasting.border, curves.wasting.background);
        if (legendVeryBad) legendVeryBad.style.background = rgbaToGradient(curves.veryBad.border, curves.veryBad.background);
        if (legendLosingMoney) legendLosingMoney.style.background = rgbaToGradient(curves.losingMoney.border, curves.losingMoney.background);
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
        const baseHourlyCosts = appState.hourlyCosts || [];

        // Apply load factor to scale usage up or down
        const loadFactor = appState.loadFactor / 100;
        const scaledHourlyCosts = baseHourlyCosts.map(cost => cost * loadFactor);

        // Prepare configuration with scaled costs
        const config = {
            hourlyCosts: scaledHourlyCosts,  // Scaled $/h for each hour
            coverageCost: appState.coverageCost,  // Coverage commitment in $/h (static)
            savingsPercentage: appState.savingsPercentage,
            onDemandRate: appState.onDemandRate
        };

        // Calculate costs
        currentCostResults = CostCalculator.calculateCosts(config);

        // Store results for chart tooltips
        ChartManager.setCurrentCostResults(currentCostResults);

        // Update cost chart with scaled costs
        ChartManager.updateCostChart(currentCostResults);

        // Update metrics display
        updateMetricsDisplay(currentCostResults);

        // Update optimal suggestion
        updateOptimalSuggestion(currentCostResults, scaledHourlyCosts);

        // Update strategy button values
        updateStrategyButtons();

        // Calculate and update savings curve with scaled costs
        updateSavingsCurveDisplay(scaledHourlyCosts);
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
        // NOTE: This is equivalent to commitmentFromCoverage() in spCalculations.js
        // Kept as variable for performance (reused in loops)
        const discountFactor = (1 - savingsPercentage / 100);
        const testIncrement = maxCost / 500; // Fine granularity for finding breakeven

        for (let coverageCost = 0; coverageCost <= maxCost; coverageCost += testIncrement) {
            let commitmentCost = 0;
            let spilloverCost = 0;

            for (let i = 0; i < hourlyCosts.length; i++) {
                // NOTE: commitmentCost calculation uses discountFactor (see above comment)
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
                // NOTE: Uses discountFactor from commitmentFromCoverage() pattern (see spCalculations.js)
                commitmentCost += coverageCost * discountFactor;
                spilloverCost += Math.max(0, hourlyCosts[i] - coverageCost);
            }

            const totalCost = commitmentCost + spilloverCost;
            const netSavings = baselineCost - totalCost;
            const savingsPercent = baselineCost > 0 ? (netSavings / baselineCost) * 100 : 0;
            const hourlyCommitment = coverageCost * discountFactor;

            curveData.push({
                coverage: coverageCost,
                commitment: hourlyCommitment,
                netSavings: netSavings,
                savingsPercent: savingsPercent,
                extraSavings: 0,  // Will be calculated below
                percentOfMin: minCost > 0 ? (coverageCost / minCost) * 100 : 0
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
            currentCoverageFromData,
            savingsPercentage
        );
    }

    /**
     * Update coverage display
     */
    function updateCoverageDisplay(coverageCost) {
        // Calculate percentage of min-hourly
        const minCost = appState.minCost || 1;
        const percentOfMin = (coverageCost / minCost) * 100;

        // Calculate actual commitment cost with discount applied
        const discountFactor = (1 - appState.savingsPercentage / 100);
        const commitmentCost = coverageCost * discountFactor;

        const displayElement = document.getElementById('coverage-display');
        if (displayElement) {
            // Show commitment (what you pay) with min-hourly percentage on the main line
            displayElement.textContent = `$${commitmentCost.toFixed(2)}/h (${percentOfMin.toFixed(1)}% Min-Hourly)`;
        }

        const unitsElement = document.getElementById('coverage-units');
        if (unitsElement) {
            // Show on-demand coverage below
            unitsElement.textContent = `Covers ${CostCalculator.formatCurrency(coverageCost)}/h on-demand`;
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
            rateElement.textContent = `Coverage $${coverageCommitment.toFixed(3)}/h vs $${avgUsage.toFixed(3)}/h Avg Usage`;
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
     * Update load factor display
     */
    function updateLoadFactorDisplay(value) {
        const displayElement = document.getElementById('load-factor-display');
        if (displayElement) {
            const delta = value - 100;

            // Remove existing color classes
            displayElement.classList.remove('positive', 'negative', 'neutral');

            if (delta === 0) {
                displayElement.textContent = '100%';
                displayElement.classList.add('neutral');
            } else if (delta > 0) {
                displayElement.textContent = `+${delta}%`;
                displayElement.classList.add('positive'); // Red for increase
            } else {
                displayElement.textContent = `${delta}%`; // Negative sign already included
                displayElement.classList.add('negative'); // Green for reduction
            }
        }

        const hintElement = document.getElementById('load-factor-hint');
        if (hintElement) {
            if (value === 100) {
                hintElement.textContent = 'Original usage level';
            } else if (value < 100) {
                hintElement.textContent = `${value}% of original usage`;
            } else {
                hintElement.textContent = `${value}% of original usage`;
            }
        }
    }

    /**
     * Get color for percentage value based on metric type
     * @param {number} percentage - The percentage value
     * @param {string} type - The metric type: 'commitment', 'waste', 'spillover'
     * @returns {string} Color code
     */
    function getPercentageColor(percentage, type) {
        switch (type) {
            case 'commitment': // Higher is better
                if (percentage >= 60) return '#00ff88'; // Green
                if (percentage >= 30) return '#ffb84d'; // Orange
                return '#ff4d4d'; // Red

            case 'waste': // Lower is better
                if (percentage <= 10) return '#00ff88'; // Green
                if (percentage <= 25) return '#ffb84d'; // Orange
                return '#ff4d4d'; // Red

            case 'spillover': // Lower is better
                if (percentage <= 20) return '#00ff88'; // Green
                if (percentage <= 40) return '#ffb84d'; // Orange
                return '#ff4d4d'; // Red

            default:
                return 'inherit';
        }
    }

    /**
     * Update metrics display
     */
    function updateMetricsDisplay(results) {
        // Convert total costs to hourly rates
        // Use actual number of hours in the data
        const numHours = appState.hourlyCosts?.length || 168;

        // Pure On-Demand cost (baseline)
        const onDemandElement = document.getElementById('metric-ondemand');
        if (onDemandElement) {
            onDemandElement.textContent = CostCalculator.formatCurrency(results.onDemandCost / numHours) + '/h';
        }

        // Total Cost with SP (commitment + spillover)
        const savingsPlanElement = document.getElementById('metric-savingsplan');
        if (savingsPlanElement) {
            savingsPlanElement.textContent = CostCalculator.formatCurrency(results.savingsPlanCost / numHours) + '/h';
        }

        // Net Savings
        const savingsElement = document.getElementById('metric-savings');
        if (savingsElement) {
            savingsElement.textContent = CostCalculator.formatCurrency(results.savings / numHours) + '/h';

            // Change color based on zone if available
            const savingsContainer = savingsElement.closest('.metric-item');
            if (savingsContainer) {
                // Remove all zone and status classes
                savingsContainer.classList.remove(
                    'success', 'danger', 'warning',
                    'building', 'gaining', 'wasting', 'very-bad', 'losing-money'
                );

                // Apply zone-based class if we have zone info
                if (results.currentZone && results.currentZone.zone) {
                    savingsContainer.classList.add(results.currentZone.zone);
                } else {
                    // Fallback to old logic
                    if (results.savings < 0) {
                        savingsContainer.classList.add('danger');
                    } else {
                        savingsContainer.classList.add('success');
                    }
                }
            }
        }

        const savingsPctElement = document.getElementById('metric-savings-pct');
        if (savingsPctElement) {
            savingsPctElement.textContent = CostCalculator.formatPercentage(results.savingsPercentageActual);
        }

        // SP Commitment
        const commitmentElement = document.getElementById('metric-commitment');
        if (commitmentElement) {
            const discountFactor = (1 - appState.savingsPercentage / 100);
            const commitmentPerHour = appState.coverageCost * discountFactor;
            commitmentElement.textContent = CostCalculator.formatCurrency(commitmentPerHour) + '/h';
        }

        const commitmentPctElement = document.getElementById('metric-commitment-pct');
        if (commitmentPctElement) {
            const commitmentPct = results.savingsPlanCost > 0
                ? (results.commitmentCost / results.savingsPlanCost) * 100
                : 0;
            commitmentPctElement.textContent = `${commitmentPct.toFixed(1)}% of total cost`;
            commitmentPctElement.style.color = getPercentageColor(commitmentPct, 'commitment');
        }

        // Spillover Cost
        const spilloverElement = document.getElementById('metric-spillover');
        if (spilloverElement) {
            spilloverElement.textContent = CostCalculator.formatCurrency(results.spilloverCost / numHours) + '/h';
        }

        const spilloverPctElement = document.getElementById('metric-spillover-pct');
        if (spilloverPctElement) {
            spilloverPctElement.textContent = `${CostCalculator.formatPercentage(results.spilloverPercentage)} of total`;
            spilloverPctElement.style.color = getPercentageColor(results.spilloverPercentage, 'spillover');
        }

        // Wasted commitment
        const wasteElement = document.getElementById('metric-waste');
        if (wasteElement) {
            wasteElement.textContent = CostCalculator.formatCurrency(results.wastedCommitment / numHours) + '/h';
        }

        const wastePctElement = document.getElementById('metric-waste-pct');
        if (wastePctElement) {
            wastePctElement.textContent = `${CostCalculator.formatPercentage(results.wastePercentage)} of commitment`;
            wastePctElement.style.color = getPercentageColor(results.wastePercentage, 'waste');
        }
    }

    /**
     * Update optimal suggestion display
     */
    function updateOptimalSuggestion(results, scaledHourlyCosts) {
        const suggestionElement = document.getElementById('optimal-suggestion');
        const textElement = document.getElementById('suggestion-text');
        const titleElement = suggestionElement?.querySelector('.suggestion-title');

        if (!suggestionElement || !textElement || !titleElement) return;

        // Convert coverage to commitment values for display using central calculation module
        const optimalCoverage = results.optimalCoverageUnits;
        const currentCoverage = appState.coverageCost;
        const minCost = appState.minCost * (appState.loadFactor / 100); // Scale min cost by load factor

        // Calculate commitment values using centralized function
        const optimalCommitment = SPCalculations.commitmentFromCoverage(optimalCoverage, appState.savingsPercentage);
        const currentCommitment = SPCalculations.commitmentFromCoverage(currentCoverage, appState.savingsPercentage);

        // Calculate hourly savings
        // Use actual number of hours in the scaled data
        const numHours = scaledHourlyCosts?.length || 168;
        const currentHourlySavings = results.savings / numHours;

        // Check if we're at optimal commitment (within 1% tolerance)
        const isAtOptimalCommitment = Math.abs(currentCommitment - optimalCommitment) < (optimalCommitment * 0.01);

        // Calculate optimal savings
        let hourlySavingsAtOptimal;
        if (isAtOptimalCommitment) {
            // At optimal: use current savings (they're the same)
            hourlySavingsAtOptimal = currentHourlySavings;
        } else {
            // Not at optimal: use maxNetSavings from calculation
            const totalSavingsAtOptimal = results.optimalCoverage.maxNetSavings || 0;
            hourlySavingsAtOptimal = totalSavingsAtOptimal / numHours;

            // Ensure optimal never shows less savings than current (sanity check)
            // Optimal should always save at least as much as any other point
            hourlySavingsAtOptimal = Math.max(hourlySavingsAtOptimal, currentHourlySavings);
        }

        const additionalSavings = hourlySavingsAtOptimal - currentHourlySavings;

        // Detect which zone the current coverage is in (use scaled costs)
        const zoneInfo = CostCalculator.detectCoverageZone(
            currentCoverage,
            scaledHourlyCosts || [],
            appState.savingsPercentage
        );

        // Get suggestion with commitment dollar values, additional savings, and zone info
        const suggestion = CostCalculator.getOptimizationSuggestionDollars(
            currentCommitment,
            optimalCommitment,
            minCost,
            additionalSavings,
            zoneInfo
        );

        // Update status class - remove all old classes first
        suggestionElement.classList.remove(
            'status-optimal', 'status-warning', 'status-danger',
            'status-building', 'status-gaining', 'status-wasting', 'status-very-bad', 'status-losing-money'
        );
        suggestionElement.classList.add(`status-${suggestion.status}`);

        // Show optimal commitment with current in parentheses
        // Different wording when at optimal vs when not at optimal
        if (isAtOptimalCommitment) {
            // Already at optimal - show what you're currently saving
            const savingsPercent = ((currentHourlySavings / (results.onDemandCost / numHours)) * 100).toFixed(1);
            titleElement.innerHTML = `Optimal Commitment: ${CostCalculator.formatCurrency(optimalCommitment)}/h<br>
                <small style="font-weight: normal; opacity: 0.9;">
                    Saving ${CostCalculator.formatCurrency(currentHourlySavings)}/h vs on-demand (${savingsPercent}% discount)
                </small>`;
        } else {
            // Not at optimal - show what you could save at optimal vs what you're saving now
            titleElement.innerHTML = `Optimal Commitment: ${CostCalculator.formatCurrency(optimalCommitment)}/h (vs current ${CostCalculator.formatCurrency(currentCommitment)}/h)<br>
                <small style="font-weight: normal; opacity: 0.9;">
                    Would save ${CostCalculator.formatCurrency(hourlySavingsAtOptimal)}/h vs on-demand (current: ${CostCalculator.formatCurrency(currentHourlySavings)}/h)
                </small>`;
        }

        // Message already has dollar values formatted correctly
        textElement.textContent = `${suggestion.icon} ${suggestion.message}`;

        // Store zone info for use in metrics display
        currentCostResults.currentZone = zoneInfo;
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

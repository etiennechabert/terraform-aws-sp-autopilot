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
        contrast: 100,        // Contrast percentage (0-200%) - amplifies min/max delta
        onDemandRate: 0.10,
        currentLoadPattern: [],
        customCurve: null
    };

    let currentCostResults = null;

    function isCustomPattern(pattern) {
        return pattern === 'custom' || pattern === 'custom-paste' || pattern === 'custom-url';
    }

    /**
     * Initialize the application
     */
    function init() {
        console.log('Initializing AWS Savings Plan Simulator...');

        // Check for URL state
        const urlState = URLState.decodeState();
        if (urlState) {
            console.log('Restoring state from URL:', urlState);

            if (urlState.usageData) {
                loadUsageData(urlState.usageData, 'custom-url');
            } else if (urlState.pasteData) {
                loadUsageData(urlState.pasteData, 'custom-paste');
            } else {
                appState = { ...appState, ...urlState };
            }

            if (urlState.awsRecommendation) {
                appState.awsRecommendation = urlState.awsRecommendation;

                // If no existing SP plan, use AWS's estimated discount rate
                if (appState.usageDataLoaded && !appState.usageData?.current_coverage) {
                    const awsPct = Math.round(urlState.awsRecommendation.estimated_savings_percentage);
                    appState.savingsPercentage = awsPct;
                    appState.actualSavingsPercentage = awsPct;
                }
            }

            // Backward compat: old URLs with pattern=custom
            if (appState.pattern === 'custom') {
                appState.pattern = 'custom-paste';
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
    function loadUsageData(usageData, pattern) {
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

        // Actual existing SP coverage (0 when no SP)
        const currentCoverage = usageData.current_coverage || 0;

        // Update app state with real data
        appState = {
            ...appState,
            pattern: pattern,
            minCost: minCost,
            maxCost: maxCost,
            coverageCost: currentCoverage || minCost,  // Start slider at min-hourly if no SP
            customCurve: customCurve,
            savingsPercentage: savingsPercentage,  // Use actual discount from user's SPs
            actualSavingsPercentage: savingsPercentage,  // Preserve original for restoring after AWS strategy
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

        header.querySelectorAll('.usage-data-banner').forEach(el => el.remove());

        const spType = appState.usageDataLoaded && appState.usageData?.sp_type
            ? appState.usageData.sp_type
            : 'All Types';

        const savingsPct = appState.savingsPercentage || 30;
        const fromReporter = !!appState.usageData?.optimal_from_python;

        const banner = document.createElement('div');

        if (fromReporter) {
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
        } else {
            banner.className = 'usage-data-banner usage-data-banner-estimate';
            banner.innerHTML = `
                <div class="banner-content">
                    <span class="banner-icon">⚠️</span>
                    <span class="banner-text">
                        <strong>Rough Estimation</strong> - Manual CLI data with default ${savingsPct.toFixed(1)}% discount<br>
                        <small>For accurate purchase recommendations, deploy the <a href="https://github.com/etiennechabert/terraform-aws-sp-autopilot" target="_blank" rel="noopener" style="color: inherit; text-decoration: underline;">terraform-aws-sp-autopilot</a> reporter</small>
                    </span>
                </div>
            `;
        }

        header.appendChild(banner);
    }

    /**
     * Setup all event listeners
     */
    function setupEventListeners() {
        // Title reset link
        const titleLink = document.getElementById('title-reset-link');
        if (titleLink) {
            titleLink.addEventListener('click', (e) => {
                e.preventDefault();
                window.location.href = window.location.origin + window.location.pathname;
            });
        }

        // Pattern buttons (both full and compact)
        document.querySelectorAll('.pattern-btn, .pattern-btn-compact').forEach(btn => {
            btn.addEventListener('click', handlePatternBtnClick);
        });

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
            coverageSlider.value = appState.coverageCost;
            coverageSlider.addEventListener('input', handleCoverageChange);
        }

        // Savings percentage slider
        const savingsSlider = document.getElementById('savings-percentage');
        if (savingsSlider) {
            savingsSlider.value = appState.savingsPercentage;
            savingsSlider.addEventListener('input', handleSavingsChange);
        }

        // Savings source reset button (delegated)
        document.getElementById('savings-source')?.addEventListener('click', (e) => {
            if (e.target.id === 'savings-source-reset' && appState.actualSavingsPercentage) {
                appState.savingsPercentage = appState.actualSavingsPercentage;
                if (savingsSlider) savingsSlider.value = appState.savingsPercentage;
                updateSavingsDisplay(appState.savingsPercentage);
                calculateAndUpdateCosts();
            }
        });

        // Load factor slider (bottom vertical)
        const loadFactorSlider = document.getElementById('load-factor');
        if (loadFactorSlider) {
            loadFactorSlider.value = appState.loadFactor;
            loadFactorSlider.addEventListener('input', handleLoadFactorChange);
        }

        // Contrast sliders (main + compact)
        document.querySelectorAll('#contrast-slider, #contrast-slider-compact').forEach(el => {
            el.value = appState.contrast;
            el.addEventListener('input', handleContrastChange);
        });

        // Reset load factor button
        const resetLoadFactorButton = document.getElementById('reset-load-factor');
        if (resetLoadFactorButton) {
            resetLoadFactorButton.addEventListener('click', () => {
                handleLoadFactorChange({ target: { value: '100' } });
            });
        }

        // Advanced costs toggle
        const toggleAdvancedCosts = document.getElementById('toggle-advanced-costs');
        if (toggleAdvancedCosts) {
            toggleAdvancedCosts.addEventListener('click', () => {
                const panel = document.getElementById('advanced-costs');
                if (panel) panel.classList.toggle('hidden');
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

        // Custom data modal
        const modalCopyBtn = document.getElementById('modal-copy-btn');
        if (modalCopyBtn) modalCopyBtn.addEventListener('click', handleModalCopyCliCommand);

        const modalCancelBtn = document.getElementById('modal-cancel-btn');
        if (modalCancelBtn) modalCancelBtn.addEventListener('click', hideCustomDataModal);

        const modalLoadBtn = document.getElementById('modal-load-btn');
        if (modalLoadBtn) modalLoadBtn.addEventListener('click', handleModalLoad);

        const modalBackdrop = document.getElementById('custom-data-modal');
        if (modalBackdrop) {
            modalBackdrop.addEventListener('click', (e) => {
                if (e.target === modalBackdrop) hideCustomDataModal();
            });
        }

        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                if (!document.getElementById('custom-data-modal').classList.contains('hidden')) {
                    hideCustomDataModal();
                }
                if (!document.getElementById('no-url-data-modal').classList.contains('hidden')) {
                    hideNoUrlDataModal();
                }
            }
        });

        // No URL data modal
        const noUrlDataCloseBtn = document.getElementById('no-url-data-close-btn');
        if (noUrlDataCloseBtn) noUrlDataCloseBtn.addEventListener('click', hideNoUrlDataModal);

        const noUrlDataBackdrop = document.getElementById('no-url-data-modal');
        if (noUrlDataBackdrop) {
            noUrlDataBackdrop.addEventListener('click', (e) => {
                if (e.target === noUrlDataBackdrop) hideNoUrlDataModal();
            });
        }
    }

    /**
     * Update UI elements from current state
     */
    function updateUIFromState() {
        // Pattern buttons
        setActivePatternBtn(appState.pattern);

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
        syncLoadFactorSliders(appState.loadFactor);
        updateLoadFactorDisplay(appState.loadFactor);

        // Contrast sliders
        syncContrastSliders(appState.contrast);
        updateContrastDisplay(appState.contrast);

        // On-demand rate
        const onDemandRateInput = document.getElementById('on-demand-rate');
        if (onDemandRateInput) {
            onDemandRateInput.value = appState.onDemandRate;
        }
    }

    function setActivePatternBtn(pattern) {
        document.querySelectorAll('.pattern-btn, .pattern-btn-compact').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.pattern === pattern);
        });
    }

    function syncLoadFactorSliders(value) {
        const bottom = document.getElementById('load-factor');
        if (bottom) bottom.value = value;
    }

    /**
     * Handle pattern type change
     */
    function handlePatternBtnClick(event) {
        const btn = event.currentTarget;
        const value = btn.dataset.pattern;

        if (value === 'custom-paste') {
            showCustomDataModal();
            return;
        }

        if (value === 'custom-url') {
            let usageData = appState.usageData;
            if (!usageData) {
                const params = new URLSearchParams(window.location.search);
                const raw = params.get('usage');
                if (raw) usageData = URLState.decompressUsageData(raw);
            }
            if (usageData) {
                loadUsageData(usageData, 'custom-url');
                updateUIFromState();
                updateLoadPattern();
                calculateAndUpdateCosts();
                URLState.debouncedUpdateURL(appState);
                return;
            }
            showNoUrlDataModal();
            return;
        }

        appState.pattern = value;
        setActivePatternBtn(value);

        if (isCustomPattern(appState.pattern) && !appState.customCurve) {
            appState.customCurve = [...appState.currentLoadPattern];
        }

        updateLoadPattern();
        calculateAndUpdateCosts();
        URLState.debouncedUpdateURL(appState);

        if (value === 'random') {
            const name = LoadPatterns.getLastRandomName();
            if (name) showRandomLabel(name);
        } else {
            hideRandomLabel();
        }
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
        const sliderMax = parseFloat(event.target.max) || appState.maxCost;
        if (!isNaN(value) && value >= 0 && value <= sliderMax) {
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
        if (!isNaN(value) && value >= 10 && value <= 90) {
            appState.savingsPercentage = value;
            updateSavingsDisplay(value);
            updateCoverageDisplay(appState.coverageCost);
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
            syncLoadFactorSliders(value);
            updateLoadFactorDisplay(value);
            updateCoverageSliderMax();
            calculateAndUpdateCosts();
            URLState.debouncedUpdateURL(appState);
        }
    }

    function handleContrastChange(event) {
        const value = parseInt(event.target.value, 10);
        if (!isNaN(value) && value >= 0 && value <= 200) {
            appState.contrast = value;
            syncContrastSliders(value);
            updateContrastDisplay(value);
            updateLoadPattern(false);
            calculateAndUpdateCosts();
            URLState.debouncedUpdateURL(appState);
        }
    }

    function syncContrastSliders(value) {
        document.querySelectorAll('#contrast-slider, #contrast-slider-compact').forEach(el => {
            el.value = value;
        });
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
                aggressive: 0
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

        // AWS recommendation: convert commitment to on-demand equivalent using actual savings rate
        let awsRecommendation = null;
        if (appState.awsRecommendation) {
            const actualPct = appState.actualSavingsPercentage || appState.savingsPercentage;
            const newPurchaseCoverage = SPCalculations.coverageFromCommitment(
                appState.awsRecommendation.hourly_commitment,
                actualPct
            );
            awsRecommendation = (appState.currentCoverage || 0) + newPurchaseCoverage;
        }

        return {
            tooPrudent,
            minHourly,
            balanced,
            aggressive,
            awsRecommendation
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
            case 'aws':
                coverageCost = strategies.awsRecommendation;
                break;
            default:
                showToast('Unknown strategy', 'error');
                return;
        }

        // Restore actual savings percentage if it was overridden
        if (appState.actualSavingsPercentage) {
            appState.savingsPercentage = appState.actualSavingsPercentage;
        }

        // Update state
        appState.coverageCost = coverageCost;

        // Update savings slider to reflect active rate
        const savingsSlider = document.getElementById('savings-percentage');
        if (savingsSlider) {
            savingsSlider.value = appState.savingsPercentage;
        }
        updateSavingsDisplay(appState.savingsPercentage);

        // Update coverage slider
        const coverageSlider = document.getElementById('coverage-slider');
        if (coverageSlider) {
            coverageSlider.value = coverageCost;
        }

        // Update display
        updateCoverageDisplay(coverageCost);

        // Recalculate (strategies will be recalculated with the new savings %)
        calculateAndUpdateCosts();

        // Update URL
        URLState.debouncedUpdateURL(appState);

        // Show success message
        const strategyNames = {
            'too-prudent': 'Prudent 🐔',
            'min-hourly': 'Min-Hourly',
            'balanced': 'Balanced',
            'aggressive': 'Risky',
            'aws': 'Recommendation'
        };
        showToast(`${strategyNames[strategy]} strategy applied: ${CostCalculator.formatCurrency(coverageCost)}/h`);
    }

    /**
     * Generate savings tooltip HTML
     */
    function generateSavingsTooltip(pureOnDemand, commitmentCost, spilloverCost, savingsValue) {
        return `
            <div class="tooltip-line"><span class="tooltip-label">Pure On-Demand:</span><span class="tooltip-value-ondemand">${CostCalculator.formatCurrency(pureOnDemand)}/h</span></div>
            <div class="tooltip-line"><span class="tooltip-label">Commitment:</span><span class="tooltip-value-commitment">${CostCalculator.formatCurrency(commitmentCost)}/h</span></div>
            <div class="tooltip-line"><span class="tooltip-label">Spillover:</span><span class="tooltip-value-spillover">${CostCalculator.formatCurrency(spilloverCost)}/h</span></div>
            <div class="tooltip-calculation">
                <span class="tooltip-value-ondemand">${CostCalculator.formatCurrency(pureOnDemand)}/h</span> -
                (<span class="tooltip-value-commitment">${CostCalculator.formatCurrency(commitmentCost)}/h</span> +
                <span class="tooltip-value-spillover">${CostCalculator.formatCurrency(spilloverCost)}/h</span>) =
                <span class="tooltip-value-savings">${CostCalculator.formatCurrency(savingsValue)}/h</span>
            </div>
        `;
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

        // Helper to calculate what top metrics would show for a given coverage
        const calculateMetricsForCoverage = (coverageValue) => {
            const config = {
                hourlyCosts: scaledHourlyCosts,
                coverageCost: coverageValue,
                savingsPercentage: savingsPercentage,
                onDemandRate: appState.onDemandRate
            };
            return CostCalculator.calculateCosts(config);
        };


        // Helper to update a strategy card
        const updateStrategyCard = (strategyId, coverage) => {
            const value = document.getElementById(`strategy-${strategyId}-value`);
            const savings = document.getElementById(`strategy-${strategyId}-savings`);
            const savingsPct = document.getElementById(`strategy-${strategyId}-savings-pct`);
            const minHourlyPct = document.getElementById(`strategy-${strategyId}-min-hourly-pct`);
            const tooltip = document.getElementById(`strategy-${strategyId}-savings-tooltip`);

            if (value && savings && savingsPct && minHourlyPct) {
                const commitment = SPCalculations.commitmentFromCoverage(coverage, savingsPercentage);
                const results = calculateMetricsForCoverage(coverage);
                const minPct = minHourlyCommitment > 0 ? (commitment / minHourlyCommitment) * 100 : 100;

                value.textContent = `${CostCalculator.formatCurrency(coverage)}/h`;
                savings.textContent = `${CostCalculator.formatCurrency(results.savings / numHours)}/h`;
                savingsPct.textContent = `${results.savingsPercentageActual.toFixed(1)}% On-Demand`;
                minHourlyPct.textContent = `${minPct.toFixed(1)}% Min-Hourly`;

                if (tooltip) {
                    tooltip.innerHTML = generateSavingsTooltip(
                        hourlyOnDemand,
                        results.commitmentCost / numHours,
                        results.spilloverCost / numHours,
                        results.savings / numHours
                    );
                }

                // Show purchase info when usage data is loaded
                const desc = document.querySelector(`#strategy-${strategyId} .strategy-desc`);
                if (desc && appState.usageDataLoaded) {
                    const currentCommitment = SPCalculations.commitmentFromCoverage(appState.currentCoverage || 0, savingsPercentage);
                    const delta = commitment - currentCommitment;
                    const amt = CostCalculator.formatCurrency(Math.abs(delta));
                    if (delta > 0.005) {
                        desc.innerHTML = `Purchase ${currentCommitment > 0.005 ? 'additional ' : ''}<span class="purchase-amount">${amt}/h</span>`;
                    } else if (delta < -0.005) {
                        desc.innerHTML = `Reduce by <span class="purchase-amount reduce">${amt}/h</span>`;
                    } else {
                        desc.textContent = 'Current commitment';
                    }
                    desc.classList.add('visible');
                }
            }
        };

        // Update all strategy cards
        updateStrategyCard('too-prudent', strategies.tooPrudent);
        updateStrategyCard('min', strategies.minHourly);
        updateStrategyCard('balanced', strategies.balanced);
        updateStrategyCard('aggressive', strategies.aggressive);

        const awsBtn = document.getElementById('strategy-aws');
        if (strategies.awsRecommendation !== null) {
            updateStrategyCard('aws', strategies.awsRecommendation);
            awsBtn?.classList.remove('hidden');
            const awsDesc = document.getElementById('strategy-aws-desc');
            if (awsDesc && appState.awsRecommendation) {
                const awsPct = Math.round(appState.awsRecommendation.estimated_savings_percentage * 10) / 10;
                const actualPct = Math.round((appState.actualSavingsPercentage || appState.savingsPercentage) * 10) / 10;
                const commitment = appState.awsRecommendation.hourly_commitment;
                let desc = `Purchase additional <span class="purchase-amount">$${commitment.toFixed(2)}/h</span>`;
                if (Math.abs(awsPct - actualPct) > 1) {
                    desc += `<br><span class="aws-discount-warning">⚠ AWS estimated discount ${awsPct}% (actual: ${actualPct}%)</span>`;
                }
                awsDesc.innerHTML = desc;
            }
        } else {
            awsBtn?.classList.add('hidden');
        }

        // Detect and highlight active strategy
        const allButtons = document.querySelectorAll('.strategy-button');
        allButtons.forEach(btn => btn.classList.remove('active'));

        // Compare with tolerance for floating point comparison (2%)
        const highlightTolerance = 0.02;
        let activeButton = null;

        const tooPrudentDiff = Math.abs(currentCoverage - strategies.tooPrudent);
        const minDiff = Math.abs(currentCoverage - strategies.minHourly);
        const balancedDiff = Math.abs(currentCoverage - strategies.balanced);
        const aggressiveDiff = Math.abs(currentCoverage - strategies.aggressive);
        const awsDiff = strategies.awsRecommendation !== null ? Math.abs(currentCoverage - strategies.awsRecommendation) : Infinity;

        // Find closest match
        const minDistance = Math.min(tooPrudentDiff, minDiff, balancedDiff, aggressiveDiff, awsDiff);

        if (minDistance / Math.max(currentCoverage, 0.01) < highlightTolerance) {
            if (minDistance === tooPrudentDiff) {
                activeButton = document.getElementById('strategy-too-prudent');
            } else if (minDistance === minDiff) {
                activeButton = document.getElementById('strategy-min');
            } else if (minDistance === balancedDiff) {
                activeButton = document.getElementById('strategy-balanced');
            } else if (minDistance === aggressiveDiff) {
                activeButton = document.getElementById('strategy-aggressive');
            } else if (minDistance === awsDiff) {
                activeButton = document.getElementById('strategy-aws');
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
        const compactControls = document.querySelector('.compact-controls');

        if (!content || !button) return;

        content.classList.toggle('collapsed');
        button.classList.toggle('collapsed');

        if (compactControls) {
            compactControls.classList.toggle('hidden', !content.classList.contains('collapsed'));
        }
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

    function updateCoverageSliderMax() {
        const hourlyCosts = appState.hourlyCosts || [];
        if (hourlyCosts.length === 0) return;

        const loadFactor = appState.loadFactor / 100;
        const maxHourly = Math.max(...hourlyCosts) * loadFactor;

        const coverageSlider = document.getElementById('coverage-slider');
        if (coverageSlider) {
            coverageSlider.max = maxHourly;
            coverageSlider.step = maxHourly / 1000;
            if (appState.coverageCost > maxHourly) {
                appState.coverageCost = maxHourly;
                coverageSlider.value = appState.coverageCost;
                updateCoverageDisplay(appState.coverageCost);
            }
        }
    }

    /**
     * Update load pattern based on current state
     */
    function updateLoadPattern(regenerate) {
        let normalizedPattern;

        if (regenerate === false && appState.currentLoadPattern.length > 0) {
            normalizedPattern = appState.currentLoadPattern;
        } else if (isCustomPattern(appState.pattern) && appState.customCurve) {
            normalizedPattern = appState.customCurve;
        } else {
            normalizedPattern = LoadPatterns.generatePattern(appState.pattern);
        }

        appState.currentLoadPattern = normalizedPattern;

        // Find the actual min/max in the pattern
        const patternMin = Math.min(...normalizedPattern);
        const patternMax = Math.max(...normalizedPattern);
        const patternRange = patternMax - patternMin;

        // Apply contrast: scale the range around the midpoint
        const midpoint = (appState.minCost + appState.maxCost) / 2;
        const halfRange = (appState.maxCost - appState.minCost) / 2;
        const contrastFactor = appState.contrast / 100;
        const effectiveMin = Math.max(0, midpoint - halfRange * contrastFactor);
        const effectiveMax = midpoint + halfRange * contrastFactor;
        const costRange = effectiveMax - effectiveMin;

        const costPattern = normalizedPattern.map(normalized => {
            if (patternRange === 0) {
                return midpoint;
            }
            const normalizedInRange = (normalized - patternMin) / patternRange;
            return effectiveMin + (normalizedInRange * costRange);
        });

        // Store the actual hourly costs for use in cost calculations
        appState.hourlyCosts = costPattern;

        // Update load chart with cost data
        ChartManager.updateLoadChart(costPattern);

        // Update coverage slider max to match actual peak hourly cost
        updateCoverageSliderMax();

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

        // NOTE: This is equivalent to commitmentFromCoverage() in spCalculations.js
        const discountFactor = (1 - savingsPercentage / 100);
        const numHours = hourlyCosts.length;

        // Beyond maxCost, spillover=0, so breakeven = baselineCost / (discountFactor * numHours)
        const analyticalBreakeven = discountFactor > 0
            ? baselineCost / (discountFactor * numHours)
            : maxCost * 2;
        const searchLimit = Math.max(maxCost, analyticalBreakeven) * 1.2;
        const testIncrement = searchLimit / 500;

        let breakevenCoverage = searchLimit;
        for (let coverageCost = 0; coverageCost <= searchLimit; coverageCost += testIncrement) {
            let commitmentCost = 0;
            let spilloverCost = 0;

            for (let i = 0; i < numHours; i++) {
                commitmentCost += coverageCost * discountFactor;
                spilloverCost += Math.max(0, hourlyCosts[i] - coverageCost);
            }

            const totalCost = commitmentCost + spilloverCost;
            const netSavings = baselineCost - totalCost;

            if (netSavings < 0) {
                breakevenCoverage = coverageCost - testIncrement;
                break;
            }
        }

        // Generate data up to breakeven so all zones are computed,
        // but the chart x-axis will be capped at maxCost (commitment terms)
        const dataMaxCoverage = Math.max(maxCost, breakevenCoverage * 1.1);
        const curveData = [];
        const increment = dataMaxCoverage / 500;

        for (let coverageCost = 0; coverageCost <= dataMaxCoverage; coverageCost += increment) {
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
        // All points compare to optimal (positive if better, negative if worse, 0 at optimal)
        curveData.forEach(point => {
            point.extraSavings = point.netSavings - optimalNetSavings;
        });

        // Always use the current slider position for the vertical line
        const currentCoverageFromData = appState.coverageCost;

        // Update chart (use optimal from curve data for consistency)
        ChartManager.updateSavingsCurveChart({
            curveData,
            minHourlySavings,
            minCost,
            maxCost,
            baselineCost,
            currentCoverage: currentCoverageFromData,
            existingCoverage: appState.currentCoverage || 0,
            savingsPercentage,
            numHours: hourlyCosts.length
        });
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
            rateElement.textContent = `Coverage $${coverageCommitment.toFixed(2)}/h vs $${avgUsage.toFixed(2)}/h Avg Usage`;
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
        updateSavingsSourceHint();
    }

    function updateSavingsSourceHint() {
        const el = document.getElementById('savings-source');
        if (!el || !appState.usageDataLoaded) return;

        const actual = appState.actualSavingsPercentage;
        if (!actual) { el.classList.add('hidden'); return; }

        const source = appState.usageData?.current_coverage
            ? 'From your existing Savings Plans'
            : 'From AWS recommendation';
        const current = appState.savingsPercentage;
        const changed = Math.abs(current - actual) > 0.1;

        if (changed) {
            el.innerHTML = `${source} (${actual}%) — <button class="savings-source-reset" id="savings-source-reset">reset</button>`;
        } else {
            el.textContent = source;
        }
        el.classList.remove('hidden');
    }

    /**
     * Update load factor display
     */
    function updateLoadFactorDisplay(value) {
        const displays = [
            document.getElementById('load-factor-display')
        ];

        const delta = value - 100;
        displays.forEach(el => {
            if (!el) return;
            el.classList.remove('positive', 'negative', 'neutral');
            if (delta === 0) {
                el.textContent = '100%';
                el.classList.add('neutral');
            } else if (delta > 0) {
                el.textContent = `+${delta}%`;
                el.classList.add('positive');
            } else {
                el.textContent = `${delta}%`;
                el.classList.add('negative');
            }
        });

        const hintElement = document.getElementById('load-factor-hint');
        if (hintElement) {
            if (value === 100) {
                hintElement.textContent = 'Original usage level';
            } else {
                hintElement.textContent = `${value}% of original usage`;
            }
        }
    }

    function updateContrastDisplay(value) {
        document.querySelectorAll('#contrast-display, #contrast-display-compact').forEach(el => {
            el.textContent = `${value}%`;
            el.classList.remove('positive', 'negative', 'neutral');
            if (value === 100) {
                el.classList.add('neutral');
            } else if (value > 100) {
                el.classList.add('positive');
            } else {
                el.classList.add('negative');
            }
        });
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
            const savingsValue = results.savings / numHours;
            savingsElement.textContent = CostCalculator.formatCurrency(savingsValue) + '/h';

            // Apply color based on positive/negative
            savingsElement.classList.remove('positive', 'negative');
            if (savingsValue > 0) {
                savingsElement.classList.add('positive');
            } else if (savingsValue < 0) {
                savingsElement.classList.add('negative');
            }

            // Populate tooltip with calculation breakdown
            const tooltip = document.getElementById('metric-savings-tooltip');
            if (tooltip) {
                tooltip.innerHTML = generateSavingsTooltip(
                    results.onDemandCost / numHours,
                    results.commitmentCost / numHours,
                    results.spilloverCost / numHours,
                    results.savings / numHours
                );
            }

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

        // SP Commitment - show actual commitment cost (what user needs to pay)
        const commitmentElement = document.getElementById('metric-commitment');
        if (commitmentElement) {
            // Show the actual commitment cost
            const commitmentCost = SPCalculations.commitmentFromCoverage(appState.coverageCost, appState.savingsPercentage);
            commitmentElement.textContent = CostCalculator.formatCurrency(commitmentCost) + '/h';
        }

        const commitmentPctElement = document.getElementById('metric-commitment-pct');
        if (commitmentPctElement) {
            // Calculate how much of on-demand usage is covered by the commitment
            const avgOnDemandPerHour = results.onDemandCost / numHours;
            const coveragePct = avgOnDemandPerHour > 0
                ? (appState.coverageCost / avgOnDemandPerHour) * 100
                : 0;
            commitmentPctElement.textContent = `Covering ${CostCalculator.formatCurrency(appState.coverageCost)}/h - ${coveragePct.toFixed(1)}% of on-demand`;
            commitmentPctElement.style.color = getPercentageColor(coveragePct, 'commitment');
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

    // ===== Custom Data Modal =====

    function showCustomDataModal() {
        // Calculate date range: 7 full days ending today at midnight UTC (exclusive)
        const end = new Date();
        end.setUTCHours(0, 0, 0, 0);
        const start = new Date(end);
        start.setUTCDate(start.getUTCDate() - 7);

        const fmt = (d) => d.toISOString().slice(0, 19) + 'Z';
        const cmd = `aws ce get-savings-plans-coverage \\
  --time-period "Start=${fmt(start)},End=${fmt(end)}" \\
  --granularity HOURLY \\
  | jq -c '[.SavingsPlansCoverages[].Coverage.TotalCost | tonumber]'`;

        const cliEl = document.getElementById('modal-cli-command');
        if (cliEl) cliEl.textContent = cmd;

        // Reset state
        const textarea = document.getElementById('modal-textarea');
        if (textarea) {
            textarea.value = '';
            textarea.classList.remove('error');
        }
        const errorEl = document.getElementById('modal-error');
        if (errorEl) errorEl.classList.add('hidden');

        document.getElementById('custom-data-modal').classList.remove('hidden');
    }

    function hideCustomDataModal() {
        document.getElementById('custom-data-modal').classList.add('hidden');
    }

    function showNoUrlDataModal() {
        document.getElementById('no-url-data-modal').classList.remove('hidden');
    }

    function hideNoUrlDataModal() {
        document.getElementById('no-url-data-modal').classList.add('hidden');
    }

    function showModalError(message) {
        const textarea = document.getElementById('modal-textarea');
        if (textarea) textarea.classList.add('error');
        const errorEl = document.getElementById('modal-error');
        if (errorEl) {
            errorEl.textContent = message;
            errorEl.classList.remove('hidden');
        }
    }

    function handleModalCopyCliCommand() {
        const cliEl = document.getElementById('modal-cli-command');
        if (!cliEl) return;

        const text = cliEl.textContent;
        const btn = document.getElementById('modal-copy-btn');

        if (navigator.clipboard?.writeText) {
            navigator.clipboard.writeText(text).then(() => {
                if (btn) {
                    btn.textContent = 'Copied!';
                    setTimeout(() => { btn.textContent = 'Copy'; }, 2000);
                }
            });
        }
    }

    function handleModalLoad() {
        const textarea = document.getElementById('modal-textarea');
        const raw = textarea?.value?.trim();

        // Reset error state
        textarea?.classList.remove('error');
        const errorEl = document.getElementById('modal-error');
        if (errorEl) errorEl.classList.add('hidden');

        if (!raw) {
            showModalError('Please paste the output from the command.');
            return;
        }

        let hourlyCosts;
        try {
            hourlyCosts = JSON.parse(raw);
        } catch {
            showModalError('Invalid JSON. Make sure you copied the complete output.');
            return;
        }

        if (!Array.isArray(hourlyCosts) || hourlyCosts.length === 0) {
            showModalError('Expected a JSON array of numbers. Make sure you ran the full command.');
            return;
        }

        if (hourlyCosts.length < 24) {
            showModalError(`Only ${hourlyCosts.length} data points found. Need at least 24 hours.`);
            return;
        }

        const sorted = [...hourlyCosts].sort((a, b) => a - b);
        const percentile = (arr, p) => arr[Math.max(0, Math.ceil(arr.length * p / 100) - 1)];

        const usageData = {
            hourly_costs: hourlyCosts,
            stats: {
                min: sorted[0],
                max: sorted[sorted.length - 1],
                p50: percentile(sorted, 50),
                p75: percentile(sorted, 75),
                p90: percentile(sorted, 90),
                p95: percentile(sorted, 95)
            },
            savings_percentage: 30,
            current_coverage: sorted[0] * 0.80,
            sp_type: 'Compute'
        };

        const jsonStr = JSON.stringify(usageData);
        const deflated = pako.deflate(jsonStr);
        let binary = '';
        for (let i = 0; i < deflated.length; i++) {
            binary += String.fromCharCode(deflated[i]);
        }
        const encoded = encodeURIComponent(btoa(binary));

        const baseUrl = window.location.origin + window.location.pathname;
        window.location.href = `${baseUrl}?paste=${encoded}`;
    }

    /**
     * Show toast notification
     */
    function showRandomLabel(name) {
        const desc = document.querySelector('.section-load-pattern .section-description');
        if (!desc) return;
        let badge = desc.querySelector('.random-archetype-badge');
        if (!badge) {
            badge = document.createElement('span');
            badge.className = 'random-archetype-badge';
            desc.appendChild(badge);
        }
        badge.textContent = name;
    }

    function hideRandomLabel() {
        const badge = document.querySelector('.random-archetype-badge');
        if (badge) badge.remove();
    }

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

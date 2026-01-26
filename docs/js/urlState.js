/**
 * URL State Management
 * Handles encoding/decoding application state to/from URL parameters
 */

const URLState = (function() {
    'use strict';

    /**
     * Encode current application state to URL
     * @param {Object} state - Application state
     * @returns {string} Full URL with encoded state
     */
    function encodeState(state) {
        const params = new URLSearchParams();

        // Basic parameters
        if (state.pattern) {
            params.set('pattern', state.pattern);
        }
        if (state.minCost !== undefined) {
            params.set('min', state.minCost.toString());
        }
        if (state.maxCost !== undefined) {
            params.set('max', state.maxCost.toString());
        }
        if (state.coverageCost !== undefined) {
            params.set('coverage', state.coverageCost.toString());
        }
        if (state.savingsPercentage !== undefined) {
            params.set('savings', state.savingsPercentage.toString());
        }
        if (state.onDemandRate !== undefined && state.onDemandRate !== 0.10) {
            params.set('rate', state.onDemandRate.toString());
        }

        // For custom patterns, encode the curve data
        if (state.pattern === 'custom' && state.customCurve) {
            const compressed = compressCurve(state.customCurve);
            params.set('curve', compressed);
        }

        const queryString = params.toString();
        const baseUrl = window.location.origin + window.location.pathname;

        return queryString ? `${baseUrl}?${queryString}` : baseUrl;
    }

    /**
     * Decompress usage data from reporter
     * @param {string} compressed - Base64 encoded, pako-compressed JSON
     * @returns {Object|null} Usage data or null if invalid
     */
    function decompressUsageData(compressed) {
        try {
            // Decode base64
            const decoded = atob(decodeURIComponent(compressed));

            // Convert string to byte array
            const bytes = new Uint8Array(decoded.length);
            for (let i = 0; i < decoded.length; i++) {
                bytes[i] = decoded.charCodeAt(i);
            }

            // Decompress with pako
            const inflated = pako.inflate(bytes, { to: 'string' });

            // Parse JSON
            const data = JSON.parse(inflated);

            // Validate structure
            if (!data.hourly_costs || !Array.isArray(data.hourly_costs) || !data.stats) {
                throw new Error('Invalid usage data structure');
            }

            return data;
        } catch (error) {
            console.error('Failed to decompress usage data:', error);
            return null;
        }
    }

    /**
     * Decode state from current URL
     * @returns {Object|null} Decoded state or null if no parameters
     */
    function decodeState() {
        const params = new URLSearchParams(window.location.search);

        // Check if we have any parameters
        if (params.toString() === '') {
            return null;
        }

        const state = {};

        // Check for usage data from reporter
        const usageParam = params.get('usage');
        if (usageParam) {
            const usageData = decompressUsageData(usageParam);
            if (usageData) {
                state.usageData = usageData;
            }
        }

        // Pattern type
        const pattern = params.get('pattern');
        if (pattern && ['ecommerce', 'global247', 'batch', 'custom'].includes(pattern)) {
            state.pattern = pattern;
        }

        // Min cost
        const min = params.get('min');
        if (min) {
            const minValue = parseFloat(min);
            if (!isNaN(minValue) && minValue >= 0 && minValue <= 10000) {
                state.minCost = minValue;
            }
        }

        // Max cost
        const max = params.get('max');
        if (max) {
            const maxValue = parseFloat(max);
            if (!isNaN(maxValue) && maxValue > 0 && maxValue <= 10000) {
                state.maxCost = maxValue;
            }
        }

        // Coverage cost
        const coverage = params.get('coverage');
        if (coverage) {
            const coverageValue = parseFloat(coverage);
            if (!isNaN(coverageValue) && coverageValue >= 0 && coverageValue <= 10000) {
                state.coverageCost = coverageValue;
            }
        }

        // Savings percentage
        const savings = params.get('savings');
        if (savings) {
            const savingsValue = parseInt(savings, 10);
            if (!isNaN(savingsValue) && savingsValue >= 0 && savingsValue <= 99) {
                state.savingsPercentage = savingsValue;
            }
        }

        // On-Demand rate (optional)
        const rate = params.get('rate');
        if (rate) {
            const rateValue = parseFloat(rate);
            if (!isNaN(rateValue) && rateValue > 0 && rateValue <= 10) {
                state.onDemandRate = rateValue;
            }
        }

        // Custom curve data
        if (state.pattern === 'custom') {
            const curve = params.get('curve');
            if (curve) {
                try {
                    const decompressed = decompressCurve(curve);
                    if (decompressed && decompressed.length === 168) {
                        state.customCurve = decompressed;
                    }
                } catch (error) {
                    console.warn('Failed to decode custom curve:', error);
                }
            }
        }

        return Object.keys(state).length > 0 ? state : null;
    }

    /**
     * Update URL with current state (without page reload)
     * @param {Object} state - Application state
     */
    function updateURL(state) {
        const url = encodeState(state);
        const currentUrl = window.location.href;

        if (url !== currentUrl) {
            window.history.replaceState({}, '', url);
        }
    }

    /**
     * Compress curve data for URL encoding
     * Uses run-length encoding to compress repetitive values
     * @param {Array<number>} curve - 168-element array of normalized values (0-100)
     * @returns {string} Compressed string
     */
    function compressCurve(curve) {
        if (!curve || curve.length !== 168) {
            throw new Error('Curve must be 168 elements');
        }

        // Round values to integers and compress using run-length encoding
        const rounded = curve.map(v => Math.round(v));

        // Simple run-length encoding
        const encoded = [];
        let currentValue = rounded[0];
        let count = 1;

        for (let i = 1; i < rounded.length; i++) {
            if (rounded[i] === currentValue && count < 99) {
                count++;
            } else {
                // Push current run
                encoded.push(`${currentValue}:${count}`);
                currentValue = rounded[i];
                count = 1;
            }
        }
        // Push last run
        encoded.push(`${currentValue}:${count}`);

        // Join and encode
        const joined = encoded.join(',');
        return btoa(joined); // Base64 encode
    }

    /**
     * Decompress curve data from URL
     * @param {string} compressed - Compressed curve string
     * @returns {Array<number>} 168-element array
     */
    function decompressCurve(compressed) {
        try {
            // Base64 decode
            const decoded = atob(compressed);

            // Split into runs
            const runs = decoded.split(',');
            const curve = [];

            for (const run of runs) {
                const [value, count] = run.split(':').map(Number);

                if (isNaN(value) || isNaN(count) || count <= 0) {
                    throw new Error('Invalid run format');
                }

                // Expand run
                for (let i = 0; i < count; i++) {
                    curve.push(value);
                }
            }

            if (curve.length !== 168) {
                throw new Error(`Expected 168 values, got ${curve.length}`);
            }

            return curve;

        } catch (error) {
            console.error('Failed to decompress curve:', error);
            return null;
        }
    }

    /**
     * Copy current URL to clipboard
     * @returns {Promise<boolean>} Success status
     */
    async function copyURLToClipboard() {
        const url = window.location.href;

        try {
            if (navigator.clipboard && navigator.clipboard.writeText) {
                await navigator.clipboard.writeText(url);
                return true;
            } else {
                // Fallback for older browsers
                const textarea = document.createElement('textarea');
                textarea.value = url;
                textarea.style.position = 'fixed';
                textarea.style.opacity = '0';
                document.body.appendChild(textarea);
                textarea.select();
                const success = document.execCommand('copy');
                document.body.removeChild(textarea);
                return success;
            }
        } catch (error) {
            console.error('Failed to copy URL:', error);
            return false;
        }
    }

    /**
     * Get shareable URL with current state
     * @param {Object} state - Application state
     * @returns {string} Shareable URL
     */
    function getShareableURL(state) {
        return encodeState(state);
    }

    /**
     * Parse URL parameters into object
     * @returns {Object} URL parameters as key-value pairs
     */
    function getURLParams() {
        const params = new URLSearchParams(window.location.search);
        const result = {};

        for (const [key, value] of params.entries()) {
            result[key] = value;
        }

        return result;
    }

    /**
     * Check if URL has state parameters
     * @returns {boolean} True if URL contains state parameters
     */
    function hasURLState() {
        return window.location.search.length > 0;
    }

    /**
     * Clear all URL parameters
     */
    function clearURLParams() {
        const baseUrl = window.location.origin + window.location.pathname;
        window.history.replaceState({}, '', baseUrl);
    }

    /**
     * Debounce function to limit URL updates
     * @param {Function} func - Function to debounce
     * @param {number} wait - Wait time in milliseconds
     * @returns {Function} Debounced function
     */
    function debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }

    // Create debounced version of updateURL
    const debouncedUpdateURL = debounce(updateURL, 500);

    // Public API
    return {
        encodeState,
        decodeState,
        updateURL,
        debouncedUpdateURL,
        copyURLToClipboard,
        getShareableURL,
        getURLParams,
        hasURLState,
        clearURLParams,
        compressCurve,
        decompressCurve,
        decompressUsageData
    };
})();

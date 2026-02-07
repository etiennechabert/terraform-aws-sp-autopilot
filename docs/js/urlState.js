/**
 * URL State Management
 * Handles encoding/decoding application state to/from URL parameters
 */

const URLState = (function() {
    'use strict';

    /**
     * Parse a numeric parameter from URL params with validation
     * @param {URLSearchParams} params - URL search params
     * @param {string} paramName - Parameter name to read
     * @param {number} min - Minimum valid value
     * @param {number} max - Maximum valid value
     * @param {Function} parseFunc - Number.parseFloat or Number.parseInt
     * @param {boolean} [exclusiveMin=false] - If true, value must be strictly greater than min
     * @returns {number|null} Parsed value or null if invalid/missing
     */
    function parseNumericParam(params, paramName, min, max, parseFunc, exclusiveMin = false) {
        const raw = params.get(paramName);
        if (!raw) return null;
        const value = parseFunc(raw);
        if (Number.isNaN(value)) return null;
        const aboveMin = exclusiveMin ? value > min : value >= min;
        if (aboveMin && value <= max) return value;
        return null;
    }

    /**
     * Encode current application state to URL
     * @param {Object} state - Application state
     * @returns {string} Full URL with encoded state
     */
    function encodeState(state) {
        const params = new URLSearchParams();

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
        if (state.onDemandRate !== undefined && state.onDemandRate !== 0.1) {
            params.set('rate', state.onDemandRate.toString());
        }

        if ((state.pattern === 'custom' || state.pattern === 'custom-paste' || state.pattern === 'custom-url') && state.customCurve) {
            const compressed = compressCurve(state.customCurve);
            params.set('curve', compressed);
        }

        const queryString = params.toString();
        const baseUrl = globalThis.location.origin + globalThis.location.pathname;

        return queryString ? `${baseUrl}?${queryString}` : baseUrl;
    }

    /**
     * Decompress usage data from reporter
     * @param {string} compressed - Base64 encoded, pako-compressed JSON
     * @returns {Object|null} Usage data or null if invalid
     */
    function decompressUsageData(compressed) {
        try {
            const decoded = atob(decodeURIComponent(compressed));

            const bytes = new Uint8Array(decoded.length);
            for (let i = 0; i < decoded.length; i++) {
                bytes[i] = decoded.codePointAt(i);
            }

            // Try zlib (deflate) first, then gzip
            let inflated;
            try {
                inflated = pako.inflate(bytes, { to: 'string' });
            } catch {
                inflated = pako.ungzip(bytes, { to: 'string' });
            }
            const data = JSON.parse(inflated);

            if (!data.hourly_costs || !Array.isArray(data.hourly_costs)) {
                throw new Error('Invalid usage data structure');
            }

            // Compute stats if missing (e.g. from CLI-generated data)
            if (!data.stats) {
                const sorted = [...data.hourly_costs].sort((a, b) => a - b);
                const pct = (arr, p) => arr[Math.max(0, Math.ceil(arr.length * p / 100) - 1)];
                data.stats = {
                    min: sorted[0],
                    max: sorted[sorted.length - 1],
                    p50: pct(sorted, 50),
                    p75: pct(sorted, 75),
                    p90: pct(sorted, 90),
                    p95: pct(sorted, 95)
                };
                if (data.current_coverage === undefined) {
                    data.current_coverage = sorted[0];
                }
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
        const params = new URLSearchParams(globalThis.location.search);

        if (params.toString() === '') {
            return null;
        }

        const state = {};

        const usageParam = params.get('usage');
        if (usageParam) {
            const usageData = decompressUsageData(usageParam);
            if (usageData) {
                state.usageData = usageData;
            }
        }

        const pasteParam = params.get('paste');
        if (pasteParam) {
            const pasteData = decompressUsageData(pasteParam);
            if (pasteData) {
                state.pasteData = pasteData;
            }
        }

        const pattern = params.get('pattern');
        if (pattern && ['ecommerce', 'global247', 'batch', 'custom', 'custom-paste', 'custom-url'].includes(pattern)) {
            state.pattern = pattern;
        }

        const minValue = parseNumericParam(params, 'min', 0, 10000, Number.parseFloat);
        if (minValue !== null) state.minCost = minValue;

        const maxValue = parseNumericParam(params, 'max', 0, 10000, Number.parseFloat, true);
        if (maxValue !== null) state.maxCost = maxValue;

        const coverageValue = parseNumericParam(params, 'coverage', 0, 10000, Number.parseFloat);
        if (coverageValue !== null) state.coverageCost = coverageValue;

        const savingsValue = parseNumericParam(params, 'savings', 0, 99, (v) => Number.parseInt(v, 10));
        if (savingsValue !== null) state.savingsPercentage = savingsValue;

        const rateValue = parseNumericParam(params, 'rate', 0, 10, Number.parseFloat, true);
        if (rateValue !== null) state.onDemandRate = rateValue;

        if (state.pattern === 'custom' || state.pattern === 'custom-paste' || state.pattern === 'custom-url') {
            const curve = params.get('curve');
            if (curve) {
                try {
                    const decompressed = decompressCurve(curve);
                    if (decompressed?.length === 168) {
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
        const currentUrl = globalThis.location.href;

        if (url !== currentUrl) {
            globalThis.history.replaceState({}, '', url);
        }
    }

    /**
     * Compress curve data for URL encoding
     * Uses run-length encoding to compress repetitive values
     * @param {Array<number>} curve - 168-element array of normalized values (0-100)
     * @returns {string} Compressed string
     */
    function compressCurve(curve) {
        if (!curve?.length || curve.length !== 168) {
            throw new Error('Curve must be 168 elements');
        }

        const rounded = curve.map(v => Math.round(v));

        const encoded = [];
        let currentValue = rounded[0];
        let count = 1;

        for (let i = 1; i < rounded.length; i++) {
            if (rounded[i] === currentValue && count < 99) {
                count++;
            } else {
                encoded.push(`${currentValue}:${count}`);
                currentValue = rounded[i];
                count = 1;
            }
        }
        encoded.push(`${currentValue}:${count}`);

        const joined = encoded.join(',');
        return btoa(joined);
    }

    /**
     * Decompress curve data from URL
     * @param {string} compressed - Compressed curve string
     * @returns {Array<number>} 168-element array
     */
    function decompressCurve(compressed) {
        try {
            const decoded = atob(compressed);
            const runs = decoded.split(',');
            const curve = [];

            for (const run of runs) {
                const [value, count] = run.split(':').map(Number);

                if (Number.isNaN(value) || Number.isNaN(count) || count <= 0) {
                    throw new Error('Invalid run format');
                }

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
        const url = globalThis.location.href;

        try {
            if (navigator.clipboard?.writeText) {
                await navigator.clipboard.writeText(url);
                return true;
            } else {
                const textarea = document.createElement('textarea');
                textarea.value = url;
                textarea.style.position = 'fixed';
                textarea.style.opacity = '0';
                document.body.appendChild(textarea);
                textarea.select();
                const success = document.execCommand('copy');
                textarea.remove();
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
        const params = new URLSearchParams(globalThis.location.search);
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
        return globalThis.location.search.length > 0;
    }

    /**
     * Clear all URL parameters
     */
    function clearURLParams() {
        const baseUrl = globalThis.location.origin + globalThis.location.pathname;
        globalThis.history.replaceState({}, '', baseUrl);
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

    const debouncedUpdateURL = debounce(updateURL, 500);

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

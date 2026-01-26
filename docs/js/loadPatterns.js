/**
 * Load Pattern Generation System
 * Generates 168-hour (7-day) normalized load patterns
 */

const LoadPatterns = (function() {
    'use strict';

    /**
     * Generate Ecommerce load pattern
     * Weekdays: Low overnight, morning ramp, lunch dip, evening peak
     * Weekends: Later start, sustained evening
     */
    function generateEcommercePattern() {
        const pattern = [];

        for (let day = 0; day < 7; day++) {
            const isWeekend = day === 5 || day === 6; // Saturday, Sunday

            for (let hour = 0; hour < 24; hour++) {
                let usage;

                if (isWeekend) {
                    // Weekend pattern: later start, sustained evening
                    if (hour >= 0 && hour < 6) {
                        usage = 0.10; // Very low overnight
                    } else if (hour >= 6 && hour < 10) {
                        usage = 0.15 + (hour - 6) * 0.10; // Slow morning ramp
                    } else if (hour >= 10 && hour < 14) {
                        usage = 0.55 + (hour - 10) * 0.075; // Midday build
                    } else if (hour >= 14 && hour < 18) {
                        usage = 0.85; // Afternoon plateau
                    } else if (hour >= 18 && hour < 23) {
                        usage = 0.95; // Evening peak
                    } else {
                        usage = 0.50; // Late night decline
                    }
                } else {
                    // Weekday pattern: standard business with evening peak
                    if (hour >= 0 && hour < 6) {
                        usage = 0.15; // Low overnight
                    } else if (hour >= 6 && hour < 8) {
                        usage = 0.15 + (hour - 6) * 0.175; // Morning ramp
                    } else if (hour >= 8 && hour < 12) {
                        usage = 0.50 + (hour - 8) * 0.0875; // Morning peak build
                    } else if (hour >= 12 && hour < 13) {
                        usage = 0.70; // Lunch dip
                    } else if (hour >= 13 && hour < 17) {
                        usage = 0.75 + (hour - 13) * 0.025; // Afternoon recovery
                    } else if (hour >= 17 && hour < 20) {
                        usage = 0.85 + (hour - 17) * 0.033; // Evening surge
                    } else if (hour >= 20 && hour < 22) {
                        usage = 0.95; // Evening peak
                    } else {
                        usage = 0.95 - (hour - 22) * 0.40; // Night decline
                    }
                }

                pattern.push(Math.min(1.0, Math.max(0, usage)));
            }
        }

        return pattern;
    }

    /**
     * Generate Global 24/7 load pattern
     * Consistent high utilization with gentle regional waves
     */
    function generateGlobal247Pattern() {
        const pattern = [];

        for (let day = 0; day < 7; day++) {
            const isWeekend = day === 5 || day === 6;
            const baselineWeekday = 0.75;
            const baselineWeekend = 0.70;
            const baseline = isWeekend ? baselineWeekend : baselineWeekday;

            for (let hour = 0; hour < 24; hour++) {
                // Create gentle sine wave with 8-hour period (3 regional handoffs per day)
                const totalHour = day * 24 + hour;
                const wave = Math.sin((totalHour / 8) * Math.PI * 2) * 0.10;

                const usage = baseline + wave;
                pattern.push(Math.min(1.0, Math.max(0, usage)));
            }
        }

        return pattern;
    }

    /**
     * Generate Batch Processing load pattern
     * Sharp spikes at scheduled times, low baseline
     */
    function generateBatchPattern() {
        const pattern = [];

        for (let day = 0; day < 7; day++) {
            const isWeekend = day === 5 || day === 6;

            for (let hour = 0; hour < 24; hour++) {
                let usage = 0.05; // Low baseline

                if (isWeekend) {
                    // Weekend: Only overnight batch
                    if (hour >= 2 && hour < 5) {
                        // 2am-5am spike (bell curve)
                        const peakHour = 3;
                        const distance = Math.abs(hour - peakHour);
                        usage = distance === 0 ? 1.0 : (distance === 1 ? 0.85 : 0.60);
                    }
                } else {
                    // Weekday: Three scheduled batches
                    // Early morning batch (2am-5am)
                    if (hour >= 2 && hour < 5) {
                        const peakHour = 3;
                        const distance = Math.abs(hour - peakHour);
                        usage = distance === 0 ? 1.0 : (distance === 1 ? 0.90 : 0.70);
                    }
                    // Mid-morning batch (10am-1pm)
                    else if (hour >= 10 && hour < 13) {
                        const peakHour = 11;
                        const distance = Math.abs(hour - peakHour);
                        usage = distance === 0 ? 1.0 : (distance === 1 ? 0.85 : 0.65);
                    }
                    // Evening batch (6pm-9pm)
                    else if (hour >= 18 && hour < 21) {
                        const peakHour = 19;
                        const distance = Math.abs(hour - peakHour);
                        usage = distance === 0 ? 1.0 : (distance === 1 ? 0.90 : 0.70);
                    }
                }

                pattern.push(Math.min(1.0, Math.max(0, usage)));
            }
        }

        return pattern;
    }

    /**
     * Generate load pattern by type
     * @param {string} type - 'ecommerce', 'global247', 'batch', or 'custom'
     * @returns {Array<number>} 168-element array of normalized values (0-1)
     */
    function generatePattern(type) {
        switch (type) {
            case 'ecommerce':
                return generateEcommercePattern();
            case 'global247':
                return generateGlobal247Pattern();
            case 'batch':
                return generateBatchPattern();
            case 'custom':
                // Start with ecommerce as base for custom editing
                return generateEcommercePattern();
            default:
                console.warn(`Unknown pattern type: ${type}, defaulting to ecommerce`);
                return generateEcommercePattern();
        }
    }

    /**
     * Scale normalized pattern to actual usage values
     * @param {Array<number>} pattern - Normalized pattern (0-1)
     * @param {number} peakValue - Peak usage value in actual units
     * @returns {Array<number>} Scaled pattern
     */
    function scalePattern(pattern, peakValue) {
        return pattern.map(normalizedValue => normalizedValue * peakValue);
    }

    /**
     * Smooth curve using moving average
     * @param {Array<number>} points - Data points to smooth
     * @param {number} windowSize - Window size for moving average (default: 3)
     * @returns {Array<number>} Smoothed data
     */
    function smoothCurve(points, windowSize = 3) {
        if (points.length === 0) return [];

        const smoothed = [];
        const halfWindow = Math.floor(windowSize / 2);

        for (let i = 0; i < points.length; i++) {
            let sum = 0;
            let count = 0;

            for (let j = -halfWindow; j <= halfWindow; j++) {
                const index = i + j;
                if (index >= 0 && index < points.length) {
                    sum += points[index];
                    count++;
                }
            }

            smoothed.push(sum / count);
        }

        return smoothed;
    }

    /**
     * Get day name from hour index
     * @param {number} hour - Hour index (0-167)
     * @returns {string} Day name
     */
    function getDayName(hour) {
        const dayNames = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
        const dayIndex = Math.floor(hour / 24);
        return dayNames[dayIndex] || 'Unknown';
    }

    /**
     * Format hour index as "Day HH:00"
     * @param {number} hour - Hour index (0-167)
     * @returns {string} Formatted time string
     */
    function formatTimeLabel(hour) {
        const dayName = getDayName(hour);
        const hourOfDay = hour % 24;
        const period = hourOfDay >= 12 ? 'pm' : 'am';
        const displayHour = hourOfDay === 0 ? 12 : (hourOfDay > 12 ? hourOfDay - 12 : hourOfDay);
        return `${dayName} ${displayHour}${period}`;
    }

    /**
     * Format hour index for X-axis display (cleaner format)
     * @param {number} hour - Hour index (0-167)
     * @returns {string} Formatted label for chart axis
     */
    function formatXAxisLabel(hour) {
        const hourOfDay = hour % 24;

        // Show day name at midnight (start of each day)
        if (hourOfDay === 0) {
            return getDayName(hour);
        }

        // Show noon marker
        if (hourOfDay === 12) {
            return '12pm';
        }

        // Don't show other hours on X-axis
        return '';
    }

    /**
     * Create control points for interactive curve editing
     * Reduces 168 points to editable control points (every 4 hours = 42 points)
     * @param {Array<number>} pattern - Full 168-hour pattern
     * @returns {Array<Object>} Control points with indices and values
     */
    function createControlPoints(pattern, interval = 4) {
        const controlPoints = [];

        for (let i = 0; i < pattern.length; i += interval) {
            controlPoints.push({
                index: i,
                value: pattern[i]
            });
        }

        return controlPoints;
    }

    /**
     * Interpolate full pattern from control points
     * @param {Array<Object>} controlPoints - Control points with index and value
     * @param {number} length - Desired output length (168)
     * @returns {Array<number>} Interpolated pattern
     */
    function interpolateFromControlPoints(controlPoints, length = 168) {
        const pattern = new Array(length);

        for (let i = 0; i < length; i++) {
            // Find surrounding control points
            let prevPoint = null;
            let nextPoint = null;

            for (let j = 0; j < controlPoints.length; j++) {
                if (controlPoints[j].index <= i) {
                    prevPoint = controlPoints[j];
                }
                if (controlPoints[j].index >= i && !nextPoint) {
                    nextPoint = controlPoints[j];
                    break;
                }
            }

            // Interpolate value
            if (prevPoint && nextPoint && prevPoint.index !== nextPoint.index) {
                const t = (i - prevPoint.index) / (nextPoint.index - prevPoint.index);
                pattern[i] = prevPoint.value + t * (nextPoint.value - prevPoint.value);
            } else if (prevPoint) {
                pattern[i] = prevPoint.value;
            } else if (nextPoint) {
                pattern[i] = nextPoint.value;
            } else {
                pattern[i] = 0;
            }
        }

        return pattern;
    }

    /**
     * Calculate pattern statistics
     * @param {Array<number>} pattern - Usage pattern
     * @returns {Object} Statistics (min, max, avg, median, percentiles)
     */
    function calculatePatternStats(pattern) {
        const sorted = [...pattern].sort((a, b) => a - b);
        const sum = pattern.reduce((acc, val) => acc + val, 0);

        return {
            min: sorted[0],
            max: sorted[sorted.length - 1],
            avg: sum / pattern.length,
            median: sorted[Math.floor(sorted.length / 2)],
            p25: sorted[Math.floor(sorted.length * 0.25)],
            p50: sorted[Math.floor(sorted.length * 0.50)],
            p75: sorted[Math.floor(sorted.length * 0.75)],
            p90: sorted[Math.floor(sorted.length * 0.90)]
        };
    }

    // Public API
    return {
        generatePattern,
        scalePattern,
        smoothCurve,
        getDayName,
        formatTimeLabel,
        formatXAxisLabel,
        createControlPoints,
        interpolateFromControlPoints,
        calculatePatternStats
    };
})();

/**
 * Load Pattern Generation System
 * Generates 168-hour (7-day) normalized load patterns
 */

const LoadPatterns = (function() {
    'use strict';

    function getEcommerceWeekendUsage(hour) {
        if (hour >= 0 && hour < 6) {
            return 0.1;
        } else if (hour >= 6 && hour < 10) {
            return 0.15 + (hour - 6) * 0.1;
        } else if (hour >= 10 && hour < 14) {
            return 0.55 + (hour - 10) * 0.075;
        } else if (hour >= 14 && hour < 18) {
            return 0.85;
        } else if (hour >= 18 && hour < 23) {
            return 0.95;
        }
        return 0.5;
    }

    function getEcommerceWeekdayUsage(hour) {
        if (hour >= 0 && hour < 6) {
            return 0.15;
        } else if (hour >= 6 && hour < 8) {
            return 0.15 + (hour - 6) * 0.175;
        } else if (hour >= 8 && hour < 12) {
            return 0.5 + (hour - 8) * 0.0875;
        } else if (hour >= 12 && hour < 13) {
            return 0.7;
        } else if (hour >= 13 && hour < 17) {
            return 0.75 + (hour - 13) * 0.025;
        } else if (hour >= 17 && hour < 20) {
            return 0.85 + (hour - 17) * 0.033;
        } else if (hour >= 20 && hour < 22) {
            return 0.95;
        }
        return 0.95 - (hour - 22) * 0.4;
    }

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
                const usage = isWeekend
                    ? getEcommerceWeekendUsage(hour)
                    : getEcommerceWeekdayUsage(hour);

                pattern.push(Math.min(1, Math.max(0, usage)));
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
            const baselineWeekend = 0.7;
            const baseline = isWeekend ? baselineWeekend : baselineWeekday;

            for (let hour = 0; hour < 24; hour++) {
                const totalHour = day * 24 + hour;
                const wave = Math.sin((totalHour / 8) * Math.PI * 2) * 0.1;

                const usage = baseline + wave;
                pattern.push(Math.min(1, Math.max(0, usage)));
            }
        }

        return pattern;
    }

    /**
     * Generate Flat load pattern
     * Constant 100% utilization
     */
    function generateFlatPattern() {
        const pattern = [];

        for (let day = 0; day < 7; day++) {
            for (let hour = 0; hour < 24; hour++) {
                pattern.push(1);
            }
        }

        return pattern;
    }

    function calculateBatchSpike(hour, peakHour, peakUsage, nearUsage, farUsage) {
        const distance = Math.abs(hour - peakHour);
        if (distance === 0) return peakUsage;
        if (distance === 1) return nearUsage;
        return farUsage;
    }

    function getBatchWeekendUsage(hour) {
        if (hour >= 2 && hour < 5) {
            return calculateBatchSpike(hour, 3, 1, 0.85, 0.6);
        }
        return 0.05;
    }

    function getBatchWeekdayUsage(hour) {
        if (hour >= 2 && hour < 5) {
            return calculateBatchSpike(hour, 3, 1, 0.9, 0.7);
        } else if (hour >= 10 && hour < 13) {
            return calculateBatchSpike(hour, 11, 1, 0.85, 0.65);
        } else if (hour >= 18 && hour < 21) {
            return calculateBatchSpike(hour, 19, 1, 0.9, 0.7);
        }
        return 0.05;
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
                const usage = isWeekend
                    ? getBatchWeekendUsage(hour)
                    : getBatchWeekdayUsage(hour);

                pattern.push(Math.min(1, Math.max(0, usage)));
            }
        }

        return pattern;
    }

    /**
     * Generate load pattern by type
     * @param {string} type - 'ecommerce', 'global247', 'flat', 'batch', or 'custom'
     * @returns {Array<number>} 168-element array of normalized values (0-1)
     */
    function generatePattern(type) {
        switch (type) {
            case 'ecommerce':
                return generateEcommercePattern();
            case 'global247':
                return generateGlobal247Pattern();
            case 'flat':
                return generateFlatPattern();
            case 'batch':
                return generateBatchPattern();
            case 'custom':
            case 'custom-paste':
            case 'custom-url':
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
        const dayIndex = Math.floor(hour / 24) % 7;
        return dayNames[dayIndex];
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

    function findSurroundingControlPoints(controlPoints, targetIndex) {
        let prevPoint = null;
        let nextPoint = null;

        for (const point of controlPoints) {
            if (point.index <= targetIndex) {
                prevPoint = point;
            }
            if (point.index >= targetIndex && !nextPoint) {
                nextPoint = point;
                break;
            }
        }

        return { prevPoint, nextPoint };
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
            const { prevPoint, nextPoint } = findSurroundingControlPoints(controlPoints, i);

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
            max: sorted.at(-1),
            avg: sum / pattern.length,
            median: sorted[Math.floor(sorted.length / 2)],
            p25: sorted[Math.floor(sorted.length * 0.25)],
            p50: sorted[Math.floor(sorted.length * 0.5)],
            p75: sorted[Math.floor(sorted.length * 0.75)],
            p90: sorted[Math.floor(sorted.length * 0.9)]
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

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
     * Generate Business Hours load pattern
     * High during 9-18, low evenings/nights, minimal weekends
     */
    function generateBusinessHoursPattern() {
        const pattern = [];

        for (let day = 0; day < 7; day++) {
            const isWeekend = day === 5 || day === 6;

            for (let hour = 0; hour < 24; hour++) {
                let usage;
                if (isWeekend) {
                    usage = 0.08;
                } else if (hour >= 8 && hour < 20) {
                    if (hour < 9) usage = 0.6;
                    else if (hour === 12) usage = 0.75;
                    else if (hour >= 18) usage = 0.7 - (hour - 18) * 0.15;
                    else usage = 0.9 + Math.sin((hour - 8) * 0.25) * 0.1;
                } else if (hour >= 6 && hour < 8) {
                    usage = 0.05 + (hour - 6) * 0.25;
                } else if (hour >= 20 && hour < 22) {
                    usage = 0.4 - (hour - 20) * 0.17;
                } else {
                    usage = 0.05;
                }
                pattern.push(Math.min(1, Math.max(0, usage)));
            }
        }

        return pattern;
    }

    let lastRandomName = null;
    let recentPicks = [];

    function generateRandomPattern() {
        const archetypes = [
            { fn: randomMultiPeak, name: 'Multi-Peak' },
            { fn: randomSpiky, name: 'Cron Jobs' },
            { fn: randomPlateau, name: 'Plateau' },
            { fn: randomGradual, name: 'Gradual Ramp' },
            { fn: randomHighBase, name: 'High Baseline' },
            { fn: randomNocturnal, name: 'Nocturnal' },
            { fn: randomBlackFriday, name: 'Black Friday' },
            { fn: randomLaunchDay, name: 'Launch Day' },
            { fn: randomDoubleShift, name: 'Double Shift' },
            { fn: randomSeasonalDecline, name: 'Seasonal Decline' },
            { fn: randomHighWeekend, name: 'High Weekend' },
        ];
        const maxHistory = archetypes.length - 1;
        const candidates = archetypes.filter(a => !recentPicks.includes(a.name));
        const pick = candidates[Math.floor(Math.random() * candidates.length)];
        recentPicks.push(pick.name);
        if (recentPicks.length > maxHistory) recentPicks.shift();
        lastRandomName = pick.name;
        return pick.fn();
    }

    function getLastRandomName() {
        return lastRandomName;
    }

    // Multi-peak: 2-3 peaks per day at random hours
    function randomMultiPeak() {
        const numPeaks = 2 + Math.floor(Math.random() * 2);
        const peaks = [];
        for (let i = 0; i < numPeaks; i++) {
            peaks.push({ hour: Math.floor(Math.random() * 24), width: 1.5 + Math.random() * 3 });
        }
        const baseline = 0.05 + Math.random() * 0.15;
        const weekendFactor = 0.3 + Math.random() * 0.6;
        const pattern = [];

        for (let day = 0; day < 7; day++) {
            const isWeekend = day === 5 || day === 6;
            for (let hour = 0; hour < 24; hour++) {
                let usage = baseline;
                for (const p of peaks) {
                    const dist = Math.min(Math.abs(hour - p.hour), 24 - Math.abs(hour - p.hour));
                    usage += Math.exp(-(dist * dist) / (2 * p.width * p.width)) * (0.4 + Math.random() * 0.1);
                }
                usage *= isWeekend ? weekendFactor : 1;
                usage += (Math.random() - 0.5) * 0.06;
                pattern.push(Math.min(1, Math.max(0, usage)));
            }
        }
        return pattern;
    }

    // Spiky: sharp narrow spikes at random intervals, very low baseline
    function randomSpiky() {
        const numSpikes = 2 + Math.floor(Math.random() * 4);
        const spikeHours = new Set();
        while (spikeHours.size < numSpikes) {
            spikeHours.add(Math.floor(Math.random() * 24));
        }
        const baseline = 0.03 + Math.random() * 0.08;
        const pattern = [];

        for (let day = 0; day < 7; day++) {
            const isWeekend = day === 5 || day === 6;
            const daySpikes = isWeekend ? Math.random() > 0.5 : true;
            for (let hour = 0; hour < 24; hour++) {
                let usage = baseline;
                if (daySpikes && spikeHours.has(hour)) {
                    usage = 0.7 + Math.random() * 0.3;
                } else if (daySpikes && spikeHours.has((hour + 1) % 24)) {
                    usage = 0.3 + Math.random() * 0.2;
                }
                usage += (Math.random() - 0.5) * 0.04;
                pattern.push(Math.min(1, Math.max(0, usage)));
            }
        }
        return pattern;
    }

    // Plateau: flat high period with sharp ramp up/down
    function randomPlateau() {
        const startHour = 4 + Math.floor(Math.random() * 8);
        const duration = 6 + Math.floor(Math.random() * 10);
        const endHour = (startHour + duration) % 24;
        const highLevel = 0.7 + Math.random() * 0.3;
        const lowLevel = 0.02 + Math.random() * 0.1;
        const weekendFactor = 0.2 + Math.random() * 0.6;
        const pattern = [];

        for (let day = 0; day < 7; day++) {
            const isWeekend = day === 5 || day === 6;
            for (let hour = 0; hour < 24; hour++) {
                const inPlateau = duration < 24
                    ? (startHour < endHour ? hour >= startHour && hour < endHour : hour >= startHour || hour < endHour)
                    : true;
                let usage = inPlateau ? highLevel : lowLevel;
                usage *= isWeekend ? weekendFactor : 1;
                usage += (Math.random() - 0.5) * 0.06;
                pattern.push(Math.min(1, Math.max(0, usage)));
            }
        }
        return pattern;
    }

    // Gradual: slow ramp up across the week, resets Monday
    function randomGradual() {
        const startLevel = 0.1 + Math.random() * 0.2;
        const endLevel = 0.7 + Math.random() * 0.3;
        const dailySwing = 0.1 + Math.random() * 0.2;
        const peakHour = 10 + Math.floor(Math.random() * 8);
        const pattern = [];

        for (let day = 0; day < 7; day++) {
            const dayProgress = day / 6;
            const dayBase = startLevel + (endLevel - startLevel) * dayProgress;
            for (let hour = 0; hour < 24; hour++) {
                const dist = Math.abs(hour - peakHour);
                const dailyCycle = Math.exp(-(dist * dist) / 20) * dailySwing;
                let usage = dayBase + dailyCycle;
                usage += (Math.random() - 0.5) * 0.05;
                pattern.push(Math.min(1, Math.max(0, usage)));
            }
        }
        return pattern;
    }

    // High base: consistently high with small dips (like 24/7 but noisier)
    function randomHighBase() {
        const base = 0.65 + Math.random() * 0.2;
        const dipDepth = 0.15 + Math.random() * 0.25;
        const dipHour = Math.floor(Math.random() * 24);
        const dipWidth = 2 + Math.random() * 4;
        const pattern = [];

        for (let day = 0; day < 7; day++) {
            const dayShift = (Math.random() - 0.5) * 0.1;
            for (let hour = 0; hour < 24; hour++) {
                const dist = Math.min(Math.abs(hour - dipHour), 24 - Math.abs(hour - dipHour));
                const dip = Math.exp(-(dist * dist) / (2 * dipWidth * dipWidth)) * dipDepth;
                let usage = base + dayShift - dip;
                usage += (Math.random() - 0.5) * 0.08;
                pattern.push(Math.min(1, Math.max(0, usage)));
            }
        }
        return pattern;
    }

    // Nocturnal: peak at night, low during day (opposite of business hours)
    function randomNocturnal() {
        const nightPeak = 0.8 + Math.random() * 0.2;
        const dayLow = 0.05 + Math.random() * 0.15;
        const peakHour = 1 + Math.floor(Math.random() * 4);
        const weekendBoost = Math.random() > 0.5 ? 0.15 : 0;
        const pattern = [];

        for (let day = 0; day < 7; day++) {
            const isWeekend = day === 5 || day === 6;
            for (let hour = 0; hour < 24; hour++) {
                const dist = Math.min(Math.abs(hour - peakHour), 24 - Math.abs(hour - peakHour));
                const nightCurve = Math.exp(-(dist * dist) / 30);
                let usage = dayLow + (nightPeak - dayLow) * nightCurve;
                if (isWeekend) usage += weekendBoost;
                usage += (Math.random() - 0.5) * 0.06;
                pattern.push(Math.min(1, Math.max(0, usage)));
            }
        }
        return pattern;
    }

    // Black Friday: normal week then massive spike on Friday, elevated Saturday
    function randomBlackFriday() {
        const normalBase = 0.2 + Math.random() * 0.15;
        const normalPeak = 0.4 + Math.random() * 0.15;
        const peakHour = 10 + Math.floor(Math.random() * 4);
        const pattern = [];

        for (let day = 0; day < 7; day++) {
            for (let hour = 0; hour < 24; hour++) {
                const dist = Math.abs(hour - peakHour);
                const dailyCurve = Math.exp(-(dist * dist) / 20);
                let usage;
                if (day === 4) { // Friday
                    usage = 0.4 + dailyCurve * 0.6;
                } else if (day === 5) { // Saturday
                    usage = 0.3 + dailyCurve * 0.4;
                } else {
                    usage = normalBase + dailyCurve * (normalPeak - normalBase);
                }
                usage += (Math.random() - 0.5) * 0.05;
                pattern.push(Math.min(1, Math.max(0, usage)));
            }
        }
        return pattern;
    }

    // Launch Day: huge spike on one random day, normal otherwise
    function randomLaunchDay() {
        const launchDay = 1 + Math.floor(Math.random() * 5); // Tue-Sat
        const normalBase = 0.15 + Math.random() * 0.15;
        const pattern = [];

        for (let day = 0; day < 7; day++) {
            for (let hour = 0; hour < 24; hour++) {
                let usage;
                if (day === launchDay) {
                    // Sharp ramp to peak at hour 10, sustained, slow decline
                    if (hour < 8) usage = normalBase + (hour / 8) * 0.3;
                    else if (hour < 14) usage = 0.85 + Math.random() * 0.15;
                    else usage = 0.9 - (hour - 14) * 0.06;
                } else if (day === launchDay + 1 || (launchDay === 6 && day === 0)) {
                    // Aftershock: elevated but declining
                    usage = 0.3 + Math.exp(-(hour * hour) / 80) * 0.3;
                } else {
                    usage = normalBase + (Math.random() - 0.5) * 0.08;
                }
                usage += (Math.random() - 0.5) * 0.04;
                pattern.push(Math.min(1, Math.max(0, usage)));
            }
        }
        return pattern;
    }

    // Double Shift: two distinct work periods per day (morning + evening)
    function randomDoubleShift() {
        const shift1Start = 6 + Math.floor(Math.random() * 2);
        const shift2Start = 16 + Math.floor(Math.random() * 3);
        const shiftDuration = 3 + Math.random() * 2;
        const peakLevel = 0.7 + Math.random() * 0.3;
        const baseline = 0.05 + Math.random() * 0.1;
        const weekendFactor = 0.2 + Math.random() * 0.4;
        const pattern = [];

        for (let day = 0; day < 7; day++) {
            const isWeekend = day === 5 || day === 6;
            for (let hour = 0; hour < 24; hour++) {
                const d1 = Math.abs(hour - shift1Start - shiftDuration / 2);
                const d2 = Math.abs(hour - shift2Start - shiftDuration / 2);
                const s1 = Math.exp(-(d1 * d1) / (2 * (shiftDuration / 2) * (shiftDuration / 2)));
                const s2 = Math.exp(-(d2 * d2) / (2 * (shiftDuration / 2) * (shiftDuration / 2)));
                let usage = baseline + Math.max(s1, s2) * (peakLevel - baseline);
                usage *= isWeekend ? weekendFactor : 1;
                usage += (Math.random() - 0.5) * 0.05;
                pattern.push(Math.min(1, Math.max(0, usage)));
            }
        }
        return pattern;
    }

    // Seasonal Decline: starts high Monday, steadily drops to low by Sunday
    function randomSeasonalDecline() {
        const startLevel = 0.8 + Math.random() * 0.2;
        const endLevel = 0.05 + Math.random() * 0.15;
        const dailySwing = 0.1 + Math.random() * 0.15;
        const peakHour = 11 + Math.floor(Math.random() * 4);
        const pattern = [];

        for (let day = 0; day < 7; day++) {
            const dayProgress = day / 6;
            const dayBase = startLevel - (startLevel - endLevel) * dayProgress;
            for (let hour = 0; hour < 24; hour++) {
                const dist = Math.abs(hour - peakHour);
                const dailyCycle = Math.exp(-(dist * dist) / 20) * dailySwing;
                let usage = dayBase + dailyCycle;
                usage += (Math.random() - 0.5) * 0.05;
                pattern.push(Math.min(1, Math.max(0, usage)));
            }
        }
        return pattern;
    }

    function randomHighWeekend() {
        const weekdayBase = 0.15 + Math.random() * 0.15;
        const weekendBase = 0.7 + Math.random() * 0.2;
        const peakHour = 12 + Math.floor(Math.random() * 4);
        const weekdaySwing = 0.1 + Math.random() * 0.1;
        const weekendSwing = 0.15 + Math.random() * 0.1;
        const pattern = [];

        for (let day = 0; day < 7; day++) {
            const isWeekend = day >= 5;
            const base = isWeekend ? weekendBase : weekdayBase;
            const swing = isWeekend ? weekendSwing : weekdaySwing;
            for (let hour = 0; hour < 24; hour++) {
                const dist = Math.abs(hour - peakHour);
                const dailyCycle = Math.exp(-(dist * dist) / 25) * swing;
                let usage = base + dailyCycle;
                usage += (Math.random() - 0.5) * 0.05;
                pattern.push(Math.min(1, Math.max(0, usage)));
            }
        }
        return pattern;
    }

    /**
     * Generate load pattern by type
     * @param {string} type - Pattern type name
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
            case 'business-hours':
                return generateBusinessHoursPattern();
            case 'random':
                return generateRandomPattern();
            case 'custom':
            case 'custom-paste':
            case 'custom-url':
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
        getLastRandomName,
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

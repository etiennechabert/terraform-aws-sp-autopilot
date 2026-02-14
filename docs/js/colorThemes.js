/**
 * Color Themes for Accessibility
 * Provides color palettes for different types of color vision deficiency
 */

const ColorThemes = (function() {
    'use strict';

    function buildTheme(name, colors) {
        return {
            name,
            covered:    { border: colors.covered[0],    background: colors.covered[1] },
            spillover:  { border: colors.spillover[0],   background: colors.spillover[1] },
            baseline:   { border: colors.baseline[0],    background: colors.baseline[1] },
            commitment: { border: colors.commitment[0],  background: colors.commitment[1] },
            loadPattern:{ border: colors.loadPattern[0], background: colors.loadPattern[1] },
            savingsCurve: {
                building:    { border: colors.building[0],    background: colors.building[1] },
                gaining:     { border: colors.gaining[0],     background: colors.gaining[1] },
                wasting:     { border: colors.wasting[0],     background: colors.wasting[1] },
                veryBad:     { border: colors.veryBad[0],     background: colors.veryBad[1] },
                losingMoney: { border: colors.losingMoney[0], background: colors.losingMoney[1] }
            }
        };
    }

    const themes = {
        default: buildTheme('Default', {
            covered:     ['#00ff88', 'rgba(0, 255, 136, 0.3)'],
            spillover:   ['#ffaa00', 'rgba(255, 170, 0, 0.5)'],
            baseline:    ['#8b95a8', 'transparent'],
            commitment:  ['#00ff88', 'transparent'],
            loadPattern: ['#00d4ff', 'rgba(0, 212, 255, 0.2)'],
            building:    ['rgba(77, 159, 255, 1)',  'rgba(77, 159, 255, 0.4)'],
            gaining:     ['rgba(0, 255, 136, 1)',   'rgba(0, 255, 136, 0.4)'],
            wasting:     ['rgba(255, 170, 0, 1)',   'rgba(255, 170, 0, 0.4)'],
            veryBad:     ['rgba(138, 43, 226, 1)',  'rgba(138, 43, 226, 0.4)'],
            losingMoney: ['rgba(255, 68, 68, 1)',   'rgba(255, 68, 68, 0.4)']
        }),
        protanopia: buildTheme('Protanopia (Red-blind)', {
            covered:     ['#0099ff', 'rgba(0, 153, 255, 0.3)'],
            spillover:   ['#ffcc00', 'rgba(255, 204, 0, 0.5)'],
            baseline:    ['#8b95a8', 'transparent'],
            commitment:  ['#0099ff', 'transparent'],
            loadPattern: ['#0099ff', 'rgba(0, 153, 255, 0.2)'],
            building:    ['rgba(153, 204, 255, 1)', 'rgba(153, 204, 255, 0.4)'],
            gaining:     ['rgba(0, 102, 204, 1)',   'rgba(0, 102, 204, 0.4)'],
            wasting:     ['rgba(255, 204, 0, 1)',   'rgba(255, 204, 0, 0.4)'],
            veryBad:     ['rgba(255, 153, 51, 1)',  'rgba(255, 153, 51, 0.4)'],
            losingMoney: ['rgba(204, 102, 0, 1)',   'rgba(204, 102, 0, 0.4)']
        }),
        tritanopia: buildTheme('Tritanopia (Blue-blind)', {
            covered:     ['#00ff66', 'rgba(0, 255, 102, 0.3)'],
            spillover:   ['#ff0066', 'rgba(255, 0, 102, 0.5)'],
            baseline:    ['#999999', 'transparent'],
            commitment:  ['#00ff66', 'transparent'],
            loadPattern: ['#ff0066', 'rgba(255, 0, 102, 0.2)'],
            building:    ['rgba(204, 255, 102, 1)', 'rgba(204, 255, 102, 0.4)'],
            gaining:     ['rgba(0, 204, 68, 1)',    'rgba(0, 204, 68, 0.4)'],
            wasting:     ['rgba(255, 204, 0, 1)',   'rgba(255, 204, 0, 0.4)'],
            veryBad:     ['rgba(255, 128, 0, 1)',   'rgba(255, 128, 0, 0.4)'],
            losingMoney: ['rgba(204, 0, 68, 1)',    'rgba(204, 0, 68, 0.4)']
        }),
        'high-contrast': buildTheme('High Contrast', {
            covered:     ['#00ff00', 'rgba(0, 255, 0, 0.4)'],
            spillover:   ['#ffff00', 'rgba(255, 255, 0, 0.6)'],
            baseline:    ['#ffffff', 'transparent'],
            commitment:  ['#00ff00', 'transparent'],
            loadPattern: ['#00ffff', 'rgba(0, 255, 255, 0.3)'],
            building:    ['rgba(0, 255, 255, 1)',   'rgba(0, 255, 255, 0.5)'],
            gaining:     ['rgba(0, 255, 0, 1)',     'rgba(0, 255, 0, 0.5)'],
            wasting:     ['rgba(255, 255, 0, 1)',   'rgba(255, 255, 0, 0.5)'],
            veryBad:     ['rgba(255, 128, 0, 1)',   'rgba(255, 128, 0, 0.5)'],
            losingMoney: ['rgba(255, 0, 0, 1)',     'rgba(255, 0, 0, 0.5)']
        })
    };

    let currentTheme = 'default';

    /**
     * Get the current theme
     * @returns {string} Theme name
     */
    function getCurrentTheme() {
        return currentTheme;
    }

    /**
     * Set the current theme
     * @param {string} themeName - Theme to activate
     */
    function setTheme(themeName) {
        if (themes[themeName]) {
            currentTheme = themeName;
        }
    }

    /**
     * Get colors for a specific theme
     * @param {string} themeName - Theme name (defaults to current)
     * @returns {Object} Theme colors
     */
    function getThemeColors(themeName = null) {
        const theme = themeName || currentTheme;
        return themes[theme] || themes.default;
    }

    /**
     * Get all available themes
     * @returns {Object} All theme definitions
     */
    function getAllThemes() {
        return themes;
    }

    // Public API
    return {
        getCurrentTheme,
        setTheme,
        getThemeColors,
        getAllThemes
    };
})();

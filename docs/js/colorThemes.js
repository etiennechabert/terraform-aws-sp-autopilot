/**
 * Color Themes for Accessibility
 *
 * Two palettes matching the report's Wong-palette approach:
 *   Palette 1 (default): Blue & Orange — safe for Protanopia/Deuteranopia (~8% of males)
 *   Palette 2 (alt):     Pink & Teal  — safe for Tritanopia
 *
 * Together they cover the vast majority of color vision deficiencies.
 */

const ColorThemes = (function() {
    'use strict';

    function buildTheme(name, colors) {
        return {
            name,
            covered:      { border: colors.covered[0],      background: colors.covered[1] },
            nextPurchase: { border: colors.nextPurchase[0],  background: colors.nextPurchase[1] },
            spillover:    { border: colors.spillover[0],     background: colors.spillover[1] },
            baseline:     { border: colors.baseline[0],      background: colors.baseline[1] },
            commitment:   { border: colors.commitment[0],    background: colors.commitment[1] },
            loadPattern:  { border: colors.loadPattern[0],   background: colors.loadPattern[1] },
            savingsCurve: {
                building:    { border: colors.building[0],    background: colors.building[1] },
                gaining:     { border: colors.gaining[0],     background: colors.gaining[1] },
                wasting:     { border: colors.wasting[0],     background: colors.wasting[1] },
                veryBad:     { border: colors.veryBad[0],     background: colors.veryBad[1] },
                losingMoney: { border: colors.losingMoney[0], background: colors.losingMoney[1] }
            }
        };
    }

    // Palette 1: Blue & Orange (safe for red-green color blindness)
    // Matching report palette1: covered=#0072B2, ondemand=#E69F00, target=#009E73
    const themes = {
        default: buildTheme('Blue / Orange', {
            covered:     ['rgb(0, 114, 178)',   'rgba(0, 114, 178, 0.35)'],
            nextPurchase:['rgb(0, 158, 115)',   'rgba(0, 158, 115, 0.5)'],
            spillover:   ['rgb(230, 159, 0)',   'rgba(230, 159, 0, 0.5)'],
            baseline:    ['#8b95a8',            'transparent'],
            commitment:  ['rgb(0, 158, 115)',   'transparent'],
            loadPattern: ['rgb(0, 114, 178)',   'rgba(0, 114, 178, 0.2)'],
            building:    ['rgba(0, 114, 178, 1)',   'rgba(0, 114, 178, 0.4)'],
            gaining:     ['rgba(0, 158, 115, 1)',   'rgba(0, 158, 115, 0.4)'],
            wasting:     ['rgba(230, 159, 0, 1)',   'rgba(230, 159, 0, 0.4)'],
            veryBad:     ['rgba(204, 121, 167, 1)', 'rgba(204, 121, 167, 0.4)'],
            losingMoney: ['rgba(213, 94, 0, 1)',    'rgba(213, 94, 0, 0.4)']
        }),

        // Palette 2: Pink & Teal (safe for blue-yellow color blindness)
        // Matching report palette2: covered=#CC79A7, ondemand=#56B4E9, target=#D55E00
        alt: buildTheme('Pink / Teal', {
            covered:     ['rgb(204, 121, 167)', 'rgba(204, 121, 167, 0.35)'],
            nextPurchase:['rgb(213, 94, 0)',    'rgba(213, 94, 0, 0.3)'],
            spillover:   ['rgb(86, 180, 233)',  'rgba(86, 180, 233, 0.5)'],
            baseline:    ['#999999',            'transparent'],
            commitment:  ['rgb(213, 94, 0)',    'transparent'],
            loadPattern: ['rgb(204, 121, 167)', 'rgba(204, 121, 167, 0.2)'],
            building:    ['rgba(86, 180, 233, 1)',  'rgba(86, 180, 233, 0.4)'],
            gaining:     ['rgba(204, 121, 167, 1)', 'rgba(204, 121, 167, 0.4)'],
            wasting:     ['rgba(230, 159, 0, 1)',   'rgba(230, 159, 0, 0.4)'],
            veryBad:     ['rgba(213, 94, 0, 1)',     'rgba(213, 94, 0, 0.4)'],
            losingMoney: ['rgba(180, 0, 0, 1)',      'rgba(180, 0, 0, 0.4)']
        })
    };

    let currentTheme = 'default';

    function getCurrentTheme() {
        return currentTheme;
    }

    function setTheme(themeName) {
        if (themes[themeName]) {
            currentTheme = themeName;
        }
    }

    function getThemeColors(themeName = null) {
        const theme = themeName || currentTheme;
        return themes[theme] || themes.default;
    }

    function getAllThemes() {
        return themes;
    }

    return {
        getCurrentTheme,
        setTheme,
        getThemeColors,
        getAllThemes
    };
})();

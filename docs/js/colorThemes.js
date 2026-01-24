/**
 * Color Themes for Accessibility
 * Provides color palettes for different types of color vision deficiency
 */

const ColorThemes = (function() {
    'use strict';

    const themes = {
        default: {
            name: 'Default',
            covered: {
                border: '#00ff88',
                background: 'rgba(0, 255, 136, 0.3)'
            },
            spillover: {
                border: '#ffaa00',
                background: 'rgba(255, 170, 0, 0.5)'
            },
            baseline: {
                border: '#8b95a8',
                background: 'transparent'
            },
            commitment: {
                border: '#00ff88',
                background: 'transparent'
            },
            loadPattern: {
                border: '#00d4ff',
                background: 'rgba(0, 212, 255, 0.2)'
            }
        },
        protanopia: {
            name: 'Protanopia (Red-blind)',
            // Use blue and yellow instead of red and green
            covered: {
                border: '#0099ff',  // Blue
                background: 'rgba(0, 153, 255, 0.3)'
            },
            spillover: {
                border: '#ffcc00',  // Yellow
                background: 'rgba(255, 204, 0, 0.5)'
            },
            baseline: {
                border: '#8b95a8',
                background: 'transparent'
            },
            commitment: {
                border: '#0099ff',
                background: 'transparent'
            },
            loadPattern: {
                border: '#0099ff',
                background: 'rgba(0, 153, 255, 0.2)'
            }
        },
        deuteranopia: {
            name: 'Deuteranopia (Green-blind)',
            // Use blue and orange/yellow
            covered: {
                border: '#0088ff',  // Deep blue
                background: 'rgba(0, 136, 255, 0.3)'
            },
            spillover: {
                border: '#ff9900',  // Orange
                background: 'rgba(255, 153, 0, 0.5)'
            },
            baseline: {
                border: '#8b95a8',
                background: 'transparent'
            },
            commitment: {
                border: '#0088ff',
                background: 'transparent'
            },
            loadPattern: {
                border: '#0088ff',
                background: 'rgba(0, 136, 255, 0.2)'
            }
        },
        tritanopia: {
            name: 'Tritanopia (Blue-blind)',
            // Use red and green (avoid blue)
            covered: {
                border: '#00ff66',  // Bright green
                background: 'rgba(0, 255, 102, 0.3)'
            },
            spillover: {
                border: '#ff0066',  // Pink/red
                background: 'rgba(255, 0, 102, 0.5)'
            },
            baseline: {
                border: '#999999',
                background: 'transparent'
            },
            commitment: {
                border: '#00ff66',
                background: 'transparent'
            },
            loadPattern: {
                border: '#ff0066',
                background: 'rgba(255, 0, 102, 0.2)'
            }
        },
        'high-contrast': {
            name: 'High Contrast',
            // Maximum contrast for low vision
            covered: {
                border: '#00ff00',  // Pure green
                background: 'rgba(0, 255, 0, 0.4)'
            },
            spillover: {
                border: '#ffff00',  // Pure yellow
                background: 'rgba(255, 255, 0, 0.6)'
            },
            baseline: {
                border: '#ffffff',  // White
                background: 'transparent'
            },
            commitment: {
                border: '#00ff00',
                background: 'transparent'
            },
            loadPattern: {
                border: '#00ffff',  // Cyan
                background: 'rgba(0, 255, 255, 0.3)'
            }
        }
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

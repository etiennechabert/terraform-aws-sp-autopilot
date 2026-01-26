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
            },
            savingsCurve: {
                building: {
                    border: 'rgba(77, 159, 255, 1)',
                    background: 'rgba(77, 159, 255, 0.4)'
                },
                gaining: {
                    border: 'rgba(0, 255, 136, 1)',
                    background: 'rgba(0, 255, 136, 0.4)'
                },
                wasting: {
                    border: 'rgba(255, 170, 0, 1)',
                    background: 'rgba(255, 170, 0, 0.4)'
                },
                veryBad: {
                    border: 'rgba(138, 43, 226, 1)',
                    background: 'rgba(138, 43, 226, 0.4)'
                },
                losingMoney: {
                    border: 'rgba(255, 68, 68, 1)',
                    background: 'rgba(255, 68, 68, 0.4)'
                }
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
            },
            savingsCurve: {
                building: {
                    border: 'rgba(51, 153, 255, 1)',  // Light blue
                    background: 'rgba(51, 153, 255, 0.4)'
                },
                gaining: {
                    border: 'rgba(0, 153, 255, 1)',  // Deep blue
                    background: 'rgba(0, 153, 255, 0.4)'
                },
                wasting: {
                    border: 'rgba(255, 204, 0, 1)',  // Yellow
                    background: 'rgba(255, 204, 0, 0.4)'
                },
                veryBad: {
                    border: 'rgba(255, 153, 51, 1)',  // Orange
                    background: 'rgba(255, 153, 51, 0.4)'
                },
                losingMoney: {
                    border: 'rgba(204, 102, 0, 1)',  // Dark orange
                    background: 'rgba(204, 102, 0, 0.4)'
                }
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
            },
            savingsCurve: {
                building: {
                    border: 'rgba(102, 255, 153, 1)',  // Light green
                    background: 'rgba(102, 255, 153, 0.4)'
                },
                gaining: {
                    border: 'rgba(0, 255, 102, 1)',  // Bright green
                    background: 'rgba(0, 255, 102, 0.4)'
                },
                wasting: {
                    border: 'rgba(255, 204, 51, 1)',  // Yellow
                    background: 'rgba(255, 204, 51, 0.4)'
                },
                veryBad: {
                    border: 'rgba(255, 102, 51, 1)',  // Orange
                    background: 'rgba(255, 102, 51, 0.4)'
                },
                losingMoney: {
                    border: 'rgba(255, 0, 102, 1)',  // Pink/red
                    background: 'rgba(255, 0, 102, 0.4)'
                }
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
            },
            savingsCurve: {
                building: {
                    border: 'rgba(0, 255, 255, 1)',  // Cyan
                    background: 'rgba(0, 255, 255, 0.5)'
                },
                gaining: {
                    border: 'rgba(0, 255, 0, 1)',  // Pure green
                    background: 'rgba(0, 255, 0, 0.5)'
                },
                wasting: {
                    border: 'rgba(255, 255, 0, 1)',  // Pure yellow
                    background: 'rgba(255, 255, 0, 0.5)'
                },
                veryBad: {
                    border: 'rgba(255, 128, 0, 1)',  // Orange
                    background: 'rgba(255, 128, 0, 0.5)'
                },
                losingMoney: {
                    border: 'rgba(255, 0, 0, 1)',  // Pure red
                    background: 'rgba(255, 0, 0, 0.5)'
                }
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

/**
 * Test data constants for Playwright tests
 */

/**
 * Real reporter output data (URL-encoded compressed JSON)
 * This is actual data from the AWS Savings Plan reporter tool
 */
export const REPORTER_URL_DATA = 'eJxtVstuIzkM%2FJc%2BNwSRIikp5%2F2LwcLwBt6ZAIlj2J7BBIP8%2B5Il9%2FrR8YFoqyWyWCxS%2FWf68f7z%2BPqxeX4%2FnU%2FT0zfpSXgukirNbEloLpxMwrLNJSeuM9fY42%2Btha02s8Qe1mQ9LJWwXfC2h2Xs1Hmczjjt%2FphS8V0ZPvxZ45ncclKeA4sEFqs47c8ELJSa7%2B8pt%2FAWpyw1%2BPRgJTVF%2BBpWb8IHoJqUYl00dpZheyRQS0BobQHlzxRwGnwSAnI4YFjPMdBUMBPvui2pjaiOoMXJDniEqK0vz5IyRZoBm1NFxrCF45ABhrMvOXUH1mA5EcCwzJqTeGwPwvHWnTkaD%2Bs20ukArGBuVEJTbeEBy%2FgvgOSs%2Bqog4ciMEiE2K%2ByVjdxhAaOiaAbybFbnIaAEd4MP6KVT6KUBPQlQwiotejGoyS6aGuQGWxGiozS5hhWcUL4WKE4QyB7aKVEPKZfctUAXwBIK8rccWMZ6RaEI2gl%2B5IKCIBIq%2BeZXsGQBuw6nPaynFi7wHI3iUpTVsYtX6JJQzn67x9dlljqoKy2wBkoOsQZuCK7XhyMt0ZKDM6lXUfV2YwkbAc94sTjqsAgCg%2B7uAGUsZdS9oR8VWmzw4OoRnwft9oBTa1EiIW88ZzmQl4RQbYgQncEg%2FC6TDFVkXhqyrgmsl34djKNata9c8KPXsuaMQctoHkIjuWDBgqcpPfh%2FzCuCQT4%2BA2IYjgGIhRYp%2BUu3hsQM%2BPtjcYfogdy%2BKD1GqEBbApnLV7msSGNIlnGC1kExA4IDl1aL8RZteedjNGKBxDjKJRjrpCv4l0mP7CDoVq82GFVkWEBDwfhyb3d%2BkIMscyK69DEMo75LVdDbag97YoY%2BeHVcpd%2F8xkXQ0BQYiwTLHW0laCUUTkYmo3AYNAZWi49arwOaTnAfMK6hVRjGOOQ0xrEttXDLDzspVV0t6eMuibmjBSURXF01msnS6C6%2FxXxZY647RV4oQ48VlLEv%2FaxA6zrl5dltXUUyiE3zw4sv9pbL%2FI3iMC4swiSPO2m19TFNGbPXbyiUxVeihex2k2GpLZcFrdnrCRotGGV1jO8GpUrYuxzGfrpDBgA6bmYIuYECRVoN1et1qeGSXLno%2Be95Op238UH0Z3p72U9P47Nketv%2Bnp5GsaaDZl%2B3KNl0qOrP%2BHSaDt3XR1%2F5s69jRn7O0%2FPP43G3P%2Fun1q%2Fdcft9Nz25HIplZiHutav6VJneD%2BeXt%2B3r5t%2Fj%2B9vm8HH%2B8b4PFMuhzfhe82jOn5bryHBarpsOu%2BOzh0IQn9pWa%2BWurWY2LiOPzX533py2v17230%2FhzQIlN7LCDmmOtC%2BxbnZRd%2B567r5R2JU47X6fj9ubDdX5bNSkSCvFW2f4iY%2FL%2Fzm8YHt53YFe0OhfM6ZZq5IYSTEfX4NT9dHcrbWmzpQ0nz2DX%2FMadHPyVLMVqqSfzvDpsDl%2FHDzn6a%2FtefvP9rSbfHGAu%2BMkOq1bdYxZS8uNPv8Dgf1V3w%3D%3D';

/**
 * Default cost range values for testing
 */
export const DEFAULT_COST_RANGE = {
  minCost: 15,
  maxCost: 100,
};

/**
 * Default slider values
 */
export const DEFAULT_SLIDER_VALUES = {
  commitment: 50,          // $/h
  savingsPercentage: 30,   // %
  loadFactor: 100,         // %
};

/**
 * Expected baseline costs for different patterns (approximate)
 * These are rough estimates based on default min/max costs
 */
export const EXPECTED_PATTERN_BASELINES = {
  ecommerce: {
    minCost: 15,
    maxCost: 100,
    description: 'Weekday peaks',
  },
  global247: {
    minCost: 15,
    maxCost: 100,
    description: 'Consistent load',
  },
  batch: {
    minCost: 15,
    maxCost: 100,
    description: 'Scheduled spikes',
  },
};

/**
 * Strategy IDs and their display names
 */
export const STRATEGIES = {
  tooPrudent: {
    id: 'too-prudent',
    name: 'Prudent',
    description: 'Under-committed',
    icon: '🐔',
  },
  min: {
    id: 'min',
    name: 'Min-Hourly',
    description: 'Baseline only',
    icon: '🛡️',
  },
  balanced: {
    id: 'balanced',
    name: 'Balanced',
    description: 'Knee point',
    icon: '⚖️',
    recommended: true,
  },
  aggressive: {
    id: 'aggressive',
    name: 'Risky',
    description: 'Max savings',
    icon: '⚠️',
  },
  aws: {
    id: 'aws',
    name: 'Recommendation',
    description: 'CE Recommendation',
    icon: '🏢',
  },
};

/**
 * CSS selectors for common elements
 */
export const SELECTORS = {
  // Sliders
  commitmentSlider: '#coverage-slider',
  savingsSlider: '#savings-percentage',
  loadFactorSlider: '#load-factor',

  // Displays
  commitmentDisplay: '#coverage-display',
  savingsDisplay: '#savings-display',
  loadFactorDisplay: '#load-factor-display',

  // Metrics
  metricOnDemand: '#metric-ondemand',
  metricSavingsPlan: '#metric-savingsplan',
  metricCommitment: '#metric-commitment',
  metricCommitmentPct: '#metric-commitment-pct',
  metricWaste: '#metric-waste',
  metricWastePct: '#metric-waste-pct',
  metricSpillover: '#metric-spillover',
  metricSpilloverPct: '#metric-spillover-pct',
  metricSavings: '#metric-savings',
  metricSavingsPct: '#metric-savings-pct',

  // Controls
  patternSelect: '#pattern-select',
  minCostInput: '#min-cost',
  maxCostInput: '#max-cost',
  resetLoadFactorButton: '#reset-load-factor',

  // Charts
  loadChart: '#load-chart',
  costChart: '#cost-chart',
  savingsCurveChart: '#savings-curve-chart',
};

/**
 * Test timeouts (in milliseconds)
 */
export const TIMEOUTS = {
  pageLoad: 1000,
  calculation: 500,
  interaction: 300,
  animation: 200,
};

/**
 * Color thresholds for percentage displays
 * Based on the application's color-coding logic
 */
export const COLOR_THRESHOLDS = {
  commitment: {
    green: 60,    // >= 60% is green (good commitment level)
    orange: 40,   // >= 40% is orange (moderate)
    // < 40% is red (low commitment)
  },
  waste: {
    green: 5,     // <= 5% is green (minimal waste)
    orange: 15,   // <= 15% is orange (moderate waste)
    // > 15% is red (high waste)
  },
  spillover: {
    green: 20,    // <= 20% is green (minimal spillover)
    orange: 40,   // <= 40% is orange (moderate)
    // > 40% is red (high spillover)
  },
};

/**
 * Test patterns for pattern selection tests
 */
export const TEST_PATTERNS = ['ecommerce', 'global247', 'batch'];

/**
 * Edge case test values
 */
export const EDGE_CASES = {
  zeroCommitment: 0,
  maxCommitment: 100,
  zeroSavings: 0,
  maxSavings: 99,
  minLoadFactor: 1,
  maxLoadFactor: 150,
  zeroCost: 0,
  largeCost: 5000,
};

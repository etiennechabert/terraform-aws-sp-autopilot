import { expect } from '@playwright/test';

/**
 * Assert that strategy card metrics match the top-level metrics
 * @param {Page} page - Playwright page object
 * @param {string} strategyId - Strategy ID (e.g., 'balanced', 'aggressive')
 */
export async function assertMetricsMatch(page, strategyId) {
  // Get values from strategy card
  const cardSavings = await page.locator(`#strategy-${strategyId}-savings`).textContent();
  const cardSavingsPct = await page.locator(`#strategy-${strategyId}-savings-pct`).textContent();

  // Get values from top metrics
  const topSavings = await page.locator('#metric-savings').textContent();
  const topSavingsPct = await page.locator('#metric-savings-pct').textContent();

  // Assert exact match
  expect(cardSavings.trim()).toBe(topSavings.trim());
  expect(cardSavingsPct.trim()).toBe(topSavingsPct.trim());
}

/**
 * Assert that a percentage display has the correct color based on thresholds
 * @param {Page} page - Playwright page object
 * @param {string} selector - CSS selector for the element
 * @param {string} expectedColorCategory - Expected color category ('green', 'orange', 'red')
 */
export async function assertColorThreshold(page, selector, expectedColorCategory) {
  const element = page.locator(selector);
  const color = await element.evaluate(el => getComputedStyle(el).color);

  // Color mapping based on the application's color theme
  const colorMap = {
    'green': /rgb\(0,\s*255,\s*136\)/,      // #00ff88
    'orange': /rgb\(255,\s*165,\s*0\)/,     // #ffa500
    'red': /rgb\(255,\s*68,\s*68\)/,        // #ff4444
  };

  expect(color).toMatch(colorMap[expectedColorCategory]);
}

/**
 * Assert that all metrics have valid dollar format
 * @param {Page} page - Playwright page object
 */
export async function assertAllMetricsValid(page) {
  const metricIds = [
    '#metric-ondemand',
    '#metric-savingsplan',
    '#metric-commitment',
    '#metric-waste',
    '#metric-spillover',
    '#metric-savings',
  ];

  for (const metricId of metricIds) {
    const value = await page.locator(metricId).textContent();
    expect(value).toMatch(/-?\$\d+\.\d{2}\/h/);
  }
}

/**
 * Assert that all strategy cards have valid values
 * @param {Page} page - Playwright page object
 */
export async function assertAllStrategyCardsValid(page) {
  const strategies = ['too-prudent', 'min', 'balanced', 'aggressive', 'too-aggressive'];

  for (const strategy of strategies) {
    const cost = await page.locator(`#strategy-${strategy}-value`).textContent();
    const savings = await page.locator(`#strategy-${strategy}-savings`).textContent();
    const savingsPct = await page.locator(`#strategy-${strategy}-savings-pct`).textContent();

    expect(cost).toMatch(/\$\d+\.\d{2}\/h/);
    expect(savings).toMatch(/-?\$\d+\.\d{2}\/h/);
    expect(savingsPct).toMatch(/-?\d+\.\d%/);
  }
}

/**
 * Parse dollar amount from formatted string
 * @param {string} formattedValue - String like "$35.00/h" or "-$10.50/h"
 * @returns {number} Numeric value
 */
export function parseDollarAmount(formattedValue) {
  return Number.parseFloat(formattedValue.replaceAll(/[$/h]/g, ''));
}

/**
 * Parse percentage from formatted string
 * @param {string} formattedValue - String like "42.5%" or "-5.0%"
 * @returns {number} Numeric value
 */
export function parsePercentage(formattedValue) {
  return Number.parseFloat(formattedValue.replaceAll(/%/g, ''));
}

/**
 * Wait for page calculations to complete
 * @param {Page} page - Playwright page object
 * @param {number} timeout - Wait time in milliseconds (default: 500ms)
 */
export async function waitForCalculations(page, timeout = 500) {
  await page.waitForTimeout(timeout);
}

/**
 * Assert that a value increased after an action
 * @param {string} beforeValue - Value before action (formatted string)
 * @param {string} afterValue - Value after action (formatted string)
 */
export function assertValueIncreased(beforeValue, afterValue) {
  const before = parseDollarAmount(beforeValue);
  const after = parseDollarAmount(afterValue);
  expect(after).toBeGreaterThan(before);
}

/**
 * Assert that a value decreased after an action
 * @param {string} beforeValue - Value before action (formatted string)
 * @param {string} afterValue - Value after action (formatted string)
 */
export function assertValueDecreased(beforeValue, afterValue) {
  const before = parseDollarAmount(beforeValue);
  const after = parseDollarAmount(afterValue);
  expect(after).toBeLessThan(before);
}

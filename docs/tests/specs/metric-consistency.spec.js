import { test, expect } from '@playwright/test';

test.describe('Metric Consistency Tests', () => {
  test('strategy card savings match top metrics when clicking Balanced', async ({ page }) => {
    await page.goto('index.html');

    // Wait for page to load and calculate
    await page.waitForSelector('#strategy-balanced');

    // Click Balanced strategy
    await page.click('#strategy-balanced');

    // Wait for metrics to update
    await page.waitForTimeout(500);

    // Get values from Balanced strategy card
    const cardSavings = await page.locator('#strategy-balanced-savings').textContent();
    const cardSavingsPct = await page.locator('#strategy-balanced-savings-pct').textContent();

    // Get values from top metrics
    const topSavings = await page.locator('#metric-savings').textContent();
    const topSavingsPct = await page.locator('#metric-savings-pct').textContent();

    // They must match exactly
    expect(cardSavings.trim()).toBe(topSavings.trim());
    expect(cardSavingsPct.trim()).toBe(topSavingsPct.trim());
  });

  test('strategy card savings match top metrics when clicking Aggressive', async ({ page }) => {
    await page.goto('index.html');

    // Wait for page to load
    await page.waitForSelector('#strategy-too-aggressive');

    // Click Aggressive strategy
    await page.click('#strategy-too-aggressive');

    // Wait for metrics to update
    await page.waitForTimeout(500);

    // Get values from strategy card
    const cardSavings = await page.locator('#strategy-too-aggressive-savings').textContent();
    const cardSavingsPct = await page.locator('#strategy-too-aggressive-savings-pct').textContent();

    // Get values from top metrics
    const topSavings = await page.locator('#metric-savings').textContent();
    const topSavingsPct = await page.locator('#metric-savings-pct').textContent();

    // They must match exactly
    expect(cardSavings.trim()).toBe(topSavings.trim());
    expect(cardSavingsPct.trim()).toBe(topSavingsPct.trim());
  });

  test('strategy card savings match top metrics when clicking Min-Hourly', async ({ page }) => {
    await page.goto('index.html');

    // Wait for page to load
    await page.waitForSelector('#strategy-min');

    // Click Min-Hourly strategy
    await page.click('#strategy-min');

    // Wait for metrics to update
    await page.waitForTimeout(500);

    // Get values from strategy card
    const cardSavings = await page.locator('#strategy-min-savings').textContent();
    const cardSavingsPct = await page.locator('#strategy-min-savings-pct').textContent();

    // Get values from top metrics
    const topSavings = await page.locator('#metric-savings').textContent();
    const topSavingsPct = await page.locator('#metric-savings-pct').textContent();

    // They must match exactly
    expect(cardSavings.trim()).toBe(topSavings.trim());
    expect(cardSavingsPct.trim()).toBe(topSavingsPct.trim());
  });

  // REMOVED: strategy card cost matching top commitment test
  // Top metric now shows coverage (on-demand equivalent) while strategy cards
  // show commitment cost (discounted). These intentionally differ.

});

// REMOVED: Strategy card savings matching top metrics tests
// These tests conflicted with the requirement that strategy cards show
// IDENTICAL values whether selected or not. Strategy cards now always show
// their own calculated values, they never update to match currentCostResults.
// The strategy-stability.spec.js tests now enforce this correct behavior.

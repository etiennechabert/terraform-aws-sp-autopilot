import { test, expect } from '@playwright/test';

test.describe('Metric Consistency Tests', () => {
  test('strategy card savings match top metrics when selected', async ({ page }) => {
    await page.goto('index.html');
    await page.waitForSelector('#strategy-balanced');

    await page.click('#strategy-balanced');
    await page.waitForTimeout(500);

    const cardSavings = await page.locator('#strategy-balanced-savings').textContent();
    const topSavings = await page.locator('#metric-savings').textContent();

    expect(cardSavings.trim()).toBe(topSavings.trim());
  });
});

import { test, expect } from '@playwright/test';

test.describe('Page Load Tests', () => {
  test('page loads without JavaScript errors', async ({ page }) => {
    const errors = [];

    page.on('pageerror', error => {
      errors.push(error.message);
    });

    await page.goto('index.html');
    await page.waitForSelector('#strategy-balanced');
    await page.waitForTimeout(500);

    expect(errors).toHaveLength(0);
  });
});

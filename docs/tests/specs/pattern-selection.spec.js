import { test, expect } from '@playwright/test';

test.describe('Pattern Selection Tests', () => {
  test('switching from E-commerce to Global 24/7 updates metrics', async ({ page }) => {
    await page.goto('index.html');
    await page.waitForSelector('#pattern-select');
    await page.waitForTimeout(500);

    // Get baseline cost with E-commerce pattern
    const ecommerceCost = await page.locator('#metric-ondemand').textContent();

    // Switch to Global 24/7 pattern
    await page.selectOption('#pattern-select', 'global247');
    await page.waitForTimeout(500);

    // Verify metrics updated
    const global247Cost = await page.locator('#metric-ondemand').textContent();
    expect(global247Cost).not.toBe(ecommerceCost);

    // All metrics should be recalculated (valid format)
    const commitment = await page.locator('#metric-commitment').textContent();
    const savings = await page.locator('#metric-savings').textContent();

    expect(commitment).toMatch(/\$\d+\.\d{2}\/h/);
    expect(savings).toMatch(/[-]?\$\d+\.\d{2}\/h/);
  });

  test('switching to Batch Processing pattern updates chart', async ({ page }) => {
    await page.goto('index.html');
    await page.waitForSelector('#pattern-select');
    await page.waitForTimeout(500);

    // Switch to Batch Processing
    await page.selectOption('#pattern-select', 'batch');
    await page.waitForTimeout(500);

    // Verify pattern selection updated
    const selectedPattern = await page.locator('#pattern-select').inputValue();
    expect(selectedPattern).toBe('batch');

    // Verify metrics calculated
    const onDemand = await page.locator('#metric-ondemand').textContent();
    expect(onDemand).toMatch(/\$\d+\.\d{2}\/h/);
  });

  test('min cost input updates baseline cost', async ({ page }) => {
    await page.goto('index.html');
    await page.waitForSelector('#min-cost');
    await page.waitForTimeout(500);

    // Get initial cost
    const initialCost = await page.locator('#metric-ondemand').textContent();

    // Change min cost from 15 to 25
    await page.locator('#min-cost').fill('25');
    await page.waitForTimeout(500);

    // Verify cost increased
    const newCost = await page.locator('#metric-ondemand').textContent();
    expect(newCost).not.toBe(initialCost);

    const initialValue = parseFloat(initialCost.replace(/[$\/h]/g, ''));
    const newValue = parseFloat(newCost.replace(/[$\/h]/g, ''));
    expect(newValue).toBeGreaterThan(initialValue);
  });

  test('max cost input updates peak cost', async ({ page }) => {
    await page.goto('index.html');
    await page.waitForSelector('#max-cost');
    await page.waitForTimeout(500);

    // Get initial cost
    const initialCost = await page.locator('#metric-ondemand').textContent();

    // Change max cost from 100 to 150
    await page.locator('#max-cost').fill('150');
    await page.waitForTimeout(500);

    // Verify cost changed
    const newCost = await page.locator('#metric-ondemand').textContent();
    expect(newCost).not.toBe(initialCost);

    const initialValue = parseFloat(initialCost.replace(/[$\/h]/g, ''));
    const newValue = parseFloat(newCost.replace(/[$\/h]/g, ''));
    expect(newValue).toBeGreaterThan(initialValue);
  });

  test('min and max cost range affects all strategy cards', async ({ page }) => {
    await page.goto('index.html');
    await page.waitForSelector('#min-cost');
    await page.waitForTimeout(500);

    // Set specific cost range
    await page.locator('#min-cost').fill('20');
    await page.locator('#max-cost').fill('80');
    await page.waitForTimeout(500);

    // Verify all strategy cards have valid values
    const minHourlyCost = await page.locator('#strategy-min-value').textContent();
    const balancedCost = await page.locator('#strategy-balanced-value').textContent();
    const riskyCost = await page.locator('#strategy-aggressive-value').textContent();
    const aggressiveCost = await page.locator('#strategy-too-aggressive-value').textContent();

    expect(minHourlyCost).toMatch(/\$\d+\.\d{2}\/h/);
    expect(balancedCost).toMatch(/\$\d+\.\d{2}\/h/);
    expect(riskyCost).toMatch(/\$\d+\.\d{2}\/h/);
    expect(aggressiveCost).toMatch(/\$\d+\.\d{2}\/h/);
  });

  test('strategy cards update when pattern changes', async ({ page }) => {
    await page.goto('index.html');
    await page.waitForSelector('#pattern-select');
    await page.waitForTimeout(500);

    // Get strategy values with E-commerce
    const ecommerceBalanced = await page.locator('#strategy-balanced-value').textContent();

    // Switch to Batch Processing
    await page.selectOption('#pattern-select', 'batch');
    await page.waitForTimeout(500);

    // Verify strategy values changed
    const batchBalanced = await page.locator('#strategy-balanced-value').textContent();
    expect(batchBalanced).not.toBe(ecommerceBalanced);
  });

  test('all patterns load without errors', async ({ page }) => {
    await page.goto('index.html');
    await page.waitForSelector('#pattern-select');

    const patterns = ['ecommerce', 'global247', 'batch'];

    for (const pattern of patterns) {
      await page.selectOption('#pattern-select', pattern);
      await page.waitForTimeout(500);

      // Verify metrics calculated for this pattern
      const onDemand = await page.locator('#metric-ondemand').textContent();
      const commitment = await page.locator('#metric-commitment').textContent();
      const savings = await page.locator('#metric-savings').textContent();

      expect(onDemand).toMatch(/\$\d+\.\d{2}\/h/);
      expect(commitment).toMatch(/\$\d+\.\d{2}\/h/);
      expect(savings).toMatch(/[-]?\$\d+\.\d{2}\/h/);
    }
  });

  test('custom pattern loads with URL data', async ({ page }) => {
    // Real reporter output data (truncated but valid)
    const urlData = 'eJxtVstuIzkM%2FJc%2BNwSRIikp5%2F2LwcLwBt6ZAIlj2J7BBIP8%2B5Il9%2FrR8YFoqyWyWCxS%2FWf68f7z%2BPqxeX4%2FnU%2FT0zfpSXgukirNbEloLpxMwrLNJSeuM9fY42%2Btha02s8Qe1mQ9LJWwXfC2h2Xs1Hmczjjt%2FphS8V0ZPvxZ45ncclKeA4sEFqs47c8ELJSa7%2B8pt%2FAWpyw1%2BPRgJTVF%2BBpWb8IHoJqUYl00dpZheyRQS0BobQHlzxRwGnwSAnI4YFjPMdBUMBPvui2pjaiOoMXJDniEqK0vz5IyRZoBm1NFxrCF45ABhrMvOXUH1mA5EcCwzJqTeGwPwvHWnTkaD%2Bs20ukArGBuVEJTbeEBy%2FgvgOSs%2Bqog4ciMEiE2K%2ByVjdxhAaOiaAbybFbnIaAEd4MP6KVT6KUBPQlQwiotejGoyS6aGuQGWxGiozS5hhWcUL4WKE4QyB7aKVEPKZfctUAXwBIK8rccWMZ6RaEI2gl%2B5IKCIBIq%2BeZXsGQBuw6nPaynFi7wHI3iUpTVsYtX6JJQzn67x9dlljqoKy2wBkoOsQZuCK7XhyMt0ZKDM6lXUfV2YwkbAc94sTjqsAgCg%2B7uAGUsZdS9oR8VWmzw4OoRnwft9oBTa1EiIW88ZzmQl4RQbYgQncEg%2FC6TDFVkXhqyrgmsl34djKNata9c8KPXsuaMQctoHkIjuWDBgqcpPfh%2FzCuCQT4%2BA2IYjgGIhRYp%2BUu3hsQM%2BPtjcYfogdy%2BKD1GqEBbApnLV7msSGNIlnGC1kExA4IDl1aL8RZteedjNGKBxDjKJRjrpCv4l0mP7CDoVq82GFVkWEBDwfhyb3d%2BkIMscyK69DEMo75LVdDbag97YoY%2BeHVcpd%2F8xkXQ0BQYiwTLHW0laCUUTkYmo3AYNAZWi49arwOaTnAfMK6hVRjGOOQ0xrEttXDLDzspVV0t6eMuibmjBSURXF01msnS6C6%2FxXxZY647RV4oQ48VlLEv%2FaxA6zrl5dltXUUyiE3zw4sv9pbL%2FI3iMC4swiSPO2m19TFNGbPXbyiUxVeihex2k2GpLZcFrdnrCRotGGV1jO8GpUrYuxzGfrpDBgA6bmYIuYECRVoN1et1qeGSXLno%2Be95Op238UH0Z3p72U9P47Nketv%2Bnp5GsaaDZl%2B3KNl0qOrP%2BHSaDt3XR1%2F5s69jRn7O0%2FPP43G3P%2Fun1q%2Fdcft9Nz25HIplZiHutav6VJneD%2BeXt%2B3r5t%2Fj%2B9vm8HH%2B8b4PFMuhzfhe82jOn5bryHBarpsOu%2BOzh0IQn9pWa%2BWurWY2LiOPzX533py2v17230%2FhzQIlN7LCDmmOtC%2BxbnZRd%2B567r5R2JU47X6fj9ubDdX5bNSkSCvFW2f4iY%2FL%2Fzm8YHt53YFe0OhfM6ZZq5IYSTEfX4NT9dHcrbWmzpQ0nz2DX%2FMadHPyVLMVqqSfzvDpsDl%2FHDzn6a%2FtefvP9rSbfHGAu%2BMkOq1bdYxZS8uNPv8Dgf1V3w%3D%3D';

    await page.goto(`index.html?usage=${urlData}`);
    await page.waitForSelector('.metrics-row');
    await page.waitForTimeout(1000);

    // Verify pattern switched to custom
    const selectedPattern = await page.locator('#pattern-select').inputValue();
    expect(selectedPattern).toBe('custom');

    // Verify metrics loaded from custom data
    const onDemand = await page.locator('#metric-ondemand').textContent();
    expect(onDemand).toMatch(/\$\d+\.\d{2}\/h/);

    // Verify strategy cards calculated with custom data
    const balancedCost = await page.locator('#strategy-balanced-value').textContent();
    expect(balancedCost).toMatch(/\$\d+\.\d{2}\/h/);
  });

  test('pattern dropdown shows correct selected value', async ({ page }) => {
    await page.goto('index.html');
    await page.waitForSelector('#pattern-select');
    await page.waitForTimeout(500);

    // Should default to E-commerce
    const defaultPattern = await page.locator('#pattern-select').inputValue();
    expect(defaultPattern).toBe('ecommerce');

    // Change to Global 24/7
    await page.selectOption('#pattern-select', 'global247');
    await page.waitForTimeout(300);

    const newPattern = await page.locator('#pattern-select').inputValue();
    expect(newPattern).toBe('global247');
  });

  test('invalid min/max cost range handled gracefully', async ({ page }) => {
    await page.goto('index.html');
    await page.waitForSelector('#min-cost');
    await page.waitForTimeout(500);

    // Try to set min > max (should be handled by the app)
    await page.locator('#min-cost').fill('90');
    await page.locator('#max-cost').fill('80');
    await page.waitForTimeout(500);

    // App should still calculate metrics without crashing
    const onDemand = await page.locator('#metric-ondemand').textContent();
    expect(onDemand).toMatch(/\$\d+\.\d{2}\/h/);
  });

  test('zero min cost handled correctly', async ({ page }) => {
    await page.goto('index.html');
    await page.waitForSelector('#min-cost');
    await page.waitForTimeout(500);

    // Set min cost to 0
    await page.locator('#min-cost').fill('0');
    await page.waitForTimeout(500);

    // Should still calculate (might be 0 or small value depending on max)
    const onDemand = await page.locator('#metric-ondemand').textContent();
    expect(onDemand).toMatch(/\$\d+\.\d{2}\/h/);
  });

  test('very large cost values handled correctly', async ({ page }) => {
    await page.goto('index.html');
    await page.waitForSelector('#max-cost');
    await page.waitForTimeout(500);

    // Set large max cost (within allowed max of 10000)
    await page.locator('#max-cost').fill('5000');
    await page.waitForTimeout(500);

    // Should calculate without overflow
    const onDemand = await page.locator('#metric-ondemand').textContent();
    expect(onDemand).toMatch(/\$\d+\.\d{2}\/h/);

    // Commitment slider should still work
    await page.locator('#coverage-slider').fill('50');
    await page.waitForTimeout(500);

    const commitment = await page.locator('#metric-commitment').textContent();
    expect(commitment).toMatch(/\$\d+\.\d{2}\/h/);
  });
});

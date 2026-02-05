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

  test('strategy card cost matches top total cost when clicking Risky', async ({ page }) => {
    await page.goto('index.html');

    // Wait for page to load
    await page.waitForSelector('#strategy-aggressive');

    // Click Risky strategy
    await page.click('#strategy-aggressive');

    // Wait for metrics to update
    await page.waitForTimeout(500);

    // Get cost from strategy card
    const cardCost = await page.locator('#strategy-aggressive-value').textContent();

    // Get commitment from top metrics (should match card cost)
    const topCommitment = await page.locator('#metric-commitment').textContent();

    // Extract just the dollar amounts (remove /h suffix from top)
    const cardAmount = cardCost.trim().replace('/h', '');
    const topAmount = topCommitment.trim().replace('/h', '');

    expect(cardAmount).toBe(topAmount);
  });

  test('strategy values match with custom URL data', async ({ page }) => {
    // Real reporter output data (truncated for brevity, but representative)
    const urlData = 'eJxtVstuIzkM%2FJc%2BNwSRIikp5%2F2LwcLwBt6ZAIlj2J7BBIP8%2B5Il9%2FrR8YFoqyWyWCxS%2FWf68f7z%2BPqxeX4%2FnU%2FT0zfpSXgukirNbEloLpxMwrLNJSeuM9fY42%2Btha02s8Qe1mQ9LJWwXfC2h2Xs1Hmczjjt%2FphS8V0ZPvxZ45ncclKeA4sEFqs47c8ELJSa7%2B8pt%2FAWpyw1%2BPRgJTVF%2BBpWb8IHoJqUYl00dpZheyRQS0BobQHlzxRwGnwSAnI4YFjPMdBUMBPvui2pjaiOoMXJDniEqK0vz5IyRZoBm1NFxrCF45ABhrMvOXUH1mA5EcCwzJqTeGwPwvHWnTkaD%2Bs20ukArGBuVEJTbeEBy%2FgvgOSs%2Bqog4ciMEiE2K%2ByVjdxhAaOiaAbybFbnIaAEd4MP6KVT6KUBPQlQwiotejGoyS6aGuQGWxGiozS5hhWcUL4WKE4QyB7aKVEPKZfctUAXwBIK8rccWMZ6RaEI2gl%2B5IKCIBIq%2BeZXsGQBuw6nPaynFi7wHI3iUpTVsYtX6JJQzn67x9dlljqoKy2wBkoOsQZuCK7XhyMt0ZKDM6lXUfV2YwkbAc94sTjqsAgCg%2B7uAGUsZdS9oR8VWmzw4OoRnwft9oBTa1EiIW88ZzmQl4RQbYgQncEg%2FC6TDFVkXhqyrgmsl34djKNata9c8KPXsuaMQctoHkIjuWDBgqcpPfh%2FzCuCQT4%2BA2IYjgGIhRYp%2BUu3hsQM%2BPtjcYfogdy%2BKD1GqEBbApnLV7msSGNIlnGC1kExA4IDl1aL8RZteedjNGKBxDjKJRjrpCv4l0mP7CDoVq82GFVkWEBDwfhyb3d%2BkIMscyK69DEMo75LVdDbag97YoY%2BeHVcpd%2F8xkXQ0BQYiwTLHW0laCUUTkYmo3AYNAZWi49arwOaTnAfMK6hVRjGOOQ0xrEttXDLDzspVV0t6eMuibmjBSURXF01msnS6C6%2FxXxZY647RV4oQ48VlLEv%2FaxA6zrl5dltXUUyiE3zw4sv9pbL%2FI3iMC4swiSPO2m19TFNGbPXbyiUxVeihex2k2GpLZcFrdnrCRotGGV1jO8GpUrYuxzGfrpDBgA6bmYIuYECRVoN1et1qeGSXLno%2Be95Op238UH0Z3p72U9P47Nketv%2Bnp5GsaaDZl%2B3KNl0qOrP%2BHSaDt3XR1%2F5s69jRn7O0%2FPP43G3P%2Fun1q%2Fdcft9Nz25HIplZiHutav6VJneD%2BeXt%2B3r5t%2Fj%2B9vm8HH%2B8b4PFMuhzfhe82jOn5bryHBarpsOu%2BOzh0IQn9pWa%2BWurWY2LiOPzX533py2v17230%2FhzQIlN7LCDmmOtC%2BxbnZRd%2B567r5R2JU47X6fj9ubDdX5bNSkSCvFW2f4iY%2FL%2Fzm8YHt53YFe0OhfM6ZZq5IYSTEfX4NT9dHcrbWmzpQ0nz2DX%2FMadHPyVLMVqqSfzvDpsDl%2FHDzn6a%2FtefvP9rSbfHGAu%2BMkOq1bdYxZS8uNPv8Dgf1V3w%3D%3D';

    await page.goto(`index.html?usage=${urlData}`);

    // Wait for custom data to load
    await page.waitForSelector('.metrics-row');
    await page.waitForTimeout(1000);

    // Click Balanced strategy with custom data
    await page.click('#strategy-balanced');
    await page.waitForTimeout(500);

    // Get values from strategy card
    const cardSavings = await page.locator('#strategy-balanced-savings').textContent();
    const cardSavingsPct = await page.locator('#strategy-balanced-savings-pct').textContent();

    // Get values from top metrics
    const topSavings = await page.locator('#metric-savings').textContent();
    const topSavingsPct = await page.locator('#metric-savings-pct').textContent();

    // They must match with real data too
    expect(cardSavings.trim()).toBe(topSavings.trim());
    expect(cardSavingsPct.trim()).toBe(topSavingsPct.trim());
  });
});

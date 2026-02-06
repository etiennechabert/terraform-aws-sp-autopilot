import { test, expect } from '@playwright/test';

test.describe('Slider Interaction Tests', () => {
  test('commitment slider updates all metrics correctly', async ({ page }) => {
    await page.goto('index.html');
    await page.waitForSelector('#coverage-slider');
    await page.waitForTimeout(500);

    await page.locator('#coverage-slider').fill('35');
    await page.waitForTimeout(500);

    const commitment = await page.locator('#metric-commitment').textContent();
    expect(commitment).toMatch(/\$\d+\.\d{2}\/h/);
    expect(commitment).not.toBe('$0.00/h');

    const savings = await page.locator('#metric-savings').textContent();
    const spillover = await page.locator('#metric-spillover').textContent();
    const waste = await page.locator('#metric-waste').textContent();

    expect(savings).not.toBe('$0.00/h');
    expect(spillover).not.toBe('$0.00/h');
    expect(waste).toMatch(/\$\d+\.\d{2}\/h/);
  });

  test('savings percentage slider updates metrics', async ({ page }) => {
    await page.goto('index.html');
    await page.waitForSelector('#savings-percentage');

    const initialSavings = await page.locator('#metric-savings').textContent();

    await page.locator('#savings-percentage').fill('50');
    await page.waitForTimeout(500);

    const savingsDisplay = await page.locator('#savings-display').textContent();
    expect(savingsDisplay).toBe('50%');

    const newSavings = await page.locator('#metric-savings').textContent();
    expect(newSavings).not.toBe(initialSavings);

    const initialValue = parseFloat(initialSavings.replace(/[$\/h]/g, ''));
    const newValue = parseFloat(newSavings.replace(/[$\/h]/g, ''));
    expect(newValue).toBeGreaterThan(initialValue);
  });

  test('load factor slider updates chart data', async ({ page }) => {
    await page.goto('index.html');
    await page.waitForSelector('#load-factor');

    const initialCost = await page.locator('#metric-ondemand').textContent();

    await page.locator('#load-factor').fill('150');
    await page.waitForTimeout(500);

    const loadFactorDisplay = await page.locator('#load-factor-display').textContent();
    expect(loadFactorDisplay).toBe('+50%');

    const loadFactorHint = await page.locator('#load-factor-hint').textContent();
    expect(loadFactorHint).toContain('150%');

    const newCost = await page.locator('#metric-ondemand').textContent();
    expect(newCost).not.toBe(initialCost);

    const initialValue = parseFloat(initialCost.replace(/[$\/h]/g, ''));
    const newValue = parseFloat(newCost.replace(/[$\/h]/g, ''));
    expect(newValue).toBeGreaterThan(initialValue);
  });

  test('combined slider changes update consistently', async ({ page }) => {
    await page.goto('index.html');
    await page.waitForSelector('#coverage-slider');

    await page.locator('#coverage-slider').fill('40');
    await page.waitForTimeout(200);
    await page.locator('#savings-percentage').fill('35');
    await page.waitForTimeout(200);
    await page.locator('#load-factor').fill('120');
    await page.waitForTimeout(500);

    const savingsDisplay = await page.locator('#savings-display').textContent();
    expect(savingsDisplay).toBe('35%');

    const loadFactorDisplay = await page.locator('#load-factor-display').textContent();
    expect(loadFactorDisplay).toBe('+20%');

    const commitment = await page.locator('#metric-commitment').textContent();
    const savings = await page.locator('#metric-savings').textContent();

    expect(commitment).toMatch(/\$\d+\.\d{2}\/h/);
    expect(savings).toMatch(/[-]?\$\d+\.\d{2}\/h/);
  });
});

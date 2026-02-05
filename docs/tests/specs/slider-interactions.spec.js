import { test, expect } from '@playwright/test';

test.describe('Slider Interaction Tests', () => {
  test('commitment slider updates all metrics correctly', async ({ page }) => {
    await page.goto('index.html');

    // Wait for page to load
    await page.waitForSelector('#coverage-slider');
    await page.waitForTimeout(500);

    // Move commitment slider to 35
    await page.locator('#coverage-slider').fill('35');
    await page.waitForTimeout(500);

    // Verify coverage units shows the slider value (on-demand coverage)
    const coverageUnits = await page.locator('#coverage-units').textContent();
    expect(coverageUnits).toContain('$35.00/h');

    // Verify SP Commitment metric shows the discounted cost (35 * 0.7 = 24.50 with 30% savings)
    const commitment = await page.locator('#metric-commitment').textContent();
    expect(commitment).toContain('24.50');

    // Verify metrics recalculated (not zero)
    const savings = await page.locator('#metric-savings').textContent();
    const spillover = await page.locator('#metric-spillover').textContent();
    const waste = await page.locator('#metric-waste').textContent();

    expect(savings).not.toBe('$0.00/h');
    expect(spillover).not.toBe('$0.00/h');
    // Waste might be zero if perfectly balanced, so we just check it's a valid format
    expect(waste).toMatch(/\$\d+\.\d{2}\/h/);
  });

  test('commitment slider at 0 shows no commitment', async ({ page }) => {
    await page.goto('index.html');
    await page.waitForSelector('#coverage-slider');

    // Set to 0
    await page.locator('#coverage-slider').fill('0');
    await page.waitForTimeout(500);

    const commitment = await page.locator('#metric-commitment').textContent();
    expect(commitment).toContain('0.00');

    // With no commitment, savings should be $0.00/h
    const savings = await page.locator('#metric-savings').textContent();
    expect(savings).toBe('$0.00/h');

    // All cost should be spillover (on-demand)
    const onDemand = await page.locator('#metric-ondemand').textContent();
    const totalCost = await page.locator('#metric-savingsplan').textContent();
    expect(onDemand).toBe(totalCost);
  });

  test('commitment slider at 100 shows maximum commitment', async ({ page }) => {
    await page.goto('index.html');
    await page.waitForSelector('#coverage-slider');

    // Set to 100 (maximum)
    await page.locator('#coverage-slider').fill('100');
    await page.waitForTimeout(500);

    // Verify coverage units shows the slider value
    const coverageUnits = await page.locator('#coverage-units').textContent();
    expect(coverageUnits).toContain('$100.00/h');

    // Verify commitment metric shows the discounted cost (100 * 0.7 = 70 with 30% savings)
    const commitment = await page.locator('#metric-commitment').textContent();
    expect(commitment).toContain('70.00');

    // At max commitment, there should be some waste
    const waste = await page.locator('#metric-waste').textContent();
    expect(waste).not.toBe('$0.00/h');
  });

  test('savings percentage slider updates metrics', async ({ page }) => {
    await page.goto('index.html');
    await page.waitForSelector('#savings-percentage');

    // Get initial savings value
    const initialSavings = await page.locator('#metric-savings').textContent();

    // Change savings percentage from 30% to 50%
    await page.locator('#savings-percentage').fill('50');
    await page.waitForTimeout(500);

    // Verify display updated
    const savingsDisplay = await page.locator('#savings-display').textContent();
    expect(savingsDisplay).toBe('50%');

    // Verify metrics recalculated
    const newSavings = await page.locator('#metric-savings').textContent();
    expect(newSavings).not.toBe(initialSavings);

    // Higher savings percentage should increase net savings
    const initialValue = parseFloat(initialSavings.replace(/[$\/h]/g, ''));
    const newValue = parseFloat(newSavings.replace(/[$\/h]/g, ''));
    expect(newValue).toBeGreaterThan(initialValue);
  });

  test('savings percentage at 0% shows no discount benefit', async ({ page }) => {
    await page.goto('index.html');
    await page.waitForSelector('#savings-percentage');

    // Set commitment to non-zero
    await page.locator('#coverage-slider').fill('35');
    await page.waitForTimeout(200);

    // Set savings to 0%
    await page.locator('#savings-percentage').fill('0');
    await page.waitForTimeout(500);

    // With 0% savings, we're paying full price for commitment (no benefit)
    const savings = await page.locator('#metric-savings').textContent();

    // Savings should be negative (we're losing money by committing with 0% discount)
    expect(savings).toMatch(/-\$\d+\.\d{2}\/h/);
  });

  test('savings percentage at 99% shows maximum discount', async ({ page }) => {
    await page.goto('index.html');
    await page.waitForSelector('#savings-percentage');

    // Set commitment to 35
    await page.locator('#coverage-slider').fill('35');
    await page.waitForTimeout(200);

    // Set savings to 99% (maximum)
    await page.locator('#savings-percentage').fill('99');
    await page.waitForTimeout(500);

    const savingsDisplay = await page.locator('#savings-display').textContent();
    expect(savingsDisplay).toBe('99%');

    // At 99% discount, commitment cost should be nearly free
    const commitment = await page.locator('#metric-commitment').textContent();
    const commitmentValue = parseFloat(commitment.replace(/[$\/h]/g, ''));

    // 35 dollars at 99% off = $0.35/h
    expect(commitmentValue).toBeLessThan(1);
  });

  test('load factor slider updates chart data', async ({ page }) => {
    await page.goto('index.html');
    await page.waitForSelector('#load-factor');

    // Get initial on-demand cost
    const initialCost = await page.locator('#metric-ondemand').textContent();

    // Increase load factor to 150%
    await page.locator('#load-factor').fill('150');
    await page.waitForTimeout(500);

    // Verify display shows delta from 100% (150 - 100 = +50%)
    const loadFactorDisplay = await page.locator('#load-factor-display').textContent();
    expect(loadFactorDisplay).toBe('+50%');

    // Verify hint text updated
    const loadFactorHint = await page.locator('#load-factor-hint').textContent();
    expect(loadFactorHint).toContain('150%');

    // Verify costs increased
    const newCost = await page.locator('#metric-ondemand').textContent();
    expect(newCost).not.toBe(initialCost);

    const initialValue = parseFloat(initialCost.replace(/[$\/h]/g, ''));
    const newValue = parseFloat(newCost.replace(/[$\/h]/g, ''));
    expect(newValue).toBeGreaterThan(initialValue);
  });

  test('load factor at 50% halves the costs', async ({ page }) => {
    await page.goto('index.html');
    await page.waitForSelector('#load-factor');

    // Get cost at 100%
    await page.locator('#load-factor').fill('100');
    await page.waitForTimeout(500);
    const cost100 = await page.locator('#metric-ondemand').textContent();
    const value100 = parseFloat(cost100.replace(/[$\/h]/g, ''));

    // Set to 50%
    await page.locator('#load-factor').fill('50');
    await page.waitForTimeout(500);
    const cost50 = await page.locator('#metric-ondemand').textContent();
    const value50 = parseFloat(cost50.replace(/[$\/h]/g, ''));

    // Should be approximately half (within 1% tolerance for rounding)
    expect(value50).toBeCloseTo(value100 / 2, 0);
  });

  test('reset button restores load factor to 100%', async ({ page }) => {
    await page.goto('index.html');
    await page.waitForSelector('#reset-load-factor');

    // Change load factor
    await page.locator('#load-factor').fill('75');
    await page.waitForTimeout(500);

    // Click reset button
    await page.click('#reset-load-factor');
    await page.waitForTimeout(500);

    // Verify reset to 100%
    const loadFactorDisplay = await page.locator('#load-factor-display').textContent();
    expect(loadFactorDisplay).toBe('100%');

    const loadFactorValue = await page.locator('#load-factor').inputValue();
    expect(loadFactorValue).toBe('100');
  });

  test('combined slider changes update consistently', async ({ page }) => {
    await page.goto('index.html');
    await page.waitForSelector('#coverage-slider');

    // Make multiple slider changes
    await page.locator('#coverage-slider').fill('40');
    await page.waitForTimeout(200);
    await page.locator('#savings-percentage').fill('35');
    await page.waitForTimeout(200);
    await page.locator('#load-factor').fill('120');
    await page.waitForTimeout(500);

    // Verify all displays match
    const coverageUnits = await page.locator('#coverage-units').textContent();
    expect(coverageUnits).toContain('$40.00/h');

    const savingsDisplay = await page.locator('#savings-display').textContent();
    expect(savingsDisplay).toBe('35%');

    const loadFactorDisplay = await page.locator('#load-factor-display').textContent();
    expect(loadFactorDisplay).toBe('+20%'); // 120 - 100 = +20%

    // Verify metrics are calculated (non-zero)
    const commitment = await page.locator('#metric-commitment').textContent();
    const savings = await page.locator('#metric-savings').textContent();

    expect(commitment).toMatch(/\$\d+\.\d{2}\/h/);
    expect(savings).toMatch(/[-]?\$\d+\.\d{2}\/h/);
  });
});

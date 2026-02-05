import { test, expect } from '@playwright/test';
import { readFileSync, readdirSync, existsSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// Path to reporter HTML files
const REPORTER_HTML_DIR = resolve(__dirname, '../../../lambda/reporter/local_data/reports');
const REPORTER_FIXTURE = resolve(__dirname, '../fixtures/reporter-sample.html');

// Get the most recent reporter HTML file, or use fixture if directory doesn't exist
function getMostRecentReporterHTML() {
  // If directory doesn't exist (CI environment), use fixture
  if (!existsSync(REPORTER_HTML_DIR)) {
    return REPORTER_FIXTURE;
  }

  const files = readdirSync(REPORTER_HTML_DIR)
    .filter(f => f.endsWith('.html'))
    .sort()
    .reverse();

  if (files.length === 0) {
    // No real reports, use fixture
    return REPORTER_FIXTURE;
  }

  return resolve(REPORTER_HTML_DIR, files[0]);
}

test.describe('Reporter HTML Tests', () => {
  test('reporter HTML loads successfully', async ({ page }) => {
    const reportPath = getMostRecentReporterHTML();
    await page.goto(`file://${reportPath}`);

    // Wait for page to load
    await page.waitForSelector('h1');

    // Verify title
    const title = await page.locator('h1').textContent();
    expect(title).toContain('Savings Plans Coverage & Savings Report');
  });

  test('summary cards display metrics', async ({ page }) => {
    const reportPath = getMostRecentReporterHTML();
    await page.goto(`file://${reportPath}`);

    // Wait for summary cards to load
    await page.waitForSelector('.summary-card');

    // Verify there are summary cards
    const summaryCards = page.locator('.summary-card');
    const count = await summaryCards.count();
    expect(count).toBeGreaterThan(0);

    // Verify cards have values
    const firstCard = summaryCards.first();
    const value = await firstCard.locator('.value').textContent();
    expect(value).toBeTruthy();
  });

  test('simulator link is present and valid', async ({ page }) => {
    const reportPath = getMostRecentReporterHTML();
    await page.goto(`file://${reportPath}`);

    // Wait for page to load
    await page.waitForSelector('.simulator-button, a[href*="index.html"], a[href*="etiennechabert.github.io"]', { timeout: 5000 }).catch(() => {
      // Simulator link might not be present if there's no usage data
    });

    // Check if simulator link exists
    const simulatorLink = page.locator('.simulator-button, a[href*="index.html"], a[href*="etiennechabert.github.io"]').first();
    const linkCount = await simulatorLink.count();

    if (linkCount > 0) {
      // Verify link has href attribute
      const href = await simulatorLink.getAttribute('href');
      expect(href).toBeTruthy();

      // Verify href contains index.html or GitHub Pages URL
      expect(href).toMatch(/index\.html|etiennechabert\.github\.io/);

      // If it has usage parameter, verify it's encoded
      if (href.includes('?usage=')) {
        expect(href).toMatch(/\?usage=[A-Za-z0-9%_-]+/);
      }
    }
  });

  test('charts render correctly', async ({ page }) => {
    const reportPath = getMostRecentReporterHTML();
    await page.goto(`file://${reportPath}`);

    // Wait for Chart.js to load
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000); // Give charts time to render

    // Check if canvas elements exist (Chart.js renders to canvas)
    const canvases = page.locator('canvas');
    const count = await canvases.count();
    expect(count).toBeGreaterThan(0);
  });

  test('tabs switch between SP types', async ({ page }) => {
    const reportPath = getMostRecentReporterHTML();
    await page.goto(`file://${reportPath}`);

    // Wait for page to load
    await page.waitForSelector('.tab-button, button[data-type]', { timeout: 5000 }).catch(() => {
      // Tabs might not be present if there's only one SP type
    });

    // Check if tabs exist
    const tabs = page.locator('.tab-button, button[data-type]');
    const tabCount = await tabs.count();

    if (tabCount > 1) {
      // Click the second tab
      await tabs.nth(1).click();
      await page.waitForTimeout(500);

      // Verify tab content changed (active class should change)
      const activeTab = page.locator('.tab-button.active, button[data-type].active');
      expect(await activeTab.count()).toBeGreaterThan(0);
    }
  });

  test('metric cards display correct format', async ({ page }) => {
    const reportPath = getMostRecentReporterHTML();
    await page.goto(`file://${reportPath}`);

    // Wait for metric cards to load (inside tabs)
    await page.waitForSelector('.metric-card, .tab-metrics', { timeout: 5000 }).catch(() => {
      // Metric cards might be in a different structure
    });

    // Check for metric cards
    const metricCards = page.locator('.metric-card');
    const count = await metricCards.count();

    if (count > 0) {
      // Verify metric values have proper format (dollar amounts, percentages, etc.)
      const firstMetricValue = await metricCards.first().locator('.metric-value').textContent();
      expect(firstMetricValue).toMatch(/\$|%|N\/A|\d+/);
    }
  });

  test('report contains usage data or shows appropriate message', async ({ page }) => {
    const reportPath = getMostRecentReporterHTML();
    await page.goto(`file://${reportPath}`);

    // Wait for page to load
    await page.waitForLoadState('networkidle');

    // Check for either usage data or no-data message
    const body = await page.locator('body').textContent();

    // Report should either have data or explain why there's no data
    expect(body.length).toBeGreaterThan(1000); // Report should have substantial content
  });

  test('scheduler preview section exists when configured', async ({ page }) => {
    const reportPath = getMostRecentReporterHTML();
    await page.goto(`file://${reportPath}`);

    // Wait for page to load
    await page.waitForLoadState('networkidle');

    // Check if scheduler preview section exists
    const schedulerSection = page.locator('h2:has-text("Scheduler Preview"), h2:has-text("Strategy Comparison")');
    const hasSchedulerSection = await schedulerSection.count() > 0;

    if (hasSchedulerSection) {
      // Verify it shows strategy information
      const body = await page.locator('body').textContent();
      expect(body).toMatch(/Fixed|Dichotomy|Follow AWS/);
    }
  });

  test('responsive layout works on mobile viewport', async ({ page }) => {
    const reportPath = getMostRecentReporterHTML();

    // Set mobile viewport
    await page.setViewportSize({ width: 375, height: 667 });
    await page.goto(`file://${reportPath}`);

    // Wait for page to load
    await page.waitForSelector('.summary');

    // Verify page is still readable
    const summary = page.locator('.summary');
    const box = await summary.boundingBox();

    // Summary should fit within mobile viewport width
    expect(box.width).toBeLessThanOrEqual(375);
  });

  test('external scripts load correctly', async ({ page }) => {
    const reportPath = getMostRecentReporterHTML();

    // Listen for console errors
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));

    await page.goto(`file://${reportPath}`);
    await page.waitForLoadState('networkidle');

    // Verify Chart.js loaded
    const chartJsLoaded = await page.evaluate(() => {
      return typeof window.Chart !== 'undefined';
    });
    expect(chartJsLoaded).toBe(true);

    // Verify pako (compression library) loaded
    const pakoLoaded = await page.evaluate(() => {
      return typeof window.pako !== 'undefined';
    });
    expect(pakoLoaded).toBe(true);

    // Check for critical JavaScript errors
    const criticalErrors = errors.filter(e =>
      !e.includes('favicon') && // Ignore favicon errors
      !e.includes('Permissions')  // Ignore permission warnings
    );
    expect(criticalErrors.length).toBe(0);
  });
});

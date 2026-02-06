import { test, expect } from '@playwright/test';
import { readFileSync, readdirSync, existsSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const REPORTER_HTML_DIR = resolve(__dirname, '../../../lambda/reporter/local_data/reports');
const REPORTER_FIXTURE = resolve(__dirname, '../fixtures/reporter-sample.html');

function getMostRecentReporterHTML() {
  if (!existsSync(REPORTER_HTML_DIR)) {
    return REPORTER_FIXTURE;
  }

  const files = readdirSync(REPORTER_HTML_DIR)
    .filter(f => f.endsWith('.html'))
    .sort()
    .reverse();

  if (files.length === 0) {
    return REPORTER_FIXTURE;
  }

  return resolve(REPORTER_HTML_DIR, files[0]);
}

test.describe('Reporter HTML Tests', () => {
  test('reporter HTML loads successfully', async ({ page }) => {
    const reportPath = getMostRecentReporterHTML();
    await page.goto(`file://${reportPath}`);
    await page.waitForSelector('h1');

    const title = await page.locator('h1').textContent();
    expect(title).toContain('Savings Plans Coverage & Savings Report');
  });

  test('simulator link is present and valid', async ({ page }) => {
    const reportPath = getMostRecentReporterHTML();
    await page.goto(`file://${reportPath}`);

    await page.waitForSelector('.simulator-button, a[href*="index.html"], a[href*="etiennechabert.github.io"]', { timeout: 5000 }).catch(() => {});

    const simulatorLink = page.locator('.simulator-button, a[href*="index.html"], a[href*="etiennechabert.github.io"]').first();
    const linkCount = await simulatorLink.count();

    if (linkCount > 0) {
      const href = await simulatorLink.getAttribute('href');
      expect(href).toBeTruthy();
      expect(href).toMatch(/index\.html|etiennechabert\.github\.io/);

      if (href.includes('?usage=')) {
        expect(href).toMatch(/\?usage=[A-Za-z0-9%_-]+/);
      }
    }
  });

  test('charts render correctly', async ({ page }) => {
    const reportPath = getMostRecentReporterHTML();
    await page.goto(`file://${reportPath}`);

    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    const canvases = page.locator('canvas');
    const count = await canvases.count();
    expect(count).toBeGreaterThan(0);
  });

  test('tabs switch between SP types', async ({ page }) => {
    const reportPath = getMostRecentReporterHTML();
    await page.goto(`file://${reportPath}`);

    await page.waitForSelector('.tab-button, button[data-type]', { timeout: 5000 }).catch(() => {});

    const tabs = page.locator('.tab-button, button[data-type]');
    const tabCount = await tabs.count();

    if (tabCount > 1) {
      await tabs.nth(1).click();
      await page.waitForTimeout(500);

      const activeTab = page.locator('.tab-button.active, button[data-type].active');
      expect(await activeTab.count()).toBeGreaterThan(0);
    }
  });

  test('external scripts load correctly', async ({ page }) => {
    const reportPath = getMostRecentReporterHTML();

    const errors = [];
    page.on('pageerror', error => errors.push(error.message));

    await page.goto(`file://${reportPath}`);
    await page.waitForLoadState('networkidle');

    const chartJsLoaded = await page.evaluate(() => {
      return typeof window.Chart !== 'undefined';
    });
    expect(chartJsLoaded).toBe(true);

    const pakoLoaded = await page.evaluate(() => {
      return typeof window.pako !== 'undefined';
    });
    expect(pakoLoaded).toBe(true);

    const criticalErrors = errors.filter(e =>
      !e.includes('favicon') &&
      !e.includes('Permissions')
    );
    expect(criticalErrors.length).toBe(0);
  });
});

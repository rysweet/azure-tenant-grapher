import { test, expect } from '@playwright/test';

test.describe('Quick Screenshot', () => {
  test('capture current state', async ({ page }) => {
    // Navigate to the app
    await page.goto('http://localhost:5173');
    await page.waitForLoadState('networkidle');

    // Take a full page screenshot with timestamp
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, -5);
    await page.screenshot({
      path: `screenshots/current-state-${timestamp}.png`,
      fullPage: true
    });

    console.log(`✅ Screenshot saved: screenshots/current-state-${timestamp}.png`);
  });

  test('capture specific tab', async ({ page }, testInfo) => {
    const tabName = testInfo.project.metadata?.tab || 'Status';

    await page.goto('http://localhost:5173');
    await page.waitForLoadState('networkidle');

    // Click on the specified tab if not Status (default)
    if (tabName !== 'Status') {
      await page.click(`text=${tabName}`);
      await page.waitForTimeout(1000); // Wait for content to load
    }

    const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, -5);
    await page.screenshot({
      path: `screenshots/${tabName.toLowerCase()}-tab-${timestamp}.png`,
      fullPage: true
    });

    console.log(`✅ Screenshot of ${tabName} tab saved`);
  });
});

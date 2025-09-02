import { test } from '@playwright/test';

test.describe('SPA Screenshots for PR', () => {
  test('capture main screens', async ({ page }) => {
    await page.goto('http://localhost:5173');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    // Status tab
    await page.screenshot({
      path: 'screenshots/pr-status-tab.png',
      fullPage: false
    });

    // Build tab
    await page.click('text=Build');
    await page.waitForTimeout(1000);
    await page.screenshot({
      path: 'screenshots/pr-build-tab.png',
      fullPage: false
    });

    // Visualize tab
    await page.click('text=Visualize');
    await page.waitForTimeout(2000);
    await page.screenshot({
      path: 'screenshots/pr-visualize-tab.png',
      fullPage: false
    });

    // CLI tab
    await page.click('text=CLI');
    await page.waitForTimeout(1000);
    await page.screenshot({
      path: 'screenshots/pr-cli-tab.png',
      fullPage: false
    });

    // Docs tab
    await page.click('text=Docs');
    await page.waitForTimeout(1000);
    await page.screenshot({
      path: 'screenshots/pr-docs-tab.png',
      fullPage: false
    });

    console.log('Screenshots saved to screenshots/ directory');
  });
});

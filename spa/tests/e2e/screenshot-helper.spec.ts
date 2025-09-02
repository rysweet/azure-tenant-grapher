import { test } from '@playwright/test';

/**
 * Helper test for taking quick screenshots during development.
 * This is a temporary utility and not a proper test.
 * Use only for capturing current state for documentation.
 */

test.describe('Screenshot Helper (Dev Only)', () => {
  test.skip('capture specific feature', async ({ page }) => {
    // This test is skipped by default - remove .skip to use
    const feature = process.env.FEATURE || 'current-state';

    await page.goto('http://localhost:5173');
    await page.waitForLoadState('networkidle');

    // Add navigation logic here if needed
    // e.g., await page.click('text=Visualize');

    const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, -5);
    await page.screenshot({
      path: `screenshots/${feature}-${timestamp}.png`,
      fullPage: true
    });

    console.log(`✅ Screenshot saved: ${feature}-${timestamp}.png`);
  });
});

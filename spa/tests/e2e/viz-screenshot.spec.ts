import { test } from '@playwright/test';

test('capture visualization tab', async ({ page }) => {
  // Set a good viewport size
  await page.setViewportSize({ width: 1600, height: 900 });

  // Navigate to the app
  await page.goto('http://localhost:5173');
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(2000);

  // Click on Visualize tab
  await page.click('text=Visualize');
  console.log('Clicked Visualize tab');

  // Wait for graph to load
  await page.waitForTimeout(3000);

  // Take screenshot
  await page.screenshot({
    path: 'screenshots/visualization-tab.png',
    fullPage: false
  });

  console.log('Screenshot saved to screenshots/visualization-tab.png');

  // Also capture Status tab for comparison
  await page.click('text=Status');
  await page.waitForTimeout(1000);
  await page.screenshot({
    path: 'screenshots/status-tab.png',
    fullPage: false
  });

  console.log('Screenshot saved to screenshots/status-tab.png');

  // Capture Build tab
  await page.click('text=Build');
  await page.waitForTimeout(1000);
  await page.screenshot({
    path: 'screenshots/build-tab.png',
    fullPage: false
  });

  console.log('Screenshot saved to screenshots/build-tab.png');
});

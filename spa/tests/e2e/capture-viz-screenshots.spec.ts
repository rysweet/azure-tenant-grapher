import { test } from '@playwright/test';

/**
 * Capture SPA Visualization Tab Screenshots
 *
 * For Multi-Layer Graph Projections presentation
 * Captures baseline, scale-up, and scale-down visualization screenshots
 */

test.describe('Capture Visualization Screenshots', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('http://localhost:5173');
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(2000);
  });

  test('Capture baseline visualization', async ({ page }) => {
    // Navigate to Visualize tab
    const vizTab = page.locator('button:has-text("Visualize"), button:has-text("Visualization")').first();

    if (await vizTab.isVisible({ timeout: 5000 })) {
      await vizTab.click();
      await page.waitForTimeout(3000); // Wait for graph to render

      // Take fullscreen screenshot
      await page.screenshot({
        path: '/home/azureuser/src/atg/docs/presentations/multi-layer-screenshots/spa-viz-baseline.png',
        fullPage: true,
      });

      console.log('✓ Captured baseline visualization screenshot');
    } else {
      console.log('⚠ Visualize tab not found');
    }
  });

  test('Capture with graph visible', async ({ page }) => {
    // Navigate to Visualize tab
    const vizTab = page.locator('button:has-text("Visualize"), button:has-text("Visualization")').first();

    if (await vizTab.isVisible({ timeout: 5000 })) {
      await vizTab.click();
      await page.waitForTimeout(5000); // Extra time for graph rendering

      // Look for graph canvas/container
      const graphContainer = page.locator('canvas, svg, #cy, .visualization-container').first();
      const graphVisible = await graphContainer.isVisible({ timeout: 5000 }).catch(() => false);

      console.log('Graph visible:', graphVisible);

      // Take screenshot
      await page.screenshot({
        path: '/home/azureuser/src/atg/docs/presentations/multi-layer-screenshots/spa-viz-with-graph.png',
        fullPage: true,
      });

      console.log('✓ Captured visualization with graph');
    }
  });

  test('Capture visualization controls', async ({ page }) => {
    // Navigate to Visualize tab
    const vizTab = page.locator('button:has-text("Visualize")').first();

    if (await vizTab.isVisible({ timeout: 5000 })) {
      await vizTab.click();
      await page.waitForTimeout(3000);

      // Look for controls panel
      const controls = page.locator('[class*="control"], [class*="panel"], [class*="toolbar"]').first();

      if (await controls.isVisible({ timeout: 2000 }).catch(() => false)) {
        console.log('Controls visible');
      }

      // Capture full visualization interface
      await page.screenshot({
        path: '/home/azureuser/src/atg/docs/presentations/multi-layer-screenshots/spa-viz-interface.png',
        fullPage: true,
      });

      console.log('✓ Captured visualization interface');
    }
  });
});

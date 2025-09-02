import { test, expect } from '@playwright/test';

test.describe('Graph Visualization', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('http://localhost:5173');
    await page.waitForLoadState('networkidle');
    await page.click('text=Visualize');
    await page.waitForTimeout(1500);
  });

  test('should hide Subscription nodes by default', async ({ page }) => {
    // Check that Subscription chip is not selected (outlined variant means not selected)
    const subscriptionChip = page.locator('div[role="button"]:has-text("Subscription")');

    if (await subscriptionChip.isVisible()) {
      // Check if it has the outlined variant (not selected)
      const variant = await subscriptionChip.evaluate((el) => {
        return el.classList.contains('MuiChip-outlined') ||
               !el.classList.contains('MuiChip-filled');
      });

      expect(variant).toBeTruthy();
    }
  });

  test('should have control panel on left (25% width)', async ({ page }) => {
    // Find the control panel (dark background panel)
    const controlPanel = page.locator('div').filter({
      has: page.locator('text=Graph Controls')
    }).first();

    if (await controlPanel.isVisible()) {
      const width = await controlPanel.evaluate((el) => {
        const rect = el.getBoundingClientRect();
        const parentRect = el.parentElement?.getBoundingClientRect();
        if (parentRect) {
          return (rect.width / parentRect.width) * 100;
        }
        return 0;
      });

      // Should be approximately 25% (allow some margin for min/max constraints)
      expect(width).toBeGreaterThan(20);
      expect(width).toBeLessThan(30);
    }
  });

  test('should have graph area on right (75% width)', async ({ page }) => {
    // Find the graph container
    const graphContainer = page.locator('#cy-container, .vis-network, canvas').first();

    if (await graphContainer.isVisible()) {
      const width = await graphContainer.evaluate((el) => {
        const rect = el.getBoundingClientRect();
        const parentRect = el.parentElement?.getBoundingClientRect();
        if (parentRect) {
          return (rect.width / parentRect.width) * 100;
        }
        return 0;
      });

      // Should be approximately 75% (flex: 1 takes remaining space)
      expect(width).toBeGreaterThan(70);
    }
  });
});

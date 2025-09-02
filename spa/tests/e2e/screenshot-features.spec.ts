import { test, expect } from '@playwright/test';

test.describe('Azure Tenant Grapher Feature Screenshots', () => {
  test.beforeEach(async ({ page }) => {
    // Connect to the already-running Electron app
    await page.goto('http://localhost:5173');

    // Wait for the app to load
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(2000); // Give it time to fully render
  });

  test('1. Status Tab - Dependency Check', async ({ page }) => {
    // Navigate to Status tab (should be default)
    await page.screenshot({ path: 'screenshots/01-status-tab-dependencies.png', fullPage: true });

    // Look for dependency section
    const depSection = await page.locator('text=System Dependencies');
    if (await depSection.isVisible()) {
      console.log('✅ Dependency check moved to Status tab');
    }
  });

  test('2. Visualize Tab - Granular Resource Types', async ({ page }) => {
    // Navigate to Visualize tab
    await page.click('text=Visualize');
    await page.waitForTimeout(2000); // Wait for graph to load

    await page.screenshot({ path: 'screenshots/02-visualize-granular-types.png', fullPage: true });
    console.log('✅ Screenshot of granular resource types in visualization');
  });

  test('3. Visualize Tab - Colored Edges and Legend', async ({ page }) => {
    // Navigate to Visualize tab first
    await page.click('text=Visualize');
    await page.waitForTimeout(1000);

    // Click the info/legend button if available
    const infoButton = await page.locator('[aria-label="Show legend"]');
    if (await infoButton.isVisible()) {
      await infoButton.click();
      await page.waitForTimeout(500);
    }

    await page.screenshot({ path: 'screenshots/03-visualize-edge-colors-legend.png', fullPage: true });
    console.log('✅ Screenshot of colored edges and legend');
  });

  test('4. Visualize Tab - Advanced Filters', async ({ page }) => {
    // Navigate to Visualize tab first
    await page.click('text=Visualize');
    await page.waitForTimeout(1000);

    // Look for and click Filters button
    const filtersButton = await page.locator('button:has-text("Filters")');
    if (await filtersButton.isVisible()) {
      await filtersButton.click();
      await page.waitForTimeout(500);
      await page.screenshot({ path: 'screenshots/04-visualize-advanced-filters.png', fullPage: true });
      console.log('✅ Screenshot of advanced filters panel');
    }
  });

  test('5. CLI Tab - Doctor Command', async ({ page }) => {
    // Navigate to CLI tab
    await page.click('text=CLI');
    await page.waitForTimeout(1500);

    await page.screenshot({ path: 'screenshots/05-cli-tab-doctor.png', fullPage: true });
    console.log('✅ Screenshot of CLI tab with doctor command capability');
  });

  test('6. Agent Tab - Sample Queries', async ({ page }) => {
    // Navigate to Agent Mode tab
    await page.click('text=Agent Mode');
    await page.waitForTimeout(1500);

    await page.screenshot({ path: 'screenshots/06-agent-sample-queries.png', fullPage: true });
    console.log('✅ Screenshot of Agent tab with sample queries');
  });

  test('7. Config Tab - Clean Configuration', async ({ page }) => {
    // Navigate to Config tab
    await page.click('text=Config');
    await page.waitForTimeout(1000);

    await page.screenshot({ path: 'screenshots/07-config-tab-clean.png', fullPage: true });
    console.log('✅ Screenshot of Config tab (dependencies removed)');
  });

  test('8. Tab Navigation - Grey Style', async ({ page }) => {
    // Take a screenshot focusing on the tab navigation
    const tabNav = await page.locator('[role="tablist"]').first();
    if (await tabNav.isVisible()) {
      await tabNav.screenshot({ path: 'screenshots/08-tab-navigation-grey.png' });
      console.log('✅ Screenshot of grey tab navigation style');
    } else {
      // Fallback to full screenshot
      await page.screenshot({ path: 'screenshots/08-tab-navigation-grey.png', fullPage: false });
    }
  });

  test('9. Generate Tabs - No Loading State', async ({ page }) => {
    // Check Generate Spec tab
    await page.click('text=Generate Spec');
    await page.waitForTimeout(1000);

    await page.screenshot({ path: 'screenshots/09-generate-spec-no-loading.png', fullPage: true });
    console.log('✅ Screenshot of Generate Spec tab without loading state');
  });

  test('10. Logs Tab - No Loading State', async ({ page }) => {
    // Navigate to Logs tab
    await page.click('text=Logs');
    await page.waitForTimeout(1000);

    await page.screenshot({ path: 'screenshots/10-logs-tab-no-loading.png', fullPage: true });
    console.log('✅ Screenshot of Logs tab without loading state');
  });
});

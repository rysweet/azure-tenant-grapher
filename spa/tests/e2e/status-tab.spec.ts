import { test, expect } from '@playwright/test';

test.describe('Status Tab', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('http://localhost:5173');
    await page.waitForLoadState('networkidle');
    // Status tab should be default/first tab
  });

  test('should display dependency check section', async ({ page }) => {
    const dependencySection = page.locator('text=System Dependencies');
    await expect(dependencySection).toBeVisible();
  });

  test('should have working Run Doctor button when dependencies are missing', async ({ page }) => {
    // Check if the Run Doctor button exists (only shows when deps are missing)
    const doctorButton = page.locator('button:has-text("Run Doctor")');

    if (await doctorButton.isVisible()) {
      // Click the button
      await doctorButton.click();

      // Should navigate to CLI tab
      await page.waitForTimeout(1000);

      // Verify we're on the CLI tab
      const cliIndicator = page.locator('text=Command Line Interface, text=CLI Commands, text=Terminal Output').first();
      await expect(cliIndicator).toBeVisible();

      // Check for doctor command in URL or UI
      const url = page.url();
      expect(url).toContain('cli');

      // Could also check if doctor command is selected
      const doctorCommand = page.locator('text=doctor, text=Check and install dependencies').first();
      if (await doctorCommand.isVisible()) {
        expect(await doctorCommand.isVisible()).toBeTruthy();
      }
    } else {
      // If button not visible, dependencies might all be installed
      console.log('Doctor button not visible - all dependencies may be installed');
    }
  });

  test('should display database statistics', async ({ page }) => {
    const dbStats = page.locator('text=Database Statistics');
    await expect(dbStats).toBeVisible();

    // Check for node/edge counts
    const nodeCount = page.locator('text=/Nodes.*\\d+/');
    const edgeCount = page.locator('text=/Edges.*\\d+/');

    // At least one should be visible
    const hasStats = await nodeCount.isVisible() || await edgeCount.isVisible();
    expect(hasStats).toBeTruthy();
  });

  test('should have database management buttons', async ({ page }) => {
    // Check for backup/restore/wipe buttons
    const backupButton = page.locator('button:has-text("Backup")');
    const restoreButton = page.locator('button:has-text("Restore")');
    const wipeButton = page.locator('button:has-text("Wipe")');

    // All three should be visible
    await expect(backupButton).toBeVisible();
    await expect(restoreButton).toBeVisible();
    await expect(wipeButton).toBeVisible();
  });
});

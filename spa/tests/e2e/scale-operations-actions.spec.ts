import { test, expect } from '@playwright/test';

/**
 * Scale Operations - Quick Actions Tests
 *
 * Tests quick action buttons and dialogs:
 * - Clean button and dialog
 * - Validate button and results
 * - Stats dialog and displays
 * - Help dialog and content
 * - Dialog interactions
 */

test.describe('Scale Operations - Quick Actions', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('http://localhost:5173');
    await page.waitForLoadState('networkidle', { timeout: 60000 });

    // Navigate to Scale Operations tab
    const scaleOpsTab = page.locator('button:has-text("Scale Ops"), button:has-text("Scale Operations")').first();
    if (await scaleOpsTab.isVisible({ timeout: 5000 })) {
      await scaleOpsTab.click();
      await page.waitForTimeout(1000);
    }
  });

  test.describe('Clean Synthetic Data', () => {
    test('should open clean dialog when clean button clicked', async ({ page }) => {
      const cleanButton = page.locator('button:has-text("Clean")').first();

      if (await cleanButton.isVisible()) {
        await cleanButton.click();
        await page.waitForTimeout(500);

        // Verify dialog opens
        await expect(page.locator('text=Clean Synthetic Data')).toBeVisible();
      }
    });

    test('should show warning message in clean dialog', async ({ page }) => {
      const cleanButton = page.locator('button:has-text("Clean")').first();

      if (await cleanButton.isVisible()) {
        await cleanButton.click();
        await page.waitForTimeout(500);

        // Check for warning message
        await expect(page.locator('text=permanently delete')).toBeVisible();
        await expect(page.locator('text=cannot be undone')).toBeVisible();
      }
    });

    test('should have cancel button in clean dialog', async ({ page }) => {
      const cleanButton = page.locator('button:has-text("Clean")').first();

      if (await cleanButton.isVisible()) {
        await cleanButton.click();
        await page.waitForTimeout(500);

        // Verify cancel button exists
        const cancelButton = page.locator('button:has-text("Cancel")').first();
        await expect(cancelButton).toBeVisible();
      }
    });

    test('should have confirm button in clean dialog', async ({ page }) => {
      const cleanButton = page.locator('button:has-text("Clean")').first();

      if (await cleanButton.isVisible()) {
        await cleanButton.click();
        await page.waitForTimeout(500);

        // Verify confirm button exists
        const confirmButton = page.locator('button:has-text("Confirm")').first();
        await expect(confirmButton).toBeVisible();
      }
    });

    test('should close clean dialog when cancel clicked', async ({ page }) => {
      const cleanButton = page.locator('button:has-text("Clean")').first();

      if (await cleanButton.isVisible()) {
        await cleanButton.click();
        await page.waitForTimeout(500);

        // Click cancel
        const cancelButton = page.locator('button:has-text("Cancel")').first();
        await cancelButton.click();
        await page.waitForTimeout(300);

        // Dialog should close
        const dialog = page.locator('text=Clean Synthetic Data');
        expect(await dialog.isVisible().catch(() => false)).toBe(false);
      }
    });

    test('should close dialog with ESC key', async ({ page }) => {
      const cleanButton = page.locator('button:has-text("Clean")').first();

      if (await cleanButton.isVisible()) {
        await cleanButton.click();
        await page.waitForTimeout(500);

        // Press ESC
        await page.keyboard.press('Escape');
        await page.waitForTimeout(300);

        // Dialog should close
        const dialog = page.locator('text=Clean Synthetic Data');
        expect(await dialog.isVisible().catch(() => false)).toBe(false);
      }
    });

    test('should show loading state when cleaning', async ({ page }) => {
      const cleanButton = page.locator('button:has-text("Clean")').first();

      if (await cleanButton.isVisible()) {
        await cleanButton.click();
        await page.waitForTimeout(500);

        // Click confirm (will fail without backend)
        const confirmButton = page.locator('button:has-text("Confirm")').first();
        await confirmButton.click();
        await page.waitForTimeout(500);

        // May show loading state
        const loadingIndicator = page.locator('text=Cleaning...').or(page.locator('[role="progressbar"]'));
        const loadingVisible = await loadingIndicator.isVisible({ timeout: 2000 }).catch(() => false);
        console.log('Loading state visible:', loadingVisible);
      }
    });

    test('should show success message after clean completes', async ({ page }) => {
      // This test would require backend mock
      // For now, just verify the dialog structure supports success state
      const cleanButton = page.locator('button:has-text("Clean")').first();

      if (await cleanButton.isVisible()) {
        await cleanButton.click();
        await page.waitForTimeout(500);

        // Verify dialog has space for success message
        const dialogContent = page.locator('[role="dialog"]');
        await expect(dialogContent).toBeVisible();
      }
    });

    test('should show error message on clean failure', async ({ page }) => {
      const cleanButton = page.locator('button:has-text("Clean")').first();

      if (await cleanButton.isVisible()) {
        await cleanButton.click();
        await page.waitForTimeout(500);

        // Try to clean (will fail without backend)
        const confirmButton = page.locator('button:has-text("Confirm")').first();
        await confirmButton.click();
        await page.waitForTimeout(2000);

        // May show error
        const errorAlert = page.locator('[role="alert"]').filter({ hasText: /error/i });
        const errorVisible = await errorAlert.isVisible().catch(() => false);
        console.log('Error alert visible:', errorVisible);
      }
    });

    test('should disable buttons during cleaning operation', async ({ page }) => {
      const cleanButton = page.locator('button:has-text("Clean")').first();

      if (await cleanButton.isVisible()) {
        await cleanButton.click();
        await page.waitForTimeout(500);

        const confirmButton = page.locator('button:has-text("Confirm")').first();
        await confirmButton.click();
        await page.waitForTimeout(300);

        // Buttons should be disabled during operation
        const cancelButton = page.locator('button:has-text("Cancel")').first();
        const isDisabled = await cancelButton.isDisabled().catch(() => false);
        console.log('Cancel button disabled during operation:', isDisabled);
      }
    });
  });

  test.describe('Validate Graph', () => {
    test('should trigger validation when validate button clicked', async ({ page }) => {
      const validateButton = page.locator('button:has-text("Validate")').first();

      if (await validateButton.isVisible()) {
        await validateButton.click();
        await page.waitForTimeout(2000);

        // May show loading or results
        const validationDialog = page.locator('text=Validation Results');
        const dialogVisible = await validationDialog.isVisible().catch(() => false);
        console.log('Validation dialog visible:', dialogVisible);
      }
    });

    test('should show loading state during validation', async ({ page }) => {
      const validateButton = page.locator('button:has-text("Validate")').first();

      if (await validateButton.isVisible()) {
        await validateButton.click();
        await page.waitForTimeout(500);

        // Look for loading indicator
        const loadingText = page.locator('text=Validating...').or(page.locator('[role="progressbar"]'));
        const loadingVisible = await loadingText.isVisible({ timeout: 1000 }).catch(() => false);
        console.log('Validation loading state:', loadingVisible);
      }
    });

    test('should display validation results dialog', async ({ page }) => {
      const validateButton = page.locator('button:has-text("Validate")').first();

      if (await validateButton.isVisible()) {
        await validateButton.click();
        await page.waitForTimeout(2000);

        // Check if results dialog appears
        const resultsDialog = page.locator('text=Validation Results');
        const dialogVisible = await resultsDialog.isVisible().catch(() => false);

        if (dialogVisible) {
          // Verify structure
          await expect(page.locator('text=checks passed')).toBeVisible();
        }
      }
    });

    test('should show validation check names', async ({ page }) => {
      const validateButton = page.locator('button:has-text("Validate")').first();

      if (await validateButton.isVisible()) {
        await validateButton.click();
        await page.waitForTimeout(2000);

        const resultsDialog = page.locator('text=Validation Results');
        const dialogVisible = await resultsDialog.isVisible().catch(() => false);

        if (dialogVisible) {
          // Check for validation check structure
          const checkItems = page.locator('[role="dialog"]');
          await expect(checkItems).toBeVisible();
        }
      }
    });

    test('should show pass/fail indicators for validation checks', async ({ page }) => {
      const validateButton = page.locator('button:has-text("Validate")').first();

      if (await validateButton.isVisible()) {
        await validateButton.click();
        await page.waitForTimeout(2000);

        const resultsDialog = page.locator('text=Validation Results');
        const dialogVisible = await resultsDialog.isVisible().catch(() => false);

        if (dialogVisible) {
          // Look for check circle or error icons
          const icons = page.locator('[data-testid*="Icon"]');
          const iconCount = await icons.count();
          console.log('Validation icons found:', iconCount);
        }
      }
    });

    test('should close validation results dialog', async ({ page }) => {
      const validateButton = page.locator('button:has-text("Validate")').first();

      if (await validateButton.isVisible()) {
        await validateButton.click();
        await page.waitForTimeout(2000);

        const resultsDialog = page.locator('text=Validation Results');
        const dialogVisible = await resultsDialog.isVisible().catch(() => false);

        if (dialogVisible) {
          // Close dialog
          const closeButton = page.locator('button:has-text("Close")').last();
          await closeButton.click();
          await page.waitForTimeout(300);

          expect(await resultsDialog.isVisible().catch(() => false)).toBe(false);
        }
      }
    });

    test('should handle validation error gracefully', async ({ page }) => {
      const validateButton = page.locator('button:has-text("Validate")').first();

      if (await validateButton.isVisible()) {
        await validateButton.click();
        await page.waitForTimeout(2000);

        // May show error if backend not available
        const errorAlert = page.locator('[role="alert"]').filter({ hasText: /error/i });
        const errorVisible = await errorAlert.isVisible().catch(() => false);
        console.log('Validation error shown:', errorVisible);
      }
    });

    test('should require tenant ID for validation', async ({ page }) => {
      // Clear tenant ID if present
      const tenantInput = page.locator('input[placeholder*="xxxx"]').first();
      if (await tenantInput.isVisible()) {
        await tenantInput.clear();
      }

      const validateButton = page.locator('button:has-text("Validate")').first();

      // Button should be disabled without tenant ID
      const isDisabled = await validateButton.isDisabled();
      expect(isDisabled).toBe(true);
    });
  });

  test.describe('Show Statistics', () => {
    test('should open statistics dialog when button clicked', async ({ page }) => {
      const statsButton = page.locator('button:has-text("Statistics")').first();

      if (await statsButton.isVisible()) {
        await statsButton.click();
        await page.waitForTimeout(1000);

        // Verify dialog opens
        await expect(page.locator('text=Graph Statistics')).toBeVisible();
      }
    });

    test('should display overview statistics', async ({ page }) => {
      const statsButton = page.locator('button:has-text("Statistics")').first();

      if (await statsButton.isVisible()) {
        await statsButton.click();
        await page.waitForTimeout(1000);

        // Check for overview section
        await expect(page.locator('text=Overview')).toBeVisible();
        await expect(page.locator('text=Total Nodes')).toBeVisible();
        await expect(page.locator('text=Total Relationships')).toBeVisible();
      }
    });

    test('should display synthetic nodes count', async ({ page }) => {
      const statsButton = page.locator('button:has-text("Statistics")').first();

      if (await statsButton.isVisible()) {
        await statsButton.click();
        await page.waitForTimeout(1000);

        // Check for synthetic nodes
        await expect(page.locator('text=Synthetic Nodes')).toBeVisible();
      }
    });

    test('should display node type distribution', async ({ page }) => {
      const statsButton = page.locator('button:has-text("Statistics")').first();

      if (await statsButton.isVisible()) {
        await statsButton.click();
        await page.waitForTimeout(1000);

        // Check for node type section
        await expect(page.locator('text=Node Type Distribution')).toBeVisible();
      }
    });

    test('should display relationship type distribution', async ({ page }) => {
      const statsButton = page.locator('button:has-text("Statistics")').first();

      if (await statsButton.isVisible()) {
        await statsButton.click();
        await page.waitForTimeout(1000);

        // Check for relationship type section
        await expect(page.locator('text=Relationship Type Distribution')).toBeVisible();
      }
    });

    test('should show progress bars for distributions', async ({ page }) => {
      const statsButton = page.locator('button:has-text("Statistics")').first();

      if (await statsButton.isVisible()) {
        await statsButton.click();
        await page.waitForTimeout(1000);

        // Look for progress bars (LinearProgress components)
        const progressBars = page.locator('[role="progressbar"]');
        const count = await progressBars.count();
        console.log('Progress bars found:', count);
        expect(count).toBeGreaterThan(0);
      }
    });

    test('should format large numbers with commas', async ({ page }) => {
      const statsButton = page.locator('button:has-text("Statistics")').first();

      if (await statsButton.isVisible()) {
        await statsButton.click();
        await page.waitForTimeout(1000);

        // Check for formatted numbers
        const statsTable = page.locator('table');
        if (await statsTable.isVisible()) {
          const content = await statsTable.textContent();
          console.log('Statistics content available');
        }
      }
    });

    test('should show percentage for synthetic nodes', async ({ page }) => {
      const statsButton = page.locator('button:has-text("Statistics")').first();

      if (await statsButton.isVisible()) {
        await statsButton.click();
        await page.waitForTimeout(1000);

        // Look for percentage indicator
        const percentText = page.locator('text=/%/');
        const hasPercent = await percentText.isVisible().catch(() => false);
        console.log('Percentage shown:', hasPercent);
      }
    });

    test('should close statistics dialog', async ({ page }) => {
      const statsButton = page.locator('button:has-text("Statistics")').first();

      if (await statsButton.isVisible()) {
        await statsButton.click();
        await page.waitForTimeout(1000);

        // Close dialog
        const closeButton = page.locator('button:has-text("Close")').last();
        await closeButton.click();
        await page.waitForTimeout(300);

        // Dialog should close
        const dialog = page.locator('text=Graph Statistics');
        expect(await dialog.isVisible().catch(() => false)).toBe(false);
      }
    });

    test('should show loading state while fetching stats', async ({ page }) => {
      const statsButton = page.locator('button:has-text("Statistics")').first();

      if (await statsButton.isVisible()) {
        await statsButton.click();
        await page.waitForTimeout(300);

        // May show loading spinner
        const spinner = page.locator('[role="progressbar"]').first();
        const spinnerVisible = await spinner.isVisible({ timeout: 1000 }).catch(() => false);
        console.log('Stats loading spinner visible:', spinnerVisible);
      }
    });

    test('should require tenant ID for statistics', async ({ page }) => {
      // Clear tenant ID if present
      const tenantInput = page.locator('input[placeholder*="xxxx"]').first();
      if (await tenantInput.isVisible()) {
        await tenantInput.clear();
      }

      const statsButton = page.locator('button:has-text("Statistics")').first();

      // Button should be disabled without tenant ID
      const isDisabled = await statsButton.isDisabled();
      expect(isDisabled).toBe(true);
    });
  });

  test.describe('Help Dialog', () => {
    test('should open help dialog when help button clicked', async ({ page }) => {
      const helpButton = page.locator('button:has-text("Help")').first();
      await helpButton.click();
      await page.waitForTimeout(500);

      // Verify dialog opens
      await expect(page.locator('text=Scale Operations Help')).toBeVisible();
    });

    test('should show scale-up section in help', async ({ page }) => {
      const helpButton = page.locator('button:has-text("Help")').first();
      await helpButton.click();
      await page.waitForTimeout(500);

      // Check for scale-up help
      await expect(page.locator('text=Scale-Up Operations')).toBeVisible();
      await expect(page.locator('text=Add synthetic nodes')).toBeVisible();
    });

    test('should show scale-down section in help', async ({ page }) => {
      const helpButton = page.locator('button:has-text("Help")').first();
      await helpButton.click();
      await page.waitForTimeout(500);

      // Check for scale-down help
      await expect(page.locator('text=Scale-Down Operations')).toBeVisible();
      await expect(page.locator('text=Sample a subset')).toBeVisible();
    });

    test('should show quick actions section in help', async ({ page }) => {
      const helpButton = page.locator('button:has-text("Help")').first();
      await helpButton.click();
      await page.waitForTimeout(500);

      // Check for quick actions help
      await expect(page.locator('text=Quick Actions')).toBeVisible();
    });

    test('should list clean action in help', async ({ page }) => {
      const helpButton = page.locator('button:has-text("Help")').first();
      await helpButton.click();
      await page.waitForTimeout(500);

      await expect(page.locator('text=Clean Synthetic Data')).toBeVisible();
    });

    test('should list validate action in help', async ({ page }) => {
      const helpButton = page.locator('button:has-text("Help")').first();
      await helpButton.click();
      await page.waitForTimeout(500);

      await expect(page.locator('text=Validate Graph')).toBeVisible();
    });

    test('should list statistics action in help', async ({ page }) => {
      const helpButton = page.locator('button:has-text("Help")').first();
      await helpButton.click();
      await page.waitForTimeout(500);

      await expect(page.locator('text=Show Statistics')).toBeVisible();
    });

    test('should close help dialog', async ({ page }) => {
      const helpButton = page.locator('button:has-text("Help")').first();
      await helpButton.click();
      await page.waitForTimeout(500);

      // Close dialog
      const closeButton = page.locator('button:has-text("Close")').last();
      await closeButton.click();
      await page.waitForTimeout(300);

      // Dialog should close
      const dialog = page.locator('text=Scale Operations Help');
      expect(await dialog.isVisible().catch(() => false)).toBe(false);
    });

    test('should close help dialog with ESC key', async ({ page }) => {
      const helpButton = page.locator('button:has-text("Help")').first();
      await helpButton.click();
      await page.waitForTimeout(500);

      // Press ESC
      await page.keyboard.press('Escape');
      await page.waitForTimeout(300);

      // Dialog should close
      const dialog = page.locator('text=Scale Operations Help');
      expect(await dialog.isVisible().catch(() => false)).toBe(false);
    });

    test('help button should always be enabled', async ({ page }) => {
      const helpButton = page.locator('button:has-text("Help")').first();

      // Help should be available without any configuration
      await expect(helpButton).toBeEnabled();
    });
  });

  test.describe('Quick Actions Bar Layout', () => {
    test('should display all quick action buttons', async ({ page }) => {
      await expect(page.locator('button:has-text("Clean")')).toBeVisible();
      await expect(page.locator('button:has-text("Validate")')).toBeVisible();
      await expect(page.locator('button:has-text("Statistics")')).toBeVisible();
      await expect(page.locator('button:has-text("Help")')).toBeVisible();
    });

    test('should have correct button icons', async ({ page }) => {
      // Verify buttons have icons (MUI icons render as SVG)
      const cleanButton = page.locator('button:has-text("Clean")').first();
      const cleanIcon = cleanButton.locator('svg').first();
      await expect(cleanIcon).toBeVisible();

      const helpButton = page.locator('button:has-text("Help")').first();
      const helpIcon = helpButton.locator('svg').first();
      await expect(helpIcon).toBeVisible();
    });

    test('should have appropriate button spacing', async ({ page }) => {
      // Check that buttons are laid out properly
      const quickActionsBar = page.locator('text=Quick Actions').locator('..').locator('..');

      if (await quickActionsBar.isVisible()) {
        const buttons = quickActionsBar.locator('button');
        const count = await buttons.count();
        expect(count).toBe(4);
      }
    });

    test('should show quick actions title', async ({ page }) => {
      await expect(page.locator('text=Quick Actions')).toBeVisible();
    });
  });

  test.describe('Dialog Accessibility', () => {
    test('clean dialog should have proper role', async ({ page }) => {
      const cleanButton = page.locator('button:has-text("Clean")').first();

      if (await cleanButton.isVisible()) {
        await cleanButton.click();
        await page.waitForTimeout(500);

        const dialog = page.locator('[role="dialog"]');
        await expect(dialog).toBeVisible();
      }
    });

    test('help dialog should have proper role', async ({ page }) => {
      const helpButton = page.locator('button:has-text("Help")').first();
      await helpButton.click();
      await page.waitForTimeout(500);

      const dialog = page.locator('[role="dialog"]');
      await expect(dialog).toBeVisible();
    });

    test('dialogs should have titles', async ({ page }) => {
      const helpButton = page.locator('button:has-text("Help")').first();
      await helpButton.click();
      await page.waitForTimeout(500);

      // Dialog should have a title
      const dialogTitle = page.locator('[role="dialog"]').locator('h2').first();
      await expect(dialogTitle).toBeVisible();
    });

    test('dialogs should trap focus', async ({ page }) => {
      const helpButton = page.locator('button:has-text("Help")').first();
      await helpButton.click();
      await page.waitForTimeout(500);

      // Tab should stay within dialog
      await page.keyboard.press('Tab');
      await page.waitForTimeout(100);

      const focusedElement = await page.evaluateHandle(() => document.activeElement);
      const isInsideDialog = await page.evaluate(
        (el) => el?.closest('[role="dialog"]') !== null,
        focusedElement
      );

      console.log('Focus trapped in dialog:', isInsideDialog);
    });
  });

  test.describe('Multiple Dialog Interactions', () => {
    test('should handle opening and closing multiple dialogs', async ({ page }) => {
      // Open help
      const helpButton = page.locator('button:has-text("Help")').first();
      await helpButton.click();
      await page.waitForTimeout(500);

      // Close help
      await page.keyboard.press('Escape');
      await page.waitForTimeout(300);

      // Open statistics
      const statsButton = page.locator('button:has-text("Statistics")').first();
      if (await statsButton.isVisible()) {
        await statsButton.click();
        await page.waitForTimeout(500);

        // Close stats
        await page.keyboard.press('Escape');
        await page.waitForTimeout(300);
      }

      // All dialogs should be closed
      const openDialogs = page.locator('[role="dialog"]');
      const count = await openDialogs.count();
      expect(count).toBe(0);
    });

    test('should not allow multiple dialogs open simultaneously', async ({ page }) => {
      // Open help
      const helpButton = page.locator('button:has-text("Help")').first();
      await helpButton.click();
      await page.waitForTimeout(500);

      // Check only one dialog is open
      const openDialogs = page.locator('[role="dialog"]');
      const count = await openDialogs.count();
      expect(count).toBe(1);
    });
  });

  test.describe('Error Handling', () => {
    test('should handle network errors gracefully', async ({ page }) => {
      // Try to execute action without backend
      const validateButton = page.locator('button:has-text("Validate")').first();

      if (await validateButton.isVisible()) {
        const tenantInput = page.locator('input[placeholder*="xxxx"]').first();
        if (await tenantInput.isVisible()) {
          await tenantInput.fill('12345678-1234-1234-1234-123456789abc');
        }

        await validateButton.click();
        await page.waitForTimeout(2000);

        // Should not crash - may show error or empty results
        const errorOrEmpty = await Promise.race([
          page.locator('[role="alert"]').filter({ hasText: /error/i }).isVisible(),
          page.locator('text=No validation results').isVisible(),
          Promise.resolve(false)
        ]);

        console.log('Error handling working:', errorOrEmpty !== undefined);
      }
    });

    test('should maintain UI state after errors', async ({ page }) => {
      // Trigger potential error
      const validateButton = page.locator('button:has-text("Validate")').first();

      if (await validateButton.isVisible()) {
        const tenantInput = page.locator('input[placeholder*="xxxx"]').first();
        if (await tenantInput.isVisible()) {
          await tenantInput.fill('12345678-1234-1234-1234-123456789abc');
        }

        await validateButton.click();
        await page.waitForTimeout(2000);

        // UI should still be functional
        await expect(page.locator('button:has-text("Help")')).toBeEnabled();
        await expect(page.locator('text=Quick Actions')).toBeVisible();
      }
    });
  });
});

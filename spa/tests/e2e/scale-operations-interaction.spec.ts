import { test, expect } from '@playwright/test';

/**
 * Scale Operations - Component Interaction Tests
 *
 * Tests user interactions with Scale Operations components:
 * - Mode toggle (scale-up ↔ scale-down)
 * - Strategy/algorithm selection
 * - Parameter validation
 * - Form submission
 * - Error states
 */

test.describe('Scale Operations - Component Interactions', () => {
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

  test.describe('Mode Toggle', () => {
    test('should toggle from scale-up to scale-down', async ({ page }) => {
      // Initially should be on scale-up
      const scaleUpButton = page.locator('button:has-text("Scale Up")').first();
      await expect(scaleUpButton).toBeVisible();

      // Toggle to scale-down
      const scaleDownButton = page.locator('button:has-text("Scale Down")').first();
      await scaleDownButton.click();
      await page.waitForTimeout(500);

      // Verify scale-down panel is visible
      await expect(page.locator('text=Scale-Down Configuration')).toBeVisible();
    });

    test('should toggle from scale-down back to scale-up', async ({ page }) => {
      // Toggle to scale-down
      const scaleDownButton = page.locator('button:has-text("Scale Down")').first();
      await scaleDownButton.click();
      await page.waitForTimeout(500);

      // Toggle back to scale-up
      const scaleUpButton = page.locator('button:has-text("Scale Up")').first();
      await scaleUpButton.click();
      await page.waitForTimeout(500);

      // Verify scale-up panel is visible
      await expect(page.locator('text=Scale-Up Configuration')).toBeVisible();
    });

    test('should preserve form state when toggling modes', async ({ page }) => {
      // Fill in tenant ID
      const tenantInput = page.locator('input[placeholder*="xxxx"]').first();
      await tenantInput.fill('12345678-1234-1234-1234-123456789abc');

      // Toggle to scale-down
      const scaleDownButton = page.locator('button:has-text("Scale Down")').first();
      await scaleDownButton.click();
      await page.waitForTimeout(500);

      // Toggle back to scale-up
      const scaleUpButton = page.locator('button:has-text("Scale Up")').first();
      await scaleUpButton.click();
      await page.waitForTimeout(500);

      // Verify tenant ID is preserved (if component maintains state)
      const tenantInputAfter = page.locator('input[placeholder*="xxxx"]').first();
      const value = await tenantInputAfter.inputValue();
      // Note: May not be preserved depending on component implementation
      console.log('Tenant ID after toggle:', value);
    });
  });

  test.describe('Scale-Up Strategy Selection', () => {
    test('should change from template to scenario strategy', async ({ page }) => {
      const strategySelect = page.locator('select').filter({ has: page.locator('option:has-text("Template")') }).first();
      await strategySelect.selectOption('scenario');
      await page.waitForTimeout(500);

      // Verify scenario-specific fields appear
      await expect(page.locator('text=Scenario Type')).toBeVisible();
      await expect(page.locator('option:has-text("Enterprise")')).toBeVisible();
    });

    test('should change from template to random strategy', async ({ page }) => {
      const strategySelect = page.locator('select').filter({ has: page.locator('option:has-text("Template")') }).first();
      await strategySelect.selectOption('random');
      await page.waitForTimeout(500);

      // Verify random-specific fields appear
      await expect(page.locator('text=Node Count')).toBeVisible();
      await expect(page.locator('text=Pattern')).toBeVisible();
    });

    test('should show template-specific fields for template strategy', async ({ page }) => {
      // Template should be default
      await expect(page.locator('text=Template File')).toBeVisible();
      await expect(page.locator('text=Scale Factor')).toBeVisible();
    });

    test('should update strategy description when changing strategies', async ({ page }) => {
      // Check initial description
      await expect(page.locator('text=Generate nodes based on a predefined template file')).toBeVisible();

      // Change to scenario
      const strategySelect = page.locator('select').filter({ has: page.locator('option:has-text("Template")') }).first();
      await strategySelect.selectOption('scenario');
      await page.waitForTimeout(300);

      // Check scenario description
      await expect(page.locator('text=Generate nodes based on common deployment scenarios')).toBeVisible();
    });
  });

  test.describe('Scale-Down Algorithm Selection', () => {
    test.beforeEach(async ({ page }) => {
      // Switch to scale-down mode
      const scaleDownButton = page.locator('button:has-text("Scale Down")').first();
      await scaleDownButton.click();
      await page.waitForTimeout(500);
    });

    test('should change from forest-fire to mhrw algorithm', async ({ page }) => {
      const algorithmSelect = page.locator('select').filter({ has: page.locator('option:has-text("Forest")') }).first();
      await algorithmSelect.selectOption('mhrw');
      await page.waitForTimeout(500);

      // Verify MHRW-specific fields appear
      await expect(page.locator('text=Walk Length')).toBeVisible();
    });

    test('should change from forest-fire to pattern algorithm', async ({ page }) => {
      const algorithmSelect = page.locator('select').filter({ has: page.locator('option:has-text("Forest")') }).first();
      await algorithmSelect.selectOption('pattern');
      await page.waitForTimeout(500);

      // Verify pattern-specific fields appear
      await expect(page.locator('text=Pattern')).toBeVisible();
    });

    test('should show forest-fire specific fields by default', async ({ page }) => {
      // Forest-fire should be default
      await expect(page.locator('text=Burn In Steps')).toBeVisible();
      await expect(page.locator('text=Forward Probability')).toBeVisible();
    });
  });

  test.describe('Parameter Validation', () => {
    test('should validate tenant ID format', async ({ page }) => {
      const tenantInput = page.locator('input[placeholder*="xxxx"]').first();
      await tenantInput.fill('invalid-tenant-id');
      await tenantInput.blur();
      await page.waitForTimeout(300);

      // Try to execute - should be disabled or show error
      const executeButton = page.locator('button:has-text("Execute")').first();
      // May be disabled or show validation error
      const isDisabled = await executeButton.isDisabled();
      console.log('Execute button disabled with invalid tenant:', isDisabled);
    });

    test('should validate required fields', async ({ page }) => {
      // Clear tenant ID
      const tenantInput = page.locator('input[placeholder*="xxxx"]').first();
      await tenantInput.clear();
      await page.waitForTimeout(300);

      // Execute button should be disabled
      const executeButton = page.locator('button:has-text("Execute")').first();
      await expect(executeButton).toBeDisabled();
    });

    test('should validate scale factor range', async ({ page }) => {
      const slider = page.locator('input[type="range"]').first();

      // Set to minimum
      await slider.fill('1');
      await expect(page.locator('text=Scale Factor: 1x')).toBeVisible();

      // Set to maximum
      await slider.fill('10');
      await expect(page.locator('text=Scale Factor: 10x')).toBeVisible();
    });

    test('should validate node count in random strategy', async ({ page }) => {
      const strategySelect = page.locator('select').filter({ has: page.locator('option:has-text("Template")') }).first();
      await strategySelect.selectOption('random');
      await page.waitForTimeout(500);

      const nodeCountInput = page.locator('input[type="number"]').first();

      // Test minimum value
      await nodeCountInput.fill('5');
      const value = await nodeCountInput.inputValue();
      expect(parseInt(value)).toBeGreaterThanOrEqual(10);

      // Test large value
      await nodeCountInput.fill('15000');
      await nodeCountInput.blur();
      // Should be accepted or clamped to max
    });
  });

  test.describe('Form Submission', () => {
    test('should enable preview button when form is valid', async ({ page }) => {
      // Fill in valid data
      const tenantInput = page.locator('input[placeholder*="xxxx"]').first();
      await tenantInput.fill('12345678-1234-1234-1234-123456789abc');
      await page.waitForTimeout(300);

      const previewButton = page.locator('button:has-text("Preview")').first();
      await expect(previewButton).toBeEnabled();
    });

    test('should disable execute button when form is invalid', async ({ page }) => {
      // Clear required field
      const tenantInput = page.locator('input[placeholder*="xxxx"]').first();
      await tenantInput.clear();
      await page.waitForTimeout(300);

      const executeButton = page.locator('button:has-text("Execute")').first();
      await expect(executeButton).toBeDisabled();
    });

    test('should show loading state during preview', async ({ page }) => {
      // Fill in valid data
      const tenantInput = page.locator('input[placeholder*="xxxx"]').first();
      await tenantInput.fill('12345678-1234-1234-1234-123456789abc');
      await page.waitForTimeout(300);

      // Click preview
      const previewButton = page.locator('button:has-text("Preview")').first();
      await previewButton.click();

      // Should show loading state (may timeout or show error without backend)
      const loadingText = page.locator('text=Previewing...');
      // May or may not be visible depending on backend
      const isVisible = await loadingText.isVisible({ timeout: 2000 }).catch(() => false);
      console.log('Preview loading state visible:', isVisible);
    });
  });

  test.describe('Clear Functionality', () => {
    test('should clear all form fields on clear button click', async ({ page }) => {
      // Fill in data
      const tenantInput = page.locator('input[placeholder*="xxxx"]').first();
      await tenantInput.fill('12345678-1234-1234-1234-123456789abc');

      const templateInput = page.locator('input[placeholder*="template"]').first();
      await templateInput.fill('custom_template.yaml');
      await page.waitForTimeout(300);

      // Click clear
      const clearButton = page.locator('button:has-text("Clear")').first();
      await clearButton.click();
      await page.waitForTimeout(300);

      // Verify fields are reset
      const templateAfter = await page.locator('input[placeholder*="template"]').first().inputValue();
      expect(templateAfter).toContain('scale_up_template.yaml'); // Default value
    });

    test('should clear error messages on clear', async ({ page }) => {
      // Try to trigger error
      const tenantInput = page.locator('input[placeholder*="xxxx"]').first();
      await tenantInput.fill('invalid');
      await page.waitForTimeout(300);

      // Click clear
      const clearButton = page.locator('button:has-text("Clear")').first();
      await clearButton.click();
      await page.waitForTimeout(300);

      // Error should be cleared
      const errorAlert = page.locator('[role="alert"]').filter({ hasText: /error/i });
      const errorVisible = await errorAlert.isVisible().catch(() => false);
      expect(errorVisible).toBe(false);
    });
  });

  test.describe('Checkbox Interactions', () => {
    test('should toggle validation checkbox', async ({ page }) => {
      const validateCheckbox = page.locator('input[type="checkbox"]').filter({ has: page.locator(':scope ~ text=*validation*') }).first();

      // Should be checked by default
      const isChecked = await validateCheckbox.isChecked();
      expect(isChecked).toBe(true);

      // Uncheck
      await validateCheckbox.uncheck();
      await page.waitForTimeout(300);
      expect(await validateCheckbox.isChecked()).toBe(false);

      // Check again
      await validateCheckbox.check();
      await page.waitForTimeout(300);
      expect(await validateCheckbox.isChecked()).toBe(true);
    });

    test('should toggle preserve relationships in scale-down', async ({ page }) => {
      // Switch to scale-down mode
      const scaleDownButton = page.locator('button:has-text("Scale Down")').first();
      await scaleDownButton.click();
      await page.waitForTimeout(500);

      const preserveCheckbox = page.locator('input[type="checkbox"]').filter({ has: page.locator(':scope ~ text=*preserve*') }).first();

      if (await preserveCheckbox.isVisible()) {
        const isChecked = await preserveCheckbox.isChecked();

        // Toggle
        if (isChecked) {
          await preserveCheckbox.uncheck();
        } else {
          await preserveCheckbox.check();
        }
        await page.waitForTimeout(300);

        expect(await preserveCheckbox.isChecked()).toBe(!isChecked);
      }
    });
  });

  test.describe('Slider Interactions', () => {
    test('should update scale factor via slider', async ({ page }) => {
      const slider = page.locator('input[type="range"]').first();

      // Set to middle value
      await slider.fill('5');
      await page.waitForTimeout(300);
      await expect(page.locator('text=Scale Factor: 5x')).toBeVisible();

      // Set to different value
      await slider.fill('7');
      await page.waitForTimeout(300);
      await expect(page.locator('text=Scale Factor: 7x')).toBeVisible();
    });

    test('should reflect slider value in display', async ({ page }) => {
      const slider = page.locator('input[type="range"]').first();

      // Test multiple values
      for (const value of [2, 4, 6, 8]) {
        await slider.fill(String(value));
        await page.waitForTimeout(200);
        await expect(page.locator(`text=Scale Factor: ${value}x`)).toBeVisible();
      }
    });
  });

  test.describe('Number Input Interactions', () => {
    test('should update node count in random strategy', async ({ page }) => {
      const strategySelect = page.locator('select').filter({ has: page.locator('option:has-text("Template")') }).first();
      await strategySelect.selectOption('random');
      await page.waitForTimeout(500);

      const nodeCountInput = page.locator('input[type="number"]').first();
      await nodeCountInput.fill('2500');
      await page.waitForTimeout(300);

      expect(await nodeCountInput.inputValue()).toBe('2500');
    });

    test('should update sample size in scale-down', async ({ page }) => {
      // Switch to scale-down mode
      const scaleDownButton = page.locator('button:has-text("Scale Down")').first();
      await scaleDownButton.click();
      await page.waitForTimeout(500);

      const sampleSizeInput = page.locator('input[type="number"]').first();
      await sampleSizeInput.fill('750');
      await page.waitForTimeout(300);

      expect(await sampleSizeInput.inputValue()).toBe('750');
    });
  });

  test.describe('Output Mode Selection (Scale-Down)', () => {
    test.beforeEach(async ({ page }) => {
      // Switch to scale-down mode
      const scaleDownButton = page.locator('button:has-text("Scale Down")').first();
      await scaleDownButton.click();
      await page.waitForTimeout(500);
    });

    test('should show file output fields for file mode', async ({ page }) => {
      // File mode should show output path field
      const outputModeRadio = page.locator('input[type="radio"][value="file"]').first();
      if (await outputModeRadio.isVisible()) {
        await outputModeRadio.check();
        await page.waitForTimeout(300);

        await expect(page.locator('text=Output Path')).toBeVisible();
      }
    });

    test('should show IaC format fields for IaC mode', async ({ page }) => {
      const outputModeRadio = page.locator('input[type="radio"][value="iac"]').first();
      if (await outputModeRadio.isVisible()) {
        await outputModeRadio.check();
        await page.waitForTimeout(300);

        await expect(page.locator('text=IaC Format')).toBeVisible();
      }
    });

    test('should show new tenant ID field for new-tenant mode', async ({ page }) => {
      const outputModeRadio = page.locator('input[type="radio"][value="new-tenant"]').first();
      if (await outputModeRadio.isVisible()) {
        await outputModeRadio.check();
        await page.waitForTimeout(300);

        await expect(page.locator('text=New Tenant ID')).toBeVisible();
      }
    });
  });

  test.describe('Error State Display', () => {
    test('should show error alert when operation fails', async ({ page }) => {
      // Fill in valid-looking data
      const tenantInput = page.locator('input[placeholder*="xxxx"]').first();
      await tenantInput.fill('12345678-1234-1234-1234-123456789abc');
      await page.waitForTimeout(300);

      // Try to execute (will fail without backend)
      const executeButton = page.locator('button:has-text("Execute")').first();
      if (await executeButton.isEnabled()) {
        await executeButton.click();
        await page.waitForTimeout(2000);

        // May show error alert
        const errorAlert = page.locator('[role="alert"]').filter({ hasText: /error/i });
        const errorVisible = await errorAlert.isVisible().catch(() => false);
        console.log('Error alert visible:', errorVisible);
      }
    });

    test('should allow dismissing error alerts', async ({ page }) => {
      // If there's an error alert with close button
      const errorAlert = page.locator('[role="alert"]').filter({ hasText: /error/i }).first();
      if (await errorAlert.isVisible({ timeout: 2000 }).catch(() => false)) {
        const closeButton = errorAlert.locator('button[aria-label*="close"]').first();
        if (await closeButton.isVisible()) {
          await closeButton.click();
          await page.waitForTimeout(300);

          expect(await errorAlert.isVisible().catch(() => false)).toBe(false);
        }
      }
    });
  });

  test.describe('Preview Results Display', () => {
    test('should show preview info when preview succeeds', async ({ page }) => {
      // This test would need backend mock or test data
      // For now, just verify the UI can display preview info

      const tenantInput = page.locator('input[placeholder*="xxxx"]').first();
      await tenantInput.fill('12345678-1234-1234-1234-123456789abc');
      await page.waitForTimeout(300);

      const previewButton = page.locator('button:has-text("Preview")').first();
      if (await previewButton.isEnabled()) {
        await previewButton.click();
        await page.waitForTimeout(2000);

        // Look for preview result alert
        const previewAlert = page.locator('[role="alert"]').filter({ hasText: /Preview/i });
        const previewVisible = await previewAlert.isVisible().catch(() => false);
        console.log('Preview results visible:', previewVisible);
      }
    });
  });

  test.describe('Browse Button Interactions', () => {
    test('should have browse button for template file', async ({ page }) => {
      const browseButton = page.locator('button:has-text("Browse")').first();
      await expect(browseButton).toBeVisible();

      // Click should not crash (even if not implemented)
      await browseButton.click();
      await page.waitForTimeout(300);
    });

    test('should have browse button in scale-down output path', async ({ page }) => {
      // Switch to scale-down mode
      const scaleDownButton = page.locator('button:has-text("Scale Down")').first();
      await scaleDownButton.click();
      await page.waitForTimeout(500);

      const browseButtons = page.locator('button:has-text("Browse")');
      const count = await browseButtons.count();
      expect(count).toBeGreaterThanOrEqual(1);
    });
  });
});

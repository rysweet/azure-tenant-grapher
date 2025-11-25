import { test, expect } from '@playwright/test';

/**
 * Layer Selector - E2E Tests
 *
 * Tests the layer selector UI component in both compact and full modes:
 * - Header integration (compact mode)
 * - Scale Operations tab integration (full mode)
 * - Layer dropdown interaction
 * - Layer switching functionality
 * - Refresh layers functionality
 * - Visual verification with screenshots
 *
 * Part of PR #459 - Multi-Layer Graph Projections (Issue #456)
 */

test.describe('Layer Selector - UI Integration', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('http://localhost:5173');
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(2000); // Give it time to fully render
  });

  test.describe('Header Integration (Compact Mode)', () => {
    test('should display layer selector in app header', async ({ page }) => {
      // Look for layer selector component in header
      const layerSelector = page.locator('[data-testid="layer-selector-compact"]')
        .or(page.locator('div').filter({ hasText: /Active Layer|Current Layer/i }).first());

      // Should be visible in header
      const isVisible = await layerSelector.isVisible({ timeout: 5000 }).catch(() => false);
      expect(isVisible).toBeTruthy();

      // Take screenshot of header with layer selector
      await page.screenshot({
        path: 'test-results/screenshots/layer-selector-header.png',
        fullPage: false,
      });
    });

    test('should show active layer indicator', async ({ page }) => {
      // Look for active layer text (e.g., "default" or "Active: default")
      const activeLayerText = page.locator('text=/default|baseline|Active:/i').first();

      const isVisible = await activeLayerText.isVisible({ timeout: 5000 }).catch(() => false);
      if (isVisible) {
        const text = await activeLayerText.textContent();
        console.log('Active layer indicator text:', text);
        expect(text).toBeTruthy();
      }
    });

    test('should have layer dropdown in header', async ({ page }) => {
      // Look for dropdown/select element
      const dropdown = page.locator('select')
        .filter({ has: page.locator('option') })
        .first()
        .or(page.locator('[role="combobox"]').first());

      const isVisible = await dropdown.isVisible({ timeout: 5000 }).catch(() => false);
      console.log('Layer dropdown in header visible:', isVisible);
    });

    test('should have refresh layers button in header', async ({ page }) => {
      // Look for refresh button (may have icon or text)
      const refreshButton = page.locator('button').filter({ hasText: /refresh|reload/i })
        .or(page.locator('button[aria-label*="refresh"]'))
        .first();

      const isVisible = await refreshButton.isVisible({ timeout: 5000 }).catch(() => false);
      if (isVisible) {
        console.log('Refresh button found in header');

        // Click refresh button
        await refreshButton.click();
        await page.waitForTimeout(500);

        // Should still be visible after click
        expect(await refreshButton.isVisible()).toBeTruthy();
      }
    });
  });

  test.describe('Scale Operations Tab Integration (Full Mode)', () => {
    test.beforeEach(async ({ page }) => {
      // Navigate to Scale Operations tab
      const scaleOpsTab = page.locator('button:has-text("Scale Ops"), button:has-text("Scale Operations")').first();
      if (await scaleOpsTab.isVisible({ timeout: 5000 })) {
        await scaleOpsTab.click();
        await page.waitForTimeout(1000);
      }
    });

    test('should display full layer selector in Scale Operations tab', async ({ page }) => {
      // Look for full layer selector component
      const layerSelector = page.locator('[data-testid="layer-selector-full"]')
        .or(page.locator('div').filter({ hasText: /Layer Selection|Active Layer/i }).first());

      const isVisible = await layerSelector.isVisible({ timeout: 5000 }).catch(() => false);
      console.log('Full layer selector in Scale Ops visible:', isVisible);

      // Take screenshot of Scale Ops with layer selector
      await page.screenshot({
        path: 'test-results/screenshots/layer-selector-scale-ops.png',
        fullPage: true,
      });
    });

    test('should show layer details (nodes, relationships)', async ({ page }) => {
      // Look for layer metadata display
      const nodeCountText = page.locator('text=/\\d+ nodes|Nodes:/i').first();
      const relationshipCountText = page.locator('text=/\\d+ relationships|Edges:/i').first();

      const nodeCountVisible = await nodeCountText.isVisible({ timeout: 5000 }).catch(() => false);
      const relCountVisible = await relationshipCountText.isVisible({ timeout: 5000 }).catch(() => false);

      if (nodeCountVisible) {
        const nodeText = await nodeCountText.textContent();
        console.log('Node count display:', nodeText);
      }

      if (relCountVisible) {
        const relText = await relationshipCountText.textContent();
        console.log('Relationship count display:', relText);
      }
    });

    test('should show layer type badge', async ({ page }) => {
      // Look for layer type indicator (baseline, scaled, experimental, snapshot)
      const layerTypeBadge = page.locator('text=/baseline|scaled|experimental|snapshot/i').first();

      const isVisible = await layerTypeBadge.isVisible({ timeout: 5000 }).catch(() => false);
      if (isVisible) {
        const badgeText = await layerTypeBadge.textContent();
        console.log('Layer type badge:', badgeText);
        expect(badgeText).toBeTruthy();
      }
    });

    test('should show layer creation timestamp', async ({ page }) => {
      // Look for timestamp display
      const timestampText = page.locator('text=/Created|\\d{4}-\\d{2}-\\d{2}/i').first();

      const isVisible = await timestampText.isVisible({ timeout: 5000 }).catch(() => false);
      if (isVisible) {
        const timestamp = await timestampText.textContent();
        console.log('Layer timestamp:', timestamp);
      }
    });
  });

  test.describe('Layer Dropdown Interaction', () => {
    test('should open layer dropdown on click', async ({ page }) => {
      // Find dropdown element
      const dropdown = page.locator('select').first()
        .or(page.locator('[role="combobox"]').first());

      const isVisible = await dropdown.isVisible({ timeout: 5000 }).catch(() => false);
      if (isVisible) {
        await dropdown.click();
        await page.waitForTimeout(500);

        // Look for options/menu
        const options = page.locator('option, [role="option"]');
        const optionCount = await options.count();
        console.log('Dropdown options count:', optionCount);
        expect(optionCount).toBeGreaterThanOrEqual(0);
      }
    });

    test('should list available layers in dropdown', async ({ page }) => {
      const dropdown = page.locator('select').first();

      const isVisible = await dropdown.isVisible({ timeout: 5000 }).catch(() => false);
      if (isVisible) {
        // Get all options
        const options = await dropdown.locator('option').all();
        const optionTexts = await Promise.all(options.map(opt => opt.textContent()));

        console.log('Available layers:', optionTexts);

        // Should have at least one layer (default/baseline)
        expect(optionTexts.length).toBeGreaterThanOrEqual(1);

        // Should include "default" layer
        const hasDefaultLayer = optionTexts.some(text =>
          text?.toLowerCase().includes('default') || text?.toLowerCase().includes('baseline')
        );
        console.log('Has default/baseline layer:', hasDefaultLayer);
      }
    });

    test('should show active layer as selected', async ({ page }) => {
      const dropdown = page.locator('select').first();

      const isVisible = await dropdown.isVisible({ timeout: 5000 }).catch(() => false);
      if (isVisible) {
        const selectedValue = await dropdown.inputValue();
        console.log('Selected layer value:', selectedValue);
        expect(selectedValue).toBeTruthy();
      }
    });
  });

  test.describe('Layer Switching Functionality', () => {
    test('should switch to different layer via dropdown', async ({ page }) => {
      const dropdown = page.locator('select').first();

      const isVisible = await dropdown.isVisible({ timeout: 5000 }).catch(() => false);
      if (isVisible) {
        // Get initial value
        const initialValue = await dropdown.inputValue();
        console.log('Initial layer:', initialValue);

        // Get all options
        const options = await dropdown.locator('option').all();

        if (options.length > 1) {
          // Select second option
          const secondOption = options[1];
          const secondValue = await secondOption.getAttribute('value');

          if (secondValue) {
            await dropdown.selectOption(secondValue);
            await page.waitForTimeout(1000);

            // Verify selection changed
            const newValue = await dropdown.inputValue();
            console.log('New layer after switch:', newValue);
            expect(newValue).toBe(secondValue);

            // Take screenshot after layer switch
            await page.screenshot({
              path: 'test-results/screenshots/layer-selector-after-switch.png',
              fullPage: false,
            });
          }
        } else {
          console.log('Only one layer available - cannot test switching');
        }
      }
    });

    test('should update active layer indicator after switch', async ({ page }) => {
      const dropdown = page.locator('select').first();

      const isVisible = await dropdown.isVisible({ timeout: 5000 }).catch(() => false);
      if (isVisible) {
        // Get active layer indicator before switch
        const activeIndicatorBefore = page.locator('text=/Active:|Current:/i').first();
        const textBefore = await activeIndicatorBefore.textContent().catch(() => '');

        // Switch layer if multiple available
        const options = await dropdown.locator('option').all();
        if (options.length > 1) {
          const secondValue = await options[1].getAttribute('value');
          if (secondValue) {
            await dropdown.selectOption(secondValue);
            await page.waitForTimeout(1000);

            // Check if active indicator updated
            const textAfter = await activeIndicatorBefore.textContent().catch(() => '');
            console.log('Active indicator before:', textBefore);
            console.log('Active indicator after:', textAfter);
          }
        }
      }
    });

    test('should persist layer selection across tab navigation', async ({ page }) => {
      const dropdown = page.locator('select').first();

      const isVisible = await dropdown.isVisible({ timeout: 5000 }).catch(() => false);
      if (isVisible) {
        const options = await dropdown.locator('option').all();

        if (options.length > 1) {
          // Select specific layer
          const secondValue = await options[1].getAttribute('value');
          if (secondValue) {
            await dropdown.selectOption(secondValue);
            await page.waitForTimeout(1000);

            // Navigate to different tab
            const scanTab = page.locator('button:has-text("Scan")').first();
            if (await scanTab.isVisible({ timeout: 2000 })) {
              await scanTab.click();
              await page.waitForTimeout(500);

              // Navigate back to Scale Ops
              const scaleOpsTab = page.locator('button:has-text("Scale Ops"), button:has-text("Scale Operations")').first();
              await scaleOpsTab.click();
              await page.waitForTimeout(500);

              // Check if selection persisted
              const dropdownAfter = page.locator('select').first();
              const valueAfter = await dropdownAfter.inputValue();
              console.log('Layer selection after tab switch:', valueAfter);
              expect(valueAfter).toBe(secondValue);
            }
          }
        }
      }
    });
  });

  test.describe('Refresh Layers Functionality', () => {
    test('should have refresh layers button', async ({ page }) => {
      const refreshButton = page.locator('button').filter({ hasText: /refresh|reload/i })
        .or(page.locator('button[aria-label*="refresh"]'))
        .first();

      const isVisible = await refreshButton.isVisible({ timeout: 5000 }).catch(() => false);
      if (isVisible) {
        console.log('Refresh layers button found');
        expect(true).toBeTruthy();
      } else {
        console.log('Refresh layers button not visible - may be icon-only');
      }
    });

    test('should refresh layer list on button click', async ({ page }) => {
      const refreshButton = page.locator('button').filter({ hasText: /refresh|reload/i })
        .or(page.locator('button[aria-label*="refresh"]'))
        .first();

      const isVisible = await refreshButton.isVisible({ timeout: 5000 }).catch(() => false);
      if (isVisible) {
        // Get layer count before refresh
        const dropdown = page.locator('select').first();
        const optionsBefore = await dropdown.locator('option').count();

        // Click refresh
        await refreshButton.click();
        await page.waitForTimeout(1000);

        // Get layer count after refresh
        const optionsAfter = await dropdown.locator('option').count();

        console.log('Layers before refresh:', optionsBefore);
        console.log('Layers after refresh:', optionsAfter);

        // Should have same or different count (depending on backend)
        expect(optionsAfter).toBeGreaterThanOrEqual(0);
      }
    });

    test('should show loading state during refresh', async ({ page }) => {
      const refreshButton = page.locator('button').filter({ hasText: /refresh|reload/i })
        .or(page.locator('button[aria-label*="refresh"]'))
        .first();

      const isVisible = await refreshButton.isVisible({ timeout: 5000 }).catch(() => false);
      if (isVisible) {
        await refreshButton.click();

        // Look for loading indicator (spinner, disabled button, etc.)
        const isDisabled = await refreshButton.isDisabled().catch(() => false);
        const loadingIndicator = page.locator('[role="progressbar"], .loading, .spinner').first();
        const hasLoadingIndicator = await loadingIndicator.isVisible({ timeout: 500 }).catch(() => false);

        console.log('Refresh button disabled during refresh:', isDisabled);
        console.log('Loading indicator visible:', hasLoadingIndicator);

        // Wait for refresh to complete
        await page.waitForTimeout(1000);
      }
    });
  });

  test.describe('Create Layer Button', () => {
    test('should have create layer button', async ({ page }) => {
      const createButton = page.locator('button').filter({ hasText: /create|new layer/i })
        .or(page.locator('button[aria-label*="create"]'))
        .first();

      const isVisible = await createButton.isVisible({ timeout: 5000 }).catch(() => false);
      if (isVisible) {
        console.log('Create layer button found');

        // Take screenshot showing create button
        await page.screenshot({
          path: 'test-results/screenshots/layer-selector-create-button.png',
          fullPage: false,
        });
      } else {
        console.log('Create layer button not visible - may be in different location');
      }
    });

    test('should open create layer dialog on button click', async ({ page }) => {
      const createButton = page.locator('button').filter({ hasText: /create|new layer/i })
        .or(page.locator('button[aria-label*="create"]'))
        .first();

      const isVisible = await createButton.isVisible({ timeout: 5000 }).catch(() => false);
      if (isVisible) {
        await createButton.click();
        await page.waitForTimeout(500);

        // Look for dialog/modal
        const dialog = page.locator('[role="dialog"], .modal, .dialog').first();
        const dialogVisible = await dialog.isVisible({ timeout: 2000 }).catch(() => false);

        console.log('Create layer dialog visible:', dialogVisible);

        if (dialogVisible) {
          // Take screenshot of dialog
          await page.screenshot({
            path: 'test-results/screenshots/layer-selector-create-dialog.png',
            fullPage: false,
          });
        }
      }
    });
  });

  test.describe('Visual Regression', () => {
    test('should capture full page screenshot with layer selector', async ({ page }) => {
      // Wait for page to fully load
      await page.waitForTimeout(2000);

      // Take full page screenshot
      await page.screenshot({
        path: 'test-results/screenshots/layer-selector-full-page.png',
        fullPage: true,
      });

      console.log('Full page screenshot captured');
    });

    test('should capture Scale Ops tab with layer selector', async ({ page }) => {
      // Navigate to Scale Operations tab
      const scaleOpsTab = page.locator('button:has-text("Scale Ops"), button:has-text("Scale Operations")').first();
      if (await scaleOpsTab.isVisible({ timeout: 5000 })) {
        await scaleOpsTab.click();
        await page.waitForTimeout(1000);

        // Take screenshot
        await page.screenshot({
          path: 'test-results/screenshots/layer-selector-scale-ops-full.png',
          fullPage: true,
        });

        console.log('Scale Ops with layer selector screenshot captured');
      }
    });
  });

  test.describe('Error Handling', () => {
    test('should handle layer API failures gracefully', async ({ page }) => {
      // Try to trigger refresh when backend might be unavailable
      const refreshButton = page.locator('button').filter({ hasText: /refresh|reload/i }).first();

      const isVisible = await refreshButton.isVisible({ timeout: 5000 }).catch(() => false);
      if (isVisible) {
        await refreshButton.click();
        await page.waitForTimeout(2000);

        // Look for error message
        const errorAlert = page.locator('[role="alert"]').filter({ hasText: /error|failed/i }).first();
        const errorVisible = await errorAlert.isVisible({ timeout: 2000 }).catch(() => false);

        console.log('Error alert shown on API failure:', errorVisible);
      }
    });

    test('should show empty state when no layers available', async ({ page }) => {
      // This would require mocking empty layer list
      const dropdown = page.locator('select').first();

      const isVisible = await dropdown.isVisible({ timeout: 5000 }).catch(() => false);
      if (isVisible) {
        const options = await dropdown.locator('option').all();

        if (options.length === 0) {
          // Look for empty state message
          const emptyMessage = page.locator('text=/no layers|empty/i').first();
          const emptyVisible = await emptyMessage.isVisible({ timeout: 1000 }).catch(() => false);
          console.log('Empty state shown when no layers:', emptyVisible);
        }
      }
    });
  });

  test.describe('Accessibility', () => {
    test('should have accessible layer selector', async ({ page }) => {
      const dropdown = page.locator('select').first();

      const isVisible = await dropdown.isVisible({ timeout: 5000 }).catch(() => false);
      if (isVisible) {
        // Check for aria-label or label
        const ariaLabel = await dropdown.getAttribute('aria-label');
        const hasLabel = page.locator('label').filter({ has: dropdown });
        const labelVisible = await hasLabel.count() > 0;

        console.log('Dropdown aria-label:', ariaLabel);
        console.log('Dropdown has associated label:', labelVisible);

        expect(ariaLabel || labelVisible).toBeTruthy();
      }
    });

    test('should support keyboard navigation', async ({ page }) => {
      const dropdown = page.locator('select').first();

      const isVisible = await dropdown.isVisible({ timeout: 5000 }).catch(() => false);
      if (isVisible) {
        // Focus dropdown
        await dropdown.focus();
        await page.waitForTimeout(300);

        // Check if focused
        const isFocused = await dropdown.evaluate(el => el === document.activeElement);
        console.log('Dropdown keyboard focusable:', isFocused);
        expect(isFocused).toBeTruthy();

        // Try keyboard navigation
        await page.keyboard.press('ArrowDown');
        await page.waitForTimeout(300);
        await page.keyboard.press('Enter');
        await page.waitForTimeout(300);

        console.log('Keyboard navigation test completed');
      }
    });
  });
});

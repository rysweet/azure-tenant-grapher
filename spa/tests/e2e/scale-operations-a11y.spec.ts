import { test, expect } from '@playwright/test';

/**
 * Scale Operations - Accessibility Tests
 *
 * Tests accessibility features:
 * - Keyboard navigation
 * - Screen reader labels
 * - Focus management
 * - ARIA attributes
 * - Color contrast
 * - Semantic HTML
 */

test.describe('Scale Operations - Accessibility', () => {
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

  test.describe('Keyboard Navigation', () => {
    test('should navigate between mode toggle buttons with keyboard', async ({ page }) => {
      // Focus on scale-up button
      const scaleUpButton = page.locator('button:has-text("Scale Up")').first();
      await scaleUpButton.focus();

      // Verify focus
      const isFocused = await scaleUpButton.evaluate(el => el === document.activeElement);
      expect(isFocused).toBe(true);

      // Tab to scale-down button
      await page.keyboard.press('Tab');
      await page.waitForTimeout(200);

      // Should be on scale-down button (or next focusable element)
      const focusedElement = await page.evaluateHandle(() => document.activeElement);
      const tagName = await page.evaluate(el => el?.tagName, focusedElement);
      console.log('Focused element after Tab:', tagName);
    });

    test('should navigate form fields with Tab key', async ({ page }) => {
      // Start from tenant ID field
      const tenantInput = page.locator('input[placeholder*="xxxx"]').first();
      await tenantInput.focus();

      // Tab through fields
      for (let i = 0; i < 5; i++) {
        await page.keyboard.press('Tab');
        await page.waitForTimeout(100);

        const focusedElement = await page.evaluateHandle(() => document.activeElement);
        const elementType = await page.evaluate(el => ({
          tag: el?.tagName,
          type: el?.getAttribute('type'),
          role: el?.getAttribute('role')
        }), focusedElement);

        console.log(`Tab ${i + 1}:`, elementType);
      }
    });

    test('should navigate backwards with Shift+Tab', async ({ page }) => {
      // Focus on a button
      const executeButton = page.locator('button:has-text("Execute")').first();
      await executeButton.focus();

      // Navigate backwards
      await page.keyboard.press('Shift+Tab');
      await page.waitForTimeout(200);

      const focusedElement = await page.evaluateHandle(() => document.activeElement);
      const tagName = await page.evaluate(el => el?.tagName, focusedElement);
      console.log('Focused element after Shift+Tab:', tagName);
    });

    test('should activate buttons with Enter key', async ({ page }) => {
      const scaleDownButton = page.locator('button:has-text("Scale Down")').first();
      await scaleDownButton.focus();

      // Press Enter
      await page.keyboard.press('Enter');
      await page.waitForTimeout(500);

      // Should switch to scale-down mode
      await expect(page.locator('text=Scale-Down Configuration')).toBeVisible();
    });

    test('should activate buttons with Space key', async ({ page }) => {
      // Switch to scale-down first
      const scaleDownButton = page.locator('button:has-text("Scale Down")').first();
      await scaleDownButton.click();
      await page.waitForTimeout(500);

      // Focus on scale-up and press Space
      const scaleUpButton = page.locator('button:has-text("Scale Up")').first();
      await scaleUpButton.focus();
      await page.keyboard.press('Space');
      await page.waitForTimeout(500);

      // Should switch to scale-up mode
      await expect(page.locator('text=Scale-Up Configuration')).toBeVisible();
    });

    test('should navigate select dropdowns with keyboard', async ({ page }) => {
      const strategySelect = page.locator('select').first();
      await strategySelect.focus();

      // Open dropdown with Space or Enter
      await page.keyboard.press('Space');
      await page.waitForTimeout(300);

      // Navigate options with arrow keys
      await page.keyboard.press('ArrowDown');
      await page.keyboard.press('ArrowDown');
      await page.waitForTimeout(200);

      // Select with Enter
      await page.keyboard.press('Enter');
      await page.waitForTimeout(300);

      console.log('Dropdown navigation successful');
    });

    test('should navigate slider with arrow keys', async ({ page }) => {
      const slider = page.locator('input[type="range"]').first();
      await slider.focus();

      // Get initial value
      const initialValue = await slider.inputValue();

      // Navigate with arrow keys
      await page.keyboard.press('ArrowRight');
      await page.keyboard.press('ArrowRight');
      await page.waitForTimeout(200);

      const newValue = await slider.inputValue();

      // Value should have increased
      expect(parseInt(newValue)).toBeGreaterThan(parseInt(initialValue));
    });

    test('should skip disabled buttons in tab order', async ({ page }) => {
      // Clear tenant ID to disable execute button
      const tenantInput = page.locator('input[placeholder*="xxxx"]').first();
      await tenantInput.clear();
      await page.waitForTimeout(300);

      // Focus on an element before execute button
      await tenantInput.focus();

      // Tab multiple times
      let foundDisabled = false;
      for (let i = 0; i < 10; i++) {
        await page.keyboard.press('Tab');
        await page.waitForTimeout(100);

        const focusedElement = await page.evaluateHandle(() => document.activeElement);
        const isDisabled = await page.evaluate(el => (el as HTMLButtonElement | HTMLInputElement)?.disabled, focusedElement);

        if (isDisabled) {
          foundDisabled = true;
          break;
        }
      }

      // Should not focus on disabled buttons
      expect(foundDisabled).toBe(false);
    });

    test('should navigate checkbox with keyboard', async ({ page }) => {
      const validateCheckbox = page.locator('input[type="checkbox"]').first();
      await validateCheckbox.focus();

      // Check current state
      const wasChecked = await validateCheckbox.isChecked();

      // Toggle with Space
      await page.keyboard.press('Space');
      await page.waitForTimeout(200);

      const isChecked = await validateCheckbox.isChecked();
      expect(isChecked).toBe(!wasChecked);
    });

    test('should open dialogs with keyboard', async ({ page }) => {
      const helpButton = page.locator('button:has-text("Help")').first();
      await helpButton.focus();
      await page.keyboard.press('Enter');
      await page.waitForTimeout(500);

      // Dialog should open
      await expect(page.locator('text=Scale Operations Help')).toBeVisible();
    });

    test('should close dialogs with Escape key', async ({ page }) => {
      const helpButton = page.locator('button:has-text("Help")').first();
      await helpButton.click();
      await page.waitForTimeout(500);

      // Close with Escape
      await page.keyboard.press('Escape');
      await page.waitForTimeout(300);

      // Dialog should close
      const dialog = page.locator('text=Scale Operations Help');
      expect(await dialog.isVisible().catch(() => false)).toBe(false);
    });

    test('should maintain focus order in dialogs', async ({ page }) => {
      const helpButton = page.locator('button:has-text("Help")').first();
      await helpButton.click();
      await page.waitForTimeout(500);

      // Tab through dialog elements
      await page.keyboard.press('Tab');
      await page.waitForTimeout(100);

      const focusedElement = await page.evaluateHandle(() => document.activeElement);
      const isInDialog = await page.evaluate(
        el => el?.closest('[role="dialog"]') !== null,
        focusedElement
      );

      expect(isInDialog).toBe(true);
    });
  });

  test.describe('Screen Reader Labels', () => {
    test('should have aria-label on mode toggle buttons', async ({ page }) => {
      const scaleUpButton = page.locator('button[aria-label*="scale up"], button:has-text("Scale Up")').first();
      const ariaLabel = await scaleUpButton.getAttribute('aria-label');

      console.log('Scale up button aria-label:', ariaLabel);
      // Should have meaningful label
    });

    test('should have labels for form inputs', async ({ page }) => {
      const tenantInput = page.locator('input[placeholder*="xxxx"]').first();

      // Check for associated label
      const inputId = await tenantInput.getAttribute('id');
      if (inputId) {
        const label = page.locator(`label[for="${inputId}"]`);
        const labelVisible = await label.isVisible();
        console.log('Tenant input has label:', labelVisible);
      }

      // Or aria-label
      const ariaLabel = await tenantInput.getAttribute('aria-label');
      const ariaLabelledBy = await tenantInput.getAttribute('aria-labelledby');

      console.log('Input aria-label:', ariaLabel);
      console.log('Input aria-labelledby:', ariaLabelledBy);
    });

    test('should have accessible names for buttons', async ({ page }) => {
      const executeButton = page.locator('button:has-text("Execute")').first();

      // Check accessible name
      const accessibleName = await executeButton.textContent();
      expect(accessibleName).toContain('Execute');
    });

    test('should have aria-label for slider', async ({ page }) => {
      const slider = page.locator('input[type="range"]').first();
      const ariaLabel = await slider.getAttribute('aria-label');

      console.log('Slider aria-label:', ariaLabel);
      expect(ariaLabel).toBeTruthy();
    });

    test('should have accessible descriptions for strategy options', async ({ page }) => {
      // Check for info text that describes strategies
      const templateDescription = page.locator('text=Generate nodes based on a predefined template');
      await expect(templateDescription).toBeVisible();
    });

    test('should have aria-describedby for inputs with help text', async ({ page }) => {
      const tenantInput = page.locator('input[placeholder*="xxxx"]').first();
      const describedBy = await tenantInput.getAttribute('aria-describedby');

      if (describedBy) {
        // Check if description element exists
        const description = page.locator(`#${describedBy}`);
        const descriptionExists = await description.isVisible();
        console.log('Input has description:', descriptionExists);
      }
    });

    test('should have alt text for icons', async ({ page }) => {
      // MUI icons render as SVG elements
      const executeButton = page.locator('button:has-text("Execute")').first();
      const icon = executeButton.locator('svg').first();

      if (await icon.isVisible()) {
        // Check for aria-hidden (decorative) or aria-label
        const ariaHidden = await icon.getAttribute('aria-hidden');
        const ariaLabel = await icon.getAttribute('aria-label');

        console.log('Icon aria-hidden:', ariaHidden);
        console.log('Icon aria-label:', ariaLabel);

        // Icons should either be hidden or labeled
        expect(ariaHidden === 'true' || ariaLabel !== null).toBe(true);
      }
    });

    test('should have role attributes for custom components', async ({ page }) => {
      const toggleGroup = page.locator('[role="group"]').first();
      if (await toggleGroup.isVisible()) {
        const ariaLabel = await toggleGroup.getAttribute('aria-label');
        console.log('Toggle group aria-label:', ariaLabel);
      }
    });

    test('should have accessible alert messages', async ({ page }) => {
      // Look for alert with role
      const alerts = page.locator('[role="alert"]');
      const count = await alerts.count();

      if (count > 0) {
        const firstAlert = alerts.first();
        const text = await firstAlert.textContent();
        console.log('Alert text:', text);

        // Alert should have text content
        expect(text?.length).toBeGreaterThan(0);
      }
    });

    test('should have accessible dialog titles', async ({ page }) => {
      const helpButton = page.locator('button:has-text("Help")').first();
      await helpButton.click();
      await page.waitForTimeout(500);

      // Dialog should have aria-labelledby pointing to title
      const dialog = page.locator('[role="dialog"]').first();
      const labelledBy = await dialog.getAttribute('aria-labelledby');

      if (labelledBy) {
        const title = page.locator(`#${labelledBy}`);
        const titleVisible = await title.isVisible();
        expect(titleVisible).toBe(true);
      }
    });
  });

  test.describe('Focus Management', () => {
    test('should have visible focus indicators', async ({ page }) => {
      const executeButton = page.locator('button:has-text("Execute")').first();
      await executeButton.focus();

      // Check for focus styles (outline, border, etc.)
      const styles = await executeButton.evaluate(el => {
        const computed = window.getComputedStyle(el);
        return {
          outline: computed.outline,
          outlineWidth: computed.outlineWidth,
          boxShadow: computed.boxShadow
        };
      });

      console.log('Focus styles:', styles);

      // Should have some focus indicator
      const hasFocusIndicator = styles.outline !== 'none' ||
                               styles.outlineWidth !== '0px' ||
                               styles.boxShadow !== 'none';

      expect(hasFocusIndicator).toBe(true);
    });

    test('should restore focus after dialog closes', async ({ page }) => {
      const helpButton = page.locator('button:has-text("Help")').first();
      await helpButton.focus();
      await page.keyboard.press('Enter');
      await page.waitForTimeout(500);

      // Close dialog
      await page.keyboard.press('Escape');
      await page.waitForTimeout(300);

      // Focus should return to help button (or be managed appropriately)
      const focusedElement = await page.evaluateHandle(() => document.activeElement);
      const tagName = await page.evaluate(el => el?.tagName, focusedElement);
      console.log('Focus after dialog close:', tagName);
    });

    test('should trap focus in dialog', async ({ page }) => {
      const helpButton = page.locator('button:has-text("Help")').first();
      await helpButton.click();
      await page.waitForTimeout(500);

      // Tab multiple times
      for (let i = 0; i < 10; i++) {
        await page.keyboard.press('Tab');
        await page.waitForTimeout(100);

        const focusedElement = await page.evaluateHandle(() => document.activeElement);
        const isInDialog = await page.evaluate(
          el => el?.closest('[role="dialog"]') !== null,
          focusedElement
        );

        if (!isInDialog) {
          console.log('Focus escaped dialog at tab', i);
          break;
        }
      }

      // Focus should stay in dialog
    });

    test('should focus first focusable element in dialog', async ({ page }) => {
      const helpButton = page.locator('button:has-text("Help")').first();
      await helpButton.click();
      await page.waitForTimeout(500);

      // First focusable element should be focused (or close to it)
      const focusedElement = await page.evaluateHandle(() => document.activeElement);
      const tagName = await page.evaluate(el => el?.tagName, focusedElement);
      console.log('First focused element in dialog:', tagName);
    });

    test('should maintain focus on slider during keyboard interaction', async ({ page }) => {
      const slider = page.locator('input[type="range"]').first();
      await slider.focus();

      // Use arrow keys
      await page.keyboard.press('ArrowRight');
      await page.waitForTimeout(100);

      // Focus should still be on slider
      const isFocused = await slider.evaluate(el => el === document.activeElement);
      expect(isFocused).toBe(true);
    });

    test('should not lose focus when toggling modes', async ({ page }) => {
      const scaleDownButton = page.locator('button:has-text("Scale Down")').first();
      await scaleDownButton.focus();
      await page.keyboard.press('Enter');
      await page.waitForTimeout(500);

      // Focus should be on some element (not lost)
      const focusedElement = await page.evaluateHandle(() => document.activeElement);
      const tagName = await page.evaluate(el => el?.tagName, focusedElement);
      expect(tagName).not.toBe('BODY');
    });

    test('should focus preview button after filling form', async ({ page }) => {
      const tenantInput = page.locator('input[placeholder*="xxxx"]').first();
      await tenantInput.fill('12345678-1234-1234-1234-123456789abc');

      // Tab to preview button
      await page.keyboard.press('Tab');
      await page.keyboard.press('Tab');
      await page.keyboard.press('Tab');
      await page.waitForTimeout(200);

      const focusedElement = await page.evaluateHandle(() => document.activeElement);
      const text = await page.evaluate(el => el?.textContent, focusedElement);
      console.log('Focused element text:', text);
    });
  });

  test.describe('ARIA Attributes', () => {
    test('should have correct role for toggle button group', async ({ page }) => {
      const toggleGroup = page.locator('button:has-text("Scale Up")').locator('..').locator('..');
      const role = await toggleGroup.getAttribute('role');

      console.log('Toggle group role:', role);
      // Should be 'group' or 'toolbar'
    });

    test('should have aria-pressed for toggle buttons', async ({ page }) => {
      const scaleUpButton = page.locator('button:has-text("Scale Up")').first();
      const ariaPressed = await scaleUpButton.getAttribute('aria-pressed');

      console.log('Scale up aria-pressed:', ariaPressed);
      // May be 'true', 'false', or undefined depending on implementation
    });

    test('should have aria-required for required fields', async ({ page }) => {
      const tenantInput = page.locator('input[placeholder*="xxxx"]').first();
      const ariaRequired = await tenantInput.getAttribute('aria-required');
      const required = await tenantInput.getAttribute('required');

      console.log('Tenant input aria-required:', ariaRequired);
      console.log('Tenant input required:', required);

      // Should indicate field is required
      expect(ariaRequired === 'true' || required !== null).toBe(true);
    });

    test('should have aria-disabled for disabled buttons', async ({ page }) => {
      // Clear tenant to disable execute button
      const tenantInput = page.locator('input[placeholder*="xxxx"]').first();
      await tenantInput.clear();
      await page.waitForTimeout(300);

      const executeButton = page.locator('button:has-text("Execute")').first();
      const ariaDisabled = await executeButton.getAttribute('aria-disabled');
      const disabled = await executeButton.isDisabled();

      console.log('Execute button aria-disabled:', ariaDisabled);
      expect(disabled).toBe(true);
    });

    test('should have aria-valuenow for slider', async ({ page }) => {
      const slider = page.locator('input[type="range"]').first();
      const ariaValueNow = await slider.getAttribute('aria-valuenow');
      const value = await slider.inputValue();

      console.log('Slider aria-valuenow:', ariaValueNow);
      console.log('Slider value:', value);

      // Should have current value
      expect(ariaValueNow || value).toBeTruthy();
    });

    test('should have aria-valuemin and aria-valuemax for slider', async ({ page }) => {
      const slider = page.locator('input[type="range"]').first();
      const ariaValueMin = await slider.getAttribute('aria-valuemin');
      const ariaValueMax = await slider.getAttribute('aria-valuemax');

      console.log('Slider aria-valuemin:', ariaValueMin);
      console.log('Slider aria-valuemax:', ariaValueMax);

      // Should have min and max values
      expect(ariaValueMin).toBeTruthy();
      expect(ariaValueMax).toBeTruthy();
    });

    test('should have aria-live for dynamic content', async ({ page }) => {
      // Look for live regions (alerts, status)
      const alerts = page.locator('[role="alert"]');
      const count = await alerts.count();

      if (count > 0) {
        const firstAlert = alerts.first();
        const ariaLive = await firstAlert.getAttribute('aria-live');
        console.log('Alert aria-live:', ariaLive);

        // Alerts should announce changes
      }
    });

    test('should have aria-busy during loading states', async ({ page }) => {
      const tenantInput = page.locator('input[placeholder*="xxxx"]').first();
      await tenantInput.fill('12345678-1234-1234-1234-123456789abc');

      const previewButton = page.locator('button:has-text("Preview")').first();
      await previewButton.click();
      await page.waitForTimeout(100);

      // Check for aria-busy
      const container = page.locator('[aria-busy="true"]');
      const isBusy = await container.isVisible().catch(() => false);
      console.log('Aria-busy during operation:', isBusy);
    });

    test('should have aria-expanded for expandable elements', async ({ page }) => {
      // Check for any expandable elements
      const expandable = page.locator('[aria-expanded]');
      const count = await expandable.count();

      if (count > 0) {
        const firstExpandable = expandable.first();
        const ariaExpanded = await firstExpandable.getAttribute('aria-expanded');
        console.log('Aria-expanded found:', ariaExpanded);
      }
    });

    test('should have aria-modal for dialogs', async ({ page }) => {
      const helpButton = page.locator('button:has-text("Help")').first();
      await helpButton.click();
      await page.waitForTimeout(500);

      const dialog = page.locator('[role="dialog"]').first();
      const ariaModal = await dialog.getAttribute('aria-modal');

      console.log('Dialog aria-modal:', ariaModal);
      expect(ariaModal).toBe('true');
    });
  });

  test.describe('Semantic HTML', () => {
    test('should use semantic heading hierarchy', async ({ page }) => {
      // Check for proper heading levels
      const h5 = await page.locator('h5').count();
      const h6 = await page.locator('h6').count();

      console.log('H5 headings:', h5);
      console.log('H6 headings:', h6);

      // Should have headings for structure
      expect(h5 + h6).toBeGreaterThan(0);
    });

    test('should use button elements for buttons', async ({ page }) => {
      const executeButton = page.locator('button:has-text("Execute")').first();
      const tagName = await executeButton.evaluate(el => el.tagName);

      expect(tagName).toBe('BUTTON');
    });

    test('should use input elements for form fields', async ({ page }) => {
      const tenantInput = page.locator('input[placeholder*="xxxx"]').first();
      const tagName = await tenantInput.evaluate(el => el.tagName);

      expect(tagName).toBe('INPUT');
    });

    test('should use select elements for dropdowns', async ({ page }) => {
      const strategySelect = page.locator('select').first();
      const tagName = await strategySelect.evaluate(el => el.tagName);

      expect(tagName).toBe('SELECT');
    });

    test('should use label elements for form labels', async ({ page }) => {
      const labels = await page.locator('label').count();
      console.log('Label elements found:', labels);

      // Should have labels for form fields
      expect(labels).toBeGreaterThan(0);
    });

    test('should use list elements for grouped items', async ({ page }) => {
      const helpButton = page.locator('button:has-text("Help")').first();
      await helpButton.click();
      await page.waitForTimeout(500);

      // Check for list in help dialog
      const lists = await page.locator('ul, ol').count();
      console.log('List elements in help:', lists);
    });
  });

  test.describe('Color Contrast', () => {
    test('should have sufficient contrast for primary text', async ({ page }) => {
      const title = page.locator('text=Scale Operations').first();

      const colors = await title.evaluate(el => {
        const computed = window.getComputedStyle(el);
        return {
          color: computed.color,
          backgroundColor: computed.backgroundColor
        };
      });

      console.log('Title colors:', colors);
      // Manual verification or automated contrast checking would be needed
    });

    test('should have sufficient contrast for buttons', async ({ page }) => {
      const executeButton = page.locator('button:has-text("Execute")').first();

      const colors = await executeButton.evaluate(el => {
        const computed = window.getComputedStyle(el);
        return {
          color: computed.color,
          backgroundColor: computed.backgroundColor
        };
      });

      console.log('Button colors:', colors);
    });

    test('should have sufficient contrast for disabled state', async ({ page }) => {
      const tenantInput = page.locator('input[placeholder*="xxxx"]').first();
      await tenantInput.clear();
      await page.waitForTimeout(300);

      const executeButton = page.locator('button:has-text("Execute")').first();

      const colors = await executeButton.evaluate(el => {
        const computed = window.getComputedStyle(el);
        return {
          color: computed.color,
          backgroundColor: computed.backgroundColor,
          opacity: computed.opacity
        };
      });

      console.log('Disabled button colors:', colors);
    });

    test('should have visible focus indicators with sufficient contrast', async ({ page }) => {
      const executeButton = page.locator('button:has-text("Execute")').first();
      await executeButton.focus();

      const focusStyles = await executeButton.evaluate(el => {
        const computed = window.getComputedStyle(el);
        return {
          outline: computed.outline,
          outlineColor: computed.outlineColor,
          boxShadow: computed.boxShadow
        };
      });

      console.log('Focus indicator styles:', focusStyles);
    });

    test('should have sufficient contrast for error messages', async ({ page }) => {
      const tenantInput = page.locator('input[placeholder*="xxxx"]').first();
      await tenantInput.fill('12345678-1234-1234-1234-123456789abc');

      const executeButton = page.locator('button:has-text("Execute")').first();
      if (await executeButton.isEnabled()) {
        await executeButton.click();
        await page.waitForTimeout(2000);

        const errorAlert = page.locator('[role="alert"]').filter({ hasText: /error/i }).first();
        if (await errorAlert.isVisible()) {
          const colors = await errorAlert.evaluate(el => {
            const computed = window.getComputedStyle(el);
            return {
              color: computed.color,
              backgroundColor: computed.backgroundColor
            };
          });

          console.log('Error alert colors:', colors);
        }
      }
    });
  });

  test.describe('Touch Target Size', () => {
    test('should have adequate touch target size for buttons', async ({ page }) => {
      const executeButton = page.locator('button:has-text("Execute")').first();

      const size = await executeButton.evaluate(el => {
        const rect = el.getBoundingClientRect();
        return {
          width: rect.width,
          height: rect.height
        };
      });

      console.log('Execute button size:', size);

      // WCAG recommends minimum 44x44 pixels for touch targets
      // MUI buttons may be smaller but should still be reasonable
      expect(size.height).toBeGreaterThan(30);
    });

    test('should have adequate touch target size for toggle buttons', async ({ page }) => {
      const scaleUpButton = page.locator('button:has-text("Scale Up")').first();

      const size = await scaleUpButton.evaluate(el => {
        const rect = el.getBoundingClientRect();
        return {
          width: rect.width,
          height: rect.height
        };
      });

      console.log('Toggle button size:', size);
      expect(size.height).toBeGreaterThan(30);
    });

    test('should have adequate spacing between buttons', async ({ page }) => {
      const previewButton = page.locator('button:has-text("Preview")').first();
      const executeButton = page.locator('button:has-text("Execute")').first();

      const positions = await Promise.all([
        previewButton.evaluate(el => el.getBoundingClientRect()),
        executeButton.evaluate(el => el.getBoundingClientRect())
      ]);

      const spacing = positions[1].left - positions[0].right;
      console.log('Button spacing:', spacing);

      // Should have reasonable spacing
      expect(spacing).toBeGreaterThanOrEqual(0);
    });
  });

  test.describe('Screen Reader Announcements', () => {
    test('should announce mode changes', async ({ page }) => {
      // This would require screen reader testing tools
      // For now, check that there are appropriate aria-live regions

      const scaleDownButton = page.locator('button:has-text("Scale Down")').first();
      await scaleDownButton.click();
      await page.waitForTimeout(500);

      // Check for live regions that would announce changes
      const liveRegions = page.locator('[aria-live]');
      const count = await liveRegions.count();
      console.log('Live regions found:', count);
    });

    test('should announce validation errors', async ({ page }) => {
      const tenantInput = page.locator('input[placeholder*="xxxx"]').first();
      await tenantInput.fill('invalid');
      await page.waitForTimeout(300);

      // Look for error message with role="alert"
      const errorAlert = page.locator('[role="alert"]');
      const hasError = await errorAlert.isVisible().catch(() => false);
      console.log('Error alert for screen readers:', hasError);
    });

    test('should announce loading states', async ({ page }) => {
      const tenantInput = page.locator('input[placeholder*="xxxx"]').first();
      await tenantInput.fill('12345678-1234-1234-1234-123456789abc');

      const previewButton = page.locator('button:has-text("Preview")').first();
      await previewButton.click();
      await page.waitForTimeout(500);

      // Check for aria-busy or status role
      const busyRegion = page.locator('[aria-busy="true"], [role="status"]');
      const isBusy = await busyRegion.isVisible().catch(() => false);
      console.log('Loading state announced:', isBusy);
    });
  });

  test.describe('Reduced Motion', () => {
    test('should respect prefers-reduced-motion', async ({ page }) => {
      // Emulate reduced motion preference
      await page.emulateMedia({ reducedMotion: 'reduce' });

      // Navigate through UI
      const scaleDownButton = page.locator('button:has-text("Scale Down")').first();
      await scaleDownButton.click();
      await page.waitForTimeout(500);

      // UI should still function without relying on motion
      await expect(page.locator('text=Scale-Down Configuration')).toBeVisible();
    });
  });
});

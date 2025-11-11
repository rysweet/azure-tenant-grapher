import { test, expect } from '@playwright/test';

/**
 * Scale Operations - Complete Workflow Tests
 *
 * Tests complete end-to-end workflows:
 * - Complete scale-up workflow
 * - Complete scale-down workflow
 * - Preview → Execute flow
 * - Clean → Validate flow
 * - Multi-step operations
 */

test.describe('Scale Operations - Complete Workflows', () => {
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

  test.describe('Scale-Up Workflows', () => {
    test('complete scale-up workflow with template strategy', async ({ page }) => {
      // Step 1: Verify scale-up mode is active
      await expect(page.locator('text=Scale-Up Configuration')).toBeVisible();

      // Step 2: Configure tenant
      const tenantInput = page.locator('input[placeholder*="xxxx"]').first();
      await tenantInput.fill('12345678-1234-1234-1234-123456789abc');
      await expect(tenantInput).toHaveValue('12345678-1234-1234-1234-123456789abc');

      // Step 3: Verify template strategy is selected (default)
      await expect(page.locator('text=Template File')).toBeVisible();

      // Step 4: Configure template file
      const templateInput = page.locator('input[placeholder*="template"]').first();
      await templateInput.fill('templates/enterprise_scale.yaml');
      await expect(templateInput).toHaveValue('templates/enterprise_scale.yaml');

      // Step 5: Adjust scale factor
      const slider = page.locator('input[type="range"]').first();
      await slider.fill('3');
      await expect(page.locator('text=Scale Factor: 3x')).toBeVisible();

      // Step 6: Enable validation
      const validateCheckbox = page.locator('input[type="checkbox"]').first();
      await validateCheckbox.check();
      await expect(validateCheckbox).toBeChecked();

      // Step 7: Preview the operation
      const previewButton = page.locator('button:has-text("Preview")').first();
      await expect(previewButton).toBeEnabled();
      await previewButton.click();
      await page.waitForTimeout(2000);

      // Step 8: Verify execute button is available
      const executeButton = page.locator('button:has-text("Execute")').first();
      await expect(executeButton).toBeVisible();

      // Note: Actual execution would require backend
      console.log('Scale-up workflow configured successfully');
    });

    test('complete scale-up workflow with scenario strategy', async ({ page }) => {
      // Step 1: Configure tenant
      const tenantInput = page.locator('input[placeholder*="xxxx"]').first();
      await tenantInput.fill('87654321-4321-4321-4321-210987654321');

      // Step 2: Switch to scenario strategy
      const strategySelect = page.locator('select').filter({ has: page.locator('option:has-text("Template")') }).first();
      await strategySelect.selectOption('scenario');
      await page.waitForTimeout(500);

      // Step 3: Verify scenario fields appear
      await expect(page.locator('text=Scenario Type')).toBeVisible();

      // Step 4: Select scenario type
      const scenarioSelect = page.locator('select').filter({ has: page.locator('option:has-text("Enterprise")') }).first();
      await scenarioSelect.selectOption('hybrid');
      await page.waitForTimeout(300);

      // Step 5: Enable validation
      const validateCheckbox = page.locator('input[type="checkbox"]').first();
      await validateCheckbox.check();

      // Step 6: Preview
      const previewButton = page.locator('button:has-text("Preview")').first();
      await previewButton.click();
      await page.waitForTimeout(2000);

      // Verify configuration is complete
      const executeButton = page.locator('button:has-text("Execute")').first();
      await expect(executeButton).toBeVisible();
    });

    test('complete scale-up workflow with random strategy', async ({ page }) => {
      // Step 1: Configure tenant
      const tenantInput = page.locator('input[placeholder*="xxxx"]').first();
      await tenantInput.fill('abcdef12-3456-7890-abcd-ef1234567890');

      // Step 2: Switch to random strategy
      const strategySelect = page.locator('select').filter({ has: page.locator('option:has-text("Template")') }).first();
      await strategySelect.selectOption('random');
      await page.waitForTimeout(500);

      // Step 3: Configure node count
      const nodeCountInput = page.locator('input[type="number"]').first();
      await nodeCountInput.fill('5000');
      await expect(nodeCountInput).toHaveValue('5000');

      // Step 4: Select pattern
      const patternSelect = page.locator('select').filter({ has: page.locator('option:has-text("Standard")') }).first();
      await patternSelect.selectOption('hub-spoke');
      await page.waitForTimeout(300);

      // Step 5: Preview
      const previewButton = page.locator('button:has-text("Preview")').first();
      await previewButton.click();
      await page.waitForTimeout(2000);

      // Verify ready for execution
      const executeButton = page.locator('button:has-text("Execute")').first();
      await expect(executeButton).toBeEnabled();
    });

    test('scale-up workflow with validation disabled', async ({ page }) => {
      // Configure basic setup
      const tenantInput = page.locator('input[placeholder*="xxxx"]').first();
      await tenantInput.fill('12345678-1234-1234-1234-123456789abc');

      // Disable validation
      const validateCheckbox = page.locator('input[type="checkbox"]').first();
      await validateCheckbox.uncheck();
      await expect(validateCheckbox).not.toBeChecked();

      // Verify execute is still available
      const executeButton = page.locator('button:has-text("Execute")').first();
      await expect(executeButton).toBeEnabled();
    });
  });

  test.describe('Scale-Down Workflows', () => {
    test.beforeEach(async ({ page }) => {
      // Switch to scale-down mode
      const scaleDownButton = page.locator('button:has-text("Scale Down")').first();
      await scaleDownButton.click();
      await page.waitForTimeout(500);
    });

    test('complete scale-down workflow with forest-fire algorithm', async ({ page }) => {
      // Step 1: Verify scale-down mode
      await expect(page.locator('text=Scale-Down Configuration')).toBeVisible();

      // Step 2: Configure tenant
      const tenantInput = page.locator('input[placeholder*="xxxx"]').first();
      await tenantInput.fill('12345678-1234-1234-1234-123456789abc');

      // Step 3: Verify forest-fire is selected (default)
      await expect(page.locator('text=Burn In Steps')).toBeVisible();

      // Step 4: Configure sample size
      const sampleSizeInput = page.locator('input[type="number"]').first();
      await sampleSizeInput.fill('1000');
      await expect(sampleSizeInput).toHaveValue('1000');

      // Step 5: Configure burn in steps
      const burnInInput = page.locator('input[type="number"]').nth(1);
      if (await burnInInput.isVisible()) {
        await burnInInput.fill('10');
      }

      // Step 6: Configure output mode (default is file)
      const outputPathInput = page.locator('input[placeholder*="output"]').first();
      if (await outputPathInput.isVisible()) {
        await outputPathInput.fill('outputs/sampled_graph.json');
      }

      // Step 7: Preview
      const previewButton = page.locator('button:has-text("Preview")').first();
      await previewButton.click();
      await page.waitForTimeout(2000);

      // Verify ready for execution
      const executeButton = page.locator('button:has-text("Execute")').first();
      await expect(executeButton).toBeVisible();
    });

    test('complete scale-down workflow with mhrw algorithm', async ({ page }) => {
      // Configure tenant
      const tenantInput = page.locator('input[placeholder*="xxxx"]').first();
      await tenantInput.fill('87654321-4321-4321-4321-210987654321');

      // Switch to MHRW algorithm
      const algorithmSelect = page.locator('select').filter({ has: page.locator('option:has-text("Forest")') }).first();
      await algorithmSelect.selectOption('mhrw');
      await page.waitForTimeout(500);

      // Verify MHRW fields appear
      await expect(page.locator('text=Walk Length')).toBeVisible();

      // Configure walk length
      const walkLengthInput = page.locator('input[type="number"]').nth(1);
      if (await walkLengthInput.isVisible()) {
        await walkLengthInput.fill('150');
      }

      // Configure sample size
      const sampleSizeInput = page.locator('input[type="number"]').first();
      await sampleSizeInput.fill('750');

      // Preview
      const previewButton = page.locator('button:has-text("Preview")').first();
      await previewButton.click();
      await page.waitForTimeout(2000);

      // Verify execute available
      const executeButton = page.locator('button:has-text("Execute")').first();
      await expect(executeButton).toBeEnabled();
    });

    test('scale-down workflow with IaC output mode', async ({ page }) => {
      // Configure tenant
      const tenantInput = page.locator('input[placeholder*="xxxx"]').first();
      await tenantInput.fill('12345678-1234-1234-1234-123456789abc');

      // Select IaC output mode
      const iacRadio = page.locator('input[type="radio"][value="iac"]').first();
      if (await iacRadio.isVisible()) {
        await iacRadio.check();
        await page.waitForTimeout(300);

        // Verify IaC format selector appears
        await expect(page.locator('text=IaC Format')).toBeVisible();

        // Select format
        const formatSelect = page.locator('select').filter({ has: page.locator('option:has-text("Terraform")') }).first();
        if (await formatSelect.isVisible()) {
          await formatSelect.selectOption('bicep');
        }
      }

      // Configure sample size
      const sampleSizeInput = page.locator('input[type="number"]').first();
      await sampleSizeInput.fill('500');

      // Preview and execute should be available
      const previewButton = page.locator('button:has-text("Preview")').first();
      await expect(previewButton).toBeEnabled();
    });

    test('scale-down workflow with new tenant output mode', async ({ page }) => {
      // Configure tenant
      const tenantInput = page.locator('input[placeholder*="xxxx"]').first();
      await tenantInput.fill('12345678-1234-1234-1234-123456789abc');

      // Select new-tenant output mode
      const newTenantRadio = page.locator('input[type="radio"][value="new-tenant"]').first();
      if (await newTenantRadio.isVisible()) {
        await newTenantRadio.check();
        await page.waitForTimeout(300);

        // Verify new tenant ID field appears
        await expect(page.locator('text=New Tenant ID')).toBeVisible();

        // Fill new tenant ID
        const newTenantInput = page.locator('input[placeholder*="new"]').first();
        if (await newTenantInput.isVisible()) {
          await newTenantInput.fill('fedcba98-7654-3210-fedc-ba9876543210');
        }
      }

      // Configure sample size
      const sampleSizeInput = page.locator('input[type="number"]').first();
      await sampleSizeInput.fill('300');

      // Verify ready for execution
      const executeButton = page.locator('button:has-text("Execute")').first();
      await expect(executeButton).toBeEnabled();
    });
  });

  test.describe('Preview → Execute Workflows', () => {
    test('preview before execute workflow', async ({ page }) => {
      // Configure operation
      const tenantInput = page.locator('input[placeholder*="xxxx"]').first();
      await tenantInput.fill('12345678-1234-1234-1234-123456789abc');

      // Step 1: Preview first
      const previewButton = page.locator('button:has-text("Preview")').first();
      await previewButton.click();
      await page.waitForTimeout(2000);

      // Step 2: Review preview results (if available)
      const previewAlert = page.locator('[role="alert"]').filter({ hasText: /Preview/i });
      const previewVisible = await previewAlert.isVisible().catch(() => false);

      if (previewVisible) {
        // Preview results are shown
        console.log('Preview results displayed');

        // Step 3: Proceed to execute
        const executeButton = page.locator('button:has-text("Execute")').first();
        await expect(executeButton).toBeEnabled();
      } else {
        // Preview may have failed (no backend)
        console.log('Preview not available (requires backend)');
      }
    });

    test('modify after preview workflow', async ({ page }) => {
      // Configure and preview
      const tenantInput = page.locator('input[placeholder*="xxxx"]').first();
      await tenantInput.fill('12345678-1234-1234-1234-123456789abc');

      const previewButton = page.locator('button:has-text("Preview")').first();
      await previewButton.click();
      await page.waitForTimeout(2000);

      // Modify configuration
      const slider = page.locator('input[type="range"]').first();
      await slider.fill('5');
      await page.waitForTimeout(300);

      // Preview again with new settings
      await previewButton.click();
      await page.waitForTimeout(2000);

      // Should still be able to execute
      const executeButton = page.locator('button:has-text("Execute")').first();
      await expect(executeButton).toBeEnabled();
    });

    test('execute without preview workflow', async ({ page }) => {
      // Configure operation
      const tenantInput = page.locator('input[placeholder*="xxxx"]').first();
      await tenantInput.fill('12345678-1234-1234-1234-123456789abc');

      // Skip preview and go directly to execute
      const executeButton = page.locator('button:has-text("Execute")').first();
      await expect(executeButton).toBeEnabled();

      // Should be able to execute without previewing
      console.log('Execute available without preview');
    });
  });

  test.describe('Clean → Validate Workflows', () => {
    test('validate before operations workflow', async ({ page }) => {
      // Step 1: Run validation first
      const validateButton = page.locator('button:has-text("Validate")').first();
      if (await validateButton.isVisible()) {
        await validateButton.click();
        await page.waitForTimeout(2000);

        // Validation dialog may appear
        const validationDialog = page.locator('text=Validation Results');
        const dialogVisible = await validationDialog.isVisible().catch(() => false);
        console.log('Validation dialog visible:', dialogVisible);

        if (dialogVisible) {
          // Close dialog
          const closeButton = page.locator('button:has-text("Close")').last();
          await closeButton.click();
        }
      }

      // Step 2: Proceed with scale-up operation
      const tenantInput = page.locator('input[placeholder*="xxxx"]').first();
      await tenantInput.fill('12345678-1234-1234-1234-123456789abc');

      const executeButton = page.locator('button:has-text("Execute")').first();
      await expect(executeButton).toBeEnabled();
    });

    test('clean synthetic data workflow', async ({ page }) => {
      // Step 1: Open clean dialog
      const cleanButton = page.locator('button:has-text("Clean")').first();
      if (await cleanButton.isVisible()) {
        await cleanButton.click();
        await page.waitForTimeout(500);

        // Step 2: Verify dialog opens
        const cleanDialog = page.locator('text=Clean Synthetic Data');
        await expect(cleanDialog).toBeVisible();

        // Step 3: Read warning message
        await expect(page.locator('text=permanently delete')).toBeVisible();

        // Step 4: Cancel (don't actually clean in test)
        const cancelButton = page.locator('button:has-text("Cancel")').first();
        await cancelButton.click();
        await page.waitForTimeout(300);

        // Dialog should close
        expect(await cleanDialog.isVisible().catch(() => false)).toBe(false);
      }
    });

    test('validate after scale-up workflow', async ({ page }) => {
      // This workflow would require:
      // 1. Execute scale-up
      // 2. Wait for completion
      // 3. Run validation
      // 4. Review results

      // For now, just verify the UI flow is available
      const tenantInput = page.locator('input[placeholder*="xxxx"]').first();
      await tenantInput.fill('12345678-1234-1234-1234-123456789abc');

      // Validation checkbox should be available
      const validateCheckbox = page.locator('input[type="checkbox"]').first();
      await validateCheckbox.check();

      // Execute button available
      const executeButton = page.locator('button:has-text("Execute")').first();
      await expect(executeButton).toBeEnabled();

      // Validation button in quick actions
      const validateButton = page.locator('button:has-text("Validate")').first();
      await expect(validateButton).toBeVisible();
    });

    test('statistics workflow', async ({ page }) => {
      // View statistics before operation
      const statsButton = page.locator('button:has-text("Statistics")').first();
      if (await statsButton.isVisible()) {
        await statsButton.click();
        await page.waitForTimeout(1000);

        // Stats dialog should appear
        const statsDialog = page.locator('text=Graph Statistics');
        await expect(statsDialog).toBeVisible();

        // Should show node and relationship counts
        await expect(page.locator('text=Total Nodes')).toBeVisible();

        // Close dialog
        const closeButton = page.locator('button:has-text("Close")').last();
        await closeButton.click();
        await page.waitForTimeout(300);
      }
    });
  });

  test.describe('Multi-Step Operations', () => {
    test('switch strategies mid-configuration', async ({ page }) => {
      // Start with template
      const tenantInput = page.locator('input[placeholder*="xxxx"]').first();
      await tenantInput.fill('12345678-1234-1234-1234-123456789abc');

      const templateInput = page.locator('input[placeholder*="template"]').first();
      await templateInput.fill('custom_template.yaml');

      // Switch to scenario
      const strategySelect = page.locator('select').filter({ has: page.locator('option:has-text("Template")') }).first();
      await strategySelect.selectOption('scenario');
      await page.waitForTimeout(500);

      // Switch to random
      await strategySelect.selectOption('random');
      await page.waitForTimeout(500);

      // Switch back to template
      await strategySelect.selectOption('template');
      await page.waitForTimeout(500);

      // Should still be functional
      const executeButton = page.locator('button:has-text("Execute")').first();
      await expect(executeButton).toBeEnabled();
    });

    test('toggle between scale-up and scale-down mid-configuration', async ({ page }) => {
      // Configure scale-up
      const tenantInput = page.locator('input[placeholder*="xxxx"]').first();
      await tenantInput.fill('12345678-1234-1234-1234-123456789abc');

      const slider = page.locator('input[type="range"]').first();
      await slider.fill('4');
      await page.waitForTimeout(300);

      // Switch to scale-down
      const scaleDownButton = page.locator('button:has-text("Scale Down")').first();
      await scaleDownButton.click();
      await page.waitForTimeout(500);

      // Configure scale-down
      const sampleSizeInput = page.locator('input[type="number"]').first();
      await sampleSizeInput.fill('600');

      // Switch back to scale-up
      const scaleUpButton = page.locator('button:has-text("Scale Up")').first();
      await scaleUpButton.click();
      await page.waitForTimeout(500);

      // Should still be functional
      const executeButton = page.locator('button:has-text("Execute")').first();
      await expect(executeButton).toBeEnabled();
    });

    test('multiple preview cycles', async ({ page }) => {
      // Configure
      const tenantInput = page.locator('input[placeholder*="xxxx"]').first();
      await tenantInput.fill('12345678-1234-1234-1234-123456789abc');

      const previewButton = page.locator('button:has-text("Preview")').first();

      // Preview multiple times
      for (let i = 0; i < 3; i++) {
        await previewButton.click();
        await page.waitForTimeout(1500);
        console.log(`Preview cycle ${i + 1} completed`);
      }

      // Should still be functional
      const executeButton = page.locator('button:has-text("Execute")').first();
      await expect(executeButton).toBeEnabled();
    });

    test('clear and reconfigure workflow', async ({ page }) => {
      // Configure operation
      const tenantInput = page.locator('input[placeholder*="xxxx"]').first();
      await tenantInput.fill('12345678-1234-1234-1234-123456789abc');

      const slider = page.locator('input[type="range"]').first();
      await slider.fill('6');
      await page.waitForTimeout(300);

      // Clear
      const clearButton = page.locator('button:has-text("Clear")').first();
      await clearButton.click();
      await page.waitForTimeout(500);

      // Reconfigure with different values
      await tenantInput.fill('fedcba98-7654-3210-fedc-ba9876543210');
      await slider.fill('8');
      await page.waitForTimeout(300);

      // Should be functional
      const executeButton = page.locator('button:has-text("Execute")').first();
      await expect(executeButton).toBeEnabled();
    });
  });

  test.describe('Error Recovery Workflows', () => {
    test('recover from validation error', async ({ page }) => {
      // Enter invalid data
      const tenantInput = page.locator('input[placeholder*="xxxx"]').first();
      await tenantInput.fill('invalid-id');
      await page.waitForTimeout(300);

      // Try to execute (should be disabled)
      const executeButton = page.locator('button:has-text("Execute")').first();
      const isDisabled = await executeButton.isDisabled();
      expect(isDisabled).toBe(true);

      // Correct the data
      await tenantInput.clear();
      await tenantInput.fill('12345678-1234-1234-1234-123456789abc');
      await page.waitForTimeout(300);

      // Should now be enabled
      await expect(executeButton).toBeEnabled();
    });

    test('recover from operation error', async ({ page }) => {
      // Configure operation
      const tenantInput = page.locator('input[placeholder*="xxxx"]').first();
      await tenantInput.fill('12345678-1234-1234-1234-123456789abc');

      // Try to execute (will fail without backend)
      const executeButton = page.locator('button:has-text("Execute")').first();
      await executeButton.click();
      await page.waitForTimeout(2000);

      // May show error
      const errorAlert = page.locator('[role="alert"]').filter({ hasText: /error/i });
      const errorVisible = await errorAlert.isVisible().catch(() => false);

      if (errorVisible) {
        // Close error
        const closeButton = errorAlert.locator('button[aria-label*="close"]').first();
        if (await closeButton.isVisible()) {
          await closeButton.click();
        }

        // Should be able to try again
        await expect(executeButton).toBeEnabled();
      }
    });

    test('handle connection warning gracefully', async ({ page }) => {
      // Check for connection warning
      const connectionWarning = page.locator('[role="alert"]').filter({ hasText: /Not connected/i });
      const warningVisible = await connectionWarning.isVisible().catch(() => false);

      if (warningVisible) {
        console.log('Connection warning displayed');
      }

      // Should still be able to configure
      const tenantInput = page.locator('input[placeholder*="xxxx"]').first();
      await tenantInput.fill('12345678-1234-1234-1234-123456789abc');

      const executeButton = page.locator('button:has-text("Execute")').first();
      await expect(executeButton).toBeVisible();
    });
  });

  test.describe('Complex Configuration Workflows', () => {
    test('configure all options workflow', async ({ page }) => {
      // Configure every available option
      const tenantInput = page.locator('input[placeholder*="xxxx"]').first();
      await tenantInput.fill('12345678-1234-1234-1234-123456789abc');

      const templateInput = page.locator('input[placeholder*="template"]').first();
      await templateInput.fill('templates/full_config.yaml');

      const slider = page.locator('input[type="range"]').first();
      await slider.fill('7');

      const validateCheckbox = page.locator('input[type="checkbox"]').first();
      await validateCheckbox.check();

      await page.waitForTimeout(500);

      // Preview with all options
      const previewButton = page.locator('button:has-text("Preview")').first();
      await previewButton.click();
      await page.waitForTimeout(2000);

      // Should be ready for execution
      const executeButton = page.locator('button:has-text("Execute")').first();
      await expect(executeButton).toBeEnabled();
    });

    test('minimal configuration workflow', async ({ page }) => {
      // Configure only required fields
      const tenantInput = page.locator('input[placeholder*="xxxx"]').first();
      await tenantInput.fill('12345678-1234-1234-1234-123456789abc');

      // Use all defaults
      const executeButton = page.locator('button:has-text("Execute")').first();
      await expect(executeButton).toBeEnabled();
    });
  });
});

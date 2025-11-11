import { test, expect } from '@playwright/test';
import * as path from 'path';

/**
 * Comprehensive screenshot capture for Scale Operations UI
 *
 * This test captures all key states and interactions of the Scale Operations feature
 * for use in PowerPoint presentations and documentation.
 */

const SCREENSHOT_DIR = path.join(__dirname, '../../screenshots/scale-operations');
const VIEWPORT_SIZE = { width: 1920, height: 1080 };
const WAIT_AFTER_NAVIGATION = 2000; // ms to wait for animations
const WAIT_AFTER_INTERACTION = 1000; // ms to wait after user interactions

test.describe.configure({ mode: 'serial', timeout: 90000 }); // Run tests sequentially with 90s timeout

test.describe('Scale Operations UI Screenshots', () => {
  test.beforeEach(async ({ page }) => {
    // Set viewport to high resolution for quality screenshots
    await page.setViewportSize(VIEWPORT_SIZE);

    // Navigate to the app
    await page.goto('http://localhost:5173', { timeout: 60000 });
    await page.waitForLoadState('networkidle', { timeout: 60000 });
    await page.waitForTimeout(WAIT_AFTER_NAVIGATION);

    // Navigate to Scale Operations tab
    // Try multiple possible selectors for the tab
    const scaleOpsTabSelectors = [
      'text=Scale Ops',
      'text=Scale Operations',
      'button:has-text("Scale Ops")',
      'button:has-text("Scale Operations")',
      '[role="tab"]:has-text("Scale")',
    ];

    let tabFound = false;
    for (const selector of scaleOpsTabSelectors) {
      try {
        const element = page.locator(selector).first();
        if (await element.isVisible({ timeout: 2000 })) {
          await element.click();
          tabFound = true;
          break;
        }
      } catch (e) {
        // Try next selector
        continue;
      }
    }

    if (!tabFound) {
      console.warn('Scale Operations tab not found, may need to adjust selectors');
    }

    await page.waitForTimeout(WAIT_AFTER_NAVIGATION);
  });

  test('01 - Initial state with Scale-Up mode selected', async ({ page }) => {
    // Ensure Scale-Up is selected (should be default)
    const scaleUpButton = page.locator('button:has-text("Scale Up")').first();
    if (await scaleUpButton.isVisible()) {
      await scaleUpButton.click();
      await page.waitForTimeout(WAIT_AFTER_INTERACTION);
    }

    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, '01-initial-scale-up.png'),
      fullPage: true,
    });
  });

  test('02 - Scale-Down mode selected', async ({ page }) => {
    // Click Scale-Down toggle
    const scaleDownButton = page.locator('button:has-text("Scale Down")').first();
    if (await scaleDownButton.isVisible()) {
      await scaleDownButton.click();
      await page.waitForTimeout(WAIT_AFTER_INTERACTION);
    }

    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, '02-scale-down-mode.png'),
      fullPage: true,
    });
  });

  test('03 - Scale-Up Template strategy form', async ({ page }) => {
    // Ensure Scale-Up is selected
    const scaleUpButton = page.locator('button:has-text("Scale Up")').first();
    if (await scaleUpButton.isVisible()) {
      await scaleUpButton.click();
      await page.waitForTimeout(WAIT_AFTER_INTERACTION);
    }

    // Select Template strategy (should be default)
    const strategySelect = page.locator('select').filter({ hasText: /strategy/i }).first();
    if (await strategySelect.isVisible()) {
      await strategySelect.selectOption('template');
      await page.waitForTimeout(WAIT_AFTER_INTERACTION);
    }

    // Fill in some sample values
    const templateFileInput = page.locator('input[type="text"]').filter({ hasText: /template/i }).first();
    if (await templateFileInput.isVisible()) {
      await templateFileInput.fill('templates/enterprise_template.yaml');
      await page.waitForTimeout(300);
    }

    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, '03-template-strategy-form.png'),
      fullPage: true,
    });
  });

  test('04 - Scale-Up Scenario strategy (hub-spoke)', async ({ page }) => {
    // Ensure Scale-Up is selected
    const scaleUpButton = page.locator('button:has-text("Scale Up")').first();
    if (await scaleUpButton.isVisible()) {
      await scaleUpButton.click();
      await page.waitForTimeout(WAIT_AFTER_INTERACTION);
    }

    // Try to select Scenario strategy
    const strategySelectors = [
      'select[name="strategy"]',
      'div[role="button"]:has-text("Strategy")',
      'input[value="scenario"]',
    ];

    for (const selector of strategySelectors) {
      try {
        const element = page.locator(selector).first();
        if (await element.isVisible({ timeout: 1000 })) {
          if (await element.evaluate(el => el.tagName) === 'SELECT') {
            await element.selectOption('scenario');
          } else {
            await element.click();
            await page.waitForTimeout(300);
            await page.locator('text=Scenario').click();
          }
          break;
        }
      } catch (e) {
        continue;
      }
    }

    await page.waitForTimeout(WAIT_AFTER_INTERACTION);

    // Try to select hub-spoke scenario
    const scenarioSelectors = [
      'select[name="scenarioType"]',
      'div[role="button"]:has-text("Scenario Type")',
      'input[value="hub-spoke"]',
    ];

    for (const selector of scenarioSelectors) {
      try {
        const element = page.locator(selector).first();
        if (await element.isVisible({ timeout: 1000 })) {
          if (await element.evaluate(el => el.tagName) === 'SELECT') {
            await element.selectOption('hub-spoke');
          } else {
            await element.click();
            await page.waitForTimeout(300);
            await page.locator('text=Hub-Spoke').click();
          }
          break;
        }
      } catch (e) {
        continue;
      }
    }

    await page.waitForTimeout(WAIT_AFTER_INTERACTION);

    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, '04-scenario-hub-spoke.png'),
      fullPage: true,
    });
  });

  test('05 - Scale-Up Random strategy form', async ({ page }) => {
    // Ensure Scale-Up is selected
    const scaleUpButton = page.locator('button:has-text("Scale Up")').first();
    if (await scaleUpButton.isVisible()) {
      await scaleUpButton.click();
      await page.waitForTimeout(WAIT_AFTER_INTERACTION);
    }

    // Try to select Random strategy
    const strategySelectors = [
      'select[name="strategy"]',
      'div[role="button"]:has-text("Strategy")',
    ];

    for (const selector of strategySelectors) {
      try {
        const element = page.locator(selector).first();
        if (await element.isVisible({ timeout: 1000 })) {
          if (await element.evaluate(el => el.tagName) === 'SELECT') {
            await element.selectOption('random');
          } else {
            await element.click();
            await page.waitForTimeout(300);
            await page.locator('text=Random').click();
          }
          break;
        }
      } catch (e) {
        continue;
      }
    }

    await page.waitForTimeout(WAIT_AFTER_INTERACTION);

    // Fill in node count
    const nodeCountInput = page.locator('input[type="number"]').first();
    if (await nodeCountInput.isVisible()) {
      await nodeCountInput.fill('5000');
      await page.waitForTimeout(300);
    }

    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, '05-random-strategy-form.png'),
      fullPage: true,
    });
  });

  test('06 - Scale-Down with Forest Fire algorithm', async ({ page }) => {
    // Click Scale-Down toggle
    const scaleDownButton = page.locator('button:has-text("Scale Down")').first();
    if (await scaleDownButton.isVisible()) {
      await scaleDownButton.click();
      await page.waitForTimeout(WAIT_AFTER_INTERACTION);
    }

    // Try to select Forest Fire algorithm
    const algorithmSelectors = [
      'select[name="algorithm"]',
      'div[role="button"]:has-text("Algorithm")',
    ];

    for (const selector of algorithmSelectors) {
      try {
        const element = page.locator(selector).first();
        if (await element.isVisible({ timeout: 1000 })) {
          if (await element.evaluate(el => el.tagName) === 'SELECT') {
            await element.selectOption('forest_fire');
          } else {
            await element.click();
            await page.waitForTimeout(300);
            await page.locator('text=Forest Fire').click();
          }
          break;
        }
      } catch (e) {
        continue;
      }
    }

    await page.waitForTimeout(WAIT_AFTER_INTERACTION);

    // Fill in target node count
    const targetNodesInput = page.locator('input[type="number"]').first();
    if (await targetNodesInput.isVisible()) {
      await targetNodesInput.fill('500');
      await page.waitForTimeout(300);
    }

    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, '06-scale-down-forest-fire.png'),
      fullPage: true,
    });
  });

  test('07 - Preview results display', async ({ page }) => {
    // Skip this test as it requires backend functionality
    // Just capture the form ready for preview
    const scaleUpButton = page.locator('button:has-text("Scale Up")').first();
    if (await scaleUpButton.isVisible()) {
      await scaleUpButton.click();
      await page.waitForTimeout(WAIT_AFTER_INTERACTION);
    }

    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, '07-ready-for-preview.png'),
      fullPage: true,
    });

    console.log('Note: Preview results require backend. Screenshot shows ready state.');
  });

  test('08 - Progress monitor during operation', async ({ page }) => {
    // This test simulates the progress state
    // In a real scenario, we'd need backend mock or test data

    // For now, capture the form in ready state
    // (Progress monitor would appear after clicking Execute)

    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, '08-ready-for-execution.png'),
      fullPage: true,
    });

    console.log('Note: Progress monitor requires running operation. Consider mocking backend responses.');
  });

  test('09 - Quick actions menu', async ({ page }) => {
    // Scroll down to see quick actions
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
    await page.waitForTimeout(500);

    // Look for quick actions bar
    const quickActionSelectors = [
      'text=Quick Actions',
      'button:has-text("History")',
      'button:has-text("Templates")',
      'button:has-text("Export")',
    ];

    let quickActionsVisible = false;
    for (const selector of quickActionSelectors) {
      if (await page.locator(selector).first().isVisible()) {
        quickActionsVisible = true;
        break;
      }
    }

    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, '09-quick-actions.png'),
      fullPage: true,
    });

    if (!quickActionsVisible) {
      console.warn('Quick actions not visible in current state');
    }
  });

  test('10 - Validation checkbox and options', async ({ page }) => {
    // Ensure Scale-Up is selected
    const scaleUpButton = page.locator('button:has-text("Scale Up")').first();
    if (await scaleUpButton.isVisible()) {
      await scaleUpButton.click();
      await page.waitForTimeout(WAIT_AFTER_INTERACTION);
    }

    // Look for validation checkbox
    const validateCheckbox = page.locator('input[type="checkbox"]').first();
    if (await validateCheckbox.isVisible()) {
      // Ensure it's checked to show validation options
      const isChecked = await validateCheckbox.isChecked();
      if (!isChecked) {
        await validateCheckbox.check();
        await page.waitForTimeout(WAIT_AFTER_INTERACTION);
      }
    }

    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, '10-validation-options.png'),
      fullPage: true,
    });
  });

  test('11 - Scale factor slider (Template mode)', async ({ page }) => {
    // Ensure Scale-Up is selected
    const scaleUpButton = page.locator('button:has-text("Scale Up")').first();
    if (await scaleUpButton.isVisible()) {
      await scaleUpButton.click();
      await page.waitForTimeout(WAIT_AFTER_INTERACTION);
    }

    // Ensure Template strategy is selected
    const strategySelect = page.locator('select').first();
    if (await strategySelect.isVisible()) {
      try {
        await strategySelect.selectOption('template');
        await page.waitForTimeout(WAIT_AFTER_INTERACTION);
      } catch (e) {
        // May already be selected
      }
    }

    // Try to interact with scale factor slider
    const sliders = page.locator('input[type="range"], [role="slider"]');
    const sliderCount = await sliders.count();

    if (sliderCount > 0) {
      const slider = sliders.first();
      await slider.focus();
      await page.waitForTimeout(300);
    }

    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, '11-scale-factor-slider.png'),
      fullPage: true,
    });
  });

  test('12 - Complete Scale-Up configuration form', async ({ page }) => {
    // Ensure Scale-Up is selected
    const scaleUpButton = page.locator('button:has-text("Scale Up")').first();
    if (await scaleUpButton.isVisible()) {
      await scaleUpButton.click();
      await page.waitForTimeout(WAIT_AFTER_INTERACTION);
    }

    // Fill in all fields with sample data
    const inputs = await page.locator('input[type="text"], input[type="number"]').all();

    // Fill tenant ID if visible
    for (const input of inputs) {
      const placeholder = await input.getAttribute('placeholder');
      if (placeholder && placeholder.toLowerCase().includes('tenant')) {
        await input.fill('12345678-1234-1234-1234-123456789abc');
        await page.waitForTimeout(300);
        break;
      }
    }

    // Fill template file
    for (const input of inputs) {
      const placeholder = await input.getAttribute('placeholder');
      if (placeholder && placeholder.toLowerCase().includes('template')) {
        await input.fill('templates/full_enterprise.yaml');
        await page.waitForTimeout(300);
        break;
      }
    }

    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, '12-complete-form.png'),
      fullPage: true,
    });
  });

  test('13 - Scale-Down complete configuration', async ({ page }) => {
    // Click Scale-Down toggle
    const scaleDownButton = page.locator('button:has-text("Scale Down")').first();
    if (await scaleDownButton.isVisible()) {
      await scaleDownButton.click();
      await page.waitForTimeout(WAIT_AFTER_INTERACTION);
    }

    // Fill in target nodes
    const targetNodesInput = page.locator('input[type="number"]').first();
    if (await targetNodesInput.isVisible()) {
      await targetNodesInput.fill('1000');
      await page.waitForTimeout(300);
    }

    // Check preserve relationships if available
    const preserveCheckbox = page.locator('input[type="checkbox"]').filter({ hasText: /preserve/i }).first();
    if (await preserveCheckbox.isVisible()) {
      await preserveCheckbox.check();
      await page.waitForTimeout(300);
    }

    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, '13-scale-down-complete.png'),
      fullPage: true,
    });
  });

  test('14 - Help text and tooltips', async ({ page }) => {
    // Ensure Scale-Up is selected
    const scaleUpButton = page.locator('button:has-text("Scale Up")').first();
    if (await scaleUpButton.isVisible()) {
      await scaleUpButton.click();
      await page.waitForTimeout(WAIT_AFTER_INTERACTION);
    }

    // Look for info icons or help text
    const infoIcon = page.locator('[data-testid="InfoIcon"], [aria-label*="info"]').first();
    if (await infoIcon.isVisible()) {
      await infoIcon.hover();
      await page.waitForTimeout(800); // Wait for tooltip
    }

    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, '14-help-text.png'),
      fullPage: true,
    });
  });

  test('15 - Error state display', async ({ page }) => {
    // Try to trigger validation error by leaving required field empty
    const scaleUpButton = page.locator('button:has-text("Scale Up")').first();
    if (await scaleUpButton.isVisible()) {
      await scaleUpButton.click();
      await page.waitForTimeout(WAIT_AFTER_INTERACTION);
    }

    // Clear tenant ID if it exists
    const tenantInput = page.locator('input').filter({ hasText: /tenant/i }).first();
    if (await tenantInput.isVisible()) {
      await tenantInput.clear();
      await page.waitForTimeout(300);
    }

    // Try to execute (should show error)
    const executeButton = page.locator('button:has-text("Execute")').first();
    if (await executeButton.isVisible()) {
      await executeButton.click();
      await page.waitForTimeout(1000);
    }

    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, '15-error-state.png'),
      fullPage: true,
    });
  });
});

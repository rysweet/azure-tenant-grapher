import { test, expect } from '@playwright/test';

test.describe('End-to-End Workflow', () => {
  test('complete configuration and build workflow', async ({ page }) => {
    await page.goto('/');

    // Step 1: Configure Azure credentials
    await page.getByRole('tab', { name: /Config/i }).click();

    // Fill in Azure settings
    await page.getByLabel('Tenant ID').fill('12345678-1234-1234-1234-123456789012');
    await page.getByLabel('Client ID').fill('87654321-4321-4321-4321-210987654321');
    await page.getByLabel('Client Secret').fill('test-secret-key');

    // Save configuration
    await page.getByRole('button', { name: /Save Configuration/i }).click();
    await expect(page.getByText(/Configuration saved successfully/i)).toBeVisible();

    // Step 2: Go to Build tab
    await page.getByRole('tab', { name: /Build/i }).click();

    // Tenant ID should be pre-filled from config
    const tenantInput = page.getByLabel('Tenant ID');
    await expect(tenantInput).toHaveValue('12345678-1234-1234-1234-123456789012');

    // Configure build options
    await page.getByRole('checkbox', { name: /Rebuild Edges/i }).check();

    // Set resource limit
    const sliders = await page.getByRole('slider').all();
    await sliders[0].fill('250');
    await expect(page.getByText(/Resource Limit: 250/i)).toBeVisible();

    // Step 3: Generate specification
    await page.getByRole('tab', { name: /Generate Spec/i }).click();

    // Configure spec options
    await page.getByRole('checkbox', { name: /Include IaC Templates/i }).check();

    // Step 4: Generate IaC
    await page.getByRole('tab', { name: /Generate IaC/i }).click();

    // Tenant ID should be pre-filled
    const iacTenantInput = page.getByLabel('Tenant ID');
    await expect(iacTenantInput).toHaveValue('12345678-1234-1234-1234-123456789012');

    // Select Bicep format
    await page.getByLabel('IaC Format').click();
    await page.getByRole('option', { name: 'Bicep' }).click();

    // Enable options
    await page.getByRole('checkbox', { name: /Include Comments/i }).check();
    await page.getByRole('checkbox', { name: /Include Tags/i }).check();

    // Step 5: Check visualization tab
    await page.getByRole('tab', { name: /Visualize/i }).click();

    // Verify query editor is present
    await expect(page.getByText(/Enter a Cypher query/i)).toBeVisible();

    // Check default query is present
    const defaultQuery = 'MATCH (n) RETURN n LIMIT 100';
    await expect(page.getByText(defaultQuery)).toBeVisible();
  });

  test('error handling workflow', async ({ page }) => {
    await page.goto('/');

    // Try to build without configuration
    await page.getByRole('tab', { name: /Build/i }).click();

    // Enter invalid tenant ID
    await page.getByLabel('Tenant ID').fill('not-a-valid-uuid');
    await page.getByRole('button', { name: /Start Build/i }).click();

    // Should show validation error
    await expect(page.getByText(/Invalid Tenant ID format/i)).toBeVisible();

    // Navigate to Generate IaC with invalid input
    await page.getByRole('tab', { name: /Generate IaC/i }).click();

    // Try to generate without tenant ID
    await page.getByRole('button', { name: /Generate IaC/i }).click();
    await expect(page.getByText(/Tenant ID is required/i)).toBeVisible();

    // Navigate to Config and test validation
    await page.getByRole('tab', { name: /Config/i }).click();

    // Enter invalid URIs
    await page.getByLabel('Neo4j URI').clear();
    await page.getByLabel('Neo4j URI').fill('not-a-valid-uri');
    await page.getByRole('button', { name: /Save Configuration/i }).click();

    // Should show validation error
    await expect(page.getByText(/Invalid Neo4j URI format/i)).toBeVisible();
  });

  test('data persistence workflow', async ({ page }) => {
    await page.goto('/');

    // Configure settings in Config tab
    await page.getByRole('tab', { name: /Config/i }).click();

    const testTenantId = '99999999-9999-9999-9999-999999999999';
    await page.getByLabel('Tenant ID').fill(testTenantId);
    await page.getByLabel('Client ID').fill('88888888-8888-8888-8888-888888888888');

    // Save configuration
    await page.getByRole('button', { name: /Save Configuration/i }).click();
    await expect(page.getByText(/Configuration saved successfully/i)).toBeVisible();

    // Navigate to Build tab - tenant ID should be populated
    await page.getByRole('tab', { name: /Build/i }).click();
    await expect(page.getByLabel('Tenant ID')).toHaveValue(testTenantId);

    // Navigate to Generate IaC tab - tenant ID should be populated
    await page.getByRole('tab', { name: /Generate IaC/i }).click();
    await expect(page.getByLabel('Tenant ID')).toHaveValue(testTenantId);

    // Go back to Config tab - settings should persist
    await page.getByRole('tab', { name: /Config/i }).click();
    await expect(page.getByLabel('Tenant ID')).toHaveValue(testTenantId);
    await expect(page.getByLabel('Client ID')).toHaveValue('88888888-8888-8888-8888-888888888888');
  });

  test('export functionality workflow', async ({ page }) => {
    await page.goto('/');

    // Navigate to Config tab
    await page.getByRole('tab', { name: /Config/i }).click();

    // Fill in some configuration
    await page.getByLabel('Tenant ID').fill('11111111-1111-1111-1111-111111111111');
    await page.getByLabel('Client ID').fill('22222222-2222-2222-2222-222222222222');
    await page.getByLabel('Neo4j URI').clear();
    await page.getByLabel('Neo4j URI').fill('bolt://test-server:7687');

    // Save configuration
    await page.getByRole('button', { name: /Save Configuration/i }).click();
    await expect(page.getByText(/Configuration saved successfully/i)).toBeVisible();

    // Check Export button is present
    await expect(page.getByRole('button', { name: /Export Configuration/i })).toBeVisible();

    // Navigate to Visualize tab
    await page.getByRole('tab', { name: /Visualize/i }).click();

    // Check Export button for graph
    await expect(page.getByRole('button', { name: /Export/i })).toBeVisible();
  });

  test('responsive UI workflow', async ({ page }) => {
    // Test at different viewport sizes
    const viewports = [
      { width: 1920, height: 1080, name: 'Desktop' },
      { width: 768, height: 1024, name: 'Tablet' },
      { width: 375, height: 667, name: 'Mobile' },
    ];

    for (const viewport of viewports) {
      await page.setViewportSize({ width: viewport.width, height: viewport.height });
      await page.goto('/');

      // Check that main elements are visible
      await expect(page.locator('h6').first()).toBeVisible();

      // Check tabs are accessible
      await expect(page.getByRole('tab', { name: /Build/i })).toBeVisible();
      await expect(page.getByRole('tab', { name: /Config/i })).toBeVisible();

      // Navigate to a tab
      await page.getByRole('tab', { name: /Config/i }).click();
      await expect(page.getByText('Configuration')).toBeVisible();
    }
  });

  test('keyboard navigation workflow', async ({ page }) => {
    await page.goto('/');

    // Focus on first tab using Tab key
    await page.keyboard.press('Tab');
    await page.keyboard.press('Tab'); // Skip header elements

    // Navigate through tabs using arrow keys
    await page.keyboard.press('ArrowRight');
    await page.keyboard.press('Enter');

    // Should be on Generate Spec tab
    await expect(page.getByText('Generate Specification')).toBeVisible();

    // Tab through form elements
    await page.keyboard.press('Tab');
    await page.keyboard.press('Tab');

    // Toggle checkbox with Space
    await page.keyboard.press('Space');

    // Continue tabbing to buttons
    for (let i = 0; i < 5; i++) {
      await page.keyboard.press('Tab');
    }

    // Should be able to activate button with Enter
    const focusedElement = await page.evaluate(() => document.activeElement?.tagName);
    expect(['BUTTON', 'INPUT']).toContain(focusedElement);
  });
});

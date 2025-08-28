import { test, expect } from '@playwright/test';

test.describe('Azure Tenant Grapher SPA', () => {
  test('should load the application', async ({ page }) => {
    await page.goto('/');
    
    // Check that the main app title is visible
    await expect(page.locator('h6').first()).toContainText('Azure Tenant Grapher');
    
    // Check that navigation tabs are present
    await expect(page.getByRole('tab', { name: /Build/i })).toBeVisible();
    await expect(page.getByRole('tab', { name: /Generate Spec/i })).toBeVisible();
    await expect(page.getByRole('tab', { name: /Generate IaC/i })).toBeVisible();
    await expect(page.getByRole('tab', { name: /Visualize/i })).toBeVisible();
  });

  test('should navigate between tabs', async ({ page }) => {
    await page.goto('/');
    
    // Click on Generate Spec tab
    await page.getByRole('tab', { name: /Generate Spec/i }).click();
    await expect(page.getByText('Generate Specification')).toBeVisible();
    
    // Click on Generate IaC tab
    await page.getByRole('tab', { name: /Generate IaC/i }).click();
    await expect(page.getByText('Generate Infrastructure as Code')).toBeVisible();
    
    // Click on Visualize tab
    await page.getByRole('tab', { name: /Visualize/i }).click();
    await expect(page.getByText('Visualize Graph')).toBeVisible();
    
    // Click on Config tab
    await page.getByRole('tab', { name: /Config/i }).click();
    await expect(page.getByText('Configuration')).toBeVisible();
  });

  test('should validate tenant ID in Build tab', async ({ page }) => {
    await page.goto('/');
    
    // Should be on Build tab by default
    await expect(page.getByText('Build Azure Tenant Graph')).toBeVisible();
    
    // Try to start build without tenant ID
    await page.getByRole('button', { name: /Start Build/i }).click();
    
    // Should show validation error
    await expect(page.getByText(/Tenant ID is required/i)).toBeVisible();
    
    // Enter invalid tenant ID
    await page.getByLabel('Tenant ID').fill('invalid-id');
    await page.getByRole('button', { name: /Start Build/i }).click();
    
    // Should show format validation error
    await expect(page.getByText(/Invalid Tenant ID format/i)).toBeVisible();
  });

  test('should update configuration settings', async ({ page }) => {
    await page.goto('/');
    
    // Navigate to Config tab
    await page.getByRole('tab', { name: /Config/i }).click();
    
    // Fill in Azure credentials
    await page.getByLabel('Tenant ID').fill('12345678-1234-1234-1234-123456789012');
    await page.getByLabel('Client ID').fill('87654321-4321-4321-4321-210987654321');
    await page.getByLabel('Client Secret').fill('test-secret');
    
    // Update Neo4j settings
    await page.getByLabel('Neo4j URI').clear();
    await page.getByLabel('Neo4j URI').fill('bolt://neo4j-server:7687');
    await page.getByLabel('Neo4j Username').clear();
    await page.getByLabel('Neo4j Username').fill('admin');
    
    // Save configuration
    await page.getByRole('button', { name: /Save Configuration/i }).click();
    
    // Should show success message
    await expect(page.getByText(/Configuration saved successfully/i)).toBeVisible();
  });

  test('should toggle password visibility in Config tab', async ({ page }) => {
    await page.goto('/');
    
    // Navigate to Config tab
    await page.getByRole('tab', { name: /Config/i }).click();
    
    // Enter a client secret
    const secretInput = page.getByLabel('Client Secret');
    await secretInput.fill('my-secret-value');
    
    // Secret should be hidden by default
    await expect(secretInput).toHaveAttribute('type', 'password');
    
    // Click visibility toggle
    const visibilityButtons = await page.getByRole('button', { name: /toggle password visibility/i }).all();
    await visibilityButtons[0].click();
    
    // Secret should now be visible
    await expect(secretInput).toHaveAttribute('type', 'text');
  });

  test('should show graph visualization controls', async ({ page }) => {
    await page.goto('/');
    
    // Navigate to Visualize tab
    await page.getByRole('tab', { name: /Visualize/i }).click();
    
    // Check for visualization controls
    await expect(page.getByRole('button', { name: /Execute/i })).toBeVisible();
    await expect(page.getByRole('button', { name: /Zoom In/i })).toBeVisible();
    await expect(page.getByRole('button', { name: /Zoom Out/i })).toBeVisible();
    await expect(page.getByRole('button', { name: /Reset View/i })).toBeVisible();
    await expect(page.getByRole('button', { name: /Export/i })).toBeVisible();
    
    // Check for query input
    await expect(page.getByText(/Enter a Cypher query/i)).toBeVisible();
  });

  test('should have correct IaC format options', async ({ page }) => {
    await page.goto('/');
    
    // Navigate to Generate IaC tab
    await page.getByRole('tab', { name: /Generate IaC/i }).click();
    
    // Click on format selector
    const formatSelector = page.getByLabel('IaC Format');
    await formatSelector.click();
    
    // Check that all format options are available
    await expect(page.getByRole('option', { name: 'Terraform' })).toBeVisible();
    await expect(page.getByRole('option', { name: 'ARM Template' })).toBeVisible();
    await expect(page.getByRole('option', { name: 'Bicep' })).toBeVisible();
    
    // Select Bicep
    await page.getByRole('option', { name: 'Bicep' }).click();
    
    // Check that Bicep is selected
    await expect(formatSelector).toContainText('Bicep');
  });

  test('should have resource limit slider in Build tab', async ({ page }) => {
    await page.goto('/');
    
    // Should be on Build tab by default
    await expect(page.getByText('Build Azure Tenant Graph')).toBeVisible();
    
    // Check that resource limit slider is present and functional
    const sliders = await page.getByRole('slider').all();
    expect(sliders.length).toBeGreaterThan(0);
    
    // The first slider should be the resource limit
    const resourceLimitSlider = sliders[0];
    
    // Check initial value
    await expect(page.getByText(/Resource Limit: \d+/i)).toBeVisible();
    
    // Change slider value
    await resourceLimitSlider.fill('500');
    
    // Check updated value
    await expect(page.getByText(/Resource Limit: 500/i)).toBeVisible();
  });

  test('should have checkboxes for build options', async ({ page }) => {
    await page.goto('/');
    
    // Should be on Build tab by default
    const rebuildCheckbox = page.getByRole('checkbox', { name: /Rebuild Edges/i });
    const skipAADCheckbox = page.getByRole('checkbox', { name: /Skip AAD Import/i });
    
    // Check that checkboxes are present
    await expect(rebuildCheckbox).toBeVisible();
    await expect(skipAADCheckbox).toBeVisible();
    
    // Check initial states
    await expect(rebuildCheckbox).not.toBeChecked();
    await expect(skipAADCheckbox).not.toBeChecked();
    
    // Toggle checkboxes
    await rebuildCheckbox.check();
    await expect(rebuildCheckbox).toBeChecked();
    
    await skipAADCheckbox.check();
    await expect(skipAADCheckbox).toBeChecked();
  });

  test('should have export and copy buttons in Generate Spec tab', async ({ page }) => {
    await page.goto('/');
    
    // Navigate to Generate Spec tab
    await page.getByRole('tab', { name: /Generate Spec/i }).click();
    
    // Check for export and copy buttons (should be disabled initially)
    const exportButton = page.getByRole('button', { name: /Export/i });
    const copyButton = page.getByRole('button', { name: /Copy/i });
    
    await expect(exportButton).toBeVisible();
    await expect(copyButton).toBeVisible();
    await expect(exportButton).toBeDisabled();
    await expect(copyButton).toBeDisabled();
    
    // Check for include options checkboxes
    await expect(page.getByRole('checkbox', { name: /Include Resource Details/i })).toBeVisible();
    await expect(page.getByRole('checkbox', { name: /Include Relationships/i })).toBeVisible();
    await expect(page.getByRole('checkbox', { name: /Include IaC Templates/i })).toBeVisible();
  });
});
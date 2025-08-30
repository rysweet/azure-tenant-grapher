import { test, expect } from '@playwright/test';

test.describe('Toolbar Appearance', () => {
  test('should have black background', async ({ page }) => {
    await page.goto('http://localhost:5173');
    await page.waitForLoadState('networkidle');
    
    // Check that the AppBar/header has black background
    const header = page.locator('header').first();
    const backgroundColor = await header.evaluate((el) => {
      return window.getComputedStyle(el).backgroundColor;
    });
    
    // RGB for black is rgb(0, 0, 0)
    expect(backgroundColor).toBe('rgb(0, 0, 0)');
  });

  test('should have white text in header', async ({ page }) => {
    await page.goto('http://localhost:5173');
    await page.waitForLoadState('networkidle');
    
    // Check that the title text is white
    const title = page.locator('header').locator('text=Azure Tenant Grapher');
    const color = await title.evaluate((el) => {
      return window.getComputedStyle(el).color;
    });
    
    // RGB for white is rgb(255, 255, 255)
    expect(color).toBe('rgb(255, 255, 255)');
  });
});
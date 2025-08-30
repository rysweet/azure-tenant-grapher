import { test } from '@playwright/test';

test('capture specific tab', async ({ page }) => {
  const tabName = process.env.TAB_NAME || 'Visualize';
  
  await page.goto('http://localhost:5173');
  await page.waitForLoadState('networkidle');
  
  // Click on the specified tab
  await page.click(`text=${tabName}`);
  await page.waitForTimeout(2000); // Wait for content to load
  
  const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, -5);
  await page.screenshot({ 
    path: `screenshots/${tabName.toLowerCase().replace(/\s+/g, '-')}-${timestamp}.png`, 
    fullPage: true 
  });
  
  console.log(`✅ Screenshot of ${tabName} tab saved`);
});
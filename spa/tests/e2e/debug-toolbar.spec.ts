import { test, expect } from '@playwright/test';
import fs from 'fs';

test('debug toolbar color', async ({ page }) => {
  let debugOutput = [];
  await page.goto('http://localhost:5173');
  await page.waitForLoadState('networkidle');
  
  // Get all elements that might be the toolbar
  const possibleToolbars = [
    '.MuiAppBar-root',
    '.MuiToolbar-root',
    'header',
    '[role="banner"]',
    'div:has-text("Azure Tenant Grapher")',
  ];
  
  for (const selector of possibleToolbars) {
    const elements = await page.$$(selector);
    for (let i = 0; i < elements.length; i++) {
      const element = elements[i];
      const info = await element.evaluate((el, idx) => {
        const styles = window.getComputedStyle(el);
        return {
          selector: el.className || el.tagName,
          index: idx,
          backgroundColor: styles.backgroundColor,
          backgroundImage: styles.backgroundImage,
          color: styles.color,
          position: styles.position,
          zIndex: styles.zIndex,
          display: styles.display,
          classList: Array.from(el.classList || []),
          tagName: el.tagName,
          textContent: el.textContent?.substring(0, 100),
        };
      }, i);
      
      debugOutput.push(`\n=== Element ${i} matching "${selector}" ===`);
      debugOutput.push(JSON.stringify(info, null, 2));
    }
  }
  
  // Take a screenshot
  await page.screenshot({ path: 'screenshots/debug-toolbar.png', fullPage: false });
  
  // Check what's actually being rendered
  const headerDiv = await page.$('div:has(> div > span:has-text("Azure Tenant Grapher"))');
  if (headerDiv) {
    const bgColor = await headerDiv.evaluate(el => {
      const styles = window.getComputedStyle(el);
      return styles.backgroundColor;
    });
    debugOutput.push('\nDirect header div background: ' + bgColor);
  }
  
  // Write debug output to file
  fs.writeFileSync('toolbar-debug.txt', debugOutput.join('\n'));
  console.log('Debug output written to toolbar-debug.txt');
});
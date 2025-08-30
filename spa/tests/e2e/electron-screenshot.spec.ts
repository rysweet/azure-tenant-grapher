import { test, _electron as electron } from '@playwright/test';
import path from 'path';

test('capture Electron app screenshots', async () => {
  // Launch Electron app
  const electronApp = await electron.launch({
    args: [path.join(__dirname, '../../dist/main/index.js')]
  });
  
  // Get the first window
  const window = await electronApp.firstWindow();
  
  // Wait for app to load
  await window.waitForLoadState('domcontentloaded');
  await window.waitForTimeout(3000);
  
  // Take screenshot of initial state
  await window.screenshot({ path: 'screenshots/electron-status.png' });
  console.log('Status tab screenshot saved');
  
  // Click Visualize tab
  await window.click('text=Visualize');
  await window.waitForTimeout(3000);
  await window.screenshot({ path: 'screenshots/electron-visualize.png' });
  console.log('Visualize tab screenshot saved');
  
  // Click Build tab
  await window.click('text=Build');
  await window.waitForTimeout(2000);
  await window.screenshot({ path: 'screenshots/electron-build.png' });
  console.log('Build tab screenshot saved');
  
  await electronApp.close();
});
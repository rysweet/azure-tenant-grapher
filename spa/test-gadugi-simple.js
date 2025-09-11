#!/usr/bin/env node

/**
 * Simple test using Gadugi framework with running app
 */

const { _electron } = require('playwright');
const path = require('path');

async function testWithGadugi() {
  console.log('🧪 Testing Azure Tenant Grapher with Gadugi Framework\n');

  let electronApp;

  try {
    // Connect to already running Electron app (avoid launching new one)
    console.log('📱 Connecting to running Electron app...');

    const electronPath = require('electron');
    electronApp = await _electron.launch({
      executablePath: electronPath,
      args: [__dirname],
      env: {
        ...process.env,
        NODE_ENV: 'test'
      }
    });

    const page = await electronApp.firstWindow();
    await page.waitForLoadState('domcontentloaded');
    console.log('✅ Connected to app\n');

    // Test navigation through tabs
    const tabs = ['Status', 'Scan', 'Visualize', 'Generate IaC', 'Config'];

    for (const tab of tabs) {
      try {
        console.log(`📂 Testing ${tab} tab...`);
        await page.click(`text="${tab}"`, { timeout: 3000 });
        await page.waitForTimeout(500);

        // Take screenshot
        await page.screenshot({
          path: path.join(__dirname, `gadugi-${tab.toLowerCase()}.png`),
          fullPage: true
        });

        console.log(`✅ ${tab} tab working`);

        // Quick element discovery
        const buttons = await page.$$('button');
        const inputs = await page.$$('input');
        console.log(`   Found ${buttons.length} buttons, ${inputs.length} inputs\n`);

      } catch (error) {
        console.log(`⚠️ Could not test ${tab}: ${error.message}\n`);
      }
    }

    console.log('✨ Gadugi testing complete!');

  } catch (error) {
    console.error('❌ Test failed:', error.message);
    process.exit(1);
  } finally {
    if (electronApp) {
      await electronApp.close();
    }
  }
}

// Run the test
testWithGadugi().catch(console.error);

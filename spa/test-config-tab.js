#!/usr/bin/env node

/**
 * Config Tab Test - Verifies configuration settings are accessible
 */

const { _electron: electron } = require('playwright');
const path = require('path');

async function runConfigTabTest() {
  console.log('🏴‍☠️ ATG Config Tab Test\n');
  console.log('Testing Config tab and settings...');

  const electronApp = await electron.launch({
    args: [path.join(__dirname, '.')],
  });

  const window = await electronApp.firstWindow();
  console.log('✅ Application launched');

  // Wait for UI to load
  await window.waitForSelector('[role="tablist"]', { timeout: 10000 });

  // Navigate to Config tab
  try {
    await window.click('text="Config"', { timeout: 5000 });
    console.log('✅ Clicked Config tab');
    await window.waitForTimeout(2000);
  } catch (e) {
    console.log('⚠️  Config tab not found, trying alternative names...');
    await window.click('text=/Configuration|Settings/i', { timeout: 5000 });
  }

  // Check for configuration elements
  const checks = {
    'Neo4j configuration': 'text=/Neo4j|Database/i',
    'Azure configuration': 'text=/Azure|Tenant/i',
    'App registration': 'text=/App Registration|Client/i',
    'Input fields': 'input',
    'Buttons': 'button',
  };

  const results = [];
  for (const [name, selector] of Object.entries(checks)) {
    try {
      const count = await window.locator(selector).count();
      if (count > 0) {
        console.log(`✅ ${name} found (${count} element(s))`);
        results.push({ name, found: true, count });
      } else {
        console.log(`⚠️  ${name} not found`);
        results.push({ name, found: false, count: 0 });
      }
    } catch (e) {
      console.log(`❌ Error checking ${name}: ${e.message}`);
      results.push({ name, found: false, count: 0 });
    }
  }

  // Check for "Create App Registration" button specifically
  try {
    const createButton = await window.locator('button:has-text("Create App Registration")').first();
    const visible = await createButton.isVisible({ timeout: 3000 });
    if (visible) {
      console.log('✅ "Create App Registration" button found');
    }
  } catch (e) {
    console.log('⚠️  "Create App Registration" button not found');
  }

  // Take screenshot
  await window.screenshot({ path: 'config-tab-test.png', fullPage: true });
  console.log('✅ Screenshot captured: config-tab-test.png');

  await electronApp.close();

  // Pass if we found at least some configuration elements
  const foundCount = results.filter(r => r.found).length;
  if (foundCount >= 2) {
    console.log(`\n🎉 Config tab test PASSED! (${foundCount}/${results.length} checks passed)`);
    return 0;
  } else {
    console.log(`\n❌ Config tab test FAILED - not enough elements found (${foundCount}/${results.length})`);
    return 1;
  }
}

runConfigTabTest()
  .then(code => process.exit(code))
  .catch(error => {
    console.error('\n❌ Config tab test FAILED:', error.message);
    process.exit(1);
  });

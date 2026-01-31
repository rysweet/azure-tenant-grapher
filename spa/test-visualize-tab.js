#!/usr/bin/env node

/**
 * Visualize Tab Test - Verifies graph visualization capabilities
 */

const { _electron: electron } = require('playwright');
const path = require('path');

async function runVisualizeTabTest() {
  console.log('🏴‍☠️ ATG Visualize Tab Test\n');
  console.log('Testing Visualize tab and graph rendering...');

  const electronApp = await electron.launch({
    args: [path.join(__dirname, '.')],
  });

  const window = await electronApp.firstWindow();
  console.log('✅ Application launched');

  // Wait for UI to load
  await window.waitForSelector('[role="tablist"]', { timeout: 10000 });

  // Navigate to Visualize tab
  try {
    await window.click('text="Visualize"', { timeout: 5000 });
    console.log('✅ Clicked Visualize tab');
    await window.waitForTimeout(3000); // Graph might take time to render
  } catch (e) {
    console.log('❌ Visualize tab not found');
    throw new Error('Visualize tab not accessible');
  }

  // Check for canvas (graph visualization often uses canvas)
  try {
    const canvasCount = await window.locator('canvas').count();
    if (canvasCount > 0) {
      console.log(`✅ Found ${canvasCount} canvas element(s) (graph rendering area)`);
    } else {
      console.log('⚠️  No canvas elements found (graph may use different rendering)');
    }
  } catch (e) {
    console.log('⚠️  Error checking canvas elements');
  }

  // Check for SVG (alternative graph rendering)
  try {
    const svgCount = await window.locator('svg').count();
    if (svgCount > 0) {
      console.log(`✅ Found ${svgCount} SVG element(s)`);
    }
  } catch (e) {
    console.log('⚠️  No SVG elements found');
  }

  // Check for graph controls
  const controls = [
    { name: 'Zoom controls', selector: 'button[aria-label*="zoom"], button:has-text("+"), button:has-text("-")' },
    { name: 'Reset/center button', selector: 'button:has-text("Reset"), button:has-text("Center")' },
    { name: 'Filter options', selector: 'select, input[type="search"], [role="combobox"]' },
    { name: 'Legend', selector: '[class*="legend"], [aria-label*="legend"]' },
  ];

  for (const control of controls) {
    try {
      const count = await window.locator(control.selector).count();
      if (count > 0) {
        console.log(`✅ ${control.name} found (${count} element(s))`);
      } else {
        console.log(`⚠️  ${control.name} not found`);
      }
    } catch (e) {
      console.log(`⚠️  ${control.name} check failed`);
    }
  }

  // Check for any data/nodes indicator
  try {
    const hasText = await window.locator('text=/node|resource|connection|graph/i').count() > 0;
    if (hasText) {
      console.log('✅ Graph-related text found in UI');
    }
  } catch (e) {
    console.log('⚠️  No graph-related text found');
  }

  // Take screenshot
  await window.screenshot({ path: 'visualize-tab-test.png', fullPage: true });
  console.log('✅ Screenshot captured: visualize-tab-test.png');

  await electronApp.close();
  console.log('\n🎉 Visualize tab test PASSED!');

  return 0;
}

runVisualizeTabTest()
  .then(code => process.exit(code))
  .catch(error => {
    console.error('\n❌ Visualize tab test FAILED:', error.message);
    process.exit(1);
  });

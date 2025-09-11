#!/usr/bin/env node

/**
 * Test runner for Gadugi Smart UI tests
 */

const { runSmartUITests } = require('@gadugi/agentic-test/dist/runners/SmartUITestRunner');
const path = require('path');

async function main() {
  console.log('🧪 Running Smart UI Tests with Gadugi Framework...\n');

  const screenshotsDir = path.join(__dirname, 'test-screenshots');

  try {
    const results = await runSmartUITests(screenshotsDir);

    console.log('\n📊 Test Results:');
    console.log(`  Total: ${results.total}`);
    console.log(`  ✅ Passed: ${results.passed}`);
    console.log(`  ❌ Failed: ${results.failed}`);
    console.log(`  ⏭️  Skipped: ${results.skipped}`);

    process.exit(results.failed > 0 ? 1 : 0);
  } catch (error) {
    console.error('❌ Test execution failed:', error);
    process.exit(1);
  }
}

// Run the tests
main();

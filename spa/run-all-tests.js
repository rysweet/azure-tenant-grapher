#!/usr/bin/env node

/**
 * Test Suite Runner - Runs all ATG tests in sequence
 */

const { spawn } = require('child_process');
const path = require('path');

const tests = [
  { name: 'Smoke Test', file: 'simple-smoke-test.js', critical: true },
  { name: 'Navigation Test', file: 'test-navigation.js', critical: true },
  { name: 'Status Tab Test', file: 'test-status-tab.js', critical: false },
  { name: 'Scan Workflow Test', file: 'test-scan-workflow.js', critical: false },
  { name: 'Config Tab Test', file: 'test-config-tab.js', critical: false },
  { name: 'Visualize Tab Test', file: 'test-visualize-tab.js', critical: false },
];

const results = [];

function runTest(testFile) {
  return new Promise((resolve) => {
    console.log(`\n${'='.repeat(60)}`);
    console.log(`Running: ${testFile}`);
    console.log('='.repeat(60));

    const testProcess = spawn('node', [testFile], {
      cwd: __dirname,
      stdio: 'inherit'
    });

    testProcess.on('close', (code) => {
      resolve(code === 0);
    });

    testProcess.on('error', (err) => {
      console.error(`Error running test: ${err.message}`);
      resolve(false);
    });
  });
}

async function runAllTests() {
  console.log('🏴‍☠️ ATG Test Suite Runner\n');
  console.log(`Running ${tests.length} tests...\n`);

  for (const test of tests) {
    const passed = await runTest(test.file);
    results.push({
      name: test.name,
      file: test.file,
      critical: test.critical,
      passed
    });

    // If critical test fails, stop
    if (test.critical && !passed) {
      console.log(`\n❌ Critical test failed: ${test.name}`);
      console.log('Stopping test suite.');
      break;
    }
  }

  // Print summary
  console.log(`\n\n${'='.repeat(60)}`);
  console.log('📊 TEST SUITE SUMMARY');
  console.log('='.repeat(60));

  const passed = results.filter(r => r.passed).length;
  const failed = results.filter(r => !r.passed).length;
  const criticalFailed = results.filter(r => !r.passed && r.critical).length;

  results.forEach(result => {
    const icon = result.passed ? '✅' : '❌';
    const critical = result.critical ? ' (CRITICAL)' : '';
    console.log(`${icon} ${result.name}${critical}`);
  });

  console.log(`\nTotal: ${results.length} tests`);
  console.log(`✅ Passed: ${passed}`);
  console.log(`❌ Failed: ${failed}`);

  if (criticalFailed > 0) {
    console.log(`\n❌ ${criticalFailed} critical test(s) failed!`);
    process.exit(1);
  } else if (passed === results.length) {
    console.log('\n🎉 All tests PASSED!');
    process.exit(0);
  } else {
    console.log(`\n⚠️  ${failed} non-critical test(s) failed`);
    process.exit(0); // Still exit 0 if only non-critical tests failed
  }
}

runAllTests().catch(error => {
  console.error('\n❌ Test suite runner failed:', error);
  process.exit(1);
});

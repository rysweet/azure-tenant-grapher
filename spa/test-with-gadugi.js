#!/usr/bin/env node

/**
 * Run tests using Gadugi Agentic Test Framework
 */

const { spawn } = require('child_process');
const path = require('path');

// Setup Gadugi path
console.log('🧪 Running tests with Gadugi Agentic Test Framework...\n');

const gadugiPath = path.join(__dirname, 'node_modules/@gadugi/agentic-test');
const testScript = path.join(gadugiPath, 'dist/runners/SmartUITestRunner.js');

// Check if compiled version exists, otherwise build it
const fs = require('fs');
if (!fs.existsSync(testScript)) {
  console.log('📦 Building Gadugi framework...');
  const build = spawn('npm', ['run', 'build'], {
    cwd: gadugiPath,
    stdio: 'inherit'
  });

  build.on('close', (code) => {
    if (code !== 0) {
      console.error('❌ Failed to build Gadugi framework');
      process.exit(1);
    }
    runTests();
  });
} else {
  runTests();
}

function runTests() {
  // Run the smart UI test
  const test = spawn('node', [testScript], {
    cwd: __dirname,
    stdio: 'inherit',
    env: {
      ...process.env,
      APP_NAME: 'Azure Tenant Grapher'
    }
  });

  test.on('close', (code) => {
    process.exit(code);
  });
}

#!/usr/bin/env node

/**
 * Run tests using Gadugi Agentic Test Framework
 */

const { spawn } = require('child_process');
const path = require('path');

// Clone and setup Gadugi
console.log('🧪 Running tests with Gadugi Agentic Test Framework...\n');

const gadugiPath = path.join(__dirname, 'node_modules/@gadugi/agentic-test');
const testScript = path.join(gadugiPath, 'smart-ui-test.js');

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
#!/usr/bin/env node

/**
 * Quick test runner for the UI testing system
 * Uses require() to bypass TypeScript compilation issues
 */

const path = require('path');
const { spawn } = require('child_process');

// Set up environment
process.env.NODE_ENV = 'test';

console.log('🚀 Starting UI Testing System...\n');

// First, check if the Electron app is running
async function checkElectronApp() {
  return new Promise((resolve) => {
    const check = spawn('pgrep', ['-f', 'electron.*azure-tenant-grapher']);
    check.on('close', (code) => {
      resolve(code === 0);
    });
  });
}

// Launch Electron app if not running
async function launchElectronApp() {
  console.log('📱 Launching Electron application...');

  const electronProcess = spawn('npm', ['start'], {
    cwd: path.resolve(__dirname, '..'),
    detached: true,
    stdio: 'ignore'
  });

  electronProcess.unref();

  // Wait for app to start
  await new Promise(resolve => setTimeout(resolve, 5000));
  console.log('✅ Electron app launched\n');
}

// Run the UI tests
async function runTests() {
  try {
    // Check if app is running
    const isRunning = await checkElectronApp();

    if (!isRunning) {
      await launchElectronApp();
    } else {
      console.log('✅ Electron app already running\n');
    }

    // Load the test scenarios
    const fs = require('fs');
    const yaml = require('js-yaml');

    const scenariosDir = path.join(__dirname, 'scenarios');
    const scenarioFiles = fs.readdirSync(scenariosDir)
      .filter(f => f.endsWith('.yaml') || f.endsWith('.yml'));

    console.log(`📋 Found ${scenarioFiles.length} scenario files\n`);

    // Initialize Playwright
    const { chromium } = require('playwright');
    const { ElectronApplication, _electron } = require('playwright');

    console.log('🎭 Initializing Playwright for Electron...\n');

    // Get the path to the Electron executable
    const electronPath = require('electron');
    const appPath = path.resolve(__dirname, '..');

    // Connect to Electron app
    const electronApp = await _electron.launch({
      executablePath: electronPath,
      args: [appPath],
      env: {
        ...process.env,
        NODE_ENV: 'test'
      }
    });

    // Get the first window
    const window = await electronApp.firstWindow();
    console.log('✅ Connected to Electron window\n');

    // Run test scenarios
    for (const file of scenarioFiles) {
      if (file.includes('ui')) {
        console.log(`\n📝 Running scenarios from ${file}...`);

        const content = fs.readFileSync(path.join(scenariosDir, file), 'utf-8');
        const data = yaml.load(content);

        if (data.scenarios) {
          for (const scenario of data.scenarios) {
            console.log(`\n  🔧 ${scenario.name}`);

            // Execute test steps
            for (const step of scenario.steps || []) {
              try {
                await executeStep(window, step);
                console.log(`    ✅ ${step.description || step.action}`);
              } catch (error) {
                console.log(`    ❌ ${step.description || step.action}: ${error.message}`);
              }
            }
          }
        }
      }
    }

    // Close the app
    await electronApp.close();
    console.log('\n✨ Testing complete!\n');

  } catch (error) {
    console.error('❌ Test failed:', error);
    process.exit(1);
  }
}

// Execute a single test step
async function executeStep(page, step) {
  switch (step.action) {
    case 'navigate':
      // For Electron, navigation is tab switching
      if (step.target && step.target.includes('tab')) {
        const tabName = step.target.replace('tab:', '').trim();
        await page.click(`text="${tabName}"`);
      }
      break;

    case 'click':
      await page.click(step.target);
      break;

    case 'type':
      await page.fill(step.target, step.value || '');
      break;

    case 'wait':
      await page.waitForTimeout(parseInt(step.value) || 1000);
      break;

    case 'waitForElement':
      await page.waitForSelector(step.target, { timeout: 5000 });
      break;

    case 'screenshot':
      const name = step.value || 'screenshot.png';
      await page.screenshot({ path: path.join(__dirname, 'screenshots', name) });
      break;

    case 'assertVisible':
      await page.waitForSelector(step.target, { state: 'visible', timeout: 5000 });
      break;

    case 'assertText':
      const element = await page.$(step.target);
      if (element) {
        const text = await element.textContent();
        if (!text.includes(step.value)) {
          throw new Error(`Expected text "${step.value}" not found`);
        }
      }
      break;

    default:
      console.log(`    ⚠️  Unknown action: ${step.action}`);
  }
}

// Run the tests
runTests().catch(console.error);

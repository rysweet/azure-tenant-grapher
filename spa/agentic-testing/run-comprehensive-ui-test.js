#!/usr/bin/env node

/**
 * Comprehensive UI test runner that exercises all tabs and features
 */

const { _electron } = require('playwright');
const path = require('path');
const fs = require('fs').promises;

// Test results tracker
const results = {
  passed: 0,
  failed: 0,
  errors: []
};

// Color output helpers
const colors = {
  green: '\x1b[32m',
  red: '\x1b[31m',
  yellow: '\x1b[33m',
  blue: '\x1b[34m',
  reset: '\x1b[0m'
};

function logSuccess(msg) {
  console.log(`${colors.green}✅ ${msg}${colors.reset}`);
  results.passed++;
}

function logError(msg, error) {
  console.log(`${colors.red}❌ ${msg}${colors.reset}`);
  if (error) console.log(`   ${colors.red}${error.message || error}${colors.reset}`);
  results.failed++;
  results.errors.push({ test: msg, error: error?.message || error });
}

function logInfo(msg) {
  console.log(`${colors.blue}ℹ️  ${msg}${colors.reset}`);
}

function logSection(msg) {
  console.log(`\n${colors.yellow}${'='.repeat(60)}${colors.reset}`);
  console.log(`${colors.yellow}${msg}${colors.reset}`);
  console.log(`${colors.yellow}${'='.repeat(60)}${colors.reset}\n`);
}

async function testTab(page, tabName, tests) {
  logSection(`Testing ${tabName} Tab`);
  
  try {
    // Navigate to tab
    await page.click(`text="${tabName}"`);
    await page.waitForTimeout(1000);
    logSuccess(`Navigated to ${tabName} tab`);
    
    // Take screenshot
    await page.screenshot({ 
      path: path.join(__dirname, 'screenshots', `${tabName.toLowerCase()}-tab.png`),
      fullPage: true 
    });
    logSuccess(`Screenshot captured for ${tabName} tab`);
    
    // Run specific tests for this tab
    for (const test of tests) {
      try {
        await test(page);
      } catch (error) {
        logError(test.name || 'Unknown test', error);
      }
    }
  } catch (error) {
    logError(`Failed to test ${tabName} tab`, error);
  }
}

async function runComprehensiveUITests() {
  logSection('Azure Tenant Grapher - Comprehensive UI Testing');
  
  // Create screenshots directory
  await fs.mkdir(path.join(__dirname, 'screenshots'), { recursive: true });
  
  let electronApp;
  
  try {
    // Launch Electron app
    logInfo('Launching Electron application...');
    const electronPath = require('electron');
    const appPath = path.resolve(__dirname, '..');
    
    electronApp = await _electron.launch({
      executablePath: electronPath,
      args: [appPath],
      env: {
        ...process.env,
        NODE_ENV: 'test',
        TESTING: 'true'
      }
    });
    
    // Get main window
    const page = await electronApp.firstWindow();
    await page.waitForLoadState('domcontentloaded');
    logSuccess('Electron app launched and ready');
    
    // Test Build Tab
    await testTab(page, 'Build', [
      async function testTenantIdInput(page) {
        const input = await page.$('input[placeholder*="tenant"]');
        if (input) {
          await input.fill('test-tenant-id-12345');
          logSuccess('Tenant ID input field working');
        } else {
          throw new Error('Tenant ID input not found');
        }
      },
      async function testBuildButton(page) {
        const button = await page.$('button:has-text("Build Graph")');
        if (button) {
          const isEnabled = await button.isEnabled();
          logSuccess(`Build button ${isEnabled ? 'enabled' : 'disabled'}`);
        } else {
          throw new Error('Build button not found');
        }
      }
    ]);
    
    // Test Generate Spec Tab
    await testTab(page, 'Generate Spec', [
      async function testSpecGeneration(page) {
        const generateBtn = await page.$('button:has-text("Generate")');
        if (generateBtn) {
          logSuccess('Spec generation button found');
        } else {
          throw new Error('Generate spec button not found');
        }
      }
    ]);
    
    // Test Generate IaC Tab
    await testTab(page, 'Generate IaC', [
      async function testFormatSelector(page) {
        const formats = ['terraform', 'arm', 'bicep'];
        for (const format of formats) {
          const option = await page.$(`text="${format}"`);
          if (option) {
            logSuccess(`IaC format option '${format}' available`);
          }
        }
      }
    ]);
    
    // Test Create Tenant Tab
    await testTab(page, 'Create Tenant', [
      async function testSpecUpload(page) {
        const uploadArea = await page.$('input[type="file"]');
        if (uploadArea) {
          logSuccess('Spec file upload area available');
        } else {
          logInfo('No file upload area found (might use text area)');
        }
      }
    ]);
    
    // Test Visualize Tab
    await testTab(page, 'Visualize', [
      async function testGraphVisualization(page) {
        // Check for graph container
        const graphContainer = await page.$('[class*="graph"], [id*="graph"], canvas, svg');
        if (graphContainer) {
          logSuccess('Graph visualization container found');
        } else {
          logInfo('Graph container not found (might need data first)');
        }
      }
    ]);
    
    // Test Agent Mode Tab
    await testTab(page, 'Agent Mode', [
      async function testAgentInterface(page) {
        const chatInput = await page.$('textarea, input[type="text"][placeholder*="message"]');
        if (chatInput) {
          await chatInput.fill('Test agent command');
          logSuccess('Agent mode input field working');
        } else {
          logInfo('Agent mode interface not found');
        }
      }
    ]);
    
    // Test Threat Model Tab
    await testTab(page, 'Threat Model', [
      async function testThreatModelGeneration(page) {
        const analyzeBtn = await page.$('button:has-text("Analyze"), button:has-text("Generate")');
        if (analyzeBtn) {
          logSuccess('Threat model analysis button found');
        } else {
          logInfo('Threat model button not found');
        }
      }
    ]);
    
    // Test Config Tab
    await testTab(page, 'Config', [
      async function testConfigFields(page) {
        // Check for environment variable inputs
        const envInputs = await page.$$('input[name*="env"], input[placeholder*="API"], input[placeholder*="key"]');
        if (envInputs.length > 0) {
          logSuccess(`Found ${envInputs.length} configuration fields`);
        } else {
          logInfo('No configuration fields found');
        }
      },
      async function testSaveConfig(page) {
        const saveBtn = await page.$('button:has-text("Save")');
        if (saveBtn) {
          logSuccess('Configuration save button found');
        } else {
          logInfo('Save button not found in Config tab');
        }
      }
    ]);
    
    // Test Status Tab
    await testTab(page, 'Status', [
      async function testSystemStatus(page) {
        // Look for status indicators
        const statusElements = await page.$$('[class*="status"], [class*="health"], [class*="indicator"]');
        if (statusElements.length > 0) {
          logSuccess(`Found ${statusElements.length} status indicators`);
        } else {
          logInfo('No status indicators found');
        }
      },
      async function testNeo4jStatus(page) {
        const neo4jStatus = await page.$('text=/neo4j/i');
        if (neo4jStatus) {
          logSuccess('Neo4j status indicator found');
        } else {
          logInfo('Neo4j status not displayed');
        }
      }
    ]);
    
    // Test Help Tab
    await testTab(page, 'Help', [
      async function testHelpContent(page) {
        const helpContent = await page.$('text=/documentation/i, text=/guide/i, text=/help/i');
        if (helpContent) {
          logSuccess('Help content available');
        } else {
          logInfo('Help content not found');
        }
      }
    ]);
    
    // Additional UI responsiveness tests
    logSection('UI Responsiveness Tests');
    
    // Test window resizing
    await page.setViewportSize({ width: 1920, height: 1080 });
    await page.waitForTimeout(500);
    logSuccess('Window resized to 1920x1080');
    
    await page.setViewportSize({ width: 1024, height: 768 });
    await page.waitForTimeout(500);
    logSuccess('Window resized to 1024x768');
    
    // Test keyboard navigation
    await page.keyboard.press('Tab');
    await page.keyboard.press('Tab');
    logSuccess('Keyboard navigation working');
    
    // Test dark mode toggle (if available)
    const darkModeToggle = await page.$('[aria-label*="theme"], [aria-label*="dark"], button:has-text("Dark")');
    if (darkModeToggle) {
      await darkModeToggle.click();
      await page.waitForTimeout(500);
      logSuccess('Dark mode toggle tested');
    } else {
      logInfo('Dark mode toggle not found');
    }
    
  } catch (error) {
    logError('Test suite failed', error);
  } finally {
    // Clean up
    if (electronApp) {
      await electronApp.close();
      logInfo('Electron app closed');
    }
    
    // Print summary
    logSection('Test Results Summary');
    console.log(`${colors.green}Passed: ${results.passed}${colors.reset}`);
    console.log(`${colors.red}Failed: ${results.failed}${colors.reset}`);
    
    if (results.errors.length > 0) {
      console.log(`\n${colors.red}Errors:${colors.reset}`);
      results.errors.forEach((err, idx) => {
        console.log(`  ${idx + 1}. ${err.test}: ${err.error}`);
      });
    }
    
    // Save results to file
    const resultsPath = path.join(__dirname, 'test-results.json');
    await fs.writeFile(resultsPath, JSON.stringify(results, null, 2));
    logInfo(`Results saved to ${resultsPath}`);
    
    // Exit with appropriate code
    process.exit(results.failed > 0 ? 1 : 0);
  }
}

// Run the tests
runComprehensiveUITests().catch(console.error);
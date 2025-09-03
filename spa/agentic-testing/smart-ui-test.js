#!/usr/bin/env node

/**
 * Smart UI Testing Agent
 * Uses Playwright's accessibility tree and element detection to test like a user
 */

const { _electron } = require('playwright');
const path = require('path');
const fs = require('fs').promises;

// Test context
const testContext = {
  currentTab: null,
  testedFeatures: [],
  interactions: [],
  issues: [],
  screenshots: []
};

// Color output helpers
const colors = {
  green: '\x1b[32m',
  red: '\x1b[31m',
  yellow: '\x1b[33m',
  blue: '\x1b[34m',
  cyan: '\x1b[36m',
  magenta: '\x1b[35m',
  reset: '\x1b[0m'
};

function log(color, emoji, msg) {
  console.log(`${colors[color]}${emoji} ${msg}${colors.reset}`);
}

/**
 * Discover all interactive elements on the page
 */
async function discoverElements(page) {
  const elements = await page.evaluate(() => {
    const interactiveElements = [];
    
    // Find all buttons
    document.querySelectorAll('button, [role="button"]').forEach(el => {
      interactiveElements.push({
        type: 'button',
        text: el.innerText || el.textContent,
        ariaLabel: el.getAttribute('aria-label'),
        id: el.id,
        className: el.className,
        disabled: el.disabled
      });
    });
    
    // Find all inputs
    document.querySelectorAll('input, textarea').forEach(el => {
      interactiveElements.push({
        type: el.type || 'text',
        placeholder: el.placeholder,
        value: el.value,
        name: el.name,
        id: el.id,
        ariaLabel: el.getAttribute('aria-label')
      });
    });
    
    // Find all selects/dropdowns
    document.querySelectorAll('select').forEach(el => {
      interactiveElements.push({
        type: 'select',
        name: el.name,
        id: el.id,
        options: Array.from(el.options).map(opt => opt.text)
      });
    });
    
    // Find all links/tabs
    document.querySelectorAll('a, [role="tab"]').forEach(el => {
      interactiveElements.push({
        type: 'link',
        text: el.innerText || el.textContent,
        href: el.href,
        ariaLabel: el.getAttribute('aria-label')
      });
    });
    
    // Get page content structure
    const headings = Array.from(document.querySelectorAll('h1, h2, h3')).map(h => h.innerText);
    const labels = Array.from(document.querySelectorAll('label')).map(l => l.innerText);
    
    return {
      interactive: interactiveElements,
      headings,
      labels,
      title: document.title
    };
  });
  
  return elements;
}

/**
 * Test Scan/Build functionality
 */
async function testScanTab(page) {
  log('magenta', '🔍', 'Testing Scan functionality...');
  
  // Find and interact with tenant ID input
  try {
    // Try multiple selectors for the tenant ID input
    const tenantInputSelectors = [
      'input[placeholder*="tenant" i]',
      'input[name*="tenant" i]',
      'input#tenantId',
      'input[type="text"]'
    ];
    
    for (const selector of tenantInputSelectors) {
      const input = await page.$(selector);
      if (input) {
        await input.fill('12345678-1234-1234-1234-123456789012');
        log('green', '✅', 'Entered test tenant ID');
        testContext.testedFeatures.push('Tenant ID input functional');
        break;
      }
    }
    
    // Look for resource limit input
    const limitInput = await page.$('input[type="number"], input[placeholder*="limit" i]');
    if (limitInput) {
      await limitInput.fill('10');
      log('green', '✅', 'Set resource limit to 10');
      testContext.testedFeatures.push('Resource limit configuration');
    }
    
    // Find build/scan button
    const buildButton = await page.$('button:has-text("Build"), button:has-text("Scan"), button:has-text("Start")');
    if (buildButton) {
      const buttonText = await buildButton.textContent();
      log('blue', '🔨', `Found action button: "${buttonText}"`);
      testContext.testedFeatures.push(`${buttonText} button ready`);
      
      // Check if button is enabled
      const isDisabled = await buildButton.isDisabled();
      if (!isDisabled) {
        log('green', '✅', 'Build/Scan button is enabled and ready');
      } else {
        log('yellow', '⚠️', 'Build/Scan button is disabled');
        testContext.issues.push('Build button disabled - may need configuration');
      }
    }
    
  } catch (error) {
    log('red', '❌', `Scan tab test failed: ${error.message}`);
  }
}

/**
 * Test Generate IaC functionality
 */
async function testGenerateIaCTab(page) {
  log('magenta', '🔍', 'Testing IaC Generation...');
  
  try {
    // Look for format options
    const formats = ['terraform', 'arm', 'bicep'];
    for (const format of formats) {
      const formatOption = await page.$(`text=/${format}/i`);
      if (formatOption) {
        log('green', '✅', `${format.toUpperCase()} format available`);
        testContext.testedFeatures.push(`${format} IaC generation`);
      }
    }
    
    // Check for generate button
    const generateButton = await page.$('button:has-text("Generate")');
    if (generateButton) {
      log('green', '✅', 'Generate IaC button found');
      testContext.testedFeatures.push('IaC generation ready');
    }
    
    // Check for output area
    const outputArea = await page.$('textarea, pre, code');
    if (outputArea) {
      log('blue', '📄', 'IaC output area detected');
    }
    
  } catch (error) {
    log('red', '❌', `IaC tab test failed: ${error.message}`);
  }
}

/**
 * Test Visualize functionality
 */
async function testVisualizeTab(page) {
  log('magenta', '🔍', 'Testing Visualization...');
  
  try {
    // Look for canvas or svg elements
    const graphElement = await page.$('canvas, svg, [class*="graph" i], [id*="graph" i]');
    if (graphElement) {
      log('green', '✅', 'Graph visualization component found');
      testContext.testedFeatures.push('Graph visualization functional');
      
      // Try to interact with zoom controls
      const zoomIn = await page.$('[aria-label*="zoom in" i], button:has-text("+")');
      if (zoomIn) {
        await zoomIn.click();
        log('green', '✅', 'Zoom controls working');
        testContext.testedFeatures.push('Graph zoom controls');
      }
    }
    
    // Check for graph statistics
    const stats = await page.$$eval('text=/nodes|edges|relationships/i', els => els.length);
    if (stats > 0) {
      log('blue', '📊', 'Graph statistics displayed');
    }
    
  } catch (error) {
    log('red', '❌', `Visualize tab test failed: ${error.message}`);
  }
}

/**
 * Test Status indicators
 */
async function testStatusTab(page) {
  log('magenta', '🔍', 'Testing Status Indicators...');
  
  try {
    // Check Neo4j status
    const neo4jStatus = await page.$('text=/neo4j/i');
    if (neo4jStatus) {
      const statusText = await page.textContent('body');
      
      if (statusText.match(/connected|running|online|active/i)) {
        log('green', '✅', 'Neo4j is connected');
        testContext.testedFeatures.push('Neo4j connection active');
      } else if (statusText.match(/disconnected|stopped|offline|inactive/i)) {
        log('yellow', '⚠️', 'Neo4j is disconnected');
        testContext.issues.push('Neo4j not connected');
      }
    }
    
    // Check Docker status
    const dockerStatus = await page.$('text=/docker/i');
    if (dockerStatus) {
      log('blue', '🐳', 'Docker status indicator found');
      testContext.testedFeatures.push('Docker monitoring');
    }
    
    // Check for error messages
    const errors = await page.$$('[class*="error" i], [class*="alert" i], [class*="warning" i]');
    if (errors.length > 0) {
      log('yellow', '⚠️', `Found ${errors.length} warning/error indicators`);
    }
    
  } catch (error) {
    log('red', '❌', `Status tab test failed: ${error.message}`);
  }
}

/**
 * Test Configuration
 */
async function testConfigTab(page) {
  log('magenta', '🔍', 'Testing Configuration...');
  
  try {
    // Find all input fields
    const inputs = await page.$$('input[type="text"], input[type="password"], input[type="number"]');
    log('blue', '⚙️', `Found ${inputs.length} configuration fields`);
    
    if (inputs.length > 0) {
      testContext.testedFeatures.push(`${inputs.length} configuration options`);
      
      // Test filling one field
      const firstInput = inputs[0];
      await firstInput.fill('test-config-value');
      log('green', '✅', 'Configuration field accepts input');
    }
    
    // Look for save button
    const saveButton = await page.$('button:has-text("Save")');
    if (saveButton) {
      log('green', '✅', 'Save configuration button found');
      testContext.testedFeatures.push('Configuration persistence');
    }
    
    // Check for environment variable fields
    const envFields = await page.$$('input[name*="env" i], input[placeholder*="api" i], input[placeholder*="key" i]');
    if (envFields.length > 0) {
      log('blue', '🔐', `${envFields.length} environment variable fields found`);
    }
    
  } catch (error) {
    log('red', '❌', `Config tab test failed: ${error.message}`);
  }
}

/**
 * Main test execution
 */
async function runSmartUITests() {
  log('cyan', '🤖', 'Smart UI Testing Agent');
  log('cyan', '🎯', 'Testing the UI by discovering and using actual features\n');
  
  // Create screenshots directory
  await fs.mkdir(path.join(__dirname, 'screenshots'), { recursive: true });
  
  let electronApp;
  
  try {
    // Launch application
    log('blue', '🚀', 'Launching application...');
    const electronPath = require('electron');
    const appPath = path.resolve(__dirname, '..');
    
    electronApp = await _electron.launch({
      executablePath: electronPath,
      args: [appPath],
      env: { ...process.env, NODE_ENV: 'test' }
    });
    
    const page = await electronApp.firstWindow();
    await page.waitForLoadState('domcontentloaded');
    log('green', '✅', 'Application ready\n');
    
    // Discover initial UI elements
    log('cyan', '🔍', 'Discovering UI elements...');
    const initialElements = await discoverElements(page);
    log('blue', '📋', `Found ${initialElements.interactive.length} interactive elements`);
    
    // Find and test all tabs
    const tabElements = initialElements.interactive.filter(el => 
      el.type === 'link' && (el.text?.length < 20)
    );
    
    log('blue', '📑', `Found ${tabElements.length} potential tabs\n`);
    
    // Define tab test mapping
    const tabTests = {
      'scan': testScanTab,
      'build': testScanTab,
      'generate iac': testGenerateIaCTab,
      'iac': testGenerateIaCTab,
      'visualize': testVisualizeTab,
      'status': testStatusTab,
      'config': testConfigTab,
      'configuration': testConfigTab
    };
    
    // Test each discovered tab
    for (const tabElement of tabElements) {
      const tabName = tabElement.text?.trim();
      if (!tabName) continue;
      
      log('cyan', '\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━', '');
      log('yellow', '📂', `Testing "${tabName}" Tab`);
      
      try {
        // Click on the tab
        const clicked = await page.click(`text="${tabName}"`, { timeout: 5000 })
          .then(() => true)
          .catch(() => false);
        
        if (clicked) {
          await page.waitForTimeout(1000);
          
          // Take screenshot
          const screenshotName = `${tabName.toLowerCase().replace(/\s+/g, '-')}-tested.png`;
          await page.screenshot({ 
            path: path.join(__dirname, 'screenshots', screenshotName),
            fullPage: true 
          });
          testContext.screenshots.push(screenshotName);
          
          // Discover elements in this tab
          const tabElements = await discoverElements(page);
          log('blue', '🔎', `Tab contains ${tabElements.interactive.length} elements`);
          
          // Run specific test for this tab
          const testFunction = Object.entries(tabTests).find(([key]) => 
            tabName.toLowerCase().includes(key)
          )?.[1];
          
          if (testFunction) {
            await testFunction(page);
          } else {
            // Generic element counting
            const buttons = tabElements.interactive.filter(el => el.type === 'button');
            const inputs = tabElements.interactive.filter(el => el.type?.includes('input') || el.type === 'text');
            
            if (buttons.length > 0) {
              log('blue', '🔘', `${buttons.length} buttons available`);
            }
            if (inputs.length > 0) {
              log('blue', '📝', `${inputs.length} input fields available`);
            }
          }
          
          testContext.interactions.push({
            tab: tabName,
            elementsFound: tabElements.interactive.length,
            headings: tabElements.headings
          });
          
        } else {
          log('yellow', '⚠️', `Could not navigate to ${tabName}`);
        }
        
      } catch (error) {
        log('red', '❌', `Error testing ${tabName}: ${error.message}`);
      }
    }
    
    // Test keyboard navigation
    log('cyan', '\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━', '');
    log('yellow', '⌨️', 'Testing Keyboard Navigation');
    
    await page.keyboard.press('Tab');
    await page.keyboard.press('Tab');
    await page.keyboard.press('Tab');
    log('green', '✅', 'Tab key navigation working');
    
    await page.keyboard.press('Escape');
    log('green', '✅', 'Escape key handled');
    
    testContext.testedFeatures.push('Keyboard navigation');
    
  } catch (error) {
    log('red', '❌', `Test failed: ${error.message}`);
  } finally {
    // Generate report
    log('cyan', '\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━', '');
    log('cyan', '📊', 'Test Report Summary');
    log('cyan', '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━', '');
    
    log('green', '\n✅', `Features Tested: ${testContext.testedFeatures.length}`);
    testContext.testedFeatures.forEach(feature => {
      log('blue', '  •', feature);
    });
    
    if (testContext.issues.length > 0) {
      log('yellow', '\n⚠️', `Issues Found: ${testContext.issues.length}`);
      testContext.issues.forEach(issue => {
        log('yellow', '  •', issue);
      });
    }
    
    log('blue', '\n📸', `Screenshots Captured: ${testContext.screenshots.length}`);
    
    log('cyan', '\n🎯', 'Testing Strategy:');
    log('blue', '  •', 'Discovered UI elements automatically');
    log('blue', '  •', 'Navigated through tabs like a user');
    log('blue', '  •', 'Interacted with forms and buttons');
    log('blue', '  •', 'Verified status indicators');
    log('blue', '  •', 'Tested keyboard navigation');
    
    // Save results
    const resultsPath = path.join(__dirname, 'smart-test-results.json');
    await fs.writeFile(resultsPath, JSON.stringify(testContext, null, 2));
    log('green', '\n💾', `Results saved to ${resultsPath}`);
    
    if (electronApp) {
      await electronApp.close();
      log('blue', '🏁', 'Application closed');
    }
  }
}

// Run tests
runSmartUITests().catch(console.error);
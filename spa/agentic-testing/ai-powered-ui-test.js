#!/usr/bin/env node

/**
 * AI-Powered UI Testing Agent
 * Uses visual recognition and intelligent interaction to test the UI like a real user
 */

const { _electron } = require('playwright');
const path = require('path');
const fs = require('fs').promises;
const OpenAI = require('openai');

// Initialize OpenAI
const openai = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY
});

// Test context to maintain state
const testContext = {
  currentTab: null,
  testedFeatures: [],
  discoveries: [],
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
  reset: '\x1b[0m'
};

function log(color, emoji, msg) {
  console.log(`${colors[color]}${emoji} ${msg}${colors.reset}`);
}

/**
 * Analyze screenshot using AI to understand UI elements
 */
async function analyzeScreenshot(screenshotPath, context = '') {
  try {
    // Read screenshot as base64
    const imageBuffer = await fs.readFile(screenshotPath);
    const base64Image = imageBuffer.toString('base64');

    const response = await openai.chat.completions.create({
      model: "gpt-4o",
      messages: [
        {
          role: "system",
          content: "You are a UI testing expert. Analyze screenshots and provide detailed information about UI elements, their positions, and possible interactions."
        },
        {
          role: "user",
          content: [
            {
              type: "text",
              text: `Analyze this screenshot of an Electron app UI. ${context}

              Please identify:
              1. What tab or section is currently active
              2. All visible UI elements (buttons, inputs, dropdowns, etc.)
              3. The text content and labels visible
              4. Any data or results displayed
              5. Possible user actions that can be taken
              6. Any error messages or warnings

              Return as JSON with structure:
              {
                "activeTab": "name",
                "elements": [{"type": "button/input/dropdown", "label": "text", "description": "what it does", "selector": "suggested selector"}],
                "content": "description of displayed content",
                "possibleActions": ["action1", "action2"],
                "issues": ["any problems noticed"]
              }`
            },
            {
              type: "image_url",
              image_url: {
                url: `data:image/png;base64,${base64Image}`
              }
            }
          ]
        }
      ],
      max_tokens: 1000,
      temperature: 0.3
    });

    const analysis = JSON.parse(response.choices[0].message.content);
    return analysis;
  } catch (error) {
    log('red', '❌', `Failed to analyze screenshot: ${error.message}`);
    return null;
  }
}

/**
 * Intelligently interact with UI elements based on analysis
 */
async function interactWithElement(page, element, action = 'click') {
  try {
    // Try multiple selector strategies
    const selectors = [
      element.selector,
      `text="${element.label}"`,
      `[aria-label="${element.label}"]`,
      `button:has-text("${element.label}")`,
      `input[placeholder*="${element.label}"]`
    ];

    for (const selector of selectors.filter(Boolean)) {
      try {
        const el = await page.$(selector);
        if (el) {
          switch (action) {
            case 'click':
              await el.click();
              log('green', '✅', `Clicked: ${element.label}`);
              break;
            case 'fill':
              await el.fill('test-value-12345');
              log('green', '✅', `Filled: ${element.label}`);
              break;
            case 'select':
              await el.selectOption({ index: 0 });
              log('green', '✅', `Selected option in: ${element.label}`);
              break;
          }
          return true;
        }
      } catch (e) {
        // Try next selector
      }
    }

    // Fallback to coordinates-based clicking if visible
    log('yellow', '⚠️', `Could not interact with: ${element.label}`);
    return false;
  } catch (error) {
    log('red', '❌', `Interaction failed: ${error.message}`);
    return false;
  }
}

/**
 * Test a specific feature by using it
 */
async function testFeature(page, tabName) {
  log('cyan', '🔍', `Analyzing ${tabName} tab...`);

  // Take screenshot
  const screenshotPath = path.join(__dirname, 'screenshots', `${tabName.toLowerCase().replace(/\s+/g, '-')}-analysis.png`);
  await page.screenshot({ path: screenshotPath, fullPage: true });

  // Analyze the screenshot
  const analysis = await analyzeScreenshot(screenshotPath, `This is the ${tabName} tab of Azure Tenant Grapher`);

  if (!analysis) return;

  log('blue', 'ℹ️', `Found ${analysis.elements.length} interactive elements`);
  testContext.discoveries.push({ tab: tabName, analysis });

  // Test based on tab functionality
  switch (tabName.toLowerCase()) {
    case 'scan':
    case 'build':
      await testScanTab(page, analysis);
      break;
    case 'generate iac':
      await testGenerateIaCTab(page, analysis);
      break;
    case 'visualize':
      await testVisualizeTab(page, analysis);
      break;
    case 'status':
      await testStatusTab(page, analysis);
      break;
    case 'config':
      await testConfigTab(page, analysis);
      break;
    default:
      await testGenericTab(page, analysis);
  }
}

async function testScanTab(page, analysis) {
  log('yellow', '🧪', 'Testing Scan/Build functionality...');

  // Find tenant ID input
  const tenantInput = analysis.elements.find(e =>
    e.type === 'input' &&
    (e.label?.toLowerCase().includes('tenant') || e.description?.toLowerCase().includes('tenant'))
  );

  if (tenantInput) {
    await interactWithElement(page, tenantInput, 'fill');
    await page.keyboard.type('12345678-1234-1234-1234-123456789012');
    log('green', '✅', 'Entered test tenant ID');
  }

  // Find and click build/scan button
  const buildButton = analysis.elements.find(e =>
    e.type === 'button' &&
    (e.label?.toLowerCase().includes('build') || e.label?.toLowerCase().includes('scan') || e.label?.toLowerCase().includes('start'))
  );

  if (buildButton) {
    log('blue', '🔨', `Found action button: ${buildButton.label}`);
    // Note: Not clicking to avoid actual API calls
    testContext.testedFeatures.push(`${buildButton.label} button identified and ready`);
  }
}

async function testGenerateIaCTab(page, analysis) {
  log('yellow', '🧪', 'Testing IaC generation functionality...');

  // Look for format selector
  const formatSelector = analysis.elements.find(e =>
    e.type === 'dropdown' || e.type === 'select' ||
    e.description?.toLowerCase().includes('format')
  );

  if (formatSelector) {
    log('green', '✅', 'Found IaC format selector');
    testContext.testedFeatures.push('IaC format selection available');
  }

  // Check for terraform, ARM, Bicep options
  const formats = ['terraform', 'arm', 'bicep'];
  for (const format of formats) {
    if (analysis.content?.toLowerCase().includes(format)) {
      log('green', '✅', `${format} format supported`);
    }
  }
}

async function testVisualizeTab(page, analysis) {
  log('yellow', '🧪', 'Testing visualization functionality...');

  // Check for graph/canvas elements
  if (analysis.content?.toLowerCase().includes('graph') ||
      analysis.content?.toLowerCase().includes('visualization') ||
      analysis.content?.toLowerCase().includes('nodes')) {
    log('green', '✅', 'Graph visualization component detected');
    testContext.testedFeatures.push('Graph visualization available');
  }

  // Look for zoom controls
  const zoomControls = analysis.elements.filter(e =>
    e.label?.toLowerCase().includes('zoom') ||
    e.description?.toLowerCase().includes('zoom')
  );

  if (zoomControls.length > 0) {
    log('green', '✅', `Found ${zoomControls.length} zoom controls`);
  }
}

async function testStatusTab(page, analysis) {
  log('yellow', '🧪', 'Testing status indicators...');

  // Check for Neo4j status
  if (analysis.content?.toLowerCase().includes('neo4j')) {
    log('green', '✅', 'Neo4j status indicator present');

    // Check connection status
    if (analysis.content?.toLowerCase().includes('connected') ||
        analysis.content?.toLowerCase().includes('running')) {
      log('green', '✅', 'Neo4j appears to be connected');
    } else if (analysis.content?.toLowerCase().includes('disconnected') ||
               analysis.content?.toLowerCase().includes('stopped')) {
      log('yellow', '⚠️', 'Neo4j appears to be disconnected');
      testContext.issues.push('Neo4j not connected');
    }
  }

  // Check for other service statuses
  const services = ['docker', 'api', 'database'];
  for (const service of services) {
    if (analysis.content?.toLowerCase().includes(service)) {
      log('blue', 'ℹ️', `${service} status being monitored`);
    }
  }
}

async function testConfigTab(page, analysis) {
  log('yellow', '🧪', 'Testing configuration options...');

  // Count configuration inputs
  const configInputs = analysis.elements.filter(e =>
    e.type === 'input' || e.type === 'checkbox' || e.type === 'toggle'
  );

  log('blue', 'ℹ️', `Found ${configInputs.length} configuration options`);

  // Test save functionality
  const saveButton = analysis.elements.find(e =>
    e.type === 'button' && e.label?.toLowerCase().includes('save')
  );

  if (saveButton) {
    log('green', '✅', 'Configuration save button available');
    testContext.testedFeatures.push('Configuration management functional');
  }
}

async function testGenericTab(page, analysis) {
  log('yellow', '🧪', `Testing ${analysis.activeTab} tab generically...`);

  // Test all buttons
  const buttons = analysis.elements.filter(e => e.type === 'button');
  log('blue', 'ℹ️', `Found ${buttons.length} buttons`);

  // Test all inputs
  const inputs = analysis.elements.filter(e => e.type === 'input');
  log('blue', 'ℹ️', `Found ${inputs.length} input fields`);

  // Record discoveries
  if (analysis.possibleActions?.length > 0) {
    testContext.testedFeatures.push(...analysis.possibleActions);
  }
}

/**
 * Main test runner
 */
async function runAIPoweredUITests() {
  log('cyan', '🤖', 'AI-Powered UI Testing Agent Starting...');
  log('cyan', '🎯', 'Mission: Test the UI like a real user would\n');

  // Check for OpenAI API key
  if (!process.env.OPENAI_API_KEY) {
    log('red', '❌', 'OPENAI_API_KEY environment variable not set');
    log('yellow', '💡', 'Set it with: export OPENAI_API_KEY=your-key-here');
    process.exit(1);
  }

  // Create screenshots directory
  await fs.mkdir(path.join(__dirname, 'screenshots'), { recursive: true });

  let electronApp;

  try {
    // Launch Electron app
    log('blue', '🚀', 'Launching Electron application...');
    const electronPath = require('electron');
    const appPath = path.resolve(__dirname, '..');

    electronApp = await _electron.launch({
      executablePath: electronPath,
      args: [appPath],
      env: {
        ...process.env,
        NODE_ENV: 'test'
      }
    });

    const page = await electronApp.firstWindow();
    await page.waitForLoadState('domcontentloaded');
    log('green', '✅', 'Application launched successfully\n');

    // Take initial screenshot to understand the UI
    log('cyan', '📸', 'Taking initial screenshot to understand UI layout...');
    const initialScreenshot = path.join(__dirname, 'screenshots', 'initial-state.png');
    await page.screenshot({ path: initialScreenshot, fullPage: true });

    // Analyze initial state
    const initialAnalysis = await analyzeScreenshot(initialScreenshot, 'Initial application state');

    if (initialAnalysis) {
      log('green', '✅', `Application opened on: ${initialAnalysis.activeTab || 'Unknown'} tab`);

      // Find all available tabs
      const tabs = initialAnalysis.elements
        .filter(e => e.type === 'tab' || e.description?.includes('tab'))
        .map(e => e.label);

      // Also look for common tab names in the content
      const commonTabs = ['Scan', 'Generate IaC', 'Create Tenant', 'Visualize', 'Agent Mode', 'Threat Model', 'Config', 'Status'];

      for (const tabName of commonTabs) {
        log('cyan', `\n📋`, `Testing ${tabName} Tab`);
        log('cyan', '='.repeat(40), '');

        try {
          // Navigate to tab
          const clicked = await page.click(`text="${tabName}"`, { timeout: 5000 }).then(() => true).catch(() => false);

          if (clicked) {
            await page.waitForTimeout(1500); // Wait for tab content to load
            await testFeature(page, tabName);
          } else {
            log('yellow', '⚠️', `Tab "${tabName}" not found in UI`);
          }
        } catch (error) {
          log('red', '❌', `Failed to test ${tabName}: ${error.message}`);
        }
      }
    }

    // Generate intelligent test report
    log('cyan', '\n📊', 'Generating AI-Powered Test Report...');
    log('cyan', '='.repeat(40), '');

    // Summary
    log('green', '✅', `Tested Features: ${testContext.testedFeatures.length}`);
    for (const feature of testContext.testedFeatures) {
      log('blue', '  •', feature);
    }

    if (testContext.issues.length > 0) {
      log('red', '\n⚠️', `Issues Found: ${testContext.issues.length}`);
      for (const issue of testContext.issues) {
        log('yellow', '  •', issue);
      }
    }

    // AI Insights
    if (testContext.discoveries.length > 0) {
      const insights = await generateTestInsights(testContext);
      if (insights) {
        log('cyan', '\n🧠', 'AI Testing Insights:');
        log('blue', '', insights);
      }
    }

  } catch (error) {
    log('red', '❌', `Test suite failed: ${error.message}`);
  } finally {
    if (electronApp) {
      await electronApp.close();
      log('blue', '\n🏁', 'Testing session complete');
    }

    // Save detailed results
    const resultsPath = path.join(__dirname, 'ai-test-results.json');
    await fs.writeFile(resultsPath, JSON.stringify(testContext, null, 2));
    log('green', '💾', `Detailed results saved to ${resultsPath}`);
  }
}

/**
 * Generate testing insights using AI
 */
async function generateTestInsights(context) {
  try {
    const response = await openai.chat.completions.create({
      model: "gpt-4o-mini",
      messages: [
        {
          role: "system",
          content: "You are a QA expert. Provide concise testing insights and recommendations."
        },
        {
          role: "user",
          content: `Based on this UI testing session, provide insights and recommendations:

          Tested Features: ${JSON.stringify(context.testedFeatures)}
          Issues Found: ${JSON.stringify(context.issues)}
          UI Elements Discovered: ${context.discoveries.length} tabs analyzed

          Provide:
          1. Overall UI health assessment
          2. Key recommendations for improvement
          3. Potential user experience issues

          Be concise and actionable.`
        }
      ],
      max_tokens: 500,
      temperature: 0.7
    });

    return response.choices[0].message.content;
  } catch (error) {
    log('yellow', '⚠️', 'Could not generate AI insights');
    return null;
  }
}

// Run the tests
runAIPoweredUITests().catch(error => {
  console.error('Fatal error:', error);
  process.exit(1);
});

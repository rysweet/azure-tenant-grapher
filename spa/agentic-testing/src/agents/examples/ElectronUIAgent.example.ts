/**
 * ElectronUIAgent Usage Examples
 * 
 * This file demonstrates various usage patterns for the ElectronUIAgent
 * in different testing scenarios.
 */

import { ElectronUIAgent } from '../ElectronUIAgent';
import { TestScenario, TestStep, Priority, TestInterface } from '../../models/TestModels';
import { LogLevel } from '../../utils/logger';

/**
 * Example 1: Basic Azure Tenant Grapher SPA Test
 */
async function basicSpaTest(): Promise<void> {
  const agent = new ElectronUIAgent({
    executablePath: '/path/to/azure-tenant-grapher/dist/main.js',
    args: ['--no-sandbox', '--disable-dev-shm-usage'],
    defaultTimeout: 15000,
    screenshotConfig: {
      mode: 'on',
      directory: './screenshots/spa-tests',
      fullPage: true
    },
    websocketConfig: {
      url: 'http://localhost:3001',
      events: ['log', 'progress', 'status', 'error'],
      reconnectAttempts: 3,
      reconnectDelay: 1000
    },
    performanceConfig: {
      enabled: true,
      sampleInterval: 2000,
      collectLogs: true
    }
  });

  try {
    // Initialize the agent
    await agent.initialize();
    
    // Launch the Electron app
    await agent.launch();
    
    // Navigate to Build tab and start a build
    await agent.clickTab('Build');
    await agent.fillInput('[data-testid="tenant-id-input"]', process.env.AZURE_TENANT_ID || 'test-tenant');
    
    // Configure build options
    await agent.clickButton('[data-testid="include-users-checkbox"]');
    await agent.clickButton('[data-testid="include-groups-checkbox"]');
    
    // Start the build
    await agent.clickButton('[data-testid="start-build-button"]');
    
    // Wait for build to complete (or progress to show)
    await agent.waitForElement('[data-testid="build-progress"]', { timeout: 30000 });
    
    // Capture final state
    const finalState = await agent.captureState();
    console.log('Build completed, final state captured');
    
    // Take a success screenshot
    await agent.screenshot('build-completed-successfully');
    
  } catch (error: any) {
    console.error('Test failed:', error?.message);
    await agent.screenshot('test-failure');
    throw error;
    
  } finally {
    await agent.close();
    await agent.cleanup();
  }
}

/**
 * Example 2: Full Scenario Execution
 */
async function fullScenarioTest(): Promise<void> {
  const agent = new ElectronUIAgent({
    executablePath: '/path/to/azure-tenant-grapher/dist/main.js',
    screenshotConfig: {
      mode: 'only-on-failure',
      directory: './screenshots/scenario-tests',
      fullPage: true
    }
  });

  // Define a complete test scenario
  const scenario: TestScenario = {
    id: 'spa-build-workflow',
    name: 'SPA Build Workflow Test',
    description: 'Complete workflow test for Azure Tenant Grapher SPA',
    priority: Priority.HIGH,
    interface: TestInterface.GUI,
    prerequisites: ['AZURE_TENANT_ID environment variable'],
    estimatedDuration: 120,
    tags: ['ui', 'build', 'integration'],
    enabled: true,
    steps: [
      {
        action: 'launch_electron',
        target: '',
        description: 'Launch the Electron application'
      },
      {
        action: 'click_tab',
        target: 'Build',
        description: 'Navigate to Build tab'
      },
      {
        action: 'fill',
        target: '[data-testid="tenant-id-input"]',
        value: process.env.AZURE_TENANT_ID || 'test-tenant',
        description: 'Enter tenant ID'
      },
      {
        action: 'click',
        target: '[data-testid="start-build-button"]',
        description: 'Start the build process'
      },
      {
        action: 'wait_for_element',
        target: '[data-testid="build-success-message"]',
        timeout: 300000, // 5 minutes
        description: 'Wait for build completion'
      },
      {
        action: 'screenshot',
        target: 'build-completion-status',
        description: 'Capture final build status'
      }
    ],
    verifications: [],
    expectedOutcome: 'Build completes successfully with success message displayed'
  };

  try {
    await agent.initialize();
    const result = await agent.execute(scenario);
    
    console.log('Scenario execution result:');
    console.log('- Status:', result.status);
    console.log('- Duration:', result.duration, 'ms');
    console.log('- Screenshots:', result.screenshots?.length || 0);
    console.log('- Performance samples:', result.performanceSamples?.length || 0);
    
    return result;
    
  } catch (error: any) {
    console.error('Scenario execution failed:', error?.message);
    throw error;
  }
}

/**
 * Example 3: Multi-Tab Navigation Test
 */
async function multiTabNavigationTest(): Promise<void> {
  const agent = new ElectronUIAgent({
    executablePath: '/path/to/azure-tenant-grapher/dist/main.js',
    defaultTimeout: 10000
  });

  try {
    await agent.initialize();
    await agent.launch();
    
    // Test navigation across different tabs
    const tabs = ['Build', 'Generate Spec', 'Generate IaC', 'Visualize', 'Agent Mode'];
    
    for (const tab of tabs) {
      console.log(`Testing navigation to ${tab} tab`);
      
      // Navigate to tab
      await agent.clickTab(tab);
      
      // Take screenshot of each tab
      await agent.screenshot(`tab-${tab.toLowerCase().replace(' ', '-')}`);
      
      // Capture state for each tab
      const state = await agent.captureState();
      console.log(`${tab} tab loaded, title: ${state.title}`);
      
      // Wait a bit between navigations
      await new Promise(resolve => setTimeout(resolve, 1000));
    }
    
    console.log('Multi-tab navigation test completed successfully');
    
  } finally {
    await agent.close();
    await agent.cleanup();
  }
}

/**
 * Example 4: Performance Monitoring Test
 */
async function performanceMonitoringTest(): Promise<void> {
  const agent = new ElectronUIAgent({
    executablePath: '/path/to/azure-tenant-grapher/dist/main.js',
    performanceConfig: {
      enabled: true,
      sampleInterval: 500, // Sample every 500ms
      collectLogs: true
    }
  });

  try {
    await agent.initialize();
    await agent.launch();
    
    // Perform some intensive operations
    await agent.clickTab('Build');
    await agent.fillInput('[data-testid="tenant-id-input"]', 'performance-test-tenant');
    
    // Enable all options for maximum load
    await agent.clickButton('[data-testid="include-users-checkbox"]');
    await agent.clickButton('[data-testid="include-groups-checkbox"]');
    await agent.clickButton('[data-testid="include-applications-checkbox"]');
    
    // Start build and monitor performance
    console.log('Starting build with performance monitoring...');
    await agent.clickButton('[data-testid="start-build-button"]');
    
    // Wait for some time to collect performance data
    await new Promise(resolve => setTimeout(resolve, 30000)); // 30 seconds
    
    // Capture final state with performance metrics
    const finalState = await agent.captureState();
    
    console.log('Performance test completed:');
    console.log('- CPU Usage:', finalState.performance?.cpuUsage);
    console.log('- Memory Usage:', finalState.performance?.memoryUsage);
    console.log('- Response Time:', finalState.performance?.responseTime);
    
  } finally {
    await agent.close();
    await agent.cleanup();
  }
}

/**
 * Example 5: Error Handling and Recovery
 */
async function errorHandlingTest(): Promise<void> {
  const agent = new ElectronUIAgent({
    executablePath: '/path/to/azure-tenant-grapher/dist/main.js',
    recoveryConfig: {
      maxRetries: 3,
      retryDelay: 2000,
      restartOnFailure: false
    },
    screenshotConfig: {
      mode: 'on', // Capture all screenshots to see recovery process
      directory: './screenshots/error-handling',
      fullPage: true
    }
  });

  try {
    await agent.initialize();
    await agent.launch();
    
    // Intentionally try to interact with non-existent elements
    try {
      await agent.clickButton('[data-testid="non-existent-button"]');
    } catch (error: any) {
      console.log('Expected error caught:', error?.message);
      await agent.screenshot('after-expected-error');
    }
    
    // Try to fill a non-existent input
    try {
      await agent.fillInput('[data-testid="non-existent-input"]', 'test value');
    } catch (error: any) {
      console.log('Expected error caught:', error?.message);
      await agent.screenshot('after-second-expected-error');
    }
    
    // Recover by performing valid actions
    await agent.clickTab('Build');
    await agent.screenshot('recovered-to-build-tab');
    
    console.log('Error handling test completed - recovery successful');
    
  } finally {
    await agent.close();
    await agent.cleanup();
  }
}

/**
 * Example 6: WebSocket Event Monitoring
 */
async function websocketMonitoringTest(): Promise<void> {
  const agent = new ElectronUIAgent({
    executablePath: '/path/to/azure-tenant-grapher/dist/main.js',
    websocketConfig: {
      url: 'http://localhost:3001',
      events: ['log', 'progress', 'status', 'error'],
      reconnectAttempts: 5,
      reconnectDelay: 2000
    }
  });

  // Set up event listeners
  agent.on('websocket_connected', () => {
    console.log('WebSocket connected successfully');
  });

  agent.on('websocket_event', (event) => {
    console.log(`WebSocket event [${event.type}]:`, event.data);
  });

  agent.on('websocket_disconnected', () => {
    console.log('WebSocket disconnected');
  });

  try {
    await agent.initialize();
    await agent.launch();
    
    // Start a build process to generate WebSocket events
    await agent.clickTab('Build');
    await agent.fillInput('[data-testid="tenant-id-input"]', 'websocket-test-tenant');
    await agent.clickButton('[data-testid="start-build-button"]');
    
    // Wait for events to be generated
    await new Promise(resolve => setTimeout(resolve, 10000)); // Wait 10 seconds
    
    // Capture state to see collected events
    const state = await agent.captureState();
    console.log('WebSocket events collected:', state.customData?.websocketEventCount);
    
  } finally {
    await agent.close();
    await agent.cleanup();
  }
}

/**
 * Example 7: Custom Step Execution
 */
async function customStepExecutionTest(): Promise<void> {
  const agent = new ElectronUIAgent({
    executablePath: '/path/to/azure-tenant-grapher/dist/main.js'
  });

  try {
    await agent.initialize();
    
    // Execute custom steps
    const steps: TestStep[] = [
      { action: 'launch_electron', target: '', description: 'Launch app' },
      { action: 'wait', value: '2000', target: '', description: 'Wait 2 seconds' },
      { action: 'click_tab', target: 'Config', description: 'Go to config tab' },
      { action: 'screenshot', target: 'config-tab-loaded', description: 'Capture config tab' },
      { action: 'get_text', target: '[data-testid="version-info"]', description: 'Get version' }
    ];

    for (let i = 0; i < steps.length; i++) {
      const step = steps[i];
      console.log(`Executing step ${i + 1}: ${step.description}`);
      
      const result = await agent.executeStep(step, i);
      
      console.log(`Step ${i + 1} result:`, result.status);
      if (result.actualResult) {
        console.log(`Step ${i + 1} output:`, result.actualResult);
      }
      
      if (result.status === 'FAILED') {
        console.error(`Step ${i + 1} failed:`, result.error);
        break;
      }
    }
    
  } finally {
    await agent.close();
    await agent.cleanup();
  }
}

// Export all examples for use in other files
export {
  basicSpaTest,
  fullScenarioTest,
  multiTabNavigationTest,
  performanceMonitoringTest,
  errorHandlingTest,
  websocketMonitoringTest,
  customStepExecutionTest
};

// Main execution if run directly
if (require.main === module) {
  console.log('Running ElectronUIAgent examples...');
  
  // Uncomment the example you want to run:
  
  // basicSpaTest().catch(console.error);
  // fullScenarioTest().catch(console.error);
  // multiTabNavigationTest().catch(console.error);
  // performanceMonitoringTest().catch(console.error);
  // errorHandlingTest().catch(console.error);
  // websocketMonitoringTest().catch(console.error);
  // customStepExecutionTest().catch(console.error);
  
  console.log('Examples ready to run. Uncomment the desired example in the main section.');
}
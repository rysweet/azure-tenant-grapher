# ElectronUIAgent

A comprehensive Electron UI testing agent built on Playwright's Electron support for the TypeScript Agentic Testing System.

## Overview

The `ElectronUIAgent` provides complete automation capabilities for testing Electron applications, including:

- **Playwright Electron Integration**: Native support for launching and controlling Electron apps
- **Socket.IO Event Monitoring**: Real-time monitoring of application events
- **Performance Metrics Collection**: CPU, memory, and response time tracking
- **Automatic Screenshot Capture**: On failures, state changes, and on-demand
- **Multi-window Support**: Handle multiple windows and contexts
- **IPC Communication**: Monitor Electron main/renderer process communication
- **Console Log Capture**: Collect and categorize console messages
- **Comprehensive Error Handling**: With automatic recovery and retry mechanisms

## Quick Start

```typescript
import { ElectronUIAgent } from './ElectronUIAgent';

// Create agent instance
const agent = new ElectronUIAgent({
  executablePath: '/path/to/your/electron/app',
  args: ['--no-sandbox', '--disable-dev-shm-usage'],
  defaultTimeout: 10000,
  screenshotConfig: {
    mode: 'only-on-failure',
    directory: './screenshots',
    fullPage: true
  }
});

// Initialize and use
await agent.initialize();
await agent.launch();

// Perform UI actions
await agent.clickTab('Build');
await agent.fillInput('[data-testid="tenant-id"]', 'my-tenant-id');
await agent.clickButton('[data-testid="start-build"]');

// Wait for elements
await agent.waitForElement('[data-testid="build-complete"]');

// Capture state
const state = await agent.captureState();

// Clean up
await agent.close();
await agent.cleanup();
```

## Configuration

### ElectronUIAgentConfig

```typescript
interface ElectronUIAgentConfig {
  // Application settings
  executablePath: string;           // Path to Electron executable (required)
  args?: string[];                  // Command line arguments
  cwd?: string;                     // Working directory
  env?: Record<string, string>;     // Environment variables
  
  // Timing settings
  launchTimeout?: number;           // Launch timeout (default: 30000ms)
  defaultTimeout?: number;          // Default operation timeout (default: 10000ms)
  slowMo?: number;                  // Slow motion delay
  
  // Display settings
  headless?: boolean;               // Run in headless mode (default: false)
  
  // Recording settings
  recordVideo?: boolean;            // Record video of test execution
  videoDir?: string;                // Video output directory
  
  // Screenshot settings
  screenshotConfig?: {
    mode: 'off' | 'on' | 'only-on-failure';  // When to capture screenshots
    directory: string;                        // Screenshot directory
    fullPage: boolean;                        // Capture full page
  };
  
  // Socket.IO monitoring
  websocketConfig?: {
    url: string;                    // Socket.IO server URL
    events: string[];               // Events to monitor
    reconnectAttempts: number;      // Reconnection attempts
    reconnectDelay: number;         // Delay between reconnections
  };
  
  // Performance monitoring
  performanceConfig?: {
    enabled: boolean;               // Enable performance monitoring
    sampleInterval: number;         // Sample collection interval (ms)
    collectLogs: boolean;           // Collect console logs
  };
  
  // Recovery settings
  recoveryConfig?: {
    maxRetries: number;             // Maximum retry attempts
    retryDelay: number;             // Delay between retries
    restartOnFailure: boolean;      // Restart app on failure
  };
}
```

## Core Methods

### Application Lifecycle

#### `initialize(): Promise<void>`
Initialize the agent and validate configuration.

```typescript
await agent.initialize();
```

#### `launch(): Promise<void>`
Launch the Electron application with configured settings.

```typescript
await agent.launch();
```

#### `close(): Promise<void>`
Close the Electron application gracefully.

```typescript
await agent.close();
```

#### `cleanup(): Promise<void>`
Clean up all resources and export final data.

```typescript
await agent.cleanup();
```

### UI Interaction Methods

#### `clickTab(tabName: string): Promise<void>`
Navigate to a specific tab in the application.

```typescript
// Try multiple selector strategies automatically
await agent.clickTab('Build');
await agent.clickTab('Generate IaC');
```

#### `fillInput(selector: string, value: string): Promise<void>`
Fill an input field with the specified value.

```typescript
await agent.fillInput('[data-testid="tenant-id"]', 'my-tenant-id');
await agent.fillInput('#email', 'test@example.com');
```

#### `clickButton(selector: string): Promise<void>`
Click a button or clickable element.

```typescript
await agent.clickButton('[data-testid="submit-btn"]');
await agent.clickButton('button:has-text("Start Build")');
```

#### `waitForElement(selector: string, options?: WaitOptions): Promise<Locator>`
Wait for an element to appear with specified state.

```typescript
// Wait for element to be visible (default)
await agent.waitForElement('[data-testid="result"]');

// Wait with custom timeout and state
await agent.waitForElement('[data-testid="loading"]', {
  state: 'hidden',
  timeout: 30000
});
```

#### `getElementText(selector: string): Promise<string>`
Get the text content of an element.

```typescript
const message = await agent.getElementText('[data-testid="status-message"]');
console.log('Status:', message);
```

### State Management

#### `captureState(): Promise<AppState>`
Capture the current application state including screenshot, performance metrics, and metadata.

```typescript
const state = await agent.captureState();
console.log('Current URL:', state.url);
console.log('Memory usage:', state.performance?.memoryUsage);
```

#### `screenshot(name: string): Promise<ScreenshotMetadata>`
Take a screenshot with the specified name.

```typescript
const screenshot = await agent.screenshot('after-login');
console.log('Screenshot saved:', screenshot.filePath);
```

### Test Step Execution

#### `executeStep(step: TestStep, stepIndex: number): Promise<StepResult>`
Execute a single test step with comprehensive error handling.

```typescript
const step: TestStep = {
  action: 'click',
  target: '[data-testid="submit-btn"]',
  description: 'Click submit button'
};

const result = await agent.executeStep(step, 0);
console.log('Step result:', result.status);
```

#### `execute(scenario: TestScenario): Promise<TestResult>`
Execute a complete test scenario with all steps.

```typescript
const scenario = {
  id: 'login-test',
  name: 'User Login Test',
  steps: [
    { action: 'launch', target: '' },
    { action: 'fill', target: '#username', value: 'testuser' },
    { action: 'fill', target: '#password', value: 'password' },
    { action: 'click', target: '#login-btn' }
  ]
};

const result = await agent.execute(scenario);
```

## Supported Test Actions

The agent supports various actions through the `executeStep` method:

| Action | Description | Parameters |
|--------|-------------|------------|
| `launch` / `launch_electron` | Launch the Electron app | - |
| `close` / `close_app` | Close the application | - |
| `click_tab` | Navigate to a specific tab | `target`: tab name |
| `click` / `click_button` | Click an element | `target`: selector |
| `fill` / `type` | Fill input field | `target`: selector, `value`: text |
| `wait_for_element` | Wait for element | `target`: selector, `timeout`: ms |
| `get_text` | Get element text | `target`: selector |
| `screenshot` | Take screenshot | `target`: name |
| `wait` | Wait for specified time | `value`: milliseconds |
| `navigate` | Navigate to URL | `target`: URL |

## Event Monitoring

### Socket.IO Events

The agent can monitor Socket.IO connections for real-time events:

```typescript
const agent = new ElectronUIAgent({
  executablePath: '/path/to/app',
  websocketConfig: {
    url: 'http://localhost:3001',
    events: ['log', 'progress', 'status'],
    reconnectAttempts: 3,
    reconnectDelay: 1000
  }
});

// Events are automatically captured and stored
agent.on('websocket_event', (event) => {
  console.log('Socket.IO event:', event.type, event.data);
});
```

### Console Monitoring

All console messages are automatically captured and categorized:

```typescript
// Console messages are stored and can be retrieved
const logs = agent.getScenarioLogs();
console.log('Error logs:', logs.filter(log => log.includes('[error]')));
```

## Performance Monitoring

Performance metrics are collected at regular intervals:

```typescript
const agent = new ElectronUIAgent({
  executablePath: '/path/to/app',
  performanceConfig: {
    enabled: true,
    sampleInterval: 1000,  // Collect every second
    collectLogs: true
  }
});

// Performance data is automatically collected
const state = await agent.captureState();
console.log('CPU usage:', state.performance?.cpuUsage);
console.log('Memory usage:', state.performance?.memoryUsage);
```

## Screenshot Management

Screenshots are automatically organized and managed:

```typescript
const agent = new ElectronUIAgent({
  executablePath: '/path/to/app',
  screenshotConfig: {
    mode: 'only-on-failure',    // 'off', 'on', 'only-on-failure'
    directory: './screenshots/electron',
    fullPage: true
  }
});

// Screenshots are taken automatically on:
// - Test failures
// - State changes
// - Manual requests via screenshot() method
```

## Error Handling and Recovery

The agent provides comprehensive error handling:

### Automatic Screenshot on Failures
- Screenshots are automatically captured when steps fail
- Failure context is preserved for debugging

### Retry Mechanisms
```typescript
const agent = new ElectronUIAgent({
  executablePath: '/path/to/app',
  recoveryConfig: {
    maxRetries: 3,
    retryDelay: 1000,
    restartOnFailure: false
  }
});
```

### Custom Error Types
- `InitializationError`: Agent initialization failures
- `LaunchError`: Application launch failures
- `InteractionError`: UI interaction failures

## Data Export

The agent automatically exports collected data:

- **Performance Data**: `performance_[timestamp].json`
- **WebSocket Events**: `websocket_events_[timestamp].json`
- **State Snapshots**: `state_snapshots_[timestamp].json`
- **Screenshot Metadata**: `screenshots_[timestamp].json`

All data is exported to `./logs/electron-agent-exports/` on cleanup.

## Advanced Usage

### Multiple Windows Support

```typescript
// The agent automatically handles the first window
// Additional windows can be accessed via Playwright's API
const windows = await agent.app?.windows();
if (windows && windows.length > 1) {
  const secondWindow = windows[1];
  // Interact with second window
}
```

### Custom Selectors

The agent supports various selector strategies:

```typescript
// Data test IDs (recommended)
await agent.clickButton('[data-testid="submit-btn"]');

// Text content
await agent.clickButton('button:has-text("Submit")');

// CSS selectors
await agent.clickButton('#submit-button');

// XPath (through Playwright)
await agent.clickButton('xpath=//button[@id="submit"]');
```

### Conditional Actions

```typescript
// Wait for specific conditions
await agent.waitForElement('[data-testid="loading"]', { 
  state: 'hidden',
  timeout: 30000 
});

// Check element text
const text = await agent.getElementText('[data-testid="status"]');
if (text.includes('Success')) {
  await agent.clickButton('[data-testid="continue"]');
}
```

## Integration with Test Scenarios

The agent integrates seamlessly with YAML test scenarios:

```yaml
# electron-test.yaml
name: "Electron App Test"
agents:
  - name: "ui-agent"
    type: "ui"
    config:
      executablePath: "/path/to/app"
      screenshotConfig:
        mode: "only-on-failure"

steps:
  - name: "Launch App"
    agent: "ui-agent"
    action: "launch_electron"
    
  - name: "Navigate to Build Tab"
    agent: "ui-agent"
    action: "click_tab"
    params:
      target: "Build"
```

## Best Practices

1. **Use Data Test IDs**: Use `data-testid` attributes for reliable element selection
2. **Set Appropriate Timeouts**: Configure timeouts based on your app's performance
3. **Enable Screenshot on Failures**: Always capture screenshots for debugging
4. **Monitor Performance**: Enable performance monitoring for long-running tests
5. **Clean Up Resources**: Always call `cleanup()` in test teardown
6. **Use Descriptive Names**: Name screenshots and state captures descriptively
7. **Handle Dialogs**: The agent auto-accepts dialogs, but consider custom handling

## Troubleshooting

### Common Issues

1. **Application Won't Launch**
   - Verify `executablePath` is correct and executable exists
   - Check that required dependencies are installed
   - Ensure proper permissions

2. **Element Not Found**
   - Use `waitForElement` instead of immediate clicks
   - Verify selectors in the actual application
   - Try multiple selector strategies

3. **Socket.IO Connection Fails**
   - Verify Socket.IO server is running
   - Check URL and port configuration
   - Ensure firewall/network allows connections

4. **Performance Monitoring Issues**
   - Reduce `sampleInterval` if causing performance problems
   - Disable if not needed for your tests
   - Check available memory for data storage

### Debug Mode

Enable debug logging for detailed information:

```typescript
import { LogLevel } from '../utils/logger';

const agent = new ElectronUIAgent({
  executablePath: '/path/to/app'
});

// Set debug level logging
agent.logger.setLevel(LogLevel.DEBUG);
```

## API Reference

For complete API documentation, see the TypeScript definitions in:
- `ElectronUIAgent.ts` - Main agent implementation
- `../models/TestModels.ts` - Test step and result interfaces
- `../models/AppState.ts` - Application state interfaces
- `../utils/screenshot.ts` - Screenshot management utilities
- `../utils/logger.ts` - Logging utilities
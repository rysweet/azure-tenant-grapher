# Agentic Testing System - Utilities

This directory contains comprehensive utility modules for the TypeScript Agentic Testing System. Each utility is designed to handle specific aspects of test automation and management.

## Available Utilities

### 1. Logger (`logger.ts`)

Winston-based logging system with configurable levels, formats, and outputs.

```typescript
import { createLogger, LogLevel, defaultLogger } from './logger';

// Create a custom logger
const logger = createLogger({
  level: LogLevel.DEBUG,
  logDir: './logs',
  enableConsole: true,
  enableFile: true
});

// Use the logger
logger.info('Test started');
logger.error('Test failed', { scenarioId: 'test-001' });

// Set logging context
logger.setContext({ scenarioId: 'test-001', component: 'ui-test' });

// Log test-specific events
logger.scenarioStart('test-001', 'Login Test');
logger.stepExecution(0, 'click', '#login-button');
logger.scenarioEnd('test-001', 'passed', 5000);
```

### 2. YAML Parser (`yamlParser.ts`)

Parse and validate YAML test scenarios with variable substitution and includes.

```typescript
import { YamlParser, loadScenariosFromFile } from './yamlParser';

// Load scenarios from a file
const scenarios = await loadScenariosFromFile('./scenarios/login.yaml', {
  env: process.env,
  global: { baseUrl: 'http://localhost:3000' },
  scenario: { username: 'testuser' }
});

// Parse inline YAML
const parser = new YamlParser();
const scenario = parser.parseScenario(`
id: test-001
name: Login Test
description: Test user login functionality
priority: HIGH
interface: GUI
steps:
  - action: navigate
    target: \${global.baseUrl}/login
  - action: type
    target: '#username'
    value: \${scenario.username}
`);
```

### 3. Configuration (`config.ts`)

Load and manage configuration from environment variables and files.

```typescript
import { ConfigManager, loadDefaultConfig } from './config';

// Load default configuration
const config = await loadDefaultConfig();

// Create a custom config manager
const configManager = new ConfigManager({
  execution: {
    maxParallel: 5,
    defaultTimeout: 60000
  }
});

// Load from file
await configManager.loadFromFile('./test.config.yaml');

// Load from environment
configManager.loadFromEnvironment();

// Get configuration values
const maxParallel = configManager.get('execution.maxParallel');
const logLevel = configManager.get('logging.level', 'info');

// Watch for changes
const unwatch = configManager.watch((newConfig) => {
  console.log('Configuration updated:', newConfig);
});
```

### 4. Retry Logic (`retry.ts`)

Robust retry mechanisms with exponential backoff and circuit breaker patterns.

```typescript
import {
  RetryManager,
  CircuitBreaker,
  retryWithBackoff,
  RetryStrategy
} from './retry';

// Simple retry with exponential backoff
const result = await retryWithBackoff(async () => {
  // Your operation that might fail
  return await fetch('/api/data');
}, {
  maxAttempts: 3,
  initialDelay: 1000,
  strategy: RetryStrategy.EXPONENTIAL
});

// Advanced retry manager
const retry = new RetryManager({
  maxAttempts: 5,
  initialDelay: 500,
  strategy: RetryStrategy.EXPONENTIAL,
  shouldRetry: (error) => error.message.includes('timeout'),
  onRetry: (error, attempt, delay) => {
    console.log(`Retry attempt ${attempt} in ${delay}ms: ${error.message}`);
  }
});

const data = await retry.execute(async () => {
  return await performNetworkRequest();
});

// Circuit breaker
const circuitBreaker = new CircuitBreaker({
  failureThreshold: 5,
  resetTimeout: 60000,
  onCircuitOpen: () => console.log('Circuit breaker opened'),
  onCircuitClose: () => console.log('Circuit breaker closed')
});

const protectedResult = await circuitBreaker.execute(async () => {
  return await unreliableService();
});
```

### 5. Screenshot Management (`screenshot.ts`)

Capture, organize, and manage screenshots using Playwright.

```typescript
import { ScreenshotManager, createScreenshotManager } from './screenshot';
import { Page } from 'playwright';

// Create screenshot manager
const screenshotManager = createScreenshotManager({
  baseDir: './screenshots',
  strategy: 'by-scenario',
  includeTimestamp: true
});

// Capture page screenshot
const metadata = await screenshotManager.capturePageScreenshot(page, {
  scenarioId: 'test-001',
  stepIndex: 0,
  description: 'Login page loaded'
});

// Capture element screenshot
const button = page.locator('#submit-button');
await screenshotManager.captureElementScreenshot(button, {
  scenarioId: 'test-001',
  stepIndex: 1,
  description: 'Submit button highlighted'
});

// Capture before/after comparison
const { before, after } = await screenshotManager.captureComparison(
  page,
  async () => {
    await page.click('#toggle-theme');
  },
  { description: 'Theme toggle' }
);

// Compare screenshots
const comparison = await screenshotManager.compareScreenshots(
  before.filePath,
  after.filePath,
  0.1 // 10% difference threshold
);

console.log(`Screenshots match: ${comparison.matches}`);
console.log(`Difference: ${comparison.differencePercentage}%`);
```

### 6. File Utilities (`fileUtils.ts`)

Comprehensive file system operations for test artifact management.

```typescript
import { FileUtils, ensureDir, readJson, writeJson } from './fileUtils';

// Basic operations
await ensureDir('./test-results');
await FileUtils.copy('./templates', './test-data', true);

const testData = await readJson<TestData>('./config/test-data.json');
await writeJson('./results/summary.json', testResults);

// Advanced file operations
const files = await FileUtils.findFiles(['**/*.log', '**/*.json'], {
  cwd: './test-results',
  ignore: ['**/node_modules/**']
});

// Cleanup old files
const cleanup = await FileUtils.cleanup('./screenshots', {
  maxAge: 7 * 24 * 60 * 60 * 1000, // 7 days
  includePatterns: ['**/*.png', '**/*.jpg'],
  excludePatterns: ['**/baseline/**'],
  removeEmptyDirs: true
});

console.log(`Deleted ${cleanup.deletedFiles.length} files`);

// Sync directories
const sync = await FileUtils.sync('./source', './destination', {
  deleteExtra: true,
  useChecksum: true,
  exclude: ['**/*.tmp']
});

// Get directory size
const size = await FileUtils.getDirectorySize('./test-results');
console.log(`Directory size: ${Math.round(size / 1024 / 1024)} MB`);
```

## Integration Example

Here's how to use multiple utilities together in a test scenario:

```typescript
import {
  createLogger,
  YamlParser,
  ScreenshotManager,
  RetryManager,
  FileUtils
} from './utils';

// Set up utilities
const logger = createLogger({ level: 'debug' });
const yamlParser = new YamlParser();
const screenshotManager = new ScreenshotManager();
const retry = new RetryManager({ maxAttempts: 3 });

export async function runTestScenario(scenarioFile: string) {
  // Load test scenario
  const scenarios = await yamlParser.loadScenarios(scenarioFile);

  for (const scenario of scenarios) {
    logger.scenarioStart(scenario.id, scenario.name);

    try {
      // Execute with retry logic
      await retry.execute(async () => {
        for (const [index, step] of scenario.steps.entries()) {
          logger.stepExecution(index, step.action, step.target);

          // Capture screenshot before action
          await screenshotManager.capturePageScreenshot(page, {
            scenarioId: scenario.id,
            stepIndex: index,
            description: `Before: ${step.description}`
          });

          // Execute step
          await executeStep(step);

          // Capture screenshot after action
          await screenshotManager.capturePageScreenshot(page, {
            scenarioId: scenario.id,
            stepIndex: index,
            description: `After: ${step.description}`
          });

          logger.stepComplete(index, 'passed', 1000);
        }
      });

      logger.scenarioEnd(scenario.id, 'passed', Date.now() - startTime);
    } catch (error) {
      logger.error(`Scenario failed: ${error.message}`, {
        scenarioId: scenario.id,
        error: error.stack
      });
      logger.scenarioEnd(scenario.id, 'failed', Date.now() - startTime);
    }
  }

  // Export results
  const results = screenshotManager.getRunStatistics();
  await FileUtils.writeJsonFile('./results/test-run.json', results);
}
```

## Error Handling

All utilities include comprehensive error handling with custom error types:

- `YamlParseError` - YAML parsing issues
- `ValidationError` - Data validation failures
- `ConfigError` - Configuration loading problems
- `FileOperationError` - File system operation failures

Each error includes context information to help with debugging and provides actionable error messages.

## Type Safety

All utilities are fully typed with TypeScript interfaces and enums for better IDE support and compile-time error checking. The utilities integrate seamlessly with the main test models defined in `../models/`.

## Performance Considerations

- The logger uses async file operations and buffering
- Screenshot operations include deduplication based on file hashes
- File utilities use streaming for large file operations
- Retry mechanisms include jitter to prevent thundering herd problems
- Configuration loading is cached and supports hot reloading

// Jest setup file for Agentic Testing System

// Extend Jest timeout for long-running integration tests
jest.setTimeout(60000);

// Mock external services by default
jest.mock('@octokit/rest');
jest.mock('socket.io-client');

// Global test utilities
global.console = {
  ...console,
  // Suppress console.log in tests unless explicitly needed
  log: jest.fn(),
  debug: jest.fn(),
  info: jest.fn(),
  warn: console.warn,
  error: console.error,
};

// Setup test environment variables
process.env.NODE_ENV = 'test';
process.env.LOG_LEVEL = 'error';

// Mock Playwright browser for tests that don't need real browser
jest.mock('playwright', () => ({
  chromium: {
    launch: jest.fn(() => Promise.resolve({
      newContext: jest.fn(() => Promise.resolve({
        newPage: jest.fn(() => Promise.resolve({
          goto: jest.fn(),
          click: jest.fn(),
          fill: jest.fn(),
          waitForSelector: jest.fn(),
          close: jest.fn(),
        })),
        close: jest.fn(),
      })),
      close: jest.fn(),
    })),
  },
}));

// Cleanup after each test
afterEach(() => {
  jest.clearAllMocks();
});

// Global teardown
afterAll(async () => {
  // Clean up any persistent connections or resources
  await new Promise(resolve => setTimeout(resolve, 100));
});
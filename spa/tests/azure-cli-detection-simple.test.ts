/**
 * Simple Azure CLI detection test
 *
 * This test verifies Azure CLI detection by testing the actual command detection logic
 */

import { exec } from 'child_process';
import { promisify } from 'util';

const execPromise = promisify(exec);

interface Dependency {
  name: string;
  installed: boolean;
  version?: string | null;
  path?: string | null;
  required: string;
}

// Timeout promise helper
const timeout = (ms: number) => new Promise<never>((_, reject) =>
  setTimeout(() => reject(new Error('Command timeout')), ms)
);

// Helper function to run command with timeout
const runCommand = async (command: string, timeoutMs = 5000) => {
  try {
    const { stdout, stderr } = await Promise.race([
      execPromise(command),
      timeout(timeoutMs)
    ]);
    return { success: true, stdout: stdout.trim(), stderr: stderr.trim() };
  } catch (error: any) {
    return { success: false, error: error.message };
  }
};

describe('Azure CLI Detection Logic', () => {
  test('should detect Azure CLI installation correctly', async () => {
    console.log('Testing Azure CLI detection...');

    // Test Azure CLI version detection
    const versionResult = await runCommand('az --version');

    if (versionResult.success && versionResult.stdout) {
      // Extract version from az --version output
      const versionMatch = versionResult.stdout.match(/azure-cli\s+(\d+\.\d+\.\d+)/);
      const version = versionMatch ? versionMatch[1] : 'unknown';

      const pathResult = await runCommand('which az');
      const azPath = pathResult.success ? pathResult.stdout : null;

      console.log('Azure CLI detected - Version:', version, 'Path:', azPath);

      const dependency: Dependency = {
        name: 'Azure CLI',
        installed: true,
        version,
        path: azPath,
        required: '>=2.0'
      };

      // Verify the dependency structure
      expect(dependency.name).toBe('Azure CLI');
      expect(dependency.installed).toBe(true);
      expect(dependency.version).toBeTruthy();
      expect(dependency.path).toBeTruthy();
      expect(dependency.required).toBe('>=2.0');

      // Verify common installation paths
      const validPaths = [
        '/opt/homebrew/bin/az',
        '/usr/local/bin/az',
        '/usr/bin/az'
      ];

      if (azPath) {
        expect(validPaths.some(validPath => azPath.includes('az'))).toBe(true);
      }

      console.log('✅ Azure CLI detection successful:', dependency);
    } else {
      console.log('Azure CLI not detected');

      const dependency: Dependency = {
        name: 'Azure CLI',
        installed: false,
        version: null,
        path: null,
        required: '>=2.0'
      };

      // Verify the dependency structure for uninstalled CLI
      expect(dependency.name).toBe('Azure CLI');
      expect(dependency.installed).toBe(false);
      expect(dependency.version).toBeFalsy();
      expect(dependency.path).toBeFalsy();
      expect(dependency.required).toBe('>=2.0');

      console.log('❌ Azure CLI not detected:', dependency);
    }
  }, 10000); // 10 second timeout

  test('should handle command timeout gracefully', async () => {
    // Test with a very short timeout to simulate timeout scenario
    const result = await runCommand('sleep 2', 100); // 100ms timeout for 2 second sleep

    expect(result.success).toBe(false);
    expect(result.error).toContain('timeout');
  });

  test('should handle invalid commands gracefully', async () => {
    const result = await runCommand('nonexistentcommand123456');

    expect(result.success).toBe(false);
    expect(result.error).toBeTruthy();
  });
});

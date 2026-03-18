/**
 * TDD Tests for Platform Utilities Module
 *
 * Tests Windows/Unix cross-platform compatibility utilities including:
 * - Platform detection (isWindows, getPlatformName)
 * - Python venv path resolution
 * - NPX command resolution
 * - Shell command configuration
 * - Azure CLI detection
 * - Version parsing
 *
 * @remarks
 * These tests use Jest's mocking capabilities to simulate both Windows and Unix
 * environments on any platform. Tests verify:
 * - Correct platform detection
 * - Platform-specific path resolution
 * - Command variants (npx.cmd vs npx, where vs which)
 * - Shell options (cmd.exe vs /bin/bash)
 *
 * @testing-strategy
 * - Mock process.platform to test both Windows and Unix paths
 * - Test boundary conditions (null, empty strings)
 * - Verify exact path formats match platform conventions
 * - Test Azure CLI detection fallback chain
 */

import {
  isWindows,
  getPlatformName,
  getPythonVenvActivatePath,
  getNpxCommand,
  getShellCommand,
  findAzureCli,
  parseVersion,
  ShellCommand,
} from './platform-utils';
import { execSync } from 'child_process';
import { existsSync } from 'fs';

// Mock Node.js modules
jest.mock('child_process');
jest.mock('fs');

const mockedExecSync = execSync as jest.MockedFunction<typeof execSync>;
const mockedExistsSync = existsSync as jest.MockedFunction<typeof existsSync>;

describe('Platform Utilities - TDD Tests', () => {
  // Store original platform
  const originalPlatform = process.platform;

  /**
   * Helper to mock process.platform
   */
  function mockPlatform(platform: NodeJS.Platform) {
    Object.defineProperty(process, 'platform', {
      value: platform,
      configurable: true,
    });
  }

  /**
   * Restore original platform after each test
   */
  afterEach(() => {
    Object.defineProperty(process, 'platform', {
      value: originalPlatform,
      configurable: true,
    });
    jest.clearAllMocks();
  });

  describe('Platform Detection', () => {
    describe('isWindows()', () => {
      test('should return true when platform is win32', () => {
        mockPlatform('win32');
        expect(isWindows()).toBe(true);
      });

      test('should return false when platform is darwin', () => {
        mockPlatform('darwin');
        expect(isWindows()).toBe(false);
      });

      test('should return false when platform is linux', () => {
        mockPlatform('linux');
        expect(isWindows()).toBe(false);
      });

      test('should return false for other Unix-like platforms', () => {
        mockPlatform('freebsd');
        expect(isWindows()).toBe(false);
      });
    });

    describe('getPlatformName()', () => {
      test('should return "win32" on Windows', () => {
        mockPlatform('win32');
        expect(getPlatformName()).toBe('win32');
      });

      test('should return "darwin" on macOS', () => {
        mockPlatform('darwin');
        expect(getPlatformName()).toBe('darwin');
      });

      test('should return "linux" on Linux', () => {
        mockPlatform('linux');
        expect(getPlatformName()).toBe('linux');
      });
    });
  });

  describe('Path Resolution', () => {
    describe('getPythonVenvActivatePath()', () => {
      test('should return Scripts\\activate.bat path on Windows', () => {
        mockPlatform('win32');
        const venvPath = 'C:\\Users\\test\\venv';
        const result = getPythonVenvActivatePath(venvPath);

        expect(result).toContain('Scripts');
        expect(result).toContain('activate.bat');
        expect(result).toMatch(/Scripts[\\/]activate\.bat$/);
      });

      test('should return bin/activate path on Unix', () => {
        mockPlatform('darwin');
        const venvPath = '/home/user/venv';
        const result = getPythonVenvActivatePath(venvPath);

        expect(result).toContain('bin');
        expect(result).toContain('activate');
        expect(result).toMatch(/bin[\/\\]activate$/);
        expect(result).not.toContain('.bat');
      });

      test('should handle relative paths on Windows', () => {
        mockPlatform('win32');
        const venvPath = '.venv';
        const result = getPythonVenvActivatePath(venvPath);

        expect(result).toContain('Scripts');
        expect(result).toContain('activate.bat');
      });

      test('should handle relative paths on Unix', () => {
        mockPlatform('linux');
        const venvPath = '.venv';
        const result = getPythonVenvActivatePath(venvPath);

        expect(result).toContain('bin');
        expect(result).toContain('activate');
      });
    });

    describe('getNpxCommand()', () => {
      test('should return "npx.cmd" on Windows', () => {
        mockPlatform('win32');
        expect(getNpxCommand()).toBe('npx.cmd');
      });

      test('should return "npx" on Unix (darwin)', () => {
        mockPlatform('darwin');
        expect(getNpxCommand()).toBe('npx');
      });

      test('should return "npx" on Unix (linux)', () => {
        mockPlatform('linux');
        expect(getNpxCommand()).toBe('npx');
      });
    });
  });

  describe('Command Resolution', () => {
    describe('getShellCommand()', () => {
      test('should return cmd.exe configuration on Windows', () => {
        mockPlatform('win32');
        const command = 'echo "Hello"';
        const result: ShellCommand = getShellCommand(command);

        expect(result).toEqual({
          shell: 'cmd.exe',
          args: ['/c', command],
        });
      });

      test('should return bash configuration on Unix', () => {
        mockPlatform('darwin');
        const command = 'ls -la';
        const result: ShellCommand = getShellCommand(command);

        expect(result).toEqual({
          shell: '/bin/bash',
          args: ['-c', command],
        });
      });

      test('should handle complex commands on Windows', () => {
        mockPlatform('win32');
        const command = 'dir /s && echo "Done"';
        const result = getShellCommand(command);

        expect(result.shell).toBe('cmd.exe');
        expect(result.args).toEqual(['/c', command]);
      });

      test('should handle complex commands on Unix', () => {
        mockPlatform('linux');
        const command = 'find . -name "*.ts" | grep test';
        const result = getShellCommand(command);

        expect(result.shell).toBe('/bin/bash');
        expect(result.args).toEqual(['-c', command]);
      });

      test('should handle empty command string', () => {
        mockPlatform('win32');
        const result = getShellCommand('');

        expect(result.shell).toBe('cmd.exe');
        expect(result.args).toEqual(['/c', '']);
      });
    });
  });

  describe('Azure CLI Detection', () => {
    describe('findAzureCli()', () => {
      test('should find az via PATH on Windows', () => {
        mockPlatform('win32');
        mockedExecSync.mockReturnValue('C:\\Program Files\\az.cmd\n');
        mockedExistsSync.mockReturnValue(true);

        const result = findAzureCli();

        expect(result).toBe('C:\\Program Files\\az.cmd');
        expect(mockedExecSync).toHaveBeenCalledWith('where az', { encoding: 'utf-8' });
      });

      test('should find az via PATH on Unix', () => {
        mockPlatform('darwin');
        mockedExecSync.mockReturnValue('/usr/local/bin/az\n');
        mockedExistsSync.mockReturnValue(true);

        const result = findAzureCli();

        expect(result).toBe('/usr/local/bin/az');
        expect(mockedExecSync).toHaveBeenCalledWith('which az', { encoding: 'utf-8' });
      });

      test('should check standard Windows locations when not in PATH', () => {
        mockPlatform('win32');
        mockedExecSync.mockImplementation(() => {
          throw new Error('Command not found');
        });

        // First path exists
        mockedExistsSync.mockImplementation((path) => {
          return path === 'C:\\Program Files\\Microsoft SDKs\\Azure\\CLI2\\wbin\\az.cmd';
        });

        const result = findAzureCli();

        expect(result).toBe('C:\\Program Files\\Microsoft SDKs\\Azure\\CLI2\\wbin\\az.cmd');
      });

      test('should check x86 location on Windows when standard fails', () => {
        mockPlatform('win32');
        mockedExecSync.mockImplementation(() => {
          throw new Error('Command not found');
        });

        // x86 path exists
        mockedExistsSync.mockImplementation((path) => {
          return path === 'C:\\Program Files (x86)\\Microsoft SDKs\\Azure\\CLI2\\wbin\\az.cmd';
        });

        const result = findAzureCli();

        expect(result).toBe('C:\\Program Files (x86)\\Microsoft SDKs\\Azure\\CLI2\\wbin\\az.cmd');
      });

      test('should check standard Unix locations when not in PATH', () => {
        mockPlatform('linux');
        mockedExecSync.mockImplementation(() => {
          throw new Error('Command not found');
        });

        // /usr/local/bin/az exists
        mockedExistsSync.mockImplementation((path) => {
          return path === '/usr/local/bin/az';
        });

        const result = findAzureCli();

        expect(result).toBe('/usr/local/bin/az');
      });

      test('should check /opt/az/bin/az on Unix', () => {
        mockPlatform('darwin');
        mockedExecSync.mockImplementation(() => {
          throw new Error('Command not found');
        });

        mockedExistsSync.mockImplementation((path) => {
          return path === '/opt/az/bin/az';
        });

        const result = findAzureCli();

        expect(result).toBe('/opt/az/bin/az');
      });

      test('should check /usr/bin/az on Unix', () => {
        mockPlatform('linux');
        mockedExecSync.mockImplementation(() => {
          throw new Error('Command not found');
        });

        mockedExistsSync.mockImplementation((path) => {
          return path === '/usr/bin/az';
        });

        const result = findAzureCli();

        expect(result).toBe('/usr/bin/az');
      });

      test('should return null when Azure CLI not found anywhere', () => {
        mockPlatform('win32');
        mockedExecSync.mockImplementation(() => {
          throw new Error('Command not found');
        });
        mockedExistsSync.mockReturnValue(false);

        const result = findAzureCli();

        expect(result).toBeNull();
      });

      test('should handle execSync throwing errors gracefully', () => {
        mockPlatform('darwin');
        mockedExecSync.mockImplementation(() => {
          throw new Error('Access denied');
        });
        mockedExistsSync.mockReturnValue(false);

        const result = findAzureCli();

        expect(result).toBeNull();
      });

      test('should trim whitespace from PATH results', () => {
        mockPlatform('linux');
        mockedExecSync.mockReturnValue('  /usr/local/bin/az  \n');
        mockedExistsSync.mockReturnValue(true);

        const result = findAzureCli();

        expect(result).toBe('/usr/local/bin/az');
      });

      test('should return null if PATH result does not exist on filesystem', () => {
        mockPlatform('win32');
        mockedExecSync.mockReturnValue('C:\\fake\\path\\az.cmd');
        mockedExistsSync.mockReturnValue(false);

        const result = findAzureCli();

        expect(result).toBeNull();
      });
    });
  });

  describe('Version Parsing', () => {
    describe('parseVersion()', () => {
      test('should parse "azure-cli 2.45.0" format', () => {
        const output = 'azure-cli 2.45.0';
        expect(parseVersion(output)).toBe('2.45.0');
      });

      test('should parse "v2.45.0" format', () => {
        const output = 'v2.45.0';
        expect(parseVersion(output)).toBe('2.45.0');
      });

      test('should parse "2.45.0" format', () => {
        const output = '2.45.0';
        expect(parseVersion(output)).toBe('2.45.0');
      });

      test('should parse multi-line Windows output', () => {
        const output = `
azure-cli                         2.45.0

core                              2.45.0
telemetry                          1.0.8
        `.trim();
        expect(parseVersion(output)).toBe('2.45.0');
      });

      test('should parse multi-line Unix output', () => {
        const output = `azure-cli (2.45.0)
Python location: /usr/bin/python3
Extensions directory: /home/user/.azure/cliextensions`;
        expect(parseVersion(output)).toBe('2.45.0');
      });

      test('should handle output with version in middle', () => {
        const output = 'Using Azure CLI version 2.45.0 from /usr/local';
        expect(parseVersion(output)).toBe('2.45.0');
      });

      test('should return null for output without version', () => {
        const output = 'Azure CLI';
        expect(parseVersion(output)).toBeNull();
      });

      test('should return null for empty string', () => {
        expect(parseVersion('')).toBeNull();
      });

      test('should parse version with patch > 9', () => {
        const output = 'azure-cli 2.45.123';
        expect(parseVersion(output)).toBe('2.45.123');
      });

      test('should parse first version if multiple present', () => {
        const output = 'azure-cli 2.45.0 requires Python 3.8.0 or later';
        expect(parseVersion(output)).toBe('2.45.0');
      });

      test('should handle version at start of line', () => {
        const output = '2.45.0\nAzure CLI';
        expect(parseVersion(output)).toBe('2.45.0');
      });

      test('should handle version at end of line', () => {
        const output = 'Azure CLI: 2.45.0';
        expect(parseVersion(output)).toBe('2.45.0');
      });
    });
  });

  describe('Integration Scenarios', () => {
    test('Windows: Complete platform configuration', () => {
      mockPlatform('win32');

      expect(isWindows()).toBe(true);
      expect(getNpxCommand()).toBe('npx.cmd');

      const shellCmd = getShellCommand('echo test');
      expect(shellCmd.shell).toBe('cmd.exe');
      expect(shellCmd.args[0]).toBe('/c');

      const venvPath = getPythonVenvActivatePath('C:\\venv');
      expect(venvPath).toContain('Scripts');
      expect(venvPath).toContain('activate.bat');
    });

    test('Unix: Complete platform configuration', () => {
      mockPlatform('linux');

      expect(isWindows()).toBe(false);
      expect(getNpxCommand()).toBe('npx');

      const shellCmd = getShellCommand('echo test');
      expect(shellCmd.shell).toBe('/bin/bash');
      expect(shellCmd.args[0]).toBe('-c');

      const venvPath = getPythonVenvActivatePath('/home/user/venv');
      expect(venvPath).toContain('bin');
      expect(venvPath).toContain('activate');
      expect(venvPath).not.toContain('.bat');
    });

    test('macOS: Complete platform configuration', () => {
      mockPlatform('darwin');

      expect(isWindows()).toBe(false);
      expect(getPlatformName()).toBe('darwin');
      expect(getNpxCommand()).toBe('npx');

      const shellCmd = getShellCommand('ls');
      expect(shellCmd.shell).toBe('/bin/bash');

      const venvPath = getPythonVenvActivatePath('/Users/test/venv');
      expect(venvPath).toMatch(/bin[\/\\]activate$/);
    });
  });

  describe('Edge Cases', () => {
    test('should handle path with spaces on Windows', () => {
      mockPlatform('win32');
      const venvPath = 'C:\\Program Files\\My App\\venv';
      const result = getPythonVenvActivatePath(venvPath);

      expect(result).toContain('Program Files');
      expect(result).toContain('My App');
      expect(result).toMatch(/Scripts[\\/]activate\.bat$/);
    });

    test('should handle path with spaces on Unix', () => {
      mockPlatform('darwin');
      const venvPath = '/home/user/my projects/venv';
      const result = getPythonVenvActivatePath(venvPath);

      expect(result).toContain('my projects');
      expect(result).toMatch(/bin[\/\\]activate$/);
    });

    test('should handle forward slashes on Windows', () => {
      mockPlatform('win32');
      const venvPath = 'C:/Users/test/venv';
      const result = getPythonVenvActivatePath(venvPath);

      // Node's path.join normalizes slashes
      expect(result).toContain('Scripts');
      expect(result).toContain('activate.bat');
    });

    test('should handle empty venv path', () => {
      mockPlatform('linux');
      const result = getPythonVenvActivatePath('');

      expect(result).toMatch(/bin[\/\\]activate$/);
    });

    test('should handle shell command with quotes', () => {
      mockPlatform('win32');
      const command = 'echo "Hello World"';
      const result = getShellCommand(command);

      expect(result.args[1]).toBe(command);
    });
  });

  describe('Boundary Conditions', () => {
    test('should handle very long venv paths on Windows', () => {
      mockPlatform('win32');
      const longPath = 'C:\\' + 'a\\'.repeat(50) + 'venv';
      const result = getPythonVenvActivatePath(longPath);

      expect(result).toContain('Scripts');
      expect(result).toContain('activate.bat');
    });

    test('should handle very long venv paths on Unix', () => {
      mockPlatform('linux');
      const longPath = '/home/' + 'a/'.repeat(50) + 'venv';
      const result = getPythonVenvActivatePath(longPath);

      expect(result).toContain('bin');
      expect(result).toContain('activate');
    });

    test('should handle version parsing with extra whitespace', () => {
      const output = '  azure-cli   2.45.0  ';
      expect(parseVersion(output)).toBe('2.45.0');
    });

    test('should handle version parsing with tabs', () => {
      const output = 'azure-cli\t2.45.0';
      expect(parseVersion(output)).toBe('2.45.0');
    });

    test('should handle version parsing with multiple spaces', () => {
      const output = 'azure-cli    2.45.0';
      expect(parseVersion(output)).toBe('2.45.0');
    });
  });
});

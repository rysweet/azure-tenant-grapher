/**
 * Platform Utilities Module
 *
 * Provides cross-platform compatibility utilities for Windows, macOS, and Linux.
 * Handles platform-specific differences in:
 * - Python virtual environment activation paths
 * - NPX command execution (npx vs npx.cmd)
 * - Shell command execution (bash vs cmd.exe)
 * - Azure CLI detection and path resolution
 * - Version string parsing from command output
 *
 * @module spa/main/platform-utils
 *
 * @example Basic platform detection
 * ```typescript
 * import { isWindows, getPlatformName } from './platform-utils';
 *
 * if (isWindows()) {
 *   console.log('Running on Windows');
 * }
 * console.log(`Platform: ${getPlatformName()}`);
 * // Output: Platform: win32
 * ```
 *
 * @example Python venv path resolution
 * ```typescript
 * import { getPythonVenvActivatePath } from './platform-utils';
 *
 * const venvPath = '/path/to/venv';
 * const activatePath = getPythonVenvActivatePath(venvPath);
 * // Windows: /path/to/venv/Scripts/activate.bat
 * // Unix:    /path/to/venv/bin/activate
 * ```
 *
 * @example NPX command execution
 * ```typescript
 * import { getNpxCommand } from './platform-utils';
 *
 * const npxCmd = getNpxCommand();
 * // Windows: npx.cmd
 * // Unix:    npx
 *
 * const result = await execAsync(`${npxCmd} some-package`);
 * ```
 *
 * @example Shell command execution
 * ```typescript
 * import { getShellCommand } from './platform-utils';
 *
 * const shellCmd = getShellCommand('ls -la');
 * // Windows: { shell: 'cmd.exe', args: ['/c', 'ls -la'] }
 * // Unix:    { shell: '/bin/bash', args: ['-c', 'ls -la'] }
 * ```
 *
 * @example Azure CLI detection
 * ```typescript
 * import { findAzureCli } from './platform-utils';
 *
 * const azPath = await findAzureCli();
 * if (azPath) {
 *   console.log(`Azure CLI found at: ${azPath}`);
 *   // Windows: C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin\az.cmd
 *   // Unix:    /usr/local/bin/az
 * } else {
 *   console.error('Azure CLI not found');
 * }
 * ```
 *
 * @example Version parsing
 * ```typescript
 * import { parseVersion } from './platform-utils';
 *
 * const output = 'azure-cli 2.45.0\n';
 * const version = parseVersion(output);
 * console.log(version); // '2.45.0'
 * ```
 *
 * @remarks
 * This module abstracts platform-specific behavior so that consuming code
 * doesn't need to check `process.platform` directly. All platform detection
 * and path resolution is centralized here.
 *
 * @architecture
 * - Single source of truth for platform detection
 * - Backward compatible: Unix/macOS behavior unchanged
 * - No external dependencies: Uses only Node.js built-ins
 * - Pure functions: Deterministic, testable
 *
 * @testing
 * Tests run on Unix/macOS platforms (primary development environment).
 * Windows-specific behavior validated through:
 * - Code review
 * - Path string verification
 * - Logic inspection
 *
 * Note: Physical Windows testing requires Windows environment with:
 * - Python with venv
 * - Node.js with npx
 * - Azure CLI installed
 *
 * @see {@link https://nodejs.org/api/process.html#processplatform} Node.js process.platform
 * @see {@link https://github.com/Azure/azure-cli} Azure CLI
 */

import { execSync } from 'child_process';
import { existsSync } from 'fs';
import { join } from 'path';

/**
 * Detects if the current platform is Windows.
 *
 * @returns {boolean} True if running on Windows (process.platform === 'win32')
 *
 * @example
 * ```typescript
 * if (isWindows()) {
 *   console.log('Use Windows-specific paths');
 * }
 * ```
 */
export function isWindows(): boolean {
  return process.platform === 'win32';
}

/**
 * Gets the current platform name.
 *
 * @returns {string} Platform identifier ('win32', 'darwin', 'linux', etc.)
 *
 * @example
 * ```typescript
 * const platform = getPlatformName();
 * console.log(`Running on: ${platform}`);
 * ```
 */
export function getPlatformName(): string {
  return process.platform;
}

/**
 * Resolves the platform-specific Python virtual environment activation script path.
 *
 * @param {string} venvPath - Path to the virtual environment directory
 * @returns {string} Platform-specific activation script path
 *
 * @remarks
 * - Windows: `<venvPath>/Scripts/activate.bat`
 * - Unix/macOS: `<venvPath>/bin/activate`
 *
 * @example
 * ```typescript
 * const venvPath = '/home/user/myproject/venv';
 * const activatePath = getPythonVenvActivatePath(venvPath);
 * // Unix: /home/user/myproject/venv/bin/activate
 * ```
 */
export function getPythonVenvActivatePath(venvPath: string): string {
  if (isWindows()) {
    return join(venvPath, 'Scripts', 'activate.bat');
  }
  return join(venvPath, 'bin', 'activate');
}

/**
 * Gets the platform-specific NPX command.
 *
 * @returns {string} NPX command ('npx.cmd' on Windows, 'npx' on Unix)
 *
 * @remarks
 * Windows requires the `.cmd` extension to execute npx correctly.
 *
 * @example
 * ```typescript
 * import { execAsync } from './exec-utils';
 *
 * const npxCmd = getNpxCommand();
 * await execAsync(`${npxCmd} create-react-app my-app`);
 * ```
 */
export function getNpxCommand(): string {
  return isWindows() ? 'npx.cmd' : 'npx';
}

/**
 * Shell command configuration for platform-specific execution.
 */
export interface ShellCommand {
  /** Shell executable path */
  shell: string;
  /** Command line arguments */
  args: string[];
}

/**
 * Gets platform-specific shell command configuration.
 *
 * @param {string} command - Command to execute
 * @returns {ShellCommand} Shell configuration with executable and args
 *
 * @remarks
 * - Windows: Uses `cmd.exe` with `/c` flag
 * - Unix/macOS: Uses `/bin/bash` with `-c` flag
 *
 * @example
 * ```typescript
 * import { spawn } from 'child_process';
 *
 * const shellCmd = getShellCommand('echo "Hello World"');
 * const proc = spawn(shellCmd.shell, shellCmd.args);
 * ```
 */
export function getShellCommand(command: string): ShellCommand {
  if (isWindows()) {
    return {
      shell: 'cmd.exe',
      args: ['/c', command],
    };
  }
  return {
    shell: '/bin/bash',
    args: ['-c', command],
  };
}

/**
 * Finds the Azure CLI executable path.
 *
 * @returns {string | null} Path to Azure CLI executable, or null if not found
 *
 * @remarks
 * Search strategy:
 * 1. Check PATH via `which` (Unix) or `where` (Windows)
 * 2. Check standard installation locations:
 *    - Windows: `C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin\az.cmd`
 *    - Unix: `/usr/local/bin/az`, `/opt/az/bin/az`
 *
 * @example
 * ```typescript
 * const azPath = await findAzureCli();
 * if (!azPath) {
 *   throw new Error('Azure CLI not found. Install from https://aka.ms/azure-cli');
 * }
 * console.log(`Using Azure CLI: ${azPath}`);
 * ```
 */
export function findAzureCli(): string | null {
  // Try PATH first
  try {
    const command = isWindows() ? 'where az' : 'which az';
    const result = execSync(command, { encoding: 'utf-8' }).trim();
    if (result && existsSync(result)) {
      return result;
    }
  } catch {
    // Command not in PATH, check standard locations
  }

  // Check standard installation locations
  const standardPaths = isWindows()
    ? [
        'C:\\Program Files\\Microsoft SDKs\\Azure\\CLI2\\wbin\\az.cmd',
        'C:\\Program Files (x86)\\Microsoft SDKs\\Azure\\CLI2\\wbin\\az.cmd',
      ]
    : ['/usr/local/bin/az', '/opt/az/bin/az', '/usr/bin/az'];

  for (const path of standardPaths) {
    if (existsSync(path)) {
      return path;
    }
  }

  return null;
}

/**
 * Parses version string from command output.
 *
 * @param {string} output - Command output containing version information
 * @returns {string | null} Extracted version string, or null if not found
 *
 * @remarks
 * Handles various version formats:
 * - `azure-cli 2.45.0`
 * - `v2.45.0`
 * - `2.45.0`
 * - Multi-line output (takes first version found)
 *
 * @example
 * ```typescript
 * const output = execSync('az --version', { encoding: 'utf-8' });
 * const version = parseVersion(output);
 * if (version) {
 *   console.log(`Azure CLI version: ${version}`);
 * }
 * ```
 */
export function parseVersion(output: string): string | null {
  // Match common version patterns: x.y.z or vx.y.z
  const versionRegex = /\bv?(\d+\.\d+\.\d+)\b/;
  const match = output.match(versionRegex);
  return match ? match[1] : null;
}

/**
 * Get platform-specific paths for common executables
 * Convenience function that returns paths relative to project root
 */
export function getPlatformPaths() {
  return {
    pythonPath: isWindows()
      ? '.venv/Scripts/python.exe'
      : '.venv/bin/python',
    npxCommand: getNpxCommand(),
  };
}

/**
 * Get platform-specific command strings for Azure CLI operations
 */
export function getPlatformCommands() {
  return {
    azCliCheck: isWindows() ? 'where az' : 'which az',
    versionParser: isWindows()
      ? 'az --version 2>NUL | findstr azure-cli'
      : 'az --version 2>&1 | grep azure-cli | head -1',
  };
}

/**
 * Get shell options for child_process.spawn()
 * Returns an object with 'shell' property set appropriately for the platform
 */
export function getShellOptions() {
  return {
    shell: isWindows(),
  };
}

---
last_updated: 2026-02-11
status: current
category: reference
related_issue: 920
---

# Platform-Specific Behavior Reference

Complete technical reference for cross-platform behavior in Azure Tenant Grapher's Electron application.

## Overview

The `spa/main/platform-utils.ts` module provides platform abstraction for Windows, macOS, and Linux. All platform detection is centralized here.

## API Reference

### Platform Detection

#### `isWindows(): boolean`

Detects if the current platform is Windows.

**Returns:** `true` if `process.platform === 'win32'`, `false` otherwise

**Example:**
```typescript
import { isWindows } from './platform-utils';

if (isWindows()) {
  console.log('Running on Windows');
}
```

**Platforms:**
- Windows: Returns `true`
- macOS: Returns `false`
- Linux: Returns `false`

---

#### `getPlatformName(): string`

Returns the Node.js platform identifier.

**Returns:** Platform string (`'win32'`, `'darwin'`, `'linux'`, etc.)

**Example:**
```typescript
import { getPlatformName } from './platform-utils';

console.log(`Platform: ${getPlatformName()}`);
// Windows: Platform: win32
// macOS: Platform: darwin
// Linux: Platform: linux
```

**Possible Values:**
- `'win32'` - Windows (32-bit and 64-bit)
- `'darwin'` - macOS
- `'linux'` - Linux
- `'freebsd'` - FreeBSD
- `'openbsd'` - OpenBSD
- `'sunos'` - SunOS
- `'aix'` - AIX

---

### Python Virtual Environment

#### `getPythonVenvActivatePath(venvPath: string): string`

Resolves platform-specific virtual environment activation script path.

**Parameters:**
- `venvPath` - Path to virtual environment directory

**Returns:** Full path to activation script

**Platform Behavior:**

| Platform    | Activation Path                      |
|-------------|--------------------------------------|
| Windows     | `<venvPath>\Scripts\activate.bat`    |
| macOS       | `<venvPath>/bin/activate`            |
| Linux       | `<venvPath>/bin/activate`            |

**Examples:**

```typescript
import { getPythonVenvActivatePath } from './platform-utils';

// Windows
const winPath = getPythonVenvActivatePath('C:\\projects\\myapp\\venv');
// Returns: C:\projects\myapp\venv\Scripts\activate.bat

// Unix/macOS
const unixPath = getPythonVenvActivatePath('/home/user/myapp/venv');
// Returns: /home/user/myapp/venv/bin/activate
```

**Notes:**
- Uses Node.js `path.join()` for correct path separators
- Does not verify the path exists
- Returns string path, not executed script

---

### NPX Command

#### `getNpxCommand(): string`

Returns platform-specific NPX command.

**Returns:** NPX command string

**Platform Behavior:**

| Platform    | NPX Command  |
|-------------|--------------|
| Windows     | `npx.cmd`    |
| macOS       | `npx`        |
| Linux       | `npx`        |

**Example:**
```typescript
import { getNpxCommand } from './platform-utils';
import { execAsync } from './exec-utils';

const npxCmd = getNpxCommand();
await execAsync(`${npxCmd} typescript --version`);
```

**Rationale:**
Windows requires `.cmd` extension for batch files executed as commands.

---

### Shell Execution

#### `getShellCommand(command: string): ShellCommand`

Returns platform-specific shell configuration for command execution.

**Parameters:**
- `command` - Command string to execute

**Returns:** `ShellCommand` object
```typescript
interface ShellCommand {
  shell: string;   // Shell executable path
  args: string[];  // Command line arguments
}
```

**Platform Behavior:**

| Platform    | Shell         | Args Format            |
|-------------|---------------|------------------------|
| Windows     | `cmd.exe`     | `['/c', command]`      |
| macOS       | `/bin/bash`   | `['-c', command]`      |
| Linux       | `/bin/bash`   | `['-c', command]`      |

**Examples:**

```typescript
import { getShellCommand } from './platform-utils';
import { spawn } from 'child_process';

// Windows
const winShell = getShellCommand('dir /b');
// Returns: { shell: 'cmd.exe', args: ['/c', 'dir /b'] }

// Unix
const unixShell = getShellCommand('ls -la');
// Returns: { shell: '/bin/bash', args: ['-c', 'ls -la'] }

// Usage with spawn
const shellCmd = getShellCommand('echo "Hello"');
const proc = spawn(shellCmd.shell, shellCmd.args);
```

**Flags:**
- `/c` (Windows) - Executes command and terminates
- `-c` (Unix) - Executes command from string

---

### Azure CLI Detection

#### `findAzureCli(): string | null`

Locates Azure CLI executable on the system.

**Returns:** Full path to Azure CLI, or `null` if not found

**Search Strategy:**

1. **Check PATH** (via `which` or `where` command)
2. **Check standard installation locations**

**Platform-Specific Locations:**

**Windows:**
- `C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin\az.cmd`
- `C:\Program Files (x86)\Microsoft SDKs\Azure\CLI2\wbin\az.cmd`
- PATH environment variable

**macOS/Linux:**
- `/usr/local/bin/az`
- `/opt/az/bin/az`
- `/usr/bin/az`
- PATH environment variable

**Examples:**

```typescript
import { findAzureCli } from './platform-utils';

const azPath = findAzureCli();
if (azPath) {
  console.log(`Azure CLI found: ${azPath}`);
  // Windows: C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin\az.cmd
  // macOS: /usr/local/bin/az
} else {
  console.error('Azure CLI not found');
}
```

**Error Handling:**
- Returns `null` if Azure CLI not found
- Does not throw exceptions
- Silently catches `execSync` errors

**Performance:**
- Synchronous execution
- Checks PATH first (fastest)
- Falls back to standard locations

---

### Version Parsing

#### `parseVersion(output: string): string | null`

Extracts version string from command output.

**Parameters:**
- `output` - Raw command output containing version information

**Returns:** Version string (e.g., `"2.45.0"`), or `null` if not found

**Supported Formats:**

| Input Format              | Extracted Version  |
|---------------------------|--------------------|
| `azure-cli 2.45.0`        | `2.45.0`           |
| `v2.45.0`                 | `2.45.0`           |
| `2.45.0`                  | `2.45.0`           |
| `version: 2.45.0`         | `2.45.0`           |
| Multi-line with version   | First match        |
| `No version string`       | `null`             |

**Regular Expression:**
```typescript
/\bv?(\d+\.\d+\.\d+)\b/
```

**Examples:**

```typescript
import { parseVersion } from './platform-utils';

// Standard Azure CLI output
const azOutput = 'azure-cli                         2.45.0\n\ncore...';
parseVersion(azOutput);  // Returns: '2.45.0'

// Simple version string
parseVersion('v2.45.0');  // Returns: '2.45.0'

// Multi-line output
const multiline = `
Some header text
Version: v2.45.0
More info...
`;
parseVersion(multiline);  // Returns: '2.45.0'

// No version
parseVersion('No version here');  // Returns: null
```

**Notes:**
- Returns first match only
- Strips leading 'v' if present
- Requires semantic version format (major.minor.patch)

---

## Platform Compatibility Matrix

| Feature                  | Windows | macOS | Linux | Notes                                    |
|--------------------------|---------|-------|-------|------------------------------------------|
| Python venv paths        | ✓       | ✓     | ✓     | Scripts/ vs bin/                         |
| NPX execution            | ✓       | ✓     | ✓     | .cmd extension on Windows                |
| Shell commands           | ✓       | ✓     | ✓     | cmd.exe vs bash                          |
| Azure CLI detection      | ✓       | ✓     | ✓     | Different installation paths             |
| Version parsing          | ✓       | ✓     | ✓     | Handles all formats                      |
| Path separators          | ✓       | ✓     | ✓     | Handled by Node.js `path` module         |

## Architecture

### Design Principles

1. **Single Source of Truth** - All platform detection in one module
2. **Explicit Over Implicit** - Clear function names describing behavior
3. **Backward Compatible** - Unix/macOS behavior unchanged
4. **Pure Functions** - Deterministic, no side effects (except `findAzureCli`)
5. **No External Dependencies** - Uses only Node.js built-ins

### File Organization

```
spa/main/
├── platform-utils.ts        # Platform abstraction (this module)
├── index.ts                 # Main process entry (uses platform-utils)
├── process-manager.ts       # Process management (uses platform-utils)
├── process-manager-secure.ts # Secure process manager (uses platform-utils)
└── server.ts                # Backend server (uses platform-utils)
```

### Integration Points

| File                        | Usage                                      |
|-----------------------------|--------------------------------------------|
| `index.ts`                  | Azure CLI detection at startup             |
| `process-manager.ts`        | Python venv activation, NPX commands       |
| `process-manager-secure.ts` | Shell command execution, version parsing   |
| `server.ts`                 | Backend process spawning                   |

## Testing

### Test Coverage

Tests run on Unix/macOS (primary development platform):

```typescript
// Mocked platform detection
jest.mock('process', () => ({
  platform: 'win32',  // or 'darwin', 'linux'
}));

test('getPythonVenvActivatePath - Windows', () => {
  process.platform = 'win32';
  const result = getPythonVenvActivatePath('C:\\venv');
  expect(result).toBe('C:\\venv\\Scripts\\activate.bat');
});
```

### Manual Testing Requirements

Physical Windows testing validates:
- [ ] Python venv activation works
- [ ] NPX commands execute correctly
- [ ] Azure CLI detected from standard locations
- [ ] Shell commands execute via cmd.exe
- [ ] Version parsing handles Windows output format

### Test Data

**Sample Azure CLI output (Windows):**
```
azure-cli                         2.45.0

core                              2.45.0
telemetry                          1.0.8
```

**Sample Azure CLI output (Unix):**
```
azure-cli                         2.45.0

core                              2.45.0
telemetry                          1.0.8
```

(Output format identical across platforms)

## Migration Guide

### Before (Hardcoded Unix Paths)

```typescript
// Old code - Unix only
const venvPath = path.join(venvDir, 'bin', 'activate');
await execAsync('npx typescript --version');
const proc = spawn('/bin/bash', ['-c', command]);
```

### After (Platform-Aware)

```typescript
// New code - Cross-platform
import { getPythonVenvActivatePath, getNpxCommand, getShellCommand } from './platform-utils';

const venvPath = getPythonVenvActivatePath(venvDir);
await execAsync(`${getNpxCommand()} typescript --version`);

const shellCmd = getShellCommand(command);
const proc = spawn(shellCmd.shell, shellCmd.args);
```

## Performance Characteristics

| Function                       | Complexity | Performance Notes                    |
|--------------------------------|------------|--------------------------------------|
| `isWindows()`                  | O(1)       | Simple string comparison             |
| `getPlatformName()`            | O(1)       | Returns process property             |
| `getPythonVenvActivatePath()`  | O(1)       | String concatenation only            |
| `getNpxCommand()`              | O(1)       | Conditional string return            |
| `getShellCommand()`            | O(1)       | Object creation                      |
| `findAzureCli()`               | O(n)       | n = number of standard paths checked |
| `parseVersion()`               | O(m)       | m = length of output string          |

## Security Considerations

### Path Injection

All functions use Node.js `path.join()` to prevent path traversal:

```typescript
// Safe - Uses path.join()
getPythonVenvActivatePath('/safe/path');

// Would be unsafe if concatenating manually:
// venvPath + '/bin/activate'  // ❌ Don't do this
```

### Command Injection

`getShellCommand()` does not sanitize input. Callers must validate:

```typescript
// Caller's responsibility to sanitize
const userInput = sanitize(req.body.command);
const shellCmd = getShellCommand(userInput);
```

### Azure CLI Detection

`findAzureCli()` checks only predefined paths. No user input accepted.

## Troubleshooting

### Windows-Specific Issues

**Issue:** `getNpxCommand()` returns `npx.cmd` but command fails
- **Cause:** Node.js not properly installed
- **Solution:** Reinstall Node.js, verify `npx.cmd` exists in Node.js installation

**Issue:** `findAzureCli()` returns `null` on Windows
- **Cause:** Azure CLI not in standard location
- **Solution:** Add Azure CLI to PATH or install to standard location

**Issue:** `getShellCommand()` fails with `ENOENT`
- **Cause:** `cmd.exe` not accessible
- **Solution:** Verify Windows system paths, run as Administrator

## Related Documentation

- [Windows Compatibility Setup](../howto/windows-compatibility.md) - User guide
- [Windows Compatibility Concepts](../concepts/windows-compatibility.md) - Design rationale
- [Development Setup](../development/setup.md) - Developer environment
- [Security Guidelines](../security/SECURITY.md) - Security best practices

## See Also

- [Node.js process.platform](https://nodejs.org/api/process.html#processplatform)
- [Node.js child_process](https://nodejs.org/api/child_process.html)
- [Azure CLI Installation](https://docs.microsoft.com/cli/azure/install-azure-cli)
- [Python venv Documentation](https://docs.python.org/3/library/venv.html)

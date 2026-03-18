---
last_updated: 2026-02-11
status: current
category: howto
related_issue: 920
---

# Windows Compatibility Setup

Run Azure Tenant Grapher's Electron web application on Windows. This guide covers platform-specific configuration and troubleshooting.

## Prerequisites

- Windows 10 or later (64-bit)
- Python 3.8+ with venv support
- Node.js 16+ with npm
- Azure CLI 2.30+

## Quick Start

The Electron app automatically detects Windows and adjusts paths and commands. No manual configuration required.

```bash
# Clone and setup (same as Unix)
git clone https://github.com/your-org/azure-tenant-grapher.git
cd azure-tenant-grapher

# Install dependencies
npm install

# Run the app
npm start
```

## Platform-Specific Behavior

The app automatically handles these Windows differences:

### 1. Python Virtual Environment

**Unix/macOS:**
```
venv/bin/activate
```

**Windows (automatic):**
```
venv\Scripts\activate.bat
```

### 2. NPX Commands

**Unix/macOS:**
```bash
npx some-package
```

**Windows (automatic):**
```bash
npx.cmd some-package
```

### 3. Shell Execution

**Unix/macOS:**
```typescript
// Internally uses: /bin/bash -c "command"
```

**Windows (automatic):**
```typescript
// Internally uses: cmd.exe /c "command"
```

### 4. Azure CLI Detection

**Standard Windows locations checked:**
- `C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin\az.cmd`
- `C:\Program Files (x86)\Microsoft SDKs\Azure\CLI2\wbin\az.cmd`
- PATH environment variable

### 5. Version Parsing

Handles Windows and Unix version output formats:
```
azure-cli 2.45.0       ✓ Supported
v2.45.0                ✓ Supported
2.45.0                 ✓ Supported
```

## Verification

Verify Windows compatibility:

```bash
# Check Python venv
cd spa/server
python -m venv venv
# Windows automatically uses: venv\Scripts\activate.bat

# Check NPX
npx --version
# Windows automatically uses: npx.cmd

# Check Azure CLI
az --version
# Should detect from Program Files or PATH
```

## Troubleshooting

### Issue: Python venv not activating

**Symptom:**
```
'activate' is not recognized as an internal or external command
```

**Solution:**
Verify Python venv is created correctly:
```bash
python -m venv venv --clear
```

App automatically uses `venv\Scripts\activate.bat` on Windows.

### Issue: NPX command not found

**Symptom:**
```
'npx' is not recognized as an internal or external command
```

**Solution:**
1. Verify Node.js installation:
   ```bash
   node --version
   npm --version
   ```

2. App automatically uses `npx.cmd` on Windows. If still failing, reinstall Node.js.

### Issue: Azure CLI not detected

**Symptom:**
```
Azure CLI not found
```

**Solution:**
1. Install Azure CLI:
   ```bash
   # Download from: https://aka.ms/installazurecliwindows
   # Or use winget:
   winget install -e --id Microsoft.AzureCLI
   ```

2. Verify installation:
   ```bash
   az --version
   ```

3. App checks these locations automatically:
   - PATH environment variable
   - `C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin\az.cmd`
   - `C:\Program Files (x86)\Microsoft SDKs\Azure\CLI2\wbin\az.cmd`

### Issue: Shell command execution fails

**Symptom:**
```
spawn ENOENT
```

**Solution:**
App automatically uses `cmd.exe` on Windows. Ensure Windows command prompt is functional:
```bash
cmd.exe /c echo "test"
```

## Differences from Unix/macOS

| Feature                | Unix/macOS                | Windows                          |
|------------------------|---------------------------|----------------------------------|
| Venv activation        | `bin/activate`            | `Scripts\activate.bat`           |
| NPX command            | `npx`                     | `npx.cmd`                        |
| Shell                  | `/bin/bash`               | `cmd.exe`                        |
| Azure CLI path         | `/usr/local/bin/az`       | `C:\Program Files\...\az.cmd`    |
| Path separator         | `/`                       | `\` (handled by Node.js `path`)  |

## Development Notes

### For Contributors

Windows-specific code is centralized in `spa/main/platform-utils.ts`:

```typescript
import { isWindows, getNpxCommand } from './platform-utils';

// Automatic platform detection
const npxCmd = getNpxCommand();
// Windows: npx.cmd
// Unix: npx
```

### Testing on Windows

Manual testing checklist:
- [ ] Python venv activation
- [ ] NPX command execution
- [ ] Azure CLI detection
- [ ] Shell command execution
- [ ] Version parsing

### Backward Compatibility

Unix/macOS behavior unchanged. All Windows-specific logic is additive.

## Related Documentation

- [Platform-Specific Behavior Reference](../reference/platform-behavior.md) - Complete technical reference
- [Windows Compatibility Concepts](../concepts/windows-compatibility.md) - Design rationale
- [Installation Guide](../quickstart/installation.md) - General installation
- [Development Setup](../development/setup.md) - Developer environment

## Support

For Windows-specific issues:
1. Check [Troubleshooting](#troubleshooting) section above
2. Verify prerequisites are met
3. Check GitHub Issues for similar problems
4. Create new issue with label `windows` and `platform-compatibility`

**Note:** Primary development occurs on Unix/macOS. Windows support is validated through code review and logic inspection. Community testing reports welcome.

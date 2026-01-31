# Azure Tenant Grapher - Gadugi Agentic Tests

This directory contains **outside-in tests** for the Azure Tenant Grapher SPA using the [gadugi-agentic-test](https://github.com/rysweet/gadugi-agentic-test) framework.

## What is Outside-In Testing?

Outside-in tests verify application behavior from the **user's perspective** without knowledge of internal implementation. These tests:

- ✅ **Survive refactoring** - Internal changes don't break tests
- ✅ **Readable by non-developers** - YAML is declarative and clear
- ✅ **AI-powered execution** - Agents handle complex interactions
- ✅ **Evidence-based** - Captures screenshots, logs, timing data

## Available Tests

### 🚀 Smoke Test (Level 1)
**File**: `scan-tab-smoke-test.yaml`
**Duration**: ~30 seconds
**Purpose**: Quick validation that app launches and Scan tab is accessible

Tests:
- Application launches successfully
- Navigation tabs are visible
- Scan tab loads correctly
- Critical UI elements exist (Tenant ID input, Start Scan button)

### 🎯 Complete Workflow (Level 2)
**File**: `scan-workflow-complete.yaml`
**Duration**: 3-5 minutes
**Purpose**: Full end-to-end scan workflow validation

Tests:
- Application launch and initialization
- Navigate to Scan tab
- Configure scan parameters (tenant ID, limits, options)
- Start scan operation
- Monitor scan progress
- Verify scan results
- Navigate to Status tab and verify graph data

## Prerequisites

### 1. Install Gadugi Framework

**Option A: From GitHub (Recommended)**
```bash
npm install -g github:rysweet/gadugi-agentic-test
```

**Option B: Clone and Build**
```bash
git clone https://github.com/rysweet/gadugi-agentic-test
cd gadugi-agentic-test
npm install
npm run build
```

### 2. Build the ATG Electron App
```bash
cd /home/sumallepally/ATG_WSL/spa
npm install
npm run build
```

### 3. Install Playwright (for Electron automation)
```bash
npm install -g playwright
npx playwright install
```

### 4. Configure Azure CLI (for real tenant scans)
```bash
az login
az account set --subscription "your-subscription-id"
```

## Running Tests

### Quick Smoke Test
```bash
# Using global installation
cd /home/sumallepally/ATG_WSL/spa
gadugi-test run tests/gadugi/scan-tab-smoke-test.yaml

# Using from source
cd /path/to/gadugi-agentic-test
node dist/cli.js run /home/sumallepally/ATG_WSL/spa/tests/gadugi/scan-tab-smoke-test.yaml
```

### Complete Workflow Test
```bash
# Using global installation
cd /home/sumallepally/ATG_WSL/spa
gadugi-test run tests/gadugi/scan-workflow-complete.yaml --verbose

# Using from source
cd /path/to/gadugi-agentic-test
node dist/cli.js run /home/sumallepally/ATG_WSL/spa/tests/gadugi/scan-workflow-complete.yaml --verbose
```

### Run All Tests
```bash
gadugi-test run tests/gadugi/*.yaml --verbose
```

### With Custom Options
```bash
# Increase timeout
gadugi-test run tests/gadugi/scan-workflow-complete.yaml --timeout 600000

# Save evidence to custom directory
gadugi-test run tests/gadugi/scan-workflow-complete.yaml --evidence-dir ./my-test-evidence

# Retry on failure
gadugi-test run tests/gadugi/scan-workflow-complete.yaml --retry 2
```

## Test Evidence

After running tests, evidence is collected in the `evidence/` directory:

```
evidence/
  scan-workflow/
    ├── scenario.yaml                 # Original test scenario
    ├── execution-log.json            # Detailed execution log
    ├── screenshots/                  # Captured screenshots
    │   ├── 01-app-launched.png
    │   ├── 02-scan-tab-loaded.png
    │   ├── 03-scan-configured.png
    │   ├── 04-scan-started.png
    │   ├── 05-scan-in-progress.png
    │   ├── 06-scan-completed.png
    │   ├── 07-status-tab.png
    │   └── 08-cleanup-final.png
    ├── timing.json                   # Performance metrics
    └── report.html                   # Human-readable report
```

## Environment Variables

Configure test behavior with environment variables:

```bash
# Override tenant ID for testing
export TEST_TENANT_ID="contoso.onmicrosoft.com"

# Override backend port
export PORT="3001"

# Set to test environment
export NODE_ENV="test"

# Run with custom config
TEST_TENANT_ID="your-tenant.com" gadugi-test run tests/gadugi/scan-workflow-complete.yaml
```

## Troubleshooting

### Problem: "electron: command not found"
**Solution**: Install Electron
```bash
npm install -g electron
```

### Problem: "Cannot find module 'playwright'"
**Solution**: Install Playwright
```bash
npm install -g playwright
npx playwright install
```

### Problem: "Neo4j connection failed"
**Solution**: Start Neo4j manually before running test
```bash
neo4j start
# Or use Docker
docker run -d --name neo4j -p 7474:7474 -p 7687:7687 neo4j:latest
```

### Problem: "Backend server not responding"
**Solution**: Ensure port 3001 is available
```bash
# Check if port is in use
lsof -i :3001

# Kill process using port (if needed)
kill -9 $(lsof -t -i:3001)
```

### Problem: "Azure authentication failed"
**Solution**: Re-authenticate with Azure CLI
```bash
az login --tenant "your-tenant-id"
```

### Problem: Test times out
**Solution**: Increase timeout in YAML config or command line
```yaml
config:
  timeout: 600000  # 10 minutes
```
Or:
```bash
gadugi-test run test.yaml --timeout 600000
```

### Problem: Screenshots are blank
**Solution**: Ensure app has time to render
- Add longer `wait_for_element` timeouts
- Use `wait_for_load_state` before screenshots

### Problem: Element not found
**Solution**: Update selectors in YAML
```yaml
# Use more specific selectors
selector: "button[aria-label='Start Scan']"

# Or use text matching
text: "Start Scan"

# Or wait longer
timeout: 10000
```

## CI/CD Integration

### GitHub Actions Example

Create `.github/workflows/gadugi-tests.yml`:

```yaml
name: Gadugi Agentic Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Setup Node.js
        uses: actions/setup-node@v3
        with:
          node-version: '18'

      - name: Install dependencies
        run: |
          cd spa
          npm install
          npm run build

      - name: Install Gadugi
        run: npm install -g github:rysweet/gadugi-agentic-test

      - name: Install Playwright
        run: |
          npm install -g playwright
          npx playwright install --with-deps

      - name: Run Smoke Tests
        run: gadugi-test run spa/tests/gadugi/scan-tab-smoke-test.yaml

      - name: Run Full Tests
        run: gadugi-test run spa/tests/gadugi/scan-workflow-complete.yaml
        continue-on-error: true  # Don't fail build on test failure

      - name: Upload Test Evidence
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: test-evidence
          path: ./evidence/
```

## Writing Your Own Tests

### Template

```yaml
name: "My Test Name"
description: "What this test verifies"
version: "1.0.0"

config:
  timeout: 60000

metadata:
  tags: ["custom"]

agents:
  - name: "electron-ui"
    type: "electron"
    config:
      executable: "./node_modules/.bin/electron"
      args: ["."]
      wait_for_window: true

steps:
  - name: "Launch app"
    agent: "electron-ui"
    action: "launch"
    params:
      target: "./node_modules/.bin/electron"
      args: ["."]
      timeout: 30000

  - name: "Your test steps here"
    agent: "electron-ui"
    action: "click"
    params:
      selector: ".my-button"

cleanup:
  - name: "Close app"
    agent: "electron-ui"
    action: "window_action"
    params:
      action: "close"
```

### Common Actions

**Navigation**:
```yaml
- action: "click"
  params:
    text: "Tab Name"
```

**Input**:
```yaml
- action: "type"
  params:
    selector: "input[aria-label='Field']"
    value: "test value"
```

**Verification**:
```yaml
- action: "verify_element"
  params:
    selector: ".success-message"
    contains: "Success"
```

**Waiting**:
```yaml
- action: "wait_for_element"
  params:
    selector: ".loading-spinner"
    disappears: true
    timeout: 10000
```

**Screenshots**:
```yaml
- action: "screenshot"
  params:
    save_as: "evidence.png"
    full_page: true
```

## Best Practices

### 1. Start Simple
Begin with smoke tests, then add complexity.

### 2. Use Descriptive Names
```yaml
# Good
name: "Verify scan completes with valid tenant ID"

# Bad
name: "Test 1"
```

### 3. Add Waits for Dynamic Content
```yaml
# Always wait before verification
- action: "click"
  params:
    selector: ".load-button"

- action: "wait_for_element"
  params:
    selector: ".data-loaded"
    timeout: 10000

- action: "verify_element"
  params:
    selector: ".data-table"
```

### 4. Use continue_on_failure for Optional Steps
```yaml
- action: "click"
  params:
    selector: ".optional-feature"
  continue_on_failure: true
```

### 5. Capture Evidence at Key Points
```yaml
- action: "screenshot"
  params:
    save_as: "01-before-action.png"

# ... perform action ...

- action: "screenshot"
  params:
    save_as: "02-after-action.png"
```

## Resources

- **Gadugi Framework**: https://github.com/rysweet/gadugi-agentic-test
- **Outside-In Testing Skill**: `.claude/skills/outside-in-testing/`
- **Playwright Docs**: https://playwright.dev/
- **Electron Testing**: https://www.electronjs.org/docs/latest/tutorial/automated-testing

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review `.claude/skills/outside-in-testing/README.md`
3. Open an issue at: https://github.com/rysweet/MicrosoftHackathon2025-AgenticCoding/issues

---

**Remember**: Outside-in tests verify WHAT your application does, not HOW it does it. Focus on user-visible behavior for stable, meaningful tests! 🎯

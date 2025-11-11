# Scale Operations Agentic Testing Setup and Findings

**Issue:** #427 - Scale Operations
**Date:** 2025-11-11
**Author:** Agentic Testing System

## Executive Summary

This document describes the setup and configuration of the gadugi-agentic-test framework for end-to-end CLI testing of scale operations commands in the Azure Tenant Grapher project. It includes test scenario definitions, findings, and recommendations.

## Table of Contents

1. [Gadugi Framework Overview](#gadugi-framework-overview)
2. [Test Scenarios Created](#test-scenarios-created)
3. [Test Execution Results](#test-execution-results)
4. [Issues Discovered](#issues-discovered)
5. [Recommendations](#recommendations)
6. [How to Run Tests](#how-to-run-tests)

---

## Gadugi Framework Overview

### What is Gadugi-Agentic-Test?

Gadugi-agentic-test (https://github.com/rysweet/gadugi-agentic-test) is an AI-powered testing framework for automating UI and CLI testing in Electron applications. It is already integrated into the Azure Tenant Grapher project.

### Current Integration

The framework is installed in the project at:
- **Package Location:** `spa/node_modules/@gadugi/agentic-test` (from GitHub)
- **Package JSON Entry:** `"@gadugi/agentic-test": "github:rysweet/gadugi-agentic-test#main"`
- **Test Runner:** `spa/test-with-gadugi.js`
- **NPM Script:** `npm run test:ui` (in spa directory)

### Framework Capabilities

The gadugi-agentic-test framework provides:

1. **System Agent**: Executes CLI commands with output capture
2. **Scenario-Based Testing**: YAML-defined test scenarios
3. **Assertion Framework**: Validates command outputs and exit codes
4. **Error Handling**: Comprehensive error detection and reporting
5. **Multiple Output Formats**: JSON, Markdown, and Table support

### Existing Test Infrastructure

The project already has agentic testing infrastructure:
- **Directory:** `spa/agentic-testing/`
- **Existing Scenarios:** CLI tests, UI workflows, error handling, integration tests
- **Scenario Location:** `spa/agentic-testing/scenarios/`

Example existing test scenarios:
- `cli-tests.yaml` - Core CLI command tests
- `ui-workflows.yaml` - UI interaction tests
- `error-handling.yaml` - Error condition tests
- `integration-tests.yaml` - Full workflow tests

---

## Test Scenarios Created

### 1. Scale Operations Smoke Tests

**File:** `spa/agentic-testing/scenarios/scale-operations-tests.yaml`

**Purpose:** Comprehensive smoke tests for all scale operations CLI commands

**Test Coverage:**

#### Scale-Stats Command Tests
- Help command output validation
- Basic execution without detailed output
- Detailed output with type breakdown
- JSON output format validation

#### Scale-Up Command Tests
- Command group help validation
- Template subcommand help validation
- Scenario subcommand help validation
- Required parameter validation (template-file)
- Error handling for non-existent files
- Required parameter validation (scenario)
- Scenario type validation

#### Scale-Down Command Tests
- Command group help validation
- Algorithm subcommand help validation
- Pattern subcommand help validation
- Required parameter validation (algorithm)
- Required parameter validation (pattern)

#### Scale-Clean Command Tests
- Help command output validation
- Dry-run execution
- JSON output format validation

#### Scale-Validate Command Tests
- Help command output validation
- Basic execution
- JSON output format validation

#### Error Handling Tests
- Missing subcommand handling
- Invalid tenant ID handling

**Total Test Steps:** 26

### 2. Scale Operations End-to-End Tests

**File:** `spa/agentic-testing/scenarios/scale-operations-e2e-tests.yaml`

**Purpose:** Real execution tests with actual parameters and template files

**Test Coverage:**

#### Setup and Baseline
- Neo4j container status check
- Baseline graph statistics retrieval

#### Scale-Up Template Tests (with real template)
- Template file existence verification
- Dry-run with scale factor 2.0
- Custom batch size testing
- JSON output format testing

#### Scale-Up Scenario Tests
- Hub-spoke scenario testing
- Multi-region scenario testing
- Dev-test-prod scenario testing

#### Scale-Down Algorithm Tests
- Random algorithm testing
- Proportional algorithm testing
- Stratified algorithm testing

#### Scale-Down Pattern Tests
- Resource type pattern filtering
- Location pattern filtering

#### Validation and Cleanup Workflow
- Comprehensive validation checks
- Detailed table output
- Cleanup preview (dry-run)
- Cleanup summary (JSON)

#### Workflow Integration Tests
- Stats → Validate → Clean workflow

#### Parameter Validation Tests
- Invalid scale factors (negative, zero)
- Invalid sample sizes (>1.0, negative)
- Invalid scenario types
- Invalid algorithm types

#### Output Format Consistency Tests
- JSON validity for scale-stats
- JSON validity for scale-validate
- JSON validity for scale-clean

**Total Test Steps:** 38

### 3. Test Template File

**File:** `test-data/scale-up-template-test.yaml`

**Purpose:** Sample template for testing scale-up template command

**Template Contents:**
- Resource definitions (VMs, VNets, Subnets, Storage Accounts)
- Relationship generation rules
- Scaling configuration
- Validation rules

---

## Test Execution Results

### Commands Tested Successfully

The following commands executed successfully and returned proper help output:

1. **atg scale-stats --help** ✅
   - Output: Proper help text with all options
   - Exit Code: 0

2. **atg scale-validate --help** ✅
   - Output: Proper help text with validation checks listed
   - Exit Code: 0

3. **atg scale-clean --help** ✅
   - Output: Proper help text with cleanup options
   - Exit Code: 0

4. **atg scale-up --help** ✅
   - Output: Shows subcommands (template, scenario)
   - Exit Code: 0

5. **atg scale-up template --help** ✅
   - Output: Proper help with all template options
   - Exit Code: 0

6. **atg scale-up scenario --help** ✅
   - Output: Proper help with scenario types
   - Exit Code: 0

7. **atg scale-down --help** ✅
   - Output: Shows subcommands (algorithm, pattern)
   - Exit Code: 0

8. **atg scale-down algorithm --help** ✅
   - Output: Proper help with algorithm types
   - Exit Code: 0

9. **atg scale-down pattern --help** ✅
   - Output: Proper help with pattern options
   - Exit Code: 0

### Commands With Execution Issues

The following commands exhibited hanging/timeout behavior:

1. **atg scale-up template** with --no-container flag
   - **Issue:** Command hangs indefinitely
   - **Expected:** Should execute or fail gracefully
   - **Actual:** Timeout after 45 seconds

2. **atg scale-up scenario** with --no-container flag
   - **Issue:** Command hangs indefinitely
   - **Expected:** Should validate scenario parameter
   - **Actual:** Timeout after 20 seconds

3. **atg scale-down algorithm** with --no-container flag
   - **Issue:** Command hangs indefinitely
   - **Expected:** Should validate algorithm parameter
   - **Actual:** Timeout after 20 seconds

---

## Issues Discovered

### Issue #1: Commands Hang with --no-container Flag

**Severity:** HIGH

**Description:**
All scale operation commands (scale-up, scale-down, scale-clean, scale-validate) hang indefinitely even when the `--no-container` flag is provided. This flag is intended to skip automatic Neo4j container management, but the commands still attempt to connect to Neo4j and wait indefinitely.

**Commands Affected:**
- `atg scale-up template`
- `atg scale-up scenario`
- `atg scale-down algorithm`
- `atg scale-down pattern`
- `atg scale-stats` (when Neo4j is not running)
- `atg scale-validate` (when Neo4j is not running)
- `atg scale-clean` (when Neo4j is not running)

**Expected Behavior:**
When `--no-container` is specified, commands should either:
1. Connect to an existing Neo4j instance if available
2. Fail gracefully with a clear error message if Neo4j is unavailable
3. Skip operations that require Neo4j (for validation/dry-run modes)

**Actual Behavior:**
Commands hang indefinitely with no output or error message, requiring manual termination (Ctrl+C or timeout).

**Root Cause Analysis:**

Looking at the code in `src/cli_commands_scale.py`, all async handlers follow this pattern:

```python
async def scale_up_template_command_handler(...):
    # Connect to Neo4j
    config = create_neo4j_config_from_env()
    session_manager = Neo4jSessionManager(config.neo4j)
    session_manager.connect()  # <-- Hangs here if Neo4j not available
    ...
```

The `--no-container` flag is defined but **not passed to or used by the command handlers**. The handlers always attempt to connect to Neo4j regardless of the flag value.

**Recommended Fix:**

1. Pass the `no_container` parameter to all command handlers
2. Modify handlers to check the flag:
   ```python
   if not no_container:
       # Only connect if flag not set
       session_manager.connect()
   else:
       # Skip Neo4j operations or use mock/test mode
       console.print("[yellow]Skipping Neo4j connection (--no-container)[/yellow]")
   ```
3. Add connection timeout with retry logic
4. Provide clear error messages when connection fails

**Impact:**
- **Testing:** Cannot run automated CLI tests without a running Neo4j instance
- **Development:** Slows development workflow as all commands require Neo4j
- **CI/CD:** Makes it difficult to run quick validation tests in CI pipelines
- **User Experience:** Users experience hanging commands with no feedback

**Workaround:**
Currently, the only workaround is to ensure Neo4j is running before executing any scale operations commands.

### Issue #2: Missing Parameter Validation for Invalid Values

**Severity:** MEDIUM

**Description:**
Based on test scenario design, scale commands should validate parameter values (e.g., scale factors > 0, sample sizes between 0 and 1), but this validation needs to be tested once Issue #1 is resolved.

**Status:** Needs verification after fixing Issue #1

---

## Recommendations

### Immediate Actions (Priority 1)

1. **Fix --no-container Flag Implementation**
   - Modify all scale command handlers to respect the `--no-container` flag
   - Add graceful connection handling with timeouts
   - Implement clear error messages for connection failures

2. **Add Connection Timeout**
   - Set reasonable timeout (e.g., 10 seconds) for Neo4j connections
   - Fail fast with actionable error message

3. **Implement Mock/Test Mode**
   - Add `--test-mode` flag for running commands without Neo4j
   - Return mock data for testing CLI behavior

### Short-term Actions (Priority 2)

4. **Parameter Validation**
   - Add validation for scale factors (must be > 0)
   - Add validation for sample sizes (must be 0 < size <= 1.0)
   - Add validation for required files before connecting to Neo4j

5. **Integration with Existing Tests**
   - Add scale operations tests to CI pipeline
   - Run smoke tests on every PR
   - Run E2E tests nightly with real Neo4j instance

### Long-term Actions (Priority 3)

6. **Enhanced Error Handling**
   - Add detailed error messages for all failure modes
   - Include suggested fixes in error output
   - Log detailed errors for debugging

7. **Performance Optimization**
   - Add connection pooling for Neo4j
   - Implement lazy connection (connect only when needed)
   - Cache connection state to avoid repeated connection attempts

---

## How to Run Tests

### Prerequisites

```bash
# Navigate to spa directory
cd spa

# Install dependencies (if not already installed)
npm install

# Ensure gadugi is installed
npm list @gadugi/agentic-test
```

### Running Scale Operations Tests

#### Smoke Tests (Quick Validation)

```bash
# From spa directory
npm run test:ui -- scenarios/scale-operations-tests.yaml
```

Expected output:
- 26 test steps executed
- Help commands should pass
- Execution commands may timeout (Issue #1)

#### End-to-End Tests (Comprehensive)

```bash
# Ensure Neo4j is running first
docker ps | grep neo4j

# From spa directory
npm run test:ui -- scenarios/scale-operations-e2e-tests.yaml
```

Expected output:
- 38 test steps executed
- Requires working Neo4j connection
- Tests real command execution

### Running Individual Test Scenarios

```bash
# Run specific test scenario
node agentic-testing/run-ui-tests.js scenarios/scale-operations-tests.yaml

# Run with verbose output
DEBUG=* node agentic-testing/run-ui-tests.js scenarios/scale-operations-tests.yaml
```

### Manual CLI Testing

For manual testing without the framework:

```bash
# Navigate to project root
cd /home/azureuser/src/atg/worktrees/feat-issue-427-scale-operations

# Test help commands (these work)
uv run atg scale-stats --help
uv run atg scale-up template --help
uv run atg scale-down algorithm --help

# Test with template (currently hangs - Issue #1)
# uv run atg scale-up template --template-file test-data/scale-up-template-test.yaml --dry-run --no-container

# Test with Neo4j running
docker start neo4j  # if not running
uv run atg scale-stats
```

---

## Test Scenario Files Reference

### Created Files

1. **spa/agentic-testing/scenarios/scale-operations-tests.yaml**
   - Smoke tests for all scale commands
   - 26 test steps
   - Tests help output and parameter validation

2. **spa/agentic-testing/scenarios/scale-operations-e2e-tests.yaml**
   - End-to-end integration tests
   - 38 test steps
   - Tests real execution with parameters

3. **test-data/scale-up-template-test.yaml**
   - Sample template for scale-up testing
   - Defines VMs, VNets, Subnets, Storage Accounts
   - Includes relationship rules and validation

### Test Scenario Structure

Each YAML scenario file contains:

```yaml
name: "Test Suite Name"
description: "Description of what is being tested"
version: "1.0.0"

config:
  timeout: 120000  # Timeout in milliseconds
  retries: 2
  parallel: false

environment:
  requires:
    - AZURE_TENANT_ID
    - NEO4J_PASSWORD
    - NEO4J_PORT

agents:
  - name: "cli-agent"
    type: "system"
    config:
      shell: "bash"
      cwd: "/path/to/project"
      timeout: 60000
      capture_output: true

steps:
  - name: "Test Step Name"
    agent: "cli-agent"
    action: "execute_command"
    params:
      command: "uv run atg scale-stats --help"
    expect:
      exit_code: 0
      stdout_contains:
        - "expected string"
    timeout: 30000

assertions:
  - name: "Assertion Name"
    type: "command_success"
    agent: "cli-agent"
    params:
      step: "Test Step Name"

metadata:
  tags:
    - "cli"
    - "scale-operations"
  priority: "high"
  issue: "427"
```

---

## Conclusion

The gadugi-agentic-test framework is well-integrated into the Azure Tenant Grapher project and provides a solid foundation for CLI testing. Comprehensive test scenarios have been created for all scale operations commands.

**Key Findings:**
1. All scale commands have proper help output ✅
2. Commands hang when --no-container flag is used due to implementation gap ❌
3. Test infrastructure is ready for automated testing once Issue #1 is resolved

**Next Steps:**
1. Fix --no-container flag implementation (Issue #1)
2. Run full test suite with Neo4j available
3. Integrate tests into CI/CD pipeline
4. Add additional test scenarios for edge cases

---

## References

- **Gadugi Repository:** https://github.com/rysweet/gadugi-agentic-test
- **Issue #427:** Scale Operations Implementation
- **CLAUDE.md:** Project development guidelines
- **docs/testing/AGENT_MODE_TEST_IMPLEMENTATION.md:** Agent mode testing docs
- **docs/GADUGI_MIGRATION.md:** Migration from Python to Gadugi framework

---

**Last Updated:** 2025-11-11
**Status:** Test scenarios complete, execution blocked by Issue #1

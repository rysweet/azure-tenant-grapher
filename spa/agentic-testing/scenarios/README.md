# Test Scenarios

This directory contains YAML-based test scenarios for the TypeScript Agentic Testing System. Each scenario defines comprehensive test workflows that can be executed by autonomous testing agents.

## Overview

Test scenarios are defined in YAML format and describe complex testing workflows that involve multiple agents working together to test different aspects of the Azure Tenant Grapher application.

## Scenario Files

### Core Test Scenarios

1. **[cli-tests.yaml](./cli-tests.yaml)** - CLI Command Testing
   - Tests all core CLI commands (`atg --version`, `atg --help`, `atg build`, etc.)
   - Validates error handling for missing parameters
   - Tests command validation and help systems

2. **[ui-navigation.yaml](./ui-navigation.yaml)** - UI Navigation Testing
   - Tests navigation through all application tabs
   - Verifies UI components load correctly
   - Tests tab switching and state management

3. **[ui-workflows.yaml](./ui-workflows.yaml)** - Complete UI Workflows
   - End-to-end workflow testing for all major operations
   - Tests Build, Generate Spec, Generate IaC, Configuration workflows
   - Includes WebSocket communication testing

4. **[error-handling.yaml](./error-handling.yaml)** - Error Scenario Testing
   - Tests application behavior under various error conditions
   - Validates error messages and recovery mechanisms
   - Tests network failures, invalid inputs, and timeout scenarios

5. **[integration-tests.yaml](./integration-tests.yaml)** - Integration Testing
   - Tests CLI-UI synchronization
   - WebSocket communication validation
   - Neo4j database integration testing
   - Azure API interaction testing

## Scenario File Structure

Each YAML scenario file follows this standard structure:

```yaml
# Scenario metadata
name: "Descriptive Scenario Name"
description: "Detailed description of what this scenario tests"
version: "1.0.0"

# Test configuration
config:
  timeout: 120000      # Maximum time for entire scenario (ms)
  retries: 2           # Number of retries on failure
  parallel: false      # Whether steps can run in parallel

# Environment requirements
environment:
  requires:            # Required environment variables
    - REQUIRED_VAR_1
    - REQUIRED_VAR_2
  optional:            # Optional environment variables
    - OPTIONAL_VAR_1

# Agent definitions
agents:
  - name: "agent-name"
    type: "agent-type"  # ui, system, websocket, database, api, network
    config:
      # Agent-specific configuration

# Test execution steps
steps:
  - name: "Step Description"
    agent: "agent-name"
    action: "action-name"
    params:
      # Action parameters
    expect:
      # Expected outcomes
    timeout: 30000
    wait_for:
      # Conditions to wait for

# Validation assertions
assertions:
  - name: "Assertion Description"
    type: "assertion-type"
    agent: "agent-name"
    params:
      # Assertion parameters

# Cleanup actions
cleanup:
  - name: "Cleanup Description"
    agent: "agent-name"
    action: "cleanup-action"

# Metadata
metadata:
  tags: ["tag1", "tag2"]
  priority: "high"
  author: "author-name"
  created: "ISO-date"
  updated: "ISO-date"
```

## Agent Types

### UI Agent (`type: "ui"`)
Handles Electron application interactions via Playwright.

**Configuration:**
```yaml
config:
  browser: "chromium"     # Browser engine
  headless: false         # Run with or without UI
  viewport:
    width: 1280
    height: 720
  timeout: 30000
  slowMo: 500            # Slow down actions for stability
```

**Common Actions:**
- `launch_electron` - Launch Electron application
- `click` - Click on elements
- `fill` - Fill form inputs
- `wait_for_element` - Wait for element states
- `multi_action` - Execute multiple actions sequentially
- `execute_script` - Run JavaScript in the browser context
- `close_app` - Close the application

### System Agent (`type: "system"`)
Executes command-line operations and system interactions.

**Configuration:**
```yaml
config:
  shell: "bash"           # Shell to use
  cwd: "/path/to/directory"
  timeout: 60000
  capture_output: true    # Capture stdout/stderr
```

**Common Actions:**
- `execute_command` - Execute shell commands
- `check_process` - Check if processes are running
- `file_operations` - File system operations

### WebSocket Agent (`type: "websocket"`)
Manages WebSocket connections and real-time communication.

**Configuration:**
```yaml
config:
  url: "ws://localhost:3001"
  reconnect: true
  timeout: 10000
```

**Common Actions:**
- `connect` - Establish WebSocket connection
- `listen` - Listen for specific events
- `send_message` - Send messages
- `disconnect` - Close connections

### Database Agent (`type: "database"`)
Handles database operations and testing.

**Configuration:**
```yaml
config:
  type: "neo4j"
  host: "localhost"
  port: "7687"
  auth:
    username: "neo4j"
    password: "${NEO4J_PASSWORD}"
  timeout: 15000
```

**Common Actions:**
- `connect` - Connect to database
- `execute_query` - Run database queries
- `stress_test` - Performance testing
- `disconnect` - Close connections

### API Agent (`type: "api"`)
Tests REST API endpoints and external service integrations.

**Configuration:**
```yaml
config:
  timeout: 30000
  retry_count: 3
```

**Common Actions:**
- `authenticate_azure` - Azure authentication
- `call_api` - HTTP API calls
- `test_endpoints` - Endpoint validation

### Network Agent (`type: "network"`)
Simulates network conditions and failures.

**Configuration:**
```yaml
config:
  can_simulate_failures: true
  timeout: 10000
```

**Common Actions:**
- `block_port` - Block network ports
- `unblock_port` - Restore network access
- `simulate_latency` - Add network delays

## Writing New Scenarios

### 1. Define the Scenario Purpose
Start by clearly defining what your scenario will test:
- What functionality or workflow?
- What success criteria?
- What failure modes to test?

### 2. Choose Appropriate Agents
Select the agents needed for your test:
- UI testing: `ui-agent`
- CLI operations: `system-agent`
- Real-time updates: `websocket-agent`
- Database operations: `database-agent`
- API testing: `api-agent`
- Network conditions: `network-agent`

### 3. Plan the Test Steps
Break down your test into logical steps:
1. Setup/initialization
2. Main test actions
3. Verification/validation
4. Cleanup

### 4. Define Environment Requirements
List all environment variables needed:
- Required: Variables that must be present
- Optional: Variables that enhance testing but aren't mandatory

### 5. Write Comprehensive Assertions
Include assertions that validate:
- Expected outcomes occurred
- No unexpected errors happened
- System remains in valid state
- Performance criteria met

### 6. Include Proper Cleanup
Always include cleanup steps to:
- Close applications and connections
- Remove test data
- Restore system state
- Clean up temporary files

## Best Practices

### Naming Conventions
- Scenario files: `kebab-case.yaml`
- Step names: "Descriptive Action Description"
- Agent names: "purpose-agent" (e.g., "ui-agent", "cli-agent")

### Timeout Management
- Set appropriate timeouts for each step
- Consider network latency and system performance
- Use longer timeouts for integration tests
- Use shorter timeouts for unit-style tests

### Error Handling
- Include `expect_failure: true` for negative tests
- Use `optional: true` for steps that may not apply
- Include `ignore_errors: true` in cleanup steps
- Test both success and failure scenarios

### Environment Variables
- Use `${VAR_NAME}` syntax for variable substitution
- Provide defaults where appropriate: `${VAR_NAME:-default_value}`
- Document all required variables in the environment section

### Test Data Management
- Use unique identifiers: `test-${TIMESTAMP}`
- Clean up test data in cleanup section
- Don't rely on persistent state between tests

### Documentation
- Use descriptive names and descriptions
- Include comments for complex steps
- Tag scenarios appropriately for filtering
- Update metadata when modifying scenarios

## Example Minimal Scenario

```yaml
name: "Simple UI Test"
description: "Basic UI interaction test"
version: "1.0.0"

config:
  timeout: 60000
  retries: 1
  parallel: false

environment:
  requires:
    - ELECTRON_APP_PATH

agents:
  - name: "ui-agent"
    type: "ui"
    config:
      browser: "chromium"
      headless: false
      timeout: 30000

steps:
  - name: "Launch App"
    agent: "ui-agent"
    action: "launch_electron"
    params:
      executablePath: "${ELECTRON_APP_PATH}"
    timeout: 20000

  - name: "Click Button"
    agent: "ui-agent"
    action: "click"
    params:
      selector: "[data-testid='test-button']"
    wait_for:
      selector: "[data-testid='result']"
      state: "visible"

assertions:
  - name: "Result Displayed"
    type: "element_visible"
    agent: "ui-agent"
    params:
      selector: "[data-testid='result']"

cleanup:
  - name: "Close App"
    agent: "ui-agent"
    action: "close_app"

metadata:
  tags: ["ui", "simple"]
  priority: "medium"
  author: "developer"
  created: "2024-09-03T00:00:00Z"
```

## Running Scenarios

Scenarios are executed by the TypeScript Agentic Testing System orchestrator. The system will:

1. Parse the YAML scenario
2. Validate environment requirements
3. Initialize specified agents
4. Execute steps in sequence
5. Run assertions to validate outcomes
6. Execute cleanup procedures
7. Generate comprehensive reports

For more information on running scenarios, see the main [README.md](../README.md) in the parent directory.

## Contributing

When adding new scenarios:

1. Follow the established naming conventions
2. Include comprehensive test coverage
3. Add appropriate metadata and tags
4. Test your scenario thoroughly
5. Update this README if introducing new patterns
6. Consider both positive and negative test cases

## Troubleshooting

Common issues when writing scenarios:

- **Timeouts**: Increase timeout values for slow operations
- **Element selectors**: Use `data-testid` attributes for reliable selection
- **Environment variables**: Ensure all required variables are documented
- **Agent configuration**: Verify agent types and configurations are valid
- **Step dependencies**: Ensure steps execute in logical order
- **Cleanup failures**: Use `ignore_errors: true` for non-critical cleanup steps

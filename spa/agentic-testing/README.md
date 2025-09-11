# TypeScript Agentic Testing System

A comprehensive TypeScript-based testing framework designed specifically for testing Electron applications with AI-powered autonomous agents. This system provides intelligent test orchestration, scenario-based testing, and integration with external services like GitHub API.

## Overview

The Agentic Testing System enables automated testing of complex Electron applications by using intelligent agents that can:

- Execute test scenarios autonomously
- Interact with Electron applications via Playwright
- Communicate with external APIs (GitHub, Azure, etc.)
- Generate dynamic test reports and insights
- Coordinate multiple testing agents for comprehensive coverage

## Architecture

### Core Components

#### 1. Agents (`src/agents/`)
Autonomous testing agents that execute specific testing tasks:
- **UI Agent**: Handles Electron UI interactions via Playwright
- **API Agent**: Tests REST API endpoints and WebSocket connections
- **GitHub Agent**: Manages GitHub integrations and CI/CD testing
- **System Agent**: Tests system-level integrations and CLI operations

#### 2. Orchestrator (`src/orchestrator/`)
Central coordination system that:
- Manages agent lifecycle and communication
- Schedules test execution based on scenarios
- Aggregates results and generates reports
- Handles error recovery and retry logic

#### 3. Scenarios (`src/scenarios/`)
Test scenario definitions and execution logic:
- YAML-based scenario descriptions (stored in `/scenarios/`)
- TypeScript scenario processors
- Dynamic scenario generation based on application state

#### 4. Utilities (`src/utils/`)
Shared utilities and helper functions:
- Logging and monitoring utilities
- Configuration management
- WebSocket communication helpers
- File system and path utilities

#### 5. Models (`src/models/`)
TypeScript interfaces and type definitions for:
- Agent communication protocols
- Test scenario structures
- Result data models
- Configuration schemas

## Installation

```bash
# Install dependencies
npm install

# Build TypeScript
npm run build

# Run tests
npm test
```

## Usage

### Command Line Interface

The system provides a CLI for running tests:

```bash
# Run all scenarios
npx agentic-test run

# Run specific scenario
npx agentic-test run --scenario "ui-workflow"

# Run with custom configuration
npx agentic-test run --config ./custom-config.yaml

# Watch mode for development
npx agentic-test watch
```

### Programmatic Usage

```typescript
import { AgenticOrchestrator } from '@/orchestrator';
import { ScenarioLoader } from '@/scenarios';

const orchestrator = new AgenticOrchestrator({
  logLevel: 'info',
  maxConcurrentAgents: 3,
  retryAttempts: 2
});

const scenarios = await ScenarioLoader.loadFromDirectory('./scenarios');
const results = await orchestrator.executeScenarios(scenarios);
```

## Configuration

Configuration is managed through environment variables and YAML files:

### Environment Variables
```bash
# GitHub API token for CI/CD testing
GITHUB_TOKEN=your_token_here

# Electron app path for testing
ELECTRON_APP_PATH=/path/to/your/electron/app

# Test data directory
TEST_DATA_DIR=./test-data

# Log level (debug, info, warn, error)
LOG_LEVEL=info

# WebSocket connection for real-time communication
WEBSOCKET_URL=ws://localhost:3001
```

### YAML Scenario Configuration

Create scenario files in the `scenarios/` directory:

```yaml
# scenarios/ui-workflow.yaml
name: "UI Workflow Test"
description: "Test main UI workflow functionality"
agents:
  - type: "ui"
    config:
      browser: "chromium"
      headless: false
      timeout: 30000
steps:
  - action: "launch_app"
  - action: "navigate_to_tab"
    params:
      tab: "Build"
  - action: "fill_form"
    params:
      tenant_id: "test-tenant-123"
  - action: "click_button"
    params:
      selector: "[data-testid='build-submit']"
  - action: "wait_for_completion"
    params:
      timeout: 60000
assertions:
  - type: "element_visible"
    selector: "[data-testid='build-success']"
  - type: "log_contains"
    message: "Build completed successfully"
```

## Development

### Project Structure

```
spa/agentic-testing/
├── src/
│   ├── agents/              # Agent implementations
│   ├── orchestrator/        # Test coordination logic
│   ├── scenarios/           # Scenario processing
│   ├── utils/              # Shared utilities
│   └── models/             # TypeScript interfaces
├── scenarios/              # YAML scenario definitions
├── tests/                  # Unit and integration tests
├── package.json           # Dependencies and scripts
├── tsconfig.json          # TypeScript configuration
└── README.md              # This file
```

### Development Scripts

```bash
# Start development mode with file watching
npm run dev

# Run linter
npm run lint

# Fix linting issues
npm run lint:fix

# Run tests with coverage
npm run test:coverage

# Run tests in watch mode
npm run test:watch

# Clean build artifacts
npm run clean

# Build for production
npm run build
```

### Adding New Agents

1. Create agent class in `src/agents/`:
```typescript
import { BaseAgent } from './BaseAgent';

export class CustomAgent extends BaseAgent {
  async execute(scenario: Scenario): Promise<TestResult> {
    // Implementation
  }
}
```

2. Register agent in orchestrator
3. Add corresponding scenario types
4. Create tests for the new agent

### Adding New Scenarios

1. Create YAML file in `scenarios/` directory
2. Define scenario structure with agents, steps, and assertions
3. Test scenario with CLI: `npx agentic-test run --scenario "your-scenario"`

## Integration Points

### Electron Application
- Uses Playwright for Electron app automation
- Supports both headless and headed testing modes
- Can test main process and renderer process interactions

### GitHub Integration
- Automated PR testing and status reporting
- CI/CD pipeline integration
- Issue and milestone tracking for test results

### WebSocket Communication
- Real-time communication with running Electron app
- Live log streaming during test execution
- Dynamic test parameter updates

### Azure Integration
- Azure tenant discovery testing
- Microsoft Graph API integration testing
- Neo4j graph database validation

## Testing Strategy

### Unit Tests
- Individual agent functionality
- Scenario parsing and validation
- Utility function testing

### Integration Tests
- Agent-to-agent communication
- Orchestrator workflow testing
- External API integration validation

### End-to-End Tests
- Full application workflow testing
- Multi-agent coordination scenarios
- Performance and reliability testing

## Monitoring and Logging

The system uses Winston for structured logging:

```typescript
import { logger } from '@/utils/logger';

logger.info('Test scenario started', {
  scenario: scenario.name,
  agent: agent.type,
  timestamp: new Date().toISOString()
});
```

Log levels:
- `debug`: Detailed execution information
- `info`: General test progress and results
- `warn`: Non-critical issues and warnings
- `error`: Test failures and system errors

## Contributing

1. Follow TypeScript best practices
2. Write comprehensive tests for new features
3. Update documentation for API changes
4. Use conventional commit messages
5. Ensure all tests pass before submitting PRs

## License

MIT License - see the main project license for details.

# Agentic Testing System

AI-powered autonomous testing system for Azure Tenant Grapher that tests both CLI and Electron GUI interfaces, discovers issues, and automatically documents them as GitHub issues.

## Architecture

The system follows a Magentic-One inspired multi-agent architecture:

- **Orchestrator**: Coordinates all agents and manages test execution
- **CLI Agent**: Tests command-line interface functionality
- **Electron UI Agent**: Tests GUI using Playwright
- **Comprehension Agent**: Analyzes documentation to generate test scenarios
- **Issue Reporter**: Creates GitHub issues for failures
- **Priority Agent**: Analyzes and prioritizes test failures

## Installation

```bash
# Install dependencies
pip install playwright openai pyyaml

# Install Playwright browsers
playwright install

# For GitHub integration, authenticate gh CLI
gh auth login
```

## Configuration

Edit `agentic_testing/config.yaml` to configure:
- CLI command settings
- UI testing parameters
- LLM provider (Azure OpenAI or OpenAI)
- GitHub repository for issue creation
- Test execution parameters

## Usage

### Run Tests

```bash
# Run smoke tests (default)
python -m agentic_testing.main

# Run full test suite
python -m agentic_testing.main --suite full

# Run regression tests
python -m agentic_testing.main --suite regression

# Dry run to see what would be tested
python -m agentic_testing.main --dry-run

# Skip GitHub issue creation
python -m agentic_testing.main --no-issues

# Save results to file
python -m agentic_testing.main --output results.json
```

### Test Suites

- **smoke**: Quick basic functionality tests
- **full**: All available test scenarios
- **regression**: Comprehensive regression testing

## Test Scenarios

Test scenarios are defined in YAML files in the `scenarios/` directory:

- `cli_basic.yaml`: Basic CLI command tests
- `ui_navigation.yaml`: UI navigation and element tests

## Components

### Models (`models.py`)
- `TestScenario`: Test scenario definition
- `TestResult`: Test execution result
- `TestFailure`: Failure information for reporting
- `TestStep`: Individual test action
- `VerificationStep`: Verification criteria

### Agents (`agents/`)
- `CLIAgent`: Executes CLI commands and captures output
- `ElectronUIAgent`: Controls Electron app via Playwright
- `ComprehensionAgent`: Uses LLM to understand features
- `IssueReporter`: Creates GitHub issues using gh CLI
- `PriorityAgent`: Analyzes failure impact and priority

### Orchestrator (`orchestrator.py`)
Main coordinator that:
1. Discovers features from documentation
2. Generates test scenarios
3. Executes tests in parallel
4. Analyzes results
5. Reports failures to GitHub

### Configuration (`config.py`)
Dataclass-based configuration system with:
- CLI testing settings
- UI testing settings
- LLM configuration
- GitHub integration
- Priority weights
- Execution parameters

## Environment Variables

Required:
- `AZURE_TENANT_ID`: Azure tenant for testing
- `AZURE_CLIENT_ID`: Azure client ID
- `AZURE_CLIENT_SECRET`: Azure client secret
- `NEO4J_PASSWORD`: Neo4j database password

For LLM (Azure OpenAI):
- `AZURE_OPENAI_DEPLOYMENT`: Deployment name
- `AZURE_OPENAI_KEY`: API key
- `AZURE_OPENAI_ENDPOINT`: Endpoint URL

For LLM (OpenAI):
- `OPENAI_API_KEY`: OpenAI API key

## Output

Test results are saved to:
- `outputs/logs/`: Test execution logs
- `outputs/screenshots/`: UI test screenshots
- `outputs/sessions/`: Complete session results
- GitHub Issues: Automatic issue creation for failures

## Features

- **Parallel Execution**: Run multiple tests concurrently
- **Retry Logic**: Automatic retry with exponential backoff
- **Deduplication**: Avoid creating duplicate GitHub issues
- **Priority Analysis**: Impact-based failure prioritization
- **LLM Comprehension**: Generate tests from documentation
- **Cross-Interface**: Test both CLI and GUI interfaces

## Development

### Adding Test Scenarios

Create YAML files in `scenarios/` with test definitions:

```yaml
scenarios:
  - id: unique_test_id
    feature: Feature Name
    name: Test Name
    description: Test Description
    interface: cli|gui|mixed
    steps:
      - action: execute|click|type|verify
        target: command|selector
        value: input_value
    expected_outcome: Expected result
    verification:
      - type: text|element
        target: output|selector
        expected: value
        operator: equals|contains
    tags: [smoke-test, feature-area]
    priority: critical|high|medium|low
```

### Extending Agents

1. Create new agent class in `agents/`
2. Implement required methods
3. Register in orchestrator
4. Add configuration in `config.py`

## Testing the Testing System

```bash
# Run in dry-run mode first
python -m agentic_testing.main --dry-run

# Test with a single scenario
python -m agentic_testing.main --suite smoke --no-issues

# Enable debug logging
python -m agentic_testing.main --log-level DEBUG
```

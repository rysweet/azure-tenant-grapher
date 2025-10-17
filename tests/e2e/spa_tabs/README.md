# SPA Tabs E2E Test Suite

Comprehensive end-to-end tests for the SPA tab components using Playwright and the gadugi-agentic-test framework.

## Overview

This test suite provides thorough testing coverage for all major tab components in the SPA:

- **Status Tab**: Real-time updates, system monitoring, WebSocket communication
- **Create Tenant Tab**: Form validation, tenant creation workflow, bulk operations
- **Threat Model Tab**: Threat generation, STRIDE analysis, MITRE ATT&CK mapping
- **Undeploy Tab**: Resource cleanup, safety checks, dependency management
- **Docs Tab**: Documentation navigation, search, version management

## Test Structure

```
tests/e2e/spa_tabs/
├── conftest.py                    # Shared fixtures and configuration
├── test_status_tab.py            # Status tab tests
├── test_create_tenant_tab.py    # Create Tenant tab tests
├── test_threat_model_tab.py     # Threat Model tab tests
├── test_undeploy_tab.py         # Undeploy tab tests
├── test_docs_tab.py             # Documentation tab tests
└── README.md                    # This file
```

## Agentic Testing Scenarios

The gadugi-agentic-test framework scenarios are located at:
```
spa/agentic-testing/scenarios/spa-tabs-workflows.yaml
```

This YAML file defines comprehensive workflow scenarios that can be executed by the agentic testing system.

## Prerequisites

### Required Dependencies

```bash
# Install Python dependencies
pip install pytest pytest-asyncio playwright websockets

# Install Playwright browsers
playwright install chromium

# Install Node dependencies for agentic testing
cd spa/agentic-testing
npm install
```

### Environment Variables

Set these environment variables before running tests:

```bash
# Required
export SPA_SERVER_URL="http://localhost:3000"
export ELECTRON_APP_PATH="/path/to/electron/app"

# Optional
export WEBSOCKET_URL="ws://localhost:3001"
export HEADLESS="false"  # Set to true for headless testing
export AZURE_TENANT_ID="your-tenant-id"
export NEO4J_PASSWORD="your-password"
```

## Running Tests

### Run All E2E Tests

```bash
# From the project root
pytest tests/e2e/spa_tabs/ -v

# With coverage
pytest tests/e2e/spa_tabs/ --cov=spa --cov-report=html
```

### Run Specific Tab Tests

```bash
# Test only Status tab
pytest tests/e2e/spa_tabs/test_status_tab.py -v

# Test only Create Tenant tab
pytest tests/e2e/spa_tabs/test_create_tenant_tab.py -v

# Test specific test case
pytest tests/e2e/spa_tabs/test_status_tab.py::TestStatusTab::test_real_time_updates -v
```

### Run with Agentic Testing Framework

```bash
# Navigate to agentic-testing directory
cd spa/agentic-testing

# Run SPA tabs workflow scenarios
npm run test -- --scenario spa-tabs-workflows

# Run specific scenario
npm run test -- --scenario spa-tabs-workflows --test "Status Tab Real-time Monitoring"
```

### Parallel Execution

```bash
# Run tests in parallel with pytest-xdist
pytest tests/e2e/spa_tabs/ -n auto

# Run with 4 workers
pytest tests/e2e/spa_tabs/ -n 4
```

## Test Features

### Fixtures (conftest.py)

- **browser**: Playwright browser instance
- **browser_context**: Isolated browser context per test
- **page**: Page object for UI interactions
- **spa_server**: Ensures SPA server is running
- **websocket_listener**: Captures WebSocket events
- **mock_azure_config**: Mock Azure configuration
- **mock_neo4j_config**: Mock Neo4j configuration

### Helper Fixtures

- **assert_element_visible**: Assert element visibility
- **assert_element_text**: Assert element text content
- **capture_screenshot**: Capture screenshots during tests

## Test Coverage

### Status Tab Tests
- Navigation and initial load
- Real-time WebSocket updates
- Service health indicators
- Activity log updates
- System metrics display
- Error state handling and recovery
- Auto-refresh functionality
- Connection status monitoring
- Status report export
- Responsive layout

### Create Tenant Tab Tests
- Form navigation
- Input validation rules
- Advanced configuration options
- Successful tenant creation flow
- Error handling
- Bulk tenant creation from CSV
- Template selection
- Password strength indicator
- Form autosave
- Keyboard navigation

### Threat Model Tab Tests
- Navigation and UI components
- Threat model generation
- STRIDE methodology analysis
- Threat filtering and search
- Detailed threat view and editing
- Export in multiple formats (JSON, CSV, PDF)
- MITRE ATT&CK framework mapping
- Model comparison
- Template usage
- Collaborative features

### Undeploy Tab Tests
- Resource listing
- Selection mechanisms
- Dependency warnings
- Safe undeploy mode with confirmations
- Force undeploy mode
- Progress tracking
- Rollback capability
- Resource filtering
- Export reports
- Operation history

### Docs Tab Tests
- Documentation tree navigation
- Search functionality
- Table of contents
- Code examples with copy
- External link handling
- Breadcrumb navigation
- Version selection
- Print-friendly view
- Responsive layout
- Feedback widget
- Offline support
- Keyboard shortcuts

## Debugging Tests

### Enable Debug Mode

```bash
# Run with Playwright debug mode
PWDEBUG=1 pytest tests/e2e/spa_tabs/test_status_tab.py

# Run with headed browser
HEADLESS=false pytest tests/e2e/spa_tabs/
```

### Capture Screenshots on Failure

Screenshots are automatically captured on test failure and saved to:
```
tests/e2e/spa_tabs/screenshots/
```

### View Test Reports

```bash
# Generate HTML report
pytest tests/e2e/spa_tabs/ --html=report.html --self-contained-html

# Open coverage report
open htmlcov/index.html
```

## CI/CD Integration

### GitHub Actions Example

```yaml
name: E2E Tests

on: [push, pull_request]

jobs:
  e2e-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2

      - name: Setup Node.js
        uses: actions/setup-node@v2
        with:
          node-version: '18'

      - name: Setup Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          npm ci
          pip install -r requirements-test.txt
          playwright install chromium

      - name: Start SPA server
        run: |
          npm run dev &
          sleep 10

      - name: Run E2E tests
        env:
          SPA_SERVER_URL: http://localhost:3000
          HEADLESS: true
        run: |
          pytest tests/e2e/spa_tabs/ -v --junit-xml=test-results.xml

      - name: Upload test results
        uses: actions/upload-artifact@v2
        if: always()
        with:
          name: test-results
          path: |
            test-results.xml
            tests/e2e/spa_tabs/screenshots/
```

## Best Practices

### Test Writing Guidelines

1. **Use data-testid attributes**: All interactive elements should have `data-testid` attributes
2. **Avoid hard-coded waits**: Use Playwright's built-in waiting mechanisms
3. **Mock external dependencies**: Use API mocking for consistent test results
4. **Test user workflows**: Focus on complete user journeys, not just individual components
5. **Handle async operations**: Properly await all async operations
6. **Clean up after tests**: Reset state and clean up resources

### Performance Considerations

- Use `page.wait_for_load_state()` for navigation
- Minimize unnecessary waits with proper selectors
- Run tests in parallel when possible
- Use browser context isolation for test independence
- Cache static resources when appropriate

### Maintenance

- Keep selectors up-to-date with UI changes
- Update mock data to reflect API changes
- Review and update test scenarios quarterly
- Monitor test execution times and optimize slow tests
- Maintain test documentation

## Troubleshooting

### Common Issues

1. **Tests timing out**
   - Increase timeout values in conftest.py
   - Check if SPA server is running
   - Verify WebSocket connection

2. **Element not found**
   - Verify data-testid attributes exist
   - Check if element is in viewport
   - Wait for dynamic content to load

3. **WebSocket connection issues**
   - Ensure WebSocket server is running
   - Check WEBSOCKET_URL environment variable
   - Verify firewall settings

4. **Screenshot failures**
   - Ensure screenshots directory exists
   - Check disk space
   - Verify write permissions

## Contributing

When adding new tests:

1. Follow existing test structure and naming conventions
2. Add comprehensive docstrings
3. Include both positive and negative test cases
4. Update this README with new test coverage
5. Ensure tests are idempotent and isolated
6. Add appropriate fixtures to conftest.py if needed
7. Update agentic testing scenarios in YAML

## Resources

- [Playwright Documentation](https://playwright.dev/python/)
- [Pytest Documentation](https://docs.pytest.org/)
- [Agentic Testing Framework](../../../spa/agentic-testing/README.md)
- [SPA Documentation](../../../spa/README.md)

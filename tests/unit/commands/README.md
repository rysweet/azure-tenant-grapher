# CLI Commands Test Suite

## Overview

Comprehensive pytest-based test coverage for Azure Tenant Grapher CLI command modules. This test suite achieves 85%+ coverage across 8 critical command modules using the TDD testing pyramid approach (60% unit, 30% integration, 10% E2E).

## Test Structure

Tests are organized parallel to source structure:

```
tests/unit/commands/
├── README.md (this file)
├── conftest.py (shared fixtures and mocks)
├── test_scan.py (scan/build command tests)
├── test_visualize.py (visualization command tests)
├── test_deploy.py (IaC deployment tests)
├── test_undeploy.py (IaC cleanup tests)
├── test_agent.py (agent mode tests)
├── test_mcp.py (MCP server tests)
├── test_lighthouse.py (Azure Lighthouse tests)
└── test_auth.py (authentication tests)
```

## Testing Philosophy

Following project philosophy (@.claude/context/PHILOSOPHY.md):

- **Ruthless Simplicity**: Test behavior at module boundaries, not implementation details
- **Zero-BS Implementation**: Every test must work, no stubs or placeholders
- **Test-Driven Development**: Tests written before implementation (TDD approach)
- **Modular Design**: Tests isolated from each other, clean boundaries

## Test Coverage Target

Each command module achieves **85%+ coverage** across:

- **Click command decorators and parameters** (CLI interface)
- **Command handler functions** (business logic)
- **Success paths** (happy path scenarios)
- **Error paths** (exception handling, user errors)
- **Edge cases** (boundary conditions, unusual inputs)

## Testing Pyramid Distribution

### Unit Tests (60%)

Test individual functions and methods in isolation with mocked dependencies:

- Parameter validation
- Configuration creation
- Error handling logic
- Helper function behavior
- Return value correctness

**Example**: `test_scan_parameter_validation()` verifies tenant-id validation without actually calling Azure SDK.

### Integration Tests (30%)

Test multiple components working together with some real dependencies:

- Command → Handler → Service interactions
- Neo4j session creation (with test database)
- File I/O operations
- Configuration loading

**Example**: `test_scan_creates_dashboard_manager()` verifies full initialization chain with real config objects.

### End-to-End Tests (10%)

Test complete workflows with realistic scenarios:

- Full command execution via Click testing
- Complete success/failure flows
- User-facing behavior verification
- CLI output format validation

**Example**: `test_scan_command_full_workflow()` executes entire scan command with mocked Azure SDK.

## Common Testing Patterns

### 1. Click Command Testing

```python
from click.testing import CliRunner

def test_scan_command_basic():
    runner = CliRunner()
    result = runner.invoke(scan, ["--tenant-id", "test-tenant"])
    assert result.exit_code == 0
    assert "Building graph" in result.output
```

### 2. Async Command Handler Testing

```python
import pytest

@pytest.mark.asyncio
async def test_scan_handler_creates_grapher(mock_config, mock_neo4j):
    result = await build_command_handler(
        ctx=mock_context,
        tenant_id="test-tenant",
        # ... other parameters
    )
    assert result is not None
    mock_neo4j.assert_called_once()
```

### 3. Mock External Dependencies

```python
@pytest.fixture
def mock_azure_sdk(mocker):
    """Mock Azure SDK calls to avoid real API calls."""
    return mocker.patch("azure.identity.DefaultAzureCredential")

@pytest.fixture
def mock_neo4j_session(mocker):
    """Mock Neo4j session to avoid database dependency."""
    return mocker.patch("src.neo4j_session_manager.Neo4jSessionManager")
```

### 4. Exception Path Testing

```python
def test_scan_handles_azure_auth_failure(mock_azure_sdk):
    mock_azure_sdk.side_effect = CredentialUnavailableError("Auth failed")
    runner = CliRunner()
    result = runner.invoke(scan, ["--tenant-id", "test"])
    assert result.exit_code == 1
    assert "Auth failed" in result.output
```

## Shared Test Fixtures

Located in `conftest.py`:

- `mock_click_context`: Simulated Click context with obj dict
- `mock_neo4j_config`: Neo4j configuration for testing
- `mock_azure_credentials`: Mocked Azure authentication
- `temp_output_dir`: Temporary directory for file outputs
- `mock_dashboard`: Mocked RichDashboard for UI testing

## Per-Command Test Coverage

### test_scan.py (scan.py coverage)

**Target Coverage**: 85%+

**Test Categories**:
- Parameter validation (tenant-id required, resource-limit numeric, etc.)
- Neo4j container startup logic
- Version mismatch detection and warning
- Filter configuration (subscriptions, resource groups)
- Dashboard creation and initialization
- Error handling (auth failures, Neo4j connection errors)
- Test mode execution (--resource-limit)
- Flag combinations (--no-dashboard, --no-container, --no-aad-import)

**Key Tests**:
- `test_scan_requires_tenant_id`: Verify tenant-id is mandatory
- `test_scan_starts_neo4j_when_not_running`: Container startup logic
- `test_scan_version_mismatch_warning`: Version detection integration
- `test_scan_filtered_by_subscriptions`: Filter configuration
- `test_scan_error_handling_auth_failure`: Azure auth error path
- `test_scan_dashboard_mode_vs_no_dashboard`: UI mode switching

### test_visualize.py (visualize.py coverage)

**Target Coverage**: 85%+

**Test Categories**:
- Neo4j connection handling
- HTML output generation
- Link hierarchy option
- Custom output path
- Container auto-start on connection failure
- Retry logic for connection establishment
- Error messaging and guidance

**Key Tests**:
- `test_visualize_generates_html_output`: Happy path with default output
- `test_visualize_custom_output_path`: Custom path handling
- `test_visualize_link_hierarchy_enabled`: Hierarchical edge creation
- `test_visualize_neo4j_connection_failure`: Connection error handling
- `test_visualize_auto_starts_container`: Container startup on failure
- `test_visualize_retry_logic`: Connection retry mechanism

### test_deploy.py (deploy.py coverage)

**Target Coverage**: 85%+

**Test Categories**:
- Terraform deployment workflow
- Job tracking initialization
- Resource group creation
- Deployment plan generation
- Apply operation
- State management
- Error handling (Terraform failures, permission errors)

**Key Tests**:
- `test_deploy_creates_terraform_files`: File generation
- `test_deploy_initializes_job_tracking`: Job tracking setup
- `test_deploy_plan_generation`: Terraform plan creation
- `test_deploy_apply_workflow`: Full apply operation
- `test_deploy_error_handling_terraform_failure`: Terraform error handling
- `test_deploy_cleanup_on_failure`: Cleanup on error

### test_undeploy.py (undeploy.py coverage)

**Target Coverage**: 85%+

**Test Categories**:
- Resource deletion workflow
- Dependency ordering
- Force delete option
- Dry run mode
- Cleanup verification
- Error handling (resource not found, deletion failures)

**Key Tests**:
- `test_undeploy_lists_resources_to_delete`: Resource discovery
- `test_undeploy_respects_dependencies`: Dependency ordering
- `test_undeploy_force_delete_option`: Force flag behavior
- `test_undeploy_dry_run_mode`: Dry run execution
- `test_undeploy_error_handling_not_found`: Resource not found handling
- `test_undeploy_partial_failure_handling`: Partial deletion errors

### test_agent.py (agent.py coverage)

**Target Coverage**: 85%+

**Test Categories**:
- MCP server initialization
- AutoGen agent loop startup
- Question mode (single question)
- Interactive mode startup
- Neo4j connection verification
- Error handling (MCP server failures, agent errors)

**Key Tests**:
- `test_agent_mode_interactive_startup`: Interactive mode
- `test_agent_mode_single_question`: Question mode execution
- `test_agent_mode_mcp_server_init`: MCP server initialization
- `test_agent_mode_neo4j_connection`: Neo4j connection check
- `test_agent_mode_error_handling_mcp_failure`: MCP error handling
- `test_agent_mode_logging_configuration`: Logging setup

### test_mcp.py (mcp.py coverage)

**Target Coverage**: 85%+

**Test Categories**:
- MCP server startup
- Graph query endpoint
- Cypher query execution
- Query parameter validation
- Server shutdown
- Error handling (invalid queries, connection errors)

**Key Tests**:
- `test_mcp_server_starts_successfully`: Server startup
- `test_mcp_query_execution`: Query execution
- `test_mcp_query_parameter_validation`: Input validation
- `test_mcp_server_shutdown`: Graceful shutdown
- `test_mcp_error_handling_invalid_query`: Query error handling
- `test_mcp_connection_error_handling`: Connection error path

### test_lighthouse.py (lighthouse.py coverage)

**Target Coverage**: 85%+

**Test Categories**:
- Azure Lighthouse delegation creation
- Tenant scanning
- Permission assignment
- Delegation removal
- Status checking
- Error handling (permission errors, API failures)

**Key Tests**:
- `test_lighthouse_create_delegation`: Delegation creation
- `test_lighthouse_scan_tenant`: Tenant scanning
- `test_lighthouse_assign_permissions`: Permission assignment
- `test_lighthouse_remove_delegation`: Delegation removal
- `test_lighthouse_status_check`: Status verification
- `test_lighthouse_error_handling_permissions`: Permission error handling

### test_auth.py (auth.py coverage)

**Target Coverage**: 85%+

**Test Categories**:
- App registration creation
- Service principal setup
- Permission grant
- Secret generation
- Configuration update
- Error handling (registration failures, permission errors)

**Key Tests**:
- `test_auth_create_app_registration`: App registration
- `test_auth_create_service_principal`: Service principal creation
- `test_auth_grant_permissions`: Permission granting
- `test_auth_generate_secret`: Secret generation
- `test_auth_update_config`: Configuration update
- `test_auth_error_handling_registration_failure`: Registration error handling

## Running Tests

```bash
# All command tests
pytest tests/unit/commands/

# Specific command module
pytest tests/unit/commands/test_scan.py

# With coverage report
pytest tests/unit/commands/ --cov=src/commands --cov-report=html

# Verbose mode
pytest tests/unit/commands/ -v

# Parallel execution
pytest tests/unit/commands/ -n auto
```

## Coverage Reporting

Generate coverage reports to verify 85%+ target:

```bash
# Terminal report
pytest tests/unit/commands/ --cov=src/commands --cov-report=term-missing

# HTML report (detailed line-by-line)
pytest tests/unit/commands/ --cov=src/commands --cov-report=html
open htmlcov/index.html

# XML report (for CI integration)
pytest tests/unit/commands/ --cov=src/commands --cov-report=xml
```

## Continuous Integration

Tests run automatically on:
- Every push to any branch
- Every pull request
- Nightly full test suite runs

CI verifies:
- All tests pass
- Coverage >= 85% per module
- No test failures or errors
- Pre-commit hooks pass

## Best Practices

1. **Mock External Dependencies**: Never call real Azure APIs or databases in unit tests
2. **Test Behavior, Not Implementation**: Focus on what commands do, not how they do it
3. **Clear Test Names**: Use descriptive names like `test_scan_handles_auth_failure`
4. **Isolated Tests**: Each test should be independent, no shared state
5. **Fast Execution**: Unit tests should run in milliseconds, not seconds
6. **Meaningful Assertions**: Assert specific values, not just "no exception"
7. **Error Message Testing**: Verify error messages are helpful to users

## Maintenance

When adding new CLI commands or modifying existing ones:

1. Update tests FIRST (TDD approach)
2. Maintain 85%+ coverage
3. Follow testing pyramid distribution
4. Add new shared fixtures to `conftest.py`
5. Update this README with new patterns or changes

## Known Limitations

- Some E2E tests may require actual Azure authentication (marked with `@pytest.mark.azure_auth`)
- Neo4j integration tests use test database (requires Docker)
- MCP server tests use ephemeral test server instance

## References

- Project Testing Strategy: @.claude/context/PROJECT.md "Testing Strategy"
- Testing Philosophy: @.claude/context/PHILOSOPHY.md "Testing Approach"
- Testing Patterns: @.claude/context/PATTERNS.md "Pattern: TDD Testing Pyramid"

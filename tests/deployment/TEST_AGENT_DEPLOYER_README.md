## Goal-Seeking Deployment Agent Tests (Issue #610)

Ahoy! These tests be written in TDD (Test-Driven Development) style, meanin' they were crafted BEFORE the implementation. They'll fail initially, and that be exactly what we want!

### Test Philosophy

These tests follow the testing pyramid principle:
- **60% Unit Tests**: Fast, focused tests of individual methods
- **30% Integration Tests**: Tests of the deployment loop with mocked dependencies
- **10% E2E Tests**: Full CLI integration tests

### Test Files

```
tests/
├── deployment/
│   ├── test_agent_deployer.py       # Unit + Integration tests
│   ├── conftest.py                  # Shared fixtures
│   └── TEST_AGENT_DEPLOYER_README.md (this file)
└── commands/
    └── test_deploy_agent.py         # E2E CLI tests
```

### Running the Tests

#### Run All Agent Tests
```bash
# From project root
uv run pytest tests/deployment/test_agent_deployer.py tests/commands/test_deploy_agent.py -v
```

#### Run Only Unit Tests
```bash
uv run pytest tests/deployment/test_agent_deployer.py::TestAgentDeployerInit -v
uv run pytest tests/deployment/test_agent_deployer.py::TestAgentDeployerStateTracking -v
```

#### Run Only Integration Tests
```bash
uv run pytest tests/deployment/test_agent_deployer.py::TestDeploymentLoop -v
uv run pytest tests/deployment/test_agent_deployer.py::TestErrorHandling -v
```

#### Run Only E2E Tests
```bash
uv run pytest tests/commands/test_deploy_agent.py -v
```

#### Run with Coverage
```bash
uv run pytest tests/deployment/test_agent_deployer.py tests/commands/test_deploy_agent.py --cov=src.deployment.agent_deployer --cov-report=term-missing
```

### Expected Test States

#### Before Implementation (Current State)
All tests will be **SKIPPED** with message:
```
SKIPPED [X] AgentDeployer not implemented yet (TDD - tests written first)
```

This is CORRECT! Tests are written first in TDD.

#### During Implementation
As you implement AgentDeployer, tests will start **FAILING** with specific error messages:
```
FAILED tests/deployment/test_agent_deployer.py::TestAgentDeployerInit::test_init_with_defaults
AssertionError: assert deployer.max_iterations == 20
```

This is PROGRESS! Tests are running but catching bugs.

#### After Implementation
Tests will **PASS**:
```
PASSED tests/deployment/test_agent_deployer.py::TestAgentDeployerInit::test_init_with_defaults
```

This is SUCCESS! Implementation matches specification.

### Test Coverage by Component

#### AgentDeployer Class
- **Initialization**: 5 tests
  - Default parameters
  - Custom limits
  - Input validation (iac_dir, tenant_id, resource_group)

- **State Tracking**: 4 tests
  - Iteration counter
  - Error logging
  - Max iteration detection
  - State snapshot

- **Deployment Loop**: 4 tests
  - Single iteration success
  - Multiple iterations with recovery
  - Max iterations reached
  - Timeout handling

- **Error Handling**: 3 tests
  - Authentication errors trigger re-auth
  - Provider registration errors trigger registration
  - Unknown errors logged but don't crash

- **Claude SDK Integration**: 2 tests
  - SDK invoked on error
  - SDK timeout handling

- **DeploymentResult**: 2 tests
  - Success result structure
  - Failure result structure

#### CLI Integration
- **Command Routing**: 5 tests
  - Without --agent uses orchestrator
  - With --agent uses AgentDeployer
  - --max-iterations flag
  - --agent-timeout flag
  - All optional parameters

- **Report Display**: 3 tests
  - Successful deployment report
  - Failed deployment report
  - Error summary display

- **Error Handling**: 3 tests
  - Invalid IaC directory
  - Exception handling
  - Timeout reporting

- **Dry Run**: 1 test
  - Agent respects --dry-run flag

- **Documentation**: 3 tests
  - Help includes --agent flag
  - Help includes --max-iterations
  - Help includes --agent-timeout

### Test Fixtures (conftest.py)

Available fixtures for your own tests:

```python
# Mock deploy_iac responses
mock_deploy_iac_success          # Returns successful deployment
mock_deploy_iac_failure          # Raises RuntimeError
mock_deploy_iac_auth_error       # Raises auth error
mock_deploy_iac_provider_error   # Raises provider error

# Mock Claude SDK
mock_claude_sdk_client           # AsyncMock Claude client

# Sample data
sample_iac_dir                   # Creates temp IaC directory
sample_deployment_error_log      # Sample error log
deployment_result_success        # Sample success result
deployment_result_failure        # Sample failure result

# Subprocess mocks
mock_subprocess_success          # Returns success
mock_subprocess_failure          # Returns failure
```

### Writing Additional Tests

When adding new tests, follow this pattern:

```python
class TestNewFeature:
    """Test new feature description."""

    def test_specific_behavior(self):
        """Test specific behavior with clear assertion."""
        # Arrange
        deployer = AgentDeployer(...)

        # Act
        result = deployer.method_under_test()

        # Assert
        assert result == expected_value, "Clear failure message"
```

### Common Testing Patterns

#### Testing Async Methods
```python
@patch("src.deployment.agent_deployer.deploy_iac")
async def test_async_method(self, mock_deploy):
    """Test async deployment method."""
    mock_deploy.return_value = {"status": "deployed"}

    deployer = AgentDeployer(...)
    result = await deployer.deploy_with_agent()

    assert result.success is True
```

#### Testing CLI Commands
```python
def test_cli_command(self):
    """Test CLI command behavior."""
    from click.testing import CliRunner

    runner = CliRunner()
    result = runner.invoke(deploy_command, ["--agent", ...])

    assert result.exit_code == 0
    assert "expected text" in result.output
```

#### Testing Error Handling
```python
def test_error_handling(self):
    """Test graceful error handling."""
    deployer = AgentDeployer(...)

    with pytest.raises(ValueError, match="specific error"):
        deployer.invalid_operation()
```

### Debugging Failed Tests

#### View Full Test Output
```bash
uv run pytest tests/deployment/test_agent_deployer.py -vv
```

#### Run Single Test with Print Statements
```bash
uv run pytest tests/deployment/test_agent_deployer.py::TestClass::test_name -s
```

#### Drop into Debugger on Failure
```bash
uv run pytest tests/deployment/test_agent_deployer.py --pdb
```

#### Show Local Variables on Failure
```bash
uv run pytest tests/deployment/test_agent_deployer.py -l
```

### Test Quality Checklist

Before considering tests complete, verify:

- [ ] All tests have clear docstrings
- [ ] Tests follow Arrange-Act-Assert pattern
- [ ] Tests are independent (no test depends on another)
- [ ] Tests are deterministic (same result every run)
- [ ] Tests are fast (unit tests < 100ms)
- [ ] Mocks are used for external dependencies
- [ ] Edge cases are covered (empty input, max values, etc.)
- [ ] Error cases are tested
- [ ] Success path is tested
- [ ] Assertions have descriptive failure messages

### Integration with CI/CD

These tests will run automatically in CI:

```bash
# CI command
uv run pytest tests/deployment/test_agent_deployer.py tests/commands/test_deploy_agent.py --cov=src.deployment.agent_deployer --cov-report=xml
```

Coverage reports will be uploaded to coverage tracking service.

### TDD Workflow

1. **RED**: Write failing test
2. **GREEN**: Write minimal code to pass test
3. **REFACTOR**: Improve code while keeping tests green

Example workflow:
```bash
# 1. Run tests (should fail)
uv run pytest tests/deployment/test_agent_deployer.py::TestAgentDeployerInit::test_init_with_defaults

# 2. Implement minimal code
# Edit src/deployment/agent_deployer.py

# 3. Run tests (should pass)
uv run pytest tests/deployment/test_agent_deployer.py::TestAgentDeployerInit::test_init_with_defaults

# 4. Refactor if needed

# 5. Run all tests to ensure nothing broke
uv run pytest tests/deployment/test_agent_deployer.py -v
```

### Questions or Issues?

If tests are unclear or need modification:
1. Check test docstrings for intent
2. Review Issue #610 requirements
3. Ask for clarification before changing tests

Remember: In TDD, tests are the specification!

---

Fair winds and following seas!

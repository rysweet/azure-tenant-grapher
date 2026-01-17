```markdown
# CTF Overlay System Test Strategy

## Overview

This document describes the comprehensive test strategy for the CTF Overlay System following Test-Driven Development (TDD) methodology. All tests are written **BEFORE** implementation and should **FAIL initially**.

## Testing Pyramid

We follow the standard testing pyramid with strict distribution:

```
       /\
      /  \    10% E2E Tests (15 tests)
     /____\
    /      \  30% Integration Tests (13 tests)
   /________\
  /          \ 60% Unit Tests (72 tests)
 /____________\

Total: 100 tests across all layers
```

### Distribution Rationale

- **Unit Tests (60%)**: Fast, isolated, test individual components
- **Integration Tests (30%)**: Test service interactions and workflows
- **E2E Tests (10%)**: Test complete user journeys and real scenarios

## Test Structure

```
tests/
├── unit/                              # 60% of tests (72 tests)
│   └── services/
│       ├── test_ctf_annotation_service.py   # 22 tests
│       ├── test_ctf_import_service.py       # 24 tests
│       └── test_ctf_deploy_service.py       # 26 tests
│
├── integration/                        # 30% of tests (13 tests)
│   └── test_ctf_import_deploy_flow.py
│
├── e2e/                                # 10% of tests (15 tests)
│   └── test_ctf_m003_scenarios.py
│
├── fixtures/
│   └── ctf_test_data.py               # Shared test data
│
├── conftest.py                         # Pytest configuration
└── CTF_TEST_STRATEGY.md               # This file
```

## Test Coverage by Component

### CTFAnnotationService (22 unit tests)

**What it tests:**
- Resource annotation with CTF properties
- Role determination logic (heuristic + explicit)
- Batch annotation operations
- Security validation (base layer protection, audit logging)
- Error handling (Neo4j failures, validation)

**Key test categories:**
1. Service initialization (2 tests)
2. Resource annotation (6 tests)
3. Role determination (5 tests)
4. Batch operations (3 tests)
5. Security validation (3 tests)
6. Error handling (3 tests)

**Coverage target:** 90%+ of `src/services/ctf_annotation_service.py`

### CTFImportService (24 unit tests)

**What it tests:**
- Terraform state file parsing
- CTF property extraction from tags
- Resource mapping (Terraform → Neo4j format)
- Import workflow with statistics
- Error handling (invalid JSON, missing files)

**Key test categories:**
1. Service initialization (2 tests)
2. Terraform parsing (6 tests)
3. Property extraction (4 tests)
4. Resource mapping (3 tests)
5. Import workflow (6 tests)
6. Error handling (3 tests)

**Coverage target:** 90%+ of `src/services/ctf_import_service.py`

### CTFDeployService (26 unit tests)

**What it tests:**
- CTF resource querying from Neo4j
- Terraform configuration generation
- Deployment orchestration
- Cleanup operations
- Error handling (Terraform failures, missing resources)

**Key test categories:**
1. Service initialization (2 tests)
2. Resource querying (5 tests)
3. Terraform generation (5 tests)
4. Scenario deployment (7 tests)
5. Scenario cleanup (4 tests)
6. Error handling (3 tests)

**Coverage target:** 90%+ of `src/services/ctf_deploy_service.py`

### Integration Tests (13 tests)

**What they test:**
- Import → Annotate workflow
- Deploy → Cleanup workflow
- Full lifecycle: Import → Deploy → Cleanup
- Layer isolation
- Error handling across services
- Concurrency and race conditions

**Test categories:**
1. Import → Annotate flow (3 tests)
2. Deploy → Cleanup flow (2 tests)
3. Full lifecycle (3 tests)
4. Error handling (3 tests)
5. Concurrency (2 tests)

**Coverage target:** Service integration points, not individual services

### E2E Tests (15 tests)

**What they test:**
- Complete M003 scenarios (v1-base, v2-cert, v3-ews, v4-blob)
- CLI command integration
- Multi-scenario management
- Error recovery
- Performance with realistic workloads

**Test categories:**
1. M003 v1-base (2 tests)
2. M003 v2-cert (2 tests)
3. M003 v3-ews (2 tests)
4. M003 v4-blob (2 tests)
5. Multi-scenario (3 tests)
6. Error recovery (2 tests)
7. Performance (2 tests)

**Coverage target:** Real-world user workflows

## Running Tests

### Run All Tests

```bash
pytest tests/
```

### Run by Test Layer

```bash
# Unit tests only (fast)
pytest tests/unit/

# Integration tests only
pytest tests/integration/

# E2E tests only (slow)
pytest tests/e2e/ -m e2e
```

### Run by Service

```bash
# Test specific service
pytest tests/unit/services/test_ctf_annotation_service.py
pytest tests/unit/services/test_ctf_import_service.py
pytest tests/unit/services/test_ctf_deploy_service.py
```

### Run with Coverage

```bash
# Generate coverage report
pytest tests/ --cov=src/services --cov-report=html

# View coverage
open htmlcov/index.html
```

### Run E2E Tests with Real Neo4j

```bash
# Requires Docker for testcontainers
pytest tests/e2e/ -m e2e --run-integration
```

## Expected Test Results

### Before Implementation

**All tests should FAIL** with import errors or missing implementation:

```
FAILED tests/unit/services/test_ctf_annotation_service.py::test_service_creation_with_driver
ERROR: ImportError: cannot import name 'CTFAnnotationService' from 'src.services.ctf_annotation_service'
...
```

### After Implementation

**All tests should PASS**:

```
tests/unit/services/test_ctf_annotation_service.py ........... [22/100]
tests/unit/services/test_ctf_import_service.py .............. [46/100]
tests/unit/services/test_ctf_deploy_service.py ............. [72/100]
tests/integration/test_ctf_import_deploy_flow.py .......... [85/100]
tests/e2e/test_ctf_m003_scenarios.py ............... [100/100]

======================== 100 passed in 45.23s ==========================
```

**Coverage targets:**
- Overall: 85%+
- Services: 90%+
- CLI commands: 80%+

## Test Data and Fixtures

### Shared Fixtures (`tests/fixtures/ctf_test_data.py`)

Provides reusable test data for all test layers:

```python
from tests.fixtures.ctf_test_data import (
    get_m003_v1_base_terraform_state,
    get_sample_neo4j_resources,
    M003_SCENARIOS
)
```

**Available fixtures:**
- Terraform state for all M003 scenarios
- Neo4j resource mocks
- Valid/invalid CTF property values
- Multi-layer test data
- Sample Terraform configurations

### Pytest Fixtures (`tests/conftest.py`)

Global fixtures available to all tests:

- `mock_neo4j_driver`: Mocked Neo4j driver
- `mock_terraform_emitter`: Mocked Terraform emitter
- `neo4j_test_container`: Real Neo4j container (E2E tests)
- `temp_workspace`: Temporary workspace for file operations

## Key Testing Principles

### 1. Arrange-Act-Assert Pattern

All tests follow AAA pattern:

```python
def test_annotate_resource(self, mock_neo4j_driver):
    # Arrange
    service = CTFAnnotationService(neo4j_driver=mock_neo4j_driver)

    # Act
    result = service.annotate_resource(
        resource_id="vm-001",
        layer_id="default"
    )

    # Assert
    assert result["success"] is True
```

### 2. Test Isolation

Each test is independent:
- No shared state between tests
- Each test creates its own fixtures
- Cleanup after every test

### 3. Clear Test Names

Test names describe what they test:

```python
def test_annotate_resource_validates_layer_id(...)  # ✓ Clear
def test_resource_validation(...)                   # ✗ Vague
```

### 4. One Assertion per Test (When Possible)

Focus each test on a single behavior:

```python
# Good - single focus
def test_import_creates_resources(...)
def test_import_returns_statistics(...)

# Avoid - multiple concerns
def test_import_workflow(...)  # Tests creation AND statistics
```

### 5. Test Edge Cases and Error Conditions

Don't just test happy paths:

```python
def test_annotate_resource_success(...)           # Happy path
def test_annotate_nonexistent_resource(...)       # Warning case
def test_annotate_with_invalid_layer_id(...)      # Error case
def test_annotate_neo4j_connection_failure(...)   # Infrastructure failure
```

## Security Testing

Security validation is tested at multiple levels:

### Unit Level
- Property validation (SQL injection, XSS, path traversal)
- Base layer protection
- Audit logging

### Integration Level
- Cross-service security boundaries
- Layer isolation

### E2E Level
- Complete security workflows
- Real-world attack scenarios

**Test cases include:**
```python
malicious_inputs = [
    "'; DROP DATABASE; --",     # SQL injection
    "\" OR \"1\"=\"1",           # SQL injection
    "<script>alert('xss')</script>",  # XSS
    "../../etc/passwd",         # Path traversal
]
```

## Performance Testing

Performance tests in E2E layer:

```python
@pytest.mark.slow
def test_import_large_scenario():
    """Test importing 100+ resources completes in <30s"""
    ...

def test_query_performance_with_indexes():
    """Test querying 1000 resources completes in <1s"""
    ...
```

**Performance targets:**
- Import 100 resources: <30s
- Query 1000 resources: <1s
- Deploy scenario: <5 minutes

## Idempotency Testing

Critical for CTF operations:

```python
def test_import_from_state_idempotent():
    """Test importing same state twice is idempotent"""
    stats1 = service.import_from_state(...)  # First import
    stats2 = service.import_from_state(...)  # Second import

    assert stats1["resources_created"] == 2
    assert stats2["resources_updated"] == 2  # Updates, not creates
    assert stats2["resources_created"] == 0
```

## Continuous Integration

### GitHub Actions Workflow

```yaml
name: CTF Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: 3.11

      - name: Install dependencies
        run: |
          pip install -r requirements-test.txt

      - name: Run unit tests
        run: pytest tests/unit/ --cov=src/services

      - name: Run integration tests
        run: pytest tests/integration/

      - name: Run E2E tests (with Docker)
        run: pytest tests/e2e/ -m e2e --run-integration
```

## Test Maintenance

### When to Update Tests

1. **New features**: Add tests BEFORE implementation
2. **Bug fixes**: Add regression test FIRST
3. **Refactoring**: Tests should still pass unchanged
4. **API changes**: Update tests to match new API

### Test Review Checklist

- [ ] All tests follow AAA pattern
- [ ] Test names are descriptive
- [ ] Edge cases are covered
- [ ] Error conditions are tested
- [ ] Security validation included
- [ ] Idempotency tested where applicable
- [ ] Performance targets met
- [ ] Documentation updated

## Common Test Patterns

### Pattern: Testing Neo4j Queries

```python
def test_query_validates_parameters(self, mock_neo4j_driver):
    service = CTFDeployService(neo4j_driver=mock_neo4j_driver)

    # Test the query was called correctly
    service.query_ctf_resources(layer_id="default")

    call_args = mock_neo4j_driver.execute_query.call_args
    assert "MATCH (r:Resource {layer_id: $layer_id})" in call_args[0][0]
```

### Pattern: Testing Error Handling

```python
def test_handles_neo4j_timeout(self, mock_neo4j_driver):
    from neo4j.exceptions import ClientError

    mock_neo4j_driver.execute_query.side_effect = ClientError("Timeout")

    service = CTFAnnotationService(neo4j_driver=mock_neo4j_driver)

    with pytest.raises(ClientError, match="Timeout"):
        service.annotate_resource(resource_id="vm-001", layer_id="default")
```

### Pattern: Testing Batch Operations

```python
def test_annotate_batch_multiple_resources(self, mock_neo4j_driver):
    service = CTFAnnotationService(neo4j_driver=mock_neo4j_driver)

    results = service.annotate_batch(
        resources=[{"id": "vm-1"}, {"id": "vm-2"}, {"id": "vm-3"}],
        layer_id="default"
    )

    assert results["success_count"] == 3
    # Verify batch operation (UNWIND)
    call_args = mock_neo4j_driver.execute_query.call_args
    assert "UNWIND $resources" in call_args[0][0]
```

## Troubleshooting Test Failures

### Import Errors

**Problem**: `ImportError: cannot import name 'CTFAnnotationService'`

**Solution**: Service not implemented yet. This is expected in TDD - tests fail first!

### Mock Failures

**Problem**: `AttributeError: Mock object has no attribute 'execute_query'`

**Solution**: Configure mock with required methods:

```python
mock_driver = Mock()
mock_driver.execute_query = Mock(return_value=([], None, None))
```

### Fixture Not Found

**Problem**: `fixture 'mock_neo4j_driver' not found`

**Solution**: Import fixture or add to conftest.py

### E2E Test Hangs

**Problem**: E2E test hangs during Neo4j container startup

**Solution**: Ensure Docker is running, or skip E2E tests:

```bash
pytest tests/unit tests/integration  # Skip E2E
```

## Summary

This test strategy provides:

✅ **100 comprehensive tests** across all layers
✅ **TDD methodology** - tests written BEFORE implementation
✅ **60/30/10 testing pyramid** distribution
✅ **90%+ coverage target** for services
✅ **Security validation** at all levels
✅ **Performance benchmarks** for realistic workloads
✅ **Idempotency guarantees** for all operations
✅ **Clear documentation** and examples

**Next Steps:**

1. Review test files and understand test structure
2. Run tests to verify they FAIL (expected in TDD)
3. Implement services following test specifications
4. Watch tests turn green as implementation progresses
5. Achieve 90%+ coverage across all services

**Remember**: In TDD, failing tests are SUCCESS! They define what needs to be built.
```

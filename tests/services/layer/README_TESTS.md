# Layer SCAN_SOURCE_NODE Tests (Issue #570)

Comprehensive test suite fer verifyin' SCAN_SOURCE_NODE relationship preservation in layer operations.

## Test Organization (Testing Pyramid)

```
        /\
       /  \      10% E2E Tests
      /----\     (Full user workflows, slower)
     /      \
    /--------\   30% Integration Tests
   /          \  (Multiple components, real Neo4j)
  /------------\
 /              \ 60% Unit Tests
/________________\(Single methods, fast, mocked)
```

### Test Files

| File | Type | Coverage | Speed | Purpose |
|------|------|----------|-------|---------|
| `test_export.py` | Unit | 60% | <100ms/test | Individual method testing with mocks |
| `../integration/test_layer_scan_source_node.py` | Integration | 30% | ~1s/test | Multi-component with real Neo4j |
| `../../iac/test_resource_comparator_with_layers.py` | E2E | 10% | ~2-5s/test | Complete user workflows |

## Running Tests Locally

### Prerequisites

```bash
# Install dependencies
pip install pytest pytest-asyncio pytest-mock

# Start Neo4j (for integration/E2E tests)
docker run -d \
  --name neo4j-test \
  -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/test_password \
  neo4j:latest
```

### Run All Tests

```bash
# Run complete test suite
pytest tests/services/layer/ tests/integration/test_layer_scan_source_node.py tests/iac/test_resource_comparator_with_layers.py -v

# With coverage report
pytest tests/services/layer/ tests/integration/ tests/iac/ \
  --cov=src/services/layer/export \
  --cov=src/iac/resource_comparator \
  --cov-report=html
```

### Run by Test Type

```bash
# Unit tests only (fast, no Neo4j required)
pytest tests/services/layer/test_export.py -v

# Integration tests only (requires Neo4j)
pytest tests/integration/test_layer_scan_source_node.py -m integration -v

# E2E tests only (requires Neo4j, slower)
pytest tests/iac/test_resource_comparator_with_layers.py -m e2e -v
```

### Run by Feature

```bash
# All SCAN_SOURCE_NODE related tests
pytest -m scan_source_node -v

# Tests for copy_layer
pytest -k "copy_layer" -v

# Tests for archive/restore
pytest -k "archive or restore" -v

# Tests for resource_comparator
pytest tests/iac/test_resource_comparator_with_layers.py -v
```

### Run Specific Tests

```bash
# Single test by name
pytest tests/services/layer/test_export.py::test_copy_layer_preserves_scan_source_node -v

# Multiple specific tests
pytest tests/services/layer/test_export.py::test_copy_layer_preserves_scan_source_node \
       tests/integration/test_layer_scan_source_node.py::test_full_copy_workflow_preserves_scan_source_node -v
```

## Expected Behavior (Before Fix)

**ALL tests should FAIL before the fix is implemented.** This is TDD - we write tests first, then implement the fix.

### Expected Failures

| Test | Why It Fails |
|------|--------------|
| `test_copy_layer_preserves_scan_source_node` | Line 166 in `export.py` excludes SCAN_SOURCE_NODE: `AND type(rel) <> 'SCAN_SOURCE_NODE'` |
| `test_archive_layer_includes_scan_source_node` | Line 255 in `export.py` excludes SCAN_SOURCE_NODE from archive |
| `test_restore_layer_recreates_scan_source_node` | Archive doesn't contain SCAN_SOURCE_NODE, so restore can't recreate them |
| `test_resource_comparator_finds_scan_source_node_in_layers` | Layer operations don't preserve SCAN_SOURCE_NODE, so comparator can't find them |

### Tests That Should PASS (Regression Tests)

| Test | Why It Passes |
|------|---------------|
| `test_layer_isolation_maintained` | Tests existing layer isolation logic (not affected by bug) |
| `test_restore_layer_backward_compatibility_v1_archives` | v1.0 archives didn't have SCAN_SOURCE_NODE, should still work |

## Test Data Setup

Tests use realistic Azure resource data:

```python
# Sample Resource (abstracted)
{
    "id": "/subscriptions/test-sub/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1_abstracted",
    "name": "vm1_abstracted",
    "type": "Microsoft.Compute/virtualMachines",
    "layer_id": "test-layer",
    "location": "eastus"
}

# Sample Original (scan result)
{
    "id": "/subscriptions/test-sub/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",
    "name": "vm1",
    "type": "Microsoft.Compute/virtualMachines",
    "location": "eastus"
}

# SCAN_SOURCE_NODE relationship
(vm1_abstracted:Resource)-[:SCAN_SOURCE_NODE]->(vm1:Original)
```

## Fixtures Available

| Fixture | Type | Purpose |
|---------|------|---------|
| `mock_session_manager` | Mock | Mock Neo4j session for unit tests |
| `mock_crud_operations` | Mock | Mock layer metadata CRUD |
| `mock_stats_operations` | Mock | Mock layer statistics |
| `sample_resource_nodes` | Data | Sample Resource nodes |
| `sample_original_nodes` | Data | Sample Original nodes |
| `sample_scan_source_relationships` | Data | Sample SCAN_SOURCE_NODE relationships |
| `neo4j_session_manager` | Real | Real Neo4j connection (integration/E2E) |
| `setup_test_layer` | Helper | Setup complete layer with SCAN_SOURCE_NODE |

## Debugging Tests

### Verbose Output

```bash
# Show detailed output for failing tests
pytest tests/services/layer/test_export.py -vv

# Show print statements
pytest tests/services/layer/test_export.py -s

# Show locals on failure
pytest tests/services/layer/test_export.py -l
```

### Debug Single Test

```bash
# Run with Python debugger
pytest tests/services/layer/test_export.py::test_copy_layer_preserves_scan_source_node --pdb

# Add breakpoint in test:
import pdb; pdb.set_trace()
```

### Check Neo4j State

```bash
# Connect to Neo4j during tests
docker exec -it neo4j-test cypher-shell -u neo4j -p test_password

# Query test data
MATCH (r:Resource)-[:SCAN_SOURCE_NODE]->(orig:Original)
WHERE r.layer_id = 'test-layer'
RETURN r, orig;
```

## Test Coverage Goals

| Component | Target Coverage | Current (Before Fix) | After Fix |
|-----------|----------------|----------------------|-----------|
| `src/services/layer/export.py` | 85% | ~70% | 85%+ |
| `src/iac/resource_comparator.py` | 90% | ~85% | 90%+ |
| SCAN_SOURCE_NODE workflows | 100% | 0% | 100% |

## CI/CD Integration

These tests run automatically in CI:

```yaml
# .github/workflows/test.yml
- name: Run Layer Tests
  run: |
    pytest tests/services/layer/ -v --cov

- name: Run Integration Tests
  run: |
    pytest tests/integration/ -m integration -v

- name: Run E2E Tests
  run: |
    pytest tests/iac/ -m e2e -v
```

## After Fix Implementation

Once the fix is implemented, run tests to verify:

```bash
# All tests should pass
pytest tests/services/layer/ tests/integration/test_layer_scan_source_node.py tests/iac/test_resource_comparator_with_layers.py -v

# Expected output:
# ✓ test_copy_layer_preserves_scan_source_node PASSED
# ✓ test_archive_layer_includes_scan_source_node PASSED
# ✓ test_restore_layer_recreates_scan_source_node PASSED
# ✓ test_resource_comparator_finds_scan_source_node_in_layers PASSED
# ... (all tests should pass)
```

## Troubleshooting

### Neo4j Connection Issues

```bash
# Check Neo4j is running
docker ps | grep neo4j-test

# Check logs
docker logs neo4j-test

# Restart Neo4j
docker restart neo4j-test
```

### Import Errors

```bash
# Ensure src/ is in PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# Or use editable install
pip install -e .
```

### Async Test Issues

```bash
# Install pytest-asyncio
pip install pytest-asyncio

# Mark async tests
@pytest.mark.asyncio
async def test_async_function():
    ...
```

## Contributing

When adding new tests:

1. Follow the testing pyramid (60/30/10 split)
2. Write tests BEFORE implementing fixes (TDD)
3. Use descriptive test names: `test_<what>_<expected_behavior>`
4. Add clear docstrings explaining why test should fail
5. Use appropriate markers (`@pytest.mark.unit`, `@pytest.mark.integration`, etc.)

## References

- Issue #570: SCAN_SOURCE_NODE preservation in layer operations
- Testing Pyramid: https://martinfowler.com/articles/practical-test-pyramid.html
- TDD Approach: Write tests first, implement fix second
- Pytest Documentation: https://docs.pytest.org/

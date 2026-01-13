# Quick Test Reference - Issue #570

**TL;DR**: Run tests to verify SCAN_SOURCE_NODE preservation in layer operations.

## Prerequisites

```bash
# Start Neo4j (required for integration/E2E tests)
docker run -d --name neo4j-test -p 7687:7687 -e NEO4J_AUTH=neo4j/test_password neo4j:latest

# Install test dependencies
pip install pytest pytest-asyncio pytest-mock pytest-cov
```

## Quick Commands

```bash
# Run all tests (expect 15 failures before fix)
pytest tests/services/layer/test_export.py tests/integration/test_layer_scan_source_node.py tests/iac/test_resource_comparator_with_layers.py -v

# Run unit tests only (fast, no Neo4j)
pytest tests/services/layer/test_export.py -v

# Run integration tests (requires Neo4j)
pytest tests/integration/test_layer_scan_source_node.py -m integration -v

# Run E2E tests (full workflow)
pytest tests/iac/test_resource_comparator_with_layers.py -m e2e -v

# Run with coverage
pytest tests/services/layer/ tests/integration/ tests/iac/ --cov=src/services/layer/export --cov=src/iac/resource_comparator --cov-report=html
```

## Test Files

| File | Tests | Type | Speed |
|------|-------|------|-------|
| `tests/services/layer/test_export.py` | 9 | Unit | <1s |
| `tests/integration/test_layer_scan_source_node.py` | 6 | Integration | ~6s |
| `tests/iac/test_resource_comparator_with_layers.py` | 5 | E2E | ~15s |

## Expected Results

### Before Fix ❌
- 15 tests FAIL (75%)
- 5 tests PASS (25% - regression tests)

### After Fix ✓
- 20 tests PASS (100%)

## Key Assertions

Each test verifies specific behavior:

1. **copy_layer** preserves SCAN_SOURCE_NODE relationships
2. **archive_layer** includes SCAN_SOURCE_NODE in JSON
3. **restore_layer** recreates SCAN_SOURCE_NODE from archive
4. **resource_comparator** finds original IDs via SCAN_SOURCE_NODE
5. Layer isolation maintained (no cross-contamination)

## Debugging

```bash
# Run single test with verbose output
pytest tests/services/layer/test_export.py::test_copy_layer_preserves_scan_source_node -vv

# Run with debugger
pytest tests/services/layer/test_export.py::test_copy_layer_preserves_scan_source_node --pdb

# Show print statements
pytest tests/services/layer/test_export.py -s
```

## Test Data

Tests use realistic Azure resources:
- Virtual Machines (`Microsoft.Compute/virtualMachines`)
- Virtual Networks (`Microsoft.Network/virtualNetworks`)
- Storage Accounts (`Microsoft.Storage/storageAccounts`)

## Documentation

- Full Test Suite: `tests/TEST_SUITE_SUMMARY.md`
- Test Instructions: `tests/services/layer/README_TESTS.md`
- Issue Tracker: Issue #570

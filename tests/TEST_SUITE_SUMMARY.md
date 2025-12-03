# Test Suite Summary: SCAN_SOURCE_NODE Preservation (Issue #570)

**Generated**: 2025-12-03
**Approach**: Test-Driven Development (TDD)
**Status**: All tests should FAIL before fix is implemented

## Overview

This test suite verifies SCAN_SOURCE_NODE relationship preservation across layer operations (copy, archive, restore) and IaC generation workflows.

## Test Statistics

| Category | Test Count | Files | Coverage Target |
|----------|-----------|-------|----------------|
| Unit Tests | 9 | 1 | 60% of pyramid |
| Integration Tests | 6 | 1 | 30% of pyramid |
| E2E Tests | 5 | 1 | 10% of pyramid |
| **Total** | **20** | **3** | **100%** |

## Test Files

### 1. Unit Tests: `tests/services/layer/test_export.py`

**Purpose**: Fast, isolated tests of individual methods in LayerExportOperations

**Tests (9 total)**:
1. ✗ `test_copy_layer_preserves_scan_source_node` - Verifies SCAN_SOURCE_NODE copied
2. ✗ `test_copy_layer_links_to_original_nodes_not_copies` - Verifies no duplicate :Original nodes
3. ✗ `test_archive_layer_includes_scan_source_node` - Verifies SCAN_SOURCE_NODE in JSON archive
4. ✗ `test_archive_layer_has_version_metadata` - Verifies archive version 2.0 metadata
5. ✗ `test_restore_layer_recreates_scan_source_node` - Verifies SCAN_SOURCE_NODE restored from archive
6. ✓ `test_layer_isolation_maintained` - Regression test (should PASS)
7. ✓ `test_copy_layer_empty_source` - Edge case: empty layer
8. ✓ `test_archive_layer_with_no_relationships` - Edge case: no relationships
9. ✓ `test_restore_layer_backward_compatibility_v1_archives` - Backward compatibility (should PASS)

**Speed**: <100ms per test
**Dependencies**: None (fully mocked)
**Run**: `pytest tests/services/layer/test_export.py -v`

### 2. Integration Tests: `tests/integration/test_layer_scan_source_node.py`

**Purpose**: Test multiple components working together with real Neo4j

**Tests (6 total)**:
1. ✗ `test_full_copy_workflow_preserves_scan_source_node` - End-to-end copy with Neo4j
2. ✗ `test_full_archive_restore_workflow_preserves_scan_source_node` - Archive → restore workflow
3. ✗ `test_copy_preserves_scan_source_to_same_originals` - Shared :Original nodes
4. ✓ `test_layer_isolation_with_real_neo4j` - Layer isolation (should PASS)
5. ✗ `test_copy_layer_with_multiple_scan_source_per_resource` - Multiple SCAN_SOURCE_NODE per Resource
6. ✗ `test_archive_restore_with_orphaned_scan_source_node` - Orphaned references handled gracefully

**Speed**: ~1s per test
**Dependencies**: Real Neo4j (Docker)
**Run**: `pytest tests/integration/test_layer_scan_source_node.py -m integration -v`

### 3. E2E Tests: `tests/iac/test_resource_comparator_with_layers.py`

**Purpose**: Complete user workflows from layer creation to IaC generation

**Tests (5 total)**:
1. ✗ `test_resource_comparator_finds_scan_source_node_in_layers` - Comparator uses SCAN_SOURCE_NODE
2. ✗ `test_heuristic_cleanup_not_triggered_with_scan_source_node` - No fallback warnings
3. ✗ `test_iac_generation_after_layer_copy` - IaC after copy operation
4. ✗ `test_iac_generation_after_archive_restore` - IaC after restore operation
5. ✗ `test_cross_tenant_iac_generation_with_scan_source_node` - Cross-tenant workflow

**Speed**: ~2-5s per test
**Dependencies**: Real Neo4j, full system
**Run**: `pytest tests/iac/test_resource_comparator_with_layers.py -m e2e -v`

## Key Test Scenarios

### Scenario 1: Copy Layer Preserves SCAN_SOURCE_NODE

```
Source Layer:
  (vm1_abs:Resource)-[:SCAN_SOURCE_NODE]->(vm1_orig:Original)

After copy_layer(source → target):
  Expected: (vm1_copy:Resource)-[:SCAN_SOURCE_NODE]->(vm1_orig:Original)
  Actual:   (vm1_copy:Resource) [NO SCAN_SOURCE_NODE]
```

**Why it fails**: Line 166 in `export.py` excludes SCAN_SOURCE_NODE

### Scenario 2: Archive Includes SCAN_SOURCE_NODE

```
Layer:
  (vm1:Resource)-[:SCAN_SOURCE_NODE]->(vm1_orig:Original)

After archive_layer(layer → JSON):
  Expected: JSON contains {"type": "SCAN_SOURCE_NODE", ...}
  Actual:   JSON relationships = [] (empty)
```

**Why it fails**: Line 255 in `export.py` excludes SCAN_SOURCE_NODE

### Scenario 3: Restore Recreates SCAN_SOURCE_NODE

```
Archive (v2.0):
  {
    "relationships": [
      {"type": "SCAN_SOURCE_NODE", "source": "vm1", "target": "vm1_orig"}
    ]
  }

After restore_layer(JSON → layer):
  Expected: (vm1:Resource)-[:SCAN_SOURCE_NODE]->(vm1_orig:Original)
  Actual:   Archive doesn't contain SCAN_SOURCE_NODE, can't restore
```

**Why it fails**: Archive doesn't include SCAN_SOURCE_NODE (Scenario 2)

### Scenario 4: IaC Generation Uses SCAN_SOURCE_NODE

```
Layer:
  (vm1_abs:Resource {id: "vm1_abstracted_abc123"})
  -[:SCAN_SOURCE_NODE]->
  (vm1_orig:Original {id: "vm1"})

resource_comparator.compare_resources():
  Expected: Query SCAN_SOURCE_NODE → find "vm1" → EXACT_MATCH
  Actual:   No SCAN_SOURCE_NODE → heuristic cleanup → NEW (wrong!)
```

**Why it fails**: Layer operations don't preserve SCAN_SOURCE_NODE

## Root Cause Analysis

### Bug Location: `src/services/layer/export.py`

**Line 166** (copy_layer):
```python
WHERE type(rel) <> 'SCAN_SOURCE_NODE'  # ❌ Explicitly excludes SCAN_SOURCE_NODE
```

**Line 255** (archive_layer):
```python
WHERE type(rel) <> 'SCAN_SOURCE_NODE'  # ❌ Explicitly excludes SCAN_SOURCE_NODE
```

### Impact

| Operation | Impact | Severity |
|-----------|--------|----------|
| Copy Layer | SCAN_SOURCE_NODE lost | HIGH |
| Archive Layer | SCAN_SOURCE_NODE not saved | HIGH |
| Restore Layer | Cannot recreate SCAN_SOURCE_NODE | HIGH |
| IaC Generation | Wrong resource classification | CRITICAL |

## Running the Tests

### Quick Start

```bash
# 1. Start Neo4j
docker run -d --name neo4j-test -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/test_password neo4j:latest

# 2. Run all tests (expect failures)
pytest tests/services/layer/ tests/integration/test_layer_scan_source_node.py tests/iac/test_resource_comparator_with_layers.py -v

# 3. View coverage
pytest --cov=src/services/layer/export --cov=src/iac/resource_comparator --cov-report=html
open htmlcov/index.html
```

### By Test Type

```bash
# Unit tests only (no Neo4j needed)
pytest tests/services/layer/test_export.py -v

# Integration tests (requires Neo4j)
pytest tests/integration/test_layer_scan_source_node.py -m integration -v

# E2E tests (requires Neo4j, slower)
pytest tests/iac/test_resource_comparator_with_layers.py -m e2e -v
```

### By Feature

```bash
# All SCAN_SOURCE_NODE tests
pytest -m scan_source_node -v

# Copy operations
pytest -k "copy" -v

# Archive/restore operations
pytest -k "archive or restore" -v

# Resource comparator tests
pytest tests/iac/ -v
```

## Expected Test Results

### Before Fix

```
tests/services/layer/test_export.py::test_copy_layer_preserves_scan_source_node FAILED ❌
tests/services/layer/test_export.py::test_archive_layer_includes_scan_source_node FAILED ❌
tests/services/layer/test_export.py::test_restore_layer_recreates_scan_source_node FAILED ❌
tests/services/layer/test_export.py::test_layer_isolation_maintained PASSED ✓
tests/integration/test_layer_scan_source_node.py::test_full_copy_workflow_preserves_scan_source_node FAILED ❌
tests/iac/test_resource_comparator_with_layers.py::test_resource_comparator_finds_scan_source_node_in_layers FAILED ❌

Expected Failures: 15/20 (75%)
Expected Passes: 5/20 (25% - regression tests)
```

### After Fix

```
All 20 tests should PASS ✓
```

## Fix Implementation Checklist

Use these tests to guide the fix implementation:

- [ ] Update `copy_layer` to include SCAN_SOURCE_NODE (remove line 166 filter)
- [ ] Update `archive_layer` to include SCAN_SOURCE_NODE (remove line 255 filter)
- [ ] Add version metadata to archives (version: "2.0", includes_scan_source_node: true)
- [ ] Update `restore_layer` to handle SCAN_SOURCE_NODE relationships
- [ ] Ensure backward compatibility with v1.0 archives (without SCAN_SOURCE_NODE)
- [ ] Verify resource_comparator uses SCAN_SOURCE_NODE when available
- [ ] Run all tests: `pytest tests/services/layer/ tests/integration/ tests/iac/ -v`
- [ ] All 20 tests pass ✓

## Test Fixtures

### Mock Fixtures (Unit Tests)
- `mock_session_manager` - Mock Neo4j session
- `mock_crud_operations` - Mock layer metadata CRUD
- `mock_stats_operations` - Mock statistics
- `sample_resource_nodes` - Sample Resource nodes
- `sample_original_nodes` - Sample Original nodes
- `sample_scan_source_relationships` - Sample SCAN_SOURCE_NODE

### Real Fixtures (Integration/E2E)
- `neo4j_session_manager` - Real Neo4j connection
- `setup_test_layer` - Helper to create complete layer with SCAN_SOURCE_NODE
- `target_scan_result` - Simulated Azure scan result

## Markers

Tests are marked for selective execution:

- `@pytest.mark.unit` - Unit tests (fast, mocked)
- `@pytest.mark.integration` - Integration tests (real Neo4j)
- `@pytest.mark.e2e` - End-to-end tests (full workflow)
- `@pytest.mark.scan_source_node` - SCAN_SOURCE_NODE related tests

## CI/CD Integration

These tests run automatically in GitHub Actions:

```yaml
- name: Run Unit Tests
  run: pytest tests/services/layer/ -v --cov

- name: Run Integration Tests
  run: pytest tests/integration/ -m integration -v

- name: Run E2E Tests
  run: pytest tests/iac/ -m e2e -v
```

## Coverage Targets

| Component | Target | Current (Before Fix) | After Fix |
|-----------|--------|----------------------|-----------|
| `export.py` | 85% | ~70% | 85%+ |
| `resource_comparator.py` | 90% | ~85% | 90%+ |
| SCAN_SOURCE_NODE workflows | 100% | 0% | 100% |

## Documentation

- **Test README**: `tests/services/layer/README_TESTS.md`
- **Issue Tracker**: Issue #570
- **Philosophy**: TDD approach - tests written before fix
- **Testing Pyramid**: 60% unit, 30% integration, 10% E2E

## Troubleshooting

### Neo4j Not Running
```bash
docker start neo4j-test
```

### Import Errors
```bash
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

### Async Test Issues
```bash
pip install pytest-asyncio
```

## Next Steps

1. Run tests to verify they FAIL (TDD)
2. Implement fix in `src/services/layer/export.py`
3. Run tests again to verify they PASS
4. Check coverage: `pytest --cov --cov-report=html`
5. Create PR with fix and passing tests

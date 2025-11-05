# Dual Graph Architecture Tests (Issue #420)

This document describes the comprehensive test suite for the dual-graph architecture feature following Test-Driven Development (TDD) principles.

## Overview

All tests are **EXPECTED TO FAIL** initially because the implementation does not exist yet. This is intentional and follows TDD best practices:

1. Write tests first (RED phase)
2. Implement code to make tests pass (GREEN phase)
3. Refactor as needed (REFACTOR phase)

## Test Files Created

### 1. ID Abstraction Service Tests
**File:** `tests/services/test_id_abstraction_service.py`

**Purpose:** Validates the ID abstraction service that creates deterministic, type-prefixed hashed IDs for Azure resources.

**Test Count:** 25 tests

**Key Test Categories:**
- Deterministic hash generation (same input = same output)
- Type-prefixed format (vm-{hash}, storage-{hash}, etc.)
- Full resource ID translation
- Subscription ID abstraction
- Resource group name abstraction
- Seed-based reproducibility (same seed = same abstractions)
- Azure resource type handling (Compute, Storage, Network, Identity)
- Hash collision resistance
- Security (one-way abstraction, no reverse lookup)
- Performance (caching mechanism)

**Example Tests:**
```python
def test_deterministic_hash_generation(self, tenant_seed)
def test_type_prefixed_format_vm(self, tenant_seed, sample_resource_ids)
def test_seed_based_reproducibility_same_seed(self, sample_resource_ids)
def test_handle_compute_resource_types(self, tenant_seed)
```

---

### 2. Dual Node Creation Tests
**File:** `tests/test_resource_processor_dual_node.py`

**Purpose:** Validates that the resource processor creates dual nodes (original and abstracted) during scan time with proper labels and relationships.

**Test Count:** 18 tests

**Key Test Categories:**
- Single resource creates exactly 2 nodes
- Original node has `:Resource:Original` labels
- Abstracted node has `:Resource` label only
- Both nodes have same non-ID properties
- `SCAN_SOURCE_NODE` relationship created correctly
- Transaction atomicity (both nodes or neither)
- Property matching except ID-related fields
- Complex nested properties handling
- Batch processing
- Error handling and rollback

**Example Tests:**
```python
def test_single_resource_creates_two_nodes(...)
def test_original_node_has_correct_labels(...)
def test_scan_source_node_relationship_created(...)
def test_transaction_atomicity_both_nodes_or_neither(...)
```

---

### 3. Relationship Duplication Tests
**File:** `tests/relationship_rules/test_dual_graph_relationships.py`

**Purpose:** Validates that all relationships are correctly duplicated in both original and abstracted graphs, maintaining topology consistency.

**Test Count:** 22 tests

**Key Test Categories:**
- CONTAINS relationship duplication
- USES_IDENTITY relationship duplication
- CONNECTED_TO relationship preservation
- DEPENDS_ON relationship duplication
- Relationship count matching between graphs
- No cross-graph contamination (original↔abstracted)
- Bidirectional relationships
- Multiple relationship types between same nodes
- Relationship properties preserved
- Hierarchical relationships (Subscription→RG→VNet→Subnet)
- Network topology relationships
- Identity relationship chains
- Monitoring relationships
- Private endpoint relationships

**Example Tests:**
```python
def test_contains_relationship_exists_in_both_graphs(...)
def test_no_cross_graph_relationships(...)
def test_hierarchical_contains_relationships(...)
def test_relationship_count_matches_between_graphs(...)
```

---

### 4. Graph Topology Preservation Tests
**File:** `tests/test_graph_topology_preservation.py`

**Purpose:** Validates that original and abstracted graphs are isomorphic (structurally identical).

**Test Count:** 24 tests

**Key Test Categories:**
- Graph isomorphism verification
- Node count equality
- Relationship count equality per type
- VNet→Subnet structure preservation
- NSG→Subnet associations
- Identity reference maintenance
- Resource Group containment hierarchy
- Dependency chains
- Network topology connectivity
- Multi-hop path queries
- Graph degree distribution
- Strongly connected components
- Shortest path preservation
- Centrality measures
- Orphaned node detection

**Example Tests:**
```python
def test_original_and_abstracted_graphs_are_isomorphic(...)
def test_node_count_equal_in_both_graphs(...)
def test_vnet_subnet_structure_preserved(...)
def test_no_orphaned_nodes_in_abstracted_graph(...)
```

---

### 5. IaC Generation Tests
**File:** `tests/iac/test_iac_with_dual_graph.py`

**Purpose:** Validates that IaC generation (Terraform, ARM, Bicep) correctly uses the abstracted graph by default.

**Test Count:** 22 tests

**Key Test Categories:**
- Traverser returns only abstracted nodes by default
- Generated Terraform uses abstracted IDs
- No translation logic executed during generation
- Resource group names are abstracted
- Subnet references use abstracted IDs
- Private endpoint connections use abstracted IDs
- Managed identity references abstracted
- Key Vault access policies abstracted
- VNet peering references abstracted
- Load balancer backend pools abstracted
- Diagnostic settings abstracted
- Generated IaC is syntactically valid
- ARM template uses abstracted IDs
- Bicep template uses abstracted IDs

**Example Tests:**
```python
def test_traverser_returns_only_abstracted_nodes_by_default(...)
def test_generated_terraform_uses_abstracted_ids(...)
def test_no_translation_logic_executed_during_generation(...)
def test_full_iac_generation_workflow_uses_abstracted_graph(...)
```

---

### 6. Tenant Seed Management Tests
**File:** `tests/test_tenant_seed_management.py`

**Purpose:** Validates that tenant nodes store abstraction seeds and seeds are used consistently.

**Test Count:** 24 tests

**Key Test Categories:**
- Tenant node stores abstraction seed
- Different tenants have different seeds
- Seed persists across graph operations
- Seed used consistently for all resources in tenant
- Cryptographically secure seed generation
- Seed immutability (cannot be modified after creation)
- Automatic seed creation on first access
- Seed not exposed in logs (security)
- Seed retrieval is fast (cached/indexed)
- Backward compatibility with existing tenant nodes
- Seed format validation
- Concurrent seed retrieval handling
- Seed rotation not supported (by design)
- Seed included in graph export/import

**Example Tests:**
```python
def test_tenant_node_stores_abstraction_seed(...)
def test_seed_persists_across_graph_operations(...)
def test_seed_generation_is_cryptographically_secure(...)
def test_seed_per_tenant_isolation(...)
```

---

### 7. Neo4j Query Pattern Tests
**File:** `tests/test_neo4j_query_patterns.py`

**Purpose:** Validates that Neo4j queries correctly handle the dual graph structure.

**Test Count:** 30 tests

**Key Test Categories:**
- `MATCH (r:Resource)` returns only abstracted nodes by default
- `MATCH (r:Resource:Original)` returns only original nodes
- Traversing from abstracted to original via SCAN_SOURCE_NODE
- Finding orphaned nodes (missing counterparts)
- Count queries work correctly for both graphs
- Query by resource type (abstracted vs original)
- Relationship queries per graph
- Path queries in abstracted graph
- Shortest path queries
- Aggregation queries
- Property existence queries
- Regex queries on abstracted IDs
- UNION queries across both graphs
- OPTIONAL MATCH patterns
- Query performance testing
- Index creation and usage
- Edge cases (null properties, missing relationships, concurrent queries)

**Example Tests:**
```python
def test_match_resource_returns_only_abstracted_by_default(...)
def test_traverse_from_abstracted_to_original(...)
def test_find_orphaned_abstracted_nodes(...)
def test_query_by_resource_type_abstracted(...)
```

---

### 8. Shared Test Fixtures
**File:** `tests/fixtures/dual_graph_fixtures.py`

**Purpose:** Provides reusable fixtures for all dual-graph tests.

**Fixtures Provided:**
- Mock Neo4j connections (driver, session, transaction)
- Sample Azure resources (VM, Storage, VNet, Subnet, Key Vault)
- Complex resource topology
- Tenant seed fixtures
- Mock ID abstraction service
- Abstracted resource ID mappings
- Graph comparison utilities
- Custom pytest marker: `@pytest.mark.dual_graph`

**Example Usage:**
```python
@pytest.mark.dual_graph
def test_something(mock_neo4j_driver, sample_azure_vm, tenant_seed_alpha):
    # Test implementation
```

---

## Running the Tests

### Run All Dual-Graph Tests
```bash
# Run all tests with the dual_graph marker
uv run pytest -m dual_graph -v

# Expected output: All tests should FAIL with "Not implemented yet" messages
```

### Run Specific Test File
```bash
# ID Abstraction Service tests
uv run pytest tests/services/test_id_abstraction_service.py -v

# Dual Node Creation tests
uv run pytest tests/test_resource_processor_dual_node.py -v

# Relationship Duplication tests
uv run pytest tests/relationship_rules/test_dual_graph_relationships.py -v

# Topology Preservation tests
uv run pytest tests/test_graph_topology_preservation.py -v

# IaC Generation tests
uv run pytest tests/iac/test_iac_with_dual_graph.py -v

# Tenant Seed Management tests
uv run pytest tests/test_tenant_seed_management.py -v

# Query Pattern tests
uv run pytest tests/test_neo4j_query_patterns.py -v
```

### Run Specific Test
```bash
uv run pytest tests/services/test_id_abstraction_service.py::TestIDAbstractionService::test_deterministic_hash_generation -v
```

---

## Test Statistics

| Category | File | Test Count | Status |
|----------|------|-----------|--------|
| ID Abstraction | `test_id_abstraction_service.py` | 25 | ❌ Not Implemented |
| Dual Node Creation | `test_resource_processor_dual_node.py` | 18 | ❌ Not Implemented |
| Relationship Duplication | `test_dual_graph_relationships.py` | 22 | ❌ Not Implemented |
| Topology Preservation | `test_graph_topology_preservation.py` | 24 | ❌ Not Implemented |
| IaC Generation | `test_iac_with_dual_graph.py` | 22 | ❌ Not Implemented |
| Tenant Seed Management | `test_tenant_seed_management.py` | 24 | ❌ Not Implemented |
| Query Patterns | `test_neo4j_query_patterns.py` | 30 | ❌ Not Implemented |
| **TOTAL** | | **165** | **All Failing (Expected)** |

---

## Implementation Roadmap

To implement the dual-graph architecture feature, work through the test files in this order:

1. **Start with Tenant Seed Management** (`test_tenant_seed_management.py`)
   - Create `src/services/tenant_manager.py` with seed management
   - Make these tests pass first

2. **Implement ID Abstraction Service** (`test_id_abstraction_service.py`)
   - Create `src/services/id_abstraction_service.py`
   - Integrate with tenant seed manager

3. **Update Resource Processor for Dual Nodes** (`test_resource_processor_dual_node.py`)
   - Modify `src/resource_processor.py` to create dual nodes
   - Create original and abstracted nodes with SCAN_SOURCE_NODE relationship

4. **Implement Relationship Duplication** (`test_dual_graph_relationships.py`)
   - Update relationship rules in `src/relationship_rules/`
   - Ensure relationships exist in both graphs

5. **Verify Topology Preservation** (`test_graph_topology_preservation.py`)
   - These should automatically pass if previous steps are correct
   - Use for validation

6. **Update IaC Generation** (`test_iac_with_dual_graph.py`)
   - Modify `src/iac/traverser.py` to default to abstracted nodes
   - Update emitters to use abstracted IDs

7. **Implement Query Patterns** (`test_neo4j_query_patterns.py`)
   - Create database indexes
   - Document query patterns
   - These should mostly work once dual nodes exist

---

## Key Design Decisions Captured in Tests

1. **ID Format:** Type-prefixed hash (e.g., `vm-a1b2c3d4`)
2. **Seed:** Per-tenant, stored in Tenant node, immutable
3. **Default Behavior:** `MATCH (r:Resource)` returns abstracted nodes only
4. **Labels:**
   - Abstracted: `:Resource`
   - Original: `:Resource:Original`
5. **Relationship:** `(abstracted)-[:SCAN_SOURCE_NODE]->(original)`
6. **IaC Generation:** Uses abstracted graph by default, no translation needed

---

## Notes

- All tests use `pytest.fail("Not implemented yet - ...")` to clearly indicate what needs to be implemented
- Tests include detailed comments showing expected behavior after implementation
- Tests use mocks extensively to avoid requiring real Azure SDK or Neo4j connections
- Tests follow existing codebase patterns and conventions
- Each test has a clear docstring explaining what it validates and why it's expected to fail

---

## Continuous Integration

These tests will be automatically run by CI once pushed. Expected CI behavior:

- All 165 tests will initially FAIL
- CI should report "165 failed" which is EXPECTED
- As implementation progresses, tests will gradually turn GREEN
- Feature is complete when all 165 tests PASS

---

## Contact

For questions about these tests or the dual-graph architecture feature, refer to:
- **Issue:** #420
- **Design Doc:** (link when available)
- **Test Files:** All in `tests/` directory with marker `@pytest.mark.dual_graph`

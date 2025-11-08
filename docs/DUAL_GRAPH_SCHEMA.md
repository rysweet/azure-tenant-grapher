# Neo4j Dual-Graph Schema Design

## Executive Summary

This document specifies the Neo4j database schema for the dual-graph architecture where every Azure resource exists as both an **Original** node (with real Azure IDs) and an **Abstracted** node (with deterministic, type-prefixed hash IDs). This architecture enables:

1. Comparison between original and abstracted topologies
2. Deterministic IaC generation with stable identifiers
3. Resource name conflict detection across environments
4. Full audit trail from abstracted resources to their Azure sources

## 1. Node Label Strategy

### Design Decision: Dual Label Approach

**Abstracted Nodes** (default query target):
- Labels: `:Resource:Abstracted`
- Primary label `:Resource` ensures backward compatibility
- `:Abstracted` label enables filtering when needed

**Original Nodes** (source of truth):
- Labels: `:Resource:Original`
- Primary label `:Resource` maintains schema consistency
- `:Original` label enables explicit selection

### Rationale

This approach satisfies the requirement that "default queries return abstracted only" while maintaining schema consistency:

```cypher
// Default query - returns abstracted nodes only
MATCH (r:Resource)
WHERE NOT r:Original
RETURN r

// Or use label filtering
MATCH (r:Resource:Abstracted)
RETURN r

// Explicitly query original nodes
MATCH (r:Resource:Original)
RETURN r

// Query both (useful for comparisons)
MATCH (r:Resource)
RETURN r
```

### Alternative Considered and Rejected

**Option**: Only abstracted nodes have `:Resource` label
- **Rejected**: Would require updating all existing queries and relationship rules to handle both `:Resource` and `:OriginalResource` labels, increasing complexity and maintenance burden.

## 2. Complete Node Schema

### 2.1 Abstracted Resource Node

```cypher
CREATE (r:Resource:Abstracted {
  // Primary identifier (deterministic hash)
  id: "vm-a1b2c3d4",

  // Core properties (copied from original)
  name: "web-server-001",
  type: "Microsoft.Compute/virtualMachines",
  location: "eastus",
  resource_group: "rg-production",
  subscription_id: "/subscriptions/...",

  // Abstraction metadata
  abstracted_id: "vm-a1b2c3d4",
  abstraction_type: "vm",
  abstraction_seed: "tenant-specific-seed-value",

  // Resource properties (serialized)
  properties: "{...}",

  // Timestamps
  created_at: datetime(),
  updated_at: datetime(),

  // Processing metadata
  processing_status: "completed",
  llm_description: "...",

  // Scan tracking
  scan_id: "scan-2025-11-05-12345",
  tenant_id: "/providers/Microsoft.Management/managementGroups/...",

  // Original reference (for quick lookup)
  original_id: "/subscriptions/.../resourceGroups/.../providers/Microsoft.Compute/virtualMachines/web-server-001"
})
```

### 2.2 Original Resource Node

```cypher
CREATE (r:Resource:Original {
  // Azure resource ID (real identifier)
  id: "/subscriptions/.../resourceGroups/.../providers/Microsoft.Compute/virtualMachines/web-server-001",

  // Core properties (exact Azure values)
  name: "web-server-001",
  type: "Microsoft.Compute/virtualMachines",
  location: "eastus",
  resource_group: "rg-production",
  subscription_id: "/subscriptions/...",

  // Resource properties (serialized, full detail)
  properties: "{...}",

  // Timestamps
  created_at: datetime(),
  updated_at: datetime(),

  // Processing metadata
  processing_status: "completed",
  llm_description: "...",

  // Scan tracking
  scan_id: "scan-2025-11-05-12345",
  tenant_id: "/providers/Microsoft.Management/managementGroups/...",

  // Abstracted reference (for quick lookup)
  abstracted_id: "vm-a1b2c3d4"
})
```

### 2.3 Property Distribution Strategy

| Property Category | Abstracted Node | Original Node | Notes |
|------------------|-----------------|---------------|-------|
| **Identifiers** | abstracted_id | Azure resource ID | Different ID formats |
| **Core metadata** | Both | Both | name, type, location, RG, subscription |
| **Resource properties** | Minimal | Full | Abstracted may exclude sensitive data |
| **Timestamps** | Both | Both | Independent lifecycle tracking |
| **LLM description** | Both | Both | Generated for both views |
| **Scan metadata** | Both | Both | scan_id, tenant_id for traceability |
| **Cross-references** | original_id | abstracted_id | Quick bidirectional lookup |
| **Abstraction metadata** | Only Abstracted | N/A | seed, type, algorithm details |

### 2.4 Abstraction Seed Storage

**Decision**: Store seed on Tenant node with bidirectional lookup properties on resources.

```cypher
// Tenant node stores the master seed
MERGE (t:Tenant {id: $tenant_id})
SET t.abstraction_seed = $seed,
    t.seed_created_at = datetime(),
    t.seed_algorithm = "sha256-truncated-8"
```

**Rationale**:
- Single source of truth for the abstraction seed
- Per-tenant isolation
- Resources reference the seed but don't duplicate it
- Enables seed rotation if needed in the future

## 3. Relationship Schema

### 3.1 Core Relationship: SCAN_SOURCE_NODE

Links abstracted resources to their original sources:

```cypher
// Direction: (Abstracted) -[:SCAN_SOURCE_NODE]-> (Original)
CREATE (abs:Resource:Abstracted {id: "vm-a1b2c3d4"})
CREATE (orig:Resource:Original {id: "/subscriptions/.../virtualMachines/web-server-001"})
CREATE (abs)-[:SCAN_SOURCE_NODE {
  created_at: datetime(),
  scan_id: "scan-2025-11-05-12345",
  confidence: "exact"  // Could be: exact, inferred, uncertain
}]->(orig)
```

**Properties**:
- `created_at`: When the relationship was established
- `scan_id`: Which scan created this link
- `confidence`: How certain we are about the mapping (future-proofing)

### 3.2 Relationship Duplication Strategy

All existing relationship types must exist in BOTH graphs:

| Relationship Type | Exists In | Notes |
|-------------------|-----------|-------|
| `CONTAINS` | Both graphs | ResourceGroup/Subscription containment |
| `USES_IDENTITY` | Both graphs | Identity assignments |
| `CONNECTED_TO` | Both graphs | Network connections |
| `DEPENDS_ON` | Both graphs | Resource dependencies |
| `USES_SUBNET` | Both graphs | Network topology |
| `SECURED_BY` | Both graphs | Security relationships |
| `RESOLVES_TO` | Both graphs | DNS relationships |
| `HAS_TAG` | Both graphs | Resource tagging |
| `LOCATED_IN` | Both graphs | Regional placement |
| `LOGS_TO` | Both graphs | Monitoring relationships |
| `SCAN_SOURCE_NODE` | Cross-graph only | Links abstracted to original |

### 3.3 Implementation Pattern for Relationship Rules

Each relationship rule will need modification to create relationships in both graphs. Two approaches:

#### Approach A: Wrapper Helper Function (Recommended)

```python
class DatabaseOperations:
    def create_dual_graph_rel(
        self,
        src_id: str,
        rel_type: str,
        tgt_id: str,
        properties: Dict[str, Any] = None
    ) -> bool:
        """
        Create a relationship in both the original and abstracted graphs.

        Args:
            src_id: Source resource ID (Azure ID)
            rel_type: Relationship type (e.g., "USES_SUBNET")
            tgt_id: Target resource ID (Azure ID)
            properties: Optional relationship properties

        Returns:
            bool: True if both relationships created successfully
        """
        # Create relationship in Original graph
        orig_success = self._create_single_rel(
            src_id, rel_type, tgt_id, "Original", properties
        )

        # Look up abstracted IDs
        src_abstracted = self._get_abstracted_id(src_id)
        tgt_abstracted = self._get_abstracted_id(tgt_id)

        # Create relationship in Abstracted graph
        abs_success = False
        if src_abstracted and tgt_abstracted:
            abs_success = self._create_single_rel(
                src_abstracted, rel_type, tgt_abstracted, "Abstracted", properties
            )

        return orig_success and abs_success
```

#### Approach B: Modify Each Rule (More Explicit)

```python
class NetworkRule(RelationshipRule):
    def emit(self, resource: Dict[str, Any], db_ops: Any) -> None:
        rid = resource.get("id")

        # Create relationship in Original graph
        db_ops.create_generic_rel(
            str(rid), "USES_SUBNET", str(subnet_id),
            "Resource", "id", label_filter="Original"
        )

        # Create relationship in Abstracted graph
        abs_id = db_ops.get_abstracted_id(rid)
        abs_subnet_id = db_ops.get_abstracted_id(subnet_id)
        if abs_id and abs_subnet_id:
            db_ops.create_generic_rel(
                abs_id, "USES_SUBNET", abs_subnet_id,
                "Resource", "id", label_filter="Abstracted"
            )
```

**Recommendation**: Use Approach A (wrapper function) because:
- Reduces code duplication
- Centralizes abstraction logic
- Easier to maintain and test
- Automatic handling of missing abstracted nodes

## 4. Indexes and Constraints

### 4.1 Updated Constraints

```cypher
// Original Resource constraint (Azure IDs)
CREATE CONSTRAINT original_resource_id_unique IF NOT EXISTS
FOR (r:Original)
REQUIRE r.id IS UNIQUE;

// Abstracted Resource constraint (hash IDs)
CREATE CONSTRAINT abstracted_resource_id_unique IF NOT EXISTS
FOR (r:Abstracted)
REQUIRE r.id IS UNIQUE;

// Keep existing constraint for backward compatibility
CREATE CONSTRAINT resource_id_unique IF NOT EXISTS
FOR (r:Resource)
REQUIRE r.id IS UNIQUE;

// Other existing constraints remain unchanged
CREATE CONSTRAINT IF NOT EXISTS
FOR (rg:ResourceGroup)
REQUIRE rg.id IS UNIQUE;

CREATE CONSTRAINT IF NOT EXISTS
FOR (s:Subscription)
REQUIRE s.id IS UNIQUE;

CREATE CONSTRAINT IF NOT EXISTS
FOR (t:Tenant)
REQUIRE t.id IS UNIQUE;
```

### 4.2 New Indexes for Dual-Graph Queries

```cypher
// Fast lookup of abstracted resources by original ID
CREATE INDEX abstracted_by_original_id IF NOT EXISTS
FOR (r:Abstracted)
ON (r.original_id);

// Fast lookup of original resources by abstracted ID
CREATE INDEX original_by_abstracted_id IF NOT EXISTS
FOR (r:Original)
ON (r.abstracted_id);

// Scan-based queries
CREATE INDEX resource_scan_id IF NOT EXISTS
FOR (r:Resource)
ON (r.scan_id);

// Type-based abstracted queries
CREATE INDEX abstracted_type IF NOT EXISTS
FOR (r:Abstracted)
ON (r.type);

// Composite index for abstracted resources by tenant and type
CREATE INDEX abstracted_tenant_type IF NOT EXISTS
FOR (r:Abstracted)
ON (r.tenant_id, r.type);
```

### 4.3 Index Strategy Rationale

- **Bidirectional lookup indexes**: Enable fast traversal between original and abstracted nodes without following relationships
- **Scan indexes**: Support audit queries and incremental updates
- **Type indexes**: Optimize common queries that filter by resource type
- **Composite indexes**: Support multi-column queries common in IaC generation

## 5. Migration Strategy

### 5.1 Migration Approach: Additive with Feature Flag

**Goal**: Zero downtime, backward compatible, gradual rollout.

**Phase 1: Schema Addition** (Migration 0010)
```cypher
// Add new labels to existing resources (mark as abstracted)
MATCH (r:Resource)
WHERE NOT r:Original AND NOT r:Abstracted
SET r:Abstracted
SET r.abstracted_id = r.id;

// Add new constraints and indexes
CREATE CONSTRAINT abstracted_resource_id_unique IF NOT EXISTS
FOR (r:Abstracted)
REQUIRE r.id IS UNIQUE;

CREATE CONSTRAINT original_resource_id_unique IF NOT EXISTS
FOR (r:Original)
REQUIRE r.id IS UNIQUE;

CREATE INDEX abstracted_by_original_id IF NOT EXISTS
FOR (r:Abstracted)
ON (r.original_id);

CREATE INDEX original_by_abstracted_id IF NOT EXISTS
FOR (r:Original)
ON (r.abstracted_id);

CREATE INDEX resource_scan_id IF NOT EXISTS
FOR (r:Resource)
ON (r.scan_id);
```

**Phase 2: Feature Flag in Code**
```python
# In config_manager.py or environment
ENABLE_DUAL_GRAPH = os.getenv("ENABLE_DUAL_GRAPH", "false").lower() == "true"

# In resource_processor.py
class DatabaseOperations:
    def upsert_resource(self, resource: Dict[str, Any]) -> bool:
        if self.config.enable_dual_graph:
            return self._upsert_dual_graph_resource(resource)
        else:
            return self._upsert_single_resource(resource)  # existing logic
```

**Phase 3: Gradual Rollout**
1. Deploy code with feature flag OFF (default)
2. Run migration 0010 on staging environment
3. Enable feature flag on staging, verify
4. Run migration 0010 on production
5. Enable feature flag on production
6. Monitor for issues
7. After stabilization period, make dual-graph the default

### 5.2 Handling Existing Graphs

For databases with existing single-node data:

```cypher
// Option 1: Convert existing resources to abstracted format
MATCH (r:Resource)
WHERE NOT r:Original AND NOT r:Abstracted
SET r:Abstracted
SET r.abstracted_id = apoc.text.slug(r.name, "-")  // Simple slug for migration
SET r.original_id = r.id
RETURN count(r) as converted;

// Option 2: Clear and rescan (recommended for correctness)
// User runs: atg scan --tenant-id <ID> --enable-dual-graph
```

**Recommendation**: Option 2 (rescan) is preferred because:
- Ensures proper hash generation with tenant seed
- Validates the full dual-graph creation pipeline
- Avoids data migration complexity
- Provides clean slate for new architecture

### 5.3 Backward Compatibility

**Query Compatibility**: Add filter to existing queries during transition:

```python
# In IaC traverser and other query locations
def get_resources_for_iac(self, tenant_id: str) -> List[Dict[str, Any]]:
    query = """
    MATCH (r:Resource)
    WHERE r.tenant_id = $tenant_id
      AND (NOT exists(r:Original))  // Exclude original nodes
    RETURN r
    """
    # This ensures only abstracted nodes are returned
```

## 6. Query Patterns

### 6.1 Common Query Examples

#### Get All Abstracted Resources
```cypher
// Method 1: Using label
MATCH (r:Resource:Abstracted)
RETURN r;

// Method 2: Using filter
MATCH (r:Resource)
WHERE NOT r:Original
RETURN r;

// Method 3: Using property (after migration)
MATCH (r:Resource)
WHERE r.abstracted_id IS NOT NULL
RETURN r;
```

#### Get Original Source for an Abstracted Resource
```cypher
// Method 1: Following relationship
MATCH (abs:Abstracted {id: $abstracted_id})-[:SCAN_SOURCE_NODE]->(orig:Original)
RETURN orig;

// Method 2: Using property lookup (faster)
MATCH (abs:Abstracted {id: $abstracted_id})
MATCH (orig:Original {id: abs.original_id})
RETURN orig;
```

#### Compare Original vs Abstracted Topology
```cypher
// Find resources connected in original but not in abstracted
MATCH (orig1:Original)-[rel:CONNECTED_TO]->(orig2:Original)
MATCH (abs1:Abstracted {original_id: orig1.id})
MATCH (abs2:Abstracted {original_id: orig2.id})
WHERE NOT (abs1)-[:CONNECTED_TO]->(abs2)
RETURN orig1.id, orig2.id, type(rel),
       "Missing in abstracted graph" as issue;
```

#### Find Orphaned Abstracted Resources (No Original)
```cypher
MATCH (abs:Abstracted)
WHERE NOT (abs)-[:SCAN_SOURCE_NODE]->(:Original)
  AND NOT exists((abs)<-[:SCAN_SOURCE_NODE]-())
RETURN abs.id, abs.name, abs.type,
       "Orphaned abstracted node" as issue;
```

#### Find Duplicate Abstracted IDs (Hash Collisions)
```cypher
MATCH (abs:Abstracted)
WITH abs.abstracted_id as hash_id, collect(abs) as resources
WHERE size(resources) > 1
RETURN hash_id,
       [r in resources | r.original_id] as original_ids,
       size(resources) as collision_count
ORDER BY collision_count DESC;
```

#### Get Resource with Full Context (Original + Abstracted)
```cypher
MATCH (abs:Abstracted {id: $abstracted_id})
OPTIONAL MATCH (abs)-[:SCAN_SOURCE_NODE]->(orig:Original)
RETURN abs as abstracted_node,
       orig as original_node,
       abs.abstracted_id = abs.id as is_abstracted,
       orig.id = abs.original_id as ids_match;
```

#### Find All Resources in Abstracted Graph with Dependencies
```cypher
MATCH (abs:Abstracted)-[rel]->(target:Abstracted)
WHERE abs.tenant_id = $tenant_id
RETURN abs.id, abs.name, abs.type,
       type(rel) as relationship_type,
       target.id, target.name, target.type
ORDER BY abs.type, abs.name;
```

#### Validate Relationship Parity Between Graphs
```cypher
// Count relationships in each graph
MATCH (orig:Original)-[rel_orig]->(target_orig:Original)
WITH count(rel_orig) as original_rel_count

MATCH (abs:Abstracted)-[rel_abs]->(target_abs:Abstracted)
WITH original_rel_count, count(rel_abs) as abstracted_rel_count

RETURN original_rel_count,
       abstracted_rel_count,
       original_rel_count - abstracted_rel_count as difference,
       CASE
         WHEN original_rel_count = abstracted_rel_count
         THEN "Graphs in sync"
         ELSE "Graph mismatch detected"
       END as status;
```

### 6.2 IaC Generation Queries

The IaC generation traverser should ONLY query abstracted nodes:

```cypher
// Start IaC traversal from subscriptions in abstracted graph
MATCH (s:Subscription)<-[:CONTAINS]-(r:Abstracted)
WHERE r.tenant_id = $tenant_id
  AND NOT r:Original  // Defensive filter
RETURN r
ORDER BY r.type, r.name;
```

### 6.3 Debugging and Audit Queries

```cypher
// Find resources created in a specific scan
MATCH (r:Resource {scan_id: $scan_id})
RETURN labels(r) as node_labels,
       r.id, r.name, r.type,
       exists((r)-[:SCAN_SOURCE_NODE]->()) as has_original_link;

// Check seed consistency
MATCH (t:Tenant {id: $tenant_id})
MATCH (r:Abstracted {tenant_id: $tenant_id})
RETURN t.abstraction_seed as tenant_seed,
       r.abstraction_seed as resource_seed,
       t.abstraction_seed = r.abstraction_seed as seeds_match,
       count(r) as resource_count;

// Find recently updated resources
MATCH (r:Resource)
WHERE r.updated_at > datetime() - duration('PT1H')
RETURN labels(r) as labels, r.id, r.name, r.updated_at
ORDER BY r.updated_at DESC;
```

## 7. Potential Schema Issues and Solutions

### 7.1 Issue: Hash Collisions in Abstracted IDs

**Problem**: Two different resources might hash to the same abstracted ID (though unlikely with 8-character hex = 4 billion combinations).

**Detection**:
```cypher
MATCH (abs:Abstracted)
WITH abs.abstracted_id as hash_id, collect(abs.original_id) as originals
WHERE size(originals) > 1
RETURN hash_id, originals;
```

**Solution**:
- Use longer hashes (12 characters = 16^12 combinations)
- Include resource type in hash input to reduce collision space
- Detect collisions during scan and append counter (e.g., `vm-a1b2c3d4-2`)
- Log warnings and alert operators

### 7.2 Issue: Orphaned Nodes (Original Without Abstracted)

**Problem**: If abstraction fails for a resource, we might create the original but not the abstracted node.

**Detection**: See query in section 6.1.

**Prevention**:
```python
def process_resource(resource: Dict[str, Any]) -> bool:
    """
    Process a resource by creating both original and abstracted nodes atomically.
    """
    try:
        # Generate abstracted ID
        abs_id = self.abstraction_service.generate_id(resource)

        # Create both nodes in a transaction
        with self.session_manager.session() as session:
            with session.begin_transaction() as tx:
                self._create_original_node(tx, resource)
                self._create_abstracted_node(tx, resource, abs_id)
                self._create_scan_source_rel(tx, abs_id, resource["id"])
                tx.commit()
        return True
    except Exception:
        # Both nodes rolled back together
        logger.exception(f"Failed to process resource {resource['id']}")
        return False
```

### 7.3 Issue: Query Performance with Dual Labels

**Problem**: Label filtering `WHERE NOT r:Original` might slow down queries.

**Solutions**:
1. Use explicit label matching: `MATCH (r:Abstracted)` instead of filters
2. Add indexes on label combinations (Neo4j does this automatically)
3. Cache abstracted node IDs in application layer for frequently accessed resources
4. Use property-based filtering if faster: `WHERE r.abstracted_id IS NOT NULL`

**Benchmark**:
```cypher
// Test query performance
PROFILE MATCH (r:Resource:Abstracted) RETURN count(r);
PROFILE MATCH (r:Resource) WHERE NOT r:Original RETURN count(r);
PROFILE MATCH (r:Resource) WHERE r.abstracted_id IS NOT NULL RETURN count(r);
```

### 7.4 Issue: Relationship Duplication Overhead

**Problem**: Creating relationships in both graphs doubles the write load.

**Solutions**:
- Use batch operations for relationship creation
- Parallelize original and abstracted graph writes
- Consider async relationship creation for non-critical relationships
- Monitor write performance and optimize bottlenecks

### 7.5 Issue: Seed Rotation

**Problem**: If we need to change the abstraction seed (e.g., security incident), all abstracted IDs change.

**Solution** (future consideration):
```cypher
// Track seed versions
MATCH (t:Tenant {id: $tenant_id})
SET t.abstraction_seeds = coalesce(t.abstraction_seeds, []) + [
  {seed: $new_seed, version: $version, created_at: datetime()}
];

// Version abstracted IDs
CREATE (r:Abstracted {
  id: "vm-a1b2c3d4",
  abstracted_id: "vm-a1b2c3d4",
  abstraction_seed_version: 1
});
```

### 7.6 Issue: Mixing Abstracted and Original in IaC Generation

**Problem**: IaC generation accidentally queries original nodes instead of abstracted.

**Prevention**:
- Create wrapper functions that enforce abstracted-only queries
- Add validation in IaC traverser to reject original nodes
- Use type hints and runtime checks

```python
class IaCTraverser:
    def _validate_node_is_abstracted(self, node: Dict[str, Any]) -> None:
        """Raise error if node is not an abstracted resource."""
        if "Original" in node.get("labels", []):
            raise ValueError(
                f"IaC generation received Original node: {node['id']}. "
                "Only Abstracted nodes should be used for IaC generation."
            )
```

## 8. Implementation Checklist

### Schema Changes
- [ ] Create migration 0010 with new constraints and indexes
- [ ] Add abstraction seed property to Tenant nodes
- [ ] Add bidirectional lookup properties (original_id, abstracted_id)

### Code Changes
- [ ] Implement abstraction ID generation service
- [ ] Add feature flag for dual-graph mode
- [ ] Modify DatabaseOperations to support dual-graph creation
- [ ] Update relationship rules to create relationships in both graphs
- [ ] Add helper functions for graph traversal (abstracted-only)
- [ ] Update IaC traverser to filter for abstracted nodes only

### Testing
- [ ] Unit tests for abstraction ID generation
- [ ] Unit tests for dual-graph node creation
- [ ] Integration tests with Neo4j container
- [ ] Test backward compatibility with single-graph mode
- [ ] Test hash collision detection
- [ ] Test orphan node detection

### Validation
- [ ] Create validation queries to check graph consistency
- [ ] Add monitoring for relationship parity
- [ ] Create debugging utilities for operators

### Documentation
- [ ] Update architecture documentation
- [ ] Document query patterns for developers
- [ ] Create operator runbook for common issues
- [ ] Update IaC generation documentation

### Deployment
- [ ] Deploy with feature flag OFF
- [ ] Run migration 0010
- [ ] Enable feature flag in staging
- [ ] Monitor and validate
- [ ] Roll out to production

## 9. Future Enhancements

### 9.1 Selective Abstraction
Allow users to choose which resources to abstract:
```python
abstraction_config = {
    "abstract_resources": ["virtualMachines", "storageAccounts"],
    "keep_original_only": ["keyVaults"]  # Sensitive resources
}
```

### 9.2 Cross-Tenant Comparison
Query abstracted graphs from multiple tenants to find common patterns:
```cypher
MATCH (r1:Abstracted {tenant_id: $tenant1}),
      (r2:Abstracted {tenant_id: $tenant2})
WHERE r1.abstracted_id = r2.abstracted_id
  AND r1.type = r2.type
RETURN r1, r2;
```

### 9.3 Temporal Abstraction
Track how abstracted IDs change over time:
```cypher
CREATE (r:Abstracted {
  id: "vm-a1b2c3d4",
  abstraction_history: [
    {id: "vm-oldid123", valid_from: "2025-01-01", valid_to: "2025-10-01"},
    {id: "vm-a1b2c3d4", valid_from: "2025-10-01", valid_to: null}
  ]
});
```

### 9.4 Confidence Scoring
Track certainty of abstraction mappings:
```cypher
CREATE (abs)-[:SCAN_SOURCE_NODE {
  confidence: 0.95,
  confidence_factors: ["exact_name_match", "same_resource_type", "same_location"],
  last_verified: datetime()
}]->(orig);
```

## 10. Conclusion

This dual-graph schema provides:

1. **Separation of Concerns**: Original nodes preserve Azure truth, abstracted nodes enable deterministic IaC
2. **Traceability**: Every abstracted resource links back to its source
3. **Flexibility**: Feature flag allows gradual rollout and easy rollback
4. **Performance**: Optimized indexes for common query patterns
5. **Maintainability**: Clear label strategy and helper functions reduce complexity

The schema is designed for incremental adoption, backward compatibility, and future extensibility while maintaining the core principle: **default queries return abstracted nodes, with explicit paths to access original nodes when needed**.

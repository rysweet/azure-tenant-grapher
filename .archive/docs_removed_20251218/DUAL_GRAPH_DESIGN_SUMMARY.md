# Dual-Graph Architecture Design Summary

## Quick Reference

This is a high-level summary of the dual-graph architecture design. For detailed information, see the linked documents.

## What is Dual-Graph Architecture?

Every Azure resource exists as **two nodes** in Neo4j:

1. **Original Node** - Has the real Azure resource ID (e.g., `/subscriptions/.../virtualMachines/vm-001`)
2. **Abstracted Node** - Has a deterministic hash ID (e.g., `vm-a1b2c3d4`)

These are linked by a `SCAN_SOURCE_NODE` relationship: `(Abstracted)-[:SCAN_SOURCE_NODE]->(Original)`

## Why Two Graphs?

- **Original Graph**: Preserves exact Azure topology for comparison and auditing
- **Abstracted Graph**: Provides stable, deterministic IDs for IaC generation
- **Benefits**: Enables name conflict detection, reproducible IaC, and topology comparison

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Relationship Direction** | `(Abstracted)-[:SCAN_SOURCE_NODE]->(Original)` | IaC uses abstracted, needs link to source |
| **ID Format** | Type-prefixed hash (e.g., `vm-a1b2c3d4`) | Readable, collision-resistant, type-safe |
| **Seed Storage** | Per-tenant property on Tenant node | Single source of truth, enables rotation |
| **Node Labels** | `:Resource:Abstracted` and `:Resource:Original` | Enables default queries to return abstracted only |
| **Default Queries** | `MATCH (r:Resource) WHERE NOT r:Original` | Returns abstracted nodes by default |

## Node Schema

### Abstracted Node
```cypher
CREATE (r:Resource:Abstracted {
  id: "vm-a1b2c3d4",                    // Hash ID
  abstracted_id: "vm-a1b2c3d4",
  original_id: "/subscriptions/.../vm-001",  // Link to original
  abstraction_seed: "tenant-seed",
  abstraction_type: "vm",

  // Standard properties
  name: "vm-001",
  type: "Microsoft.Compute/virtualMachines",
  location: "eastus",
  resource_group: "rg-prod",
  subscription_id: "/subscriptions/...",

  // Metadata
  scan_id: "scan-2025-11-05-12345",
  tenant_id: "/providers/...",
  created_at: datetime(),
  updated_at: datetime()
})
```

### Original Node
```cypher
CREATE (r:Resource:Original {
  id: "/subscriptions/.../virtualMachines/vm-001",  // Azure ID
  abstracted_id: "vm-a1b2c3d4",                    // Link to abstracted

  // Standard properties (same as abstracted)
  name: "vm-001",
  type: "Microsoft.Compute/virtualMachines",
  location: "eastus",
  // ... etc
})
```

## Relationship Schema

**All existing relationships are duplicated in both graphs:**

- `CONTAINS` (ResourceGroup/Subscription containment)
- `USES_IDENTITY` (Identity assignments)
- `CONNECTED_TO` (Network connections)
- `DEPENDS_ON` (Dependencies)
- `USES_SUBNET` (Network topology)
- `SECURED_BY` (Security)
- `RESOLVES_TO` (DNS)
- `HAS_TAG` (Tagging)
- `LOCATED_IN` (Regional placement)
- `LOGS_TO` (Monitoring)

**Plus one cross-graph relationship:**
- `SCAN_SOURCE_NODE` (links abstracted to original)

## Query Patterns

### Get Abstracted Resources (for IaC)
```cypher
MATCH (r:Resource:Abstracted)
WHERE r.tenant_id = $tenant_id
RETURN r;
```

### Get Original Source
```cypher
MATCH (abs:Abstracted {id: $abstracted_id})-[:SCAN_SOURCE_NODE]->(orig:Original)
RETURN orig;
```

### Compare Topologies
```cypher
// Find missing relationships in abstracted graph
MATCH (orig1:Original)-[rel]->(orig2:Original)
MATCH (abs1:Abstracted {original_id: orig1.id})
MATCH (abs2:Abstracted {original_id: orig2.id})
WHERE NOT (abs1)-[rel]->(abs2)
RETURN "Missing relationship" as issue;
```

## Implementation Approach

### Phase-Based Rollout
1. **Schema + Infrastructure** (Week 1)
2. **Node Creation** (Week 2)
3. **Relationships** (Week 3)
4. **IaC Updates** (Week 4)
5. **Validation** (Week 5)
6. **Production** (Week 6)

### Feature Flag
```bash
export ENABLE_DUAL_GRAPH=true  # Enable dual-graph mode
```

- Default: `false` (backward compatible)
- Easy rollback if issues arise
- Gradual rollout to production

## Code Changes Required

### 1. Abstraction Service (New)
```python
# src/services/abstraction_service.py
class AbstractionIDGenerator:
    def generate_id(self, resource: Dict) -> str:
        # Generate type-prefixed hash ID
        return f"{type_prefix}-{hash_value}"
```

### 2. Database Operations (Modified)
```python
# src/resource_processor.py
class DatabaseOperations:
    def upsert_dual_graph_resource(self, resource: Dict) -> bool:
        # Create both Original and Abstracted nodes
        pass

    def create_dual_graph_rel(self, src_id, rel_type, tgt_id) -> bool:
        # Create relationship in both graphs
        pass
```

### 3. Relationship Rules (Modified)
```python
# src/relationship_rules/network_rule.py
def emit(self, resource, db_ops):
    # OLD: db_ops.create_generic_rel(src, rel_type, tgt, "Resource", "id")
    # NEW: db_ops.create_dual_graph_rel(src, rel_type, tgt)
    pass
```

### 4. IaC Traverser (Modified)
```cypher
-- OLD: MATCH (r:Resource) WHERE r.tenant_id = $tenant_id
-- NEW: MATCH (r:Resource:Abstracted) WHERE r.tenant_id = $tenant_id
```

## Database Migration

```cypher
// migrations/0010_dual_graph_schema.cypher

// Add constraints
CREATE CONSTRAINT original_resource_id_unique IF NOT EXISTS
FOR (r:Original) REQUIRE r.id IS UNIQUE;

CREATE CONSTRAINT abstracted_resource_id_unique IF NOT EXISTS
FOR (r:Abstracted) REQUIRE r.id IS UNIQUE;

// Add indexes
CREATE INDEX abstracted_by_original_id IF NOT EXISTS
FOR (r:Abstracted) ON (r.original_id);

CREATE INDEX original_by_abstracted_id IF NOT EXISTS
FOR (r:Original) ON (r.abstracted_id);
```

## Testing Strategy

### Unit Tests
- Abstraction ID generation
- Hash collision detection
- Seed management

### Integration Tests
- Dual-graph node creation
- Relationship duplication
- Feature flag toggle

### End-to-End Tests
- Full scan with dual-graph
- IaC generation validation
- Backward compatibility

### Validation Queries
- Check for orphaned nodes
- Verify relationship parity
- Detect hash collisions

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| **Data corruption** | Test thoroughly, backup before migration, use transactions |
| **Performance degradation** | Profile early, use batching, add indexes proactively |
| **Hash collisions** | 8-char hex = 4B combinations, collision detection, type prefixes |
| **Feature flag issues** | Integration tests for both modes, clear logging |
| **Relationship parity** | Validation queries, automated checks, repair scripts |

## Rollback Plan

### Quick Rollback (< 1 hour)
```bash
export ENABLE_DUAL_GRAPH=false
systemctl restart azure-tenant-grapher
```

### Full Rollback (< 4 hours)
1. Restore database from backup
2. Deploy previous code version
3. Verify system health

## Success Criteria

### Functional
- ✓ 100% of resources have both nodes
- ✓ 100% of relationships duplicated
- ✓ 0 hash collisions
- ✓ 0 orphaned nodes
- ✓ Deterministic IaC output

### Performance
- ✓ Scan time increase < 20%
- ✓ Query performance within 10%
- ✓ Database size < 2.5x
- ✓ Memory usage increase < 30%

## Document Reference

For complete details, see:

1. **[DUAL_GRAPH_SCHEMA.md](./DUAL_GRAPH_SCHEMA.md)** - Complete schema specification
   - Node labels and properties
   - Relationship types
   - Indexes and constraints
   - Query patterns
   - Schema issues and solutions

2. **[DUAL_GRAPH_QUERIES.cypher](./DUAL_GRAPH_QUERIES.cypher)** - Query examples
   - Basic queries
   - Cross-reference queries
   - Topology queries
   - Validation queries
   - Debugging queries

3. **[DUAL_GRAPH_IMPLEMENTATION_EXAMPLE.py](./DUAL_GRAPH_IMPLEMENTATION_EXAMPLE.py)** - Code reference
   - Abstraction service implementation
   - Database operations
   - Relationship rule patterns
   - Usage examples

4. **[DUAL_GRAPH_IMPLEMENTATION_STRATEGY.md](./DUAL_GRAPH_IMPLEMENTATION_STRATEGY.md)** - Implementation plan
   - Phase-by-phase tasks
   - Testing strategy
   - Risk mitigation
   - Rollback procedures

5. **[../migrations/0010_dual_graph_schema.cypher](../migrations/0010_dual_graph_schema.cypher)** - Database migration
   - Constraints
   - Indexes
   - Verification queries

## Quick Start for Developers

```bash
# 1. Read the schema design
cat docs/DUAL_GRAPH_SCHEMA.md

# 2. Review the implementation example
cat docs/DUAL_GRAPH_IMPLEMENTATION_EXAMPLE.py

# 3. Check the migration
cat migrations/0010_dual_graph_schema.cypher

# 4. Run tests
uv run pytest tests/test_abstraction_service.py -v

# 5. Try it locally
export ENABLE_DUAL_GRAPH=true
uv run atg scan --tenant-id <YOUR_TENANT_ID>

# 6. Validate the graph
uv run atg validate-graph --tenant-id <YOUR_TENANT_ID>

# 7. Generate IaC
uv run atg generate-iac --tenant-id <YOUR_TENANT_ID> --format terraform
```

## Questions?

- **Schema questions**: See [DUAL_GRAPH_SCHEMA.md](./DUAL_GRAPH_SCHEMA.md)
- **Implementation questions**: See [DUAL_GRAPH_IMPLEMENTATION_EXAMPLE.py](./DUAL_GRAPH_IMPLEMENTATION_EXAMPLE.py)
- **Process questions**: See [DUAL_GRAPH_IMPLEMENTATION_STRATEGY.md](./DUAL_GRAPH_IMPLEMENTATION_STRATEGY.md)
- **Query questions**: See [DUAL_GRAPH_QUERIES.cypher](./DUAL_GRAPH_QUERIES.cypher)

## Next Steps

1. Review this design with the team
2. Start Phase 1: Schema and Infrastructure
3. Follow the implementation strategy
4. Test thoroughly at each phase
5. Deploy to staging first
6. Monitor and validate
7. Roll out to production

---

**Design Status**: ✅ Complete - Ready for Implementation
**Last Updated**: 2025-11-05
**Implementation Tracking**: See [DUAL_GRAPH_IMPLEMENTATION_STRATEGY.md](./DUAL_GRAPH_IMPLEMENTATION_STRATEGY.md)

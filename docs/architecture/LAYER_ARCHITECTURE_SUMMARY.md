# Multi-Layer Graph Architecture - Summary

**Version**: 1.0
**Date**: 2025-11-16
**Status**: Ready for Implementation

## Quick Overview

This architecture solves the data loss problem in scale operations by introducing multiple coexisting graph layers (projections) that allow non-destructive experimentation while preserving the immutable Original graph as the source of truth.

## The Problem We're Solving

**Before (Current State):**
```
┌─────────────────────────────────────────────┐
│ Original Graph (5,584 nodes)                │
│ └─→ Real Azure IDs                          │
└─────────────────────────────────────────────┘
               ↓ SCAN_SOURCE_NODE
┌─────────────────────────────────────────────┐
│ Abstracted Graph (56 nodes) ← DATA LOSS!    │
│ └─→ Abstracted IDs                          │
└─────────────────────────────────────────────┘
         ↓ Scale operations
     DESTRUCTIVE!
```

**Problem**: Scale operations (merge, split) directly modify the abstracted graph, destroying baseline data. 99% data loss occurred: 5,584 → 56 nodes.

**After (Multi-Layer):**
```
┌─────────────────────────────────────────────┐
│ Original Graph (5,584 nodes) - IMMUTABLE    │
│ └─→ Real Azure IDs                          │
└─────────────────────────────────────────────┘
               ↓ SCAN_SOURCE_NODE
    ┌──────────┴──────────┬──────────┐
    ↓                     ↓          ↓
┌─────────┐  ┌──────────────┐  ┌──────────────┐
│ default │  │ scaled-v1    │  │ experiment-1 │
│ 5,584   │  │ 1,245 nodes  │  │ 856 nodes    │
│ nodes   │  │              │  │              │
└─────────┘  └──────────────┘  └──────────────┘
  BASELINE     PRODUCTION        TESTING
  (active)     (derived)         (derived)
```

**Solution**: Multiple independent layers, each a complete projection. Scale operations create new layers, preserving existing ones.

## Core Concepts

### 1. Three-Tier Structure

```
┌────────────────────────────────────────────────────────┐
│                    Tier 3: Layer Metadata              │
│  (:Layer nodes) - Management, lineage, statistics      │
├────────────────────────────────────────────────────────┤
│                    Tier 2: Abstracted Layers           │
│  (:Resource nodes with layer_id property)              │
│  - Multiple coexisting projections                     │
│  - One marked as "active"                              │
├────────────────────────────────────────────────────────┤
│                    Tier 1: Original Graph              │
│  (:Resource:Original nodes) - Immutable source         │
└────────────────────────────────────────────────────────┘
```

### 2. Active Layer Concept

- **One active layer at a time** (per tenant)
- All operations default to active layer
- Switching layers changes operational context
- Like switching git branches

**Example:**
```bash
# All commands use active layer by default
uv run atg layer active                    # Shows: default
uv run atg generate-iac                    # Uses: default

# Switch to scaled version
uv run atg layer active scaled-v1          # Activate: scaled-v1
uv run atg generate-iac                    # Uses: scaled-v1
```

### 3. Layer Isolation

**Key Guarantee**: Layers never interfere with each other.

```cypher
// Queries MUST filter by layer_id
MATCH (r:Resource {layer_id: $layer_id})
WHERE r.resource_type = 'VirtualMachine'

// Relationships MUST stay within layer
MATCH (r1:Resource {layer_id: $layer_id})
      -[rel]->
      (r2:Resource {layer_id: $layer_id})

// SCAN_SOURCE_NODE can cross (connects to Original)
MATCH (r:Resource {layer_id: $layer_id})
      -[:SCAN_SOURCE_NODE]->
      (orig:Original)
```

### 4. Copy-Then-Transform Pattern

Scale operations follow this pattern:

```
1. Copy source layer → target layer
2. Apply transformations in target layer
3. Optionally activate target layer
4. Source layer remains unchanged
```

**Example:**
```python
# Before: Direct modification (DESTRUCTIVE)
merge_vnets(["vnet-1", "vnet-2"])  # Modifies current graph!

# After: Copy-then-transform (NON-DESTRUCTIVE)
copy_layer("default", "scaled-v1")                    # Copy
merge_vnets(["vnet-1", "vnet-2"], layer="scaled-v1")  # Transform
activate_layer("scaled-v1")                           # Switch
# "default" layer unchanged!
```

## Schema Changes

### Node Property Addition

```cypher
// Before
(:Resource {
  id: "vm-a1b2c3d4",
  resource_type: "VirtualMachine",
  name: "prod-vm-001"
})

// After (with layer_id)
(:Resource {
  id: "vm-a1b2c3d4",
  resource_type: "VirtualMachine",
  name: "prod-vm-001",
  layer_id: "default",                    // NEW
  layer_created_at: "2025-11-16T10:00:00Z" // NEW
})
```

### New Node Type: Layer

```cypher
(:Layer {
  layer_id: "default",
  name: "Default Baseline",
  description: "1:1 abstraction from initial scan",
  created_at: "2025-11-16T10:00:00Z",
  created_by: "scan",
  parent_layer_id: null,
  is_active: true,
  is_baseline: true,
  tenant_id: "tenant-123",
  node_count: 5584,
  relationship_count: 8234,
  metadata: {...}
})
```

### New Relationship Type: DERIVED_FROM

```cypher
(:Layer {layer_id: "scaled-v1"})
-[:DERIVED_FROM {
  operation: "merge_vnets",
  operation_id: "op-xyz789",
  created_at: "2025-11-16T11:00:00Z"
}]->
(:Layer {layer_id: "default"})
```

### Indexes and Constraints

```cypher
// Composite unique constraint (was: just id)
CREATE CONSTRAINT resource_layer_id_unique
FOR (r:Resource) REQUIRE (r.id, r.layer_id) IS UNIQUE;

// Layer ID index for fast filtering
CREATE INDEX resource_layer_id
FOR (r:Resource) ON (r.layer_id);

// Layer metadata constraint
CREATE CONSTRAINT layer_id_unique
FOR (l:Layer) REQUIRE l.layer_id IS UNIQUE;
```

## Service Architecture

### Core Services

```
LayerManagementService
├─ create_layer()           Create new layer metadata
├─ list_layers()            List all layers
├─ get_layer()              Get specific layer
├─ get_active_layer()       Get active layer
├─ delete_layer()           Delete layer (with safety checks)
├─ set_active_layer()       Switch active layer
├─ copy_layer()             Duplicate entire layer
├─ compare_layers()         Find differences between layers
├─ refresh_layer_stats()    Recalculate node/relationship counts
└─ validate_layer_integrity() Check layer health

LayerAwareQueryService
├─ get_resource()           Get resource from layer
├─ find_resources()         Query resources in layer
├─ traverse_relationships() Follow relationships within layer
├─ get_resource_original()  Get Original node for resource
└─ count_resources()        Count resources in layer

ScaleOperationsService (Enhanced)
├─ merge_vnets()            Merge VNets in new layer
├─ merge_subnets()          Merge subnets in new layer
├─ split_vnet()             Split VNet in new layer
└─ consolidate_vms()        Consolidate VMs in new layer
```

### Service Dependencies

```
     CLI Commands
          ↓
  LayerManagementService  ←──┐
          ↓                   │
  LayerAwareQueryService      │
          ↓                   │
  ScaleOperationsService ─────┘
          ↓
     Neo4j Driver
```

## CLI Interface

### New Command Group: atg layer

```bash
atg layer list                          # List all layers
atg layer show <layer-id>               # Show layer details
atg layer active [layer-id]             # Show/set active layer
atg layer create <layer-id>             # Create new empty layer
atg layer copy <source> <target>        # Copy layer
atg layer delete <layer-id>             # Delete layer
atg layer diff <layer-a> <layer-b>      # Compare layers
atg layer validate <layer-id>           # Validate layer integrity
atg layer refresh-stats <layer-id>      # Refresh statistics
atg layer archive <layer-id> <path>     # Export to JSON
atg layer restore <path>                # Import from JSON
```

### Enhanced Existing Commands

```bash
# Scale operations (now create new layers)
atg scale merge-vnets <vnets...> \
  --source-layer default \
  --target-layer scaled-v1 \
  --make-active

# IaC generation (from specific layer)
atg generate-iac --layer scaled-v1

# Scan (creates default layer)
atg scan --tenant-id <id>  # Creates/updates "default" layer
```

## Migration Strategy

### Phase 1: Schema (Non-Breaking)

```python
# Migration: 012_add_layer_support.py

1. Add layer_id='default' to existing :Resource nodes
2. Create :Layer node for 'default'
3. Set is_active=true, is_baseline=true
4. Create indexes and constraints
5. Validate migration success
```

**Impact**: Existing code continues to work (queries default layer).

### Phase 2: Service Updates

```python
1. Implement LayerManagementService
2. Implement LayerAwareQueryService
3. Update ResourceProcessingService (add layer_id param)
4. Update ScaleOperationsService (copy-then-transform)
5. Update GraphTraverser (add layer filtering)
```

**Impact**: New functionality available, old code still works.

### Phase 3: CLI Commands

```python
1. Add 'atg layer' command group
2. Add layer options to scale commands
3. Add layer option to generate-iac
4. Update scan to create default layer
```

**Impact**: Users can now manage layers via CLI.

## Key Design Decisions

### Decision 1: Property vs Label

**Chosen**: Layer as property (`layer_id`) on nodes
**Alternative**: Layer as label (`:Resource:LayerDefault`)

**Rationale**:
- Properties are more flexible (dynamic filtering)
- Labels would explode (`:Resource:Default:Scaled:Experiment`)
- Easier to query with parameters
- Better index performance

### Decision 2: Single Active Layer

**Chosen**: One active layer at a time (per tenant)
**Alternative**: Explicit layer specification required

**Rationale**:
- Matches git branch model (familiar)
- Reduces cognitive load (default context)
- Backward compatible (existing code works)
- Can always override with explicit --layer flag

### Decision 3: Copy-Then-Transform

**Chosen**: Always copy source layer before modifying
**Alternative**: In-place modifications with undo log

**Rationale**:
- Simpler mental model (layers are immutable after creation)
- Easier to reason about lineage
- No complex undo logic
- Storage is cheap compared to data loss

### Decision 4: Layer Metadata as Separate Nodes

**Chosen**: `:Layer` nodes separate from resources
**Alternative**: Embedded metadata in each resource

**Rationale**:
- Centralized management
- Faster layer listing
- Cleaner separation of concerns
- Easier to track lineage

## Benefits

### 1. Non-Destructive Operations

```bash
# Experiment without fear
atg layer copy default experiment-1
atg scale merge-vnets vnet-1 vnet-2 --target-layer experiment-1
# If bad: atg layer delete experiment-1
# If good: atg layer active experiment-1
```

### 2. A/B Testing

```bash
# Test two approaches
atg layer copy default strategy-a
atg layer copy default strategy-b

# Apply different transformations
atg scale merge-vnets vnet-1 vnet-2 --target-layer strategy-a
atg scale consolidate-vms vm-1 vm-2 --target-layer strategy-b

# Compare results
atg layer diff strategy-a strategy-b
```

### 3. Version History

```bash
# Track evolution
default → scaled-v1 → scaled-v2 → scaled-v3
  ↓
experiment-1 → experiment-2
  ↓
production-final
```

### 4. Rapid Rollback

```bash
# Made a mistake?
atg layer active scaled-v1  # Bad
atg layer active default    # Rollback instantly
```

### 5. Safe Experimentation

```bash
# Sandbox environment
atg layer create sandbox --type experimental
# Experiment freely, delete when done
atg layer delete sandbox --yes
```

## Backward Compatibility

### Existing Code Works Unchanged

```python
# Old code (no layer awareness)
resources = await query_service.find_resources(resource_type="VirtualMachine")

# New implementation
async def find_resources(self, resource_type=None, layer_id=None):
    if layer_id is None:
        # Get active layer (defaults to "default")
        active_layer = await layer_service.get_active_layer()
        layer_id = active_layer.layer_id if active_layer else "default"

    # Filter by layer_id automatically
    query = """
    MATCH (r:Resource {layer_id: $layer_id})
    WHERE r.resource_type = $resource_type
    RETURN r
    """
```

### Migration Path

```
Week 1: Deploy schema migration
        → All existing resources get layer_id='default'
        → No code changes needed yet

Week 2: Deploy service updates
        → New layer operations available
        → Old code still works (queries default layer)

Week 3: Deploy CLI commands
        → Users can manage layers
        → Optional feature, not required

Week 4+: Gradual adoption
        → Users start using layers
        → Old workflows continue working
```

## Performance Considerations

### Query Performance

- **Index overhead**: < 5% (composite index efficient)
- **Query overhead**: < 10% (one additional filter)
- **Storage overhead**: ~2x per additional layer

### Layer Copy Performance

- **Speed**: ~1000 nodes/sec, ~2000 relationships/sec
- **5,584 nodes**: ~6 seconds copy time
- **Memory**: ~100MB per 10K nodes

### Optimization Strategies

1. **Batching**: Copy in chunks of 1000 nodes
2. **Parallel processing**: Copy nodes and relationships concurrently
3. **Index usage**: Always filter by layer_id first in queries
4. **Layer cleanup**: Delete old experimental layers
5. **Archive**: Export to JSON, delete from graph

## Testing Strategy

### Unit Tests

- LayerManagementService methods
- LayerAwareQueryService methods
- Layer isolation guarantees
- Active layer switching

### Integration Tests

- Layer copy preserves structure
- Scale operations create new layers
- Cross-layer relationship prevention
- SCAN_SOURCE_NODE link preservation

### E2E Tests

- Full workflow (scan → copy → scale → compare → activate)
- Layer validation
- IaC generation from multiple layers
- Migration testing

### Performance Tests

- Query performance with layer filtering
- Layer copy performance (various sizes)
- Multiple layer overhead (5, 10, 20 layers)

## Success Metrics

1. **Data Preservation**: No data loss after scale operations
2. **Layer Isolation**: No cross-layer contamination
3. **Performance**: Query overhead < 10%
4. **Compatibility**: All existing code works unchanged
5. **Usability**: Clear CLI, intuitive workflows
6. **Reliability**: Layer validation catches issues

## Risk Mitigation

### Risk 1: Performance Degradation

**Mitigation**:
- Comprehensive benchmarking
- Index optimization
- Query pattern analysis
- Layer cleanup automation

### Risk 2: Cross-Layer Contamination

**Mitigation**:
- Strict validation in service layer
- Automated integrity checks
- Constraint enforcement at database level

### Risk 3: User Confusion

**Mitigation**:
- Clear documentation
- Intuitive CLI commands
- Smart defaults (active layer concept)
- Helpful error messages

### Risk 4: Migration Issues

**Mitigation**:
- Thorough migration testing
- Idempotent migration script
- Rollback procedure documented
- Database backups before migration

## Future Enhancements

### Phase 4: Advanced Features (Post-MVP)

1. **Layer Branching**: Git-like branches and merging
2. **Layer Templates**: Predefined layer configurations
3. **Multi-Tenant Active Layers**: One active layer per tenant
4. **Layer Access Control**: Per-layer permissions
5. **Automated Cleanup**: Old layer garbage collection
6. **Layer Diffs Visualization**: Graphical comparison tool
7. **Layer Snapshots**: Automatic pre-operation snapshots
8. **Layer Tagging**: Semantic versioning (v1.0, v2.0)

## Implementation Timeline

**Total Estimated Time: 3-4 days**

- **Day 1**: Schema migration + core services (50%)
- **Day 2**: Service enhancements + integration (30%)
- **Day 3**: CLI commands + testing (15%)
- **Day 4**: Documentation + validation (5%)

## Conclusion

This multi-layer architecture transforms Azure Tenant Grapher from a single-projection system into a powerful experimentation platform. By maintaining immutable Original data and supporting multiple coexisting abstracted projections, users can explore infrastructure transformations without fear of data loss.

**Key Principles:**
- **Simplicity**: Layers are just nodes with a layer_id property
- **Safety**: Original graph never modified
- **Clarity**: Active layer concept is intuitive
- **Compatibility**: Existing code works unchanged

**Ready for Implementation**: All specifications complete, interfaces defined, CLI designed, migration planned. The builder agent can now proceed with autonomous implementation.

---

## Quick Reference

### Most Important Files

1. **Architecture**: /home/azureuser/src/atg/docs/architecture/MULTI_LAYER_GRAPH_ARCHITECTURE.md
2. **Implementation Checklist**: /home/azureuser/src/atg/docs/architecture/LAYER_IMPLEMENTATION_CHECKLIST.md
3. **Service Interfaces**: /home/azureuser/src/atg/docs/architecture/LAYER_SERVICE_INTERFACES.md
4. **CLI Specification**: /home/azureuser/src/atg/docs/architecture/LAYER_CLI_SPECIFICATION.md
5. **This Summary**: /home/azureuser/src/atg/docs/architecture/LAYER_ARCHITECTURE_SUMMARY.md

### Start Implementation Here

```bash
# 1. Read the architecture
cat /home/azureuser/src/atg/docs/architecture/MULTI_LAYER_GRAPH_ARCHITECTURE.md

# 2. Follow the checklist
cat /home/azureuser/src/atg/docs/architecture/LAYER_IMPLEMENTATION_CHECKLIST.md

# 3. Implement services per interfaces
cat /home/azureuser/src/atg/docs/architecture/LAYER_SERVICE_INTERFACES.md

# 4. Build CLI per specification
cat /home/azureuser/src/atg/docs/architecture/LAYER_CLI_SPECIFICATION.md
```

**Estimated completion: 3-4 days of focused implementation**

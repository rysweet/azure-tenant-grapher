# SCAN_SOURCE_NODE Relationships in Layer Operations

Arrr! This document explains the critical SCAN_SOURCE_NODE relationships that connect abstracted resources to their original Azure IDs, and why layer operations preserve 'em.

## Overview

The dual-graph architecture stores every Azure resource as **two nodes**:

1. **Abstracted nodes** (`:Resource`) - Deterministic hash-based IDs fer cross-tenant deployment
2. **Original nodes** (`:Resource:Original`) - Real Azure IDs from the scanned tenant

These nodes be connected by `SCAN_SOURCE_NODE` relationships:

```cypher
(abstracted:Resource)-[:SCAN_SOURCE_NODE]->(original:Resource:Original)
```

## Why SCAN_SOURCE_NODE Matters

### Original Azure IDs Are Essential

When generatin' Infrastructure-as-Code (IaC), the system needs **original Azure resource IDs** to:

- **Smart Import Comparison**: Compare generated IaC against existing tenant resources (Bug #115)
- **Same-Tenant Deployments**: Use original principal IDs fer role assignments (Bug #96)
- **Validation**: Verify generated resources match source topology
- **Traceability**: Track which abstracted resource came from which Azure resource

### The Critical Query Pattern

IaC generation relies on this query pattern:

```cypher
MATCH (r:Resource)
WHERE r.layer_id = $layer_id
OPTIONAL MATCH (r)-[:SCAN_SOURCE_NODE]->(orig:Resource:Original)
RETURN r, orig.id as original_id, orig as original_properties
```

**Without SCAN_SOURCE_NODE in layers**, this query returns:
- ✅ Abstracted resources (`r`)
- ❌ NULL fer `original_id` (causes 900+ false positives!)
- ❌ NULL fer `original_properties`

**With SCAN_SOURCE_NODE preserved**, this query returns:
- ✅ Abstracted resources (`r`)
- ✅ Original Azure IDs (`original_id`)
- ✅ Original properties (`original_properties`)

## Layer Operations Behavior

### Copy Layer Operation

When copyin' a layer, SCAN_SOURCE_NODE relationships **are preserved**:

```python
# From src/services/layer/export.py copy_layer()
session.run("""
    MATCH (r1:Resource)-[rel]->(r2:Resource)
    WHERE NOT r1:Original AND NOT r2:Original
      AND r1.layer_id = $source_layer_id
      AND r2.layer_id = $source_layer_id
    -- SCAN_SOURCE_NODE relationships are INCLUDED
    WITH r1, r2, rel
    MATCH (new1:Resource {id: r1.id, layer_id: $target_layer_id})
    MATCH (new2:Resource {id: r2.id, layer_id: $target_layer_id})
    WITH new1, new2, type(rel) as rel_type, properties(rel) as rel_props
    CALL apoc.create.relationship(new1, rel_type, rel_props, new2) YIELD rel as new_rel
    RETURN count(new_rel)
""")
```

**Key behavior**:
- The query matches **all relationships** between Resource nodes
- **SCAN_SOURCE_NODE is included** because it connects abstracted nodes to Original nodes
- This enables IaC generation on copied layers

### Archive Layer Operation

When archiving a layer to JSON, SCAN_SOURCE_NODE relationships **are preserved** in the archive format:

```python
# From src/services/layer/export.py archive_layer()
rel_result = session.run("""
    MATCH (r1:Resource)-[rel]->(r2:Resource)
    WHERE NOT r1:Original AND NOT r2:Original
      AND r1.layer_id = $layer_id
      AND r2.layer_id = $layer_id
    -- SCAN_SOURCE_NODE relationships are INCLUDED
    RETURN r1.id as source, r2.id as target,
           type(rel) as type, properties(rel) as props
""")
```

**Archive format** (JSON):
```json
{
  "metadata": {...},
  "nodes": [...],
  "relationships": [
    {
      "source": "vm-abc123",
      "target": "/subscriptions/.../virtualMachines/my-vm",
      "type": "SCAN_SOURCE_NODE",
      "properties": {}
    }
  ]
}
```

### Restore Layer Operation

When restorin' a layer from archive, **all relationships** (including SCAN_SOURCE_NODE) are restored:

```python
# From src/services/layer/export.py restore_layer()
for rel in relationships:
    session.run("""
        MATCH (r1:Resource {id: $source, layer_id: $layer_id})
        MATCH (r2:Resource {id: $target, layer_id: $layer_id})
        WITH r1, r2
        CALL apoc.create.relationship(r1, $rel_type, $props, r2) YIELD rel
        RETURN rel
    """)
```

## The Bug That Was Fixed

### Problem (Before Fix)

Lines 166 and 255 of `export.py` had this filter:

```cypher
AND type(rel) <> 'SCAN_SOURCE_NODE'  -- ❌ EXCLUDED!
```

This caused:
- **Layer copies**: Missing SCAN_SOURCE_NODE → IaC generation queries return NULL original_ids
- **Layer archives**: Missing SCAN_SOURCE_NODE → Restored layers lack original ID mappings
- **Smart import**: 900+ false positives because comparison couldn't find original IDs

### Solution (After Fix)

Removed the exclusion filter from lines 166 and 255:

```cypher
-- No exclusion! SCAN_SOURCE_NODE is preserved
```

**Impact**:
- ✅ IaC generation finds original Azure IDs reliably
- ✅ Smart import comparison works correctly
- ✅ Same-tenant deployments use correct principal IDs
- ✅ Layer operations maintain full traceability

## Archive Format Versioning

Archives now include version metadata fer backward compatibility:

```json
{
  "version": "2.0",
  "metadata": {...},
  "nodes": [...],
  "relationships": [...]
}
```

**Version compatibility**:
- **v1.0 archives** (old): Missing SCAN_SOURCE_NODE relationships
- **v2.0 archives** (new): Include SCAN_SOURCE_NODE relationships

When restorin' v1.0 archives:
- System detects missing version field
- Logs warning: "Archive may be missing SCAN_SOURCE_NODE relationships"
- Restores what's available (graceful degradation)

## Best Practices

### Working with Layer Exports

1. **Always verify SCAN_SOURCE_NODE presence**:
   ```cypher
   MATCH (r:Resource {layer_id: $layer_id})-[:SCAN_SOURCE_NODE]->(orig:Resource:Original)
   RETURN count(r) as abstracted_with_source_nodes
   ```

2. **Check archive version** before assuming original_id availability:
   ```python
   with open(archive_path) as f:
       archive = json.load(f)
       version = archive.get("version", "1.0")
       if version == "1.0":
           logger.warning("Old archive format - may lack SCAN_SOURCE_NODE")
   ```

3. **Test IaC generation** after layer copy/restore:
   ```bash
   # Verify original IDs are accessible
   uv run python -m src.iac.cli export \
     --layer-id copied-layer \
     --validate-original-ids
   ```

### Troubleshooting Missing Original IDs

If IaC generation returns NULL fer `original_id`:

1. **Check SCAN_SOURCE_NODE relationships exist**:
   ```cypher
   MATCH (r:Resource {layer_id: $layer_id})
   OPTIONAL MATCH (r)-[:SCAN_SOURCE_NODE]->(orig:Resource:Original)
   WHERE orig IS NULL
   RETURN r.id as missing_source_node
   LIMIT 10
   ```

2. **Verify layer was copied with current code** (post-fix):
   ```bash
   git log --oneline src/services/layer/export.py
   # Should show commit removing SCAN_SOURCE_NODE exclusion
   ```

3. **Re-copy the layer** using fixed code if needed:
   ```python
   await layer_service.copy_layer(
       source_layer_id="original-scan",
       target_layer_id="fixed-copy",
       name="Re-copied with SCAN_SOURCE_NODE",
       description="Includes original ID mappings"
   )
   ```

## Implementation Details

### Node Types in Queries

Layer operations query patterns:

```cypher
-- ✅ CORRECT: Matches abstracted nodes, includes SCAN_SOURCE_NODE
MATCH (r:Resource)
WHERE NOT r:Original AND r.layer_id = $layer_id

-- ❌ WRONG: Would miss abstracted nodes
MATCH (r:Resource:Original)
WHERE r.layer_id = $layer_id

-- ✅ CORRECT: Optional match to Original via SCAN_SOURCE_NODE
OPTIONAL MATCH (r)-[:SCAN_SOURCE_NODE]->(orig:Resource:Original)
```

### Why :Original Nodes Stay in Base Graph

Original nodes (`Resource:Original`) **are NOT copied** to layers because:

1. **Original nodes are global**: Single source of truth fer real Azure IDs
2. **SCAN_SOURCE_NODE crosses layer boundary**: Abstracted nodes in layers reference Original nodes in base graph
3. **Storage efficiency**: No duplication of Original nodes across layers
4. **Update once, reference everywhere**: Original node updates don't require layer synchronization

### Cross-Layer Relationship Pattern

```
Base Graph:
  (original:Resource:Original {id: "/subscriptions/.../my-vm"})

Layer "experimental-01":
  (abstracted:Resource {id: "vm-abc123", layer_id: "experimental-01"})
    -[:SCAN_SOURCE_NODE]->
  (original:Resource:Original {id: "/subscriptions/.../my-vm"})
```

**Key insight**: SCAN_SOURCE_NODE is the **only relationship type** that crosses the layer boundary between abstracted nodes (in layer) and Original nodes (in base graph).

## Related Documentation

- [Dual-Graph Architecture](../DUAL_GRAPH_SCHEMA.md) - Complete dual-graph design
- [Resource Processing](../../src/services/resource_processing/README.md) - How SCAN_SOURCE_NODE is created
- [IaC Generation](../../src/iac/README.md) - How SCAN_SOURCE_NODE is queried
- [Smart Import Bug Fixes](../smart-import-bug-fixes.md) - Impact on deployment validation

## References

- **Bug #115**: Smart import false positives (900+ errors)
- **Bug #116**: Heuristic ID cleanup fer relationship queries
- **Bug #117**: Layer export excluding SCAN_SOURCE_NODE
- **Issue #570**: Preserve SCAN_SOURCE_NODE in layer operations

---

**Last Updated**: 2025-12-03
**Status**: ✅ Fix deployed
**Impact**: Resolves deployment blocker, enables reliable IaC generation

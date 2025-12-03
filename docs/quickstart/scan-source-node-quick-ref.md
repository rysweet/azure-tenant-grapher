# SCAN_SOURCE_NODE Quick Reference

Quick reference fer developers workin' with SCAN_SOURCE_NODE relationships in the dual-graph architecture.

## TL;DR

**SCAN_SOURCE_NODE connects abstracted resources to their original Azure IDs. NEVER filter this relationship out in layer operations.**

```cypher
// ✅ CORRECT: Include SCAN_SOURCE_NODE
MATCH (r:Resource)-[rel]->(target)
WHERE r.layer_id = $layer_id

// ❌ WRONG: Never exclude SCAN_SOURCE_NODE!
MATCH (r:Resource)-[rel]->(target)
WHERE r.layer_id = $layer_id
  AND type(rel) <> 'SCAN_SOURCE_NODE'  // DON'T DO THIS!
```

## Essential Queries

### Query Resources with Original IDs

```cypher
MATCH (r:Resource)
WHERE r.layer_id = $layer_id
OPTIONAL MATCH (r)-[:SCAN_SOURCE_NODE]->(orig:Resource:Original)
RETURN r.id as abstracted_id,
       r.type as resource_type,
       orig.id as original_azure_id,
       orig.properties as original_properties;
```

### Count Resources with/without SCAN_SOURCE_NODE

```cypher
MATCH (r:Resource)
WHERE r.layer_id = $layer_id
  AND NOT r:Original
WITH count(r) as total
MATCH (r:Resource)-[:SCAN_SOURCE_NODE]->(orig:Resource:Original)
WHERE r.layer_id = $layer_id
RETURN total as total_resources,
       count(r) as with_scan_source_node,
       total - count(r) as missing_scan_source_node;
```

### Verify Layer Health

```cypher
// Check if ALL abstracted resources have SCAN_SOURCE_NODE
MATCH (r:Resource)
WHERE r.layer_id = $layer_id
  AND NOT r:Original
  AND NOT EXISTS {
    MATCH (r)-[:SCAN_SOURCE_NODE]->(:Resource:Original)
  }
RETURN count(r) as resources_missing_scan_source_node;

// Should return 0 for healthy layers!
```

## Python API Examples

### Create Resources with SCAN_SOURCE_NODE

```python
from src.services.resource_processing import NodeManager

node_manager = NodeManager(session_manager, tenant_id="tenant-123")

# Upsert resource creates BOTH abstracted and Original nodes
# with SCAN_SOURCE_NODE relationship automatically
resource_data = {
    "id": "/subscriptions/sub-123/resourceGroups/rg-1/providers/Microsoft.Compute/virtualMachines/vm-1",
    "type": "Microsoft.Compute/virtualMachines",
    "name": "vm-1",
    "properties": {...}
}

node_manager.upsert_resource(
    resource_data=resource_data,
    processing_status="completed"
)

# Result in Neo4j:
# (abstracted:Resource {id: "vm-abc123"})-[:SCAN_SOURCE_NODE]->
# (original:Resource:Original {id: "/subscriptions/.../vm-1"})
```

### Query Original IDs from IaC Generation

```python
from src.iac.traverser import GraphTraverser

traverser = GraphTraverser(driver)

# Traverse returns resources WITH original_id populated
graph = await traverser.traverse(
    filter_cypher="WHERE r.layer_id = $layer_id",
    use_original_ids=False,  # Query abstracted nodes
    parameters={"layer_id": "layer-01"}
)

for resource in graph.resources:
    print(f"Abstracted: {resource['id']}")
    print(f"Original: {resource.get('original_id')}")  # From SCAN_SOURCE_NODE!
    print(f"Original props: {resource.get('original_properties')}")
```

### Check Layer for SCAN_SOURCE_NODE

```python
from neo4j import GraphDatabase

with driver.session() as session:
    result = session.run("""
        MATCH (r:Resource)
        WHERE r.layer_id = $layer_id AND NOT r:Original
        WITH count(r) as total
        MATCH (r:Resource)-[:SCAN_SOURCE_NODE]->(orig:Resource:Original)
        WHERE r.layer_id = $layer_id
        RETURN total, count(r) as with_scan_source
    """, layer_id="layer-01")

    record = result.single()
    total = record["total"]
    with_scan = record["with_scan_source"]

    if with_scan < total:
        print(f"WARNING: {total - with_scan} resources missing SCAN_SOURCE_NODE!")
    else:
        print(f"✅ All {total} resources have SCAN_SOURCE_NODE")
```

## Common Mistakes

### ❌ Filtering Out SCAN_SOURCE_NODE

```python
# DON'T DO THIS!
query = """
MATCH (r1:Resource)-[rel]->(r2:Resource)
WHERE r1.layer_id = $layer_id
  AND type(rel) <> 'SCAN_SOURCE_NODE'  // ❌ Breaks IaC generation!
"""
```

**Impact**: IaC generation can't find original Azure IDs → 900+ false positives in smart import.

### ❌ Assuming All Relationships Stay in Layer

```python
# WRONG ASSUMPTION
query = """
MATCH (r1:Resource)-[rel]->(r2:Resource)
WHERE r1.layer_id = $layer_id
  AND r2.layer_id = $layer_id  // ❌ SCAN_SOURCE_NODE crosses boundary!
"""
```

**Reality**: SCAN_SOURCE_NODE connects abstracted nodes (in layer) to Original nodes (in base graph). The target node does NOT have the layer_id.

### ❌ Copying Only Abstracted Nodes

```python
# INCOMPLETE
query = """
MATCH (r:Resource)
WHERE r.layer_id = $source_layer
CREATE (new:Resource)
SET new = properties(r), new.layer_id = $target_layer
// ❌ Forgot to copy SCAN_SOURCE_NODE relationships!
"""
```

**Fix**: Always copy relationships AFTER copying nodes:

```python
# CORRECT
# Step 1: Copy nodes
query1 = """
MATCH (r:Resource)
WHERE r.layer_id = $source_layer
CREATE (new:Resource)
SET new = properties(r), new.layer_id = $target_layer
"""

# Step 2: Copy relationships (including SCAN_SOURCE_NODE)
query2 = """
MATCH (r1:Resource)-[rel]->(r2:Resource)
WHERE r1.layer_id = $source_layer
  AND r2.layer_id = $source_layer
WITH r1, r2, type(rel) as rel_type, properties(rel) as rel_props
MATCH (new1:Resource {id: r1.id, layer_id: $target_layer})
MATCH (new2:Resource {id: r2.id, layer_id: $target_layer})
CALL apoc.create.relationship(new1, rel_type, rel_props, new2) YIELD rel
RETURN count(rel)
"""
```

## Debugging Checklist

When IaC generation or smart import fails:

- [ ] **Verify SCAN_SOURCE_NODE exists**
  ```cypher
  MATCH (r:Resource {layer_id: $layer_id})-[:SCAN_SOURCE_NODE]->(orig)
  RETURN count(r);
  ```

- [ ] **Check Original nodes exist in base graph**
  ```cypher
  MATCH (orig:Resource:Original)
  RETURN count(orig);
  ```

- [ ] **Verify layer was created/copied with current code** (post-Bug #117 fix)
  ```bash
  git log --oneline src/services/layer/export.py
  # Should see commit removing SCAN_SOURCE_NODE exclusion
  ```

- [ ] **Test IaC query pattern**
  ```cypher
  MATCH (r:Resource)
  WHERE r.layer_id = $layer_id
  OPTIONAL MATCH (r)-[:SCAN_SOURCE_NODE]->(orig:Resource:Original)
  RETURN r.id, orig.id as original_id
  LIMIT 10;
  // original_id should NOT be NULL!
  ```

## Key Takeaways

1. **SCAN_SOURCE_NODE is special** - Only relationship type that crosses layer boundary
2. **Never filter it out** - Always include in layer copy/archive operations
3. **IaC depends on it** - Smart import needs original Azure IDs fer comparison
4. **Verify after migration** - Check count matches expected resources

## Related Documentation

- [Full SCAN_SOURCE_NODE Documentation](../architecture/scan-source-node-relationships.md)
- [Migration Guide](../guides/scan-source-node-migration.md)
- [Dual-Graph Architecture](../DUAL_GRAPH_SCHEMA.md)

---

**Last Updated**: 2025-12-03
**For**: Developers workin' with layer operations and IaC generation

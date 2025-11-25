# Layer-Aware Query Patterns

This document provides Cypher query patterns for working with the multi-layer graph architecture.

## Core Principles

1. **Always filter by layer_id** - First filter in every query
2. **Never cross layer boundaries** - Relationships stay within layer
3. **SCAN_SOURCE_NODE is special** - Can cross from abstracted to Original
4. **Use active layer by default** - Resolve at application level

## Query Pattern Templates

### Pattern 1: Get All Resources in Layer

```cypher
// Basic query
MATCH (r:Resource {layer_id: $layer_id})
RETURN r

// With type filter
MATCH (r:Resource {layer_id: $layer_id})
WHERE r.resource_type = $resource_type
RETURN r

// With multiple filters
MATCH (r:Resource {layer_id: $layer_id})
WHERE r.resource_type = $resource_type
  AND r.location = $location
RETURN r
ORDER BY r.name

// Count resources
MATCH (r:Resource {layer_id: $layer_id})
RETURN count(r) as total
```

**Performance**: Use composite index on (resource_type, layer_id).

### Pattern 2: Get Specific Resource

```cypher
// By resource ID (abstracted ID)
MATCH (r:Resource {id: $resource_id, layer_id: $layer_id})
RETURN r

// By name (less efficient)
MATCH (r:Resource {layer_id: $layer_id})
WHERE r.name = $name
RETURN r

// By Azure ID (requires traversal to Original)
MATCH (r:Resource {layer_id: $layer_id})
      -[:SCAN_SOURCE_NODE]->
      (orig:Original {id: $azure_id})
RETURN r
```

### Pattern 3: Traverse Relationships Within Layer

```cypher
// One hop (outgoing)
MATCH (start:Resource {id: $start_id, layer_id: $layer_id})
      -[rel]->
      (target:Resource)
WHERE target.layer_id = $layer_id
RETURN start, rel, target

// Specific relationship type
MATCH (start:Resource {id: $start_id, layer_id: $layer_id})
      -[rel:CONTAINS]->
      (target:Resource)
WHERE target.layer_id = $layer_id
RETURN target

// Multi-hop (path)
MATCH path = (start:Resource {id: $start_id, layer_id: $layer_id})
             -[*1..3]->
             (end:Resource)
WHERE end.layer_id = $layer_id
  AND all(node IN nodes(path) WHERE node.layer_id = $layer_id)
RETURN path

// Bidirectional
MATCH (r1:Resource {id: $resource_id, layer_id: $layer_id})
      -[rel]-
      (r2:Resource {layer_id: $layer_id})
RETURN r1, rel, r2
```

**Critical**: Always verify target nodes are in same layer.

### Pattern 4: Get Original Node for Resource

```cypher
// Single resource
MATCH (r:Resource {id: $resource_id, layer_id: $layer_id})
      -[:SCAN_SOURCE_NODE]->
      (orig:Original)
RETURN orig

// Batch lookup
MATCH (r:Resource {layer_id: $layer_id})
      -[:SCAN_SOURCE_NODE]->
      (orig:Original)
WHERE r.id IN $resource_ids
RETURN r.id as abstracted_id, orig.id as azure_id

// All resources with Original IDs
MATCH (r:Resource {layer_id: $layer_id})
      -[:SCAN_SOURCE_NODE]->
      (orig:Original)
RETURN r, orig
```

### Pattern 5: Find Resources Without Original Links

```cypher
// Orphaned abstracted nodes
MATCH (r:Resource {layer_id: $layer_id})
WHERE NOT (r)-[:SCAN_SOURCE_NODE]->(:Original)
RETURN r

// Count orphans
MATCH (r:Resource {layer_id: $layer_id})
WHERE NOT (r)-[:SCAN_SOURCE_NODE]->(:Original)
RETURN count(r) as orphan_count
```

## Layer Management Queries

### List All Layers

```cypher
// All layers with stats
MATCH (l:Layer)
RETURN l.layer_id as layer_id,
       l.name as name,
       l.is_active as active,
       l.node_count as nodes,
       l.created_at as created
ORDER BY l.created_at DESC

// Active layer only
MATCH (l:Layer {is_active: true})
RETURN l

// By tenant
MATCH (l:Layer {tenant_id: $tenant_id})
RETURN l
ORDER BY l.created_at DESC

// By type
MATCH (l:Layer)
WHERE l.metadata.layer_type = $layer_type
RETURN l
```

### Get Layer Lineage

```cypher
// Parents (ancestors)
MATCH path = (l:Layer {layer_id: $layer_id})
             -[:DERIVED_FROM*]->
             (ancestor:Layer)
RETURN path

// Children (descendants)
MATCH path = (descendant:Layer)
             -[:DERIVED_FROM*]->
             (l:Layer {layer_id: $layer_id})
RETURN path

// Immediate parent only
MATCH (l:Layer {layer_id: $layer_id})
      -[:DERIVED_FROM]->
      (parent:Layer)
RETURN parent

// Full lineage tree
MATCH (root:Layer {is_baseline: true})
OPTIONAL MATCH path = (root)<-[:DERIVED_FROM*]-(descendant:Layer)
RETURN root, collect(path) as lineage
```

### Set Active Layer (Atomic Transaction)

```cypher
// Deactivate all, activate one (transaction required)
MATCH (l:Layer)
SET l.is_active = false;

MATCH (l:Layer {layer_id: $layer_id})
SET l.is_active = true,
    l.updated_at = datetime()
RETURN l;
```

**Important**: Use transaction to ensure atomicity.

## Layer Operations Queries

### Copy Layer (Batched)

```cypher
// Step 1: Create target layer metadata
CREATE (target:Layer {
  layer_id: $target_layer_id,
  name: $name,
  description: $description,
  created_at: datetime(),
  created_by: 'copy',
  is_active: false,
  node_count: 0,
  relationship_count: 0
})

// Step 2: Link to parent
MATCH (source:Layer {layer_id: $source_layer_id}),
      (target:Layer {layer_id: $target_layer_id})
CREATE (target)-[:DERIVED_FROM {
  operation: 'copy',
  created_at: datetime()
}]->(source)

// Step 3: Copy nodes (batched)
MATCH (r:Resource {layer_id: $source_layer_id})
WITH r
SKIP $offset
LIMIT $batch_size
CREATE (copy:Resource)
SET copy = r,
    copy.layer_id = $target_layer_id,
    copy.layer_created_at = datetime()

// Step 4: Copy SCAN_SOURCE_NODE links
MATCH (r:Resource {layer_id: $source_layer_id})
      -[:SCAN_SOURCE_NODE]->
      (orig:Original)
WITH r, orig
SKIP $offset
LIMIT $batch_size
MATCH (copy:Resource {id: r.id, layer_id: $target_layer_id})
CREATE (copy)-[:SCAN_SOURCE_NODE]->(orig)

// Step 5: Copy relationships (batched)
MATCH (r1:Resource {layer_id: $source_layer_id})
      -[rel]->
      (r2:Resource {layer_id: $source_layer_id})
WITH r1, rel, r2
SKIP $offset
LIMIT $batch_size
MATCH (copy1:Resource {id: r1.id, layer_id: $target_layer_id}),
      (copy2:Resource {id: r2.id, layer_id: $target_layer_id})
CREATE (copy1)-[rel_copy:rel]->(copy2)
SET rel_copy = properties(rel)

// Step 6: Update counts
MATCH (l:Layer {layer_id: $target_layer_id})
WITH l
MATCH (r:Resource {layer_id: $target_layer_id})
WITH l, count(r) as node_count
MATCH (r1:Resource {layer_id: $target_layer_id})
      -[rel]->
      (r2:Resource {layer_id: $target_layer_id})
WITH l, node_count, count(rel) as rel_count
SET l.node_count = node_count,
    l.relationship_count = rel_count,
    l.updated_at = datetime()
```

### Compare Layers

```cypher
// Nodes added (in B, not in A)
MATCH (b:Resource {layer_id: $layer_b_id})
WHERE NOT EXISTS {
  MATCH (a:Resource {id: b.id, layer_id: $layer_a_id})
}
RETURN b.id as added_node_id, b.resource_type

// Nodes removed (in A, not in B)
MATCH (a:Resource {layer_id: $layer_a_id})
WHERE NOT EXISTS {
  MATCH (b:Resource {id: a.id, layer_id: $layer_b_id})
}
RETURN a.id as removed_node_id, a.resource_type

// Nodes modified (same ID, different properties)
MATCH (a:Resource {layer_id: $layer_a_id}),
      (b:Resource {id: a.id, layer_id: $layer_b_id})
WHERE properties(a) <> properties(b)
RETURN a.id as modified_node_id,
       properties(a) as layer_a_props,
       properties(b) as layer_b_props

// Summary statistics
MATCH (a:Resource {layer_id: $layer_a_id})
WITH count(a) as count_a
MATCH (b:Resource {layer_id: $layer_b_id})
WITH count_a, count(b) as count_b
MATCH (common:Resource {layer_id: $layer_a_id})
WHERE EXISTS {
  MATCH (b:Resource {id: common.id, layer_id: $layer_b_id})
}
WITH count_a, count_b, count(common) as count_common
RETURN count_a as layer_a_nodes,
       count_b as layer_b_nodes,
       count_common as common_nodes,
       count_b - count_common as added,
       count_a - count_common as removed
```

### Delete Layer

```cypher
// Step 1: Delete relationships
MATCH (r1:Resource {layer_id: $layer_id})
      -[rel]->
      (r2:Resource {layer_id: $layer_id})
DELETE rel

// Step 2: Delete SCAN_SOURCE_NODE links
MATCH (r:Resource {layer_id: $layer_id})
      -[rel:SCAN_SOURCE_NODE]->
      (orig:Original)
DELETE rel

// Step 3: Delete nodes
MATCH (r:Resource {layer_id: $layer_id})
DELETE r

// Step 4: Delete layer metadata
MATCH (l:Layer {layer_id: $layer_id})
DETACH DELETE l
```

**Warning**: This is destructive! Check protection flags first.

## Validation Queries

### Check Layer Integrity

```cypher
// Check 1: All resources have SCAN_SOURCE_NODE
MATCH (r:Resource {layer_id: $layer_id})
WHERE NOT (r)-[:SCAN_SOURCE_NODE]->(:Original)
RETURN count(r) as missing_scan_source_node

// Check 2: No cross-layer relationships
MATCH (r1:Resource {layer_id: $layer_id})
      -[rel]->
      (r2:Resource)
WHERE r2.layer_id <> $layer_id
RETURN type(rel) as relationship_type,
       r1.id as source,
       r2.layer_id as target_layer,
       r2.id as target

// Check 3: No orphaned relationships
MATCH (r1:Resource {layer_id: $layer_id})
      -[rel]->
      (r2)
WHERE NOT r2:Resource OR r2.layer_id <> $layer_id
RETURN type(rel) as relationship_type,
       r1.id as source,
       r2

// Check 4: Node count accuracy
MATCH (l:Layer {layer_id: $layer_id})
WITH l.node_count as expected
MATCH (r:Resource {layer_id: $layer_id})
WITH expected, count(r) as actual
RETURN expected, actual, expected - actual as difference

// Check 5: SCAN_SOURCE_NODE targets exist
MATCH (r:Resource {layer_id: $layer_id})
      -[:SCAN_SOURCE_NODE]->
      (orig)
WHERE NOT orig:Original
RETURN r.id as resource_id, orig

// Check 6: No duplicate (id, layer_id)
MATCH (r:Resource {layer_id: $layer_id})
WITH r.id as resource_id, count(*) as count
WHERE count > 1
RETURN resource_id, count
```

### Find Common Issues

```cypher
// Orphaned abstracted nodes
MATCH (r:Resource)
WHERE r.layer_id IS NULL
RETURN r.id, r.resource_type

// Resources in non-existent layers
MATCH (r:Resource)
WHERE NOT EXISTS {
  MATCH (l:Layer {layer_id: r.layer_id})
}
RETURN r.layer_id, count(r) as orphaned_count

// Multiple active layers (error state)
MATCH (l:Layer {is_active: true})
WITH count(l) as active_count
WHERE active_count > 1
MATCH (l:Layer {is_active: true})
RETURN l.layer_id, l.name

// Layers with zero nodes
MATCH (l:Layer)
WHERE l.node_count = 0 OR NOT EXISTS {
  MATCH (r:Resource {layer_id: l.layer_id})
}
RETURN l.layer_id, l.name, l.created_at
```

## Performance Optimization Patterns

### Use Index Hints

```cypher
// Force index usage
MATCH (r:Resource)
USING INDEX r:Resource(layer_id)
WHERE r.layer_id = $layer_id
  AND r.resource_type = $resource_type
RETURN r
```

### Batch Operations

```cypher
// Instead of N queries, use one with UNWIND
UNWIND $resource_ids as rid
MATCH (r:Resource {id: rid, layer_id: $layer_id})
RETURN r
```

### Limit Early

```cypher
// Good: Limit before expensive operations
MATCH (r:Resource {layer_id: $layer_id})
WHERE r.resource_type = 'VirtualMachine'
WITH r
LIMIT 100
MATCH (r)-[rel]->(other)
RETURN r, rel, other

// Bad: Limit after expensive operations
MATCH (r:Resource {layer_id: $layer_id})
WHERE r.resource_type = 'VirtualMachine'
MATCH (r)-[rel]->(other)
WITH r, rel, other
LIMIT 100
RETURN r, rel, other
```

### Count Optimization

```cypher
// Fast: Use stored count
MATCH (l:Layer {layer_id: $layer_id})
RETURN l.node_count

// Slower: Recount every time
MATCH (r:Resource {layer_id: $layer_id})
RETURN count(r)
```

## Common Query Patterns in Code

### Python AsyncIO Pattern

```python
from neo4j import AsyncGraphDatabase

async def get_resources_in_layer(session, layer_id, resource_type=None):
    """Get resources from specific layer."""
    query = """
    MATCH (r:Resource {layer_id: $layer_id})
    WHERE $resource_type IS NULL OR r.resource_type = $resource_type
    RETURN r
    """

    result = await session.run(
        query,
        layer_id=layer_id,
        resource_type=resource_type
    )

    resources = []
    async for record in result:
        resources.append(dict(record["r"]))

    return resources


async def traverse_relationships(session, start_id, layer_id, rel_type, depth=1):
    """Traverse relationships within layer."""
    query = f"""
    MATCH (start:Resource {{id: $start_id, layer_id: $layer_id}})
    MATCH path = (start)-[:{rel_type}*1..{depth}]->(target:Resource)
    WHERE target.layer_id = $layer_id
      AND all(node IN nodes(path) WHERE node.layer_id = $layer_id)
    RETURN target
    """

    result = await session.run(
        query,
        start_id=start_id,
        layer_id=layer_id
    )

    targets = []
    async for record in result:
        targets.append(dict(record["target"]))

    return targets


async def copy_layer_batch(session, source_layer_id, target_layer_id, offset, batch_size):
    """Copy nodes in batches."""
    query = """
    MATCH (r:Resource {layer_id: $source_layer_id})
    WITH r
    SKIP $offset
    LIMIT $batch_size
    CREATE (copy:Resource)
    SET copy = r,
        copy.layer_id = $target_layer_id,
        copy.layer_created_at = datetime()
    RETURN count(copy) as copied
    """

    result = await session.run(
        query,
        source_layer_id=source_layer_id,
        target_layer_id=target_layer_id,
        offset=offset,
        batch_size=batch_size
    )

    record = await result.single()
    return record["copied"]
```

### Transaction Pattern for Atomic Operations

```python
async def set_active_layer(driver, layer_id):
    """Atomically switch active layer."""
    async with driver.session() as session:
        async with session.begin_transaction() as tx:
            # Deactivate all
            await tx.run("""
                MATCH (l:Layer)
                SET l.is_active = false
            """)

            # Activate target
            result = await tx.run("""
                MATCH (l:Layer {layer_id: $layer_id})
                SET l.is_active = true,
                    l.updated_at = datetime()
                RETURN l
            """, layer_id=layer_id)

            record = await result.single()
            if not record:
                await tx.rollback()
                raise LayerNotFoundError(layer_id)

            await tx.commit()
            return dict(record["l"])
```

## Migration Queries

### Add Layer Support to Existing Graph

```cypher
// Step 1: Add layer_id to existing resources
MATCH (r:Resource)
WHERE NOT r:Original AND r.layer_id IS NULL
SET r.layer_id = 'default',
    r.layer_created_at = datetime()

// Step 2: Create default layer
MERGE (l:Layer {layer_id: 'default'})
SET l.name = 'Default Baseline',
    l.description = '1:1 abstraction from initial scan',
    l.created_at = datetime(),
    l.created_by = 'migration',
    l.is_active = true,
    l.is_baseline = true

// Step 3: Count nodes and relationships
MATCH (l:Layer {layer_id: 'default'})
WITH l
MATCH (r:Resource {layer_id: 'default'})
WITH l, count(r) as node_count
MATCH (r1:Resource {layer_id: 'default'})
      -[rel]->
      (r2:Resource {layer_id: 'default'})
WITH l, node_count, count(rel) as rel_count
SET l.node_count = node_count,
    l.relationship_count = rel_count

// Step 4: Set tenant_id from resources
MATCH (l:Layer {layer_id: 'default'})
WITH l
MATCH (r:Resource {layer_id: 'default'})
WITH l, r.tenant_id as tenant_id
LIMIT 1
SET l.tenant_id = tenant_id
```

## Debugging Queries

### Find Anomalies

```cypher
// Resources with no relationships
MATCH (r:Resource {layer_id: $layer_id})
WHERE NOT (r)-[]-()
RETURN r.id, r.resource_type

// Relationships pointing to wrong layer
MATCH (r1:Resource {layer_id: $layer_id})
      -[rel]->
      (r2:Resource)
WHERE r2.layer_id <> $layer_id
RETURN r1.id, type(rel), r2.id, r2.layer_id

// Duplicate SCAN_SOURCE_NODE links
MATCH (r:Resource {layer_id: $layer_id})
      -[rel:SCAN_SOURCE_NODE]->
      (orig:Original)
WITH r, count(rel) as link_count
WHERE link_count > 1
RETURN r.id, link_count

// Original nodes without abstractions
MATCH (orig:Original)
WHERE NOT (orig)<-[:SCAN_SOURCE_NODE]-(:Resource)
RETURN orig.id, orig.resource_type
```

### Performance Analysis

```cypher
// Query execution plan (prefix with PROFILE or EXPLAIN)
PROFILE
MATCH (r:Resource {layer_id: $layer_id})
WHERE r.resource_type = 'VirtualMachine'
RETURN count(r)

// Index usage verification
EXPLAIN
MATCH (r:Resource)
USING INDEX r:Resource(layer_id)
WHERE r.layer_id = $layer_id
RETURN r
```

## Best Practices

1. **Always filter by layer_id first** in WHERE clause
2. **Use composite indexes** for (resource_type, layer_id)
3. **Batch large operations** (copy, delete)
4. **Use transactions** for atomic operations
5. **Verify layer boundaries** in traversals
6. **Store counts** in :Layer metadata for fast access
7. **Validate after operations** (run integrity checks)
8. **Profile slow queries** and optimize

## Anti-Patterns to Avoid

### ❌ Don't: Forget layer filter
```cypher
// BAD: No layer filter
MATCH (r:Resource)
WHERE r.resource_type = 'VirtualMachine'
RETURN r
```

### ✅ Do: Always filter by layer
```cypher
// GOOD: Layer filter first
MATCH (r:Resource {layer_id: $layer_id})
WHERE r.resource_type = 'VirtualMachine'
RETURN r
```

### ❌ Don't: Allow cross-layer relationships
```cypher
// BAD: Can link different layers
MATCH (r1:Resource {id: $r1_id}),
      (r2:Resource {id: $r2_id})
CREATE (r1)-[:CONTAINS]->(r2)
```

### ✅ Do: Verify same layer
```cypher
// GOOD: Check layer_id match
MATCH (r1:Resource {id: $r1_id, layer_id: $layer_id}),
      (r2:Resource {id: $r2_id, layer_id: $layer_id})
CREATE (r1)-[:CONTAINS]->(r2)
```

### ❌ Don't: Recount every time
```cypher
// BAD: Expensive count on every request
MATCH (r:Resource {layer_id: $layer_id})
RETURN count(r)
```

### ✅ Do: Use stored count
```cypher
// GOOD: Read from metadata
MATCH (l:Layer {layer_id: $layer_id})
RETURN l.node_count
```

---

**These query patterns form the foundation for all layer-aware operations. Follow these patterns for consistent, performant, and correct layer management.**

# Dual-Graph Architecture

Azure Tenant Grapher uses a unique dual-graph architecture where every Azure resource exists as two nodes in Neo4j:

## Overview

### The Two Graphs

1. **Original Graph** (`:Resource:Original`)
   - Contains real Azure resource IDs
   - Preserves exact source tenant topology
   - Used for query and analysis

2. **Abstracted Graph** (`:Resource`)
   - Contains hash-based abstracted IDs (e.g., `vm-a1b2c3d4`)
   - Safe for cross-tenant deployment
   - Used for IaC generation

Both graphs are connected via `SCAN_SOURCE_NODE` relationships:

```cypher
(Abstracted)-[:SCAN_SOURCE_NODE]->(Original)
```

## Why Dual-Graph?

### Problem

Cross-tenant deployments need abstracted IDs, but analysis needs original IDs.

### Solution

Store both! This enables:

- **Cross-tenant deployment** - Abstracted IDs prevent collisions
- **Flexible queries** - Query original topology OR deployment view
- **No runtime translation** - IaC generation is simple
- **Graph-based validation** - Verify abstractions in Neo4j

## Key Components

### ID Abstraction Service

```python
class IDAbstractionService:
    def generate_abstracted_id(self, resource: Dict) -> str:
        """Generate deterministic hash-based ID"""
        # Example: vm-a1b2c3d4 (type-prefix-hash)
```

### Tenant Seed Manager

```python
class TenantSeedManager:
    """Per-tenant cryptographic seeds for reproducible abstraction"""
```

### Dual-Graph Operations

```python
# Create both nodes in single operation
db_ops.upsert_dual_graph_resource(resource)

# Create relationship in both graphs
db_ops.create_dual_graph_rel(src_id, rel_type, tgt_id)
```

## Node Structure

### Original Node

```cypher
(:VirtualMachine:Resource:Original {
  id: "/subscriptions/.../resourceGroups/rg-test/providers/Microsoft.Compute/virtualMachines/vm-prod",
  name: "vm-prod",
  resource_type: "Microsoft.Compute/virtualMachines",
  tenant_id: "source-tenant-id"
})
```

### Abstracted Node

```cypher
(:VirtualMachine:Resource {
  id: "vm-a1b2c3d4",
  name: "vm-prod",
  resource_type: "Microsoft.Compute/virtualMachines",
  tenant_id: "source-tenant-id"
})
```

## Relationship Duplication

All resource relationships exist in both graphs:

```cypher
# Original graph
(vm:Original)-[:USES_SUBNET]->(subnet:Original)

# Abstracted graph
(vm:Abstracted)-[:USES_SUBNET]->(subnet:Abstracted)

# Link between graphs
(vm:Abstracted)-[:SCAN_SOURCE_NODE]->(vm:Original)
```

## Query Patterns

### Query Original Topology

```cypher
MATCH (vm:VirtualMachine:Original)
WHERE vm.tenant_id = $tenantId
RETURN vm
```

### Query Abstracted for IaC

```cypher
MATCH (vm:VirtualMachine)
WHERE vm.tenant_id = $tenantId
AND NOT vm:Original
RETURN vm
```

### Cross-Reference

```cypher
MATCH (abs:VirtualMachine)-[:SCAN_SOURCE_NODE]->(orig:Original)
WHERE abs.id = $abstractedId
RETURN orig
```

## IaC Generation

IaC generation queries ONLY abstracted nodes:

```cypher
MATCH (rg:ResourceGroup)
WHERE NOT rg:Original
AND rg.tenant_id = $tenantId
RETURN rg
```

This ensures generated IaC uses safe abstracted IDs.

## Benefits

1. **Separation of Concerns**
   - Original graph for analysis
   - Abstracted graph for deployment

2. **No Runtime Overhead**
   - IaC generation doesn't need translation
   - Queries are simple and fast

3. **Graph-Based Validation**
   - Verify abstraction quality with Cypher
   - Find missing SCAN_SOURCE_NODE relationships

4. **Flexible Querying**
   - Original topology for understanding
   - Abstracted topology for deployment

## Implementation Details

For complete technical specification, see:

- [DUAL_GRAPH_SCHEMA.md](../DUAL_GRAPH_SCHEMA.md) - Complete schema
- [DUAL_GRAPH_QUERIES.cypher](../DUAL_GRAPH_QUERIES.cypher) - Query examples
- [DUAL_GRAPH_INDEX.md](../DUAL_GRAPH_INDEX.md) - Documentation index
- [scan-source-node-relationships.md](scan-source-node-relationships.md) - SCAN_SOURCE_NODE details

## See Also

- [Neo4j Schema Reference](../NEO4J_SCHEMA_REFERENCE.md)
- [SCAN_SOURCE_NODE Relationships](scan-source-node-relationships.md)
- [Terraform Import Blocks](../concepts/TERRAFORM_IMPORT_BLOCKS.md)

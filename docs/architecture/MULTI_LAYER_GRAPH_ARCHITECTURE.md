# Multi-Layer Graph Projection Architecture

## Executive Summary

This document specifies a multi-layer graph architecture that enables non-destructive scale operations by maintaining multiple coexisting abstracted projections of Azure resources. Each layer is isolated, versioned, and independently queryable while preserving the immutable Original graph as the source of truth.

## Problem Statement

### Current Architecture Limitations

1. **Data Loss**: Scale operations destructively modify the abstracted graph
   - 5,584 Original nodes → 56 Abstracted nodes (99% degradation)
   - No way to recover baseline after merge/split operations

2. **Lack of Experimentation**: Cannot try different scaling strategies
   - Each operation overwrites previous state
   - No ability to compare outcomes

3. **No Versioning**: Cannot track evolution of abstractions
   - Historical states are lost
   - Difficult to debug or audit changes

### Design Goals

1. **Non-destructive Operations**: Never lose baseline data
2. **Layer Isolation**: Each projection is independent
3. **Active Layer Concept**: One layer is "current" for operations
4. **Layer Management**: Full lifecycle (create, list, switch, delete, compare)
5. **Backward Compatibility**: Existing code works with "default" layer
6. **Performance**: Indexed queries, minimal overhead

## Architecture Overview

### Conceptual Model

```
┌─────────────────────────────────────────────────────────────┐
│                     Neo4j Graph Database                     │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────────────────────────────────────────────┐   │
│  │         ORIGINAL GRAPH (Immutable)                   │   │
│  │  :Resource:Original - Real Azure IDs                 │   │
│  │  Source of truth for all projections                 │   │
│  └──────────────────────────────────────────────────────┘   │
│                            ▲                                  │
│                            │ SCAN_SOURCE_NODE                 │
│                            │                                  │
│  ┌────────────────────────┴─────────────────────────────┐   │
│  │      ABSTRACTED LAYERS (Multiple Projections)        │   │
│  │                                                       │   │
│  │  ┌─────────────────────────────────────────────┐    │   │
│  │  │ Layer: "default" (active: true)             │    │   │
│  │  │ :Resource (layer_id='default')              │    │   │
│  │  │ Baseline 1:1 abstraction from scan          │    │   │
│  │  └─────────────────────────────────────────────┘    │   │
│  │                                                       │   │
│  │  ┌─────────────────────────────────────────────┐    │   │
│  │  │ Layer: "scaled-v1" (active: false)          │    │   │
│  │  │ :Resource (layer_id='scaled-v1')            │    │   │
│  │  │ After merge operations                      │    │   │
│  │  └─────────────────────────────────────────────┘    │   │
│  │                                                       │   │
│  │  ┌─────────────────────────────────────────────┐    │   │
│  │  │ Layer: "scaled-v2" (active: false)          │    │   │
│  │  │ :Resource (layer_id='scaled-v2')            │    │   │
│  │  │ Alternative scaling strategy                │    │   │
│  │  └─────────────────────────────────────────────┘    │   │
│  └───────────────────────────────────────────────────────┘   │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐   │
│  │         LAYER METADATA (Management)                  │   │
│  │  :Layer nodes track metadata                         │   │
│  │  Active layer configuration                          │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### Three-Tier Structure

1. **Original Graph** (Tier 1)
   - Immutable source of truth
   - Real Azure IDs
   - No layer_id (always represents baseline)

2. **Abstracted Layers** (Tier 2)
   - Multiple coexisting projections
   - Each has unique layer_id
   - One marked as "active"

3. **Layer Metadata** (Tier 3)
   - Management nodes tracking layer state
   - Active layer configuration
   - Layer lineage and provenance

## Graph Schema Design

### Node Properties

#### Original Nodes (Unchanged)
```cypher
(:Resource:Original {
  id: "azure-id-12345",
  resource_type: "VirtualMachine",
  name: "prod-vm-001",
  tenant_id: "tenant-123",
  // ... existing properties
})
```

#### Abstracted Nodes (Enhanced)
```cypher
(:Resource {
  id: "vm-a1b2c3d4",              // Abstracted ID
  resource_type: "VirtualMachine",
  name: "prod-vm-001",
  layer_id: "default",             // NEW: Layer identifier
  layer_created_at: "2025-11-16T10:00:00Z",  // NEW: Layer timestamp
  // ... existing properties
})
```

#### Layer Metadata Nodes (New)
```cypher
(:Layer {
  layer_id: "default",             // Unique layer identifier
  name: "Default Baseline",        // Human-readable name
  description: "1:1 abstraction from initial scan",
  created_at: "2025-11-16T10:00:00Z",
  created_by: "scan",              // Operation that created it
  parent_layer_id: null,           // For derived layers
  is_active: true,                 // Only one active at a time
  is_baseline: true,               // Special flag for default
  tenant_id: "tenant-123",
  node_count: 5584,
  relationship_count: 8234,
  metadata: {                      // Extensible metadata
    "operation": "scan",
    "scan_id": "scan-abc123",
    "version": "1.0"
  }
})
```

### Relationships

#### SCAN_SOURCE_NODE (Enhanced)
```cypher
// Links abstracted nodes to their original source
(:Resource {layer_id: "default"})-[:SCAN_SOURCE_NODE]->(:Resource:Original)
(:Resource {layer_id: "scaled-v1"})-[:SCAN_SOURCE_NODE]->(:Resource:Original)

// Multiple abstracted nodes can point to same original
// Enables different abstractions of same source data
```

#### DERIVED_FROM (New)
```cypher
// Tracks layer lineage
(:Layer {layer_id: "scaled-v1"})-[:DERIVED_FROM {
  operation: "merge_vnets",
  operation_id: "op-xyz789",
  created_at: "2025-11-16T11:00:00Z"
}]->(:Layer {layer_id: "default"})
```

#### Resource Relationships (Layer-Scoped)
```cypher
// All resource relationships are scoped within a layer
(:Resource {layer_id: "default"})-[:CONTAINS]->(:Resource {layer_id: "default"})
(:Resource {layer_id: "scaled-v1"})-[:USES_SUBNET]->(:Resource {layer_id: "scaled-v1"})

// Relationships never cross layer boundaries
// Each layer is a complete, isolated projection
```

### Indexes and Constraints

```cypher
-- Core constraints (existing, now per-layer)
CREATE CONSTRAINT resource_layer_id_unique IF NOT EXISTS
FOR (r:Resource) REQUIRE (r.id, r.layer_id) IS UNIQUE;

CREATE CONSTRAINT original_id_unique IF NOT EXISTS
FOR (r:Original) REQUIRE r.id IS UNIQUE;

CREATE CONSTRAINT layer_id_unique IF NOT EXISTS
FOR (l:Layer) REQUIRE l.layer_id IS UNIQUE;

-- Performance indexes
CREATE INDEX resource_layer_id IF NOT EXISTS
FOR (r:Resource) ON (r.layer_id);

CREATE INDEX resource_type_layer IF NOT EXISTS
FOR (r:Resource) ON (r.resource_type, r.layer_id);

CREATE INDEX layer_active IF NOT EXISTS
FOR (l:Layer) ON (l.is_active);

CREATE INDEX layer_tenant IF NOT EXISTS
FOR (l:Layer) ON (l.tenant_id);

-- Full-text search per layer
CREATE FULLTEXT INDEX resource_search_by_layer IF NOT EXISTS
FOR (r:Resource) ON EACH [r.name, r.id, r.layer_id];
```

## Service Layer Design

### LayerManagementService

```python
# src/services/layer_management_service.py

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum


class LayerType(Enum):
    """Type of layer for classification."""
    BASELINE = "baseline"      # Original 1:1 abstraction
    SCALED = "scaled"          # After merge/split operations
    EXPERIMENTAL = "experimental"  # Sandbox for testing
    SNAPSHOT = "snapshot"      # Point-in-time backup


@dataclass
class LayerMetadata:
    """Metadata for a graph layer."""
    layer_id: str
    name: str
    description: str
    created_at: datetime
    created_by: str  # Operation: scan, merge, split, etc.
    parent_layer_id: Optional[str]
    is_active: bool
    is_baseline: bool
    tenant_id: str
    node_count: int
    relationship_count: int
    layer_type: LayerType
    metadata: Dict[str, Any]


@dataclass
class LayerDiff:
    """Comparison between two layers."""
    layer_a_id: str
    layer_b_id: str
    nodes_added: int
    nodes_removed: int
    nodes_modified: int
    relationships_added: int
    relationships_removed: int
    details: Dict[str, Any]


class LayerManagementService:
    """
    Service for managing graph layers.

    Responsibilities:
    - Create, list, delete layers
    - Switch active layer
    - Query layer metadata
    - Compare layers
    - Validate layer operations
    """

    def __init__(self, neo4j_driver):
        self.driver = neo4j_driver

    # ===== Layer Lifecycle =====

    async def create_layer(
        self,
        layer_id: str,
        name: str,
        description: str,
        created_by: str,
        parent_layer_id: Optional[str] = None,
        layer_type: LayerType = LayerType.EXPERIMENTAL,
        tenant_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        make_active: bool = False
    ) -> LayerMetadata:
        """
        Create a new layer metadata node.

        Args:
            layer_id: Unique identifier for the layer
            name: Human-readable name
            description: Purpose of this layer
            created_by: Operation that created it (scan, merge, etc.)
            parent_layer_id: Source layer if derived
            layer_type: Classification of layer
            tenant_id: Azure tenant ID
            metadata: Additional metadata
            make_active: Whether to make this the active layer

        Returns:
            LayerMetadata object

        Raises:
            ValueError: If layer_id already exists
        """
        pass

    async def list_layers(
        self,
        tenant_id: Optional[str] = None,
        include_inactive: bool = True,
        layer_type: Optional[LayerType] = None
    ) -> List[LayerMetadata]:
        """
        List all layers, optionally filtered.

        Args:
            tenant_id: Filter by tenant
            include_inactive: Whether to include inactive layers
            layer_type: Filter by layer type

        Returns:
            List of LayerMetadata objects
        """
        pass

    async def get_layer(self, layer_id: str) -> Optional[LayerMetadata]:
        """Get metadata for a specific layer."""
        pass

    async def get_active_layer(self, tenant_id: Optional[str] = None) -> Optional[LayerMetadata]:
        """Get the currently active layer."""
        pass

    async def delete_layer(
        self,
        layer_id: str,
        force: bool = False
    ) -> bool:
        """
        Delete a layer and all its nodes/relationships.

        Args:
            layer_id: Layer to delete
            force: Allow deletion of active or baseline layers

        Returns:
            True if deleted, False if not found

        Raises:
            ValueError: If trying to delete active/baseline without force
        """
        pass

    # ===== Active Layer Management =====

    async def set_active_layer(
        self,
        layer_id: str,
        tenant_id: Optional[str] = None
    ) -> LayerMetadata:
        """
        Switch the active layer.

        Args:
            layer_id: Layer to activate
            tenant_id: Tenant context (for multi-tenant)

        Returns:
            Updated LayerMetadata

        Side Effects:
            - Marks previous active layer as inactive
            - Updates is_active flag on new layer
            - Updates global active layer config
        """
        pass

    # ===== Layer Operations =====

    async def copy_layer(
        self,
        source_layer_id: str,
        target_layer_id: str,
        name: str,
        description: str
    ) -> LayerMetadata:
        """
        Copy an entire layer (nodes + relationships).

        Args:
            source_layer_id: Layer to copy from
            target_layer_id: New layer ID
            name: Name for new layer
            description: Description for new layer

        Returns:
            LayerMetadata for new layer

        Implementation:
            - Duplicates all nodes with source layer_id
            - Duplicates all relationships
            - Preserves SCAN_SOURCE_NODE links to Original
            - Creates DERIVED_FROM relationship
        """
        pass

    async def compare_layers(
        self,
        layer_a_id: str,
        layer_b_id: str,
        detailed: bool = False
    ) -> LayerDiff:
        """
        Compare two layers to find differences.

        Args:
            layer_a_id: First layer (baseline)
            layer_b_id: Second layer (comparison)
            detailed: Include detailed node/relationship diffs

        Returns:
            LayerDiff object with statistics and details
        """
        pass

    async def refresh_layer_stats(self, layer_id: str) -> LayerMetadata:
        """
        Recalculate node_count and relationship_count for a layer.

        Useful after bulk operations.
        """
        pass

    # ===== Validation =====

    async def validate_layer_integrity(self, layer_id: str) -> Dict[str, Any]:
        """
        Validate layer integrity.

        Checks:
        - All nodes have valid SCAN_SOURCE_NODE links
        - No relationships crossing layer boundaries
        - Node count matches metadata
        - No orphaned relationships

        Returns:
            Validation report with issues
        """
        pass
```

### Query Patterns with Layer Filtering

```python
# src/services/layer_aware_query_service.py

class LayerAwareQueryService:
    """
    Service for querying resources with layer awareness.

    All queries are scoped to the active layer by default.
    Can explicitly query other layers.
    """

    def __init__(self, neo4j_driver, layer_service: LayerManagementService):
        self.driver = neo4j_driver
        self.layer_service = layer_service

    async def get_resource(
        self,
        resource_id: str,
        layer_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get a resource from specified or active layer.

        Args:
            resource_id: Resource ID to fetch
            layer_id: Specific layer, or None for active

        Returns:
            Resource properties or None
        """
        if layer_id is None:
            layer_metadata = await self.layer_service.get_active_layer()
            layer_id = layer_metadata.layer_id if layer_metadata else "default"

        query = """
        MATCH (r:Resource {id: $resource_id, layer_id: $layer_id})
        RETURN r
        """
        # Execute query...
        pass

    async def find_resources(
        self,
        resource_type: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        layer_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Find resources matching criteria in specified or active layer.

        Args:
            resource_type: Filter by type (e.g., "VirtualMachine")
            filters: Additional property filters
            layer_id: Specific layer, or None for active

        Returns:
            List of matching resources
        """
        if layer_id is None:
            layer_metadata = await self.layer_service.get_active_layer()
            layer_id = layer_metadata.layer_id if layer_metadata else "default"

        # Build dynamic query with layer filter...
        pass

    async def traverse_relationships(
        self,
        start_resource_id: str,
        relationship_type: str,
        layer_id: Optional[str] = None,
        depth: int = 1
    ) -> List[Dict[str, Any]]:
        """
        Traverse relationships within a single layer.

        Args:
            start_resource_id: Starting node
            relationship_type: Relationship to follow
            layer_id: Layer to traverse
            depth: Max traversal depth

        Returns:
            List of connected resources
        """
        if layer_id is None:
            layer_metadata = await self.layer_service.get_active_layer()
            layer_id = layer_metadata.layer_id if layer_metadata else "default"

        # Ensure traversal stays within layer boundary
        query = f"""
        MATCH (start:Resource {{id: $start_id, layer_id: $layer_id}})
        MATCH path = (start)-[:{relationship_type}*1..{depth}]->(target:Resource)
        WHERE target.layer_id = $layer_id
        RETURN target
        """
        pass

    async def get_resource_original(
        self,
        resource_id: str,
        layer_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get the Original node for a resource in a layer.

        Useful for cross-referencing back to source data.
        """
        if layer_id is None:
            layer_metadata = await self.layer_service.get_active_layer()
            layer_id = layer_metadata.layer_id if layer_metadata else "default"

        query = """
        MATCH (r:Resource {id: $resource_id, layer_id: $layer_id})
              -[:SCAN_SOURCE_NODE]->(orig:Original)
        RETURN orig
        """
        pass
```

### Scale Operations Service (Enhanced)

```python
# src/services/scale_operations_service.py

class ScaleOperationsService:
    """
    Enhanced scale operations that create new layers.

    All operations are non-destructive:
    - Create new layer from source layer
    - Apply transformations
    - Optionally make new layer active
    """

    def __init__(
        self,
        neo4j_driver,
        layer_service: LayerManagementService,
        query_service: LayerAwareQueryService
    ):
        self.driver = neo4j_driver
        self.layer_service = layer_service
        self.query_service = query_service

    async def merge_vnets(
        self,
        vnet_ids: List[str],
        source_layer_id: Optional[str] = None,
        target_layer_id: Optional[str] = None,
        name: Optional[str] = None,
        make_active: bool = False
    ) -> LayerMetadata:
        """
        Merge VNets by creating a new layer.

        Args:
            vnet_ids: VNets to merge
            source_layer_id: Layer to read from (or active)
            target_layer_id: New layer ID (auto-generated if None)
            name: Name for new layer
            make_active: Whether to activate new layer

        Returns:
            Metadata for new layer

        Process:
        1. Copy source layer to new layer
        2. Apply merge transformations in new layer
        3. Update layer metadata
        4. Optionally activate
        """
        # Get source layer
        if source_layer_id is None:
            source = await self.layer_service.get_active_layer()
            source_layer_id = source.layer_id

        # Generate target layer ID
        if target_layer_id is None:
            target_layer_id = f"scaled-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"

        # Copy layer
        await self.layer_service.copy_layer(
            source_layer_id=source_layer_id,
            target_layer_id=target_layer_id,
            name=name or f"Merged VNets: {source_layer_id}",
            description=f"Merged {len(vnet_ids)} VNets from {source_layer_id}"
        )

        # Apply merge in new layer
        await self._apply_vnet_merge(vnet_ids, target_layer_id)

        # Refresh stats
        layer_metadata = await self.layer_service.refresh_layer_stats(target_layer_id)

        # Optionally activate
        if make_active:
            layer_metadata = await self.layer_service.set_active_layer(target_layer_id)

        return layer_metadata

    async def _apply_vnet_merge(self, vnet_ids: List[str], layer_id: str):
        """Apply VNet merge transformation within a layer."""
        # Implementation: Merge VNet nodes, consolidate subnets, update relationships
        pass
```

## CLI Command Specifications

### Layer Management Commands

```bash
# List all layers
uv run atg layer list [--tenant-id TENANT] [--include-inactive]

# Show detailed layer info
uv run atg layer show <layer-id>

# Create new layer (empty)
uv run atg layer create <layer-id> --name "My Layer" --description "..."

# Copy layer
uv run atg layer copy <source-layer> <target-layer> --name "..." --description "..."

# Delete layer
uv run atg layer delete <layer-id> [--force]

# Set active layer
uv run atg layer activate <layer-id>

# Show active layer
uv run atg layer active

# Compare two layers
uv run atg layer diff <layer-a> <layer-b> [--detailed]

# Validate layer integrity
uv run atg layer validate <layer-id>

# Refresh layer statistics
uv run atg layer refresh-stats <layer-id>
```

### Enhanced Scale Operations Commands

```bash
# All scale operations now accept --layer flags

# Merge VNets (creates new layer)
uv run atg scale merge-vnets <vnet-id-1> <vnet-id-2> \
  --source-layer default \
  --target-layer scaled-v1 \
  --name "Merged Production VNets" \
  --make-active

# If no --target-layer, auto-generates: scaled-YYYYMMDD-HHMMSS
uv run atg scale merge-vnets <vnet-id-1> <vnet-id-2>

# Merge subnets (creates new layer)
uv run atg scale merge-subnets <subnet-id-1> <subnet-id-2> \
  --source-layer scaled-v1 \
  --target-layer scaled-v2

# Split VNet (creates new layer)
uv run atg scale split-vnet <vnet-id> \
  --source-layer default \
  --target-layer experimental-split

# Consolidate VMs (creates new layer)
uv run atg scale consolidate-vms <vm-id-1> <vm-id-2> \
  --source-layer default \
  --target-layer cost-optimized
```

### Enhanced IaC Generation Commands

```bash
# Generate IaC from specific layer
uv run atg generate-iac --layer scaled-v1

# Generate IaC from active layer (default)
uv run atg generate-iac

# Compare IaC from two layers
uv run atg generate-iac --layer default --output default-iac/
uv run atg generate-iac --layer scaled-v1 --output scaled-iac/
diff -r default-iac/ scaled-iac/
```

### Backward Compatibility

```bash
# All existing commands work with active layer
uv run atg scan  # Creates "default" layer, makes it active
uv run atg generate-iac  # Uses active layer
uv run atg visualize  # Shows active layer

# Explicit layer specification is optional
uv run atg generate-iac --layer default  # Explicit
uv run atg generate-iac  # Implicit (uses active)
```

## Migration Strategy

### Phase 1: Schema Migration (Non-Breaking)

```python
# migrations/012_add_layer_support.py

async def upgrade(neo4j_driver):
    """
    Add layer support to existing graph.

    Steps:
    1. Add layer_id property to all :Resource nodes (default: "default")
    2. Create :Layer metadata node for default layer
    3. Mark default layer as active and baseline
    4. Create indexes and constraints
    5. Validate migration
    """

    async with neo4j_driver.session() as session:
        # Step 1: Add layer_id to existing resources
        await session.run("""
            MATCH (r:Resource)
            WHERE NOT r:Original AND r.layer_id IS NULL
            SET r.layer_id = 'default',
                r.layer_created_at = datetime()
        """)

        # Step 2: Create default Layer metadata node
        await session.run("""
            MERGE (l:Layer {layer_id: 'default'})
            SET l.name = 'Default Baseline',
                l.description = '1:1 abstraction from initial scan',
                l.created_at = datetime(),
                l.created_by = 'migration',
                l.is_active = true,
                l.is_baseline = true,
                l.tenant_id = coalesce(
                    (MATCH (r:Resource {layer_id: 'default'})
                     RETURN r.tenant_id LIMIT 1).tenant_id,
                    'unknown'
                )
        """)

        # Step 3: Count nodes and relationships
        result = await session.run("""
            MATCH (r:Resource {layer_id: 'default'})
            WITH count(r) as node_count
            MATCH (r1:Resource {layer_id: 'default'})
                  -[rel]->
                  (r2:Resource {layer_id: 'default'})
            WITH node_count, count(rel) as rel_count
            MATCH (l:Layer {layer_id: 'default'})
            SET l.node_count = node_count,
                l.relationship_count = rel_count
            RETURN node_count, rel_count
        """)

        # Step 4: Create indexes
        await session.run("""
            CREATE INDEX resource_layer_id IF NOT EXISTS
            FOR (r:Resource) ON (r.layer_id)
        """)

        await session.run("""
            CREATE CONSTRAINT layer_id_unique IF NOT EXISTS
            FOR (l:Layer) REQUIRE l.layer_id IS UNIQUE
        """)

        # Step 5: Update composite unique constraint
        await session.run("""
            DROP CONSTRAINT resource_id_unique IF EXISTS
        """)

        await session.run("""
            CREATE CONSTRAINT resource_layer_id_unique IF NOT EXISTS
            FOR (r:Resource) REQUIRE (r.id, r.layer_id) IS UNIQUE
        """)


async def downgrade(neo4j_driver):
    """
    Remove layer support (destructive).

    WARNING: This removes all non-default layers!
    """

    async with neo4j_driver.session() as session:
        # Delete non-default layers
        await session.run("""
            MATCH (r:Resource)
            WHERE r.layer_id <> 'default'
            DETACH DELETE r
        """)

        # Remove layer metadata
        await session.run("""
            MATCH (l:Layer)
            DELETE l
        """)

        # Remove layer_id property
        await session.run("""
            MATCH (r:Resource {layer_id: 'default'})
            REMOVE r.layer_id, r.layer_created_at
        """)

        # Restore original constraint
        await session.run("""
            DROP CONSTRAINT resource_layer_id_unique IF EXISTS
        """)

        await session.run("""
            CREATE CONSTRAINT resource_id_unique IF NOT EXISTS
            FOR (r:Resource) REQUIRE r.id IS UNIQUE
        """)
```

### Phase 2: Code Updates

```python
# Update existing services to be layer-aware

# src/services/resource_processing_service.py
class ResourceProcessingService:
    """Updated to write to specified layer."""

    async def create_resource_node(
        self,
        resource: Dict[str, Any],
        layer_id: str = "default"  # NEW: Default to baseline layer
    ):
        """Create resource node in specified layer."""
        # Add layer_id to properties
        properties = {**resource, "layer_id": layer_id}
        # Create node...


# src/iac/traverser.py
class GraphTraverser:
    """Updated to traverse specific layer."""

    def __init__(self, neo4j_driver, layer_id: Optional[str] = None):
        self.driver = neo4j_driver
        self.layer_id = layer_id  # None = use active layer

    async def traverse(self):
        """Traverse graph in specified layer."""
        if self.layer_id is None:
            # Get active layer
            layer_service = LayerManagementService(self.driver)
            active_layer = await layer_service.get_active_layer()
            self.layer_id = active_layer.layer_id if active_layer else "default"

        # All queries now include: WHERE r.layer_id = $layer_id
```

### Phase 3: Testing Strategy

```python
# tests/test_layer_management.py

async def test_create_layer():
    """Test layer creation."""
    service = LayerManagementService(driver)

    layer = await service.create_layer(
        layer_id="test-layer",
        name="Test Layer",
        description="Testing",
        created_by="test",
        layer_type=LayerType.EXPERIMENTAL
    )

    assert layer.layer_id == "test-layer"
    assert layer.is_active is False


async def test_copy_layer_preserves_structure():
    """Test that copying layer preserves all nodes and relationships."""
    # Create source layer with resources
    # Copy to target layer
    # Verify counts match
    # Verify relationships preserved
    # Verify SCAN_SOURCE_NODE links intact


async def test_scale_operation_creates_new_layer():
    """Test that merge operation is non-destructive."""
    # Get baseline node count
    baseline_count = await count_nodes("default")

    # Perform merge (creates new layer)
    new_layer = await scale_service.merge_vnets(
        vnet_ids=["vnet1", "vnet2"],
        target_layer_id="test-merge"
    )

    # Verify baseline unchanged
    assert await count_nodes("default") == baseline_count

    # Verify new layer has different structure
    assert await count_nodes("test-merge") < baseline_count


async def test_active_layer_switching():
    """Test switching active layers."""
    # Create two layers
    # Set layer1 active
    # Verify queries use layer1
    # Set layer2 active
    # Verify queries use layer2


async def test_layer_isolation():
    """Test that layers don't interfere."""
    # Create resource in layer1
    # Verify not visible in layer2
    # Create relationship in layer1
    # Verify not traversable from layer2
```

## Implementation Checklist

### Database Schema
- [ ] Create migration 012_add_layer_support.py
- [ ] Add layer_id property to Resource nodes
- [ ] Create Layer metadata node schema
- [ ] Add DERIVED_FROM relationship type
- [ ] Create composite unique constraint (id, layer_id)
- [ ] Create layer_id index for performance
- [ ] Update SCAN_SOURCE_NODE to support multiple layers
- [ ] Test migration on sample data

### Service Layer
- [ ] Implement LayerManagementService
  - [ ] create_layer()
  - [ ] list_layers()
  - [ ] get_layer()
  - [ ] get_active_layer()
  - [ ] delete_layer()
  - [ ] set_active_layer()
  - [ ] copy_layer()
  - [ ] compare_layers()
  - [ ] refresh_layer_stats()
  - [ ] validate_layer_integrity()

- [ ] Implement LayerAwareQueryService
  - [ ] get_resource() with layer filter
  - [ ] find_resources() with layer filter
  - [ ] traverse_relationships() within layer
  - [ ] get_resource_original()

- [ ] Update ResourceProcessingService
  - [ ] Add layer_id parameter to create_resource_node()
  - [ ] Update batch operations for layers

- [ ] Update ScaleOperationsService
  - [ ] Make all operations create new layers
  - [ ] Add source/target layer parameters
  - [ ] Implement copy-then-transform pattern

### CLI Commands
- [ ] Implement atg layer list
- [ ] Implement atg layer show
- [ ] Implement atg layer create
- [ ] Implement atg layer copy
- [ ] Implement atg layer delete
- [ ] Implement atg layer activate
- [ ] Implement atg layer active
- [ ] Implement atg layer diff
- [ ] Implement atg layer validate
- [ ] Implement atg layer refresh-stats

- [ ] Update atg scale commands
  - [ ] Add --source-layer flag
  - [ ] Add --target-layer flag
  - [ ] Add --make-active flag

- [ ] Update atg generate-iac
  - [ ] Add --layer flag
  - [ ] Default to active layer

- [ ] Update atg scan
  - [ ] Create "default" layer
  - [ ] Mark as baseline and active

### Backward Compatibility
- [ ] Ensure all existing commands work without --layer flags
- [ ] Default to active layer in all operations
- [ ] Auto-migrate existing graphs on first run
- [ ] Add warning if no active layer set

### Testing
- [ ] Unit tests for LayerManagementService
- [ ] Unit tests for LayerAwareQueryService
- [ ] Integration tests for layer operations
- [ ] E2E tests for scale operations with layers
- [ ] Migration tests (upgrade/downgrade)
- [ ] Performance tests with multiple layers
- [ ] Test layer isolation
- [ ] Test active layer switching

### Documentation
- [ ] Update NEO4J_SCHEMA_REFERENCE.md
- [ ] Update CLAUDE.md with layer concepts
- [ ] Create LAYER_MANAGEMENT_GUIDE.md
- [ ] Add examples to scale operations docs
- [ ] Update CLI help text
- [ ] Create migration guide for existing deployments

## Performance Considerations

### Query Optimization

1. **Always filter by layer_id early in query**
   ```cypher
   -- Good: Filter first
   MATCH (r:Resource {layer_id: $layer_id})
   WHERE r.resource_type = 'VirtualMachine'

   -- Bad: Filter late
   MATCH (r:Resource)
   WHERE r.resource_type = 'VirtualMachine' AND r.layer_id = $layer_id
   ```

2. **Use composite indexes**
   ```cypher
   CREATE INDEX resource_type_layer IF NOT EXISTS
   FOR (r:Resource) ON (r.resource_type, r.layer_id)
   ```

3. **Limit layer proliferation**
   - Warn users when > 10 layers exist
   - Provide cleanup recommendations
   - Auto-delete old experimental layers

### Storage Overhead

- Each additional layer roughly duplicates node storage
- Relationships are also duplicated per layer
- SCAN_SOURCE_NODE relationships are 1:1 per abstracted node

**Mitigation:**
- Aggressive layer cleanup
- Layer archival (export to JSON, delete from graph)
- Periodic garbage collection of unused layers

## Security Considerations

### Layer Access Control (Future Enhancement)

```python
# Layer metadata could include ACLs
(:Layer {
  layer_id: "production-scaled",
  acl: {
    "read": ["admin", "ops"],
    "write": ["admin"],
    "delete": ["admin"]
  }
})
```

### Audit Trail

All layer operations should be logged:
- Layer creation (who, when, from what)
- Layer activation (switches)
- Layer deletion
- Scale operations

## Open Questions / Future Enhancements

1. **Layer Archival**: Export layer to file, delete from graph, re-import later?
2. **Layer Branching**: Git-like branching model for experimentation?
3. **Layer Merging**: Merge changes from experimental layer back to baseline?
4. **Multi-Tenant Active Layers**: One active layer per tenant?
5. **Layer Templates**: Predefined layer configurations?
6. **Layer Snapshots**: Automatic snapshots before destructive operations?

## Success Criteria

This architecture succeeds if:

1. **Non-Destructive**: Scale operations never lose data
2. **Isolated**: Layers don't interfere with each other
3. **Performant**: Layer filtering adds < 10% query overhead
4. **Compatible**: Existing code works without changes
5. **Manageable**: Clear CLI for all layer operations
6. **Recoverable**: Can always return to baseline state

## Conclusion

This multi-layer architecture transforms Azure Tenant Grapher from a single-projection system into a powerful workspace for experimenting with infrastructure topology. By maintaining immutable Original data and supporting multiple coexisting abstracted projections, users can explore different scaling strategies without fear of data loss.

The design emphasizes:
- **Simplicity**: Layers are just nodes with a layer_id property
- **Clarity**: Active layer concept is intuitive
- **Modularity**: Services are cleanly separated
- **Regeneratable**: Layers can be copied, deleted, recreated

Implementation should proceed incrementally, with careful testing at each phase to ensure backward compatibility and data integrity.

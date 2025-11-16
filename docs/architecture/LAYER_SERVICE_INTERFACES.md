# Layer Service Interfaces

This document provides complete interface specifications for all layer-related services. These are the contracts that implementations must fulfill.

## Core Data Models

### LayerType Enum

```python
from enum import Enum

class LayerType(Enum):
    """Classification of layer purpose."""
    BASELINE = "baseline"          # Original 1:1 abstraction from scan
    SCALED = "scaled"              # Result of merge/split operations
    EXPERIMENTAL = "experimental"  # Sandbox for testing
    SNAPSHOT = "snapshot"          # Point-in-time backup
```

### LayerMetadata Dataclass

```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any

@dataclass
class LayerMetadata:
    """Complete metadata for a graph layer."""

    # Identity
    layer_id: str                      # Unique identifier
    name: str                          # Human-readable name
    description: str                   # Purpose description

    # Timestamps
    created_at: datetime               # When layer was created
    updated_at: Optional[datetime] = None  # Last modification

    # Provenance
    created_by: str = "unknown"        # Operation: scan, merge, split, copy
    parent_layer_id: Optional[str] = None  # Source layer if derived

    # State
    is_active: bool = False            # Currently active for operations
    is_baseline: bool = False          # Protected baseline layer
    is_locked: bool = False            # Prevent modifications

    # Scope
    tenant_id: str = "unknown"         # Azure tenant
    subscription_ids: list[str] = field(default_factory=list)  # Subscriptions included

    # Statistics
    node_count: int = 0                # Number of :Resource nodes
    relationship_count: int = 0        # Number of relationships

    # Classification
    layer_type: LayerType = LayerType.EXPERIMENTAL

    # Extensible metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Tags
    tags: list[str] = field(default_factory=list)


@dataclass
class LayerDiff:
    """Comparison result between two layers."""

    # Identity
    layer_a_id: str                    # Baseline layer
    layer_b_id: str                    # Comparison layer
    compared_at: datetime              # When comparison was done

    # Node differences
    nodes_added: int                   # In B, not in A
    nodes_removed: int                 # In A, not in B
    nodes_modified: int                # Same ID, different properties
    nodes_unchanged: int               # Identical

    # Relationship differences
    relationships_added: int
    relationships_removed: int
    relationships_modified: int
    relationships_unchanged: int

    # Detailed changes (optional)
    added_node_ids: list[str] = field(default_factory=list)
    removed_node_ids: list[str] = field(default_factory=list)
    modified_node_ids: list[str] = field(default_factory=list)

    # Property-level changes (optional)
    property_changes: Dict[str, Any] = field(default_factory=dict)

    # Summary
    total_changes: int = 0
    change_percentage: float = 0.0


@dataclass
class LayerValidationReport:
    """Validation results for layer integrity."""

    layer_id: str
    validated_at: datetime
    is_valid: bool

    # Checks
    checks_passed: int
    checks_failed: int
    checks_warned: int

    # Issues
    issues: list[Dict[str, Any]] = field(default_factory=list)
    warnings: list[Dict[str, Any]] = field(default_factory=list)

    # Statistics
    orphaned_nodes: int = 0
    orphaned_relationships: int = 0
    cross_layer_relationships: int = 0
    missing_scan_source_nodes: int = 0

    def add_error(self, code: str, message: str, details: Dict[str, Any] = None):
        """Add validation error."""
        self.issues.append({
            "level": "error",
            "code": code,
            "message": message,
            "details": details or {}
        })
        self.checks_failed += 1
        self.is_valid = False

    def add_warning(self, code: str, message: str, details: Dict[str, Any] = None):
        """Add validation warning."""
        self.warnings.append({
            "level": "warning",
            "code": code,
            "message": message,
            "details": details or {}
        })
        self.checks_warned += 1
```

## LayerManagementService Interface

```python
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any

class ILayerManagementService(ABC):
    """
    Interface for layer management operations.

    Responsibilities:
    - CRUD operations on layers
    - Active layer management
    - Layer copying and comparison
    - Layer validation

    Thread Safety: Methods should be thread-safe
    Error Handling: Raise specific exceptions (LayerNotFoundError, etc.)
    """

    # ===== Layer Lifecycle =====

    @abstractmethod
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
            layer_id: Unique identifier (e.g., "scaled-20251116-1234")
            name: Human-readable name (e.g., "Production Scaled v1")
            description: Purpose and context
            created_by: Operation name (scan, merge, split, copy)
            parent_layer_id: Source layer if derived (for provenance)
            layer_type: Classification (BASELINE, SCALED, etc.)
            tenant_id: Azure tenant ID
            metadata: Arbitrary key-value pairs
            make_active: Set as active layer immediately

        Returns:
            LayerMetadata object for created layer

        Raises:
            LayerAlreadyExistsError: If layer_id already exists
            InvalidLayerIdError: If layer_id format invalid
            ValueError: If parent_layer_id doesn't exist

        Side Effects:
            - Creates :Layer node in Neo4j
            - If make_active=True, deactivates current active layer
            - If parent_layer_id set, creates :DERIVED_FROM relationship

        Example:
            layer = await service.create_layer(
                layer_id="scaled-v1",
                name="Merged Production VNets",
                description="Consolidated 3 VNets into 1",
                created_by="merge_vnets",
                parent_layer_id="default",
                layer_type=LayerType.SCALED,
                make_active=True
            )
        """
        pass

    @abstractmethod
    async def list_layers(
        self,
        tenant_id: Optional[str] = None,
        include_inactive: bool = True,
        layer_type: Optional[LayerType] = None,
        tags: Optional[List[str]] = None,
        sort_by: str = "created_at",
        ascending: bool = False
    ) -> List[LayerMetadata]:
        """
        List layers with optional filtering.

        Args:
            tenant_id: Filter by tenant (None = all tenants)
            include_inactive: Include non-active layers
            layer_type: Filter by type
            tags: Filter by tags (AND logic)
            sort_by: Sort field (created_at, name, node_count)
            ascending: Sort order

        Returns:
            List of LayerMetadata objects

        Example:
            layers = await service.list_layers(
                tenant_id="tenant-123",
                layer_type=LayerType.SCALED,
                sort_by="created_at",
                ascending=False  # Most recent first
            )
        """
        pass

    @abstractmethod
    async def get_layer(self, layer_id: str) -> Optional[LayerMetadata]:
        """
        Get metadata for a specific layer.

        Args:
            layer_id: Layer identifier

        Returns:
            LayerMetadata if found, None otherwise

        Example:
            layer = await service.get_layer("default")
            if layer:
                print(f"Layer has {layer.node_count} nodes")
        """
        pass

    @abstractmethod
    async def get_active_layer(
        self,
        tenant_id: Optional[str] = None
    ) -> Optional[LayerMetadata]:
        """
        Get the currently active layer.

        Args:
            tenant_id: Tenant context (for multi-tenant support)

        Returns:
            LayerMetadata of active layer, None if no active layer

        Behavior:
            - If multiple active layers found (error state), return first
            - If no active layer, return None (caller should default to "default")

        Example:
            active = await service.get_active_layer()
            layer_id = active.layer_id if active else "default"
        """
        pass

    @abstractmethod
    async def update_layer(
        self,
        layer_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        is_locked: Optional[bool] = None
    ) -> LayerMetadata:
        """
        Update layer metadata.

        Args:
            layer_id: Layer to update
            name: New name (None = no change)
            description: New description (None = no change)
            tags: New tags (None = no change, [] = clear tags)
            metadata: Update metadata (merged with existing)
            is_locked: Lock/unlock layer

        Returns:
            Updated LayerMetadata

        Raises:
            LayerNotFoundError: If layer doesn't exist
            LayerLockedError: If trying to modify locked layer

        Example:
            layer = await service.update_layer(
                "scaled-v1",
                description="Updated description",
                tags=["production", "optimized"]
            )
        """
        pass

    @abstractmethod
    async def delete_layer(
        self,
        layer_id: str,
        force: bool = False
    ) -> bool:
        """
        Delete a layer and all its nodes/relationships.

        Args:
            layer_id: Layer to delete
            force: Allow deletion of active/baseline layers

        Returns:
            True if deleted, False if not found

        Raises:
            LayerProtectedError: If active/baseline without force=True
            LayerLockedError: If layer is locked

        Side Effects:
            - Deletes all :Resource nodes with layer_id
            - Deletes all relationships within layer
            - Deletes :Layer metadata node
            - DOES NOT delete :Original nodes (immutable)

        Warning:
            This is destructive! Consider archival instead.

        Example:
            # Safe delete
            deleted = await service.delete_layer("experimental-v1")

            # Force delete active layer
            deleted = await service.delete_layer("default", force=True)
        """
        pass

    # ===== Active Layer Management =====

    @abstractmethod
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

        Raises:
            LayerNotFoundError: If layer_id doesn't exist

        Side Effects:
            - Sets is_active=False on previous active layer
            - Sets is_active=True on new layer
            - Updates updated_at timestamp

        Atomic:
            Uses transaction to ensure only one active layer

        Example:
            # Switch to scaled version
            layer = await service.set_active_layer("scaled-v1")

            # All subsequent operations use scaled-v1
            resources = await query_service.find_resources()  # Uses scaled-v1
        """
        pass

    # ===== Layer Operations =====

    @abstractmethod
    async def copy_layer(
        self,
        source_layer_id: str,
        target_layer_id: str,
        name: str,
        description: str,
        copy_metadata: bool = True,
        batch_size: int = 1000,
        progress_callback: Optional[callable] = None
    ) -> LayerMetadata:
        """
        Copy an entire layer (nodes + relationships).

        Args:
            source_layer_id: Layer to copy from
            target_layer_id: New layer ID
            name: Name for new layer
            description: Description for new layer
            copy_metadata: Copy metadata dict from source
            batch_size: Nodes per batch for performance
            progress_callback: Called with (current, total) for progress

        Returns:
            LayerMetadata for new layer

        Raises:
            LayerNotFoundError: If source doesn't exist
            LayerAlreadyExistsError: If target exists

        Process:
            1. Validate source exists
            2. Create target :Layer metadata node
            3. Copy all :Resource nodes (batch)
                - Preserve all properties except layer_id
                - Set layer_id = target_layer_id
                - Preserve SCAN_SOURCE_NODE links
            4. Copy all relationships (batch)
                - Only relationships within layer
                - Update source/target to new nodes
            5. Create :DERIVED_FROM relationship
            6. Update node/relationship counts

        Performance:
            - Uses batching for large layers
            - Typically processes 1000 nodes/sec
            - Memory usage ~100MB per 10K nodes

        Example:
            layer = await service.copy_layer(
                source_layer_id="default",
                target_layer_id="experiment-1",
                name="Experiment: Aggressive Merging",
                description="Testing 10:1 consolidation ratio",
                progress_callback=lambda curr, total: print(f"{curr}/{total}")
            )
        """
        pass

    @abstractmethod
    async def compare_layers(
        self,
        layer_a_id: str,
        layer_b_id: str,
        detailed: bool = False,
        include_properties: bool = False
    ) -> LayerDiff:
        """
        Compare two layers to find differences.

        Args:
            layer_a_id: Baseline layer
            layer_b_id: Comparison layer
            detailed: Include node IDs in results
            include_properties: Compare property values

        Returns:
            LayerDiff object with statistics

        Raises:
            LayerNotFoundError: If either layer doesn't exist

        Comparison Logic:
            - Nodes compared by resource ID
            - Added: In B, not in A
            - Removed: In A, not in B
            - Modified: Same ID, different properties (if include_properties)
            - Relationships compared by (source, type, target) triple

        Performance:
            - Fast mode (detailed=False): ~1 sec per 10K nodes
            - Detailed mode: ~5 sec per 10K nodes
            - Property comparison adds ~50% overhead

        Example:
            diff = await service.compare_layers(
                "default",
                "scaled-v1",
                detailed=True
            )

            print(f"Nodes removed: {diff.nodes_removed}")
            print(f"Change: {diff.change_percentage:.1f}%")

            if diff.change_percentage > 50:
                print("Warning: Major topology change!")
        """
        pass

    @abstractmethod
    async def refresh_layer_stats(self, layer_id: str) -> LayerMetadata:
        """
        Recalculate node_count and relationship_count.

        Args:
            layer_id: Layer to refresh

        Returns:
            Updated LayerMetadata

        Raises:
            LayerNotFoundError: If layer doesn't exist

        Use Cases:
            - After bulk operations
            - After manual graph modifications
            - Validate metadata accuracy

        Example:
            # After bulk merge
            await scale_service.merge_vnets(...)
            layer = await service.refresh_layer_stats("scaled-v1")
            print(f"Final count: {layer.node_count} nodes")
        """
        pass

    # ===== Validation =====

    @abstractmethod
    async def validate_layer_integrity(
        self,
        layer_id: str,
        fix_issues: bool = False
    ) -> LayerValidationReport:
        """
        Validate layer integrity and optionally fix issues.

        Args:
            layer_id: Layer to validate
            fix_issues: Attempt automatic fixes

        Returns:
            LayerValidationReport with findings

        Raises:
            LayerNotFoundError: If layer doesn't exist

        Validation Checks:
            1. All :Resource nodes have SCAN_SOURCE_NODE links
            2. No relationships crossing layer boundaries
            3. No orphaned relationships (dangling references)
            4. Node count matches metadata
            5. Relationship count matches metadata
            6. All SCAN_SOURCE_NODE targets exist
            7. No duplicate (id, layer_id) combinations

        Auto-Fix Actions (if fix_issues=True):
            - Remove orphaned relationships
            - Fix metadata counts
            - Cannot fix: missing SCAN_SOURCE_NODE (requires re-scan)

        Example:
            report = await service.validate_layer_integrity("scaled-v1")

            if not report.is_valid:
                print(f"Found {report.checks_failed} issues:")
                for issue in report.issues:
                    print(f"  - {issue['message']}")

                # Try auto-fix
                report = await service.validate_layer_integrity(
                    "scaled-v1",
                    fix_issues=True
                )
        """
        pass

    # ===== Utility =====

    @abstractmethod
    async def archive_layer(
        self,
        layer_id: str,
        output_path: str,
        include_original: bool = False
    ) -> str:
        """
        Export layer to JSON file.

        Args:
            layer_id: Layer to archive
            output_path: File path for JSON output
            include_original: Include :Original nodes

        Returns:
            Path to created archive file

        Archive Format:
            {
                "metadata": {...},
                "nodes": [...],
                "relationships": [...]
            }

        Example:
            path = await service.archive_layer(
                "scaled-v1",
                "/backups/scaled-v1-20251116.json"
            )

            # Can delete from graph after archive
            await service.delete_layer("scaled-v1")
        """
        pass

    @abstractmethod
    async def restore_layer(
        self,
        archive_path: str,
        target_layer_id: Optional[str] = None
    ) -> LayerMetadata:
        """
        Restore layer from JSON archive.

        Args:
            archive_path: Path to archive file
            target_layer_id: Override layer ID (None = use archived ID)

        Returns:
            LayerMetadata of restored layer

        Example:
            layer = await service.restore_layer(
                "/backups/scaled-v1-20251116.json",
                target_layer_id="restored-scaled-v1"
            )
        """
        pass
```

## LayerAwareQueryService Interface

```python
class ILayerAwareQueryService(ABC):
    """
    Interface for querying resources with layer awareness.

    All queries default to active layer unless explicitly specified.
    Ensures layer isolation and prevents cross-layer contamination.
    """

    @abstractmethod
    async def get_resource(
        self,
        resource_id: str,
        layer_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get a resource from specified or active layer.

        Args:
            resource_id: Resource ID (abstracted ID, not Azure ID)
            layer_id: Specific layer, or None for active

        Returns:
            Resource properties dict, or None if not found

        Example:
            # From active layer
            resource = await service.get_resource("vm-a1b2c3d4")

            # From specific layer
            resource = await service.get_resource("vm-a1b2c3d4", layer_id="scaled-v1")
        """
        pass

    @abstractmethod
    async def find_resources(
        self,
        resource_type: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        layer_id: Optional[str] = None,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Find resources matching criteria in layer.

        Args:
            resource_type: Filter by type (e.g., "VirtualMachine")
            filters: Property filters {"name": "prod-vm-*", "location": "eastus"}
            layer_id: Specific layer, or None for active
            limit: Max results
            offset: Skip first N results

        Returns:
            List of resource dicts

        Example:
            # Find all VMs in active layer
            vms = await service.find_resources(resource_type="VirtualMachine")

            # Find VNets in specific region
            vnets = await service.find_resources(
                resource_type="VirtualNetwork",
                filters={"location": "eastus"}
            )
        """
        pass

    @abstractmethod
    async def traverse_relationships(
        self,
        start_resource_id: str,
        relationship_type: str,
        direction: str = "outgoing",
        layer_id: Optional[str] = None,
        depth: int = 1,
        include_path: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Traverse relationships within a layer.

        Args:
            start_resource_id: Starting node
            relationship_type: Relationship to follow (e.g., "CONTAINS")
            direction: "outgoing", "incoming", "both"
            layer_id: Layer to traverse
            depth: Max traversal depth
            include_path: Include full path in results

        Returns:
            List of connected resources

        Guarantees:
            - Never crosses layer boundaries
            - All returned nodes have same layer_id

        Example:
            # Find all VMs in a VNet
            vms = await service.traverse_relationships(
                start_resource_id="vnet-12345",
                relationship_type="CONTAINS",
                depth=2  # VNet -> Subnet -> VM
            )
        """
        pass

    @abstractmethod
    async def get_resource_original(
        self,
        resource_id: str,
        layer_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get the :Original node for a resource.

        Args:
            resource_id: Abstracted resource ID
            layer_id: Layer context

        Returns:
            Original node properties (with real Azure ID)

        Use Cases:
            - Cross-reference abstracted IDs to Azure IDs
            - Validate abstraction correctness
            - Debug ID translation

        Example:
            original = await service.get_resource_original("vm-a1b2c3d4")
            azure_id = original["id"]  # Real Azure resource ID
        """
        pass

    @abstractmethod
    async def count_resources(
        self,
        resource_type: Optional[str] = None,
        layer_id: Optional[str] = None
    ) -> int:
        """
        Count resources in layer.

        Args:
            resource_type: Filter by type (None = all types)
            layer_id: Layer to count

        Returns:
            Resource count

        Example:
            total = await service.count_resources()
            vms = await service.count_resources(resource_type="VirtualMachine")
        """
        pass
```

## Exception Hierarchy

```python
class LayerError(Exception):
    """Base exception for layer operations."""
    pass

class LayerNotFoundError(LayerError):
    """Layer does not exist."""
    def __init__(self, layer_id: str):
        super().__init__(f"Layer not found: {layer_id}")
        self.layer_id = layer_id

class LayerAlreadyExistsError(LayerError):
    """Layer already exists."""
    def __init__(self, layer_id: str):
        super().__init__(f"Layer already exists: {layer_id}")
        self.layer_id = layer_id

class LayerProtectedError(LayerError):
    """Cannot modify/delete protected layer."""
    def __init__(self, layer_id: str, reason: str):
        super().__init__(f"Layer protected: {layer_id} - {reason}")
        self.layer_id = layer_id
        self.reason = reason

class LayerLockedError(LayerError):
    """Layer is locked for modifications."""
    def __init__(self, layer_id: str):
        super().__init__(f"Layer locked: {layer_id}")
        self.layer_id = layer_id

class InvalidLayerIdError(LayerError):
    """Layer ID format invalid."""
    def __init__(self, layer_id: str, reason: str):
        super().__init__(f"Invalid layer ID '{layer_id}': {reason}")
        self.layer_id = layer_id
        self.reason = reason

class LayerIntegrityError(LayerError):
    """Layer integrity validation failed."""
    def __init__(self, layer_id: str, issues: List[str]):
        super().__init__(f"Layer integrity errors: {layer_id}")
        self.layer_id = layer_id
        self.issues = issues

class CrossLayerRelationshipError(LayerError):
    """Attempted to create relationship across layers."""
    def __init__(self, source_layer: str, target_layer: str):
        super().__init__(f"Cross-layer relationship: {source_layer} -> {target_layer}")
        self.source_layer = source_layer
        self.target_layer = target_layer
```

## Usage Examples

### Complete Workflow Example

```python
# Initialize services
layer_service = LayerManagementService(neo4j_driver)
query_service = LayerAwareQueryService(neo4j_driver, layer_service)
scale_service = ScaleOperationsService(neo4j_driver, layer_service, query_service)

# 1. Check current state
active = await layer_service.get_active_layer()
print(f"Active layer: {active.name} ({active.node_count} nodes)")

# 2. Create experimental layer by copying baseline
experiment = await layer_service.copy_layer(
    source_layer_id="default",
    target_layer_id="experiment-aggressive",
    name="Aggressive Consolidation",
    description="Testing 10:1 VM consolidation"
)

# 3. Perform scale operations on experimental layer
await scale_service.merge_vnets(
    vnet_ids=["vnet-1", "vnet-2", "vnet-3"],
    source_layer_id="experiment-aggressive",
    target_layer_id="experiment-aggressive-merged",
    make_active=False  # Don't activate yet
)

# 4. Compare with baseline
diff = await layer_service.compare_layers(
    "default",
    "experiment-aggressive-merged",
    detailed=True
)

print(f"Reduced nodes by {diff.nodes_removed} ({diff.change_percentage:.1f}%)")

# 5. Validate new layer
report = await layer_service.validate_layer_integrity("experiment-aggressive-merged")
if not report.is_valid:
    print("Validation failed!")
    for issue in report.issues:
        print(f"  - {issue['message']}")
    return

# 6. Generate IaC from both layers for comparison
default_iac = await iac_service.generate(layer_id="default")
experimental_iac = await iac_service.generate(layer_id="experiment-aggressive-merged")

# 7. If satisfied, make experimental layer active
await layer_service.set_active_layer("experiment-aggressive-merged")

# 8. Archive old experimental layers
await layer_service.archive_layer(
    "experiment-aggressive",
    "/backups/experiment-aggressive-20251116.json"
)
await layer_service.delete_layer("experiment-aggressive")

print("Workflow complete!")
```

## Implementation Notes

### Transaction Management

All layer operations should use Neo4j transactions:

```python
async def set_active_layer(self, layer_id: str) -> LayerMetadata:
    async with self.driver.session() as session:
        async with session.begin_transaction() as tx:
            # 1. Deactivate current active
            await tx.run("""
                MATCH (l:Layer {is_active: true})
                SET l.is_active = false
            """)

            # 2. Activate new layer
            result = await tx.run("""
                MATCH (l:Layer {layer_id: $layer_id})
                SET l.is_active = true,
                    l.updated_at = datetime()
                RETURN l
            """, layer_id=layer_id)

            # 3. Commit atomically
            await tx.commit()
```

### Performance Optimization

Layer copy should use batching:

```python
async def copy_layer(self, source_layer_id: str, target_layer_id: str, ...) -> LayerMetadata:
    # Copy nodes in batches
    offset = 0
    batch_size = 1000

    while True:
        result = await session.run("""
            MATCH (r:Resource {layer_id: $source_layer_id})
            RETURN r
            SKIP $offset
            LIMIT $batch_size
        """, source_layer_id=source_layer_id, offset=offset, batch_size=batch_size)

        nodes = await result.data()
        if not nodes:
            break

        # Create new nodes with target layer_id
        # ... batch creation logic ...

        offset += batch_size
        if progress_callback:
            progress_callback(offset, total_nodes)
```

### Error Handling

All public methods should validate inputs and provide clear errors:

```python
async def delete_layer(self, layer_id: str, force: bool = False) -> bool:
    # Check existence
    layer = await self.get_layer(layer_id)
    if not layer:
        raise LayerNotFoundError(layer_id)

    # Check protection
    if layer.is_locked:
        raise LayerLockedError(layer_id)

    if layer.is_active and not force:
        raise LayerProtectedError(layer_id, "Cannot delete active layer without force=True")

    if layer.is_baseline and not force:
        raise LayerProtectedError(layer_id, "Cannot delete baseline layer without force=True")

    # Proceed with deletion...
```

---

**These interfaces form the contract for implementation. Any implementation of these services must fulfill these contracts exactly.**

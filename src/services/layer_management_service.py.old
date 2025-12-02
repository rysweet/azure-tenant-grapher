"""
Layer Management Service

This service implements CRUD operations on graph layers (multi-layer projections).
Each layer represents a separate view of the Azure tenant graph, enabling
non-destructive scale operations and experimentation.

Architecture:
- Layers are metadata nodes (:Layer) in Neo4j
- Each :Resource node has a layer_id property
- Layers track node counts, relationships, provenance
- Active layer concept for default operations

Thread Safety: All methods are thread-safe via Neo4j transactions
Error Handling: Raises specific LayerError subclasses
"""

import json
import logging
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from neo4j.exceptions import Neo4jError

from src.utils.session_manager import Neo4jSessionManager

logger = logging.getLogger(__name__)


# =============================================================================
# Data Models and Enums
# =============================================================================


class LayerType(Enum):
    """Classification of layer purpose."""

    BASELINE = "baseline"  # Original 1:1 abstraction from scan
    SCALED = "scaled"  # Result of merge/split operations
    EXPERIMENTAL = "experimental"  # Sandbox for testing
    SNAPSHOT = "snapshot"  # Point-in-time backup


class LayerMetadata:
    """Complete metadata for a graph layer."""

    def __init__(
        self,
        layer_id: str,
        name: str,
        description: str,
        created_at: datetime,
        updated_at: Optional[datetime] = None,
        created_by: str = "unknown",
        parent_layer_id: Optional[str] = None,
        is_active: bool = False,
        is_baseline: bool = False,
        is_locked: bool = False,
        tenant_id: str = "unknown",
        subscription_ids: Optional[List[str]] = None,
        node_count: int = 0,
        relationship_count: int = 0,
        layer_type: LayerType = LayerType.EXPERIMENTAL,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
    ):
        self.layer_id = layer_id
        self.name = name
        self.description = description
        self.created_at = created_at
        self.updated_at = updated_at
        self.created_by = created_by
        self.parent_layer_id = parent_layer_id
        self.is_active = is_active
        self.is_baseline = is_baseline
        self.is_locked = is_locked
        self.tenant_id = tenant_id
        self.subscription_ids = subscription_ids or []
        self.node_count = node_count
        self.relationship_count = relationship_count
        self.layer_type = layer_type
        self.metadata = metadata or {}
        self.tags = tags or []

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "layer_id": self.layer_id,
            "name": self.name,
            "description": self.description,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "created_by": self.created_by,
            "parent_layer_id": self.parent_layer_id,
            "is_active": self.is_active,
            "is_baseline": self.is_baseline,
            "is_locked": self.is_locked,
            "tenant_id": self.tenant_id,
            "subscription_ids": self.subscription_ids,
            "node_count": self.node_count,
            "relationship_count": self.relationship_count,
            "layer_type": self.layer_type.value,
            "metadata": self.metadata,
            "tags": self.tags,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LayerMetadata":
        """Create from dictionary representation."""
        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)

        updated_at = data.get("updated_at")
        if isinstance(updated_at, str):
            updated_at = datetime.fromisoformat(updated_at)

        layer_type_str = data.get("layer_type", "experimental")
        layer_type = LayerType(layer_type_str)

        return cls(
            layer_id=data["layer_id"],
            name=data["name"],
            description=data["description"],
            created_at=created_at,
            updated_at=updated_at,
            created_by=data.get("created_by", "unknown"),
            parent_layer_id=data.get("parent_layer_id"),
            is_active=data.get("is_active", False),
            is_baseline=data.get("is_baseline", False),
            is_locked=data.get("is_locked", False),
            tenant_id=data.get("tenant_id", "unknown"),
            subscription_ids=data.get("subscription_ids", []),
            node_count=data.get("node_count", 0),
            relationship_count=data.get("relationship_count", 0),
            layer_type=layer_type,
            metadata=data.get("metadata", {}),
            tags=data.get("tags", []),
        )


class LayerDiff:
    """Comparison result between two layers."""

    def __init__(
        self,
        layer_a_id: str,
        layer_b_id: str,
        compared_at: datetime,
        nodes_added: int,
        nodes_removed: int,
        nodes_modified: int,
        nodes_unchanged: int,
        relationships_added: int,
        relationships_removed: int,
        relationships_modified: int,
        relationships_unchanged: int,
        added_node_ids: Optional[List[str]] = None,
        removed_node_ids: Optional[List[str]] = None,
        modified_node_ids: Optional[List[str]] = None,
        property_changes: Optional[Dict[str, Any]] = None,
        total_changes: int = 0,
        change_percentage: float = 0.0,
    ):
        self.layer_a_id = layer_a_id
        self.layer_b_id = layer_b_id
        self.compared_at = compared_at
        self.nodes_added = nodes_added
        self.nodes_removed = nodes_removed
        self.nodes_modified = nodes_modified
        self.nodes_unchanged = nodes_unchanged
        self.relationships_added = relationships_added
        self.relationships_removed = relationships_removed
        self.relationships_modified = relationships_modified
        self.relationships_unchanged = relationships_unchanged
        self.added_node_ids = added_node_ids or []
        self.removed_node_ids = removed_node_ids or []
        self.modified_node_ids = modified_node_ids or []
        self.property_changes = property_changes or {}
        self.total_changes = total_changes
        self.change_percentage = change_percentage


class LayerValidationReport:
    """Validation results for layer integrity."""

    def __init__(
        self,
        layer_id: str,
        validated_at: datetime,
        is_valid: bool,
        checks_passed: int = 0,
        checks_failed: int = 0,
        checks_warned: int = 0,
        issues: Optional[List[Dict[str, Any]]] = None,
        warnings: Optional[List[Dict[str, Any]]] = None,
        orphaned_nodes: int = 0,
        orphaned_relationships: int = 0,
        cross_layer_relationships: int = 0,
        missing_scan_source_nodes: int = 0,
    ):
        self.layer_id = layer_id
        self.validated_at = validated_at
        self.is_valid = is_valid
        self.checks_passed = checks_passed
        self.checks_failed = checks_failed
        self.checks_warned = checks_warned
        self.issues = issues or []
        self.warnings = warnings or []
        self.orphaned_nodes = orphaned_nodes
        self.orphaned_relationships = orphaned_relationships
        self.cross_layer_relationships = cross_layer_relationships
        self.missing_scan_source_nodes = missing_scan_source_nodes

    def add_error(
        self, code: str, message: str, details: Optional[Dict[str, Any]] = None
    ):
        """Add validation error."""
        self.issues.append(
            {
                "level": "error",
                "code": code,
                "message": message,
                "details": details or {},
            }
        )
        self.checks_failed += 1
        self.is_valid = False

    def add_warning(
        self, code: str, message: str, details: Optional[Dict[str, Any]] = None
    ):
        """Add validation warning."""
        self.warnings.append(
            {
                "level": "warning",
                "code": code,
                "message": message,
                "details": details or {},
            }
        )
        self.checks_warned += 1


# =============================================================================
# Exception Hierarchy
# =============================================================================


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


# =============================================================================
# Layer Management Service
# =============================================================================


class LayerManagementService:
    """
    Service for layer management operations.

    Responsibilities:
    - CRUD operations on layers
    - Active layer management
    - Layer copying and comparison
    - Layer validation

    Thread Safety: Methods are thread-safe via Neo4j transactions
    Error Handling: Raises specific LayerError subclasses
    """

    def __init__(self, session_manager: Neo4jSessionManager):
        """
        Initialize the layer management service.

        Args:
            session_manager: Neo4j session manager for database operations
        """
        self.session_manager = session_manager
        self.logger = logging.getLogger(__name__)
        self._ensure_layer_schema()

    def _ensure_layer_schema(self) -> None:
        """Ensure Layer node schema exists with indexes and constraints."""
        try:
            with self.session_manager.session() as session:
                # Create unique constraint on layer_id
                session.run(
                    "CREATE CONSTRAINT layer_id_unique IF NOT EXISTS "
                    "FOR (l:Layer) REQUIRE l.layer_id IS UNIQUE"
                )

                # Create indexes for common queries
                session.run(
                    "CREATE INDEX layer_tenant_id IF NOT EXISTS "
                    "FOR (l:Layer) ON (l.tenant_id)"
                )
                session.run(
                    "CREATE INDEX layer_is_active IF NOT EXISTS "
                    "FOR (l:Layer) ON (l.is_active)"
                )
                session.run(
                    "CREATE INDEX layer_type IF NOT EXISTS "
                    "FOR (l:Layer) ON (l.layer_type)"
                )

            self.logger.debug("Layer schema ensured")
        except Neo4jError as e:
            self.logger.warning(f"Failed to ensure layer schema: {e}")

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
        make_active: bool = False,
    ) -> LayerMetadata:
        """
        Create a new layer metadata node.

        Args:
            layer_id: Unique identifier
            name: Human-readable name
            description: Purpose and context
            created_by: Operation name
            parent_layer_id: Source layer if derived
            layer_type: Classification
            tenant_id: Azure tenant ID
            metadata: Arbitrary key-value pairs
            make_active: Set as active layer immediately

        Returns:
            LayerMetadata object for created layer

        Raises:
            LayerAlreadyExistsError: If layer_id already exists
            InvalidLayerIdError: If layer_id format invalid
            ValueError: If parent_layer_id doesn't exist
        """
        # Validate layer ID format
        if not layer_id or len(layer_id) > 200:
            raise InvalidLayerIdError(layer_id, "Layer ID must be 1-200 characters")

        # Check if layer already exists
        existing = await self.get_layer(layer_id)
        if existing:
            raise LayerAlreadyExistsError(layer_id)

        # Validate parent layer if specified
        if parent_layer_id:
            parent = await self.get_layer(parent_layer_id)
            if not parent:
                raise ValueError(f"Parent layer not found: {parent_layer_id}")

        # Create layer metadata
        created_at = datetime.utcnow()

        with self.session_manager.session() as session:
            # Deactivate current active layer if make_active=True
            if make_active:
                session.run(
                    """
                    MATCH (l:Layer)
                    WHERE l.is_active = true
                    SET l.is_active = false, l.updated_at = datetime()
                    """
                )

            # Create new layer node
            query = """
            CREATE (l:Layer {
                layer_id: $layer_id,
                name: $name,
                description: $description,
                created_at: datetime($created_at),
                updated_at: null,
                created_by: $created_by,
                parent_layer_id: $parent_layer_id,
                is_active: $is_active,
                is_baseline: $is_baseline,
                is_locked: false,
                tenant_id: $tenant_id,
                subscription_ids: $subscription_ids,
                node_count: 0,
                relationship_count: 0,
                layer_type: $layer_type,
                metadata: $metadata,
                tags: $tags
            })
            RETURN l
            """

            result = session.run(
                query,
                {
                    "layer_id": layer_id,
                    "name": name,
                    "description": description,
                    "created_at": created_at.isoformat(),
                    "created_by": created_by,
                    "parent_layer_id": parent_layer_id,
                    "is_active": make_active,
                    "is_baseline": layer_type == LayerType.BASELINE,
                    "tenant_id": tenant_id or "unknown",
                    "subscription_ids": [],
                    "layer_type": layer_type.value,
                    "metadata": json.dumps(metadata or {}),
                    "tags": [],
                },
            )

            record = result.single()
            if not record:
                raise LayerError(f"Failed to create layer: {layer_id}")

            # Create DERIVED_FROM relationship if parent specified
            if parent_layer_id:
                session.run(
                    """
                    MATCH (child:Layer {layer_id: $child_id})
                    MATCH (parent:Layer {layer_id: $parent_id})
                    CREATE (child)-[:DERIVED_FROM]->(parent)
                    """,
                    {"child_id": layer_id, "parent_id": parent_layer_id},
                )

        self.logger.info(f"Created layer: {layer_id} (active={make_active})")

        return LayerMetadata(
            layer_id=layer_id,
            name=name,
            description=description,
            created_at=created_at,
            created_by=created_by,
            parent_layer_id=parent_layer_id,
            is_active=make_active,
            is_baseline=layer_type == LayerType.BASELINE,
            tenant_id=tenant_id or "unknown",
            layer_type=layer_type,
            metadata=metadata or {},
        )

    async def list_layers(
        self,
        tenant_id: Optional[str] = None,
        include_inactive: bool = True,
        layer_type: Optional[LayerType] = None,
        tags: Optional[List[str]] = None,
        sort_by: str = "created_at",
        ascending: bool = False,
    ) -> List[LayerMetadata]:
        """
        List layers with optional filtering.

        Args:
            tenant_id: Filter by tenant
            include_inactive: Include non-active layers
            layer_type: Filter by type
            tags: Filter by tags (AND logic)
            sort_by: Sort field
            ascending: Sort order

        Returns:
            List of LayerMetadata objects
        """
        query_parts = ["MATCH (l:Layer)"]
        where_clauses = []
        params = {}

        # Build WHERE clauses
        if tenant_id:
            where_clauses.append("l.tenant_id = $tenant_id")
            params["tenant_id"] = tenant_id

        if not include_inactive:
            where_clauses.append("l.is_active = true")

        if layer_type:
            where_clauses.append("l.layer_type = $layer_type")
            params["layer_type"] = layer_type.value

        if where_clauses:
            query_parts.append("WHERE " + " AND ".join(where_clauses))

        # Add RETURN clause
        query_parts.append("RETURN l")

        # Add ORDER BY
        sort_order = "ASC" if ascending else "DESC"
        query_parts.append(f"ORDER BY l.{sort_by} {sort_order}")

        query = "\n".join(query_parts)

        with self.session_manager.session() as session:
            result = session.run(query, params)

            layers = []
            for record in result:
                node = record["l"]
                layer = self._node_to_layer_metadata(node)

                # Apply tag filtering (post-query since tags are list)
                if tags:
                    if all(tag in layer.tags for tag in tags):
                        layers.append(layer)
                else:
                    layers.append(layer)

            return layers

    async def get_layer(self, layer_id: str) -> Optional[LayerMetadata]:
        """
        Get metadata for a specific layer.

        Args:
            layer_id: Layer identifier

        Returns:
            LayerMetadata if found, None otherwise
        """
        query = "MATCH (l:Layer {layer_id: $layer_id}) RETURN l"

        with self.session_manager.session() as session:
            result = session.run(query, {"layer_id": layer_id})
            record = result.single()

            if not record:
                return None

            return self._node_to_layer_metadata(record["l"])

    async def get_active_layer(
        self, tenant_id: Optional[str] = None
    ) -> Optional[LayerMetadata]:
        """
        Get the currently active layer.

        Args:
            tenant_id: Tenant context (for multi-tenant support)

        Returns:
            LayerMetadata of active layer, None if no active layer
        """
        query_parts = ["MATCH (l:Layer)", "WHERE l.is_active = true"]
        params = {}

        if tenant_id:
            query_parts[1] += " AND l.tenant_id = $tenant_id"
            params["tenant_id"] = tenant_id

        query_parts.append("RETURN l LIMIT 1")
        query = "\n".join(query_parts)

        with self.session_manager.session() as session:
            result = session.run(query, params)
            record = result.single()

            if not record:
                return None

            return self._node_to_layer_metadata(record["l"])

    async def update_layer(
        self,
        layer_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        is_locked: Optional[bool] = None,
    ) -> LayerMetadata:
        """
        Update layer metadata.

        Args:
            layer_id: Layer to update
            name: New name
            description: New description
            tags: New tags
            metadata: Update metadata (merged with existing)
            is_locked: Lock/unlock layer

        Returns:
            Updated LayerMetadata

        Raises:
            LayerNotFoundError: If layer doesn't exist
            LayerLockedError: If trying to modify locked layer
        """
        # Check layer exists
        layer = await self.get_layer(layer_id)
        if not layer:
            raise LayerNotFoundError(layer_id)

        # Check if locked (unless we're unlocking it)
        if layer.is_locked and is_locked:
            raise LayerLockedError(layer_id)

        # Build safe SET clause using helper to prevent Cypher injection

        # Define allowed update keys for layers (whitelist)
        ALLOWED_UPDATE_KEYS = {
            "name",
            "description",
            "tags",
            "metadata",
            "is_locked",
            "updated_at",
        }

        # Build updates dictionary
        updates_dict = {"updated_at": "datetime()"}  # Special case: datetime() function
        params = {"layer_id": layer_id}

        if name is not None:
            updates_dict["name"] = name
        if description is not None:
            updates_dict["description"] = description
        if tags is not None:
            updates_dict["tags"] = tags
        if metadata is not None:
            # Merge with existing metadata
            merged_metadata = {**layer.metadata, **metadata}
            updates_dict["metadata"] = json.dumps(merged_metadata)
        if is_locked is not None:
            updates_dict["is_locked"] = is_locked

        # Build safe SET clause (prevents injection via property names)
        set_clauses = []
        for key, value in updates_dict.items():
            if key not in ALLOWED_UPDATE_KEYS:
                raise ValueError(f"Invalid update key: {key}")
            if key == "updated_at" and value == "datetime()":
                # Special handling for datetime() function
                set_clauses.append("l.updated_at = datetime()")
            else:
                set_clauses.append(f"l.{key} = ${key}")
                params[key] = value

        set_clause_str = ", ".join(set_clauses)

        query = f"""
        MATCH (l:Layer {{layer_id: $layer_id}})
        SET {set_clause_str}
        RETURN l
        """

        with self.session_manager.session() as session:
            result = session.run(query, params)
            record = result.single()

            if not record:
                raise LayerNotFoundError(layer_id)

            return self._node_to_layer_metadata(record["l"])

    async def delete_layer(self, layer_id: str, force: bool = False) -> bool:
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
        """
        # Check layer exists
        layer = await self.get_layer(layer_id)
        if not layer:
            return False

        # Check protections
        if layer.is_locked:
            raise LayerLockedError(layer_id)

        if layer.is_active and not force:
            raise LayerProtectedError(
                layer_id, "Cannot delete active layer without force=True"
            )

        if layer.is_baseline and not force:
            raise LayerProtectedError(
                layer_id, "Cannot delete baseline layer without force=True"
            )

        with self.session_manager.session() as session:
            # Delete all Resource nodes with this layer_id
            session.run(
                """
                MATCH (r:Resource)
                WHERE NOT r:Original AND r.layer_id = $layer_id
                DETACH DELETE r
                """,
                {"layer_id": layer_id},
            )

            # Delete Layer metadata node
            session.run(
                "MATCH (l:Layer {layer_id: $layer_id}) DETACH DELETE l",
                {"layer_id": layer_id},
            )

        self.logger.info(f"Deleted layer: {layer_id}")
        return True

    async def set_active_layer(
        self, layer_id: str, tenant_id: Optional[str] = None
    ) -> LayerMetadata:
        """
        Switch the active layer.

        Args:
            layer_id: Layer to activate
            tenant_id: Tenant context

        Returns:
            Updated LayerMetadata

        Raises:
            LayerNotFoundError: If layer_id doesn't exist
        """
        # Check layer exists
        layer = await self.get_layer(layer_id)
        if not layer:
            raise LayerNotFoundError(layer_id)

        with self.session_manager.session() as session:
            # Atomic transaction to ensure only one active layer
            session.run(
                """
                MATCH (l:Layer)
                WHERE l.is_active = true
                SET l.is_active = false, l.updated_at = datetime()
                """
            )

            session.run(
                """
                MATCH (l:Layer {layer_id: $layer_id})
                SET l.is_active = true, l.updated_at = datetime()
                """,
                {"layer_id": layer_id},
            )

        self.logger.info(f"Set active layer: {layer_id}")

        # Return updated metadata
        return await self.get_layer(layer_id)

    async def copy_layer(
        self,
        source_layer_id: str,
        target_layer_id: str,
        name: str,
        description: str,
        copy_metadata: bool = True,
        batch_size: int = 1000,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> LayerMetadata:
        """
        Copy an entire layer (nodes + relationships).

        Args:
            source_layer_id: Layer to copy from
            target_layer_id: New layer ID
            name: Name for new layer
            description: Description for new layer
            copy_metadata: Copy metadata dict from source
            batch_size: Nodes per batch
            progress_callback: Called with (current, total)

        Returns:
            LayerMetadata for new layer

        Raises:
            LayerNotFoundError: If source doesn't exist
            LayerAlreadyExistsError: If target exists
        """
        # Validate source exists
        source_layer = await self.get_layer(source_layer_id)
        if not source_layer:
            raise LayerNotFoundError(source_layer_id)

        # Check target doesn't exist
        if await self.get_layer(target_layer_id):
            raise LayerAlreadyExistsError(target_layer_id)

        # Create target layer metadata
        target_metadata = source_layer.metadata if copy_metadata else {}

        await self.create_layer(
            layer_id=target_layer_id,
            name=name,
            description=description,
            created_by="copy_layer",
            parent_layer_id=source_layer_id,
            layer_type=LayerType.EXPERIMENTAL,
            tenant_id=source_layer.tenant_id,
            metadata=target_metadata,
            make_active=False,
        )

        # Copy nodes in batches
        with self.session_manager.session() as session:
            # Count total nodes
            result = session.run(
                """
                MATCH (r:Resource)
                WHERE NOT r:Original AND r.layer_id = $source_layer_id
                RETURN count(r) as total
                """,
                {"source_layer_id": source_layer_id},
            )
            total_nodes = result.single()["total"]

            copied_nodes = 0
            skip = 0

            while skip < total_nodes:
                # Copy batch of nodes
                session.run(
                    """
                    MATCH (r:Resource)
                    WHERE NOT r:Original AND r.layer_id = $source_layer_id
                    WITH r
                    SKIP $skip
                    LIMIT $batch_size
                    CREATE (new:Resource)
                    SET new = properties(r),
                        new.layer_id = $target_layer_id
                    """,
                    {
                        "source_layer_id": source_layer_id,
                        "target_layer_id": target_layer_id,
                        "skip": skip,
                        "batch_size": batch_size,
                    },
                )

                copied_nodes += min(batch_size, total_nodes - skip)
                skip += batch_size

                if progress_callback:
                    progress_callback(copied_nodes, total_nodes)

            # Copy relationships
            session.run(
                """
                MATCH (r1:Resource)-[rel]->(r2:Resource)
                WHERE NOT r1:Original AND NOT r2:Original
                  AND r1.layer_id = $source_layer_id
                  AND r2.layer_id = $source_layer_id
                  AND type(rel) <> 'SCAN_SOURCE_NODE'
                WITH r1, r2, rel
                MATCH (new1:Resource {id: r1.id, layer_id: $target_layer_id})
                MATCH (new2:Resource {id: r2.id, layer_id: $target_layer_id})
                WITH new1, new2, type(rel) as rel_type, properties(rel) as rel_props
                CALL apoc.create.relationship(new1, rel_type, rel_props, new2) YIELD rel as new_rel
                RETURN count(new_rel)
                """,
                {
                    "source_layer_id": source_layer_id,
                    "target_layer_id": target_layer_id,
                },
            )

        # Refresh stats
        await self.refresh_layer_stats(target_layer_id)

        self.logger.info(
            f"Copied layer {source_layer_id} to {target_layer_id} ({copied_nodes} nodes)"
        )

        return await self.get_layer(target_layer_id)

    async def compare_layers(
        self,
        layer_a_id: str,
        layer_b_id: str,
        detailed: bool = False,
        include_properties: bool = False,
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
        """
        # Validate both layers exist
        layer_a = await self.get_layer(layer_a_id)
        layer_b = await self.get_layer(layer_b_id)

        if not layer_a:
            raise LayerNotFoundError(layer_a_id)
        if not layer_b:
            raise LayerNotFoundError(layer_b_id)

        with self.session_manager.session() as session:
            # Count nodes in each layer
            nodes_a_result = session.run(
                """
                MATCH (r:Resource)
                WHERE NOT r:Original AND r.layer_id = $layer_id
                RETURN collect(r.id) as ids, count(r) as count
                """,
                {"layer_id": layer_a_id},
            )
            nodes_a_record = nodes_a_result.single()
            nodes_a_ids = set(nodes_a_record["ids"])
            nodes_a_count = nodes_a_record["count"]

            nodes_b_result = session.run(
                """
                MATCH (r:Resource)
                WHERE NOT r:Original AND r.layer_id = $layer_id
                RETURN collect(r.id) as ids, count(r) as count
                """,
                {"layer_id": layer_b_id},
            )
            nodes_b_record = nodes_b_result.single()
            nodes_b_ids = set(nodes_b_record["ids"])
            nodes_b_count = nodes_b_record["count"]

            # Calculate differences
            added_ids = nodes_b_ids - nodes_a_ids
            removed_ids = nodes_a_ids - nodes_b_ids
            common_ids = nodes_a_ids & nodes_b_ids

            # Count relationships
            rels_a = session.run(
                """
                MATCH (r1:Resource)-[rel]->(r2:Resource)
                WHERE NOT r1:Original AND NOT r2:Original
                  AND r1.layer_id = $layer_id
                  AND r2.layer_id = $layer_id
                  AND type(rel) <> 'SCAN_SOURCE_NODE'
                RETURN count(rel) as count
                """,
                {"layer_id": layer_a_id},
            ).single()["count"]

            rels_b = session.run(
                """
                MATCH (r1:Resource)-[rel]->(r2:Resource)
                WHERE NOT r1:Original AND NOT r2:Original
                  AND r1.layer_id = $layer_id
                  AND r2.layer_id = $layer_id
                  AND type(rel) <> 'SCAN_SOURCE_NODE'
                RETURN count(rel) as count
                """,
                {"layer_id": layer_b_id},
            ).single()["count"]

        # Calculate change percentage
        total_nodes = max(nodes_a_count, nodes_b_count)
        total_changes = len(added_ids) + len(removed_ids)
        change_percentage = (
            (total_changes / total_nodes * 100) if total_nodes > 0 else 0.0
        )

        return LayerDiff(
            layer_a_id=layer_a_id,
            layer_b_id=layer_b_id,
            compared_at=datetime.utcnow(),
            nodes_added=len(added_ids),
            nodes_removed=len(removed_ids),
            nodes_modified=0,  # Would need property comparison
            nodes_unchanged=len(common_ids),
            relationships_added=max(0, rels_b - rels_a),
            relationships_removed=max(0, rels_a - rels_b),
            relationships_modified=0,
            relationships_unchanged=min(rels_a, rels_b),
            added_node_ids=list(added_ids) if detailed else [],
            removed_node_ids=list(removed_ids) if detailed else [],
            total_changes=total_changes,
            change_percentage=change_percentage,
        )

    async def refresh_layer_stats(self, layer_id: str) -> LayerMetadata:
        """
        Recalculate node_count and relationship_count.

        Args:
            layer_id: Layer to refresh

        Returns:
            Updated LayerMetadata

        Raises:
            LayerNotFoundError: If layer doesn't exist
        """
        layer = await self.get_layer(layer_id)
        if not layer:
            raise LayerNotFoundError(layer_id)

        with self.session_manager.session() as session:
            # Count nodes
            node_count = session.run(
                """
                MATCH (r:Resource)
                WHERE NOT r:Original AND r.layer_id = $layer_id
                RETURN count(r) as count
                """,
                {"layer_id": layer_id},
            ).single()["count"]

            # Count relationships
            rel_count = session.run(
                """
                MATCH (r1:Resource)-[rel]->(r2:Resource)
                WHERE NOT r1:Original AND NOT r2:Original
                  AND r1.layer_id = $layer_id
                  AND r2.layer_id = $layer_id
                  AND type(rel) <> 'SCAN_SOURCE_NODE'
                RETURN count(rel) as count
                """,
                {"layer_id": layer_id},
            ).single()["count"]

            # Update layer metadata
            session.run(
                """
                MATCH (l:Layer {layer_id: $layer_id})
                SET l.node_count = $node_count,
                    l.relationship_count = $rel_count,
                    l.updated_at = datetime()
                """,
                {
                    "layer_id": layer_id,
                    "node_count": node_count,
                    "rel_count": rel_count,
                },
            )

        self.logger.info(
            f"Refreshed stats for layer {layer_id}: {node_count} nodes, {rel_count} relationships"
        )

        return await self.get_layer(layer_id)

    async def validate_layer_integrity(
        self, layer_id: str, fix_issues: bool = False
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
        """
        layer = await self.get_layer(layer_id)
        if not layer:
            raise LayerNotFoundError(layer_id)

        report = LayerValidationReport(
            layer_id=layer_id,
            validated_at=datetime.utcnow(),
            is_valid=True,
        )

        with self.session_manager.session() as session:
            # Check 1: All Resource nodes have SCAN_SOURCE_NODE links
            missing_scan_source = session.run(
                """
                MATCH (r:Resource)
                WHERE NOT r:Original AND r.layer_id = $layer_id
                  AND NOT (r)-[:SCAN_SOURCE_NODE]->()
                RETURN count(r) as count
                """,
                {"layer_id": layer_id},
            ).single()["count"]

            if missing_scan_source > 0:
                report.add_error(
                    "MISSING_SCAN_SOURCE",
                    f"{missing_scan_source} nodes missing SCAN_SOURCE_NODE",
                    {"count": missing_scan_source},
                )
                report.missing_scan_source_nodes = missing_scan_source

            # Check 2: No cross-layer relationships
            cross_layer_rels = session.run(
                """
                MATCH (r1:Resource)-[rel]->(r2:Resource)
                WHERE NOT r1:Original AND NOT r2:Original
                  AND r1.layer_id = $layer_id
                  AND r2.layer_id <> $layer_id
                  AND type(rel) <> 'SCAN_SOURCE_NODE'
                RETURN count(rel) as count
                """,
                {"layer_id": layer_id},
            ).single()["count"]

            if cross_layer_rels > 0:
                report.add_error(
                    "CROSS_LAYER_RELS",
                    f"{cross_layer_rels} cross-layer relationships found",
                    {"count": cross_layer_rels},
                )
                report.cross_layer_relationships = cross_layer_rels

                if fix_issues:
                    # Delete cross-layer relationships
                    session.run(
                        """
                        MATCH (r1:Resource)-[rel]->(r2:Resource)
                        WHERE NOT r1:Original AND NOT r2:Original
                          AND r1.layer_id = $layer_id
                          AND r2.layer_id <> $layer_id
                          AND type(rel) <> 'SCAN_SOURCE_NODE'
                        DELETE rel
                        """,
                        {"layer_id": layer_id},
                    )
                    report.add_warning(
                        "CROSS_LAYER_RELS_FIXED",
                        f"Deleted {cross_layer_rels} cross-layer relationships",
                    )

            # Check 3: Node count matches metadata
            actual_node_count = session.run(
                """
                MATCH (r:Resource)
                WHERE NOT r:Original AND r.layer_id = $layer_id
                RETURN count(r) as count
                """,
                {"layer_id": layer_id},
            ).single()["count"]

            if actual_node_count != layer.node_count:
                report.add_warning(
                    "NODE_COUNT_MISMATCH",
                    f"Metadata says {layer.node_count}, actual is {actual_node_count}",
                    {"expected": layer.node_count, "actual": actual_node_count},
                )

                if fix_issues:
                    await self.refresh_layer_stats(layer_id)
                    report.add_warning("NODE_COUNT_FIXED", "Updated metadata counts")

            # Mark passed checks
            if not report.issues:
                report.checks_passed = 3
            else:
                report.checks_passed = 3 - len(report.issues)

        return report

    async def archive_layer(
        self,
        layer_id: str,
        output_path: str,
        include_original: bool = False,
    ) -> str:
        """
        Export layer to JSON file.

        Args:
            layer_id: Layer to archive
            output_path: File path for JSON output
            include_original: Include :Original nodes

        Returns:
            Path to created archive file
        """
        layer = await self.get_layer(layer_id)
        if not layer:
            raise LayerNotFoundError(layer_id)

        # Collect nodes and relationships
        nodes = []
        relationships = []

        with self.session_manager.session() as session:
            # Get nodes
            node_result = session.run(
                """
                MATCH (r:Resource)
                WHERE NOT r:Original AND r.layer_id = $layer_id
                RETURN r
                """,
                {"layer_id": layer_id},
            )

            for record in node_result:
                node = record["r"]
                nodes.append(dict(node))

            # Get relationships
            rel_result = session.run(
                """
                MATCH (r1:Resource)-[rel]->(r2:Resource)
                WHERE NOT r1:Original AND NOT r2:Original
                  AND r1.layer_id = $layer_id
                  AND r2.layer_id = $layer_id
                  AND type(rel) <> 'SCAN_SOURCE_NODE'
                RETURN r1.id as source, r2.id as target,
                       type(rel) as type, properties(rel) as props
                """,
                {"layer_id": layer_id},
            )

            for record in rel_result:
                relationships.append(
                    {
                        "source": record["source"],
                        "target": record["target"],
                        "type": record["type"],
                        "properties": dict(record["props"]),
                    }
                )

        # Write to file
        archive_data = {
            "metadata": layer.to_dict(),
            "nodes": nodes,
            "relationships": relationships,
        }

        with open(output_path, "w") as f:
            json.dump(archive_data, f, indent=2, default=str)

        self.logger.info(f"Archived layer {layer_id} to {output_path}")

        return output_path

    async def restore_layer(
        self,
        archive_path: str,
        target_layer_id: Optional[str] = None,
    ) -> LayerMetadata:
        """
        Restore layer from JSON archive.

        Args:
            archive_path: Path to archive file
            target_layer_id: Override layer ID

        Returns:
            LayerMetadata of restored layer
        """
        # Load archive
        with open(archive_path) as f:
            archive_data = json.load(f)

        metadata_dict = archive_data["metadata"]
        nodes = archive_data["nodes"]
        relationships = archive_data["relationships"]

        # Override layer_id if specified
        if target_layer_id:
            metadata_dict["layer_id"] = target_layer_id

        # Create layer
        layer_metadata = LayerMetadata.from_dict(metadata_dict)

        await self.create_layer(
            layer_id=layer_metadata.layer_id,
            name=layer_metadata.name,
            description=f"Restored from {archive_path}",
            created_by="restore_layer",
            layer_type=layer_metadata.layer_type,
            tenant_id=layer_metadata.tenant_id,
            metadata=layer_metadata.metadata,
        )

        # Restore nodes
        with self.session_manager.session() as session:
            for node in nodes:
                # Update layer_id if overridden
                if target_layer_id:
                    node["layer_id"] = target_layer_id

                # Create node
                session.run(
                    """
                    CREATE (r:Resource)
                    SET r = $props
                    """,
                    {"props": node},
                )

            # Restore relationships
            for rel in relationships:
                session.run(
                    """
                    MATCH (r1:Resource {id: $source, layer_id: $layer_id})
                    MATCH (r2:Resource {id: $target, layer_id: $layer_id})
                    WITH r1, r2
                    CALL apoc.create.relationship(r1, $rel_type, $props, r2) YIELD rel
                    RETURN rel
                    """,
                    {
                        "source": rel["source"],
                        "target": rel["target"],
                        "layer_id": layer_metadata.layer_id,
                        "rel_type": rel["type"],
                        "props": rel["properties"],
                    },
                )

        # Refresh stats
        await self.refresh_layer_stats(layer_metadata.layer_id)

        self.logger.info(
            f"Restored layer {layer_metadata.layer_id} from {archive_path}"
        )

        return await self.get_layer(layer_metadata.layer_id)

    def _node_to_layer_metadata(self, node) -> LayerMetadata:
        """Convert Neo4j node to LayerMetadata."""
        created_at = node.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        elif not isinstance(created_at, datetime):
            created_at = datetime.utcnow()

        updated_at = node.get("updated_at")
        if isinstance(updated_at, str):
            updated_at = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
        elif updated_at and not isinstance(updated_at, datetime):
            updated_at = datetime.utcnow()

        # Parse metadata JSON string
        metadata_str = node.get("metadata", "{}")
        if isinstance(metadata_str, str):
            try:
                metadata = json.loads(metadata_str)
            except json.JSONDecodeError:
                metadata = {}
        else:
            metadata = metadata_str

        # Parse layer type
        layer_type_str = node.get("layer_type", "experimental")
        try:
            layer_type = LayerType(layer_type_str)
        except ValueError:
            layer_type = LayerType.EXPERIMENTAL

        return LayerMetadata(
            layer_id=node["layer_id"],
            name=node["name"],
            description=node["description"],
            created_at=created_at,
            updated_at=updated_at,
            created_by=node.get("created_by", "unknown"),
            parent_layer_id=node.get("parent_layer_id"),
            is_active=node.get("is_active", False),
            is_baseline=node.get("is_baseline", False),
            is_locked=node.get("is_locked", False),
            tenant_id=node.get("tenant_id", "unknown"),
            subscription_ids=node.get("subscription_ids", []),
            node_count=node.get("node_count", 0),
            relationship_count=node.get("relationship_count", 0),
            layer_type=layer_type,
            metadata=metadata,
            tags=node.get("tags", []),
        )

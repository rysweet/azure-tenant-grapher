"""
Layer CRUD Operations Module

This module handles Create, Read, Update, Delete operations for layers.
Extracted from layer_management_service.py as part of modular refactoring.

Philosophy:
- Single responsibility: CRUD operations only
- Thread-safe via Neo4j transactions
- Clear error handling with specific exceptions
- Standard library only (no external dependencies beyond Neo4j)

Public API (the "studs"):
    LayerCrudOperations: Class handling CRUD operations for layers
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from neo4j.exceptions import Neo4jError

from src.services.layer.models import (
    InvalidLayerIdError,
    LayerAlreadyExistsError,
    LayerError,
    LayerLockedError,
    LayerMetadata,
    LayerNotFoundError,
    LayerProtectedError,
    LayerType,
)
from src.utils.session_manager import Neo4jSessionManager

logger = logging.getLogger(__name__)


class LayerCrudOperations:
    """
    Handles CRUD operations for layers.

    Responsibilities:
    - Create new layers
    - Read/list/get layers
    - Update layer metadata
    - Delete layers
    - Manage active layer state

    Thread Safety: All methods are thread-safe via Neo4j transactions
    """

    def __init__(self, session_manager: Neo4jSessionManager):
        """
        Initialize CRUD operations handler.

        Args:
            session_manager: Neo4j session manager for database operations
        """
        self.session_manager = session_manager
        self.logger = logging.getLogger(__name__)

    def ensure_schema(self) -> None:
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

    def node_to_layer_metadata(self, node) -> LayerMetadata:
        """
        Convert Neo4j node to LayerMetadata.

        Args:
            node: Neo4j node object

        Returns:
            LayerMetadata object
        """
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
                layer = self.node_to_layer_metadata(node)

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

            return self.node_to_layer_metadata(record["l"])

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

            return self.node_to_layer_metadata(record["l"])

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

            return self.node_to_layer_metadata(record["l"])

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


__all__ = ["LayerCrudOperations"]

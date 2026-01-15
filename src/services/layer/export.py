"""
Layer Export and Import Operations Module

This module handles export, import, copy, archive, and restore operations for layers.
Extracted from layer_management_service.py as part of modular refactoring.

Philosophy:
- Single responsibility: Export and import operations only
- Thread-safe via Neo4j transactions
- Clear error handling
- Standard library only (no external dependencies beyond Neo4j)

Public API (the "studs"):
    LayerExportOperations: Class handling export/import operations for layers
"""

import json
import logging
from typing import Callable, Optional

from src.services.layer.models import (
    LayerAlreadyExistsError,
    LayerMetadata,
    LayerNotFoundError,
    LayerType,
)
from src.utils.session_manager import Neo4jSessionManager

logger = logging.getLogger(__name__)


class LayerExportOperations:
    """
    Handles export, import, copy, archive, and restore operations for layers.

    Responsibilities:
    - Copy layers (nodes + relationships)
    - Archive layers to JSON files
    - Restore layers from JSON archives

    Thread Safety: All methods are thread-safe via Neo4j transactions
    """

    def __init__(
        self,
        session_manager: Neo4jSessionManager,
        crud_operations: Optional[object] = None,
        stats_operations: Optional[object] = None,
    ):
        """
        Initialize export operations handler.

        Args:
            session_manager: Neo4j session manager for database operations
            crud_operations: CRUD operations handler for layer metadata
            stats_operations: Stats operations handler for refreshing stats
        """
        self.session_manager = session_manager
        self.crud_operations = crud_operations
        self.stats_operations = stats_operations
        self.logger = logging.getLogger(__name__)

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
        # Validate source exists and target doesn't exist
        if self.crud_operations:
            source_layer = await self.crud_operations.get_layer(source_layer_id)
            if not source_layer:
                raise LayerNotFoundError(source_layer_id)

            if await self.crud_operations.get_layer(target_layer_id):
                raise LayerAlreadyExistsError(target_layer_id)

            # Create target layer metadata
            target_metadata = source_layer.metadata if copy_metadata else {}

            await self.crud_operations.create_layer(
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
            # NOTE: SCAN_SOURCE_NODE relationships are preserved to enable
            # proper resource classification during IaC generation.
            # These relationships link abstracted Resources to their original
            # Azure IDs, which is critical for smart import functionality.
            # See docs/architecture/scan-source-node-relationships.md
            #
            # Two types of relationships are copied:
            # 1. Within-layer relationships: Both nodes are layer nodes
            # 2. SCAN_SOURCE_NODE relationships: Source is layer node, target is Original
            session.run(
                """
                MATCH (r1:Resource)-[rel]->(r2:Resource)
                WHERE NOT r1:Original AND r1.layer_id = $source_layer_id
                  AND (
                    (NOT r2:Original AND r2.layer_id = $source_layer_id)
                    OR (r2:Original)
                  )
                WITH r1, r2, rel, type(rel) as rel_type
                MATCH (new1:Resource {id: r1.id, layer_id: $target_layer_id})
                WITH new1, r2, rel, rel_type, properties(rel) as rel_props
                OPTIONAL MATCH (new2:Resource {id: r2.id, layer_id: $target_layer_id})
                WHERE NOT r2:Original
                WITH new1, COALESCE(new2, r2) as target_node, rel_type, rel_props
                CALL apoc.create.relationship(new1, rel_type, rel_props, target_node) YIELD rel as new_rel
                RETURN count(new_rel)
                """,
                {
                    "source_layer_id": source_layer_id,
                    "target_layer_id": target_layer_id,
                },
            )

        # Refresh stats
        if self.stats_operations:
            await self.stats_operations.refresh_layer_stats(target_layer_id)

        self.logger.info(
            f"Copied layer {source_layer_id} to {target_layer_id} ({copied_nodes} nodes)"
        )

        # Return the target layer
        if self.crud_operations:
            return await self.crud_operations.get_layer(target_layer_id)

        # If no crud_operations, return minimal metadata
        from datetime import datetime, timezone

        return LayerMetadata(
            layer_id=target_layer_id,
            name=name,
            description=description,
            created_at=datetime.now(timezone.utc),
        )

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

        Raises:
            LayerNotFoundError: If layer doesn't exist
        """
        # Check if layer exists
        layer = None
        if self.crud_operations:
            layer = await self.crud_operations.get_layer(layer_id)
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
            # NOTE: SCAN_SOURCE_NODE relationships are included in archives
            # to preserve the connection between abstracted and original nodes.
            # This is essential for IaC generation workflows.
            #
            # Two types of relationships are archived:
            # 1. Within-layer relationships: Both nodes are layer nodes
            # 2. SCAN_SOURCE_NODE relationships: Source is layer node, target is Original
            rel_result = session.run(
                """
                MATCH (r1:Resource)-[rel]->(r2:Resource)
                WHERE NOT r1:Original AND r1.layer_id = $layer_id
                  AND (
                    (NOT r2:Original AND r2.layer_id = $layer_id)
                    OR (r2:Original)
                  )
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
            "version": "2.0",  # Version 2.0 includes SCAN_SOURCE_NODE
            "includes_scan_source_node": True,  # Flag for backward compat
            "metadata": layer.to_dict() if layer else {},
            "nodes": nodes,
            "relationships": relationships,
        }

        with open(output_path, "w") as f:
            json.dump(archive_data, f, indent=2, default=str)

        self.logger.info(str(f"Archived layer {layer_id} to {output_path}"))

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

        Raises:
            LayerAlreadyExistsError: If target layer already exists
        """
        # Load archive
        with open(archive_path) as f:
            archive_data = json.load(f)

        archive_version = archive_data.get("version", "1.0")
        includes_scan_source = archive_data.get("includes_scan_source_node", False)

        logger.info(
            f"Restoring layer from archive version {archive_version}, "
            f"includes_scan_source_node={includes_scan_source}"
        )

        metadata_dict = archive_data["metadata"]
        nodes = archive_data["nodes"]
        relationships = archive_data["relationships"]

        # Override layer_id if specified
        if target_layer_id:
            metadata_dict["layer_id"] = target_layer_id

        # Create layer
        layer_metadata = LayerMetadata.from_dict(metadata_dict)

        if self.crud_operations:
            await self.crud_operations.create_layer(
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
            # NOTE: SCAN_SOURCE_NODE relationships need special handling
            # because they target Original nodes (no layer_id filter)
            for rel in relationships:
                if rel["type"] == "SCAN_SOURCE_NODE":
                    # Special handling: target is Original node, no layer_id filter
                    session.run(
                        """
                        MATCH (r1:Resource {id: $source, layer_id: $layer_id})
                        MATCH (r2:Resource:Original {id: $target})
                        WITH r1, r2
                        CALL apoc.create.relationship(r1, $rel_type, $props, r2) YIELD rel
                        RETURN rel
                        """,
                        {
                            "source": rel["source"],
                            "target": rel["target"],
                            "layer_id": target_layer_id
                            if target_layer_id
                            else layer_metadata.layer_id,
                            "rel_type": rel["type"],
                            "props": rel["properties"],
                        },
                    )
                else:
                    # Regular within-layer relationships
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
                            "layer_id": target_layer_id
                            if target_layer_id
                            else layer_metadata.layer_id,
                            "rel_type": rel["type"],
                            "props": rel["properties"],
                        },
                    )

        # Refresh stats
        if self.stats_operations:
            await self.stats_operations.refresh_layer_stats(layer_metadata.layer_id)

        self.logger.info(
            f"Restored layer {layer_metadata.layer_id} from {archive_path}"
        )

        # Return restored layer
        if self.crud_operations:
            return await self.crud_operations.get_layer(layer_metadata.layer_id)

        return layer_metadata


__all__ = ["LayerExportOperations"]

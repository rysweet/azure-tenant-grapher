"""
Layer Management Service - Modular Implementation

This module provides the main orchestrator service that delegates to specialized modules.
This maintains the same public API as the original layer_management_service.py but with
a modular internal architecture.

Architecture:
- LayerManagementService: Main orchestrator that delegates to specialized modules
- models.py: Data models, enums, and exception classes
- crud.py: Create, Read, Update, Delete operations
- stats.py: Statistics and metrics operations
- validation.py: Validation and comparison operations
- export.py: Export, import, copy, archive, and restore operations

Philosophy:
- Modular design with clear separation of concerns
- Each module < 300 lines
- Orchestrator delegates to specialized modules
- Zero breaking changes to existing API
- Thread-safe via Neo4j transactions

Public API (the "studs"):
    LayerManagementService: Main service orchestrator
    LayerType: Enum for layer classification
    LayerMetadata: Complete metadata for a graph layer
    LayerDiff: Comparison result between two layers
    LayerValidationReport: Validation results
    LayerError: Base exception class
    [All exception classes from models.py]
"""

import logging
from typing import Any, Callable, Dict, List, Optional

from src.services.layer.crud import LayerCrudOperations
from src.services.layer.export import LayerExportOperations
from src.services.layer.models import (
    CrossLayerRelationshipError,
    InvalidLayerIdError,
    LayerAlreadyExistsError,
    LayerDiff,
    LayerError,
    LayerIntegrityError,
    LayerLockedError,
    LayerMetadata,
    LayerNotFoundError,
    LayerProtectedError,
    LayerType,
    LayerValidationReport,
)
from src.services.layer.stats import LayerStatsOperations
from src.services.layer.validation import LayerValidationOperations
from src.utils.session_manager import Neo4jSessionManager

logger = logging.getLogger(__name__)


class LayerManagementService:
    """
    Main orchestrator service for layer management operations.

    This service maintains the same public API as the original layer_management_service.py
    but delegates to specialized modules internally.

    Responsibilities:
    - Initialize and coordinate specialized modules
    - Provide unified interface to all layer operations
    - Maintain backward compatibility

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

        # Initialize specialized modules
        self.crud = LayerCrudOperations(session_manager)
        self.stats = LayerStatsOperations(session_manager, crud_operations=self.crud)
        self.validation = LayerValidationOperations(
            session_manager, crud_operations=self.crud, stats_operations=self.stats
        )
        self.export = LayerExportOperations(
            session_manager, crud_operations=self.crud, stats_operations=self.stats
        )

        # Ensure schema on initialization
        self._ensure_layer_schema()

    def _ensure_layer_schema(self) -> None:
        """Ensure Layer node schema exists with indexes and constraints."""
        self.crud.ensure_schema()

    def _node_to_layer_metadata(self, node) -> LayerMetadata:
        """Convert Neo4j node to LayerMetadata (for backward compatibility)."""
        return self.crud.node_to_layer_metadata(node)

    # =============================================================================
    # CRUD Operations (delegated to crud.py)
    # =============================================================================

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
        return await self.crud.create_layer(
            layer_id=layer_id,
            name=name,
            description=description,
            created_by=created_by,
            parent_layer_id=parent_layer_id,
            layer_type=layer_type,
            tenant_id=tenant_id,
            metadata=metadata,
            make_active=make_active,
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
        return await self.crud.list_layers(
            tenant_id=tenant_id,
            include_inactive=include_inactive,
            layer_type=layer_type,
            tags=tags,
            sort_by=sort_by,
            ascending=ascending,
        )

    async def get_layer(self, layer_id: str) -> Optional[LayerMetadata]:
        """
        Get metadata for a specific layer.

        Args:
            layer_id: Layer identifier

        Returns:
            LayerMetadata if found, None otherwise
        """
        return await self.crud.get_layer(layer_id)

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
        return await self.crud.get_active_layer(tenant_id=tenant_id)

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
        return await self.crud.update_layer(
            layer_id=layer_id,
            name=name,
            description=description,
            tags=tags,
            metadata=metadata,
            is_locked=is_locked,
        )

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
        return await self.crud.delete_layer(layer_id=layer_id, force=force)

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
        return await self.crud.set_active_layer(layer_id=layer_id, tenant_id=tenant_id)

    # =============================================================================
    # Statistics Operations (delegated to stats.py)
    # =============================================================================

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
        return await self.stats.refresh_layer_stats(layer_id)

    # =============================================================================
    # Validation Operations (delegated to validation.py)
    # =============================================================================

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
        return await self.validation.compare_layers(
            layer_a_id=layer_a_id,
            layer_b_id=layer_b_id,
            detailed=detailed,
            include_properties=include_properties,
        )

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
        return await self.validation.validate_layer_integrity(
            layer_id=layer_id, fix_issues=fix_issues
        )

    # =============================================================================
    # Export/Import Operations (delegated to export.py)
    # =============================================================================

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
        return await self.export.copy_layer(
            source_layer_id=source_layer_id,
            target_layer_id=target_layer_id,
            name=name,
            description=description,
            copy_metadata=copy_metadata,
            batch_size=batch_size,
            progress_callback=progress_callback,
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
        return await self.export.archive_layer(
            layer_id=layer_id, output_path=output_path, include_original=include_original
        )

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
        return await self.export.restore_layer(
            archive_path=archive_path, target_layer_id=target_layer_id
        )


# Export all public API components
__all__ = [
    "LayerManagementService",
    "LayerType",
    "LayerMetadata",
    "LayerDiff",
    "LayerValidationReport",
    "LayerError",
    "LayerNotFoundError",
    "LayerAlreadyExistsError",
    "LayerProtectedError",
    "LayerLockedError",
    "InvalidLayerIdError",
    "LayerIntegrityError",
    "CrossLayerRelationshipError",
]

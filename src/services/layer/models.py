"""
Layer Data Models and Exceptions

This module contains data models, enums, and exception classes for layer management.
Extracted from layer_management_service.py as part of modular refactoring.

Philosophy:
- Self-contained data models with clear contracts
- Type-safe enums for layer classification
- Specific exception classes for error handling
- Standard library only (no external dependencies)

Public API (the "studs"):
    LayerType: Enum for layer classification
    LayerMetadata: Complete metadata for a graph layer
    LayerDiff: Comparison result between two layers
    LayerValidationReport: Validation results for layer integrity
    LayerError: Base exception for layer operations
    LayerNotFoundError: Layer does not exist
    LayerAlreadyExistsError: Layer already exists
    LayerProtectedError: Cannot modify/delete protected layer
    LayerLockedError: Layer is locked for modifications
    InvalidLayerIdError: Layer ID format invalid
    LayerIntegrityError: Layer integrity validation failed
    CrossLayerRelationshipError: Attempted to create relationship across layers
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

# =============================================================================
# Enums
# =============================================================================


class LayerType(Enum):
    """Classification of layer purpose."""

    BASELINE = "baseline"  # Original 1:1 abstraction from scan
    SCALED = "scaled"  # Result of merge/split operations
    EXPERIMENTAL = "experimental"  # Sandbox for testing
    SNAPSHOT = "snapshot"  # Point-in-time backup


# =============================================================================
# Data Models
# =============================================================================


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
            created_at=created_at,  # type: ignore[arg-type]
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


__all__ = [
    "CrossLayerRelationshipError",
    "InvalidLayerIdError",
    "LayerAlreadyExistsError",
    "LayerDiff",
    "LayerError",
    "LayerIntegrityError",
    "LayerLockedError",
    "LayerMetadata",
    "LayerNotFoundError",
    "LayerProtectedError",
    "LayerType",
    "LayerValidationReport",
]

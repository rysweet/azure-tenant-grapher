"""
Layer Metadata Models

Data models for multi-layer graph projection architecture in Azure Tenant Grapher.
Layers enable non-destructive scale operations by maintaining multiple coexisting
abstracted projections while preserving the immutable Original graph as source of truth.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class LayerType(Enum):
    """Classification of layer purpose."""

    BASELINE = "baseline"  # Original 1:1 abstraction from scan
    SCALED = "scaled"  # Result of merge/split operations
    EXPERIMENTAL = "experimental"  # Sandbox for testing
    SNAPSHOT = "snapshot"  # Point-in-time backup


@dataclass
class LayerMetadata:
    """
    Complete metadata for a graph layer.

    A layer represents a complete, isolated projection of abstracted Azure resources.
    Each layer maintains its own nodes and relationships while linking back to the
    immutable Original graph via SCAN_SOURCE_NODE relationships.

    Attributes:
        layer_id: Unique identifier for the layer (e.g., "default", "scaled-v1")
        name: Human-readable name for the layer
        description: Purpose and context description
        created_at: Timestamp when layer was created
        updated_at: Timestamp of last modification (None if never updated)
        created_by: Operation that created the layer (scan, merge, split, copy)
        parent_layer_id: Source layer ID if this layer was derived from another
        is_active: Whether this is the currently active layer for operations
        is_baseline: Whether this is a protected baseline layer
        is_locked: Whether modifications to this layer are prevented
        tenant_id: Azure tenant ID
        subscription_ids: List of Azure subscription IDs included in this layer
        node_count: Number of :Resource nodes in this layer
        relationship_count: Number of relationships between resources in this layer
        layer_type: Classification of the layer's purpose
        metadata: Extensible key-value metadata for custom properties
        tags: List of tags for categorization and filtering

    Examples:
        >>> from datetime import datetime, UTC
        >>> layer = LayerMetadata(
        ...     layer_id="default",
        ...     name="Default Baseline",
        ...     description="1:1 abstraction from initial scan",
        ...     created_at=datetime.now(UTC),
        ...     created_by="scan",
        ...     is_active=True,
        ...     is_baseline=True,
        ...     tenant_id="00000000-0000-0000-0000-000000000000",
        ...     layer_type=LayerType.BASELINE
        ... )
        >>> print(layer.layer_id)
        default
        >>> print(layer.is_active)
        True
    """

    # Identity
    layer_id: str
    name: str
    description: str

    # Timestamps
    created_at: datetime
    updated_at: Optional[datetime] = None

    # Provenance
    created_by: str = "unknown"
    parent_layer_id: Optional[str] = None

    # State
    is_active: bool = False
    is_baseline: bool = False
    is_locked: bool = False

    # Scope
    tenant_id: str = "unknown"
    subscription_ids: List[str] = field(default_factory=list)

    # Statistics
    node_count: int = 0
    relationship_count: int = 0

    # Classification
    layer_type: LayerType = LayerType.EXPERIMENTAL

    # Extensible metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Tags
    tags: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Validate fields after initialization."""
        if not self.layer_id:
            raise ValueError("layer_id cannot be empty")
        if not self.name:
            raise ValueError("name cannot be empty")
        if self.node_count < 0:
            raise ValueError("node_count cannot be negative")
        if self.relationship_count < 0:
            raise ValueError("relationship_count cannot be negative")

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert metadata to dictionary format.

        Returns:
            Dict[str, Any]: Dictionary representation suitable for JSON serialization

        Example:
            >>> layer = LayerMetadata(...)
            >>> data = layer.to_dict()
            >>> print(data["layer_id"])
            default
        """
        return {
            "layer_id": self.layer_id,
            "name": self.name,
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else None,
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
        """
        Create metadata instance from dictionary.

        Args:
            data: Dictionary containing metadata fields

        Returns:
            LayerMetadata: New instance created from dictionary

        Example:
            >>> data = {
            ...     "layer_id": "default",
            ...     "name": "Default Baseline",
            ...     "description": "1:1 abstraction",
            ...     "created_at": "2025-11-16T10:00:00+00:00",
            ...     "created_by": "scan",
            ...     "tenant_id": "tenant-123",
            ...     "layer_type": "baseline"
            ... }
            >>> layer = LayerMetadata.from_dict(data)
            >>> print(layer.layer_id)
            default
        """
        # Parse timestamps if they're strings
        created_at = data["created_at"]
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)

        updated_at = data.get("updated_at")
        if isinstance(updated_at, str):
            updated_at = datetime.fromisoformat(updated_at)

        # Parse layer_type enum
        layer_type = data.get("layer_type", "experimental")
        if isinstance(layer_type, str):
            layer_type = LayerType(layer_type)

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

    def mark_active(self) -> None:
        """
        Mark layer as active.

        Updates is_active flag and sets updated_at timestamp.

        Example:
            >>> layer = LayerMetadata(..., is_active=False)
            >>> layer.mark_active()
            >>> print(layer.is_active)
            True
        """
        self.is_active = True
        self.updated_at = datetime.now(UTC)

    def mark_inactive(self) -> None:
        """
        Mark layer as inactive.

        Updates is_active flag and sets updated_at timestamp.

        Example:
            >>> layer = LayerMetadata(..., is_active=True)
            >>> layer.mark_inactive()
            >>> print(layer.is_active)
            False
        """
        self.is_active = False
        self.updated_at = datetime.now(UTC)

    def update_stats(self, node_count: int, relationship_count: int) -> None:
        """
        Update layer statistics.

        Args:
            node_count: New node count
            relationship_count: New relationship count

        Example:
            >>> layer = LayerMetadata(...)
            >>> layer.update_stats(5584, 8234)
            >>> print(layer.node_count)
            5584
        """
        self.node_count = node_count
        self.relationship_count = relationship_count
        self.updated_at = datetime.now(UTC)


@dataclass
class LayerDiff:
    """
    Comparison result between two layers.

    Represents the differences found when comparing a baseline layer (A)
    against a comparison layer (B). Tracks additions, removals, and modifications
    at both the node and relationship level.

    Attributes:
        layer_a_id: Baseline layer identifier
        layer_b_id: Comparison layer identifier
        compared_at: Timestamp when comparison was performed
        nodes_added: Count of nodes in B but not in A
        nodes_removed: Count of nodes in A but not in B
        nodes_modified: Count of nodes with same ID but different properties
        nodes_unchanged: Count of nodes that are identical
        relationships_added: Count of relationships in B but not in A
        relationships_removed: Count of relationships in A but not in B
        relationships_modified: Count of relationships with different properties
        relationships_unchanged: Count of relationships that are identical
        added_node_ids: List of resource IDs for added nodes
        removed_node_ids: List of resource IDs for removed nodes
        modified_node_ids: List of resource IDs for modified nodes
        property_changes: Detailed property-level changes by resource ID
        total_changes: Total count of all changes
        change_percentage: Percentage of resources that changed

    Examples:
        >>> diff = LayerDiff(
        ...     layer_a_id="default",
        ...     layer_b_id="scaled-v1",
        ...     compared_at=datetime.now(UTC),
        ...     nodes_added=10,
        ...     nodes_removed=100,
        ...     nodes_modified=5,
        ...     nodes_unchanged=5474
        ... )
        >>> print(diff.total_changes)
        115
        >>> print(str(f"{diff.change_percentage:.1f}%"))
        2.1%
    """

    # Identity
    layer_a_id: str
    layer_b_id: str
    compared_at: datetime

    # Node differences
    nodes_added: int
    nodes_removed: int
    nodes_modified: int
    nodes_unchanged: int

    # Relationship differences
    relationships_added: int = 0
    relationships_removed: int = 0
    relationships_modified: int = 0
    relationships_unchanged: int = 0

    # Detailed changes (optional)
    added_node_ids: List[str] = field(default_factory=list)
    removed_node_ids: List[str] = field(default_factory=list)
    modified_node_ids: List[str] = field(default_factory=list)

    # Property-level changes (optional)
    property_changes: Dict[str, Any] = field(default_factory=dict)

    # Summary
    total_changes: int = 0
    change_percentage: float = 0.0

    def __post_init__(self) -> None:
        """Calculate derived fields after initialization."""
        self.total_changes = (
            self.nodes_added
            + self.nodes_removed
            + self.nodes_modified
            + self.relationships_added
            + self.relationships_removed
            + self.relationships_modified
        )

        total_items = (
            self.nodes_added
            + self.nodes_removed
            + self.nodes_modified
            + self.nodes_unchanged
        )
        if total_items > 0:
            self.change_percentage = (
                (self.nodes_added + self.nodes_removed + self.nodes_modified)
                / total_items
                * 100.0
            )

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert diff to dictionary format.

        Returns:
            Dict[str, Any]: Dictionary representation suitable for JSON serialization
        """
        return {
            "layer_a_id": self.layer_a_id,
            "layer_b_id": self.layer_b_id,
            "compared_at": self.compared_at.isoformat() if self.compared_at else None,
            "nodes_added": self.nodes_added,
            "nodes_removed": self.nodes_removed,
            "nodes_modified": self.nodes_modified,
            "nodes_unchanged": self.nodes_unchanged,
            "relationships_added": self.relationships_added,
            "relationships_removed": self.relationships_removed,
            "relationships_modified": self.relationships_modified,
            "relationships_unchanged": self.relationships_unchanged,
            "added_node_ids": self.added_node_ids,
            "removed_node_ids": self.removed_node_ids,
            "modified_node_ids": self.modified_node_ids,
            "property_changes": self.property_changes,
            "total_changes": self.total_changes,
            "change_percentage": self.change_percentage,
        }


@dataclass
class LayerValidationReport:
    """
    Validation results for layer integrity.

    Comprehensive report of layer validation checks including errors, warnings,
    and statistics about layer health. Used to ensure layer integrity after
    operations and to identify issues requiring correction.

    Attributes:
        layer_id: Layer being validated
        validated_at: Timestamp of validation
        is_valid: Overall validation result (False if any errors found)
        checks_passed: Count of successful validation checks
        checks_failed: Count of failed validation checks
        checks_warned: Count of checks that passed with warnings
        issues: List of error-level issues found
        warnings: List of warning-level issues found
        orphaned_nodes: Count of nodes without SCAN_SOURCE_NODE links
        orphaned_relationships: Count of relationships with missing endpoints
        cross_layer_relationships: Count of relationships crossing layer boundaries
        missing_scan_source_nodes: Count of missing Original nodes

    Examples:
        >>> report = LayerValidationReport(
        ...     layer_id="scaled-v1",
        ...     validated_at=datetime.now(UTC),
        ...     is_valid=False,
        ...     checks_passed=5,
        ...     checks_failed=2,
        ...     checks_warned=1
        ... )
        >>> report.add_error("ORPHAN_NODE", "Found 3 orphaned nodes", {"count": 3})
        >>> print(report.is_valid)
        False
        >>> print(report.checks_failed)
        3
    """

    layer_id: str
    validated_at: datetime
    is_valid: bool

    # Checks
    checks_passed: int
    checks_failed: int
    checks_warned: int

    # Issues
    issues: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[Dict[str, Any]] = field(default_factory=list)

    # Statistics
    orphaned_nodes: int = 0
    orphaned_relationships: int = 0
    cross_layer_relationships: int = 0
    missing_scan_source_nodes: int = 0

    def add_error(
        self, code: str, message: str, details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Add validation error.

        Args:
            code: Error code (e.g., "ORPHAN_NODE", "MISSING_LINK")
            message: Human-readable error message
            details: Optional additional error details

        Example:
            >>> report = LayerValidationReport(...)
            >>> report.add_error("ORPHAN_NODE", "Found orphaned nodes", {"count": 3})
            >>> print(report.is_valid)
            False
        """
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
    ) -> None:
        """
        Add validation warning.

        Args:
            code: Warning code
            message: Human-readable warning message
            details: Optional additional warning details

        Example:
            >>> report = LayerValidationReport(...)
            >>> report.add_warning("STALE_STATS", "Node count may be outdated")
            >>> print(len(report.warnings))
            1
        """
        self.warnings.append(
            {
                "level": "warning",
                "code": code,
                "message": message,
                "details": details or {},
            }
        )
        self.checks_warned += 1

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert report to dictionary format.

        Returns:
            Dict[str, Any]: Dictionary representation suitable for JSON serialization
        """
        return {
            "layer_id": self.layer_id,
            "validated_at": self.validated_at.isoformat()
            if self.validated_at
            else None,
            "is_valid": self.is_valid,
            "checks_passed": self.checks_passed,
            "checks_failed": self.checks_failed,
            "checks_warned": self.checks_warned,
            "issues": self.issues,
            "warnings": self.warnings,
            "orphaned_nodes": self.orphaned_nodes,
            "orphaned_relationships": self.orphaned_relationships,
            "cross_layer_relationships": self.cross_layer_relationships,
            "missing_scan_source_nodes": self.missing_scan_source_nodes,
        }

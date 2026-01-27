"""Models for Tenant Reset Feature.

Philosophy:
- Type-safe data structures using dataclasses
- Explicit scope types for safety
- Clear separation of preview vs execution results

Public API:
    ResetScope: Defines the scope of a reset operation
    ResetPreview: Preview of resources that will be deleted
    ResetResult: Result of a reset operation
    ResourceDeletionResult: Result of deleting a single resource
    EntraObjectDeletionResult: Result of deleting an Entra ID object
    GraphCleanupResult: Result of Neo4j graph cleanup

Issue #627: Tenant Reset Feature with Granular Scopes
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class ScopeType(str, Enum):
    """Type of reset scope."""

    TENANT = "tenant"
    SUBSCRIPTION = "subscription"
    RESOURCE_GROUP = "resource_group"
    RESOURCE = "resource"


class ResetStatus(str, Enum):
    """Status of reset operation."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"  # Some deletions succeeded, some failed


@dataclass
class ResetScope:
    """Defines the scope of a reset operation."""

    scope_type: ScopeType
    subscription_id: Optional[str] = None
    resource_group_name: Optional[str] = None
    resource_id: Optional[str] = None

    def __post_init__(self):
        """Validate scope parameters."""
        if self.scope_type == ScopeType.SUBSCRIPTION and not self.subscription_id:
            raise ValueError("subscription_id required for subscription scope")
        if self.scope_type == ScopeType.RESOURCE_GROUP and (
            not self.subscription_id or not self.resource_group_name
        ):
            raise ValueError(
                "subscription_id and resource_group_name required for resource_group scope"
            )
        if self.scope_type == ScopeType.RESOURCE and not self.resource_id:
            raise ValueError("resource_id required for resource scope")

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "scope_type": self.scope_type.value,
            "subscription_id": self.subscription_id,
            "resource_group_name": self.resource_group_name,
            "resource_id": self.resource_id,
        }


@dataclass
class ResetPreview:
    """Preview of resources that will be deleted.

    Shows counts and warnings before actual deletion.
    """

    scope: ResetScope
    azure_resources_count: int
    entra_users_count: int = 0
    entra_groups_count: int = 0
    entra_service_principals_count: int = 0
    graph_nodes_count: int = 0
    estimated_duration_seconds: int = 0
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "scope": self.scope.to_dict(),
            "azure_resources_count": self.azure_resources_count,
            "entra_users_count": self.entra_users_count,
            "entra_groups_count": self.entra_groups_count,
            "entra_service_principals_count": self.entra_service_principals_count,
            "graph_nodes_count": self.graph_nodes_count,
            "estimated_duration_seconds": self.estimated_duration_seconds,
            "warnings": self.warnings,
        }


@dataclass
class ResourceDeletionResult:
    """Result of deleting a single Azure resource."""

    resource_id: str
    resource_type: str
    success: bool
    error: Optional[str] = None
    duration_seconds: float = 0.0


@dataclass
class EntraObjectDeletionResult:
    """Result of deleting a single Entra ID object."""

    object_id: str
    object_type: str  # "user", "group", "service_principal"
    display_name: str
    success: bool
    error: Optional[str] = None


@dataclass
class GraphCleanupResult:
    """Result of Neo4j graph cleanup."""

    nodes_deleted: int
    relationships_deleted: int
    success: bool
    error: Optional[str] = None
    duration_seconds: float = 0.0


@dataclass
class ResetResult:
    """Result of a reset operation.

    Contains detailed information about what was deleted and any errors.
    """

    scope: ResetScope
    status: ResetStatus
    deleted_azure_resources: int = 0
    deleted_entra_users: int = 0
    deleted_entra_groups: int = 0
    deleted_entra_service_principals: int = 0
    deleted_graph_nodes: int = 0
    deleted_graph_relationships: int = 0
    errors: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    resource_deletion_details: list[ResourceDeletionResult] = field(default_factory=list)
    entra_deletion_details: list[EntraObjectDeletionResult] = field(default_factory=list)
    graph_cleanup_details: Optional[GraphCleanupResult] = None

    @property
    def success(self) -> bool:
        """Check if operation was fully successful."""
        return self.status == ResetStatus.COMPLETED and len(self.errors) == 0

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "scope": self.scope.to_dict(),
            "status": self.status.value,
            "success": self.success,
            "deleted_azure_resources": self.deleted_azure_resources,
            "deleted_entra_users": self.deleted_entra_users,
            "deleted_entra_groups": self.deleted_entra_groups,
            "deleted_entra_service_principals": self.deleted_entra_service_principals,
            "deleted_graph_nodes": self.deleted_graph_nodes,
            "deleted_graph_relationships": self.deleted_graph_relationships,
            "errors": self.errors,
            "duration_seconds": self.duration_seconds,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }

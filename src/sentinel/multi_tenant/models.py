"""Data models for Azure Lighthouse delegations.

Philosophy:
- Simple dataclasses (no complex inheritance)
- Immutable where possible
- Clear field documentation
- Type hints for all fields

Models:
    LighthouseStatus: Enum for delegation statuses
    LighthouseDelegation: Core delegation data model
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import List, Optional


class LighthouseStatus(Enum):
    """Status of an Azure Lighthouse delegation.

    Statuses:
        PENDING: Template generated, awaiting deployment
        ACTIVE: Delegation deployed and verified in Azure
        REVOKED: Delegation removed from Azure
        ERROR: Deployment or verification failed
    """

    PENDING = "pending"
    ACTIVE = "active"
    REVOKED = "revoked"
    ERROR = "error"


@dataclass
class LighthouseDelegation:
    """Azure Lighthouse delegation between MSSP and customer tenant.

    This model represents the complete state of a Lighthouse delegation,
    including both Azure resource IDs and Neo4j graph data.

    Attributes:
        customer_tenant_id: Customer's Azure AD tenant ID (UUID)
        customer_tenant_name: Human-readable customer name
        managing_tenant_id: MSSP managing tenant ID (UUID)
        subscription_id: Customer subscription ID being delegated
        resource_group: Optional resource group scope (None = subscription scope)
        registration_definition_id: Azure resource ID of registration definition
        registration_assignment_id: Azure resource ID of registration assignment
        status: Current delegation status (PENDING, ACTIVE, REVOKED, ERROR)
        created_at: Timestamp when delegation was first created
        updated_at: Timestamp of last status change
        bicep_template_path: Path to generated Bicep template
        authorizations: List of RBAC authorizations (principal + role pairs)
        error_message: Error details if status is ERROR

    Example:
        >>> delegation = LighthouseDelegation(
        ...     customer_tenant_id="11111111-1111-1111-1111-111111111111",
        ...     customer_tenant_name="Acme Corp",
        ...     managing_tenant_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        ...     subscription_id="22222222-2222-2222-2222-222222222222",
        ...     resource_group=None,
        ...     registration_definition_id="/subscriptions/.../registrationDefinitions/...",
        ...     registration_assignment_id="/subscriptions/.../registrationAssignments/...",
        ...     status=LighthouseStatus.ACTIVE,
        ...     created_at=datetime.now(),
        ...     updated_at=datetime.now(),
        ...     bicep_template_path="./iac_output/lighthouse-acme-corp.bicep"
        ... )
    """

    customer_tenant_id: str
    customer_tenant_name: str
    managing_tenant_id: str
    subscription_id: str
    status: LighthouseStatus
    created_at: datetime
    updated_at: datetime
    bicep_template_path: str
    resource_group: Optional[str] = None
    registration_definition_id: Optional[str] = None
    registration_assignment_id: Optional[str] = None
    authorizations: Optional[List[dict]] = None
    error_message: Optional[str] = None

    def __post_init__(self):
        """Validate fields after initialization."""
        # Convert string status to enum if needed
        if isinstance(self.status, str):
            self.status = LighthouseStatus(self.status)

        # Validate UUIDs (basic format check)
        for field_name in [
            "customer_tenant_id",
            "managing_tenant_id",
            "subscription_id",
        ]:
            field_value = getattr(self, field_name)
            if not self._is_valid_uuid(field_value):
                raise ValueError(
                    f"{field_name} must be a valid UUID, got: {field_value}"
                )

    @staticmethod
    def _is_valid_uuid(value: str) -> bool:
        """Basic UUID format validation (8-4-4-4-12)."""
        if not value or not isinstance(value, str):
            return False
        parts = value.split("-")
        if len(parts) != 5:
            return False
        expected_lengths = [8, 4, 4, 4, 12]
        return all(
            len(part) == expected_len
            for part, expected_len in zip(parts, expected_lengths)
        )

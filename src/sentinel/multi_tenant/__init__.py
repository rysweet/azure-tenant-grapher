"""Multi-tenant Sentinel integration for MSSP operations.

This module provides Azure Lighthouse delegation management for MSSPs
managing 50-100+ customer tenants.

Philosophy:
- Automation-first (no portal dependencies)
- Neo4j-backed delegation tracking
- Bicep template generation for reproducibility
- Zero-BS implementation (all code works)

Public API:
    LighthouseManager: Main service for delegation management
    LighthouseDelegation: Data model for delegations
    LighthouseStatus: Status enum (PENDING, ACTIVE, REVOKED, ERROR)

    LighthouseError: Base exception
    DelegationNotFoundError: Delegation doesn't exist
    DelegationExistsError: Delegation already exists

Example:
    >>> from sentinel.multi_tenant import LighthouseManager, LighthouseStatus
    >>> manager = LighthouseManager(
    ...     managing_tenant_id="mssp-tenant-id",
    ...     neo4j_connection=driver,
    ...     bicep_output_dir="./iac_output"
    ... )
    >>>
    >>> # Generate Bicep template
    >>> template_path = manager.generate_delegation_template(
    ...     customer_tenant_id="customer-id",
    ...     customer_tenant_name="Acme Corp",
    ...     subscription_id="sub-id"
    ... )
    >>>
    >>> # List delegations
    >>> delegations = manager.list_delegations(status_filter=LighthouseStatus.ACTIVE)
"""

from .exceptions import DelegationExistsError, DelegationNotFoundError, LighthouseError
from .lighthouse_manager import LighthouseManager
from .models import LighthouseDelegation, LighthouseStatus

__all__ = [
    "DelegationExistsError",
    "DelegationNotFoundError",
    "LighthouseDelegation",
    "LighthouseError",
    "LighthouseManager",
    "LighthouseStatus",
]

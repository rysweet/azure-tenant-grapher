"""
Service Layer Module

This module contains the service layer implementation for Azure Tenant Grapher,
providing focused, single-responsibility services that replace the monolithic
AzureTenantGrapher class.

This is currently being implemented incrementally as part of Phase 2 refactoring.
"""

from .azure_discovery_service import (
    AzureDiscoveryService,
    create_azure_discovery_service,
)
from .azure_mcp_client import (
    AzureMCPClient,
    MCPConnectionError,
    MCPOperationError,
    create_mcp_client,
    integrate_with_discovery_service,
)
from .change_feed_ingestion_service import ChangeFeedIngestionService
from .discovery_filter_service import DiscoveryFilterService
from .tenant_manager import (
    InvalidTenantConfigError,
    Tenant,
    TenantManager,
    TenantNotFoundError,
    TenantSwitchError,
    get_current_tenant,
    get_tenant_manager,
    register_tenant,
    switch_tenant,
)

__all__ = [
    "AzureDiscoveryService",
    "AzureMCPClient",
    "ChangeFeedIngestionService",
    "DiscoveryFilterService",
    "InvalidTenantConfigError",
    "MCPConnectionError",
    "MCPOperationError",
    "Tenant",
    "TenantManager",
    "TenantNotFoundError",
    "TenantSwitchError",
    "create_azure_discovery_service",
    "create_mcp_client",
    "get_current_tenant",
    "get_tenant_manager",
    "integrate_with_discovery_service",
    "register_tenant",
    "switch_tenant",
]

# Additional services will be added as they are implemented:
# - Neo4jSessionManager (for Neo4j session management)
# - ResourceProcessingService (for resource processing operations)
# - TenantSpecificationService (for tenant specification generation)

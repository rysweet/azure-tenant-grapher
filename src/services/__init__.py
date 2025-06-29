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
from .change_feed_ingestion_service import ChangeFeedIngestionService

__all__ = [
    "AzureDiscoveryService",
    "ChangeFeedIngestionService",
    "create_azure_discovery_service",
]

# Additional services will be added as they are implemented:
# - Neo4jSessionManager (for Neo4j session management)
# - ResourceProcessingService (for resource processing operations)
# - TenantSpecificationService (for tenant specification generation)

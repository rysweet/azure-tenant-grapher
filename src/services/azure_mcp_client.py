"""
Azure MCP Client Service

This service provides natural language interface to Azure operations via MCP (Model Context Protocol).
It acts as a bridge between natural language queries and Azure API operations, allowing
for intuitive exploration and management of Azure resources.

Following the project's philosophy of ruthless simplicity, this implementation:
- Starts with basic operations that demonstrate value
- Can be enabled/disabled via configuration
- Works alongside existing AzureDiscoveryService
- Uses async patterns consistent with the codebase
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..config_manager import AzureTenantGrapherConfig
from .tenant_manager import TenantManager

logger = logging.getLogger(__name__)


class MCPConnectionError(Exception):
    """Raised when MCP connection fails."""

    pass


class MCPOperationError(Exception):
    """Raised when MCP operation fails."""

    pass


class AzureMCPClient:
    """
    Client for interacting with Azure via Model Context Protocol (MCP).

    This client enables natural language queries and operations on Azure resources,
    translating human-friendly requests into appropriate Azure API calls through
    the MCP interface.
    """

    def __init__(
        self,
        config: AzureTenantGrapherConfig,
        tenant_manager: Optional[TenantManager] = None,
        mcp_endpoint: str = "http://localhost:8080",
        enabled: bool = True,
    ):
        """
        Initialize the Azure MCP Client.

        Args:
            config: Configuration object containing Azure settings
            tenant_manager: Optional TenantManager for multi-tenant operations
            mcp_endpoint: MCP server endpoint (default: localhost:8080)
            enabled: Whether MCP integration is enabled
        """
        self.config = config
        self.tenant_manager = tenant_manager
        self.mcp_endpoint = mcp_endpoint
        self.enabled = enabled
        self.connected = False
        self._session = None
        self._current_context: Dict[str, Any] = {}

        # Operation mapping for natural language to Azure operations
        self._operation_patterns = {
            "list_resources": ["list", "show", "get", "find", "resources"],
            "discover_tenants": ["discover", "find", "tenants", "subscriptions"],
            "get_identity": [
                "identity",
                "user",
                "service principal",
                "who",
                "permissions",
            ],
            "resource_groups": ["resource group", "groups", "rg"],
            "virtual_machines": ["vm", "virtual machine", "compute", "instances"],
            "storage": ["storage", "blob", "container", "files"],
            "network": ["network", "vnet", "subnet", "nsg", "firewall"],
        }

        logger.info(f"Azure MCP Client initialized (enabled={self.enabled})")

    async def connect(self) -> bool:
        """
        Establish connection to MCP server.

        Returns:
            True if connection successful, False otherwise
        """
        if not self.enabled:
            logger.debug("MCP integration is disabled")
            return False

        try:
            # Import aiohttp only when needed
            import aiohttp

            # Create session if not exists
            if not self._session:
                self._session = aiohttp.ClientSession()

            # Test connection with health check
            async with self._session.get(f"{self.mcp_endpoint}/health") as response:
                if response.status == 200:
                    self.connected = True
                    logger.info(f"Connected to MCP server at {self.mcp_endpoint}")

                    # Set initial context
                    await self._set_context()
                    return True
                else:
                    logger.warning(f"MCP server returned status {response.status}")
                    return False

        except Exception as e:
            logger.warning(f"Failed to connect to MCP server: {e}")
            self.connected = False
            return False

    async def disconnect(self) -> None:
        """Close MCP connection and cleanup resources."""
        if self._session:
            await self._session.close()
            self._session = None
        self.connected = False
        logger.info("Disconnected from MCP server")

    async def _set_context(self) -> None:
        """Set the current Azure context for MCP operations."""
        self._current_context = {
            "tenant_id": self.config.tenant_id,
            "timestamp": datetime.utcnow().isoformat(),
        }

        # Add current tenant info if available
        if self.tenant_manager:
            try:
                current_tenant = await self.tenant_manager.get_current_tenant()
                if current_tenant:
                    self._current_context.update(
                        {
                            "tenant_name": current_tenant.display_name,
                            "subscription_ids": current_tenant.subscription_ids,
                        }
                    )
            except Exception as e:
                logger.debug(f"Could not get current tenant: {e}")

    async def discover_tenants(self) -> List[Dict[str, Any]]:
        """
        Discover available Azure tenants using MCP.

        Returns:
            List of discovered tenants with their metadata
        """
        if not self.enabled:
            logger.debug("MCP integration disabled, returning empty list")
            return []

        if not self.connected:
            if not await self.connect():
                raise MCPConnectionError("Failed to connect to MCP server")

        try:
            # Prepare MCP request for tenant discovery
            request = {
                "operation": "discover_tenants",
                "context": self._current_context,
            }

            # Send request to MCP
            result = await self._execute_mcp_request(request)

            # Process and return tenant information
            tenants = result.get("tenants", [])
            logger.info(f"Discovered {len(tenants)} tenants via MCP")

            return tenants

        except Exception as e:
            logger.error(f"Failed to discover tenants via MCP: {e}")
            raise MCPOperationError(f"Tenant discovery failed: {e}")

    async def query_resources(self, natural_language_query: str) -> Dict[str, Any]:
        """
        Query Azure resources using natural language.

        Args:
            natural_language_query: Human-friendly query like "show all VMs in production"

        Returns:
            Dictionary containing query results and metadata
        """
        if not self.enabled:
            return {
                "status": "disabled",
                "message": "MCP integration is not enabled",
                "results": [],
            }

        if not self.connected:
            if not await self.connect():
                return {
                    "status": "error",
                    "message": "Failed to connect to MCP server",
                    "results": [],
                }

        try:
            # Analyze query to determine operation type
            operation_type = self._analyze_query(natural_language_query)

            # Prepare MCP request
            request = {
                "operation": "query_resources",
                "query": natural_language_query,
                "operation_hint": operation_type,
                "context": self._current_context,
            }

            # Execute query via MCP
            result = await self._execute_mcp_request(request)

            return {
                "status": "success",
                "query": natural_language_query,
                "operation_type": operation_type,
                "results": result.get("resources", []),
                "metadata": result.get("metadata", {}),
            }

        except Exception as e:
            logger.error(f"Resource query failed: {e}")
            return {
                "status": "error",
                "message": str(e),
                "query": natural_language_query,
                "results": [],
            }

    async def get_identity_info(self, query: Optional[str] = None) -> Dict[str, Any]:
        """
        Get identity and permission information via natural language.

        Args:
            query: Optional specific identity query (e.g., "what can this service principal do?")

        Returns:
            Dictionary containing identity information and permissions
        """
        if not self.enabled:
            return {"status": "disabled", "message": "MCP integration is not enabled"}

        if not self.connected:
            if not await self.connect():
                return {"status": "error", "message": "Failed to connect to MCP server"}

        try:
            request = {
                "operation": "get_identity",
                "query": query or "current identity and permissions",
                "context": self._current_context,
            }

            result = await self._execute_mcp_request(request)

            return {
                "status": "success",
                "identity": result.get("identity", {}),
                "permissions": result.get("permissions", []),
                "roles": result.get("roles", []),
            }

        except Exception as e:
            logger.error(f"Identity query failed: {e}")
            return {"status": "error", "message": str(e)}

    async def execute_operation(self, operation: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a specific Azure operation via MCP.

        Args:
            operation: Dictionary describing the operation to execute

        Returns:
            Operation result dictionary
        """
        if not self.enabled:
            raise MCPOperationError("MCP integration is not enabled")

        if not self.connected:
            if not await self.connect():
                raise MCPConnectionError("Failed to connect to MCP server")

        try:
            # Add context to operation
            operation["context"] = self._current_context

            # Execute via MCP
            result = await self._execute_mcp_request(operation)

            logger.info(f"Executed operation: {operation.get('type', 'unknown')}")
            return result

        except Exception as e:
            logger.error(f"Operation execution failed: {e}")
            raise MCPOperationError(f"Failed to execute operation: {e}")

    def _analyze_query(self, query: str) -> str:
        """
        Analyze natural language query to determine operation type.

        Args:
            query: Natural language query

        Returns:
            Operation type hint
        """
        query_lower = query.lower()

        # Check for operation patterns
        for op_type, patterns in self._operation_patterns.items():
            if any(pattern in query_lower for pattern in patterns):
                return op_type

        return "general_query"

    async def _execute_mcp_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute request against MCP server.

        Args:
            request: Request dictionary

        Returns:
            Response from MCP server
        """
        if not self._session:
            raise MCPConnectionError("No active session")

        try:
            # For now, this is a placeholder that simulates MCP responses
            # In a real implementation, this would send requests to an actual MCP server
            # that bridges to Azure services

            logger.debug(f"Executing MCP request: {request.get('operation')}")

            # Simulate different response types based on operation
            operation = request.get("operation")

            if operation == "discover_tenants":
                # Simulate tenant discovery
                return {
                    "tenants": [
                        {
                            "tenant_id": self.config.tenant_id,
                            "display_name": "Current Tenant",
                            "subscription_count": 1,
                            "discovered_at": datetime.utcnow().isoformat(),
                        }
                    ]
                }

            elif operation == "query_resources":
                # Simulate resource query
                return {
                    "resources": [
                        {
                            "id": f"/subscriptions/{self.config.tenant_id}/resourceGroups/example-rg",
                            "name": "example-rg",
                            "type": "Microsoft.Resources/resourceGroups",
                            "location": "eastus",
                        }
                    ],
                    "metadata": {
                        "query_time": datetime.utcnow().isoformat(),
                        "result_count": 1,
                    },
                }

            elif operation == "get_identity":
                # Simulate identity query
                return {
                    "identity": {
                        "type": "ServicePrincipal",
                        "id": "example-sp-id",
                        "name": "Azure Tenant Grapher",
                    },
                    "permissions": ["Reader"],
                    "roles": ["Contributor"],
                }

            else:
                # Generic response
                return {
                    "status": "success",
                    "operation": operation,
                    "timestamp": datetime.utcnow().isoformat(),
                }

        except Exception as e:
            logger.error(f"MCP request failed: {e}")
            raise MCPOperationError(f"Request execution failed: {e}")

    async def get_natural_language_help(self) -> List[str]:
        """
        Get list of example natural language queries that can be executed.

        Returns:
            List of example queries
        """
        return [
            "List all virtual machines in the tenant",
            "Show resource groups in East US region",
            "Find storage accounts with public access",
            "Get my current identity and permissions",
            "Discover available Azure tenants",
            "Show network security groups with open ports",
            "List all resources created in the last 7 days",
            "Find resources with tag 'environment=production'",
            "Show cost analysis for current month",
            "Get compliance status of subscriptions",
        ]

    def is_available(self) -> bool:
        """
        Check if MCP integration is available and enabled.

        Returns:
            True if MCP is available and enabled
        """
        return self.enabled and self.connected

    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()


# Helper functions for integration with existing codebase


async def create_mcp_client(
    config: AzureTenantGrapherConfig,
    tenant_manager: Optional[TenantManager] = None,
    auto_connect: bool = True,
) -> AzureMCPClient:
    """
    Factory function to create and optionally connect an Azure MCP Client.

    Args:
        config: Azure configuration
        tenant_manager: Optional tenant manager for multi-tenant support
        auto_connect: Whether to automatically connect to MCP server

    Returns:
        Configured AzureMCPClient instance
    """
    # Check if MCP is enabled in config (default to True for now)
    mcp_enabled = getattr(config, "mcp_enabled", True)
    mcp_endpoint = getattr(config, "mcp_endpoint", "http://localhost:8080")

    client = AzureMCPClient(
        config=config,
        tenant_manager=tenant_manager,
        mcp_endpoint=mcp_endpoint,
        enabled=mcp_enabled,
    )

    if auto_connect and mcp_enabled:
        await client.connect()

    return client


def integrate_with_discovery_service(
    discovery_service: Any, mcp_client: AzureMCPClient
) -> None:
    """
    Integrate MCP client with existing AzureDiscoveryService.

    This allows the discovery service to optionally use MCP for
    enhanced natural language queries while maintaining backward compatibility.

    Args:
        discovery_service: Existing AzureDiscoveryService instance
        mcp_client: Configured AzureMCPClient instance
    """
    # Add MCP client as an optional enhancement to discovery service
    discovery_service.mcp_client = mcp_client

    # Add method to discovery service for natural language queries
    async def query_with_natural_language(self, query: str) -> Dict[str, Any]:
        """Query resources using natural language via MCP."""
        if hasattr(self, "mcp_client") and self.mcp_client.is_available():
            return await self.mcp_client.query_resources(query)
        else:
            return {
                "status": "unavailable",
                "message": "MCP natural language queries not available",
                "results": [],
            }

    # Bind the method to the discovery service instance
    import types

    discovery_service.query_with_natural_language = types.MethodType(
        query_with_natural_language, discovery_service
    )

    logger.info("MCP client integrated with AzureDiscoveryService")

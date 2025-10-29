"""
MCP (Model Context Protocol) Integration Service for Azure Tenant Grapher

Provides optional MCP-based discovery alongside existing discovery, with natural
language query interface and fallback to traditional API when MCP is unavailable.
"""

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

# FilterConfig imported but not used directly - needed for type checking
# from src.models.filter_config import FilterConfig
from src.services.azure_discovery_service import AzureDiscoveryService

logger = logging.getLogger(__name__)


@dataclass
class MCPConfig:
    """Configuration for MCP integration."""

    endpoint: str = "http://localhost:8080"
    enabled: bool = False
    timeout: int = 30
    api_key: Optional[str] = None


class MCPIntegrationService:
    """
    Service for integrating MCP (Model Context Protocol) with Azure Tenant Grapher.

    This service provides:
    - Natural language query interface for Azure resources
    - Optional MCP-based discovery alongside traditional discovery
    - Graceful fallback to API-based discovery when MCP is unavailable
    """

    def __init__(
        self,
        config: MCPConfig,
        discovery_service: Optional[AzureDiscoveryService] = None,
    ):
        """
        Initialize MCP Integration Service.

        Args:
            config: MCP configuration
            discovery_service: Optional existing discovery service for fallback
        """
        self.config = config
        self.discovery_service = discovery_service
        self._mcp_client: Optional[Any] = None
        self._is_connected = False

    async def initialize(self) -> bool:
        """
        Initialize MCP connection if configured and available.

        Returns:
            bool: True if MCP connection successful, False otherwise
        """
        if not self.config.enabled:
            logger.info("MCP integration disabled in configuration")
            return False

        try:
            # Try to import MCP client
            try:
                from autogen_ext.mcp import MCPClient

                self._mcp_client = MCPClient(
                    endpoint=self.config.endpoint,
                    timeout=self.config.timeout,
                    api_key=self.config.api_key,
                )

                # Test connection
                await self._test_connection()
                self._is_connected = True
                logger.info(f"✅ MCP connection established to {self.config.endpoint}")
                return True

            except ImportError:
                logger.warning("MCP client library not available (autogen_ext.mcp)")
                return False

        except Exception as e:
            logger.warning(f"Failed to initialize MCP connection: {e}")
            return False

    async def _test_connection(self) -> None:
        """Test MCP connection by sending a simple query."""
        if self._mcp_client:
            # Send a test query to verify connection
            test_response = await self._mcp_client.query(
                "list available tools", timeout=5
            )
            if not test_response:
                raise ConnectionError("MCP server not responding")

    @property
    def is_available(self) -> bool:
        """Check if MCP is available and connected."""
        return self._is_connected and self._mcp_client is not None

    async def query_resources(
        self, natural_language_query: str
    ) -> Tuple[bool, List[Dict[str, Any]]]:
        """
        Query Azure resources using natural language via MCP.

        Args:
            natural_language_query: Natural language query for resources

        Returns:
            Tuple of (success: bool, resources: List[Dict])
        """
        if not self.is_available:
            logger.info("MCP not available, falling back to traditional discovery")
            return False, []

        try:
            logger.info(f"Executing MCP query: {natural_language_query}")

            # Send natural language query to MCP
            if not self._mcp_client:
                raise RuntimeError("MCP client not initialized")
            response = await self._mcp_client.query(
                f"azure resources: {natural_language_query}",
                timeout=self.config.timeout,
            )

            # Parse response - expecting JSON list of resources
            if isinstance(response, str):
                try:
                    resources = json.loads(response)
                except json.JSONDecodeError:
                    logger.warning("MCP response was not valid JSON")
                    return False, []
            elif isinstance(response, list):
                resources = response
            else:
                resources = [response] if response else []

            logger.info(f"MCP query returned {len(resources)} resources")
            return True, resources

        except asyncio.TimeoutError:
            logger.warning(f"MCP query timed out after {self.config.timeout} seconds")
            return False, []
        except Exception as e:
            logger.error(f"MCP query failed: {e}")
            return False, []

    async def discover_resources(
        self,
        subscription_id: str,
        resource_types: Optional[List[str]] = None,
        use_mcp: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Discover Azure resources with MCP integration.

        Args:
            subscription_id: Azure subscription ID
            resource_types: Optional list of resource types to filter
            use_mcp: Whether to try MCP first (default: True)

        Returns:
            List of discovered resources
        """
        resources = []

        # Try MCP first if enabled and requested
        if use_mcp and self.is_available:
            query = f"list all resources in subscription {subscription_id}"
            if resource_types:
                query += f" of types: {', '.join(resource_types)}"

            success, mcp_resources = await self.query_resources(query)
            if success:
                logger.info(
                    f"Using MCP discovery results: {len(mcp_resources)} resources"
                )
                return mcp_resources

        # Fallback to traditional discovery
        if self.discovery_service:
            logger.info("Using traditional API-based discovery")
            # Note: resource_types filtering isn't supported directly in discover_resources_in_subscription
            # We'd need to filter post-discovery if needed
            resources = await self.discovery_service.discover_resources_in_subscription(
                subscription_id, filter_config=None
            )

            # Filter by resource types if specified
            if resource_types:
                resources = [
                    r
                    for r in resources
                    if any(rt in r.get("type", "") for rt in resource_types)
                ]
        else:
            logger.warning("No discovery service available for fallback")

        return resources

    async def analyze_resource_relationships(self, resource_id: str) -> Dict[str, Any]:
        """
        Analyze relationships for a specific resource using MCP.

        Args:
            resource_id: Azure resource ID

        Returns:
            Dictionary containing resource relationships and metadata
        """
        if not self.is_available:
            return {"resource_id": resource_id, "relationships": [], "mcp_used": False}

        try:
            query = (
                f"analyze relationships and dependencies for resource: {resource_id}"
            )
            if not self._mcp_client:
                raise RuntimeError("MCP client not initialized")
            response = await self._mcp_client.query(query, timeout=self.config.timeout)

            # Parse response
            if isinstance(response, str):
                try:
                    analysis = json.loads(response)
                except json.JSONDecodeError:
                    analysis = {"raw_response": response}
            else:
                analysis = response or {}

            analysis["mcp_used"] = "true"
            analysis["resource_id"] = resource_id

            return analysis

        except Exception as e:
            logger.error(f"MCP relationship analysis failed: {e}")
            return {
                "resource_id": resource_id,
                "relationships": [],
                "mcp_used": False,
                "error": str(e),
            }

    async def get_resource_insights(
        self, resource_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Get AI-powered insights about a resource using MCP.

        Args:
            resource_data: Resource data dictionary

        Returns:
            Dictionary containing insights and recommendations
        """
        if not self.is_available:
            return {"insights": [], "recommendations": [], "mcp_used": False}

        try:
            # Create a focused query for insights
            resource_type = resource_data.get("type", "unknown")
            resource_name = resource_data.get("name", "unknown")

            query = (
                f"Provide security insights and recommendations for Azure {resource_type} "
                f"resource named '{resource_name}' with the following configuration: "
                f"{json.dumps(resource_data, indent=2)}"
            )

            if not self._mcp_client:
                raise RuntimeError("MCP client not initialized")
            response = await self._mcp_client.query(query, timeout=self.config.timeout)

            # Parse insights from response
            if isinstance(response, str):
                try:
                    insights = json.loads(response)
                except json.JSONDecodeError:
                    insights = {
                        "insights": [response] if response else [],
                        "recommendations": [],
                    }
            else:
                insights = response or {"insights": [], "recommendations": []}

            insights["mcp_used"] = ["true"]
            return insights

        except Exception as e:
            logger.error(f"MCP insights generation failed: {e}")
            return {
                "insights": [],
                "recommendations": [],
                "mcp_used": False,
                "error": str(e),
            }

    async def natural_language_command(
        self, command: str
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Execute a natural language command via MCP.

        Args:
            command: Natural language command to execute

        Returns:
            Tuple of (success: bool, result: Dict)
        """
        if not self.is_available:
            return False, {
                "error": "MCP not available",
                "suggestion": "Use traditional CLI commands",
            }

        try:
            logger.info(f"Executing natural language command: {command}")

            # Send command to MCP
            if not self._mcp_client:
                raise RuntimeError("MCP client not initialized")
            response = await self._mcp_client.query(
                command,
                timeout=self.config.timeout * 2,  # Allow more time for complex commands
            )

            # Parse and structure response
            if isinstance(response, str):
                try:
                    result = json.loads(response)
                except json.JSONDecodeError:
                    result = {"response": response, "format": "text"}
            else:
                result = {"response": response, "format": "structured"}

            return True, result

        except asyncio.TimeoutError:
            return False, {
                "error": f"Command timed out after {self.config.timeout * 2} seconds",
                "suggestion": "Try a simpler query or use traditional commands",
            }
        except Exception as e:
            return False, {"error": str(e)}

    async def close(self) -> None:
        """Close MCP connection if active."""
        if self._mcp_client:
            try:
                await self._mcp_client.close()
            except Exception as e:
                logger.warning(f"Error closing MCP connection: {e}")
            finally:
                self._mcp_client = None
                self._is_connected = False


# Helper function for standalone MCP queries
async def execute_mcp_query(
    query: str, config: Optional[MCPConfig] = None
) -> Tuple[bool, Any]:
    """
    Execute a standalone MCP query.

    Args:
        query: Natural language query
        config: Optional MCP configuration (uses defaults if not provided)

    Returns:
        Tuple of (success: bool, result: Any)
    """
    if not config:
        config = MCPConfig()

    service = MCPIntegrationService(config)

    try:
        if await service.initialize():
            return await service.natural_language_command(query)
        else:
            return False, {"error": "Failed to initialize MCP connection"}
    finally:
        await service.close()

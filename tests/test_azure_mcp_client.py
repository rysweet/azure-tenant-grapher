"""
Test suite for Azure MCP Client

Tests the Azure MCP Client functionality including connection management,
natural language queries, and integration with existing services.
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.config_manager import AzureTenantGrapherConfig
from src.services.azure_mcp_client import (
    AzureMCPClient,
    MCPConnectionError,
    create_mcp_client,
    integrate_with_discovery_service,
)
from src.services.tenant_manager import Tenant, TenantManager


@pytest.fixture
def config():
    """Create a test configuration."""
    return AzureTenantGrapherConfig(tenant_id="test-tenant-123")


@pytest.fixture
def mock_tenant_manager():
    """Create a mock tenant manager."""
    manager = MagicMock(spec=TenantManager)
    manager.get_current_tenant = AsyncMock(
        return_value=Tenant(
            tenant_id="test-tenant-123",
            display_name="Test Tenant",
            subscription_ids=["sub-1", "sub-2"],
        )
    )
    return manager


@pytest.fixture
def mcp_client(config, mock_tenant_manager):
    """Create an MCP client for testing."""
    return AzureMCPClient(
        config=config,
        tenant_manager=mock_tenant_manager,
        mcp_endpoint="http://localhost:8080",
        enabled=True,
    )


class TestAzureMCPClient:
    """Test suite for AzureMCPClient."""

    @pytest.mark.asyncio
    async def test_client_initialization(self, config):
        """Test that client initializes correctly."""
        client = AzureMCPClient(config=config)

        assert client.config == config
        assert client.enabled is True
        assert client.connected is False
        assert client.mcp_endpoint == "http://localhost:8080"

    @pytest.mark.asyncio
    async def test_client_disabled(self, config):
        """Test that disabled client doesn't connect."""
        client = AzureMCPClient(config=config, enabled=False)

        result = await client.connect()
        assert result is False
        assert client.connected is False

    @pytest.mark.asyncio
    async def test_connect_success(self, mcp_client):
        """Test successful connection to MCP server."""
        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = AsyncMock()
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_session.get.return_value.__aenter__.return_value = mock_response
            mock_session_class.return_value = mock_session

            result = await mcp_client.connect()

            assert result is True
            assert mcp_client.connected is True
            mock_session.get.assert_called_with("http://localhost:8080/health")

    @pytest.mark.asyncio
    async def test_connect_failure(self, mcp_client):
        """Test failed connection to MCP server."""
        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = AsyncMock()
            mock_session.get.side_effect = Exception("Connection refused")
            mock_session_class.return_value = mock_session

            result = await mcp_client.connect()

            assert result is False
            assert mcp_client.connected is False

    @pytest.mark.asyncio
    async def test_disconnect(self, mcp_client):
        """Test disconnection from MCP server."""
        # Setup mock session
        mcp_client._session = AsyncMock()
        mcp_client.connected = True

        await mcp_client.disconnect()

        assert mcp_client._session is None
        assert mcp_client.connected is False

    @pytest.mark.asyncio
    async def test_discover_tenants(self, mcp_client):
        """Test tenant discovery via MCP."""
        mcp_client.connected = True

        with patch.object(mcp_client, "_execute_mcp_request") as mock_execute:
            mock_execute.return_value = {
                "tenants": [
                    {
                        "tenant_id": "tenant-1",
                        "display_name": "Tenant 1",
                        "subscription_count": 3,
                    }
                ]
            }

            tenants = await mcp_client.discover_tenants()

            assert len(tenants) == 1
            assert tenants[0]["tenant_id"] == "tenant-1"
            mock_execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_query_resources(self, mcp_client):
        """Test natural language resource queries."""
        mcp_client.connected = True

        with patch.object(mcp_client, "_execute_mcp_request") as mock_execute:
            mock_execute.return_value = {
                "resources": [
                    {
                        "name": "vm-1",
                        "type": "Microsoft.Compute/virtualMachines",
                        "location": "eastus",
                    }
                ],
                "metadata": {"query_time": datetime.utcnow().isoformat()},
            }

            result = await mcp_client.query_resources("show all VMs")

            assert result["status"] == "success"
            assert len(result["results"]) == 1
            assert result["results"][0]["name"] == "vm-1"
            assert result["operation_type"] == "virtual_machines"

    @pytest.mark.asyncio
    async def test_query_resources_disabled(self, config):
        """Test that queries return disabled status when MCP is disabled."""
        client = AzureMCPClient(config=config, enabled=False)

        result = await client.query_resources("show all VMs")

        assert result["status"] == "disabled"
        assert result["message"] == "MCP integration is not enabled"

    @pytest.mark.asyncio
    async def test_get_identity_info(self, mcp_client):
        """Test getting identity information."""
        mcp_client.connected = True

        with patch.object(mcp_client, "_execute_mcp_request") as mock_execute:
            mock_execute.return_value = {
                "identity": {
                    "type": "ServicePrincipal",
                    "id": "sp-123",
                    "name": "Test SP",
                },
                "permissions": ["Reader"],
                "roles": ["Contributor"],
            }

            result = await mcp_client.get_identity_info()

            assert result["status"] == "success"
            assert result["identity"]["type"] == "ServicePrincipal"
            assert "Reader" in result["permissions"]

    @pytest.mark.asyncio
    async def test_execute_operation(self, mcp_client):
        """Test executing specific operations."""
        mcp_client.connected = True

        operation = {
            "type": "list_resources",
            "resource_type": "Microsoft.Storage/storageAccounts",
        }

        with patch.object(mcp_client, "_execute_mcp_request") as mock_execute:
            mock_execute.return_value = {"status": "success", "resources": []}

            result = await mcp_client.execute_operation(operation)

            assert result["status"] == "success"
            mock_execute.assert_called_once()
            call_args = mock_execute.call_args[0][0]
            assert call_args["type"] == "list_resources"

    @pytest.mark.asyncio
    async def test_execute_operation_not_connected(self, mcp_client):
        """Test that operations fail when not connected."""
        mcp_client.connected = False

        with patch.object(mcp_client, "connect") as mock_connect:
            mock_connect.return_value = False

            with pytest.raises(MCPConnectionError):
                await mcp_client.execute_operation({"type": "test"})

    def test_analyze_query(self, mcp_client):
        """Test query analysis for operation type detection."""
        # Test various query patterns
        assert mcp_client._analyze_query("list all resources") == "list_resources"
        assert mcp_client._analyze_query("show VMs") == "virtual_machines"
        assert mcp_client._analyze_query("find storage accounts") == "storage"
        assert mcp_client._analyze_query("get my identity") == "get_identity"
        assert mcp_client._analyze_query("discover tenants") == "discover_tenants"
        assert mcp_client._analyze_query("something else") == "general_query"

    @pytest.mark.asyncio
    async def test_get_natural_language_help(self, mcp_client):
        """Test getting natural language query examples."""
        examples = await mcp_client.get_natural_language_help()

        assert isinstance(examples, list)
        assert len(examples) > 0
        assert any("virtual machines" in ex.lower() for ex in examples)

    def test_is_available(self, mcp_client):
        """Test availability check."""
        mcp_client.enabled = True
        mcp_client.connected = False
        assert mcp_client.is_available() is False

        mcp_client.connected = True
        assert mcp_client.is_available() is True

        mcp_client.enabled = False
        assert mcp_client.is_available() is False

    @pytest.mark.asyncio
    async def test_context_manager(self, mcp_client):
        """Test async context manager functionality."""
        with patch.object(mcp_client, "connect") as mock_connect:
            with patch.object(mcp_client, "disconnect") as mock_disconnect:
                mock_connect.return_value = True

                async with mcp_client as client:
                    assert client == mcp_client

                mock_connect.assert_called_once()
                mock_disconnect.assert_called_once()


class TestFactoryFunctions:
    """Test factory and integration functions."""

    @pytest.mark.asyncio
    async def test_create_mcp_client(self, config):
        """Test MCP client factory function."""
        with patch(
            "src.services.azure_mcp_client.AzureMCPClient.connect"
        ) as mock_connect:
            mock_connect.return_value = True

            client = await create_mcp_client(config=config, auto_connect=True)

            assert isinstance(client, AzureMCPClient)
            assert client.config == config
            mock_connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_mcp_client_no_auto_connect(self, config):
        """Test creating client without auto-connect."""
        client = await create_mcp_client(config=config, auto_connect=False)

        assert isinstance(client, AzureMCPClient)
        assert client.connected is False

    def test_integrate_with_discovery_service(self, config, mcp_client):
        """Test integration with discovery service."""
        # Create a mock discovery service
        discovery_service = MagicMock()

        # Integrate MCP client
        integrate_with_discovery_service(discovery_service, mcp_client)

        # Check that MCP client was added
        assert discovery_service.mcp_client == mcp_client

        # Check that natural language method was added
        assert hasattr(discovery_service, "query_with_natural_language")

    @pytest.mark.asyncio
    async def test_integrated_natural_language_query(self, config, mcp_client):
        """Test natural language queries through integrated discovery service."""
        # Create and integrate
        discovery_service = MagicMock()
        integrate_with_discovery_service(discovery_service, mcp_client)

        # Mock MCP client as available
        mcp_client.is_available = MagicMock(return_value=True)
        mcp_client.query_resources = AsyncMock(
            return_value={"status": "success", "results": [{"name": "test-vm"}]}
        )

        # Test query through discovery service
        result = await discovery_service.query_with_natural_language("show VMs")

        assert result["status"] == "success"
        assert len(result["results"]) == 1
        mcp_client.query_resources.assert_called_once_with("show VMs")

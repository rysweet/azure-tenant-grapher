"""
Tests for MCP (Model Context Protocol) Integration Service

Tests MCP client connection, fallback behavior, natural language query parsing,
and mock MCP server responses.
"""

import asyncio
import json
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.config_manager import MCPConfig
from src.services.mcp_integration import (
    MCPIntegrationService,
    execute_mcp_query,
)


class TestMCPConfig:
    """Test MCP configuration handling."""

    def test_default_config(self):
        """Test default MCP configuration values."""
        config = MCPConfig()
        assert config.endpoint == "http://localhost:8080"
        assert config.enabled is False
        assert config.timeout == 30
        assert config.api_key is None

    def test_config_validation(self):
        """Test MCP configuration validation."""
        # Valid config
        config = MCPConfig(enabled=True, endpoint="http://test:8080", timeout=60)
        config.__post_init__()  # Should not raise

        # Invalid timeout
        with pytest.raises(ValueError, match="timeout must be at least 1"):
            config = MCPConfig(timeout=0)
            config.__post_init__()

        # Missing endpoint when enabled
        with pytest.raises(ValueError, match="endpoint is required"):
            config = MCPConfig(enabled=True, endpoint="")
            config.__post_init__()

    def test_config_from_env(self, monkeypatch):
        """Test MCP configuration from environment variables."""
        monkeypatch.setenv("MCP_ENDPOINT", "http://custom:9090")
        monkeypatch.setenv("MCP_ENABLED", "true")
        monkeypatch.setenv("MCP_TIMEOUT", "45")
        monkeypatch.setenv("MCP_API_KEY", "test-key-123")

        config = MCPConfig()
        assert config.endpoint == "http://custom:9090"
        assert config.enabled is True
        assert config.timeout == 45
        assert config.api_key == "test-key-123"


class TestMCPIntegrationService:
    """Test MCP Integration Service functionality."""

    @pytest.fixture
    def mock_config(self):
        """Create a test MCP configuration."""
        return MCPConfig(
            enabled=True,
            endpoint="http://test-mcp:8080",
            timeout=30,
            api_key="test-api-key",
        )

    @pytest.fixture
    def mock_discovery_service(self):
        """Create a mock discovery service."""
        mock = MagicMock()
        mock.discover_resources = AsyncMock(return_value=[])
        return mock

    @pytest.fixture
    def service(self, mock_config, mock_discovery_service):
        """Create an MCP integration service instance."""
        return MCPIntegrationService(mock_config, mock_discovery_service)

    @pytest.mark.asyncio
    async def test_initialize_success(self, service):
        """Test successful MCP initialization."""
        with patch("src.services.mcp_integration.MCPClient") as MockClient:
            mock_client = MagicMock()
            mock_client.query = AsyncMock(return_value="test response")
            MockClient.return_value = mock_client

            result = await service.initialize()
            assert result is True
            assert service.is_available is True

    @pytest.mark.asyncio
    async def test_initialize_disabled(self, mock_discovery_service):
        """Test initialization when MCP is disabled."""
        config = MCPConfig(enabled=False)
        service = MCPIntegrationService(config, mock_discovery_service)

        result = await service.initialize()
        assert result is False
        assert service.is_available is False

    @pytest.mark.asyncio
    async def test_initialize_import_error(self, service):
        """Test initialization when MCP client is not available."""
        with patch(
            "src.services.mcp_integration.MCPClient",
            side_effect=ImportError("Module not found"),
        ):
            result = await service.initialize()
            assert result is False
            assert service.is_available is False

    @pytest.mark.asyncio
    async def test_initialize_connection_error(self, service):
        """Test initialization with connection error."""
        with patch("src.services.mcp_integration.MCPClient") as MockClient:
            mock_client = MagicMock()
            mock_client.query = AsyncMock(side_effect=ConnectionError("Connection failed"))
            MockClient.return_value = mock_client

            result = await service.initialize()
            assert result is False
            assert service.is_available is False

    @pytest.mark.asyncio
    async def test_query_resources_success(self, service):
        """Test successful resource query via MCP."""
        # Set up mock MCP client
        service._mcp_client = MagicMock()
        service._is_connected = True

        mock_resources = [
            {"name": "vm1", "type": "VirtualMachine", "location": "eastus"},
            {"name": "storage1", "type": "StorageAccount", "location": "westus"},
        ]
        service._mcp_client.query = AsyncMock(return_value=json.dumps(mock_resources))

        success, resources = await service.query_resources("list all resources")
        assert success is True
        assert len(resources) == 2
        assert resources[0]["name"] == "vm1"

    @pytest.mark.asyncio
    async def test_query_resources_fallback(self, service):
        """Test fallback when MCP is not available."""
        service._is_connected = False

        success, resources = await service.query_resources("list all resources")
        assert success is False
        assert resources == []

    @pytest.mark.asyncio
    async def test_query_resources_timeout(self, service):
        """Test query timeout handling."""
        service._mcp_client = MagicMock()
        service._is_connected = True
        service._mcp_client.query = AsyncMock(side_effect=asyncio.TimeoutError())

        success, resources = await service.query_resources("list all resources")
        assert success is False
        assert resources == []

    @pytest.mark.asyncio
    async def test_query_resources_json_error(self, service):
        """Test handling of invalid JSON response."""
        service._mcp_client = MagicMock()
        service._is_connected = True
        service._mcp_client.query = AsyncMock(return_value="invalid json {]")

        success, resources = await service.query_resources("list all resources")
        assert success is False
        assert resources == []

    @pytest.mark.asyncio
    async def test_discover_resources_with_mcp(self, service, mock_discovery_service):
        """Test resource discovery using MCP."""
        service._mcp_client = MagicMock()
        service._is_connected = True

        mock_resources = [{"name": "resource1", "type": "VM"}]
        service._mcp_client.query = AsyncMock(return_value=json.dumps(mock_resources))

        resources = await service.discover_resources("sub-123", use_mcp=True)
        assert len(resources) == 1
        assert resources[0]["name"] == "resource1"
        mock_discovery_service.discover_resources.assert_not_called()

    @pytest.mark.asyncio
    async def test_discover_resources_fallback(self, service, mock_discovery_service):
        """Test fallback to traditional discovery."""
        service._is_connected = False
        mock_discovery_service.discover_resources.return_value = [
            {"name": "api-resource", "type": "Storage"}
        ]

        resources = await service.discover_resources("sub-123", use_mcp=True)
        assert len(resources) == 1
        assert resources[0]["name"] == "api-resource"
        mock_discovery_service.discover_resources.assert_called_once()

    @pytest.mark.asyncio
    async def test_discover_resources_no_mcp(self, service, mock_discovery_service):
        """Test discovery with MCP explicitly disabled."""
        service._mcp_client = MagicMock()
        service._is_connected = True
        mock_discovery_service.discover_resources.return_value = [
            {"name": "api-resource", "type": "Storage"}
        ]

        resources = await service.discover_resources("sub-123", use_mcp=False)
        assert len(resources) == 1
        assert resources[0]["name"] == "api-resource"
        mock_discovery_service.discover_resources.assert_called_once()

    @pytest.mark.asyncio
    async def test_analyze_relationships(self, service):
        """Test relationship analysis via MCP."""
        service._mcp_client = MagicMock()
        service._is_connected = True

        mock_analysis = {
            "resource_id": "res-123",
            "relationships": [
                {"target": "res-456", "type": "depends_on"},
                {"target": "res-789", "type": "references"},
            ],
        }
        service._mcp_client.query = AsyncMock(return_value=json.dumps(mock_analysis))

        result = await service.analyze_resource_relationships("res-123")
        assert result["resource_id"] == "res-123"
        assert result["mcp_used"] is True
        assert len(result["relationships"]) == 2

    @pytest.mark.asyncio
    async def test_analyze_relationships_no_mcp(self, service):
        """Test relationship analysis fallback."""
        service._is_connected = False

        result = await service.analyze_resource_relationships("res-123")
        assert result["resource_id"] == "res-123"
        assert result["mcp_used"] is False
        assert result["relationships"] == []

    @pytest.mark.asyncio
    async def test_get_resource_insights(self, service):
        """Test AI-powered insights generation."""
        service._mcp_client = MagicMock()
        service._is_connected = True

        mock_insights = {
            "insights": ["Public endpoint exposed", "No encryption at rest"],
            "recommendations": ["Enable private endpoints", "Enable encryption"],
        }
        service._mcp_client.query = AsyncMock(return_value=json.dumps(mock_insights))

        resource_data = {"name": "storage1", "type": "StorageAccount"}
        result = await service.get_resource_insights(resource_data)
        assert result["mcp_used"] is True
        assert len(result["insights"]) == 2
        assert len(result["recommendations"]) == 2

    @pytest.mark.asyncio
    async def test_natural_language_command(self, service):
        """Test natural language command execution."""
        service._mcp_client = MagicMock()
        service._is_connected = True

        mock_result = {"action": "list", "resources": ["vm1", "vm2"]}
        service._mcp_client.query = AsyncMock(return_value=json.dumps(mock_result))

        success, result = await service.natural_language_command("show all VMs")
        assert success is True
        assert result["action"] == "list"

    @pytest.mark.asyncio
    async def test_natural_language_command_timeout(self, service):
        """Test command timeout handling."""
        service._mcp_client = MagicMock()
        service._is_connected = True
        service._mcp_client.query = AsyncMock(side_effect=asyncio.TimeoutError())

        success, result = await service.natural_language_command("complex query")
        assert success is False
        assert "timed out" in result["error"]
        assert "suggestion" in result

    @pytest.mark.asyncio
    async def test_close_connection(self, service):
        """Test closing MCP connection."""
        mock_client = MagicMock()
        mock_client.close = AsyncMock()
        service._mcp_client = mock_client
        service._is_connected = True

        await service.close()
        mock_client.close.assert_called_once()
        assert service._mcp_client is None
        assert service._is_connected is False

    @pytest.mark.asyncio
    async def test_close_connection_error(self, service):
        """Test handling errors during connection close."""
        mock_client = MagicMock()
        mock_client.close = AsyncMock(side_effect=Exception("Close failed"))
        service._mcp_client = mock_client
        service._is_connected = True

        await service.close()  # Should not raise
        assert service._mcp_client is None
        assert service._is_connected is False


class TestExecuteMCPQuery:
    """Test the standalone MCP query helper function."""

    @pytest.mark.asyncio
    async def test_execute_query_success(self):
        """Test successful standalone query execution."""
        with patch("src.services.mcp_integration.MCPIntegrationService") as MockService:
            mock_service = MockService.return_value
            mock_service.initialize = AsyncMock(return_value=True)
            mock_service.natural_language_command = AsyncMock(
                return_value=(True, {"result": "success"})
            )
            mock_service.close = AsyncMock()

            success, result = await execute_mcp_query("test query")
            assert success is True
            assert result["result"] == "success"
            mock_service.initialize.assert_called_once()
            mock_service.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_query_init_failure(self):
        """Test query execution with initialization failure."""
        with patch("src.services.mcp_integration.MCPIntegrationService") as MockService:
            mock_service = MockService.return_value
            mock_service.initialize = AsyncMock(return_value=False)
            mock_service.close = AsyncMock()

            success, result = await execute_mcp_query("test query")
            assert success is False
            assert "Failed to initialize" in result["error"]
            mock_service.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_query_with_custom_config(self):
        """Test query execution with custom configuration."""
        custom_config = MCPConfig(
            endpoint="http://custom:9090",
            enabled=True,
            timeout=45,
        )

        with patch("src.services.mcp_integration.MCPIntegrationService") as MockService:
            mock_service = MockService.return_value
            mock_service.initialize = AsyncMock(return_value=True)
            mock_service.natural_language_command = AsyncMock(
                return_value=(True, {"result": "custom"})
            )
            mock_service.close = AsyncMock()

            success, result = await execute_mcp_query("test query", custom_config)
            assert success is True
            assert result["result"] == "custom"
            MockService.assert_called_once_with(custom_config)


class TestMCPIntegrationWithRealResponses:
    """Test MCP integration with realistic response patterns."""

    @pytest.fixture
    def service_with_mcp(self, mock_config, mock_discovery_service):
        """Create a service with mocked MCP client."""
        service = MCPIntegrationService(mock_config, mock_discovery_service)
        service._mcp_client = MagicMock()
        service._is_connected = True
        return service

    @pytest.mark.asyncio
    async def test_complex_resource_query(self, service_with_mcp):
        """Test handling of complex resource query response."""
        complex_response = {
            "resources": [
                {
                    "id": "/subscriptions/sub-123/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",
                    "name": "vm1",
                    "type": "Microsoft.Compute/virtualMachines",
                    "location": "eastus",
                    "properties": {
                        "vmSize": "Standard_D2s_v3",
                        "osProfile": {"computerName": "vm1"},
                    },
                    "tags": {"environment": "production"},
                }
            ],
            "metadata": {"query_time": "2024-01-01T00:00:00Z", "total_count": 1},
        }

        service_with_mcp._mcp_client.query = AsyncMock(
            return_value=json.dumps(complex_response)
        )

        success, resources = await service_with_mcp.query_resources(
            "list production VMs in eastus"
        )
        assert success is True
        assert isinstance(resources, dict)
        assert "resources" in resources
        assert len(resources["resources"]) == 1

    @pytest.mark.asyncio
    async def test_security_analysis_response(self, service_with_mcp):
        """Test handling of security analysis response."""
        security_response = {
            "insights": [
                {
                    "severity": "high",
                    "category": "network",
                    "finding": "Public IP address exposed without NSG restrictions",
                    "resource": "vm1",
                },
                {
                    "severity": "medium",
                    "category": "identity",
                    "finding": "Service principal has excessive permissions",
                    "resource": "sp-app1",
                },
            ],
            "recommendations": [
                {
                    "priority": 1,
                    "action": "Apply network security group to VM",
                    "impact": "Reduces attack surface",
                },
                {
                    "priority": 2,
                    "action": "Review and reduce service principal permissions",
                    "impact": "Follows principle of least privilege",
                },
            ],
            "risk_score": 7.5,
        }

        service_with_mcp._mcp_client.query = AsyncMock(
            return_value=json.dumps(security_response)
        )

        result = await service_with_mcp.get_resource_insights(
            {"name": "vm1", "type": "VirtualMachine"}
        )
        assert result["mcp_used"] is True
        assert "insights" in result
        assert len(result["insights"]) == 2
        assert result["risk_score"] == 7.5
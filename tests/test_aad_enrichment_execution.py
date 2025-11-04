"""
Test to verify AAD enrichment actually executes during build_graph.

This test ensures that:
1. AAD Graph Service is properly initialized
2. Service principals are fetched from Graph API
3. Service principals are added to the resource processing queue
4. Service principals are processed and stored in Neo4j
"""

import asyncio
import logging
import os
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.azure_tenant_grapher import AzureTenantGrapher
from src.config_manager import AzureTenantGrapherConfig

logger = logging.getLogger(__name__)


@pytest.fixture
def mock_config():
    """Create a test configuration with AAD import enabled."""
    config = AzureTenantGrapherConfig()
    # Enable AAD import
    config.processing.enable_aad_import = True
    # Disable container auto-start for tests
    config.processing.auto_start_container = False
    # Set a small resource limit for fast testing
    config.processing.resource_limit = 5
    return config


@pytest.fixture
def mock_aad_service():
    """Create a mock AAD Graph Service."""
    service = MagicMock()
    service.get_service_principals = AsyncMock(
        return_value=[
            {
                "id": "sp-test-1",
                "displayName": "Test Service Principal 1",
                "appId": "app-test-1",
                "servicePrincipalType": "Application",
            },
            {
                "id": "sp-test-2",
                "displayName": "Test Service Principal 2",
                "appId": "app-test-2",
                "servicePrincipalType": "ManagedIdentity",
            },
        ]
    )
    return service


@pytest.mark.asyncio
async def test_aad_enrichment_executes(mock_config, mock_aad_service, caplog):
    """Test that AAD enrichment code actually executes during build_graph."""
    caplog.set_level(logging.INFO)

    # Mock the session manager to avoid Neo4j connection
    with patch("src.utils.session_manager.Neo4jSessionManager"):
        # Mock discovery service to return minimal data
        with patch("src.services.azure_discovery_service.AzureDiscoveryService") as MockDiscovery:
            mock_discovery = MockDiscovery.return_value
            mock_discovery.discover_subscriptions = AsyncMock(
                return_value=[{"id": "sub-test-1", "display_name": "Test Subscription"}]
            )
            mock_discovery.discover_resources_in_subscription = AsyncMock(
                return_value=[
                    {
                        "id": "/subscriptions/sub-test-1/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/test-vm",
                        "name": "test-vm",
                        "type": "Microsoft.Compute/virtualMachines",
                        "location": "eastus",
                        "tags": {},
                        "properties": {},
                        "subscription_id": "sub-test-1",
                        "resource_group": "test-rg",
                    }
                ]
            )

            # Mock AAD Graph Service
            with patch("src.services.aad_graph_service.AADGraphService") as MockAAD:
                MockAAD.return_value = mock_aad_service

                # Mock processing service to track what resources it receives
                with patch(
                    "src.services.resource_processing_service.ResourceProcessingService"
                ) as MockProcessing:
                    mock_processing = MockProcessing.return_value
                    received_resources = []

                    async def capture_resources(resources, **kwargs):
                        """Capture resources passed to process_resources."""
                        received_resources.extend(resources)
                        # Return mock stats
                        stats = MagicMock()
                        stats.to_dict = MagicMock(
                            return_value={
                                "total_resources": len(resources),
                                "processed": len(resources),
                                "successful": len(resources),
                                "failed": 0,
                                "skipped": 0,
                            }
                        )
                        return stats

                    mock_processing.process_resources = AsyncMock(
                        side_effect=capture_resources
                    )

                    # Create grapher and run build_graph
                    grapher = AzureTenantGrapher(mock_config)
                    result = await grapher.build_graph()

                    # Verify the result
                    assert result["success"] is True, "build_graph should succeed"

                    # Verify AAD service was called
                    mock_aad_service.get_service_principals.assert_called_once()

                    # Verify service principals were added to resources
                    sp_resources = [
                        r
                        for r in received_resources
                        if r.get("type") == "Microsoft.Graph/servicePrincipals"
                    ]
                    assert len(sp_resources) == 2, (
                        "Should have 2 service principal resources"
                    )

                    # Verify service principal properties
                    sp1 = next(
                        (r for r in sp_resources if r["name"] == "Test Service Principal 1"),
                        None,
                    )
                    assert sp1 is not None, "Should find first service principal"
                    assert sp1["id"] == "/servicePrincipals/sp-test-1"
                    assert sp1["properties"]["appId"] == "app-test-1"
                    assert sp1["location"] == "global"
                    assert sp1["resource_group"] is None

                    sp2 = next(
                        (r for r in sp_resources if r["name"] == "Test Service Principal 2"),
                        None,
                    )
                    assert sp2 is not None, "Should find second service principal"
                    assert sp2["id"] == "/servicePrincipals/sp-test-2"
                    assert sp2["properties"]["appId"] == "app-test-2"

                    # Verify logging output
                    assert (
                        "Enriching with Entra ID (Azure AD) identity data" in caplog.text
                    ), "Should log AAD enrichment start"
                    assert (
                        "Fetching service principals from Microsoft Graph API"
                        in caplog.text
                    ), "Should log fetching service principals"
                    assert (
                        "Successfully fetched 2 service principals from Graph API"
                        in caplog.text
                    ), "Should log successful fetch"
                    assert (
                        "Successfully added 2 service principals to processing queue"
                        in caplog.text
                    ), "Should log adding to queue"


@pytest.mark.asyncio
async def test_aad_enrichment_handles_errors(mock_config, caplog):
    """Test that AAD enrichment handles errors gracefully."""
    caplog.set_level(logging.WARNING)

    # Mock the session manager
    with patch("src.utils.session_manager.Neo4jSessionManager"):
        # Mock discovery service
        with patch("src.services.azure_discovery_service.AzureDiscoveryService") as MockDiscovery:
            mock_discovery = MockDiscovery.return_value
            mock_discovery.discover_subscriptions = AsyncMock(
                return_value=[{"id": "sub-test-1", "display_name": "Test Subscription"}]
            )
            mock_discovery.discover_resources_in_subscription = AsyncMock(
                return_value=[
                    {
                        "id": "/subscriptions/sub-test-1/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/test-vm",
                        "name": "test-vm",
                        "type": "Microsoft.Compute/virtualMachines",
                        "location": "eastus",
                        "tags": {},
                        "properties": {},
                        "subscription_id": "sub-test-1",
                        "resource_group": "test-rg",
                    }
                ]
            )

            # Mock AAD Graph Service to raise an error
            with patch("src.services.aad_graph_service.AADGraphService") as MockAAD:
                mock_aad_service = MockAAD.return_value
                mock_aad_service.get_service_principals = AsyncMock(
                    side_effect=Exception("Graph API error: Insufficient permissions")
                )

                # Mock processing service
                with patch("src.services.resource_processing_service.ResourceProcessingService") as MockProcessing:
                    mock_processing = MockProcessing.return_value
                    stats = MagicMock()
                    stats.to_dict = MagicMock(
                        return_value={
                            "total_resources": 1,
                            "processed": 1,
                            "successful": 1,
                            "failed": 0,
                        }
                    )
                    mock_processing.process_resources = AsyncMock(return_value=stats)

                    # Create grapher and run build_graph
                    grapher = AzureTenantGrapher(mock_config)
                    result = await grapher.build_graph()

                    # Verify build_graph still succeeds despite AAD error
                    assert result["success"] is True, (
                        "build_graph should succeed even if AAD enrichment fails"
                    )

                    # Verify error was logged
                    assert "Failed to fetch service principals from Graph API" in caplog.text
                    assert "Continuing without service principal enrichment" in caplog.text


@pytest.mark.asyncio
async def test_aad_enrichment_disabled(mock_config, caplog):
    """Test that AAD enrichment is skipped when disabled."""
    caplog.set_level(logging.INFO)

    # Disable AAD import
    mock_config.processing.enable_aad_import = False

    # Mock the session manager
    with patch("src.utils.session_manager.Neo4jSessionManager"):
        # Mock discovery service
        with patch("src.services.azure_discovery_service.AzureDiscoveryService") as MockDiscovery:
            mock_discovery = MockDiscovery.return_value
            mock_discovery.discover_subscriptions = AsyncMock(
                return_value=[{"id": "sub-test-1", "display_name": "Test Subscription"}]
            )
            mock_discovery.discover_resources_in_subscription = AsyncMock(
                return_value=[
                    {
                        "id": "/subscriptions/sub-test-1/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/test-vm",
                        "name": "test-vm",
                        "type": "Microsoft.Compute/virtualMachines",
                        "location": "eastus",
                        "tags": {},
                        "properties": {},
                        "subscription_id": "sub-test-1",
                        "resource_group": "test-rg",
                    }
                ]
            )

            # Mock processing service
            with patch("src.services.resource_processing_service.ResourceProcessingService") as MockProcessing:
                mock_processing = MockProcessing.return_value
                received_resources = []

                async def capture_resources(resources, **kwargs):
                    received_resources.extend(resources)
                    stats = MagicMock()
                    stats.to_dict = MagicMock(
                        return_value={
                            "total_resources": len(resources),
                            "processed": len(resources),
                            "successful": len(resources),
                            "failed": 0,
                        }
                    )
                    return stats

                mock_processing.process_resources = AsyncMock(side_effect=capture_resources)

                # Create grapher and run build_graph
                grapher = AzureTenantGrapher(mock_config)
                result = await grapher.build_graph()

                # Verify no service principals were added
                sp_resources = [
                    r
                    for r in received_resources
                    if r.get("type") == "Microsoft.Graph/servicePrincipals"
                ]
                assert len(sp_resources) == 0, "Should have no service principal resources"

                # Verify logging output
                assert "AAD enrichment disabled" in caplog.text
                assert "Skipping service principal discovery" in caplog.text

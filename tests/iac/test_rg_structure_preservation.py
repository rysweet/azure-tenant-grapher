"""Tests for Resource Group Structure Preservation (GAP-017 / Issue #313).

Tests the --preserve-rg-structure flag that maintains source tenant's
resource group organizational structure in generated Terraform.
"""

from unittest.mock import AsyncMock, Mock

import pytest

from src.iac.emitters.terraform.emitter import TerraformEmitter
from src.iac.emitters.terraform.utils.resource_helpers import (
    extract_resource_group_from_id,
)
from src.iac.traverser import GraphTraverser, TenantGraph


class TestResourceGroupExtraction:
    """Test utility function for extracting RG name from Azure resource IDs."""

    def test_extract_rg_from_standard_resource_id(self):
        """Test extraction from standard Azure resource ID."""
        resource_id = "/subscriptions/12345/resourceGroups/my-rg/providers/Microsoft.Network/virtualNetworks/my-vnet"
        result = extract_resource_group_from_id(resource_id)
        assert result == "my-rg"

    def test_extract_rg_from_storage_account_id(self):
        """Test extraction from storage account resource ID."""
        resource_id = "/subscriptions/12345/resourceGroups/storage-rg/providers/Microsoft.Storage/storageAccounts/mystorageacct"
        result = extract_resource_group_from_id(resource_id)
        assert result == "storage-rg"

    def test_extract_rg_with_hyphens_and_underscores(self):
        """Test extraction with complex RG names."""
        resource_id = "/subscriptions/12345/resourceGroups/team-prod_east-rg/providers/Microsoft.Compute/virtualMachines/vm1"
        result = extract_resource_group_from_id(resource_id)
        assert result == "team-prod_east-rg"

    def test_extract_rg_returns_none_for_invalid_id(self):
        """Test that invalid IDs return None."""
        assert extract_resource_group_from_id("") is None
        assert extract_resource_group_from_id("/invalid/path") is None
        assert extract_resource_group_from_id(None) is None

    def test_extract_rg_returns_none_for_subscription_level_resource(self):
        """Test that subscription-level resources return None."""
        resource_id = "/subscriptions/12345/providers/Microsoft.Resources/deployments/my-deployment"
        result = extract_resource_group_from_id(resource_id)
        assert result is None


class TestTraverserRGMetadata:
    """Test that traverser adds RG metadata to resources."""

    @pytest.mark.asyncio
    async def test_traverser_adds_source_rg_metadata(self):
        """Test that traverse() adds _source_rg metadata to resources."""
        # Create mock driver
        mock_driver = Mock()
        mock_session = AsyncMock()
        mock_driver.session.return_value.__aenter__.return_value = mock_session

        # Mock Neo4j query result
        mock_result = [
            {
                "r": {
                    "id": "/subscriptions/sub1/resourceGroups/frontend-rg/providers/Microsoft.Web/sites/webapp1",
                    "type": "Microsoft.Web/sites",
                    "name": "webapp1",
                },
                "rels": [],
                "original_id": None,
                "original_properties": None,
            },
            {
                "r": {
                    "id": "/subscriptions/sub1/resourceGroups/backend-rg/providers/Microsoft.Sql/servers/sqlserver1",
                    "type": "Microsoft.Sql/servers",
                    "name": "sqlserver1",
                },
                "rels": [],
                "original_id": None,
                "original_properties": None,
            },
        ]
        mock_session.run.return_value = AsyncMock()
        mock_session.run.return_value.__aiter__.return_value = iter(mock_result)

        # Create traverser and traverse
        traverser = GraphTraverser(mock_driver)
        graph = await traverser.traverse()

        # Verify resources have _source_rg metadata
        assert len(graph.resources) == 2
        assert graph.resources[0]["_source_rg"] == "frontend-rg"
        assert graph.resources[1]["_source_rg"] == "backend-rg"


class TestMultiRGEmission:
    """Test Terraform emission with multiple resource groups."""

    def test_single_rg_default_behavior(self):
        """Test default behavior - all resources in single RG (no flag)."""
        emitter = TerraformEmitter()

        resources = [
            {
                "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1",
                "type": "Microsoft.Network/virtualNetworks",
                "name": "vnet1",
                "_source_rg": "rg1",
            },
            {
                "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Storage/storageAccounts/storage1",
                "type": "Microsoft.Storage/storageAccounts",
                "name": "storage1",
                "_source_rg": "rg1",
            },
        ]

        graph = TenantGraph(resources=resources)
        config = emitter.emit(graph.resources, preserve_rg_structure=False)

        # Should have exactly 1 resource group
        rg_resources = list(
            config.get("resource", {}).get("azurerm_resource_group", {}).keys()
        )
        assert len(rg_resources) == 1

    def test_multi_rg_with_preserve_flag(self):
        """Test preserve_rg_structure flag creates multiple RGs."""
        emitter = TerraformEmitter()

        resources = [
            {
                "id": "/subscriptions/sub1/resourceGroups/frontend-rg/providers/Microsoft.Web/sites/webapp1",
                "type": "Microsoft.Web/sites",
                "name": "webapp1",
                "_source_rg": "frontend-rg",
            },
            {
                "id": "/subscriptions/sub1/resourceGroups/backend-rg/providers/Microsoft.Sql/servers/sqlserver1",
                "type": "Microsoft.Sql/servers",
                "name": "sqlserver1",
                "_source_rg": "backend-rg",
            },
            {
                "id": "/subscriptions/sub1/resourceGroups/shared-rg/providers/Microsoft.KeyVault/vaults/keyvault1",
                "type": "Microsoft.KeyVault/vaults",
                "name": "keyvault1",
                "_source_rg": "shared-rg",
            },
        ]

        graph = TenantGraph(resources=resources)
        config = emitter.emit(
            graph.resources, preserve_rg_structure=True, location="eastus"
        )

        # Should have 3 resource groups
        rg_resources = config.get("resource", {}).get("azurerm_resource_group", {})
        assert len(rg_resources) == 3
        assert "frontend_rg" in rg_resources
        assert "backend_rg" in rg_resources
        assert "shared_rg" in rg_resources

    def test_resources_reference_correct_rg(self):
        """Test that resources reference their correct target RG."""
        emitter = TerraformEmitter()

        resources = [
            {
                "id": "/subscriptions/sub1/resourceGroups/network-rg/providers/Microsoft.Network/virtualNetworks/vnet1",
                "type": "Microsoft.Network/virtualNetworks",
                "name": "vnet1",
                "location": "eastus",
                "_source_rg": "network-rg",
            },
        ]

        graph = TenantGraph(resources=resources)
        config = emitter.emit(
            graph.resources, preserve_rg_structure=True, location="eastus"
        )

        # VNet should reference the network-rg resource group
        vnet_config = config["resource"]["azurerm_virtual_network"]["vnet1"]
        assert "resource_group_name" in vnet_config
        # Should be a Terraform reference to the RG
        assert "azurerm_resource_group" in vnet_config["resource_group_name"]
        assert "network_rg" in vnet_config["resource_group_name"]


class TestCrossRGDependencies:
    """Test handling of dependencies across resource groups."""

    def test_cross_rg_vnet_peering(self):
        """Test VNet peering between RGs uses correct references."""
        emitter = TerraformEmitter()

        resources = [
            {
                "id": "/subscriptions/sub1/resourceGroups/hub-rg/providers/Microsoft.Network/virtualNetworks/vnet-hub",
                "type": "Microsoft.Network/virtualNetworks",
                "name": "vnet-hub",
                "location": "eastus",
                "properties": {"addressSpace": {"addressPrefixes": ["10.0.0.0/16"]}},
                "_source_rg": "hub-rg",
            },
            {
                "id": "/subscriptions/sub1/resourceGroups/spoke-rg/providers/Microsoft.Network/virtualNetworks/vnet-spoke",
                "type": "Microsoft.Network/virtualNetworks",
                "name": "vnet-spoke",
                "location": "eastus",
                "properties": {"addressSpace": {"addressPrefixes": ["10.1.0.0/16"]}},
                "_source_rg": "spoke-rg",
            },
        ]

        graph = TenantGraph(resources=resources)
        config = emitter.emit(
            graph.resources, preserve_rg_structure=True, location="eastus"
        )

        # Verify both VNets created in correct RGs
        assert "hub_rg" in config["resource"]["azurerm_resource_group"]
        assert "spoke_rg" in config["resource"]["azurerm_resource_group"]

        # Verify VNets reference their respective RGs
        hub_vnet = config["resource"]["azurerm_virtual_network"]["vnet_hub"]
        spoke_vnet = config["resource"]["azurerm_virtual_network"]["vnet_spoke"]

        assert "hub_rg" in hub_vnet["resource_group_name"]
        assert "spoke_rg" in spoke_vnet["resource_group_name"]

    def test_cross_rg_private_endpoint(self):
        """Test private endpoint referencing storage account in different RG."""
        emitter = TerraformEmitter()

        resources = [
            {
                "id": "/subscriptions/sub1/resourceGroups/data-rg/providers/Microsoft.Storage/storageAccounts/storageacct1",
                "type": "Microsoft.Storage/storageAccounts",
                "name": "storageacct1",
                "location": "eastus",
                "_source_rg": "data-rg",
            },
            {
                "id": "/subscriptions/sub1/resourceGroups/app-rg/providers/Microsoft.Network/privateEndpoints/pe-storage",
                "type": "Microsoft.Network/privateEndpoints",
                "name": "pe-storage",
                "location": "eastus",
                "properties": {
                    "privateLinkServiceConnections": [
                        {
                            "privateLinkServiceId": "/subscriptions/sub1/resourceGroups/data-rg/providers/Microsoft.Storage/storageAccounts/storageacct1"
                        }
                    ]
                },
                "_source_rg": "app-rg",
            },
        ]

        graph = TenantGraph(resources=resources)
        config = emitter.emit(
            graph.resources, preserve_rg_structure=True, location="eastus"
        )

        # Verify both RGs created
        assert "data_rg" in config["resource"]["azurerm_resource_group"]
        assert "app_rg" in config["resource"]["azurerm_resource_group"]

        # Verify private endpoint in app-rg references storage in data-rg
        pe_config = config["resource"]["azurerm_private_endpoint"]["pe_storage"]
        assert "app_rg" in pe_config["resource_group_name"]

        # Private endpoint should reference storage account ID from data-rg
        connection_config = pe_config["private_service_connection"][0]
        assert "storageacct1" in connection_config["private_connection_resource_id"]


class TestAzureManagedRGExclusion:
    """Test that Azure-managed RGs are excluded."""

    def test_network_watcher_rg_excluded(self):
        """Test that NetworkWatcherRG is not created."""
        emitter = TerraformEmitter()

        resources = [
            {
                "id": "/subscriptions/sub1/resourceGroups/NetworkWatcherRG/providers/Microsoft.Network/networkWatchers/nw1",
                "type": "Microsoft.Network/networkWatchers",
                "name": "nw1",
                "_source_rg": "NetworkWatcherRG",
            },
            {
                "id": "/subscriptions/sub1/resourceGroups/my-app-rg/providers/Microsoft.Web/sites/webapp1",
                "type": "Microsoft.Web/sites",
                "name": "webapp1",
                "_source_rg": "my-app-rg",
            },
        ]

        graph = TenantGraph(resources=resources)
        config = emitter.emit(
            graph.resources, preserve_rg_structure=True, location="eastus"
        )

        # Only my-app-rg should be created
        rg_resources = config["resource"]["azurerm_resource_group"]
        assert len(rg_resources) == 1
        assert "my_app_rg" in rg_resources
        assert "NetworkWatcherRG" not in str(rg_resources)

    def test_aks_managed_rg_excluded(self):
        """Test that AKS node resource groups (_managed) are not created."""
        emitter = TerraformEmitter()

        resources = [
            {
                "id": "/subscriptions/sub1/resourceGroups/MC_aks-rg_mycluster_eastus/providers/Microsoft.Compute/virtualMachineScaleSets/vmss1",
                "type": "Microsoft.Compute/virtualMachineScaleSets",
                "name": "vmss1",
                "_source_rg": "MC_aks-rg_mycluster_eastus",
            },
            {
                "id": "/subscriptions/sub1/resourceGroups/aks-rg/providers/Microsoft.ContainerService/managedClusters/mycluster",
                "type": "Microsoft.ContainerService/managedClusters",
                "name": "mycluster",
                "_source_rg": "aks-rg",
            },
        ]

        graph = TenantGraph(resources=resources)
        config = emitter.emit(
            graph.resources, preserve_rg_structure=True, location="eastus"
        )

        # Only aks-rg should be created (not the MC_* node RG)
        rg_resources = config["resource"]["azurerm_resource_group"]
        assert len(rg_resources) == 1
        assert "aks_rg" in rg_resources
        assert "MC_aks" not in str(rg_resources)


class TestRGWithPrefix:
    """Test resource group naming with prefix."""

    def test_rg_prefix_applied(self):
        """Test that resource_group_prefix is applied to RG names."""
        emitter = TerraformEmitter(resource_group_prefix="migrated-")

        resources = [
            {
                "id": "/subscriptions/sub1/resourceGroups/prod-rg/providers/Microsoft.Web/sites/webapp1",
                "type": "Microsoft.Web/sites",
                "name": "webapp1",
                "_source_rg": "prod-rg",
            },
        ]

        graph = TenantGraph(resources=resources)
        config = emitter.emit(
            graph.resources, preserve_rg_structure=True, location="eastus"
        )

        # RG should have prefix
        rg_config = config["resource"]["azurerm_resource_group"]["migrated_prod_rg"]
        assert rg_config["name"] == "migrated-prod-rg"


class TestRGLocationHandling:
    """Test resource group location handling."""

    def test_all_rgs_created_in_specified_location(self):
        """Test that all RGs use the specified location parameter."""
        emitter = TerraformEmitter()

        resources = [
            {
                "id": "/subscriptions/sub1/resourceGroups/eastus-rg/providers/Microsoft.Web/sites/webapp1",
                "type": "Microsoft.Web/sites",
                "name": "webapp1",
                "location": "eastus",  # Original location
                "_source_rg": "eastus-rg",
            },
            {
                "id": "/subscriptions/sub1/resourceGroups/westus-rg/providers/Microsoft.Sql/servers/sql1",
                "type": "Microsoft.Sql/servers",
                "name": "sql1",
                "location": "westus",  # Different original location
                "_source_rg": "westus-rg",
            },
        ]

        graph = TenantGraph(resources=resources)
        config = emitter.emit(
            graph.resources,
            preserve_rg_structure=True,
            location="centralus",  # Override
        )

        # Both RGs should be in centralus
        eastus_rg = config["resource"]["azurerm_resource_group"]["eastus_rg"]
        westus_rg = config["resource"]["azurerm_resource_group"]["westus_rg"]

        assert eastus_rg["location"] == "centralus"
        assert westus_rg["location"] == "centralus"


class TestBackwardCompatibility:
    """Test backward compatibility with existing behavior."""

    def test_default_behavior_unchanged(self):
        """Test that default behavior (no flag) remains unchanged."""
        emitter = TerraformEmitter()

        resources = [
            {
                "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1",
                "type": "Microsoft.Network/virtualNetworks",
                "name": "vnet1",
                "_source_rg": "rg1",
            },
            {
                "id": "/subscriptions/sub1/resourceGroups/rg2/providers/Microsoft.Storage/storageAccounts/storage1",
                "type": "Microsoft.Storage/storageAccounts",
                "name": "storage1",
                "_source_rg": "rg2",
            },
        ]

        graph = TenantGraph(resources=resources)
        # Call emit WITHOUT preserve_rg_structure flag (default=False)
        config = emitter.emit(graph.resources)

        # Should consolidate to single RG (default behavior)
        rg_resources = config["resource"]["azurerm_resource_group"]
        assert len(rg_resources) == 1


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_resources_without_source_rg_metadata(self):
        """Test handling of resources without _source_rg metadata."""
        emitter = TerraformEmitter()

        resources = [
            {
                "id": "/subscriptions/sub1/providers/Microsoft.Resources/deployments/deploy1",
                "type": "Microsoft.Resources/deployments",
                "name": "deploy1",
                # No _source_rg metadata (subscription-level resource)
            },
        ]

        graph = TenantGraph(resources=resources)
        # Should not crash, should use default/fallback RG
        config = emitter.emit(
            graph.resources, preserve_rg_structure=True, location="eastus"
        )

        # At minimum, should have created a default RG
        assert "resource" in config

    def test_empty_resource_list(self):
        """Test handling of empty resource list."""
        emitter = TerraformEmitter()

        graph = TenantGraph(resources=[])
        config = emitter.emit(
            graph.resources, preserve_rg_structure=True, location="eastus"
        )

        # Should not crash, should return valid empty config
        assert config["terraform"] is not None
        assert "resource" in config

    def test_duplicate_rg_names_deduplicated(self):
        """Test that duplicate RG names are handled correctly."""
        emitter = TerraformEmitter()

        resources = [
            {
                "id": "/subscriptions/sub1/resourceGroups/my-rg/providers/Microsoft.Web/sites/webapp1",
                "type": "Microsoft.Web/sites",
                "name": "webapp1",
                "_source_rg": "my-rg",
            },
            {
                "id": "/subscriptions/sub1/resourceGroups/my-rg/providers/Microsoft.Sql/servers/sql1",
                "type": "Microsoft.Sql/servers",
                "name": "sql1",
                "_source_rg": "my-rg",
            },
        ]

        graph = TenantGraph(resources=resources)
        config = emitter.emit(
            graph.resources, preserve_rg_structure=True, location="eastus"
        )

        # Should only create ONE resource group named my-rg
        rg_resources = config["resource"]["azurerm_resource_group"]
        assert len(rg_resources) == 1
        assert "my_rg" in rg_resources

"""Complete end-to-end test for Private DNS Zones support.

This test verifies that Microsoft.Network/privateDnsZones resources are:
1. Properly mapped to azurerm_private_dns_zone
2. Correctly emitted with all required fields
3. Compatible with Terraform validation
"""

import json
import tempfile
from pathlib import Path
from typing import Any, Dict

import pytest

from src.iac.emitters.terraform_emitter import TerraformEmitter
from src.iac.traverser import TenantGraph


@pytest.fixture
def private_dns_zone_resource() -> Dict[str, Any]:
    """Sample Private DNS Zone resource as it comes from Azure."""
    return {
        "id": "/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/networking-rg/providers/Microsoft.Network/privateDnsZones/privatelink.blob.core.windows.net",
        "name": "privatelink.blob.core.windows.net",
        "type": "Microsoft.Network/privateDnsZones",
        "location": "global",
        "resource_group": "networking-rg",
        "subscription_id": "12345678-1234-1234-1234-123456789012",
        "tags": json.dumps({"Environment": "Production", "ManagedBy": "Terraform"}),
        "properties": json.dumps(
            {
                "maxNumberOfRecordSets": 25000,
                "numberOfRecordSets": 5,
                "maxNumberOfVirtualNetworkLinks": 1000,
                "numberOfVirtualNetworkLinks": 2,
                "maxNumberOfVirtualNetworkLinksWithRegistration": 100,
                "numberOfVirtualNetworkLinksWithRegistration": 0,
                "provisioningState": "Succeeded",
            }
        ),
    }


@pytest.fixture
def multiple_private_dns_zones() -> list[Dict[str, Any]]:
    """Sample of 7 Private DNS Zones as mentioned in the issue."""
    base_zones = [
        "privatelink.blob.core.windows.net",
        "privatelink.vaultcore.azure.net",
        "privatelink.database.windows.net",
        "privatelink.azurewebsites.net",
        "privatelink.file.core.windows.net",
        "privatelink.queue.core.windows.net",
        "privatelink.table.core.windows.net",
    ]

    return [
        {
            "id": f"/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/networking-rg/providers/Microsoft.Network/privateDnsZones/{zone}",
            "name": zone,
            "type": "Microsoft.Network/privateDnsZones",
            "location": "global",
            "resource_group": "networking-rg",
            "subscription_id": "12345678-1234-1234-1234-123456789012",
            "properties": json.dumps(
                {
                    "maxNumberOfRecordSets": 25000,
                    "numberOfRecordSets": 1,
                    "provisioningState": "Succeeded",
                }
            ),
        }
        for zone in base_zones
    ]


def test_private_dns_zone_mapping_exists():
    """Verify that Microsoft.Network/privateDnsZones is mapped to azurerm_private_dns_zone."""
    emitter = TerraformEmitter()

    assert "Microsoft.Network/privateDnsZones" in emitter.AZURE_TO_TERRAFORM_MAPPING
    assert (
        emitter.AZURE_TO_TERRAFORM_MAPPING["Microsoft.Network/privateDnsZones"]
        == "azurerm_private_dns_zone"
    )


def test_single_private_dns_zone_emission(private_dns_zone_resource: Dict[str, Any]):
    """Test that a single Private DNS Zone is correctly emitted."""
    emitter = TerraformEmitter()
    graph = TenantGraph()
    graph.resources = [private_dns_zone_resource]

    with tempfile.TemporaryDirectory() as temp_dir:
        out_dir = Path(temp_dir)
        written_files = emitter.emit(graph, out_dir)

        assert len(written_files) == 1

        with open(written_files[0]) as f:
            terraform_config = json.load(f)

        # Verify resource exists
        assert "azurerm_private_dns_zone" in terraform_config["resource"]

        # Verify the specific zone
        zones = terraform_config["resource"]["azurerm_private_dns_zone"]
        assert "privatelink_blob_core_windows_net" in zones

        zone_config = zones["privatelink_blob_core_windows_net"]

        # Verify required fields
        assert zone_config["name"] == "privatelink.blob.core.windows.net"
        assert zone_config["resource_group_name"] == "networking-rg"

        # Verify no location field (Private DNS Zones are global)
        assert "location" not in zone_config

        # Verify tags are preserved
        assert "tags" in zone_config
        assert zone_config["tags"]["Environment"] == "Production"
        assert zone_config["tags"]["ManagedBy"] == "Terraform"


def test_multiple_private_dns_zones_emission(
    multiple_private_dns_zones: list[Dict[str, Any]],
):
    """Test that multiple Private DNS Zones (7 as mentioned in issue) are correctly emitted."""
    emitter = TerraformEmitter()
    graph = TenantGraph()
    graph.resources = multiple_private_dns_zones

    with tempfile.TemporaryDirectory() as temp_dir:
        out_dir = Path(temp_dir)
        written_files = emitter.emit(graph, out_dir)

        with open(written_files[0]) as f:
            terraform_config = json.load(f)

        # Verify all 7 zones are present
        assert "azurerm_private_dns_zone" in terraform_config["resource"]
        zones = terraform_config["resource"]["azurerm_private_dns_zone"]

        assert len(zones) == 7

        # Verify specific zones
        expected_zones = [
            "privatelink_blob_core_windows_net",
            "privatelink_vaultcore_azure_net",
            "privatelink_database_windows_net",
            "privatelink_azurewebsites_net",
            "privatelink_file_core_windows_net",
            "privatelink_queue_core_windows_net",
            "privatelink_table_core_windows_net",
        ]

        for zone_name in expected_zones:
            assert zone_name in zones
            zone_config = zones[zone_name]
            assert "name" in zone_config
            assert "resource_group_name" in zone_config
            assert "location" not in zone_config  # Should not have location


def test_private_dns_zone_with_vnet_link(private_dns_zone_resource: Dict[str, Any]):
    """Test Private DNS Zone with Virtual Network Link."""
    vnet = {
        "id": "/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/networking-rg/providers/Microsoft.Network/virtualNetworks/main-vnet",
        "name": "main-vnet",
        "type": "Microsoft.Network/virtualNetworks",
        "location": "eastus",
        "resource_group": "networking-rg",
        "properties": json.dumps(
            {"addressSpace": {"addressPrefixes": ["10.0.0.0/16"]}}
        ),
    }

    vnet_link = {
        "id": "/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/networking-rg/providers/Microsoft.Network/privateDnsZones/privatelink.blob.core.windows.net/virtualNetworkLinks/main-vnet-link",
        "name": "privatelink.blob.core.windows.net/main-vnet-link",
        "type": "Microsoft.Network/privateDnsZones/virtualNetworkLinks",
        "location": "global",
        "resource_group": "networking-rg",
        "properties": json.dumps(
            {
                "registrationEnabled": False,
                "virtualNetwork": {
                    "id": "/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/networking-rg/providers/Microsoft.Network/virtualNetworks/main-vnet"
                },
                "provisioningState": "Succeeded",
            }
        ),
    }

    emitter = TerraformEmitter()
    graph = TenantGraph()
    graph.resources = [vnet, private_dns_zone_resource, vnet_link]

    with tempfile.TemporaryDirectory() as temp_dir:
        out_dir = Path(temp_dir)
        written_files = emitter.emit(graph, out_dir)

        with open(written_files[0]) as f:
            terraform_config = json.load(f)

        # Verify both Private DNS Zone and VNet Link exist
        assert "azurerm_private_dns_zone" in terraform_config["resource"]
        assert (
            "azurerm_private_dns_zone_virtual_network_link"
            in terraform_config["resource"]
        )

        # Verify VNet Link references
        links = terraform_config["resource"][
            "azurerm_private_dns_zone_virtual_network_link"
        ]
        assert len(links) >= 1

        link_config = next(iter(links.values()))
        assert "private_dns_zone_name" in link_config
        assert "virtual_network_id" in link_config
        assert (
            "${azurerm_private_dns_zone.privatelink_blob_core_windows_net.name}"
            in link_config["private_dns_zone_name"]
        )
        assert (
            "${azurerm_virtual_network.main_vnet.id}"
            in link_config["virtual_network_id"]
        )


def test_private_dns_zone_terraform_validity(private_dns_zone_resource: Dict[str, Any]):
    """Test that generated Terraform is structurally valid."""
    emitter = TerraformEmitter()
    graph = TenantGraph()
    graph.resources = [private_dns_zone_resource]

    with tempfile.TemporaryDirectory() as temp_dir:
        out_dir = Path(temp_dir)
        written_files = emitter.emit(graph, out_dir)

        with open(written_files[0]) as f:
            terraform_config = json.load(f)

        # Verify required Terraform structure
        assert "terraform" in terraform_config
        assert "required_providers" in terraform_config["terraform"]
        assert "azurerm" in terraform_config["terraform"]["required_providers"]

        assert "provider" in terraform_config
        assert "resource" in terraform_config

        # Verify the template is valid according to emitter's validator
        assert emitter.validate_template(terraform_config)


def test_private_dns_zone_resource_group_prefix(
    private_dns_zone_resource: Dict[str, Any],
):
    """Test that resource group prefix is properly applied to Private DNS Zones."""
    emitter = TerraformEmitter(resource_group_prefix="TEST_")
    graph = TenantGraph()
    graph.resources = [private_dns_zone_resource]

    with tempfile.TemporaryDirectory() as temp_dir:
        out_dir = Path(temp_dir)
        written_files = emitter.emit(graph, out_dir)

        with open(written_files[0]) as f:
            terraform_config = json.load(f)

        # Verify resource group prefix is applied
        zone_config = terraform_config["resource"]["azurerm_private_dns_zone"][
            "privatelink_blob_core_windows_net"
        ]
        assert zone_config["resource_group_name"] == "TEST_networking-rg"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

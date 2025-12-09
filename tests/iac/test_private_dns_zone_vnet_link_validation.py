"""Test for Private DNS Zone Virtual Network Link validation.

This test verifies that VNet Links that reference missing Private DNS Zones
are properly detected and skipped during IaC generation.
"""

import json
import tempfile
from pathlib import Path
from typing import Any, Dict

import pytest

from src.iac.emitters.terraform_emitter import TerraformEmitter
from src.iac.traverser import TenantGraph


@pytest.fixture
def vnet_resource() -> Dict[str, Any]:
    """Sample VNet resource."""
    return {
        "id": "/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/networking-rg/providers/Microsoft.Network/virtualNetworks/main-vnet",
        "name": "main-vnet",
        "type": "Microsoft.Network/virtualNetworks",
        "location": "eastus",
        "resource_group": "networking-rg",
        "properties": json.dumps(
            {"addressSpace": {"addressPrefixes": ["10.0.0.0/16"]}}
        ),
    }


@pytest.fixture
def private_dns_zone() -> Dict[str, Any]:
    """Sample Private DNS Zone that exists."""
    return {
        "id": "/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/networking-rg/providers/Microsoft.Network/privateDnsZones/privatelink.blob.core.windows.net",
        "name": "privatelink.blob.core.windows.net",
        "type": "Microsoft.Network/privateDnsZones",
        "location": "global",
        "resource_group": "networking-rg",
        "properties": json.dumps({"provisioningState": "Succeeded"}),
    }


@pytest.fixture
def vnet_link_valid(private_dns_zone: Dict[str, Any]) -> Dict[str, Any]:
    """VNet Link that references an existing DNS Zone."""
    return {
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


@pytest.fixture
def vnet_link_missing_dns_zone() -> Dict[str, Any]:
    """VNet Link that references a MISSING DNS Zone (privatelink.table.core.windows.net)."""
    return {
        "id": "/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/networking-rg/providers/Microsoft.Network/privateDnsZones/privatelink.table.core.windows.net/virtualNetworkLinks/main-vnet-link",
        "name": "privatelink.table.core.windows.net/main-vnet-link",
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


def test_vnet_link_with_existing_dns_zone(
    vnet_resource: Dict[str, Any],
    private_dns_zone: Dict[str, Any],
    vnet_link_valid: Dict[str, Any],
):
    """Test that VNet Links are emitted when their parent DNS Zone exists."""
    emitter = TerraformEmitter()
    graph = TenantGraph()
    graph.resources = [vnet_resource, private_dns_zone, vnet_link_valid]

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

        # Verify the DNS Zone was emitted
        dns_zones = terraform_config["resource"]["azurerm_private_dns_zone"]
        assert "privatelink_blob_core_windows_net" in dns_zones

        # Verify the VNet Link was emitted
        vnet_links = terraform_config["resource"][
            "azurerm_private_dns_zone_virtual_network_link"
        ]
        assert len(vnet_links) == 1


def test_vnet_link_with_missing_dns_zone_is_skipped(
    vnet_resource: Dict[str, Any],
    private_dns_zone: Dict[str, Any],
    vnet_link_missing_dns_zone: Dict[str, Any],
):
    """Test that VNet Links are SKIPPED when their parent DNS Zone doesn't exist.

    This test verifies the fix for the bug where VNet Links would reference
    non-existent DNS Zones, causing Terraform deployment failures.
    """
    emitter = TerraformEmitter()
    graph = TenantGraph()
    # Note: We have privatelink.blob.core.windows.net DNS Zone
    # but the VNet Link references privatelink.table.core.windows.net (missing)
    graph.resources = [vnet_resource, private_dns_zone, vnet_link_missing_dns_zone]

    with tempfile.TemporaryDirectory() as temp_dir:
        out_dir = Path(temp_dir)
        written_files = emitter.emit(graph, out_dir)

        with open(written_files[0]) as f:
            terraform_config = json.load(f)

        # Verify the existing DNS Zone was emitted
        assert "azurerm_private_dns_zone" in terraform_config["resource"]
        dns_zones = terraform_config["resource"]["azurerm_private_dns_zone"]
        assert "privatelink_blob_core_windows_net" in dns_zones
        assert "privatelink_table_core_windows_net" not in dns_zones

        # Verify the VNet Link was SKIPPED (not emitted)
        if (
            "azurerm_private_dns_zone_virtual_network_link"
            in terraform_config["resource"]
        ):
            vnet_links = terraform_config["resource"][
                "azurerm_private_dns_zone_virtual_network_link"
            ]
            # Should be empty or not contain the invalid link
            assert len(vnet_links) == 0


def test_mixed_vnet_links_valid_and_invalid(
    vnet_resource: Dict[str, Any],
    private_dns_zone: Dict[str, Any],
    vnet_link_valid: Dict[str, Any],
    vnet_link_missing_dns_zone: Dict[str, Any],
):
    """Test that valid VNet Links are emitted while invalid ones are skipped."""
    emitter = TerraformEmitter()
    graph = TenantGraph()
    # Mix of valid and invalid VNet Links
    graph.resources = [
        vnet_resource,
        private_dns_zone,
        vnet_link_valid,  # References existing privatelink.blob.core.windows.net
        vnet_link_missing_dns_zone,  # References missing privatelink.table.core.windows.net
    ]

    with tempfile.TemporaryDirectory() as temp_dir:
        out_dir = Path(temp_dir)
        written_files = emitter.emit(graph, out_dir)

        with open(written_files[0]) as f:
            terraform_config = json.load(f)

        # Verify the existing DNS Zone was emitted
        assert "azurerm_private_dns_zone" in terraform_config["resource"]
        dns_zones = terraform_config["resource"]["azurerm_private_dns_zone"]
        assert "privatelink_blob_core_windows_net" in dns_zones

        # Verify only the VALID VNet Link was emitted (1 link, not 2)
        assert (
            "azurerm_private_dns_zone_virtual_network_link"
            in terraform_config["resource"]
        )
        vnet_links = terraform_config["resource"][
            "azurerm_private_dns_zone_virtual_network_link"
        ]
        assert len(vnet_links) == 1

        # Verify the link references the correct DNS Zone
        link_config = next(iter(vnet_links.values()))
        assert (
            "${azurerm_private_dns_zone.privatelink_blob_core_windows_net.name}"
            in link_config["private_dns_zone_name"]
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

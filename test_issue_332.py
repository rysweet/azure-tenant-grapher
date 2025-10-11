#!/usr/bin/env python3
"""Quick test to verify Issue #332 fix works."""

import json
import tempfile
from pathlib import Path

from src.iac.emitters.terraform_emitter import TerraformEmitter
from src.iac.traverser import TenantGraph


def create_vnet(name: str, subnet_names: list) -> dict:
    """Create mock VNet resource."""
    subnets = [
        {
            "name": subnet_name,
            "properties": {"addressPrefix": f"10.0.{i}.0/24"}
        }
        for i, subnet_name in enumerate(subnet_names)
    ]

    return {
        "id": f"/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/{name}",
        "name": name,
        "type": "Microsoft.Network/virtualNetworks",
        "location": "eastus",
        "resourceGroup": "test-rg",
        "address_space": ["10.0.0.0/16"],
        "properties": json.dumps({
            "addressSpace": {"addressPrefixes": ["10.0.0.0/16"]},
            "subnets": subnets
        })
    }


def test_vnet_scoped_naming():
    """Test VNet-scoped subnet naming works."""
    emitter = TerraformEmitter()

    # Create two VNets with identically-named subnets
    vnet1 = create_vnet("infra-vnet", ["AzureBastionSubnet"])
    vnet2 = create_vnet("attack-vnet", ["AzureBastionSubnet"])

    graph = TenantGraph()
    graph.resources = [vnet1, vnet2]

    # Generate Terraform
    with tempfile.TemporaryDirectory() as temp_dir:
        out_dir = Path(temp_dir)
        emitter.emit(graph, out_dir)

        with open(out_dir / "main.tf.json") as f:
            config = json.load(f)

    # Verify two distinct subnet resources exist
    subnets = config["resource"]["azurerm_subnet"]

    print(f"Generated subnets: {list(subnets.keys())}")

    assert "infra_vnet_AzureBastionSubnet" in subnets, \
        "Should have VNet-scoped subnet: infra_vnet_AzureBastionSubnet"
    assert "attack_vnet_AzureBastionSubnet" in subnets, \
        "Should have VNet-scoped subnet: attack_vnet_AzureBastionSubnet"
    assert len(subnets) == 2, \
        f"Expected 2 distinct subnets, got {len(subnets)}"

    # Verify Azure names are preserved
    assert subnets["infra_vnet_AzureBastionSubnet"]["name"] == "AzureBastionSubnet"
    assert subnets["attack_vnet_AzureBastionSubnet"]["name"] == "AzureBastionSubnet"

    # Verify VNet references are correct
    assert "infra_vnet" in subnets["infra_vnet_AzureBastionSubnet"]["virtual_network_name"]
    assert "attack_vnet" in subnets["attack_vnet_AzureBastionSubnet"]["virtual_network_name"]

    print("✓ All tests passed!")
    return True


if __name__ == "__main__":
    test_vnet_scoped_naming()

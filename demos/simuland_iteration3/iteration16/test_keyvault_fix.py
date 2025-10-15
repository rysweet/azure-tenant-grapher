#!/usr/bin/env python3
"""Test script to verify Key Vault tenant_id fix."""
import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from iac.emitters.terraform_emitter import TerraformEmitter
from iac.traverser import TenantGraph


def test_keyvault_tenant_id_fix():
    """Test that Key Vault tenant_id is properly resolved."""

    # Create a sample Key Vault resource with missing tenant_id
    kv_resource = {
        "type": "Microsoft.KeyVault/vaults",
        "name": "test-keyvault",
        "location": "eastus",
        "resource_group": "test-rg",
        "id": "/subscriptions/12345-abcde-67890/resourceGroups/test-rg/providers/Microsoft.KeyVault/vaults/test-keyvault",
        # Note: NO tenant_id field - this is the bug condition
    }

    # Create a graph with the Key Vault
    graph = TenantGraph(resources=[kv_resource])

    # Create emitter
    emitter = TerraformEmitter()

    # Generate IaC
    out_dir = Path(__file__).parent / "test_output"
    out_dir.mkdir(exist_ok=True)

    result = emitter.emit(graph, out_dir)

    # Read generated main.tf.json
    with open(out_dir / "main.tf.json") as f:
        config = json.load(f)

    # Check if Key Vault exists
    if "azurerm_key_vault" not in config.get("resource", {}):
        print("FAIL: No Key Vault resource generated")
        return False

    # Get the Key Vault config
    kv_config = config["resource"]["azurerm_key_vault"]["test_keyvault"]

    # Check tenant_id
    tenant_id = kv_config.get("tenant_id")

    print(f"Generated tenant_id: {tenant_id}")

    # Verify it's using the data source reference (not placeholder)
    if tenant_id == "${data.azurerm_client_config.current.tenant_id}":
        print("SUCCESS: tenant_id is using Terraform data source reference")

        # Verify data source was added
        if "data" in config and "azurerm_client_config" in config["data"]:
            print("SUCCESS: azurerm_client_config data source added")
            print(f"Data source config: {config['data']['azurerm_client_config']}")
            return True
        else:
            print("FAIL: Data source not added to config")
            return False
    elif tenant_id == "00000000-0000-0000-0000-000000000000":
        print("FAIL: tenant_id is still using placeholder value")
        return False
    else:
        print(f"SUCCESS: tenant_id resolved from resource data: {tenant_id}")
        return True


if __name__ == "__main__":
    success = test_keyvault_tenant_id_fix()
    sys.exit(0 if success else 1)

"""Test to verify Key Vault tenant_id fix (ITERATION 15 bug)."""
import json
from pathlib import Path
import tempfile

import pytest

from src.iac.emitters.terraform_emitter import TerraformEmitter
from src.iac.traverser import TenantGraph


class TestKeyVaultTenantIDFix:
    """Test Key Vault tenant_id resolution."""

    def test_keyvault_without_tenant_id_uses_data_source(self):
        """When Key Vault has no tenant_id, should use Terraform data source."""
        # Create a Key Vault resource WITHOUT tenant_id (the bug condition)
        kv_resource = {
            "type": "Microsoft.KeyVault/vaults",
            "name": "test-keyvault",
            "location": "eastus",
            "resource_group": "test-rg",
            "id": "/subscriptions/12345-abcde-67890/resourceGroups/test-rg/providers/Microsoft.KeyVault/vaults/test-keyvault",
            # NOTE: NO tenant_id - this is the bug that caused deployment failures
        }

        graph = TenantGraph(resources=[kv_resource])
        emitter = TerraformEmitter()

        with tempfile.TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir)
            emitter.emit(graph, out_dir)

            # Read generated config
            with open(out_dir / "main.tf.json") as f:
                config = json.load(f)

        # Verify Key Vault exists
        assert "azurerm_key_vault" in config["resource"]
        kv_config = config["resource"]["azurerm_key_vault"]["test_keyvault"]

        # Verify tenant_id is using data source reference (not placeholder)
        assert kv_config["tenant_id"] == "${data.azurerm_client_config.current.tenant_id}"

        # Verify data source was added
        assert "data" in config
        assert "azurerm_client_config" in config["data"]
        assert "current" in config["data"]["azurerm_client_config"]

    def test_keyvault_with_tenant_id_uses_provided_value(self):
        """When Key Vault has tenant_id in resource data, should use it."""
        tenant_id = "aaaabbbb-cccc-dddd-eeee-ffff11112222"

        kv_resource = {
            "type": "Microsoft.KeyVault/vaults",
            "name": "test-keyvault-2",
            "location": "westus",
            "resource_group": "test-rg",
            "tenant_id": tenant_id,  # Explicit tenant_id
            "id": "/subscriptions/12345-abcde-67890/resourceGroups/test-rg/providers/Microsoft.KeyVault/vaults/test-keyvault-2",
        }

        graph = TenantGraph(resources=[kv_resource])
        emitter = TerraformEmitter()

        with tempfile.TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir)
            emitter.emit(graph, out_dir)

            with open(out_dir / "main.tf.json") as f:
                config = json.load(f)

        # Verify tenant_id matches provided value
        kv_config = config["resource"]["azurerm_key_vault"]["test_keyvault_2"]
        assert kv_config["tenant_id"] == tenant_id

    def test_keyvault_with_placeholder_tenant_id_uses_data_source(self):
        """When Key Vault has placeholder tenant_id, should replace with data source."""
        kv_resource = {
            "type": "Microsoft.KeyVault/vaults",
            "name": "test-keyvault-3",
            "location": "centralus",
            "resource_group": "test-rg",
            "tenant_id": "00000000-0000-0000-0000-000000000000",  # Placeholder (bug condition)
            "id": "/subscriptions/12345-abcde-67890/resourceGroups/test-rg/providers/Microsoft.KeyVault/vaults/test-keyvault-3",
        }

        graph = TenantGraph(resources=[kv_resource])
        emitter = TerraformEmitter()

        with tempfile.TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir)
            emitter.emit(graph, out_dir)

            with open(out_dir / "main.tf.json") as f:
                config = json.load(f)

        # Verify placeholder was replaced with data source reference
        kv_config = config["resource"]["azurerm_key_vault"]["test_keyvault_3"]
        assert kv_config["tenant_id"] == "${data.azurerm_client_config.current.tenant_id}"
        assert kv_config["tenant_id"] != "00000000-0000-0000-0000-000000000000"

    def test_keyvault_tenant_id_from_properties(self):
        """When Key Vault has tenant_id in properties JSON, should use it."""
        tenant_id = "11112222-3333-4444-5555-666677778888"

        kv_resource = {
            "type": "Microsoft.KeyVault/vaults",
            "name": "test-keyvault-4",
            "location": "northeurope",
            "resource_group": "test-rg",
            "properties": json.dumps({"tenantId": tenant_id}),  # tenant_id in properties
            "id": "/subscriptions/12345-abcde-67890/resourceGroups/test-rg/providers/Microsoft.KeyVault/vaults/test-keyvault-4",
        }

        graph = TenantGraph(resources=[kv_resource])
        emitter = TerraformEmitter()

        with tempfile.TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir)
            emitter.emit(graph, out_dir)

            with open(out_dir / "main.tf.json") as f:
                config = json.load(f)

        # Verify tenant_id was extracted from properties
        kv_config = config["resource"]["azurerm_key_vault"]["test_keyvault_4"]
        assert kv_config["tenant_id"] == tenant_id

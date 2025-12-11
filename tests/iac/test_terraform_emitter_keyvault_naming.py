"""Tests for Key Vault naming and truncation in Terraform emitter.

Tests for fix to Issue related to Key Vault name length > 24 characters.
Key Vaults have a 24-character name limit, and the unique suffix (7 chars)
must be accounted for when generating names.
"""

import json
from pathlib import Path

from src.iac.emitters.terraform_emitter import TerraformEmitter
from src.iac.traverser import TenantGraph


class TestKeyVaultNaming:
    """Test Key Vault name generation and truncation."""

    def test_keyvault_short_name_with_suffix(self, tmp_path: Path):
        """Test that short Key Vault names are properly suffixed without truncation."""
        graph = TenantGraph(
            resources=[
                {
                    "type": "Microsoft.KeyVault/vaults",
                    "name": "myvault",
                    "location": "eastus",
                    "resourceGroup": "test-rg",
                    "id": "/subscriptions/test/resourceGroups/test-rg/providers/Microsoft.KeyVault/vaults/myvault",
                }
            ]
        )

        emitter = TerraformEmitter()
        output_files = emitter.emit(graph, tmp_path)

        # Read generated config
        with open(output_files[0]) as f:
            config = json.load(f)

        # Find the key vault resource (structure is dict with resource name as key)
        assert "azurerm_key_vault" in config["resource"], (
            "azurerm_key_vault not found in config"
        )
        vault_resources = config["resource"]["azurerm_key_vault"]
        # Get first vault (there should be at least one)
        vault_name = (
            next(iter(vault_resources.values()))["name"] if vault_resources else None
        )
        assert vault_name, "No key vault resource found"

        # Name should start with original name and have suffix
        assert vault_name.startswith("myvault")
        # Should have hyphen and 6-char hash
        assert len(vault_name.split("-")) == 2
        # Must be <= 24 chars
        assert len(vault_name) <= 24, (
            f"Key Vault name '{vault_name}' exceeds 24 chars: {len(vault_name)}"
        )

    def test_keyvault_long_name_is_truncated(self, tmp_path: Path):
        """Test that long Key Vault names are truncated before suffix is added.

        This tests the fix for the case where base name + suffix > 24 chars.
        Example: "simKV160224hpcp4rein6" (21 chars) + "-f5648f" (7 chars) = 28 chars > 24 limit
        """
        # Use the example name from the bug report
        long_name = "simKV160224hpcp4rein6"  # 21 chars
        assert len(long_name) == 21

        graph = TenantGraph(
            resources=[
                {
                    "type": "Microsoft.KeyVault/vaults",
                    "name": long_name,
                    "location": "eastus",
                    "resourceGroup": "test-rg",
                    "id": f"/subscriptions/test/resourceGroups/test-rg/providers/Microsoft.KeyVault/vaults/{long_name}",
                }
            ]
        )

        emitter = TerraformEmitter()
        output_files = emitter.emit(graph, tmp_path)

        # Read generated config
        with open(output_files[0]) as f:
            config = json.load(f)

        # Find the key vault resource
        vault_resources = config["resource"]["azurerm_key_vault"]
        vault_name = (
            next(iter(vault_resources.values()))["name"] if vault_resources else None
        )
        assert vault_name, "No key vault resource found"

        # Must be <= 24 chars
        assert len(vault_name) <= 24, (
            f"Key Vault name '{vault_name}' exceeds 24 chars: {len(vault_name)}"
        )
        # Name should have been truncated and then suffixed
        assert "-" in vault_name, f"Key Vault name '{vault_name}' should have suffix"
        # The suffix should be 6 hex chars
        parts = vault_name.split("-")
        assert len(parts[1]) == 6, f"Suffix should be 6 chars, got: {parts[1]}"

    def test_keyvault_name_at_max_length_without_truncation(self, tmp_path: Path):
        """Test that names exactly at or under 17 chars don't need truncation."""
        # 17 chars is the max without truncation (leaves room for 7-char suffix)
        name_17 = "a" * 17
        assert len(name_17) == 17

        graph = TenantGraph(
            resources=[
                {
                    "type": "Microsoft.KeyVault/vaults",
                    "name": name_17,
                    "location": "eastus",
                    "resourceGroup": "test-rg",
                    "id": f"/subscriptions/test/resourceGroups/test-rg/providers/Microsoft.KeyVault/vaults/{name_17}",
                }
            ]
        )

        emitter = TerraformEmitter()
        output_files = emitter.emit(graph, tmp_path)

        # Read generated config
        with open(output_files[0]) as f:
            config = json.load(f)

        # Find the key vault resource
        vault_resources = config["resource"]["azurerm_key_vault"]
        vault_name = (
            next(iter(vault_resources.values()))["name"] if vault_resources else None
        )
        assert vault_name, "No key vault resource found"

        # Must be <= 24 chars
        assert len(vault_name) <= 24, (
            f"Key Vault name '{vault_name}' exceeds 24 chars: {len(vault_name)}"
        )
        # Name should start with original name
        assert vault_name.startswith(name_17)

    def test_keyvault_name_exceeds_17_chars_is_truncated(self, tmp_path: Path):
        """Test that names over 17 chars are truncated to 17 before suffix."""
        # 18 chars is over the limit (17 chars + 7-char suffix = 24)
        name_18 = "a" * 18
        assert len(name_18) == 18

        graph = TenantGraph(
            resources=[
                {
                    "type": "Microsoft.KeyVault/vaults",
                    "name": name_18,
                    "location": "eastus",
                    "resourceGroup": "test-rg",
                    "id": f"/subscriptions/test/resourceGroups/test-rg/providers/Microsoft.KeyVault/vaults/{name_18}",
                }
            ]
        )

        emitter = TerraformEmitter()
        output_files = emitter.emit(graph, tmp_path)

        # Read generated config
        with open(output_files[0]) as f:
            config = json.load(f)

        # Find the key vault resource
        vault_resources = config["resource"]["azurerm_key_vault"]
        vault_name = (
            next(iter(vault_resources.values()))["name"] if vault_resources else None
        )
        assert vault_name, "No key vault resource found"

        # Must be <= 24 chars
        assert len(vault_name) <= 24, (
            f"Key Vault name '{vault_name}' exceeds 24 chars: {len(vault_name)}"
        )
        # Should have suffix
        assert "-" in vault_name
        # Base part should be 17 chars (truncated)
        parts = vault_name.split("-")
        assert len(parts[0]) == 17, (
            f"Truncated base should be 17 chars, got: {len(parts[0])}"
        )

    def test_keyvault_other_globally_unique_not_truncated(self, tmp_path: Path):
        """Test that other globally unique resources don't get Key Vault-specific truncation."""
        # Test with a Web Site which also needs unique suffix but doesn't require truncation
        long_name = "mywebsite123456"

        graph = TenantGraph(
            resources=[
                {
                    "type": "Microsoft.Web/sites",
                    "name": long_name,
                    "location": "eastus",
                    "resourceGroup": "test-rg",
                    "id": f"/subscriptions/test/resourceGroups/test-rg/providers/Microsoft.Web/sites/{long_name}",
                    "kind": "app",
                }
            ]
        )

        emitter = TerraformEmitter()
        output_files = emitter.emit(graph, tmp_path)

        # Read generated config
        with open(output_files[0]) as f:
            config = json.load(f)

        # Find the app service resource
        if "azurerm_linux_web_app" in config["resource"]:
            web_resources = config["resource"]["azurerm_linux_web_app"]
            web_name = (
                next(iter(web_resources.values()))["name"] if web_resources else None
            )
            assert web_name, "No web app resource found"
            # Name should start with original long name (not truncated like Key Vault would)
            assert web_name.startswith(long_name)

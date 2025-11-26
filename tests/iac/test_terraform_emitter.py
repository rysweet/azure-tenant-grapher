"""Tests for Terraform emitter functionality.

Tests the TerraformEmitter class for generating Terraform templates.
"""

import json
import tempfile
from pathlib import Path

from src.iac.emitters.terraform_emitter import TerraformEmitter
from src.iac.traverser import TenantGraph


class TestTerraformEmitter:
    """Test cases for TerraformEmitter class."""

    def test_emitter_initialization(self) -> None:
        """Test that TerraformEmitter initializes correctly."""
        emitter = TerraformEmitter()
        assert emitter.config == {}

    def test_emit_creates_terraform_file(self) -> None:
        """Test that emit creates main.tf.json file."""
        emitter = TerraformEmitter()

        # Create test graph with sample resources
        graph = TenantGraph()
        graph.resources = [
            {
                "type": "Microsoft.Storage/storageAccounts",
                "name": "teststorage",
                "location": "East US",
                "resourceGroup": "test-rg",
            },
            {
                "type": "Microsoft.Compute/virtualMachines",
                "name": "testvm",
                "location": "West US",
                "resourceGroup": "vm-rg",
                "tags": {"environment": "test"},
            },
        ]

        # Create temporary output directory
        with tempfile.TemporaryDirectory() as temp_dir:
            out_dir = Path(temp_dir)

            # Generate templates
            written_files = emitter.emit(graph, out_dir)

            # Verify file was created
            assert len(written_files) == 1
            assert written_files[0].name == "main.tf.json"
            assert written_files[0].exists()

            # Verify content structure
            with open(written_files[0]) as f:
                terraform_config = json.load(f)

            # Check required top-level keys
            assert "terraform" in terraform_config
            assert "provider" in terraform_config
            assert "resource" in terraform_config

            # Check terraform block
            assert "required_providers" in terraform_config["terraform"]
            assert "azurerm" in terraform_config["terraform"]["required_providers"]

            # Check provider block
            assert "azurerm" in terraform_config["provider"]
            assert "features" in terraform_config["provider"]["azurerm"]

            # Check resources were converted
            assert "azurerm_storage_account" in terraform_config["resource"]
            assert "azurerm_linux_virtual_machine" in terraform_config["resource"]

    def test_azure_to_terraform_mapping(self) -> None:
        """Test Azure resource type to Terraform mapping."""
        emitter = TerraformEmitter()

        # Test known mappings
        assert "Microsoft.Storage/storageAccounts" in emitter.AZURE_TO_TERRAFORM_MAPPING
        assert (
            emitter.AZURE_TO_TERRAFORM_MAPPING["Microsoft.Storage/storageAccounts"]
            == "azurerm_storage_account"
        )

        assert "Microsoft.Compute/virtualMachines" in emitter.AZURE_TO_TERRAFORM_MAPPING
        assert (
            emitter.AZURE_TO_TERRAFORM_MAPPING["Microsoft.Compute/virtualMachines"]
            == "azurerm_linux_virtual_machine"
        )

    def test_get_supported_resource_types(self) -> None:
        """Test getting supported resource types."""
        emitter = TerraformEmitter()
        supported_types = emitter.get_supported_resource_types()

        assert isinstance(supported_types, list)
        assert len(supported_types) > 0
        assert "Microsoft.Storage/storageAccounts" in supported_types
        assert "Microsoft.Compute/virtualMachines" in supported_types

    def test_validate_template_basic(self) -> None:
        """Test basic template validation."""
        emitter = TerraformEmitter()

        # Valid template
        valid_template = {
            "terraform": {"required_providers": {}},
            "provider": {"azurerm": {}},
            "resource": {},
        }
        assert emitter.validate_template(valid_template) is True

        # Invalid template (missing required keys)
        invalid_template = {
            "terraform": {"required_providers": {}},
            "provider": {"azurerm": {}},
            # Missing "resource" key
        }
        assert emitter.validate_template(invalid_template) is False

    def test_sanitize_terraform_name(self) -> None:
        """Test Terraform name sanitization."""
        emitter = TerraformEmitter()

        # Test various name formats
        assert emitter._sanitize_terraform_name("test-vm") == "test_vm"
        assert emitter._sanitize_terraform_name("test.storage") == "test_storage"
        assert emitter._sanitize_terraform_name("123invalid") == "resource_123invalid"
        assert emitter._sanitize_terraform_name("") == "unnamed_resource"
        assert emitter._sanitize_terraform_name("valid_name") == "valid_name"

    def test_add_unique_suffix_container_registry(self) -> None:
        """Test that Container Registry names don't get dashes in suffix.

        Bug fix: Container Registries require alphanumeric-only names (no dashes).
        Previous behavior added "-XXXXXX" suffix, which is invalid.
        """
        emitter = TerraformEmitter()

        # Container Registry resource type
        resource_id = "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.ContainerRegistry/registries/myacr"

        # Test Container Registry: should NOT have dash in suffix
        acr_name = "myacr"
        result = emitter._add_unique_suffix(
            acr_name, resource_id, "Microsoft.ContainerRegistry/registries"
        )

        # Result should be "myacr" + 6-char hash with NO dash
        assert len(result) == len(acr_name) + 6  # name + 6 char hash
        assert result.startswith(acr_name)
        assert "-" not in result  # No dash for Container Registry
        # Verify it's all alphanumeric
        assert result.isalnum()

    def test_add_unique_suffix_keyvault(self) -> None:
        """Test that Key Vault names still get dashes in suffix."""
        emitter = TerraformEmitter()

        resource_id = "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.KeyVault/vaults/myvault"

        # Test Key Vault: should have dash in suffix
        vault_name = "myvault"
        result = emitter._add_unique_suffix(
            vault_name, resource_id, "Microsoft.KeyVault/vaults"
        )

        # Result should be "myvault-XXXXXX"
        assert len(result) == len(vault_name) + 7  # name + dash + 6 char hash
        assert result.startswith(vault_name + "-")
        assert "-" in result  # Dash is present for Key Vault

    def test_add_unique_suffix_other_types(self) -> None:
        """Test that other globally unique types get dashes in suffix."""
        emitter = TerraformEmitter()

        resource_id = "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Cache/Redis/myredis"

        # Test Redis Cache: should have dash in suffix
        cache_name = "myredis"
        result = emitter._add_unique_suffix(
            cache_name, resource_id, "Microsoft.Cache/Redis"
        )

        # Result should be "myredis-XXXXXX"
        assert len(result) == len(cache_name) + 7  # name + dash + 6 char hash
        assert result.startswith(cache_name + "-")
        assert "-" in result  # Dash is present for other types

    def test_add_unique_suffix_default_behavior(self) -> None:
        """Test that default behavior (no resource_type) adds dash."""
        emitter = TerraformEmitter()

        resource_id = "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Storage/storageAccounts/mystorage"

        # Test with no resource_type specified: should default to dash behavior
        storage_name = "mystorage"
        result = emitter._add_unique_suffix(storage_name, resource_id)

        # Result should be "mystorage-XXXXXX"
        assert len(result) == len(storage_name) + 7  # name + dash + 6 char hash
        assert result.startswith(storage_name + "-")
        assert "-" in result  # Dash is present by default


class TestTerraformEmitterIntegration:
    """Integration tests for TerraformEmitter."""

    def test_emit_template_legacy_method(self) -> None:
        """Test the legacy emit_template method."""
        emitter = TerraformEmitter()

        graph = TenantGraph()
        graph.resources = [
            {
                "type": "Microsoft.Storage/storageAccounts",
                "name": "storage",
                "location": "East US",
            }
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            # Test legacy method (async)
            import asyncio

            result = asyncio.run(emitter.emit_template(graph, temp_dir))

            assert "files_written" in result
            assert "resource_count" in result
            assert result["resource_count"] == 1
            assert len(result["files_written"]) == 1

    def test_container_registry_naming_integration(self) -> None:
        """Integration test: Container Registry names should not have dashes.

        Bug fix for ~30 errors: Container Registries require alphanumeric-only names.
        This test ensures the Terraform emitter generates valid Container Registry names
        without dashes in the unique suffix.
        """
        emitter = TerraformEmitter()

        # Create a test graph with a Container Registry resource
        graph = TenantGraph()
        graph.resources = [
            {
                "type": "Microsoft.ContainerRegistry/registries",
                "name": "noahtestacr",
                "location": "East US",
                "resourceGroup": "test-rg",
                "id": "/subscriptions/sub1/resourceGroups/test-rg/providers/Microsoft.ContainerRegistry/registries/noahtestacr",
                "properties": {
                    "adminUserEnabled": True,
                    "sku": {"name": "Basic"},
                },
            }
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            out_dir = Path(temp_dir)
            written_files = emitter.emit(graph, out_dir)

            assert len(written_files) == 1
            assert written_files[0].name == "main.tf.json"
            assert written_files[0].exists()

            # Verify the generated Terraform configuration
            with open(written_files[0]) as f:
                terraform_config = json.load(f)

            # Check that the Container Registry resource was created
            assert "azurerm_container_registry" in terraform_config["resource"]

            # Get the generated resource name
            acr_resources = terraform_config["resource"]["azurerm_container_registry"]
            assert len(acr_resources) > 0

            # Get the first (and should be only) Container Registry resource
            acr_resource_name = next(iter(acr_resources.keys()))
            acr_config = acr_resources[acr_resource_name]

            # Verify the name in the generated Terraform code
            generated_name = acr_config["name"]

            # Key assertion: the generated name should NOT contain dashes
            # (except for the original name, but the suffix should be alphanumeric only)
            # The name should be alphanumeric only
            assert (
                generated_name.replace("noahtestacr", "").replace("_", "").isalnum()
            ), (
                f"Container Registry name '{generated_name}' contains invalid characters "
                f"(should be alphanumeric only). Container Registries do not allow dashes."
            )

    def test_vnet_with_null_resource_group_skipped(self) -> None:
        """Test that VNets with null resource_group_name are skipped.

        Bug fix: VNets like hub_vnet, spoke_1_vnet were getting
        resource_group_name: null in Terraform config.
        This test ensures VNets without a valid resource group are skipped entirely.
        """
        emitter = TerraformEmitter()

        # Create a test graph with a VNet that has no resource group
        graph = TenantGraph()
        graph.resources = [
            {
                "type": "Microsoft.Network/virtualNetworks",
                "name": "hub_vnet",
                "location": "East US",
                "resourceGroup": None,  # NULL RESOURCE GROUP - should be skipped
                "resource_group": None,
                "id": "/subscriptions/sub1/resourceGroups/unknown/providers/Microsoft.Network/virtualNetworks/hub_vnet",
                "original_id": "/subscriptions/sub1/resourceGroups/unknown/providers/Microsoft.Network/virtualNetworks/hub_vnet",
                "addressSpace": ["10.0.0.0/16"],
                "properties": {
                    "addressSpace": {"addressPrefixes": ["10.0.0.0/16"]},
                    "subnets": [],
                },
            }
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            out_dir = Path(temp_dir)
            written_files = emitter.emit(graph, out_dir)

            assert len(written_files) == 1
            assert written_files[0].name == "main.tf.json"
            assert written_files[0].exists()

            # Verify the generated Terraform configuration
            with open(written_files[0]) as f:
                terraform_config = json.load(f)

            # Key assertion: VNets with null resource_group_name should NOT be created
            # The resource section should either not have azurerm_virtual_network,
            # or if it does, it should not contain the hub_vnet
            if "azurerm_virtual_network" in terraform_config.get("resource", {}):
                vnet_resources = terraform_config["resource"]["azurerm_virtual_network"]
                # Check that no VNet has null resource_group_name
                for vnet_name, vnet_config in vnet_resources.items():
                    assert vnet_config.get("resource_group_name") is not None, (
                        f"VNet '{vnet_name}' has null resource_group_name in Terraform config. "
                        f"VNets without valid resource groups should be skipped."
                    )

    def test_vnet_with_valid_resource_group_included(self) -> None:
        """Test that VNets with valid resource_group_name are included.

        Ensures that the fix to skip null resource groups doesn't accidentally
        filter out VNets with valid resource groups.
        """
        emitter = TerraformEmitter()

        # Create a test graph with a VNet that has a valid resource group
        graph = TenantGraph()
        graph.resources = [
            {
                "type": "Microsoft.Network/virtualNetworks",
                "name": "test_vnet",
                "location": "East US",
                "resourceGroup": "test-rg",
                "resource_group": "test-rg",
                "id": "/subscriptions/sub1/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/test_vnet",
                "original_id": "/subscriptions/sub1/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/test_vnet",
                "addressSpace": ["10.0.0.0/16"],
                "properties": {
                    "addressSpace": {"addressPrefixes": ["10.0.0.0/16"]},
                    "subnets": [],
                },
            }
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            out_dir = Path(temp_dir)
            written_files = emitter.emit(graph, out_dir)

            assert len(written_files) == 1
            assert written_files[0].name == "main.tf.json"
            assert written_files[0].exists()

            # Verify the generated Terraform configuration
            with open(written_files[0]) as f:
                terraform_config = json.load(f)

            # Key assertion: VNets with valid resource_group_name SHOULD be created
            assert "azurerm_virtual_network" in terraform_config.get("resource", {}), (
                "VNet with valid resource_group_name should be included in Terraform config"
            )

            vnet_resources = terraform_config["resource"]["azurerm_virtual_network"]
            assert len(vnet_resources) > 0, "At least one VNet should be created"

            # Check that the VNet has valid resource_group_name
            for vnet_name, vnet_config in vnet_resources.items():
                assert vnet_config.get("resource_group_name") == "test-rg", (
                    f"VNet '{vnet_name}' should have resource_group_name='test-rg'"
                )
                assert vnet_config.get("address_space") == ["10.0.0.0/16"], (
                    f"VNet '{vnet_name}' should have valid address space"
                )

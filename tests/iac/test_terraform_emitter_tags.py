"""Tests for Terraform emitter tags parsing functionality.

This test module covers the tags formatting bug where tags stored as JSON strings
in Neo4j cause Terraform validation failures. Terraform expects native dict/map
format, not JSON string representations.

Bug: Issue #295 - IaC Tags Formatting Bug
"""

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from src.iac.emitters.terraform_emitter import TerraformEmitter
from src.iac.traverser import TenantGraph


class TestTerraformTagsParsing:
    """Unit tests for tags parsing in TerraformEmitter."""

    def test_tags_as_json_string_should_parse_to_dict(self) -> None:
        """Test that tags stored as JSON string are parsed to dict.

        This is the most common bug scenario where Neo4j stores tags
        as JSON strings but Terraform expects native dict.
        """
        emitter = TerraformEmitter()
        graph = TenantGraph()
        graph.resources = [
            {
                "type": "Microsoft.Storage/storageAccounts",
                "name": "teststorage",
                "location": "eastus",
                "resourceGroup": "test-rg",
                "tags": '{"Environment": "prod", "Team": "security"}',  # JSON string
            }
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            out_dir = Path(temp_dir)
            written_files = emitter.emit(graph, out_dir)

            # Read generated Terraform config
            with open(written_files[0]) as f:
                terraform_config = json.load(f)

            # Extract tags from storage account
            storage_resource = terraform_config["resource"]["azurerm_storage_account"][
                "teststorage"
            ]

            # Tags should be parsed to dict, not remain as string
            assert "tags" in storage_resource
            assert isinstance(storage_resource["tags"], dict), (
                "Tags should be dict, not string"
            )
            assert storage_resource["tags"]["Environment"] == "prod"
            assert storage_resource["tags"]["Team"] == "security"

    def test_tags_already_as_dict_should_pass_through(self) -> None:
        """Test that tags already as dict are passed through unchanged."""
        emitter = TerraformEmitter()
        graph = TenantGraph()
        graph.resources = [
            {
                "type": "Microsoft.Storage/storageAccounts",
                "name": "teststorage",
                "location": "eastus",
                "resourceGroup": "test-rg",
                "tags": {"Environment": "dev", "CostCenter": "12345"},  # Already dict
            }
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            out_dir = Path(temp_dir)
            written_files = emitter.emit(graph, out_dir)

            with open(written_files[0]) as f:
                terraform_config = json.load(f)

            storage_resource = terraform_config["resource"]["azurerm_storage_account"][
                "teststorage"
            ]

            # Tags should remain as dict
            assert "tags" in storage_resource
            assert isinstance(storage_resource["tags"], dict)
            assert storage_resource["tags"]["Environment"] == "dev"
            assert storage_resource["tags"]["CostCenter"] == "12345"

    def test_tags_invalid_json_string_should_return_empty_dict(self) -> None:
        """Test that invalid JSON string tags result in no tags field with warning."""
        emitter = TerraformEmitter()
        graph = TenantGraph()
        graph.resources = [
            {
                "type": "Microsoft.Storage/storageAccounts",
                "name": "teststorage",
                "location": "eastus",
                "resourceGroup": "test-rg",
                "tags": "{invalid json}",  # Invalid JSON
            }
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            out_dir = Path(temp_dir)
            written_files = emitter.emit(graph, out_dir)

            with open(written_files[0]) as f:
                terraform_config = json.load(f)

            storage_resource = terraform_config["resource"]["azurerm_storage_account"][
                "teststorage"
            ]

            # Should not have tags field when JSON parsing fails (to avoid invalid Terraform)
            assert "tags" not in storage_resource

    def test_tags_null_should_result_in_no_tags_field(self) -> None:
        """Test that null/None tags result in no tags field in output."""
        emitter = TerraformEmitter()
        graph = TenantGraph()
        graph.resources = [
            {
                "type": "Microsoft.Storage/storageAccounts",
                "name": "teststorage",
                "location": "eastus",
                "resourceGroup": "test-rg",
                "tags": None,
            }
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            out_dir = Path(temp_dir)
            written_files = emitter.emit(graph, out_dir)

            with open(written_files[0]) as f:
                terraform_config = json.load(f)

            storage_resource = terraform_config["resource"]["azurerm_storage_account"][
                "teststorage"
            ]

            # None tags should not create tags field
            assert "tags" not in storage_resource or storage_resource["tags"] == {}

    def test_tags_empty_string_should_result_in_no_tags_field(self) -> None:
        """Test that empty string tags result in no tags field in output."""
        emitter = TerraformEmitter()
        graph = TenantGraph()
        graph.resources = [
            {
                "type": "Microsoft.Storage/storageAccounts",
                "name": "teststorage",
                "location": "eastus",
                "resourceGroup": "test-rg",
                "tags": "",
            }
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            out_dir = Path(temp_dir)
            written_files = emitter.emit(graph, out_dir)

            with open(written_files[0]) as f:
                terraform_config = json.load(f)

            storage_resource = terraform_config["resource"]["azurerm_storage_account"][
                "teststorage"
            ]

            # Empty string should not create tags field
            assert "tags" not in storage_resource or storage_resource["tags"] == {}

    def test_tags_empty_dict_should_result_in_no_tags_field(self) -> None:
        """Test that empty dict tags result in no tags field in output."""
        emitter = TerraformEmitter()
        graph = TenantGraph()
        graph.resources = [
            {
                "type": "Microsoft.Storage/storageAccounts",
                "name": "teststorage",
                "location": "eastus",
                "resourceGroup": "test-rg",
                "tags": {},
            }
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            out_dir = Path(temp_dir)
            written_files = emitter.emit(graph, out_dir)

            with open(written_files[0]) as f:
                terraform_config = json.load(f)

            storage_resource = terraform_config["resource"]["azurerm_storage_account"][
                "teststorage"
            ]

            # Empty dict should not create tags field or should be empty
            assert "tags" not in storage_resource or storage_resource["tags"] == {}

    def test_tags_with_special_characters_should_parse_correctly(self) -> None:
        """Test tags with special characters like dashes and escaped quotes."""
        emitter = TerraformEmitter()
        graph = TenantGraph()
        graph.resources = [
            {
                "type": "Microsoft.Storage/storageAccounts",
                "name": "teststorage",
                "location": "eastus",
                "resourceGroup": "test-rg",
                "tags": '{"hidden-DevTestLabs-LabUId": "303399a5-2aaa", "Cost\\"Center": "12345"}',
            }
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            out_dir = Path(temp_dir)
            written_files = emitter.emit(graph, out_dir)

            with open(written_files[0]) as f:
                terraform_config = json.load(f)

            storage_resource = terraform_config["resource"]["azurerm_storage_account"][
                "teststorage"
            ]

            # Should parse special characters correctly
            assert "tags" in storage_resource
            assert isinstance(storage_resource["tags"], dict)
            assert (
                storage_resource["tags"]["hidden-DevTestLabs-LabUId"] == "303399a5-2aaa"
            )
            # Note: escaped quote becomes regular quote after JSON parsing
            assert storage_resource["tags"]['Cost"Center'] == "12345"

    def test_tags_missing_field_should_not_add_tags(self) -> None:
        """Test that resources without tags field don't get tags added."""
        emitter = TerraformEmitter()
        graph = TenantGraph()
        graph.resources = [
            {
                "type": "Microsoft.Storage/storageAccounts",
                "name": "teststorage",
                "location": "eastus",
                "resourceGroup": "test-rg",
                # No tags field at all
            }
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            out_dir = Path(temp_dir)
            written_files = emitter.emit(graph, out_dir)

            with open(written_files[0]) as f:
                terraform_config = json.load(f)

            storage_resource = terraform_config["resource"]["azurerm_storage_account"][
                "teststorage"
            ]

            # Should not have tags field
            assert "tags" not in storage_resource

    def test_tags_on_multiple_resources_with_mixed_formats(self) -> None:
        """Test multiple resources with different tag formats."""
        emitter = TerraformEmitter()
        graph = TenantGraph()
        graph.resources = [
            {
                "type": "Microsoft.Storage/storageAccounts",
                "name": "storage1",
                "location": "eastus",
                "resourceGroup": "test-rg",
                "tags": '{"env": "prod"}',  # JSON string
            },
            {
                "type": "Microsoft.Network/virtualNetworks",
                "name": "vnet1",
                "location": "westus",
                "resourceGroup": "test-rg",
                "tags": {"env": "dev"},  # Dict
            },
            {
                "type": "Microsoft.KeyVault/vaults",
                "name": "kv1",
                "location": "eastus2",
                "resourceGroup": "test-rg",
                "tags": "",  # Empty string
            },
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            out_dir = Path(temp_dir)
            written_files = emitter.emit(graph, out_dir)

            with open(written_files[0]) as f:
                terraform_config = json.load(f)

            # Verify storage account with JSON string tags
            storage = terraform_config["resource"]["azurerm_storage_account"][
                "storage1"
            ]
            assert isinstance(storage["tags"], dict)
            assert storage["tags"]["env"] == "prod"

            # Verify vnet with dict tags
            vnet = terraform_config["resource"]["azurerm_virtual_network"]["vnet1"]
            assert isinstance(vnet["tags"], dict)
            assert vnet["tags"]["env"] == "dev"

            # Verify key vault with empty tags
            kv = terraform_config["resource"]["azurerm_key_vault"]["kv1"]
            assert "tags" not in kv or kv["tags"] == {}


class TestTerraformTagsIntegration:
    """Integration tests for tags with actual Terraform validation."""

    @pytest.mark.skipif(
        shutil.which("terraform") is None,
        reason="Terraform CLI not found. Install via 'brew install terraform'",
    )
    def test_terraform_validate_with_json_string_tags(self, tmp_path: Path) -> None:
        """Integration test: Terraform should validate with parsed JSON string tags.

        This is the critical integration test that ensures the fix works
        end-to-end with actual Terraform CLI validation.
        """
        emitter = TerraformEmitter()
        graph = TenantGraph()
        graph.resources = [
            {
                "type": "Microsoft.Storage/storageAccounts",
                "name": "teststorage",
                "location": "eastus",
                "resourceGroup": "test-rg",
                "tags": '{"Environment": "prod", "Team": "security", "CostCenter": "12345"}',
            }
        ]

        # Generate Terraform config
        emitter.emit(graph, tmp_path)

        # Initialize Terraform
        terraform = shutil.which("terraform")
        assert terraform is not None  # Type guard for mypy

        subprocess.run(
            [
                terraform,
                f"-chdir={tmp_path!s}",
                "init",
                "-backend=false",
                "-input=false",
                "-no-color",
            ],
            check=True,
        )

        # Validate - this should pass if tags are properly formatted as dict
        proc = subprocess.run(
            [terraform, f"-chdir={tmp_path!s}", "validate", "-no-color"],
            capture_output=True,
            text=True,
        )

        # The validation should pass with properly formatted tags
        assert proc.returncode == 0, (
            f"terraform validate failed with JSON string tags:\n"
            f"STDOUT:\n{proc.stdout}\n"
            f"STDERR:\n{proc.stderr}\n"
            "This indicates tags were not properly parsed from JSON string to dict"
        )

    @pytest.mark.skipif(
        shutil.which("terraform") is None,
        reason="Terraform CLI not found. Install via 'brew install terraform'",
    )
    def test_terraform_validate_with_complex_tags(self, tmp_path: Path) -> None:
        """Integration test: Terraform validates with complex tag scenarios."""
        emitter = TerraformEmitter()
        graph = TenantGraph()
        graph.resources = [
            {
                "type": "Microsoft.Storage/storageAccounts",
                "name": "storage1",
                "location": "eastus",
                "resourceGroup": "rg1",
                "tags": '{"hidden-DevTestLabs-LabUId": "abc-123", "env": "test"}',
            },
            {
                "type": "Microsoft.Network/virtualNetworks",
                "name": "vnet1",
                "location": "westus",
                "resourceGroup": "rg1",
                "tags": {"project": "demo"},  # Dict format
            },
            {
                "type": "Microsoft.KeyVault/vaults",
                "name": "kv1",
                "location": "eastus2",
                "resourceGroup": "rg1",
                # No tags
            },
        ]

        emitter.emit(graph, tmp_path)

        terraform = shutil.which("terraform")
        assert terraform is not None

        subprocess.run(
            [
                terraform,
                f"-chdir={tmp_path!s}",
                "init",
                "-backend=false",
                "-input=false",
                "-no-color",
            ],
            check=True,
        )

        proc = subprocess.run(
            [terraform, f"-chdir={tmp_path!s}", "validate", "-no-color"],
            capture_output=True,
            text=True,
        )

        assert proc.returncode == 0, (
            f"terraform validate failed with mixed tag formats:\n"
            f"STDOUT:\n{proc.stdout}\n"
            f"STDERR:\n{proc.stderr}"
        )


class TestTerraformTagsEdgeCases:
    """Edge case tests for tags parsing."""

    def test_tags_with_nested_json_should_handle_gracefully(self) -> None:
        """Test tags with nested JSON structures."""
        emitter = TerraformEmitter()
        graph = TenantGraph()
        graph.resources = [
            {
                "type": "Microsoft.Storage/storageAccounts",
                "name": "teststorage",
                "location": "eastus",
                "resourceGroup": "test-rg",
                "tags": '{"metadata": "{\\"nested\\": \\"value\\"}"}',
            }
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            out_dir = Path(temp_dir)
            written_files = emitter.emit(graph, out_dir)

            with open(written_files[0]) as f:
                terraform_config = json.load(f)

            storage_resource = terraform_config["resource"]["azurerm_storage_account"][
                "teststorage"
            ]

            # Should parse outer JSON but keep nested as string
            assert "tags" in storage_resource
            assert isinstance(storage_resource["tags"], dict)
            assert "metadata" in storage_resource["tags"]

    def test_tags_with_unicode_characters(self) -> None:
        """Test tags with unicode characters."""
        emitter = TerraformEmitter()
        graph = TenantGraph()
        graph.resources = [
            {
                "type": "Microsoft.Storage/storageAccounts",
                "name": "teststorage",
                "location": "eastus",
                "resourceGroup": "test-rg",
                "tags": '{"owner": "José García", "description": "测试"}',
            }
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            out_dir = Path(temp_dir)
            written_files = emitter.emit(graph, out_dir)

            with open(written_files[0]) as f:
                terraform_config = json.load(f)

            storage_resource = terraform_config["resource"]["azurerm_storage_account"][
                "teststorage"
            ]

            assert "tags" in storage_resource
            assert isinstance(storage_resource["tags"], dict)
            assert storage_resource["tags"]["owner"] == "José García"
            assert storage_resource["tags"]["description"] == "测试"

    def test_tags_with_very_long_values(self) -> None:
        """Test tags with very long string values."""
        emitter = TerraformEmitter()
        long_value = "a" * 1000
        graph = TenantGraph()
        graph.resources = [
            {
                "type": "Microsoft.Storage/storageAccounts",
                "name": "teststorage",
                "location": "eastus",
                "resourceGroup": "test-rg",
                "tags": f'{{"longkey": "{long_value}"}}',
            }
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            out_dir = Path(temp_dir)
            written_files = emitter.emit(graph, out_dir)

            with open(written_files[0]) as f:
                terraform_config = json.load(f)

            storage_resource = terraform_config["resource"]["azurerm_storage_account"][
                "teststorage"
            ]

            assert "tags" in storage_resource
            assert isinstance(storage_resource["tags"], dict)
            assert storage_resource["tags"]["longkey"] == long_value

    def test_tags_with_numeric_values_in_json_string(self) -> None:
        """Test tags with numeric values in JSON string."""
        emitter = TerraformEmitter()
        graph = TenantGraph()
        graph.resources = [
            {
                "type": "Microsoft.Storage/storageAccounts",
                "name": "teststorage",
                "location": "eastus",
                "resourceGroup": "test-rg",
                "tags": '{"version": 123, "count": 456.789, "enabled": true}',
            }
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            out_dir = Path(temp_dir)
            written_files = emitter.emit(graph, out_dir)

            with open(written_files[0]) as f:
                terraform_config = json.load(f)

            storage_resource = terraform_config["resource"]["azurerm_storage_account"][
                "teststorage"
            ]

            # JSON parsing will preserve numeric types
            assert "tags" in storage_resource
            assert isinstance(storage_resource["tags"], dict)
            # Note: These may need to be converted to strings for Terraform
            # which expects string values in tags
            assert "version" in storage_resource["tags"]
            assert "count" in storage_resource["tags"]
            assert "enabled" in storage_resource["tags"]

    def test_tags_with_array_value_should_handle_gracefully(self) -> None:
        """Test tags with array values (invalid but should not crash)."""
        emitter = TerraformEmitter()
        graph = TenantGraph()
        graph.resources = [
            {
                "type": "Microsoft.Storage/storageAccounts",
                "name": "teststorage",
                "location": "eastus",
                "resourceGroup": "test-rg",
                "tags": '{"items": ["a", "b", "c"]}',
            }
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            out_dir = Path(temp_dir)
            written_files = emitter.emit(graph, out_dir)

            with open(written_files[0]) as f:
                terraform_config = json.load(f)

            storage_resource = terraform_config["resource"]["azurerm_storage_account"][
                "teststorage"
            ]

            # Should parse but may contain array (though Terraform expects strings)
            assert "tags" in storage_resource
            assert isinstance(storage_resource["tags"], dict)

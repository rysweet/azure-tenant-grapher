"""
Unit tests for ResourceTypeResolver brick.

Tests the resource type resolution logic for Azure resource types.
"""

import pytest

from src.replicator.modules.resource_type_resolver import ResourceTypeResolver


class TestResourceTypeResolver:
    """Test suite for ResourceTypeResolver brick."""

    def test_resolve_type_with_azure_type(self):
        """Test resolution using Azure resource type string."""
        labels = ["Resource"]
        azure_type = "Microsoft.Compute/virtualMachines"

        result = ResourceTypeResolver.resolve_type(labels, azure_type)

        assert result == "virtualMachines"

    def test_resolve_type_with_label_fallback(self):
        """Test resolution falling back to label when Azure type is None."""
        labels = ["Resource", "VirtualMachine"]
        azure_type = None

        result = ResourceTypeResolver.resolve_type(labels, azure_type)

        assert result == "VirtualMachine"

    def test_resolve_type_with_empty_labels_no_type(self):
        """Test resolution with empty labels and no Azure type."""
        labels = []
        azure_type = None

        result = ResourceTypeResolver.resolve_type(labels, azure_type)

        assert result == "Unknown"

    def test_resolve_type_with_resource_label_only(self):
        """Test resolution with only Resource label."""
        labels = ["Resource"]
        azure_type = None

        result = ResourceTypeResolver.resolve_type(labels, azure_type)

        # Should fall back to "Resource" or "Unknown" depending on implementation
        assert isinstance(result, str)
        assert len(result) > 0

    def test_resolve_type_with_complex_azure_type(self):
        """Test resolution with complex Azure type paths."""
        labels = ["Resource"]
        azure_type = "Microsoft.Network/networkInterfaces/ipConfigurations"

        result = ResourceTypeResolver.resolve_type(labels, azure_type)

        # Should handle nested resource types
        assert isinstance(result, str)
        assert len(result) > 0

    def test_resolve_type_with_storage_account(self):
        """Test resolution for storage account type."""
        labels = ["Resource"]
        azure_type = "Microsoft.Storage/storageAccounts"

        result = ResourceTypeResolver.resolve_type(labels, azure_type)

        assert result == "storageAccounts"

    def test_resolve_type_with_multiple_labels(self):
        """Test resolution with multiple labels (priority test)."""
        labels = ["Resource", "StorageAccount", "Original"]
        azure_type = "Microsoft.Storage/storageAccounts"

        result = ResourceTypeResolver.resolve_type(labels, azure_type)

        # Azure type should take priority
        assert result == "storageAccounts"

    def test_resolve_type_is_stateless(self):
        """Test that resolver maintains no state between calls."""
        labels1 = ["Resource"]
        azure_type1 = "Microsoft.Compute/virtualMachines"

        result1 = ResourceTypeResolver.resolve_type(labels1, azure_type1)

        labels2 = ["Resource"]
        azure_type2 = "Microsoft.Storage/storageAccounts"

        result2 = ResourceTypeResolver.resolve_type(labels2, azure_type2)

        # Results should be independent
        assert result1 == "virtualMachines"
        assert result2 == "storageAccounts"

    def test_resolve_type_with_web_app(self):
        """Test resolution for web app resource type."""
        labels = ["Resource"]
        azure_type = "Microsoft.Web/sites"

        result = ResourceTypeResolver.resolve_type(labels, azure_type)

        assert result == "sites"

    def test_resolve_type_with_key_vault(self):
        """Test resolution for Key Vault resource type."""
        labels = ["Resource"]
        azure_type = "Microsoft.KeyVault/vaults"

        result = ResourceTypeResolver.resolve_type(labels, azure_type)

        assert result == "vaults"

    def test_resolve_type_consistency(self):
        """Test that same input always produces same output (deterministic)."""
        labels = ["Resource"]
        azure_type = "Microsoft.Compute/virtualMachines"

        # Call multiple times
        results = [
            ResourceTypeResolver.resolve_type(labels, azure_type)
            for _ in range(5)
        ]

        # All results should be identical
        assert len(set(results)) == 1
        assert results[0] == "virtualMachines"

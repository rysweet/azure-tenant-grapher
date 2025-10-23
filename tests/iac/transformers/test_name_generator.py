"""Tests for unique name generator."""

import pytest

from src.iac.transformers.name_generator import UniqueNameGenerator, NameGenerationResult


class TestUniqueNameGenerator:
    """Test suite for UniqueNameGenerator."""

    @pytest.fixture
    def generator(self):
        """Create generator instance."""
        return UniqueNameGenerator()

    def test_initialization(self, generator):
        """Test generator initialization."""
        assert generator.suffix is None

    def test_initialization_with_suffix(self):
        """Test generator initialization with suffix."""
        generator = UniqueNameGenerator(suffix="prod")
        assert generator.suffix == "prod"

    def test_generate_keyvault_name(self, generator):
        """Test Key Vault name generation."""
        resources = [
            {
                "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.KeyVault/vaults/myvault",
                "type": "Microsoft.KeyVault/vaults",
                "name": "myvault",
            }
        ]

        result = generator.transform_resources(resources)

        assert result.resources_processed == 1
        assert result.resources_renamed == 1
        new_name = resources[0]["name"]

        # Validate constraints
        assert 3 <= len(new_name) <= 24
        assert new_name[0].isalpha()
        assert all(c.isalnum() or c == "-" for c in new_name)
        assert not new_name.endswith("-")

    def test_generate_storage_account_name(self, generator):
        """Test Storage Account name generation."""
        resources = [
            {
                "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Storage/storageAccounts/mystorageaccount",
                "type": "Microsoft.Storage/storageAccounts",
                "name": "MyStorageAccount",
            }
        ]

        result = generator.transform_resources(resources)

        assert result.resources_processed == 1
        assert result.resources_renamed == 1
        new_name = resources[0]["name"]

        # Validate constraints
        assert 3 <= len(new_name) <= 24
        assert new_name.islower()
        assert new_name.isalnum()

    def test_deterministic_name_generation(self, generator):
        """Test that name generation is deterministic."""
        resource = {
            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.KeyVault/vaults/test",
            "type": "Microsoft.KeyVault/vaults",
            "name": "test",
        }

        # Generate name twice
        result1 = generator.transform_resources([resource.copy()])
        name1 = result1.renames[0][2]

        result2 = generator.transform_resources([resource.copy()])
        name2 = result2.renames[0][2]

        assert name1 == name2

    def test_no_transformation_for_non_unique_types(self, generator):
        """Test no transformation for non-globally unique types."""
        resources = [
            {
                "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",
                "type": "Microsoft.Compute/virtualMachines",
                "name": "vm1",
            }
        ]

        result = generator.transform_resources(resources)

        assert result.resources_processed == 1
        assert result.resources_renamed == 0
        assert resources[0]["name"] == "vm1"

    def test_keyvault_name_max_length(self, generator):
        """Test Key Vault name respects max length."""
        resources = [
            {
                "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.KeyVault/vaults/vault",
                "type": "Microsoft.KeyVault/vaults",
                "name": "very-long-keyvault-name-that-exceeds-maximum-length-limit",
            }
        ]

        result = generator.transform_resources(resources)

        new_name = resources[0]["name"]
        assert len(new_name) <= 24

    def test_storage_name_max_length(self, generator):
        """Test Storage Account name respects max length."""
        resources = [
            {
                "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Storage/storageAccounts/storage",
                "type": "Microsoft.Storage/storageAccounts",
                "name": "verylongstorageaccountnamethatexceedsmaximumlength",
            }
        ]

        result = generator.transform_resources(resources)

        new_name = resources[0]["name"]
        assert len(new_name) <= 24

    def test_keyvault_name_with_suffix(self):
        """Test Key Vault name generation with suffix."""
        generator = UniqueNameGenerator(suffix="dev")

        resources = [
            {
                "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.KeyVault/vaults/vault",
                "type": "Microsoft.KeyVault/vaults",
                "name": "myvault",
            }
        ]

        result = generator.transform_resources(resources)

        new_name = resources[0]["name"]
        assert "dev" in new_name
        assert len(new_name) <= 24

    def test_storage_name_with_suffix(self):
        """Test Storage Account name generation with suffix."""
        generator = UniqueNameGenerator(suffix="prod")

        resources = [
            {
                "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Storage/storageAccounts/storage",
                "type": "Microsoft.Storage/storageAccounts",
                "name": "mystorage",
            }
        ]

        result = generator.transform_resources(resources)

        new_name = resources[0]["name"]
        assert "prod" in new_name
        assert len(new_name) <= 24
        assert new_name.islower()

    def test_multiple_resources(self, generator):
        """Test generating names for multiple resources."""
        resources = [
            {
                "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.KeyVault/vaults/vault1",
                "type": "Microsoft.KeyVault/vaults",
                "name": "vault1",
            },
            {
                "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Storage/storageAccounts/storage1",
                "type": "Microsoft.Storage/storageAccounts",
                "name": "storage1",
            },
            {
                "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.KeyVault/vaults/vault2",
                "type": "Microsoft.KeyVault/vaults",
                "name": "vault2",
            },
        ]

        result = generator.transform_resources(resources)

        assert result.resources_processed == 3
        assert result.resources_renamed == 3

    def test_get_generation_summary(self, generator):
        """Test generation summary."""
        result = NameGenerationResult(
            resources_processed=5,
            resources_renamed=2,
            renames=[
                ("vault1", "oldvault1", "newvault1-abc123"),
                ("storage1", "oldstorage1", "newstorage1abc123"),
            ],
        )

        summary = generator.get_generation_summary(result)

        assert "Resources processed: 5" in summary
        assert "Resources renamed: 2" in summary
        assert "oldvault1 -> newvault1-abc123" in summary
        assert "oldstorage1 -> newstorage1abc123" in summary

    def test_keyvault_name_starts_with_letter(self, generator):
        """Test Key Vault name starts with letter."""
        resources = [
            {
                "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.KeyVault/vaults/vault",
                "type": "Microsoft.KeyVault/vaults",
                "name": "123vault",  # Invalid start
            }
        ]

        result = generator.transform_resources(resources)

        new_name = resources[0]["name"]
        assert new_name[0].isalpha()

    def test_storage_name_lowercase_only(self, generator):
        """Test Storage Account name is lowercase only."""
        resources = [
            {
                "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Storage/storageAccounts/storage",
                "type": "Microsoft.Storage/storageAccounts",
                "name": "MyStorageWithCaps",
            }
        ]

        result = generator.transform_resources(resources)

        new_name = resources[0]["name"]
        assert new_name.islower()
        assert new_name.isalnum()

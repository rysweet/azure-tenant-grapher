"""Tests for community-based Terraform splitting.

Issue #473: Community-based Terraform splitting for parallel deployment
"""

import json
from unittest.mock import MagicMock

import pytest

from src.iac.community_splitter import CommunitySplitter


class TestCommunitySplitter:
    """Test CommunitySplitter class."""

    def test_split_terraform_creates_multiple_files(self, tmp_path):
        """When split_by_community enabled, creates multiple .tf.json files."""
        # Arrange
        detector = MagicMock()
        detector.detect_communities.return_value = [
            {"vm1", "nic1"},  # Community 0
            {"vnet1", "subnet1"},  # Community 1
        ]

        terraform_config = {
            "resource": {
                "azurerm_virtual_machine": {
                    "vm1": {"name": "vm1", "location": "eastus"}
                },
                "azurerm_network_interface": {
                    "nic1": {"name": "nic1", "location": "eastus"}
                },
                "azurerm_virtual_network": {
                    "vnet1": {"name": "vnet1", "location": "westus"}
                },
                "azurerm_subnet": {"subnet1": {"name": "subnet1"}},
            }
        }

        splitter = CommunitySplitter(detector)

        # Act
        files, manifest = splitter.split_terraform(terraform_config, tmp_path)

        # Assert
        assert len(files) == 3  # 2 communities + 1 manifest
        assert manifest.total_communities == 2
        assert manifest.total_resources == 4

    def test_file_naming_convention(self, tmp_path):
        """Verify files follow community_<id>_<size>_<type>.tf.json convention."""
        # Arrange
        detector = MagicMock()
        detector.detect_communities.return_value = [
            {"vm1", "vm2"},
        ]

        terraform_config = {
            "resource": {
                "azurerm_virtual_machine": {
                    "vm1": {"name": "vm1"},
                    "vm2": {"name": "vm2"},
                }
            }
        }

        splitter = CommunitySplitter(detector)

        # Act
        files, _ = splitter.split_terraform(terraform_config, tmp_path)

        # Assert
        community_files = [f for f in files if f.name != "community_manifest.json"]
        assert len(community_files) == 1
        assert community_files[0].name.startswith("community_0_2_")
        assert community_files[0].suffix == ".json"

    def test_manifest_generation(self, tmp_path):
        """Verify manifest contains correct metadata."""
        # Arrange
        detector = MagicMock()
        detector.detect_communities.return_value = [
            {"vm1"},
        ]

        terraform_config = {
            "resource": {"azurerm_virtual_machine": {"vm1": {"name": "vm1"}}}
        }

        splitter = CommunitySplitter(detector)

        # Act
        files, manifest = splitter.split_terraform(terraform_config, tmp_path)

        # Assert
        manifest_file = tmp_path / "community_manifest.json"
        assert manifest_file.exists()

        manifest_data = json.loads(manifest_file.read_text())
        assert manifest_data["total_communities"] == 1
        assert manifest_data["total_resources"] == 1
        assert len(manifest_data["communities"]) == 1

    def test_cross_community_reference_raises_error(self, tmp_path):
        """ERROR when cross-community reference detected."""
        # Arrange
        detector = MagicMock()
        detector.detect_communities.return_value = [
            {"azurerm_virtual_machine.vm1"},  # Community 0
            {"azurerm_virtual_network.vnet1"},  # Community 1
        ]

        # VM in community 0 references VNet in community 1 (INVALID!)
        terraform_config = {
            "resource": {
                "azurerm_virtual_machine": {
                    "vm1": {
                        "id": "azurerm_virtual_machine.vm1",
                        "name": "vm1",
                        "network_interface_ids": [
                            "${azurerm_virtual_network.vnet1.id}"
                        ],
                    }
                },
                "azurerm_virtual_network": {
                    "vnet1": {"id": "azurerm_virtual_network.vnet1", "name": "vnet1"}
                },
            }
        }

        splitter = CommunitySplitter(detector)

        # Act & Assert
        with pytest.raises(ValueError, match="cross-community reference"):
            splitter.split_terraform(terraform_config, tmp_path)

    def test_provider_block_in_each_file(self, tmp_path):
        """Each community file contains provider block for independent deployment."""
        # Arrange
        detector = MagicMock()
        detector.detect_communities.return_value = [
            {"vm1"},
            {"vnet1"},
        ]

        terraform_config = {
            "resource": {
                "azurerm_virtual_machine": {"vm1": {"name": "vm1"}},
                "azurerm_virtual_network": {"vnet1": {"name": "vnet1"}},
            }
        }

        splitter = CommunitySplitter(detector)

        # Act
        files, _ = splitter.split_terraform(terraform_config, tmp_path)

        # Assert
        community_files = [f for f in files if f.name != "community_manifest.json"]
        for cf in community_files:
            content = json.loads(cf.read_text())
            assert "provider" in content
            assert "azurerm" in content["provider"]

    def test_backward_compatibility_single_file(self, tmp_path):
        """When split disabled, generates single file (existing behavior)."""
        # This test verifies integration point in TerraformEmitter
        # Actual test will be in TerraformEmitter test suite
        pass


__all__ = ["TestCommunitySplitter"]

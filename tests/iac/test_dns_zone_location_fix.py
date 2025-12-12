"""Tests for DNS Zone location field fix (GitHub Issue).

DNS Zones are global Azure resources and should NOT have a location field
in Terraform output. This test ensures the TerraformEmitter correctly
excludes the location field from azurerm_dns_zone resources.
"""

import json
import tempfile
from pathlib import Path

from src.iac.emitters.terraform_emitter import TerraformEmitter
from src.iac.traverser import TenantGraph


class TestDNSZoneLocationFix:
    """Test cases for DNS Zone location field fix."""

    def test_public_dns_zone_no_location_field(self) -> None:
        """Test that public DNS zones don't have location field."""
        emitter = TerraformEmitter()

        # Create test graph with a public DNS zone resource
        graph = TenantGraph()
        graph.resources = [
            {
                "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/dnszones/example.com",
                "type": "Microsoft.Network/dnszones",
                "name": "example.com",
                "location": "eastus",  # Even if provided, should be stripped
                "resource_group": "rg1",
                "resourceGroup": "rg1",
            }
        ]

        # Generate templates
        with tempfile.TemporaryDirectory() as temp_dir:
            out_dir = Path(temp_dir)
            written_files = emitter.emit(graph, out_dir)

            # Verify file was created
            assert len(written_files) == 1
            assert written_files[0].name == "main.tf.json"

            # Parse Terraform config
            with open(written_files[0]) as f:
                terraform_config = json.load(f)

            # Verify DNS zone resource exists
            assert "azurerm_dns_zone" in terraform_config["resource"]
            dns_zone_config = terraform_config["resource"]["azurerm_dns_zone"]

            # Verify location field is NOT present
            assert len(dns_zone_config) > 0, "DNS zone resource should be present"
            for resource_name, resource_def in dns_zone_config.items():
                assert "location" not in resource_def, (
                    f"DNS zone '{resource_name}' should NOT have location field, but got: {resource_def}"
                )
                # Verify required fields ARE present
                assert "name" in resource_def
                assert "resource_group_name" in resource_def

    def test_public_dns_zone_dnsZones_casing(self) -> None:
        """Test that both dnsZones and dnszones casings are handled."""
        emitter = TerraformEmitter()

        # Create test graph with alternate casing
        graph = TenantGraph()
        graph.resources = [
            {
                "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/dnsZones/example.com",
                "type": "Microsoft.Network/dnsZones",  # Alternate casing
                "name": "example.com",
                "location": "westus",
                "resource_group": "rg1",
                "resourceGroup": "rg1",
            }
        ]

        # Generate templates
        with tempfile.TemporaryDirectory() as temp_dir:
            out_dir = Path(temp_dir)
            written_files = emitter.emit(graph, out_dir)

            # Parse Terraform config
            with open(written_files[0]) as f:
                terraform_config = json.load(f)

            # Verify DNS zone resource exists
            assert "azurerm_dns_zone" in terraform_config["resource"]
            dns_zone_config = terraform_config["resource"]["azurerm_dns_zone"]

            # Verify location field is NOT present
            for resource_name, resource_def in dns_zone_config.items():
                assert "location" not in resource_def, (
                    f"DNS zone '{resource_name}' should NOT have location field"
                )

    def test_dns_zone_with_other_resources(self) -> None:
        """Test that DNS zone location fix works alongside other resources."""
        emitter = TerraformEmitter()

        # Create test graph with mixed resources
        graph = TenantGraph()
        graph.resources = [
            {
                "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/dnszones/example.com",
                "type": "Microsoft.Network/dnszones",
                "name": "example.com",
                "location": "eastus",
                "resource_group": "rg1",
                "resourceGroup": "rg1",
            },
            {
                "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Storage/storageAccounts/teststorage",
                "type": "Microsoft.Storage/storageAccounts",
                "name": "teststorage",
                "location": "eastus",
                "resource_group": "rg1",
                "resourceGroup": "rg1",
                "account_tier": "Standard",
                "account_replication_type": "LRS",
            },
        ]

        # Generate templates
        with tempfile.TemporaryDirectory() as temp_dir:
            out_dir = Path(temp_dir)
            written_files = emitter.emit(graph, out_dir)

            # Parse Terraform config
            with open(written_files[0]) as f:
                terraform_config = json.load(f)

            # Verify DNS zone has NO location
            dns_zone_config = terraform_config["resource"]["azurerm_dns_zone"]
            for _resource_name, resource_def in dns_zone_config.items():
                assert "location" not in resource_def

            # Verify Storage Account HAS location (normal resources should keep it)
            storage_config = terraform_config["resource"]["azurerm_storage_account"]
            for _resource_name, resource_def in storage_config.items():
                assert "location" in resource_def, (
                    "Storage account should have location field"
                )


def test_terraform_validation_dns_zone() -> None:
    """Integration test: Verify generated Terraform is valid."""
    emitter = TerraformEmitter()

    graph = TenantGraph()
    graph.resources = [
        {
            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/dnszones/example.com",
            "type": "Microsoft.Network/dnszones",
            "name": "example.com",
            "location": "eastus",
            "resource_group": "rg1",
            "resourceGroup": "rg1",
        }
    ]

    with tempfile.TemporaryDirectory() as temp_dir:
        out_dir = Path(temp_dir)
        written_files = emitter.emit(graph, out_dir)

        # Parse Terraform config
        with open(written_files[0]) as f:
            terraform_config = json.load(f)

        # Verify Terraform JSON structure is valid
        assert isinstance(terraform_config, dict)
        assert "terraform" in terraform_config
        assert "provider" in terraform_config
        assert "resource" in terraform_config

        # Verify azurerm provider is configured
        assert "azurerm" in terraform_config["provider"]
        assert "azurerm" in terraform_config["terraform"]["required_providers"]

        # Verify no JSON serialization errors would occur
        json_str = json.dumps(terraform_config, indent=2)
        assert len(json_str) > 0

        # Re-parse to ensure valid JSON
        reparsed = json.loads(json_str)
        assert reparsed == terraform_config

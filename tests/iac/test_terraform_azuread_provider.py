"""Tests for Azure AD provider configuration in Terraform emitter.

Tests that the TerraformEmitter correctly includes the Azure AD provider
when generating Terraform configurations with Azure AD resources.
"""

import json
import tempfile
from pathlib import Path

from src.iac.emitters.terraform_emitter import TerraformEmitter
from src.iac.traverser import TenantGraph


class TestTerraformAzureADProvider:
    """Test cases for Azure AD provider configuration in TerraformEmitter."""

    def test_azuread_provider_included_with_ad_resources(self) -> None:
        """Test that Azure AD provider is included when Azure AD resources are present."""
        emitter = TerraformEmitter()

        # Create test graph with Azure AD resources
        graph = TenantGraph()
        graph.resources = [
            {
                "type": "Microsoft.AAD/User",
                "name": "testuser",
                "userPrincipalName": "testuser@example.com",
            },
            {
                "type": "Microsoft.AAD/Group",
                "name": "testgroup",
                "displayName": "Test Group",
            },
            {
                "type": "Microsoft.AAD/ServicePrincipal",
                "name": "testsp",
                "displayName": "Test Service Principal",
                "applicationId": "11111111-1111-1111-1111-111111111111",
            },
            {
                "type": "Microsoft.Storage/storageAccounts",
                "name": "teststorage",
                "location": "East US",
                "resourceGroup": "test-rg",
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

            # Check terraform block includes azuread provider
            assert "required_providers" in terraform_config["terraform"]
            assert "azurerm" in terraform_config["terraform"]["required_providers"]
            assert "azuread" in terraform_config["terraform"]["required_providers"], (
                "Azure AD provider is missing from required_providers"
            )

            # Check provider block includes both azurerm and azuread
            # Provider block should be a list containing both providers
            providers = terraform_config["provider"]
            assert isinstance(providers, list), (
                "Provider block should be a list when multiple providers are present"
            )

            # Check that both providers are present
            provider_types = []
            for provider in providers:
                provider_types.extend(provider.keys())

            assert "azurerm" in provider_types, "azurerm provider missing"
            assert "azuread" in provider_types, "azuread provider missing"

            # Check resources were converted
            assert "azurerm_storage_account" in terraform_config["resource"]
            assert "azuread_user" in terraform_config["resource"], (
                "Azure AD user resource was not converted"
            )
            assert "azuread_group" in terraform_config["resource"], (
                "Azure AD group resource was not converted"
            )
            assert "azuread_service_principal" in terraform_config["resource"], (
                "Azure AD service principal resource was not converted"
            )

    def test_azuread_provider_not_included_without_ad_resources(self) -> None:
        """Test that Azure AD provider is not included when no Azure AD resources are present."""
        emitter = TerraformEmitter()

        # Create test graph with only Azure resources (no Azure AD)
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
            },
        ]

        # Create temporary output directory
        with tempfile.TemporaryDirectory() as temp_dir:
            out_dir = Path(temp_dir)

            # Generate templates
            written_files = emitter.emit(graph, out_dir)

            # Verify content structure
            with open(written_files[0]) as f:
                terraform_config = json.load(f)

            # When no Azure AD resources, provider can be a dict (single provider)
            # or a list with just azurerm
            providers = terraform_config["provider"]
            if isinstance(providers, dict):
                # Single provider case - should only have azurerm
                assert "azurerm" in providers
                assert "azuread" not in providers
            else:
                # List of providers case - should not include azuread
                provider_types = []
                for provider in providers:
                    provider_types.extend(provider.keys())
                assert "azurerm" in provider_types
                assert "azuread" not in provider_types

    def test_azure_ad_resource_type_mappings(self) -> None:
        """Test that Azure AD resource types are properly mapped to Terraform resources."""
        emitter = TerraformEmitter()

        # Check that Azure AD mappings exist
        assert "Microsoft.AAD/User" in emitter.AZURE_TO_TERRAFORM_MAPPING, (
            "Microsoft.AAD/User mapping is missing"
        )
        assert (
            emitter.AZURE_TO_TERRAFORM_MAPPING["Microsoft.AAD/User"] == "azuread_user"
        )

        assert "Microsoft.AAD/Group" in emitter.AZURE_TO_TERRAFORM_MAPPING, (
            "Microsoft.AAD/Group mapping is missing"
        )
        assert (
            emitter.AZURE_TO_TERRAFORM_MAPPING["Microsoft.AAD/Group"] == "azuread_group"
        )

        assert "Microsoft.AAD/ServicePrincipal" in emitter.AZURE_TO_TERRAFORM_MAPPING, (
            "Microsoft.AAD/ServicePrincipal mapping is missing"
        )
        assert (
            emitter.AZURE_TO_TERRAFORM_MAPPING["Microsoft.AAD/ServicePrincipal"]
            == "azuread_service_principal"
        )

    def test_service_principal_uses_client_id_field(self) -> None:
        """Test that Azure AD service principals use 'client_id' not 'application_id' field.

        This is a regression test for the bug where Service Principals were generated
        with 'application_id' instead of 'client_id', causing Terraform validation errors.
        The azuread_service_principal Terraform resource requires 'client_id', not 'application_id'.
        """
        emitter = TerraformEmitter()

        # Create test graph with Service Principal
        graph = TenantGraph()
        graph.resources = [
            {
                "type": "Microsoft.AAD/ServicePrincipal",
                "name": "test-app-sp",
                "displayName": "Test Application Service Principal",
                "applicationId": "12345678-1234-1234-1234-123456789012",
                "accountEnabled": True,
            },
            {
                "type": "Microsoft.Graph/servicePrincipals",
                "name": "test-graph-sp",
                "displayName": "Test Graph Service Principal",
                "applicationId": "87654321-4321-4321-4321-210987654321",
                "accountEnabled": False,
            },
        ]

        # Generate templates
        with tempfile.TemporaryDirectory() as temp_dir:
            out_dir = Path(temp_dir)
            written_files = emitter.emit(graph, out_dir)

            # Verify file was created
            assert len(written_files) == 1

            # Read and validate content
            with open(written_files[0]) as f:
                terraform_config = json.load(f)

            # Get service principals from generated config
            sp_resources = terraform_config.get("resource", {}).get(
                "azuread_service_principal", {}
            )
            assert len(sp_resources) == 2, "Expected 2 service principal resources"

            # Verify each service principal has 'client_id' and not 'application_id'
            for sp_name, sp_config in sp_resources.items():
                # Must have client_id field
                assert "client_id" in sp_config, (
                    f"Service principal '{sp_name}' missing 'client_id' field. "
                    "This is required by the azuread_service_principal Terraform resource."
                )

                # Must NOT have application_id field (regression test)
                assert "application_id" not in sp_config, (
                    f"Service principal '{sp_name}' has 'application_id' field. "
                    "This field is not recognized by azuread_service_principal resource. "
                    "Use 'client_id' instead."
                )

                # Verify client_id has the correct value
                if sp_name == "test_app_sp":
                    assert (
                        sp_config["client_id"] == "12345678-1234-1234-1234-123456789012"
                    )
                elif sp_name == "test_graph_sp":
                    assert (
                        sp_config["client_id"] == "87654321-4321-4321-4321-210987654321"
                    )

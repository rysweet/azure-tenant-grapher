"""Tests for identity resource generation in Terraform emitter.

Tests that the TerraformEmitter correctly generates Terraform configurations
for Entra ID (Azure AD) identity resources including Users, Groups, and
Service Principals with IaC-standard properties.
"""

import json
import tempfile
from pathlib import Path

from src.iac.emitters.terraform_emitter import TerraformEmitter
from src.iac.traverser import TenantGraph


class TestTerraformEmitterIdentities:
    """Test cases for identity resource generation in TerraformEmitter."""

    def test_azuread_user_generation_with_standard_properties(self) -> None:
        """Test that azuread_user resources are generated with all required properties."""
        emitter = TerraformEmitter()

        # Create test graph with User resource containing IaC-standard properties
        graph = TenantGraph()
        graph.resources = [
            {
                "id": "user-001",
                "type": "Microsoft.Graph/users",
                "name": "John Doe",
                "displayName": "John Doe",
                "userPrincipalName": "john.doe@example.com",
                "location": "global",
                "resourceGroup": "identity-resources",
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

            # Check that azuread_user resource was created
            assert "resource" in terraform_config
            assert "azuread_user" in terraform_config["resource"], (
                "azuread_user resource was not generated"
            )

            # Get the user resource
            user_resources = terraform_config["resource"]["azuread_user"]
            assert len(user_resources) > 0, "No azuread_user resources found"

            # Check the first user resource
            user_key = next(iter(user_resources.keys()))
            user_config = user_resources[user_key]

            # Verify required properties
            assert "display_name" in user_config or "displayName" in user_config, (
                "display_name is missing from azuread_user"
            )
            assert (
                "user_principal_name" in user_config
                or "userPrincipalName" in user_config
            ), "user_principal_name is missing from azuread_user"

            # Verify Azure AD provider is included
            assert "provider" in terraform_config
            providers = terraform_config["provider"]
            if isinstance(providers, list):
                provider_types = []
                for provider in providers:
                    provider_types.extend(provider.keys())
                assert "azuread" in provider_types, "azuread provider missing"
            else:
                assert "azuread" in providers, "azuread provider missing"

    def test_azuread_group_generation_with_standard_properties(self) -> None:
        """Test that azuread_group resources are generated with all required properties."""
        emitter = TerraformEmitter()

        # Create test graph with Group resource containing IaC-standard properties
        graph = TenantGraph()
        graph.resources = [
            {
                "id": "group-001",
                "type": "Microsoft.Graph/groups",
                "name": "Engineering Team",
                "displayName": "Engineering Team",
                "location": "global",
                "resourceGroup": "identity-resources",
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

            # Check that azuread_group resource was created
            assert "azuread_group" in terraform_config["resource"], (
                "azuread_group resource was not generated"
            )

            # Get the group resource
            group_resources = terraform_config["resource"]["azuread_group"]
            assert len(group_resources) > 0, "No azuread_group resources found"

            # Check the first group resource
            group_key = next(iter(group_resources.keys()))
            group_config = group_resources[group_key]

            # Verify required properties
            assert "display_name" in group_config or "displayName" in group_config, (
                "display_name is missing from azuread_group"
            )

    def test_azuread_service_principal_generation(self) -> None:
        """Test that azuread_service_principal resources are generated correctly."""
        emitter = TerraformEmitter()

        # Create test graph with ServicePrincipal resource
        graph = TenantGraph()
        graph.resources = [
            {
                "id": "sp-001",
                "type": "Microsoft.Graph/servicePrincipals",
                "name": "MyApp Service Principal",
                "displayName": "MyApp Service Principal",
                "applicationId": "22222222-2222-2222-2222-222222222222",
                "location": "global",
                "resourceGroup": "identity-resources",
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

            # Check that azuread_service_principal resource was created
            assert "azuread_service_principal" in terraform_config["resource"], (
                "azuread_service_principal resource was not generated"
            )

            # Get the service principal resource
            sp_resources = terraform_config["resource"]["azuread_service_principal"]
            assert len(sp_resources) > 0, "No azuread_service_principal resources found"

    def test_multiple_identity_resources_generation(self) -> None:
        """Test generation of multiple identity resources together."""
        emitter = TerraformEmitter()

        # Create test graph with multiple identity resources
        graph = TenantGraph()
        graph.resources = [
            {
                "id": "user-001",
                "type": "Microsoft.Graph/users",
                "name": "Alice Smith",
                "displayName": "Alice Smith",
                "userPrincipalName": "alice.smith@example.com",
                "location": "global",
                "resourceGroup": "identity-resources",
            },
            {
                "id": "user-002",
                "type": "Microsoft.Graph/users",
                "name": "Bob Jones",
                "displayName": "Bob Jones",
                "userPrincipalName": "bob.jones@example.com",
                "location": "global",
                "resourceGroup": "identity-resources",
            },
            {
                "id": "group-001",
                "type": "Microsoft.Graph/groups",
                "name": "Developers",
                "displayName": "Developers",
                "location": "global",
                "resourceGroup": "identity-resources",
            },
            {
                "id": "sp-001",
                "type": "Microsoft.Graph/servicePrincipals",
                "name": "API Service Principal",
                "displayName": "API Service Principal",
                "applicationId": "44444444-4444-4444-4444-444444444444",
                "location": "global",
                "resourceGroup": "identity-resources",
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

            # Check that all identity resource types are present
            assert "azuread_user" in terraform_config["resource"], (
                "azuread_user resources missing"
            )
            assert "azuread_group" in terraform_config["resource"], (
                "azuread_group resources missing"
            )
            assert "azuread_service_principal" in terraform_config["resource"], (
                "azuread_service_principal resources missing"
            )

            # Verify correct counts
            user_count = len(terraform_config["resource"]["azuread_user"])
            assert user_count == 2, f"Expected 2 users, got {user_count}"

            group_count = len(terraform_config["resource"]["azuread_group"])
            assert group_count == 1, f"Expected 1 group, got {group_count}"

            sp_count = len(terraform_config["resource"]["azuread_service_principal"])
            assert sp_count == 1, f"Expected 1 service principal, got {sp_count}"

    def test_identity_resources_mixed_with_azure_resources(self) -> None:
        """Test that identity resources are correctly generated alongside Azure resources."""
        emitter = TerraformEmitter()

        # Create test graph with both identity and Azure resources
        graph = TenantGraph()
        graph.resources = [
            {
                "id": "user-001",
                "type": "Microsoft.Graph/users",
                "name": "Test User",
                "displayName": "Test User",
                "userPrincipalName": "test.user@example.com",
                "location": "global",
                "resourceGroup": "identity-resources",
            },
            {
                "id": "storage-001",
                "type": "Microsoft.Storage/storageAccounts",
                "name": "teststorage",
                "location": "East US",
                "resourceGroup": "storage-rg",
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

            # Check both identity and Azure resources are present
            assert "azuread_user" in terraform_config["resource"], (
                "Identity resource missing"
            )
            assert "azurerm_storage_account" in terraform_config["resource"], (
                "Azure resource missing"
            )

            # Verify both azurerm and azuread providers are present
            providers = terraform_config["provider"]
            if isinstance(providers, list):
                provider_types = []
                for provider in providers:
                    provider_types.extend(provider.keys())
                assert "azurerm" in provider_types, "azurerm provider missing"
                assert "azuread" in provider_types, "azuread provider missing"
            else:
                # Should be a list when multiple providers are needed
                raise AssertionError(
                    "Provider should be a list with multiple providers"
                )

    def test_managed_identity_not_in_azuread_provider(self) -> None:
        """Test that Managed Identities are not treated as Azure AD resources."""
        emitter = TerraformEmitter()

        # Create test graph with ManagedIdentity
        graph = TenantGraph()
        graph.resources = [
            {
                "id": "mi-001",
                "type": "Microsoft.ManagedIdentity/managedIdentities",
                "name": "test-managed-identity",
                "location": "East US",
                "resourceGroup": "identity-rg",
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

            # Managed Identity should use azurerm provider, not azuread
            assert "resource" in terraform_config
            # It should be an azurerm_user_assigned_identity
            assert "azurerm_user_assigned_identity" in terraform_config[
                "resource"
            ] or "azurerm_user_assigned_identity" in str(terraform_config), (
                "Managed Identity should use azurerm provider"
            )

            # Azure AD provider should NOT be included for just managed identities
            providers = terraform_config["provider"]
            if isinstance(providers, dict):
                assert "azurerm" in providers
                assert "azuread" not in providers, (
                    "azuread provider should not be included for managed identities only"
                )
            elif isinstance(providers, list):
                provider_types = []
                for provider in providers:
                    provider_types.extend(provider.keys())
                assert "azurerm" in provider_types
                assert "azuread" not in provider_types, (
                    "azuread provider should not be included for managed identities only"
                )

    def test_azuread_user_with_parentheses_in_upn(self) -> None:
        """Test that UPNs with parentheses are sanitized correctly.

        Tests the fix for users with parentheses in their UPNs like:
        - BrianHooper(DEX)@example.com -> BrianHooper-DEX@example.com
        - MichaelHoward(REDTEAM)@example.com -> MichaelHoward-REDTEAM@example.com
        """
        emitter = TerraformEmitter()

        # Create test graph with users having parentheses in UPN
        graph = TenantGraph()
        graph.resources = [
            {
                "id": "user-001",
                "type": "Microsoft.Graph/users",
                "name": "BrianHooper",
                "displayName": "Brian Hooper",
                "userPrincipalName": "BrianHooper(DEX)@example.com",
                "location": "global",
                "resourceGroup": "identity-resources",
            },
            {
                "id": "user-002",
                "type": "Microsoft.Graph/users",
                "name": "CameronThomas",
                "displayName": "Cameron Thomas",
                "userPrincipalName": "CameronThomas(DEX)@example.com",
                "location": "global",
                "resourceGroup": "identity-resources",
            },
            {
                "id": "user-003",
                "type": "Microsoft.Graph/users",
                "name": "MichaelHoward",
                "displayName": "Michael Howard",
                "userPrincipalName": "MichaelHoward(REDTEAM)@example.com",
                "location": "global",
                "resourceGroup": "identity-resources",
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

            # Check that azuread_user resources were created
            assert "azuread_user" in terraform_config["resource"], (
                "azuread_user resource was not generated"
            )

            user_resources = terraform_config["resource"]["azuread_user"]
            assert len(user_resources) == 3, "Expected 3 users"

            # Check that parentheses have been removed/replaced with hyphens
            upn_values = []
            for user_config in user_resources.values():
                upn = user_config.get("user_principal_name")
                if upn:
                    upn_values.append(upn)

            # Verify no UPNs contain parentheses
            for upn in upn_values:
                assert "(" not in upn, (
                    f"UPN '{upn}' still contains opening parenthesis"
                )
                assert ")" not in upn, (
                    f"UPN '{upn}' still contains closing parenthesis"
                )

            # Verify expected transformation (parentheses replaced with hyphens)
            assert any(
                "BrianHooper-DEX@example.com" in upn for upn in upn_values
            ), "BrianHooper(DEX) should be sanitized to BrianHooper-DEX"

            assert any(
                "CameronThomas-DEX@example.com" in upn for upn in upn_values
            ), "CameronThomas(DEX) should be sanitized to CameronThomas-DEX"

            assert any(
                "MichaelHoward-REDTEAM@example.com" in upn
                for upn in upn_values
            ), "MichaelHoward(REDTEAM) should be sanitized to MichaelHoward-REDTEAM"

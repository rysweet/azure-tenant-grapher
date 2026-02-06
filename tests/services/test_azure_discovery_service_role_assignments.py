"""
Tests for resource-scoped role assignments discovery in AzureDiscoveryService.

This module tests Phase 3: Resource-Scoped Role Assignments Discovery, which
discovers role assignments scoped to individual resources (Key Vaults, Storage
Accounts, etc.) using AuthorizationManagementClient.list_for_resource().
"""

import asyncio
from unittest.mock import MagicMock

import pytest

from src.config_manager import AzureTenantGrapherConfig
from src.services.azure_discovery_service import AzureDiscoveryService


class MockRoleAssignment:
    """Mock role assignment returned by Azure Authorization API."""

    def __init__(
        self,
        assignment_id: str,
        principal_id: str,
        principal_type: str,
        role_definition_id: str,
        scope: str,
    ):
        self.id = assignment_id
        self.principal_id = principal_id
        self.principal_type = principal_type
        self.role_definition_id = role_definition_id
        self.scope = scope


@pytest.fixture
def mock_config():
    """Create a mock configuration."""
    config = MagicMock(spec=AzureTenantGrapherConfig)
    config.tenant_id = "test-tenant-id"
    config.processing = MagicMock()
    config.processing.max_retries = 3
    config.processing.max_build_threads = 20
    return config


@pytest.fixture
def mock_credential():
    """Create a mock Azure credential."""
    credential = MagicMock()
    credential.get_token.return_value = MagicMock(token="fake-token")
    return credential


@pytest.fixture
def mock_authorization_client():
    """Create a mock AuthorizationManagementClient."""
    return MagicMock()


def test_discover_resource_scoped_role_assignments_basic(
    mock_config, mock_credential, mock_authorization_client
):
    """Test basic resource-scoped role assignment discovery for Key Vault."""
    # Arrange
    subscription_id = "test-subscription-id"
    vault_id = "/subscriptions/test-subscription-id/resourceGroups/test-rg/providers/Microsoft.KeyVault/vaults/test-vault"
    resources = [
        {
            "id": vault_id,
            "name": "test-vault",
            "type": "Microsoft.KeyVault/vaults",
            "location": "eastus",
            "resource_group": "test-rg",
            "scan_id": "scan-123",
            "tenant_id": "tenant-456",
        }
    ]

    # Mock resource-scoped role assignment
    mock_assignment = MockRoleAssignment(
        assignment_id=f"{vault_id}/providers/Microsoft.Authorization/roleAssignments/abc123",
        principal_id="principal-id-123",
        principal_type="ServicePrincipal",
        role_definition_id="/subscriptions/test-subscription-id/providers/Microsoft.Authorization/roleDefinitions/00482a5a-887f-4fb3-b363-3b7fe8e74483",
        scope=vault_id,  # Scoped to the vault
    )

    mock_authorization_client.role_assignments.list_for_resource.return_value = [
        mock_assignment
    ]

    def authorization_factory(credential, sub_id):
        return mock_authorization_client

    service = AzureDiscoveryService(
        mock_config,
        mock_credential,
        authorization_client_factory=authorization_factory,
    )

    # Act
    result = asyncio.run(
        service.discover_resource_scoped_role_assignments(subscription_id, resources)
    )

    # Assert
    assert len(result) == 1
    assert result[0]["id"] == mock_assignment.id
    assert result[0]["type"] == "Microsoft.Authorization/roleAssignments"
    assert result[0]["subscription_id"] == subscription_id
    assert result[0]["resource_group"] == "test-rg"
    assert result[0]["scan_id"] == "scan-123"
    assert result[0]["tenant_id"] == "tenant-456"

    # Verify properties
    props = result[0]["properties"]
    assert props["principalId"] == "principal-id-123"
    assert props["principalType"] == "ServicePrincipal"
    assert props["scope"] == vault_id

    # Verify list_for_resource was called correctly
    mock_authorization_client.role_assignments.list_for_resource.assert_called_once_with(
        resource_group_name="test-rg",
        resource_provider_namespace="Microsoft.KeyVault",
        parent_resource_path="",
        resource_type="vaults",
        resource_name="test-vault",
    )


def test_discover_resource_scoped_role_assignments_multiple_resources(
    mock_config, mock_credential, mock_authorization_client
):
    """Test resource-scoped role assignments for multiple resources."""
    # Arrange
    subscription_id = "test-subscription-id"
    vault_id = "/subscriptions/test-subscription-id/resourceGroups/test-rg/providers/Microsoft.KeyVault/vaults/vault1"
    storage_id = "/subscriptions/test-subscription-id/resourceGroups/test-rg/providers/Microsoft.Storage/storageAccounts/storage1"

    resources = [
        {
            "id": vault_id,
            "name": "vault1",
            "type": "Microsoft.KeyVault/vaults",
            "location": "eastus",
            "resource_group": "test-rg",
            "scan_id": "scan-123",
            "tenant_id": "tenant-456",
        },
        {
            "id": storage_id,
            "name": "storage1",
            "type": "Microsoft.Storage/storageAccounts",
            "location": "eastus",
            "resource_group": "test-rg",
            "scan_id": "scan-123",
            "tenant_id": "tenant-456",
        },
    ]

    # Mock assignments for both resources
    vault_assignment = MockRoleAssignment(
        assignment_id=f"{vault_id}/providers/Microsoft.Authorization/roleAssignments/vault-assign",
        principal_id="vault-principal",
        principal_type="ServicePrincipal",
        role_definition_id="/subscriptions/test-subscription-id/providers/Microsoft.Authorization/roleDefinitions/00482a5a-887f-4fb3-b363-3b7fe8e74483",
        scope=vault_id,
    )

    storage_assignment = MockRoleAssignment(
        assignment_id=f"{storage_id}/providers/Microsoft.Authorization/roleAssignments/storage-assign",
        principal_id="storage-principal",
        principal_type="User",
        role_definition_id="/subscriptions/test-subscription-id/providers/Microsoft.Authorization/roleDefinitions/ba92f5b4-2d11-453d-a403-e96b0029c9fe",
        scope=storage_id,
    )

    def mock_list_for_resource(
        resource_group_name,
        resource_provider_namespace,
        parent_resource_path,
        resource_type,
        resource_name,
    ):
        if resource_name == "vault1":
            return [vault_assignment]
        elif resource_name == "storage1":
            return [storage_assignment]
        return []

    mock_authorization_client.role_assignments.list_for_resource.side_effect = (
        mock_list_for_resource
    )

    def authorization_factory(credential, sub_id):
        return mock_authorization_client

    service = AzureDiscoveryService(
        mock_config,
        mock_credential,
        authorization_client_factory=authorization_factory,
    )

    # Act
    result = asyncio.run(
        service.discover_resource_scoped_role_assignments(subscription_id, resources)
    )

    # Assert
    assert len(result) == 2
    assert result[0]["properties"]["principalId"] == "vault-principal"
    assert result[1]["properties"]["principalId"] == "storage-principal"


def test_discover_resource_scoped_role_assignments_filters_subscription_scope(
    mock_config, mock_credential, mock_authorization_client
):
    """Test that subscription-level assignments are filtered out."""
    # Arrange
    subscription_id = "test-subscription-id"
    vault_id = "/subscriptions/test-subscription-id/resourceGroups/test-rg/providers/Microsoft.KeyVault/vaults/test-vault"
    resources = [
        {
            "id": vault_id,
            "name": "test-vault",
            "type": "Microsoft.KeyVault/vaults",
            "location": "eastus",
            "resource_group": "test-rg",
        }
    ]

    # Mock both resource-scoped and subscription-scoped assignments
    resource_scoped = MockRoleAssignment(
        assignment_id=f"{vault_id}/providers/Microsoft.Authorization/roleAssignments/resource-assign",
        principal_id="resource-principal",
        principal_type="ServicePrincipal",
        role_definition_id="/subscriptions/test-subscription-id/providers/Microsoft.Authorization/roleDefinitions/role1",
        scope=vault_id,  # Scoped to resource
    )

    subscription_scoped = MockRoleAssignment(
        assignment_id=f"/subscriptions/{subscription_id}/providers/Microsoft.Authorization/roleAssignments/sub-assign",
        principal_id="sub-principal",
        principal_type="User",
        role_definition_id="/subscriptions/test-subscription-id/providers/Microsoft.Authorization/roleDefinitions/role2",
        scope=f"/subscriptions/{subscription_id}",  # Scoped to subscription
    )

    mock_authorization_client.role_assignments.list_for_resource.return_value = [
        resource_scoped,
        subscription_scoped,  # Should be filtered out
    ]

    def authorization_factory(credential, sub_id):
        return mock_authorization_client

    service = AzureDiscoveryService(
        mock_config,
        mock_credential,
        authorization_client_factory=authorization_factory,
    )

    # Act
    result = asyncio.run(
        service.discover_resource_scoped_role_assignments(subscription_id, resources)
    )

    # Assert
    assert len(result) == 1  # Only resource-scoped assignment
    assert result[0]["properties"]["principalId"] == "resource-principal"


def test_discover_resource_scoped_role_assignments_unsupported_type(
    mock_config, mock_credential, mock_authorization_client
):
    """Test graceful handling of unsupported resource types."""
    # Arrange
    subscription_id = "test-subscription-id"
    resources = [
        {
            "id": "/subscriptions/test-subscription-id/resourceGroups/test-rg/providers/Microsoft.Network/networkInterfaces/nic1",
            "name": "nic1",
            "type": "Microsoft.Network/networkInterfaces",  # Not in target_types
            "location": "eastus",
            "resource_group": "test-rg",
        }
    ]

    def authorization_factory(credential, sub_id):
        return mock_authorization_client

    service = AzureDiscoveryService(
        mock_config,
        mock_credential,
        authorization_client_factory=authorization_factory,
    )

    # Act
    result = asyncio.run(
        service.discover_resource_scoped_role_assignments(subscription_id, resources)
    )

    # Assert
    assert len(result) == 0
    # Verify no API calls for unsupported type
    mock_authorization_client.role_assignments.list_for_resource.assert_not_called()


def test_discover_resource_scoped_role_assignments_permission_error(
    mock_config, mock_credential, mock_authorization_client
):
    """Test graceful handling of permission errors."""
    # Arrange
    subscription_id = "test-subscription-id"
    resources = [
        {
            "id": "/subscriptions/test-subscription-id/resourceGroups/test-rg/providers/Microsoft.KeyVault/vaults/restricted-vault",
            "name": "restricted-vault",
            "type": "Microsoft.KeyVault/vaults",
            "location": "eastus",
            "resource_group": "test-rg",
        }
    ]

    # Mock permission error
    mock_authorization_client.role_assignments.list_for_resource.side_effect = (
        Exception("Access denied: insufficient privileges")
    )

    def authorization_factory(credential, sub_id):
        return mock_authorization_client

    service = AzureDiscoveryService(
        mock_config,
        mock_credential,
        authorization_client_factory=authorization_factory,
    )

    # Act
    result = asyncio.run(
        service.discover_resource_scoped_role_assignments(subscription_id, resources)
    )

    # Assert
    assert len(result) == 0  # Permission error handled gracefully


def test_discover_resource_scoped_role_assignments_no_assignments(
    mock_config, mock_credential, mock_authorization_client
):
    """Test resource with no role assignments."""
    # Arrange
    subscription_id = "test-subscription-id"
    resources = [
        {
            "id": "/subscriptions/test-subscription-id/resourceGroups/test-rg/providers/Microsoft.KeyVault/vaults/empty-vault",
            "name": "empty-vault",
            "type": "Microsoft.KeyVault/vaults",
            "location": "eastus",
            "resource_group": "test-rg",
        }
    ]

    # Mock empty assignments list
    mock_authorization_client.role_assignments.list_for_resource.return_value = []

    def authorization_factory(credential, sub_id):
        return mock_authorization_client

    service = AzureDiscoveryService(
        mock_config,
        mock_credential,
        authorization_client_factory=authorization_factory,
    )

    # Act
    result = asyncio.run(
        service.discover_resource_scoped_role_assignments(subscription_id, resources)
    )

    # Assert
    assert len(result) == 0


def test_extract_provider():
    """Test _extract_provider helper method."""
    # Arrange
    config = MagicMock(spec=AzureTenantGrapherConfig)
    config.tenant_id = "test-tenant-id"
    credential = MagicMock()
    service = AzureDiscoveryService(config, credential)

    # Act & Assert
    assert (
        service._extract_provider("Microsoft.KeyVault/vaults") == "Microsoft.KeyVault"
    )
    assert (
        service._extract_provider("Microsoft.Storage/storageAccounts")
        == "Microsoft.Storage"
    )
    assert service._extract_provider("invalid-type") == ""
    assert service._extract_provider("") == ""


def test_extract_resource_type():
    """Test _extract_resource_type helper method."""
    # Arrange
    config = MagicMock(spec=AzureTenantGrapherConfig)
    config.tenant_id = "test-tenant-id"
    credential = MagicMock()
    service = AzureDiscoveryService(config, credential)

    # Act & Assert
    assert service._extract_resource_type("Microsoft.KeyVault/vaults") == "vaults"
    assert (
        service._extract_resource_type("Microsoft.Storage/storageAccounts")
        == "storageAccounts"
    )
    assert service._extract_resource_type("invalid-type") == ""
    assert service._extract_resource_type("") == ""


def test_discover_resource_scoped_role_assignments_preserves_scan_metadata(
    mock_config, mock_credential, mock_authorization_client
):
    """Test that resource-scoped assignments preserve scan_id and tenant_id."""
    # Arrange
    subscription_id = "test-subscription-id"
    vault_id = "/subscriptions/test-subscription-id/resourceGroups/test-rg/providers/Microsoft.KeyVault/vaults/test-vault"
    resources = [
        {
            "id": vault_id,
            "name": "test-vault",
            "type": "Microsoft.KeyVault/vaults",
            "location": "eastus",
            "resource_group": "test-rg",
            "scan_id": "critical-scan-id",
            "tenant_id": "critical-tenant-id",
        }
    ]

    mock_assignment = MockRoleAssignment(
        assignment_id=f"{vault_id}/providers/Microsoft.Authorization/roleAssignments/test-assign",
        principal_id="test-principal",
        principal_type="ServicePrincipal",
        role_definition_id="/subscriptions/test-subscription-id/providers/Microsoft.Authorization/roleDefinitions/role1",
        scope=vault_id,
    )

    mock_authorization_client.role_assignments.list_for_resource.return_value = [
        mock_assignment
    ]

    def authorization_factory(credential, sub_id):
        return mock_authorization_client

    service = AzureDiscoveryService(
        mock_config,
        mock_credential,
        authorization_client_factory=authorization_factory,
    )

    # Act
    result = asyncio.run(
        service.discover_resource_scoped_role_assignments(subscription_id, resources)
    )

    # Assert
    assert len(result) == 1
    assert result[0]["scan_id"] == "critical-scan-id"
    assert result[0]["tenant_id"] == "critical-tenant-id"

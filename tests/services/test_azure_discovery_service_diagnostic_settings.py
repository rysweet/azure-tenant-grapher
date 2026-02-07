"""
Tests for diagnostic settings discovery in AzureDiscoveryService.

This module tests Phase 2: Diagnostic Settings Discovery, which discovers
diagnostic settings for resources that support them using MonitorManagementClient.
"""

import asyncio
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock

import pytest

from src.config_manager import AzureTenantGrapherConfig
from src.services.azure_discovery_service import AzureDiscoveryService


class MockDiagnosticSetting:
    """Mock diagnostic setting returned by Azure Monitor API."""

    def __init__(
        self,
        setting_id: str,
        name: str,
        logs: Optional[List[Dict[str, Any]]] = None,
        metrics: Optional[List[Dict[str, Any]]] = None,
        workspace_id: Optional[str] = None,
        storage_account_id: Optional[str] = None,
    ):
        self.id = setting_id
        self.name = name
        self.logs = logs or []
        self.metrics = metrics or []
        self.workspace_id = workspace_id
        self.storage_account_id = storage_account_id
        self.event_hub_authorization_rule_id = None
        self.event_hub_name = None


class MockLogCategory:
    """Mock log category in diagnostic settings."""

    def __init__(self, category: str, enabled: bool):
        self.category = category
        self.enabled = enabled


class MockMetricCategory:
    """Mock metric category in diagnostic settings."""

    def __init__(self, category: str, enabled: bool):
        self.category = category
        self.enabled = enabled


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
def mock_monitor_client():
    """Create a mock MonitorManagementClient."""
    return MagicMock()


def test_discover_diagnostic_settings_basic(
    mock_config, mock_credential, mock_monitor_client
):
    """Test basic diagnostic settings discovery for Key Vault."""
    # Arrange
    subscription_id = "test-subscription-id"
    parent_resources = [
        {
            "id": "/subscriptions/test-subscription-id/resourceGroups/test-rg/providers/Microsoft.KeyVault/vaults/test-vault",
            "name": "test-vault",
            "type": "Microsoft.KeyVault/vaults",
            "location": "eastus",
            "resource_group": "test-rg",
            "scan_id": "scan-123",
            "tenant_id": "tenant-456",
        }
    ]

    # Mock diagnostic settings response
    mock_setting = MockDiagnosticSetting(
        setting_id="/subscriptions/test-subscription-id/resourceGroups/test-rg/providers/Microsoft.KeyVault/vaults/test-vault/providers/Microsoft.Insights/diagnosticSettings/test-diag",
        name="test-diag",
        logs=[MockLogCategory("AuditEvent", True)],
        metrics=[MockMetricCategory("AllMetrics", True)],
        workspace_id="/subscriptions/test-subscription-id/resourceGroups/test-rg/providers/Microsoft.OperationalInsights/workspaces/test-workspace",
        storage_account_id="/subscriptions/test-subscription-id/resourceGroups/test-rg/providers/Microsoft.Storage/storageAccounts/teststorage",
    )

    mock_monitor_client.diagnostic_settings.list.return_value = [mock_setting]

    def monitor_factory(credential, sub_id):
        return mock_monitor_client

    service = AzureDiscoveryService(
        mock_config,
        mock_credential,
        monitor_client_factory=monitor_factory,
    )

    # Act
    result = asyncio.run(
        service.discover_diagnostic_settings(subscription_id, parent_resources)
    )

    # Assert
    assert len(result) == 1
    assert result[0]["id"] == mock_setting.id
    assert result[0]["name"] == "test-diag"
    assert result[0]["type"] == "Microsoft.Insights/diagnosticSettings"
    assert result[0]["subscription_id"] == subscription_id
    assert result[0]["resource_group"] == "test-rg"
    assert result[0]["scan_id"] == "scan-123"
    assert result[0]["tenant_id"] == "tenant-456"

    # Verify properties
    props = result[0]["properties"]
    assert len(props["logs"]) == 1
    assert props["logs"][0]["category"] == "AuditEvent"
    assert props["logs"][0]["enabled"] is True
    assert len(props["metrics"]) == 1
    assert props["metrics"][0]["category"] == "AllMetrics"
    assert props["metrics"][0]["enabled"] is True
    assert props["workspaceId"] == mock_setting.workspace_id
    assert props["storageAccountId"] == mock_setting.storage_account_id


def test_discover_diagnostic_settings_multiple_resources(
    mock_config, mock_credential, mock_monitor_client
):
    """Test diagnostic settings discovery for multiple resource types."""
    # Arrange
    subscription_id = "test-subscription-id"
    parent_resources = [
        {
            "id": "/subscriptions/test-subscription-id/resourceGroups/test-rg/providers/Microsoft.KeyVault/vaults/vault1",
            "name": "vault1",
            "type": "Microsoft.KeyVault/vaults",
            "location": "eastus",
            "resource_group": "test-rg",
            "scan_id": "scan-123",
            "tenant_id": "tenant-456",
        },
        {
            "id": "/subscriptions/test-subscription-id/resourceGroups/test-rg/providers/Microsoft.Storage/storageAccounts/storage1",
            "name": "storage1",
            "type": "Microsoft.Storage/storageAccounts",
            "location": "eastus",
            "resource_group": "test-rg",
            "scan_id": "scan-123",
            "tenant_id": "tenant-456",
        },
        {
            "id": "/subscriptions/test-subscription-id/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/vm1",
            "name": "vm1",
            "type": "Microsoft.Compute/virtualMachines",
            "location": "eastus",
            "resource_group": "test-rg",
            "scan_id": "scan-123",
            "tenant_id": "tenant-456",
        },
    ]

    # Mock different settings for each resource
    settings_map = {
        parent_resources[0]["id"]: [
            MockDiagnosticSetting(
                setting_id=f"{parent_resources[0]['id']}/providers/Microsoft.Insights/diagnosticSettings/vault-diag",
                name="vault-diag",
                logs=[MockLogCategory("AuditEvent", True)],
            )
        ],
        parent_resources[1]["id"]: [
            MockDiagnosticSetting(
                setting_id=f"{parent_resources[1]['id']}/providers/Microsoft.Insights/diagnosticSettings/storage-diag",
                name="storage-diag",
                metrics=[MockMetricCategory("Transaction", True)],
            )
        ],
        parent_resources[2]["id"]: [],  # VM has no diagnostic settings
    }

    def mock_list(resource_uri):
        return settings_map.get(resource_uri, [])

    mock_monitor_client.diagnostic_settings.list.side_effect = mock_list

    def monitor_factory(credential, sub_id):
        return mock_monitor_client

    service = AzureDiscoveryService(
        mock_config,
        mock_credential,
        monitor_client_factory=monitor_factory,
    )

    # Act
    result = asyncio.run(
        service.discover_diagnostic_settings(subscription_id, parent_resources)
    )

    # Assert
    assert len(result) == 2  # Vault and Storage each have 1 setting
    assert result[0]["name"] == "vault-diag"
    assert result[1]["name"] == "storage-diag"


def test_discover_diagnostic_settings_unsupported_resource_type(
    mock_config, mock_credential, mock_monitor_client
):
    """Test graceful handling of unsupported resource types."""
    # Arrange
    subscription_id = "test-subscription-id"
    parent_resources = [
        {
            "id": "/subscriptions/test-subscription-id/resourceGroups/test-rg/providers/Microsoft.Network/networkInterfaces/nic1",
            "name": "nic1",
            "type": "Microsoft.Network/networkInterfaces",  # Not in supported_types list
            "location": "eastus",
            "resource_group": "test-rg",
        }
    ]

    def monitor_factory(credential, sub_id):
        return mock_monitor_client

    service = AzureDiscoveryService(
        mock_config,
        mock_credential,
        monitor_client_factory=monitor_factory,
    )

    # Act
    result = asyncio.run(
        service.discover_diagnostic_settings(subscription_id, parent_resources)
    )

    # Assert
    assert len(result) == 0  # Unsupported type skipped
    # Verify no API calls were made for unsupported type
    mock_monitor_client.diagnostic_settings.list.assert_not_called()


def test_discover_diagnostic_settings_permission_error(
    mock_config, mock_credential, mock_monitor_client
):
    """Test graceful handling of permission errors."""
    # Arrange
    subscription_id = "test-subscription-id"
    parent_resources = [
        {
            "id": "/subscriptions/test-subscription-id/resourceGroups/test-rg/providers/Microsoft.KeyVault/vaults/test-vault",
            "name": "test-vault",
            "type": "Microsoft.KeyVault/vaults",
            "location": "eastus",
            "resource_group": "test-rg",
        }
    ]

    # Mock permission error
    mock_monitor_client.diagnostic_settings.list.side_effect = Exception(
        "Authorization failed for this request"
    )

    def monitor_factory(credential, sub_id):
        return mock_monitor_client

    service = AzureDiscoveryService(
        mock_config,
        mock_credential,
        monitor_client_factory=monitor_factory,
    )

    # Act
    result = asyncio.run(
        service.discover_diagnostic_settings(subscription_id, parent_resources)
    )

    # Assert
    assert len(result) == 0  # Permission error handled gracefully


def test_discover_diagnostic_settings_resource_not_found(
    mock_config, mock_credential, mock_monitor_client
):
    """Test graceful handling of resource not found errors."""
    # Arrange
    subscription_id = "test-subscription-id"
    parent_resources = [
        {
            "id": "/subscriptions/test-subscription-id/resourceGroups/test-rg/providers/Microsoft.KeyVault/vaults/deleted-vault",
            "name": "deleted-vault",
            "type": "Microsoft.KeyVault/vaults",
            "location": "eastus",
            "resource_group": "test-rg",
        }
    ]

    # Mock not found error
    mock_monitor_client.diagnostic_settings.list.side_effect = Exception(
        "The resource 'deleted-vault' was not found"
    )

    def monitor_factory(credential, sub_id):
        return mock_monitor_client

    service = AzureDiscoveryService(
        mock_config,
        mock_credential,
        monitor_client_factory=monitor_factory,
    )

    # Act
    result = asyncio.run(
        service.discover_diagnostic_settings(subscription_id, parent_resources)
    )

    # Assert
    assert len(result) == 0  # Resource not found handled gracefully


def test_discover_diagnostic_settings_empty_parent_list(
    mock_config, mock_credential, mock_monitor_client
):
    """Test handling of empty parent resource list."""
    # Arrange
    subscription_id = "test-subscription-id"
    parent_resources = []

    def monitor_factory(credential, sub_id):
        return mock_monitor_client

    service = AzureDiscoveryService(
        mock_config,
        mock_credential,
        monitor_client_factory=monitor_factory,
    )

    # Act
    result = asyncio.run(
        service.discover_diagnostic_settings(subscription_id, parent_resources)
    )

    # Assert
    assert len(result) == 0
    mock_monitor_client.diagnostic_settings.list.assert_not_called()


def test_discover_diagnostic_settings_no_settings(
    mock_config, mock_credential, mock_monitor_client
):
    """Test resource with no diagnostic settings configured."""
    # Arrange
    subscription_id = "test-subscription-id"
    parent_resources = [
        {
            "id": "/subscriptions/test-subscription-id/resourceGroups/test-rg/providers/Microsoft.KeyVault/vaults/unconfigured-vault",
            "name": "unconfigured-vault",
            "type": "Microsoft.KeyVault/vaults",
            "location": "eastus",
            "resource_group": "test-rg",
        }
    ]

    # Mock empty settings list
    mock_monitor_client.diagnostic_settings.list.return_value = []

    def monitor_factory(credential, sub_id):
        return mock_monitor_client

    service = AzureDiscoveryService(
        mock_config,
        mock_credential,
        monitor_client_factory=monitor_factory,
    )

    # Act
    result = asyncio.run(
        service.discover_diagnostic_settings(subscription_id, parent_resources)
    )

    # Assert
    assert len(result) == 0  # No settings configured


def test_discover_diagnostic_settings_preserves_scan_metadata(
    mock_config, mock_credential, mock_monitor_client
):
    """Test that diagnostic settings preserve scan_id and tenant_id from parent."""
    # Arrange
    subscription_id = "test-subscription-id"
    parent_resources = [
        {
            "id": "/subscriptions/test-subscription-id/resourceGroups/test-rg/providers/Microsoft.KeyVault/vaults/test-vault",
            "name": "test-vault",
            "type": "Microsoft.KeyVault/vaults",
            "location": "eastus",
            "resource_group": "test-rg",
            "scan_id": "important-scan-id",
            "tenant_id": "important-tenant-id",
        }
    ]

    mock_setting = MockDiagnosticSetting(
        setting_id="/subscriptions/test-subscription-id/resourceGroups/test-rg/providers/Microsoft.KeyVault/vaults/test-vault/providers/Microsoft.Insights/diagnosticSettings/test-diag",
        name="test-diag",
    )

    mock_monitor_client.diagnostic_settings.list.return_value = [mock_setting]

    def monitor_factory(credential, sub_id):
        return mock_monitor_client

    service = AzureDiscoveryService(
        mock_config,
        mock_credential,
        monitor_client_factory=monitor_factory,
    )

    # Act
    result = asyncio.run(
        service.discover_diagnostic_settings(subscription_id, parent_resources)
    )

    # Assert
    assert len(result) == 1
    assert result[0]["scan_id"] == "important-scan-id"
    assert result[0]["tenant_id"] == "important-tenant-id"

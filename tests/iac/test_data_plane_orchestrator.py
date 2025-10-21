"""
Comprehensive tests for DataPlaneOrchestrator.

Tests cover:
- Plugin discovery for each resource type
- Error handling for all error types (permission, not_found, sdk_missing, unexpected)
- Skip filters
- Progress callbacks
- Statistics calculation
- Resource validation
- Edge cases and error conditions
"""

import logging
from unittest.mock import Mock, patch

import pytest

from src.iac.data_plane_orchestrator import (
    DataPlaneOrchestrator,
    DiscoveryError,
    DiscoveryResult,
    DiscoveryStats,
)
from src.iac.plugins import DataPlaneItem

# Test Fixtures


@pytest.fixture
def mock_keyvault_resource():
    """Mock Key Vault resource dictionary."""
    return {
        "id": "/subscriptions/sub-123/resourceGroups/rg-test/providers/Microsoft.KeyVault/vaults/kv-test",
        "type": "Microsoft.KeyVault/vaults",
        "name": "kv-test",
        "properties": {"vaultUri": "https://kv-test.vault.azure.net/"},
    }


@pytest.fixture
def mock_storage_resource():
    """Mock Storage Account resource dictionary."""
    return {
        "id": "/subscriptions/sub-123/resourceGroups/rg-test/providers/Microsoft.Storage/storageAccounts/sttest",
        "type": "Microsoft.Storage/storageAccounts",
        "name": "sttest",
        "properties": {
            "primaryEndpoints": {"blob": "https://sttest.blob.core.windows.net/"}
        },
    }


@pytest.fixture
def mock_sql_resource():
    """Mock SQL Database resource dictionary."""
    return {
        "id": "/subscriptions/sub-123/resourceGroups/rg-test/providers/Microsoft.Sql/servers/sql-test/databases/db-test",
        "type": "Microsoft.Sql/servers/databases",
        "name": "db-test",
        "properties": {"databaseId": "12345"},
    }


@pytest.fixture
def mock_vm_resource():
    """Mock VM resource (no plugin available)."""
    return {
        "id": "/subscriptions/sub-123/resourceGroups/rg-test/providers/Microsoft.Compute/virtualMachines/vm-test",
        "type": "Microsoft.Compute/virtualMachines",
        "name": "vm-test",
        "properties": {},
    }


@pytest.fixture
def mock_data_plane_items():
    """Mock data plane items."""
    return [
        DataPlaneItem(
            name="secret1",
            item_type="secret",
            properties={"contentType": "text/plain"},
            source_resource_id="/subscriptions/sub-123/resourceGroups/rg-test/providers/Microsoft.KeyVault/vaults/kv-test",
        ),
        DataPlaneItem(
            name="secret2",
            item_type="secret",
            properties={"contentType": "application/json"},
            source_resource_id="/subscriptions/sub-123/resourceGroups/rg-test/providers/Microsoft.KeyVault/vaults/kv-test",
        ),
    ]


# Test DiscoveryError


def test_discovery_error_creation():
    """Test DiscoveryError creation and string representation."""
    error = DiscoveryError(
        resource_id="/subscriptions/sub-123/resourceGroups/rg-test/providers/Microsoft.KeyVault/vaults/kv-test",
        resource_type="Microsoft.KeyVault/vaults",
        error_type="permission",
        message="Access denied",
    )

    assert error.resource_id.endswith("kv-test")
    assert error.resource_type == "Microsoft.KeyVault/vaults"
    assert error.error_type == "permission"
    assert error.message == "Access denied"
    assert "[permission]" in str(error)
    assert "Access denied" in str(error)


# Test DiscoveryStats


def test_discovery_stats_initialization():
    """Test DiscoveryStats default initialization."""
    stats = DiscoveryStats()

    assert stats.resources_scanned == 0
    assert stats.resources_with_items == 0
    assert stats.total_items == 0
    assert stats.items_by_type == {}


def test_discovery_stats_add_items(mock_data_plane_items):
    """Test adding items to statistics."""
    stats = DiscoveryStats()

    stats.add_items(mock_data_plane_items)

    assert stats.resources_with_items == 1
    assert stats.total_items == 2
    assert stats.items_by_type["secret"] == 2


def test_discovery_stats_add_items_multiple_types():
    """Test statistics with multiple item types."""
    stats = DiscoveryStats()

    items1 = [
        DataPlaneItem(
            name="secret1",
            item_type="secret",
            properties={},
            source_resource_id="resource1",
        ),
    ]
    items2 = [
        DataPlaneItem(
            name="blob1",
            item_type="blob",
            properties={},
            source_resource_id="resource2",
        ),
        DataPlaneItem(
            name="blob2",
            item_type="blob",
            properties={},
            source_resource_id="resource2",
        ),
    ]

    stats.add_items(items1)
    stats.add_items(items2)

    assert stats.resources_with_items == 2
    assert stats.total_items == 3
    assert stats.items_by_type["secret"] == 1
    assert stats.items_by_type["blob"] == 2


def test_discovery_stats_str_representation(mock_data_plane_items):
    """Test string representation of statistics."""
    stats = DiscoveryStats()
    stats.resources_scanned = 5
    stats.add_items(mock_data_plane_items)

    result = str(stats)

    assert "Resources scanned: 5" in result
    assert "Resources with items: 1" in result
    assert "Total items: 2" in result
    assert "secret: 2" in result


# Test DiscoveryResult


def test_discovery_result_initialization():
    """Test DiscoveryResult default initialization."""
    result = DiscoveryResult()

    assert result.items_by_resource == {}
    assert result.errors == []
    assert result.warnings == []
    assert isinstance(result.stats, DiscoveryStats)


def test_discovery_result_total_items(mock_data_plane_items):
    """Test total items property."""
    result = DiscoveryResult()
    result.items_by_resource["resource1"] = mock_data_plane_items
    result.items_by_resource["resource2"] = [mock_data_plane_items[0]]

    assert result.total_items == 3


def test_discovery_result_has_errors():
    """Test has_errors property."""
    result = DiscoveryResult()
    assert not result.has_errors

    result.errors.append(
        DiscoveryError(
            resource_id="resource1",
            resource_type="type1",
            error_type="permission",
            message="error",
        )
    )
    assert result.has_errors


def test_discovery_result_get_items_by_type(mock_data_plane_items):
    """Test filtering items by type."""
    result = DiscoveryResult()

    items_mixed = [
        *mock_data_plane_items,
        DataPlaneItem(
            name="blob1",
            item_type="blob",
            properties={},
            source_resource_id="resource2",
        ),
    ]
    result.items_by_resource["resource1"] = items_mixed

    secrets = result.get_items_by_type("secret")
    blobs = result.get_items_by_type("blob")

    assert len(secrets) == 2
    assert len(blobs) == 1
    assert all(item.item_type == "secret" for item in secrets)


def test_discovery_result_get_errors_by_type():
    """Test filtering errors by type."""
    result = DiscoveryResult()
    result.errors = [
        DiscoveryError("r1", "type1", "permission", "denied"),
        DiscoveryError("r2", "type2", "sdk_missing", "no sdk"),
        DiscoveryError("r3", "type3", "permission", "denied again"),
    ]

    permission_errors = result.get_errors_by_type("permission")
    sdk_errors = result.get_errors_by_type("sdk_missing")

    assert len(permission_errors) == 2
    assert len(sdk_errors) == 1


# Test DataPlaneOrchestrator Initialization


def test_orchestrator_initialization():
    """Test orchestrator initialization with defaults."""
    orchestrator = DataPlaneOrchestrator()

    assert orchestrator.skip_resource_types == set()
    assert orchestrator.logger is not None


def test_orchestrator_initialization_with_skip_types():
    """Test orchestrator initialization with skip types."""
    skip_types = ["Microsoft.KeyVault/vaults", "Microsoft.Storage/storageAccounts"]
    orchestrator = DataPlaneOrchestrator(skip_resource_types=skip_types)

    assert orchestrator.skip_resource_types == set(skip_types)


def test_orchestrator_initialization_with_logger():
    """Test orchestrator initialization with custom logger."""
    custom_logger = logging.getLogger("test.custom")
    orchestrator = DataPlaneOrchestrator(logger=custom_logger)

    assert orchestrator.logger == custom_logger


# Test Resource Filtering


def test_should_skip_resource(mock_keyvault_resource):
    """Test resource skipping logic."""
    orchestrator = DataPlaneOrchestrator(
        skip_resource_types=["Microsoft.KeyVault/vaults"]
    )

    assert orchestrator._should_skip_resource(mock_keyvault_resource)


def test_should_not_skip_resource(mock_storage_resource):
    """Test resource not skipped."""
    orchestrator = DataPlaneOrchestrator(
        skip_resource_types=["Microsoft.KeyVault/vaults"]
    )

    assert not orchestrator._should_skip_resource(mock_storage_resource)


# Test Progress Tracking


def test_log_progress_with_callback():
    """Test progress logging with callback."""
    orchestrator = DataPlaneOrchestrator()
    callback = Mock()

    orchestrator._log_progress("Processing", 5, 10, callback)

    callback.assert_called_once_with("Processing", 5, 10)


def test_log_progress_without_callback():
    """Test progress logging without callback."""
    orchestrator = DataPlaneOrchestrator()

    # Should not raise
    orchestrator._log_progress("Processing", 5, 10, None)


def test_log_progress_callback_exception():
    """Test progress logging handles callback exceptions."""
    orchestrator = DataPlaneOrchestrator()
    callback = Mock(side_effect=Exception("Callback failed"))

    # Should not raise, just log warning
    orchestrator._log_progress("Processing", 5, 10, callback)


# Test Error Creation


def test_create_error(mock_keyvault_resource):
    """Test error creation helper."""
    orchestrator = DataPlaneOrchestrator()

    error = orchestrator._create_error(
        mock_keyvault_resource, "permission", "Access denied"
    )

    assert error.resource_id == mock_keyvault_resource["id"]
    assert error.resource_type == mock_keyvault_resource["type"]
    assert error.error_type == "permission"
    assert error.message == "Access denied"


# Test Discovery - Success Cases


@pytest.mark.asyncio
async def test_discover_all_with_keyvault(
    mock_keyvault_resource, mock_data_plane_items
):
    """Test successful discovery with Key Vault."""
    orchestrator = DataPlaneOrchestrator()

    # Mock plugin
    mock_plugin = Mock()
    mock_plugin.plugin_name = "KeyVaultPlugin"
    mock_plugin.discover.return_value = mock_data_plane_items

    with patch.object(
        orchestrator._plugin_registry,
        "get_plugin_for_resource",
        return_value=mock_plugin,
    ):
        result = await orchestrator.discover_all([mock_keyvault_resource])

    assert result.stats.resources_scanned == 1
    assert result.stats.resources_with_items == 1
    assert result.stats.total_items == 2
    assert len(result.errors) == 0
    assert mock_keyvault_resource["id"] in result.items_by_resource


@pytest.mark.asyncio
async def test_discover_all_with_multiple_resources(
    mock_keyvault_resource, mock_storage_resource, mock_data_plane_items
):
    """Test discovery with multiple resources."""
    orchestrator = DataPlaneOrchestrator()

    mock_plugin = Mock()
    mock_plugin.plugin_name = "MockPlugin"
    mock_plugin.discover.return_value = mock_data_plane_items

    with patch.object(
        orchestrator._plugin_registry,
        "get_plugin_for_resource",
        return_value=mock_plugin,
    ):
        result = await orchestrator.discover_all(
            [mock_keyvault_resource, mock_storage_resource]
        )

    assert result.stats.resources_scanned == 2
    assert result.stats.resources_with_items == 2
    assert result.stats.total_items == 4
    assert len(result.items_by_resource) == 2


@pytest.mark.asyncio
async def test_discover_all_no_items_found(mock_keyvault_resource):
    """Test discovery when no items are found."""
    orchestrator = DataPlaneOrchestrator()

    mock_plugin = Mock()
    mock_plugin.plugin_name = "KeyVaultPlugin"
    mock_plugin.discover.return_value = []

    with patch.object(
        orchestrator._plugin_registry,
        "get_plugin_for_resource",
        return_value=mock_plugin,
    ):
        result = await orchestrator.discover_all([mock_keyvault_resource])

    assert result.stats.resources_scanned == 1
    assert result.stats.resources_with_items == 0
    assert result.stats.total_items == 0
    assert len(result.errors) == 0


@pytest.mark.asyncio
async def test_discover_all_with_progress_callback(
    mock_keyvault_resource, mock_data_plane_items
):
    """Test discovery with progress callback."""
    orchestrator = DataPlaneOrchestrator()
    callback = Mock()

    mock_plugin = Mock()
    mock_plugin.plugin_name = "KeyVaultPlugin"
    mock_plugin.discover.return_value = mock_data_plane_items

    with patch.object(
        orchestrator._plugin_registry,
        "get_plugin_for_resource",
        return_value=mock_plugin,
    ):
        result = await orchestrator.discover_all([mock_keyvault_resource], callback)

    # Callback should be called for initialization, processing, and completion
    assert callback.call_count >= 2
    assert result.stats.resources_scanned == 1


# Test Discovery - Error Cases


@pytest.mark.asyncio
async def test_discover_all_no_plugin_available(mock_vm_resource):
    """Test discovery when no plugin is available for resource type."""
    orchestrator = DataPlaneOrchestrator()

    with patch.object(
        orchestrator._plugin_registry, "get_plugin_for_resource", return_value=None
    ):
        result = await orchestrator.discover_all([mock_vm_resource])

    assert result.stats.resources_scanned == 1
    assert result.stats.resources_with_items == 0
    assert len(result.errors) == 0


@pytest.mark.asyncio
async def test_discover_all_sdk_missing_error(mock_keyvault_resource):
    """Test discovery with SDK missing error."""
    orchestrator = DataPlaneOrchestrator()

    mock_plugin = Mock()
    mock_plugin.plugin_name = "KeyVaultPlugin"
    mock_plugin.discover.side_effect = ImportError("No module named 'azure.keyvault'")

    with patch.object(
        orchestrator._plugin_registry,
        "get_plugin_for_resource",
        return_value=mock_plugin,
    ):
        result = await orchestrator.discover_all([mock_keyvault_resource])

    assert result.stats.resources_scanned == 1
    assert len(result.errors) == 1
    assert result.errors[0].error_type == "sdk_missing"
    assert "SDK" in result.errors[0].message
    assert len(result.warnings) == 1


@pytest.mark.asyncio
async def test_discover_all_permission_error(mock_keyvault_resource):
    """Test discovery with permission denied error."""
    orchestrator = DataPlaneOrchestrator()

    mock_plugin = Mock()
    mock_plugin.plugin_name = "KeyVaultPlugin"

    # Create mock HTTP error with status_code attribute
    http_error = Exception("Permission denied")
    http_error.status_code = 403
    mock_plugin.discover.side_effect = http_error

    with patch.object(
        orchestrator._plugin_registry,
        "get_plugin_for_resource",
        return_value=mock_plugin,
    ):
        result = await orchestrator.discover_all([mock_keyvault_resource])

    assert result.stats.resources_scanned == 1
    assert len(result.errors) == 1
    assert result.errors[0].error_type == "permission"
    assert "Permission denied" in result.errors[0].message
    assert len(result.warnings) == 1


@pytest.mark.asyncio
async def test_discover_all_not_found_error(mock_keyvault_resource):
    """Test discovery with resource not found error."""
    orchestrator = DataPlaneOrchestrator()

    mock_plugin = Mock()
    mock_plugin.plugin_name = "KeyVaultPlugin"

    # Create mock HTTP error with status_code attribute
    http_error = Exception("Resource not found")
    http_error.status_code = 404
    mock_plugin.discover.side_effect = http_error

    with patch.object(
        orchestrator._plugin_registry,
        "get_plugin_for_resource",
        return_value=mock_plugin,
    ):
        result = await orchestrator.discover_all([mock_keyvault_resource])

    assert result.stats.resources_scanned == 1
    assert len(result.errors) == 1
    assert result.errors[0].error_type == "not_found"
    assert "not found" in result.errors[0].message.lower()
    assert len(result.warnings) == 1


@pytest.mark.asyncio
async def test_discover_all_unexpected_error(mock_keyvault_resource):
    """Test discovery with unexpected error."""
    orchestrator = DataPlaneOrchestrator()

    mock_plugin = Mock()
    mock_plugin.plugin_name = "KeyVaultPlugin"
    mock_plugin.discover.side_effect = RuntimeError("Unexpected failure")

    with patch.object(
        orchestrator._plugin_registry,
        "get_plugin_for_resource",
        return_value=mock_plugin,
    ):
        result = await orchestrator.discover_all([mock_keyvault_resource])

    assert result.stats.resources_scanned == 1
    assert len(result.errors) == 1
    assert result.errors[0].error_type == "unexpected"
    assert "Unexpected failure" in result.errors[0].message


@pytest.mark.asyncio
async def test_discover_all_http_error_other_status(mock_keyvault_resource):
    """Test discovery with HTTP error (status code other than 403/404)."""
    orchestrator = DataPlaneOrchestrator()

    mock_plugin = Mock()
    mock_plugin.plugin_name = "KeyVaultPlugin"

    # Create mock HTTP error with status_code 500
    http_error = Exception("Internal server error")
    http_error.status_code = 500
    mock_plugin.discover.side_effect = http_error

    with patch.object(
        orchestrator._plugin_registry,
        "get_plugin_for_resource",
        return_value=mock_plugin,
    ):
        result = await orchestrator.discover_all([mock_keyvault_resource])

    assert result.stats.resources_scanned == 1
    assert len(result.errors) == 1
    assert result.errors[0].error_type == "unexpected"
    assert "Internal server error" in result.errors[0].message


@pytest.mark.asyncio
async def test_discover_all_plugin_lookup_error(mock_keyvault_resource):
    """Test discovery when plugin lookup fails."""
    orchestrator = DataPlaneOrchestrator()

    with patch.object(
        orchestrator._plugin_registry,
        "get_plugin_for_resource",
        side_effect=Exception("Registry error"),
    ):
        result = await orchestrator.discover_all([mock_keyvault_resource])

    assert result.stats.resources_scanned == 1
    assert len(result.errors) == 1
    assert result.errors[0].error_type == "unexpected"
    assert "Plugin lookup failed" in result.errors[0].message


# Test Skip Filters


@pytest.mark.asyncio
async def test_discover_all_with_skip_filter(
    mock_keyvault_resource, mock_storage_resource
):
    """Test discovery with skip filter."""
    orchestrator = DataPlaneOrchestrator(
        skip_resource_types=["Microsoft.KeyVault/vaults"]
    )

    mock_plugin = Mock()
    mock_plugin.plugin_name = "StoragePlugin"
    mock_plugin.discover.return_value = [
        DataPlaneItem(
            name="blob1",
            item_type="blob",
            properties={},
            source_resource_id="resource1",
        )
    ]

    with patch.object(
        orchestrator._plugin_registry,
        "get_plugin_for_resource",
        return_value=mock_plugin,
    ):
        result = await orchestrator.discover_all(
            [mock_keyvault_resource, mock_storage_resource]
        )

    # Key Vault should be skipped, only storage should be processed
    assert result.stats.resources_scanned == 2
    assert result.stats.resources_with_items == 1
    assert len(result.warnings) == 1
    assert "Skipped" in result.warnings[0]


# Test Mixed Success and Failure


@pytest.mark.asyncio
async def test_discover_all_mixed_results(
    mock_keyvault_resource,
    mock_storage_resource,
    mock_vm_resource,
    mock_data_plane_items,
):
    """Test discovery with mixed success, failure, and no plugin."""
    orchestrator = DataPlaneOrchestrator()

    def mock_get_plugin(resource):
        if resource["type"] == "Microsoft.KeyVault/vaults":
            plugin = Mock()
            plugin.plugin_name = "KeyVaultPlugin"
            plugin.discover.return_value = mock_data_plane_items
            return plugin
        elif resource["type"] == "Microsoft.Storage/storageAccounts":
            plugin = Mock()
            plugin.plugin_name = "StoragePlugin"
            http_error = Exception("Permission denied")
            http_error.status_code = 403
            plugin.discover.side_effect = http_error
            return plugin
        else:
            return None

    with patch.object(
        orchestrator._plugin_registry,
        "get_plugin_for_resource",
        side_effect=mock_get_plugin,
    ):
        result = await orchestrator.discover_all(
            [mock_keyvault_resource, mock_storage_resource, mock_vm_resource]
        )

    assert result.stats.resources_scanned == 3
    assert result.stats.resources_with_items == 1
    assert result.stats.total_items == 2
    assert len(result.errors) == 1
    assert result.errors[0].error_type == "permission"


# Test Statistics Calculation


@pytest.mark.asyncio
async def test_statistics_calculation_multiple_types(
    mock_keyvault_resource, mock_storage_resource
):
    """Test statistics with different item types."""
    orchestrator = DataPlaneOrchestrator()

    def mock_discover(resource):
        if resource["type"] == "Microsoft.KeyVault/vaults":
            return [
                DataPlaneItem(
                    name="secret1",
                    item_type="secret",
                    properties={},
                    source_resource_id=resource["id"],
                ),
                DataPlaneItem(
                    name="secret2",
                    item_type="secret",
                    properties={},
                    source_resource_id=resource["id"],
                ),
            ]
        elif resource["type"] == "Microsoft.Storage/storageAccounts":
            return [
                DataPlaneItem(
                    name="blob1",
                    item_type="blob",
                    properties={},
                    source_resource_id=resource["id"],
                ),
                DataPlaneItem(
                    name="file1",
                    item_type="file",
                    properties={},
                    source_resource_id=resource["id"],
                ),
            ]
        return []

    mock_plugin = Mock()
    mock_plugin.plugin_name = "MockPlugin"
    mock_plugin.discover.side_effect = mock_discover

    with patch.object(
        orchestrator._plugin_registry,
        "get_plugin_for_resource",
        return_value=mock_plugin,
    ):
        result = await orchestrator.discover_all(
            [mock_keyvault_resource, mock_storage_resource]
        )

    assert result.stats.total_items == 4
    assert result.stats.items_by_type["secret"] == 2
    assert result.stats.items_by_type["blob"] == 1
    assert result.stats.items_by_type["file"] == 1


# Test Edge Cases


@pytest.mark.asyncio
async def test_discover_all_empty_resources():
    """Test discovery with empty resource list."""
    orchestrator = DataPlaneOrchestrator()
    result = await orchestrator.discover_all([])

    assert result.stats.resources_scanned == 0
    assert result.stats.total_items == 0
    assert len(result.errors) == 0


@pytest.mark.asyncio
async def test_discover_all_malformed_resource():
    """Test discovery with malformed resource (missing fields)."""
    orchestrator = DataPlaneOrchestrator()
    malformed_resource = {"name": "test"}  # Missing id and type

    with patch.object(
        orchestrator._plugin_registry, "get_plugin_for_resource", return_value=None
    ):
        result = await orchestrator.discover_all([malformed_resource])

    assert result.stats.resources_scanned == 1
    # Should handle gracefully without crashing


@pytest.mark.asyncio
async def test_discover_all_null_resource():
    """Test discovery with None resource."""
    orchestrator = DataPlaneOrchestrator()

    with patch.object(
        orchestrator._plugin_registry, "get_plugin_for_resource", return_value=None
    ):
        result = await orchestrator.discover_all([None])

    assert result.stats.resources_scanned == 1
    # Should handle gracefully


# Test Result Methods


def test_discovery_result_total_errors():
    """Test total_errors property."""
    result = DiscoveryResult()
    result.errors = [
        DiscoveryError("r1", "t1", "permission", "e1"),
        DiscoveryError("r2", "t2", "sdk_missing", "e2"),
    ]

    assert result.total_errors == 2


def test_discovery_result_get_items_by_type_empty():
    """Test get_items_by_type with no matches."""
    result = DiscoveryResult()
    result.items_by_resource["r1"] = [
        DataPlaneItem(
            name="secret1", item_type="secret", properties={}, source_resource_id="r1"
        )
    ]

    blobs = result.get_items_by_type("blob")
    assert len(blobs) == 0


def test_discovery_result_get_errors_by_type_empty():
    """Test get_errors_by_type with no matches."""
    result = DiscoveryResult()
    result.errors = [DiscoveryError("r1", "t1", "permission", "e1")]

    sdk_errors = result.get_errors_by_type("sdk_missing")
    assert len(sdk_errors) == 0

"""
Comprehensive unit tests for Virtual Machine Data Plane Plugin.

These tests mock the Azure SDK to verify plugin behavior without
requiring actual Azure resources.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from typing import Any, Dict, List

from src.iac.data_plane_plugins.vm_plugin import VirtualMachinePlugin
from src.iac.plugins.base_plugin import (
    DataPlaneItem,
    ReplicationMode,
    ReplicationResult,
    Permission,
)


# ============ FIXTURES ============


@pytest.fixture
def vm_resource() -> Dict[str, Any]:
    """Sample VM resource for testing."""
    return {
        "id": "/subscriptions/test-sub-123/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/test-vm",
        "type": "Microsoft.Compute/virtualMachines",
        "name": "test-vm",
        "location": "eastus",
        "properties": {
            "vmId": "vm-123",
            "hardwareProfile": {"vmSize": "Standard_D2s_v3"},
        },
    }


@pytest.fixture
def vm_plugin():
    """Create VM plugin instance for testing."""
    return VirtualMachinePlugin()


@pytest.fixture
def mock_extension():
    """Mock VM extension object."""
    ext = Mock()
    ext.name = "CustomScriptExtension"
    ext.publisher = "Microsoft.Compute"
    ext.type_handler_version = "1.10"
    ext.auto_upgrade_minor_version = True
    ext.provisioning_state = "Succeeded"
    ext.id = "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/test-vm/extensions/CustomScriptExtension"
    ext.location = "eastus"
    ext.tags = {"env": "test"}

    # Mock as_dict method
    ext.as_dict = Mock(
        return_value={
            "name": "CustomScriptExtension",
            "publisher": "Microsoft.Compute",
            "type_handler_version": "1.10",
            "settings": {"commandToExecute": "echo hello"},
            "protected_settings": None,
        }
    )

    return ext


@pytest.fixture
def mock_data_disk():
    """Mock data disk object."""
    disk = Mock()
    disk.name = "test-vm-data-disk-0"
    disk.lun = 0
    disk.disk_size_gb = 128
    disk.caching = "ReadWrite"
    disk.create_option = "Attach"
    disk.write_accelerator_enabled = False
    disk.to_be_detached = False
    disk.managed_disk = Mock()
    disk.managed_disk.id = "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Compute/disks/test-vm-data-disk-0"

    return disk


# ============ BASIC PLUGIN TESTS ============


def test_plugin_initialization():
    """Test plugin initializes correctly."""
    plugin = VirtualMachinePlugin()

    assert plugin.supported_resource_type == "Microsoft.Compute/virtualMachines"
    assert plugin.plugin_name == "VirtualMachinePlugin"
    assert plugin.supports_mode(ReplicationMode.TEMPLATE)
    assert plugin.supports_mode(ReplicationMode.REPLICATION)


def test_validate_resource_success(vm_plugin, vm_resource):
    """Test resource validation succeeds for valid VM resource."""
    assert vm_plugin.validate_resource(vm_resource) is True


def test_validate_resource_wrong_type(vm_plugin):
    """Test resource validation fails for wrong resource type."""
    invalid_resource = {
        "id": "/subscriptions/test/resourceGroups/rg/providers/Microsoft.Storage/storageAccounts/sa",
        "type": "Microsoft.Storage/storageAccounts",
        "name": "test-sa",
    }

    assert vm_plugin.validate_resource(invalid_resource) is False


def test_validate_resource_missing_id(vm_plugin):
    """Test resource validation fails when ID is missing."""
    invalid_resource = {
        "type": "Microsoft.Compute/virtualMachines",
        "name": "test-vm",
    }

    assert vm_plugin.validate_resource(invalid_resource) is False


def test_validate_resource_none(vm_plugin):
    """Test resource validation fails for None."""
    assert vm_plugin.validate_resource(None) is False


# ============ DISCOVERY TESTS ============


@patch("azure.mgmt.compute.ComputeManagementClient")
@patch("azure.identity.DefaultAzureCredential")
def test_discover_success(
    mock_credential, mock_compute_client, vm_plugin, vm_resource, mock_extension, mock_data_disk
):
    """Test successful discovery of VM extensions and data disks."""
    # Setup mocks
    mock_cred_instance = Mock()
    mock_credential.return_value = mock_cred_instance

    mock_client_instance = Mock()
    mock_compute_client.return_value = mock_client_instance

    # Mock extension listing
    mock_client_instance.virtual_machine_extensions.list.return_value = [mock_extension]

    # Mock VM details with data disks
    mock_vm_details = Mock()
    mock_vm_details.storage_profile = Mock()
    mock_vm_details.storage_profile.data_disks = [mock_data_disk]
    mock_client_instance.virtual_machines.get.return_value = mock_vm_details

    # Execute discovery
    items = vm_plugin.discover(vm_resource)

    # Assertions
    assert len(items) == 2  # 1 extension + 1 data disk

    # Check extension item
    ext_items = [item for item in items if item.item_type == "vm_extension"]
    assert len(ext_items) == 1
    ext_item = ext_items[0]
    assert ext_item.name == "CustomScriptExtension"
    assert ext_item.properties["publisher"] == "Microsoft.Compute"
    assert ext_item.properties["type_handler_version"] == "1.10"
    assert ext_item.metadata["tags"]["env"] == "test"

    # Check data disk item
    disk_items = [item for item in items if item.item_type == "data_disk"]
    assert len(disk_items) == 1
    disk_item = disk_items[0]
    assert disk_item.name == "test-vm-data-disk-0"
    assert disk_item.properties["lun"] == 0
    assert disk_item.properties["disk_size_gb"] == 128
    assert disk_item.size_bytes == 128 * 1024 * 1024 * 1024


@patch("azure.mgmt.compute.ComputeManagementClient")
@patch("azure.identity.DefaultAzureCredential")
def test_discover_no_extensions(
    mock_credential, mock_compute_client, vm_plugin, vm_resource
):
    """Test discovery when VM has no extensions."""
    # Setup mocks
    mock_cred_instance = Mock()
    mock_credential.return_value = mock_cred_instance

    mock_client_instance = Mock()
    mock_compute_client.return_value = mock_client_instance

    # Mock empty extension list
    mock_client_instance.virtual_machine_extensions.list.return_value = []

    # Mock VM with no data disks
    mock_vm_details = Mock()
    mock_vm_details.storage_profile = Mock()
    mock_vm_details.storage_profile.data_disks = []
    mock_client_instance.virtual_machines.get.return_value = mock_vm_details

    # Execute discovery
    items = vm_plugin.discover(vm_resource)

    # Assertions
    assert len(items) == 0


@patch("azure.mgmt.compute.ComputeManagementClient")
@patch("azure.identity.DefaultAzureCredential")
def test_discover_with_azure_error(
    mock_credential, mock_compute_client, vm_plugin, vm_resource
):
    """Test discovery handles Azure SDK errors gracefully."""
    from azure.core.exceptions import HttpResponseError

    # Setup mocks
    mock_cred_instance = Mock()
    mock_credential.return_value = mock_cred_instance

    mock_client_instance = Mock()
    mock_compute_client.return_value = mock_client_instance

    # Mock Azure error during extension listing
    mock_client_instance.virtual_machine_extensions.list.side_effect = HttpResponseError(
        "VM not found"
    )

    # Mock successful data disk retrieval
    mock_vm_details = Mock()
    mock_vm_details.storage_profile = Mock()
    mock_vm_details.storage_profile.data_disks = []
    mock_client_instance.virtual_machines.get.return_value = mock_vm_details

    # Execute discovery (should not raise exception)
    items = vm_plugin.discover(vm_resource)

    # Should return empty list but not crash
    assert items == []


def test_discover_invalid_resource(vm_plugin):
    """Test discovery raises ValueError for invalid resource."""
    invalid_resource = {"type": "Microsoft.Storage/storageAccounts", "name": "test"}

    with pytest.raises(ValueError, match="Invalid resource"):
        vm_plugin.discover(invalid_resource)


def test_discover_with_credential_provider(vm_plugin, vm_resource):
    """Test discovery uses credential provider when available."""
    # Create mock credential provider
    mock_cred_provider = Mock()
    mock_custom_cred = Mock()
    mock_cred_provider.get_credential.return_value = mock_custom_cred

    # Set credential provider on plugin
    vm_plugin.credential_provider = mock_cred_provider

    # Mock compute client
    with patch("azure.identity.DefaultAzureCredential") as mock_default:
        mock_client = Mock()
        mock_client.virtual_machine_extensions.list.return_value = []

        # Mock VM details properly
        mock_vm_details = Mock()
        mock_vm_details.storage_profile = Mock()
        mock_vm_details.storage_profile.data_disks = []
        mock_client.virtual_machines.get.return_value = mock_vm_details

        with patch(
            "azure.mgmt.compute.ComputeManagementClient",
            return_value=mock_client,
        ):
            vm_plugin.discover(vm_resource)

            # Verify custom credential was used
            mock_cred_provider.get_credential.assert_called_once()
            # DefaultAzureCredential should NOT be called
            mock_default.assert_not_called()


# ============ CODE GENERATION TESTS ============


def test_generate_replication_code_empty():
    """Test code generation with no items."""
    plugin = VirtualMachinePlugin()
    code = plugin.generate_replication_code([])

    assert "# No VM data plane items to replicate" in code


def test_generate_replication_code_extensions():
    """Test code generation for VM extensions."""
    plugin = VirtualMachinePlugin()

    items = [
        DataPlaneItem(
            name="CustomScriptExtension",
            item_type="vm_extension",
            properties={
                "publisher": "Microsoft.Compute",
                "type": "CustomScriptExtension",
                "type_handler_version": "1.10",
                "auto_upgrade_minor_version": True,
                "settings": {"commandToExecute": "echo hello"},
            },
            source_resource_id="/subscriptions/test/resourceGroups/rg/providers/Microsoft.Compute/virtualMachines/vm1",
            metadata={"has_protected_settings": False, "tags": {"env": "prod"}},
        )
    ]

    code = plugin.generate_replication_code(items)

    # Check for key Terraform elements
    assert 'resource "azurerm_virtual_machine_extension"' in code
    assert 'name                 = "CustomScriptExtension"' in code
    assert 'publisher            = "Microsoft.Compute"' in code
    assert 'type_handler_version = "1.10"' in code
    assert "auto_upgrade_minor_version = true" in code
    assert "settings = jsonencode({" in code
    assert '"env" = "prod"' in code


def test_generate_replication_code_with_protected_settings():
    """Test code generation includes comment for protected settings."""
    plugin = VirtualMachinePlugin()

    items = [
        DataPlaneItem(
            name="CustomScriptExtension",
            item_type="vm_extension",
            properties={
                "publisher": "Microsoft.Compute",
                "type": "CustomScriptExtension",
                "type_handler_version": "1.10",
                "auto_upgrade_minor_version": True,
                "settings": {},
            },
            source_resource_id="/subscriptions/test/resourceGroups/rg/providers/Microsoft.Compute/virtualMachines/vm1",
            metadata={"has_protected_settings": True, "tags": {}},
        )
    ]

    code = plugin.generate_replication_code(items)

    # Should include comment about protected settings
    assert "# SECURITY: Protected settings not included" in code
    assert "protected_settings" in code


def test_generate_replication_code_data_disks():
    """Test code generation for data disks."""
    plugin = VirtualMachinePlugin()

    items = [
        DataPlaneItem(
            name="test-vm-data-disk-0",
            item_type="data_disk",
            properties={"lun": 0, "disk_size_gb": 256, "caching": "ReadWrite"},
            source_resource_id="/subscriptions/test/resourceGroups/rg/providers/Microsoft.Compute/virtualMachines/vm1",
            metadata={},
        )
    ]

    code = plugin.generate_replication_code(items)

    # Check for managed disk resource
    assert 'resource "azurerm_managed_disk"' in code
    assert 'name                 = "test-vm-data-disk-0"' in code
    assert "disk_size_gb         = 256" in code

    # Check for disk attachment resource
    assert 'resource "azurerm_virtual_machine_data_disk_attachment"' in code
    assert "lun                = 0" in code
    assert 'caching            = "ReadWrite"' in code


def test_generate_replication_code_unsupported_format():
    """Test code generation raises error for unsupported format."""
    plugin = VirtualMachinePlugin()
    items = [
        DataPlaneItem(
            name="test", item_type="vm_extension", properties={}, source_resource_id="/test"
        )
    ]

    with pytest.raises(ValueError, match="not supported"):
        plugin.generate_replication_code(items, output_format="bicep")


# ============ REPLICATION TESTS ============


@patch("azure.mgmt.compute.ComputeManagementClient")
@patch("azure.identity.DefaultAzureCredential")
def test_replicate_with_mode_template(
    mock_credential, mock_compute_client, vm_plugin, vm_resource, mock_extension
):
    """Test replication in template mode (discovery only)."""
    # Setup mocks
    mock_cred_instance = Mock()
    mock_credential.return_value = mock_cred_instance

    mock_client_instance = Mock()
    mock_compute_client.return_value = mock_client_instance

    # Mock discovery
    mock_client_instance.virtual_machine_extensions.list.return_value = [mock_extension]
    mock_vm_details = Mock()
    mock_vm_details.storage_profile = Mock()
    mock_vm_details.storage_profile.data_disks = []
    mock_client_instance.virtual_machines.get.return_value = mock_vm_details

    # Execute replication in template mode
    target_vm = vm_resource.copy()
    target_vm["name"] = "target-vm"
    target_vm["id"] = target_vm["id"].replace("test-vm", "target-vm")

    result = vm_plugin.replicate_with_mode(vm_resource, target_vm, ReplicationMode.TEMPLATE)

    # Assertions
    assert result.success is True
    assert result.items_discovered == 1
    assert result.items_replicated == 1  # Template mode logs replication intent
    assert len(result.errors) == 0


@patch("azure.mgmt.compute.ComputeManagementClient")
@patch("azure.identity.DefaultAzureCredential")
def test_replicate_with_mode_replication(
    mock_credential, mock_compute_client, vm_plugin, vm_resource, mock_extension
):
    """Test replication in full replication mode."""
    # Setup mocks
    mock_cred_instance = Mock()
    mock_credential.return_value = mock_cred_instance

    mock_client_instance = Mock()
    mock_compute_client.return_value = mock_client_instance

    # Mock discovery
    mock_client_instance.virtual_machine_extensions.list.return_value = [mock_extension]
    mock_vm_details = Mock()
    mock_vm_details.storage_profile = Mock()
    mock_vm_details.storage_profile.data_disks = []
    mock_client_instance.virtual_machines.get.return_value = mock_vm_details

    # Mock extension creation
    mock_poller = Mock()
    mock_poller.result.return_value = None
    mock_client_instance.virtual_machine_extensions.begin_create_or_update.return_value = (
        mock_poller
    )

    # Execute replication in full mode
    target_vm = vm_resource.copy()
    target_vm["name"] = "target-vm"
    target_vm["id"] = target_vm["id"].replace("test-vm", "target-vm")

    result = vm_plugin.replicate_with_mode(
        vm_resource, target_vm, ReplicationMode.REPLICATION
    )

    # Assertions
    assert result.success is True
    assert result.items_discovered == 1
    assert result.items_replicated == 1
    assert len(result.errors) == 0

    # Verify Azure SDK was called to create extension
    mock_client_instance.virtual_machine_extensions.begin_create_or_update.assert_called_once()


def test_replicate_invalid_source(vm_plugin):
    """Test replication raises ValueError for invalid source resource."""
    invalid_source = {"type": "Microsoft.Storage/storageAccounts", "name": "test"}
    valid_target = {
        "id": "/subscriptions/test/resourceGroups/rg/providers/Microsoft.Compute/virtualMachines/vm",
        "type": "Microsoft.Compute/virtualMachines",
        "name": "vm",
    }

    with pytest.raises(ValueError, match="Invalid source resource"):
        vm_plugin.replicate_with_mode(
            invalid_source, valid_target, ReplicationMode.TEMPLATE
        )


def test_replicate_invalid_target(vm_plugin, vm_resource):
    """Test replication raises ValueError for invalid target resource."""
    invalid_target = {"type": "Microsoft.Storage/storageAccounts", "name": "test"}

    with pytest.raises(ValueError, match="Invalid target resource"):
        vm_plugin.replicate_with_mode(
            vm_resource, invalid_target, ReplicationMode.TEMPLATE
        )


@patch("azure.mgmt.compute.ComputeManagementClient")
@patch("azure.identity.DefaultAzureCredential")
def test_replicate_with_progress_reporter(
    mock_credential, mock_compute_client, vm_plugin, vm_resource, mock_extension
):
    """Test replication reports progress correctly."""
    # Setup mocks
    mock_cred_instance = Mock()
    mock_credential.return_value = mock_cred_instance

    mock_client_instance = Mock()
    mock_compute_client.return_value = mock_client_instance

    # Mock discovery
    mock_client_instance.virtual_machine_extensions.list.return_value = [mock_extension]
    mock_vm_details = Mock()
    mock_vm_details.storage_profile = Mock()
    mock_vm_details.storage_profile.data_disks = []
    mock_client_instance.virtual_machines.get.return_value = mock_vm_details

    # Create mock progress reporter
    mock_progress = Mock()
    vm_plugin.progress_reporter = mock_progress

    # Execute replication
    target_vm = vm_resource.copy()
    target_vm["name"] = "target-vm"
    target_vm["id"] = target_vm["id"].replace("test-vm", "target-vm")

    result = vm_plugin.replicate_with_mode(vm_resource, target_vm, ReplicationMode.TEMPLATE)

    # Verify progress reporting
    assert mock_progress.report_replication_progress.called
    assert mock_progress.report_completion.called
    mock_progress.report_completion.assert_called_once_with(result)


# ============ PERMISSION TESTS ============


def test_get_required_permissions_template_mode():
    """Test required permissions for template mode."""
    plugin = VirtualMachinePlugin()
    perms = plugin.get_required_permissions(ReplicationMode.TEMPLATE)

    assert len(perms) > 0
    assert any("Microsoft.Compute/virtualMachines/read" in p.actions for p in perms)
    assert any("Microsoft.Compute/virtualMachines/extensions/read" in p.actions for p in perms)


def test_get_required_permissions_replication_mode():
    """Test required permissions for replication mode."""
    plugin = VirtualMachinePlugin()
    perms = plugin.get_required_permissions(ReplicationMode.REPLICATION)

    assert len(perms) > 0
    assert any("Microsoft.Compute/virtualMachines/read" in p.actions for p in perms)
    assert any("Microsoft.Compute/virtualMachines/extensions/write" in p.actions for p in perms)
    assert any("Microsoft.Compute/snapshots/write" in p.actions for p in perms)


def test_replication_mode_has_more_permissions():
    """Test that replication mode requires more permissions than template mode."""
    plugin = VirtualMachinePlugin()

    template_perms = plugin.get_required_permissions(ReplicationMode.TEMPLATE)
    replication_perms = plugin.get_required_permissions(ReplicationMode.REPLICATION)

    # Replication mode should have more actions
    template_actions = sum(len(p.actions) for p in template_perms)
    replication_actions = sum(len(p.actions) for p in replication_perms)

    assert replication_actions > template_actions


# ============ UTILITY FUNCTION TESTS ============


def test_parse_resource_id_success():
    """Test parsing valid Azure resource ID."""
    plugin = VirtualMachinePlugin()

    resource_id = (
        "/subscriptions/abc-123/resourceGroups/my-rg/"
        "providers/Microsoft.Compute/virtualMachines/my-vm"
    )

    sub_id, rg = plugin._parse_resource_id(resource_id)

    assert sub_id == "abc-123"
    assert rg == "my-rg"


def test_parse_resource_id_invalid():
    """Test parsing invalid resource ID returns None."""
    plugin = VirtualMachinePlugin()

    resource_id = "invalid-id"
    sub_id, rg = plugin._parse_resource_id(resource_id)

    assert sub_id is None
    assert rg is None


def test_sanitize_name():
    """Test name sanitization for Terraform."""
    plugin = VirtualMachinePlugin()

    assert plugin._sanitize_name("my-extension") == "my_extension"
    assert plugin._sanitize_name("extension.v1.0") == "extension_v1_0"
    assert plugin._sanitize_name("Extension With Spaces") == "extension_with_spaces"
    assert plugin._sanitize_name("123-starts-with-number") == "vm_123_starts_with_number"


# ============ TIME ESTIMATION TESTS ============


def test_estimate_operation_time_template_mode():
    """Test time estimation for template mode (should be zero)."""
    plugin = VirtualMachinePlugin()
    items = [
        DataPlaneItem(
            name="ext1", item_type="vm_extension", properties={}, source_resource_id="/test"
        )
        for _ in range(5)
    ]

    time_est = plugin.estimate_operation_time(items, ReplicationMode.TEMPLATE)
    assert time_est == 0.0


def test_estimate_operation_time_replication_mode():
    """Test time estimation for replication mode."""
    plugin = VirtualMachinePlugin()

    # 2 extensions + 1 data disk (100GB)
    items = [
        DataPlaneItem(
            name="ext1", item_type="vm_extension", properties={}, source_resource_id="/test"
        ),
        DataPlaneItem(
            name="ext2", item_type="vm_extension", properties={}, source_resource_id="/test"
        ),
        DataPlaneItem(
            name="disk1",
            item_type="data_disk",
            properties={"disk_size_gb": 100},
            source_resource_id="/test",
        ),
    ]

    time_est = plugin.estimate_operation_time(items, ReplicationMode.REPLICATION)

    # Should account for: 2 extensions * 30s + 100GB * 300s = 60 + 30000 = 30060s
    assert time_est == pytest.approx(30060.0)


def test_estimate_operation_time_no_items():
    """Test time estimation with no items."""
    plugin = VirtualMachinePlugin()
    time_est = plugin.estimate_operation_time([], ReplicationMode.REPLICATION)
    assert time_est == 0.0


# ============ EDGE CASES ============


@patch("azure.mgmt.compute.ComputeManagementClient")
@patch("azure.identity.DefaultAzureCredential")
def test_discover_with_malformed_resource_id(mock_credential, mock_compute_client, vm_plugin):
    """Test discovery handles malformed resource ID gracefully."""
    malformed_resource = {
        "id": "not-a-valid-resource-id",
        "type": "Microsoft.Compute/virtualMachines",
        "name": "test-vm",
    }

    # Discovery should return empty list but not crash
    items = vm_plugin.discover(malformed_resource)
    assert items == []


@patch("azure.mgmt.compute.ComputeManagementClient")
@patch("azure.identity.DefaultAzureCredential")
def test_replicate_with_no_discovered_items(
    mock_credential, mock_compute_client, vm_plugin, vm_resource
):
    """Test replication when no items are discovered."""
    # Setup mocks
    mock_cred_instance = Mock()
    mock_credential.return_value = mock_cred_instance

    mock_client_instance = Mock()
    mock_compute_client.return_value = mock_client_instance

    # Mock empty discovery
    mock_client_instance.virtual_machine_extensions.list.return_value = []
    mock_vm_details = Mock()
    mock_vm_details.storage_profile = Mock()
    mock_vm_details.storage_profile.data_disks = []
    mock_client_instance.virtual_machines.get.return_value = mock_vm_details

    # Execute replication
    target_vm = vm_resource.copy()
    result = vm_plugin.replicate_with_mode(vm_resource, target_vm, ReplicationMode.TEMPLATE)

    # Should succeed with warning
    assert result.success is True
    assert result.items_discovered == 0
    assert len(result.warnings) > 0


# ============ INTEGRATION WITH BASE CLASS ============


def test_supports_output_format():
    """Test plugin only supports Terraform format."""
    plugin = VirtualMachinePlugin()

    assert plugin.supports_output_format("terraform") is True
    assert plugin.supports_output_format("Terraform") is True
    assert plugin.supports_output_format("bicep") is False
    assert plugin.supports_output_format("arm") is False


def test_plugin_name():
    """Test plugin name property."""
    plugin = VirtualMachinePlugin()
    assert plugin.plugin_name == "VirtualMachinePlugin"


def test_supports_both_modes():
    """Test plugin supports both replication modes."""
    plugin = VirtualMachinePlugin()

    assert plugin.supports_mode(ReplicationMode.TEMPLATE) is True
    assert plugin.supports_mode(ReplicationMode.REPLICATION) is True

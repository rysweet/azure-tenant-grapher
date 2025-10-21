# Data Plane Plugins

## Overview

Data plane plugins extend IaC generation by handling Azure resource-specific data that isn't part of the Azure Resource Manager control plane. This directory contains plugins for replicating data plane items during tenant migration.

## Available Plugins

1. [Virtual Machine Plugin](#virtual-machine-data-plane-plugin) - VM extensions and data disks
2. [Container Registry Plugin](#container-registry-data-plane-plugin) - Container images and repositories

---

# Virtual Machine Data Plane Plugin

## Overview

The Virtual Machine Data Plane Plugin enables replication of VM-specific data plane elements including:
- VM Extensions (CustomScriptExtension, AADLogin, etc.)
- Custom script data
- Data disk configurations and snapshots

## Features

### Two Replication Modes

#### 1. Template Mode
- Replicates extension configurations without data
- Creates empty data disks with correct specifications
- Fast and safe for testing environments
- **Required Permission**: Virtual Machine Contributor

#### 2. Replication Mode
- Full data copy including disk snapshots
- Copies custom scripts to target storage
- Replicates extension configurations with data
- **Required Permissions**: Virtual Machine Contributor + Storage Account Contributor

## Usage

### Basic Usage

```python
from src.iac.data_plane_plugins.vm_plugin import VirtualMachinePlugin
from src.iac.plugins.base_plugin import ReplicationMode

# Initialize plugin
plugin = VirtualMachinePlugin()

# Define VM resource
vm_resource = {
    "id": "/subscriptions/xxx/resourceGroups/rg/providers/Microsoft.Compute/virtualMachines/my-vm",
    "type": "Microsoft.Compute/virtualMachines",
    "name": "my-vm",
    "location": "eastus"
}

# Discover data plane items
items = plugin.discover(vm_resource)
print(f"Found {len(items)} data plane items")

# Generate Terraform code
terraform_code = plugin.generate_replication_code(items)
print(terraform_code)

# Replicate to target (template mode)
target_vm = {
    "id": "/subscriptions/yyy/resourceGroups/rg/providers/Microsoft.Compute/virtualMachines/target-vm",
    "type": "Microsoft.Compute/virtualMachines",
    "name": "target-vm",
    "location": "westus"
}

result = plugin.replicate_with_mode(vm_resource, target_vm, ReplicationMode.TEMPLATE)
print(f"Success: {result.success}, Replicated: {result.items_replicated}")
```

### With Credential Provider

```python
from azure.identity import DefaultAzureCredential

# Create credential provider mock
class CredentialProvider:
    def get_credential(self):
        return DefaultAzureCredential()

# Initialize plugin with credential provider
plugin = VirtualMachinePlugin()
plugin.credential_provider = CredentialProvider()

# Now discovery and replication will use provided credentials
items = plugin.discover(vm_resource)
```

### With Progress Reporter

```python
# Create progress reporter
class ProgressReporter:
    def report_discovery(self, resource_id, item_count):
        print(f"Discovered {item_count} items in {resource_id}")

    def report_replication_progress(self, item_name, progress_pct):
        print(f"Replicating {item_name}: {progress_pct:.0f}%")

    def report_completion(self, result):
        print(f"Completed: {result.items_replicated}/{result.items_discovered} items")

# Initialize plugin with progress reporter
plugin = VirtualMachinePlugin()
plugin.progress_reporter = ProgressReporter()

# Progress will be reported during operations
result = plugin.replicate_with_mode(vm_resource, target_vm, ReplicationMode.REPLICATION)
```

## Data Plane Items

### VM Extensions

The plugin discovers and replicates:
- Extension name and version
- Publisher information
- Public settings (JSON)
- Auto-upgrade configuration
- Tags and metadata

**Note**: Protected settings (encrypted) are NOT replicated for security reasons.

### Data Disks

The plugin handles:
- Disk size and SKU
- LUN (Logical Unit Number)
- Caching configuration
- Managed disk references

In **template mode**, only metadata is replicated.
In **replication mode**, disk snapshots can be created (requires additional permissions).

## Generated Terraform Code

### Extension Example

```hcl
resource "azurerm_virtual_machine_extension" "customscriptextension" {
  name                 = "CustomScriptExtension"
  virtual_machine_id   = azurerm_virtual_machine.REPLACE_ME.id

  publisher            = "Microsoft.Compute"
  type                 = "CustomScriptExtension"
  type_handler_version = "1.10"

  auto_upgrade_minor_version = true

  settings = jsonencode({
    commandToExecute = "echo hello"
  })

  # SECURITY: Protected settings not included
  # Configure manually or via variable:
  # protected_settings = var.vm_extension_customscriptextension_protected

  tags = {
    "env" = "prod"
  }
}
```

### Data Disk Example

```hcl
resource "azurerm_managed_disk" "test_vm_data_disk_0" {
  name                 = "test-vm-data-disk-0"
  location             = azurerm_resource_group.REPLACE_ME.location
  resource_group_name  = azurerm_resource_group.REPLACE_ME.name

  storage_account_type = "Premium_LRS"
  create_option        = "Empty"
  disk_size_gb         = 256
}

resource "azurerm_virtual_machine_data_disk_attachment" "test_vm_data_disk_0_attach" {
  managed_disk_id    = azurerm_managed_disk.test_vm_data_disk_0.id
  virtual_machine_id = azurerm_virtual_machine.REPLACE_ME.id
  lun                = 0
  caching            = "ReadWrite"
}
```

## Permissions

### Template Mode
- `Microsoft.Compute/virtualMachines/read`
- `Microsoft.Compute/virtualMachines/extensions/read`

### Replication Mode
- `Microsoft.Compute/virtualMachines/read`
- `Microsoft.Compute/virtualMachines/extensions/read`
- `Microsoft.Compute/virtualMachines/extensions/write`
- `Microsoft.Compute/disks/read`
- `Microsoft.Compute/snapshots/write`

## Time Estimation

The plugin provides operation time estimates:

```python
items = plugin.discover(vm_resource)

# Template mode: instant
time_template = plugin.estimate_operation_time(items, ReplicationMode.TEMPLATE)
print(f"Template mode: {time_template}s")  # 0.0

# Replication mode: varies by disk size
time_replication = plugin.estimate_operation_time(items, ReplicationMode.REPLICATION)
print(f"Replication mode: {time_replication}s")  # ~30s per extension + 300s per GB
```

## Error Handling

The plugin handles common errors gracefully:

```python
result = plugin.replicate_with_mode(vm_resource, target_vm, ReplicationMode.REPLICATION)

if not result.success:
    print(f"Errors: {result.errors}")
    for error in result.errors:
        print(f"  - {error}")

if result.warnings:
    print(f"Warnings: {result.warnings}")
    for warning in result.warnings:
        print(f"  - {warning}")
```

## Testing

The plugin includes comprehensive unit tests:

```bash
# Run all VM plugin tests
uv run pytest tests/iac/data_plane_plugins/test_vm_plugin.py -v

# Run specific test
uv run pytest tests/iac/data_plane_plugins/test_vm_plugin.py::test_discover_success -v

# Run with coverage
uv run pytest tests/iac/data_plane_plugins/test_vm_plugin.py --cov=src/iac/data_plane_plugins/vm_plugin
```

**Test Coverage**: 34 comprehensive unit tests covering:
- Plugin initialization
- Resource validation
- Extension discovery
- Data disk discovery
- Code generation
- Template mode replication
- Full mode replication
- Error handling
- Permission checking
- Utility functions

## Architecture

The VM plugin follows the Data Plane Plugin Architecture:

1. **Discovery**: Enumerates VM extensions and data disks using Azure SDK
2. **Code Generation**: Creates Terraform resources for replication
3. **Replication**: Executes actual data copying based on mode
4. **Progress Reporting**: Reports status for long-running operations
5. **Permission Checking**: Verifies required RBAC permissions

## Dependencies

```python
# Azure SDK
from azure.identity import DefaultAzureCredential
from azure.mgmt.compute import ComputeManagementClient
from azure.core.exceptions import AzureError, HttpResponseError

# Base plugin
from ..plugins.base_plugin import (
    DataPlaneItem,
    DataPlanePlugin,
    Permission,
    ReplicationMode,
    ReplicationResult,
)
```

## Limitations

1. **Protected Settings**: Not replicated for security reasons
2. **Disk Content**: Full disk replication requires manual snapshot process
3. **Extension State**: Provisioning state may differ after replication
4. **Custom Scripts**: Script files must be accessible in target environment

## Best Practices

1. **Test First**: Always use template mode for testing
2. **Verify Permissions**: Check required permissions before replication
3. **Monitor Progress**: Use progress reporter for large operations
4. **Validate Results**: Verify VM functionality after replication
5. **Handle Secrets**: Manually configure protected settings after deployment

## Related Documentation

- [Data Plane Plugin Architecture](/docs/DATAPLANE_PLUGIN_ARCHITECTURE.md)
- [Base Plugin Documentation](/src/iac/plugins/base_plugin.py)
- [Azure Compute SDK Documentation](https://docs.microsoft.com/python/api/azure-mgmt-compute)

## Contributing

To extend the VM plugin:

1. Add new discovery logic in `discover()` method
2. Update code generation in `generate_replication_code()` method
3. Enhance replication in `replicate_with_mode()` method
4. Add corresponding tests in `tests/iac/data_plane_plugins/test_vm_plugin.py`
5. Update this README with new features

## License

Part of Azure Tenant Grapher project. See main project LICENSE for details.

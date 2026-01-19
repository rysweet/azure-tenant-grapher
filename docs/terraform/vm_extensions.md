# VM Extension Terraform Emission

## Overview

Azure Tenant Grapher fully supports Virtual Machine extensions through the `VMExtensionHandler`. This handler converts Azure VM extensions (`Microsoft.Compute/virtualMachines/extensions`) into Terraform `azurerm_virtual_machine_extension` resources with complete property mapping and intelligent parent VM detection.

## Features

### Automatic OS Type Detection

The handler automatically detects whether the parent VM is Linux or Windows and generates the correct parent reference:
- Linux VMs → References `azurerm_linux_virtual_machine.{vm_name}.id`
- Windows VMs → References `azurerm_windows_virtual_machine.{vm_name}.id`
- Unknown OS → Defaults to Linux with warning

### Complete Property Mapping

All essential VM extension properties are mapped to Terraform:
- `name` - Extension name (extracted from Azure resource name)
- `virtual_machine_id` - Reference to parent VM (OS-aware)
- `publisher` - Extension publisher (e.g., "Microsoft.Azure.Extensions")
- `type` - Extension type (e.g., "CustomScript")
- `type_handler_version` - Extension version (e.g., "2.1")
- `auto_upgrade_minor_version` - Auto-upgrade flag (optional)
- `settings` - Public configuration settings (optional, JSON object)
- `protected_settings` - Sensitive configuration (optional, marked sensitive in HCL)

### Parent VM Relationship Handling

Extensions maintain proper dependency on their parent VMs:
- Extension name format: `{vm_name}/{extension_name}`
- Extracts VM name and queries context/graph for VM OS type
- Validates parent VM exists before emitting extension
- Skips extension with warning if parent VM was skipped/not found

### Sensitive Data Protection

Protected settings are handled securely:
- `protected_settings` property marked as sensitive in Terraform
- Values not exposed in logs or plan output
- Supports secure deployment of scripts, keys, and credentials

## Supported Extension Types

The handler supports all Azure VM extension types, including:
- **CustomScript** (Linux/Windows) - Run scripts on VM deployment
- **OMS Agent** - Log Analytics workspace integration
- **Azure Monitor Agent** - Monitoring and diagnostics
- **Azure AD Login** - Azure AD authentication
- **Network Watcher** - Network diagnostics
- **Custom extensions** - Any publisher/type combination

## Usage Example

### Azure Resource (Discovered)

```json
{
  "type": "Microsoft.Compute/virtualMachines/extensions",
  "name": "web-vm-01/CustomScriptExtension",
  "properties": {
    "publisher": "Microsoft.Azure.Extensions",
    "type": "CustomScript",
    "typeHandlerVersion": "2.1",
    "autoUpgradeMinorVersion": true,
    "settings": {
      "fileUris": ["https://example.com/script.sh"],
      "commandToExecute": "sh script.sh"
    },
    "protectedSettings": {
      "storageAccountKey": "***sensitive***"
    }
  }
}
```

### Generated Terraform (Linux VM)

```hcl
resource "azurerm_virtual_machine_extension" "web_vm_01_CustomScriptExtension" {
  name                 = "CustomScriptExtension"
  virtual_machine_id   = azurerm_linux_virtual_machine.web_vm_01.id
  publisher            = "Microsoft.Azure.Extensions"
  type                 = "CustomScript"
  type_handler_version = "2.1"
  auto_upgrade_minor_version = true

  settings = jsonencode({
    fileUris = ["https://example.com/script.sh"]
    commandToExecute = "sh script.sh"
  })

  protected_settings = jsonencode({
    storageAccountKey = "***sensitive***"
  })
}
```

### Generated Terraform (Windows VM)

```hcl
resource "azurerm_virtual_machine_extension" "app_vm_02_CustomScriptExtension" {
  name                 = "CustomScriptExtension"
  virtual_machine_id   = azurerm_windows_virtual_machine.app_vm_02.id
  publisher            = "Microsoft.Compute"
  type                 = "CustomScriptExtension"
  type_handler_version = "1.10"
  auto_upgrade_minor_version = true

  settings = jsonencode({
    fileUris = ["https://example.com/script.ps1"]
  })

  protected_settings = jsonencode({
    commandToExecute = "powershell -ExecutionPolicy Unrestricted -File script.ps1"
  })
}
```

## Implementation Details

### OS Type Detection Algorithm

1. **Extract VM name** from extension name (`{vm_name}/{extension_name}` format)
2. **Query EmitterContext** for parent VM resource
3. **If found in context:**
   - Check emitted Terraform type (`azurerm_linux_virtual_machine` or `azurerm_windows_virtual_machine`)
   - Use matching reference
4. **If not in context:**
   - Query Neo4j graph for parent VM
   - Parse `properties.osProfile.windowsConfiguration` or `linuxConfiguration`
   - Determine OS type from config
5. **Fallback:** Default to Linux if OS type cannot be determined (with warning)

### Settings Serialization

Both `settings` and `protected_settings` are:
- Parsed from JSON properties
- Re-serialized using `jsonencode()` in Terraform
- Protected settings marked as `sensitive = true` in HCL output

### Validation

The handler performs validation before emission:
- Parent VM name extracted successfully
- Parent VM exists (either in emitted Terraform or queryable in graph)
- Required properties present (publisher, type, typeHandlerVersion)
- If validation fails, extension is skipped with detailed warning

## Error Handling

### Skipped Extensions

Extensions are skipped (with warnings) when:
- Parent VM name cannot be extracted from resource name
- Parent VM was skipped during emission (e.g., missing NICs)
- Parent VM not found in context or graph
- Required properties missing (publisher, type, or version)

### Warning Messages

```
WARNING: VM Extension 'web-vm-01/CustomScriptExtension' - parent VM 'web-vm-01' not found in emitted resources. Skipping extension.
WARNING: VM Extension 'unknown-vm/Extension1' - cannot determine OS type for parent VM. Defaulting to Linux.
```

## Testing

Comprehensive tests cover:
- Linux VM extensions (correct parent reference)
- Windows VM extensions (correct parent reference)
- Settings and protected_settings mapping
- Missing parent VM (extension skipped)
- Unknown OS type (defaults to Linux)
- Multiple extensions on same VM
- Extensions with no settings (basic properties only)

## Terraform Compatibility

Generated configurations are compatible with:
- Terraform >= 1.0
- azurerm provider >= 3.0
- Follows Terraform best practices for sensitive data

## Known Limitations

- Extension provisioning state not mapped (Terraform manages state independently)
- Extension dependencies (if multiple extensions on same VM) may require manual dependency declarations
- Data plane operations (script content download) handled by Terraform during apply, not by ATG

## Related Documentation

- [Virtual Machine Emission](./virtual_machines.md)
- [Terraform Handler Architecture](./handlers.md)
- [EmitterContext API](./context.md)
- [Azure VM Extensions Reference](https://docs.microsoft.com/en-us/azure/virtual-machines/extensions/overview)

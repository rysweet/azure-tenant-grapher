# VM Extension OS-Aware Publisher/Type Mapping

## Overview

The VM Extensions handler automatically maps extension publisher and type values based on the parent VM's operating system. This prevents deployment failures when extension metadata doesn't match the VM OS type.

## Problem Solved

When converting DevTestLab Windows VMs to standard Linux VMs (to avoid lab dependency), extensions retain Windows-specific publisher/type metadata. Deploying these extensions fails with:

```
Error: OperationNotAllowed: Publisher 'Microsoft.Compute' and type 'CustomScriptExtension'
are not supported for OS type 'Linux'. Please use publisher 'Microsoft.Azure.Extensions'
and type 'CustomScript' instead.
```

## Solution

The handler now:
1. Detects parent VM OS type (Linux vs Windows) from emitted VM resources
2. Maps extension metadata to OS-appropriate values using `EXTENSION_MAPPINGS` dictionary
3. Logs warnings when mappings are applied for transparency
4. Preserves all other extension properties (settings, protectedSettings, autoUpgradeMinorVersion)

## Supported Extension Types

### CustomScriptExtension
| OS | Publisher | Type | Handler Version |
|----|-----------|------|----------------|
| Linux | Microsoft.Azure.Extensions | CustomScript | 2.1 |
| Windows | Microsoft.Compute | CustomScriptExtension | 1.10 |

### DSC (Desired State Configuration)
| OS | Publisher | Type | Handler Version |
|----|-----------|------|----------------|
| Windows | Microsoft.Powershell | DSC | 2.77 |

Note: DSC is Windows-only.

### AADLogin (Azure AD Authentication)
| OS | Publisher | Type | Handler Version |
|----|-----------|------|----------------|
| Linux | Microsoft.Azure.ActiveDirectory | AADSSHLoginForLinux | 1.0 |
| Windows | Microsoft.Azure.ActiveDirectory | AADLoginForWindows | 1.0 |

### AzureMonitorAgent
| OS | Publisher | Type | Handler Version |
|----|-----------|------|----------------|
| Linux | Microsoft.Azure.Monitor | AzureMonitorLinuxAgent | 1.0 |
| Windows | Microsoft.Azure.Monitor | AzureMonitorWindowsAgent | 1.0 |

### NetworkWatcherAgent
| OS | Publisher | Type | Handler Version |
|----|-----------|------|----------------|
| Linux | Microsoft.Azure.NetworkWatcher | NetworkWatcherAgentLinux | 1.4 |
| Windows | Microsoft.Azure.NetworkWatcher | NetworkWatcherAgentWindows | 1.4 |

## Usage

The mapping happens automatically during Terraform emission. No user configuration required.

### Example: CustomScriptExtension

**Source (Azure):**
```json
{
  "type": "Microsoft.Compute/virtualMachines/extensions",
  "name": "linux-vm-01/customscript",
  "properties": {
    "publisher": "Microsoft.Compute",
    "type": "CustomScriptExtension",
    "typeHandlerVersion": "1.10",
    "settings": {
      "script": "echo 'Hello World'"
    }
  }
}
```

**Emitted (Terraform):**
```hcl
resource "azurerm_virtual_machine_extension" "linux_vm_01_customscript" {
  name                 = "customscript"
  virtual_machine_id   = azurerm_linux_virtual_machine.linux_vm_01.id
  publisher            = "Microsoft.Azure.Extensions"          # Mapped for Linux
  type                 = "CustomScript"                        # Mapped for Linux
  type_handler_version = "2.1"                                 # Mapped for Linux
  auto_upgrade_minor_version = true

  settings = jsonencode({
    "script" = "echo 'Hello World'"
  })
}
```

**Log Output:**
```
WARNING: Extension 'customscript' mapped from Windows (Microsoft.Compute/CustomScriptExtension/1.10)
to Linux (Microsoft.Azure.Extensions/CustomScript/2.1) for VM 'linux-vm-01'
```

## Implementation Details

### OS Detection

OS type is detected from the parent VM's Terraform resource type:
- `azurerm_linux_virtual_machine` → Linux
- `azurerm_windows_virtual_machine` → Windows

### Mapping Logic

1. Extract original publisher and type from Azure resource properties
2. Detect parent VM OS type via `_detect_vm_os_type()`
3. Create lookup key: `(os_type, extension_type)`
4. Check `EXTENSION_MAPPINGS` dictionary
5. If mapping exists, override publisher/type/version and log warning
6. If no mapping exists, use original values (fallback for unsupported types)

### Fallback Behavior

For unsupported extension types not in `EXTENSION_MAPPINGS`, the handler preserves original metadata. This allows:
- Third-party extensions to work without modification
- Custom extension types to pass through unchanged
- Gradual expansion of supported types without breaking existing functionality

## Testing

Comprehensive unit tests cover:
- OS detection for both Linux and Windows VMs
- Mapping for all 5 supported extension types
- Fallback behavior for unmapped types
- Warning log generation
- Property preservation (settings, protectedSettings, autoUpgrade)

## Future Enhancements

Additional extension types can be added to `EXTENSION_MAPPINGS` as needed:
- MicrosoftMonitoringAgent
- DependencyAgentLinux/Windows
- AzureDiskEncryption
- Custom VM extensions

## Related

- Issue #326: VM Extension OS-aware publisher/type mapping
- GAP-020: VM Extensions gap analysis

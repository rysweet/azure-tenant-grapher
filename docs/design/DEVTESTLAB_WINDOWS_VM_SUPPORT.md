# DevTest Lab Windows VM Support

**Status**: ✅ IMPLEMENTED
**Issue**: #305 (GAP-002)
**Date**: 2026-01-19

## Overview

Azure Tenant Grapher now supports both Windows and Linux virtual machines in Azure DevTest Labs. The system automatically detects the operating system type and generates the appropriate Terraform resource configuration.

## Supported VM Types

### Linux VMs
- **Terraform Resource**: `azurerm_dev_test_linux_virtual_machine`
- **Authentication**: SSH public key
- **Detection**: `osType: "Linux"` in galleryImageReference, or Linux-specific offers (Ubuntu, CentOS, etc.)

### Windows VMs
- **Terraform Resource**: `azurerm_dev_test_windows_virtual_machine`
- **Authentication**: Admin password (variable reference)
- **Detection**: `osType: "Windows"` in galleryImageReference, or Windows-specific offers (WindowsServer, etc.)

## OS Detection Logic

The handler uses a multi-layered detection strategy:

1. **Primary**: Check `galleryImageReference.osType` field
2. **Fallback 1**: Inspect `offer` field for Windows keywords
3. **Fallback 2**: Inspect `publisher` field for Microsoft indicators

```python
gallery_image_ref = properties.get("galleryImageReference", {})
os_type = gallery_image_ref.get("osType", "").lower()
offer = gallery_image_ref.get("offer", "").lower()
publisher = gallery_image_ref.get("publisher", "").lower()

is_windows = (
    os_type == "windows"
    or "windows" in offer
    or "microsoftwindowsserver" in publisher
)
```

## Authentication Configuration

### Windows VMs
Windows virtual machines use password-based authentication:

```hcl
resource "azurerm_dev_test_windows_virtual_machine" "example" {
  lab_name            = azurerm_dev_test_lab.example.name
  name                = "example-vm"
  location            = azurerm_resource_group.example.location
  resource_group_name = azurerm_resource_group.example.name

  size                   = "Standard_DS1_v2"
  username               = "adminuser"
  password               = var.devtest_vm_password_example_vm  # Password variable
  storage_type           = "Standard"
  lab_subnet_name        = "default"
  lab_virtual_network_id = azurerm_dev_test_lab.example.id

  gallery_image_reference {
    offer     = "WindowsServer"
    publisher = "MicrosoftWindowsServer"
    sku       = "2022-Datacenter"
    version   = "latest"
  }
}
```

### Linux VMs
Linux virtual machines use SSH key authentication:

```hcl
resource "azurerm_dev_test_linux_virtual_machine" "example" {
  lab_name            = azurerm_dev_test_lab.example.name
  name                = "example-vm"
  location            = azurerm_resource_group.example.location
  resource_group_name = azurerm_resource_group.example.name

  size                   = "Standard_DS1_v2"
  username               = "azureuser"
  ssh_key                = var.devtest_vm_ssh_key_example_vm  # SSH key variable
  storage_type           = "Standard"
  lab_subnet_name        = "default"
  lab_virtual_network_id = azurerm_dev_test_lab.example.id

  gallery_image_reference {
    offer     = "0001-com-ubuntu-server-jammy"
    publisher = "Canonical"
    sku       = "22_04-lts-gen2"
    version   = "latest"
  }
}
```

## Variable References

The generated Terraform code references variables for sensitive authentication data:

- **Windows VMs**: `var.devtest_vm_password_{safe_name}`
- **Linux VMs**: `var.devtest_vm_ssh_key_{safe_name}`

Users must provide these variables when applying the Terraform configuration.

## Common Image References

### Windows Server Images
- **Publisher**: `MicrosoftWindowsServer`
- **Offers**: `WindowsServer`, `WindowsServerSemiAnnual`
- **SKUs**: `2022-Datacenter`, `2019-Datacenter`, `2016-Datacenter`

### Linux Images
- **Ubuntu**: Publisher `Canonical`, Offer `0001-com-ubuntu-server-jammy`
- **CentOS**: Publisher `OpenLogic`, Offer `CentOS`
- **Red Hat**: Publisher `RedHat`, Offer `RHEL`

## Testing

The implementation includes comprehensive unit tests:

1. Linux VM detection and configuration
2. Windows VM detection via `osType`
3. Windows VM detection via `offer` keywords
4. Windows VM detection via `publisher` keywords
5. Authentication configuration validation
6. Terraform resource type selection

## Migration Impact

Existing deployments with Linux-only DevTest Labs are **not affected**. This enhancement adds Windows VM support without breaking existing functionality.

## Troubleshooting

### Issue: VM not detected as Windows
**Solution**: Check the `galleryImageReference` properties in the Azure resource. Ensure `osType`, `offer`, or `publisher` contain Windows indicators.

### Issue: Missing password variable
**Solution**: Provide the password variable in your Terraform variables file:
```hcl
variable "devtest_vm_password_myvm" {
  type      = string
  sensitive = true
}
```

### Issue: Wrong VM type generated
**Solution**: Verify the Azure resource properties match the expected OS type. The handler logs the detection decision for debugging.

## References

- **Terraform Provider**: [azurerm_dev_test_windows_virtual_machine](https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/dev_test_windows_virtual_machine)
- **Azure API**: [Microsoft.DevTestLab/labs/virtualmachines](https://learn.microsoft.com/en-us/azure/templates/microsoft.devtestlab/labs/virtualmachines)
- **Pattern Source**: `src/iac/emitters/terraform/handlers/compute/virtual_machine.py`

## Sources

- [Terraform azurerm_dev_test_windows_virtual_machine](https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/dev_test_windows_virtual_machine)
- [Azure Dev Test Labs VM API](https://learn.microsoft.com/en-us/azure/templates/microsoft.devtestlab/labs/virtualmachines)
- [Create lab and VM using Terraform - Azure DevTest Labs](https://learn.microsoft.com/en-us/azure/devtest-labs/quickstarts/create-lab-windows-vm-terraform)

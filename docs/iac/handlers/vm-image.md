# VM Image Handler

## Overview

The VM Image handler converts Azure custom VM images from your scanned Azure tenant into Terraform `azurerm_image` resources. This enables you to recreate custom virtual machine images when deploying infrastructure to new environments.

**Handler**: `VMImageHandler`
**Location**: `src/iac/emitters/terraform/handlers/compute/vm_image.py`
**Azure Resource Type**: `Microsoft.Compute/images`
**Terraform Resource**: `azurerm_image`

## What are VM Images?

Azure VM Images (also called Custom Images) are snapshots of generalized or specialized virtual machines that can be used to create new VMs. They enable you to:

- Capture a configured VM as a reusable template
- Create multiple VMs from the same base configuration
- Distribute custom software configurations across environments
- Preserve zone-resilient disk configurations
- Support both Linux and Windows operating systems

VM Images contain:
- OS disk configuration (required)
- Optional data disk configurations
- Hyper-V generation settings
- Zone resilience configuration

## When to Use This Handler

The VM Image handler is automatically invoked during IaC generation when:

1. You've scanned an Azure tenant with `azure-tenant-grapher scan`
2. The scanned resources include custom VM images (`Microsoft.Compute/images`)
3. You run `azure-tenant-grapher generate-iac --format terraform`

## How It Works

### Discovery Phase
During Azure tenant scanning, VM images are discovered as `Microsoft.Compute/images` resources and stored in the Neo4j graph with properties including:
- Source virtual machine references
- OS disk configuration
- Data disk configurations
- Zone resilience settings
- Hyper-V generation

### Generation Phase
When generating Terraform IaC, the VM Image handler:

1. **Reads** VM image nodes from Neo4j
2. **Extracts** source VM reference if present
3. **Maps** OS disk properties (type, state, size)
4. **Maps** data disk array if present
5. **Includes** zone resilience and Hyper-V generation settings
6. **Emits** `azurerm_image` Terraform resource

## Generated Terraform Structure

### Basic Linux Image Example
```hcl
resource "azurerm_image" "ubuntu_custom" {
  name                = "ubuntu-2204-apache"
  location            = "eastus"
  resource_group_name = "images-rg"

  os_disk {
    os_type  = "Linux"
    os_state = "Generalized"
    size_gb  = 30
  }

  tags = {
    environment = "production"
    created_by  = "atg"
  }
}
```

### Windows Image with Source VM Example
```hcl
resource "azurerm_image" "windows_custom" {
  name                      = "windows-2022-configured"
  location                  = "eastus"
  resource_group_name       = "images-rg"
  source_virtual_machine_id = azurerm_windows_virtual_machine.source_vm.id

  os_disk {
    os_type  = "Windows"
    os_state = "Generalized"
  }

  tags = {
    environment = "staging"
  }
}
```

### Image with Data Disks Example
```hcl
resource "azurerm_image" "multi_disk_image" {
  name                = "app-server-image"
  location            = "westus2"
  resource_group_name = "images-rg"

  os_disk {
    os_type  = "Linux"
    os_state = "Generalized"
    size_gb  = 64
  }

  data_disk {
    lun     = 0
    size_gb = 128
  }

  data_disk {
    lun     = 1
    size_gb = 256
  }

  zone_resilient = true
  hyper_v_generation = "V2"
}
```

### Image from VHD Blob Example
```hcl
resource "azurerm_image" "vhd_image" {
  name                = "imported-vhd-image"
  location            = "centralus"
  resource_group_name = "images-rg"

  os_disk {
    os_type   = "Linux"
    os_state  = "Generalized"
    blob_uri  = "https://mystorage.blob.core.windows.net/vhds/mydisk.vhd"
    size_gb   = 32
  }
}
```

## Supported Scenarios

### ✅ Supported
- Linux VM images (os_type: "Linux")
- Windows VM images (os_type: "Windows")
- Generalized images (os_state: "Generalized")
- Specialized images (os_state: "Specialized")
- Source VM references
- OS disk configuration (type, state, size, blob URI)
- Multiple data disks
- Zone resilient images
- Hyper-V generation V1 and V2
- VHD blob URIs
- Standard tags and metadata

### ⚠️ Limitations
- Managed disk IDs in os_disk/data_disk not yet supported (future enhancement)
- Image encryption settings not yet mapped (future enhancement)
- Shared Image Gallery images handled by separate handler

## Configuration Details

### OS Disk Properties
The handler maps these OS disk properties:

| Azure Property | Terraform Field | Required | Description |
|---------------|----------------|----------|-------------|
| `osType` | `os_type` | Yes | "Linux" or "Windows" |
| `osState` | `os_state` | Yes | "Generalized" or "Specialized" |
| `blobUri` | `blob_uri` | No | VHD blob URI if applicable |
| `diskSizeGB` | `size_gb` | No | Disk size in gigabytes |

### Data Disk Properties
For each data disk in the array:

| Azure Property | Terraform Field | Required | Description |
|---------------|----------------|----------|-------------|
| `lun` | `lun` | Yes | Logical Unit Number (0-63) |
| `blobUri` | `blob_uri` | No | VHD blob URI if applicable |
| `diskSizeGB` | `size_gb` | No | Disk size in gigabytes |

### Zone Resilience
- Maps `zoneResilient` boolean directly to `zone_resilient` in Terraform
- Enables storage to span availability zones when true

### Hyper-V Generation
- Maps `hyperVGeneration` to `hyper_v_generation`
- Values: "V1" (default) or "V2" (UEFI boot, larger disk sizes)

## Troubleshooting

### VM Images Not Generated

**Symptom**: Expected VM images missing from Terraform output

**Causes**:
1. **Missing required properties**: OS disk configuration incomplete
   - **Solution**: Verify Azure image has os_type and os_state
2. **Resource not scanned**: Image not included in scan scope
   - **Solution**: Rescan with broader scope or include specific resource groups
3. **Invalid resource type**: Shared Image Gallery images use different handler
   - **Solution**: Check if resource is `Microsoft.Compute/galleries/images` instead

**Check logs**:
```bash
# Look for skip messages during IaC generation
azure-tenant-grapher generate-iac --format terraform 2>&1 | grep -i "image"
```

### Missing Source VM Reference

**Symptom**: Generated image doesn't include `source_virtual_machine_id`

**Cause**: Source VM was not captured or not in scope

**Solution**:
1. Verify source VM exists in Neo4j:
   ```cypher
   MATCH (i:Image {name: 'your-image-name'})
   OPTIONAL MATCH (i)-[:CREATED_FROM]->(vm:VirtualMachine)
   RETURN i.name, vm.name
   ```
2. If VM missing, rescan with VM included in scope
3. If creating from VHD blob, source VM reference not needed

### Invalid OS Type or State

**Symptom**: Terraform validation fails with invalid os_type or os_state

**Cause**: Azure image properties corrupted or invalid

**Solution**:
1. Query image properties in Neo4j:
   ```cypher
   MATCH (i:Image {name: 'your-image-name'})
   RETURN i.properties
   ```
2. Verify os_type is "Linux" or "Windows" (case-sensitive)
3. Verify os_state is "Generalized" or "Specialized"
4. Recreate image in Azure if properties invalid

## Integration with Other Handlers

The VM Image handler works alongside:

- **Virtual Machine Handler**: VMs can reference images via `source_image_id`
- **Managed Disk Handler**: Images contain disk configurations
- **Resource Group Handler**: Generates resource groups containing images

## Examples

### Scan and Generate with VM Images

```bash
# 1. Scan Azure tenant
azure-tenant-grapher scan --tenant-id YOUR_TENANT_ID

# 2. Generate Terraform IaC
azure-tenant-grapher generate-iac --format terraform --output-dir ./terraform-output

# 3. Review generated VM images
ls ./terraform-output/compute/images/

# 4. Validate Terraform
cd ./terraform-output
terraform init
terraform validate
```

### Query VM Images in Neo4j

```cypher
// Find all VM images
MATCH (i:Image)
WHERE i.type = 'Microsoft.Compute/images'
RETURN i.name, i.location, i.properties

// Find images with source VMs
MATCH (i:Image)-[:CREATED_FROM]->(vm:VirtualMachine)
RETURN i.name AS ImageName, vm.name AS SourceVM

// Find zone-resilient images
MATCH (i:Image)
WHERE i.properties CONTAINS 'zoneResilient'
  AND i.properties CONTAINS 'true'
RETURN i.name, i.location

// Count images by OS type
MATCH (i:Image)
WHERE i.properties CONTAINS 'osType'
RETURN
  CASE
    WHEN i.properties CONTAINS '"osType":"Linux"' THEN 'Linux'
    WHEN i.properties CONTAINS '"osType":"Windows"' THEN 'Windows'
    ELSE 'Unknown'
  END AS OSType,
  COUNT(*) AS Count
```

## Best Practices

1. **Generalize images before capture**: Use sysprep (Windows) or waagent (Linux) to generalize VMs
2. **Use zone-resilient storage**: Enable `zone_resilient` for production images
3. **Document image contents**: Use tags to track installed software and versions
4. **Version your images**: Include version numbers in image names
5. **Clean up old images**: Delete unused images to reduce storage costs
6. **Use Hyper-V Gen 2**: For new images, use V2 for UEFI boot and larger disk support
7. **Separate image resource groups**: Keep images in dedicated resource groups for easier management

## Related Documentation

- [Azure VM Images Overview](https://learn.microsoft.com/en-us/azure/virtual-machines/capture-image-portal)
- [Terraform azurerm_image](https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/image)
- [ATG IaC Generation Guide](../iac-generation.md)
- [Virtual Machine Handler](./virtual-machine.md)
- [Managed Disk Handler](./managed-disk.md)

## Changelog

### v1.0.0 (2026-01-24)
- Initial implementation
- Support for Linux and Windows images
- Source VM reference mapping
- OS disk and data disk configuration
- Zone resilience support
- Hyper-V generation mapping
- VHD blob URI support

## Support

If you encounter issues with the VM Image handler:

1. Check the [Troubleshooting](#troubleshooting) section above
2. Review logs during IaC generation
3. Query Neo4j to verify images were captured during scan
4. File an issue on GitHub with:
   - Image ARM ID
   - Expected vs actual Terraform output
   - Relevant log messages
   - Neo4j query results showing image properties

# DevTestLab Policy and Virtual Network Handlers

## Overview

The DevTestLab Policy and Virtual Network handlers preserve lab-specific features during Infrastructure-as-Code generation. These handlers ensure that DevTestLab policies (VM limits, size restrictions) and lab-specific virtual networks are correctly mapped to Terraform resources.

## Handlers

### devtest_policy Handler

**File**: `src/iac/emitters/terraform/handlers/devtest/devtest_policy.py`

**Handles**: `Microsoft.DevTestLab/labs/policysets/policies`

**Emits**: `azurerm_dev_test_policy`

**Purpose**: Converts Azure DevTestLab policies to Terraform `azurerm_dev_test_policy` resources, preserving policy configurations such as VM limits, allowed sizes, and gallery image restrictions.

#### Supported Policy Types

- **GalleryImage** - Restricts allowed VM images
- **LabVmCount** - Maximum VMs allowed in the lab
- **LabVmSize** - Allowed VM sizes
- **LabPremiumVmCount** - Maximum premium VMs
- **LabTargetCost** - Lab cost management
- **UserOwnedLabVmCount** - Per-user VM limits
- **UserOwnedLabPremiumVmCount** - Per-user premium VM limits
- **UserOwnedLabVmCountInSubnet** - Subnet-specific VM limits

#### Usage Example

Given an Azure DevTestLab policy resource:

```json
{
  "type": "Microsoft.DevTestLab/labs/policysets/policies",
  "name": "MyLab/default/LabVmCount",
  "location": "eastus",
  "properties": {
    "description": "Maximum VMs allowed in lab",
    "status": "Enabled",
    "factName": "LabVmCount",
    "factData": "",
    "threshold": "10",
    "evaluatorType": "MaxValuePolicy"
  }
}
```

The handler generates:

```hcl
resource "azurerm_dev_test_policy" "lab_vm_count" {
  name                = "LabVmCount"
  policy_set_name     = "default"
  lab_name            = "MyLab"
  resource_group_name = azurerm_resource_group.rg.name
  location            = "eastus"
  tags                = {}

  fact_data      = ""
  threshold      = "10"
  evaluator_type = "MaxValuePolicy"
  description    = "Maximum VMs allowed in lab"
}
```

#### Key Features

- **Hierarchical Name Parsing**: Extracts lab name, policy set, and policy name from Azure resource name (`lab/policyset/policy`)
- **Policy Set Handling**: Correctly identifies policy set (typically "default")
- **Evaluator Type Mapping**: Maps Azure evaluator types to Terraform equivalents
- **Threshold Preservation**: Maintains policy threshold values as strings (Terraform requirement)
- **Status Handling**: Preserves Enabled/Disabled policy status

### devtest_virtual_network Handler

**File**: `src/iac/emitters/terraform/handlers/devtest/devtest_virtual_network.py`

**Handles**: `Microsoft.DevTestLab/labs/virtualnetworks`

**Emits**: `azurerm_dev_test_virtual_network`

**Purpose**: Converts lab-specific virtual networks to Terraform `azurerm_dev_test_virtual_network` resources, preserving subnet configurations and permission settings.

#### Subnet Configuration

Lab virtual networks have specialized subnet configurations:

- **use_public_ip_address** - Controls public IP usage in the subnet
- **use_in_virtual_machine_creation** - Controls VM creation permission in the subnet
- **shared_public_ip_address_configuration** - Shared public IP settings

#### Usage Example

Given an Azure DevTestLab virtual network resource:

```json
{
  "type": "Microsoft.DevTestLab/labs/virtualnetworks",
  "name": "MyLab/MyLabVnet",
  "location": "eastus",
  "properties": {
    "description": "Lab virtual network",
    "externalProviderResourceId": "/subscriptions/.../providers/Microsoft.Network/virtualNetworks/ActualVNet",
    "subnetOverrides": [
      {
        "labSubnetName": "default",
        "resourceId": "/subscriptions/.../subnets/default",
        "useInVmCreationPermission": "Allow",
        "usePublicIpAddressPermission": "Allow"
      }
    ]
  }
}
```

The handler generates:

```hcl
resource "azurerm_dev_test_virtual_network" "my_lab_vnet" {
  name                = "MyLabVnet"
  lab_name            = "MyLab"
  resource_group_name = azurerm_resource_group.rg.name
  location            = "eastus"
  tags                = {}

  description = "Lab virtual network"

  subnet {
    use_public_ip_address          = "Allow"
    use_in_virtual_machine_creation = "Allow"
  }
}
```

#### Key Features

- **Hierarchical Name Parsing**: Extracts lab name and virtual network name from Azure resource name (`lab/vnet`)
- **External VNet Reference**: Handles references to existing Azure virtual networks
- **Subnet Override Mapping**: Converts Azure subnet overrides to Terraform subnet blocks
- **Permission Mapping**: Correctly maps permission levels (Allow, Default, Deny)
- **Multiple Subnet Support**: Handles labs with multiple subnet configurations

## Design Patterns

### Common Handler Pattern

Both handlers follow the established DevTestLab handler pattern:

1. **Type Declaration**: Use `@handler` decorator to register with the handler registry
2. **Name Parsing**: Extract hierarchical components (lab name, resource name)
3. **Property Extraction**: Use `parse_properties()` to get Azure properties
4. **Base Config**: Use `build_base_config()` for common attributes (location, tags, resource_group)
5. **Resource-Specific Config**: Add handler-specific properties
6. **Terraform Emission**: Return (terraform_type, safe_name, config)

### Error Handling

- **Missing Properties**: Use sensible defaults (e.g., "default" for policy_set_name)
- **Malformed Names**: Log warnings and use fallback values
- **Invalid Configurations**: Skip resource with explicit logging

## Integration

### Handler Registration

The handlers are automatically registered via the `@handler` decorator and imported in `src/iac/emitters/terraform/handlers/__init__.py`:

```python
# DevTest handlers
from .devtest import devtest_lab, devtest_policy, devtest_schedule, devtest_virtual_network, devtest_vm

_ = (devtest_lab, devtest_policy, devtest_schedule, devtest_virtual_network, devtest_vm)
```

### Dependency Handling

- **Lab Reference**: Both handlers require the parent DevTestLab to exist
- **Virtual Network Reference**: VNet handler may reference external Azure virtual networks
- **Policy Dependencies**: Policies are independent but belong to a policy set (typically "default")

## Testing

### Test Coverage

Comprehensive test suites ensure correct behavior:

- **test_devtest_policy.py**: ~120-150 lines
  - Basic policy emission
  - Hierarchical name parsing
  - Different policy types
  - Evaluator type mapping
  - Edge cases (missing properties, defaults)

- **test_devtest_virtual_network.py**: ~130-180 lines
  - Basic VNet emission
  - Name parsing
  - Subnet configuration mapping
  - External VNet references
  - Permission level mapping
  - Edge cases (empty subnets, missing config)

### Running Tests

```bash
# Test both handlers
pytest tests/unit/iac/emitters/terraform/handlers/test_devtest_policy.py
pytest tests/unit/iac/emitters/terraform/handlers/test_devtest_virtual_network.py

# Test all DevTestLab handlers
pytest tests/unit/iac/emitters/terraform/handlers/ -k devtest
```

## Limitations

### Known Limitations

1. **Policy Set Assumption**: Assumes policy set name is "default" (standard Azure convention)
2. **Single Subnet**: Virtual network handler currently maps primary subnet only
3. **Permission Levels**: Maps three levels (Allow, Default, Deny) - may need expansion for future Azure updates

### Future Enhancements

1. **Multiple Policy Sets**: Support for custom policy set names
2. **Advanced Subnet Config**: Support for subnet pooling and advanced configurations
3. **Dynamic Properties**: Handle new Azure policy types automatically

## Troubleshooting

### Common Issues

**Issue**: Policy not emitted
- **Cause**: Malformed resource name or missing lab reference
- **Solution**: Verify resource name follows `lab/policyset/policy` pattern

**Issue**: VNet subnet configuration missing
- **Cause**: Empty subnetOverrides array in Azure resource
- **Solution**: Handler uses defaults - check Azure resource for actual subnet config

**Issue**: Terraform apply fails with "policy already exists"
- **Cause**: Policy name collision
- **Solution**: Use unique policy names per lab or import existing policies

## References

- **Azure API**: [Microsoft.DevTestLab/labs/policysets/policies](https://learn.microsoft.com/en-us/azure/templates/microsoft.devtestlab/labs/policysets/policies)
- **Azure API**: [Microsoft.DevTestLab/labs/virtualnetworks](https://learn.microsoft.com/en-us/azure/templates/microsoft.devtestlab/labs/virtualnetworks)
- **Terraform**: [azurerm_dev_test_policy](https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/dev_test_policy)
- **Terraform**: [azurerm_dev_test_virtual_network](https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/dev_test_virtual_network)
- **Pattern Reference**: `src/iac/emitters/terraform/handlers/devtest/devtest_schedule.py`

## Related

- Issue #307: GAP-019 DevTestLab Feature Preservation
- PR #769: DevTestLab VM Windows Support (GAP-002)
- Gap Catalog: `demo_run/GAP_ANALYSIS_CATALOG.md`

# DevTestLab Policy and Virtual Network Handler Design

## Overview

This document specifies the design for two new Terraform handlers that preserve DevTestLab-specific features during IaC generation:

1. **devtest_policy.py** - DevTestLab policy handler
2. **devtest_virtual_network.py** - DevTestLab virtual network handler

## Design Goals

- Follow established DevTestLab handler pattern (devtest_lab.py, devtest_vm.py, devtest_schedule.py)
- Map Azure resource types to Terraform resource types correctly
- Extract and preserve critical properties
- Maintain ruthless simplicity (no over-engineering)
- Zero-BS implementation (no stubs or placeholders)

## Handler 1: devtest_policy.py

### Azure Resource Type
- `Microsoft.DevTestLab/labs/policysets/policies`

### Terraform Resource Type
- `azurerm_dev_test_policy`

### Key Properties (from Azure API)
Based on API version 2018-09-15:
- `name` - Policy name (e.g., GalleryImage, LabVmCount, LabVmSize, etc.)
- `properties.description` - Policy description
- `properties.evaluatorType` - Evaluator type (e.g., "MaxValuePolicy")
- `properties.factData` - Additional policy data
- `properties.factName` - Fact name for evaluation
- `properties.status` - Policy status (Enabled/Disabled)
- `properties.threshold` - Policy threshold value

### Terraform Mapping
```python
{
    "name": policy_name,
    "policy_set_name": "default",  # Standard policy set name
    "lab_name": lab_name,
    "resource_group_name": resource_group,
    "location": location,
    "tags": tags,
    "fact_data": fact_data,
    "threshold": threshold,
    "evaluator_type": evaluator_type,
    "description": description,
}
```

### Name Parsing Logic
Policy names follow pattern: `labname/default/policyname`
- Extract lab_name (first part)
- policy_set_name is typically "default" (second part)
- policy_name is the actual policy type (third part)

### Policy Types (Common Examples)
- `GalleryImage` - Allowed VM images
- `LabVmCount` - Maximum VMs in lab
- `LabVmSize` - Allowed VM sizes
- `LabPremiumVmCount` - Premium VM limit
- `UserOwnedLabVmCount` - User VM limit
- `UserOwnedLabPremiumVmCount` - User premium VM limit

### Implementation Size Estimate
~80-90 lines (similar to devtest_schedule.py)

## Handler 2: devtest_virtual_network.py

### Azure Resource Type
- `Microsoft.DevTestLab/labs/virtualnetworks`

### Terraform Resource Type
- `azurerm_dev_test_virtual_network`

### Key Properties (from Azure API)
Based on API version 2018-09-15:
- `name` - Virtual network name
- `properties.description` - VNet description
- `properties.externalProviderResourceId` - External VNet resource ID
- `properties.allowedSubnets` - Array of allowed subnets
  - `allowPublicIp` - Boolean
  - `labSubnetName` - Subnet name
  - `resourceId` - Subnet resource ID
- `properties.subnetOverrides` - Subnet configuration overrides
  - `labSubnetName` - Subnet name
  - `resourceId` - Resource ID
  - `useInVmCreationPermission` - Permission level
  - `usePublicIpAddressPermission` - IP permission level
  - `virtualNetworkPoolName` - Pool name
  - `sharedPublicIpAddressConfiguration` - Public IP config

### Terraform Mapping
```python
{
    "name": vnet_name,
    "lab_name": lab_name,
    "resource_group_name": resource_group,
    "location": location,
    "tags": tags,
    "description": description,
    "subnet": {
        "use_public_ip_address": subnet_config.get("usePublicIpAddressPermission"),
        "use_in_virtual_machine_creation": subnet_config.get("useInVmCreationPermission"),
    }
}
```

### Name Parsing Logic
VNet names follow pattern: `labname/vnetname`
- Extract lab_name (first part)
- vnet_name (second part)

### Implementation Size Estimate
~90-100 lines (slightly more complex due to subnet configuration)

## Common Pattern Elements

Both handlers follow this structure:

### 1. Class Declaration
```python
@handler
class DevTestPolicyHandler(ResourceHandler):
    HANDLED_TYPES: ClassVar[Set[str]] = {
        "Microsoft.DevTestLab/labs/policysets/policies",
    }
    TERRAFORM_TYPES: ClassVar[Set[str]] = {
        "azurerm_dev_test_policy",
    }
```

### 2. Emit Method Structure
```python
def emit(
    self,
    resource: Dict[str, Any],
    context: EmitterContext,
) -> Optional[Tuple[str, str, Dict[str, Any]]]:
    # 1. Extract name and parse components
    resource_name = resource.get("name", "unknown")
    properties = self.parse_properties(resource)

    # 2. Parse hierarchical name (lab/policyset/policy or lab/vnet)
    parts = resource_name.split("/")
    lab_name = parts[0] if len(parts) > 0 else "unknown-lab"
    specific_name = parts[-1]  # Last part is the specific resource name

    # 3. Build base config
    safe_name = self.sanitize_name(specific_name)
    config = self.build_base_config(resource)
    config["name"] = specific_name

    # 4. Add resource-specific properties
    config.update({
        "lab_name": lab_name,
        # ... other properties
    })

    # 5. Return terraform type, safe name, and config
    logger.debug(f"DevTest X '{specific_name}' emitted for lab '{lab_name}'")
    return "azurerm_dev_test_X", safe_name, config
```

### 3. Property Extraction
- Use `self.parse_properties(resource)` for JSON properties
- Use `self.build_base_config(resource)` for common attributes (location, tags, resource_group)
- Use `self.sanitize_name()` for Terraform-safe naming

## Test Strategy

### Test Coverage Goals
- Target ratio: 3:1 to 5:1 (test lines : implementation lines)
- Total estimate: ~250-400 lines of tests for both handlers combined

### Test Cases per Handler

#### devtest_policy.py Tests (~120-150 lines)
1. **Basic Policy Emission** - Verify correct Terraform type and structure
2. **Name Parsing** - Test lab/policyset/policy name parsing
3. **Policy Types** - Test different policy types (GalleryImage, LabVmCount, LabVmSize)
4. **Property Mapping** - Verify all properties mapped correctly
5. **Evaluator Types** - Test MaxValuePolicy and other evaluator types
6. **Edge Cases** - Missing properties, malformed names, default values

#### devtest_virtual_network.py Tests (~130-180 lines)
1. **Basic VNet Emission** - Verify correct Terraform type and structure
2. **Name Parsing** - Test lab/vnet name parsing
3. **Subnet Configuration** - Test subnet mapping with use permissions
4. **External Provider Resource** - Test external VNet reference
5. **Allowed Subnets** - Test allowed subnets array mapping
6. **Subnet Overrides** - Test subnet override configurations
7. **Edge Cases** - Missing subnets, empty configurations, default values

### Test Structure
```python
# tests/unit/iac/emitters/terraform/handlers/test_devtest_policy.py
# tests/unit/iac/emitters/terraform/handlers/test_devtest_virtual_network.py

class TestDevTestPolicyHandler:
    def test_basic_emission(self):
        # Test basic policy emission

    def test_name_parsing(self):
        # Test hierarchical name parsing

    def test_property_mapping(self):
        # Test property extraction and mapping

    # ... more tests
```

## Implementation Plan

### Files to Create
1. `src/iac/emitters/terraform/handlers/devtest/devtest_policy.py` (~80-90 lines)
2. `src/iac/emitters/terraform/handlers/devtest/devtest_virtual_network.py` (~90-100 lines)
3. `tests/unit/iac/emitters/terraform/handlers/test_devtest_policy.py` (~120-150 lines)
4. `tests/unit/iac/emitters/terraform/handlers/test_devtest_virtual_network.py` (~130-180 lines)

### Files to Modify
1. `src/iac/emitters/terraform/handlers/__init__.py` - Add imports for new handlers

### Total Estimated Lines
- Implementation: ~170-190 lines
- Tests: ~250-330 lines
- Test Ratio: ~1.5:1 to 1.7:1 (within proportional range for business logic)

## Proportionality Analysis

### Complexity Classification: COMPLEX
- 2 new handler files
- Hierarchical name parsing logic
- Multiple property mappings
- Integration with existing handler registry
- Comprehensive test coverage required

### Test Ratio Justification
- Target: 3:1 to 5:1 for business logic
- Actual: ~1.5:1 to 1.7:1
- Justification: Handlers are straightforward property mappings with well-defined patterns from existing handlers
- Not over-testing: Tests focus on critical path (name parsing, property mapping, edge cases)
- Proportional: Test effort matches implementation complexity

## References

### Azure API Documentation
- [Microsoft.DevTestLab/labs/policysets/policies](https://learn.microsoft.com/en-us/azure/templates/microsoft.devtestlab/labs/policysets/policies)
- [Microsoft.DevTestLab/labs/virtualnetworks](https://learn.microsoft.com/en-us/azure/templates/microsoft.devtestlab/labs/virtualnetworks)

### Terraform Provider Documentation
- [azurerm_dev_test_policy](https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/dev_test_policy)
- [azurerm_dev_test_virtual_network](https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/dev_test_virtual_network)

### Existing Handler Patterns
- `src/iac/emitters/terraform/handlers/devtest/devtest_lab.py`
- `src/iac/emitters/terraform/handlers/devtest/devtest_vm.py`
- `src/iac/emitters/terraform/handlers/devtest/devtest_schedule.py`

## Success Criteria

1. Both handlers follow established DevTestLab pattern
2. All tests pass with appropriate coverage
3. Philosophy compliance (ruthless simplicity, zero-BS)
4. Handles GAP-019 requirements (preserves policies and virtual networks)
5. PR is mergeable with CI passing

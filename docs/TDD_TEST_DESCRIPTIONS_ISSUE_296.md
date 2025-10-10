# Test Descriptions and Expected Failures - Issue #296

## Test Suite Organization

### Unit Tests (60% - 14 tests)

#### Test Group 1: Subnet Resource Detection

**1. test_standalone_subnet_is_detected**
- **Purpose**: Verify that standalone subnet resources from Neo4j are detected and converted (not skipped)
- **Status**: ✅ PASS - Basic detection implemented
- **What it validates**:
  - `_convert_resource()` returns a tuple (not None) for Microsoft.Network/subnets
  - The returned terraform_type is "azurerm_subnet"

**2. test_subnet_type_mapping**
- **Purpose**: Verify the Azure-to-Terraform type mapping exists and conversion works
- **Status**: ✅ PASS - Mapping exists and is used
- **What it validates**:
  - AZURE_TO_TERRAFORM_MAPPING contains "Microsoft.Network/subnets"
  - Mapping value is "azurerm_subnet"
  - Actual conversion produces a result

**3. test_subnet_with_missing_properties_handled**
- **Purpose**: Ensure graceful degradation when subnet properties are incomplete
- **Status**: ❌ FAIL - No validation or defaults implemented
- **Current error**: `AssertionError: assert 'address_prefixes' in {'name': 'incomplete', 'location': 'eastus', 'resource_group_name': 'test-rg'}`
- **Expected behavior**: Either skip with warning or provide default address_prefixes
- **What it validates**: Error handling for edge case data

---

#### Test Group 2: Required Field Extraction

**4. test_subnet_name_extracted_correctly**
- **Purpose**: Verify subnet name is correctly extracted from resource data
- **Status**: ✅ PASS - Basic name extraction works
- **What it validates**:
  - `resource_config["name"]` equals original subnet name
  - `resource_name` equals sanitized subnet name

**5. test_resource_group_extracted_from_properties**
- **Purpose**: Verify resource group is extracted from resource data
- **Status**: ✅ PASS - RG extraction works
- **What it validates**:
  - `resource_config["resource_group_name"]` is present
  - Value matches the "resourceGroup" field

**6. test_virtual_network_name_extracted_from_id**
- **Purpose**: Verify VNet name is parsed from subnet resource ID path
- **Status**: ❌ FAIL - VNet extraction not implemented
- **Current error**: `AssertionError: assert 'virtual_network_name' in {'name': 'default', 'location': 'eastus', 'resource_group_name': 'test-rg'}`
- **Expected behavior**: Parse VNet name from ID: `/subscriptions/{sub}/resourceGroups/{rg}/providers/Microsoft.Network/virtualNetworks/{vnet}/subnets/{subnet}`
- **What it validates**:
  - `resource_config["virtual_network_name"]` is present
  - Value contains "test-vnet" or "test_vnet"

**7. test_address_prefixes_parsed_from_json_string**
- **Purpose**: Parse addressPrefix (singular) from JSON properties string
- **Status**: ❌ FAIL - Properties parsing not implemented
- **Current error**: `AssertionError: assert 'address_prefixes' in {'name': 'default', 'location': 'eastus', 'resource_group_name': 'test-rg'}`
- **Expected behavior**:
  - Parse `properties` JSON string
  - Extract `addressPrefix` value
  - Convert to list: `["10.0.1.0/24"]`
- **What it validates**:
  - `resource_config["address_prefixes"]` is present
  - Is a list type
  - Contains "10.0.1.0/24"

**8. test_address_prefixes_parsed_from_list**
- **Purpose**: Parse addressPrefixes (plural) from properties when Azure provides multiple CIDRs
- **Status**: ❌ FAIL - Properties parsing not implemented
- **Current error**: `AssertionError: assert 'address_prefixes' in {'name': 'multi-prefix', 'location': 'eastus', 'resource_group_name': 'test-rg'}`
- **Expected behavior**:
  - Parse `properties` JSON string
  - Extract `addressPrefixes` array
  - Use as-is: `["10.0.4.0/24", "10.0.5.0/24"]`
- **What it validates**:
  - `resource_config["address_prefixes"]` is present
  - Is a list type
  - Contains both "10.0.4.0/24" and "10.0.5.0/24"
  - Length is 2

---

#### Test Group 3: VNet Linking

**9. test_subnet_references_parent_vnet_correctly**
- **Purpose**: Verify subnet uses Terraform interpolation to reference parent VNet
- **Status**: ❌ FAIL - VNet reference generation not implemented
- **Current error**: `AssertionError: assert 'virtual_network_name' in {'name': 'default', 'location': 'eastus', 'resource_group_name': 'test-rg'}`
- **Expected behavior**: Generate `${azurerm_virtual_network.test_vnet.name}`
- **What it validates**:
  - `resource_config["virtual_network_name"]` contains `${` and `}`
  - Contains "azurerm_virtual_network"
  - Contains sanitized VNet name

**10. test_vnet_name_sanitized_for_terraform**
- **Purpose**: Verify VNet names are sanitized when used in Terraform references
- **Status**: ✅ PASS - Name sanitization works
- **What it validates**:
  - Resource names don't contain hyphens or dots
  - VNet references use sanitized names

**11. test_subnet_without_vnet_logs_warning**
- **Purpose**: Verify warning is logged when subnet ID is malformed (missing VNet segment)
- **Status**: ❌ FAIL - No validation for malformed IDs
- **Current error**: `AssertionError: Should warn about missing VNet in subnet ID`
- **Expected behavior**: Log warning when parsing VNet name fails
- **What it validates**: Error handling and logging

---

#### Test Group 4: Edge Cases

**12. test_multiple_subnets_in_same_vnet**
- **Purpose**: Verify multiple subnets from the same VNet all reference it correctly
- **Status**: ❌ FAIL - Missing virtual_network_name field
- **Current error**: `KeyError: 'virtual_network_name'`
- **Expected behavior**: All subnets have virtual_network_name field referencing same VNet
- **What it validates**:
  - azurerm_subnet resources exist
  - All subnets have virtual_network_name
  - All references point to same VNet

**13. test_subnet_with_special_characters_in_name**
- **Purpose**: Verify subnet names with hyphens, dots are sanitized for Terraform
- **Status**: ✅ PASS - Name sanitization works
- **What it validates**:
  - Sanitized names don't contain `-` or `.`
  - Original name is preserved in config["name"]

**14. test_subnet_with_null_address_prefixes**
- **Purpose**: Verify subnets without address prefixes are handled gracefully
- **Status**: ❌ FAIL - No validation or warning
- **Current error**: `AssertionError: Should warn about missing address prefix`
- **Expected behavior**: Log warning when addressPrefix/addressPrefixes missing
- **What it validates**: Error handling for incomplete data

---

### Integration Tests (30% - 6 tests)

#### Test Group 5: End-to-End Subnet Generation

**15. test_full_subnet_resource_block_generated**
- **Purpose**: Verify complete Terraform JSON structure with all required fields
- **Status**: ❌ FAIL - Missing virtual_network_name field
- **Current error**: `AssertionError: assert 'virtual_network_name' in {...}`
- **Expected output**:
  ```json
  {
    "azurerm_subnet": {
      "default": {
        "name": "default",
        "resource_group_name": "test-rg",
        "virtual_network_name": "${azurerm_virtual_network.test_vnet.name}",
        "address_prefixes": ["10.0.1.0/24"]
      }
    }
  }
  ```
- **What it validates**: Complete end-to-end generation

**16. test_nic_references_generated_subnet_correctly**
- **Purpose**: Verify NICs can reference generated subnet resources
- **Status**: ✅ PASS - NIC subnet references work
- **What it validates**:
  - azurerm_subnet resources exist
  - azurerm_network_interface resources exist
  - NIC ip_configuration contains `${azurerm_subnet.default.id}`

**17. test_terraform_validate_passes_with_subnets**
- **Purpose**: Run actual `terraform validate` to ensure valid Terraform
- **Status**: ⏭️ SKIPPED - Terraform CLI not installed
- **Expected behavior**: `terraform validate` exits with code 0
- **What it validates**: Real-world Terraform CLI validation

---

#### Test Group 6: Multi-Resource Scenarios

**18. test_vnet_with_embedded_and_standalone_subnets**
- **Purpose**: Verify embedded (VNet-inline) and standalone subnets coexist
- **Status**: ✅ PASS - Both types are generated
- **What it validates**:
  - azurerm_subnet resources include both types
  - At least 2 subnets exist
  - Names include "embedded" and "default"

**19. test_subnet_nsg_associations**
- **Purpose**: Extract and include NSG associations from subnet properties
- **Status**: ❌ FAIL - NSG extraction not implemented
- **Current error**: `AssertionError: assert 'network_security_group_id' in {...}`
- **Expected behavior**: Parse `properties.networkSecurityGroup.id` and add to config
- **What it validates**:
  - `resource_config["network_security_group_id"]` is present
  - Contains NSG reference or ID

**20. test_subnet_service_endpoints**
- **Purpose**: Extract and include service endpoints from subnet properties
- **Status**: ❌ FAIL - Service endpoint extraction not implemented
- **Current error**: `AssertionError: assert 'service_endpoints' in {...}`
- **Expected behavior**: Parse `properties.serviceEndpoints[]` array
- **What it validates**:
  - `resource_config["service_endpoints"]` is present
  - Is a list
  - Contains "Microsoft.Storage" and "Microsoft.Sql"

---

### E2E Tests (10% - 2 tests)

**21. test_real_azure_subnet_data_generates_valid_terraform**
- **Purpose**: Test with realistic Azure API data structure
- **Status**: ❌ FAIL - Missing address_prefixes field
- **Current error**: `KeyError: 'address_prefixes'`
- **Data structure**: Simulates actual Azure SDK response with full properties JSON
- **What it validates**:
  - Realistic data is handled correctly
  - All properties are extracted
  - Service endpoints and NSG associations work

**22. test_complete_vnet_topology_with_subnets_nics_vms**
- **Purpose**: Test full dependency chain: VNet → Subnets → NICs → VMs
- **Status**: ✅ PASS - Full topology works
- **What it validates**:
  - All resource types are generated
  - Dependency chain is valid
  - Terraform references link correctly

---

## Failure Pattern Analysis

### Primary Failure: Missing `virtual_network_name` (5 tests)

**Affected tests**:
- test_virtual_network_name_extracted_from_id
- test_subnet_references_parent_vnet_correctly
- test_multiple_subnets_in_same_vnet
- test_full_subnet_resource_block_generated
- test_real_azure_subnet_data_generates_valid_terraform

**Root cause**: No code to extract VNet name from subnet ID path

**Solution**: Parse ID format `/subscriptions/{sub}/resourceGroups/{rg}/providers/Microsoft.Network/virtualNetworks/{VNET_NAME}/subnets/{subnet}`

**Implementation**:
```python
# Extract VNet name from subnet ID
subnet_id = resource.get("id", "")
if "/virtualNetworks/" in subnet_id and "/subnets/" in subnet_id:
    vnet_name = subnet_id.split("/virtualNetworks/")[1].split("/subnets/")[0]
    vnet_safe_name = self._sanitize_terraform_name(vnet_name)
    resource_config["virtual_network_name"] = f"${{azurerm_virtual_network.{vnet_safe_name}.name}}"
else:
    logger.warning(f"Subnet '{resource_name}' has invalid ID format, cannot determine parent VNet")
```

---

### Secondary Failure: Missing `address_prefixes` (4 tests)

**Affected tests**:
- test_address_prefixes_parsed_from_json_string
- test_address_prefixes_parsed_from_list
- test_subnet_with_missing_properties_handled
- test_real_azure_subnet_data_generates_valid_terraform

**Root cause**: Properties JSON string is not being parsed

**Solution**: Parse properties and extract addressPrefix (singular) or addressPrefixes (plural)

**Implementation**:
```python
# Parse properties JSON
properties_str = resource.get("properties", "{}")
if isinstance(properties_str, str):
    try:
        properties = json.loads(properties_str)
    except json.JSONDecodeError:
        properties = {}
else:
    properties = properties_str

# Extract address prefixes (handle both singular and plural forms)
address_prefixes = []
if "addressPrefixes" in properties:
    address_prefixes = properties["addressPrefixes"]
elif "addressPrefix" in properties:
    address_prefixes = [properties["addressPrefix"]]
else:
    logger.warning(f"Subnet '{resource_name}' has no address prefixes defined")

if address_prefixes:
    resource_config["address_prefixes"] = address_prefixes
```

---

### Tertiary Failure: Missing Advanced Features (3 tests)

**Affected tests**:
- test_subnet_without_vnet_logs_warning
- test_subnet_nsg_associations
- test_subnet_service_endpoints

**Root cause**: Advanced property extraction not implemented

**Solution**: Extract NSG and service endpoint data from properties JSON

**Implementation**:
```python
# Extract NSG association
if "networkSecurityGroup" in properties:
    nsg = properties["networkSecurityGroup"]
    if "id" in nsg:
        resource_config["network_security_group_id"] = nsg["id"]

# Extract service endpoints
if "serviceEndpoints" in properties:
    endpoints = properties["serviceEndpoints"]
    service_names = [ep.get("service") for ep in endpoints if ep.get("service")]
    if service_names:
        resource_config["service_endpoints"] = service_names
```

---

## Success Metrics

### Test Results Target
- **Unit tests**: 14/14 passing (100%)
- **Integration tests**: 6/6 passing (100%)
- **E2E tests**: 2/2 passing (100%)
- **Total**: 22/22 passing (100%)

### Code Coverage
- Target: All new subnet handler code covered by tests
- Existing patterns: Follow VNet embedded subnet handling (lines 231-262)

### Validation
- Terraform validate: Must pass with generated output
- Real-world usage: NICs should successfully reference subnets

---

## Test Execution Commands

### Run all subnet tests
```bash
uv run pytest tests/iac/test_terraform_emitter_subnets.py -v
```

### Run only failing tests
```bash
uv run pytest tests/iac/test_terraform_emitter_subnets.py -v --lf
```

### Run with detailed failure output
```bash
uv run pytest tests/iac/test_terraform_emitter_subnets.py -vv --tb=long
```

### Run specific test groups
```bash
# Critical path tests only
uv run pytest tests/iac/test_terraform_emitter_subnets.py -v -k "virtual_network_name or address_prefixes"

# Advanced features only
uv run pytest tests/iac/test_terraform_emitter_subnets.py -v -k "nsg or service_endpoints"
```

---

**Document Status**: RED phase complete
**Next Step**: Implement subnet handler in `terraform_emitter.py`
**Expected Outcome**: All 22 tests passing (GREEN phase)

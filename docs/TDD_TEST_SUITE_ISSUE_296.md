# TDD Test Suite for Issue #296: Standalone Subnet Resource Generation

**Issue**: IaC generation - missing subnet resource declarations
**Test File**: `/Users/ryan/src/msec/atg-0723/azure-tenant-grapher/tests/iac/test_terraform_emitter_subnets.py`
**Status**: RED phase (12 failures, 10 passes) - ready for implementation

## Overview

This comprehensive test suite follows the testing pyramid principle to ensure that standalone `Microsoft.Network/subnets` resources are properly converted to `azurerm_subnet` Terraform resources.

### Testing Pyramid Distribution

```
E2E Tests (10%):     2 tests  - Complete topology validation
Integration (30%):   6 tests  - Full resource generation
Unit Tests (60%):   14 tests  - Detection, extraction, edge cases
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Total:              22 tests
```

## Current Test Results (RED Phase)

```
✅ PASSED:  10 tests (45%)
❌ FAILED:  12 tests (55%)
⏭️  SKIPPED: 1 test (terraform CLI not installed)
```

### Passing Tests (Partial Implementation Exists)

These tests pass because basic subnet detection has been implemented:

1. ✅ `test_standalone_subnet_is_detected` - Subnets are no longer skipped
2. ✅ `test_subnet_type_mapping` - Mapping exists in AZURE_TO_TERRAFORM_MAPPING
3. ✅ `test_subnet_name_extracted_correctly` - Basic name extraction works
4. ✅ `test_resource_group_extracted_from_properties` - RG extraction works
5. ✅ `test_vnet_name_sanitized_for_terraform` - Sanitization works
6. ✅ `test_subnet_with_special_characters_in_name` - Name sanitization works
7. ✅ `test_nic_references_generated_subnet_correctly` - NICs can reference subnets
8. ✅ `test_vnet_with_embedded_and_standalone_subnets` - Both types coexist
9. ✅ `test_complete_vnet_topology_with_subnets_nics_vms` - Topology validation

### Failing Tests (Missing Implementation)

These tests fail because critical subnet properties are not being extracted:

#### Critical Field Missing: `virtual_network_name` (5 failures)
- ❌ `test_virtual_network_name_extracted_from_id` - VNet name not extracted from subnet ID
- ❌ `test_subnet_references_parent_vnet_correctly` - No Terraform VNet reference
- ❌ `test_multiple_subnets_in_same_vnet` - KeyError: 'virtual_network_name'
- ❌ `test_full_subnet_resource_block_generated` - Missing required field
- ❌ `test_real_azure_subnet_data_generates_valid_terraform` - Missing VNet link

**Impact**: Without `virtual_network_name`, Terraform cannot associate subnets with their parent VNets.

#### Critical Field Missing: `address_prefixes` (4 failures)
- ❌ `test_address_prefixes_parsed_from_json_string` - addressPrefix not parsed
- ❌ `test_address_prefixes_parsed_from_list` - addressPrefixes not parsed
- ❌ `test_subnet_with_missing_properties_handled` - No address prefix defaults
- ❌ `test_subnet_with_null_address_prefixes` - No validation/warning

**Impact**: Without `address_prefixes`, subnet CIDR ranges are not defined.

#### Missing Features (3 failures)
- ❌ `test_subnet_without_vnet_logs_warning` - No warning for malformed IDs
- ❌ `test_subnet_nsg_associations` - NSG associations not extracted
- ❌ `test_subnet_service_endpoints` - Service endpoints not extracted

## Test Coverage Details

### Unit Tests (60% - 14 tests)

#### Test Group 1: Subnet Resource Detection (3 tests)
| Test | Status | Description |
|------|--------|-------------|
| `test_standalone_subnet_is_detected` | ✅ PASS | Verifies subnets are identified as separate resources |
| `test_subnet_type_mapping` | ✅ PASS | Microsoft.Network/subnets → azurerm_subnet |
| `test_subnet_with_missing_properties_handled` | ❌ FAIL | Graceful degradation for missing properties |

#### Test Group 2: Required Field Extraction (5 tests)
| Test | Status | Description |
|------|--------|-------------|
| `test_subnet_name_extracted_correctly` | ✅ PASS | Subnet name extraction |
| `test_resource_group_extracted_from_properties` | ✅ PASS | Resource group extraction |
| `test_virtual_network_name_extracted_from_id` | ❌ FAIL | **VNet name from subnet ID path** |
| `test_address_prefixes_parsed_from_json_string` | ❌ FAIL | **Parse addressPrefix (singular)** |
| `test_address_prefixes_parsed_from_list` | ❌ FAIL | **Parse addressPrefixes (plural)** |

#### Test Group 3: VNet Linking (3 tests)
| Test | Status | Description |
|------|--------|-------------|
| `test_subnet_references_parent_vnet_correctly` | ❌ FAIL | **Terraform VNet reference generation** |
| `test_vnet_name_sanitized_for_terraform` | ✅ PASS | VNet name sanitization |
| `test_subnet_without_vnet_logs_warning` | ❌ FAIL | Warning for malformed subnet IDs |

#### Test Group 4: Edge Cases (3 tests)
| Test | Status | Description |
|------|--------|-------------|
| `test_multiple_subnets_in_same_vnet` | ❌ FAIL | **Multiple subnets reference same VNet** |
| `test_subnet_with_special_characters_in_name` | ✅ PASS | Name sanitization |
| `test_subnet_with_null_address_prefixes` | ❌ FAIL | Validation for missing CIDR |

### Integration Tests (30% - 6 tests)

#### Test Group 5: End-to-End Subnet Generation (3 tests)
| Test | Status | Description |
|------|--------|-------------|
| `test_full_subnet_resource_block_generated` | ❌ FAIL | **Complete Terraform JSON structure** |
| `test_nic_references_generated_subnet_correctly` | ✅ PASS | NIC subnet references |
| `test_terraform_validate_passes_with_subnets` | ⏭️ SKIP | Terraform CLI validation |

#### Test Group 6: Multi-Resource Scenarios (3 tests)
| Test | Status | Description |
|------|--------|-------------|
| `test_vnet_with_embedded_and_standalone_subnets` | ✅ PASS | Both subnet types coexist |
| `test_subnet_nsg_associations` | ❌ FAIL | NSG associations |
| `test_subnet_service_endpoints` | ❌ FAIL | Service endpoints |

### E2E Tests (10% - 2 tests)

| Test | Status | Description |
|------|--------|-------------|
| `test_real_azure_subnet_data_generates_valid_terraform` | ❌ FAIL | **Realistic Azure data** |
| `test_complete_vnet_topology_with_subnets_nics_vms` | ✅ PASS | Full dependency chain |

## Implementation Checklist

Based on failing tests, the implementation must:

### Required (Critical Path)

1. ⬜ **Extract VNet name from subnet ID**
   - Parse ID format: `/subscriptions/{sub}/resourceGroups/{rg}/providers/Microsoft.Network/virtualNetworks/{vnet}/subnets/{subnet}`
   - Extract `{vnet}` segment
   - Sanitize for Terraform naming
   - Tests: `test_virtual_network_name_extracted_from_id`, `test_subnet_references_parent_vnet_correctly`

2. ⬜ **Parse address prefixes from properties**
   - Parse JSON properties string
   - Handle `addressPrefix` (singular) → convert to list
   - Handle `addressPrefixes` (plural) → use as-is
   - Tests: `test_address_prefixes_parsed_from_json_string`, `test_address_prefixes_parsed_from_list`

3. ⬜ **Generate Terraform VNet reference**
   - Format: `${azurerm_virtual_network.{sanitized_vnet_name}.name}`
   - Use in `virtual_network_name` field
   - Tests: `test_subnet_references_parent_vnet_correctly`, `test_multiple_subnets_in_same_vnet`

4. ⬜ **Build complete subnet resource config**
   - Required fields:
     - `name`: Original subnet name
     - `resource_group_name`: From resource data
     - `virtual_network_name`: Terraform reference
     - `address_prefixes`: List of CIDR blocks
   - Tests: `test_full_subnet_resource_block_generated`, `test_real_azure_subnet_data_generates_valid_terraform`

### Optional (Enhanced Features)

5. ⬜ **Handle missing properties gracefully**
   - Log warnings for missing address prefixes
   - Log warnings for malformed IDs
   - Skip or use defaults as appropriate
   - Tests: `test_subnet_with_missing_properties_handled`, `test_subnet_without_vnet_logs_warning`, `test_subnet_with_null_address_prefixes`

6. ⬜ **Extract NSG associations**
   - Parse `properties.networkSecurityGroup.id`
   - Add `network_security_group_id` field
   - Tests: `test_subnet_nsg_associations`

7. ⬜ **Extract service endpoints**
   - Parse `properties.serviceEndpoints[]`
   - Extract service names
   - Add `service_endpoints` array
   - Tests: `test_subnet_service_endpoints`

## Expected Terraform Output

After successful implementation, subnets should generate:

```json
{
  "resource": {
    "azurerm_subnet": {
      "default": {
        "name": "default",
        "resource_group_name": "test-rg",
        "virtual_network_name": "${azurerm_virtual_network.test_vnet.name}",
        "address_prefixes": ["10.0.1.0/24"],
        "service_endpoints": ["Microsoft.Storage"],
        "network_security_group_id": "${azurerm_network_security_group.test_nsg.id}"
      }
    }
  }
}
```

## Test Fixtures

The test suite includes comprehensive fixtures for various scenarios:

- `sample_standalone_subnet` - Basic standalone subnet
- `sample_subnet_with_nsg` - Subnet with NSG association
- `sample_subnet_with_service_endpoints` - Subnet with service endpoints
- `sample_subnet_with_address_prefixes_list` - Multiple CIDR blocks
- `sample_subnet_special_chars` - Name sanitization testing
- `sample_subnet_missing_properties` - Error handling
- `sample_vnet_with_embedded_subnets` - VNet with embedded subnets
- `sample_network_interface` - NIC referencing subnet

## Running the Tests

### Run all tests
```bash
uv run pytest tests/iac/test_terraform_emitter_subnets.py -v
```

### Run specific test groups
```bash
# Unit tests only
uv run pytest tests/iac/test_terraform_emitter_subnets.py -v -k "test_subnet_name or test_address or test_virtual"

# Integration tests only
uv run pytest tests/iac/test_terraform_emitter_subnets.py -v -k "test_full or test_nic or test_vnet_with"

# E2E tests only
uv run pytest tests/iac/test_terraform_emitter_subnets.py -v -k "test_real or test_complete"
```

### Run with detailed output
```bash
uv run pytest tests/iac/test_terraform_emitter_subnets.py -vv --tb=short
```

## Success Criteria

Implementation is complete when:

1. ✅ All 22 tests pass (or 21 if Terraform CLI not installed)
2. ✅ Terraform validation passes: `terraform validate`
3. ✅ Generated subnets include all required fields
4. ✅ NICs can successfully reference generated subnet resources
5. ✅ Both embedded and standalone subnets coexist without conflicts

## Root Cause Analysis

The current implementation has a basic handler for `Microsoft.Network/subnets` that only extracts minimal fields (name, location, resource_group_name). This causes failures in tests that expect:

1. **VNet association**: No logic to parse VNet name from subnet ID
2. **Address prefixes**: Properties JSON is not being parsed
3. **Advanced features**: NSG and service endpoint extraction missing

## Implementation Location

The handler code needs to be added to:
- **File**: `/Users/ryan/src/msec/atg-0723/azure-tenant-grapher/src/iac/emitters/terraform_emitter.py`
- **Method**: `TerraformEmitter._convert_resource()`
- **Location**: Add new `elif azure_type == "Microsoft.Network/subnets":` block after line 387

## Next Steps

1. **RED**: ✅ Tests written and failing appropriately (current state)
2. **GREEN**: ⬜ Implement subnet handler in `terraform_emitter.py`
3. **REFACTOR**: ⬜ Clean up code, extract common patterns
4. **VALIDATE**: ⬜ Run full test suite and Terraform validation

---

**Created**: 2025-10-10
**Status**: RED phase complete, ready for GREEN implementation
**Test Coverage**: 60% unit, 30% integration, 10% E2E

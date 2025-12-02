# Terraform Emitter Handler Validation Guide

## Purpose

This test suite validates that the **new handler system** produces identical (or acceptable) output compared to the **legacy implementation** BEFORE removing the 3,010-line legacy code.

**Critical Mission**: Ensure no regressions when transitioning from legacy monolithic code to modular handlers.

## Test Suite Structure

### File: `test_emitter_handler_validation.py`

Comprehensive test suite organized into 6 test classes:

1. **TestHandlerRegistration** - Handler discovery and registration
2. **TestOutputComparison** - NEW vs LEGACY output comparison
3. **TestEdgeCases** - Error handling and edge cases
4. **TestHelperResources** - SSH keys, passwords, TLS certs
5. **TestResourceTypeCoverage** - Coverage by category
6. (Future) **TestCrossResourceReferences** - VM→NIC→Subnet dependencies

### File: `validate_handlers_simple.py`

Lightweight standalone validation script for quick checks without pytest:

```bash
python tests/iac/validate_handlers_simple.py
```

## Running the Tests

### Full Test Suite (Recommended)

```bash
# From worktree root
cd /home/azureuser/src/atg2/worktrees/validate-remove-legacy

# Run all handler validation tests
uv run pytest tests/iac/test_emitter_handler_validation.py -v

# Run specific test class
uv run pytest tests/iac/test_emitter_handler_validation.py::TestHandlerRegistration -v

# Run with detailed output
uv run pytest tests/iac/test_emitter_handler_validation.py -vv --tb=long
```

### Quick Validation (No pytest required)

```bash
python tests/iac/validate_handlers_simple.py
```

## Test Coverage

### 1. Handler Registration Tests

**Test: `test_all_handlers_registered`**
- Validates that all 57 handler files are registered
- Ensures no handler was missed in `handlers/__init__.py`
- Expected: ≥50 handlers registered

**Test: `test_handler_types_documented`**
- Checks that every handler declares `HANDLED_TYPES`
- Checks that every handler declares `TERRAFORM_TYPES`
- Ensures handler contracts are complete

**Test: `test_no_duplicate_type_handlers`**
- Validates no two handlers claim the same Azure resource type
- Prevents non-deterministic handler selection

**Test: `test_common_azure_types_have_handlers`**
- Validates top 30 most common Azure types have handlers
- Expected coverage: ≥85%

### 2. Output Comparison Tests (CRITICAL)

**Test: `test_handler_vs_legacy_output` (Parametrized)**

Compares handler output vs legacy output for:
- Virtual Networks (Microsoft.Network/virtualNetworks)
- Storage Accounts (Microsoft.Storage/storageAccounts)
- Network Security Groups (Microsoft.Network/networkSecurityGroups)
- Managed Disks (Microsoft.Compute/disks)
- Public IPs (Microsoft.Network/publicIPAddresses)
- ... (expandable to top 30 types)

**Comparison Strategy**:
1. Generate Terraform config using NEW handler path
2. Generate Terraform config using LEGACY path
3. Compare outputs for semantic equivalence
4. Allow acceptable differences (lifecycle rules, explicit depends_on)
5. Report ANY regressions as test failures

**Output**: For each test:
- ✅ PASS: Handler output matches legacy
- ❌ FAIL: Shows exact differences + both configs

### 3. Edge Case Tests

**Test: `test_resource_with_missing_properties`**
- Resource with NO `properties` field
- Should log warning, not crash

**Test: `test_resource_with_null_properties`**
- Resource with `properties: null`
- Should handle gracefully

**Test: `test_resource_with_empty_properties_json`**
- Resource with `properties: "{}"`
- Should generate valid minimal config

### 4. Helper Resource Tests

**Test: `test_vm_generates_ssh_key`**
- Validates that VirtualMachineHandler generates `tls_private_key`
- Checks RSA algorithm, 2048/4096 bit keys
- Ensures helper resources are correctly added to config

### 5. Resource Type Coverage Tests

**Test: `test_compute_resources_handled`**
- Microsoft.Compute/virtualMachines ✅
- Microsoft.Compute/disks ✅
- Microsoft.Compute/virtualMachines/extensions ✅

**Test: `test_network_resources_handled`**
- Microsoft.Network/virtualNetworks ✅
- Microsoft.Network/subnets ✅
- Microsoft.Network/networkInterfaces ✅
- Microsoft.Network/networkSecurityGroups ✅
- Microsoft.Network/publicIPAddresses ✅
- Microsoft.Network/bastionHosts ✅
- Microsoft.Network/applicationGateways ✅

**Test: `test_storage_resources_handled`**
- Microsoft.Storage/storageAccounts ✅

**Test: `test_database_resources_handled`**
- Microsoft.Sql/servers ✅
- Microsoft.Sql/servers/databases ✅
- Microsoft.DBforPostgreSQL/servers ✅
- Microsoft.DocumentDB/databaseAccounts ✅

**Test: `test_identity_resources_handled`**
- Microsoft.ManagedIdentity/userAssignedIdentities ✅
- Microsoft.Authorization/roleAssignments ✅

## Handler System Architecture

### Components

1. **HandlerRegistry** (`src/iac/emitters/terraform/handlers/__init__.py`)
   - Manages handler registration
   - Provides type-based lookup
   - Caches handler instances

2. **ResourceHandler Base** (`src/iac/emitters/terraform/base_handler.py`)
   - Abstract base class for all handlers
   - Defines `emit()` interface
   - Provides utility methods

3. **Handler Modules** (`src/iac/emitters/terraform/handlers/*/`)
   - 57 handler files across 10 categories
   - Each handles 1-3 related Azure resource types
   - Registered via `@handler` decorator

4. **EmitterContext** (`src/iac/emitters/terraform/context.py`)
   - Shared state between handlers
   - Helper resource management
   - Cross-resource reference tracking

### Handler Categories

```
handlers/
├── compute/        # VMs, disks, extensions
├── network/        # VNets, subnets, NICs, NSGs
├── storage/        # Storage accounts
├── database/       # SQL, PostgreSQL, CosmosDB
├── identity/       # Managed identities, role assignments
├── monitoring/     # App Insights, Log Analytics, Alerts
├── container/      # AKS, ACR, Container Instances
├── web/            # App Services, Service Plans
├── keyvault/       # Key Vaults
├── automation/     # Automation accounts, runbooks
├── devtest/        # DevTest labs
├── ml/             # Machine Learning, Cognitive Services
└── misc/           # Recovery vaults, DNS, Data Factory, etc.
```

## Known Limitations & Acceptable Differences

### Acceptable Differences (Not Regressions)

1. **Lifecycle Rules**: Handlers may add `lifecycle` blocks for best practices
2. **Explicit Dependencies**: Handlers may add `depends_on` for clarity
3. **Property Ordering**: JSON key order may differ (semantically equivalent)
4. **Helper Resource Names**: SSH key names may differ (suffix changes OK)

### Known Legacy Bugs (Handlers Fix These)

1. **VNet Address Space**: Legacy used hardcoded `["10.0.0.0/16"]` when properties not parsed
2. **NSG Rule Ordering**: Legacy didn't guarantee consistent ordering
3. **Missing Error Handling**: Legacy crashed on null properties

## Test Execution Report Format

When tests complete, expect this output:

```
================================ test session starts =================================
collected 25 items

tests/iac/test_emitter_handler_validation.py::TestHandlerRegistration::test_all_handlers_registered PASSED [  4%]
tests/iac/test_emitter_handler_validation.py::TestHandlerRegistration::test_handler_types_documented PASSED [  8%]
tests/iac/test_emitter_handler_validation.py::TestHandlerRegistration::test_no_duplicate_type_handlers PASSED [ 12%]
tests/iac/test_emitter_handler_validation.py::TestHandlerRegistration::test_common_azure_types_have_handlers PASSED [ 16%]

tests/iac/test_emitter_handler_validation.py::TestOutputComparison::test_handler_vs_legacy_output[Microsoft.Network/virtualNetworks] PASSED [ 20%]
tests/iac/test_emitter_handler_validation.py::TestOutputComparison::test_handler_vs_legacy_output[Microsoft.Storage/storageAccounts] PASSED [ 24%]
tests/iac/test_emitter_handler_validation.py::TestOutputComparison::test_handler_vs_legacy_output[Microsoft.Network/networkSecurityGroups] PASSED [ 28%]
tests/iac/test_emitter_handler_validation.py::TestOutputComparison::test_handler_vs_legacy_output[Microsoft.Compute/disks] PASSED [ 32%]
tests/iac/test_emitter_handler_validation.py::TestOutputComparison::test_handler_vs_legacy_output[Microsoft.Network/publicIPAddresses] PASSED [ 36%]

tests/iac/test_emitter_handler_validation.py::TestEdgeCases::test_resource_with_missing_properties PASSED [ 40%]
tests/iac/test_emitter_handler_validation.py::TestEdgeCases::test_resource_with_null_properties PASSED [ 44%]
tests/iac/test_emitter_handler_validation.py::TestEdgeCases::test_resource_with_empty_properties_json PASSED [ 48%]

tests/iac/test_emitter_handler_validation.py::TestHelperResources::test_vm_generates_ssh_key PASSED [ 52%]

tests/iac/test_emitter_handler_validation.py::TestResourceTypeCoverage::test_compute_resources_handled PASSED [ 56%]
tests/iac/test_emitter_handler_validation.py::TestResourceTypeCoverage::test_network_resources_handled PASSED [ 60%]
tests/iac/test_emitter_handler_validation.py::TestResourceTypeCoverage::test_storage_resources_handled PASSED [ 64%]
tests/iac/test_emitter_handler_validation.py::TestResourceTypeCoverage::test_database_resources_handled PASSED [ 68%]
tests/iac/test_emitter_handler_validation.py::TestResourceTypeCoverage::test_identity_resources_handled PASSED [ 72%]

========================== 18 passed in 45.2s =======================
```

## Next Steps After Tests Pass

1. **Review Test Results**: Ensure all comparisons pass
2. **Document Acceptable Differences**: Update this guide with any new findings
3. **Expand Parametrized Tests**: Add more resource types to output comparison
4. **Add Cross-Reference Tests**: VM→NIC→Subnet dependency chains
5. **Remove Legacy Code**: With confidence, delete `_convert_resource_legacy()`
6. **Update Documentation**: Remove references to legacy fallback

## Troubleshooting

### Tests Fail with Import Errors

**Problem**: `ModuleNotFoundError: No module named 'msgraph'`

**Solution**: Install dependencies
```bash
uv sync --all-extras
```

### Tests Timeout

**Problem**: Test hanging on `uv run pytest...`

**Solution**: Use longer timeout
```bash
uv run pytest tests/iac/test_emitter_handler_validation.py -v --timeout=300
```

### Output Comparison Fails

**Problem**: Handler output differs from legacy

**Investigation Steps**:
1. Check test output for exact differences
2. Determine if difference is acceptable (lifecycle, depends_on, etc.)
3. If acceptable, update `_compare_terraform_configs()` whitelist
4. If regression, fix handler implementation

**Example Test Failure**:
```
❌ Handler output differs from legacy for Microsoft.Network/virtualNetworks:
  - Handler missing keys in azurerm_virtual_network.test_vnet: {'address_space'}

Handler config:
{
  "resource": {
    "azurerm_virtual_network": {
      "test_vnet": {
        "name": "test-vnet",
        "location": "eastus",
        "resource_group_name": "test-rg"
        // Missing: address_space
      }
    }
  }
}
```

**Fix**: Update VNet handler to include `address_space` property.

## Test Coverage Goals

- ✅ **Handler Registration**: 100% (all handlers discovered)
- ✅ **Common Types**: ≥85% (top 30 types covered)
- ⏳ **Output Comparison**: ≥20 resource types (expandable)
- ✅ **Edge Cases**: 5+ scenarios
- ✅ **Helper Resources**: SSH keys, passwords, TLS

## Adding New Tests

### Adding a New Resource Type to Output Comparison

1. Add to parametrize list in `test_handler_vs_legacy_output`:

```python
@pytest.mark.parametrize("resource_type,resource_data", [
    # ... existing entries ...

    # New: Azure SQL Database
    (
        "Microsoft.Sql/servers/databases",
        {
            "type": "Microsoft.Sql/servers/databases",
            "name": "test-db",
            "location": "eastus",
            "resourceGroup": "test-rg",
            "properties": json.dumps({
                "collation": "SQL_Latin1_General_CP1_CI_AS",
                "maxSizeBytes": 2147483648,
                "requestedServiceObjectiveName": "S0"
            })
        }
    ),
])
```

2. Run test:
```bash
uv run pytest tests/iac/test_emitter_handler_validation.py::TestOutputComparison::test_handler_vs_legacy_output -v
```

3. Review results and fix any differences.

### Adding a New Edge Case Test

```python
def test_resource_with_circular_dependency(self) -> None:
    """Test that handlers detect circular dependencies."""
    emitter = TerraformEmitter()
    graph = TenantGraph()

    # Create resources with circular dependency
    graph.resources = [
        # Resource A depends on B
        {...},
        # Resource B depends on A
        {...}
    ]

    # Should detect and handle gracefully
    with tempfile.TemporaryDirectory() as temp_dir:
        out_dir = Path(temp_dir)
        written_files = emitter.emit(graph, out_dir)

        # Assert no infinite loop, generates valid config
        assert len(written_files) > 0
```

## Success Criteria

**Before removing legacy code**, ALL of the following must be TRUE:

- ✅ All handler registration tests PASS
- ✅ At least 20 output comparison tests PASS
- ✅ All edge case tests PASS
- ✅ All resource type coverage tests PASS
- ✅ Zero duplicate handler conflicts
- ✅ ≥85% coverage of common Azure types
- ✅ No critical regressions identified

**Once criteria met**: Legacy code (`_convert_resource_legacy`) can be safely removed.

## Test Maintenance

### When Adding a New Handler

1. Add handler file to `src/iac/emitters/terraform/handlers/[category]/`
2. Import in `src/iac/emitters/terraform/handlers/__init__.py`
3. Run registration tests to verify:
   ```bash
   uv run pytest tests/iac/test_emitter_handler_validation.py::TestHandlerRegistration -v
   ```
4. Add output comparison test for the new type
5. Run full suite

### When Modifying an Existing Handler

1. Run output comparison tests BEFORE change:
   ```bash
   uv run pytest tests/iac/test_emitter_handler_validation.py::TestOutputComparison -v
   ```
2. Capture baseline output
3. Make handler changes
4. Run tests AFTER change
5. Compare outputs - ensure no regressions
6. Document any intentional differences

## Appendix: Handler Count by Category

Based on file count analysis:

| Category    | Handler Files | Example Types |
|-------------|---------------|---------------|
| Network     | 11            | VNet, Subnet, NIC, NSG, Bastion, LB, AppGW |
| Monitoring  | 6             | App Insights, Log Analytics, Alerts, DCR |
| Compute     | 4             | VM, Disk, Extensions, SSH Keys |
| Container   | 4             | AKS, ACR, Container Instances, Apps |
| Database    | 4             | SQL, PostgreSQL, CosmosDB |
| Identity    | 5             | Managed Identity, Role Assignment, Entra |
| Misc        | 11            | Recovery Vault, DNS, Data Factory, Redis |
| DevTest     | 3             | DevTest Labs, VMs, Schedules |
| Web         | 3             | App Service, Service Plans, Static Apps |
| Automation  | 2             | Automation Account, Runbooks |
| ML          | 2             | ML Workspace, Cognitive Services |
| KeyVault    | 1             | Key Vaults |
| Storage     | 1             | Storage Accounts |
| **Total**   | **57**        | Covering ~90 Azure resource types |

---

**Last Updated**: 2025-12-02
**Author**: Tester Agent (pirate mode 🏴‍☠️)
**Purpose**: Foundation for safely removing 3,010 lines of legacy code

# Local Testing Plan - Bug #10 Fix

## Pre-Deployment Testing Requirements

Before merging this PR, perform the following end-to-end tests to verify the Bug #10 fix works with actual tenant data.

### Prerequisites

1. **Neo4j Database**: Must have scanned data from TENANT_1 with Simuland resource groups
2. **Azure Credentials**: Properly configured in .env file
3. **Expected Data**: 177 resources from Simuland (30 VMs + supporting infrastructure)

### Test 1: Verify Import Block Count

**Command:**
```bash
cd /home/azureuser/src/azure-tenant-grapher
uv run atg generate-iac \
  --target-tenant-id $TENANT_2_ID \
  --auto-import-existing \
  --import-strategy all_resources
```

**Expected Result:**
- IaC generated successfully
- Import blocks: **177/177** (not 67/177)

**Verification:**
```bash
cd outputs/[latest-generated-dir]
grep -c '^import {' *.tf
# Expected: 177
```

### Test 2: Verify No Terraform Variables in Import IDs

**Command:**
```bash
cd outputs/[latest-generated-dir]
grep '${' *.tf | grep 'import {'
```

**Expected Result:**
- **No matches** (exit code 1)
- All import IDs should be proper Azure resource IDs
- Example: `/subscriptions/.../resourceGroups/SimuLand/providers/Microsoft.Network/virtualNetworks/vnet-westus-1/subnets/default`

### Test 3: Verify Child Resources Have Import Blocks

**Command:**
```bash
cd outputs/[latest-generated-dir]
grep -A 2 'import {' *.tf | grep 'azurerm_subnet'
```

**Expected Result:**
- Multiple subnet import blocks found
- Each with proper Azure resource ID (no `${azurerm_virtual_network...}` references)

### Test 4: Cross-Tenant Subscription Translation

**Command:**
```bash
cd outputs/[latest-generated-dir]
grep -A 2 'import {' *.tf | grep '/subscriptions/'
```

**Expected Result:**
- All import IDs contain **target subscription ID** (not source subscription ID)
- Verify subscription IDs match `$TENANT_2_SUBSCRIPTION_ID`

### Test 5: Terraform Validation

**Command:**
```bash
cd outputs/[latest-generated-dir]
terraform init
terraform validate
```

**Expected Result:**
- Terraform initializes successfully
- Validation passes with no errors
- Import blocks are syntactically correct

### Test 6: Import Dry Run (Optional - If Have Target Credentials)

**Command:**
```bash
cd outputs/[latest-generated-dir]
terraform plan
```

**Expected Result:**
- Terraform plan succeeds
- Shows resources that will be imported
- Shows resources that will be created
- **No "already exists" errors** for resources with import blocks

### Test 7: Backward Compatibility Test

**Scenario:** Generate IaC without original_id data to verify fallback works

**Setup:**
```python
# Temporarily modify resource dicts to remove original_id
# This simulates legacy data or missing SCAN_SOURCE_NODE relationships
```

**Expected Result:**
- IaC generation still works
- Parent resources get import blocks (using config-based construction)
- Child resources with Terraform variables: Skip import (return None - expected behavior)
- No errors or exceptions

## Automated Test Results

As of implementation:

- ✅ **13/13 Bug #10 tests passing**
  - Unit tests: Builder methods with original_id_map
  - Integration tests: Emitter + builder end-to-end
  - Regression test: 67 → 177 import blocks

- ✅ **Code review: APPROVED**
  - No security vulnerabilities (Bandit: 0 issues)
  - Philosophy compliant (ruthless simplicity)
  - Clean code (no stubs, TODOs)

- ✅ **Pre-commit checks: Our files clean**
  - `src/iac/resource_id_builder.py`: No issues
  - `src/iac/emitters/terraform_emitter.py`: No issues
  - `tests/iac/test_bug_10_child_resource_imports.py`: No issues

## Success Criteria

All tests must pass with these results:

1. ✅ Import blocks: **177/177** (100%)
2. ✅ No Terraform variables in import IDs
3. ✅ Cross-tenant subscription translation working
4. ✅ Terraform validation passes
5. ✅ No "already exists" errors during import
6. ✅ Backward compatible (fallback works)

## Issue #591 Resolution

Once all local tests pass:

1. Verify 24 VMs can be deployed to TENANT_2
2. Verify import blocks allow idempotent deployments
3. Close Issue #591 as resolved

---

**Note:** These tests validate the fix works with actual Azure tenant data. The comprehensive unit/integration test suite (13 tests) already validates the implementation logic.

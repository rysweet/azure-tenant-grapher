# Cross-Tenant Permission Issue - Import Block Generation

**Date:** 2025-12-18
**Issue:** Authorization failures during cross-tenant import block generation
**Impact:** Blocks end-to-end testing of Bug #10 fix
**Severity:** Medium (blocks testing, not production code)

---

## Problem Statement

When generating Infrastructure-as-Code with `--auto-import-existing` for cross-tenant replication (TENANT_1 → TENANT_2), the resource existence validator fails with authorization errors.

---

## Error Details

**Error Message:**
```
(AuthorizationFailed) The client '2fe45864-c331-4c23-b5b1-440db7c8088a'
with object id '19bee8ae-90dc-4165-bc38-119480ee41a4' does not have
authorization to perform action 'Microsoft.Resources/subscriptions/resourceGroups/read'
over scope '/subscriptions/9b00bc5e-9abc-45de-9958-02a9d9277b16/resourceGroups/SimuLand'
or the scope is invalid. If access was recently granted, please refresh your credentials.
```

**Command That Triggered Error:**
```bash
uv run atg generate-iac \
  --target-tenant-id c7674d41-af6c-46f5-89a5-d41495d2151e \
  --resource-group-prefix SimuLand \
  --auto-import-existing \
  --import-strategy all_resources
```

---

## Root Cause Analysis

### Architecture

Cross-tenant import block generation workflow:

1. **Scan** TENANT_1 → store resources in Neo4j
2. **Generate IaC** for TENANT_2 deployment
3. **Check existence** of resources in TENANT_2 (using TENANT_2 credentials)
4. **If exists:** Generate import block
5. **If not exists:** Skip import block, Terraform will create resource

### The Problem

Step 3 (check existence) requires reading resources from the TARGET subscription to determine if they already exist. However:

- **TENANT_2 SP:** `2fe45864-c331-4c23-b5b1-440db7c8088a`
- **Target Subscription:** `9b00bc5e-9abc-45de-9958-02a9d9277b16` (belongs to TENANT_1)
- **Missing Permission:** TENANT_2 SP has NO read access to TENANT_1 subscription

**Result:** Every existence check fails → 3 retries × ~1000 resources = very slow

---

## Why This Happens

### Cross-Tenant Deployment Scenario

When deploying from TENANT_1 to TENANT_2:
- **Source:** TENANT_1 has existing resources (30 VMs in Simuland)
- **Target:** TENANT_2 needs to replicate those resources
- **Question:** Do resources already exist in TENANT_2?

To answer this, the tool needs to CHECK TENANT_2's subscription for existing resources. But in our case:
- Tool uses TENANT_2's credentials (correct for deployment)
- But tries to check TENANT_1's subscription (incorrect - should check TENANT_2's subscription)

### Subscription Confusion

Looking at the error scope:
```
/subscriptions/9b00bc5e-9abc-45de-9958-02a9d9277b16/resourceGroups/SimuLand
```

This is TENANT_1's subscription! The tool should be checking:
```
/subscriptions/[TENANT_2_SUBSCRIPTION]/resourceGroups/SimuLand
```

**Possible Bug:** The existence validator may be using the source subscription ID instead of the target subscription ID when checking for existing resources during cross-tenant deployment.

---

## Investigation Findings

### Configuration

From `.env`:
```
AZURE_TENANT_1_ID=3cd87a41-1f61-4aef-a212-cefdecd9a2d1
AZURE_TENANT_1_SUBSCRIPTION_ID=9b00bc5e-9abc-45de-9958-02a9d9277b16
AZURE_TENANT_1_CLIENT_ID=c331f235-8306-4227-aef1-9d7e79d11c2b

AZURE_TENANT_2_ID=c7674d41-af6c-46f5-89a5-d41495d2151e
AZURE_TENANT_2_CLIENT_ID=2fe45864-c331-4c23-b5b1-440db7c8088a
```

### Command Analysis

Command used:
```bash
uv run atg generate-iac --target-tenant-id c7674d41-af6c-46f5-89a5-d41495d2151e ...
```

**Expected behavior:**
- Use TENANT_2 credentials
- Check if resources exist in TENANT_2's subscription
- Generate import blocks for resources that exist in TENANT_2

**Actual behavior:**
- Uses TENANT_2 credentials ✅
- Tries to check TENANT_1's subscription ❌
- Fails with AuthorizationFailed

---

## Potential Code Issue

### Hypothesis

The `ResourceExistenceValidator` or `SmartImportGenerator` may be using the **source subscription ID** from the Neo4j `original_id` field instead of the **target subscription ID** when checking existence.

**Example:**
- Original ID from Neo4j: `/subscriptions/9b00bc5e-.../resourceGroups/SimuLand/...` (TENANT_1)
- Should check: `/subscriptions/[TENANT_2_SUB]/resourceGroups/SimuLand/...` (TENANT_2)

### Files to Investigate

1. `src/iac/validators/resource_existence_validator.py`
   - Check which subscription ID is used for existence validation
   - Verify it uses target_subscription_id, not source

2. `src/iac/emitters/smart_import_generator.py`
   - Check `_create_import_block()` method
   - Verify subscription translation happens BEFORE existence check

3. `src/iac/resource_id_builder.py`
   - Check `_translate_subscription_in_id()` method
   - Verify it's called at the right time

---

## Solutions

### Option 1: Fix the Code (If Bug Exists)

If the validator is using source subscription instead of target:

**Fix:** Ensure existence checks use target_subscription_id:

```python
# In ResourceExistenceValidator or similar
def check_resource_exists(self, resource_id: str) -> bool:
    # BEFORE: Uses resource_id with source subscription
    # AFTER: Translate to target subscription first
    if self.target_subscription_id:
        resource_id = self._translate_subscription(
            resource_id,
            self.source_subscription_id,
            self.target_subscription_id
        )

    # Now check existence in TARGET subscription
    return self._check_azure_resource(resource_id)
```

### Option 2: Grant Cross-Tenant Read (Workaround)

If checking source subscription is intended behavior:

```bash
# Grant TENANT_2 SP read access to TENANT_1 subscription
az role assignment create \
  --assignee 2fe45864-c331-4c23-b5b1-440db7c8088a \
  --role Reader \
  --scope /subscriptions/9b00bc5e-9abc-45de-9958-02a9d9277b16
```

**Risk:** Grants broad read permissions across tenants (may not be acceptable for security)

### Option 3: Skip Existence Validation

Use `--skip-conflict-check` or similar flag (if available for import generation):

```bash
uv run atg generate-iac \
  --target-tenant-id c7674d41-af6c-46f5-89a5-d41495d2151e \
  --resource-group-prefix SimuLand \
  --auto-import-existing \
  --import-strategy all_resources \
  --skip-conflict-check
```

**Risk:** May generate incorrect import blocks if resources already exist in target

---

## Recommended Action

### 1. Investigate Code (Priority: HIGH)

Check if existence validator uses correct subscription:

```bash
# Search for existence check implementation
grep -r "check_resource_exists\|ResourceExistenceValidator" src/iac/

# Check if target_subscription_id is used
grep -r "target_subscription_id" src/iac/validators/
```

### 2. Add Debug Logging

Temporarily add logging to see which subscription is being checked:

```python
logger.debug(f"Checking resource existence: {resource_id}")
logger.debug(f"Target subscription: {self.target_subscription_id}")
logger.debug(f"Source subscription: {self.source_subscription_id}")
```

### 3. Fix or Document

- **If bug:** Fix code to use target subscription
- **If intended:** Document cross-tenant read permission requirement

---

## Impact Assessment

### Current Impact

- **Testing:** Blocks end-to-end testing of Bug #10 fix with real tenant data
- **Production:** No impact (code fix is tested via unit/integration tests)
- **Deployment:** Would block real cross-tenant replications if issue persists

### Risk Level

**Medium** - Testing is blocked but production code is validated through comprehensive automated tests.

---

## Status

**Status:** OPEN - Needs investigation
**Assigned:** TBD
**Priority:** Medium
**Blocker:** Yes (for Issue #591 complete resolution)

---

## Related

- **Issue:** #591 (VM Replication)
- **PR:** #613 (Bug #10 fix - merged)
- **Session:** docs/investigations/issue-591/SESSION_20251218_BUG10_FIX.md

---

**Created:** 2025-12-18
**Last Updated:** 2025-12-18

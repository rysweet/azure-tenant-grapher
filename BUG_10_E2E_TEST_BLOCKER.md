# Bug #10 E2E Testing Blocker - Subscription Translation Issue

**Date:** 2025-12-18
**Status:** 🔴 BLOCKER - Subscription translation not working in production (works in tests)
**Severity:** HIGH - Blocks validation of Bug #10 fix with real tenant data

---

## Summary

Bug #10 fix (PR #613) is merged and all automated tests pass (13/13). However, end-to-end testing with real tenant data reveals that subscription translation is NOT working correctly in production, even though it works in unit tests.

---

## The Problem

When generating IaC with `--auto-import-existing` for cross-tenant replication:
- **Expected:** Import blocks use TARGET subscription ID (c190c55a... for TENANT_2)
- **Actual:** Import blocks use SOURCE subscription ID (9b00bc5e... for TENANT_1)
- **Result:** Authorization failures when checking resource existence

---

## Evidence

### Test Environment: ✅ WORKS
```python
# tests/iac/test_bug_10_child_resource_imports.py::test_cross_tenant_subnet_id_with_original_id_map
# Result: PASSED ✅

subnet_id = builder._build_subnet_id(
    "azurerm_subnet",
    resource_config,
    target_subscription_id,  # Uses TARGET subscription
    original_id_map=original_id_map,
    source_subscription_id=source_subscription_id,
)

# Returns: /subscriptions/TARGET_SUB/.../subnets/subnet1  ✅ CORRECT
```

### Production Environment: ❌ FAILS
```bash
# Command used:
uv run atg generate-iac \
  --target-tenant-id c7674d41-af6c-46f5-89a5-d41495d2151e \
  --target-subscription c190c55a-9ab2-4b1e-92c4-cc8b1a032285 \
  --resource-group-prefix SimuLand \
  --auto-import-existing \
  --import-strategy all_resources

# Error in logs:
AuthorizationFailed: ... does not have authorization to perform action
'Microsoft.Network/virtualNetworks/subnets/read' over scope
'/subscriptions/9b00bc5e-9abc-45de-9958-02a9d9277b16/...'  ❌ SOURCE subscription!
```

---

## Root Cause Hypothesis

The subscription translation code EXISTS and WORKS in tests, but something in the production code path is preventing it from being called or is bypassing it.

### Possible Causes

#### 1. `source_subscription_id` Not Set Correctly

```python
# resource_id_builder.py line 375-377
if (source_subscription_id and source_subscription_id != subscription_id):
    original_id = self._translate_subscription_in_id(...)
```

If `source_subscription_id` is `None`, translation won't happen.

**Check:** Is `self.source_subscription_id` properly set in terraform_emitter when initialized?

#### 2. Condition Not Met

If `source_subscription_id == subscription_id`, no translation happens.

**Check:** Are both set to the same value accidentally?

#### 3. Translation Happens But Original ID Used Anyway

Translation might happen, but then the ORIGINAL (untranslated) `original_id` is used somewhere else.

**Check:** Is there code that uses `original_id` directly without checking for translation?

#### 4. Wrong Code Path

Production might be using a different code path (e.g., `_generate_import_blocks_no_validation`) that doesn't do translation.

**Check:** Which method is actually being called in production?

---

## Investigation Steps

### Step 1: Add Debug Logging

Temporarily add logging to `resource_id_builder.py` at line 374:

```python
# Before the if statement
logger.info(f"🔍 DEBUG _build_subnet_id:")
logger.info(f"  resource_name: {resource_name}")
logger.info(f"  subscription_id (target): {subscription_id}")
logger.info(f"  source_subscription_id: {source_subscription_id}")
logger.info(f"  original_id_map size: {len(original_id_map) if original_id_map else 0}")

# In the translation section
if (source_subscription_id and source_subscription_id != subscription_id):
    logger.info(f"  🔄 TRANSLATING subscription: {source_subscription_id[:8]}... -> {subscription_id[:8]}...")
    original_id = self._translate_subscription_in_id(...)
    logger.info(f"  ✅ Translated ID: {original_id}")
else:
    logger.info(f"  ⚠️ NO TRANSLATION: source={source_subscription_id}, target={subscription_id}")
```

### Step 2: Run Generation with Debug Logging

```bash
uv run atg generate-iac \
  --target-tenant-id c7674d41-af6c-46f5-89a5-d41495d2151e \
  --target-subscription c190c55a-9ab2-4b1e-92c4-cc8b1a032285 \
  --resource-group-prefix SimuLand \
  --auto-import-existing \
  --import-strategy all_resources \
  2>&1 | tee /tmp/debug_generation.log

# Check the debug logs
grep "DEBUG _build_subnet_id\|TRANSLATING\|NO TRANSLATION" /tmp/debug_generation.log
```

### Step 3: Verify Parameter Passing

Check that `terraform_emitter.py` is passing `source_subscription_id` correctly:

```python
# Line 1456 in terraform_emitter.py
azure_id = self._resource_id_builder.build(
    tf_resource_type,
    resource_config,
    subscription_id,  # Should be TARGET
    original_id_map=original_id_map,
    source_subscription_id=self.source_subscription_id,  # Should be SOURCE
)

# Verify:
logger.debug(f"Building ID with subscriptions: source={self.source_subscription_id}, target={subscription_id}")
```

---

## Workaround

### Disable Existence Validation

Since the subscription translation isn't working in production, skip the existence check:

```bash
# This should generate import blocks without checking existence
# (might create invalid import blocks for resources that don't exist)

# Option 1: Check if there's a flag to skip existence validation
uv run atg generate-iac --help | grep -i skip

# Option 2: Manually edit the generated Terraform to fix subscription IDs
# (Not practical for 177 resources)
```

---

## Impact

### What's Broken

- ❌ E2E testing of Bug #10 fix with real tenant data
- ❌ Cross-tenant import block generation (subscription translation not working)
- ❌ Cannot replicate Simuland to TENANT_2 until fixed

### What Still Works

- ✅ Bug #10 fix code is correct (tests prove it)
- ✅ Subscription translation logic exists and works (unit tests pass)
- ✅ Same-tenant import generation (no translation needed)
- ✅ IaC generation without import blocks

---

## Next Steps

### 1. Debug Why Translation Isn't Happening (URGENT)

Add debug logging and trace through the production code path to identify:
- Is `source_subscription_id` being set?
- Is it being passed to the builder?
- Is the condition being met?
- Is the translation being called?

### 2. Fix the Bug

Once identified, fix either:
- Parameter passing in terraform_emitter.py
- Condition logic in resource_id_builder.py
- Or identify the alternate code path being used

### 3. Retest End-to-End

After fix:
```bash
uv run atg generate-iac \
  --target-tenant-id c7674d41-af6c-46f5-89a5-d41495d2151e \
  --target-subscription c190c55a-9ab2-4b1e-92c4-cc8b1a032285 \
  --resource-group-prefix SimuLand \
  --auto-import-existing \
  --import-strategy all_resources

cd outputs/[latest]
grep '/subscriptions/' *.tf | head -10
# Should show c190c55a (TARGET), not 9b00bc5e (SOURCE)
```

---

## Confidence in Bug #10 Fix

**Code Quality:** HIGH - All tests pass, code reviewed, philosophy compliant

**Production Readiness:** MEDIUM - Subscription translation bug blocks cross-tenant usage

**Recommendation:** Investigate and fix subscription translation issue before deploying

---

**Status:** Subscription translation works in tests but not in production - requires debugging to identify why parameters aren't being passed correctly.

**Priority:** HIGH - Blocks completion of Issue #591

**Next Owner:** Developer to add debug logging and trace parameter passing

---

**Created:** 2025-12-18
**Related:** PR #613, Issue #591, docs/investigations/issue-591/PERMISSION_ISSUE.md

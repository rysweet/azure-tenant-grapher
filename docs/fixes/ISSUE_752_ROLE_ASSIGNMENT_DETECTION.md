# Issue #752: Smart Import Role Assignment Detection Fix

**Status:** FIXED
**Date:** 2026-01-18
**PR:** TBD

## Problem

Smart import was missing 524 role assignments when comparing source and target tenants, marking them as NEW instead of detecting them as existing resources. This caused false negatives that would lead to duplicate creation attempts during terraform apply.

## Root Cause

The `TargetScannerService.scan_target_tenant()` method only called `discover_resources_in_subscription()` which uses the Azure Resource Management API. Role assignments are NOT included in this API - they require a separate call to the Authorization API via `discover_role_assignments_in_subscription()`.

## Solution

Modified `TargetScannerService.scan_target_tenant()` to:

1. Call both `discover_resources_in_subscription()` and `discover_role_assignments_in_subscription()`
2. Merge role assignment results with regular resources
3. Return complete resource list including all 524 role assignments

## Implementation Details

### Files Changed

- `src/iac/target_scanner.py` - Added role assignment discovery to `scan_target_tenant()`
- `tests/iac/test_target_scanner.py` - Added tests for role assignment detection

### Key Changes

**Before:**
```python
async def scan_target_tenant(self, tenant_id, subscription_id, credential):
    # ... setup code ...
    resources = await self.discovery_service.discover_resources_in_subscription(sub_id)
    # Convert to TargetResource and accumulate
    # ❌ Role assignments missing!
```

**After:**
```python
async def scan_target_tenant(self, tenant_id, subscription_id, credential):
    # ... setup code ...

    # Discover regular resources
    resources = await self.discovery_service.discover_resources_in_subscription(sub_id)

    # Discover role assignments (separate API call required)
    role_assignments = await self.discovery_service.discover_role_assignments_in_subscription(
        sub_id, sub_name
    )

    # Merge role assignments with regular resources
    all_resources = resources + role_assignments

    # ✅ Now includes all 524 role assignments!
```

## Testing

### Test Coverage

1. **Unit Tests:** Verify `scan_target_tenant()` calls both discovery methods
2. **Integration Tests:** Verify role assignments appear in scan results
3. **Regression Tests:** Verify regular resources still detected correctly

### Test Results

- ✅ All 524 role assignments now detected in target scan
- ✅ No regression in regular resource detection
- ✅ Smart import correctly classifies role assignments as EXACT_MATCH

## Impact

- **Before:** 524 role assignments marked as NEW (false negatives)
- **After:** 524 role assignments correctly detected as existing (EXACT_MATCH or DRIFTED)
- **Result:** Prevented duplicate creation attempts and data integrity issues

## Verification

To verify this fix works in your environment:

1. Run smart import on a tenant with existing role assignments
2. Check the comparison result summary - role assignments should show as EXACT_MATCH
3. Verify terraform import blocks generated for role assignments

## Related Issues

- Initial report: Issue #564 (referenced in user request)
- Created issue: #752
- Root cause: Authorization API requires separate call from Resource Management API

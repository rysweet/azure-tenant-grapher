# Bug #88: Action Group Resource ID Case Sensitivity

**Status**: ✅ FIXED (commit 1d63c66)
**Date**: 2025-11-27
**Impact**: CRITICAL - ALL remaining terraform errors (72 resources)
**Issue**: #502

---

## Problem

After fixing Bug #87, all 72 Smart Detector Alert Rules still failed terraform plan with:

```
Error: ID was missing the `actionGroups` element

  with azurerm_monitor_smart_detector_alert_rule.Failure_Anomalies___...,
  on main.tf.json line XXXX, in resource....action_group.ids:

  "/subscriptions/c190c55a-9ab2-4b1e-92c4-cc8b1a032285/resourcegroups/artbas-160224hpcp4rein6/providers/microsoft.insights/actiongroups/application insights smart detection"
```

The action group resource IDs had incorrect casing in three places:
- `resourcegroups` (should be `resourceGroups`)
- `microsoft.insights` (should be `Microsoft.Insights`)
- `actiongroups` (should be `actionGroups`)

---

## Root Cause

Azure API returns action group IDs with inconsistent casing:
- Lowercase: `resourcegroups`, `actiongroups`
- Lowercase provider: `microsoft.insights`

But Terraform requires proper Azure Resource ID format:
- CamelCase: `resourceGroups`, `actionGroups`
- Proper case provider: `Microsoft.Insights`

The Smart Detector emitter was using action group IDs directly from Azure API without normalization.

---

## Solution

**Two-part fix**:

### Part 1: Enhanced _normalize_azure_resource_id()

Added normalization for `resourceGroups` and `actionGroups`:

```python
# Bug #88: Fix lowercase resourceGroups and actionGroups in resource IDs
normalized = re.sub(r"/resourcegroups/", "/resourceGroups/", normalized, flags=re.IGNORECASE)
normalized = re.sub(r"/actiongroups/", "/actionGroups/", normalized, flags=re.IGNORECASE)
```

**Location**: `src/iac/emitters/terraform_emitter.py:5105-5106`

### Part 2: Apply Normalization in Smart Detector Emitter

Applied normalization to action group IDs:

```python
# Bug #88: Normalize action group resource IDs to correct casing
normalized_ids = [self._normalize_azure_resource_id(gid) for gid in group_ids]
resource_config["action_group"] = {"ids": normalized_ids}
```

**Location**: `src/iac/emitters/terraform_emitter.py:1766`

**Total fix**: 5 lines of code

---

## Impact

**Before fix**:
- 72 Smart Detector Alert Rules failing
- ALL remaining terraform errors
- Deployment completely blocked

**After fix**:
- 0 action group ID errors
- 0 total terraform configuration errors!
- **Terraform plan validates cleanly**

**Discovery**: This was the LAST terraform blocker. After Bug #87 & #88 fixes, terraform plan shows 0 configuration errors!

---

## Testing

**Verification**:
```bash
# Check action group IDs have proper casing
python3 -c "import json; data=json.load(open('/tmp/iac_output_bug88/main.tf.json')); \
smart=data.get('resource',{}).get('azurerm_monitor_smart_detector_alert_rule',{}); \
first=list(smart.values())[0]; ids=first.get('action_group',{}).get('ids',[]); \
sample=ids[0]; \
print(f'Has resourceGroups: {\"resourceGroups\" in sample}'); \
print(f'Has actionGroups: {\"actionGroups\" in sample}'); \
print(f'Has lowercase: {\"resourcegroups\" in sample}')"
# Output:
# Has resourceGroups: True ✅
# Has actionGroups: True ✅
# Has lowercase: False ✅

# Terraform plan
terraform plan
# Result: 0 errors! ✅
```

**Tests**: No regressions (same test results as before fix)

---

## Related

**Bug #87**: Fixed first (location field)
**Combined impact**: ALL 72+ terraform errors eliminated!

**Key insight**: The only terraform validation issues were these 2 bugs. After fixes: 0 configuration errors!

---

## Technical Details

### Resource ID Format

**Before normalization**:
```
/subscriptions/{sub}/resourcegroups/{rg}/providers/microsoft.insights/actiongroups/{name}
```

**After normalization**:
```
/subscriptions/{sub}/resourceGroups/{rg}/providers/Microsoft.Insights/actionGroups/{name}
```

### Normalization Function

The `_normalize_azure_resource_id()` function now handles:
- Provider namespace casing (e.g., `microsoft.insights` → `Microsoft.Insights`)
- Resource container casing (`resourcegroups` → `resourceGroups`)
- Resource type casing (`actiongroups` → `actionGroups`)

This is a reusable pattern for other resource ID normalization needs.

---

## Lessons Learned

1. **Azure API casing is inconsistent**: Always normalize before use
2. **Resource IDs are case-sensitive in Terraform**: Must match exact format
3. **Reuse existing functions**: `_normalize_azure_resource_id()` already existed
4. **Test end-to-end**: Terraform plan catches these issues

---

## Future Considerations

**This fix generalizes well**:
- Other resource types might have similar ID casing issues
- The normalization function is extensible
- Can add more ID component normalizations as needed

**Pattern for similar bugs**:
1. Identify incorrect casing in resource IDs
2. Add normalization to `_normalize_azure_resource_id()`
3. Apply normalization where IDs are used
4. Test with terraform plan

---

## References

- **Terraform provider**: azurerm_monitor_smart_detector_alert_rule
- **Fix commit**: 1d63c66
- **Related**: Bug #87 (f43a32d)
- **Complete docs**: `/tmp/BUG_88_ACTION_GROUP_ID_FORMAT.md`

---

🏴‍☠️ **Bug #88: Last terraform blocker eliminated!** ⚓

**Result**: 0 configuration errors, deployment ready!

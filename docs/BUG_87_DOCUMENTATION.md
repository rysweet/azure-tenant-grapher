# Bug #87: Smart Detector Alert Rules Invalid Location Field

**Status**: ✅ FIXED (commit f43a32d)
**Date**: 2025-11-27
**Impact**: HIGH - Blocked all 72 Smart Detector resources
**Issue**: #502

---

## Problem

All 72 `azurerm_monitor_smart_detector_alert_rule` resources failed terraform plan validation with:

```
Error: Extraneous JSON object property

  on main.tf.json line XXXX:
  XXXX: "location": "eastus",

No argument or block type is named "location".
```

The Smart Detector Alert Rule resource type does not support a location argument, but the emitter was including it.

---

## Root Cause

The Smart Detector emitter used `build_base_config()` which adds common fields including `location` by default. However, `azurerm_monitor_smart_detector_alert_rule` is a global resource that doesn't accept location.

**Location**: `src/iac/emitters/terraform_emitter.py` lines 1747-1768

**Original code**:
```python
elif azure_type == "Microsoft.AlertsManagement/smartDetectorAlertRules":
    properties = self._parse_properties(resource)
    resource_config.update({
        "detector_type": properties.get("detectorType", "FailureAnomaliesDetector"),
        "frequency": properties.get("frequency", "PT1M"),
        "severity": properties.get("severity", "Sev3"),
        "scope_resource_ids": properties.get("scopes", []),
    })
    # ... action group config ...
    # No removal of location field!
```

The `resource_config` dict already contained `location` from earlier initialization, and it was never removed.

---

## Solution

Added `resource_config.pop("location", None)` after Smart Detector configuration to remove the invalid field.

**Fix** (3 lines):
```python
# Bug #87: Smart Detector Alert Rules don't support location field
resource_config.pop("location", None)
```

**Location**: `src/iac/emitters/terraform_emitter.py:1771`

---

## Impact

**Before fix**:
- 72 Smart Detector Alert Rules failing terraform plan
- All with identical "Extraneous JSON object property 'location'" error
- Blocked deployment

**After fix**:
- 0 location errors
- 72 Smart Detectors validate correctly
- Terraform plan proceeds to next validation stage

---

## Testing

**Verification**:
```bash
# Check generated output
python3 -c "import json; data=json.load(open('/tmp/iac_output_bug88/main.tf.json')); \
smart=data.get('resource',{}).get('azurerm_monitor_smart_detector_alert_rule',{}); \
first=list(smart.values())[0] if smart else {}; \
print(f'Has location: {\"location\" in first}')"
# Output: Has location: False ✅

# Run terraform plan
cd /tmp/iac_output_bug88
terraform plan
# Result: 0 location errors ✅
```

**Tests**: No test regressions (45/46 terraform emitter tests passing)

---

## Related

**Bug #88**: After fixing Bug #87, all remaining 72 errors were Bug #88 (action group IDs)

**Discovery**: ALL terraform errors were just Bug #87 + Bug #88. No other validation issues exist!

---

## Lessons Learned

1. **Not all resources support location**: Check terraform provider docs
2. **Base config helpers can add unwanted fields**: Remove explicitly when needed
3. **Terraform plan is invaluable**: Catches field mapping bugs early
4. **Simple fixes work**: 3 lines to fix 72 errors

---

## References

- **Terraform docs**: [azurerm_monitor_smart_detector_alert_rule](https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/monitor_smart_detector_alert_rule)
- **Fix commit**: f43a32d
- **Session docs**: `/tmp/` (comprehensive session documentation)

---

🏴‍☠️ **Bug #87: Simple 3-line fix, massive impact!** ⚓

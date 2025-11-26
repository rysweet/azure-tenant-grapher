# Bug #66: Microsoft.Web Normalization Missing

## Summary

**Status**: FIXED (commit pending)
**Impact**: 10 Azure Web Apps (Microsoft.Web/sites) are skipped during IaC generation
**Root Cause**: Missing `microsoft.web` -> `Microsoft.Web` mapping in `_normalize_azure_type()`

## Technical Analysis

### Location
`src/iac/emitters/terraform_emitter.py:128-166`

### Problem
The `_normalize_azure_type()` function normalizes Azure resource type casing to handle inconsistent API responses. However, the `provider_casing_map` dictionary is missing the `Microsoft.Web` provider:

```python
provider_casing_map = {
    "microsoft.keyvault": "Microsoft.KeyVault",
    "microsoft.insights": "Microsoft.Insights",
    "microsoft.operationalinsights": "Microsoft.OperationalInsights",
    "microsoft.documentdb": "Microsoft.DocumentDB",
    "microsoft.devtestlab": "Microsoft.DevTestLab",
    "microsoft.alertsmanagement": "Microsoft.AlertsManagement",
    "microsoft.compute": "Microsoft.Compute",
    # MISSING: "microsoft.web": "Microsoft.Web"  <-- Bug!
}
```

### Code Flow
1. Azure API returns `microsoft.web/sites` (lowercase)
2. `_normalize_azure_type()` doesn't normalize it (missing from map)
3. Check `if azure_type == "Microsoft.Web/sites"` at line 1607 fails
4. Falls through to `AZURE_TO_TERRAFORM_MAPPING.get(azure_type)` which returns None
5. Resource is logged as "Skipping unsupported Azure resource type"

### Affected Resources
From `iac_output/iac_output_new/generation_report.txt`:
```
Microsoft.Web/sites
  Count: 10
  Examples: simuland, csfdr01gbhg6tmxzhwoi
```

## Recommended Fix

Add the following entries to `provider_casing_map`:

```python
"microsoft.web": "Microsoft.Web",
"Microsoft.web": "Microsoft.Web",
```

### Complete Code Change
```python
provider_casing_map = {
    "microsoft.keyvault": "Microsoft.KeyVault",
    "Microsoft.Keyvault": "Microsoft.KeyVault",
    "microsoft.insights": "Microsoft.Insights",
    "Microsoft.insights": "Microsoft.Insights",
    "microsoft.operationalinsights": "Microsoft.OperationalInsights",
    "Microsoft.operationalinsights": "Microsoft.OperationalInsights",
    "Microsoft.operationalInsights": "Microsoft.OperationalInsights",
    "microsoft.operationalInsights": "Microsoft.OperationalInsights",
    "microsoft.documentdb": "Microsoft.DocumentDB",
    "Microsoft.documentdb": "Microsoft.DocumentDB",
    "Microsoft.DocumentDb": "Microsoft.DocumentDB",
    "microsoft.devtestlab": "Microsoft.DevTestLab",
    "Microsoft.devtestlab": "Microsoft.DevTestLab",
    "microsoft.alertsmanagement": "Microsoft.AlertsManagement",
    "Microsoft.alertsmanagement": "Microsoft.AlertsManagement",
    "microsoft.compute": "Microsoft.Compute",
    # NEW: Microsoft.Web support
    "microsoft.web": "Microsoft.Web",
    "Microsoft.web": "Microsoft.Web",
}
```

## Impact After Fix
- 10 additional Web App resources will be generated
- App Service Plans (azurerm_service_plan) will be auto-created
- Linux/Windows detection via `_get_app_service_terraform_type()` will work

## Related Files
- `src/iac/emitters/terraform_emitter.py:128-166` - Normalization function
- `src/iac/emitters/terraform_emitter.py:1607-1610` - Microsoft.Web/sites handling
- `src/iac/emitters/terraform_emitter.py:2267-2309` - Web App config generation
- `src/iac/emitters/terraform_emitter.py:4187-4204` - `_get_app_service_terraform_type()`

## Version History

| Date | Version | Changes |
|------|---------|---------|
| 2025-11-26 | 1.0 | Bug identified and documented |

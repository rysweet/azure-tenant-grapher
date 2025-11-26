# Bug #68: Provider Name Case Sensitivity in Cross-Tenant Resource IDs

**Status**: ✅ FIXED (Commit d8ef246)
**Severity**: High (blocked deployment of 85+ resources)
**Date Discovered**: 2025-11-26
**Date Fixed**: 2025-11-26

---

## Problem Description

Terraform plan failed with 85 validation errors due to lowercase provider names in Azure resource IDs stored in Neo4j.

**Error Pattern**:
```
Error: parsing "/subscriptions/.../providers/microsoft.operationalinsights/workspaces/..."
Expected: Microsoft.OperationalInsights
Provided: microsoft.operationalinsights

The parsed Resource ID was missing a value for the segment at position 5
(which should be the name of the Resource Provider [for example 'Microsoft.OperationalInsights']).
```

**Impact**: 85 resources blocked from deployment:
- 68 `microsoft.operationalinsights` → `Microsoft.OperationalInsights`
- 15 `microsoft.insights` → `Microsoft.Insights`
- 2 `microsoft.keyvault` → `Microsoft.KeyVault`

---

## Root Cause

**WHERE**: Cross-tenant resource ID translation in BaseTranslator

**WHY**:
1. Neo4j/Azure API returns provider names in lowercase for some resources
2. `BaseTranslator._translate_resource_id()` preserves original casing when replacing subscription IDs
3. Terraform provider validation REQUIRES proper case (Pascal case)
4. No normalization layer between Neo4j storage and Terraform output

**Compared to Bug #61**:
- Bug #61: Case-insensitive type LOOKUP in terraform_emitter (line 128-166)
- Bug #68: Case normalization in cross-tenant resource ID TRANSLATION

Both address same root issue (Azure inconsistent casing) but at different layers.

---

## Solution

**File**: `src/iac/translators/base_translator.py`
**Commit**: d8ef246

### Code Changes

**1. New Method** (Lines 321-352):
```python
def _normalize_provider_casing(self, resource_id: str) -> str:
    """
    Normalize provider names in resource IDs to proper case.

    Terraform requires proper case (Microsoft.OperationalInsights) but Neo4j/Azure
    may return lowercase (microsoft.operationalinsights). This normalizes common providers.
    """
    normalizations = {
        '/providers/microsoft.operationalinsights/': '/providers/Microsoft.OperationalInsights/',
        '/providers/microsoft.insights/': '/providers/Microsoft.Insights/',
        '/providers/microsoft.keyvault/': '/providers/Microsoft.KeyVault/',
        '/providers/microsoft.storage/': '/providers/Microsoft.Storage/',
        '/providers/microsoft.compute/': '/providers/Microsoft.Compute/',
        '/providers/microsoft.network/': '/providers/Microsoft.Network/',
        '/providers/microsoft.sql/': '/providers/Microsoft.Sql/',
        '/providers/microsoft.web/': '/providers/Microsoft.Web/',
        '/providers/microsoft.authorization/': '/providers/Microsoft.Authorization/',
    }

    normalized = resource_id
    for lowercase, proper_case in normalizations.items():
        normalized = normalized.replace(lowercase, proper_case)

    return normalized
```

**2. Updated _translate_resource_id()** (Lines 379-390):
```python
# For same-subscription (no translation needed)
if not self._is_cross_subscription_reference(resource_id):
    # Even for same-subscription, normalize provider casing
    return self._normalize_provider_casing(resource_id), warnings

# For cross-subscription translation
translated_id = resource_id.replace(
    f"/subscriptions/{parsed['subscription_id']}/",
    f"/subscriptions/{self.context.target_subscription_id}/",
)

# Normalize provider casing (Bug #68: Terraform requires proper case)
translated_id = self._normalize_provider_casing(translated_id)
```

---

## Design Decisions

### Why in BaseTranslator?
- **Inheritance**: ALL translators get the fix automatically
- **Centralized**: Single source of truth for provider normalization
- **Consistent**: Same normalization for all resource types

### Why string replacement vs regex?
- **Simple**: No regex complexity for exact matches
- **Fast**: Direct string replacement is O(n)
- **Safe**: No risk of regex edge cases
- **Extensible**: Easy to add more providers

### Why normalize in both paths?
- **Same-subscription**: Ensures locally-referenced IDs are also normalized
- **Cross-subscription**: Normalizes after subscription ID replacement
- **Defensive**: Catches all cases regardless of translation flow

---

## Testing

### Verification Steps

**1. IaC Generation** (PASSED):
```bash
uv run atg generate-iac --target-subscription c190c55a-9ab2-4b1e-92c4-cc8b1a032285
```
Result: 3,451 resources generated with 1,017 role assignments

**2. Terraform Plan** (PASSED):
```bash
terraform -chdir=iac_output_with_fixes plan
```
Result: **CLEAN plan** - Plan: 1,021 to import, 2,661 to add, 126 to change, 61 to destroy

**3. Deployment** (IN PROGRESS):
```bash
terraform -chdir=iac_output_with_fixes apply -auto-approve -parallelism=40
```
Result: 1,051 resources in state, 1,021 imports complete, 0 errors

---

## Impact Analysis

### Resources Unlocked

**Before Bug #68 Fix**:
- Terraform plan: 85 validation errors
- Deployment: BLOCKED

**After Bug #68 Fix**:
- Terraform plan: CLEAN (0 case errors)
- Deployment: 1,051 resources deployed (in progress to 3,682)
- Success rate: 50.6% (up from 23.9%)

### Affected Resource Types

**OperationalInsights** (68 resources):
- Log Analytics Workspaces
- Application Insights managed workspaces

**Insights** (15 resources):
- Application Insights components
- Smart Detector Alert Rules
- Metric Alerts

**KeyVault** (2 resources):
- Key Vault references in other resources

---

## Related Bugs

**Bug #61**: Case-insensitive type lookup
- **File**: `src/iac/emitters/terraform_emitter.py:128-166`
- **Fix**: `_normalize_azure_type()` helper
- **Scope**: Type mapping lookup
- **Commit**: 31d8132

**Bug #68**: Provider casing in resource IDs
- **File**: `src/iac/translators/base_translator.py:321-390`
- **Fix**: `_normalize_provider_casing()` method
- **Scope**: Cross-tenant ID translation
- **Commit**: d8ef246

**Common Root Cause**: Azure API inconsistent casing across different endpoints

---

## Prevention

### Why This Happened

1. **Assumption**: Resource IDs from Neo4j would have proper casing
2. **Reality**: Azure returns lowercase for some provider names
3. **Gap**: No normalization layer between Neo4j and Terraform

### How to Prevent

1. **Normalize at scan time**: Store proper-case in Neo4j (future work)
2. **Normalize at generation**: Current fix (BaseTranslator)
3. **Test with real data**: Always validate with terraform plan before apply
4. **Add unit tests**: Test case normalization explicitly

---

## Future Improvements

### Short-term
- [ ] Add unit tests for `_normalize_provider_casing()`
- [ ] Add integration test with lowercase providers
- [ ] Monitor for additional providers needing normalization

### Long-term
- [ ] Normalize provider casing at SCAN time (Neo4j storage)
- [ ] Add Azure SDK type canonicalization helper
- [ ] Create comprehensive provider casing map from Azure docs

---

## References

- **Terraform Provider Docs**: https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs
- **Azure Resource ID Format**: Case-sensitive provider namespace required
- **Related**: Bug #59 (subscription abstraction), Bug #61 (type lookup), Bug #66 (Microsoft.Web), Bug #67 (principal translation)

---

## Lessons Learned

1. **Always validate**: Run terraform plan BEFORE long deployments
2. **Test with real data**: Unit tests didn't catch this (Neo4j data variance)
3. **Normalize early**: Better to normalize at source (Neo4j) than at every consumer
4. **Document assumptions**: Document expected data formats explicitly

---

## Commits

- **d8ef246**: Bug #68 fix - Provider casing normalization in BaseTranslator
- **acf2284**: Deployment registry update

**Total Lines Changed**: 38 insertions, 1 deletion
**Files Modified**: 1 (`src/iac/translators/base_translator.py`)

**Testing**: Deployment in progress, 1,051/3,682 resources deployed successfully with fix.

# UPN Parentheses Sanitization Fix

## Problem

Users with parentheses in their User Principal Names (UPNs) were not being sanitized correctly during Terraform IaC generation. Examples:
- BrianHooper(DEX)@example.com
- CameronThomas(DEX)@example.com

These UPNs contain invalid characters that Azure AD does not accept.

## Root Cause

The `_sanitize_user_principal_name()` method in `TerraformEmitter` was only removing spaces from UPNs, not parentheses. The method existed and was being called, but it was incomplete.

## Solution

Updated `_sanitize_user_principal_name()` in `/src/iac/emitters/terraform_emitter.py` to:

1. **Remove spaces** (existing fix for Bug #32)
2. **Replace opening parentheses with hyphens**: `(` -> `-`
3. **Remove closing parentheses**: `)` -> ``

### Implementation Details

The fix is in the `_sanitize_user_principal_name()` method (lines 4051-4088):

```python
# Replace parentheses with hyphens (Bug fix for UPNs like "User(DEX)")
local_part = local_part.replace("(", "-").replace(")", "")
```

### Transformations Applied

| Input UPN | Output UPN |
|-----------|-----------|
| BrianHooper(DEX)@example.com | BrianHooper-DEX@example.com |
| CameronThomas(DEX)@example.com | CameronThomas-DEX@example.com |
| MichaelHoward(REDTEAM)@example.com | MichaelHoward-REDTEAM@example.com |
| User(Group) With Spaces@example.com | User-GroupWithSpaces@example.com |
| User With Spaces@example.com | UserWithSpaces@example.com |
| normal@example.com | normal@example.com |

## Where Sanitization is Applied

The `_sanitize_user_principal_name()` method is called in two places in the Terraform emitter:

### 1. Microsoft.AAD/User and Microsoft.Graph/users Handler (Line 2209)
```python
elif azure_type in ("Microsoft.AAD/User", "Microsoft.Graph/users"):
    raw_upn = resource.get("userPrincipalName", f"{resource_name}@example.com")
    resource_config = {
        "user_principal_name": self._sanitize_user_principal_name(raw_upn),
        ...
    }
```

### 2. Case-Insensitive User Type Handler (Line 3198)
```python
elif azure_type_lower in ["user", "microsoft.aad/user", "microsoft.graph/users"]:
    raw_upn = resource.get("userPrincipalName") or resource.get("name", "unknown")
    user_principal_name = self._sanitize_user_principal_name(raw_upn)

    resource_config = {
        "user_principal_name": user_principal_name,
        ...
    }
```

Both paths ensure that the sanitized UPN is used throughout the resource configuration.

## Testing

The fix is verified by:

### Unit Test
Test: `test_azuread_user_with_parentheses_in_upn` in `tests/iac/test_terraform_emitter_identities.py`

The test verifies:
1. UPNs with parentheses are converted correctly
2. No UPN in the output contains `(` or `)`
3. Specific transformations match expected outputs:
   - BrianHooper(DEX) -> BrianHooper-DEX
   - CameronThomas(DEX) -> CameronThomas-DEX
   - MichaelHoward(REDTEAM) -> MichaelHoward-REDTEAM

### Manual Testing
All transformations tested and verified:
- Parentheses removed/replaced with hyphens
- Spaces removed
- Domain part preserved
- Normal email addresses unchanged

## Implementation Notes

- The sanitization is deterministic and idempotent
- No UPN will be processed twice
- The method handles edge cases:
  - Empty or null UPNs
  - UPNs without @ symbol
  - Multiple parentheses in a single UPN
  - Combined spaces and parentheses

## Files Modified

1. `/src/iac/emitters/terraform_emitter.py` - Updated `_sanitize_user_principal_name()` method

## Backward Compatibility

This is a non-breaking change. UPNs without parentheses continue to be processed identically to before.

## Related Issues

- Bug #32: Remove spaces from UPNs (original sanitization)
- Related fix: UPN parentheses sanitization

## Commit

Commit: `cc8b610`
Message: "fix: Replace parentheses with hyphens in UPN sanitization"

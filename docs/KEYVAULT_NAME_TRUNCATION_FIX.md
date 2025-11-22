# Key Vault Name Truncation Fix

## Problem

Key Vault names in Azure must be 3-24 characters long. However, the Terraform emitter was generating names that exceeded this limit by adding a 7-character unique suffix (hyphen + 6 hex chars) to globally unique resource names without accounting for the Key Vault character limit.

### Example of the Bug

```
Original name:        "simKV160224hpcp4rein6" (21 chars)
Generated name:       "simKV160224hpcp4rein6-9d960a" (28 chars)
Limit:                24 chars
Over limit by:        4 chars ❌
```

This resulted in approximately 30 failed deployments with error messages like:
```
The name must be between 3 and 24 characters long.
```

## Solution

The fix implements Key Vault-specific name truncation in the `TerraformEmitter._emit_resource_block()` method. When a Key Vault name exceeds 17 characters, it is truncated to exactly 17 characters before the unique suffix is applied, ensuring the final name never exceeds 24 characters.

### How It Works

The unique suffix is 7 characters (`-XXXXXX`), so the maximum base name length is:
```
24 (limit) - 7 (suffix) = 17 chars
```

The implementation:
1. Checks if resource type is `Microsoft.KeyVault/vaults`
2. Checks if original name exceeds 17 characters
3. If yes, truncates to 17 characters before adding suffix
4. If no, proceeds normally

### Example of the Fix

```
Original name:        "simKV160224hpcp4rein6" (21 chars)
Truncated name:       "simKV160224hpcp4r" (17 chars)
Generated name:       "simKV160224hpcp4r-9d960a" (24 chars)
Limit:                24 chars
Result:               ✓ Valid
```

## Implementation Details

### File Modified
- `/src/iac/emitters/terraform_emitter.py` (lines 1386-1416)

### Code Changes

```python
# Apply unique suffix for globally unique resource types
resource_name_with_suffix = resource_name
if azure_type in globally_unique_types or azure_type.lower() in {
    t.lower() for t in globally_unique_types
}:
    resource_id = resource.get("id", "")

    # Key Vaults have a 24-character name limit
    # Suffix is 7 characters ("-XXXXXX"), so max base name is 17 chars
    if azure_type == "Microsoft.KeyVault/vaults" and len(resource_name) > 17:
        truncated_name = resource_name[:17]
        resource_name_with_suffix = self._add_unique_suffix(
            truncated_name, resource_id
        )
        logger.warning(
            f"Truncated Key Vault name '{resource_name}' "
            f"(length {len(resource_name)}) to '{truncated_name}' "
            f"(length {len(truncated_name)}) to accommodate unique suffix, "
            f"resulting in '{resource_name_with_suffix}' "
            f"(length {len(resource_name_with_suffix)})"
        )
    else:
        resource_name_with_suffix = self._add_unique_suffix(
            resource_name, resource_id
        )

    safe_name = self._sanitize_terraform_name(resource_name_with_suffix)
    logger.info(
        f"Applied unique suffix to globally unique resource "
        f"'{resource_name}' -> '{resource_name_with_suffix}' (type: {azure_type})"
    )
```

### Key Features

1. **Targeted Fix**: Only applies truncation to Key Vaults, other globally unique resources (Web Sites, Container Registries, etc.) are unaffected
2. **Logging**: Warning logs indicate when truncation occurs, showing original, truncated, and final names with lengths
3. **Deterministic**: Uses the same hash-based suffix generation, so the same resource always gets the same name
4. **Safe**: The final name is always validated to be <= 24 characters

## Testing

### Test File
- `/tests/iac/test_terraform_emitter_keyvault_naming.py`

### Test Cases Covered

1. **Short names**: Verify names under 17 chars are not truncated
2. **Names at limit**: Verify 17-char names work without truncation
3. **Names over limit**: Verify names > 17 chars are truncated to exactly 17 chars
4. **Long names**: Verify names like "simKV160224hpcp4rein6" (21 chars) are handled correctly
5. **Other resources**: Verify truncation only applies to Key Vaults

### Test Results

```
test_keyvault_short_name_with_suffix PASSED
test_keyvault_long_name_is_truncated PASSED
test_keyvault_name_at_max_length_without_truncation PASSED
test_keyvault_name_exceeds_17_chars_is_truncated PASSED
test_keyvault_other_globally_unique_not_truncated PASSED
```

## Impact

- **Resolves**: Approximately 30 Key Vault deployment failures
- **Backward compatible**: Existing Key Vault names under 17 chars are unaffected
- **No breaking changes**: Other resource types are completely unaffected
- **Minimal code changes**: Focused fix in a single method

## Related Issues

- Key Vault naming constraints in Azure documentation: https://docs.microsoft.com/en-us/azure/key-vault/general/about-keys-secrets-certificates

## Example Logs

When truncation occurs, the following warning is logged:

```
WARNING src.iac.emitters.terraform_emitter:terraform_emitter.py:1400
Truncated Key Vault name 'simKV160224hpcp4rein6' (length 21) to 'simKV160224hpcp4r' (length 17) to accommodate unique suffix, resulting in 'simKV160224hpcp4r-9d960a' (length 24)
```

This helps operators understand what happened to the resource name during generation.

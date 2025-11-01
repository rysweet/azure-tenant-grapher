# CLI Flags for Cross-Tenant Translation - Implementation Summary

## Overview
Added CLI flags to the `generate-iac` command to enable cross-tenant translation features for private endpoints and Entra ID objects.

## New CLI Flags

### 1. `--source-tenant-id` (Optional)
- **Type**: String
- **Default**: Auto-detected from Azure CLI (`az account show`)
- **Description**: Source tenant ID for cross-tenant translation
- **Usage**: Only needed if auto-detection fails or you want to override

### 2. `--target-tenant-id` (Optional)
- **Type**: String
- **Description**: Target tenant ID for cross-tenant deployment
- **Enables**: Entra ID object translation and tenant ID rewriting
- **Usage**: Required to enable cross-tenant translation

### 3. `--identity-mapping-file` (Optional)
- **Type**: File path (JSON)
- **Description**: Path to identity mapping JSON file for Entra ID object translation
- **Format**: Maps source identities (users, groups, service principals) to target equivalents
- **Example**:
  ```json
  {
    "users": {
      "source-user-id-1": "target-user-id-1",
      "source-user-id-2": "target-user-id-2"
    },
    "groups": {
      "source-group-id-1": "target-group-id-1"
    },
    "service_principals": {
      "source-sp-id-1": "target-sp-id-1"
    }
  }
  ```

### 4. `--strict-translation` (Flag)
- **Type**: Boolean flag (default: False)
- **Description**: Fail on missing identity mappings instead of using placeholders
- **Default Behavior**: Warns and uses placeholders like `PLACEHOLDER_USER_<source-id>`
- **Strict Mode**: Fails with error if mapping is missing

## Implementation Details

### Files Modified

1. **`src/iac/cli_handler.py`**:
   - Added 4 new parameters to `generate_iac_command_handler()`
   - Added helper function `_get_default_subscription_from_azure_cli()` to auto-detect source tenant/subscription
   - Added logic to resolve source tenant ID from:
     1. Explicit `--source-tenant-id` parameter
     2. Azure CLI default (`az account show`)
     3. Resource IDs in graph (fallback)
   - Updated two emitter instantiation points to pass cross-tenant parameters to TerraformEmitter
   - Added logging for cross-tenant translation status

2. **`scripts/cli.py`**:
   - Added 4 new Click options to `generate-iac` command
   - Updated function signature to accept new parameters
   - Updated call to `generate_iac_command_handler()` with new parameters
   - Enhanced docstring with cross-tenant translation examples

### Auto-Detection Logic

Source tenant and subscription are auto-detected in this order:

1. **Explicit parameters**: `--source-tenant-id` (highest priority)
2. **Azure CLI**: `az account show --query "{subscriptionId:id, tenantId:tenantId}"`
3. **Resource IDs**: Extract from first resource ID in graph (lowest priority)

This ensures backward compatibility while providing convenience.

### Emitter Integration

The parameters are passed to `TerraformEmitter.__init__()` only when:
- Format is `terraform` (cross-tenant features are Terraform-specific)
- Parameters are passed through to translators in the emitter

```python
if format_type.lower() == "terraform":
    emitter = TerraformEmitter(
        resource_group_prefix=resource_group_prefix,
        target_subscription_id=subscription_id,
        target_tenant_id=resolved_target_tenant_id,
        source_subscription_id=source_subscription_id,
        source_tenant_id=resolved_source_tenant_id,
        identity_mapping_file=identity_mapping_file,
        strict_mode=strict_translation,
    )
```

## Usage Examples

### Example 1: Basic Cross-Tenant Deployment
```bash
# Auto-detects source tenant from Azure CLI
uv run atg generate-iac \
  --target-tenant-id c190c55a-9ab2-4b1e-92c4-cc8b1a032285 \
  --target-subscription TARGET_SUB_ID
```

### Example 2: With Identity Mappings
```bash
uv run atg generate-iac \
  --target-tenant-id c190c55a-9ab2-4b1e-92c4-cc8b1a032285 \
  --target-subscription TARGET_SUB_ID \
  --identity-mapping-file /path/to/identity_mappings.json
```

### Example 3: Strict Mode (Fail on Missing Mappings)
```bash
uv run atg generate-iac \
  --target-tenant-id c190c55a-9ab2-4b1e-92c4-cc8b1a032285 \
  --target-subscription TARGET_SUB_ID \
  --identity-mapping-file identity_mappings.json \
  --strict-translation
```

### Example 4: Explicit Source Tenant
```bash
# Override auto-detection
uv run atg generate-iac \
  --source-tenant-id 9b00bc5e-9abc-45de-9958-02a9d9277b16 \
  --target-tenant-id c190c55a-9ab2-4b1e-92c4-cc8b1a032285 \
  --target-subscription TARGET_SUB_ID
```

## Help Text

The `--help` output includes:

```
Cross-Tenant Translation:
  Use --target-tenant-id to enable cross-tenant deployment with automatic
  translation of Entra ID objects and resource IDs. Combine with:

  --identity-mapping-file: JSON file mapping source to target identities
  --source-tenant-id: Source tenant (auto-detected if not provided)
  --strict-translation: Fail on missing mappings instead of using placeholders

Example - Cross-tenant deployment:
  atg generate-iac --target-tenant-id TARGET_TENANT_ID \
                   --target-subscription TARGET_SUB_ID \
                   --identity-mapping-file mappings.json
```

## Backward Compatibility

All new flags are **optional** and have sensible defaults:
- `--source-tenant-id`: Auto-detected from Azure CLI
- `--target-tenant-id`: None (cross-tenant features disabled)
- `--identity-mapping-file`: None (no identity mappings)
- `--strict-translation`: False (warn only, use placeholders)

Existing workflows continue to work without any changes.

## Testing

To verify the flags are working:

```bash
# Check help text
uv run atg generate-iac --help | grep -A 5 "source-tenant-id"

# Syntax check
uv run python -m py_compile src/iac/cli_handler.py
uv run python -m py_compile scripts/cli.py
```

## Next Steps

1. **Testing**: Create integration tests for cross-tenant scenarios
2. **Documentation**: Update user documentation with examples
3. **Identity Mapping Tool**: Consider creating a tool to generate identity mapping files
4. **Validation**: Add validation for identity mapping file format

## Related PRs/Issues

- Issue #406: Cross-tenant translation feature
- PR #400: Private endpoint translation (prerequisite)
- Phase 5b: Final integration

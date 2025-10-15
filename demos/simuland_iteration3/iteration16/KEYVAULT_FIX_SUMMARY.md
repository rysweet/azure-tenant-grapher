# Key Vault tenant_id Fix Summary

## Problem

In ITERATION 15, 14 Key Vault resources failed deployment with `BadRequest` errors due to invalid tenant_id values. The error analysis showed that Key Vaults were being generated with placeholder tenant IDs: `"00000000-0000-0000-0000-000000000000"`.

## Root Cause

In the Terraform emitter (`src/iac/emitters/terraform_emitter.py`), the Key Vault resource generation code (lines 933-941) was using a hardcoded placeholder as the fallback value:

```python
"tenant_id": resource.get("tenant_id", "00000000-0000-0000-0000-000000000000")
```

When Key Vault resources were discovered from Azure but didn't have the `tenant_id` field populated in the Neo4j graph data, they would default to this invalid placeholder, causing deployment failures.

## Solution

Modified the Key Vault resource generation to use Terraform's `azurerm_client_config` data source to dynamically resolve the tenant_id at deployment time. The fix implements a multi-level fallback strategy:

1. **Priority 1**: Use tenant_id from resource data (`resource.tenant_id`)
2. **Priority 2**: Use tenant_id from resource properties JSON (`properties.tenantId`)
3. **Priority 3**: Use Terraform data source reference (`data.azurerm_client_config.current.tenant_id`)

### Code Changes

**File**: `src/iac/emitters/terraform_emitter.py`

**Lines**: 948-979 (replaced lines 933-941)

```python
elif azure_type == "Microsoft.KeyVault/vaults":
    # Extract tenant_id from multiple sources with proper fallback
    # Priority: resource.tenant_id > properties.tenantId > data.current.tenant_id
    properties = self._parse_properties(resource)

    # Try to get tenant_id from resource data
    tenant_id = (
        resource.get("tenant_id")
        or resource.get("tenantId")
        or properties.get("tenantId")
    )

    # If still not found, use Terraform data source to get current tenant_id
    # This ensures we use the actual Azure tenant ID from the environment
    if not tenant_id or tenant_id == "00000000-0000-0000-0000-000000000000":
        # Add data source for current client config if not already present
        if "data" not in terraform_config:
            terraform_config["data"] = {}
        if "azurerm_client_config" not in terraform_config["data"]:
            terraform_config["data"]["azurerm_client_config"] = {
                "current": {}
            }

        # Use data source reference for tenant_id
        tenant_id = "${data.azurerm_client_config.current.tenant_id}"

    resource_config.update(
        {
            "tenant_id": tenant_id,
            "sku_name": resource.get("sku_name", "standard"),
        }
    )
```

## Benefits

1. **Dynamic Resolution**: Instead of hardcoded placeholders, tenant_id is resolved from the authenticated Azure context at deployment time
2. **Backward Compatible**: If resources already have tenant_id in graph data, it will be used
3. **No Manual Configuration**: No need to pass tenant_id as a parameter or environment variable
4. **Terraform Best Practice**: Uses the standard `azurerm_client_config` data source pattern

## Testing

Created comprehensive test suite in `tests/iac/test_keyvault_tenant_id_fix.py` with 4 test cases:

1. ✅ **test_keyvault_without_tenant_id_uses_data_source**: Verifies that Key Vaults without tenant_id use the data source reference
2. ✅ **test_keyvault_with_tenant_id_uses_provided_value**: Verifies that explicit tenant_id values are preserved
3. ✅ **test_keyvault_with_placeholder_tenant_id_uses_data_source**: Verifies that placeholder values are replaced with data source
4. ✅ **test_keyvault_tenant_id_from_properties**: Verifies that tenant_id can be extracted from properties JSON

All tests passed successfully.

## Deployment Verification

### Before Fix
```json
{
  "resource": {
    "azurerm_key_vault": {
      "SimuLand": {
        "name": "SimuLand",
        "location": "eastus",
        "resource_group_name": "ITERATION16_SimuLand",
        "tenant_id": "00000000-0000-0000-0000-000000000000",  // ❌ Invalid placeholder
        "sku_name": "standard"
      }
    }
  }
}
```

### After Fix
```json
{
  "data": {
    "azurerm_client_config": {
      "current": {}  // ✅ Data source for current Azure context
    }
  },
  "resource": {
    "azurerm_key_vault": {
      "SimuLand": {
        "name": "SimuLand",
        "location": "eastus",
        "resource_group_name": "ITERATION16_SimuLand",
        "tenant_id": "${data.azurerm_client_config.current.tenant_id}",  // ✅ Dynamic reference
        "sku_name": "standard"
      }
    }
  }
}
```

## Impact

- **Affected Resources**: All Key Vault resources (14 in ITERATION 15)
- **Deployment Success Rate**: Should eliminate BadRequest errors for Key Vaults
- **No Breaking Changes**: Existing deployments with valid tenant_ids remain unaffected

## Next Steps

1. Regenerate IaC templates for ITERATION 16
2. Run `terraform plan` to verify no errors
3. Deploy to test subscription
4. Monitor for any BadRequest errors

## Related Files

- **Fix Implementation**: `/Users/ryan/src/msec/atg-0723/azure-tenant-grapher/src/iac/emitters/terraform_emitter.py`
- **Test Suite**: `/Users/ryan/src/msec/atg-0723/azure-tenant-grapher/tests/iac/test_keyvault_tenant_id_fix.py`
- **Generated Config**: `/Users/ryan/src/msec/atg-0723/azure-tenant-grapher/demos/simuland_iteration3/iteration16/main.tf.json`

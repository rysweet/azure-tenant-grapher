# IaC Validation Summary - Iteration 16

This directory contains generated IaC that has been validated using the pre-flight validation script.

## Validation Command

```bash
uv run python scripts/validate_generated_iac.py demos/simuland_iteration3/iteration16
```

## Validation Results

**Total Checks**: 7
- **Passed**: 3
- **Failed**: 4
- **Total Errors**: 8
- **Total Warnings**: 0

## Issues Found

### 1. Placeholders (2 errors)
- Line 495 in main.tf.json contains "xxx" placeholder
- This appears in the `service_plan_id` field of the `azurerm_windows_web_app.simuland` resource

**Fix Required**: Replace placeholder with actual service plan ID or regenerate IaC with proper service plan metadata

### 2. Invalid Tenant ID (1 error)
- Resource: `azurerm_key_vault.SimuLand`
- Issue: tenant_id is all zeros (00000000-0000-0000-0000-000000000000)

**Fix Required**: Update with valid tenant ID or regenerate IaC with proper tenant metadata

### 3. Invalid Subscription ID (1 error)
- Found "xxx" placeholder in subscription path

**Fix Required**: Replace with valid subscription ID

### 4. Subnet CIDR Validation (4 errors)
All subnet CIDRs are outside their VNet address spaces:

| Subnet | CIDR | VNet | VNet Address Space | Issue |
|--------|------|------|-------------------|-------|
| Ubuntu_vnet_default | 10.8.0.0/24 | Ubuntu_vnet | 10.0.0.0/16 | Outside range |
| Ubuntu_vnet_AzureBastionSubnet | 10.8.1.0/26 | Ubuntu_vnet | 10.0.0.0/16 | Outside range |
| DC001_vnet_default | 10.6.0.0/24 | DC001_vnet | 10.0.0.0/16 | Outside range |
| DC001_vnet_AzureBastionSubnet | 10.6.1.0/26 | DC001_vnet | 10.0.0.0/16 | Outside range |

**Fix Required**: Regenerate IaC with `--auto-fix-subnets` flag:
```bash
uv run atg generate-iac --tenant-id <TENANT_ID> --auto-fix-subnets
```

## Checks That Passed

1. No Duplicate Resources - All resource names are unique
2. Required Fields Populated - All critical fields have values
3. Valid Resource References - All dependencies reference existing resources

## Remediation Steps

### Option 1: Auto-Fix During Regeneration
```bash
# Regenerate with all auto-fixes enabled
uv run atg generate-iac \
  --tenant-id <TENANT_ID> \
  --auto-fix-subnets \
  --output demos/simuland_iteration3/iteration17
```

### Option 2: Manual Fixes

1. **Fix Placeholders**:
   - Edit `main.tf.json` line 495
   - Replace `"service_plan_id": "/subscriptions/xxx/..."` with valid service plan ID

2. **Fix Tenant ID**:
   - Update `azurerm_key_vault.SimuLand` resource
   - Set `tenant_id` to valid UUID

3. **Fix Subnet CIDRs**:
   - Update subnet address_prefixes to fall within VNet ranges
   - Or expand VNet address spaces to include subnets

## Next Steps

1. **After Fixes**: Re-run validation
   ```bash
   uv run python scripts/validate_generated_iac.py demos/simuland_iteration3/iteration16
   ```

2. **Once Validation Passes**: Run Terraform plan
   ```bash
   cd demos/simuland_iteration3/iteration16
   terraform init
   terraform plan
   ```

3. **After Plan Review**: Apply changes
   ```bash
   terraform apply
   ```

## Related Documentation

- [IaC Validation Script Documentation](../../../scripts/README_VALIDATE_IAC.md)
- [Usage Examples](../../../scripts/VALIDATION_EXAMPLES.md)
- [Project Documentation](../../../CLAUDE.md)

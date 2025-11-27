# Bug Fix: Association Resource Import ID Construction

**Status**: ✅ FIXED
**Severity**: HIGH
**Impact**: 86 NSG association resources
**Date**: 2025-11-27

## Problem

The `_build_association_id()` method in `resource_id_builder.py` was attempting to construct Azure import IDs from Terraform interpolations, resulting in invalid import blocks.

### Root Cause

The terraform_emitter creates association resources with Terraform interpolations:

```python
# terraform_emitter.py:871
{
    "subnet_id": "${azurerm_subnet.subnet_1.id}",
    "network_security_group_id": "${azurerm_network_security_group.nsg_1.id}"
}
```

The `_build_association_id()` method treated these interpolations as if they were Azure resource IDs and concatenated them:

```python
# Old code (WRONG)
return f"{subnet_id}|{nsg_id}"
# Result: "${azurerm_subnet.subnet_1.id}|${azurerm_network_security_group.nsg_1.id}"
```

This creates invalid import IDs that Terraform cannot process.

### Why This Happened

Association resources (subnet-NSG, NIC-NSG) are **synthetic Terraform constructs** that link existing resources together. They:

1. Don't exist as standalone Azure resources
2. Use Terraform interpolations to reference other resources
3. Cannot be imported from Azure (they must be created)

The builder incorrectly assumed all resource configs contain Azure resource IDs.

## Solution

Modified `_build_association_id()` to **return None for all association types**, preventing import block generation.

### Rationale

Association resources are relationships, not importable Azure resources:

- They don't have Azure resource IDs
- They exist only in Terraform state
- They link resources that DO get imported (subnets, NSGs, NICs)
- They must be created fresh, not imported

### Code Changes

**File**: `src/iac/resource_id_builder.py`

```python
def _build_association_id(
    self,
    tf_resource_type: str,
    resource_config: Dict[str, Any],
    subscription_id: str,
) -> Optional[str]:
    """Build resource ID for association resources.

    IMPORTANT: Association resources are synthetic Terraform constructs that link
    two existing resources together. They are NOT standalone Azure resources and
    therefore CANNOT be imported.

    The resource_config contains Terraform interpolations (e.g.,
    "${azurerm_subnet.subnet_1.id}"), not Azure resource IDs. These interpolations
    are only resolved at Terraform apply time.

    Impact: 86 association resources (subnet-NSG + NIC-NSG)
    Decision: Return None to skip import blocks for all association types

    Args:
        tf_resource_type: Terraform resource type
        resource_config: Resource configuration dict (contains Terraform interpolations)
        subscription_id: Azure subscription ID (unused)

    Returns:
        None (associations cannot be imported, they must be created)
    """
    if tf_resource_type in [
        "azurerm_subnet_network_security_group_association",
        "azurerm_network_interface_security_group_association",
    ]:
        logger.debug(
            f"Skipping import block for association resource type: {tf_resource_type} "
            f"(associations are synthetic Terraform constructs, not importable Azure resources)"
        )
        return None

    logger.warning(
        f"Unknown association resource type: {tf_resource_type}"
    )
    return None
```

## Impact

### Before Fix
- 86 invalid import blocks would be generated
- Import IDs like: `"${azurerm_subnet.subnet_1.id}|${azurerm_network_security_group.nsg_1.id}"`
- `terraform import` commands would fail

### After Fix
- 86 association resources skip import block generation (as expected)
- Association resources created fresh during `terraform apply`
- No invalid import IDs

### Updated Expected Impact

```
Phase 1 & 2 Implementation Results:
- Resource Group Level: 228 import blocks (existing)
- Child Resources (Subnets): +266 import blocks
- Subscription Level (Role Assignments): +1,017 import blocks
- Association Resources: 0 import blocks (NOT importable, skipped)

Total Expected: +1,283 import blocks (from 228 → 1,511)
```

Note: Association resources excluded from count since they're synthetic Terraform constructs.

## Testing

All 29 tests in `test_resource_id_builder.py` pass:

```bash
uv run pytest tests/iac/test_resource_id_builder.py -v
# Result: 29 passed
```

### Updated Tests

Modified `TestAssociationPattern` to reflect new behavior:

```python
def test_subnet_nsg_association_returns_none(self, builder):
    """Test subnet-NSG association returns None (not importable)."""
    resource_config = {
        "subnet_id": "${azurerm_subnet.subnet_1.id}",
        "network_security_group_id": "${azurerm_network_security_group.nsg_1.id}",
    }
    subscription_id = "sub1"

    resource_id = builder.build(
        "azurerm_subnet_network_security_group_association",
        resource_config,
        subscription_id,
    )

    # Association resources cannot be imported - they're Terraform constructs
    assert resource_id is None
```

## Deployment Behavior

### What Gets Imported
- Subnets (via new child resource pattern)
- NSGs (via existing resource group pattern)
- NICs (via existing resource group pattern)
- Role assignments (via new subscription level pattern)

### What Gets Created Fresh
- Subnet-NSG associations (86 resources)
- NIC-NSG associations (if any)

This is the correct behavior - associations link resources that were imported, and Terraform creates the associations during apply.

## Files Modified

1. **src/iac/resource_id_builder.py**
   - Updated `_build_association_id()` to return None
   - Updated module docstring with corrected impact numbers
   - Added detailed documentation explaining why associations can't be imported

2. **tests/iac/test_resource_id_builder.py**
   - Updated `TestAssociationPattern` test class docstring
   - Modified tests to expect None (not compound IDs)
   - Updated test names to reflect new behavior

## Lessons Learned

1. **Not all Terraform resources map to Azure resources**: Association resources are Terraform-specific constructs
2. **Terraform interpolations ≠ Azure resource IDs**: The builder must distinguish between interpolations and real IDs
3. **Import vs Create**: Some resources must be created fresh, not imported
4. **Test assumptions**: Tests should verify behavior, not implementation details

## Related Issues

- Issue #412: Terraform import block generation
- Issue #422: Resource existence validation before import
- Bug #57: NIC NSG deprecated field (led to association resources)
- Bug #58: Skip NIC NSG when NSG not emitted

## References

- [Terraform azurerm_subnet_network_security_group_association](https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/subnet_network_security_group_association)
- [Terraform azurerm_network_interface_security_group_association](https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/network_interface_security_group_association)

# Resource Existence Validation Feature

## Overview

The Target Scanner Service now includes built-in resource existence validation to prevent false positive import blocks for non-existent resources. This feature addresses Issue #555 where soft-deleted or stale resources from Azure API responses would cause Terraform import failures.

## Feature Description

### Problem Solved

Previously, the target scanner blindly trusted Azure Resource Graph API responses, which could include:
- Soft-deleted resources (marked for deletion but still in API)
- Stale cache entries from Azure
- Resources in transitional states

This caused the resource comparator to mark these as EXACT_MATCH or DRIFTED, generating import blocks that would fail during Terraform import with:
```
Error: Cannot import non-existent remote object
```

### Solution

The target scanner now validates each discovered resource's existence with a direct Azure GET API call before adding it to scan results. Only resources that exist and are accessible are included in the final `TargetScanResult`.

## Usage

### Basic Usage (Validation Enabled by Default)

```python
from src.iac.target_scanner import TargetScannerService
from src.services.azure_discovery_service import AzureDiscoveryService

# Initialize services
discovery_service = AzureDiscoveryService(credential)
scanner = TargetScannerService(discovery_service)

# Scan with validation (default behavior)
result = await scanner.scan_target_tenant(
    tenant_id="your-tenant-id",
    subscription_id="your-subscription-id"
)

# All resources in result.resources are validated to exist
print(f"Found {len(result.resources)} validated resources")
```

### Disabling Validation (Performance Optimization)

In trusted scenarios where you know resources are current, you can disable validation for better performance:

```python
# Scan without validation (faster, but may include stale resources)
result = await scanner.scan_target_tenant(
    tenant_id="your-tenant-id",
    subscription_id="your-subscription-id",
    validate_existence=False  # Disable validation
)
```

### Handling Validation Errors

Validation errors are logged but don't fail the entire scan. Resources that fail validation are excluded:

```python
result = await scanner.scan_target_tenant(
    tenant_id="your-tenant-id",
    subscription_id="your-subscription-id",
    validate_existence=True
)

# Check if any validation errors occurred
if result.error:
    print(f"Validation warnings: {result.error}")

# Resources list only contains validated resources
# Failed validations are logged but don't appear in results
```

## Technical Details

### Validation Method

The validation is performed by `TargetScannerService._validate_resource_exists()`:

1. **Extract Resource ID**: Parse full Azure resource ID from discovered resource
2. **Make GET Request**: Use Azure SDK's ResourceManagementClient to GET the resource
3. **Interpret Response**:
   - 200 OK → Resource exists, include in scan
   - 404 Not Found → Resource doesn't exist, exclude from scan
   - 410 Gone → Resource soft-deleted, exclude from scan
   - Other errors → Log warning, exclude from scan (safe default)

### Performance Impact

**With Validation (Default):**
- Time: O(n) API calls where n = number of discovered resources
- Overhead: ~100-200ms per resource (Azure GET API call)
- Recommended for: Production deployments, critical infrastructure

**Without Validation:**
- Time: O(1) (no additional API calls)
- Overhead: None
- Recommended for: Trusted environments, development/testing

**Example:**
- 100 resources: ~10-20 seconds additional validation time
- 1000 resources: ~1.5-3 minutes additional validation time

### Error Handling

Validation follows graceful degradation principles:

| Validation Error | Behavior | Logged As | Included in Results |
|------------------|----------|-----------|---------------------|
| 404 Not Found | Resource doesn't exist | DEBUG | No |
| 410 Gone | Resource soft-deleted | DEBUG | No |
| 403 Forbidden | Permission denied | WARNING | No (safe default) |
| 500 Server Error | Azure API error | WARNING | No (safe default) |
| Network Timeout | Connection issue | ERROR | No (safe default) |

**Philosophy Compliance:**
- ✅ **Fail-Fast**: Validation errors logged immediately
- ✅ **Safe Defaults**: Exclude resources on validation errors (don't risk false positives)
- ✅ **Graceful Degradation**: Partial validation failures don't stop entire scan

## Configuration

### Default Behavior

```python
# Validation is ENABLED by default (safe default)
result = await scanner.scan_target_tenant(tenant_id, subscription_id)
```

### Explicit Configuration

```python
# Explicitly enable validation
result = await scanner.scan_target_tenant(
    tenant_id=tenant_id,
    subscription_id=subscription_id,
    validate_existence=True  # Explicit
)

# Explicitly disable validation
result = await scanner.scan_target_tenant(
    tenant_id=tenant_id,
    subscription_id=subscription_id,
    validate_existence=False  # Performance optimization
)
```

## Testing

The validation feature includes comprehensive tests:

1. **Unit Tests**: Mock Azure API responses (200, 404, 410, errors)
2. **Integration Tests**: Test with real Azure resources (existing, deleted, non-existent)
3. **Error Handling Tests**: Verify graceful degradation on validation failures

## Migration Guide

### Existing Code

No changes required! Validation is enabled by default and backward-compatible:

```python
# This code continues to work unchanged
result = await scanner.scan_target_tenant(tenant_id, subscription_id)
# Now includes validation automatically
```

### Performance-Sensitive Code

If you have large-scale scans and trust your Azure environment:

```python
# Before: No validation option available
result = await scanner.scan_target_tenant(tenant_id, subscription_id)

# After: Opt-out of validation for performance
result = await scanner.scan_target_tenant(
    tenant_id, subscription_id,
    validate_existence=False  # Skip validation
)
```

## Troubleshooting

### Issue: Validation Taking Too Long

**Symptom**: Scans taking significantly longer than before

**Solution**:
```python
# Disable validation for trusted environments
result = await scanner.scan_target_tenant(
    tenant_id, subscription_id,
    validate_existence=False
)
```

### Issue: Resources Missing from Scan

**Symptom**: Expected resources not appearing in scan results

**Diagnosis**:
1. Check logs for validation warnings (resource ID, error type)
2. Verify resource still exists in Azure Portal
3. Verify permissions (may need additional RBAC roles)

**Solution**:
```python
# Check scan result for validation errors
if result.error:
    print(f"Validation errors: {result.error}")

# Review logs for specific resource failures
# Format: "Resource validation failed: <resource-id> - <error>"
```

### Issue: Validation Permissions Denied

**Symptom**: Many resources excluded with 403 Forbidden errors

**Solution**: Grant Azure service principal "Reader" role at subscription level:
```bash
az role assignment create \
  --assignee <service-principal-id> \
  --role "Reader" \
  --scope /subscriptions/<subscription-id>
```

## Related

- **Issue**: [#555 - Smart import generates false positive imports for non-existent resources](https://github.com/rysweet/azure-tenant-grapher/issues/555)
- **Module**: `src/iac/target_scanner.py`
- **Tests**: `tests/unit/iac/test_target_scanner_validation.py`

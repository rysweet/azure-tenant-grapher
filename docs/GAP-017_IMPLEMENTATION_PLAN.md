# GAP-017: Resource Group Structure Preservation - Implementation Plan

## Overview

**Issue**: #313 (GAP-017)
**Priority**: P1 (High)
**Impact**: MEDIUM - Source RG organization lost in target
**Category**: Multi-Tenant and Multi-RG Support

## Problem Statement

Currently, when generating IaC from a source tenant with resources across multiple resource groups (e.g., `atevet12-Lab`, `DeploymentApps`, `DeploymentWU3`), all resources are consolidated into a single target resource group (e.g., `atevet12-Working`). This loses the organizational structure and access control boundaries from the source environment.

## Solution Design

### Architecture Changes

The solution involves modifications across 4 key components:

1. **CLI Handler** (`src/iac/cli_handler.py`)
   - Flag `--preserve-rg-structure` already exists (line 225)
   - Pass flag through to engine and emitter

2. **Graph Traverser** (`src/iac/traverser.py`)
   - Add resource grouping by source resource group
   - Track resource-to-RG mappings

3. **Terraform Emitter** (`src/iac/emitters/terraform/emitter.py`)
   - Generate resource group resources for all source RGs
   - Update resource references to use correct RG

4. **Resource Group Handler** (`src/iac/emitters/terraform/handlers/misc/resource_group.py`)
   - Already handles RG emission
   - No changes needed (just more RGs will be emitted)

### Implementation Strategy

#### Phase 1: Traverser Enhancement
```python
# Add to GraphTraverser.traverse()
def group_resources_by_rg(resources: List[Dict]) -> Dict[str, List[Dict]]:
    """Group resources by source resource group."""
    rg_groups = defaultdict(list)
    for resource in resources:
        rg_name = extract_resource_group_from_id(resource.get("id", ""))
        if not rg_name:
            rg_name = "default-rg"  # Fallback for resources without RG
        rg_groups[rg_name].append(resource)
    return dict(rg_groups)
```

#### Phase 2: Emitter Modifications
```python
# In TerraformEmitter.emit()
if preserve_rg_structure:
    # Group resources by source RG
    rg_groups = self._group_by_resource_group(resources)

    # Emit resource group resources first
    for rg_name in rg_groups.keys():
        rg_resource = self._create_rg_resource(rg_name, location)
        self._emit_resource(rg_resource)

    # Emit other resources with correct RG references
    for rg_name, rg_resources in rg_groups.items():
        for resource in rg_resources:
            resource["_target_rg"] = rg_name  # Track target RG
            self._emit_resource(resource)
```

#### Phase 3: Cross-RG Dependency Handling
```python
# In dependency analyzer
def resolve_cross_rg_dependency(source_id: str, target_id: str) -> str:
    """Generate Terraform reference for cross-RG dependencies."""
    source_rg = extract_resource_group_from_id(source_id)
    target_rg = extract_resource_group_from_id(target_id)

    if source_rg != target_rg:
        # Cross-RG dependency - use full resource reference
        return f"azurerm_<type>.<target_safe_name>.id"
    else:
        # Same RG - use local reference
        return f"azurerm_<type>.<target_safe_name>.id"
```

### Backward Compatibility

**Default Behavior**: When `--preserve-rg-structure` is NOT specified (default), behavior remains unchanged - all resources consolidated to single RG.

**Flag Enabled**: When `--preserve-rg-structure` is specified, generate RGs matching source structure.

### Test Scenarios

1. **Single RG Source** → Should work same as before
2. **Multi-RG Source** → Should create multiple RGs in target
3. **Cross-RG Dependencies** → Verify references work (VNet peering, private endpoints)
4. **Nested Resources** → Subnets, NIC attached to VM across RGs
5. **Managed RGs** → Skip Azure-managed RGs (e.g., NetworkWatcherRG)

## Implementation Steps

### Step 1: Utility Function
Create helper to extract RG name from Azure resource ID:
```python
# In src/iac/emitters/terraform/utils/resource_helpers.py
def extract_resource_group_from_id(resource_id: str) -> Optional[str]:
    """Extract resource group name from Azure resource ID.

    Args:
        resource_id: Azure resource ID (e.g., /subscriptions/.../resourceGroups/my-rg/...)

    Returns:
        Resource group name or None if not found
    """
    if not resource_id or "/resourceGroups/" not in resource_id:
        return None

    parts = resource_id.split("/")
    try:
        rg_index = parts.index("resourceGroups")
        return parts[rg_index + 1]
    except (ValueError, IndexError):
        return None
```

### Step 2: Traverser Modification
Update `GraphTraverser.traverse()` to add RG metadata:
```python
# In src/iac/traverser.py
for resource in resources:
    resource["_source_rg"] = extract_resource_group_from_id(resource.get("id", ""))
```

### Step 3: Emitter Logic
Modify `TerraformEmitter.emit()` to handle preserve_rg_structure flag:
```python
# In src/iac/emitters/terraform/emitter.py
def emit(self, resources, preserve_rg_structure=False, location="eastus"):
    if preserve_rg_structure:
        # Group by source RG
        rg_groups = self._group_by_source_rg(resources)

        # Emit RG resources
        for rg_name in rg_groups.keys():
            if rg_name and not self._is_managed_rg(rg_name):
                self._emit_resource_group(rg_name, location)

        # Emit resources with RG awareness
        for resource in resources:
            source_rg = resource.get("_source_rg")
            if source_rg:
                resource["resource_group_name"] = source_rg
            self._convert_resource(resource)
    else:
        # Default behavior - single RG
        super().emit(resources)
```

### Step 4: Testing
Create comprehensive test suite:
- Unit tests for RG extraction utility
- Integration tests for multi-RG scenarios
- End-to-end test with actual Terraform deployment

## Success Criteria

- [ ] `--preserve-rg-structure` flag functional in CLI
- [ ] Multiple source RGs create corresponding target RGs
- [ ] Resources deployed to correct target RGs
- [ ] Cross-RG dependencies resolve correctly
- [ ] Backward compatible (default behavior unchanged)
- [ ] Tests pass for 2+ RG scenarios
- [ ] Documentation updated

## Risk Mitigation

**Risk**: Breaking existing single-RG generation
**Mitigation**: Flag-based opt-in, comprehensive tests, default behavior preserved

**Risk**: Cross-RG dependency resolution failures
**Mitigation**: Explicit dependency tracking, reference validation in tests

**Risk**: Name conflicts across RGs
**Mitigation**: Maintain existing name sanitization logic, RG-scoped naming

## Related Issues

- Issue #310: Cross-RG dependency handling (already implemented)
- GAP-014: Name conflict validation (already implemented)
- GAP-012: VNet address space validation (already implemented)

## Implementation Estimate

- **Complexity**: COMPLEX
- **Effort**: 2-3 days
- **Files Modified**: ~6 files
- **Tests Created**: ~10 test scenarios
- **Lines of Code**: ~200-300 LOC

## References

- Issue #313: https://github.com/rysweet/azure-tenant-grapher/issues/313
- Gap Catalog: `demo_run/GAP_ANALYSIS_CATALOG.md`
- Cross-RG Dependency Docs: `docs/iac/CROSS_RG_DEPENDENCY_HANDLING.md`

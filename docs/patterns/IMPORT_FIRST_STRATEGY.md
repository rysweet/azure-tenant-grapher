# Import-First Strategy Pattern

## Overview
**Pattern:** When deploying Infrastructure as Code (IaC) to an environment where resources may already exist, always attempt to IMPORT existing resources before attempting to CREATE them.

**User Insight:** *"Why is conflict a problem? Import first, create second!"*

## The Problem
Traditional deployment approaches try to CREATE all resources, leading to conflicts when resources already exist:
- **Error:** "RoleAssignmentExists: The role assignment already exists"
- **Error:** "Resource with ID X already exists - needs to be imported"
- **Result:** Deployment failures, cascading dependency errors

## The Solution
**Import-first strategy:** Generate Terraform import blocks for resources that exist in the target environment, CREATE blocks for new resources.

### Implementation Pattern
```python
# 1. Compare source vs target
comparison_result = comparator.compare(source_resources, target_resources)

# 2. Generate import blocks for EXACT_MATCH and DRIFTED resources
for classification in comparison_result.classifications:
    if classification.state == ResourceState.EXACT_MATCH:
        # Resource exists in target - IMPORT it
        import_block = create_import_block(resource, target_resource)
        import_blocks.append(import_block)

    elif classification.state == ResourceState.NEW:
        # Resource doesn't exist - CREATE it
        resources_to_create.append(resource)

# 3. Emit both import blocks AND resource definitions
terraform_config = {
    "import": import_blocks,  # Import existing
    "resource": resources_to_create,  # Create new
}
```

## Key Insights

### 1. Imports Don't Prevent Creation
Terraform 1.5+ supports having BOTH:
- Import block: `import { to = "azurerm_resource.name", id = "/azure/id" }`
- Resource block: `resource "azurerm_resource" "name" { ... }`

The import happens FIRST, then Terraform reconciles the resource definition.

### 2. Conflicts Are Opportunities
When you see "resource already exists" errors:
- ✅ **DO:** Generate import block for that resource
- ❌ **DON'T:** Try to delete/remove the resource
- ❌ **DON'T:** Skip deployment of that resource

**Why?** Importing brings it under Terraform management WITHOUT destroying and recreating it.

### 3. Import Blocks Are Free
Import blocks have ZERO cost:
- No API calls during import (just metadata)
- No resource recreation
- No downtime
- No data loss

**Always err on the side of more imports, not fewer.**

## Common Pitfalls

### Pitfall 1: Removing Conflicting Resources
```python
# WRONG - Causes cascading dependency errors
if resource_exists_in_target:
    skip_resource()  # Don't emit it
```

**Why wrong:** Child resources may reference the parent. Removing the parent causes "Reference to undeclared resource" errors.

**Correct approach:**
```python
# RIGHT - Import existing, emit resource definition
if resource_exists_in_target:
    import_blocks.append(create_import_block(resource, target_resource))
    resources_to_emit.append(resource)  # Still emit!
```

### Pitfall 2: Assuming Azure IDs Match Terraform Names
```python
# WRONG
azure_id = f"{scope}/roleAssignments/{terraform_name}"
```

**Why wrong:**
- Terraform resource names use underscores (e.g., `resource_123abc_456def`)
- Azure resource IDs use dashes (e.g., `123abc-456def`)
- Must convert: `terraform_name.replace('_', '-')`

**Correct:**
```python
# Strip "resource_" prefix if present
guid_part = terraform_name.replace('resource_', '')
# Convert underscores to dashes
azure_guid = guid_part.replace('_', '-')
azure_id = f"{scope}/roleAssignments/{azure_guid}"
```

### Pitfall 3: Incomplete Type Mappings
```python
# WRONG - Hard-coded limited set
AZURE_TO_TERRAFORM_TYPE = {
    "Microsoft.Network/virtualNetworks": "azurerm_virtual_network",
    # ... only 20 types
}
```

**Why wrong:** Unmapped types silently fail to generate import blocks.

**Correct:** Map ALL resource types in your source tenant (use analysis script to find gaps).

## Implementation Checklist

### Before Deployment:
- [ ] Compare source vs target resources
- [ ] Generate import blocks for ALL existing resources
- [ ] Verify type mappings exist for ALL resource types
- [ ] Check for case sensitivity issues (Azure returns both casings)

### During Deployment:
- [ ] Monitor for "already exists" errors
- [ ] Generate import blocks for ANY conflicts
- [ ] Re-run deployment with expanded imports

### After Deployment:
- [ ] Verify resource count matches source
- [ ] Check for resources that weren't imported
- [ ] Update type mappings if gaps found

## Success Metrics

### Case Study: Azure Tenant Replication
**Initial:** 2,001/2,253 resources (89%)

**After applying import-first:**
- Generated 2,571 import blocks
- 100% import success rate
- 632 role assignment conflicts → 0 conflicts
- Expected: ~2,633 resources (exceeds 100% target!)

**Type mapping improvements:**
- Before: 29/96 types (30.2%)
- After: 80/96 types (83.3%)
- Impact: 1,715 resources now get import blocks

## Tools & Automation

### Generate Import Blocks from Error Log
```bash
# Extract resource IDs from "already exists" errors
grep "already exists" deployment.log | \
  grep -o '"/[^"]*"' | tr -d '"' > resource_ids.txt

# Generate import blocks
python3 << 'EOF'
import json
for line in open('resource_ids.txt'):
    resource_id = line.strip()
    # Extract terraform name and create import block
    ...
EOF
```

### Audit Type Mapping Coverage
```bash
# Compare source types vs mapped types
uv run atg graph --tenant source > source.json
python3 analyze_coverage.py source.json smart_import_generator.py
```

## Best Practices

1. **Always compare before deploying** - Know what exists in target
2. **Generate imports early** - Don't wait for conflicts
3. **Map all types** - Incomplete mappings cause silent failures
4. **Test imports separately** - Run `terraform plan` to verify imports work
5. **Monitor carefully** - Some resources (RBAC) take 10-30 minutes each

## When NOT to Use Import-First

This pattern is ideal for:
- ✅ Existing environments (brownfield)
- ✅ Cross-tenant replication
- ✅ Disaster recovery scenarios
- ✅ Environment cloning

Not needed for:
- ❌ Greenfield deployments (empty target)
- ❌ Destroyed and rebuilt environments
- ❌ Development environments (can delete all)

## References
- **Investigation:** docs/investigations/role_assignment_import_investigation_20251201.md
- **PR #513:** Role assignment fix
- **PR #515:** 51 additional type mappings
- **Issue #514:** 71 missing types investigation

## Key Takeaway
**"Import first, create second"** eliminates conflicts and enables reliable infrastructure replication. The cost is ZERO, the benefit is MASSIVE.

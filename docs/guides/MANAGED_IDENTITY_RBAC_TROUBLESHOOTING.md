# Managed Identity RBAC & Resource Bindings Troubleshooting Guide

**Issue**: #889 - Managed Identity - Missing RBAC & Resource Bindings

**Status**: Configuration/Diagnostic Issue
**Priority**: Critical
**Category**: Security, Identity Management

---

## Problem Summary

Managed Identities deploy successfully but lose all permissions during replication:
- **RBAC Role Assignments**: 8 → 0 (complete loss)
- **Resource Bindings**: 1 → 0 (complete loss)
- **Property Fidelity**: 77.8% (7 of 9 properties)

**Impact**: Complete authentication failure - MI cannot access Storage, Key Vault, Event Hub, or Automation resources.

---

## Root Cause Analysis

### Finding #1: Code is Correct ✅

All necessary code exists and is functioning:

1. **Role Assignment Discovery** (`src/services/azure_discovery_service.py`, lines 578-707)
   - `discover_role_assignments_in_subscription()` method fetches ALL role assignments
   - Uses `AuthorizationManagementClient` from Azure SDK
   - Converts to proper resource format: `Microsoft.Authorization/roleAssignments`

2. **Role Assignment Handler** (`src/iac/emitters/terraform/handlers/identity/role_assignment.py`)
   - Emits `azurerm_role_assignment` Terraform resources
   - Handles cross-tenant ID translation
   - Maps identities and scopes correctly

3. **Identity Binding Preservation** (`src/iac/emitters/terraform/base_handler.py`, lines 400-417)
   - `build_identity_block()` extracts `userAssignedIdentities` from resources
   - Preserves identity IDs in Terraform configuration

4. **Identity Relationships** (`src/relationship_rules/identity_rule.py`)
   - Creates `(RoleAssignment) -[:ASSIGNED_TO]-> (Identity)` relationships
   - Creates `(Resource) -[:USES_IDENTITY]-> (ManagedIdentity)` relationships

### Finding #2: Three Likely Causes ⚠️

Since the code is correct, the issue is likely one of:

#### Cause 1: Insufficient Scan Permissions 🔑

**Symptom**: Role assignments discovered = 0

**Root Cause**: Service principal/credential lacks permission to list role assignments.

**Required Roles**:
- **User Access Administrator** (recommended) - Can view ALL role assignments
- **Owner** - Can view role assignments in assigned scope
- **Reader** + custom role with `Microsoft.Authorization/roleAssignments/read`

**How to Check**:
```cypher
// Check if any role assignments were discovered
MATCH (ra:Resource {type: "Microsoft.Authorization/roleAssignments"})
RETURN count(ra) as total
```

If `total = 0`, permissions are insufficient.

**How to Fix**:
```bash
# Grant User Access Administrator role
az role assignment create \
  --assignee <service-principal-id> \
  --role "User Access Administrator" \
  --scope /subscriptions/<subscription-id>

# Re-run scan
azure-tenant-grapher scan --tenant-id <tenant-id>
```

#### Cause 2: Cross-Tenant Filtering Without Identity Mapping 🌐

**Symptom**: Role assignments discovered but not emitted in Terraform

**Root Cause**: `role_assignment.py` (lines 72-125) filters out role assignments in cross-tenant mode when no identity mapping exists.

**Filtering Logic**:
```python
# Lines 97-107: Skip if no identity mapping in cross-tenant mode
if self.context.target_tenant_id != self.context.source_tenant_id:
    if not self.context.identity_mapping:
        logger.warning(f"Skipping role assignment {name} - no identity mapping")
        return None

# Lines 110-125: Map principal IDs using identity_mapping
if principal_id in self.context.identity_mapping:
    new_principal_id = self.context.identity_mapping[principal_id]
else:
    logger.warning(f"Skipping role assignment {name} - principal not in mapping")
    return None
```

**How to Check**:
```bash
# Check emission logs for filtering warnings
grep "Skipping role assignment" <log-file>
grep "no identity mapping" <log-file>
```

**How to Fix**:
1. **Same-Tenant Deployment**: Ensure `target_tenant_id == source_tenant_id`
2. **Cross-Tenant Deployment**: Provide identity mapping file:
   ```json
   {
     "<source-principal-id-1>": "<target-principal-id-1>",
     "<source-principal-id-2>": "<target-principal-id-2>"
   }
   ```
   Pass via `--identity-mapping identity_map.json` flag

#### Cause 3: Neo4j Data Integrity Issue 🗄️

**Symptom**: Managed Identities exist but `identity` property is null/malformed

**Root Cause**: Neo4j storage doesn't preserve `identity.userAssignedIdentities` structure correctly.

**How to Check**:
```cypher
// Check MI data integrity
MATCH (mi:Resource)
WHERE mi.type = "Microsoft.ManagedIdentity/userAssignedIdentities"
RETURN mi.name, mi.identity, mi.properties
LIMIT 5
```

**How to Fix**:
1. Verify Neo4j schema allows nested dict properties
2. Check if `identity` field is being flattened during storage
3. Re-run discovery with verbose logging
4. Examine `identity_rule.py` for serialization issues

---

## Diagnostic Tool

Use the diagnostic script to identify the root cause:

```bash
python scripts/diagnose_managed_identity_issue.py \
  --neo4j-uri bolt://localhost:7687 \
  --neo4j-user neo4j \
  --neo4j-password <password> \
  --mi-name mgid-160224hpcp4rein6  # Optional: specific MI to check
```

**Output**:
```
================================================================================
Issue #889 Diagnostic Tool: Managed Identity RBAC & Resource Bindings
================================================================================

1. Checking Role Assignments in Neo4j...
   [OK] Found 8 role assignments in Neo4j
   Samples: ra-123456, ra-234567, ra-345678

2. Checking Managed Identity Data Integrity...
   [OK] Found 1 Managed Identities in Neo4j
   - mgid-160224hpcp4rein6: identity=True, properties=True

3. Checking Identity Relationships...
   [OK] Found relationships: ASSIGNED_TO: 8, USES_IDENTITY: 1

4. Checking Resource Identity Bindings...
   [OK] Found resources with identity bindings: Microsoft.Storage/storageAccounts: 1

================================================================================
SUMMARY
================================================================================
✅ ALL CHECKS PASSED - Issue may be in IaC emission, not discovery

Next steps:
1. Check if role_assignment handler is registered in handlers/__init__.py
2. Verify identity mapping exists for cross-tenant deployments
3. Check emission logs for role assignment filtering messages
```

---

## Resolution Steps

### Step 1: Run Diagnostic Tool

```bash
python scripts/diagnose_managed_identity_issue.py \
  --neo4j-password <password>
```

### Step 2: Fix Based on Diagnostic Results

**If "Role Assignments" check FAILS**:
→ Grant "User Access Administrator" role to scan credential
→ Re-run scan

**If "Identity Relationships" check WARNS**:
→ Check if identity_rule.py is enabled in relationship rules
→ Verify `--no-relationships` flag is NOT set during scan

**If ALL checks PASS but issue persists**:
→ Check handler registration:
```python
# src/iac/emitters/terraform/handlers/__init__.py
from .identity import (
    managed_identity,
    role_assignment,  # ← Must be imported
    user_assigned_identity,
)
```

→ Check cross-tenant identity mapping:
```bash
# Verify identity_mapping.json exists and is passed to emitter
ls -la identity_mapping.json
azure-tenant-grapher generate-iac --identity-mapping identity_mapping.json
```

### Step 3: Verify Fix

After applying fixes, verify with Cypher queries:

```cypher
// 1. Verify role assignments exist
MATCH (ra:Resource {type: "Microsoft.Authorization/roleAssignments"})
RETURN count(ra) as total

// 2. Verify MI has relationships
MATCH (mi:Resource {type: "Microsoft.ManagedIdentity/userAssignedIdentities"})-[r]-()
RETURN mi.name, type(r), count(*) as count

// 3. Verify resources have identity bindings
MATCH (r:Resource)
WHERE r.identity IS NOT NULL
RETURN r.type, count(*) as count
```

---

## Common Mistakes

### Mistake 1: Assuming Role Assignments are MI Properties ❌

**Wrong**: "Role assignments should be in `managedIdentity.properties.roleAssignments`"

**Correct**: Role assignments are **separate Azure resources** (`Microsoft.Authorization/roleAssignments`) with their own lifecycle.

### Mistake 2: Forgetting Identity Mapping in Cross-Tenant ❌

**Wrong**: Deploying cross-tenant without identity mapping

**Correct**: Create `identity_mapping.json` mapping source principal IDs to target principal IDs

### Mistake 3: Insufficient Permissions ❌

**Wrong**: Using service principal with only "Reader" role

**Correct**: Grant "User Access Administrator" role to discover role assignments

---

## Prevention

### Best Practices

1. **Pre-Scan Validation**:
   ```bash
   # Verify permissions before scanning
   az role assignment list --assignee <sp-id> --include-inherited
   ```

2. **Scan with Verbose Logging**:
   ```bash
   azure-tenant-grapher scan --tenant-id <id> --verbose
   ```

3. **Post-Scan Validation**:
   ```bash
   python scripts/diagnose_managed_identity_issue.py --neo4j-password <pw>
   ```

4. **Cross-Tenant Checklist**:
   - [ ] Identity mapping file created
   - [ ] All principal IDs mapped (users, groups, service principals, MIs)
   - [ ] Mapping file passed to `generate-iac` command
   - [ ] Target tenant identities pre-created (if required)

---

## Key Takeaways

1. **Code is correct** - All handlers and discovery logic exist and work properly
2. **Three root causes** - Permissions, cross-tenant filtering, or data integrity
3. **Use diagnostic tool** - `diagnose_managed_identity_issue.py` identifies root cause quickly
4. **Prevention is key** - Validate permissions and identity mapping BEFORE scanning

---

## Related Documentation

- [Azure RBAC Documentation](https://docs.microsoft.com/en-us/azure/role-based-access-control/)
- [Managed Identity Documentation](https://docs.microsoft.com/en-us/azure/active-directory/managed-identities-azure-resources/)
- [Cross-Tenant Deployment Guide](../cross-tenant-deployment/)
- [Troubleshooting Guide](../troubleshooting/)

---

**Last Updated**: 2026-02-06
**Issue**: #889
**Status**: Diagnostic/Configuration Issue

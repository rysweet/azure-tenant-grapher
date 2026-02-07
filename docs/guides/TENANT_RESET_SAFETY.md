# Tenant Reset Safety Guide

Deep dive into Azure Tenant Grapher's Tenant Reset safety mechanisms, including ATG Service Principal preservation, confirmation flows, and dependency-aware deletion.

## Safety Philosophy

The Tenant Reset feature follows a defense-in-depth approach with multiple safety layers:

1. **ATG Service Principal Preservation** - Automatic protection against self-destruction
2. **Dry-Run Mode** - Preview all operations before execution
3. **Type "DELETE" Confirmation** - Explicit user acknowledgment of destructive operations
4. **Dependency-Aware Deletion** - Correct ordering prevents orphaned resources
5. **Comprehensive Audit Logging** - Complete record of all operations

## ATG Service Principal Preservation

### Overview

The most critical safety mechanism prevents deletion of the Service Principal that Azure Tenant Grapher uses to authenticate with Azure. Without this protection, ATG would delete itself and lose all access to the tenant.

### How It Works

**Step 1: Identity Detection**

When you authenticate with Azure CLI or provide credentials, ATG captures the identity:

```python
# ATG detects current identity
from azure.identity import DefaultAzureCredential
credential = DefaultAzureCredential()

# Extract Service Principal object ID from token claims
token = credential.get_token("https://management.azure.com/.default")
atg_sp_object_id = extract_object_id_from_token(token)
```

**Step 2: Scope Calculation**

The `TenantResetService` calculates what resources to delete and automatically excludes the ATG SP:

```python
# Example scope calculation for tenant reset
resources_to_delete = discover_all_resources(tenant_id)
resources_to_preserve = [atg_service_principal]

# Filter out ATG SP and dependencies
final_deletion_list = [
    r for r in resources_to_delete
    if r.id not in resources_to_preserve
]
```

**Step 3: Dependency Preservation**

ATG also preserves resources that depend on the ATG SP:

- Role assignments where ATG SP is the principal
- Key Vault access policies granting permissions to ATG SP
- Any resources that ATG SP manages

### What Gets Preserved

| Resource Type | Preservation Logic |
|---------------|-------------------|
| Service Principal | ATG SP object preserved completely |
| Role Assignments | Assignments with ATG SP as principal |
| Key Vault Access Policies | Policies granting access to ATG SP |
| Application Registrations | App registration linked to ATG SP |

### Verification

After reset, verify preservation:

```bash
# Check ATG SP exists
az ad sp show --id <atg-sp-object-id>

# Output:
# {
#   "appId": "12345678-1234-1234-1234-123456789abc",
#   "displayName": "azure-tenant-grapher",
#   "objectId": "87654321-4321-4321-4321-210987654321",
#   "servicePrincipalType": "Application"
# }

# Verify role assignments still exist
az role assignment list --assignee <atg-sp-object-id>

# Output shows preserved role assignments:
# [
#   {
#     "principalId": "87654321-4321-4321-4321-210987654321",
#     "principalName": "azure-tenant-grapher",
#     "roleDefinitionName": "Reader",
#     "scope": "/subscriptions/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
#   }
# ]
```

## Dry-Run Mode

### Purpose

Dry-run mode shows exactly what will be deleted without executing any deletions. Use this to validate scope and verify ATG SP preservation before committing to destructive operations.

### Usage

Add `--dry-run` flag to any reset command:

```bash
# Preview tenant reset
atg reset tenant --tenant-id <tenant-id> --dry-run

# Preview subscription reset
atg reset subscription --subscription-ids <sub-id> --dry-run

# Preview resource group reset
atg reset resource-group --resource-group-names test-rg --subscription-id <sub-id> --dry-run
```

### Output Format

Dry-run output includes:

```
=== TENANT RESET DRY-RUN ===

Tenant ID: 12345678-1234-1234-1234-123456789abc

Resources Discovered: 847
Resources to Delete: 845
Resources to Preserve: 2

Resources by Type:
  - Microsoft.Compute/virtualMachines: 45
  - Microsoft.Network/networkInterfaces: 45
  - Microsoft.Storage/storageAccounts: 12
  - Microsoft.Network/virtualNetworks: 8
  - Microsoft.KeyVault/vaults: 3
  - [... additional types ...]

Preserved Resources:
  - Service Principal: azure-tenant-grapher (87654321-4321-4321-4321-210987654321)
  - Role Assignment: azure-tenant-grapher → Reader on /subscriptions/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee

Deletion Order (by dependency):
  1. Virtual Machines (45 resources)
  2. Network Interfaces (45 resources)
  3. Disks (45 resources)
  4. Virtual Networks (8 resources)
  5. Storage Accounts (12 resources)
  6. Resource Groups (15 resources - empty only)

Total deletion time estimate: 8-12 minutes (5 concurrent threads)

[DRY-RUN] No resources were deleted.
```

### Interpreting Results

**Key metrics:**

- **Resources Discovered**: Total resources found in scope
- **Resources to Delete**: Resources that will be deleted
- **Resources to Preserve**: ATG SP and dependencies (should always be ≥ 1)

**Validation checklist:**

- [ ] "Resources to Preserve" includes ATG Service Principal
- [ ] Resource counts match expectations for scope
- [ ] Deletion order looks correct (dependencies first)
- [ ] No critical production resources in deletion list

## Type "DELETE" Confirmation

### Purpose

Explicit, case-sensitive confirmation prevents accidental deletions from typos or scripts running unintended commands.

### Confirmation Flow

**Step 1: Scope Summary**

ATG displays what will be deleted:

```
=== TENANT RESET CONFIRMATION ===

About to delete 845 resources across 3 subscriptions.
This operation cannot be undone.

Resources by Type:
  - Microsoft.Compute/virtualMachines: 45
  - Microsoft.Storage/storageAccounts: 12
  - [... additional types ...]

Preserved Resources:
  - Service Principal: azure-tenant-grapher
```

**Step 2: User Prompt**

ATG prompts for confirmation:

```
Type 'DELETE' to confirm:
```

**Step 3: Validation**

ATG validates input:

- Must type exactly `DELETE` in uppercase
- Any other input cancels operation
- No confirmation in `--dry-run` mode

**Examples:**

```bash
# Correct confirmation
Type 'DELETE' to confirm: DELETE
✓ Confirmation received. Starting deletion...

# Incorrect confirmations (operation cancelled)
Type 'DELETE' to confirm: delete
✗ Confirmation failed. Operation cancelled.

Type 'DELETE' to confirm: yes
✗ Confirmation failed. Operation cancelled.

Type 'DELETE' to confirm: DELETE
✗ Confirmation failed. Operation cancelled. (trailing space)
```

### Skipping Confirmation

Use `--skip-confirmation` flag for automation scenarios:

```bash
# Skip confirmation (use with extreme caution)
atg reset tenant --tenant-id <tenant-id> --skip-confirmation
```

**When to use:**
- Automated test cleanup scripts
- CI/CD pipeline resource cleanup
- Scheduled maintenance jobs

**When NOT to use:**
- Production environments
- Manual operations
- Exploratory cleanup tasks

## Dependency-Aware Deletion

### Why It Matters

Azure resources have dependencies. Deleting a Virtual Network before deleting Network Interfaces that use it causes errors. Dependency-aware deletion ensures correct ordering.

### Deletion Order

Resources are deleted in reverse dependency order:

```
1. Virtual Machines
   ├─ Dependencies: Network Interfaces, Disks
   └─ Delete first to release dependencies

2. Network Interfaces
   ├─ Dependencies: Virtual Networks, Subnets
   └─ Delete after VMs, before VNets

3. Disks
   ├─ Dependencies: None (after VM detachment)
   └─ Delete after VMs

4. Public IP Addresses
   ├─ Dependencies: Network Interfaces
   └─ Delete after Network Interfaces

5. Load Balancers
   ├─ Dependencies: Backend pools, VMs
   └─ Delete after VMs

6. Virtual Networks
   ├─ Dependencies: Subnets, Network Interfaces
   └─ Delete after Network Interfaces

7. Network Security Groups
   ├─ Dependencies: Subnets, Network Interfaces
   └─ Delete after Virtual Networks

8. Storage Accounts
   ├─ Dependencies: VM diagnostics
   └─ Delete after VMs

9. Key Vaults
   ├─ Dependencies: VM secrets, certificates
   └─ Delete after VMs

10. Resource Groups
    ├─ Dependencies: All contained resources
    └─ Delete last (empty only)
```

### How It Works

**Step 1: Dependency Graph Construction**

ATG builds a dependency graph from Azure Resource Manager data:

```python
# Simplified example
dependency_graph = {
    "vm-1": ["nic-1", "disk-1"],
    "nic-1": ["vnet-1"],
    "vnet-1": [],
    "disk-1": []
}
```

**Step 2: Topological Sort**

ATG performs topological sort to determine deletion order:

```python
# Deletion order from topological sort
deletion_order = ["vm-1", "nic-1", "disk-1", "vnet-1"]
```

**Step 3: Batched Deletion**

ATG deletes resources in waves, respecting dependencies:

```bash
Wave 1: Delete VMs (45 resources, 5 concurrent threads)
  ✓ Deleted vm-1
  ✓ Deleted vm-2
  ...
  ✓ Deleted vm-45

Wave 2: Delete Network Interfaces (45 resources, 5 concurrent threads)
  ✓ Deleted nic-1
  ✓ Deleted nic-2
  ...
  ✓ Deleted nic-45

Wave 3: Delete Disks (45 resources, 5 concurrent threads)
  ✓ Deleted disk-1
  ...

[... additional waves ...]
```

### Handling Deletion Errors

If a resource fails to delete:

1. ATG logs the error with details
2. Continues deleting other resources in the wave
3. Retries failed resources in subsequent wave
4. Reports undeleted resources at completion

```bash
Wave 2: Delete Network Interfaces (45 resources)
  ✓ Deleted nic-1
  ✗ Failed to delete nic-2: Resource still attached to VM
  ✓ Deleted nic-3
  ...

Wave 2 Retry: (1 resources)
  ✓ Deleted nic-2 (VM detachment completed)

Deletion Summary:
  Total resources: 845
  Deleted successfully: 843
  Failed to delete: 2
  Preserved (ATG SP): 2

Failed Resources:
  - /subscriptions/.../resourceGroups/test-rg/providers/Microsoft.Network/networkSecurityGroups/nsg-locked
    Reason: Resource has delete lock
```

## Audit Logging

### Log Location

All reset operations log to `~/.atg/logs/tenant-reset/`:

```bash
~/.atg/logs/tenant-reset/
├── reset-tenant-2026-01-27-143022.log
├── reset-subscription-2026-01-27-143145.log
└── reset-resource-group-2026-01-27-143302.log
```

### Log Contents

Each log includes:

1. **Operation Metadata**
   - Timestamp
   - Scope (tenant/subscription/resource-group/resource)
   - User identity
   - Command-line arguments

2. **Discovery Phase**
   - Resources discovered
   - Resources to delete
   - Resources to preserve (ATG SP)

3. **Confirmation Phase**
   - User confirmation (or skip-confirmation flag)
   - Dry-run mode indicator

4. **Deletion Phase**
   - Deletion waves (dependency-ordered)
   - Per-resource deletion status
   - Error details for failed deletions

5. **Completion Summary**
   - Total resources deleted
   - Total resources failed
   - Total execution time
   - Performance metrics

### Example Log

```
2026-01-27 14:30:22.123 [INFO] ===== TENANT RESET OPERATION START =====
2026-01-27 14:30:22.124 [INFO] Scope: tenant
2026-01-27 14:30:22.124 [INFO] Tenant ID: 12345678-1234-1234-1234-123456789abc
2026-01-27 14:30:22.125 [INFO] User Identity: user@example.com
2026-01-27 14:30:22.125 [INFO] Dry Run: False
2026-01-27 14:30:22.125 [INFO] Skip Confirmation: False
2026-01-27 14:30:22.125 [INFO] Concurrency: 5

2026-01-27 14:30:23.456 [INFO] ===== DISCOVERY PHASE =====
2026-01-27 14:30:23.456 [INFO] Discovering resources in tenant...
2026-01-27 14:30:28.789 [INFO] Discovered 847 resources across 3 subscriptions
2026-01-27 14:30:28.790 [INFO] Identified ATG Service Principal: azure-tenant-grapher (87654321-4321-4321-4321-210987654321)
2026-01-27 14:30:28.791 [INFO] Resources to delete: 845
2026-01-27 14:30:28.791 [INFO] Resources to preserve: 2 (ATG SP + dependencies)

2026-01-27 14:30:28.792 [INFO] ===== CONFIRMATION PHASE =====
2026-01-27 14:30:28.792 [INFO] Displaying confirmation prompt to user...
2026-01-27 14:30:35.123 [INFO] User typed: DELETE
2026-01-27 14:30:35.123 [INFO] Confirmation received. Proceeding with deletion.

2026-01-27 14:30:35.124 [INFO] ===== DELETION PHASE =====
2026-01-27 14:30:35.124 [INFO] Starting dependency-aware deletion (5 concurrent threads)
2026-01-27 14:30:35.125 [INFO] Wave 1: Virtual Machines (45 resources)
2026-01-27 14:30:37.456 [INFO] [Wave 1] Deleted: /subscriptions/.../virtualMachines/vm-1
2026-01-27 14:30:38.123 [INFO] [Wave 1] Deleted: /subscriptions/.../virtualMachines/vm-2
...
2026-01-27 14:31:02.789 [INFO] Wave 1 complete: 45/45 resources deleted

2026-01-27 14:31:02.790 [INFO] Wave 2: Network Interfaces (45 resources)
2026-01-27 14:31:04.123 [INFO] [Wave 2] Deleted: /subscriptions/.../networkInterfaces/nic-1
...
2026-01-27 14:31:25.456 [INFO] Wave 2 complete: 45/45 resources deleted

[... additional waves ...]

2026-01-27 14:32:15.789 [INFO] ===== COMPLETION SUMMARY =====
2026-01-27 14:32:15.789 [INFO] Total resources deleted: 843
2026-01-27 14:32:15.789 [INFO] Total resources failed: 2
2026-01-27 14:32:15.789 [INFO] Total resources preserved: 2
2026-01-27 14:32:15.789 [INFO] Total execution time: 113.2 seconds
2026-01-27 14:32:15.790 [INFO] Average deletion rate: 7.4 resources/second
2026-01-27 14:32:15.790 [INFO] ===== TENANT RESET OPERATION COMPLETE =====
```

## Recovery Scenarios

### ATG SP Accidentally Deleted

If ATG SP is somehow deleted despite protections:

**Symptoms:**
- `az login` fails with authentication errors
- ATG commands fail with permission errors
- Azure portal shows no Service Principal

**Recovery:**

```bash
# Step 1: Recreate Service Principal
az ad sp create-for-rbac --name azure-tenant-grapher --role Reader --scopes /subscriptions/<sub-id>

# Output:
# {
#   "appId": "12345678-1234-1234-1234-123456789abc",
#   "password": "new-generated-password",  # pragma: allowlist secret
#   "tenant": "87654321-4321-4321-4321-210987654321"
# }

# Step 2: Update ATG configuration
atg config set azure.service_principal.app_id "12345678-1234-1234-1234-123456789abc"
atg config set azure.service_principal.password "new-generated-password"

# Step 3: Test authentication
az login --service-principal \
  --username "12345678-1234-1234-1234-123456789abc" \
  --password "new-generated-password" \
  --tenant "87654321-4321-4321-4321-210987654321"

# Step 4: Verify ATG access
atg scan --tenant-id <tenant-id>
```

### Partial Deletion Failure

If deletion fails partway through:

**Symptoms:**
- Some resources deleted, others remain
- Log shows errors for specific resources
- Dry-run shows different resource count than expected

**Recovery:**

```bash
# Step 1: Review logs to identify failed resources
cat ~/.atg/logs/tenant-reset/reset-tenant-*.log | grep "Failed to delete"

# Step 2: Check for delete locks
az resource list --query "[?id=='<failed-resource-id>'].locks"

# Step 3: Remove locks if present
az lock delete --name <lock-name> --resource-group <rg-name> --resource-name <resource-name>

# Step 4: Re-run reset operation (only deletes remaining resources)
atg reset tenant --tenant-id <tenant-id>
```

## Related Documentation

- [Tenant Reset Guide](./TENANT_RESET_GUIDE.md) - User guide and command reference
- [Tenant Reset API Reference](../reference/TENANT_RESET_API.md) - Service architecture
- [Tenant Reset Troubleshooting](../reference/TENANT_RESET_TROUBLESHOOTING.md) - Error resolution

## Metadata

---
last_updated: 2026-01-27
status: current
category: guides
related_services: TenantResetService, ResetConfirmation
---

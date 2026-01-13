# Terraform Import Blocks Explained

Understanding how Azure Tenant Grapher generates Terraform import blocks for existing resources.

---

## What Are Import Blocks?

Terraform 1.5+ introduced **import blocks** to bring existing infrastructure under Terraform management without destroying and recreating it.

**Without imports:**
```bash
terraform apply
# Error: A Subnet with name "default" already exists
```

**With imports:**
```terraform
import {
  to = azurerm_subnet.subnet_123
  id = "/subscriptions/.../subnets/default"
}

resource "azurerm_subnet" "subnet_123" {
  name                 = "default"
  virtual_network_name = azurerm_virtual_network.vnet_456.name
  address_prefixes     = ["10.0.1.0/24"]
}
```

```bash
terraform apply
# Success: Imported subnet, no changes needed
```

**The import block:**
1. Tells Terraform the resource already exists
2. Provides the Azure resource ID
3. Links it to the Terraform resource definition
4. No destruction, no downtime, no data loss

---

## Why Import Blocks Matter

### Cross-Tenant Replication

When replicating Azure infrastructure to a new tenant:

**Scenario 1: Without imports (broken)**
- Source tenant: VNet with 3 subnets
- Target tenant: VNet already exists (manually created)
- Deploy with Terraform: **FAILS** - "VNet already exists"
- Result: Cannot deploy

**Scenario 2: With imports (working)**
- Source tenant: VNet with 3 subnets
- Target tenant: VNet already exists
- Deploy with Terraform: **SUCCEEDS** - Imports VNet, creates subnets
- Result: Full replication

### Brownfield Deployments

Bringing existing infrastructure under IaC management:

**Without imports:**
- Must delete all existing resources first
- Causes downtime
- Loses data and configurations
- High risk

**With imports:**
- Keep all existing resources
- Zero downtime
- Preserve all data
- Low risk

---

## How Azure Tenant Grapher Generates Imports

### The Challenge

Terraform resource definitions use **variable references**:

```json
{
  "resource": {
    "azurerm_subnet": {
      "subnet_123": {
        "name": "default",
        "virtual_network_name": "${azurerm_virtual_network.vnet_456.name}",
        "resource_group_name": "${azurerm_resource_group.rg_789.name}"
      }
    }
  }
}
```

But import blocks need **actual Azure IDs**:

```terraform
import {
  to = azurerm_subnet.subnet_123
  id = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/my-rg/providers/Microsoft.Network/virtualNetworks/vnet-prod/subnets/default"
}
```

**Problem:** How to convert `${azurerm_virtual_network.vnet_456.name}` to `/subscriptions/.../virtualNetworks/vnet-prod`?

### The Solution: Dual-Graph Architecture

Azure Tenant Grapher stores every resource as **two nodes** in Neo4j:

```
┌─────────────────────────────────────────────────────────────┐
│                      Neo4j Graph                            │
│                                                             │
│  ┌──────────────────┐    SCAN_SOURCE_NODE    ┌───────────┐ │
│  │ Abstracted Node  │─────────────────────────>│ Original  │ │
│  │ (for deployment) │                         │   Node    │ │
│  └──────────────────┘                         └───────────┘ │
│                                                             │
│  id: "subnet-abc123"                    id: "/subscriptions│
│  name: "default"                           .../subnets/    │
│                                            default"         │
└─────────────────────────────────────────────────────────────┘
```

**Abstracted node:**
- Safe IDs for cross-tenant deployment (e.g., `subnet-abc123`)
- Used for Terraform resource names
- Linked to parent resources for config generation

**Original node:**
- Real Azure IDs from source tenant
- Exact resource paths
- Preserved for import block generation

**Key insight:** The original node has exactly what we need - the real Azure resource ID!

### The Process

**Step 1: Query Neo4j for both nodes**
```cypher
MATCH (r:Resource)
OPTIONAL MATCH (r)-[:SCAN_SOURCE_NODE]->(o:Resource:Original)
RETURN
  r.id as abstracted_id,    // subnet-abc123
  o.id as original_id,      // /subscriptions/.../subnets/default
  r.name as name            // default
```

**Step 2: Build original_id map**
```python
original_id_map = {
    "subnet-abc123": "/subscriptions/.../subnets/default",
    "vnet-456": "/subscriptions/.../virtualNetworks/vnet-prod",
    "rg-789": "/subscriptions/.../resourceGroups/my-rg",
    # ... all resources
}
```

**Step 3: Generate import blocks using original IDs**
```python
for resource in resources:
    abstracted_id = resource['id']           # subnet-abc123
    original_id = original_id_map[abstracted_id]  # /subscriptions/.../subnets/default

    # For cross-tenant: translate subscription ID
    if target_subscription:
        original_id = original_id.replace(source_sub, target_sub)

    import_block = {
        "to": f"azurerm_subnet.{abstracted_id}",
        "id": original_id
    }
```

**Result:**
- ✅ No string manipulation or variable resolution
- ✅ Works for all resource types automatically
- ✅ Handles complex parent-child relationships
- ✅ Cross-tenant subscription translation built-in

---

## Parent vs Child Resources

### Parent Resources (Easy)

Resources with simple, flat IDs:

```
Resource Group:     /subscriptions/{sub}/resourceGroups/my-rg
Virtual Network:    /subscriptions/{sub}/resourceGroups/my-rg/providers/Microsoft.Network/virtualNetworks/vnet-prod
Virtual Machine:    /subscriptions/{sub}/resourceGroups/my-rg/providers/Microsoft.Compute/virtualMachines/vm-app
```

**Easy to generate imports:** All path segments are known from resource properties.

### Child Resources (Complex)

Resources nested under parents with references:

```
Subnet:             /subscriptions/{sub}/resourceGroups/{rg}/providers/Microsoft.Network/virtualNetworks/{vnet}/subnets/default
VM Extension:       /subscriptions/{sub}/resourceGroups/{rg}/providers/Microsoft.Compute/virtualMachines/{vm}/extensions/monitoring
Runbook:            /subscriptions/{sub}/resourceGroups/{rg}/providers/Microsoft.Automation/automationAccounts/{account}/runbooks/backup
```

**Complex to generate imports:** Parent resource names needed, but configs only have `${variable.references}`.

**Bug #10 impact:**
- Before fix: Only parent resources got imports (67/177 = 37.9%)
- After fix: All resources get imports (177/177 = 100%)

---

## Cross-Tenant Translation

When deploying to a different tenant, subscription IDs must be translated:

**Source tenant:**
```
/subscriptions/11111111-1111-1111-1111-111111111111/resourceGroups/my-rg/...
```

**Target tenant:**
```
/subscriptions/22222222-2222-2222-2222-222222222222/resourceGroups/my-rg/...
              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
              Target subscription ID substituted
```

**Process:**
1. Get original_id from source tenant: `/subscriptions/11111111-.../...`
2. Replace source subscription with target: `/subscriptions/22222222-.../...`
3. Use translated ID in import block

**Why this works:**
- Resource group names stay the same
- Resource names stay the same
- Only subscription ID changes
- Import block points to correct target resource

---

## What Users See

### Successful Import Generation

```bash
uv run atg generate-iac --auto-import-existing

Analyzing resources...
Generating Terraform configuration...
Creating import blocks: 177/177 ✅
Writing output to /tmp/iac_output

Generated:
  - main.tf.json (resource definitions)
  - import blocks: 177 resources
  - Coverage: 100%
```

### Verifying Results

```bash
cd /tmp/iac_output
terraform init
terraform plan

# Expected output:
Terraform will perform the following actions:

  # azurerm_virtual_network.vnet_456 will be imported
  resource "azurerm_virtual_network" "vnet_456" {
      name                = "vnet-prod"
      location            = "eastus"
      ...
  }

  # azurerm_subnet.subnet_123 will be imported
  resource "azurerm_subnet" "subnet_123" {
      name                = "default"
      virtual_network_name = azurerm_virtual_network.vnet_456.name
      ...
  }

Plan: 177 to import, 0 to add, 0 to change, 0 to destroy.
```

**Success indicators:**
- "X to import" matches resource count
- "0 to add" (resources exist, not creating new ones)
- "0 to change" (perfect match between source and target)

---

## Common Questions

### Q: Do I need to do anything special?

**A:** No. Just use `--auto-import-existing` flag:

```bash
uv run atg generate-iac --auto-import-existing
```

The tool handles everything automatically.

### Q: What if resources don't exist in target tenant?

**A:** The import block is harmless. Terraform will:
1. Try to import (fails silently if resource doesn't exist)
2. Create the resource instead

Better yet, use `--scan-target` to generate imports only for existing resources:

```bash
uv run atg generate-iac \
  --target-tenant-id TARGET_TENANT \
  --scan-target \
  --auto-import-existing
```

### Q: Will this modify my existing resources?

**A:** Import blocks are **read-only**. They:
- ✅ Bring resources under Terraform management
- ✅ Detect configuration drift
- ❌ Do NOT modify resources
- ❌ Do NOT delete resources
- ❌ Do NOT recreate resources

The only changes happen when you run `terraform apply` after import.

### Q: What if I see "X to change" in terraform plan?

**A:** This indicates **configuration drift** - the target resource differs from source. Common causes:
- Different configurations between tenants
- Manual changes in target tenant
- Expected differences (different regions, sizes, etc.)

**Options:**
1. Accept drift: Update source config to match target
2. Fix drift: Run `terraform apply` to reconcile target to source
3. Investigate: Check if differences are intentional

### Q: Can I use this with existing Terraform code?

**A:** Yes! Import blocks work alongside existing Terraform:
- Existing resources: Import blocks bring them under management
- New resources: Standard resource blocks create them
- Both coexist in same configuration

---

## Troubleshooting

**If import coverage is low (< 100%):**

Check SCAN_SOURCE_NODE relationships:
```cypher
MATCH (r:Resource)-[:SCAN_SOURCE_NODE]->(o:Resource:Original)
RETURN count(r)
```

If count is low, you scanned before Bug #117 fix. Re-scan tenant:
```bash
uv run atg scan --tenant-id YOUR_TENANT_ID
```

**If import IDs contain variables:**

Example of broken import:
```json
{
  "id": "/subscriptions/.../resourceGroups/${azurerm_resource_group.rg_123.name}/..."
}
```

**Fix:** Update to latest version and regenerate:
```bash
git pull
uv sync
uv run atg generate-iac --auto-import-existing
```

**For detailed troubleshooting:** See [Terraform Import Troubleshooting Guide](../guides/TERRAFORM_IMPORT_TROUBLESHOOTING.md).

---

## Best Practices

1. **Always use --auto-import-existing for brownfield deployments**
   ```bash
   uv run atg generate-iac --auto-import-existing
   ```

2. **Scan target tenant for smart imports**
   ```bash
   uv run atg generate-iac --scan-target --auto-import-existing
   ```

3. **Verify import coverage before deployment**
   ```bash
   python3 -c "import json; c=json.load(open('main.tf.json')); i=len(c.get('import',[])); r=sum(len(x) for x in c.get('resource',{}).values()); print(f'{i}/{r} ({100*i/r:.1f}%)')"
   ```
   Expected: 100%

4. **Test with terraform plan first**
   ```bash
   cd /tmp/iac_output
   terraform init
   terraform plan  # Review before applying
   ```

5. **Monitor imports during apply**
   ```bash
   terraform apply
   # Watch for "X imported" messages
   # Should match import block count
   ```

---

## Related Documentation

- **[Bug #10 Documentation](../BUG_10_DOCUMENTATION.md)** - Technical details of child resource fix
- **[Troubleshooting Guide](../guides/TERRAFORM_IMPORT_TROUBLESHOOTING.md)** - Diagnose import issues
- **[Quick Reference](../quickstart/terraform-import-quick-ref.md)** - Commands and one-liners
- **[Import-First Strategy](../patterns/IMPORT_FIRST_STRATEGY.md)** - Design pattern for reliable replication
- **[Dual-Graph Architecture](../DUAL_GRAPH_SCHEMA.md)** - How original IDs are stored

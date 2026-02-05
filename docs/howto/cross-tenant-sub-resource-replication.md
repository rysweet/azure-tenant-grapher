# Cross-Tenant Sub-Resource Replication

> **⚠️ FUTURE IMPLEMENTATION**
> This documentation describes the **planned architecture** for Issues #886 and #887.
> **Current Status**: Design approved, implementation in progress.
> **Target Version**: ATG 0.10.0
> **GitHub Issues**: [#886](https://github.com/rysweet/azure-tenant-grapher/issues/886), [#887](https://github.com/rysweet/azure-tenant-grapher/issues/887)

Replicate Private Endpoints, Diagnostic Settings, and RBAC role assignments when replicating resources across Azure tenants.

## What This Enables

When you replicate resources like Key Vaults or Storage Accounts to a target tenant, Azure Tenant Grapher **will automatically replicate** (once implemented):

- **Private Endpoints** - Network isolation and private connectivity
- **Diagnostic Settings** - Logging and monitoring configurations
- **RBAC Role Assignments** - Resource-scoped access control

These sub-resources **will preserve** your security posture, network architecture, and operational observability across tenants.

## Quick Example

```bash
# Replicate a Key Vault with all sub-resources
atg iac generate \
  --layer source-scan \
  --target-subscription-id <target-sub-id> \
  --target-tenant-id <target-tenant-id> \
  --identity-mapping-file identity_map.json

# Output includes:
# ✅ Key Vault resource
# ✅ Private Endpoint connections
# ✅ Diagnostic Settings (logs/metrics)
# ✅ RBAC role assignments
```

Result: Complete functional replica with security, networking, and access control intact.

## Prerequisites

### Source Tenant
- Completed discovery scan with ATG (created Neo4j graph)
- Resources **will have** established relationships in graph (once discovery phases complete):
  - `CONNECTED_TO_PE` (Private Endpoints)
  - `SENDS_DIAG_TO` (Diagnostic Settings)
  - `HAS_ROLE_ASSIGNMENT` (RBAC)

### Required Azure RBAC Permissions

To discover sub-resources, your Azure credentials need:
- `Microsoft.Network/privateEndpoints/read`
- `Microsoft.Authorization/roleAssignments/read`
- `Microsoft.Insights/diagnosticSettings/read`

### Target Tenant
- Azure subscription and credentials configured
- Network infrastructure (VNets, subnets) already deployed if replicating Private Endpoints
- Log Analytics workspace or Storage Account deployed if replicating Diagnostic Settings
- Service principal or managed identity for Terraform deployment

### Identity Mapping File
For RBAC role assignments, provide identity mapping JSON:

```json
{
  "source_tenant_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
  "target_tenant_id": "ffffffff-0000-1111-2222-333333333333",
  "mappings": {
    "user:<source-object-id>": "user:<target-object-id>",
    "group:<source-group-id>": "group:<target-group-id>",
    "sp:<source-sp-id>": "sp:<target-sp-id>"
  }
}
```

## How It Works

### Phase 1: Discovery
During `atg discover`, ATG **will discover** sub-resources as separate entities (once discovery phases complete):

```cypher
// Private Endpoints discovered as nodes
(kv:KeyVault)-[:CONNECTED_TO_PE]->(pe:PrivateEndpoint)

// Diagnostic Settings discovered as sub-resources
(kv:KeyVault)-[:SENDS_DIAG_TO]->(ds:DiagnosticSetting)

// RBAC role assignments discovered at resource scope
(kv:KeyVault)-[:HAS_ROLE_ASSIGNMENT]->(ra:RoleAssignment)
```

These relationships **will be created** automatically when ATG scans your Azure tenant.

## Implementation Phases

This feature is implemented in three phases:

### Phase 1: Discovery Enhancement
- [ ] Private Endpoint discovery (Phase 1.4)
- [ ] Role Assignment discovery (Phase 1.5)
- [ ] Diagnostic Settings discovery (Phase 1.6)

### Phase 2: Terraform Handler Creation
- [ ] `private_endpoint.py` handler (Issue #887)
- [ ] `diagnostic_settings.py` handler (Issue #886)
- [ ] `role_assignment.py` handler enhancements (Issue #886)

### Phase 3: Cross-Tenant Translation
- [ ] Subnet ID translation
- [ ] Workspace ID translation
- [ ] Principal ID translation (identity mapping)

### Phase 2: Translation
During `atg iac generate`, ATG **will**:

1. **Private Endpoints**: Query Neo4j for `CONNECTED_TO_PE` relationships, **will generate** `azurerm_private_endpoint` Terraform resources (once Issue #887 is resolved)
2. **Diagnostic Settings**: Query for `SENDS_DIAG_TO` relationships, **will generate** `azurerm_monitor_diagnostic_setting` resources (once Issue #886 is resolved)
3. **RBAC**: Query for `HAS_ROLE_ASSIGNMENT` relationships, translate principal IDs using identity mapping, **will generate** `azurerm_role_assignment` resources

### Phase 3: Deployment
Terraform **will deploy** resources in dependency order:

```
1. Main resource (Key Vault, Storage Account)
2. Private Endpoints (requires VNet/subnet)
3. Diagnostic Settings (requires workspace/storage)
4. RBAC role assignments (requires resource and principals)
```

## Step-by-Step Guide

### Step 1: Run Discovery Scan

Discover all resources in source tenant:

```bash
atg discover --subscription-id <source-sub-id>
```

ATG **will automatically discover** (once implementation is complete):
- Main resources (Key Vaults, Storage Accounts, etc.)
- Private Endpoints and their connections
- Diagnostic Settings configurations
- RBAC role assignments at resource scope

### Step 2: Verify Discovery

Check that sub-resources were discovered:

```cypher
// Check Private Endpoints
MATCH (kv:KeyVault {name: "myKeyVault"})-[:CONNECTED_TO_PE]->(pe:PrivateEndpoint)
RETURN kv.name, pe.name, pe.properties.privateLinkServiceConnections

// Check Diagnostic Settings
MATCH (kv:KeyVault {name: "myKeyVault"})-[:SENDS_DIAG_TO]->(ds:DiagnosticSetting)
RETURN kv.name, ds.name, ds.properties.logs, ds.properties.metrics

// Check RBAC Role Assignments
MATCH (kv:KeyVault {name: "myKeyVault"})-[:HAS_ROLE_ASSIGNMENT]->(ra:RoleAssignment)
RETURN kv.name, ra.properties.roleDefinitionName, ra.properties.principalType
```

### Step 3: Create Identity Mapping

For RBAC replication, map Entra ID principals from source to target:

```bash
# Create mapping file
cat > identity_map.json <<EOF
{
  "source_tenant_id": "source-tenant-id",
  "target_tenant_id": "target-tenant-id",
  "mappings": {
    "user:john.doe@source.com": "user:john.doe@target.com",
    "group:developers": "group:developers",
    "sp:app-service-principal": "sp:app-service-principal"
  }
}
EOF
```

**Tip**: Use `az ad user show`, `az ad group show`, or `az ad sp show` to find object IDs.

### Step 4: Generate IaC with Translation

Generate Terraform with cross-tenant translation:

```bash
atg iac generate \
  --layer source-scan \
  --target-subscription-id <target-sub-id> \
  --target-tenant-id <target-tenant-id> \
  --identity-mapping-file identity_map.json \
  --output-dir ./terraform-output
```

ATG **will generate** (once implemented):
- `main.tf` - Main resources
- `private_endpoints.tf` - Private endpoint resources
- `diagnostic_settings.tf` - Monitoring configurations
- `role_assignments.tf` - RBAC assignments
- `translation_report.txt` - Human-readable summary
- `translation_report.json` - Machine-readable details

### Step 5: Review Translation Report

Check translation results:

```bash
cat terraform-output/translation_report.txt
```

Example output:
```
=== Translation Report ===
Resources Processed: 15
Successfully Translated: 14
Warnings: 1
Errors: 0

Private Endpoints:
  ✅ kv-private-endpoint → Translated (subnet updated)
  ✅ storage-blob-pe → Translated (subnet updated)

Diagnostic Settings:
  ✅ kv-diag-logs → Translated (workspace updated)
  ✅ storage-diag-metrics → Translated (workspace updated)

RBAC Role Assignments:
  ✅ john.doe@source.com (Key Vault Admin) → john.doe@target.com
  ⚠️  temp-user@source.com (Key Vault Reader) → No mapping (skipped)
  ✅ developers-group (Key Vault Contributor) → developers-group

Translation complete. Review terraform-output/ directory.
```

### Step 6: Deploy to Target Tenant

Deploy translated Terraform:

```bash
cd terraform-output

# Initialize Terraform
terraform init

# Review plan
terraform plan

# Deploy
terraform apply
```

### Step 7: Verify Replication

Verify sub-resources were replicated:

```bash
# Check Private Endpoints
az network private-endpoint list \
  --resource-group <target-rg> \
  --subscription <target-sub-id>

# Check Diagnostic Settings
az monitor diagnostic-settings list \
  --resource <resource-id>

# Check RBAC Role Assignments
az role assignment list \
  --scope <resource-id>
```

## Feature Details

### Private Endpoint Replication

**What Will Be Replicated:**
- Private endpoint resource
- Private link service connections
- Network interface associations
- Private DNS zone group configurations
- Custom DNS configurations

**Translation Behavior (Once Implemented):**
- Subnet references **will be translated** to target VNet subnets
- Private DNS zones **will be translated** to target tenant zones
- Resource references **will be updated** to target subscription

**Requirements:**
- Target VNet and subnets must exist before deployment
- Subnet must have `privateEndpointNetworkPolicies` disabled
- Target tenant Private DNS zones configured (if using)

**Example Terraform (Once Implemented):**

```hcl
resource "azurerm_private_endpoint" "kv_pe" {
  name                = "kv-private-endpoint"
  location            = "northcentralus"
  resource_group_name = azurerm_resource_group.main.name
  subnet_id           = data.azurerm_subnet.target_subnet.id

  private_service_connection {
    name                           = "kv-connection"
    private_connection_resource_id = azurerm_key_vault.main.id
    is_manual_connection           = false
    subresource_names              = ["vault"]
  }

  private_dns_zone_group {
    name                 = "kv-dns-zone-group"
    private_dns_zone_ids = [data.azurerm_private_dns_zone.keyvault.id]
  }
}
```

### Diagnostic Settings Replication

**What Will Be Replicated:**
- Log categories (enabled/disabled state)
- Metric categories (enabled/disabled state)
- Retention policies
- Destination targets (Log Analytics, Storage Account, Event Hub)

**Translation Behavior (Once Implemented):**
- Log Analytics workspace references **will be translated** to target workspace
- Storage Account references **will be translated** to target storage account
- Event Hub references **will be translated** to target namespace
- Category configurations **will be preserved** exactly

**Requirements:**
- Target Log Analytics workspace exists (if logs enabled)
- Target Storage Account exists (if archive enabled)
- Target Event Hub namespace exists (if streaming enabled)

**Example Terraform (Once Implemented):**

```hcl
resource "azurerm_monitor_diagnostic_setting" "kv_diag" {
  name                       = "kv-diagnostics"
  target_resource_id         = azurerm_key_vault.main.id
  log_analytics_workspace_id = data.azurerm_log_analytics_workspace.target.id

  log {
    category = "AuditEvent"
    enabled  = true

    retention_policy {
      enabled = true
      days    = 30
    }
  }

  metric {
    category = "AllMetrics"
    enabled  = true

    retention_policy {
      enabled = true
      days    = 30
    }
  }
}
```

### RBAC Role Assignment Replication

**What Will Be Replicated:**
- Role definition (e.g., "Key Vault Administrator")
- Principal type (User, Group, Service Principal)
- Assignment scope (resource-level)
- Condition expressions (if present)

**Translation Behavior (Once Implemented):**
- Principal IDs **will be translated** using identity mapping file
- Role definitions **will be translated** to target tenant role IDs
- Scope **will be updated** to target resource ID
- Unmapped principals **will be skipped** with warning (strict mode: error)

**Identity Mapping Format:**

```json
{
  "mappings": {
    "user:<source-object-id>": "user:<target-object-id>",
    "group:<source-object-id>": "group:<target-object-id>",
    "sp:<source-object-id>": "sp:<target-object-id>"
  }
}
```

**Example Terraform (Once Implemented):**

```hcl
resource "azurerm_role_assignment" "kv_admin" {
  scope                = azurerm_key_vault.main.id
  role_definition_name = "Key Vault Administrator"
  principal_id         = var.john_doe_target_principal_id

  # Translated from source tenant:
  # - Principal: john.doe@source.com → john.doe@target.com
  # - Role: Key Vault Administrator (preserved)
  # - Scope: /subscriptions/source/.../vaults/kv → /subscriptions/target/.../vaults/kv
}
```

**Strict Mode:**
- `--strict-translation`: Fail if any principal has no mapping
- Default (permissive): Skip unmapped principals with warning

## Common Scenarios

### Scenario 1: Replicate Key Vault with Full Security

**Source Configuration:**
- Key Vault with 2 Private Endpoints (vault, backup)
- 3 Diagnostic Settings (audit logs, metrics, backup logs)
- 4 RBAC assignments (admin, contributor, 2 readers)

**Replication Command:**

```bash
atg iac generate \
  --layer prod-kv-scan \
  --target-subscription-id <target-sub> \
  --target-tenant-id <target-tenant> \
  --identity-mapping-file kv_identity_map.json \
  --output-dir ./kv-terraform
```

**Result:**
- 1 Key Vault resource
- 2 Private Endpoints (vault, backup)
- 3 Diagnostic Settings (logs preserved)
- 4 RBAC role assignments (principals mapped)

Total: 10 Terraform resources generated

### Scenario 2: Replicate Storage Account with Private Endpoints

**Source Configuration:**
- Storage Account with 3 Private Endpoints (blob, file, queue)
- 1 Diagnostic Setting (metrics to Log Analytics)
- 2 RBAC assignments (Storage Blob Data Contributor, Reader)

**Replication Command:**

```bash
atg iac generate \
  --layer storage-scan \
  --target-subscription-id <target-sub> \
  --target-tenant-id <target-tenant> \
  --identity-mapping-file storage_identity_map.json
```

**Result:**
- 1 Storage Account
- 3 Private Endpoints (blob, file, queue services)
- 1 Diagnostic Setting (metrics)
- 2 RBAC role assignments

### Scenario 3: Replicate Multiple Resources

**Source Configuration:**
- 5 Key Vaults
- 10 Storage Accounts
- 15 Private Endpoints total
- 30 Diagnostic Settings
- 45 RBAC role assignments

**Replication Command:**

```bash
atg iac generate \
  --layer entire-environment \
  --target-subscription-id <target-sub> \
  --target-tenant-id <target-tenant> \
  --identity-mapping-file full_identity_map.json
```

**Result:**
- All 15 main resources
- All 15 Private Endpoints
- All 30 Diagnostic Settings
- All 45 RBAC role assignments (where mapping exists)

Translation report shows summary of each category.

## Troubleshooting

### Private Endpoints Not Generated

**Symptom:**
```
Translation report shows 0 Private Endpoints processed
```

**Possible Causes:**

1. **Discovery Issue** - Private Endpoints not discovered during scan

   **Check:**
   ```cypher
   MATCH (r)-[:CONNECTED_TO_PE]->(pe:PrivateEndpoint)
   RETURN count(pe)
   ```

   **Fix:** Re-run discovery with proper permissions:
   ```bash
   atg discover --subscription-id <sub-id>
   ```

2. **Relationship Missing** - Neo4j relationships not established

   **Check:**
   ```cypher
   MATCH (kv:KeyVault {name: "myKeyVault"})
   OPTIONAL MATCH (kv)-[:CONNECTED_TO_PE]->(pe)
   RETURN kv.name, pe.name
   ```

   **Fix:** This is a discovery bug. Report as GitHub issue with example resource.

3. **Handler Not Yet Implemented** - Private Endpoint handler not yet created (see Issue #887)

   **Check logs:**
   ```bash
   grep "private_endpoint" atg.log
   ```

   **Fix:** Wait for Issue #887 completion or contribute implementation at `src/iac/emitters/terraform/handlers/network/private_endpoint.py`

### Diagnostic Settings Missing

**Symptom:**
```
Warning: Diagnostic Settings discovered but not in Terraform output
```

**Possible Causes:**

1. **Target Workspace Missing** - Log Analytics workspace doesn't exist in target

   **Fix:**
   ```bash
   # Deploy workspace first
   az monitor log-analytics workspace create \
     --resource-group <rg> \
     --workspace-name <workspace-name>
   ```

2. **Reference Translation Failed** - Workspace ID not translated

   **Check translation report:**
   ```bash
   grep "workspace" translation_report.txt
   ```

   **Fix:** Ensure workspace exists before running `atg iac generate`

### RBAC Assignments Skipped

**Symptom:**
```
Warning: Principal user:abc123 has no mapping in identity file (skipped)
```

**Possible Causes:**

1. **Identity Mapping Incomplete** - Principal not in mapping file

   **Fix:** Add missing principal to `identity_map.json`:
   ```json
   {
     "mappings": {
       "user:abc123": "user:xyz789"
     }
   }
   ```

2. **Principal Doesn't Exist in Target** - Target principal not created

   **Fix:** Create target principal first:
   ```bash
   az ad user create --display-name "John Doe" \
     --user-principal-name john.doe@target.com \
     --password <secure-password>
   ```

3. **Strict Mode Blocking** - Translation fails on missing mapping

   **Fix:** Either add mapping or disable strict mode:
   ```bash
   atg iac generate --strict-translation false
   ```

### Terraform Apply Failures

**Symptom:**
```
Error: Private Endpoint subnet not configured for private endpoints
```

**Possible Causes:**

1. **Subnet Policy Not Disabled** - Subnet has network policies enabled

   **Fix:**
   ```bash
   az network vnet subnet update \
     --resource-group <rg> \
     --vnet-name <vnet> \
     --name <subnet> \
     --disable-private-endpoint-network-policies true
   ```

2. **Subnet Doesn't Exist** - Target subnet not deployed

   **Fix:** Deploy VNet infrastructure before replicating Private Endpoints

3. **DNS Zone Missing** - Private DNS zone not configured

   **Fix:**
   ```bash
   az network private-dns zone create \
     --resource-group <rg> \
     --name privatelink.vaultcore.azure.net
   ```

### Translation Report Shows Errors

**Symptom:**
```
Errors: 3
  ❌ Failed to translate private_endpoint_1: Subnet not found
  ❌ Failed to translate diagnostic_setting_2: Workspace reference invalid
  ❌ Failed to translate role_assignment_3: Principal mapping missing
```

**Resolution:**

1. **Review Detailed Errors** - Check `translation_report.json`:
   ```bash
   cat terraform-output/translation_report.json | jq '.errors'
   ```

2. **Fix Prerequisites** - Address each error:
   - Deploy missing infrastructure (subnets, workspaces)
   - Update identity mapping file
   - Re-run IaC generation

3. **Graceful Degradation** - ATG continues with partial translation:
   - Successfully translated resources included in Terraform
   - Failed resources logged in report
   - Manual intervention required for failures

## Best Practices

### Pre-Flight Checks

Before replicating, verify:

```bash
# 1. Discovery completed
atg layer list | grep <layer-name>

# 2. Relationships exist
cypher-shell < verify_relationships.cypher

# 3. Target infrastructure ready
az network vnet show --resource-group <rg> --name <vnet>
az monitor log-analytics workspace show --resource-group <rg> --workspace-name <workspace>

# 4. Identity mapping complete
jq '.mappings | keys | length' identity_map.json
```

### Phased Replication

For large environments, replicate in phases:

1. **Phase 1: Infrastructure**
   - Deploy VNets, subnets, DNS zones
   - Deploy Log Analytics workspaces

2. **Phase 2: Main Resources**
   - Generate and deploy Key Vaults, Storage Accounts
   - No sub-resources yet

3. **Phase 3: Networking**
   - Generate and deploy Private Endpoints
   - Verify connectivity

4. **Phase 4: Observability**
   - Deploy Diagnostic Settings
   - Verify logs flowing

5. **Phase 5: Access Control**
   - Deploy RBAC role assignments
   - Verify permissions

### Identity Mapping Strategy

**Option 1: Manual Mapping** (Small environments)
```json
{
  "mappings": {
    "user:alice": "user:alice-target",
    "user:bob": "user:bob-target"
  }
}
```

**Option 2: Group-Based Mapping** (Medium environments)
```json
{
  "mappings": {
    "group:developers": "group:developers-target",
    "group:admins": "group:admins-target"
  }
}
```

**Option 3: Automated Discovery** (Large environments)
```bash
# Generate mapping from CSV
python scripts/generate_identity_map.py \
  --source-csv source_users.csv \
  --target-csv target_users.csv \
  --output identity_map.json
```

### Validation After Deployment

Verify complete replication:

```bash
# Check Private Endpoints
az network private-endpoint list --resource-group <rg> | jq '.[].name'

# Check Diagnostic Settings
for resource in $(az resource list --resource-group <rg> --query '[].id' -o tsv); do
  az monitor diagnostic-settings list --resource $resource
done

# Check RBAC Role Assignments
for resource in $(az resource list --resource-group <rg> --query '[].id' -o tsv); do
  az role assignment list --scope $resource
done
```

## Limitations

### Known Limitations

1. **Cross-Subscription References** - Private DNS zones must exist in target subscription or be manually referenced
2. **Event Hub Destinations** - Event Hub namespaces must be deployed before Diagnostic Settings
3. **Conditional Role Assignments** - ABAC conditions may need manual adjustment for target tenant
4. **Service Principal Credentials** - Secrets/certificates not replicated (security best practice)

### Unsupported Scenarios

- **System-Managed Identities** - Cannot be pre-created; use user-assigned identities instead
- **Just-In-Time Access** - PIM role assignments not replicated (time-bound by nature)
- **Legacy Diagnostic Settings** - Old format diagnostic settings not supported
- **Managed Private Endpoints** - Some PaaS services use managed private endpoints (e.g., Synapse) which differ from standard private endpoints

## Related Documentation

- [Cross-Tenant Translation Integration](/home/azureuser/src/azure-tenant-grapher/docs/design/cross-tenant-translation/INTEGRATION_SUMMARY.md) - Technical architecture
- [Neo4j Schema Reference](/home/azureuser/src/azure-tenant-grapher/docs/NEO4J_SCHEMA_REFERENCE.md) - Graph relationships
- [Terraform Import Blocks](/home/azureuser/src/azure-tenant-grapher/docs/concepts/TERRAFORM_IMPORT_BLOCKS.md) - Import strategy

---

**Last Updated:** 2026-02-04
**ATG Version:** 0.10.0 (Target)
**Status:** Design Complete, Implementation In Progress

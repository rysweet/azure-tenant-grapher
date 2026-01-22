# Resource Group Structure Preservation (GAP-017)

## Overview

The `--preserve-rg-structure` flag enables Azure Tenant Grapher to preserve the source tenant's resource group organizational structure when generating Infrastructure-as-Code. Instead of consolidating all resources into a single target resource group, this feature creates corresponding resource groups in the target tenant that match the source structure.

## Use Cases

### Multi-Team Environments
Organizations that use resource groups to separate teams, environments, or projects can maintain these organizational boundaries during tenant migration or replication.

**Example**:
```
Source Tenant:
├── team-frontend-rg     (Web apps, CDN)
├── team-backend-rg      (APIs, databases)
└── team-shared-rg       (Key Vault, networking)

Target Tenant (with --preserve-rg-structure):
├── team-frontend-rg     (Same resources)
├── team-backend-rg      (Same resources)
└── team-shared-rg       (Same resources)
```

### Access Control Boundaries
Preserve RBAC boundaries where different teams have different permissions scoped to specific resource groups.

### Cost Allocation
Maintain cost center separation where resource groups represent different billing units or departments.

## Usage

### Basic Usage

```bash
azure-tenant-grapher generate-iac \
  --format terraform \
  --preserve-rg-structure \
  --output-dir ./iac-multi-rg
```

This command:
1. Scans the source tenant
2. Identifies all source resource groups
3. Generates Terraform code that creates corresponding RGs in target
4. Places each resource in its original resource group

### With Location Override

```bash
azure-tenant-grapher generate-iac \
  --format terraform \
  --preserve-rg-structure \
  --location westus2 \
  --output-dir ./iac-multi-rg
```

All resource groups will be created in `westus2` region (overrides source locations).

### Cross-Tenant Deployment

```bash
azure-tenant-grapher generate-iac \
  --format terraform \
  --preserve-rg-structure \
  --source-tenant-id <source-tenant-id> \
  --target-tenant-id <target-tenant-id> \
  --target-subscription <target-sub-id> \
  --output-dir ./iac-cross-tenant
```

Preserves RG structure across tenant boundaries.

## Behavior

### Default Behavior (Flag Not Specified)

Without `--preserve-rg-structure`, all resources are consolidated into a single target resource group:

```
Source: 3 RGs, 50 resources
Target: 1 RG (atevet12-Working), 50 resources
```

### With --preserve-rg-structure

The source RG structure is preserved:

```
Source: 3 RGs, 50 resources
Target: 3 RGs (matching names), 50 resources
```

### Resource Group Naming

Resource group names are preserved from source by default. Use `--resource-group-prefix` to add a prefix:

```bash
--preserve-rg-structure --resource-group-prefix "migrated-"
```

Result:
```
Source: team-frontend-rg
Target: migrated-team-frontend-rg
```

### Azure-Managed Resource Groups

Azure-managed resource groups (created automatically by Azure services) are skipped:
- `NetworkWatcherRG*`
- `*_managed` resource groups (e.g., AKS node resource groups)

These cannot be created via Terraform and are excluded from generation.

## Cross-Resource-Group Dependencies

The feature automatically handles dependencies that span resource groups.

### Example: VNet Peering

```
Source:
├── network-rg
│   └── vnet-hub (10.0.0.0/16)
└── spoke-rg
    └── vnet-spoke (10.1.0.0/16)
    └── VNet peering: vnet-spoke → vnet-hub
```

Generated Terraform correctly references the hub VNet in the peering resource:

```hcl
resource "azurerm_virtual_network_peering" "spoke_to_hub" {
  name                      = "vnet-spoke-to-vnet-hub"
  resource_group_name       = azurerm_resource_group.spoke_rg.name
  virtual_network_name      = azurerm_virtual_network.vnet_spoke.name
  remote_virtual_network_id = azurerm_virtual_network.vnet_hub.id  # Cross-RG reference
}
```

### Example: Private Endpoint

```
Source:
├── data-rg
│   └── storage-account-prod
└── app-rg
    └── private-endpoint (connects to storage-account-prod)
```

The private endpoint in `app-rg` correctly references the storage account in `data-rg`:

```hcl
resource "azurerm_private_endpoint" "app_storage_pe" {
  resource_group_name = azurerm_resource_group.app_rg.name
  # ...
  private_service_connection {
    private_connection_resource_id = azurerm_storage_account.storage_account_prod.id  # Cross-RG
  }
}
```

## Generated Terraform Structure

### Without --preserve-rg-structure (Default)

```
outputs/iac-out-<timestamp>/
└── main.tf.json
```

Single file with:
- 1 resource group resource
- All other resources in that RG

### With --preserve-rg-structure

```
outputs/iac-out-<timestamp>/
└── main.tf.json
```

Single file with:
- Multiple resource group resources (one per source RG)
- Resources grouped by their source RG
- Cross-RG dependencies handled via Terraform references

## Testing Your Deployment

### Verify Resource Group Creation

```bash
cd outputs/iac-out-<timestamp>
terraform init
terraform plan
```

Check that the plan shows creation of all expected resource groups:

```
Plan: 53 to add, 0 to change, 0 to destroy.

azurerm_resource_group.team_frontend_rg will be created
azurerm_resource_group.team_backend_rg will be created
azurerm_resource_group.team_shared_rg will be created
...
```

### Validate Cross-RG References

Search for cross-RG dependencies in the plan output:

```bash
terraform plan | grep "azurerm_.*\\..*\\.id"
```

Ensure references are valid and point to resources in the correct RGs.

### Deploy and Verify

```bash
terraform apply
```

After deployment, verify resources are in correct RGs:

```bash
az resource list --resource-group team-frontend-rg --output table
az resource list --resource-group team-backend-rg --output table
az resource list --resource-group team-shared-rg --output table
```

## Troubleshooting

### Issue: "Resource group not found" errors during apply

**Cause**: Terraform tries to create resources before their RG exists.

**Solution**: This is usually a dependency resolution issue. Check that resource group resources are defined before resources that use them. The feature automatically handles this ordering.

### Issue: Cross-RG references fail

**Cause**: Invalid Terraform resource reference.

**Solution**: Check the generated Terraform for proper `depends_on` clauses and resource references. File an issue if references are incorrect.

### Issue: Too many resource groups created

**Cause**: All source RGs are being replicated, including test/dev RGs you don't want.

**Solution**: Use filtered scanning to scan only the RGs you want to replicate:

```bash
azure-tenant-grapher scan --filter-by-rgs "prod-*,shared-*"
azure-tenant-grapher generate-iac --preserve-rg-structure
```

## Best Practices

### 1. Scan Only What You Need

Use filtered scanning to avoid replicating unnecessary resource groups:

```bash
--filter-by-rgs "production-*,shared-services-*"
```

### 2. Review Generated Terraform Before Applying

Always run `terraform plan` and review the output before applying, especially for cross-RG dependencies.

### 3. Use Resource Group Prefixes for Safety

Add a prefix to target RGs to avoid naming conflicts:

```bash
--resource-group-prefix "replica-"
```

### 4. Test with Small Subsets First

Test the feature with a small number of resource groups first:

```bash
--filter-by-rgs "test-rg-1,test-rg-2"
```

### 5. Combine with Other Validation Flags

Use with other validation features for safer deployments:

```bash
--preserve-rg-structure \
--skip-name-validation=false \
--check-conflicts=true
```

## Limitations

### 1. Azure-Managed Resource Groups

Cannot replicate Azure-managed resource groups (these are automatically created by Azure services).

### 2. Resource Group Location

All target resource groups are created in the same location (specified by `--location` or default).

### 3. Resource Group Properties

Only the following RG properties are preserved:
- Name
- Location
- Tags

Other properties (locks, policies) are not replicated.

### 4. Naming Conflicts

If multiple source RGs have the same name across different subscriptions, use `--resource-group-prefix` to disambiguate.

## Implementation Notes

### File Structure

The feature is implemented across:
- `src/iac/cli_handler.py`: CLI flag handling
- `src/iac/traverser.py`: Resource grouping by source RG
- `src/iac/emitters/terraform/emitter.py`: RG-aware emission logic
- `src/iac/emitters/terraform/utils/resource_helpers.py`: RG extraction utilities

### Backward Compatibility

The feature is fully backward compatible. Default behavior (single RG consolidation) is unchanged unless `--preserve-rg-structure` is explicitly specified.

## Related Features

- **Cross-RG Dependency Handling** (Issue #310): Foundation for cross-RG references
- **Name Conflict Validation** (GAP-014): Ensures unique names across RGs
- **VNet Address Space Validation** (GAP-012): Validates network configurations across RGs

## References

- GitHub Issue: #313 (GAP-017)
- Implementation Plan: `docs/GAP-017_IMPLEMENTATION_PLAN.md`
- Cross-RG Dependency Docs: `docs/iac/CROSS_RG_DEPENDENCY_HANDLING.md`

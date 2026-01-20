# Community-Based Terraform Splitting

## Overview

The community splitting feature allows Terraform generation to be split into multiple independent files based on graph communities (connected components). This enables parallel deployment, better error isolation, and faster validation for large Azure tenant replications.

## Usage

### Basic Usage

```bash
# Generate split Terraform files by community
azure-tenant-grapher generate-iac \
  --format terraform \
  --output-dir ./terraform-output \
  --split-by-community
```

### Output Structure

```
terraform-output/
├── community_0_245_vnet.tf.json          # Networking resources
├── community_1_103_vm.tf.json            # Compute resources
├── community_2_12_storage.tf.json        # Storage resources
├── community_manifest.json               # Metadata
└── ...
```

### Parallel Deployment

Deploy all communities simultaneously:

```bash
cd terraform-output

# Deploy all communities in parallel
for tf in community_*.tf.json; do
  (terraform apply -auto-approve "$tf") &
done
wait

echo "All communities deployed!"
```

## Community Detection

**Community**: A set of resources connected by any relationship path (RBAC, networking, dependencies, etc.)

**Algorithm**: Uses Neo4j graph traversal to detect weakly connected components:
- Resources connected directly or transitively are in the same community
- Isolated resources form single-resource communities
- Communities are independent deployment units

## File Naming Convention

Format: `community_<id>_<size>_<type>.tf.json`

- **id**: Community index (0-based, sorted by size)
- **size**: Number of resources in community
- **type**: Dominant resource type (e.g., vnet, vm, storage)

**Examples**:
- `community_0_1245_vm.tf.json` - 1,245 resources, mostly VMs
- `community_1_450_vnet.tf.json` - 450 resources, mostly VNets

## Community Manifest

The `community_manifest.json` file contains metadata about all communities:

```json
{
  "total_communities": 12,
  "total_resources": 3042,
  "split_strategy": "graph_connectivity",
  "generated_at": "2026-01-20T10:30:00Z",
  "communities": [
    {
      "id": 0,
      "file": "community_0_1245_vm.tf.json",
      "size": 1245,
      "resource_types": {
        "azurerm_virtual_machine": 450,
        "azurerm_network_interface": 450,
        "azurerm_managed_disk": 345
      },
      "dominant_type": "azurerm_virtual_machine"
    }
  ]
}
```

## Benefits

### 1. Parallel Deployment
Deploy multiple communities simultaneously instead of waiting for one giant file:
- **Before**: 3,000 resources in 1 file = ~45 minutes sequential
- **After**: 12 communities in parallel = ~5-10 minutes

### 2. Better Error Isolation
Errors in one community don't block deployment of others:
```
Community 3 fails (storage issue)
→ Communities 0, 1, 2, 4-11 deploy successfully
→ Fix community 3 and redeploy only that file
```

### 3. Faster Validation
Smaller files validate faster:
- **Before**: `terraform validate` on 3,000 resources = 2-3 minutes
- **After**: `terraform validate` on 250 resources = 10-20 seconds per community

### 4. No Cross-Community References
Generation FAILS if resources reference across communities, preventing "undeclared resource" errors:
```
ERROR: Cross-community reference detected
  Source: azurerm_virtual_machine.vm1 (community_0)
  Target: azurerm_virtual_network.vnet2 (community_3)

Communities must be self-contained deployment units.
```

## Backward Compatibility

Default behavior (single file) is preserved when flag is NOT used:

```bash
# Old behavior (still works)
azure-tenant-grapher generate-iac --format terraform --output-dir ./output
# → Generates single main.tf.json file
```

## Edge Cases

### Single-Resource Communities
Resources with no relationships become single-resource communities:
```
community_8_1_keyvault.tf.json  # Valid - isolated Key Vault
```

### Orphaned Resources
Each orphaned resource gets its own file (acceptable):
```
community_10_1_appservice.tf.json
community_11_1_loganalytics.tf.json
```

### Provider Configuration
Each community file includes the provider block for independent deployment:
```json
{
  "provider": {
    "azurerm": [{"features": {}}]
  },
  "resource": { ... }
}
```

## Limitations

1. **Cross-Community References**: Not supported (validation error)
2. **Maximum Communities**: 1,000 (filesystem limit)
3. **State Management**: User must configure shared backend
4. **Terraform Version**: All files must use same provider version

## Troubleshooting

### "Cross-community reference detected"
**Cause**: Resource in one community references resource in another
**Solution**: These resources should be in the same community - check graph relationships

### "No communities detected"
**Cause**: Empty graph or all resources isolated
**Solution**: Verify graph has resources, check community detection

### "Too many communities (>1000)"
**Cause**: Graph too fragmented
**Solution**: Reduce graph scope with filtered scanning

## See Also

- `CommunityDetector` class: `src/iac/community_detector.py`
- `CommunitySplitter` class: `src/iac/community_splitter.py`
- CLI Reference: `docs/CLI_COMMANDS.md`

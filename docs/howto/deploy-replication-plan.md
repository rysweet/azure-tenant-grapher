# How to Deploy from Architecture-Based Replication Plans

This guide shows you how to deploy infrastructure to a target Azure tenant using architecture-based replication plans. This approach automatically analyzes your source tenant's architectural patterns and replicates them to a new environment.

## Prerequisites

Before you begin, ensure you have:

1. **Source Tenant Scan**
   - Scanned your source Azure tenant using `azure-tenant-grapher scan`
   - Neo4j database contains the source tenant graph data

2. **Neo4j Container Running**
   - Docker container with Neo4j is running and accessible
   - Environment variables configured (`NEO4J_URI` or `NEO4J_PORT`, `NEO4J_USER`, `NEO4J_PASSWORD`)

3. **Azure Authentication**
   - Authenticated to target Azure tenant using `az login`
   - Have permissions to create resources in the target tenant

4. **Environment Variables Set**
   ```bash
   export NEO4J_URI="bolt://localhost:7687"  # or NEO4J_PORT=7687
   export NEO4J_USER="neo4j"
   export NEO4J_PASSWORD="your-password"
   export AZURE_TENANT_ID="your-target-tenant-id"  # optional
   ```

## Basic Deployment

Deploy all architectural patterns from the source tenant to the target tenant:

```bash
azure-tenant-grapher deploy \
  --from-replication-plan \
  --target-tenant-id <TARGET_TENANT_ID> \
  --resource-group "replicated-infrastructure" \
  --location "eastus"
```

This command will:
1. Analyze the source tenant and detect architectural patterns
2. Generate a replication plan with representative resource instances
3. Convert the plan to a deployment graph with relationships
4. Generate Terraform IaC (default format)
5. Deploy the infrastructure to the target tenant

## Pattern Filtering

Deploy only specific architectural patterns:

```bash
azure-tenant-grapher deploy \
  --from-replication-plan \
  --pattern-filter "Web Application" \
  --pattern-filter "VM Workload" \
  --target-tenant-id <TARGET_TENANT_ID> \
  --resource-group "web-and-vm-infrastructure"
```

**Available Patterns**: The exact pattern names depend on your source tenant. Common examples:
- "Web Application" (sites, serverFarms, storageAccounts)
- "VM Workload" (virtualMachines, networkInterfaces, disks)
- "Container Platform" (containerRegistries, managedClusters, containerInstances)
- "Database Services" (sqlServers, databases, managedInstances)

To see detected patterns, check the output during the analysis phase.

## Instance Filtering

Deploy only specific instances of a pattern:

```bash
# Deploy first and third instances only (zero-indexed)
azure-tenant-grapher deploy \
  --from-replication-plan \
  --pattern-filter "Web Application" \
  --instance-filter "0,2" \
  --target-tenant-id <TARGET_TENANT_ID> \
  --resource-group "web-app-subset"

# Deploy a range of instances
azure-tenant-grapher deploy \
  --from-replication-plan \
  --pattern-filter "VM Workload" \
  --instance-filter "0-3" \
  --target-tenant-id <TARGET_TENANT_ID> \
  --resource-group "vm-workload-range"
```

**Instance Filter Syntax**:
- Single indices: `"0,2,5"` - Deploy instances at positions 0, 2, and 5
- Ranges: `"0-3"` - Deploy instances at positions 0, 1, 2, and 3
- Mixed: `"0,2-4,7"` - Deploy instances at positions 0, 2, 3, 4, and 7

## IaC Format Selection

Generate IaC in different formats:

```bash
# Terraform (default)
azure-tenant-grapher deploy \
  --from-replication-plan \
  --format terraform \
  --target-tenant-id <TARGET_TENANT_ID> \
  --resource-group "terraform-deployed"

# Bicep
azure-tenant-grapher deploy \
  --from-replication-plan \
  --format bicep \
  --target-tenant-id <TARGET_TENANT_ID> \
  --resource-group "bicep-deployed"

# ARM Templates
azure-tenant-grapher deploy \
  --from-replication-plan \
  --format arm \
  --target-tenant-id <TARGET_TENANT_ID> \
  --resource-group "arm-deployed"
```

## Dry-Run Mode

Preview the deployment without actually creating resources:

```bash
azure-tenant-grapher deploy \
  --from-replication-plan \
  --target-tenant-id <TARGET_TENANT_ID> \
  --resource-group "preview-deployment" \
  --dry-run
```

This will:
- Analyze patterns and generate the replication plan
- Create the TenantGraph with relationships
- Generate IaC files in `./output/iac-from-replication/`
- Skip the actual deployment to Azure

Review the generated IaC files before running without `--dry-run`.

## Complete Example Workflow

Here's a complete workflow from scan to deployment:

```bash
# Step 1: Scan source tenant (if not already done)
azure-tenant-grapher scan --tenant-id <SOURCE_TENANT_ID>

# Step 2: Verify Neo4j is running
docker ps | grep neo4j

# Step 3: Set environment variables
export NEO4J_URI="bolt://localhost:7687"
export NEO4J_USER="neo4j"
export NEO4J_PASSWORD="your-password"

# Step 4: Preview deployment (dry-run)
azure-tenant-grapher deploy \
  --from-replication-plan \
  --target-tenant-id <TARGET_TENANT_ID> \
  --resource-group "replicated-infra" \
  --dry-run

# Step 5: Review generated IaC
ls -la ./output/iac-from-replication/

# Step 6: Deploy to target tenant
azure-tenant-grapher deploy \
  --from-replication-plan \
  --target-tenant-id <TARGET_TENANT_ID> \
  --resource-group "replicated-infra" \
  --location "eastus"
```

## Troubleshooting

### Error: NEO4J_PASSWORD environment variable is required

**Solution**: Set the Neo4j password environment variable:
```bash
export NEO4J_PASSWORD="your-neo4j-password"
```

### Error: No architectural patterns detected

**Possible causes**:
1. Source tenant doesn't have enough resources (minimum 5-10 resources recommended)
2. Neo4j database is empty (scan not completed)
3. Neo4j connection failed

**Solution**: Verify Neo4j connection and re-scan source tenant:
```bash
# Check Neo4j is running
docker ps | grep neo4j

# Re-scan source tenant
azure-tenant-grapher scan --tenant-id <SOURCE_TENANT_ID>
```

### Error: Pattern filter excludes all patterns

**Possible causes**:
1. Pattern name doesn't match exactly (case-sensitive)
2. Typo in pattern name

**Solution**: Run without `--pattern-filter` first to see available pattern names in the analysis output.

### Warning: No relationships found between resources

**This is normal if**:
- Resources are independent (no CONTAINS, DEPENDS_ON, etc. relationships)
- You're deploying a single resource type

**Action**: The deployment will succeed, but resources won't have explicit dependencies in IaC.

### Deployment fails with Terraform/Bicep errors

**Solution**: Check generated IaC files in `./output/iac-from-replication/`:
```bash
# For Terraform
cd ./output/iac-from-replication
terraform validate

# For Bicep
az bicep build --file main.bicep
```

Review validation errors and adjust if needed. Some Azure resources may require manual configuration.

## Tips and Best Practices

### Start Small
- Use `--pattern-filter` and `--instance-filter` for initial deployments
- Validate one pattern at a time before deploying everything

### Use Dry-Run First
- Always run with `--dry-run` first to preview what will be deployed
- Review generated IaC for correctness

### Pattern Discovery
- Run deployment without filters first to see all detected patterns
- Note the exact pattern names (case-sensitive) for filtering

### Resource Group Strategy
- Use different resource groups for different patterns
- Makes cleanup easier if deployment needs to be reverted

### Location Selection
- Ensure target location supports all resource types in your patterns
- Some Azure services are region-specific

### Monitor Deployments
- Watch deployment output for errors or warnings
- Check Azure Portal to verify resources are created correctly

## Next Steps

- Learn about [Architecture-Based Deployment Concepts](../concepts/architecture-based-deployment.md)
- Understand [Architectural Pattern Analysis](../ARCHITECTURAL_PATTERN_ANALYSIS.md)
- Explore [Architecture-Based Replication](../ARCHITECTURE_BASED_REPLICATION.md)

## See Also

- [Tenant Reset Quick Reference](TENANT_RESET_QUICK_REFERENCE.md) - Clean up deployed resources
- [IaC Plugin Architecture](../DATAPLANE_PLUGIN_ARCHITECTURE.md) - Data plane replication options
- [Contributing Guidelines](../CONTRIBUTING.md) - Contribute improvements

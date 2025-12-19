# Tutorial: Your First Autonomous Deployment

This tutorial walks you through using the goal-seeking deployment agent to autonomously deploy Azure infrastructure from a scanned tenant.

**Time to complete:** 15-30 minutes

**What you'll learn:**
- How to generate IaC from a scanned tenant
- How to enable autonomous deployment with the agent
- How to interpret deployment reports
- How to troubleshoot common issues

**Prerequisites:**
- Azure Tenant Grapher installed and configured
- Azure CLI authenticated with target tenant
- At least one tenant scanned into Neo4j graph

## Step 1: Generate IaC from Scanned Tenant

First, generate Infrastructure-as-Code from your scanned tenant:

```bash
# List available scanned tenants
atg list-tenants

# Generate IaC for cross-tenant deployment
atg generate-iac \
  --tenant-id <SOURCE_TENANT_ID> \
  --target-tenant-id <TARGET_TENANT_ID> \
  --format terraform \
  --output ./my-deployment

# Expected output:
# ✓ Generated 156 resources
# ✓ Created deployment scripts
# ✓ IaC written to: ./my-deployment
```

**What just happened:**
- ATG queried Neo4j graph for source tenant
- Traversed relationships to find all resources
- Translated source IDs to abstracted IDs for target tenant
- Generated Terraform templates with dependencies

## Step 2: Review Generated IaC (Optional)

Before deploying, you can inspect what was generated:

```bash
# View generated structure
tree ./my-deployment

# Output:
# my-deployment/
#   ├── main.tf              # Provider and backend config
#   ├── resource_groups.tf   # Resource group definitions
#   ├── networking.tf        # VNets, subnets, NSGs
#   ├── compute.tf           # VMs, disks
#   ├── storage.tf           # Storage accounts
#   └── variables.tf         # Input variables

# View a specific file
cat ./my-deployment/compute.tf
```

**Key things to look for:**
- Resource names use abstracted IDs (e.g., `vm-a1b2c3d4`)
- Dependencies are correctly ordered
- Network configurations are valid

## Step 3: Authenticate with Target Tenant

Make sure you're authenticated with the target tenant:

```bash
# Logout from current session
az logout

# Login to target tenant
az login --tenant <TARGET_TENANT_ID>

# Set the target subscription
az account set --subscription <TARGET_SUBSCRIPTION_ID>

# Verify authentication
az account show
```

**Expected output:**
```json
{
  "id": "your-subscription-id",
  "name": "Your Subscription",
  "tenantId": "your-target-tenant-id",
  "state": "Enabled"
}
```

## Step 4: Deploy with Agent Mode (First Attempt)

Now deploy with autonomous error recovery enabled:

```bash
atg deploy \
  --agent \
  --path ./my-deployment \
  --format terraform

# You'll see live progress:
# Starting autonomous deployment...
# Iteration 1: Attempting deployment...
```

**What happens during iteration 1:**

The agent executes `terraform apply` and captures the output. Let's say it fails with a common error:

```
Error: Provider not registered: Microsoft.Network

The subscription is not registered to use namespace 'Microsoft.Network'.
```

**Agent response:**
```
Iteration 1: FAILED (duration: 45s)
Analyzing error with AI...
AI Analysis: Missing Azure resource provider registration
Generating fix...
Fix: Register Microsoft.Network provider
Applying fix to IaC...
✓ Modified: main.tf (added provider registration)

Iteration 2: Attempting deployment...
```

## Step 5: Watch the Agent Work

The agent continues iterating automatically:

**Iteration 2:**
```
Iteration 2: Attempting deployment...
Progress: Creating resource groups... ✓
Progress: Creating virtual networks... ✗

Error: InvalidVMSize
Virtual machine size 'Standard_D4s_v3' is not available in location 'eastus2'.

Iteration 2: FAILED (duration: 178s)
Analyzing error with AI...
AI Analysis: VM SKU not available in target region
Fix: Change VM size to Standard_D4s_v5 (available in eastus2)
Applying fix...
✓ Modified: compute.tf (line 42: size = "Standard_D4s_v5")

Iteration 3: Attempting deployment...
```

**Iteration 3:**
```
Iteration 3: Attempting deployment...
Progress: Creating resource groups... ✓ (skipped, already exists)
Progress: Creating virtual networks... ✓
Progress: Creating subnets... ✓
Progress: Creating network security groups... ✓
Progress: Creating storage accounts... ✓
Progress: Creating virtual machines... ✓

Iteration 3: SUCCESS (duration: 248s)
Resources deployed: 156
```

## Step 6: Review the Deployment Report

After deployment completes, check the generated report:

```bash
cat ./my-deployment/deployment_report.md
```

**Sample report:**

```markdown
# Deployment Report - 2025-12-18 15:30:42

## Summary
- **Status:** SUCCESS
- **Total Iterations:** 3
- **Total Duration:** 471 seconds (7.9 minutes)
- **Resources Deployed:** 156

## Iteration History

### Iteration 1 (FAILED)
**Duration:** 45 seconds
**Error:** Provider not registered: Microsoft.Network

**AI Analysis:**
The deployment failed because the Microsoft.Network resource provider
is not registered in the target subscription. This is required for
creating virtual networks and related networking resources.

**Fix Applied:**
Added provider registration block to main.tf:

```terraform
resource "azurerm_resource_provider_registration" "network" {
  name = "Microsoft.Network"
}
```

**Files Modified:**
- main.tf (added provider registration)

### Iteration 2 (FAILED)
**Duration:** 178 seconds
**Error:** InvalidVMSize - Standard_D4s_v3 not available

**AI Analysis:**
The VM SKU 'Standard_D4s_v3' specified in the source tenant is not
available in the target region (eastus2). The error indicates that
Standard_D4s_v5 series is available in this region.

**Fix Applied:**
Updated VM size in compute.tf:

```diff
- size = "Standard_D4s_v3"
+ size = "Standard_D4s_v5"
```

**Files Modified:**
- compute.tf (line 42: VM size updated)

### Iteration 3 (SUCCESS)
**Duration:** 248 seconds
**Resources Created:** 156

**Breakdown:**
- Resource Groups: 3
- Virtual Networks: 2
- Subnets: 8
- Network Security Groups: 4
- Storage Accounts: 6
- Virtual Machines: 12
- Managed Disks: 24
- Network Interfaces: 12
- Public IPs: 4
- Other Resources: 81

**Warnings:**
- 3 role assignments skipped (cross-tenant identity mapping not configured)

## Recommendations

### For Future Deployments to eastus2:
1. Pre-register providers: Microsoft.Network, Microsoft.Compute, Microsoft.Storage
2. Use Standard_D4s_v5 for VMs instead of Standard_D4s_v3
3. Consider implementing identity mapping for role assignments (see docs/cross-tenant/)

### Time-Saving Tips:
Run these commands before next deployment:
```bash
az provider register --namespace Microsoft.Network --wait
az provider register --namespace Microsoft.Compute --wait
az provider register --namespace Microsoft.Storage --wait
```

## Troubleshooting

If you encounter similar errors in future deployments:

**Provider Registration Errors:**
```bash
# List all providers
az provider list --query "[].{Namespace:namespace, State:registrationState}"

# Register a provider
az provider register --namespace <NAMESPACE> --wait
```

**VM SKU Availability:**
```bash
# Check available VM sizes in a region
az vm list-skus --location eastus2 --size Standard_D --output table
```

## Deployment Artifacts

All iteration artifacts preserved in:
- `./my-deployment/iteration_1/` - First attempt (failed)
- `./my-deployment/iteration_2/` - Second attempt (failed)
- `./my-deployment/iteration_3/` - Final successful deployment

Terraform state file: `./my-deployment/terraform.tfstate`
```

## Step 7: Verify Deployed Resources

Confirm resources were created in Azure:

```bash
# List all resource groups created
az group list --query "[].name" --output table

# Check resources in a specific group
az resource list --resource-group <RG_NAME> --output table

# Verify a specific VM
az vm show --name <VM_NAME> --resource-group <RG_NAME>
```

**Expected output:**
You should see all 156 resources successfully deployed to your target tenant.

## Common Scenarios and Variations

### Scenario A: Deployment Succeeds on First Try

If your target environment is well-configured, deployment might succeed immediately:

```bash
atg deploy --agent --path ./my-deployment

# Output:
# Iteration 1: Attempting deployment...
# Iteration 1: SUCCESS (duration: 312s)
# Resources deployed: 156
```

**No AI fixes needed!** The agent still generates a report documenting the successful deployment.

### Scenario B: Deployment Requires Many Iterations

For complex environments, you might need more iterations:

```bash
# Increase iteration limit for complex deployments
atg deploy --agent --max-iterations 10 --path ./my-deployment

# Output:
# Iteration 1: FAILED (provider issue)
# Iteration 2: FAILED (SKU issue)
# Iteration 3: FAILED (network conflict)
# Iteration 4: FAILED (quota limit)
# Iteration 5: SUCCESS
```

The agent will try up to 10 times, fixing errors along the way.

### Scenario C: Dry Run to Preview

Before actually deploying, preview what the agent would do:

```bash
atg deploy --agent --dry-run --path ./my-deployment

# Output:
# DRY RUN: No resources will be deployed
# Iteration 1 (simulated):
#   - Would attempt: terraform apply
#   - Would create: 156 resources
# Report: Would generate deployment_report.md
```

### Scenario D: Large Deployment with Extended Timeout

For large deployments that take longer:

```bash
atg deploy \
  --agent \
  --max-iterations 7 \
  --timeout 900 \
  --path ./my-deployment

# Each iteration gets 1100 minutes instead of default 100 minutes
```

## Understanding What Can Go Wrong

### The Agent Reaches Max Iterations

**What happens:**
```bash
Iteration 5: FAILED (duration: 267s)
Error: [Some persistent error]

Maximum iterations (5) reached without success.
Deployment failed.

Report generated: ./my-deployment/deployment_report.md
```

**What to do:**
1. Check the deployment report for patterns
2. Look at the errors across iterations
3. Identify if there's a persistent issue (quota, permission, etc.)
4. Fix the root cause manually
5. Try again with `atg deploy --agent`

**Example manual fixes:**
```bash
# If quota issue:
az vm list-usage --location eastus2
# Request quota increase through Azure portal

# If permission issue:
az role assignment create --role Contributor --assignee <YOUR_ID> --scope /subscriptions/<SUB_ID>

# If network conflict:
# Manually edit networking.tf to adjust CIDR ranges
```

### Understanding AI-Generated Fixes

**Good fixes the agent can make:**
- Register missing providers
- Adjust VM SKUs for region availability
- Fix resource naming conflicts
- Adjust network CIDR ranges
- Modify resource properties for compatibility

**Fixes the agent cannot make:**
- Increase Azure quotas (requires portal or support ticket)
- Fix authentication/permission issues (requires Azure RBAC changes)
- Resolve Azure service outages (requires waiting)

## Best Practices from This Tutorial

1. **Always review IaC before deploying** - Even with agent mode, understanding what's being deployed is important

2. **Start with small deployments** - Test agent mode on 10-20 resources before trying 300+

3. **Use appropriate iteration limits** - More complex = more iterations needed

4. **Read the deployment reports** - They contain valuable lessons for future deployments

5. **Pre-register common providers** - Saves time on future deployments:
   ```bash
   az provider register --namespace Microsoft.Network --wait
   az provider register --namespace Microsoft.Compute --wait
   az provider register --namespace Microsoft.Storage --wait
   ```

6. **Keep authentication fresh** - For long deployments, use service principal instead of interactive login

## Next Steps

Now that you've completed your first autonomous deployment, explore:

- **[Cross-Tenant Features](../cross-tenant/FEATURES.md)** - Deploy between different Azure tenants
- **[Terraform Import Blocks](../design/cross-tenant-translation/CLI_FLAGS_SUMMARY.md)** - Import existing resources
- **[Deployment Troubleshooting](../guides/AUTONOMOUS_DEPLOYMENT_FAQ.md)** - Manual troubleshooting techniques
- **[Agent Deployer Reference](../design/AGENT_DEPLOYER_REFERENCE.md)** - Technical details

## Troubleshooting This Tutorial

### "Command not found: atg"

Make sure you're in the virtual environment:
```bash
source .venv/bin/activate
```

### "Neo4j connection failed"

Start Neo4j container:
```bash
docker-compose -f docker/docker-compose.yml up -d neo4j
```

### "No tenants found"

Scan a tenant first:
```bash
atg scan --tenant-id <YOUR_TENANT_ID>
```

### "Authentication failed"

Re-authenticate with Azure:
```bash
az logout
az login --tenant <TARGET_TENANT_ID>
```

## Summary

Congratulations! You've learned:
- ✓ How to generate IaC from a scanned tenant
- ✓ How to enable autonomous deployment with `--agent`
- ✓ How the agent iteratively fixes deployment errors
- ✓ How to interpret deployment reports
- ✓ Common error scenarios and solutions

The goal-seeking deployment agent saves time by automatically handling common deployment issues, letting you focus on higher-level infrastructure decisions.

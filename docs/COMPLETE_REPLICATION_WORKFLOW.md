# Complete Architecture-Based Replication Workflow

This guide explains the **complete end-to-end workflow** for architecture-based tenant replication, including subscription handling and target cleanup.

## Understanding Azure Subscriptions

### Important: Subscriptions Cannot Be "Created" Programmatically

**Azure subscriptions are NOT created by the replication tool.** Subscriptions are:

- Created at the Azure account level (Azure portal, Enterprise Agreement, etc.)
- Associated with billing accounts
- Cannot be created via ARM, Terraform, or most APIs
- Must already exist before deployment

### What This Tool Does

The tool **deploys resources INTO an existing subscription** that you're already logged into via Azure CLI. You don't need to specify a subscription ID because it uses your current Azure context:

```bash
# Your current login context
az account show

# Output shows your active subscription:
{
  "id": "<target-subscription-id>",  ← This is your target
  "name": "Subscription 1",
  "tenantId": "<tenant-id>",
  "user": { "name": "user@domain.com" }
}
```

## Complete Workflow

### Prerequisites

1. **Two Azure Subscriptions**:
   - **Source**: Contains resources you want to replicate (already scanned into Neo4j)
   - **Target**: Empty subscription where replicas will be deployed (you're currently logged into this)

2. **Neo4j**: Running with source tenant data
   ```bash
   docker ps --filter "name=neo4j"
   ```

3. **Azure CLI**: Logged into TARGET tenant
   ```bash
   az login
   az account set --subscription "TARGET_SUBSCRIPTION_ID"
   az account show  # Verify you're in the right subscription
   ```

### Step 1: Clean Up Target Subscription (if needed)

If your target subscription has existing resources, clean them up first:

```bash
# Interactive cleanup with confirmation
./scripts/cleanup_target_tenant.sh

# Or with automatic confirmation (dangerous!)
./scripts/cleanup_target_tenant.sh --yes
```

**What this does**:
- Deletes ALL resource groups in the current subscription
- Deletes ALL resources
- Parallel deletion for speed
- Safety confirmations required

**Output**:
```
WARNING: TARGET TENANT CLEANUP
======================================================

Current Azure Context:
  Tenant ID:       <tenant-id>
  Subscription ID: <target-subscription-id>
  Subscription:    Subscription 1

Found:
  Resource Groups: 15
  Total Resources: 247

Type 'DELETE ALL RESOURCES' to continue: DELETE ALL RESOURCES
Are you absolutely sure? Type 'YES' to proceed: YES

[1/15] Deleting resource group: rg-webapp-prod
  Started deletion (async)...
[2/15] Deleting resource group: rg-vm-workload
  Started deletion (async)...
...

✓ Cleanup complete!
Ready for architecture-based replication!
```

### Step 2: Verify Your Azure Context

```bash
# Confirm you're logged into the TARGET subscription
az account show --query '{subscription:name, subscriptionId:id}'

# Expected output:
{
  "subscription": "Subscription 1",
  "subscriptionId": "<target-subscription-id>"
}
```

### Step 3: Set Neo4j Credentials

```bash
# Export your Neo4j password
export NEO4J_PASSWORD="your_neo4j_password_here"

# Verify it's set
echo $NEO4J_PASSWORD
```

### Step 4: Run Architecture-Based Replication

#### Option A: Interactive Script (Recommended for First Time)

```bash
./scripts/run_architecture_replication.sh
```

The script will:
1. Connect to Neo4j
2. Show available source subscriptions
3. Prompt you to select source subscription
4. Auto-detect your current Azure subscription as target
5. Run the orchestrator
6. Generate comprehensive reports

**Example interaction**:
```
Architecture-Based Tenant Replication
======================================================

[1/5] Checking Neo4j connection...
✓ Neo4j container is running

[2/5] Verifying Neo4j credentials...

[3/5] Querying available subscriptions...

Available subscriptions in Neo4j:
--------------------------------------------------------------------------------
  1. <source-subscription-id> (410 resources)
  2. <subscription-2-id> (158 resources)
--------------------------------------------------------------------------------

✓ Neo4j connection successful

[4/5] Configuring replication parameters...
Enter source subscription ID (or number from list above): 1

✓ Found current Azure subscription: <target-subscription-id>
Use this as target subscription? (Y/n): Y

Configuration:
  Source Subscription: <source-subscription-id>
  Target Subscription: <target-subscription-id>
  Instance Count: 10

[5/5] Running replication orchestrator...
Output directory: ./output/replication_20250218_120000
```

#### Option B: Direct Execution

If you already know your source subscription ID:

```bash
python3 scripts/architecture_replication_with_fidelity.py \
    --source-subscription <source-subscription-id> \
    --target-subscription <target-subscription-id> \
    --target-instance-count 10 \
    --output-dir ./output/test_run \
    --neo4j-password $NEO4J_PASSWORD
```

**Note**: The `--target-subscription` should match your current `az account show` subscription.

### Step 5: Review Results

After the workflow completes, check the output directory:

```bash
# Navigate to output directory
cd output/replication_20250218_120000

# List generated files
ls -lh

# Output:
# 00_COMPREHENSIVE_REPORT.md          - Human-readable summary
# 01_analysis_summary.json            - Source analysis
# 02_replication_plan.json            - Selected instances
# 03_resource_mappings.json           - Source-to-target mappings
# 04_deployment_summary.json          - Deployment status
# 05_fidelity_validation.json         - Fidelity comparison

# Read the comprehensive report
cat 00_COMPREHENSIVE_REPORT.md
```

### Step 6: Understand the Output

#### Replication Plan (`02_replication_plan.json`)

Shows which resource instances were selected:

```json
{
  "total_instances": 10,
  "patterns": {
    "Virtual Machine Workload": {
      "instance_count": 3,
      "resource_count": 15
    },
    "Web Application": {
      "instance_count": 2,
      "resource_count": 8
    }
  }
}
```

#### Resource Mappings (`03_resource_mappings.json`)

Explicit source-to-target mappings for validation:

```json
[
  {
    "source_id": "/subscriptions/SOURCE/.../vm1",
    "source_name": "vm1",
    "source_type": "Microsoft.Compute/virtualMachines",
    "target_id": "/subscriptions/TARGET/.../vm1-replica",
    "target_name": "vm1-replica",
    "target_type": "Microsoft.Compute/virtualMachines",
    "pattern": "Virtual Machine Workload"
  }
]
```

#### Fidelity Validation (`05_fidelity_validation.json`)

Property-level comparison results:

```json
{
  "summary": {
    "total_resources": 23,
    "exact_match": 18,
    "drifted": 3,
    "missing_target": 2,
    "missing_source": 0,
    "match_percentage": 78.3
  },
  "resources": [
    {
      "name": "vm1",
      "type": "Microsoft.Compute/virtualMachines",
      "status": "exact_match",
      "mismatch_count": 0
    }
  ]
}
```

## Current Limitation: Deployment is Placeholder

**IMPORTANT**: The current implementation does NOT actually deploy resources. Stage 4 (Deployment) is a placeholder.

### What Happens Now

The orchestrator:
1. ✅ Analyzes source tenant
2. ✅ Generates replication plan
3. ✅ Creates source-target mappings
4. ⚠️  **SIMULATES deployment** (no actual resources created)
5. ✅ Validates fidelity (using Neo4j data)

### Why?

The deployment stage requires:
- IaC generation (Terraform/Bicep) from replication plan
- Integration with existing `src/deployment/` infrastructure
- Error handling and retry logic
- State management

### What You Get

Even without actual deployment, you get:
- Complete replication plan showing what WOULD be deployed
- Exact resource mappings for fidelity tracking
- Framework ready for IaC integration
- Validation logic that works with real deployments

## Next Steps: Integrating Real Deployment

To enable actual deployment:

### 1. Generate IaC from Replication Plan

Modify `_deploy_resources()` in `scripts/architecture_replication_with_fidelity.py`:

```python
async def _deploy_resources(self, selected_instances: List[tuple]) -> Dict[str, Any]:
    """Deploy resources using existing IaC generators."""
    from src.iac.engine import IaCEngine
    from src.deployment.orchestrator import deploy_iac

    # Generate IaC from selected instances
    iac_dir = self.output_dir / "generated_iac"
    engine = IaCEngine(...)
    engine.generate_from_instances(selected_instances, output_dir=iac_dir)

    # Deploy using existing orchestrator
    result = deploy_iac(
        iac_dir=iac_dir,
        target_tenant_id=self.target_tenant_id,
        resource_group="replication-rg",
        subscription_id=self.target_subscription,
        iac_format="terraform",
        dry_run=False,
    )

    return result
```

### 2. Update Mappings with Real Resource IDs

After deployment, update mappings with actual deployed resource IDs:

```python
# Get deployed resources from Azure
deployed_resources = self._query_deployed_resources()

# Update mappings
for mapping in self.mappings:
    actual_target = self._find_deployed_resource(
        mapping.target_name,
        mapping.target_resource_type
    )
    if actual_target:
        mapping.target_resource_id = actual_target['id']
```

### 3. Re-run Fidelity Validation

After actual deployment:

```bash
# Run fidelity validation against real deployed resources
python3 scripts/architecture_replication_with_fidelity.py \
    --source-subscription SOURCE_ID \
    --target-subscription TARGET_ID \
    --skip-deployment \
    --validate-only
```

## Troubleshooting

### "Not logged in to Azure CLI"

```bash
# Login to target tenant
az login

# Set the subscription
az account set --subscription "<target-subscription-id>"

# Verify
az account show
```

### "Neo4j connection failed"

```bash
# Start Neo4j
docker start atg-neo4j

# Check it's running
docker ps --filter "name=neo4j"

# Test connection
docker exec atg-neo4j cypher-shell -u neo4j -p $NEO4J_PASSWORD "RETURN 1"
```

### "No subscriptions found in Neo4j"

```bash
# Scan source tenant first
# (Requires separate atg installation or access to source tenant)
atg scan --subscription-id SOURCE_SUBSCRIPTION_ID
```

### "Target subscription has existing resources"

```bash
# Clean up target subscription
./scripts/cleanup_target_tenant.sh
```

## Summary

**What Works Now**:
- ✅ Source tenant analysis
- ✅ Intelligent replication plan generation
- ✅ Source-target mapping creation
- ✅ Fidelity validation framework
- ✅ Comprehensive reporting

**What's Placeholder**:
- ⚠️  Actual resource deployment (Stage 4)

**Your Workflow**:
1. Clean target subscription: `./scripts/cleanup_target_tenant.sh`
2. Run replication: `./scripts/run_architecture_replication.sh`
3. Review outputs in `./output/replication_TIMESTAMP/`
4. (Future) Deploy resources using generated plan

## Related Documentation

- [Architecture Replication with Fidelity](./ARCHITECTURE_REPLICATION_WITH_FIDELITY.md)
- [Tenant Reset Safety Guide](./guides/TENANT_RESET_SAFETY.md)
- [Deployment Guide](./TENANT_REPLICATION_DEPLOYMENT_GUIDE.md)

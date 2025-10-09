# Cross-Tenant IaC Demo (CLI-Based)

This demo showcases the Azure Tenant Grapher CLI for cross-tenant infrastructure replication.

## Demo Scenario

**Source Tenant**: DefenderATEVET17 (Tenant 1)
**Target Tenant**: Simuland (Tenant 2)
**Resource Group**: SimuLand (90 resources)

## Prerequisites

1. Azure CLI authenticated to both tenants
2. Neo4j running with Tenant 1 already scanned
3. Service principal credentials for both tenants in `.env`
4. Sufficient quotas in Target Tenant

## Demo Workflow

### Step 1: Generate IaC from Source Tenant

Extract Infrastructure-as-Code for the SimuLand resource group:

```bash
./01_generate_iac.sh              # Original approach (manual Neo4j queries)
# OR
./01_generate_iac_v2.sh           # Improved approach (resource group filtering)
```

The v2 script uses the new `--subset-filter "resourceGroup=SimuLand"` option, eliminating the need for manual Neo4j queries.

### Step 2: Deploy to Target Tenant

Deploy the generated IaC to Tenant 2 using the new `atg deploy` command:

```bash
./02_deploy.sh
```

This script demonstrates:
- Auto-detection of IaC format (Terraform, Bicep, ARM)
- Dry-run validation before deployment
- Multi-tenant authentication switching
- Safety prompts for production deployments

### Step 3: Validate Deployment

Compare the source and target graphs using the new `atg validate-deployment` command:

```bash
./03_validate.sh
```

This script demonstrates:
- Graph comparison between source and target tenants
- Similarity scoring
- Missing/extra resource detection
- Markdown and JSON report generation

### Step 4: Cleanup

Remove deployed resources using the cleanup script:

```bash
./04_cleanup.sh
```

This script demonstrates:
- Safe deletion with confirmation prompts
- Support for Terraform destroy
- Resource group deletion for Bicep/ARM
- Cross-tenant cleanup operations

## Implementation Status

All 4 issues have been implemented and tested:

- ✅ **Issue #276** (P0): Fix Cypher Syntax Error - [PR #280](https://github.com/rysweet/azure-tenant-grapher/pull/280)
- ✅ **Issue #277** (P1): Add Resource Group Filtering - [PR #281](https://github.com/rysweet/azure-tenant-grapher/pull/281)
- ✅ **Issue #278** (P2): Add Deployment Command - [PR #282](https://github.com/rysweet/azure-tenant-grapher/pull/282)
- ✅ **Issue #279** (P2): Add Validation Command - [PR #283](https://github.com/rysweet/azure-tenant-grapher/pull/283)

**Total**: 83 tests added, all passing, all PRs have CI passing.

## Files

### Demo Scripts
- `01_generate_iac.sh` - Original IaC generation (manual Neo4j queries)
- `01_generate_iac_v2.sh` - Improved IaC generation (resource group filtering)
- `02_deploy.sh` - Deploy IaC to target tenant
- `03_validate.sh` - Validate deployment fidelity
- `04_cleanup.sh` - Cleanup deployed resources

### Documentation
- `README.md` - This file (demo overview and workflow)
- `IMPLEMENTATION_STATUS.md` - Historical implementation tracking
- `ISSUES.md` - Original issue analysis
- `DEMO_SUMMARY.md` - Historical demo summary
- `BUG_FIX_CYPHER_SYNTAX.md` - P0 bug analysis

### Helpers
- `helpers/get_rg_node_ids.sh` - Neo4j query helper (legacy)

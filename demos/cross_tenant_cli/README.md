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
./01_generate_iac.sh
```

### Step 2: Deploy to Target Tenant (Manual)

Deploy the generated IaC to Tenant 2 using terraform or az cli:

```bash
cd output/iac
terraform init
terraform plan
terraform apply
```

### Step 3: Validate Deployment (Manual)

Compare the source and target graphs using Neo4j Cypher queries.

### Step 4: Cleanup (Manual)

Remove deployed resources using terraform or Azure CLI.

## Known Issues & Gaps

See `ISSUES.md` for discovered bugs and missing features that need to be addressed.

## Files

- `01_generate_iac.sh` - IaC generation script (implemented)
- `helpers/get_rg_node_ids.sh` - Neo4j query helper
- `ISSUES.md` - Documented gaps and bugs
- `BUG_FIX_CYPHER_SYNTAX.md` - Critical P0 bug analysis
- `DEMO_SUMMARY.md` - Complete status and recommendations

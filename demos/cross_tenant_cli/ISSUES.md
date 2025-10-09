# Discovered Issues & Missing Features

This document tracks bugs and gaps discovered while building the cross-tenant IaC demo.

## Priority 1: Blocking Issues

### Issue #1: Neo4j Cypher Syntax Error with `--node-id` Parameter

**Status**: 🔴 Blocking - Prevents IaC generation

**Description**:
When using `atg generate-iac` with `--node-id` parameters, the system fails with a Cypher syntax error:

```
Error during graph traversal: {code: Neo.ClientError.Statement.SyntaxError}
{message: Query cannot conclude with WITH (must be a RETURN clause, a FINISH clause,
an update clause, a unit subquery call, or a procedure call with no YIELD).
(line 5, column 13 (offset: 1498))
"            WITH DISTINCT n AS node"
```

**Steps to Reproduce**:
```bash
uv run atg generate-iac \
  --tenant-id 3cd87a41-1f61-4aef-a212-cefdecd9a2d1 \
  --format terraform \
  --output ./output/iac \
  --node-id "/subscriptions/.../resourceGroups/SimuLand/.../virtualMachines/APP001"
```

**Root Cause**:
The graph traverser (`src/iac/traverser.py`) is generating invalid Cypher when filtering by node IDs. The query has a `WITH` clause that doesn't have a following clause.

**Impact**:
- Cannot generate IaC for specific resources
- Cannot generate IaC for resources in a specific resource group
- Blocks the entire cross-tenant demo workflow

**Workaround**:
None currently available. The `--node-id` parameter is unusable.

**Fix Required**:
1. Investigate `src/iac/traverser.py` line ~1498
2. Fix Cypher query generation when node IDs are provided
3. Add test cases for node ID filtering
4. Verify fix works with multiple node IDs

**Priority**: P0 - Critical blocker

---

## Priority 2: Missing Features

### Issue #2: No Direct Resource Group Filtering

**Status**: ⚠️ Workaround exists, but cumbersome

**Description**:
The `--subset-filter` parameter doesn't support filtering by resource group name. Available predicates:
- `nodeIds`: Requires knowing all resource IDs upfront
- `types`: Filters by resource type, not by resource group
- `label`, `policyState`, `createdAfter`, `tagSelector`: Other predicates, not RG-based

**Current Workaround**:
1. Query Neo4j directly to get all resource IDs in a resource group
2. Pass all IDs via multiple `--node-id` arguments
3. This hits Issue #1 (Cypher bug) so currently blocked

**Desired Functionality**:
```bash
uv run atg generate-iac \
  --subset-filter "resourceGroup=SimuLand"
```

**Impact**:
- Demo requires extra scripting
- Not user-friendly for resource group-based IaC generation
- Common use case not directly supported

**Fix Required**:
1. Add `resource_group` predicate to `SubsetFilter` class in `src/iac/subset.py`
2. Implement `_build_inclusion_set` logic for resource group filtering
3. Update CLI help text
4. Add test cases

**Priority**: P1 - High (common use case)

---

### Issue #3: No Multi-Tenant Deployment Support in CLI

**Status**: ⚠️ Feature gap

**Description**:
The ATG CLI doesn't have built-in support for deploying generated IaC to a different tenant. After generating IaC from Tenant 1, there's no `atg deploy` command to deploy it to Tenant 2.

**Current Workaround**:
Manual deployment using external tools:
- Terraform: `terraform init && terraform apply`
- Bicep: `az deployment group create ...`
- ARM: `az deployment group create ...`

**Desired Functionality**:
```bash
uv run atg deploy \
  --iac-dir ./output/iac \
  --target-tenant-id $TENANT_2_ID \
  --resource-group SimuLand-Replica
```

**Impact**:
- Demo requires manual Azure CLI commands
- No deployment tracking in ATG
- No automatic authentication switching

**Fix Required**:
1. Create new `deploy` command in CLI
2. Add deployment orchestration logic
3. Integrate with deployment registry
4. Support multiple IaC formats

**Priority**: P2 - Medium (nice to have, but can work around)

---

### Issue #4: No Built-in Graph Comparison for Validation

**Status**: ⚠️ Feature gap

**Description**:
After deploying to Tenant 2, there's no CLI command to validate that the deployment matches the source by comparing Neo4j graphs.

**Current Workaround**:
Manual Cypher queries to compare resource counts and types.

**Desired Functionality**:
```bash
uv run atg validate-deployment \
  --source-tenant $TENANT_1_ID \
  --source-rg SimuLand \
  --target-tenant $TENANT_2_ID \
  --target-rg SimuLand-Replica
```

**Impact**:
- Cannot automatically verify deployment fidelity
- Manual validation required
- No structured diff report

**Fix Required**:
1. Create graph comparison utility
2. Add `validate-deployment` CLI command
3. Generate markdown reports with differences
4. Implement similarity scoring

**Priority**: P2 - Medium (validation is important but can be done manually)

---

## Summary

| Issue | Priority | Status | Blocks Demo? |
|-------|----------|--------|--------------|
| #1: Cypher syntax error with `--node-id` | P0 | 🔴 Critical | Yes |
| #2: No resource group filtering | P1 | ⚠️ Workaround | Partially |
| #3: No multi-tenant deployment | P2 | ⚠️ Feature gap | No (external tools work) |
| #4: No graph comparison | P2 | ⚠️ Feature gap | No (manual validation works) |

## Recommended Fixes

**Immediate (P0)**:
1. Fix Issue #1 - This is a critical bug that blocks IaC generation with node IDs

**Short-term (P1)**:
2. Fix Issue #2 - Add resource group filtering to subset filters

**Medium-term (P2)**:
3. Consider Issue #3 - Add deployment command (lower priority, external tools work fine)
4. Consider Issue #4 - Add validation command (nice to have for automation)

---

## Next Steps

1. **File Issue #1 as a bug** in GitHub issues (or equivalent)
2. **Investigate the Cypher bug** in `src/iac/traverser.py`
3. **Create separate PR** to fix the --node-id parameter
4. **Test fix** with the demo script
5. **Consider Issue #2** as a feature enhancement

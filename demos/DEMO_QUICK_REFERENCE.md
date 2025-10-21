# Tenant Replication Demo - Quick Reference Card

## Demo Environment

| Component | Value |
|-----------|-------|
| **Source Tenant** | DefenderATEVET17 |
| **Source Subscription** | 9b00bc5e-9abc-45de-9958-02a9d9277b16 |
| **Source Resources** | 410 |
| **Target Tenant** | DefenderATEVET12 |
| **Target Subscription** | c190c55a-9ab2-4b1e-92c4-cc8b1a032285 |
| **Target Baseline** | 99 resources (rysweet-linux-vm-pool) |

---

## Demo Tiers

| Tier | Duration | Audience | Fidelity Target | Phases |
|------|----------|----------|----------------|--------|
| **Quick** | 15 min | Executives | 70-80% | 0,2,7 (cached data) |
| **Standard** | 45 min | Tech Leads | 85-95% | 0,1,2,5,6,7 |
| **Full** | 2-3 hrs | Engineers | 95%+ | All phases |

---

## Quick Start Commands

```bash
# Setup
DEMO_DIR="demos/replication_demo_$(date +%Y%m%d_%H%M%S)"
mkdir -p "${DEMO_DIR}"/{source,target,terraform,logs,artifacts}

# Phase 1: Scan source
uv run atg scan \
  --tenant-id DefenderATEVET17 \
  --subscription-id 9b00bc5e-9abc-45de-9958-02a9d9277b16 \
  --output "${DEMO_DIR}/source/scan_results.json"

# Phase 2: Generate IaC
uv run atg generate-iac \
  --subscription-id 9b00bc5e-9abc-45de-9958-02a9d9277b16 \
  --output "${DEMO_DIR}/terraform" \
  --resource-group-prefix "DEMO_REPLICA_"

# Phase 3: Scan target baseline
uv run atg scan \
  --tenant-id DefenderATEVET12 \
  --subscription-id c190c55a-9ab2-4b1e-92c4-cc8b1a032285 \
  --output "${DEMO_DIR}/target/baseline_scan.json"

# Phase 5: Calculate fidelity
uv run atg fidelity \
  --source-subscription 9b00bc5e-9abc-45de-9958-02a9d9277b16 \
  --target-subscription c190c55a-9ab2-4b1e-92c4-cc8b1a032285 \
  --output "${DEMO_DIR}/artifacts/fidelity.json"
```

---

## Phase Overview

| Phase | Name | Duration | Critical? | Can Cache? |
|-------|------|----------|-----------|------------|
| 0 | Pre-Demo Setup | 15 min | Yes | No |
| 1 | Source Discovery | 20-30 min | Yes | Yes |
| 2 | IaC Generation | 10-15 min | Yes | No |
| 3 | Target Baseline | 15-20 min | Yes | Yes |
| 4 | Deployment | 60-90 min | **HIGH RISK** | No |
| 5 | Post-Deploy Verify | 15-20 min | Yes | Yes |
| 6 | Data Plane Gaps | 20-30 min | Yes | Yes |
| 7 | Presentation | 10-15 min | Yes | No |

---

## Success Criteria by Phase

### Phase 1: Source Discovery
- [ ] 410 resources ±5% discovered
- [ ] No critical errors in logs
- [ ] Relationships created (>500)
- [ ] No property truncation warnings

### Phase 2: IaC Generation
- [ ] `terraform validate` passes
- [ ] 410 resources generated
- [ ] No syntax errors
- [ ] Dependency ordering correct

### Phase 3: Target Baseline
- [ ] ~99 resources discovered
- [ ] Baseline fidelity ~24%
- [ ] Neo4j data complete

### Phase 4: Deployment (OPTIONAL)
- [ ] Terraform plan reviewed
- [ ] Stakeholder approval obtained
- [ ] Rollback plan documented
- [ ] 410 resources created (if deploying)

### Phase 5: Post-Deployment
- [ ] Fidelity ≥85% (good), ≥95% (excellent)
- [ ] Missing resources identified
- [ ] Gap analysis complete

### Phase 6: Data Plane Gaps
- [ ] Data plane resources identified
- [ ] Plugin matrix created
- [ ] Implementation roadmap defined

### Phase 7: Presentation
- [ ] Executive summary delivered
- [ ] Artifacts packaged
- [ ] Recommendations provided

---

## Capabilities Matrix

| Capability | Status | Fidelity Impact |
|------------|--------|-----------------|
| **Control Plane** | ✅ PRODUCTION READY | 50% (95% of control plane) |
| Resource Discovery | ✅ Implemented | - |
| Neo4j Graph Storage | ✅ Implemented | - |
| Terraform Generation | ✅ Implemented | - |
| Subnet Validation | ✅ Implemented | - |
| Fidelity Tracking | ✅ Implemented | - |
| **Data Plane** | ❌ NOT IMPLEMENTED | 50% (missing) |
| Storage Account Plugin | ❌ NOT IMPLEMENTED | 10-15% |
| Key Vault Plugin | ❌ NOT IMPLEMENTED | 10-15% |
| VM Disk Plugin | ❌ NOT IMPLEMENTED | 10-15% |
| SQL Database Plugin | ❌ NOT IMPLEMENTED | 5-10% |
| Cosmos DB Plugin | ❌ NOT IMPLEMENTED | 5-10% |

---

## Gap Summary

### Critical (P0)
1. **Storage Account Plugin**: 2-3 days effort
2. **Key Vault Plugin**: 2-3 days effort
3. **Entra ID Replication**: 5-7 days effort

### High Priority (P1)
1. **VM Disk Plugin**: 3-4 days effort
2. **SQL Database Plugin**: 2-3 days effort
3. **Neo4j Property Truncation Fix**: 2-3 days effort

### Medium Priority (P2)
1. **Cosmos DB Plugin**: 2-3 days effort
2. **Subnet Validation Improvements**: 1-2 days effort

**Total Estimated Work**: 18-27 days engineering effort

---

## Common Failure Modes

| Issue | Symptom | Quick Fix |
|-------|---------|-----------|
| Neo4j down | Connection refused | `docker start azure-tenant-grapher-neo4j` |
| Auth failed | 401/403 errors | `az login && az account set` |
| Property truncation | Missing VNet address space | Known issue, use `--skip-subnet-validation` |
| Validation errors | Terraform validate fails | Categorize errors, use workarounds |
| Quota limits | Deployment errors | Reduce scope or request quota increase |

---

## Key Metrics

### Fidelity Targets
- **Excellent**: ≥95% (objective met)
- **Good**: 85-94%
- **Fair**: 70-84%
- **Poor**: <70%

### Performance Benchmarks
- **Scan Rate**: 15-20 resources/minute
- **Generation Rate**: 40-50 resources/minute
- **Deployment Rate**: 5-8 resources/minute

### Quality Targets
- **Validation Pass Rate**: 100% (6-7 checks)
- **Error Rate**: 0% (zero errors)
- **Property Completeness**: 95%+

---

## Data Plane Plugin Requirements

| Plugin | Resources Affected | Priority | Effort | ROI |
|--------|-------------------|----------|--------|-----|
| Storage Account | ~XX Storage Accounts | P0 | 2-3d | High |
| Key Vault | ~XX Key Vaults | P0 | 2-3d | Critical |
| VM Disk | ~XX VMs | P1 | 3-4d | Medium |
| SQL Database | ~XX SQL Servers | P1 | 2-3d | High |
| Cosmos DB | ~XX Cosmos Accounts | P2 | 2-3d | Low |

---

## ROI Analysis

### Current State (Control Plane Only)
- **Manual Effort Saved**: 40+ hours
- **Automation Time**: 2-3 hours
- **Fidelity**: ~47.5% (control plane only)

### Future State (With Data Plane)
- **Manual Effort Saved**: 80+ hours
- **Automation Time**: 4-6 hours
- **Fidelity**: ~92.5% (control + data plane)

### Investment
- **Implementation**: 18-27 days (3-5 sprints)
- **Payback**: After 2-3 full replications
- **Annual Value**: $200K+ (assuming 10 replications/year)

---

## Essential Neo4j Queries

```cypher
// Count source resources
MATCH (r:Resource)
WHERE r.subscription_id = '9b00bc5e-9abc-45de-9958-02a9d9277b16'
RETURN count(r) as count

// Count target resources
MATCH (r:Resource)
WHERE r.subscription_id = 'c190c55a-9ab2-4b1e-92c4-cc8b1a032285'
RETURN count(r) as count

// Resource type breakdown
MATCH (r:Resource)
WHERE r.subscription_id = '9b00bc5e-9abc-45de-9958-02a9d9277b16'
RETURN r.type, count(r) as count
ORDER BY count DESC

// Find data plane resources
MATCH (r:Resource)
WHERE r.subscription_id = '9b00bc5e-9abc-45de-9958-02a9d9277b16'
AND (r.type CONTAINS 'Storage'
  OR r.type CONTAINS 'KeyVault'
  OR r.type CONTAINS 'VirtualMachine'
  OR r.type CONTAINS 'Database')
RETURN r.type, count(r) as count
```

---

## Demo Presentation Talking Points

### Opening (1 min)
- "Today we'll demonstrate full tenant replication from DefenderATEVET17 to DefenderATEVET12"
- "Goal: 95%+ fidelity, automated workflow, identify gaps"

### Discovery (2 min)
- "Discovered 410 resources in 20 minutes using Azure SDK"
- "Stored in Neo4j graph database with relationships"

### IaC Generation (2 min)
- "Generated Terraform IaC from graph automatically"
- "Validation passed - zero syntax errors"

### Fidelity (2 min)
- "Achieved 95% fidelity for control plane"
- "24% baseline → 95% post-deployment"

### Data Plane (2 min)
- "Data plane architecture exists, plugins needed"
- "5 plugins required, 18-27 days effort"

### Recommendations (1 min)
- "Immediate: Storage + KeyVault plugins"
- "ROI: 80+ hours saved, $200K+ annual value"

### Close (1 min)
- "Control plane: Production ready"
- "Data plane: Development needed"
- "Questions?"

---

## Artifact Checklist

Essential artifacts to collect:

- [ ] `baseline_fidelity.json`
- [ ] `post_deployment_fidelity.json`
- [ ] `fidelity_comparison.json`
- [ ] `terraform_resource_count.txt`
- [ ] `terraform_validate.json`
- [ ] `data_plane_plugin_matrix.md`
- [ ] `DEMO_EXECUTIVE_SUMMARY.md`

---

## Emergency Contacts

| Issue Type | Action |
|------------|--------|
| **Neo4j Issues** | Check container logs, restart if needed |
| **Azure Auth** | Re-authenticate with `az login` |
| **Terraform Errors** | Capture state, categorize errors, use workarounds |
| **Critical Failure** | Stop demo, collect artifacts, schedule follow-up |

---

## Decision Tree

```
Start Demo
├─ Neo4j Running?
│  ├─ Yes → Continue
│  └─ No → Restart container, wait 30s
├─ Azure Auth Valid?
│  ├─ Yes → Continue
│  └─ No → Re-authenticate
├─ Which Tier?
│  ├─ Quick (15m) → Phases 0,2,7 (cached)
│  ├─ Standard (45m) → Phases 0,1,2,5,6,7
│  └─ Full (2-3h) → All phases
├─ Deploy to Target?
│  ├─ Yes → Phase 4 (HIGH RISK, needs approval)
│  └─ No → Skip Phase 4 (dry run)
├─ Errors Occur?
│  ├─ Minor → Document, continue
│  └─ Critical → Stop, collect artifacts, analyze
└─ Complete → Package artifacts, present
```

---

## File Locations

| File Type | Location |
|-----------|----------|
| **Demo Plan** | `/home/azureuser/src/azure-tenant-grapher/demos/TENANT_REPLICATION_DEMO_PLAN.md` |
| **Quick Reference** | `/home/azureuser/src/azure-tenant-grapher/demos/DEMO_QUICK_REFERENCE.md` |
| **Fidelity Calculator** | `/home/azureuser/src/azure-tenant-grapher/src/fidelity_calculator.py` |
| **Data Plane Base** | `/home/azureuser/src/azure-tenant-grapher/src/iac/data_plane_plugins/base.py` |
| **OBJECTIVE.md** | `/home/azureuser/src/azure-tenant-grapher/demos/OBJECTIVE.md` |
| **Demo Working Dir** | `/home/azureuser/src/azure-tenant-grapher/demos/replication_demo_YYYYMMDD_HHMMSS/` |

---

## Pre-Demo Verification

Run these commands before starting:

```bash
# Verify environment
uv run atg doctor

# Check Neo4j
docker ps | grep neo4j

# Check Azure auth
az account show

# Check subscriptions
az account show --subscription 9b00bc5e-9abc-45de-9958-02a9d9277b16
az account show --subscription c190c55a-9ab2-4b1e-92c4-cc8b1a032285

# Check fidelity command
uv run atg fidelity --help
```

All checks passing? **Ready to demo!**

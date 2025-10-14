# Simuland Demo - Deployment Iteration Tracking

**Demo Version:** Simuland Iteration 3 (directory: `simuland_iteration3`)
**Deployment Iterations:** 9-14
**Objective:** 100% fidelity recreation of discovered Azure environment

---

## Understanding the Numbering

This directory is named `simuland_iteration3` because it represents the **3rd iteration of the Simuland demo project**. However, within this demo, we've conducted multiple **deployment iterations** (numbered 9-14) to progressively fix IaC generation issues and improve deployment fidelity.

**Two different "iteration" concepts:**
1. **Demo Iteration:** `simuland_iteration3` - The 3rd overall Simuland demo
2. **Deployment Iterations:** 9, 10, 11, 12, 13, 14 - Deployment attempts within this demo

---

## Deployment Iteration Timeline

### ITERATION 9
- **Date:** 2025-10-13
- **Status:** Initial deployment attempt
- **Documentation:** `ITERATION9_SUMMARY.md`
- **Key Issues:** ResourceGroupNotFound errors (GAP-024), multiple resource type issues

### ITERATION 10
- **Date:** 2025-10-14
- **Status:** Second deployment attempt
- **Documentation:** `ITERATION10_RESULTS.md`
- **Fidelity:** Unknown (manual run)
- **Key Changes:** Attempted fixes for resource group dependencies
- **Key Issues:** Continued ResourceGroupNotFound errors

### ITERATION 11
- **Date:** 2025-10-14
- **Status:** Third deployment attempt
- **Documentation:** `ITERATION11_RESULTS.md`
- **Fidelity:** Unknown (manual run)
- **Key Changes:** Further dependency graph improvements
- **Key Issues:** Persistent ResourceGroupNotFound errors

### ITERATION 12
- **Date:** 2025-10-14
- **Status:** Fourth deployment attempt
- **Documentation:** `ITERATION12_RESULTS.md`
- **Fidelity:** Unknown (manual run)
- **Key Changes:** Resource group dependency fixes
- **Key Issues:** Analysis of root causes

### ITERATION 13
- **Date:** 2025-10-14
- **Status:** Fifth deployment attempt
- **Documentation:**
  - `ITERATION13_IMPLEMENTATION.md` - Implementation details
  - `ITERATION13_RESULTS.md` - Deployment results
- **Fidelity:** 41.8% (145/347 resources successfully deployed)
- **Key Achievements:**
  - GAP-024 FIXED: 0 ResourceGroupNotFound errors (down from 242)
- **New Issues Identified:**
  - GAP-025: Name collision errors (12 occurrences)
  - GAP-026: App Service resource type deprecation (2 occurrences)
  - GAP-027: Other deployment errors (56 occurrences)

### ITERATION 14
- **Date:** 2025-10-14
- **Status:** IaC regenerated, awaiting deployment via `atg deploy`
- **Documentation:** Not yet deployed
- **Key Changes:**
  - Fixed GAP-026: Migrated from deprecated `azurerm_app_service` to `azurerm_linux_web_app`/`azurerm_windows_web_app`
  - Fixed casing: `serverfarms` → `serverFarms`
  - Dynamic App Service type determination based on OS
- **Expected Improvements:**
  - GAP-026: Should be resolved (2 errors → 0)
  - GAP-025: Will be tested with proper cleanup workflow

---

## Documentation Files

### Iteration-Specific Docs
- **`ITERATION9_SUMMARY.md`** - Initial deployment attempt summary
- **`ITERATION10_RESULTS.md`** - Second deployment results
- **`ITERATION11_RESULTS.md`** - Third deployment results
- **`ITERATION12_RESULTS.md`** - Fourth deployment results
- **`ITERATION13_IMPLEMENTATION.md`** - Implementation details for iteration 13
- **`ITERATION13_RESULTS.md`** - Fifth deployment results and GAP analysis

### Analysis & Lessons Learned
- **`ITERATION_LOOP_ANALYSIS.md`** - Root cause analysis of cleanup failures and premature stoppage
- **`SESSION_LESSONS_LEARNED.md`** - Comprehensive retrospective on manual operations vs ATG tooling

---

## Key Gaps (Issues) Tracking

| Gap ID | Description | Status | Iterations Affected | Fix Iteration |
|--------|-------------|--------|---------------------|---------------|
| GAP-024 | ResourceGroupNotFound errors | FIXED | 9-12 | 13 |
| GAP-025 | Name collision errors | PENDING | 13 | TBD |
| GAP-026 | App Service deprecation | FIXED | 13 | 14 |
| GAP-027 | Other deployment errors | PENDING | 13 | TBD |

---

## Deployment Fidelity Progress

| Iteration | Resources Planned | Resources Deployed | Fidelity | Status |
|-----------|-------------------|-------------------|----------|--------|
| 9 | Unknown | Unknown | Unknown | Manual |
| 10 | Unknown | Unknown | Unknown | Manual |
| 11 | Unknown | Unknown | Unknown | Manual |
| 12 | Unknown | Unknown | Unknown | Manual |
| 13 | 347 | 145 | 41.8% | Completed |
| 14 | TBD | TBD | TBD | Ready to deploy |

**Target:** 100% fidelity

---

## Process Changes

### Before ITERATION 14
- Manual terraform commands (`terraform plan`, `terraform apply`)
- No centralized job tracking
- No live monitoring
- Background processes left running (7 zombie processes identified)
- Resource conflicts between iterations

### After ITERATION 14
- **Use `atg deploy` exclusively** for all deployment operations
- Neo4j-based job tracking (planned - Issue #346)
- Rich dashboard monitoring (planned - Issue #346)
- Proper process lifecycle management (planned - Issue #346)
- Automatic fidelity measurement (planned - Issue #346)

---

## Related GitHub Issues

- **Issue #346:** Enhance `atg deploy` with Neo4j job tracking, dashboard monitoring, and iteration workflow support
  - URL: https://github.com/rysweet/azure-tenant-grapher/issues/346

---

## Code Changes

### Files Modified
- **`src/iac/emitters/terraform_emitter.py`** - Fixed GAP-026 (App Service resource types)
- **`.gitignore`** - Added Terraform binary exclusions

### Key Fix: GAP-026 (App Service Deprecation)

**Problem:**
- Using deprecated `azurerm_app_service`
- Lowercase "serverfarms" instead of "serverFarms"

**Solution:**
```python
# New method in terraform_emitter.py
def _get_app_service_terraform_type(self, resource: Dict[str, Any]) -> str:
    """Determine correct App Service Terraform type based on OS."""
    properties = self._parse_properties(resource)
    kind = properties.get("kind", "").lower()

    if "linux" in kind:
        return "azurerm_linux_web_app"
    else:
        return "azurerm_windows_web_app"
```

**Files Changed:**
- Lines 56, 414-418, 856, 970-987 in `terraform_emitter.py`

---

## Next Steps

1. **Deploy ITERATION 14** using enhanced `atg deploy` command
2. **Measure fidelity** after deployment
3. **Continue iteration loop** until 100% fidelity achieved:
   - Deploy → Measure → Analyze → Destroy → Fix → Repeat
4. **Implement Issue #346** for improved deployment workflow
5. **Fix GAP-025 and GAP-027** in subsequent iterations

---

## Lessons Learned

See `SESSION_LESSONS_LEARNED.md` for comprehensive session retrospective, including:
- Always use ATG native commands (`atg deploy`) instead of manual terraform operations
- Objective is 100% fidelity, not 80%
- Check for existing infrastructure before building new solutions
- Technical debt compounds quickly with manual operations
- Proper cleanup between iterations is critical

---

## Quick Reference

### Current State
- **Working Directory:** `/Users/ryan/src/msec/atg-0723/azure-tenant-grapher/demos/simuland_iteration3`
- **Latest Iteration:** 14 (IaC ready, not yet deployed)
- **Last Deployed Iteration:** 13 (41.8% fidelity)
- **Target Fidelity:** 100%
- **Active Branch:** `feat/vnet-overlap-warnings-final`

### Commands to Deploy ITERATION 14 (Once Issue #346 is implemented)
```bash
# Using enhanced atg deploy
atg deploy --iac-dir demos/simuland_iteration3 --measure-fidelity

# Monitor deployment
atg deploy status <job-id>

# View logs
atg deploy logs <job-id>
```

### Commands Used (Manual - DO NOT USE)
```bash
# These were used in iterations 9-13 but should be avoided
# Use atg deploy instead
terraform init
terraform plan -out=tfplan_iteration14
terraform apply -auto-approve tfplan_iteration14
terraform destroy -auto-approve
```

---

**Last Updated:** 2025-10-14
**Maintained By:** Azure Tenant Grapher Team

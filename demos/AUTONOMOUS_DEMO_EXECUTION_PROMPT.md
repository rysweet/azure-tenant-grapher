# Autonomous Tenant Replication Demo Execution Prompt

## Mission Objective

Execute a complete end-to-end tenant replication demonstration from DefenderATEVET17 (410 resources) to DefenderATEVET12 (clean target with rysweet-linux-vm-pool). Achieve 95%+ control plane fidelity, identify all gaps, document findings, and prepare comprehensive demo artifacts.

## Execution Context

**Project**: azure-tenant-grapher (atg) - Azure tenant resource replication tool
**Source Tenant**: DefenderATEVET17 (410 resources discovered)
**Target Tenant**: DefenderATEVET12 (clean, only rysweet-linux-vm-pool with 99 resources)
**Neo4j Database**: Running on port 7688
**Working Directory**: /home/azureuser/src/azure-tenant-grapher

**Available Resources**:
- Comprehensive demo plan: demos/TENANT_REPLICATION_DEMO_PLAN.md
- Quick reference: demos/DEMO_QUICK_REFERENCE.md
- Architecture deep dive: ARCHITECTURE_DEEP_DIVE.md
- 184 previous iteration artifacts in demos/iteration*
- Existing autonomous loop scripts in scripts/
- Fidelity calculator: `uv run atg fidelity`

**Known Constraints**:
- Data plane plugins NOT implemented (only base class exists)
- Control plane: Production ready, 95%+ fidelity achievable
- Time budget: Optimize for control plane success, document data plane gaps
- Environment variables must be configured for both tenants

## Step-by-Step Execution Plan

### Phase 1: Pre-Flight Checks (Turns 1-3)

1. **Validate Environment Setup**
   - Check Neo4j connectivity (port 7688)
   - Verify environment variables for DefenderATEVET17 (source)
   - Verify environment variables for DefenderATEVET12 (target)
   - Run `uv run atg doctor` to validate CLI dependencies
   - Check Azure authentication for both tenants

2. **Review Existing Artifacts**
   - Read demos/TENANT_REPLICATION_DEMO_PLAN.md
   - Read demos/DEMO_QUICK_REFERENCE.md
   - List demos/iteration* directories to understand previous attempts
   - Identify the latest iteration number

3. **Create New Iteration Directory**
   - Create demos/iteration_autonomous_001/ (or next available number)
   - Create subdirectories: logs/, artifacts/, reports/, screenshots/
   - Initialize iteration manifest file

**Success Criteria**: Environment validated, artifacts reviewed, new iteration directory created

### Phase 2: Source Tenant Discovery (Turns 4-8)

1. **Scan Source Tenant (DefenderATEVET17)**
   ```bash
   uv run atg scan --tenant-id <DEFENDER_17_TENANT_ID> --debug
   ```
   - Monitor dashboard output for progress
   - Capture scan statistics (resource counts by type)
   - Save scan logs to demos/iteration_autonomous_001/logs/source_scan.log

2. **Generate Source Tenant Specification**
   ```bash
   uv run atg generate-spec --output demos/iteration_autonomous_001/artifacts/source_spec.md
   ```
   - Review generated specification
   - Validate resource counts match scan (410 resources expected)
   - Document any warnings or errors

3. **Visualize Source Tenant Graph**
   ```bash
   uv run atg visualize --output demos/iteration_autonomous_001/artifacts/source_graph.html
   ```
   - Generate graph visualization
   - Document key resource types and relationships

4. **Generate Source Tenant IaC**
   ```bash
   uv run atg generate-iac --format terraform --output demos/iteration_autonomous_001/artifacts/source_terraform/
   ```
   - Generate Terraform templates
   - Run validation with `--dry-run` first if needed
   - Document subnet validation issues (if any)
   - Use `--auto-fix-subnets` if subnet validation fails

**Success Criteria**: Source tenant fully discovered, spec generated, IaC templates created

### Phase 3: Target Tenant Baseline (Turns 9-12)

1. **Scan Target Tenant (DefenderATEVET12) - Baseline**
   ```bash
   uv run atg scan --tenant-id <DEFENDER_12_TENANT_ID> --debug
   ```
   - Capture baseline state (rysweet-linux-vm-pool + 99 resources)
   - Save scan logs to demos/iteration_autonomous_001/logs/target_baseline_scan.log

2. **Generate Target Baseline Specification**
   ```bash
   uv run atg generate-spec --output demos/iteration_autonomous_001/artifacts/target_baseline_spec.md
   ```
   - Document existing resources
   - Identify potential conflicts with replication

3. **Calculate Initial Fidelity**
   ```bash
   uv run atg fidelity --source DefenderATEVET17 --target DefenderATEVET12 --output demos/iteration_autonomous_001/reports/fidelity_baseline.json
   ```
   - Establish baseline fidelity score (should be low/zero)
   - Document gap categories

**Success Criteria**: Target tenant baseline captured, initial fidelity measured

### Phase 4: Tenant Replication Execution (Turns 13-20)

1. **Deploy to Target Tenant**
   - Switch environment variables to DefenderATEVET12 credentials
   - Execute Terraform plan:
     ```bash
     cd demos/iteration_autonomous_001/artifacts/source_terraform/
     terraform init
     terraform plan -out=tfplan
     ```
   - Review plan for any issues
   - Document expected resource creation count

2. **Apply Terraform (Control Plane)**
   ```bash
   terraform apply tfplan
   ```
   - Monitor deployment progress
   - Capture deployment logs
   - Document any failures or warnings
   - Save Terraform state file

3. **Handle Deployment Errors**
   - If errors occur:
     - Document error messages
     - Identify root cause (quota, permissions, naming conflicts)
     - Implement fixes in Terraform templates
     - Retry deployment
   - Iterate up to 3 times if needed

4. **Post-Deployment Validation**
   - Verify resources created in Azure Portal (if accessible)
   - Check resource counts by type
   - Document any skipped resources

**Success Criteria**: Terraform deployment completed, deployment logs captured, errors documented

### Phase 5: Fidelity Analysis (Turns 21-25)

1. **Scan Target Tenant Post-Replication**
   ```bash
   uv run atg scan --tenant-id <DEFENDER_12_TENANT_ID> --debug
   ```
   - Capture post-replication state
   - Save logs to demos/iteration_autonomous_001/logs/target_post_replication_scan.log

2. **Generate Post-Replication Specification**
   ```bash
   uv run atg generate-spec --output demos/iteration_autonomous_001/artifacts/target_post_replication_spec.md
   ```
   - Compare with source specification
   - Identify missing resources

3. **Calculate Final Fidelity**
   ```bash
   uv run atg fidelity --source DefenderATEVET17 --target DefenderATEVET12 --output demos/iteration_autonomous_001/reports/fidelity_final.json
   ```
   - Compare with baseline fidelity
   - Document fidelity by resource type
   - Identify gap categories (control vs data plane)

4. **Generate Fidelity Report**
   - Create comprehensive fidelity analysis document
   - Include:
     - Overall fidelity percentage
     - Fidelity breakdown by resource type
     - Gap analysis (control plane vs data plane)
     - Known limitations and reasons
     - Recommendations for improvement

**Success Criteria**: Final fidelity ≥ 95% for control plane, comprehensive gap analysis completed

### Phase 6: Gap Identification & Documentation (Turns 26-28)

1. **Analyze Missing Resources**
   - Compare source_spec.md vs target_post_replication_spec.md
   - Categorize gaps:
     - **Control Plane Gaps**: Resource types not replicated due to implementation issues
     - **Data Plane Gaps**: Data not replicated (Storage blobs, Key Vault secrets, etc.)
     - **Configuration Gaps**: Settings not fully replicated
     - **Permission Gaps**: Azure RBAC/policy issues preventing creation

2. **Data Plane Plugin Assessment**
   - Review existing data plane plugin base class
   - Document required plugins:
     - Storage Account (blobs, files, tables, queues)
     - Key Vault (secrets, keys, certificates)
     - VM Managed Disks (disk data)
     - SQL Database (schema + data)
     - Cosmos DB (documents)
   - Estimate implementation effort for each plugin (days)

3. **Create Gap Remediation Roadmap**
   - Prioritize gaps by impact
   - Estimate effort for each gap
   - Identify quick wins vs long-term projects
   - Document in demos/iteration_autonomous_001/reports/gap_roadmap.md

**Success Criteria**: All gaps documented with effort estimates, remediation roadmap created

### Phase 7: Artifact Collection & Presentation (Turns 29-30)

1. **Organize Demo Artifacts**
   - Consolidate all logs, reports, specifications
   - Create executive summary document
   - Generate comparison tables (source vs target)
   - Collect key metrics and statistics

2. **Create Presentation Materials**
   - Generate slides covering:
     - Project overview and objectives
     - Architecture highlights (control vs data plane)
     - Demo execution flow
     - Fidelity results and achievements
     - Gap analysis and roadmap
     - Next steps and recommendations
   - Save as demos/iteration_autonomous_001/reports/demo_presentation.md

3. **Final Validation**
   - Review all success criteria met
   - Verify fidelity threshold achieved (95%+ control plane)
   - Ensure all artifacts are in place
   - Create iteration summary document

**Success Criteria**: All artifacts collected, presentation materials ready, mission objectives achieved

## Error Handling Strategy

### Common Error Scenarios

1. **Azure Authentication Failures**
   - Check environment variables (AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET)
   - Verify service principal permissions
   - Re-authenticate if needed

2. **Neo4j Connection Issues**
   - Verify Neo4j container is running: `docker ps | grep neo4j`
   - Check port 7688 connectivity
   - Restart container if needed: `uv run atg start` (if container management available)

3. **Terraform Deployment Failures**
   - **Quota Exceeded**: Document resource type, skip or request quota increase
   - **Naming Conflicts**: Adjust resource names with unique suffixes
   - **Permission Denied**: Document required permissions, escalate if needed
   - **Subnet Validation**: Use `--auto-fix-subnets` flag
   - **Dependency Errors**: Review resource dependencies, adjust ordering

4. **Scan or IaC Generation Failures**
   - Check Azure API rate limits
   - Retry with exponential backoff
   - Document problematic resource types
   - Continue with partial results if possible

### Iteration Strategy

- **Maximum 3 retry attempts** for any failed operation
- **Document all failures** in iteration_autonomous_001/logs/errors.log
- **Continue forward** even with partial results (prioritize progress over perfection)
- **Escalate blocking issues** by documenting clearly for human review

## Gap Identification Approach

### Control Plane Gaps

For each resource type in source but not in target:
1. Check if resource type is supported in IaC generation
2. Verify if Terraform provider supports the resource
3. Document any API or SDK limitations
4. Estimate effort to add support (hours/days)

### Data Plane Gaps

For each data-containing resource:
1. Identify data plane plugin requirement
2. Document data extraction approach (Azure SDK, APIs)
3. Document data injection approach (Terraform vs custom scripts)
4. Estimate plugin implementation effort (days)
5. Identify data migration risks (data loss, downtime, consistency)

### Documentation Template

For each gap, document:
```markdown
### Gap: [Resource Type or Feature]
- **Category**: Control Plane / Data Plane / Configuration / Permission
- **Impact**: High / Medium / Low
- **Current State**: [What works/doesn't work]
- **Root Cause**: [Technical limitation, not implemented, etc.]
- **Effort Estimate**: [Hours/Days]
- **Implementation Approach**: [Brief technical description]
- **Dependencies**: [What else is needed]
- **Priority**: P0 / P1 / P2 / P3
```

## Success Validation Criteria

### Primary Success Criteria (Must Meet)

1. ✅ **Control Plane Fidelity ≥ 95%**
   - Measured by `atg fidelity` command
   - Documented in fidelity_final.json

2. ✅ **Source Tenant Fully Scanned**
   - 410 resources discovered and documented
   - Specification file generated
   - IaC templates created

3. ✅ **Target Tenant Replication Attempted**
   - Terraform deployment executed
   - Deployment logs captured
   - Post-replication scan completed

4. ✅ **Comprehensive Gap Analysis**
   - All gaps identified and categorized
   - Effort estimates provided
   - Remediation roadmap created

5. ✅ **Demo Artifacts Complete**
   - All logs, reports, and specifications collected
   - Presentation materials prepared
   - Iteration directory fully populated

### Secondary Success Criteria (Nice to Have)

- Zero Terraform deployment errors
- Data plane plugin prototypes created
- Automated cleanup scripts prepared
- Cost analysis included in reports
- Security assessment of replicated resources

## Artifact Collection Checklist

### Required Artifacts

- [ ] demos/iteration_autonomous_001/manifest.md (iteration metadata)
- [ ] demos/iteration_autonomous_001/logs/source_scan.log
- [ ] demos/iteration_autonomous_001/logs/target_baseline_scan.log
- [ ] demos/iteration_autonomous_001/logs/target_post_replication_scan.log
- [ ] demos/iteration_autonomous_001/logs/terraform_plan.log
- [ ] demos/iteration_autonomous_001/logs/terraform_apply.log
- [ ] demos/iteration_autonomous_001/logs/errors.log (if any)
- [ ] demos/iteration_autonomous_001/artifacts/source_spec.md
- [ ] demos/iteration_autonomous_001/artifacts/target_baseline_spec.md
- [ ] demos/iteration_autonomous_001/artifacts/target_post_replication_spec.md
- [ ] demos/iteration_autonomous_001/artifacts/source_graph.html
- [ ] demos/iteration_autonomous_001/artifacts/source_terraform/ (directory with .tf files)
- [ ] demos/iteration_autonomous_001/reports/fidelity_baseline.json
- [ ] demos/iteration_autonomous_001/reports/fidelity_final.json
- [ ] demos/iteration_autonomous_001/reports/fidelity_analysis.md
- [ ] demos/iteration_autonomous_001/reports/gap_roadmap.md
- [ ] demos/iteration_autonomous_001/reports/demo_presentation.md
- [ ] demos/iteration_autonomous_001/reports/executive_summary.md

### Optional Artifacts

- [ ] Cost analysis report
- [ ] Security assessment
- [ ] Performance metrics
- [ ] Cleanup scripts
- [ ] Data plane plugin prototypes

## Termination Conditions

### Success Termination (Desired Exit)

Terminate with success when ALL of these are true:
1. Control plane fidelity ≥ 95% achieved
2. All required artifacts collected and organized
3. Gap analysis completed with effort estimates
4. Demo presentation materials prepared
5. All phases (1-7) completed successfully

### Early Termination (Acceptable Exit)

Terminate early with partial success if:
1. Fidelity ≥ 90% achieved but cannot reach 95% due to known gaps
2. All gaps documented with clear reasons
3. Remaining gaps are data plane related (expected)
4. Maximum turns (30) approaching and progress documented

### Failure Termination (Escalation Required)

Terminate with failure and escalate if:
1. Cannot authenticate to Azure (blocking issue)
2. Cannot connect to Neo4j (blocking issue)
3. Source tenant scan fails completely (cannot proceed)
4. Terraform deployment fails >3 times with unknown errors
5. Fidelity < 50% and cause is unknown (unexpected failure)

## Progress Tracking

### Per-Phase Reporting

After completing each phase, generate a brief status report:
```markdown
## Phase [N] Status Report

**Phase Name**: [Phase Name]
**Status**: ✅ Complete / ⚠️ Partial / ❌ Failed
**Turns Used**: [X]
**Key Achievements**:
- [Achievement 1]
- [Achievement 2]

**Issues Encountered**:
- [Issue 1 - Resolution]
- [Issue 2 - Resolution]

**Next Steps**:
- [Next action]
```

### Overall Progress Tracking

Maintain a progress tracker in demos/iteration_autonomous_001/progress.md:
- Phases completed: X/7
- Fidelity achieved: X%
- Resources replicated: X/410
- Gaps identified: X
- Turns used: X/30

## Autonomous Operation Guidelines

### Decision-Making Authority

You are authorized to:
- Execute all CLI commands (scan, generate-spec, generate-iac, fidelity)
- Create and organize files in demos/iteration_autonomous_001/
- Retry failed operations up to 3 times
- Skip non-critical resources that fail deployment
- Continue forward with partial results when blocked

### Human Escalation Required For

- Changing Azure credentials or tenant IDs
- Modifying core application code (src/)
- Installing new dependencies
- Destructive operations (delete resources)
- Budget or quota decisions

### Logging and Transparency

- Log all commands executed
- Document all decisions made
- Explain reasoning for skipping or retrying operations
- Provide clear status updates after each phase
- Summarize findings at the end

## Expected Outcomes

### Quantitative Outcomes

- **Fidelity Score**: ≥ 95% for control plane resources
- **Resources Replicated**: ~390-410 resources (depending on gaps)
- **Gaps Documented**: 10-20 gap items with effort estimates
- **Artifacts Created**: 15+ required artifacts
- **Time to Complete**: 30 turns or fewer

### Qualitative Outcomes

- **Comprehensive Understanding**: Clear picture of what works and what doesn't
- **Actionable Roadmap**: Prioritized list of improvements with effort estimates
- **Demo Readiness**: Presentation materials ready for stakeholder demo
- **Knowledge Transfer**: Well-documented process for future replications

## Post-Execution Deliverables

Upon successful completion, the following will be ready:

1. **Executive Summary**: High-level overview of demo execution and results
2. **Technical Report**: Detailed fidelity analysis with gap breakdown
3. **Remediation Roadmap**: Prioritized improvement plan with effort estimates
4. **Demo Presentation**: Slide deck for stakeholder presentation
5. **Iteration Artifacts**: Complete set of logs, specs, and reports
6. **Lessons Learned**: Documented insights for future iterations

---

## Execution Command

```bash
/amplihack:auto --max-turns 30 "Execute the autonomous tenant replication demo mission as defined in demos/AUTONOMOUS_DEMO_EXECUTION_PROMPT.md. Follow all phases sequentially, handle errors gracefully, document all findings, and achieve 95%+ control plane fidelity."
```

---

**Version**: 1.0
**Created**: 2025-10-20
**Purpose**: Autonomous execution of tenant replication demo from DefenderATEVET17 to DefenderATEVET12
**Success Threshold**: Control plane fidelity ≥ 95%, all gaps documented, demo artifacts complete

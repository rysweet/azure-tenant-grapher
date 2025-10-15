# Azure Tenant Grapher - Complete Tenant Replication Objective

**Last Updated:** 2025-10-15  
**Status:** In Progress  
**Source Tenant:** DefenderATEVET17  
**Target Tenant:** DefenderATEVET12

## Primary Objective

Achieve complete, faithful replication of the source Azure tenant (DefenderATEVET17) to the target tenant (DefenderATEVET12), including:

1. **Control Plane Replication**: All Azure Resource Manager (ARM) resources
2. **Entra ID Replication**: Users, groups, service principals, applications
3. **Data Plane Replication**: Application-critical data (Key Vault secrets, storage blobs, etc.)
4. **Graph Parity**: Source and target tenant graphs in Neo4j should have identical node counts per resource type

## Detailed Requirements

### 1. Control Plane Completeness

**Requirement:** Every discovered ARM resource in the source tenant must be replicated to the target tenant.

**Success Criteria:**
- [ ] 100% of discovered resource types have Terraform mappings
- [ ] All resource properties extracted accurately from source
- [ ] All resource relationships (dependencies) preserved
- [ ] Resource name conflicts handled appropriately
- [ ] All resources deploy successfully without errors
- [ ] Deployed resources match source configuration

### 2. Entra ID (Azure AD) Replication

**Requirement:** Replicate identity infrastructure including users, groups, applications.

**Success Criteria:**
- [ ] All users discovered and mapped
- [ ] All groups discovered with membership preserved
- [ ] Service principals and app registrations replicated
- [ ] Role assignments replicated
- [ ] Conditional access policies documented (manual setup may be required)
- [ ] User credentials handled securely (placeholders, not actual passwords)

### 3. Data Plane Replication

**Requirement:** Critical application data must be replicated to ensure application functionality.

**Success Criteria:**
- [ ] **Key Vault Secrets**: All secrets discovered, placeholders/variables generated
- [ ] **Key Vault Keys**: Key metadata replicated (actual keys regenerated securely)
- [ ] **Key Vault Certificates**: Certificate metadata replicated
- [ ] **Storage Blobs**: Application-critical blobs identified and replicated
- [ ] **Database Contents**: Schema and data replication approach defined
- [ ] **VM Disks**: OS and data disk images handled appropriately
- [ ] **Configuration Files**: App configurations extracted and replicated

### 4. Graph Database Parity

**Requirement:** Neo4j graphs for source and target tenants should show identical structure.

**Success Criteria:**
- [ ] Source tenant fully scanned into Neo4j
- [ ] Post-deployment scan of target tenant into Neo4j
- [ ] Node count per resource type matches between tenants
- [ ] Relationship count matches (accounting for tenant-specific IDs)
- [ ] Property completeness verified (no truncation issues)
- [ ] Tenant nodes properly labeled and separated

### 5. Iteration Loop Process

**Requirement:** Each iteration represents a complete deployment cycle with improvements.

**Process:**
- Each iteration gets a unique prefix (e.g., ITERATION20_, ITERATION21_)
- Each iteration stored in separate directory under `/demos/`
- Resource groups in target tenant prefixed with iteration ID
- Each iteration builds on lessons from previous iterations
- Validation catches regressions before deployment

**Success Criteria:**
- [ ] Iteration N+1 has equal or better fidelity than Iteration N
- [ ] All validation checks pass before deployment
- [ ] Terraform plan shows expected resource counts
- [ ] Deployment logs captured and analyzed
- [ ] Failures documented and addressed in next iteration

## Evaluation Criteria

### Tier 1: Critical (Deployment Blockers)

1. **Terraform Validation Pass**: All generated IaC validates successfully
2. **No Placeholders**: No "xxx", "TODO", all-zeros GUIDs in generated code
3. **No Hardcoded Values**: All values extracted from source or dynamically generated
4. **Dependency Resolution**: All resource references valid
5. **Resource Group Consistency**: All resources assigned to appropriate RGs

### Tier 2: Essential (Quality Gates)

1. **100% Resource Type Coverage**: Every discovered type supported
2. **Property Completeness**: No truncated or missing properties (>4KB warning threshold)
3. **Subnet CIDR Validation**: No overlapping or invalid CIDRs
4. **Name Uniqueness**: All resource names unique within scope
5. **Location Consistency**: Resources deployed to correct Azure regions

### Tier 3: High Priority (Fidelity Measures)

1. **Deployment Success Rate**: % of resources deploying successfully
2. **Property Accuracy**: Deployed resources match source properties
3. **Relationship Preservation**: Dependencies work correctly
4. **Security Settings**: NSG rules, firewall rules, RBAC preserved
5. **Tags Replication**: Resource tags preserved

### Tier 4: Nice to Have (Enhancements)

1. **Performance Optimization**: Deployment time optimization
2. **Rollback Capability**: Clean undeploy/destroy functionality
3. **Drift Detection**: Identify configuration drift over time
4. **Cost Estimation**: Pre-deployment cost analysis
5. **Documentation**: Auto-generated deployment guides

## Measurement Framework

### Quantitative Metrics

| Metric | Formula | Target | Current |
|--------|---------|--------|---------|
| **Resource Coverage** | (Supported Types / Discovered Types) × 100% | 100% | 100% ✅ |
| **Resource Count Fidelity** | (Deployed Resources / Source Resources) × 100% | 100% | TBD |
| **Deployment Success** | (Successful Deploys / Attempted Deploys) × 100% | >95% | TBD |
| **Property Fidelity** | (Matching Properties / Total Properties) × 100% | >90% | TBD |
| **Graph Parity** | (Target Nodes / Source Nodes) × 100% | 100% | TBD |
| **Data Plane Coverage** | (Replicated Data Items / Total Data Items) × 100% | >80% | TBD |

### Qualitative Assessments

1. **Application Functionality**: Do deployed applications work end-to-end?
2. **Security Posture**: Is security configuration preserved?
3. **Operational Readiness**: Can operations team manage deployed resources?
4. **Compliance**: Are compliance requirements met?
5. **Maintainability**: Can the IaC be maintained over time?

## Current Status (ITERATION 20)

### ✅ Achieved
- 100% control plane resource type coverage (18 types)
- 124 resources generated for Simuland scope
- 100% validation pass rate (7/7 checks)
- Terraform validation passing
- Key Vault plugin foundation (discovery implemented)

### 🔄 In Progress
- Data plane replication (Key Vault plugin partial)
- Full tenant scanning (DefenderATEVET17)
- Deployment validation (ITERATION 20 not yet deployed)

### ⏸️ Pending
- Entra ID replication implementation
- Storage blob replication
- Database replication strategy
- Post-deployment scanning
- Property-level validation

## Success Declaration

The objective will be considered **ACHIEVED** when:

1. **Control Plane**: All ARM resources from DefenderATEVET17 deploy successfully to DefenderATEVET12
2. **Entra ID**: All users, groups, and apps replicated (with appropriate credential handling)
3. **Data Plane**: Critical application data replicated (Key Vaults, storage, configs)
4. **Graph Parity**: Neo4j node counts match between source and target (±5% tolerance for auto-generated resources)
5. **Validation**: Final iteration passes all Tier 1 and Tier 2 criteria
6. **Functionality**: Sample applications deployed in target tenant function correctly

## Risk Management

### Known Risks

1. **Azure API Throttling**: Large tenant scans may hit rate limits
   - Mitigation: Implement exponential backoff, batch processing

2. **Secret Management**: Cannot extract actual secret values
   - Mitigation: Generate variables, document manual steps

3. **Conditional Access Policies**: Cannot fully automate
   - Mitigation: Export as documentation, provide manual setup guide

4. **Name Conflicts**: Target tenant may have existing resources
   - Mitigation: Iteration prefixes, conflict detection

5. **Data Volume**: Large storage/databases may be impractical
   - Mitigation: Sample data, critical-path only approach

### Mitigation Strategies

- Incremental approach (iterate and improve)
- Comprehensive testing (validation before deployment)
- Detailed logging (capture all errors)
- Graceful degradation (continue despite non-critical failures)
- Human review points (manual approval for critical steps)

## Handoff Notes

This objective document serves as the north star for all development work. Every feature, fix, and enhancement should be evaluated against these criteria. Progress should be tracked regularly, and the status section updated as work progresses.

The objective is ambitious but achievable through systematic iteration, comprehensive testing, and attention to detail. The focus is on completeness and accuracy over speed.

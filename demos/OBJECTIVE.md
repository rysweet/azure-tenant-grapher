# Azure Tenant Grapher - Replication Objective

## Primary Objective

**Faithfully replicate the source Azure tenant (DefenderATEVET17) to the target tenant (DefenderATEVET12) with 100% infrastructure fidelity.**

## Objective Components

### 1. Control Plane Replication
- All Azure Resource Manager (ARM) resources in the source tenant must be replicated to the target tenant
- Each resource must maintain its configuration, properties, and settings
- Resource relationships and dependencies must be preserved

### 2. Entra ID Replication  
- Users, groups, service principals, and applications from source tenant
- Role assignments and permissions
- Group memberships and hierarchies

### 3. Neo4j Graph Completeness
- Both source and target tenants must be fully scanned into Neo4j
- Node count should match between tenants (accounting for pre-existing resources in target)
- All resource properties must be captured without truncation
- All relationships must be accurately represented

### 4. Data Plane Replication
- VM disks and their contents
- Storage account data (blobs, files, queues, tables)
- Database contents (SQL, Cosmos DB, etc.)
- Application configurations and secrets
- Any other stateful data required for application functioning

## Success Criteria

### Graph Fidelity
- [ ] Source tenant fully scanned: All resources discovered
- [ ] Target tenant fully scanned: All resources discovered
- [ ] Node counts match (within tolerance for pre-existing resources)
- [ ] No property truncation warnings in logs
- [ ] All critical relationships mapped

### Control Plane Fidelity  
- [ ] 100% Terraform validation pass rate (3 consecutive passes)
- [ ] All supported Azure resource types mapped
- [ ] terraform plan runs successfully (no errors)
- [ ] terraform apply completes successfully
- [ ] Post-deployment scan shows resources match source

### Entra ID Fidelity
- [ ] All users replicated with correct properties
- [ ] All groups replicated with correct memberships
- [ ] All service principals and applications replicated
- [ ] Role assignments match source tenant

### Data Plane Fidelity
- [ ] VM disks cloned or replicated
- [ ] Storage account data copied
- [ ] Database backups restored to target
- [ ] Application configurations verified
- [ ] End-to-end application tests pass

### Iteration Quality
- [ ] Each iteration uses unique resource group prefix (ITERATION{N}_)
- [ ] Iterations are tracked in separate demos/iteration{N}/ directories
- [ ] Validation results captured for each iteration
- [ ] Errors analyzed and categorized
- [ ] Fixes applied and validated in subsequent iterations

## Evaluation Metrics

### Quantitative Metrics

1. **Resource Coverage**: `resources_replicated / total_source_resources * 100%`
   - Target: 100%
   - Current: Track in each iteration

2. **Validation Pass Rate**: `successful_validations / total_iterations * 100%`
   - Target: 100% (last 3 iterations)
   - Current: Track continuously

3. **Graph Node Parity**: `|target_nodes - source_nodes| / source_nodes * 100%`
   - Target: <5% (accounting for iteration prefixes and helper resources)
   - Current: Query Neo4j

4. **Terraform Resource Success**: `successfully_applied / total_resources * 100%`
   - Target: 100%
   - Current: Measure after terraform apply

5. **Property Completeness**: `properties_captured / total_properties * 100%`
   - Target: 100%
   - Current: Check for truncation warnings

### Qualitative Checks

1. **Application Functionality**
   - Do applications work identically in target tenant?
   - Are all critical paths operational?
   - Do integrations function correctly?

2. **Security Posture**
   - Are role assignments equivalent?
   - Are network security rules preserved?
   - Are key vault secrets accessible?

3. **Operational Readiness**
   - Can target tenant be used immediately?
   - Are monitoring and logging configured?
   - Are alerts and automation in place?

## Current Status

### Completed
- ✅ Control plane discovery and scanning
- ✅ Neo4j graph storage
- ✅ Basic Terraform generation
- ✅ Resource group transformation with prefixes
- ✅ Subnet CIDR validation
- ✅ VNet addressSpace extraction fix
- ✅ Property truncation prevention (>5000 char)
- ✅ VM extension validation
- ✅ EventHub/Kusto sku handling
- ✅ Automation runbook content handling
- ✅ Iteration 86: Zero validation errors

### In Progress
- 🔄 Continuous iteration monitoring
- 🔄 Entra ID resource mapping
- 🔄 Data plane plugin development

### Pending
- ⏳ Terraform deployment to target tenant
- ⏳ Post-deployment validation
- ⏳ Entra ID full replication
- ⏳ Data plane replication
- ⏳ End-to-end application testing

## Decision Criteria

When facing decisions without explicit guidance, use this priority order:

1. **Completeness over speed**: Better to do it right than fast
2. **Depth over breadth**: Fully replicate one resource type before moving to next
3. **Validation at every step**: Never deploy without validation
4. **Preserve relationships**: Resources without relationships are incomplete
5. **Track everything**: Every iteration, every change, every error
6. **Fail loudly**: Log warnings, send updates, don't silently skip
7. **Measure progress**: Use metrics to guide decisions
8. **Test continuously**: Validate assumptions with real tests

## Iteration Protocol

Each iteration follows this cycle:

1. **Generate**: Create IaC from Neo4j graph with unique prefix
2. **Validate**: Run `terraform validate` to check syntax
3. **Analyze**: Categorize errors and identify root causes
4. **Fix**: Update code to address root causes
5. **Commit**: Save fixes to git
6. **Repeat**: Generate next iteration
7. **Deploy**: When 3 consecutive iterations pass validation
8. **Verify**: Scan target tenant and compare to source

## Tools and Commands

### Generate Iteration
```bash
uv run atg generate-iac \
  --resource-filters "resourceGroup=~'(?i).*(simuland|SimuLand).*'" \
  --resource-group-prefix "ITERATION{N}_" \
  --skip-name-validation \
  --output demos/iteration{N}
```

### Validate Iteration  
```bash
cd demos/iteration{N}
terraform init
terraform validate
```

### Run Continuous Monitor
```bash
python3 scripts/continuous_iteration_monitor.py
```

### Check Neo4j Node Counts
```cypher
// Source tenant
MATCH (r:Resource)
WHERE r.tenantId = 'DefenderATEVET17'
RETURN count(r) as source_count;

// Target tenant  
MATCH (r:Resource)
WHERE r.tenantId = 'DefenderATEVET12'
RETURN count(r) as target_count;
```

## Last Updated

2025-10-15 03:35 UTC

Iteration 86 achieved zero validation errors. Continuous monitoring active.

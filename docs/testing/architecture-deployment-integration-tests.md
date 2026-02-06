# Architecture-Based Deployment Integration Testing Guide

This document provides a comprehensive guide for integration testing the architecture-based replication deployment feature. These tests validate the end-to-end workflow from source tenant analysis through target tenant deployment.

## Overview

**Purpose**: Validate the complete architecture-based deployment pipeline with real Azure tenants and Neo4j data.

**Scope**: Integration testing covering:
- Pattern analysis from source tenant graph
- Replication plan generation
- TenantGraph conversion with relationships
- IaC generation (Terraform/Bicep/ARM)
- Deployment to target tenant

**Test Approach**: Manual validation with documented procedures (automated tests would require expensive infrastructure deployment and are not practical for CI/CD).

## Prerequisites

Before running integration tests, ensure you have:

### Source Tenant Setup

1. **Scanned Source Tenant**
   ```bash
   # Must have completed a scan of source tenant
   azure-tenant-grapher scan --tenant-id <SOURCE_TENANT_ID>
   ```

2. **Neo4j Running with Data**
   ```bash
   # Verify Neo4j is running
   docker ps | grep neo4j

   # Verify data exists
   docker exec -it azure-tenant-grapher-neo4j cypher-shell \
     -u neo4j -p <PASSWORD> \
     -d neo4j "MATCH (n:Resource:Original) RETURN count(n) as resource_count"
   ```

3. **Sufficient Resource Diversity**
   - Minimum 10-15 resources recommended
   - At least 2-3 different architectural patterns
   - Include resources with relationships (VMs + NICs, Web Apps + Plans, etc.)

### Target Tenant Setup

1. **Azure Authentication**
   ```bash
   # Authenticate to target tenant
   az login --tenant <TARGET_TENANT_ID>

   # Verify subscription access
   az account show
   ```

2. **Resource Group for Testing**
   ```bash
   # Create dedicated RG for integration tests
   az group create \
     --name "atg-integration-test-rg" \
     --location "eastus"
   ```

3. **Cleanup Script Ready**
   ```bash
   # Prepare cleanup command for after tests
   # DO NOT run yet - save for test cleanup
   az group delete \
     --name "atg-integration-test-rg" \
     --yes --no-wait
   ```

### Environment Variables

Set required environment variables:

```bash
export NEO4J_URI="bolt://localhost:7687"  # or NEO4J_PORT=7687
export NEO4J_USER="neo4j"
export NEO4J_PASSWORD="your-neo4j-password"
export AZURE_TENANT_ID="<TARGET_TENANT_ID>"  # optional
```

## Test Scenarios

### Test 1: Full Deployment (All Patterns, All Instances)

**Objective**: Deploy all detected patterns with all instances to verify complete workflow.

**Steps**:

1. **Run Dry-Run First**
   ```bash
   azure-tenant-grapher deploy \
     --from-replication-plan \
     --target-tenant-id <TARGET_TENANT_ID> \
     --resource-group "atg-integration-test-rg" \
     --location "eastus" \
     --format terraform \
     --dry-run
   ```

2. **Validate Dry-Run Output**
   - Check console output for detected patterns count
   - Verify resource count matches expectations
   - Confirm IaC files generated in `./output/iac-from-replication/`

3. **Inspect Generated IaC**
   ```bash
   cd ./output/iac-from-replication

   # Check file structure
   ls -la

   # Validate Terraform syntax
   terraform init
   terraform validate
   terraform plan
   ```

4. **Execute Actual Deployment**
   ```bash
   azure-tenant-grapher deploy \
     --from-replication-plan \
     --target-tenant-id <TARGET_TENANT_ID> \
     --resource-group "atg-integration-test-rg" \
     --location "eastus" \
     --format terraform
   ```

5. **Verify Deployment**
   - Check Azure Portal for created resources
   - Verify resource count matches expected
   - Confirm no deployment errors in console output

**Expected Results**:
- All detected patterns deployed
- Resources created in target tenant
- No Terraform errors
- Relationships preserved (verify in next test)

**Pass Criteria**:
- ✅ Dry-run completes without errors
- ✅ Terraform validate succeeds
- ✅ Deployment completes successfully
- ✅ Resources visible in Azure Portal
- ✅ Resource count matches replication plan

---

### Test 2: Filtered Deployment (Single Pattern)

**Objective**: Deploy only one architectural pattern to verify pattern filtering works.

**Steps**:

1. **Identify Available Patterns**
   ```bash
   # Run dry-run and note pattern names in output
   azure-tenant-grapher deploy \
     --from-replication-plan \
     --target-tenant-id <TARGET_TENANT_ID> \
     --resource-group "atg-integration-test-rg" \
     --dry-run \
     2>&1 | grep "Found.*architectural patterns"
   ```

2. **Deploy Single Pattern**
   ```bash
   # Replace "Web Application" with actual pattern name from your tenant
   azure-tenant-grapher deploy \
     --from-replication-plan \
     --pattern-filter "Web Application" \
     --target-tenant-id <TARGET_TENANT_ID> \
     --resource-group "atg-integration-test-pattern-filter" \
     --location "eastus"
   ```

3. **Verify Selective Deployment**
   - Check Azure Portal
   - Confirm ONLY resources from selected pattern are present
   - Verify other patterns were NOT deployed

**Expected Results**:
- Only filtered pattern resources deployed
- Other patterns excluded
- Resource types match pattern composition

**Pass Criteria**:
- ✅ Only selected pattern resources created
- ✅ Resource count matches single pattern
- ✅ No resources from other patterns

---

### Test 3: Instance Filtering

**Objective**: Deploy subset of instances for a pattern to verify instance filtering.

**Steps**:

1. **Deploy with Instance Filter**
   ```bash
   # Deploy only first two instances (indices 0 and 1)
   azure-tenant-grapher deploy \
     --from-replication-plan \
     --pattern-filter "Web Application" \
     --instance-filter "0-1" \
     --target-tenant-id <TARGET_TENANT_ID> \
     --resource-group "atg-integration-test-instance-filter" \
     --location "eastus"
   ```

2. **Verify Instance Count**
   - Check generated IaC
   - Count resource instances in Terraform files
   - Verify only 2 instance groups deployed

3. **Test Alternative Filter Syntax**
   ```bash
   # Clean up previous test
   az group delete --name "atg-integration-test-instance-filter" --yes --no-wait

   # Test comma-separated syntax: Deploy instances 0 and 2
   azure-tenant-grapher deploy \
     --from-replication-plan \
     --pattern-filter "Web Application" \
     --instance-filter "0,2" \
     --target-tenant-id <TARGET_TENANT_ID> \
     --resource-group "atg-integration-test-instance-filter" \
     --location "eastus"
   ```

**Expected Results**:
- Correct number of instances deployed
- Instance indices match filter specification
- Other instances excluded

**Pass Criteria**:
- ✅ Instance count matches filter (2 instances for "0-1")
- ✅ Correct instances selected (0 and 2 for "0,2" syntax)
- ✅ No unexpected instances deployed

---

### Test 4: Relationship Preservation

**Objective**: Verify instance-level relationships are preserved in IaC.

**Steps**:

1. **Deploy Pattern with Known Relationships**
   ```bash
   # Deploy VM Workload pattern (VMs typically have CONTAINS relationships with NICs)
   azure-tenant-grapher deploy \
     --from-replication-plan \
     --pattern-filter "VM Workload" \
     --instance-filter "0" \
     --target-tenant-id <TARGET_TENANT_ID> \
     --resource-group "atg-integration-test-relationships" \
     --location "eastus" \
     --dry-run
   ```

2. **Inspect Terraform for Relationships**
   ```bash
   cd ./output/iac-from-replication

   # Check for dependency declarations
   grep -r "depends_on" *.tf

   # Check for resource references (e.g., network_interface_ids)
   grep -r "network_interface" *.tf
   ```

3. **Verify Deployment Order**
   ```bash
   # Run terraform plan and check resource creation order
   terraform plan

   # Look for dependency chains in plan output
   ```

**Expected Results**:
- Relationships preserved in IaC (depends_on, resource references)
- Dependent resources created in correct order
- No missing dependency errors during deployment

**Pass Criteria**:
- ✅ Terraform files contain `depends_on` declarations
- ✅ Resource references present (e.g., NIC IDs in VM config)
- ✅ Terraform plan shows correct creation order
- ✅ No dependency errors during deployment

---

### Test 5: Globally Unique Names

**Objective**: Verify globally unique resource names are transformed correctly.

**Steps**:

1. **Deploy Pattern with Storage Account**
   ```bash
   # Deploy pattern containing Storage Accounts or Key Vaults
   azure-tenant-grapher deploy \
     --from-replication-plan \
     --pattern-filter "Storage Pattern" \
     --instance-filter "0" \
     --target-tenant-id <TARGET_TENANT_ID> \
     --resource-group "atg-integration-test-unique-names" \
     --location "eastus" \
     --dry-run
   ```

2. **Inspect Generated Names**
   ```bash
   cd ./output/iac-from-replication

   # Check Storage Account names
   grep -A 5 "resource \"azurerm_storage_account\"" *.tf | grep "name"

   # Verify names follow Azure constraints:
   # - 3-24 characters
   # - lowercase letters and numbers only
   # - globally unique
   ```

3. **Verify Name Transformation**
   - Check that hyphens removed (Storage Accounts don't support hyphens)
   - Verify length is within limits
   - Confirm uniqueness suffix applied

**Expected Results**:
- Storage Account names valid (no hyphens, correct length)
- Key Vault names valid (hyphens allowed, correct length)
- Container Registry names valid (alphanumeric only, 5-50 chars)
- Names are globally unique

**Pass Criteria**:
- ✅ All generated names meet Azure naming constraints
- ✅ No hyphens in Storage Account names
- ✅ Names within length limits (3-24 for storage, 3-24 for key vaults, 5-50 for ACR)
- ✅ Deployment succeeds without name conflicts

---

### Test 6: Multi-Format Consistency

**Objective**: Verify same replication plan generates consistent IaC across formats.

**Steps**:

1. **Generate Terraform**
   ```bash
   azure-tenant-grapher deploy \
     --from-replication-plan \
     --pattern-filter "Web Application" \
     --instance-filter "0" \
     --target-tenant-id <TARGET_TENANT_ID> \
     --resource-group "atg-integration-test-terraform" \
     --format terraform \
     --dry-run

   # Save output for comparison
   cp -r ./output/iac-from-replication ./output/iac-terraform
   ```

2. **Generate Bicep**
   ```bash
   azure-tenant-grapher deploy \
     --from-replication-plan \
     --pattern-filter "Web Application" \
     --instance-filter "0" \
     --target-tenant-id <TARGET_TENANT_ID> \
     --resource-group "atg-integration-test-bicep" \
     --format bicep \
     --dry-run

   # Save output for comparison
   cp -r ./output/iac-from-replication ./output/iac-bicep
   ```

3. **Generate ARM**
   ```bash
   azure-tenant-grapher deploy \
     --from-replication-plan \
     --pattern-filter "Web Application" \
     --instance-filter "0" \
     --target-tenant-id <TARGET_TENANT_ID> \
     --resource-group "atg-integration-test-arm" \
     --format arm \
     --dry-run

   # Save output for comparison
   cp -r ./output/iac-from-replication ./output/iac-arm
   ```

4. **Compare Resource Counts**
   ```bash
   # Count Terraform resources
   grep -c "resource \"azurerm_" ./output/iac-terraform/*.tf

   # Count Bicep resources
   grep -c "^resource " ./output/iac-bicep/*.bicep

   # Count ARM resources
   jq '.resources | length' ./output/iac-arm/template.json
   ```

5. **Validate Each Format**
   ```bash
   # Validate Terraform
   cd ./output/iac-terraform && terraform validate

   # Validate Bicep
   cd ../iac-bicep && az bicep build --file main.bicep

   # Validate ARM
   cd ../iac-arm && az deployment group validate \
     --resource-group "atg-integration-test-arm" \
     --template-file template.json
   ```

**Expected Results**:
- Same resource count across all formats
- Same resource types in each format
- All formats validate successfully
- Resource configurations equivalent

**Pass Criteria**:
- ✅ Resource count identical across formats
- ✅ Terraform validate succeeds
- ✅ Bicep build succeeds
- ✅ ARM template validation succeeds
- ✅ No format-specific errors

---

## Validation Procedures

### IaC Validation

**Terraform**:
```bash
cd ./output/iac-from-replication

# Initialize
terraform init

# Validate syntax
terraform validate

# Check plan (requires Azure authentication)
terraform plan

# Expected output:
# - No syntax errors
# - Plan succeeds
# - Resource count matches expectations
```

**Bicep**:
```bash
cd ./output/iac-from-replication

# Build Bicep to ARM
az bicep build --file main.bicep

# Expected output:
# - No compilation errors
# - main.json generated successfully
```

**ARM**:
```bash
cd ./output/iac-from-replication

# Validate template
az deployment group validate \
  --resource-group <TEST_RG> \
  --template-file template.json

# Expected output:
# - Validation succeeded
# - No schema errors
```

### Deployment Validation

**Resource Existence**:
```bash
# List resources in test resource group
az resource list \
  --resource-group "atg-integration-test-rg" \
  --output table

# Expected output:
# - All expected resources present
# - Resource types match replication plan
# - No unexpected resources
```

**Relationship Validation**:
```bash
# Check VM has NIC attached
az vm show \
  --resource-group "atg-integration-test-rg" \
  --name <VM_NAME> \
  --query "networkProfile.networkInterfaces[].id" \
  --output tsv

# Expected output:
# - NIC resource ID present
# - NIC exists in same resource group
```

**Configuration Validation**:
```bash
# Check resource properties
az resource show \
  --resource-group "atg-integration-test-rg" \
  --name <RESOURCE_NAME> \
  --resource-type <TYPE> \
  --output json

# Verify:
# - Location matches
# - Tags present (if applicable)
# - Properties match source configuration
```

## Troubleshooting Common Issues

### Issue: Neo4j Connection Failed

**Symptoms**:
```
Error: NEO4J_PASSWORD environment variable is required
```

**Solution**:
```bash
# Verify Neo4j is running
docker ps | grep neo4j

# Set environment variable
export NEO4J_PASSWORD="your-password"

# Test connection
docker exec -it azure-tenant-grapher-neo4j cypher-shell \
  -u neo4j -p $NEO4J_PASSWORD \
  -d neo4j "RETURN 1"
```

---

### Issue: No Patterns Detected

**Symptoms**:
```
Found 0 architectural patterns
```

**Solution**:
1. Verify source tenant scan completed
2. Check resource count in Neo4j
3. Ensure minimum resource diversity (10-15 resources recommended)

```bash
# Check resource count
docker exec -it azure-tenant-grapher-neo4j cypher-shell \
  -u neo4j -p $NEO4J_PASSWORD \
  -d neo4j "MATCH (n:Resource:Original) RETURN count(n)"

# If count is low, re-scan source tenant
azure-tenant-grapher scan --tenant-id <SOURCE_TENANT_ID>
```

---

### Issue: Terraform Validation Fails

**Symptoms**:
```
Error: Invalid resource type
```

**Solution**:
1. Check Terraform version compatibility
2. Verify Azure provider version
3. Review generated .tf files for syntax errors

```bash
# Check Terraform version
terraform version

# Re-initialize with correct provider
cd ./output/iac-from-replication
rm -rf .terraform*
terraform init
```

---

### Issue: Deployment Fails with Name Conflict

**Symptoms**:
```
Error: Storage account name already exists
```

**Solution**:
1. Check if resource from previous test still exists
2. Clean up previous deployments
3. Verify name transformation applied

```bash
# List storage accounts in subscription
az storage account list --output table

# Delete conflicting resource
az storage account delete \
  --name <CONFLICTING_NAME> \
  --resource-group <RG> \
  --yes
```

---

### Issue: Missing Relationships in IaC

**Symptoms**:
- No `depends_on` in Terraform
- Resources created in wrong order

**Solution**:
1. Verify source tenant has relationships
2. Check relationship types included in query

```bash
# Query relationships in Neo4j
docker exec -it azure-tenant-grapher-neo4j cypher-shell \
  -u neo4j -p $NEO4J_PASSWORD \
  -d neo4j "MATCH (s:Resource:Original)-[r]->(t:Resource:Original) RETURN type(r), count(*) ORDER BY count(*) DESC"

# Expected output:
# - CONTAINS, DEPENDS_ON, etc. with counts
```

---

## Test Cleanup

After completing integration tests, clean up all created resources:

```bash
# List all integration test resource groups
az group list --query "[?starts_with(name, 'atg-integration-test')]" --output table

# Delete all test resource groups
for rg in $(az group list --query "[?starts_with(name, 'atg-integration-test')].name" -o tsv); do
  echo "Deleting $rg..."
  az group delete --name "$rg" --yes --no-wait
done

# Verify deletion completed
az group list --query "[?starts_with(name, 'atg-integration-test')]" --output table

# Clean up local IaC output directories
rm -rf ./output/iac-from-replication
rm -rf ./output/iac-terraform
rm -rf ./output/iac-bicep
rm -rf ./output/iac-arm
```

## Test Execution Checklist

Use this checklist when running integration tests:

### Pre-Test Setup
- [ ] Source tenant scanned successfully
- [ ] Neo4j running with data
- [ ] Environment variables set (NEO4J_*, AZURE_TENANT_ID)
- [ ] Authenticated to target tenant (`az login`)
- [ ] Test resource groups created

### Test Execution
- [ ] Test 1: Full Deployment - Passed
- [ ] Test 2: Filtered Deployment (Pattern) - Passed
- [ ] Test 3: Instance Filtering - Passed
- [ ] Test 4: Relationship Preservation - Passed
- [ ] Test 5: Globally Unique Names - Passed
- [ ] Test 6: Multi-Format Consistency - Passed

### Validation
- [ ] IaC files validate successfully (Terraform/Bicep/ARM)
- [ ] Resources deployed to Azure
- [ ] Relationships preserved
- [ ] Names meet Azure constraints
- [ ] No deployment errors

### Post-Test Cleanup
- [ ] All test resource groups deleted
- [ ] Local IaC output directories cleaned
- [ ] No orphaned resources in subscription

## Success Metrics

**Integration testing is successful when**:

1. **Completeness**: All 6 test scenarios pass
2. **Correctness**: Generated IaC validates without errors
3. **Deployment**: Resources deploy successfully to target tenant
4. **Relationships**: Dependencies preserved in IaC
5. **Naming**: Globally unique names meet Azure constraints
6. **Consistency**: All IaC formats produce equivalent results

## Next Steps

After successful integration testing:

1. **Document Results**: Record test outcomes and any issues encountered
2. **Update Documentation**: If issues found, update troubleshooting guides
3. **User Acceptance**: Have users validate with real scenarios
4. **Production Readiness**: Mark feature as production-ready

## See Also

- [Deploy from Replication Plans Guide](../howto/deploy-replication-plan.md) - User deployment guide
- [Architecture-Based Deployment Concepts](../concepts/architecture-based-deployment.md) - Design explanation
- [Architecture Document](.claude/docs/ARCHITECTURE_architecture_based_replication_deployment.md) - Full specification

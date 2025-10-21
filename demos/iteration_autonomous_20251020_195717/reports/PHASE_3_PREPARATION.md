# Phase 3: IaC Generation - PREPARATION 📋

**Preparation Started**: 2025-10-20 20:09 UTC
**Phase 3 Start**: Pending Phase 2 completion
**Estimated Duration**: 4-6 turns (~10-15 minutes)

## Overview

Phase 3 will generate Infrastructure-as-Code (IaC) templates in Terraform format from the Neo4j graph database populated during Phase 2.

## Prerequisites

### Phase 2 Completion Criteria (To Be Met)
- ✅ Source tenant fully scanned (1,632 resources discovered)
- ⏳ Neo4j database fully populated
- ⏳ Specification file generated
- ⏳ All resource relationships established
- ⏳ No blocking scan errors

### Phase 3 Requirements
- ✅ Neo4j running and accessible
- ✅ Terraform v1.13.4 installed
- ✅ Target tenant credentials configured
- ✅ Iteration directory structure in place

## IaC Generation Strategy

### Command to Execute
```bash
uv run atg generate-iac \
  --tenant-id <TARGET_TENANT_ID> \
  --format terraform \
  --output-dir demos/iteration_autonomous_001/terraform/ \
  --validate-subnets \
  --auto-fix-subnets
```

### Key Parameters
- **`--format terraform`**: Generate Terraform HCL format
- **`--validate-subnets`**: Ensure subnet address spaces are within VNet ranges
- **`--auto-fix-subnets`**: Automatically correct subnet misconfigurations (Issue #333 fix)
- **`--output-dir`**: Target directory for generated templates

### Expected Outputs

1. **Terraform Files**:
   - `main.tf` - Main resource definitions
   - `variables.tf` - Variable declarations
   - `outputs.tf` - Output values
   - `providers.tf` - Azure provider configuration
   - `terraform.tfvars` - Variable values

2. **Resource Files by Type**:
   - `network.tf` - VNets, subnets, NSGs
   - `compute.tf` - VMs, VM scale sets
   - `storage.tf` - Storage accounts
   - `identity.tf` - Managed identities
   - `database.tf` - SQL, Cosmos DB
   - Additional files per resource category

3. **Dependency Graph**:
   - Resources ordered by dependencies
   - Proper `depends_on` relationships
   - No circular dependencies

## Architecture Components Involved

### Core Services
- **IaC Traverser** (`src/iac/traverser.py`): Traverses Neo4j graph
- **Terraform Emitter** (`src/iac/emitters/terraform_emitter.py`): Generates HCL
- **Subnet Validator** (`src/iac/validators/subnet_validator.py`): Validates subnets
- **Dependency Resolver**: Orders resources correctly

### Graph Traversal Strategy
1. Query Neo4j for all resources and relationships
2. Build dependency tree
3. Topologically sort resources
4. Generate templates in correct order
5. Apply subnet validation and auto-fix

## Known Challenges and Mitigations

### Challenge 1: Large Resource Count (1,632 resources)
**Impact**: May generate very large Terraform files
**Mitigation**:
- Split into multiple files by resource type
- Use Terraform modules for organization
- Generate deployment in phases if needed

### Challenge 2: Subnet Validation (Issue #333)
**Impact**: Invalid subnet address spaces can cause deployment failures
**Mitigation**:
- `--validate-subnets` flag enabled by default
- `--auto-fix-subnets` will correct common issues
- Manual review if auto-fix cannot resolve

### Challenge 3: Resource Dependencies
**Impact**: Incorrect ordering causes deployment failures
**Mitigation**:
- Dependency resolver analyzes Neo4j relationships
- `depends_on` attributes added where needed
- Explicit resource references maintained

### Challenge 4: Azure API Rate Limits
**Impact**: May slow validation during generation
**Mitigation**:
- Batch validation requests
- Exponential backoff on rate limit errors
- Cache validation results

## Success Criteria

### Phase 3 Completion Requirements
- ✅ All 1,632 resources represented in IaC
- ✅ Terraform validates successfully (`terraform validate`)
- ✅ Subnet validation passes (no critical errors)
- ✅ Dependency graph is acyclic
- ✅ Resources properly organized by type
- ✅ No generation errors or warnings

### Quality Metrics
- **Coverage**: 100% of scanned resources
- **Validation**: 0 terraform validation errors
- **Organization**: Resources split into logical files
- **Documentation**: Inline comments for complex resources

## Resource Type Mapping

### Expected Resource Categories

| Azure Resource Type | Terraform Resource | Estimated Count |
|---------------------|-------------------|-----------------|
| Virtual Networks | `azurerm_virtual_network` | ~50 |
| Subnets | `azurerm_subnet` | ~150 |
| Network Security Groups | `azurerm_network_security_group` | ~150 |
| Storage Accounts | `azurerm_storage_account` | ~100 |
| Virtual Machines | `azurerm_virtual_machine` | ~50 |
| Managed Disks | `azurerm_managed_disk` | ~100 |
| Public IPs | `azurerm_public_ip` | ~50 |
| NICs | `azurerm_network_interface` | ~100 |
| App Services | `azurerm_app_service` | ~30 |
| Key Vaults | `azurerm_key_vault` | ~20 |
| SQL Databases | `azurerm_sql_database` | ~10 |
| Other Resources | Various | ~832 |

### Resource Types Not Supported
The following will be skipped (control plane only, no data plane):
- Actual data in storage accounts
- Key vault secrets/keys
- Database data
- VM disk contents

## Autonomous Agent Decision Points

### Decision 1: Output Directory Structure
**Options**:
- Single directory with all files
- Subdirectories by resource type
- Subdirectories by resource group

**Expected Decision**: Subdirectories by resource type (better organization)

### Decision 2: Subnet Auto-Fix Strategy
**Options**:
- Skip auto-fix, generate warnings only
- Auto-fix and document changes
- Interactive review (not possible in autonomous mode)

**Expected Decision**: Auto-fix and document (maximizes deployment success)

### Decision 3: Large File Handling
**Options**:
- Generate single massive main.tf
- Split by resource type
- Split by resource group

**Expected Decision**: Split by resource type (Terraform best practice)

## Timeline Projection

### Estimated Phase 3 Timeline
- **Turn 3**: Initiate IaC generation command
- **Turn 3-4**: Process resources and generate templates
- **Turn 4**: Validate Terraform syntax
- **Turn 5**: Apply subnet fixes if needed
- **Turn 5-6**: Final validation and documentation
- **Phase 3 Complete**: Turn 6 (estimated)

### Contingency Plans
- If generation takes >6 turns, continue but document delay
- If validation fails, retry with stricter subnet validation
- If resource count too large, split into multiple terraform workspaces

## Monitoring Plan

### Metrics to Track
- Resources processed per minute
- Files generated
- Validation errors encountered
- Auto-fix applications
- Turn consumption

### Success Indicators
- ✅ Generation completes without crashes
- ✅ All resources accounted for
- ✅ Terraform validation passes
- ✅ Ready to deploy to target tenant

---

**Status**: 🟡 READY TO BEGIN (Awaiting Phase 2 completion)

Phase 3 preparation complete. Will automatically initiate when Phase 2 completes successfully.

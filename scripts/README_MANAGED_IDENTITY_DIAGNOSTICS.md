# Managed Identity RBAC Diagnostics

This script diagnoses issues with Managed Identity RBAC role assignments and resource bindings during Azure tenant replication (Issue #889).

## Purpose

This is a **permanent diagnostic tool** for troubleshooting common Managed Identity configuration and permission issues. It helps identify root causes when:

- RBAC role assignments are missing from replicated infrastructure
- Managed Identity bindings are not preserved on resources
- Identity relationships are not discovered correctly

## Common Root Causes Detected

1. **Insufficient Scan Permissions** (Most Common)
   - Service principal lacks "User Access Administrator" role
   - Cannot discover role assignments in Azure
   
2. **Cross-Tenant Identity Mapping Issues**
   - Missing `identity_mapping.json` in cross-tenant deployments
   - Role assignments filtered out during cross-tenant operations

3. **Neo4j Data Integrity Problems**
   - Identity properties not preserved correctly
   - Relationship creation failures

## Usage

### Basic Usage

```bash
# Diagnose issues for a specific Managed Identity
python scripts/diagnose_managed_identity_issue.py \
  --neo4j-password <password> \
  --mi-name mgid-160224hpcp4rein6
```

### With Custom Neo4j Connection

```bash
# Specify custom Neo4j URI and credentials
python scripts/diagnose_managed_identity_issue.py \
  --neo4j-uri bolt://localhost:7687 \
  --neo4j-user neo4j \
  --neo4j-password <password> \
  --mi-name mgid-160224hpcp4rein6
```

### General Diagnostics (All Managed Identities)

```bash
# Run diagnostics without specifying a particular MI
python scripts/diagnose_managed_identity_issue.py \
  --neo4j-password <password>
```

## Output Examples

### All Checks Passed

```
Running Managed Identity diagnostics...

Check 1: Role Assignments in Neo4j
✅ OK - Found 45 role assignments in Neo4j

Check 2: Managed Identity Data Integrity
✅ OK - Found 3 Managed Identities in Neo4j

Check 3: Identity Relationships
✅ OK - Found relationships: HAS_ROLE: 15, USES_IDENTITY: 8

Check 4: Resource Identity Bindings
✅ OK - Found resources with identity bindings

✅ ALL CHECKS PASSED - Issue may be in IaC emission, not discovery

Next steps:
1. Check if role_assignment handler is registered in emitters
2. Verify identity mapping exists for cross-tenant deployments
3. Review emission logs for filtering messages
```

### Permission Issues Detected

```
Running Managed Identity diagnostics...

Check 1: Role Assignments in Neo4j
❌ FAIL - NO role assignments found - check scan permissions

Check 2: Managed Identity Data Integrity
✅ OK - Found 3 Managed Identities in Neo4j

Check 3: Identity Relationships
⚠️  WARN - No identity relationships found

Check 4: Resource Identity Bindings
⚠️  WARN - No resources with identity bindings found

❌ 1 CRITICAL ISSUES FOUND:
   - Role Assignments

Next steps:
1. Verify scan service principal has 'User Access Administrator' role
2. Re-run Azure tenant scan with proper permissions
3. Check Azure RBAC portal to confirm role assignments exist
```

## When to Use This Tool

### Use this diagnostic tool when:

- Setting up a new tenant replication and want to verify configuration
- Troubleshooting missing role assignments in replicated infrastructure
- Validating that scan permissions are correctly configured
- Investigating identity binding preservation issues
- Confirming Neo4j graph data integrity after a scan

### Don't use this tool for:

- Creating or modifying role assignments (use Azure Portal/CLI)
- Fixing code bugs in handlers or discovery logic (this is diagnostic only)
- Scanning Azure resources (use the main discovery service)

## Integration with Workflow

This tool fits into the troubleshooting workflow:

1. **After Azure Scan**: Run diagnostics to verify data was captured
2. **Before IaC Generation**: Confirm all identity data is present
3. **After Deployment Issues**: Diagnose root cause of missing role assignments
4. **During Setup**: Validate permissions before starting large scans

## Exit Codes

- `0`: All checks passed or warnings only
- `1`: Critical issues detected requiring action

## Related Documentation

- Issue #889: Managed Identity RBAC & Resource Bindings
- Azure RBAC Permission Requirements
- Cross-Tenant Deployment Guide
- Identity Mapping Configuration

## Maintenance

This diagnostic tool should be maintained as Azure's identity and RBAC features evolve. Update detection logic when:

- New identity property fields are added
- RBAC role assignment schema changes
- New relationship types are introduced
- Neo4j schema is updated

## Support

For issues with this diagnostic tool:
1. Check the script's inline documentation
2. Review Issue #889 for context
3. Verify Neo4j connection parameters
4. Ensure proper Azure authentication

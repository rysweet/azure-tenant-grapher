# Version Tracking Tutorial

**Type**: Tutorial (Learning-oriented)
**Audience**: New Azure Tenant Grapher users
**Time**: 30 minutes
**Last Updated**: 2026-01-16

This tutorial teaches you how version tracking works by walking through a complete scenario from first installation to handling your first version mismatch.

## What You'll Learn

By the end of this tutorial, you'll understand:
- How version tracking protects your graph data
- What happens when versions don't match
- How to safely rebuild your graph
- When to rebuild vs. when to skip

## Prerequisites

- Azure Tenant Grapher installed (`pip install azure-tenant-grapher`)
- Azure credentials configured (`az login`)
- A test Azure tenant or subscription
- Neo4j database running

## Step 1: Your First Scan (Clean Slate)

Let's start with a fresh installation and scan a tenant.

### Action: Run Your First Scan

```bash
atg scan --tenant-id tutorial-tenant
```

### What You'll See

```
Azure Tenant Grapher v1.5.0

✓ Version check passed (no existing database)
✓ Initializing Neo4j connection...
✓ Scanning subscriptions...
✓ Found 3 subscriptions, 147 resources

Building graph...
[Progress bar: 147/147 resources processed]

✓ Graph construction complete
✓ Version metadata saved: 1.5.0
✓ Last scan: 2026-01-16T14:30:00Z

Summary:
  Nodes created: 147
  Relationships created: 284
  Time elapsed: 3m 45s
```

### What Just Happened

1. ATG checked for existing version metadata (found none - fresh install)
2. Scanned Azure resources using API calls
3. Built Neo4j graph with nodes and relationships
4. Saved metadata node with current version (1.5.0)

### Verify: Check the Metadata Node

```bash
# Query Neo4j for metadata
neo4j-shell -c "MATCH (m:ATG_Metadata) RETURN m"
```

**Output:**

```
┌──────────────────────────────────────────────────────┐
│ m                                                    │
├──────────────────────────────────────────────────────┤
│ (:ATG_Metadata {                                     │
│   graph_construction_version: "1.5.0",               │
│   last_scan_at: "2026-01-16T14:30:00Z"               │
│ })                                                   │
└──────────────────────────────────────────────────────┘
```

**Key insight**: The version is now stored in your database.

## Step 2: Simulate an Upgrade (Time Travel)

Imagine three months pass. ATG releases version 1.8.0 with new relationship types. You upgrade your installation.

### Action: Upgrade ATG

```bash
pip install --upgrade azure-tenant-grapher

# Check new version
atg --version
# Output: Azure Tenant Grapher v1.8.0
```

### What Changed

Version 1.8.0 added:
- `DELEGATED_TO` relationships for Azure Lighthouse
- `compliance_tags` property on resources
- Improved RBAC relationship detection

Your database still contains the 1.5.0 graph structure.

## Step 3: Your First Version Mismatch Warning

Now run a scan with the new version against your old database.

### Action: Run a Scan

```bash
atg scan --tenant-id tutorial-tenant
```

### What You'll See

```
Azure Tenant Grapher v1.8.0

⚠️  Version Mismatch Detected
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   Current code version: 1.8.0
   Database version: 1.5.0

   Your graph was built with an older version and may be
   missing:
   - DELEGATED_TO relationships (Azure Lighthouse)
   - compliance_tags properties
   - Improved RBAC detection

   Recommendation: Rebuild your graph to get complete data.

   To rebuild:
     atg backup-metadata --tenant-id tutorial-tenant
     atg rebuild --tenant-id tutorial-tenant

   To suppress this warning:
     (This warning is informational - operations continue)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Continuing with scan...

✓ Scanning resources...
✓ Added 5 new resources
✓ Updated 12 changed resources

Summary:
  New nodes: 5
  Updated nodes: 12
  Time elapsed: 1m 15s

⚠️  Database version still 1.5.0 (rebuild to update)
```

### What Just Happened

1. ATG detected version mismatch (1.8.0 code vs. 1.5.0 database)
2. Displayed informational warning
3. Scan continued normally (non-blocking behavior)
4. New resources added using 1.8.0 logic
5. Old resources retain 1.5.0 structure

**Your graph now has mixed versions** - some parts use 1.5.0 logic, new parts use 1.8.0 logic.

## Step 4: Investigate What Changed

Before rebuilding, let's understand what changed between versions.

### Action: Check the Changelog

```bash
# View version changes in git history
git log --grep="GRAPH_CONSTRUCTION_VERSION" --oneline
```

**Output:**

```
a1b2c3d Bump GRAPH_CONSTRUCTION_VERSION to 1.8.0
e4f5g6h Bump GRAPH_CONSTRUCTION_VERSION to 1.7.0
i7j8k9l Bump GRAPH_CONSTRUCTION_VERSION to 1.6.0
m0n1o2p Initial version 1.5.0
```

### Action: View Specific Change Details

```bash
# See what changed in version 1.8.0
git show a1b2c3d
```

**Output:**

```
commit a1b2c3d
Author: ATG Team
Date: 2026-01-10

Bump GRAPH_CONSTRUCTION_VERSION to 1.8.0

Added support for Azure Lighthouse cross-tenant scenarios:

- New relationship: (ManagedTenant)-[:DELEGATED_TO]->(ManagingTenant)
- New property: compliance_tags on all resource nodes
- Improved RBAC detection: now includes inherited assignments

Impact:
  Required for: Multi-tenant MSPs, Azure Lighthouse users
  Optional for: Single-tenant users without Lighthouse

Breaking changes: None (additive only)

Files changed:
  src/graph_builder.py | 45 +++++++++++++++++++++
  src/relationships/lighthouse.py | 123 +++++++++++++++++++
```

### Key Questions to Ask

1. **Do I use Azure Lighthouse?**
   - Yes → Rebuild to get `DELEGATED_TO` relationships
   - No → Rebuild is optional

2. **Do I need compliance_tags?**
   - Yes → Rebuild to get new properties
   - No → Current graph sufficient

3. **Is this a breaking change?**
   - No → Additive only, safe to rebuild

**Decision for this tutorial**: Let's rebuild to learn the process.

## Step 5: Backup Metadata (Safety First)

Always backup before rebuilding.

### Action: Create Backup

```bash
atg backup-metadata --tenant-id tutorial-tenant
```

### What You'll See

```
Azure Tenant Grapher v1.8.0

Creating metadata backup...

✓ Metadata backed up successfully

Backup details:
  File: backups/tutorial-tenant-metadata-20260116-143500.json
  Size: 2.4 KB
  Contents:
    - Graph construction version: 1.5.0
    - Last scan timestamp: 2026-01-16T14:30:00Z
    - Tenant ID: tutorial-tenant
    - Subscription count: 3
    - Resource count: 152

To restore (if needed):
  atg restore-metadata --file backups/tutorial-tenant-metadata-20260116-143500.json
```

### Action: Verify Backup File

```bash
# View the backup
cat backups/tutorial-tenant-metadata-20260116-143500.json
```

**Output:**

```json
{
  "backup_timestamp": "2026-01-16T14:35:00Z",
  "atg_version": "1.8.0",
  "metadata": {
    "graph_construction_version": "1.5.0",
    "last_scan_at": "2026-01-16T14:30:00Z"
  },
  "tenant": {
    "tenant_id": "tutorial-tenant",
    "subscription_count": 3,
    "resource_count": 152
  }
}
```

**Key insight**: The backup contains metadata only, not the full graph. It's a reference point showing what version you had before rebuilding.

## Step 6: Rebuild the Graph

Now let's rebuild with the new version.

### Action: Start the Rebuild

```bash
atg rebuild --tenant-id tutorial-tenant
```

### What You'll See

```
Azure Tenant Grapher v1.8.0

⚠️  REBUILD OPERATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

This will:
  1. Clear all nodes and relationships in Neo4j
  2. Re-scan your Azure tenant from scratch
  3. Rebuild the graph with version 1.8.0 logic

Current database:
  Version: 1.5.0
  Nodes: 152
  Relationships: 298
  Last scan: 2026-01-16T14:30:00Z

Estimated rebuild time: ~4 minutes (based on 152 resources)

Backup created: backups/tutorial-tenant-metadata-20260116-143500.json

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Continue with rebuild? [y/N]: y

✓ Clearing database...
✓ Database cleared (0 nodes remaining)

Scanning Azure tenant...
✓ Discovering subscriptions... (found 3)
✓ Scanning resources... [152/152 complete]

Building graph (version 1.8.0)...
✓ Creating resource nodes... [152/152]
✓ Creating LIGHTHOUSE relationships... [4 new]
✓ Creating RBAC relationships... [87 total, 12 new]
✓ Creating region relationships... [24]
✓ Creating resource group relationships... [152]
✓ Adding compliance_tags properties... [152]

✓ Graph rebuild complete!

Summary:
  Version: 1.5.0 → 1.8.0 ✓
  Nodes: 152 (unchanged)
  Relationships: 298 → 323 (+25 new)
  New features applied:
    - 4 DELEGATED_TO relationships added
    - 12 inherited RBAC assignments detected
    - compliance_tags added to all resources

  Time elapsed: 4m 12s

Next steps:
  - Test queries to verify new relationships work
  - Update dashboards to use compliance_tags
  - Document that tenant uses version 1.8.0
```

### What Just Happened

1. **Database cleared** - All old nodes and relationships deleted
2. **Azure re-scanned** - Fresh API calls to get current state
3. **Graph rebuilt** - New logic applied (version 1.8.0)
4. **Version updated** - Metadata node now shows 1.8.0

## Step 7: Verify the Rebuild

Let's confirm everything worked correctly.

### Action: Check Version Status

```bash
atg scan --tenant-id tutorial-tenant --dry-run
```

**Output:**

```
Azure Tenant Grapher v1.8.0

✓ Version check passed
  Code version: 1.8.0
  Database version: 1.8.0
  Status: ✓ Synchronized

No version mismatch detected.
Dry-run mode: Exiting without scanning.
```

**Success!** No warning appears - versions match.

### Action: Query New Relationships

Let's verify the new `DELEGATED_TO` relationships exist:

```bash
neo4j-shell -c "
  MATCH (mt:ManagedTenant)-[:DELEGATED_TO]->(managing:ManagingTenant)
  RETURN mt.name, managing.name
"
```

**Output:**

```
┌────────────────────────────────────────────────────────┐
│ mt.name                 │ managing.name               │
├────────────────────────────────────────────────────────┤
│ "Contoso-Dev"           │ "Contoso-MSP"               │
│ "Fabrikam-Prod"         │ "Contoso-MSP"               │
│ "Northwind-Test"        │ "Contoso-MSP"               │
│ "AdventureWorks-Staging"│ "Contoso-MSP"               │
└────────────────────────────────────────────────────────┘

4 rows
```

**Perfect!** The new relationships exist. These didn't exist in version 1.5.0.

### Action: Query New Properties

Check that `compliance_tags` properties were added:

```bash
neo4j-shell -c "
  MATCH (r:Resource)
  WHERE r.compliance_tags IS NOT NULL
  RETURN r.name, r.compliance_tags
  LIMIT 3
"
```

**Output:**

```
┌─────────────────────────────────────────────────────────────┐
│ r.name               │ r.compliance_tags                    │
├─────────────────────────────────────────────────────────────┤
│ "webapp-prod-001"    │ ["PCI-DSS", "SOC2", "HIPAA"]         │
│ "sql-db-customer"    │ ["PCI-DSS", "GDPR"]                  │
│ "storage-logs"       │ ["SOC2"]                             │
└─────────────────────────────────────────────────────────────┘
```

**Excellent!** Properties are present with actual compliance tag data.

## Step 8: Compare Before and After

Let's see the difference between versions 1.5.0 and 1.8.0.

### Before Rebuild (v1.5.0)
- 152 nodes
- 298 relationships
- No `DELEGATED_TO` relationships
- No `compliance_tags` properties
- Missing 12 inherited RBAC assignments

### After Rebuild (v1.8.0)
- 152 nodes (same resources)
- 323 relationships (+25 new)
- 4 `DELEGATED_TO` relationships (Lighthouse)
- All resources have `compliance_tags`
- 12 inherited RBAC assignments detected

**Key learning**: Same resources, richer graph. The version change added relationships and properties without changing the core resource data.

## Step 9: Future Scans (Staying Current)

Now when you run scans, no warning appears.

### Action: Run a Regular Scan

```bash
atg scan --tenant-id tutorial-tenant
```

**Output:**

```
Azure Tenant Grapher v1.8.0

✓ Version check passed (1.8.0 = 1.8.0)
✓ Scanning resources...
✓ Updated 3 changed resources
✓ Graph up to date

Summary:
  Nodes: 152
  Relationships: 323
  Time elapsed: 45s
```

No warning! Everything is synchronized.

## Step 10: CI/CD Integration (Bonus)

Let's configure ATG to run in CI/CD with automatic handling.

### Option A: Block on Mismatch

For production environments where you want manual control:

```bash
#!/bin/bash
# .github/workflows/scan-tenant.sh

set -e  # Exit on error

# This will fail (exit 1) if version mismatch detected
atg scan --tenant-id prod-tenant --block-on-mismatch

echo "Scan successful - no version issues"
```

**Behavior:**
- Version match → Pipeline succeeds, scan runs
- Version mismatch → Pipeline fails, manual rebuild required

### Option B: Auto-Rebuild

For test environments where data loss is acceptable:

```bash
#!/bin/bash
# .github/workflows/scan-test-tenant.sh

# Automatically rebuild if version mismatch
atg scan --tenant-id test-tenant --auto-rebuild

echo "Scan successful - rebuilt if needed"
```

**Behavior:**
- Version match → Scan runs normally
- Version mismatch → Automatic rebuild, then scan runs

## What You've Learned

**Core concepts:**
- Version tracking detects when graph construction logic changes
- Mismatches warn but don't block (you stay in control)
- Rebuilding re-scans Azure and applies new logic
- Always backup before rebuilding

**Practical skills:**
- Read version mismatch warnings
- Check git history for what changed
- Safely rebuild your graph
- Verify rebuild success
- Configure CI/CD behavior

**Best practices:**
- Backup metadata before rebuilding (`atg backup-metadata`)
- Understand what changed before rebuilding
- Rebuild during maintenance windows for production
- Use `--auto-rebuild` for test environments only
- Use `--block-on-mismatch` for compliance-critical systems

## Next Steps

Now that you understand version tracking:

1. **Read the how-to guide** - [Handle Version Mismatches](../howto/handle-version-mismatches.md) for specific scenarios
2. **Check the reference** - [Command Reference](../reference/commands.md#rebuild) for all flags and options
3. **Understand the concepts** - [Version Tracking Concepts](../concepts/GRAPH_VERSION_TRACKING.md) for deeper understanding

## Common Questions After This Tutorial

**Q: Do I always need to rebuild after upgrading?**
A: No. Only rebuild if you want the new features/relationships. The warning is informational.

**Q: Can I ignore version warnings forever?**
A: Yes, but your graph becomes increasingly incomplete over time as new features accumulate.

**Q: Will I lose data when rebuilding?**
A: The graph is cleared and rebuilt from Azure. Historical metadata can be backed up (as you learned in Step 5).

**Q: How long do rebuilds take for large tenants?**
A: Roughly 1 minute per 100 resources. A 5,000 resource tenant takes ~50 minutes.

**Q: Can I roll back a rebuild?**
A: No direct rollback. You'd need to downgrade ATG version and rebuild with the older version (not recommended).

## Conclusion

You've successfully completed the version tracking tutorial! You now understand:

- How version tracking protects graph integrity
- When to rebuild vs. when to skip
- How to safely rebuild with backups
- How to verify rebuild success

Version tracking is a safety feature, not a barrier. It ensures you're aware when your graph structure is outdated while giving you full control over when and if to rebuild.

Happy graphing! 🚀

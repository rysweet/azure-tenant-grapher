# How to Handle Version Mismatches

**Type**: How-To Guide (Task-oriented)
**Audience**: DevOps engineers, cloud architects
**Last Updated**: 2026-01-16

This guide shows you how to handle version mismatch warnings when running Azure Tenant Grapher.

## Quick Reference

| Situation | Command |
|-----------|---------|
| Check current version status | `atg scan --tenant-id <id> --dry-run` |
| Backup before rebuilding | `atg backup-metadata --tenant-id <id>` |
| Rebuild graph | `atg rebuild --tenant-id <id>` |
| Auto-rebuild in CI/CD | `atg scan --tenant-id <id> --auto-rebuild` |
| Block on mismatch (CI) | `atg scan --tenant-id <id> --block-on-mismatch` |

## Scenario 1: First Time Seeing a Version Warning

**You run a scan and see:**

```bash
$ atg scan --tenant-id contoso-prod

⚠️  Version Mismatch Detected
   Current code: 1.5.0
   Database: 1.0.0

   Your graph may be incomplete. Consider rebuilding:
   atg rebuild --tenant-id contoso-prod

Continuing with scan...
```

**What to do:**

1. **Read the warning** - Note the version numbers
2. **Check what changed** - See [what changed between versions](#checking-what-changed)
3. **Decide whether to rebuild** - See [decision criteria](#deciding-whether-to-rebuild)
4. **Continue or rebuild** - The scan continues by default

**Quick decision:**
- Need new features → Rebuild now
- Just exploring → Ignore for now
- Production system → Schedule rebuild during maintenance window

## Scenario 2: Checking What Changed Between Versions

**You want to know what changed between database version 1.0.0 and code version 1.5.0.**

### Step 1: View Version History

```bash
# List all version changes
git log --grep="GRAPH_CONSTRUCTION_VERSION" --oneline

# Output:
# abc123 Bump GRAPH_CONSTRUCTION_VERSION to 1.5.0
# def456 Bump GRAPH_CONSTRUCTION_VERSION to 1.4.0
# ghi789 Bump GRAPH_CONSTRUCTION_VERSION to 1.3.0
```

### Step 2: Read Specific Changes

```bash
# View details of version 1.5.0 change
git show abc123

# Look for:
# - Commit message explaining why
# - Code changes showing what relationships/properties were added
```

### Step 3: Assess Impact

Ask yourself:
- Do I use the features mentioned?
- Will the new relationships help my queries?
- Is this a security or compliance fix?

**Example commit message:**

```
Bump GRAPH_CONSTRUCTION_VERSION to 1.5.0

Added LIGHTHOUSE_DELEGATED relationship for Azure Lighthouse
cross-tenant scenarios. Required for proper RBAC visualization
across managed tenants.

Affects: Users of Azure Lighthouse, MSPs managing multiple tenants
```

If you use Azure Lighthouse → Rebuild
If you don't → Safe to skip

## Scenario 3: Safely Rebuilding Your Graph

**You've decided to rebuild. Here's the safe workflow:**

### Step 1: Backup Metadata

```bash
atg backup-metadata --tenant-id contoso-prod

# Output:
# ✓ Metadata backed up to: backups/contoso-prod-metadata-20260116-143000.json
#
# Backup contains:
# - Graph construction version: 1.0.0
# - Last scan timestamp: 2026-01-10T08:15:00Z
# - Tenant configuration
```

**What's backed up**: Version info and metadata, NOT the entire graph.

### Step 2: Rebuild the Graph

```bash
atg rebuild --tenant-id contoso-prod

# Output:
# ⚠️  This will clear the database and rescan all resources.
#    Estimated time: 45 minutes (based on 2,500 resources)
#
# Continue? [y/N]: y
#
# ✓ Database cleared
# ✓ Scanning resources... (1/2500)
# ...
# ✓ Graph rebuilt successfully
# ✓ Version updated to 1.5.0
```

**What happens:**
1. Neo4j database is cleared (all nodes and relationships deleted)
2. Azure tenant is scanned fresh
3. Graph is rebuilt with current version logic
4. Version metadata is updated

**Time estimate**: ~30-60 minutes for typical tenant (1,000-5,000 resources)

### Step 3: Verify the Rebuild

```bash
# Check version matches
atg scan --tenant-id contoso-prod --dry-run

# Output:
# ✓ Version check passed (code: 1.5.0, database: 1.5.0)
# No scan needed (dry-run mode)
```

**Success indicators:**
- No version warning appears
- Queries return expected data
- New features work correctly

## Scenario 4: Handling Version Mismatches in CI/CD

**You run ATG in automated pipelines and need consistent behavior.**

### Option A: Block Pipeline on Mismatch

Use this when you want the pipeline to fail if versions don't match:

```bash
#!/bin/bash
# ci-scan.sh

atg scan --tenant-id ci-test-tenant --block-on-mismatch

# If version mismatch, exit code 1 (pipeline fails)
# If version matches, scan proceeds normally
```

**Output on mismatch:**

```
❌ Version Mismatch Detected
   Current code: 1.5.0
   Database: 1.0.0

   Pipeline blocked (--block-on-mismatch enabled)

   To fix:
   1. Run: atg rebuild --tenant-id ci-test-tenant
   2. Retry pipeline

Exit code: 1
```

**When to use**: Compliance-critical environments, security-focused pipelines

### Option B: Auto-Rebuild on Mismatch

Use this when data loss is acceptable (e.g., test environments):

```bash
#!/bin/bash
# ci-scan-auto-rebuild.sh

atg scan --tenant-id ci-test-tenant --auto-rebuild

# Automatically rebuilds if version mismatch detected
# Then proceeds with scan
```

**Output on mismatch:**

```
⚠️  Version Mismatch Detected (auto-rebuild enabled)
   Current code: 1.5.0
   Database: 1.0.0

✓ Automatically rebuilding...
✓ Database cleared
✓ Scanning resources...
✓ Graph rebuilt successfully
✓ Version updated to 1.5.0

Continuing with scan...
```

**When to use**: Development environments, ephemeral test tenants, nightly builds

### Option C: Separate Rebuild Job

Use this for production environments with controlled rebuilds:

```yaml
# .github/workflows/tenant-graph.yml

jobs:
  check-version:
    runs-on: ubuntu-latest
    steps:
      - name: Check version compatibility
        run: |
          atg scan --tenant-id prod --dry-run
        continue-on-error: true
        id: version-check

      - name: Notify if rebuild needed
        if: failure()
        run: |
          echo "Version mismatch detected. Manual rebuild required."
          # Send notification to ops team

  rebuild-graph:
    runs-on: ubuntu-latest
    # Manual trigger only
    workflow_dispatch:
      inputs:
        confirm:
          description: 'Type REBUILD to confirm'
          required: true
    steps:
      - name: Backup metadata
        run: atg backup-metadata --tenant-id prod

      - name: Rebuild graph
        if: github.event.inputs.confirm == 'REBUILD'
        run: atg rebuild --tenant-id prod
```

**When to use**: Production environments where rebuilds require approval

## Scenario 5: Recovering from a Failed Rebuild

**The rebuild command failed partway through.**

### Step 1: Identify the Failure Point

```bash
# Check logs for error messages
atg logs --tail 50

# Look for:
# - API rate limiting
# - Network timeouts
# - Permission errors
```

### Step 2: Clear Partial State

```bash
# The database may have partial data
# Rebuild will clear it, but you can manually clear if needed
atg db clear --tenant-id contoso-prod --confirm
```

### Step 3: Fix the Issue

**Common issues:**

| Error | Fix |
|-------|-----|
| Rate limiting | Wait 10 minutes, retry |
| Permission denied | Check Azure credentials with `az account show` |
| Network timeout | Check internet connection, retry |
| Out of memory | Reduce batch size in config |

### Step 4: Retry the Rebuild

```bash
atg rebuild --tenant-id contoso-prod

# The rebuild starts fresh (database cleared automatically)
```

## Scenario 6: Postponing a Rebuild

**You see the warning but can't rebuild right now.**

### Acknowledge the Warning

Document that you're aware:

```bash
# Document the decision
echo "Version mismatch: 1.5.0 (code) vs 1.0.0 (db)" > version-status.txt
echo "Decision: Postponing rebuild until maintenance window 2026-01-20" >> version-status.txt
echo "Impact: New Lighthouse relationships not available" >> version-status.txt
```

### Continue Using Current Graph

The warning appears each time you run ATG, but operations continue normally:

```bash
$ atg scan --tenant-id contoso-prod

⚠️  Version Mismatch Detected
   (warning appears every time)

Continuing with scan...
```

### Schedule the Rebuild

Add to your maintenance calendar:

1. **Preparation** (5 min)
   - Review what changed
   - Notify stakeholders
   - Backup metadata

2. **Rebuild** (30-60 min)
   - Run during low-usage window
   - Monitor progress
   - Verify completion

3. **Verification** (10 min)
   - Test key queries
   - Confirm new features work
   - Update documentation

## Deciding Whether to Rebuild

### Rebuild Immediately If:
- ✅ Security vulnerability fixed
- ✅ Compliance requirement added
- ✅ Feature you need is missing
- ✅ Queries returning incorrect results
- ✅ Major version upgrade (1.x → 2.x)

### Rebuild During Maintenance Window If:
- ⏱️ Minor version upgrade (1.4 → 1.5)
- ⏱️ New features you'll use eventually
- ⏱️ Optimization or performance improvement
- ⏱️ Large tenant (>5,000 resources, >1 hour rebuild)

### Safe to Skip If:
- ⛔ Feature doesn't apply to your tenant
- ⛔ Testing or development environment
- ⛔ Graph is temporary/disposable
- ⛔ Version difference is documentation-only

## Troubleshooting

### Problem: Warning Still Appears After Rebuild

**Symptom**: Version warning persists even after successful rebuild.

**Cause**: Metadata node not updated.

**Fix**:

```bash
# Verify database version
echo "MATCH (m:ATG_Metadata) RETURN m.graph_construction_version" | neo4j-shell

# If wrong or missing, rebuild again
atg rebuild --tenant-id contoso-prod --force
```

### Problem: Rebuild Taking Too Long

**Symptom**: Rebuild running for >2 hours.

**Cause**: Large tenant or API throttling.

**Fix**:

```bash
# Check progress
atg status --tenant-id contoso-prod

# If stuck, cancel and tune batch size
# Edit config file:
# batch_size: 50  # Reduce from default 100

# Retry rebuild
atg rebuild --tenant-id contoso-prod
```

### Problem: Can't Remember Database Version

**Symptom**: Need to know database version without running scan.

**Fix**:

```bash
# Query Neo4j directly
echo "MATCH (m:ATG_Metadata) RETURN m" | neo4j-shell

# Or use atg info
atg info --tenant-id contoso-prod
```

## Related Documentation

- [Graph Version Tracking Concepts](../concepts/GRAPH_VERSION_TRACKING.md) - Why version tracking exists
- [Version Tracking Tutorial](../tutorials/version-tracking-tutorial.md) - Step-by-step walkthrough
- [Command Reference](../reference/commands.md) - All command flags and options

## Summary

Version mismatches are **informational warnings**, not errors. You control when and if to rebuild:

1. **See warning** → Understand what changed
2. **Assess impact** → Does it affect your use case?
3. **Decide timing** → Now, scheduled, or never
4. **Backup first** → Always `atg backup-metadata`
5. **Rebuild safely** → `atg rebuild` when ready
6. **Verify** → Confirm version matches

The system never forces rebuilds - you remain in control of your data.

# Version Tracking Command Reference

**Type**: Reference (Information-oriented)
**Audience**: All users
**Last Updated**: 2026-01-16

This reference documents all commands, flags, and options related to graph construction version tracking.

## Commands Overview

| Command | Purpose | Typical Use Case |
|---------|---------|------------------|
| `atg scan` | Scan Azure and detect version mismatches | Regular graph updates |
| `atg rebuild` | Clear database and rebuild with current version | After upgrades |
| `atg backup-metadata` | Backup version and scan metadata | Before rebuilds |
| `atg info` | Display current version status | Check synchronization |

---

## `atg scan`

Scans Azure resources and updates the Neo4j graph. Detects version mismatches before scanning.

### Syntax

```bash
atg scan --tenant-id <TENANT_ID> [OPTIONS]
```

### Version-Related Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--block-on-mismatch` | Flag | False | Exit with error if version mismatch detected |
| `--auto-rebuild` | Flag | False | Automatically rebuild if version mismatch detected |
| `--skip-version-check` | Flag | False | Skip version check (not recommended) |
| `--dry-run` | Flag | False | Check version only, don't scan |

### Behavior Matrix

| Scenario | Default Behavior | With `--block-on-mismatch` | With `--auto-rebuild` |
|----------|------------------|----------------------------|----------------------|
| Version match | Scan normally | Scan normally | Scan normally |
| Version mismatch | Warn, continue scan | Exit with error (code 1) | Rebuild, then scan |

### Examples

#### Default Behavior (Warn and Continue)

```bash
atg scan --tenant-id contoso-prod
```

**Output:**
```
⚠️  Version Mismatch Detected (1.8.0 code vs 1.5.0 database)
   Consider rebuilding: atg rebuild --tenant-id contoso-prod

Continuing with scan...
✓ Scan complete (5 resources added)
```

#### Block Pipeline on Mismatch

```bash
atg scan --tenant-id contoso-prod --block-on-mismatch
```

**Output on mismatch:**
```
❌ Version Mismatch Detected (1.8.0 code vs 1.5.0 database)
   Pipeline blocked (--block-on-mismatch flag enabled)

   To fix:
   1. atg backup-metadata --tenant-id contoso-prod
   2. atg rebuild --tenant-id contoso-prod
   3. Retry this command

Exit code: 1
```

**Use case**: CI/CD pipelines where version consistency is mandatory.

#### Auto-Rebuild on Mismatch

```bash
atg scan --tenant-id test-tenant --auto-rebuild
```

**Output on mismatch:**
```
⚠️  Version Mismatch Detected (auto-rebuild enabled)
   Database: 1.5.0 → Code: 1.8.0

✓ Automatically rebuilding...
✓ Database cleared
✓ Scanning resources... [152/152]
✓ Graph rebuilt (version 1.8.0)

Continuing with scan...
✓ Scan complete
```

**Use case**: Test environments, ephemeral tenants, CI/CD where data loss is acceptable.

#### Check Version Only (No Scan)

```bash
atg scan --tenant-id contoso-prod --dry-run
```

**Output:**
```
✓ Version check passed
  Code: 1.8.0
  Database: 1.8.0
  Status: Synchronized

Dry-run mode: Exiting without scanning.
```

**Use case**: Quick version status check without performing actual scan.

### Exit Codes

| Code | Meaning | When It Occurs |
|------|---------|----------------|
| 0 | Success | Scan completed successfully |
| 1 | Error | `--block-on-mismatch` triggered or scan failed |
| 2 | Invalid arguments | Missing required options |

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ATG_SUPPRESS_VERSION_WARNING` | `false` | Set to `true` to suppress version warnings |
| `ATG_VERSION_CHECK_TIMEOUT` | `5000` | Version check timeout in milliseconds |

**Example:**

```bash
# Suppress version warnings (not recommended)
export ATG_SUPPRESS_VERSION_WARNING=true
atg scan --tenant-id contoso-prod
```

---

## `atg rebuild`

Clears the Neo4j database and rebuilds the graph from scratch using current version logic.

### Syntax

```bash
atg rebuild --tenant-id <TENANT_ID> [OPTIONS]
```

### Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--tenant-id` | String | **Required** | Azure tenant identifier |
| `--force` | Flag | False | Skip confirmation prompt |
| `--no-backup` | Flag | False | Skip automatic metadata backup |
| `--batch-size` | Integer | 100 | Resources to process per batch |
| `--timeout` | Integer | 300 | Timeout per batch in seconds |

### Behavior

1. **Confirmation prompt** (unless `--force`)
2. **Automatic backup** (unless `--no-backup`)
3. **Database clear** - All nodes and relationships deleted
4. **Azure scan** - Fresh API calls to Azure
5. **Graph construction** - Build graph with current version logic
6. **Version update** - Update metadata node to current version

### Examples

#### Interactive Rebuild (Default)

```bash
atg rebuild --tenant-id contoso-prod
```

**Output:**
```
⚠️  REBUILD OPERATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
This will clear the database and rescan all resources.

Current database:
  Version: 1.5.0
  Nodes: 152
  Relationships: 298

Estimated time: 4 minutes

Continue? [y/N]: y

✓ Creating automatic backup...
✓ Backup saved: backups/contoso-prod-20260116-143500.json
✓ Clearing database...
✓ Scanning Azure...
✓ Building graph...
✓ Rebuild complete (version 1.8.0)

Summary:
  Nodes: 152
  Relationships: 323 (+25)
  Time: 4m 12s
```

#### Force Rebuild (No Confirmation)

```bash
atg rebuild --tenant-id contoso-prod --force
```

**Use case**: CI/CD pipelines, automated scripts where interactive prompts break automation.

#### Rebuild Without Backup

```bash
atg rebuild --tenant-id contoso-prod --no-backup
```

**Warning**: Not recommended. Use only for disposable test environments.

#### Rebuild with Custom Batch Size

```bash
# Smaller batches for API rate limiting
atg rebuild --tenant-id contoso-prod --batch-size 50

# Larger batches for faster processing (if no rate limits)
atg rebuild --tenant-id contoso-prod --batch-size 200
```

**Use case**: Tune performance based on Azure API throttling behavior.

### Exit Codes

| Code | Meaning | When It Occurs |
|------|---------|----------------|
| 0 | Success | Rebuild completed successfully |
| 1 | Error | Rebuild failed (network, permissions, etc.) |
| 2 | Cancelled | User cancelled at confirmation prompt |
| 3 | Invalid arguments | Missing or invalid options |

### Time Estimates

| Resource Count | Estimated Time | Notes |
|----------------|----------------|-------|
| 100 resources | ~2 minutes | Small test tenant |
| 500 resources | ~8 minutes | Typical dev environment |
| 1,000 resources | ~15 minutes | Small production tenant |
| 5,000 resources | ~60 minutes | Large tenant |
| 10,000+ resources | ~2+ hours | Enterprise tenant |

**Factors affecting time:**
- Azure API rate limiting
- Network latency
- Neo4j write performance
- Number of relationships

---

## `atg backup-metadata`

Creates a JSON backup of version metadata and scan timestamps.

### Syntax

```bash
atg backup-metadata --tenant-id <TENANT_ID> [OPTIONS]
```

### Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--tenant-id` | String | **Required** | Azure tenant identifier |
| `--output` | String | `backups/` | Output directory for backup file |
| `--format` | String | `json` | Backup format (`json` or `yaml`) |

### Backup Contents

The backup includes:
- Graph construction version
- Last scan timestamp
- Tenant identifier
- Subscription count
- Resource count

**Does NOT include:**
- Full graph data (nodes and relationships)
- Azure resource details
- Query results

### Examples

#### Basic Backup

```bash
atg backup-metadata --tenant-id contoso-prod
```

**Output:**
```
✓ Metadata backed up successfully

Backup details:
  File: backups/contoso-prod-metadata-20260116-143500.json
  Size: 2.4 KB

Contents:
  - Version: 1.5.0
  - Last scan: 2026-01-16T14:30:00Z
  - Resources: 152
```

#### Custom Output Location

```bash
atg backup-metadata --tenant-id contoso-prod --output ./my-backups/
```

#### YAML Format

```bash
atg backup-metadata --tenant-id contoso-prod --format yaml
```

**Output file:**
```yaml
backup_timestamp: "2026-01-16T14:35:00Z"
atg_version: "1.8.0"
metadata:
  graph_construction_version: "1.5.0"
  last_scan_at: "2026-01-16T14:30:00Z"
tenant:
  tenant_id: "contoso-prod"
  subscription_count: 3
  resource_count: 152
```

### Exit Codes

| Code | Meaning | When It Occurs |
|------|---------|----------------|
| 0 | Success | Backup created successfully |
| 1 | Error | Neo4j connection failed or no metadata found |
| 2 | Invalid arguments | Missing tenant ID or invalid path |

---

## `atg info`

Displays current version status and database statistics.

### Syntax

```bash
atg info --tenant-id <TENANT_ID> [OPTIONS]
```

### Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--tenant-id` | String | **Required** | Azure tenant identifier |
| `--verbose` | Flag | False | Show detailed version history |
| `--format` | String | `text` | Output format (`text`, `json`, `yaml`) |

### Examples

#### Basic Info

```bash
atg info --tenant-id contoso-prod
```

**Output:**
```
Azure Tenant Grapher - Version Status

Code Version: 1.8.0
Database Version: 1.8.0
Status: ✓ Synchronized

Database Statistics:
  Nodes: 152
  Relationships: 323
  Last scan: 2026-01-16T14:30:00Z

Version Status: ✓ Up to date
```

#### Verbose Mode

```bash
atg info --tenant-id contoso-prod --verbose
```

**Output:**
```
Azure Tenant Grapher - Version Status

Code Version: 1.8.0
Database Version: 1.8.0
Status: ✓ Synchronized

Database Statistics:
  Nodes: 152
  Relationships: 323
  Last scan: 2026-01-16T14:30:00Z

Version History (last 5 rebuilds):
  1. 2026-01-16 14:30:00 - v1.8.0 (current)
  2. 2025-12-01 09:15:00 - v1.7.0
  3. 2025-10-15 13:45:00 - v1.6.0
  4. 2025-09-20 11:00:00 - v1.5.0
  5. 2025-08-10 08:30:00 - v1.5.0

Latest changes (v1.8.0):
  - Added DELEGATED_TO relationships
  - Added compliance_tags properties
  - Improved RBAC detection
```

#### JSON Output

```bash
atg info --tenant-id contoso-prod --format json
```

**Output:**
```json
{
  "code_version": "1.8.0",
  "database_version": "1.8.0",
  "synchronized": true,
  "statistics": {
    "nodes": 152,
    "relationships": 323,
    "last_scan": "2026-01-16T14:30:00Z"
  },
  "status": "up_to_date"
}
```

**Use case**: Machine-readable output for scripts and monitoring systems.

### Exit Codes

| Code | Meaning | When It Occurs |
|------|---------|----------------|
| 0 | Success | Info retrieved successfully |
| 1 | Warning | Version mismatch detected |
| 2 | Error | Neo4j connection failed |

---

## Version String Format

ATG uses semantic versioning for graph construction versions:

```
MAJOR.MINOR.PATCH

Example: 1.8.0
```

### Version Component Meanings

| Component | Changes When | Example |
|-----------|-------------|---------|
| MAJOR | Breaking schema changes | 1.x.x → 2.0.0 |
| MINOR | New relationships or properties (additive) | 1.5.x → 1.6.0 |
| PATCH | Bug fixes to existing logic | 1.5.0 → 1.5.1 |

### Version Comparison

ATG compares versions using standard semantic versioning rules:

| Comparison | Result | Action Required |
|------------|--------|-----------------|
| 1.8.0 = 1.8.0 | Match | None |
| 1.8.0 > 1.5.0 | Newer code | Consider rebuild |
| 1.5.0 < 1.8.0 | Older database | Rebuild recommended |
| 2.0.0 > 1.8.0 | Major upgrade | Rebuild required |

---

## CI/CD Integration Patterns

### Pattern 1: Block on Mismatch (Production)

```yaml
# .github/workflows/scan-prod.yml
name: Scan Production Tenant

on:
  schedule:
    - cron: '0 2 * * *'  # Daily at 2 AM

jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
      - name: Scan tenant
        run: |
          atg scan \
            --tenant-id ${{ secrets.PROD_TENANT_ID }} \
            --block-on-mismatch

      - name: Notify on version mismatch
        if: failure()
        run: |
          echo "Version mismatch detected. Manual rebuild required."
          # Send notification to ops team
```

### Pattern 2: Auto-Rebuild (Test/Staging)

```yaml
# .github/workflows/scan-test.yml
name: Scan Test Tenant

on:
  push:
    branches: [main]

jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
      - name: Scan tenant (auto-rebuild)
        run: |
          atg scan \
            --tenant-id ${{ secrets.TEST_TENANT_ID }} \
            --auto-rebuild
```

### Pattern 3: Manual Rebuild Approval

```yaml
# .github/workflows/rebuild.yml
name: Rebuild Graph

on:
  workflow_dispatch:
    inputs:
      tenant_id:
        description: 'Tenant ID to rebuild'
        required: true
      confirm:
        description: 'Type REBUILD to confirm'
        required: true

jobs:
  rebuild:
    runs-on: ubuntu-latest
    if: github.event.inputs.confirm == 'REBUILD'
    steps:
      - name: Backup metadata
        run: atg backup-metadata --tenant-id ${{ github.event.inputs.tenant_id }}

      - name: Rebuild graph
        run: atg rebuild --tenant-id ${{ github.event.inputs.tenant_id }} --force

      - name: Verify rebuild
        run: atg info --tenant-id ${{ github.event.inputs.tenant_id }}
```

---

## Troubleshooting Reference

### Problem: Version Check Slow (>5 seconds)

**Symptoms**: `atg scan` hangs at "Checking version..."

**Causes**:
- Neo4j connection timeout
- Large database with slow metadata query

**Solutions**:

```bash
# Increase timeout
export ATG_VERSION_CHECK_TIMEOUT=10000
atg scan --tenant-id contoso-prod

# Skip version check (not recommended)
atg scan --tenant-id contoso-prod --skip-version-check
```

### Problem: Version Mismatch After Rebuild

**Symptoms**: Warning persists after successful rebuild

**Causes**:
- Metadata node not updated
- Multiple ATG_Metadata nodes in database

**Solutions**:

```bash
# Check for duplicate metadata nodes
neo4j-shell -c "MATCH (m:ATG_Metadata) RETURN count(m)"

# If count > 1, clean up and rebuild
neo4j-shell -c "MATCH (m:ATG_Metadata) DELETE m"
atg rebuild --tenant-id contoso-prod --force
```

### Problem: Backup Command Fails

**Symptoms**: `atg backup-metadata` exits with error

**Causes**:
- No metadata node in database (fresh install)
- Neo4j connection failed
- Insufficient disk space

**Solutions**:

```bash
# Check Neo4j connection
neo4j-shell -c "RETURN 1"

# Check metadata exists
neo4j-shell -c "MATCH (m:ATG_Metadata) RETURN m"

# If no metadata, run initial scan first
atg scan --tenant-id contoso-prod
atg backup-metadata --tenant-id contoso-prod
```

---

## Related Documentation

- [Version Tracking Concepts](../concepts/GRAPH_VERSION_TRACKING.md) - Understanding why version tracking exists
- [Handle Version Mismatches How-To](../howto/handle-version-mismatches.md) - Step-by-step workflows
- [Version Tracking Tutorial](../tutorials/version-tracking-tutorial.md) - Complete walkthrough

---

## Quick Command Cheat Sheet

```bash
# Check version status
atg info --tenant-id <TENANT_ID>

# Scan with version check
atg scan --tenant-id <TENANT_ID>

# Backup before rebuild
atg backup-metadata --tenant-id <TENANT_ID>

# Rebuild graph
atg rebuild --tenant-id <TENANT_ID>

# CI/CD: Block on mismatch
atg scan --tenant-id <TENANT_ID> --block-on-mismatch

# CI/CD: Auto-rebuild
atg scan --tenant-id <TENANT_ID> --auto-rebuild

# Suppress warnings (not recommended)
export ATG_SUPPRESS_VERSION_WARNING=true
```

---

**This reference is comprehensive and up-to-date as of ATG v1.8.0.**

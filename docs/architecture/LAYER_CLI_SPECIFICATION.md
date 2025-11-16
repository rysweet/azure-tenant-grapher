# Layer Management CLI Specification

This document specifies the complete CLI interface for layer management in Azure Tenant Grapher.

## Command Structure

All layer commands are under the `atg layer` command group:

```bash
uv run atg layer <subcommand> [options]
```

## Command Reference

### atg layer list

List all layers with summary information.

**Usage:**
```bash
uv run atg layer list [OPTIONS]
```

**Options:**
- `--tenant-id TEXT`: Filter by tenant ID
- `--include-inactive / --active-only`: Show inactive layers (default: true)
- `--type [baseline|scaled|experimental|snapshot]`: Filter by layer type
- `--sort-by [name|created_at|node_count]`: Sort field (default: created_at)
- `--ascending / --descending`: Sort order (default: descending)
- `--format [table|json|yaml]`: Output format (default: table)

**Output (table format):**
```
Layer ID              Name                    Type         Active  Nodes   Created
─────────────────────────────────────────────────────────────────────────────────
default               Default Baseline        baseline     ✓       5,584   2025-11-15 14:23:11
scaled-20251116-1030  Production Scaled v1    scaled               1,245   2025-11-16 10:30:45
experiment-merge      Aggressive Merge Test   experimental         856     2025-11-16 11:15:22
```

**Output (JSON format):**
```json
{
  "layers": [
    {
      "layer_id": "default",
      "name": "Default Baseline",
      "type": "baseline",
      "is_active": true,
      "is_baseline": true,
      "node_count": 5584,
      "relationship_count": 8234,
      "created_at": "2025-11-15T14:23:11Z",
      "created_by": "scan",
      "tenant_id": "tenant-123"
    }
  ],
  "total": 3,
  "active_layer": "default"
}
```

**Exit Codes:**
- `0`: Success
- `1`: Error

**Examples:**
```bash
# List all layers
uv run atg layer list

# List only active layer
uv run atg layer list --active-only

# List scaled layers, sorted by node count
uv run atg layer list --type scaled --sort-by node_count --ascending

# Export to JSON
uv run atg layer list --format json > layers.json
```

---

### atg layer show

Show detailed information about a specific layer.

**Usage:**
```bash
uv run atg layer show <LAYER_ID> [OPTIONS]
```

**Arguments:**
- `LAYER_ID`: Layer identifier (required)

**Options:**
- `--format [text|json|yaml]`: Output format (default: text)
- `--show-stats`: Include detailed statistics
- `--show-lineage`: Show parent/child layers

**Output (text format):**
```
Layer: default
─────────────────────────────────────────────────────────────────

  Name:              Default Baseline
  Description:       1:1 abstraction from initial scan
  Type:              baseline
  Status:            ✓ Active, Protected (baseline)

  Created:           2025-11-15 14:23:11
  Created by:        scan
  Last updated:      2025-11-16 09:45:32

  Tenant ID:         tenant-123
  Subscription IDs:  sub-001, sub-002

  Statistics:
    Nodes:           5,584 resources
    Relationships:   8,234 connections
    Resource types:  47 distinct types

  Tags:              production, baseline

  Lineage:
    Parent:          (none - baseline layer)
    Children:        scaled-20251116-1030, experiment-merge
```

**Exit Codes:**
- `0`: Success
- `1`: Layer not found
- `2`: Error

**Examples:**
```bash
# Show default layer
uv run atg layer show default

# Show with full stats
uv run atg layer show scaled-v1 --show-stats

# Export to JSON
uv run atg layer show default --format json
```

---

### atg layer active

Show or set the active layer.

**Usage:**
```bash
# Show active layer
uv run atg layer active

# Set active layer
uv run atg layer active <LAYER_ID>
```

**Arguments:**
- `LAYER_ID`: Layer to activate (optional)

**Options:**
- `--tenant-id TEXT`: Tenant context (for multi-tenant)
- `--format [text|json]`: Output format

**Output (show):**
```
Active Layer: default
─────────────────────────────────────────
Name:         Default Baseline
Nodes:        5,584
Created:      2025-11-15 14:23:11

All operations will use this layer by default.
```

**Output (set):**
```
✓ Active layer changed: default → scaled-v1

Active Layer: scaled-v1
─────────────────────────────────────────
Name:         Production Scaled v1
Nodes:        1,245
Created:      2025-11-16 10:30:45

Subsequent operations will use this layer.
```

**Exit Codes:**
- `0`: Success
- `1`: Layer not found (when setting)
- `2`: Error

**Examples:**
```bash
# Show current active layer
uv run atg layer active

# Switch to scaled version
uv run atg layer active scaled-v1

# Switch back to baseline
uv run atg layer active default
```

---

### atg layer create

Create a new empty layer.

**Usage:**
```bash
uv run atg layer create <LAYER_ID> [OPTIONS]
```

**Arguments:**
- `LAYER_ID`: Unique layer identifier (required)

**Options:**
- `--name TEXT`: Human-readable name (default: layer_id)
- `--description TEXT`: Layer description
- `--type [baseline|scaled|experimental|snapshot]`: Layer type (default: experimental)
- `--parent-layer TEXT`: Parent layer for lineage
- `--tenant-id TEXT`: Tenant ID
- `--tag TEXT`: Add tag (multiple allowed)
- `--make-active`: Set as active layer
- `--yes`: Skip confirmation

**Output:**
```
Creating new layer: experiment-1
  Name:        Experiment 1
  Type:        experimental
  Parent:      default

✓ Layer created successfully

Layer ID:     experiment-1
Node count:   0 (empty layer)

Use 'atg layer copy' to populate this layer, or run scale operations
with --target-layer experiment-1 to write directly to it.
```

**Exit Codes:**
- `0`: Success
- `1`: Layer already exists
- `2`: Validation error
- `3`: User cancelled

**Examples:**
```bash
# Create experimental layer
uv run atg layer create experiment-1 \
  --name "Experiment 1" \
  --description "Testing aggressive merging" \
  --type experimental \
  --parent-layer default

# Create and activate
uv run atg layer create scaled-v2 \
  --name "Scaled Version 2" \
  --type scaled \
  --make-active

# Quick create (minimal options)
uv run atg layer create test-layer --yes
```

---

### atg layer copy

Copy an entire layer (nodes + relationships).

**Usage:**
```bash
uv run atg layer copy <SOURCE> <TARGET> [OPTIONS]
```

**Arguments:**
- `SOURCE`: Source layer ID (required)
- `TARGET`: Target layer ID (required)

**Options:**
- `--name TEXT`: Name for new layer
- `--description TEXT`: Description for new layer
- `--copy-metadata`: Copy metadata dict from source (default: true)
- `--make-active`: Set new layer as active
- `--yes`: Skip confirmation

**Output:**
```
Copying layer: default → experiment-1

  Source:  default (5,584 nodes)
  Target:  experiment-1

Confirm copy operation? [y/N]: y

Copying nodes...
  ████████████████████████████ 5,584 / 5,584 (100%)

Copying relationships...
  ████████████████████████████ 8,234 / 8,234 (100%)

Creating layer metadata...
✓ Layer copied successfully

Layer:        experiment-1
Nodes:        5,584
Relationships: 8,234
Time:         12.3 seconds
```

**Exit Codes:**
- `0`: Success
- `1`: Source layer not found
- `2`: Target layer already exists
- `3`: User cancelled
- `4`: Copy failed

**Examples:**
```bash
# Copy default to experiment
uv run atg layer copy default experiment-1 \
  --name "Experiment 1" \
  --description "Testing consolidation"

# Copy and activate
uv run atg layer copy scaled-v1 scaled-v2 --make-active

# Quick copy (auto-generate name)
uv run atg layer copy default test-copy --yes
```

---

### atg layer delete

Delete a layer and all its nodes/relationships.

**Usage:**
```bash
uv run atg layer delete <LAYER_ID> [OPTIONS]
```

**Arguments:**
- `LAYER_ID`: Layer to delete (required)

**Options:**
- `--force`: Allow deletion of active/baseline layers
- `--yes`: Skip confirmation
- `--archive PATH`: Archive layer before deletion

**Output:**
```
Deleting layer: experiment-1

  Name:         Experiment 1
  Nodes:        5,584
  Relationships: 8,234
  Status:       Inactive

⚠️  WARNING: This will permanently delete all nodes and relationships
           in this layer. Original nodes are preserved.

Confirm deletion? [y/N]: y

Deleting nodes...
  ████████████████████████████ 5,584 / 5,584 (100%)

Deleting relationships...
  ████████████████████████████ 8,234 / 8,234 (100%)

Deleting metadata...
✓ Layer deleted successfully

Freed:        ~45 MB graph storage
Time:         3.2 seconds
```

**Protected Layer Warning:**
```
Cannot delete layer: default

Reason:  Active baseline layer
Status:  Protected

This layer is marked as active and baseline. To delete:

  1. Switch to another layer:
     uv run atg layer active scaled-v1

  2. Delete with --force flag:
     uv run atg layer delete default --force

⚠️  Force deletion of baseline layer is not recommended.
```

**Exit Codes:**
- `0`: Success
- `1`: Layer not found
- `2`: Layer protected (without --force)
- `3`: User cancelled
- `4`: Deletion failed

**Examples:**
```bash
# Delete experimental layer
uv run atg layer delete experiment-1

# Force delete active layer
uv run atg layer delete default --force --yes

# Archive before deletion
uv run atg layer delete old-layer \
  --archive /backups/old-layer-20251116.json
```

---

### atg layer diff

Compare two layers to find differences.

**Usage:**
```bash
uv run atg layer diff <LAYER_A> <LAYER_B> [OPTIONS]
```

**Arguments:**
- `LAYER_A`: Baseline layer (required)
- `LAYER_B`: Comparison layer (required)

**Options:**
- `--detailed`: Include node IDs in output
- `--properties`: Compare property values
- `--output PATH`: Save report to file
- `--format [text|json|html]`: Output format (default: text)

**Output (text format):**
```
Layer Comparison
═══════════════════════════════════════════════════════════

Baseline:    default (Default Baseline)
Comparison:  scaled-v1 (Production Scaled v1)

Node Differences
─────────────────────────────────────────────────────────
  Added:      12 nodes
  Removed:    4,351 nodes (77.9% reduction)
  Modified:   5 nodes
  Unchanged:  1,233 nodes

Relationship Differences
─────────────────────────────────────────────────────────
  Added:      45 relationships
  Removed:    6,123 relationships
  Modified:   0 relationships
  Unchanged:  2,111 relationships

Summary
─────────────────────────────────────────────────────────
  Total changes:     10,531
  Change percentage: 78.4%
  Impact:            Major topology change

Interpretation:
  This layer shows aggressive consolidation with 78% fewer nodes.
  Review IaC output carefully before deployment.
```

**Output (JSON format):**
```json
{
  "layer_a_id": "default",
  "layer_b_id": "scaled-v1",
  "compared_at": "2025-11-16T12:34:56Z",
  "nodes": {
    "added": 12,
    "removed": 4351,
    "modified": 5,
    "unchanged": 1233
  },
  "relationships": {
    "added": 45,
    "removed": 6123,
    "modified": 0,
    "unchanged": 2111
  },
  "total_changes": 10531,
  "change_percentage": 78.4,
  "impact": "major"
}
```

**Output (detailed mode):**
```
Removed Nodes (4,351):
  - vm-a1b2c3d4 (VirtualMachine: "prod-vm-001")
  - vm-c5d6e7f8 (VirtualMachine: "prod-vm-002")
  - vnet-12345678 (VirtualNetwork: "prod-vnet-02")
  ... (4,348 more)

Added Nodes (12):
  + vm-merged-001 (VirtualMachine: "consolidated-vm-001")
  + vnet-merged-01 (VirtualNetwork: "consolidated-vnet")
  ... (10 more)

Modified Nodes (5):
  ~ subnet-abc123 (Subnet)
    - addressPrefix: "10.0.1.0/24"
    + addressPrefix: "10.0.0.0/16"
  ... (4 more)
```

**Exit Codes:**
- `0`: Success
- `1`: Layer not found
- `2`: Comparison failed

**Examples:**
```bash
# Basic comparison
uv run atg layer diff default scaled-v1

# Detailed comparison with property changes
uv run atg layer diff default scaled-v1 --detailed --properties

# Export to JSON
uv run atg layer diff default scaled-v1 --format json --output diff.json

# Generate HTML report
uv run atg layer diff default scaled-v1 --format html --output report.html
```

---

### atg layer validate

Validate layer integrity and check for issues.

**Usage:**
```bash
uv run atg layer validate <LAYER_ID> [OPTIONS]
```

**Arguments:**
- `LAYER_ID`: Layer to validate (required)

**Options:**
- `--fix`: Attempt automatic fixes
- `--output PATH`: Save report to file
- `--format [text|json]`: Output format (default: text)

**Output (clean layer):**
```
Validating layer: scaled-v1
═══════════════════════════════════════════════════════════

Running integrity checks...

✓ SCAN_SOURCE_NODE links          5,584 / 5,584 (100%)
✓ Layer boundary isolation         No cross-layer relationships
✓ Orphaned relationships           0 found
✓ Node count accuracy              5,584 matches metadata
✓ Relationship count accuracy      8,234 matches metadata
✓ Duplicate constraints            No duplicates found
✓ Original node references         All targets exist

Summary
─────────────────────────────────────────────────────────
Status:        ✓ Valid
Checks passed: 7 / 7
Checks failed: 0
Warnings:      0

This layer is healthy and ready for use.
```

**Output (issues found):**
```
Validating layer: scaled-v1
═══════════════════════════════════════════════════════════

Running integrity checks...

✓ SCAN_SOURCE_NODE links          5,580 / 5,584 (99.9%)
✗ Layer boundary isolation         3 cross-layer relationships found
✓ Orphaned relationships           0 found
✗ Node count accuracy              5,584 actual vs 5,600 metadata
✓ Relationship count accuracy      8,234 matches metadata
✓ Duplicate constraints            No duplicates found
✗ Original node references         2 missing targets

Issues Found
─────────────────────────────────────────────────────────
ERROR: Missing SCAN_SOURCE_NODE links
  - vm-a1b2c3d4 (no link to Original)
  - vm-c5d6e7f8 (no link to Original)
  - subnet-abc123 (no link to Original)
  - vnet-xyz789 (no link to Original)

ERROR: Cross-layer relationships
  - (scaled-v1)vm-a1b2c3d4 -[:USES_SUBNET]-> (default)subnet-123
  - (scaled-v1)vm-c5d6e7f8 -[:USES_SUBNET]-> (default)subnet-456
  - (scaled-v1)nsg-001 -[:APPLIED_TO]-> (default)subnet-789

ERROR: Metadata count mismatch
  - Expected: 5,600 nodes
  - Actual:   5,584 nodes
  - Difference: -16 nodes

ERROR: Missing Original references
  - vm-merged-001 -> azure-id-12345 (Original node not found)
  - vnet-merged-01 -> azure-id-67890 (Original node not found)

Summary
─────────────────────────────────────────────────────────
Status:        ✗ Invalid
Checks passed: 4 / 7
Checks failed: 3
Warnings:      0

Recommendations:
  1. Run with --fix to auto-fix metadata counts
  2. Manually remove cross-layer relationships
  3. Re-scan to restore missing Original nodes

Use: uv run atg layer validate scaled-v1 --fix
```

**Output (with --fix):**
```
Validating layer: scaled-v1 (auto-fix enabled)
═══════════════════════════════════════════════════════════

Running integrity checks...

✓ SCAN_SOURCE_NODE links          5,584 / 5,584 (100%)
✗ Layer boundary isolation         3 cross-layer relationships found
✓ Orphaned relationships           15 found
✗ Node count accuracy              5,584 actual vs 5,600 metadata

Auto-fixing issues...

  Removing orphaned relationships... 15 deleted
  Updating metadata node count... 5,600 → 5,584
  (Cannot auto-fix: cross-layer relationships require manual review)

Re-validating...

✓ Orphaned relationships           0 found
✓ Node count accuracy              5,584 matches metadata

Summary
─────────────────────────────────────────────────────────
Status:        ⚠️  Issues remaining
Checks passed: 6 / 7
Checks failed: 1 (requires manual fix)
Auto-fixed:    2 issues

Remaining Issues:
  - 3 cross-layer relationships (manual review required)
```

**Exit Codes:**
- `0`: Layer valid
- `1`: Layer not found
- `2`: Validation failed (issues found)
- `3`: Validation error

**Examples:**
```bash
# Validate layer
uv run atg layer validate scaled-v1

# Validate and auto-fix
uv run atg layer validate scaled-v1 --fix

# Export report
uv run atg layer validate default --format json --output validation.json
```

---

### atg layer refresh-stats

Refresh layer metadata statistics.

**Usage:**
```bash
uv run atg layer refresh-stats <LAYER_ID> [OPTIONS]
```

**Arguments:**
- `LAYER_ID`: Layer to refresh (required)

**Options:**
- `--format [text|json]`: Output format

**Output:**
```
Refreshing layer statistics: scaled-v1

Counting nodes...
  ████████████████████████████ 5,584 / 5,584 (100%)

Counting relationships...
  ████████████████████████████ 8,234 / 8,234 (100%)

Updating metadata...
✓ Statistics refreshed

Previous Values          Current Values
────────────────────────────────────────────
Nodes:        5,600  →  5,584 (-16)
Relationships: 8,234  →  8,234 (no change)

Updated:      2025-11-16 12:45:33
```

**Exit Codes:**
- `0`: Success
- `1`: Layer not found
- `2`: Refresh failed

**Examples:**
```bash
# Refresh stats
uv run atg layer refresh-stats scaled-v1

# JSON output
uv run atg layer refresh-stats default --format json
```

---

### atg layer archive

Export layer to JSON archive file.

**Usage:**
```bash
uv run atg layer archive <LAYER_ID> <OUTPUT_PATH> [OPTIONS]
```

**Arguments:**
- `LAYER_ID`: Layer to archive (required)
- `OUTPUT_PATH`: File path for archive (required)

**Options:**
- `--include-original`: Include Original nodes in archive
- `--compress`: Compress archive with gzip
- `--yes`: Skip confirmation

**Output:**
```
Archiving layer: scaled-v1
═══════════════════════════════════════════════════════════

Output: /backups/scaled-v1-20251116.json

Layer:        scaled-v1 (Production Scaled v1)
Nodes:        5,584
Relationships: 8,234
Include Original: No

Confirm archive? [y/N]: y

Exporting layer metadata...
Exporting nodes...
  ████████████████████████████ 5,584 / 5,584 (100%)
Exporting relationships...
  ████████████████████████████ 8,234 / 8,234 (100%)

Writing archive...
✓ Layer archived successfully

Archive:      /backups/scaled-v1-20251116.json
Size:         12.3 MB
Time:         4.5 seconds

You can now safely delete this layer if needed:
  uv run atg layer delete scaled-v1
```

**Exit Codes:**
- `0`: Success
- `1`: Layer not found
- `2`: File write error
- `3`: User cancelled

**Examples:**
```bash
# Archive layer
uv run atg layer archive scaled-v1 /backups/scaled-v1.json

# Archive with compression
uv run atg layer archive scaled-v1 /backups/scaled-v1.json.gz --compress

# Archive with Original nodes
uv run atg layer archive default /backups/full-backup.json --include-original
```

---

### atg layer restore

Restore layer from JSON archive.

**Usage:**
```bash
uv run atg layer restore <ARCHIVE_PATH> [OPTIONS]
```

**Arguments:**
- `ARCHIVE_PATH`: Path to archive file (required)

**Options:**
- `--layer-id TEXT`: Override layer ID from archive
- `--make-active`: Set as active layer after restore
- `--yes`: Skip confirmation

**Output:**
```
Restoring layer from archive
═══════════════════════════════════════════════════════════

Archive:      /backups/scaled-v1-20251116.json
Layer:        scaled-v1 (Production Scaled v1)
Nodes:        5,584
Relationships: 8,234
Created:      2025-11-16 10:30:45

⚠️  This will create layer 'scaled-v1' in the graph.

Confirm restore? [y/N]: y

Creating layer metadata...
Importing nodes...
  ████████████████████████████ 5,584 / 5,584 (100%)
Importing relationships...
  ████████████████████████████ 8,234 / 8,234 (100%)

Validating layer...
✓ Layer restored successfully

Layer:        scaled-v1
Nodes:        5,584
Relationships: 8,234
Time:         8.7 seconds

Use: uv run atg layer active scaled-v1
```

**Exit Codes:**
- `0`: Success
- `1`: Archive not found
- `2`: Archive format invalid
- `3`: Layer already exists
- `4`: User cancelled
- `5`: Restore failed

**Examples:**
```bash
# Restore layer
uv run atg layer restore /backups/scaled-v1.json

# Restore with new ID
uv run atg layer restore /backups/scaled-v1.json --layer-id scaled-v2

# Restore and activate
uv run atg layer restore /backups/scaled-v1.json --make-active
```

---

## Enhanced Scale Operations Commands

All scale operations now support layer parameters:

### atg scale merge-vnets

**New Options:**
- `--source-layer TEXT`: Layer to read from (default: active)
- `--target-layer TEXT`: Layer to write to (default: auto-generate)
- `--make-active`: Set new layer as active

**Usage:**
```bash
uv run atg scale merge-vnets <VNET_ID> <VNET_ID> [OPTIONS]
```

**Examples:**
```bash
# Merge VNets (creates new layer)
uv run atg scale merge-vnets vnet-1 vnet-2

# Merge with explicit layers
uv run atg scale merge-vnets vnet-1 vnet-2 \
  --source-layer default \
  --target-layer scaled-v1 \
  --make-active

# Merge from experimental layer
uv run atg scale merge-vnets vnet-1 vnet-2 \
  --source-layer experiment-1 \
  --target-layer experiment-2
```

### atg scale merge-subnets

Same layer options as merge-vnets.

### atg scale split-vnet

Same layer options as merge-vnets.

### atg scale consolidate-vms

Same layer options as merge-vnets.

---

## Enhanced IaC Generation Command

### atg generate-iac

**New Options:**
- `--layer TEXT`: Layer to generate from (default: active)

**Usage:**
```bash
uv run atg generate-iac [OPTIONS]
```

**Examples:**
```bash
# Generate from active layer
uv run atg generate-iac

# Generate from specific layer
uv run atg generate-iac --layer scaled-v1

# Compare IaC from different layers
uv run atg generate-iac --layer default --output default-iac/
uv run atg generate-iac --layer scaled-v1 --output scaled-iac/
diff -r default-iac/ scaled-iac/
```

---

## Enhanced Scan Command

### atg scan

**Behavior Changes:**
- Creates "default" layer if it doesn't exist
- Writes all resources to "default" layer
- Sets "default" as active and baseline

**No new options** - backward compatible

**Usage:**
```bash
uv run atg scan --tenant-id <TENANT_ID>
```

---

## Global Options

All layer commands support:

- `--debug`: Enable debug output
- `--quiet`: Suppress non-error output
- `--no-color`: Disable colored output
- `--help`: Show command help

---

## Error Handling

### Exit Codes

- `0`: Success
- `1`: Layer not found / resource not found
- `2`: Validation error / constraint violation
- `3`: User cancelled operation
- `4`: Operation failed
- `5`: Permission denied / protected resource

### Error Messages

Clear, actionable error messages with suggested fixes:

```
Error: Layer not found: scaled-v1

Available layers:
  - default (active)
  - experiment-1

Did you mean one of these?
  - scaled-v2
  - scaled-20251115-1030

Create new layer:
  uv run atg layer create scaled-v1
```

---

## Output Formats

### Table Format (default)

- Human-readable
- Colored output (when terminal supports)
- Aligned columns
- Summary statistics

### JSON Format

- Machine-readable
- Complete data
- Suitable for scripting
- Schema-stable

### YAML Format

- Human-readable
- Complete data
- Good for configuration

### HTML Format (for reports)

- Rich formatting
- Embedded visualizations
- Suitable for sharing

---

## Interactive Features

### Confirmation Prompts

Destructive operations require confirmation:

```
⚠️  This will permanently delete layer 'experiment-1' (5,584 nodes)

Confirm? [y/N]:
```

Skip with `--yes` flag.

### Progress Bars

Long operations show progress:

```
Copying nodes...
  ████████████████████████████ 5,584 / 5,584 (100%) | ETA: 0s
```

### Smart Suggestions

CLI suggests corrections:

```
Error: Layer not found: default

Did you mean: defaults

Available layers: default, scaled-v1, experiment-1
```

---

## Bash Completion

Install completion for layer commands:

```bash
# Generate completion script
uv run atg --install-completion

# Or manually:
eval "$(uv run atg --show-completion)"
```

Provides:
- Command completion
- Option completion
- Layer ID completion (dynamic)
- File path completion

---

## Examples: Common Workflows

### Workflow 1: Create and Test Experimental Layer

```bash
# 1. Copy baseline to experiment
uv run atg layer copy default experiment-aggressive \
  --name "Aggressive Consolidation" \
  --description "Testing 10:1 VM consolidation"

# 2. Apply scale operations
uv run atg scale merge-vnets vnet-1 vnet-2 vnet-3 \
  --source-layer experiment-aggressive \
  --target-layer experiment-aggressive-merged

# 3. Validate
uv run atg layer validate experiment-aggressive-merged

# 4. Compare with baseline
uv run atg layer diff default experiment-aggressive-merged --detailed

# 5. Generate IaC to preview changes
uv run atg generate-iac --layer experiment-aggressive-merged --output /tmp/iac

# 6. If satisfied, activate
uv run atg layer active experiment-aggressive-merged

# 7. Clean up intermediate layers
uv run atg layer delete experiment-aggressive --yes
```

### Workflow 2: A/B Test Two Scaling Strategies

```bash
# Strategy A: Merge VNets first
uv run atg layer copy default strategy-a
uv run atg scale merge-vnets vnet-1 vnet-2 \
  --source-layer strategy-a \
  --target-layer strategy-a

# Strategy B: Consolidate VMs first
uv run atg layer copy default strategy-b
uv run atg scale consolidate-vms vm-1 vm-2 vm-3 \
  --source-layer strategy-b \
  --target-layer strategy-b

# Compare strategies
uv run atg layer diff default strategy-a > strategy-a-diff.txt
uv run atg layer diff default strategy-b > strategy-b-diff.txt

# Review both outputs
cat strategy-a-diff.txt
cat strategy-b-diff.txt

# Choose winner
uv run atg layer active strategy-a

# Archive alternative
uv run atg layer archive strategy-b /backups/strategy-b.json
uv run atg layer delete strategy-b
```

### Workflow 3: Daily Snapshot Workflow

```bash
# Daily backup script
DATE=$(date +%Y%m%d)

# Create snapshot
uv run atg layer copy default snapshot-$DATE \
  --name "Daily Snapshot $DATE" \
  --type snapshot \
  --yes

# Archive and compress
uv run atg layer archive snapshot-$DATE \
  /backups/daily/snapshot-$DATE.json.gz \
  --compress \
  --yes

# Delete old snapshots (keep 7 days)
OLDDATE=$(date -d '7 days ago' +%Y%m%d)
uv run atg layer delete snapshot-$OLDDATE --yes || true

# Verify archive
ls -lh /backups/daily/snapshot-$DATE.json.gz
```

---

## Implementation Notes

### CLI Framework

Use Click framework for Python CLI:

```python
import click

@click.group()
def layer():
    """Layer management commands."""
    pass

@layer.command()
@click.argument('layer_id')
@click.option('--format', type=click.Choice(['text', 'json', 'yaml']), default='text')
async def show(layer_id, format):
    """Show detailed information about a layer."""
    # Implementation...
```

### Output Formatting

Use Rich library for beautiful CLI output:

```python
from rich.console import Console
from rich.table import Table

console = Console()

table = Table(title="Layers")
table.add_column("Layer ID", style="cyan")
table.add_column("Name", style="green")
table.add_column("Active", style="yellow")

# ... add rows ...

console.print(table)
```

### Error Handling

Consistent error handling pattern:

```python
try:
    layer = await layer_service.get_layer(layer_id)
    if not layer:
        raise LayerNotFoundError(layer_id)
except LayerNotFoundError as e:
    console.print(f"[red]Error: {e}[/red]")
    console.print(f"[dim]Available layers: {', '.join(available_layers)}[/dim]")
    sys.exit(1)
```

---

**This CLI specification is complete and ready for implementation.**

# Layer Management Quick Start Guide

This guide provides quick examples for managing graph layers in Azure Tenant Grapher.

## What are Layers?

Layers are separate projections of your Azure tenant graph. They enable:
- **Non-destructive experimentation** - Test scale operations without affecting original data
- **A/B testing** - Compare different consolidation strategies
- **Version control** - Maintain multiple versions of your infrastructure
- **Safe rollback** - Archive and restore previous states

## Quick Start

### View Available Layers

```bash
# List all layers
uv run atg layer list

# List with JSON output
uv run atg layer list --format json
```

### Show Active Layer

```bash
# See which layer is currently active
uv run atg layer active
```

### Create a New Layer

```bash
# Create an empty experimental layer
uv run atg layer create my-experiment \
  --name "My First Experiment" \
  --description "Testing VNet consolidation" \
  --type experimental

# Create and make active immediately
uv run atg layer create test-layer --make-active --yes
```

### Copy a Layer

```bash
# Copy default layer to experiment with it
uv run atg layer copy default my-experiment

# Copy and make active
uv run atg layer copy default experiment-2 --make-active
```

### Switch Active Layer

```bash
# Change to a different layer
uv run atg layer active my-experiment

# All subsequent operations will use this layer
```

### View Layer Details

```bash
# Show detailed information
uv run atg layer show my-experiment

# Show with parent/child relationships
uv run atg layer show my-experiment --show-lineage

# JSON format for scripting
uv run atg layer show my-experiment --format json
```

### Compare Layers

```bash
# Compare two layers
uv run atg layer diff default my-experiment

# Detailed comparison with node IDs
uv run atg layer diff default my-experiment --detailed

# Save comparison to file
uv run atg layer diff default my-experiment --output diff.txt
```

### Validate Layer Integrity

```bash
# Check layer health
uv run atg layer validate my-experiment

# Auto-fix issues
uv run atg layer validate my-experiment --fix
```

### Archive and Restore

```bash
# Archive a layer
uv run atg layer archive my-experiment backup.json

# Restore from archive
uv run atg layer restore backup.json

# Restore with different ID
uv run atg layer restore backup.json --layer-id experiment-2
```

### Delete a Layer

```bash
# Delete layer (with confirmation)
uv run atg layer delete my-experiment

# Delete without confirmation
uv run atg layer delete my-experiment --yes

# Archive before deletion
uv run atg layer delete my-experiment --archive backup.json
```

## Common Workflows

### Workflow 1: Test Scale Operation

```bash
# 1. Copy baseline to experiment
uv run atg layer copy default test-consolidation

# 2. Perform scale operation on experimental layer
# (Scale operations would target the layer)

# 3. Compare results
uv run atg layer diff default test-consolidation --detailed

# 4. If satisfied, make it active
uv run atg layer active test-consolidation

# 5. Clean up
uv run atg layer delete test-consolidation --archive backup.json
```

### Workflow 2: A/B Testing

```bash
# Create two strategies
uv run atg layer copy default strategy-aggressive --yes
uv run atg layer copy default strategy-conservative --yes

# Apply different scale operations to each
# ...

# Compare both to baseline
uv run atg layer diff default strategy-aggressive
uv run atg layer diff default strategy-conservative

# Choose winner
uv run atg layer active strategy-aggressive

# Archive alternative
uv run atg layer archive strategy-conservative backup.json
uv run atg layer delete strategy-conservative --yes
```

### Workflow 3: Daily Snapshots

```bash
#!/bin/bash
# Daily backup script

DATE=$(date +%Y%m%d)

# Create snapshot
uv run atg layer copy default snapshot-$DATE \
  --name "Daily Snapshot $DATE" \
  --type snapshot \
  --yes

# Archive and compress
uv run atg layer archive snapshot-$DATE \
  /backups/snapshot-$DATE.json \
  --yes

# Delete old snapshots (keep 7 days)
OLDDATE=$(date -d '7 days ago' +%Y%m%d)
uv run atg layer delete snapshot-$OLDDATE --yes || true
```

## Tips and Best Practices

### Layer Naming Conventions

```bash
# Use descriptive names
uv run atg layer create prod-consolidation-v1  # Good
uv run atg layer create test123                # Avoid

# Include dates for time-series
uv run atg layer create snapshot-20251116
uv run atg layer create experiment-20251116-1030

# Use prefixes for organization
uv run atg layer create prod-scaled-001
uv run atg layer create dev-experiment-001
uv run atg layer create test-aggressive-merge
```

### Layer Types

```bash
# baseline: Protected, source of truth
uv run atg layer create source --type baseline

# scaled: Production-ready consolidated version
uv run atg layer create prod-v1 --type scaled

# experimental: Temporary testing
uv run atg layer create test-merge --type experimental

# snapshot: Point-in-time backup
uv run atg layer create backup-20251116 --type snapshot
```

### Validation

```bash
# Always validate after major operations
uv run atg layer validate my-layer

# Use --fix for automatic repairs
uv run atg layer validate my-layer --fix

# Save validation reports
uv run atg layer validate my-layer --format json --output report.json
```

### Archiving

```bash
# Regular backups
uv run atg layer archive default backup-$(date +%Y%m%d).json

# Before risky operations
uv run atg layer archive production pre-migration-backup.json

# Before deletion
uv run atg layer delete old-layer --archive backup.json
```

## Output Formats

### Table Format (Default)
Best for human readability:
```bash
uv run atg layer list
```

### JSON Format
Best for scripting and automation:
```bash
uv run atg layer list --format json | jq '.layers[].layer_id'
```

### YAML Format
Best for configuration:
```bash
uv run atg layer show default --format yaml > layer-config.yaml
```

## Scripting Examples

### Get Layer Node Count

```bash
#!/bin/bash
NODE_COUNT=$(uv run atg layer show default --format json | jq '.node_count')
echo "Layer has $NODE_COUNT nodes"
```

### List Experimental Layers

```bash
#!/bin/bash
uv run atg layer list --type experimental --format json | \
  jq -r '.layers[].layer_id'
```

### Validate All Layers

```bash
#!/bin/bash
LAYERS=$(uv run atg layer list --format json | jq -r '.layers[].layer_id')

for layer in $LAYERS; do
  echo "Validating $layer..."
  uv run atg layer validate $layer --fix
done
```

## Troubleshooting

### Layer Not Found
```bash
# List available layers
uv run atg layer list

# CLI provides suggestions
uv run atg layer show typo-layer
# Error: Layer not found: typo-layer
# Available layers: default, test-layer, experiment-1
# Did you mean one of these?
#   - test-layer
```

### Cannot Delete Active Layer
```bash
# Switch to another layer first
uv run atg layer active default
uv run atg layer delete old-layer

# Or force deletion
uv run atg layer delete active-layer --force
```

### Validation Failures
```bash
# Run with --fix to auto-repair
uv run atg layer validate my-layer --fix

# Review detailed report
uv run atg layer validate my-layer --format json --output report.json
```

### Outdated Statistics
```bash
# Refresh layer metadata
uv run atg layer refresh-stats my-layer
```

## Next Steps

- Read the [full specification](../architecture/LAYER_CLI_SPECIFICATION.md)
- Learn about [scale operations](../SCALE_OPERATIONS.md)
- Understand [dual-graph architecture](../NEO4J_SCHEMA_REFERENCE.md)

## Need Help?

```bash
# Command help
uv run atg layer --help
uv run atg layer <command> --help

# Examples
uv run atg layer list --help
uv run atg layer create --help
uv run atg layer diff --help
```

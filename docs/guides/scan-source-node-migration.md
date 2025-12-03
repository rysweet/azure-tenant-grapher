# SCAN_SOURCE_NODE Migration Guide

This guide helps ye migrate layers and archives created BEFORE the Bug #117 fix (Issue #570) that excluded SCAN_SOURCE_NODE relationships.

## Problem Overview

**Before Bug #117 fix** (versions < Issue #570):
- Layer copy operations excluded SCAN_SOURCE_NODE relationships
- Layer archives excluded SCAN_SOURCE_NODE relationships
- IaC generation couldn't find original Azure IDs
- Smart import validation produced 900+ false positives

**After Bug #117 fix** (versions >= Issue #570):
- Layer operations preserve SCAN_SOURCE_NODE relationships
- Archives include SCAN_SOURCE_NODE relationships (v2.0 format)
- IaC generation works reliably
- Smart import validation accurate

## Who Needs to Migrate

Ye need to migrate if:

1. **Copied layers before the fix** - Layers copied from scanned data lack SCAN_SOURCE_NODE
2. **Old archives** - Archives created before the fix (v1.0 format)
3. **IaC generation fails** - Seeing NULL fer `original_id` in generated IaC
4. **Smart import errors** - Getting false positives about "resources not found in target"

## Detection: Do I Need to Migrate?

### Check Layer for Missing SCAN_SOURCE_NODE

Run this Cypher query to check a layer:

```cypher
// Count abstracted resources
MATCH (r:Resource)
WHERE r.layer_id = "your-layer-id"
  AND NOT r:Original
RETURN count(r) as total_resources;

// Count abstracted resources WITH SCAN_SOURCE_NODE
MATCH (r:Resource)-[:SCAN_SOURCE_NODE]->(orig:Resource:Original)
WHERE r.layer_id = "your-layer-id"
RETURN count(r) as resources_with_source_node;

// If resources_with_source_node == 0, migration needed!
```

### Check Archive Version

```python
import json

with open("your-archive.json") as f:
    archive = json.load(f)
    version = archive.get("version", "1.0")

    if version == "1.0":
        print("Old archive format - migration needed")

        # Check if SCAN_SOURCE_NODE relationships exist
        scan_source_rels = [
            r for r in archive.get("relationships", [])
            if r.get("type") == "SCAN_SOURCE_NODE"
        ]
        print(f"SCAN_SOURCE_NODE relationships: {len(scan_source_rels)}")

        if len(scan_source_rels) == 0:
            print("CRITICAL: Archive missing SCAN_SOURCE_NODE!")
    else:
        print(f"Archive version {version} - should include SCAN_SOURCE_NODE")
```

## Migration Paths

### Path 1: Re-Copy from Original Scan Layer (Recommended)

If the original scanned layer still exists, re-copy it with the fixed code:

```python
from src.services.layer_management_service import LayerManagementService

service = LayerManagementService(session_manager)

# Re-copy the layer with SCAN_SOURCE_NODE preservation
await service.copy_layer(
    source_layer_id="original-scan-layer",
    target_layer_id="fixed-copy-layer",
    name="Re-copied with SCAN_SOURCE_NODE",
    description="Includes SCAN_SOURCE_NODE for IaC generation"
)

# Verify SCAN_SOURCE_NODE exists
stats = await service.get_layer_stats("fixed-copy-layer")
print(f"Layer has {stats.total_resources} resources")

# Manually verify with Cypher:
# MATCH (r:Resource {layer_id: "fixed-copy-layer"})-[:SCAN_SOURCE_NODE]->(orig)
# RETURN count(r)
```

### Path 2: Re-Archive from Original Scan Layer

If ye need a fresh archive with SCAN_SOURCE_NODE:

```python
# Create new archive with v2.0 format
output_path = await service.archive_layer(
    layer_id="original-scan-layer",
    output_path="./archives/layer-v2.0.json",
    include_original=False  # Original nodes aren't copied
)

print(f"Created v2.0 archive: {output_path}")

# Verify archive includes SCAN_SOURCE_NODE
with open(output_path) as f:
    archive = json.load(f)
    scan_source_count = sum(
        1 for r in archive["relationships"]
        if r["type"] == "SCAN_SOURCE_NODE"
    )
    print(f"SCAN_SOURCE_NODE relationships: {scan_source_count}")
```

### Path 3: Manual SCAN_SOURCE_NODE Reconstruction (Advanced)

If the original scan layer was deleted, ye can manually reconstruct SCAN_SOURCE_NODE relationships:

```cypher
// WARNING: Only run if you understand the dual-graph architecture!
// This assumes Original nodes still exist in the base graph.

MATCH (abstracted:Resource)
WHERE abstracted.layer_id = "your-layer-id"
  AND NOT abstracted:Original
  AND NOT EXISTS {
    MATCH (abstracted)-[:SCAN_SOURCE_NODE]->(:Resource:Original)
  }
WITH abstracted
MATCH (original:Resource:Original)
WHERE original.id = abstracted.original_id  // Must have stored original_id!
  OR original.id = abstracted.id  // Or try matching by ID
CREATE (abstracted)-[:SCAN_SOURCE_NODE]->(original)
RETURN count(*) as created_relationships;
```

**Caveats for Path 3**:
- Only works if `original_id` was stored in abstracted nodes
- Only works if Original nodes still exist in base graph
- High risk of creating incorrect mappings
- **Not recommended** unless Path 1 and Path 2 are impossible

## Verification After Migration

After migrating, verify the fix worked:

### 1. Check SCAN_SOURCE_NODE Exists

```cypher
MATCH (r:Resource {layer_id: "migrated-layer"})-[:SCAN_SOURCE_NODE]->(orig:Resource:Original)
RETURN count(r) as resources_with_scan_source_node,
       count(DISTINCT r) as total_resources;

// Should see resources_with_scan_source_node > 0
```

### 2. Test IaC Generation

```bash
# Generate IaC and check for original_id
uv run python -m src.iac.cli export \
  --layer-id migrated-layer \
  --output-dir ./iac-test

# Check generated Terraform
grep -r "original_id" ./iac-test/

# Should see original Azure IDs in comments or metadata
```

### 3. Test Smart Import Validation

```python
from src.services.smart_import_service import SmartImportService

service = SmartImportService(session_manager)

# Run smart import comparison
result = await service.compare_with_tenant(
    layer_id="migrated-layer",
    tenant_id="target-tenant-id"
)

print(f"False positives: {result.false_positives}")
# Should be < 10, not 900+!
```

## Archive Format Compatibility

### v1.0 Archives (Old Format)

```json
{
  "metadata": {...},
  "nodes": [...],
  "relationships": [
    // Missing SCAN_SOURCE_NODE relationships!
  ]
}
```

**Compatibility**: System detects missing `version` field, logs warning, restores what's available.

### v2.0 Archives (New Format)

```json
{
  "version": "2.0",
  "metadata": {...},
  "nodes": [...],
  "relationships": [
    {
      "source": "vm-abc123",
      "target": "/subscriptions/.../virtualMachines/my-vm",
      "type": "SCAN_SOURCE_NODE",
      "properties": {}
    },
    // ... other relationships
  ]
}
```

**Compatibility**: Fully supported, includes all relationships needed fer IaC generation.

## Troubleshooting

### "No SCAN_SOURCE_NODE found after migration"

**Cause**: Original nodes were deleted from base graph.

**Solution**:
1. Re-scan the source tenant to recreate Original nodes
2. Then re-copy the layer

### "IaC generation still returns NULL fer original_id"

**Cause**: Query might be usin' wrong node type.

**Debug**:
```cypher
// Check both abstracted and Original nodes
MATCH (r:Resource)
WHERE r.layer_id = "your-layer-id"
OPTIONAL MATCH (r)-[:SCAN_SOURCE_NODE]->(orig:Resource:Original)
RETURN r.id, r:Original as is_original, orig.id as original_id
LIMIT 10;
```

### "Archive restore creates duplicate nodes"

**Cause**: Layer already exists in database.

**Solution**:
```python
# Delete old layer first
await service.delete_layer("layer-to-restore")

# Then restore
await service.restore_layer("archive.json", "layer-to-restore")
```

## FAQ

**Q: Can I use old archives with new code?**

A: Aye, but they won't have SCAN_SOURCE_NODE. Ye'll need to re-scan and re-archive fer full functionality.

**Q: Will new archives work with old code?**

A: Aye, backward compatible. Old code will restore all nodes and relationships, just won't use SCAN_SOURCE_NODE.

**Q: Do I need to migrate ALL layers?**

A: Only layers used fer IaC generation or smart import validation. Experimental layers not used fer deployment can skip migration.

**Q: How long does re-copying take?**

A: Depends on layer size. For 3,500 resources: ~2-5 minutes.

## Related Documentation

- [SCAN_SOURCE_NODE Relationships](../architecture/scan-source-node-relationships.md) - Technical details
- [Smart Import Bug Fixes](../smart-import-bug-fixes.md) - Bug #117 context
- [Dual-Graph Architecture](../DUAL_GRAPH_SCHEMA.md) - Architecture overview

---

**Last Updated**: 2025-12-03
**Status**: Post-fix migration guide
**Applies to**: Systems with layers/archives created before Issue #570

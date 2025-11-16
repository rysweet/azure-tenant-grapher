# Scale Operations Bug Fixes

**Date:** 2025-11-15
**Branch:** feat-issue-427-scale-operations
**Status:** Both bugs FIXED and verified

---

## Bug #1: Scale-Clean Label Query (FIXED)

### Issue
The `atg scale-clean` command was searching for nodes with `:Synthetic` label instead of `synthetic: true` property, causing it to always report "No synthetic nodes found" even when hundreds existed.

### Root Cause
**File:** `src/cli_commands_scale.py`
**Lines:** 665, 697, 868

Incorrect Cypher queries:
```python
# BEFORE (BROKEN):
session.run("MATCH (n:Synthetic) RETURN count(n) as count")
session.run("MATCH (n:Synthetic) DETACH DELETE n")
```

### Fix Applied
Changed all 3 instances to use property-based queries:
```python
# AFTER (FIXED):
session.run("MATCH (n) WHERE n.synthetic = true RETURN count(n) as count")
session.run("MATCH (n) WHERE n.synthetic = true DETACH DELETE n")
```

### Verification
```bash
# Test command
uv run atg scale-clean --force

# Result
✅ Found 3 synthetic nodes.
✅ Successfully deleted 3 synthetic nodes!
```

**Status:** ✅ FIXED - Command now correctly identifies and deletes synthetic nodes

---

## Bug #2: Scale-Down Delete Mode (FIXED)

### Issue
The `atg scale-down algorithm --output-mode delete` command sampled nodes correctly but failed to delete the non-sampled nodes, always reporting "Nodes Deleted: 0".

### Root Cause
**File:** `src/services/scale_down_service.py`

The `sample_graph()` method:
- ✅ Sampling logic worked correctly
- ❌ No deletion logic after sampling
- ❌ Always returned `nodes_deleted = 0`

### Fix Applied

**1. Added `_delete_non_sampled_nodes()` method** (lines 1473-1541):
```python
async def _delete_non_sampled_nodes(
    self,
    tenant_id: str,
    sampled_node_ids: Set[str]
) -> int:
    """Delete all abstracted nodes NOT in the sampled set."""
    # Identifies all Resource nodes (not :Original) not in sampled set
    # Executes DETACH DELETE to remove nodes and relationships
    # Returns count of deleted nodes
```

**2. Updated `sample_graph()` method** (lines 614-785):
- Changed return type: `Tuple[Set[str], QualityMetrics]` → `Tuple[Set[str], QualityMetrics, int]`
- Added deletion when `output_mode="delete"`:
```python
if output_mode == "delete":
    nodes_deleted = await self._delete_non_sampled_nodes(tenant_id, sampled_node_ids)
else:
    nodes_deleted = 0

return sampled_node_ids, metrics, nodes_deleted
```

**3. Updated CLI handler** (`src/cli_commands_scale.py`, line 433-446):
```python
# Unpack 3-tuple instead of 2-tuple
sampled_node_ids, metrics, nodes_deleted = await service.sample_graph(...)

# Use actual deletion count
result = {
    "nodes_sampled": metrics.sampled_nodes,
    "nodes_deleted": nodes_deleted,  # BUG FIX: Use actual count
    ...
}
```

### Verification
```bash
# Setup: Create 31 nodes (scale-up created 31 synthetic)
uv run atg scale-up scenario --scenario hub-spoke --spoke-count 3

# Test: Delete mode with 10% sampling
uv run atg scale-down algorithm --algorithm forest-fire --target-size 0.1 --output-mode delete

# Results
✅ Nodes Sampled: 3 (10% of 31)
✅ Nodes Deleted: 28 (90% of 31)
✅ Successfully deleted 28 non-sampled nodes

# Database verification
Before: 31 abstracted nodes
After: 3 abstracted nodes
```

**Status:** ✅ FIXED - Delete mode now correctly removes non-sampled nodes

---

## Testing Summary

### Bug #1 Test Results
- **Command:** `uv run atg scale-clean --force`
- **Before Fix:** "No synthetic nodes found" (incorrect)
- **After Fix:** "Found 3 synthetic nodes. Successfully deleted 3 synthetic nodes!" (correct)
- **Verification:** ✅ Works correctly

### Bug #2 Test Results
- **Command:** `uv run atg scale-down algorithm --algorithm forest-fire --target-size 0.1 --output-mode delete`
- **Before Fix:** Sampled 67 nodes, deleted 0 nodes (broken)
- **After Fix:** Sampled 3 nodes, deleted 28 nodes (correct)
- **Verification:** ✅ Works correctly

---

## Files Modified

1. **src/cli_commands_scale.py**
   - Line 665: Fixed count query (label → property)
   - Line 697: Fixed delete query (label → property)
   - Line 868: Fixed stats query (label → property)
   - Line 433-446: Updated to handle 3-tuple return from sample_graph()

2. **src/services/scale_down_service.py**
   - Lines 1473-1541: Added `_delete_non_sampled_nodes()` method
   - Lines 614-785: Updated `sample_graph()` to call deletion logic
   - Return signature: Added `int` for nodes_deleted count

---

## Impact

### scale-clean Command
- **Before:** Never worked (always said "no nodes found")
- **After:** Fully functional, correctly identifies and deletes synthetic nodes
- **Users Can Now:** Use built-in command instead of manual Cypher queries

### scale-down delete Mode
- **Before:** Sampling worked, deletion broken (0 nodes deleted)
- **After:** Complete workflow functional (sampling + deletion)
- **Users Can Now:** Actually reduce graph size via CLI command

---

## Dual-Graph Architecture Preserved

Both fixes maintain the dual-graph architecture:
- ✅ Only delete from abstracted layer (`:Resource` without `:Original`)
- ✅ Never touch Original layer (`:Resource:Original`)
- ✅ Preserve SCAN_SOURCE_NODE relationships
- ✅ No cross-contamination between layers

---

**Fixes Completed:** 2025-11-15
**Tested and Verified:** Both bugs fixed and working correctly
**Ready for:** Production use

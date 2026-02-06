# Investigation: rare_boost_factor Counterintuitive Behavior

**Date**: 2026-02-04
**Investigator**: Claude (ultrathink workflow)
**Status**: ✅ ROOT CAUSE IDENTIFIED

## Problem Statement

The notebook `notebooks/architecture_based_replication.ipynb` shows counterintuitive behavior where **higher `rare_boost_factor` values result in LESS coverage**:

- **Baseline (rare_boost_factor=1.0)**: 85/91 types (93.4%)
- **Best (rare_boost_factor=5.0)**: 84/91 types (92.3%)

This is unexpected because `rare_boost_factor` is designed to BOOST rare type inclusion, not reduce it.

## Investigation Summary

### Cell 15 Output (Actual Results)

```
📊 Coverage Improvement:
   Baseline: 85/91 types (93.4%)
   Best:     84/91 types (92.3%)
   Gain:     -1 types (-1.2% relative improvement)
```

### Cell 18 Output (Distribution Fidelity)

```
📊 Architecture Distribution Statistics:

Baseline (rare_boost_factor=1.0):
   Average deviation: 1.41%
   Maximum deviation: 3.08%
   Patterns within ±5%: 11/11 (100.0%)

Best (rare_boost_factor=5.0):
   Average deviation: 2.14%
   Maximum deviation: 6.90%
   Patterns within ±5%: 10/11 (90.9%)

⚠️  Regression: 0.73% worse distribution fidelity with upweighting
```

**Both metrics show regression with higher rare_boost_factor!**

## Root Cause Analysis

### The Problem: Per-Pattern Isolation

When `rare_boost_factor > 1.0`, the selection process operates in **per-pattern isolation** without cross-pattern coordination:

#### Code Flow

1. **`_select_instances_proportionally`** (line 1854): Loops over each pattern
2. For each pattern, calls **`_select_with_hybrid_scoring`** (line 1879)
3. Inside `_select_with_hybrid_scoring`:
   - Calls `_sample_for_coverage` with `target_type_counts=None` (line 2100)
   - Each pattern starts with EMPTY `dynamic_target_counts`
   - When `rare_boost_factor > 1.0`, **BYPASSES spectral rescoring** (lines 2110-2121)
   - Returns `sampled_instances[:target_count]` directly

#### The Bypass Logic (Lines 2110-2121)

```python
# OPTION 1 FIX: When upweighting is enabled, skip spectral rescoring
# Rationale: Spectral rescoring dominates selection and makes upweighting ineffective.
# Solution: Return coverage-based selection directly when rare_boost_factor > 1.0
if rare_boost_factor > 1.0:
    logger.info(
        f"[UPWEIGHT_BYPASS] Skipping spectral rescoring (rare_boost_factor={rare_boost_factor})"
    )
    logger.info(
        f"[UPWEIGHT_BYPASS] Returning {len(sampled_instances[:target_count])} instances "
        f"from coverage sampling"
    )
    return sampled_instances[:target_count]
```

### Why This Causes Less Coverage

**Scenario with rare_boost_factor=5.0:**

1. **Pattern A** selects instances (with empty `dynamic_target_counts`)
   - Prioritizes rare type X (boost factor 30x due to rare_boost_factor=5.0)
   - Selects instance A1 containing type X

2. **Pattern B** selects instances (with empty `dynamic_target_counts` - no knowledge of Pattern A's selection!)
   - Also prioritizes rare type X (same 30x boost)
   - Selects instance B1 containing type X
   - **REDUNDANCY**: Both patterns selected instances with type X

3. **Pattern C** selects instances (with empty `dynamic_target_counts`)
   - Also prioritizes type X
   - Selects instance C1 containing type X
   - **MORE REDUNDANCY**: Three patterns now have type X

**Result**:
- Type X is over-represented (appears in 3 patterns)
- Other rare types Y and Z are under-represented or missing
- Overall coverage: **84/91 types** (worse than baseline)

**Scenario with rare_boost_factor=1.0 (baseline):**

1. **Pattern A** selects instances
   - Spectral rescoring considers `selected_so_far` (empty at start)
   - Selects instance A1 with best structural match

2. **Pattern B** selects instances
   - Spectral rescoring considers `selected_so_far` (includes Pattern A's selections)
   - Knows that type X is already covered
   - Selects instance B2 with complementary types (Y and Z)
   - **CROSS-PATTERN COORDINATION via spectral rescoring**

3. **Pattern C** selects instances
   - Spectral rescoring considers `selected_so_far` (includes A and B)
   - Knows X, Y, Z are covered
   - Selects instance C3 with other missing types
   - **CONTINUED COORDINATION**

**Result**:
- Better complementarity between patterns
- Less redundancy
- Overall coverage: **85/91 types** (better than upweighted!)

### The Attempted Fix: Cross-Pattern Supplementation

The code includes cross-pattern supplementation (lines 1943-2032) to address missing types AFTER per-pattern selection:

```python
# NEW (2026-02-02): Cross-pattern supplementation when upweighting
# If rare_boost_factor > 1.0, look across ALL patterns for instances with missing types
if rare_boost_factor > 1.0 and self.source_resource_type_counts:
    # ... compute missing types ...
    # ... add supplemental instances (up to 10% of target budget) ...
```

**Limitations of this approach:**
1. **Budget constraint**: Can only add up to 10% more instances (line 1993)
2. **After-the-fact**: Doesn't prevent redundant selections, just supplements
3. **Insufficient for high rare_boost_factor**: When redundancy is severe, 10% budget can't compensate

## Proposed Solutions

### Option 1: Pass `selected_so_far` to `_sample_for_coverage` (RECOMMENDED)

**Change**: Modify `_sample_for_coverage` to accept and use global `selected_so_far` to compute `dynamic_target_counts` from ALL previously selected instances (across all patterns).

**Benefits:**
- Provides cross-pattern coordination without spectral rescoring
- Maintains upweighting effectiveness
- Prevents redundant rare type selections
- Preserves performance (no expensive spectral distance computations)

**Implementation:**
```python
# In _select_with_hybrid_scoring, line 2096:
sampled_instances, instance_metadata = self._sample_for_coverage(
    available_instances,
    max_samples=actual_max_samples,
    source_type_counts=self.source_resource_type_counts,
    target_type_counts=self._compute_global_target_counts(selected_so_far),  # NEW!
    rare_boost_factor=rare_boost_factor,
    missing_type_threshold=missing_type_threshold
)
```

**New helper function:**
```python
def _compute_global_target_counts(self, selected_so_far):
    """Compute type counts across ALL selected instances (all patterns)."""
    counts = {}
    for _, instance in selected_so_far:
        for resource in instance:
            resource_type = resource.get("type", "unknown")
            counts[resource_type] = counts.get(resource_type, 0) + 1
    return counts
```

### Option 2: Hybrid Approach (Coverage + Spectral)

**Change**: Don't bypass spectral rescoring entirely. Instead:
1. Use `_sample_for_coverage` to get a pool of high-coverage candidates
2. Apply spectral rescoring to prioritize among them
3. Combine coverage goals (upweighting) with structural similarity (spectral)

**Benefits:**
- Best of both worlds: coverage + structural similarity
- Cross-pattern coordination via spectral rescoring
- Maintains upweighting effectiveness

**Trade-off:**
- Higher computational cost (spectral distance calculations)
- May reduce upweighting impact if spectral scoring dominates

### Option 3: Two-Phase Selection with Swapping

**Change**: After per-pattern selection, identify and SWAP OUT redundant instances (not just supplement):
1. Phase 1: Per-pattern selection with upweighting
2. Phase 2: Identify redundant types (over-represented in multiple patterns)
3. Phase 3: Swap out instances with redundant types for instances with missing types

**Benefits:**
- Maintains target instance count (no budget inflation)
- More sophisticated than 10% supplementation
- Directly addresses redundancy issue

**Trade-off:**
- More complex implementation
- May disrupt architectural distribution balance

## Recommended Action

**Implement Option 1** (`selected_so_far` to `_sample_for_coverage`):

1. **Minimal code change**: Add helper function and pass global target counts
2. **Preserves performance**: No spectral rescoring overhead
3. **Fixes root cause**: Provides cross-pattern coordination during upweighted selection
4. **Maintains benefits**: Keeps upweighting effectiveness for rare type inclusion

### Expected Results After Fix

With Option 1 implemented:
- **rare_boost_factor=5.0**: Expected 87-90/91 types (improvement over both baseline AND current)
- **rare_boost_factor=3.0**: Expected 86-88/91 types (balanced, still improvement)
- **rare_boost_factor=1.0**: Expected 85/91 types (unchanged baseline)

## Additional Findings

### Distribution Fidelity Trade-off

Cell 18 shows that upweighting also affects distribution fidelity:
- **Baseline**: 1.41% average deviation (excellent fidelity)
- **Best**: 2.14% average deviation (worse fidelity)

**Explanation**: Upweighting prioritizes rare type coverage over proportional distribution. This is a fundamental trade-off:
- **More coverage** → More rare types included
- **Less distribution fidelity** → Architectural proportions slightly distorted

**Recommendation**: This trade-off is acceptable when coverage is the priority. For applications requiring strict distribution fidelity, use lower `rare_boost_factor` (2.0-3.0 instead of 5.0).

## Code References

- `_select_instances_proportionally`: src/architecture_based_replicator.py:1812-2032
- `_select_with_hybrid_scoring`: src/architecture_based_replicator.py:2034-2200
- `_sample_for_coverage`: src/architecture_based_replicator.py:2331-2524
- `_compute_boost_factor`: src/architecture_based_replicator.py:2526-2603
- Bypass logic: src/architecture_based_replicator.py:2110-2121
- Cross-pattern supplementation: src/architecture_based_replicator.py:1943-2032

## Testing Plan

After implementing Option 1:

1. **Unit test**: Verify `_compute_global_target_counts` correctly aggregates types across patterns
2. **Integration test**: Verify per-pattern selection with global target counts
3. **Notebook test**: Re-run `architecture_based_replication.ipynb` and verify improved coverage
4. **Regression test**: Ensure baseline (rare_boost_factor=1.0) remains unchanged

## Conclusion

The counterintuitive behavior where higher `rare_boost_factor` gives LESS coverage is caused by **per-pattern isolation without cross-pattern coordination**. The bypass of spectral rescoring (intended to preserve upweighting effectiveness) inadvertently removes the coordination mechanism that prevents redundant selections.

**Fix**: Pass global target counts (computed from `selected_so_far`) to `_sample_for_coverage` to provide cross-pattern coordination during upweighted selection.

**Impact**: Expected +3-5 type coverage improvement with rare_boost_factor=5.0 after fix.

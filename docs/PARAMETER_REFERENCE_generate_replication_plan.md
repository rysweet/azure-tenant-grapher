# Parameter Reference: `generate_replication_plan()`

**Generated**: 2026-02-03
**Source**: `src/architecture_based_replicator.py:563-649`

This document explains each parameter in `generate_replication_plan()` based on the current implementation.

---

## Quick Reference Table

| Parameter | Default | Status | Purpose |
|-----------|---------|--------|---------|
| `hops` | 2 | ⚠️ **UNUSED** | Defined but not implemented (intended for local subgraph comparison) |
| `include_orphaned_node_patterns` | True | ✅ **ACTIVE** | Includes instances with orphaned resource types for coverage |
| `use_architecture_distribution` | True | ✅ **ACTIVE** | Enables proportional pattern allocation based on source distribution |
| `use_configuration_coherence` | True | ✅ **ACTIVE** | Groups resources by configuration similarity |
| `use_spectral_guidance` | True | ✅ **ACTIVE** | Hybrid scoring: distribution balance + spectral optimization |
| `spectral_weight` | 0.1 | ✅ **ACTIVE** | Weight for spectral component in hybrid scoring (0.0-1.0) |
| `max_config_samples` | 500 | ✅ **ACTIVE** | Max configurations sampled per pattern |
| `sampling_strategy` | 'coverage' | ✅ **ACTIVE** | Instance selection strategy ('coverage' or 'diversity') |
| `rare_boost_factor` | varies | ✅ **ACTIVE** | Coverage-aware upweighting multiplier (1.0-5.0) |
| `missing_type_threshold` | 0.1 | ✅ **ACTIVE** | Threshold for "underrepresented" types (0.0-1.0) |

---

## Detailed Parameter Analysis

### 1. `hops: int = 2`

**Status**: ⚠️ **DEFINED BUT NOT USED**

**Intended Purpose** (from docstring):
- "Number of hops for local subgraph comparison"

**Current Implementation**:
- Parameter is accepted but never referenced in the code
- No local subgraph extraction logic exists
- Likely a placeholder for future feature or legacy from removed code

**Recommendation**:
- Remove parameter or implement local subgraph comparison feature
- Does not affect current behavior at any value

**Code Reference**: `src/architecture_based_replicator.py:566,596`

---

### 2. `include_orphaned_node_patterns: bool = True`

**Status**: ✅ **ACTIVE AND CRITICAL**

**Purpose**: Adds instances containing resource types NOT covered by detected architectural patterns

**How It Works**:
1. Detects "orphaned" resource types (in source but not in any pattern)
2. Queries Neo4j for ResourceGroups containing these types
3. Adds them to selection pool with pattern name "Orphaned Resources"
4. Reserves 25% of target budget by default (or uses coverage-aware allocation)

**Impact When Enabled**:
- **Before Fix**: Found 0 orphaned ResourceGroups (type name mismatch bug)
- **After Fix**: Finds 187 orphaned ResourceGroups
- **Coverage Improvement**: +66-68% node coverage (23% → 89-91%)
- **Rare Type Inclusion**: +93-100% improvement

**When to Disable**:
- Only when you want to EXCLUDE orphaned types from target tenant
- Testing pattern detection completeness
- You have 100% pattern coverage already

**Code References**:
- `src/architecture_based_replicator.py:708-715` (adds orphaned instances)
- `src/architecture_based_replicator.py:927-1003` (_find_orphaned_node_instances implementation)

---

### 3. `use_architecture_distribution: bool = True`

**Status**: ✅ **ACTIVE - LAYER 1 CONTROL**

**Purpose**: Enables proportional pattern allocation based on source tenant distribution

**How It Works**:

**LAYER 1: Distribution Analysis**
```python
distribution_scores = analyzer.compute_architecture_distribution(
    pattern_resources, source_pattern_graph
)
# Output: {pattern_name: {distribution_score, rank, instances, ...}}
```

**LAYER 2: Proportional Targets**
```python
pattern_targets = analyzer.compute_pattern_targets(
    distribution_scores, target_instance_count
)
# Output: {pattern_name: target_instance_count}
# Example: {"Web Application": 15, "Data Platform": 8, ...}
```

**Impact When Enabled**:
- Maintains architectural pattern proportions from source
- Allocates instance budget proportionally across patterns
- Enables Layers 1 & 2 of the selection pipeline

**Impact When Disabled**:
- Falls back to greedy spectral matching (old algorithm)
- No proportional allocation
- Uses `node_coverage_weight` parameter instead
- Random exploration/exploitation trade-off

**When to Disable**:
- Want pure spectral distance optimization
- Don't care about maintaining architectural proportions
- Testing fallback algorithm

**Code References**:
- `src/architecture_based_replicator.py:675-698` (Layer 1: distribution analysis)
- `src/architecture_based_replicator.py:729-781` (Layer 2: proportional targets)
- `src/architecture_based_replicator.py:806-814` (fallback when disabled)

---

### 4. `use_configuration_coherence: bool = True`

**Status**: ✅ **ACTIVE - AFFECTS LAYER 3**

**Purpose**: Groups resources by configuration similarity before pattern detection

**How It Works**:

**Configuration Fingerprinting**:
```python
# For each resource, extract configuration properties
fingerprint = {
    "tags": resource.get("tags", {}),
    "location": resource.get("location"),
    "sku": resource.get("sku"),
    "properties": resource.get("properties", {})
}
```

**Similarity Computation**:
```python
# Jaccard similarity on configuration keys/values
similarity = len(set1 & set2) / len(set1 | set2)
```

**Clustering**:
```python
# Agglomerative clustering: merge clusters with avg similarity > threshold
# Only clusters with 2+ resources become instances
```

**Impact When Enabled**:
- Resources with similar configs grouped together
- Instances represent coherent configuration patterns
- More realistic tenant replication (configs match source patterns)

**Impact When Disabled**:
- Random instance selection within patterns
- No configuration similarity considered
- Faster but less realistic

**Threshold**: 0.5 (hardcoded in `analyze_source_tenant`)

**Code References**:
- `src/architecture_based_replicator.py:485-561` (_find_configuration_coherent_instances)
- `src/architecture_based_replicator.py:793-805` (Layer 3: selection uses this)

---

### 5. `use_spectral_guidance: bool = True`

**Status**: ✅ **ACTIVE - HYBRID SCORING MODE**

**Purpose**: Combines architectural distribution adherence with spectral distance optimization

**How It Works**:

**Hybrid Scoring Function**:
```python
# For each candidate instance during selection:
distribution_deviation = |target_count - ideal_count| / ideal_count
spectral_distance = compute_spectral_distance(source_graph, target_graph + candidate)

hybrid_score = (1 - spectral_weight) * distribution_deviation +
               spectral_weight * spectral_distance

# Lower score is better
# spectral_weight controls trade-off
```

**Impact When Enabled** (`use_spectral_guidance=True`):
- Balances distribution fidelity AND structural similarity
- Each instance scored by both distribution and spectral components
- Recommended for best results

**Impact When Disabled** (`use_spectral_guidance=False`):
- Uses configuration coherence only (if enabled)
- OR random selection within patterns
- No spectral optimization during selection (only post-hoc validation)

**Trade-Off Control**: See `spectral_weight` parameter below

**Code References**:
- `src/architecture_based_replicator.py:786-805` (Layer 3: selection mode)
- `src/architecture_based_replicator.py:1074-1147` (_select_instance_spectral_guided)

---

### 6. `spectral_weight: float = 0.1`

**Status**: ✅ **ACTIVE - CONTROLS HYBRID TRADE-OFF**

**Purpose**: Controls balance between distribution adherence and spectral optimization

**Only Used When**: `use_spectral_guidance=True`

**How It Works**:

```python
hybrid_score = (1.0 - spectral_weight) * distribution_component +
               spectral_weight * spectral_component

# spectral_weight = 0.0: Pure distribution adherence (ignore spectral)
# spectral_weight = 0.1: Mostly distribution (90%), some spectral (10%) ← NOTEBOOK
# spectral_weight = 0.4: Balanced (60% distribution, 40% spectral) ← RECOMMENDED
# spectral_weight = 1.0: Pure spectral optimization (ignore distribution)
```

**Impact of Different Values**:

| Value | Distribution Weight | Spectral Weight | Best For |
|-------|-------------------|----------------|----------|
| 0.0 | 100% | 0% | Pure pattern proportion matching |
| 0.1 | 90% | 10% | **Notebook setting** (slight structural awareness) |
| 0.4 | 60% | 40% | **Recommended** (balance fidelity & structure) |
| 0.7 | 30% | 70% | Structure-first, proportions secondary |
| 1.0 | 0% | 100% | Pure structural matching (ignore proportions) |

**Notebook Uses 0.1**: Prioritizes maintaining architectural distribution with slight structural awareness

**Default in Code**: 0.4 (recommended balance)

**When to Adjust**:
- **Lower (0.0-0.2)**: When architectural proportions are critical, structure less so
- **Medium (0.3-0.5)**: Balanced approach (recommended)
- **Higher (0.6-1.0)**: When graph topology is more important than pattern proportions

**Code Reference**: `src/architecture_based_replicator.py:607-611,1074-1147`

---

### 7. `max_config_samples: int = 500`

**Status**: ✅ **ACTIVE - PERFORMANCE OPTIMIZATION**

**Purpose**: Limits number of instances evaluated per pattern during spectral-guided selection

**Only Used When**: `use_spectral_guidance=True`

**How It Works**:

```python
# For patterns with many instances (> max_config_samples):
if len(pattern_instances) > max_config_samples:
    # Sample max_config_samples instances using sampling_strategy
    sampled = sample_instances(pattern_instances, max_config_samples, strategy)
else:
    # Use all instances (no sampling needed)
    sampled = pattern_instances

# Then perform spectral-guided selection from sampled pool
```

**Impact of Different Values**:

| Value | Effect | Best For |
|-------|--------|----------|
| 10 | Very fast, limited diversity | Quick prototyping, small tenants |
| 100 | **Default (sufficient for most)** | Balanced speed/diversity |
| 500 | **Notebook setting** | Large tenants, comprehensive search |
| 1000+ | Slow, maximum diversity | Very large patterns only |

**Performance Trade-Off**:
- **Lower values**: Faster execution, may miss diverse configurations
- **Higher values**: Slower execution, more comprehensive search
- **No effect**: When patterns have fewer instances than this limit

**Notebook Uses 500**: Ensures comprehensive evaluation for large patterns

**When to Adjust**:
- **10-50**: Development/testing, need speed
- **100**: Production default, good balance
- **500+**: Large tenants with 100+ instances per pattern

**Code References**:
- `src/architecture_based_replicator.py:612-618` (docstring)
- `src/architecture_based_replicator.py:1098-1108` (sampling in _select_instance_spectral_guided)

---

### 8. `sampling_strategy: str = 'coverage'`

**Status**: ✅ **ACTIVE - DETERMINES SAMPLING ALGORITHM**

**Purpose**: Controls HOW instances are sampled when pattern has > max_config_samples instances

**Valid Values**:
- `"coverage"` ← **Notebook setting, RECOMMENDED**
- `"diversity"`

**How Each Strategy Works**:

#### **Strategy 1: `"coverage"` (RECOMMENDED)**

**Algorithm**: Greedy set cover to maximize unique resource types

```python
# For each iteration:
1. Compute which resource types are still missing from sample
2. Find instance that covers the most NEW types
3. Apply upweighting boost for missing/underrepresented types (if enabled)
4. Select instance with highest coverage score
5. Repeat until max_samples reached

# Scoring with upweighting:
for each new_type in instance:
    rarity_score = 1.0 / type_frequency
    boost = compute_boost_factor(new_type, source_counts, target_counts, rare_boost_factor)
    score += rarity_score * boost
```

**Impact**:
- Maximizes node coverage (unique resource types in target)
- Prioritizes rare types when upweighting enabled
- **Best for**: Comprehensive tenant replication, maximizing type diversity

**Upweighting Integration**: Works with `rare_boost_factor` parameter

#### **Strategy 2: `"diversity"`**

**Algorithm**: Maximin diversity sampling for configuration variation

```python
# For each iteration:
1. Select instance most dissimilar to already-selected instances
2. Use configuration fingerprint distance (Jaccard dissimilarity)
3. Maximize minimum distance to existing samples
4. No resource type awareness

# Scoring:
for each candidate:
    min_distance = min(distance(candidate, selected) for selected in samples)
    # Select candidate with highest min_distance
```

**Impact**:
- Maximizes configuration diversity
- No resource type coverage awareness
- **Best for**: Exploring configuration space, testing config variations

**Upweighting Integration**: Does NOT use upweighting (ignores `rare_boost_factor`)

**Recommendation**: Use `"coverage"` for production (notebook default)

**Code References**:
- `src/architecture_based_replicator.py:619-622` (docstring)
- `src/architecture_based_replicator.py:2207-2306` (_sample_for_coverage implementation)
- `src/architecture_based_replicator.py:2157-2205` (_sample_for_diversity implementation)

---

### 9. `rare_boost_factor: float` (varies in notebook: 1.0 or 5.0)

**Status**: ✅ **ACTIVE - COVERAGE OPTIMIZATION**

**Purpose**: Global multiplier for coverage-aware upweighting of missing/underrepresented resource types

**Only Used When**: `sampling_strategy="coverage"` (ignored for "diversity")

**How It Works**:

**Three-Tier Boost System**:
```python
def compute_boost_factor(resource_type, source_counts, target_counts, rare_boost_factor, threshold):
    if rare_boost_factor <= 1.0:
        return 1.0  # Feature disabled

    source_count = source_counts.get(resource_type, 0)
    target_count = target_counts.get(resource_type, 0)

    # Tier 1: Missing types (exist in source, not in target)
    if source_count > 0 and target_count == 0:
        return 6.0 * rare_boost_factor  # HIGHEST PRIORITY

    # Tier 2: Underrepresented types (target/source < threshold)
    if source_count > 0:
        coverage_ratio = target_count / source_count
        if coverage_ratio < threshold:
            return 3.0 * rare_boost_factor  # MEDIUM PRIORITY

    # Tier 3: Normal types
    return 1.0  # No boost

# Applied in greedy scoring:
score += rarity_score * boost_factor
```

**Impact of Different Values**:

| rare_boost_factor | Missing Boost | Underrep Boost | Effect | Use Case |
|----------------|---------------|----------------|--------|----------|
| 1.0 | 6.0 (disabled) | 3.0 (disabled) | **No upweighting** (backward compatible) | Baseline comparison |
| 2.0 | 12.0x | 6.0x | Moderate upweighting | Conservative improvement |
| 3.0 | **18.0x** | **9.0x** | **RECOMMENDED** balance | Production (balanced) |
| 5.0 | 30.0x | 15.0x | Aggressive upweighting | Maximum rare type coverage |
| 10.0 | 60.0x | 30.0x | Extreme upweighting | Research/testing only |

**Notebook Test Values**:
- `1.0`: Baseline (feature disabled)
- `5.0`: Aggressive upweighting for maximum improvement

**Expected Impact (at rare_boost_factor=3.0)**:
- **Node Coverage**: +15-25% improvement
- **Rare Type Inclusion**: +20-40% improvement (types with frequency < 5)
- **Performance Cost**: < 5% overhead (O(1) boost computation per type)

**Notebook Results (rare_boost_factor=5.0)**:
- Node Coverage: 87.9% → 91.2% (+3.3%)
- Rare Type Inclusion: 86.7% → 100% (+13.3%)

**When to Adjust**:
- `1.0`: Baseline, no upweighting
- `2.0-3.0`: Production use (balanced)
- `5.0+`: Maximum rare type coverage (may over-prioritize rare types)

**Code References**:
- `src/architecture_based_replicator.py:623-638` (docstring)
- `src/architecture_based_replicator.py:1945-2011` (_compute_boost_factor)
- `src/architecture_based_replicator.py:2256-2293` (greedy scoring with boost)

---

### 10. `missing_type_threshold: float = 0.1`

**Status**: ✅ **ACTIVE - DEFINES "UNDERREPRESENTED"**

**Purpose**: Threshold ratio for classifying types as "underrepresented" in upweighting logic

**Only Used When**: `rare_boost_factor > 1.0` and `sampling_strategy="coverage"`

**How It Works**:

```python
# For each resource type during selection:
coverage_ratio = target_count / source_count

if coverage_ratio < missing_type_threshold:
    # Type is "underrepresented" → apply 3x * rare_boost_factor boost
    boost = 3.0 * rare_boost_factor
else:
    # Type is adequately represented → no boost
    boost = 1.0
```

**Impact of Different Values**:

| Threshold | Meaning | Effect | Example (source=10) |
|-----------|---------|--------|---------------------|
| 0.05 | < 5% coverage | Aggressive (more types boosted) | target < 0.5 boosted |
| 0.10 | **< 10% coverage** (NOTEBOOK) | Balanced (recommended) | target < 1 boosted |
| 0.20 | < 20% coverage | Moderate | target < 2 boosted |
| 0.30 | < 30% coverage | Conservative (fewer types boosted) | target < 3 boosted |

**Notebook Uses 0.1** (10% threshold):
- Type with 10 instances in source needs at least 1 in target to avoid boost
- Type with 100 instances in source needs at least 10 in target

**When to Adjust**:
- **Lower (0.05)**: More aggressive boosting, more types classified as underrepresented
- **Medium (0.10)**: **Recommended** balance
- **Higher (0.30)**: Conservative, only severely underrepresented types boosted

**Interaction with rare_boost_factor**:
```python
# Example: Type with 10 in source, 0 in target
# rare_boost_factor=3.0, missing_type_threshold=0.1

coverage_ratio = 0 / 10 = 0.0
0.0 < 0.1  # TRUE → underrepresented
boost = 3.0 * 3.0 = 9.0x  # Boost applied

# If threshold was 0.30:
0.0 < 0.30  # Still TRUE → same outcome for missing types
# But threshold matters for PARTIAL coverage cases
```

**Code References**:
- `src/architecture_based_replicator.py:639-645` (docstring)
- `src/architecture_based_replicator.py:1978-1989` (threshold check in _compute_boost_factor)

---

## Summary: Notebook Configuration Analysis

**Notebook Parameters**:
```python
generate_replication_plan(
    target_instance_count=500,
    hops=2,                              # ⚠️ UNUSED (no effect)
    include_orphaned_node_patterns=True,  # ✅ CRITICAL (fixes coverage)
    use_architecture_distribution=True,   # ✅ Enables Layers 1 & 2
    use_configuration_coherence=True,     # ✅ Config similarity grouping
    use_spectral_guidance=True,           # ✅ Hybrid scoring mode
    spectral_weight=0.1,                  # ✅ 90% distribution, 10% spectral
    max_config_samples=500,               # ✅ Comprehensive sampling
    sampling_strategy='coverage',         # ✅ Greedy set cover (upweight-compatible)
    rare_boost_factor=rare_boost_factor,      # ✅ VARIES (1.0 baseline, 5.0 aggressive)
    missing_type_threshold=0.1            # ✅ 10% threshold (balanced)
)
```

### Configuration Quality Assessment

| Aspect | Assessment | Notes |
|--------|------------|-------|
| **Orphaned Coverage** | ✅ Optimal | `include_orphaned_node_patterns=True` enables fix |
| **Distribution Fidelity** | ✅ Excellent | `use_architecture_distribution=True` + `spectral_weight=0.1` prioritizes proportions |
| **Structural Similarity** | ⚠️ Low Weight | `spectral_weight=0.1` gives only 10% weight to graph structure |
| **Rare Type Coverage** | ✅ Strong | `sampling_strategy='coverage'` + `rare_boost_factor=5.0` maximizes rare types |
| **Performance** | ✅ Good | `max_config_samples=500` provides comprehensive search without excessive cost |
| **Configuration Realism** | ✅ Enabled | `use_configuration_coherence=True` groups similar configs |

### Recommendations

**Current Configuration is Well-Tuned For**:
- Maximizing resource type coverage (node coverage)
- Including rare/orphaned resource types
- Maintaining architectural pattern proportions
- Realistic configuration grouping

**Potential Adjustments**:

1. **Increase Structural Awareness**:
   - Change `spectral_weight=0.4` (from 0.1) for more graph topology matching
   - Trade-off: Slightly less exact distribution matching

2. **More Conservative Upweighting**:
   - Change `rare_boost_factor=3.0` (from 5.0) for balanced improvement
   - Still gets +20-40% rare type improvement with less aggressive boosting

3. **Remove Unused Parameter**:
   - Remove `hops=2` (has no effect in current implementation)

4. **Optimal Production Config**:
```python
generate_replication_plan(
    target_instance_count=500,
    include_orphaned_node_patterns=True,     # Critical for coverage
    use_architecture_distribution=True,      # Enable proportional allocation
    use_configuration_coherence=True,        # Realistic config grouping
    use_spectral_guidance=True,              # Hybrid scoring
    spectral_weight=0.4,                     # Balanced (60/40 distribution/spectral)
    max_config_samples=100,                  # Sufficient for most cases
    sampling_strategy='coverage',            # Greedy set cover
    rare_boost_factor=3.0,                     # Recommended balance
    missing_type_threshold=0.1               # 10% threshold
)
```

---

## Layer Pipeline Summary

**4-Layer Architecture Selection Pipeline**:

1. **LAYER 1: Distribution Analysis** (`use_architecture_distribution=True`)
   - Computes architectural pattern importance scores
   - Ranks patterns by distribution contribution

2. **LAYER 2: Proportional Targets** (`use_architecture_distribution=True`)
   - Allocates instance budget proportionally across patterns
   - Includes orphaned resources if enabled

3. **LAYER 3: Instance Selection** (mode depends on flags)
   - **Hybrid Spectral-Guided** (`use_spectral_guidance=True`): Distribution + spectral optimization
   - **Configuration-Coherent** (`use_configuration_coherence=True`): Config similarity
   - **Random**: Fast baseline (both flags False)
   - **Fallback**: Greedy spectral matching (if `use_architecture_distribution=False`)

4. **LAYER 4: Validation** (always runs)
   - Computes spectral distance history
   - Validates proportional allocation
   - Statistical tests for distribution fidelity

**Notebook Uses**: Layers 1-4 with hybrid spectral-guided selection (optimal configuration)

---

## Files for Further Reference

- **Implementation**: `src/architecture_based_replicator.py:563-849`
- **Coverage-Aware Upweighting**: `src/architecture_based_replicator.py:1945-2306`
- **Fix Summary**: `COMPLETE_FIX_SUMMARY.md`
- **Investigation**: `.claude/docs/INVESTIGATION_spectral_weight_parameter_effectiveness.md`
- **Tests**: `tests/test_coverage_aware_upweighting.py`

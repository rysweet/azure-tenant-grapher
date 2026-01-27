# Investigation: Spectral Comparison Influence on Resource Selection

**Investigation Date**: 2026-01-27
**Investigator**: Claude Code (ultrathink investigation-workflow)
**Context**: Understanding how spectral comparison influences resource selection in architecture-based replication

---

## Executive Summary

**Spectral distance plays TWO DISTINCT ROLES depending on selection mode:**

1. **Proportional Mode (default)**: Architecture distribution drives selection; spectral distance is a **post-hoc quality metric** used for validation and monitoring only.

2. **Greedy Mode (fallback)**: Spectral distance is an **active optimization target** that directly determines which instances are selected (when node_coverage_weight=0.0).

**Key Finding**: Recent updates made architecture distribution the default, relegating spectral distance from primary selection driver to validation metric.

---

## Investigation Questions Answered

### 1. Where Spectral Distance is Computed and Used

**Computation**: `_compute_spectral_distance()` at **src/architecture_based_replicator.py:1161-1206**

**Algorithm**: Laplacian Eigenvalue Spectrum Comparison
```
distance = ||eigenvalues(L₁) - eigenvalues(L₂)||₂ / (λ_max × √n)
```

**Usage Locations**:
- **Post-hoc validation** (proportional mode): Lines 709-719 - computed AFTER selection
- **Active optimization** (greedy mode): Lines 1141-1142, 1551 - computed DURING selection
- **Progress monitoring** (greedy mode): Lines 1581-1593 - logged periodically

### 2. How Spectral Distance Affects Selection

**Proportional Mode (Default)**: **NO DIRECT EFFECT**
- Selection driven by distribution scores and pattern targets
- Spectral distance computed after selection for validation only
- Lines: 686-694 (selection), 709-719 (post-hoc spectral)

**Greedy Mode (Fallback)**: **DIRECT EFFECT - Primary driver**
- Weighted score = `(1-w) × spectral_distance + w × node_coverage_penalty`
- Instance with lowest score selected at each iteration
- When w=0.0: Pure spectral distance optimization
- Lines: 703-707 (mode selection), 1551 (scoring), 1559-1561 (selection)

### 3. Balance Between Strategies

**They are MUTUALLY EXCLUSIVE strategies, not balanced:**

```
if use_architecture_distribution and pattern_targets:
    → Proportional selection (no spectral in selection)
else:
    → Greedy spectral selection (spectral-driven)
```

**Decision Tree**:
```
use_architecture_distribution parameter
    │
    ├─ TRUE (default) ─→ Layer 1-2: Distribution analysis
    │                    Layer 3: Proportional selection (NO spectral)
    │                    Post: Spectral validation
    │
    └─ FALSE ─────────→ Layer 3: Greedy spectral selection (USES spectral)
```

### 4. Evolution After Architecture Distribution Updates

**Before** (original):
- **Primary strategy**: Greedy spectral matching
- **Spectral role**: Selection driver (100% influence)
- **Pattern balance**: Emergent from structural matching

**After** (current):
- **Primary strategy**: Proportional selection based on distribution
- **Spectral role**: Validation metric (0% influence in default path)
- **Pattern balance**: Explicit (maintained by design)

**Impact**: Spectral distance influence DECREASED from primary driver to validation metric in default workflow.

---

## Key Technical Details

### Spectral Distance Formula

**Mathematical Basis**: Compares eigenvalue spectra of Graph Laplacian matrices
- Captures global structural properties beyond node/edge counts
- Normalized by maximum eigenvalue and matrix size for scale-invariance

**Interpretation**:
- **0.0** = Perfect structural match
- **< 0.2** = Good architectural similarity (documented threshold)
- **1.0** = Maximum dissimilarity or error

**Edge Cases**:
- Empty graphs → 1.0
- Different sizes → matrix padding with zeros
- Exceptions → 1.0 with logged warning

### Weighted Score System (Greedy Mode)

**Location**: `_compute_weighted_score()` at Lines 1116-1159

**Formula**:
```python
score = (1.0 - node_coverage_weight) * spectral_distance +
        node_coverage_weight * node_coverage_penalty
```

**Weight Effects**:

| Weight | Behavior | Use Case |
|--------|----------|----------|
| 0.0 | Pure spectral distance | Structure-first (matches graph topology) |
| 0.5 | Balanced | Equal weight to structure and completeness |
| 1.0 | Pure node coverage | Completeness-first (covers all resource types) |
| None | Random (0.0 or 1.0) | Exploration/exploitation |

### Layer Architecture

**4-Layer Selection System**:

1. **Layer 1**: Architecture Distribution Analysis (Lines 610-632)
   - Computes distribution scores using 4 metrics
   - Activates only when `use_architecture_distribution=True`

2. **Layer 2**: Proportional Pattern Targets (Lines 664-680)
   - Allocates target count proportionally across patterns
   - Based on distribution scores from Layer 1

3. **Layer 3**: Instance Selection (Lines 686-707)
   - **3A**: Proportional selection (Lines 686-694) - default, no spectral
   - **3B**: Greedy spectral selection (Lines 695-707) - fallback, uses spectral

4. **Layer 4**: Validation & Traceability (Lines 732-804)
   - Validates proportional sampling against targets
   - Computes distribution similarity metrics

---

## Code References

**Primary File**: `src/architecture_based_replicator.py`

**Key Methods**:
- `generate_replication_plan()`: Line 552 (entry point, strategy selection)
- `_compute_spectral_distance()`: Line 1161 (spectral algorithm)
- `_compute_weighted_score()`: Line 1116 (scoring formula)
- `_select_instances_proportionally()`: Line 1428 (proportional mode)
- `_select_instances_greedy()`: Line 1510 (greedy spectral mode)

**Critical Lines**:
- Strategy decision: 686-707
- Post-hoc spectral: 709-719
- Spectral in scoring: 1141-1142, 1551
- Selection based on score: 1559-1561

---

## Verification Examples

### Example 1: Proportional Mode (Default)

**Setup**:
- Pattern A: 60 instances (score: 60.0)
- Pattern B: 40 instances (score: 40.0)
- Target: 20 instances

**Execution**:
1. Layer 1: Distribution analysis → scores computed
2. Layer 2: Proportional allocation → Pattern A: 12, Pattern B: 8
3. Layer 3: Proportional selection → Select 12 from A, 8 from B (random/config-similar)
4. Post: Spectral distance computed for history → 0.167 (monitoring only)

**Spectral Role**: Validation only, NO selection influence

### Example 2: Greedy Mode (Fallback)

**Setup**:
- 100 available instances
- Target: 20 instances
- Weight: 0.0 (pure spectral)

**Execution**:
```
Iteration 1:
  For each of 100 instances:
    Build hypothetical_target with instance
    score = spectral_distance(source, hypothetical_target)
  Select instance with minimum score (e.g., 0.723)

Iteration 2:
  For each of 99 remaining:
    Build hypothetical_target with previous + instance
    score = spectral_distance(source, hypothetical_target)
  Select instance with minimum score (e.g., 0.654)

... 20 iterations total
```

**Spectral Role**: Primary optimization target, DIRECT selection influence

---

## Actionable Insights

### For Developers

1. **Tuning Selection Behavior**:
   - Want pattern balance? → Use proportional mode (default)
   - Want structural similarity? → Disable architecture distribution
   - Want hybrid? → Run proportional, then validate spectral_history

2. **Performance Optimization**:
   - Proportional mode: Fast O(P×I)
   - Greedy mode: Slow O(N²×G) due to graph operations per candidate

3. **Quality Metrics**:
   - Proportional mode: Check distribution validation (Layer 4)
   - Greedy mode: Track spectral_history convergence
   - Both: Spectral distance < 0.2 indicates good match

### For Tuning Parameters

**Parameter**: `use_architecture_distribution`
- **True** (default): Fast, pattern-balanced, spectral for validation
- **False**: Slow, structure-focused, spectral for optimization

**Parameter**: `node_coverage_weight` (greedy mode only)
- **0.0**: Pure spectral (structure-first)
- **0.5**: Balanced (structure + completeness)
- **1.0**: Pure coverage (completeness-first)

**Parameter**: `use_configuration_coherence` (proportional mode only)
- **True**: Select operationally similar instances
- **False**: Random sampling within pattern

---

## Related Patterns

### Multi-Strategy Selection Pattern

**Pattern**: Layer-based strategy selection with fallback
- Primary strategy: Architecture distribution (fast, pattern-aware)
- Fallback strategy: Greedy spectral (slow, structure-aware)
- Post-hoc validation: Spectral distance regardless of mode

**Application**: When you have complementary approaches (fast heuristic + accurate optimization), layer them with fallback.

### Post-Hoc Validation Pattern

**Pattern**: Compute expensive metric after selection for quality assurance
- Selection: Fast heuristic (distribution-based)
- Validation: Expensive metric (spectral distance)
- Benefit: Speed of heuristic + quality assurance of metric

**Application**: When optimization metric is too expensive to use in selection loop but valuable for validation.

---

## Future Investigations

**Potential Follow-ups**:

1. **Performance Analysis**:
   - Benchmark spectral computation time on large graphs (1000+ nodes)
   - Compare execution time: proportional vs greedy mode
   - Profile eigenvalue computation overhead

2. **Empirical Validation**:
   - A/B test: proportional vs greedy on same source tenant
   - Measure spectral distance convergence rates
   - Validate architecture distribution accuracy

3. **Parameter Sensitivity**:
   - Test node_coverage_weight impact across 0.0-1.0 range
   - Analyze optimal weight for different tenant profiles
   - Document when each mode performs best

---

## Session Metadata

**Investigation Workflow**: 6-phase systematic investigation (INVESTIGATION_WORKFLOW.md)

**Agents Deployed**:
- **Phase 1**: prompt-writer (scope clarification)
- **Phase 2**: architect (exploration strategy), patterns (similar investigations)
- **Phase 3**: analyzer (spectral computation), patterns (distribution system), architect (integration flow) - **parallel execution**
- **Phase 5**: reviewer (completeness check)

**Verification Methods**:
- Code tracing (lines 686-719, 1141-1595)
- Concrete example scenarios (proportional vs greedy)
- Formula verification (weighted score)
- Hypothesis confirmation (4 hypotheses tested)

**Files Analyzed**:
- `src/architecture_based_replicator.py` (1596 lines)
- Focus: Lines 552-804 (selection flow), 1116-1595 (scoring and greedy mode)

---

## Document Maintenance

**Last Updated**: 2026-01-27
**Status**: Complete investigation, verified findings
**Next Review**: When architecture-based replication undergoes major refactoring

**Update Triggers**:
- Changes to `_compute_spectral_distance()` algorithm
- New selection strategies added
- Parameter defaults changed
- Layer architecture modified

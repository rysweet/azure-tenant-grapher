# Quick Start: Upweight Factor Test Script

## TL;DR

Test if `rare_boost_factor` parameter is working effectively:

```bash
# Full test with auto-improvement
python scripts/test_rare_boost_factor.py

# Safe mode (no code changes)
python scripts/test_rare_boost_factor.py --dry-run
```

## What It Does

1. Tests replicator with `rare_boost_factor=1.0` (baseline)
2. Tests replicator with `rare_boost_factor=5.0` (boosted)
3. Measures node coverage difference (should be ≥5%)
4. If difference < 5%, tries improvement strategies automatically
5. Always restores original code (100% safe)

## Prerequisites

- Neo4j running (`docker-compose up -d`)
- Environment variables set (or use defaults):
  ```bash
  export NEO4J_URI="bolt://localhost:7687"
  export NEO4J_USER="neo4j"
  export NEO4J_PASSWORD="password"
  ```

## Three Usage Modes

### 1. Full Improvement Loop (Default)

```bash
python scripts/test_rare_boost_factor.py
```

**Runs**: Baseline + up to 10 improvement strategies
**Output**: Console logs + `upweight_test_report.json`
**Safe**: Yes, always restores original code

### 2. Dry Run (Safe Mode)

```bash
python scripts/test_rare_boost_factor.py --dry-run
```

**Runs**: Baseline only
**Output**: Console logs (coverage difference)
**Safe**: Yes, never modifies code

### 3. Single Strategy Test

```bash
python scripts/test_rare_boost_factor.py --strategy 0
```

**Runs**: Tests one specific strategy
**Available strategies**: 0-4 (see strategies below)
**Safe**: Yes, always restores original code

## Available Strategies

| Index | Name              | Type       | Description                                     |
|-------|-------------------|------------|-------------------------------------------------|
| 0     | boost_8_4         | Multiplier | Orphaned=8x, Underrepresented=4x                |
| 1     | boost_10_5        | Multiplier | Orphaned=10x, Underrepresented=5x               |
| 2     | boost_12_6        | Multiplier | Orphaned=12x, Underrepresented=6x               |
| 3     | threshold_0.05    | Threshold  | Lower threshold (more aggressive)               |
| 4     | threshold_0.15    | Threshold  | Raise threshold (less aggressive)               |

**Current baseline values**:
- Orphaned boost: `6.0 * rare_boost_factor`
- Underrepresented boost: `3.0 * rare_boost_factor`
- Threshold: `0.1` (10%)

## Interpreting Results

### Coverage Difference Metric

- **≥ 5%**: SUCCESS ✓ (rare_boost_factor working well)
- **2-5%**: Moderate effect (below threshold, try improvements)
- **< 2%**: Minimal effect (potential issue)

### Success Outcomes

#### Baseline Already Successful
```
✓ Baseline already meets success threshold (8.45% >= 5.0%)
No improvement needed.
```

**Meaning**: Current parameters are effective, no changes needed.

#### Strategy Succeeds
```
✓ SUCCESS! Strategy 'boost_8_4' achieves 6.80% coverage difference (>= 5.0%)

Recommendation: Apply 'boost_8_4' permanently
  Increase missing boost to 8x, underrepresented to 4x
```

**Meaning**: Strategy `boost_8_4` improves effectiveness. Consider applying permanently.

#### Max Iterations Reached
```
✗ Max iterations (10) reached without success

Best strategy: boost_10_5 (4.32%)
```

**Meaning**: No strategy reached 5% threshold. Best was `boost_10_5` at 4.32%.

## Example Usage

### Quick Validation

Before investigating effectiveness issues:

```bash
# Check current effectiveness (safe mode)
python scripts/test_rare_boost_factor.py --dry-run
```

If coverage difference < 5%, run full improvement loop:

```bash
# Try improvements automatically
python scripts/test_rare_boost_factor.py
```

### Testing Specific Strategy

After reading investigation results, test recommended strategy:

```bash
# Test boost_10_5 strategy
python scripts/test_rare_boost_factor.py --strategy 1
```

### Validating Code Changes

After manually applying a strategy, validate improvement:

```bash
# Test current code effectiveness
python scripts/test_rare_boost_factor.py --dry-run
```

## Safety Guarantees

1. **Always restores original code** (in `finally` block)
2. **Creates backup** before any modification (`*.py.backup`)
3. **Validates syntax** before writing modified code
4. **Git safety checks** (warns if uncommitted changes)
5. **Error handling** for all failure modes

**You cannot permanently break your code by running this script.**

## Common Issues

### "Not in a git repository"
**Solution**: Run from project root

### "Failed to import ArchitecturePatternReplicator"
**Solution**: Run from project root or add `src/` to `PYTHONPATH`

### "Neo4j connection failure"
**Solution**: Start Neo4j with `docker-compose up -d`

### "Syntax error after modification"
**Solution**: Report as bug (script should validate syntax)

## Output Files

- **Console**: Real-time logs and progress
- **upweight_test_report.json**: Full test results (full loop mode only)
- **architecture_based_replicator.py.backup**: Temporary backup (auto-cleaned)

## Next Steps After Success

1. Review successful strategy parameters
2. Manually apply changes to code (if recommended)
3. Run dry-run mode to validate improvement persists
4. Create PR with changes and test results
5. Document in investigation notes

## Related Documentation

- **Full Documentation**: `scripts/README_test_rare_boost_factor.md`
- **Investigation**: `.claude/docs/INVESTIGATION_spectral_weight_parameter_effectiveness.md`
- **Implementation**: `src/architecture_based_replicator.py` (lines 2200-2223)

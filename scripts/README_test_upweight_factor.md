# Auto-Improving Upweight Factor Test Script

## Overview

`test_rare_boost_factor.py` is an auto-improving test script that validates the effectiveness of the `rare_boost_factor` parameter in architecture-based tenant replication. It measures node coverage differences between baseline (`rare_boost_factor=1.0`) and boosted (`rare_boost_factor=5.0`) configurations, then automatically tries improvement strategies if the difference is below the success threshold.

## Architecture

The script follows a 4-layer architecture design:

### Layer 1: Safety & State Management
- **TestSession**: Manages backup/restore and iteration tracking
- Creates backup immediately on initialization
- Records all iteration results
- Restores original code on exit (always)
- Generates JSON report of test session

### Layer 2: Core Testing
- **test_rare_boost_factor()**: Runs replicator with specific rare_boost_factor and extracts metrics
- **compute_coverage_difference()**: Computes percentage point difference in node coverage

### Layer 3: Improvement Strategies
- **STRATEGIES**: List of predefined improvement strategies
- **apply_strategy()**: Modifies source code based on strategy type
- **reload_replicator()**: Reloads module after code modification

### Layer 4: Orchestration
- **run_improvement_loop()**: Main loop that tests strategies until success or max iterations
- **main()**: CLI entry point with three modes (full loop, dry-run, single strategy)

## Usage

### Full Improvement Loop (Default)

Runs baseline test, then tries improvement strategies until success threshold is reached or max iterations exhausted:

```bash
python scripts/test_rare_boost_factor.py
```

**Output**: JSON report saved to `upweight_test_report.json`

### Dry Run Mode

Tests baseline only without any code modifications (safe mode):

```bash
python scripts/test_rare_boost_factor.py --dry-run
```

**Use case**: Validate current effectiveness without risk of modifications

### Single Strategy Test

Tests a specific improvement strategy by index:

```bash
python scripts/test_rare_boost_factor.py --strategy 0  # boost_8_4
python scripts/test_rare_boost_factor.py --strategy 1  # boost_10_5
python scripts/test_rare_boost_factor.py --strategy 2  # boost_12_6
python scripts/test_rare_boost_factor.py --strategy 3  # threshold_0.05
python scripts/test_rare_boost_factor.py --strategy 4  # threshold_0.15
```

**Use case**: Validate a specific strategy without running full loop

## Improvement Strategies

The script includes 5 predefined strategies:

### Boost Multiplier Strategies

Modify the hardcoded boost multipliers in `_compute_boost_factor()`:

1. **boost_8_4**: Orphaned boost = 8.0x, Underrepresented boost = 4.0x
2. **boost_10_5**: Orphaned boost = 10.0x, Underrepresented boost = 5.0x
3. **boost_12_6**: Orphaned boost = 12.0x, Underrepresented boost = 6.0x

**Current values** (baseline):
- Orphaned (missing) boost: `6.0 * rare_boost_factor`
- Underrepresented boost: `3.0 * rare_boost_factor`

### Threshold Strategies

Modify the `missing_type_threshold` default parameter:

4. **threshold_0.05**: Lower threshold to 0.05 (more aggressive underrepresented detection)
5. **threshold_0.15**: Raise threshold to 0.15 (less aggressive underrepresented detection)

**Current value** (baseline): `0.1` (10% coverage ratio)

## How It Works

### Iteration Process

1. **Baseline Test** (Iteration 0):
   - Test with `rare_boost_factor=1.0` → Extract metrics
   - Test with `rare_boost_factor=5.0` → Extract metrics
   - Compute coverage difference (percentage points)
   - If `diff >= 5.0%` → SUCCESS, stop
   - If `diff < 5.0%` → Continue to improvement strategies

2. **Improvement Iterations** (1-10):
   - Apply strategy N (modify source code)
   - Reload `ArchitecturePatternReplicator` module
   - Test with `rare_boost_factor=1.0` and `5.0`
   - Compute coverage difference
   - If `diff >= 5.0%` → SUCCESS, stop
   - Otherwise → Restore original code, try next strategy

3. **Completion**:
   - Generate JSON report with all iteration results
   - Identify best strategy (highest coverage difference)
   - Always restore original code (safety guarantee)

### Metrics Extracted

For each test run, the script extracts:

- `instance_count`: Number of instances selected
- `source_nodes`: Number of unique node types in source pattern graph
- `target_nodes`: Number of unique node types in selected instances
- `covered_nodes`: Intersection of source and target nodes
- `node_coverage`: Percentage of source nodes covered by target (`covered / source * 100`)

### Success Criteria

- **Success Threshold**: `5.0` percentage points
- **Max Iterations**: `10` strategies (baseline + 9 improvement attempts)
- **Success Condition**: `coverage_diff >= 5.0%`

## Safety Features

### Automatic Backup/Restore

- Backup created immediately on TestSession initialization
- Original code ALWAYS restored on exit (in `finally` block)
- Backup file: `architecture_based_replicator.py.backup`

### Syntax Validation

- All code modifications validated with `compile()` before writing
- Syntax errors abort strategy and restore original code

### Git Safety Checks

- Verifies script runs in git repository
- Warns if uncommitted changes exist
- Prompts user to continue or abort

### Error Handling

- **Neo4j connection failure**: Fail fast with clear error
- **Syntax error from edit**: Abort strategy, restore original
- **Import error after reload**: Restore original, log failure
- **Module reload failure**: Stop iteration loop, restore code

## Configuration

### Neo4j Connection

Uses environment variables:

```bash
export NEO4J_URI="bolt://localhost:7687"
export NEO4J_USER="neo4j"
export NEO4J_PASSWORD="your_password"
```

**Defaults**: `bolt://localhost:7687`, `neo4j`, `password`

### Test Parameters

Hardcoded in script (modify in `main()` if needed):

```python
test_params = {
    "target_count": 10,           # Number of instances to select
    "max_config_samples": 5,       # Max configuration samples
    "missing_type_threshold": 0.1, # Coverage ratio threshold (10%)
}
```

### Success Threshold

```python
success_threshold = 5.0  # 5 percentage points coverage difference
```

## Output

### Console Output

Real-time logging of:
- Iteration progress
- Strategy application
- Test results (instance count, node coverage)
- Coverage differences
- Success/failure status

### JSON Report

Saved to `upweight_test_report.json` (full loop mode only):

```json
{
  "timestamp": "2026-01-29T10:30:00.000000",
  "target_file": "/path/to/architecture_based_replicator.py",
  "iterations": [
    {
      "strategy_name": "baseline",
      "coverage_diff": 3.45,
      "success": false,
      "error": null,
      "metrics_1_0": { ... },
      "metrics_5_0": { ... }
    },
    {
      "strategy_name": "boost_8_4",
      "coverage_diff": 6.78,
      "success": true,
      "error": null,
      "metrics_1_0": { ... },
      "metrics_5_0": { ... }
    }
  ],
  "best_strategy": {
    "strategy_name": "boost_8_4",
    "coverage_diff": 6.78,
    "success": true
  }
}
```

## Interpreting Results

### Coverage Difference Interpretation

- **< 2%**: Upweight factor has minimal effect (potential issue)
- **2-5%**: Moderate effect (below threshold, try improvements)
- **≥ 5%**: Strong effect (SUCCESS - upweight factor working well)
- **> 10%**: Excellent effect (upweight factor highly effective)

### Strategy Recommendation

If baseline fails but a strategy succeeds:

1. Review the successful strategy parameters
2. Consider applying the strategy permanently to codebase
3. Re-run tests to validate improvement persists
4. Document the change in code review

### Baseline Already Successful

If baseline (iteration 0) meets success threshold:

- Upweight factor already working effectively
- No code changes needed
- Current boost multipliers and thresholds are appropriate

## Implementation Notes

### Code Modification Strategy

Uses string replacement on hardcoded values:

**Boost multipliers** (lines 2214, 2220):
```python
# Before
return 6.0 * rare_boost_factor  # Missing/orphaned
return 3.0 * rare_boost_factor  # Underrepresented

# After (boost_10_5 strategy)
return 10.0 * rare_boost_factor
return 5.0 * rare_boost_factor
```

**Threshold** (multiple function signatures):
```python
# Before
missing_type_threshold: float = 0.1

# After (threshold_0.05 strategy)
missing_type_threshold: float = 0.05
```

### Module Reload

After code modification:
1. Remove module from `sys.modules` cache
2. Re-import with `importlib.import_module()`
3. Use fresh class for testing

This ensures modified code is actually used in tests.

### Test Isolation

Each strategy test:
- Starts from clean baseline code
- Modifies code
- Tests
- Restores original code

No cross-contamination between strategies.

## Troubleshooting

### "Not in a git repository"

**Cause**: Script requires git repository for safety checks

**Solution**: Run from project root or bypass check (not recommended)

### "Failed to import ArchitecturePatternReplicator"

**Cause**: Python import path issue or module not found

**Solution**: Run from project root or ensure `src/` is in `PYTHONPATH`

### "Neo4j connection failure"

**Cause**: Neo4j not running or incorrect credentials

**Solution**:
- Start Neo4j: `docker-compose up -d`
- Verify environment variables: `echo $NEO4J_URI`

### "Syntax error after modification"

**Cause**: String replacement created invalid Python syntax

**Solution**: Review strategy implementation, fix replacement logic

### "Module reload failed"

**Cause**: Import error after code modification

**Solution**: Check modified code for import issues, restore original

## Examples

### Example 1: Baseline Already Effective

```bash
$ python scripts/test_rare_boost_factor.py

[Iteration 0] Baseline test
Testing rare_boost_factor=1.0
  instance_count=10, node_coverage=75.00%
Testing rare_boost_factor=5.0
  instance_count=10, node_coverage=83.45%
Coverage difference: 83.45% - 75.00% = 8.45 percentage points

✓ Baseline already meets success threshold (8.45% >= 5.0%)
No improvement needed.

================================================================================
IMPROVEMENT LOOP RESULTS
================================================================================
Success: True
Iterations: 1
Best strategy: baseline
================================================================================
```

### Example 2: Improvement Strategy Succeeds

```bash
$ python scripts/test_rare_boost_factor.py

[Iteration 0] Baseline test
Testing rare_boost_factor=1.0
  instance_count=10, node_coverage=70.00%
Testing rare_boost_factor=5.0
  instance_count=10, node_coverage=73.20%
Coverage difference: 73.20% - 70.00% = 3.20 percentage points

✗ Baseline below threshold (3.20% < 5.0%)
Trying improvement strategies...

[Iteration 1] Testing strategy: boost_8_4
  Increase missing boost to 8x, underrepresented to 4x
Testing rare_boost_factor=1.0
  instance_count=10, node_coverage=70.00%
Testing rare_boost_factor=5.0
  instance_count=10, node_coverage=76.80%
Coverage difference: 76.80% - 70.00% = 6.80 percentage points

✓ SUCCESS! Strategy 'boost_8_4' achieves 6.80% coverage difference (>= 5.0%)

Recommendation: Apply 'boost_8_4' permanently
  Increase missing boost to 8x, underrepresented to 4x

================================================================================
IMPROVEMENT LOOP RESULTS
================================================================================
Success: True
Iterations: 2
Best strategy: boost_8_4
================================================================================
```

### Example 3: Dry Run

```bash
$ python scripts/test_rare_boost_factor.py --dry-run

DRY RUN MODE: Testing baseline only (no modifications)
================================================================================
Testing rare_boost_factor=1.0
  instance_count=10, node_coverage=72.50%
Testing rare_boost_factor=5.0
  instance_count=10, node_coverage=75.30%
Coverage difference: 75.30% - 72.50% = 2.80 percentage points

================================================================================
DRY RUN RESULTS
================================================================================
Coverage difference: 2.80 percentage points
Baseline (upweight=1.0): 72.50%
Boosted (upweight=5.0):  75.30%
================================================================================
```

## Related Documentation

- **Investigation**: `.claude/docs/INVESTIGATION_spectral_weight_parameter_effectiveness.md`
- **Architecture Design**: See architect agent analysis in notebook
- **Replicator Implementation**: `src/architecture_based_replicator.py`
- **Testing Strategy**: `SPECTRAL_WEIGHT_INVESTIGATION.md`

## Future Enhancements

Potential improvements (not implemented):

1. **Adaptive Strategy Selection**: Use Bayesian optimization to choose next strategy
2. **Multi-Parameter Tuning**: Optimize boost multipliers AND threshold simultaneously
3. **Configurable Success Threshold**: Make 5.0% threshold a CLI argument
4. **Strategy Templates**: User-defined strategies via JSON config
5. **Regression Testing**: Track coverage differences over time, detect regressions
6. **Automated PR Creation**: If strategy succeeds, offer to create PR with changes

# Quick Fix Implementation Guide

**For**: Bugs #113, #115, #116 (Smart Import Failures)
**Time Required**: 2-3 hours for immediate mitigation
**Skill Level**: Intermediate Python/Neo4j

---

## Prerequisites

```bash
# Ensure you have the codebase
cd /home/azureuser/src/azure-tenant-grapher

# Check Python environment
python3 --version  # Should be 3.8+

# Check Neo4j connection
# (Verify Neo4j is running and accessible)
```

---

## Step 1: Diagnose the Problem (5 minutes)

### Check SCAN_SOURCE_NODE Relationships

Open Neo4j Browser or use cypher-shell:

```cypher
// Count missing relationships by type
MATCH (abs:Resource:Abstracted)
WHERE NOT (abs)-[:SCAN_SOURCE_NODE]->(:Resource:Original)
RETURN abs.type, count(*) as missing_count
ORDER BY missing_count DESC
LIMIT 20;
```

**Expected Output**: Shows resource types with missing SCAN_SOURCE_NODE relationships

**Record the numbers**:
- CosmosDB accounts missing: ______
- Automation runbooks missing: ______
- Role assignments missing: ______
- Total missing: ______

If **total missing > 100**, proceed with immediate fixes.

---

## Step 2: Backup Current Code (2 minutes)

```bash
# Backup the file we'll modify
cp src/iac/resource_comparator.py src/iac/resource_comparator.py.backup

# Create a git branch for the fix
git checkout -b fix/smart-import-bugs-113-115-116
```

---

## Step 3: Implement Fix #1 - Heuristic ID Cleanup (60 minutes)

### 3.1: Add the cleanup method

Open `src/iac/resource_comparator.py` and add this method around **line 555** (after `_generate_summary`):

```python
def _heuristic_clean_abstracted_id(self, abstracted_id: str) -> str:
    """
    Attempt to clean abstracted ID back to original Azure ID format.

    Abstracted IDs often have patterns like:
    - Suffix: resource_name_abc123_def456 → resource-name
    - Underscores: my_resource → my-resource (Azure convention)

    This is a HEURISTIC approach and may not work for all resource types.
    The proper fix is to ensure SCAN_SOURCE_NODE relationships exist.

    Args:
        abstracted_id: Abstracted resource ID with transformed name

    Returns:
        Best-effort cleaned ID
    """
    import re

    # Split ID into parts
    parts = abstracted_id.split("/")
    if len(parts) < 2:
        logger.warning(
            f"Cannot clean abstracted ID (unexpected format): {abstracted_id}"
        )
        return abstracted_id

    # Extract resource name (last part of ID)
    resource_name = parts[-1]
    original_name = resource_name

    # Pattern 1: Remove suffix pattern _hexhex_hexhex (e.g., _a9c787_f05ca8)
    # This is added by abstraction process to make names unique
    cleaned_name = re.sub(r'_[a-f0-9]{6}_[a-f0-9]{6}$', '', resource_name)

    if cleaned_name != resource_name:
        logger.debug(
            f"Removed hex suffix: {resource_name} → {cleaned_name}"
        )
        original_name = cleaned_name

    # Pattern 2: Replace underscores with hyphens (Azure naming convention)
    # BUT: Only if we removed a suffix (otherwise we might break valid names)
    if original_name != resource_name:
        hyphen_name = original_name.replace('_', '-')
        if hyphen_name != original_name:
            logger.debug(
                f"Replaced underscores: {original_name} → {hyphen_name}"
            )
            original_name = hyphen_name

    # Rebuild ID with cleaned name
    if original_name != resource_name:
        parts[-1] = original_name
        cleaned_id = "/".join(parts)
        logger.info(
            f"Heuristic cleanup applied: {abstracted_id} → {cleaned_id} "
            "(SCAN_SOURCE_NODE missing - this is a FALLBACK approach)"
        )
        return cleaned_id

    # No cleanup possible - return original
    logger.debug(
        f"No heuristic cleanup applied to {abstracted_id} "
        "(no patterns matched)"
    )
    return abstracted_id
```

### 3.2: Update _get_original_azure_id to use heuristic cleanup

Find the `_get_original_azure_id` method (around **line 283**) and modify the exception handling:

**Find this code** (around line 336-341):
```python
except Exception as e:
    logger.warning(
        f"Error querying SCAN_SOURCE_NODE for {abstracted_id}: {e}",
        exc_info=True,
    )
    return None
```

**Replace with**:
```python
except Exception as e:
    logger.warning(
        f"Error querying SCAN_SOURCE_NODE for {abstracted_id}: {e}, "
        "attempting heuristic cleanup",
        exc_info=True,
    )
    # FALLBACK: Attempt heuristic cleanup of abstracted ID
    return self._heuristic_clean_abstracted_id(abstracted_id)
```

**Also find** (around line 330-334):
```python
else:
    logger.debug(
        f"No SCAN_SOURCE_NODE relationship found for {abstracted_id}"
    )
    return None
```

**Replace with**:
```python
else:
    logger.debug(
        f"No SCAN_SOURCE_NODE relationship found for {abstracted_id}, "
        "attempting heuristic cleanup"
    )
    # FALLBACK: Attempt heuristic cleanup of abstracted ID
    return self._heuristic_clean_abstracted_id(abstracted_id)
```

---

## Step 4: Implement Fix #3 - Validation Warnings (30 minutes)

### 4.1: Add validation method

Add this method around **line 560** (after `_heuristic_clean_abstracted_id`):

```python
def _validate_classification_summary(
    self, summary: Dict[str, int], total_resources: int
) -> None:
    """
    Validate classification summary for suspicious patterns.

    Logs warnings if classification ratios indicate potential issues like
    missing SCAN_SOURCE_NODE relationships.

    Args:
        summary: Classification summary counts
        total_resources: Total number of abstracted resources
    """
    if total_resources == 0:
        return

    new_count = summary.get(ResourceState.NEW.value, 0)
    exact_match_count = summary.get(ResourceState.EXACT_MATCH.value, 0)
    drifted_count = summary.get(ResourceState.DRIFTED.value, 0)

    new_percentage = (new_count / total_resources) * 100
    matched_count = exact_match_count + drifted_count
    matched_percentage = (matched_count / total_resources) * 100

    # Expected: Most resources should match (EXACT_MATCH or DRIFTED)
    # NEW resources should be < 50% in most scenarios

    if new_percentage > 50.0:
        logger.warning(
            f"SUSPICIOUS CLASSIFICATION PATTERN DETECTED:\\n"
            f"  {new_count}/{total_resources} ({new_percentage:.1f}%) classified as NEW\\n"
            f"  {matched_count}/{total_resources} ({matched_percentage:.1f}%) classified as EXACT_MATCH/DRIFTED\\n"
            f"\\n"
            f"This may indicate:\\n"
            f"  1. SCAN_SOURCE_NODE relationships are missing/broken in the graph\\n"
            f"  2. Target scan is incomplete or from different environment\\n"
            f"  3. Resource ID normalization issues\\n"
            f"\\n"
            f"RECOMMENDED ACTIONS:\\n"
            f"  1. Run diagnostic query in Neo4j\\n"
            f"  2. Verify target scan completed successfully\\n"
            f"  3. Check logs for 'heuristic cleanup' messages\\n"
            f"\\n"
            f"See ROOT_CAUSE_ANALYSIS_SMART_IMPORT.md for details"
        )

    if new_percentage > 90.0:
        logger.error(
            f"CRITICAL: {new_percentage:.1f}% of resources classified as NEW. "
            f"This will likely cause false positives/negatives in smart import. "
            f"Investigation required before proceeding."
        )
```

### 4.2: Call validation in compare_resources

Find the `compare_resources` method (around **line 83**) and add validation call.

**Find this code** (around line 140-149):
```python
# Generate summary
summary = self._generate_summary(classifications)

logger.info(
    f"Resource comparison complete: {summary[ResourceState.NEW.value]} new, "
    f"{summary[ResourceState.EXACT_MATCH.value]} exact matches, "
    f"{summary[ResourceState.DRIFTED.value]} drifted, "
    f"{summary[ResourceState.ORPHANED.value]} orphaned"
)

return ComparisonResult(classifications=classifications, summary=summary)
```

**Replace with**:
```python
# Generate summary
summary = self._generate_summary(classifications)

# NEW: Validation check for suspicious classification patterns
self._validate_classification_summary(summary, len(abstracted_resources))

logger.info(
    f"Resource comparison complete: {summary[ResourceState.NEW.value]} new, "
    f"{summary[ResourceState.EXACT_MATCH.value]} exact matches, "
    f"{summary[ResourceState.DRIFTED.value]} drifted, "
    f"{summary[ResourceState.ORPHANED.value]} orphaned"
)

return ComparisonResult(classifications=classifications, summary=summary)
```

---

## Step 5: Test the Fixes (30 minutes)

### 5.1: Run existing unit tests

```bash
# Run all resource comparator tests
pytest tests/iac/test_resource_comparator.py -v

# Expected: All tests should pass (may see new debug logs)
```

### 5.2: Test with real data (if available)

```bash
# Enable debug logging
export LOG_LEVEL=DEBUG

# Run smart import generation
python -m src.iac.cli_handler generate \
    --subscription-id YOUR_SUBSCRIPTION_ID \
    --output-dir /tmp/test_smart_import

# Check logs for:
# 1. "heuristic cleanup applied" messages (should see some)
# 2. "SUSPICIOUS CLASSIFICATION" warnings (should NOT see if fix works)
# 3. Classification summary (NEW should be < 50%)
```

### 5.3: Verify improved classification

Check the generation report:

```bash
cat /tmp/test_smart_import/generation_report.txt
```

**Look for**:
- Import blocks count (should be much higher than before)
- Resources generated (should match import blocks closely)

**Compare with before**:
- Before: ~1% had import blocks
- After: ~80%+ should have import blocks

---

## Step 6: Commit the Fixes (5 minutes)

```bash
# Add the modified file
git add src/iac/resource_comparator.py

# Commit with reference to bugs
git commit -m "fix: Add heuristic ID cleanup and validation for Bugs #113, #115, #116

- Add _heuristic_clean_abstracted_id() to handle missing SCAN_SOURCE_NODE
- Add _validate_classification_summary() to detect suspicious patterns
- Update _get_original_azure_id() to use heuristic cleanup as fallback
- Update compare_resources() to validate classification ratios

This mitigates false positives/negatives in smart import when
SCAN_SOURCE_NODE relationships are missing from the graph.

Bugs: #113 (CosmosDB false positives), #115 (runbook false negative),
#116 (role assignment false negatives)

See ROOT_CAUSE_ANALYSIS_SMART_IMPORT.md for complete analysis."

# Push to remote (optional - review first)
# git push origin fix/smart-import-bugs-113-115-116
```

---

## Step 7: Monitor Results (Ongoing)

### After running smart import again:

1. **Check logs for warnings**:
   ```bash
   grep -i "SUSPICIOUS CLASSIFICATION" /path/to/log.txt
   grep -i "heuristic cleanup applied" /path/to/log.txt | wc -l
   ```

2. **Verify metrics**:
   - Classification ratio (NEW vs MATCHED)
   - Import block count
   - Terraform apply success rate

3. **If still seeing issues**:
   - Check Neo4j diagnostic query again
   - Review heuristic cleanup logs
   - May need to adjust heuristic patterns

---

## Expected Results

### Before Fixes
```
Classification Summary:
- NEW: 3,400 (90%)
- EXACT_MATCH: 50 (1%)
- DRIFTED: 50 (1%)
- ORPHANED: 300 (8%)

Import blocks: ~50 (1%)
Terraform apply: Many errors (trying to create existing resources)
```

### After Fixes
```
Classification Summary:
- NEW: 700 (20%)
- EXACT_MATCH: 2,400 (64%)
- DRIFTED: 600 (16%)
- ORPHANED: 300 (8%)

Import blocks: ~3,000 (80%)
Terraform apply: Much fewer errors
Warnings: "SUSPICIOUS CLASSIFICATION" may appear if < 80% success
```

---

## Troubleshooting

### Issue: Tests fail after implementing fixes

**Solution**:
```bash
# Check syntax errors
python -m py_compile src/iac/resource_comparator.py

# Check imports
python -c "from src.iac.resource_comparator import ResourceComparator; print('OK')"

# Run specific test
pytest tests/iac/test_resource_comparator.py::TestResourceComparator::test_classify_new_resource_not_in_target -v
```

### Issue: Still seeing high % of NEW resources

**Possible causes**:
1. Heuristic pattern doesn't match your naming convention
2. Target scan incomplete or from different environment
3. SCAN_SOURCE_NODE relationships still missing (proper fix needed)

**Action**:
```bash
# Check heuristic cleanup logs
grep "heuristic cleanup" /path/to/log.txt | head -20

# Manually test heuristic on sample ID
python3 << EOF
from src.iac.resource_comparator import ResourceComparator
from unittest.mock import MagicMock

comparator = ResourceComparator(MagicMock())
test_id = "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.DocumentDB/databaseAccounts/my_db_abc123_def456"
cleaned = comparator._heuristic_clean_abstracted_id(test_id)
print(f"Original: {test_id}")
print(f"Cleaned:  {cleaned}")
EOF
```

### Issue: Validation warnings appearing

**This is expected!** The warnings are there to alert you that the proper fix (SCAN_SOURCE_NODE relationships) is still needed.

**Action**: Proceed with Phase 2 (proper fix) from SMART_IMPORT_INVESTIGATION_SUMMARY.md

---

## Next Steps

After implementing immediate fixes:

1. **Phase 2: Proper Fix** (6-9 hours)
   - Investigate graph abstraction process
   - Fix SCAN_SOURCE_NODE relationship creation
   - Re-run abstraction
   - Verify 100% fix

2. **Phase 3: Regression Prevention** (5-6 hours)
   - Implement comprehensive test suite (TEST_CASES_SMART_IMPORT.md)
   - Add CI pipeline checks
   - Update documentation

---

## Success Criteria

✅ **Fixes are successful when**:
- Classification ratio: < 30% NEW, > 60% MATCHED
- Import blocks: > 80% of resources
- Terraform apply: < 10% errors related to false positives
- Logs: "heuristic cleanup applied" messages present
- Logs: No "CRITICAL" classification warnings

❌ **Fixes need adjustment when**:
- Classification ratio: > 70% NEW
- Import blocks: < 30% of resources
- Terraform apply: Many "resource already exists" errors
- Logs: "CRITICAL" classification warnings

---

## Quick Reference

### File Locations
- Code to modify: `src/iac/resource_comparator.py`
- Tests: `tests/iac/test_resource_comparator.py`
- Documentation: `ROOT_CAUSE_ANALYSIS_SMART_IMPORT.md`

### Key Methods Added
- `_heuristic_clean_abstracted_id()` - ID cleanup logic
- `_validate_classification_summary()` - Validation warnings

### Key Changes
- `_get_original_azure_id()` - Use heuristic on fallback
- `compare_resources()` - Call validation

### Testing Commands
```bash
# Unit tests
pytest tests/iac/test_resource_comparator.py -v

# With coverage
pytest tests/iac/test_resource_comparator.py --cov=src.iac.resource_comparator --cov-report=term-missing

# Debug mode
export LOG_LEVEL=DEBUG
pytest tests/iac/test_resource_comparator.py -v -s
```

---

Arrr, follow this guide and ye'll have the immediate fixes implemented in no time! 🏴‍☠️

**Remember**: These are MITIGATIONS, not complete solutions. The proper fix requires addressing SCAN_SOURCE_NODE relationships in the graph abstraction process (see Phase 2 in SMART_IMPORT_INVESTIGATION_SUMMARY.md).

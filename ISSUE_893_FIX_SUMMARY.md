# Issue #893 Fix: CLI --node-id Parameter Not Functional

## Problem Summary

The `--node-id` parameter in the CLI `generate-iac` command was returning zero results instead of querying Neo4j by node ID.

## Root Causes

1. **Type Mismatch**: Neo4j node IDs are integers (`id(node) = 12345`), but the code was treating them as strings
2. **Wrong Query**: Cypher query used `WHERE n.id IN $node_ids` (string property) instead of `WHERE id(n) IN $node_ids` (integer node ID function)
3. **Missing Conversion**: CLI passes node IDs as strings, but they needed to be converted to integers before querying

## Solution Implemented

### Code Changes

**File**: `src/iac/cli_handler.py`

**Lines 320-343**: Modified node ID validation and query construction

**Changes**:
1. Added integer conversion for node IDs (CLI provides strings)
2. Changed Cypher query from `WHERE n.id IN $node_ids` to `WHERE id(n) IN $node_ids`
3. Added diagnostic logging to show validated node IDs
4. Added clear error messages for invalid node ID formats

**Before**:
```python
# Validate node_ids are non-empty strings
validated_node_ids = []
for nid in node_ids:
    if not isinstance(nid, str) or not nid.strip():
        raise ValueError(f"Invalid node ID: {nid}")
    validated_node_ids.append(nid.strip())

# Use parameterized query with $node_ids parameter
filter_cypher = """
MATCH (n)
WHERE n.id IN $node_ids  # WRONG: Uses string property
...
"""
```

**After**:
```python
# Validate and convert node_ids to integers
validated_node_ids = []
for nid in node_ids:
    try:
        # Convert to integer (Neo4j node IDs are integers)
        node_id_int = int(nid) if isinstance(nid, str) else nid
        validated_node_ids.append(node_id_int)
        logger.debug(f"Validated node ID: {node_id_int} (from input: {nid})")
    except (ValueError, TypeError) as e:
        raise ValueError(f"Invalid node ID '{nid}': must be an integer") from e

# Use parameterized query with id() function for Neo4j integer node IDs
filter_cypher = """
MATCH (n)
WHERE id(n) IN $node_ids  # CORRECT: Uses id() function for integers
...
"""
filter_params = {"node_ids": validated_node_ids}
logger.info(f"Filtering by {len(validated_node_ids)} Neo4j node IDs: {validated_node_ids}")
```

### Test Changes

**File**: `tests/iac/test_cli_handler.py`

**Updated Tests** (lines 183-193, 280-293):
- Changed assertions from `WHERE n.id IN $node_ids` to `WHERE id(n) IN $node_ids`
- Added Issue #893 references to test assertions

**New Tests** (lines 384-473):
1. `test_node_id_integer_conversion`: Verifies string-to-integer conversion works correctly
2. `test_node_id_invalid_format`: Verifies clear error messages for invalid node IDs

## Testing

### Unit Tests
- ✅ `test_node_id_filter_single` - Single node ID query
- ✅ `test_node_id_filter_multiple` - Multiple node IDs query
- ✅ `test_node_id_filter_with_relationships` - Node IDs with relationships
- ✅ `test_node_id_integer_conversion` - String-to-integer conversion (NEW)
- ✅ `test_node_id_invalid_format` - Invalid format error handling (NEW)

### Manual Testing Command
```bash
# Test with single node ID
atg generate-iac --node-id 12345 --format terraform

# Test with multiple node IDs
atg generate-iac --node-id 12345 --node-id 67890 --format terraform
```

## Impact

- **Breaking Change**: None - this is a bug fix that makes existing functionality work
- **Backwards Compatibility**: Yes - still accepts node IDs as strings (CLI default)
- **Performance**: No impact - same query performance, now returns correct results
- **Security**: Maintains existing parameterized query protection (Issue #524)

## Related Issues

- Issue #524: Cypher injection prevention (parameterized queries maintained)
- Issue #893: CLI --node-id parameter not functional (FIXED)

## Files Modified

1. `src/iac/cli_handler.py` - Fixed node ID query logic
2. `tests/iac/test_cli_handler.py` - Updated and added tests

## Zero-BS Implementation

- ✅ No stubs or placeholders
- ✅ No dead code
- ✅ Every function works
- ✅ Diagnostic logging added
- ✅ Clear error messages
- ✅ Comprehensive test coverage

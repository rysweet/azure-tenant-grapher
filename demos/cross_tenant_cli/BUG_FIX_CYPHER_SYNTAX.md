# Bug Fix: Cypher Syntax Error in IaC Generation with --node-id

## Issue Summary

**Component**: `src/iac/cli_handler.py` (lines 94-106)
**Severity**: P0 - Critical Blocker
**Impact**: `atg generate-iac --node-id` command is completely broken

## Problem Description

When using `atg generate-iac` with `--node-id` parameters, the system generates invalid Cypher query syntax that causes Neo4j to reject the query with:

```
Error: {code: Neo.ClientError.Statement.SyntaxError}
{message: Query cannot conclude with WITH (must be a RETURN clause...}
"WITH DISTINCT n AS node"
```

## Root Cause

The current implementation in `src/iac/cli_handler.py` lines 94-106:

```python
if node_ids:
    node_id_list = ", ".join([f"'{nid}'" for nid in node_ids])
    filter_cypher = f"""
    MATCH (n)
    WHERE n.id IN [{node_id_list}]
    OPTIONAL MATCH (n)-[r1]-(connected)
    WITH DISTINCT n AS node
    UNION
    MATCH (n)
    WHERE n.id IN [{node_id_list}]
    OPTIONAL MATCH (n)-[r2]-(connected)
    WITH DISTINCT connected AS node
    WHERE node IS NOT NULL
    RETURN node AS r, [] AS rels
    """
```

**Problem**: The first part of the UNION query ends with `WITH DISTINCT n AS node` without a `RETURN` statement. This is invalid Cypher syntax.

## Proposed Fix

Replace the invalid query with a corrected version:

### Option 1: Fix UNION Query (Preserves Intent)

```python
if node_ids:
    node_id_list = ", ".join([f"'{nid}'" for nid in node_ids])
    filter_cypher = f"""
    MATCH (n)
    WHERE n.id IN [{node_id_list}]
    RETURN n AS r, [] AS rels
    UNION
    MATCH (n)
    WHERE n.id IN [{node_id_list}]
    OPTIONAL MATCH (n)-[]-(connected)
    WHERE connected IS NOT NULL
    RETURN DISTINCT connected AS r, [] AS rels
    """
```

### Option 2: Single Query with COALESCE (Simpler)

```python
if node_ids:
    node_id_list = ", ".join([f"'{nid}'" for nid in node_ids])
    filter_cypher = f"""
    MATCH (n)
    WHERE n.id IN [{node_id_list}]
    OPTIONAL MATCH (n)-[]-(connected)
    WITH DISTINCT coalesce(connected, n) AS node
    WHERE node IS NOT NULL
    RETURN node AS r, [] AS rels
    """
```

### Option 3: Use Cypher Subquery (Most Robust)

```python
if node_ids:
    node_id_list = ", ".join([f"'{nid}'" for nid in node_ids])
    filter_cypher = f"""
    CALL {{
        MATCH (n)
        WHERE n.id IN [{node_id_list}]
        RETURN n AS node
        UNION
        MATCH (n)
        WHERE n.id IN [{node_id_list}]
        OPTIONAL MATCH (n)-[]-(connected)
        WHERE connected IS NOT NULL
        RETURN connected AS node
    }}
    WITH DISTINCT node
    RETURN node AS r, [] AS rels
    """
```

## Recommended Solution

**Use Option 3** (Subquery approach) as it:
- Correctly implements the original intent (get nodes + connected nodes)
- Uses modern Cypher syntax
- Is most readable and maintainable
- Handles DISTINCT properly

## Testing Steps

1. **Create test case**:
```bash
uv run atg generate-iac \
  --tenant-id 3cd87a41-1f61-4aef-a212-cefdecd9a2d1 \
  --format terraform \
  --output ./test-output \
  --node-id "/subscriptions/.../SimuLand/.../USER1-Test"
```

2. **Expected Result**:
- No Cypher syntax errors
- IaC files generated successfully
- Includes the specified node and its connected resources

3. **Test with multiple node IDs**:
```bash
uv run atg generate-iac \
  --tenant-id ... \
  --node-id "id1" \
  --node-id "id2" \
  --node-id "id3"
```

## Implementation Checklist

- [ ] Update `src/iac/cli_handler.py` lines 94-106
- [ ] Add unit tests for node ID filtering
- [ ] Test with single node ID
- [ ] Test with multiple node IDs
- [ ] Test with resources that have relationships
- [ ] Update documentation/examples
- [ ] Verify no regression in other filter types

## Related Issues

This bug blocks:
- Cross-tenant IaC demo (this directory)
- Resource group-based IaC generation (workaround required)
- Any use case requiring selective IaC generation

## Additional Context

The intent of the original query was to:
1. Get all specified nodes by ID
2. Get all nodes connected to those nodes
3. Return both sets (specified + connected)

This is a common pattern for dependency closure, but the implementation had incorrect Cypher syntax.

## Files to Modify

- `src/iac/cli_handler.py` (lines 94-106): Fix the Cypher query
- `tests/iac/test_cli_handler.py` (new file): Add test cases

## Priority Justification

**P0 Critical** because:
- Feature is completely non-functional
- No workaround available
- Blocks multiple use cases
- Simple fix with clear solution
- Affects core IaC generation capability

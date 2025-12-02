# Safe Cypher Query Builder

## Overview

The `safe_cypher_builder` module provides utilities for constructing Cypher queries without injection vulnerabilities. It enforces parameterization, input validation, and safe identifier handling.

## Security Problem

Cypher injection occurs when user input is directly interpolated into query strings:

```python
# VULNERABLE CODE - DO NOT USE
query = f"MATCH (r:Resource) WHERE r.name = '{user_input}' RETURN r"
```

An attacker could provide: `' OR 1=1 OR r.name = '` to bypass filters.

## Solution

Use the `SafeCypherBuilder` for all dynamic query construction:

```python
# SAFE CODE - USE THIS
from src.utils.safe_cypher_builder import SafeCypherBuilder

builder = SafeCypherBuilder()
builder.add_filter("name", user_input)
query, params = builder.build_match_query()

# Execute with parameters
result = session.run(query, params)
```

## Features

### 1. Parameterized Queries

All values are passed as parameters, never interpolated:

```python
builder = SafeCypherBuilder()
builder.add_filter("type", "VirtualMachine")
builder.add_filter("location", "eastus")

query, params = builder.build_match_query()
# query: "MATCH (r:Resource) WHERE r.type = $filter_type_0 AND r.location = $filter_location_1 RETURN r"
# params: {"filter_type_0": "VirtualMachine", "filter_location_1": "eastus"}
```

### 2. Whitelist Validation

Only pre-approved filter keys are allowed:

```python
# Define allowed keys
builder = SafeCypherBuilder(allowed_keys={"name", "type", "location"})

# This works
builder.add_filter("name", "vm-1")

# This raises CypherInjectionError
builder.add_filter("malicious_key", "value")  # ❌ Not in allowed keys
```

### 3. Identifier Escaping

Safe escaping for property names from user input:

```python
from src.utils.safe_cypher_builder import escape_identifier

# Safely escape user-provided property name
prop_name = escape_identifier(user_property)  # Returns `user-property`
query = f"MATCH (r:Resource) RETURN r.{prop_name}"
```

### 4. Scope Filters for Cost Queries

Helper for building safe Azure scope filters:

```python
from src.utils.safe_cypher_builder import build_scope_filter

scope = "/subscriptions/abc123/resourceGroups/rg1"
filter_clause, param_name, param_value = build_scope_filter(scope)

query = f"""
MATCH (c:Cost)
WHERE {filter_clause}
RETURN c
"""
params = {param_name: param_value}
```

## Usage Examples

### Basic Resource Query

```python
from src.utils.safe_cypher_builder import SafeCypherBuilder

builder = SafeCypherBuilder()
builder.add_filter("type", "VirtualMachine")
builder.add_filter("location", "eastus")

query, params = builder.build_match_query(
    return_clause="properties(r) as props"
)

with session_manager.session() as session:
    result = session.run(query, params)
    resources = [dict(record["props"]) for record in result]
```

### Layer Query with Custom WHERE

```python
builder = SafeCypherBuilder(
    allowed_keys=SafeCypherBuilder.LAYER_FILTER_KEYS,
    node_label="Layer"
)

builder.add_filter("is_active", True)
builder.add_custom_where(
    "l.created_at > $min_date",
    {"min_date": "2024-01-01"}
)

query, params = builder.build_match_query(
    return_clause="l"
)
```

### Update with SET Clause

```python
from src.utils.safe_cypher_builder import build_set_clause

updates = {
    "name": "new-name",
    "description": "Updated description",
}

set_clause, params = build_set_clause(
    updates,
    allowed_keys={"name", "description", "tags", "metadata"}
)

query = f"""
MATCH (l:Layer {{layer_id: $layer_id}})
SET {set_clause}
RETURN l
"""

params["layer_id"] = layer_id

with session_manager.session() as session:
    result = session.run(query, params)
```

### Cost Query with Scope Filter

```python
from src.utils.safe_cypher_builder import build_scope_filter

scope = "/subscriptions/abc-123"
filter_clause, param_name, param_value = build_scope_filter(scope)

query = f"""
MATCH (c:Cost)
WHERE {filter_clause}
  AND c.date >= date($start_date)
  AND c.date <= date($end_date)
RETURN sum(c.actual_cost) AS total
"""

params = {
    param_name: param_value,
    "start_date": start_date.isoformat(),
    "end_date": end_date.isoformat(),
}

result = await tx.run(query, **params)
```

## Common Patterns

### Pattern 1: Resource Filtering

```python
def find_resources(
    resource_type: Optional[str] = None,
    filters: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Find resources with safe filtering"""

    builder = SafeCypherBuilder()

    # Add type filter if provided
    if resource_type:
        builder.add_filter("type", resource_type)

    # Add additional filters
    if filters:
        validate_filter_keys(filters, builder.allowed_keys)
        for key, value in filters.items():
            builder.add_filter(key, value)

    query, params = builder.build_match_query(
        return_clause="properties(r) as props"
    )

    with session_manager.session() as session:
        result = session.run(query, params)
        return [dict(record["props"]) for record in result]
```

### Pattern 2: Dynamic Property Updates

```python
async def update_layer(
    layer_id: str,
    **updates
) -> LayerMetadata:
    """Update layer properties safely"""

    # Whitelist allowed update fields
    ALLOWED_UPDATES = {"name", "description", "tags", "metadata", "is_locked"}

    # Build safe SET clause
    set_clause, params = build_set_clause(updates, ALLOWED_UPDATES)
    params["layer_id"] = layer_id

    query = f"""
    MATCH (l:Layer {{layer_id: $layer_id}})
    SET {set_clause}
    RETURN l
    """

    with session_manager.session() as session:
        result = session.run(query, params)
        return _node_to_layer_metadata(result.single()["l"])
```

### Pattern 3: Cost Aggregation

```python
@staticmethod
async def _fetch_cost_summary(
    tx,
    scope: str,
    start_date: date,
    end_date: date,
) -> CostSummary:
    """Fetch cost summary with safe scope filtering"""

    # Build safe scope filter
    filter_clause, param_name, param_value = build_scope_filter(scope)

    query = f"""
    MATCH (c:Cost)
    WHERE {filter_clause}
        AND c.date >= date($start_date)
        AND c.date <= date($end_date)
    WITH sum(c.actual_cost) AS total,
         collect(DISTINCT c.currency)[0] AS currency,
         count(DISTINCT c.resource_id) AS resource_count
    RETURN total, currency, resource_count
    """

    result = await tx.run(
        query,
        **{
            param_name: param_value,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
        }
    )

    record = await result.single()
    return CostSummary(...)
```

## Migration Guide

### Before (Vulnerable)

```python
# OLD CODE - Vulnerable to injection
def find_resources(filters: Dict[str, Any]):
    where_clauses = []
    for key, value in filters.items():
        where_clauses.append(f"r.{key} = '{value}'")  # ❌ VULNERABLE

    where_clause = " AND ".join(where_clauses)
    query = f"MATCH (r:Resource) WHERE {where_clause} RETURN r"

    result = session.run(query)
```

### After (Secure)

```python
# NEW CODE - Safe from injection
def find_resources(filters: Dict[str, Any]):
    builder = SafeCypherBuilder()

    for key, value in filters.items():
        builder.add_filter(key, value)  # ✅ SAFE - validated & parameterized

    query, params = builder.build_match_query()
    result = session.run(query, params)
```

## API Reference

### SafeCypherBuilder

Main class for building safe queries.

#### Constructor

```python
SafeCypherBuilder(
    allowed_keys: Optional[Set[str]] = None,
    node_label: str = "Resource"
)
```

**Parameters:**
- `allowed_keys`: Set of allowed filter keys (defaults to RESOURCE_FILTER_KEYS)
- `node_label`: Default node label for queries

#### Methods

##### `add_filter(key: str, value: Any) -> SafeCypherBuilder`

Add a parameterized filter condition.

**Raises:** `CypherInjectionError` if key not in allowed_keys

##### `add_custom_where(clause: str, params: Optional[Dict]) -> SafeCypherBuilder`

Add custom WHERE clause (must use parameterization).

**Raises:** `CypherInjectionError` if clause uses string interpolation

##### `build_match_query(node_label: Optional[str] = None, return_clause: str = "r", additional_where: Optional[str] = None) -> Tuple[str, Dict[str, Any]]`

Build complete MATCH query with WHERE clauses.

**Returns:** Tuple of (query_string, parameters)

##### `build_where_clause() -> Tuple[str, Dict[str, Any]]`

Build just the WHERE clause and parameters.

**Returns:** Tuple of (where_clause, parameters)

##### `reset() -> SafeCypherBuilder`

Reset builder state for reuse.

### Helper Functions

#### `build_scope_filter(scope: str) -> Tuple[str, str, str]`

Build safe Azure scope filter for cost queries.

**Returns:** Tuple of (filter_clause, param_name, param_value)

#### `build_set_clause(updates: Dict[str, Any], allowed_keys: Set[str]) -> Tuple[str, Dict[str, Any]]`

Build safe SET clause for UPDATE operations.

**Returns:** Tuple of (set_clause, parameters)

#### `escape_identifier(identifier: str) -> str`

Escape identifier by backtick-quoting.

**Raises:** `CypherInjectionError` if identifier contains unsafe characters

#### `validate_filter_keys(filters: Dict[str, Any], allowed_keys: Set[str]) -> None`

Validate all filter keys are allowed.

**Raises:** `CypherInjectionError` if any key is not allowed

## Testing

See `tests/test_safe_cypher_builder.py` for comprehensive test coverage including:
- Injection prevention tests
- Whitelist validation
- Parameter binding
- Edge cases and error conditions

## Related

- Issue #532: Cypher Injection Vulnerabilities
- Security review: [Security Pattern Analysis](../docs/security/cypher-injection-prevention.md)

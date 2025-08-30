# Fix: Property Preservation During Updates

## Problem
When `atg build` is re-run, if property fetching fails or is disabled, existing properties in the database are overwritten with empty `{}`.

## Root Cause
In `azure_discovery_service.py` line 203:
```python
"properties": {},  # Will be populated if parallel fetching enabled
```

This creates resources with empty properties that then overwrite existing data via:
```cypher
MERGE (r:Resource {id: $props.id})
SET r += $props  # This overwrites properties with {}
```

## Solution

### Option 1: Don't Include Empty Properties in Update (RECOMMENDED)
```python
# In resource_processor.py, before line 274
if "properties" in resource_data and resource_data["properties"] == {}:
    # Don't overwrite existing properties with empty
    del resource_data["properties"]
```

### Option 2: Preserve Existing Properties on Fetch Failure
```python
# In azure_discovery_service.py, line 505
# Instead of returning resource with empty properties
# Query existing properties from DB and preserve them
existing_props = await self._get_existing_properties(resource_id)
resource["properties"] = existing_props or {}
```

### Option 3: Add Merge Semantics
```cypher
# Instead of SET r += $props
# Use conditional update for properties
SET r.id = $props.id,
    r.name = $props.name,
    r.properties = CASE
        WHEN $props.properties IS NOT NULL AND $props.properties <> {}
        THEN $props.properties
        ELSE r.properties
    END
```

## Testing Required
1. Run build with properties
2. Disable parallel fetching and re-run
3. Verify properties are preserved, not lost

## Impact
- Prevents data loss during re-runs
- Preserves expensive LLM-generated descriptions
- Maintains data integrity across updates

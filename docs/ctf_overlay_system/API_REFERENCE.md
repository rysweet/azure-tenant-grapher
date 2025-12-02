# CTF Overlay System API Reference

## Overview

This document provides complete API reference for the CTF Overlay System, including:
- Neo4j Cypher queries for CTF operations
- Python APIs for TerraformEmitter and TerraformImporter
- Common query patterns and examples

## Neo4j Cypher API

### Resource Creation and Updates

#### Create CTF Resource

```cypher
// Create or update a resource with CTF properties
MERGE (r:Resource {id: $id})
SET r.name = $name,
    r.resource_type = $resource_type,
    r.location = $location,
    r.layer_id = $layer_id,
    r.ctf_exercise = $ctf_exercise,
    r.ctf_scenario = $ctf_scenario,
    r.ctf_role = $ctf_role,
    r.created_at = COALESCE(r.created_at, datetime()),
    r.updated_at = datetime()
RETURN r
```

**Parameters:**
```json
{
  "id": "vm-a1b2c3d4",
  "name": "target-vm-001",
  "resource_type": "VirtualMachine",
  "location": "eastus",
  "layer_id": "default",
  "ctf_exercise": "M003",
  "ctf_scenario": "v2-cert",
  "ctf_role": "target"
}
```

**Returns:**
```json
{
  "r": {
    "id": "vm-a1b2c3d4",
    "name": "target-vm-001",
    "resource_type": "VirtualMachine",
    "location": "eastus",
    "layer_id": "default",
    "ctf_exercise": "M003",
    "ctf_scenario": "v2-cert",
    "ctf_role": "target",
    "created_at": "2025-12-02T10:30:00Z",
    "updated_at": "2025-12-02T10:30:00Z"
  }
}
```

**Idempotency:** Safe to run multiple times. First run creates, subsequent runs update.

#### Update CTF Properties

```cypher
// Update CTF properties on existing resource
MATCH (r:Resource {id: $id})
SET r.ctf_role = $new_role,
    r.updated_at = datetime()
RETURN r
```

**Parameters:**
```json
{
  "id": "vm-a1b2c3d4",
  "new_role": "infrastructure"
}
```

#### Batch Create Resources

```cypher
// Create multiple resources in one transaction
UNWIND $resources AS resource
MERGE (r:Resource {id: resource.id})
SET r.name = resource.name,
    r.resource_type = resource.resource_type,
    r.location = resource.location,
    r.layer_id = resource.layer_id,
    r.ctf_exercise = resource.ctf_exercise,
    r.ctf_scenario = resource.ctf_scenario,
    r.ctf_role = resource.ctf_role,
    r.updated_at = datetime()
RETURN count(r) AS created_count
```

**Parameters:**
```json
{
  "resources": [
    {
      "id": "vm-target-001",
      "name": "target-vm",
      "resource_type": "VirtualMachine",
      "location": "eastus",
      "layer_id": "default",
      "ctf_exercise": "M003",
      "ctf_scenario": "v2-cert",
      "ctf_role": "target"
    },
    {
      "id": "vnet-001",
      "name": "ctf-vnet",
      "resource_type": "VirtualNetwork",
      "location": "eastus",
      "layer_id": "default",
      "ctf_exercise": "M003",
      "ctf_scenario": "v2-cert",
      "ctf_role": "infrastructure"
    }
  ]
}
```

### Querying CTF Resources

#### Find All Resources in a Scenario

```cypher
// Get all resources for a specific CTF scenario
MATCH (r:Resource {layer_id: $layer_id})
WHERE r.ctf_exercise = $exercise
  AND r.ctf_scenario = $scenario
RETURN r
ORDER BY r.ctf_role, r.name
```

**Parameters:**
```json
{
  "layer_id": "default",
  "exercise": "M003",
  "scenario": "v2-cert"
}
```

**Returns:** All resources in M003 v2-cert scenario, ordered by role then name.

**Performance:** O(1) index lookup on `layer_id`, then filters. ~5ms for 10K resources.

#### Find Resources by Role

```cypher
// Get all target VMs in a scenario
MATCH (r:Resource {layer_id: $layer_id})
WHERE r.ctf_exercise = $exercise
  AND r.ctf_scenario = $scenario
  AND r.ctf_role = $role
  AND r.resource_type = $resource_type
RETURN r.id, r.name, r.location
```

**Parameters:**
```json
{
  "layer_id": "default",
  "exercise": "M003",
  "scenario": "v2-cert",
  "role": "target",
  "resource_type": "VirtualMachine"
}
```

**Use Case:** Find all target VMs for attack simulation.

#### List All Scenarios in a Layer

```cypher
// Get distinct scenarios in a layer
MATCH (r:Resource {layer_id: $layer_id})
WHERE r.ctf_exercise IS NOT NULL
  AND r.ctf_scenario IS NOT NULL
RETURN DISTINCT r.ctf_exercise AS exercise,
                r.ctf_scenario AS scenario,
                count(r) AS resource_count
ORDER BY exercise, scenario
```

**Parameters:**
```json
{
  "layer_id": "default"
}
```

**Returns:**
```json
[
  {
    "exercise": "M003",
    "scenario": "v2-cert",
    "resource_count": 5
  },
  {
    "exercise": "M003",
    "scenario": "v3-oauth",
    "resource_count": 7
  }
]
```

**Use Case:** Dashboard showing all active CTF scenarios.

#### Count Resources by Role

```cypher
// Count resources by role in a scenario
MATCH (r:Resource {layer_id: $layer_id})
WHERE r.ctf_exercise = $exercise
  AND r.ctf_scenario = $scenario
RETURN r.ctf_role AS role,
       count(r) AS count
ORDER BY count DESC
```

**Parameters:**
```json
{
  "layer_id": "default",
  "exercise": "M003",
  "scenario": "v2-cert"
}
```

**Returns:**
```json
[
  {"role": "target", "count": 2},
  {"role": "infrastructure", "count": 3},
  {"role": "attacker", "count": 1}
]
```

#### Find Resources by Resource Type

```cypher
// Get all VMs in a scenario
MATCH (r:Resource {layer_id: $layer_id})
WHERE r.ctf_exercise = $exercise
  AND r.ctf_scenario = $scenario
  AND r.resource_type = $resource_type
RETURN r.id, r.name, r.ctf_role
```

**Parameters:**
```json
{
  "layer_id": "default",
  "exercise": "M003",
  "scenario": "v2-cert",
  "resource_type": "VirtualMachine"
}
```

**Use Case:** Find all VMs for SSH access provisioning.

#### Search Resources by Name Pattern

```cypher
// Find resources matching a name pattern
MATCH (r:Resource {layer_id: $layer_id})
WHERE r.ctf_exercise = $exercise
  AND r.name CONTAINS $name_pattern
RETURN r
```

**Parameters:**
```json
{
  "layer_id": "default",
  "exercise": "M003",
  "name_pattern": "target"
}
```

**Use Case:** Find all resources with "target" in their name.

### Deletion and Cleanup

#### Delete Entire Scenario

```cypher
// Delete all resources in a CTF scenario
MATCH (r:Resource {layer_id: $layer_id})
WHERE r.ctf_exercise = $exercise
  AND r.ctf_scenario = $scenario
DETACH DELETE r
```

**Parameters:**
```json
{
  "layer_id": "default",
  "exercise": "M003",
  "scenario": "v2-cert"
}
```

**Effect:** Removes all resources (and their relationships) for the specified scenario.

**Idempotency:** Safe to run multiple times. No error if resources already deleted.

**Performance:** O(m) where m is number of matching resources. ~20ms for 100 resources.

#### Delete Entire Layer

```cypher
// Delete all resources in a layer
MATCH (r:Resource {layer_id: $layer_id})
DETACH DELETE r
```

**Parameters:**
```json
{
  "layer_id": "default"
}
```

**WARNING:** This deletes ALL resources in the layer, including multiple scenarios.

**Best Practice:** Use scenario-specific deletion unless cleaning up entire layer.

#### Delete Resources by Role

```cypher
// Delete only target resources in a scenario
MATCH (r:Resource {layer_id: $layer_id})
WHERE r.ctf_exercise = $exercise
  AND r.ctf_scenario = $scenario
  AND r.ctf_role = $role
DETACH DELETE r
```

**Parameters:**
```json
{
  "layer_id": "default",
  "exercise": "M003",
  "scenario": "v2-cert",
  "role": "target"
}
```

**Use Case:** Partial cleanup (e.g., remove targets but keep infrastructure).

#### Delete Single Resource

```cypher
// Delete a specific resource by ID
MATCH (r:Resource {id: $id})
DETACH DELETE r
```

**Parameters:**
```json
{
  "id": "vm-a1b2c3d4"
}
```

**Use Case:** Remove individual resource from scenario.

### Advanced Queries

#### Find Overlapping Resources

```cypher
// Find resources used in multiple scenarios
MATCH (r:Resource {layer_id: $layer_id})
WHERE r.ctf_exercise IS NOT NULL
  AND r.ctf_scenario IS NOT NULL
WITH r.id AS resource_id,
     collect(DISTINCT r.ctf_scenario) AS scenarios
WHERE size(scenarios) > 1
RETURN resource_id, scenarios
```

**Parameters:**
```json
{
  "layer_id": "default"
}
```

**Returns:** Resources shared across multiple scenarios (unusual but possible).

#### Resource Summary by Exercise

```cypher
// Aggregate resource counts by exercise
MATCH (r:Resource {layer_id: $layer_id})
WHERE r.ctf_exercise IS NOT NULL
RETURN r.ctf_exercise AS exercise,
       count(DISTINCT r.ctf_scenario) AS scenario_count,
       count(r) AS total_resources,
       collect(DISTINCT r.resource_type) AS resource_types
ORDER BY exercise
```

**Parameters:**
```json
{
  "layer_id": "default"
}
```

**Returns:** High-level summary of CTF exercises in a layer.

#### Find Resources Missing CTF Properties

```cypher
// Audit: Find resources without complete CTF metadata
MATCH (r:Resource {layer_id: $layer_id})
WHERE r.ctf_exercise IS NOT NULL
  AND (r.ctf_scenario IS NULL OR r.ctf_role IS NULL)
RETURN r.id, r.name,
       r.ctf_exercise,
       r.ctf_scenario,
       r.ctf_role
```

**Use Case:** Data quality check - find incomplete CTF annotations.

## Python API

### TerraformEmitter API

**Location:** `src/terraform_emitter.py`

#### generate_ctf_scenario()

```python
def generate_ctf_scenario(
    exercise: str,
    scenario: str,
    layer_id: str = "default",
    location: str = "eastus",
    vm_size: str = "Standard_B2s"
) -> str:
    """Generate Terraform configuration for CTF scenario.

    Args:
        exercise: Exercise identifier (e.g., "M003")
        scenario: Scenario variant (e.g., "v2-cert")
        layer_id: Layer identifier for isolation (default: "default")
        location: Azure region (default: "eastus")
        vm_size: VM SKU (default: "Standard_B2s")

    Returns:
        Terraform configuration as string

    Example:
        >>> emitter = TerraformEmitter()
        >>> terraform = emitter.generate_ctf_scenario(
        ...     exercise="M003",
        ...     scenario="v2-cert",
        ...     layer_id="test-layer"
        ... )
        >>> print(terraform)
        resource "azurerm_virtual_machine" "target" {
          name = "vm-test-layer-M003-v2-cert-target"
          tags = {
            layer_id = "test-layer"
            ctf_exercise = "M003"
            ctf_scenario = "v2-cert"
            ctf_role = "target"
          }
        }
    """
    pass  # Implementation details
```

**Key Features:**
- Generates Terraform with CTF tags (layer_id, exercise, scenario, role)
- Layer-based naming prevents conflicts
- Idempotent (same inputs → same output)

### TerraformImporter API

**Location:** `src/services/terraform_importer.py`

#### import_from_state()

```python
def import_from_state(
    state_file: str,
    layer_id: str = "default",
    neo4j_driver: Optional[Neo4jDriver] = None
) -> Dict[str, int]:
    """Import Terraform state into Neo4j with CTF properties.

    Args:
        state_file: Path to terraform.tfstate file
        layer_id: Layer identifier (default: "default")
        neo4j_driver: Neo4j driver instance (default: uses global)

    Returns:
        Dictionary with import statistics:
        {
            "resources_created": 5,
            "resources_updated": 2,
            "errors": 0
        }

    Raises:
        FileNotFoundError: If state_file doesn't exist
        ValueError: If state file is invalid JSON
        Neo4jError: If Neo4j connection fails

    Example:
        >>> importer = TerraformImporter()
        >>> stats = importer.import_from_state(
        ...     state_file="terraform.tfstate",
        ...     layer_id="test-layer"
        ... )
        >>> print(f"Created {stats['resources_created']} resources")
        Created 5 resources
    """
    pass  # Implementation details
```

**Key Features:**
- Parses Terraform state JSON
- Extracts CTF properties from tags
- Uses MERGE for idempotency
- Returns detailed statistics

#### import_from_plan()

```python
def import_from_plan(
    plan_file: str,
    layer_id: str = "default",
    dry_run: bool = False
) -> Dict[str, Any]:
    """Import Terraform plan (preview without creating resources).

    Args:
        plan_file: Path to terraform plan JSON
        layer_id: Layer identifier
        dry_run: If True, don't create resources (validation only)

    Returns:
        Dictionary with plan summary:
        {
            "resources_to_create": 5,
            "resources_to_update": 2,
            "resources_to_delete": 1,
            "validation_errors": []
        }

    Example:
        >>> importer = TerraformImporter()
        >>> summary = importer.import_from_plan(
        ...     plan_file="terraform.plan.json",
        ...     dry_run=True
        ... )
        >>> print(f"Will create {summary['resources_to_create']} resources")
        Will create 5 resources
    """
    pass  # Implementation details
```

**Use Case:** Validate Terraform plan before applying.

### Neo4jQueryHelper API

**Location:** `src/services/neo4j_query_helper.py`

#### find_ctf_resources()

```python
def find_ctf_resources(
    layer_id: str,
    exercise: Optional[str] = None,
    scenario: Optional[str] = None,
    role: Optional[str] = None,
    resource_type: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Find CTF resources with optional filters.

    Args:
        layer_id: Layer identifier (required)
        exercise: Filter by exercise (optional)
        scenario: Filter by scenario (optional)
        role: Filter by role (optional)
        resource_type: Filter by resource type (optional)

    Returns:
        List of resource dictionaries

    Example:
        >>> helper = Neo4jQueryHelper()
        >>> targets = helper.find_ctf_resources(
        ...     layer_id="default",
        ...     exercise="M003",
        ...     scenario="v2-cert",
        ...     role="target"
        ... )
        >>> print(f"Found {len(targets)} target VMs")
        Found 2 target VMs
    """
    pass  # Implementation details
```

#### delete_ctf_scenario()

```python
def delete_ctf_scenario(
    layer_id: str,
    exercise: str,
    scenario: str,
    dry_run: bool = False
) -> Dict[str, int]:
    """Delete entire CTF scenario.

    Args:
        layer_id: Layer identifier
        exercise: Exercise identifier
        scenario: Scenario variant
        dry_run: If True, return count without deleting

    Returns:
        Dictionary with deletion statistics:
        {
            "resources_deleted": 5,
            "relationships_deleted": 8
        }

    Example:
        >>> helper = Neo4jQueryHelper()
        >>> stats = helper.delete_ctf_scenario(
        ...     layer_id="default",
        ...     exercise="M003",
        ...     scenario="v2-cert"
        ... )
        >>> print(f"Deleted {stats['resources_deleted']} resources")
        Deleted 5 resources
    """
    pass  # Implementation details
```

## Common Query Patterns

### Pattern 1: Create-Import-Query-Delete Workflow

```python
# Step 1: Generate Terraform
emitter = TerraformEmitter()
terraform = emitter.generate_ctf_scenario(
    exercise="M003",
    scenario="v2-cert",
    layer_id="demo"
)

# Step 2: Apply Terraform (external command)
# subprocess.run(["terraform", "apply"])

# Step 3: Import into Neo4j
importer = TerraformImporter()
stats = importer.import_from_state(
    state_file="terraform.tfstate",
    layer_id="demo"
)
print(f"Imported {stats['resources_created']} resources")

# Step 4: Query resources
helper = Neo4jQueryHelper()
resources = helper.find_ctf_resources(
    layer_id="demo",
    exercise="M003",
    scenario="v2-cert"
)
print(f"Found {len(resources)} resources")

# Step 5: Cleanup
cleanup_stats = helper.delete_ctf_scenario(
    layer_id="demo",
    exercise="M003",
    scenario="v2-cert"
)
print(f"Deleted {cleanup_stats['resources_deleted']} resources")
```

### Pattern 2: Multi-Scenario Management

```python
# Create multiple scenarios in same layer
scenarios = ["v2-cert", "v3-oauth", "v4-saml"]

for scenario in scenarios:
    terraform = emitter.generate_ctf_scenario(
        exercise="M003",
        scenario=scenario,
        layer_id="multi-test"
    )
    # Deploy and import each scenario

# Query all scenarios
helper = Neo4jQueryHelper()
all_resources = helper.find_ctf_resources(
    layer_id="multi-test",
    exercise="M003"
)
print(f"Total resources across all scenarios: {len(all_resources)}")

# Group by scenario
from collections import defaultdict
by_scenario = defaultdict(list)
for resource in all_resources:
    by_scenario[resource['ctf_scenario']].append(resource)

for scenario, resources in by_scenario.items():
    print(f"{scenario}: {len(resources)} resources")
```

### Pattern 3: Incremental Updates

```python
# Initial creation
terraform = emitter.generate_ctf_scenario(
    exercise="M003",
    scenario="v2-cert",
    layer_id="incremental"
)

# Deploy and import
importer.import_from_state("terraform.tfstate", layer_id="incremental")

# Update role of a specific resource
driver = neo4j_driver
driver.execute_query(
    """
    MATCH (r:Resource {id: $id})
    SET r.ctf_role = $new_role, r.updated_at = datetime()
    RETURN r
    """,
    id="vm-target-001",
    new_role="infrastructure"
)

# Re-import (idempotent - updates existing resources)
importer.import_from_state("terraform.tfstate", layer_id="incremental")
```

## Performance Optimization Tips

### 1. Use Batch Operations

**Bad:**
```python
# Creating resources one at a time
for resource in resources:
    driver.execute_query(
        "MERGE (r:Resource {id: $id}) SET r.name = $name",
        id=resource['id'],
        name=resource['name']
    )
```

**Good:**
```python
# Create all resources in single transaction
driver.execute_query(
    """
    UNWIND $resources AS resource
    MERGE (r:Resource {id: resource.id})
    SET r.name = resource.name, r.updated_at = datetime()
    """,
    resources=resources
)
```

**Improvement:** 10-50x faster for large batches.

### 2. Filter Early with Indexed Properties

**Bad:**
```cypher
// Scans all resources, then filters
MATCH (r:Resource)
WHERE r.layer_id = 'default'
  AND r.ctf_exercise = 'M003'
RETURN r
```

**Good:**
```cypher
// Index lookup first, then filter
MATCH (r:Resource {layer_id: 'default'})
WHERE r.ctf_exercise = 'M003'
RETURN r
```

**Improvement:** Uses index on `layer_id` for O(1) lookup.

### 3. Avoid Unnecessary RETURN Clauses

**Bad:**
```cypher
// Returns full resource objects (expensive)
MATCH (r:Resource {layer_id: 'default'})
WHERE r.ctf_exercise = 'M003'
RETURN r
```

**Good:**
```cypher
// Returns only needed fields
MATCH (r:Resource {layer_id: 'default'})
WHERE r.ctf_exercise = 'M003'
RETURN r.id, r.name, r.ctf_role
```

**Improvement:** Reduces data transfer by 60-80%.

## Error Handling

### Neo4j Connection Errors

```python
from neo4j.exceptions import ServiceUnavailable

try:
    resources = helper.find_ctf_resources(layer_id="default")
except ServiceUnavailable:
    print("Neo4j database is not running")
    # Fallback or retry logic
```

### Invalid Query Parameters

```python
def validate_layer_id(layer_id: str):
    """Validate layer_id before query"""
    if not re.match(r'^[a-zA-Z0-9_-]+$', layer_id):
        raise ValueError(f"Invalid layer_id: {layer_id}")

# Use validation
try:
    validate_layer_id(user_input)
    resources = helper.find_ctf_resources(layer_id=user_input)
except ValueError as e:
    print(f"Validation error: {e}")
```

### Terraform Import Errors

```python
try:
    stats = importer.import_from_state(
        state_file="terraform.tfstate",
        layer_id="test"
    )
except FileNotFoundError:
    print("Terraform state file not found")
except ValueError as e:
    print(f"Invalid state file: {e}")
```

## Testing Examples

### Unit Test: Query Resources

```python
def test_find_ctf_resources():
    """Test finding resources by scenario"""

    # Create test resources
    driver.execute_query(
        """
        MERGE (r:Resource {id: 'test-vm-001'})
        SET r.layer_id = 'test',
            r.ctf_exercise = 'M003',
            r.ctf_scenario = 'v2-cert',
            r.ctf_role = 'target'
        """
    )

    # Query resources
    helper = Neo4jQueryHelper()
    resources = helper.find_ctf_resources(
        layer_id="test",
        exercise="M003",
        scenario="v2-cert"
    )

    # Validate
    assert len(resources) == 1
    assert resources[0]['id'] == 'test-vm-001'

    # Cleanup
    driver.execute_query(
        "MATCH (r:Resource {id: 'test-vm-001'}) DETACH DELETE r"
    )
```

### Integration Test: Full Workflow

```python
def test_ctf_scenario_lifecycle():
    """Test complete CTF scenario workflow"""

    layer_id = f"test-{uuid.uuid4()}"

    try:
        # 1. Generate Terraform
        terraform = emitter.generate_ctf_scenario(
            exercise="M003",
            scenario="v2-cert",
            layer_id=layer_id
        )
        assert "layer_id" in terraform

        # 2. Import (simulated deployment)
        importer.import_from_state(
            state_file="test_terraform.tfstate",
            layer_id=layer_id
        )

        # 3. Query resources
        resources = helper.find_ctf_resources(layer_id=layer_id)
        assert len(resources) > 0

        # 4. Cleanup
        stats = helper.delete_ctf_scenario(
            layer_id=layer_id,
            exercise="M003",
            scenario="v2-cert"
        )
        assert stats['resources_deleted'] == len(resources)

    finally:
        # Ensure cleanup even if test fails
        driver.execute_query(
            "MATCH (r:Resource {layer_id: $layer_id}) DETACH DELETE r",
            layer_id=layer_id
        )
```

## Summary

**Neo4j Cypher API:**
- Properties-only queries (no relationship traversals)
- Indexed lookups for performance
- Idempotent operations (MERGE, SET, DETACH DELETE)

**Python API:**
- TerraformEmitter: Generate Terraform with CTF tags
- TerraformImporter: Import Terraform state into Neo4j
- Neo4jQueryHelper: High-level query interface

**Performance:**
- Use batch operations for multiple resources
- Filter with indexed properties first
- Return only needed fields

**Testing:**
- Unit tests for individual queries
- Integration tests for full workflows
- Always cleanup test data (use try/finally)

For more examples, see:
- `tests/test_scenarios_M003.py` - Real-world scenario tests
- `tests/test_ctf_properties.py` - Unit tests for CTF queries

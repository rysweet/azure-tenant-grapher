# Module: CTF Annotation Service

## Purpose

Manage CTF (Capture The Flag) annotations in Neo4j graph database. Provides CRUD operations for adding, querying, and removing CTF-specific properties from resource nodes.

**Single Responsibility**: Neo4j operations for CTF metadata only - no Terraform parsing, no deployment orchestration.

## Contract

### Inputs

```python
# Annotation operations
node_id: str                    # Neo4j internal node ID
annotation: CTFAnnotation       # CTF properties to add

# Query operations
exercise: str | None            # Filter by exercise name
scenario: str | None            # Filter by scenario name
layer_id: str                   # Target layer (default: "default")

# Bulk operations
annotations: List[CTFAnnotation] # Multiple annotations in transaction
```

### Outputs

```python
# Single annotation
bool                            # Success/failure

# Bulk annotation
tuple[int, List[str]]          # (success_count, error_messages)

# Query operations
List[Dict[str, Any]]           # List of annotated resources with properties

# Clear operations
int                             # Number of nodes cleared

# Statistics
Dict[str, Any]                  # Aggregated CTF statistics
```

### Side Effects

- **Neo4j writes**: Adds/removes properties on existing nodes
- **Neo4j queries**: Reads node properties and relationships
- **Transactions**: All operations are transactional (all-or-nothing)
- **Indexes**: Queries use indexes on ctf_exercise + ctf_scenario + layer_id

**Important**: This service NEVER creates or deletes nodes, only modifies properties.

## Data Models

### CTFAnnotation

```python
@dataclass
class CTFAnnotation:
    """CTF properties for a resource."""
    node_id: str                    # Neo4j node ID (internal)
    resource_id: str                # Abstracted resource ID
    resource_type: str              # VirtualMachine, StorageAccount, etc.
    resource_name: str              # Human-readable name
    ctf_exercise: str               # Exercise identifier (e.g., "M003")
    ctf_scenario: str               # Scenario identifier (e.g., "v2-cert")
    ctf_role: str | None            # Role: target, decoy, infrastructure
    ctf_terraform_address: str      # Terraform address (e.g., azurerm_storage_account.example)
    ctf_terraform_source: str       # Source location (e.g., main.tf:45)
```

### Neo4j Schema

**Node properties added**:
```cypher
(:Resource {
  id: "vm-a1b2c3d4",              // Existing
  resource_type: "VirtualMachine", // Existing
  layer_id: "default",             // Existing

  // CTF properties (added by this service)
  ctf_exercise: "M003",
  ctf_scenario: "v2-cert",
  ctf_role: "target",
  ctf_terraform_address: "azurerm_virtual_machine.attacker",
  ctf_terraform_source: "main.tf:127"
})
```

**Indexes required**:
```cypher
// Fast CTF queries
CREATE INDEX ctf_exercise_scenario_layer IF NOT EXISTS
FOR (r:Resource)
ON (r.ctf_exercise, r.ctf_scenario, r.layer_id)

// Statistics queries
CREATE INDEX ctf_exercise_layer IF NOT EXISTS
FOR (r:Resource)
ON (r.ctf_exercise, r.layer_id)
```

## Public API

### CTFAnnotationService

```python
class CTFAnnotationService:
    """Service for managing CTF annotations in Neo4j.

    Philosophy:
    - Single responsibility: Neo4j CTF property management
    - Standard library + neo4j driver only
    - Self-contained and regeneratable
    """

    def __init__(self, driver: Driver):
        """Initialize with Neo4j driver.

        Args:
            driver: Neo4j driver instance (connection pooled)
        """
        self.driver = driver

    async def annotate_node(
        self,
        node_id: str,
        annotation: CTFAnnotation,
    ) -> bool:
        """Add CTF properties to a single node.

        Args:
            node_id: Neo4j internal node ID
            annotation: CTF properties to add

        Returns:
            True if successful, False if node not found

        Raises:
            Neo4jError: On database errors
            ValueError: If node_id or annotation invalid
        """

    async def annotate_nodes_bulk(
        self,
        annotations: List[CTFAnnotation],
    ) -> tuple[int, List[str]]:
        """Bulk annotate nodes in single transaction.

        All annotations succeed or all fail (atomic).

        Args:
            annotations: List of CTF annotations to add

        Returns:
            (success_count, error_messages)
            - success_count: Number of nodes annotated
            - error_messages: Errors for failed nodes

        Raises:
            Neo4jError: On transaction failure (all rolled back)
        """

    async def query_ctf_resources(
        self,
        exercise: str | None = None,
        scenario: str | None = None,
        layer_id: str = "default",
        tenant_id: str | None = None,
    ) -> List[Dict[str, Any]]:
        """Query nodes with CTF annotations.

        Args:
            exercise: Filter by exercise (None = all)
            scenario: Filter by scenario (None = all)
            layer_id: Target layer
            tenant_id: Filter by tenant (None = all)

        Returns:
            List of resource dictionaries with CTF properties

        Example return:
            [
                {
                    "node_id": "12345",
                    "id": "vm-a1b2c3d4",
                    "resource_type": "VirtualMachine",
                    "name": "attacker-vm",
                    "ctf_exercise": "M003",
                    "ctf_scenario": "v2-cert",
                    "ctf_role": "target",
                    "ctf_terraform_address": "azurerm_virtual_machine.attacker",
                },
                ...
            ]
        """

    async def clear_ctf_annotations(
        self,
        exercise: str,
        scenario: str | None = None,
        layer_id: str = "default",
    ) -> int:
        """Remove CTF properties from nodes.

        Removes all ctf_* properties matching filters.

        Args:
            exercise: Exercise to clear (required)
            scenario: Scenario to clear (None = all scenarios)
            layer_id: Layer to clear from

        Returns:
            Number of nodes cleared

        Raises:
            Neo4jError: On database errors
        """

    async def get_ctf_statistics(
        self,
        exercise: str | None = None,
        layer_id: str = "default",
    ) -> Dict[str, Any]:
        """Get statistics about CTF annotations.

        Args:
            exercise: Filter by exercise (None = all)
            layer_id: Target layer

        Returns:
            Statistics dictionary with:
            - total_resources: Total CTF-annotated nodes
            - by_exercise: Count per exercise
            - by_scenario: Count per scenario
            - by_resource_type: Count per resource type
            - by_role: Count per CTF role

        Example return:
            {
                "total_resources": 47,
                "by_exercise": {"M003": 47},
                "by_scenario": {"v2-cert": 47},
                "by_resource_type": {
                    "VirtualMachine": 5,
                    "StorageAccount": 12,
                    "NetworkSecurityGroup": 8,
                    ...
                },
                "by_role": {
                    "target": 15,
                    "decoy": 10,
                    "infrastructure": 22
                }
            }
        """

    async def ensure_indexes(self) -> None:
        """Create CTF indexes if they don't exist.

        Idempotent - safe to call multiple times.

        Creates:
        - Index on (ctf_exercise, ctf_scenario, layer_id)
        - Index on (ctf_exercise, layer_id)
        """
```

## Dependencies

- **neo4j**: Graph database driver (connection, transactions, queries)
- **dataclasses**: Data models (CTFAnnotation)
- **typing**: Type hints
- **logging**: Error and debug logging

**No dependencies on**:
- Terraform parsing libraries
- Azure SDK
- CLI frameworks
- Other services (self-contained brick)

## Implementation Notes

### Transaction Strategy

**All operations are transactional**:
```python
async def annotate_nodes_bulk(self, annotations):
    async with self.driver.session() as session:
        async with session.begin_transaction() as tx:
            success_count = 0
            errors = []

            for annotation in annotations:
                try:
                    await tx.run(ANNOTATE_QUERY, annotation.to_dict())
                    success_count += 1
                except Exception as e:
                    errors.append(f"{annotation.node_id}: {str(e)}")

            if errors:
                # Rollback transaction
                raise Neo4jError(f"Bulk annotation failed: {errors}")

            # Commit transaction
            return success_count, []
```

### Cypher Query Patterns

**Annotate node**:
```cypher
MATCH (r:Resource {layer_id: $layer_id})
WHERE id(r) = $node_id
SET r.ctf_exercise = $ctf_exercise,
    r.ctf_scenario = $ctf_scenario,
    r.ctf_role = $ctf_role,
    r.ctf_terraform_address = $ctf_terraform_address,
    r.ctf_terraform_source = $ctf_terraform_source
RETURN id(r) as node_id
```

**Query CTF resources**:
```cypher
MATCH (r:Resource {layer_id: $layer_id})
WHERE r.ctf_exercise = $exercise
  AND (r.ctf_scenario = $scenario OR $scenario IS NULL)
RETURN id(r) as node_id, r.id as id, r.resource_type as resource_type,
       r.name as name, r.ctf_exercise as ctf_exercise,
       r.ctf_scenario as ctf_scenario, r.ctf_role as ctf_role,
       r.ctf_terraform_address as ctf_terraform_address
```

**Clear annotations**:
```cypher
MATCH (r:Resource {layer_id: $layer_id})
WHERE r.ctf_exercise = $exercise
  AND (r.ctf_scenario = $scenario OR $scenario IS NULL)
REMOVE r.ctf_exercise, r.ctf_scenario, r.ctf_role,
       r.ctf_terraform_address, r.ctf_terraform_source
RETURN count(r) as cleared_count
```

**Statistics**:
```cypher
MATCH (r:Resource {layer_id: $layer_id})
WHERE r.ctf_exercise IS NOT NULL
  AND (r.ctf_exercise = $exercise OR $exercise IS NULL)
RETURN r.ctf_exercise as exercise,
       r.ctf_scenario as scenario,
       r.resource_type as resource_type,
       r.ctf_role as role,
       count(r) as count
```

### Error Handling Strategy

**Node not found**:
```python
# Return False, don't raise exception
if result.single() is None:
    logger.warning(f"Node {node_id} not found in layer {layer_id}")
    return False
```

**Transaction failure**:
```python
# Rollback automatically, re-raise with context
try:
    async with tx:
        # Operations
except Neo4jError as e:
    logger.error(f"Transaction failed: {e}")
    raise Neo4jError(f"Failed to annotate nodes: {e}")
```

**Invalid parameters**:
```python
# Validate early, provide clear messages
if not node_id or not annotation.ctf_exercise:
    raise ValueError(
        "node_id and annotation.ctf_exercise are required"
    )
```

### Index Management

**Ensure indexes on service initialization**:
```python
async def __aenter__(self):
    await self.ensure_indexes()
    return self

async def ensure_indexes(self):
    queries = [
        """
        CREATE INDEX ctf_exercise_scenario_layer IF NOT EXISTS
        FOR (r:Resource)
        ON (r.ctf_exercise, r.ctf_scenario, r.layer_id)
        """,
        """
        CREATE INDEX ctf_exercise_layer IF NOT EXISTS
        FOR (r:Resource)
        ON (r.ctf_exercise, r.layer_id)
        """,
    ]

    async with self.driver.session() as session:
        for query in queries:
            await session.run(query)
```

### Property Naming Convention

**All CTF properties prefixed with `ctf_`**:
- Avoids conflicts with existing properties
- Easy to identify CTF-specific data
- Clean removal (just drop ctf_* properties)

**Example**:
```python
CTF_PROPERTIES = [
    "ctf_exercise",
    "ctf_scenario",
    "ctf_role",
    "ctf_terraform_address",
    "ctf_terraform_source",
]

def clear_ctf_properties(node):
    for prop in CTF_PROPERTIES:
        if hasattr(node, prop):
            delattr(node, prop)
```

## Test Requirements

### Unit Tests

**Test coverage**: 100% of public methods

**Test cases**:

1. **test_annotate_node_success**: Annotate single node, verify properties set
2. **test_annotate_node_not_found**: Node doesn't exist, returns False
3. **test_annotate_nodes_bulk_success**: Bulk annotate, all succeed
4. **test_annotate_nodes_bulk_partial_failure**: Some nodes fail, transaction rolls back
5. **test_query_ctf_resources_with_filters**: Query with exercise+scenario filter
6. **test_query_ctf_resources_no_filters**: Query all CTF resources
7. **test_clear_ctf_annotations_scenario**: Clear specific scenario
8. **test_clear_ctf_annotations_all_scenarios**: Clear all scenarios for exercise
9. **test_get_ctf_statistics**: Verify statistics aggregation
10. **test_ensure_indexes_idempotent**: Calling multiple times is safe

**Mock strategy**:
- Mock Neo4j driver
- Use in-memory Neo4j for integration tests
- Verify Cypher queries are correct

### Integration Tests

**Test with real Neo4j**:

1. **test_full_annotation_lifecycle**:
   - Create test nodes
   - Annotate with CTF properties
   - Query annotated resources
   - Clear annotations
   - Verify cleanup

2. **test_multi_layer_isolation**:
   - Annotate nodes in "default" layer
   - Annotate nodes in "test" layer
   - Verify queries return correct layer only

3. **test_concurrent_annotations**:
   - Multiple threads annotating simultaneously
   - Verify no conflicts or data corruption

### Performance Tests

**Benchmarks**:

- Annotate 1000 nodes in bulk: < 5 seconds
- Query 1000 CTF resources: < 1 second
- Clear 1000 annotations: < 3 seconds
- Statistics over 10,000 nodes: < 2 seconds

## Example Usage

### Annotate Resources

```python
from src.services.ctf_annotation_service import CTFAnnotationService, CTFAnnotation
from neo4j import GraphDatabase

# Initialize service
driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "password"))
service = CTFAnnotationService(driver)

# Create annotation
annotation = CTFAnnotation(
    node_id="12345",
    resource_id="vm-a1b2c3d4",
    resource_type="VirtualMachine",
    resource_name="attacker-vm",
    ctf_exercise="M003",
    ctf_scenario="v2-cert",
    ctf_role="target",
    ctf_terraform_address="azurerm_virtual_machine.attacker",
    ctf_terraform_source="main.tf:127",
)

# Annotate single node
success = await service.annotate_node("12345", annotation)
print(f"Annotation {'succeeded' if success else 'failed'}")
```

### Query CTF Resources

```python
# Query all resources for M003/v2-cert
resources = await service.query_ctf_resources(
    exercise="M003",
    scenario="v2-cert",
    layer_id="default",
)

print(f"Found {len(resources)} CTF resources:")
for resource in resources:
    print(f"  - {resource['name']} ({resource['resource_type']})")
    print(f"    Role: {resource['ctf_role']}")
    print(f"    Terraform: {resource['ctf_terraform_address']}")
```

### Get Statistics

```python
# Get CTF statistics for M003 exercise
stats = await service.get_ctf_statistics(
    exercise="M003",
    layer_id="default",
)

print(f"Total CTF resources: {stats['total_resources']}")
print(f"By scenario: {stats['by_scenario']}")
print(f"By role: {stats['by_role']}")
```

### Clear Annotations

```python
# Clear all annotations for M003/v2-cert
cleared = await service.clear_ctf_annotations(
    exercise="M003",
    scenario="v2-cert",
    layer_id="default",
)

print(f"Cleared {cleared} CTF annotations")
```

## Regeneration Specification

**This module can be completely regenerated from this spec.**

**Requirements**:
1. Neo4j driver installed: `pip install neo4j`
2. Neo4j instance running
3. This specification document

**Regeneration process**:
1. Create `src/services/ctf_annotation_service.py`
2. Implement data models (CTFAnnotation)
3. Implement CTFAnnotationService class
4. Implement all public methods per contract
5. Add Cypher queries per implementation notes
6. Add error handling per strategy
7. Write tests per test requirements
8. Verify with example usage

**Validation**:
- All unit tests pass
- Integration tests pass with real Neo4j
- Performance benchmarks met
- Example usage runs without errors

---

**Module Status**: Specification Complete
**Ready for Implementation**: Yes
**Dependencies**: neo4j driver only
**Estimated LOC**: ~400 (class + tests)

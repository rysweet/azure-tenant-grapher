# Module: CTF Import Service

## Purpose

Parse Terraform files, map resources to Neo4j graph nodes, and annotate them with CTF (Capture The Flag) metadata. This service bridges Terraform definitions with the existing graph structure.

**Single Responsibility**: Terraform → Graph mapping only - no deployment, no Neo4j CRUD (delegates to CTFAnnotationService).

## Contract

### Inputs

```python
terraform_dir: Path             # Directory containing *.tf files
exercise: str                   # CTF exercise identifier (e.g., "M003")
scenario: str                   # Scenario identifier (e.g., "v2-cert")
tenant_id: str                  # Target tenant ID
layer_id: str                   # Target layer (default: "default")
```

### Outputs

```python
ImportResult                    # Statistics and mapping details
    - exercise: str
    - scenario: str
    - layer_id: str
    - parsed_count: int         # Terraform resources parsed
    - mapped_count: int         # Successfully mapped to graph
    - annotated_count: int      # Successfully annotated in Neo4j
    - skipped_count: int        # Resources not found in graph
    - mappings: List[ResourceMapping]
    - warnings: List[str]       # User-actionable warnings
```

### Side Effects

- **Reads Terraform files**: Parses all *.tf files in directory
- **Queries Neo4j**: Searches for matching resources
- **Delegates annotation**: Calls CTFAnnotationService to add properties
- **No direct Neo4j writes**: All writes through CTFAnnotationService

## Data Models

### TerraformResource

```python
@dataclass
class TerraformResource:
    """Parsed Terraform resource definition."""
    resource_type: str          # azurerm_storage_account
    resource_name: str          # example_storage
    terraform_address: str      # azurerm_storage_account.example_storage
    properties: Dict[str, Any]  # HCL attributes (name, resource_group, etc.)
    file_path: str              # main.tf
    line_number: int            # 45 (for error reporting)

    @property
    def azure_resource_type(self) -> str:
        """Convert Terraform type to Azure type."""
        # azurerm_storage_account → Microsoft.Storage/storageAccounts
        return TERRAFORM_TO_AZURE_TYPE_MAP.get(self.resource_type)

    @property
    def identifying_properties(self) -> Dict[str, str]:
        """Extract properties used for graph matching."""
        return {
            "name": self.properties.get("name"),
            "resource_group_name": self.properties.get("resource_group_name"),
            "location": self.properties.get("location"),
        }
```

### ResourceMapping

```python
@dataclass
class ResourceMapping:
    """Mapping between Terraform resource and graph node."""
    terraform_resource: TerraformResource
    graph_node_id: str | None   # Neo4j node ID if found
    match_confidence: str       # "exact", "fuzzy", "not_found"
    match_reason: str           # Explanation for debugging

    @property
    def is_mapped(self) -> bool:
        """Check if mapping succeeded."""
        return self.graph_node_id is not None

    def to_ctf_annotation(self, exercise: str, scenario: str, role: str | None) -> CTFAnnotation:
        """Convert to CTF annotation."""
        if not self.is_mapped:
            raise ValueError("Cannot create annotation for unmapped resource")

        return CTFAnnotation(
            node_id=self.graph_node_id,
            resource_id=self.terraform_resource.properties.get("id"),
            resource_type=self.terraform_resource.azure_resource_type,
            resource_name=self.terraform_resource.properties.get("name"),
            ctf_exercise=exercise,
            ctf_scenario=scenario,
            ctf_role=role,
            ctf_terraform_address=self.terraform_resource.terraform_address,
            ctf_terraform_source=f"{self.terraform_resource.file_path}:{self.terraform_resource.line_number}",
        )
```

### ImportResult

```python
@dataclass
class ImportResult:
    """Result of import operation with statistics."""
    exercise: str
    scenario: str
    layer_id: str
    parsed_count: int
    mapped_count: int
    annotated_count: int
    skipped_count: int
    mappings: List[ResourceMapping]
    warnings: List[str]

    def format_report(self) -> str:
        """Generate human-readable import report."""
        lines = [
            "=" * 60,
            "CTF Import Report",
            f"Exercise: {self.exercise}",
            f"Scenario: {self.scenario}",
            f"Layer: {self.layer_id}",
            "=" * 60,
            "",
            "Statistics:",
            f"  Parsed:    {self.parsed_count} Terraform resources",
            f"  Mapped:    {self.mapped_count} to graph nodes",
            f"  Annotated: {self.annotated_count} successfully",
            f"  Skipped:   {self.skipped_count} (not found in graph)",
            "",
        ]

        if self.warnings:
            lines.append("Warnings:")
            for warning in self.warnings:
                lines.append(f"  - {warning}")
            lines.append("")

        return "\n".join(lines)
```

## Public API

### CTFImportService

```python
class CTFImportService:
    """Service for importing CTF exercises from Terraform.

    Philosophy:
    - Single responsibility: Terraform → Graph mapping
    - Delegates Neo4j writes to CTFAnnotationService
    - Standard library + python-hcl2 + neo4j driver
    - Self-contained and regeneratable
    """

    def __init__(
        self,
        driver: Driver,
        annotation_service: CTFAnnotationService,
    ):
        """Initialize with Neo4j driver and annotation service.

        Args:
            driver: Neo4j driver for graph queries
            annotation_service: Service for Neo4j CTF operations
        """
        self.driver = driver
        self.annotation_service = annotation_service

    async def import_terraform(
        self,
        terraform_dir: Path,
        exercise: str,
        scenario: str,
        tenant_id: str,
        layer_id: str = "default",
        role_mapping: Dict[str, str] | None = None,
    ) -> ImportResult:
        """Import Terraform as CTF overlay.

        Steps:
        1. Parse all *.tf files in directory
        2. Map resources to graph nodes
        3. Delegate annotation to CTFAnnotationService
        4. Return import statistics

        Args:
            terraform_dir: Directory with Terraform files
            exercise: CTF exercise identifier
            scenario: Scenario identifier
            tenant_id: Target tenant ID
            layer_id: Target layer
            role_mapping: Optional resource_name → role mapping

        Returns:
            ImportResult with statistics and mappings

        Raises:
            TerraformParseError: Invalid HCL syntax
            ValueError: Invalid parameters
        """

    def parse_terraform(
        self,
        terraform_dir: Path,
    ) -> List[TerraformResource]:
        """Parse all *.tf files in directory.

        Args:
            terraform_dir: Directory with Terraform files

        Returns:
            List of parsed Terraform resources

        Raises:
            TerraformParseError: Invalid HCL syntax with file:line
        """

    async def map_to_graph(
        self,
        resources: List[TerraformResource],
        tenant_id: str,
        layer_id: str,
    ) -> List[ResourceMapping]:
        """Map Terraform resources to Neo4j nodes.

        Mapping strategy:
        1. Exact match by name + type + resource_group
        2. Fuzzy match by name + type (any resource group)
        3. Match by tags (if present)
        4. Not found → log warning, skip

        Args:
            resources: Parsed Terraform resources
            tenant_id: Target tenant ID
            layer_id: Target layer

        Returns:
            List of resource mappings (some may be unmapped)
        """

    async def _match_resource_exact(
        self,
        resource: TerraformResource,
        tenant_id: str,
        layer_id: str,
    ) -> tuple[str | None, str]:
        """Try exact match by name + type + resource_group.

        Returns:
            (node_id, match_reason) or (None, reason)
        """

    async def _match_resource_fuzzy(
        self,
        resource: TerraformResource,
        tenant_id: str,
        layer_id: str,
    ) -> tuple[str | None, str]:
        """Try fuzzy match by name + type (ignore resource_group).

        Returns:
            (node_id, match_reason) or (None, reason)
        """

    def _infer_role_from_name(self, resource_name: str) -> str | None:
        """Infer CTF role from Terraform resource name.

        Heuristics:
        - "attacker", "malicious" → target
        - "decoy", "honeypot" → decoy
        - "infra", "network" → infrastructure

        Args:
            resource_name: Terraform resource name

        Returns:
            Inferred role or None
        """
```

## Dependencies

- **neo4j**: Graph database queries (NOT writes - through annotation_service)
- **python-hcl2**: Terraform HCL parsing
- **pathlib**: File operations
- **dataclasses**: Data models
- **src.services.ctf_annotation_service**: Delegates Neo4j writes

**No dependencies on**:
- Terraform CLI (subprocess)
- Azure SDK
- CLI frameworks
- TerraformEmitter/Importer (separation of concerns)

## Implementation Notes

### Terraform Parsing Strategy

**Use python-hcl2 library** (not subprocess):
```python
import hcl2

def parse_terraform(self, terraform_dir: Path) -> List[TerraformResource]:
    resources = []

    for tf_file in terraform_dir.glob("*.tf"):
        try:
            with tf_file.open("r") as f:
                hcl_dict = hcl2.load(f)

            # Extract resource blocks
            for resource_block in hcl_dict.get("resource", []):
                for resource_type, resource_defs in resource_block.items():
                    for resource_name, properties in resource_defs.items():
                        resources.append(
                            TerraformResource(
                                resource_type=resource_type,
                                resource_name=resource_name,
                                terraform_address=f"{resource_type}.{resource_name}",
                                properties=properties,
                                file_path=str(tf_file.name),
                                line_number=self._find_line_number(tf_file, resource_name),
                            )
                        )

        except Exception as e:
            raise TerraformParseError(
                f"Failed to parse {tf_file.name}: {e}\n"
                f"Check Terraform syntax and try again."
            )

    return resources
```

**Benefits**:
- Fast (no subprocess overhead)
- Accurate line numbers for errors
- Programmatic access to HCL structure
- No Terraform CLI dependency

### Resource Mapping Strategy

**Multi-tier matching** (try strategies in order):

**Tier 1: Exact match**
```cypher
MATCH (r:Resource {layer_id: $layer_id, tenant_id: $tenant_id})
WHERE r.resource_type = $azure_resource_type
  AND r.name = $name
  AND r.resource_group_name = $resource_group_name
RETURN id(r) as node_id
```

**Tier 2: Fuzzy match (ignore resource group)**
```cypher
MATCH (r:Resource {layer_id: $layer_id, tenant_id: $tenant_id})
WHERE r.resource_type = $azure_resource_type
  AND r.name = $name
RETURN id(r) as node_id
```

**Tier 3: Tag-based match** (if tags present in Terraform)
```cypher
MATCH (r:Resource {layer_id: $layer_id, tenant_id: $tenant_id})
WHERE r.resource_type = $azure_resource_type
  AND r.tags_ctf_id = $ctf_id  // Custom tag for CTF identification
RETURN id(r) as node_id
```

**Tier 4: Not found**
```python
# Log warning with actionable guidance
logger.warning(
    f"Resource not found: {resource.terraform_address}\n"
    f"  Name: {resource.properties['name']}\n"
    f"  Type: {resource.azure_resource_type}\n"
    f"  Resource Group: {resource.properties.get('resource_group_name')}\n\n"
    f"This resource may not have been scanned yet. Run:\n"
    f"  atg scan --tenant-id {tenant_id} --subscription-id <sub>"
)
```

### Type Mapping (Terraform → Azure)

**Mapping table**:
```python
TERRAFORM_TO_AZURE_TYPE_MAP = {
    "azurerm_storage_account": "Microsoft.Storage/storageAccounts",
    "azurerm_virtual_machine": "Microsoft.Compute/virtualMachines",
    "azurerm_network_security_group": "Microsoft.Network/networkSecurityGroups",
    "azurerm_virtual_network": "Microsoft.Network/virtualNetworks",
    "azurerm_subnet": "Microsoft.Network/virtualNetworks/subnets",
    "azurerm_key_vault": "Microsoft.KeyVault/vaults",
    "azurerm_application_insights": "Microsoft.Insights/components",
    "azurerm_log_analytics_workspace": "Microsoft.OperationalInsights/workspaces",
    # ... (use existing TerraformEmitter.RESOURCE_TYPE_MAPPINGS)
}
```

**Reuse existing mappings** from TerraformEmitter to avoid duplication.

### Role Inference Heuristics

**Extract role from resource name** (if not explicitly provided):
```python
def _infer_role_from_name(self, resource_name: str) -> str | None:
    """Infer CTF role from naming conventions."""
    name_lower = resource_name.lower()

    # Target indicators
    if any(keyword in name_lower for keyword in ["attacker", "malicious", "exploit", "target"]):
        return "target"

    # Decoy indicators
    if any(keyword in name_lower for keyword in ["decoy", "honeypot", "fake", "trap"]):
        return "decoy"

    # Infrastructure indicators
    if any(keyword in name_lower for keyword in ["infra", "network", "base", "foundation"]):
        return "infrastructure"

    # No clear role
    return None
```

**Override with explicit role_mapping**:
```python
# role_mapping = {"attacker_vm": "target", "decoy_storage": "decoy"}
role = role_mapping.get(resource.resource_name) or self._infer_role_from_name(resource.resource_name)
```

### Error Handling Strategy

**Terraform parse errors**:
```python
try:
    hcl_dict = hcl2.load(f)
except Exception as e:
    raise TerraformParseError(
        f"Terraform syntax error in {tf_file.name}:{line}\n"
        f"  {str(e)}\n\n"
        f"Common fixes:\n"
        f"  - Check for missing closing braces\n"
        f"  - Verify string quotes are balanced\n"
        f"  - Run 'terraform validate' to check syntax"
    )
```

**Resource not found** (warning, not error):
```python
if node_id is None:
    warnings.append(
        f"Resource not in graph: {resource.terraform_address}\n"
        f"  This is expected if the resource hasn't been scanned yet."
    )
    skipped_count += 1
    continue  # Don't fail entire import
```

**Annotation failures** (fail entire import):
```python
try:
    annotated_count, errors = await self.annotation_service.annotate_nodes_bulk(annotations)
    if errors:
        raise CTFImportError(
            f"Failed to annotate {len(errors)} resources:\n" +
            "\n".join(errors)
        )
except Neo4jError as e:
    raise CTFImportError(
        f"Neo4j transaction failed: {e}\n"
        f"All annotations rolled back. No changes made to graph."
    )
```

### Performance Optimization

**Batch graph queries**:
```python
# BAD: Query for each resource individually (N queries)
for resource in resources:
    node_id = await self._match_resource_exact(resource, tenant_id, layer_id)

# GOOD: Batch query all resources at once (1 query)
query = """
MATCH (r:Resource {layer_id: $layer_id, tenant_id: $tenant_id})
WHERE r.resource_type IN $resource_types
  AND r.name IN $names
RETURN id(r) as node_id, r.name as name, r.resource_type as resource_type
"""
results = await session.run(query, {
    "layer_id": layer_id,
    "tenant_id": tenant_id,
    "resource_types": [r.azure_resource_type for r in resources],
    "names": [r.properties.get("name") for r in resources],
})

# Build lookup map
node_map = {(r["name"], r["resource_type"]): r["node_id"] for r in results}

# Match resources to nodes
for resource in resources:
    key = (resource.properties.get("name"), resource.azure_resource_type)
    node_id = node_map.get(key)
```

**Target performance**:
- Parse 100 Terraform resources: < 2 seconds
- Map 100 resources to graph: < 5 seconds
- Annotate 100 nodes: < 3 seconds
- **Total import time**: < 10 seconds for 100 resources

## Test Requirements

### Unit Tests

**Test coverage**: 100% of public methods

**Test cases**:

1. **test_parse_terraform_valid**: Parse valid *.tf files, verify resources extracted
2. **test_parse_terraform_invalid_syntax**: Invalid HCL → clear error with file:line
3. **test_parse_terraform_empty_directory**: No *.tf files → empty result
4. **test_map_to_graph_exact_match**: All resources match exactly
5. **test_map_to_graph_fuzzy_match**: Some resources match fuzzily
6. **test_map_to_graph_not_found**: Some resources not in graph (warnings, not errors)
7. **test_import_terraform_success**: Full import succeeds, verify annotations
8. **test_import_terraform_with_role_mapping**: Explicit roles override inference
9. **test_infer_role_from_name**: Heuristics work correctly
10. **test_terraform_to_azure_type_mapping**: Type conversion correct

**Mock strategy**:
- Mock Neo4j driver for graph queries
- Use test Terraform files in fixtures
- Verify CTFAnnotationService called correctly

### Integration Tests

**Test with real Neo4j**:

1. **test_import_m003_v1_base**:
   - Import M003 v1-base Terraform
   - Verify 5-10 resources annotated
   - Check CTF properties set correctly

2. **test_import_with_missing_resources**:
   - Import Terraform referencing non-existent resources
   - Verify warnings generated
   - Verify other resources still annotated

3. **test_import_idempotency**:
   - Import same Terraform twice
   - Second import overwrites annotations (or skips if already present)
   - No errors or duplicates

### E2E Tests

**M003 scenario tests**:

1. **v1-base**: 5-10 resources, basic CTF setup
2. **v2-cert**: Certificate-related resources added
3. **v3-ews**: EWS-specific resources added
4. **v4-blob**: Blob storage resources added

**Test flow per scenario**:
```python
# 1. Import Terraform
result = await import_service.import_terraform(
    terraform_dir=Path(f"tests/fixtures/m003/{scenario}"),
    exercise="M003",
    scenario=scenario,
    tenant_id="test-tenant",
)

# 2. Verify statistics
assert result.parsed_count > 0
assert result.mapped_count == result.parsed_count  # All mapped
assert result.annotated_count == result.mapped_count  # All annotated
assert result.skipped_count == 0  # None skipped

# 3. Query annotations
resources = await annotation_service.query_ctf_resources(
    exercise="M003",
    scenario=scenario,
)
assert len(resources) == result.annotated_count

# 4. Verify properties
for resource in resources:
    assert resource["ctf_exercise"] == "M003"
    assert resource["ctf_scenario"] == scenario
    assert resource["ctf_terraform_address"].startswith("azurerm_")
```

## Example Usage

### Import M003 v2-cert

```python
from src.services.ctf_import_service import CTFImportService
from src.services.ctf_annotation_service import CTFAnnotationService
from neo4j import GraphDatabase
from pathlib import Path

# Initialize services
driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "password"))
annotation_service = CTFAnnotationService(driver)
import_service = CTFImportService(driver, annotation_service)

# Import Terraform
result = await import_service.import_terraform(
    terraform_dir=Path("./m003/v2-cert"),
    exercise="M003",
    scenario="v2-cert",
    tenant_id="my-tenant-id",
    layer_id="default",
)

# Print report
print(result.format_report())
```

**Output**:
```
============================================================
CTF Import Report
Exercise: M003
Scenario: v2-cert
Layer: default
============================================================

Statistics:
  Parsed:    47 Terraform resources
  Mapped:    45 to graph nodes
  Annotated: 45 successfully
  Skipped:   2 (not found in graph)

Warnings:
  - Resource not in graph: azurerm_storage_account.decoy_storage
    This is expected if the resource hasn't been scanned yet.
  - Resource not in graph: azurerm_key_vault.target_vault
    This is expected if the resource hasn't been scanned yet.
```

### Custom Role Mapping

```python
# Override role inference with explicit mapping
role_mapping = {
    "attacker_vm": "target",
    "decoy_storage": "decoy",
    "network_infra": "infrastructure",
}

result = await import_service.import_terraform(
    terraform_dir=Path("./m003/v2-cert"),
    exercise="M003",
    scenario="v2-cert",
    tenant_id="my-tenant-id",
    role_mapping=role_mapping,  # Explicit roles
)
```

## Regeneration Specification

**This module can be completely regenerated from this spec.**

**Requirements**:
1. Neo4j driver: `pip install neo4j`
2. python-hcl2: `pip install python-hcl2`
3. CTFAnnotationService implemented
4. This specification document

**Regeneration process**:
1. Create `src/services/ctf_import_service.py`
2. Implement data models (TerraformResource, ResourceMapping, ImportResult)
3. Implement CTFImportService class
4. Implement Terraform parsing with python-hcl2
5. Implement multi-tier resource matching
6. Implement role inference heuristics
7. Add error handling per strategy
8. Write tests per test requirements
9. Verify with example usage

**Validation**:
- All unit tests pass
- Integration tests pass with real Neo4j
- E2E tests pass for M003 scenarios
- Example usage runs without errors

---

**Module Status**: Specification Complete
**Ready for Implementation**: Yes (requires CTFAnnotationService first)
**Dependencies**: neo4j driver, python-hcl2, CTFAnnotationService
**Estimated LOC**: ~600 (class + tests)

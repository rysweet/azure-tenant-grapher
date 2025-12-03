# CTF Overlay System Architecture

## Executive Summary

This document specifies a CTF (Capture The Flag) overlay system that models security exercises as annotations on the abstracted resource graph. CTF exercises are imported from Terraform, mapped to existing graph nodes, and annotated with special properties. Deployment is idempotent, automatically detecting and importing existing resources before applying changes.

**Design Philosophy**: Ruthless simplicity - CTF is metadata on existing resources, not a separate graph structure.

## Problem Statement

### Requirements

1. **Model CTF exercises as overlays**: Annotate existing abstracted resources with CTF-specific properties
2. **Import command**: Parse Terraform, map to graph nodes, store as CTF annotations
3. **Deploy command**: Export Terraform, detect existing resources, import if needed, apply idempotently
4. **Test with M003 scenarios**: v1-base, v2-cert, v3-ews, v4-blob (4 progressive scenarios)

### Design Goals

1. **Non-invasive**: Don't modify existing dual-graph architecture
2. **Reuse existing patterns**: Leverage terraform_emitter and terraform_importer
3. **Idempotent deployment**: Can re-run without errors
4. **Clear separation**: CTF logic isolated in dedicated modules
5. **Single responsibility**: Each service handles one aspect

## Architecture Overview

### Conceptual Model

```
┌────────────────────────────────────────────────────────────────┐
│                     Neo4j Graph Database                        │
├────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │         ORIGINAL GRAPH (Immutable)                        │ │
│  │  :Resource:Original - Real Azure IDs                      │ │
│  │  Source of truth for all projections                      │ │
│  └───────────────────────────────────────────────────────────┘ │
│                            ▲                                     │
│                            │ SCAN_SOURCE_NODE                    │
│                            │                                     │
│  ┌────────────────────────┴──────────────────────────────────┐ │
│  │      ABSTRACTED GRAPH (Layer-based)                       │ │
│  │  :Resource (layer_id='default')                           │ │
│  │  Baseline abstraction from scan                           │ │
│  │                                                            │ │
│  │  ┌──────────────────────────────────────────────────────┐│ │
│  │  │    CTF OVERLAY (Annotations)                         ││ │
│  │  │                                                       ││ │
│  │  │  :Resource {                                         ││ │
│  │  │    ctf_exercise: "M003",                            ││ │
│  │  │    ctf_scenario: "v2-cert",                         ││ │
│  │  │    ctf_role: "target",                              ││ │
│  │  │    ctf_terraform_address: "azurerm_...",            ││ │
│  │  │    ctf_terraform_source: "/path/to/main.tf:45"     ││ │
│  │  │  }                                                   ││ │
│  │  │                                                       ││ │
│  │  └──────────────────────────────────────────────────────┘│ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                  │
└────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────┐
│                     CLI Commands                                │
├────────────────────────────────────────────────────────────────┤
│  atg ctf import --terraform-dir ./m003/v2-cert --exercise M003  │
│  atg ctf deploy --exercise M003 --scenario v2-cert             │
│  atg ctf list --exercise M003                                   │
│  atg ctf clear --exercise M003 --scenario v2-cert              │
└────────────────────────────────────────────────────────────────┘
```

### Component Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                       CTF Overlay System                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  CLI Layer (src/commands/ctf.py)                         │   │
│  │  - Subcommands: import, deploy, list, clear              │   │
│  │  - Argument parsing and validation                       │   │
│  │  - User feedback and error reporting                     │   │
│  └──────────────────────────────────────────────────────────┘   │
│                            │                                     │
│                            ▼                                     │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Service Layer                                           │   │
│  ├──────────────────────────────────────────────────────────┤   │
│  │                                                           │   │
│  │  CTFImportService (src/services/ctf_import_service.py)  │   │
│  │  - Parse Terraform files                                 │   │
│  │  - Map resources to graph nodes                          │   │
│  │  - Annotate nodes with CTF properties                    │   │
│  │                                                           │   │
│  │  CTFDeployService (src/services/ctf_deploy_service.py)  │   │
│  │  - Retrieve CTF-annotated resources                      │   │
│  │  - Generate Terraform with import blocks                 │   │
│  │  - Orchestrate deployment                                │   │
│  │                                                           │   │
│  │  CTFAnnotationService (src/services/ctf_annotation_service.py) │
│  │  - Neo4j CRUD operations for CTF properties              │   │
│  │  - Query CTF-annotated nodes                             │   │
│  │  - Clear CTF annotations                                 │   │
│  │                                                           │   │
│  └──────────────────────────────────────────────────────────┘   │
│                            │                                     │
│                            ▼                                     │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Integration Layer                                       │   │
│  ├──────────────────────────────────────────────────────────┤   │
│  │                                                           │   │
│  │  TerraformEmitter (existing)                             │   │
│  │  - Generate Terraform from graph                         │   │
│  │  - Add import blocks for existing resources              │   │
│  │                                                           │   │
│  │  TerraformImporter (existing)                            │   │
│  │  - Detect existing Azure resources                       │   │
│  │  - Generate import commands                              │   │
│  │                                                           │   │
│  │  Neo4j Driver (existing)                                 │   │
│  │  - Graph database operations                             │   │
│  │  - Transaction support                                   │   │
│  │                                                           │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

## Data Flow Diagrams

### Import Workflow

```
┌────────────┐
│   User     │
└─────┬──────┘
      │ atg ctf import --terraform-dir ./m003/v2-cert --exercise M003
      ▼
┌─────────────────────────────────────────────────────────────────┐
│ Step 1: CLI Command (src/commands/ctf.py)                       │
│ - Validate arguments                                             │
│ - Create CTFImportService                                        │
└─────┬───────────────────────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────────────────────────────┐
│ Step 2: Parse Terraform (CTFImportService)                       │
│ - Read *.tf files from directory                                 │
│ - Parse HCL using python-hcl2                                    │
│ - Extract resource definitions                                   │
│ - Result: List[TerraformResource]                                │
└─────┬───────────────────────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────────────────────────────┐
│ Step 3: Map to Graph Nodes (CTFImportService)                    │
│ - For each Terraform resource:                                   │
│   1. Determine resource type (azurerm_storage_account, etc.)     │
│   2. Extract identifying properties (name, resource_group)       │
│   3. Query Neo4j for matching abstracted node                    │
│   4. If not found, query Original graph and create abstracted    │
│   5. If still not found, log warning and skip                    │
│ - Result: List[ResourceMapping]                                  │
└─────┬───────────────────────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────────────────────────────┐
│ Step 4: Annotate Nodes (CTFAnnotationService)                    │
│ - For each mapped resource:                                      │
│   1. Add ctf_exercise property                                   │
│   2. Add ctf_scenario property                                   │
│   3. Add ctf_role property (if specified)                        │
│   4. Add ctf_terraform_address                                   │
│   5. Add ctf_terraform_source (file:line)                        │
│ - Transaction: All or nothing                                    │
└─────┬───────────────────────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────────────────────────────┐
│ Step 5: Report Results                                           │
│ - Statistics: Resources parsed, mapped, annotated, skipped       │
│ - List of annotated resources                                    │
│ - Warnings for unmapped resources                                │
└─────────────────────────────────────────────────────────────────┘
```

### Deploy Workflow

```
┌────────────┐
│   User     │
└─────┬──────┘
      │ atg ctf deploy --exercise M003 --scenario v2-cert
      ▼
┌─────────────────────────────────────────────────────────────────┐
│ Step 1: CLI Command (src/commands/ctf.py)                       │
│ - Validate arguments                                             │
│ - Create CTFDeployService                                        │
└─────┬───────────────────────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────────────────────────────┐
│ Step 2: Retrieve CTF Resources (CTFAnnotationService)            │
│ - Query Neo4j for nodes with:                                    │
│   - ctf_exercise = "M003"                                        │
│   - ctf_scenario = "v2-cert"                                     │
│ - Result: List[AnnotatedResource]                                │
└─────┬───────────────────────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────────────────────────────┐
│ Step 3: Generate Terraform (TerraformEmitter)                    │
│ - Create TerraformEmitter with auto_import_existing=True         │
│ - Pass CTF resources to emitter                                  │
│ - Emitter generates:                                             │
│   1. Resource definitions                                        │
│   2. Import blocks for existing resources                        │
│ - Result: Terraform files in output directory                    │
└─────┬───────────────────────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────────────────────────────┐
│ Step 4: Detect Existing Resources (TerraformImporter)           │
│ - For each resource in Terraform:                                │
│   1. Check if exists in Azure (via Azure SDK)                    │
│   2. Generate import block if exists                             │
│   3. Add to imports list                                         │
│ - Result: List[ImportCommand]                                    │
└─────┬───────────────────────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────────────────────────────┐
│ Step 5: Execute Terraform (CTFDeployService)                     │
│ - terraform init                                                 │
│ - terraform plan (with import blocks)                            │
│ - terraform apply (if not dry-run)                               │
│ - Handle errors and retries                                      │
└─────┬───────────────────────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────────────────────────────┐
│ Step 6: Validate Deployment                                      │
│ - Check Terraform state                                          │
│ - Verify resources exist in Azure                                │
│ - Report success/failure                                         │
└─────────────────────────────────────────────────────────────────┘
```

## Module Specifications

### 1. CTF Command Module

**Location**: `src/commands/ctf.py`

**Purpose**: CLI interface for CTF overlay operations

**Contract**:

```python
@click.group()
def ctf():
    """CTF overlay management commands."""
    pass

@ctf.command()
@click.option('--terraform-dir', required=True, type=click.Path(exists=True))
@click.option('--exercise', required=True, help='CTF exercise name (e.g., M003)')
@click.option('--scenario', required=True, help='Scenario name (e.g., v2-cert)')
@click.option('--layer-id', default='default', help='Target layer (default: default)')
@click.option('--tenant-id', help='Tenant ID (from env if not specified)')
def import_cmd(terraform_dir: str, exercise: str, scenario: str, layer_id: str, tenant_id: str | None):
    """Import CTF exercise from Terraform."""
    # Implementation

@ctf.command()
@click.option('--exercise', required=True, help='CTF exercise name')
@click.option('--scenario', required=True, help='Scenario name')
@click.option('--output-dir', default='./ctf-output', help='Output directory for Terraform')
@click.option('--dry-run', is_flag=True, help='Plan only, no apply')
@click.option('--tenant-id', help='Target tenant ID')
def deploy(exercise: str, scenario: str, output_dir: str, dry_run: bool, tenant_id: str | None):
    """Deploy CTF exercise to Azure."""
    # Implementation

@ctf.command()
@click.option('--exercise', help='Filter by exercise')
@click.option('--scenario', help='Filter by scenario')
@click.option('--layer-id', default='default', help='Layer to query')
def list_cmd(exercise: str | None, scenario: str | None, layer_id: str):
    """List CTF-annotated resources."""
    # Implementation

@ctf.command()
@click.option('--exercise', required=True, help='Exercise to clear')
@click.option('--scenario', help='Scenario to clear (all if not specified)')
@click.option('--layer-id', default='default', help='Layer to clear from')
@click.confirmation_option(prompt='Are you sure?')
def clear(exercise: str, scenario: str | None, layer_id: str):
    """Clear CTF annotations."""
    # Implementation
```

**Dependencies**:
- click
- src.commands.base (CommandContext)
- src.services.ctf_import_service
- src.services.ctf_deploy_service
- src.services.ctf_annotation_service

**Implementation Notes**:
- Follow existing command pattern from Issue #482
- Use CommandContext for Neo4j setup
- Use async_command decorator for async operations
- Provide rich console output with statistics

**Test Requirements**:
- Unit tests for each subcommand
- Integration tests with mock Neo4j
- E2E tests with real M003 scenarios

---

### 2. CTF Import Service

**Location**: `src/services/ctf_import_service.py`

**Purpose**: Parse Terraform and map to graph nodes

**Contract**:

```python
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional
from neo4j import Driver

@dataclass
class TerraformResource:
    """Parsed Terraform resource."""
    resource_type: str          # azurerm_storage_account
    resource_name: str          # example_storage
    terraform_address: str      # azurerm_storage_account.example_storage
    properties: Dict[str, Any]  # HCL attributes
    file_path: str              # main.tf
    line_number: int            # 45

@dataclass
class ResourceMapping:
    """Mapping between Terraform and graph node."""
    terraform_resource: TerraformResource
    graph_node_id: str | None   # Neo4j node ID if found
    match_confidence: str       # "exact", "fuzzy", "not_found"
    match_reason: str           # Explanation

@dataclass
class ImportResult:
    """Result of import operation."""
    exercise: str
    scenario: str
    layer_id: str
    parsed_count: int
    mapped_count: int
    annotated_count: int
    skipped_count: int
    mappings: List[ResourceMapping]
    warnings: List[str]

class CTFImportService:
    """Service for importing CTF exercises from Terraform."""

    def __init__(self, driver: Driver):
        """Initialize with Neo4j driver."""
        self.driver = driver

    async def import_terraform(
        self,
        terraform_dir: Path,
        exercise: str,
        scenario: str,
        tenant_id: str,
        layer_id: str = "default",
    ) -> ImportResult:
        """Import Terraform as CTF overlay.

        Steps:
        1. Parse Terraform files
        2. Map resources to graph nodes
        3. Annotate nodes with CTF properties
        4. Return import statistics
        """
        pass

    def _parse_terraform(self, terraform_dir: Path) -> List[TerraformResource]:
        """Parse all *.tf files in directory."""
        pass

    async def _map_to_graph(
        self,
        resources: List[TerraformResource],
        tenant_id: str,
        layer_id: str,
    ) -> List[ResourceMapping]:
        """Map Terraform resources to Neo4j nodes."""
        pass

    async def _annotate_nodes(
        self,
        mappings: List[ResourceMapping],
        exercise: str,
        scenario: str,
    ) -> int:
        """Annotate mapped nodes with CTF properties."""
        pass
```

**Dependencies**:
- neo4j (Driver)
- python-hcl2 (Terraform parsing)
- src.services.ctf_annotation_service
- pathlib (file operations)

**Implementation Notes**:
- Use python-hcl2 for HCL parsing (not subprocess)
- Mapping strategy:
  1. Try exact match by resource name + type
  2. Try fuzzy match by name similarity
  3. Try match by resource group + type
  4. Log warning if no match found
- Transaction: All annotations or nothing
- Preserve Terraform source location for debugging

**Error Handling**:
- Terraform parsing errors → user-friendly message with file:line
- Missing graph nodes → warning, continue with others
- Neo4j transaction failures → rollback, report which resources failed

---

### 3. CTF Deploy Service

**Location**: `src/services/ctf_deploy_service.py`

**Purpose**: Orchestrate idempotent CTF deployment

**Contract**:

```python
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional
from neo4j import Driver

@dataclass
class DeploymentConfig:
    """Configuration for CTF deployment."""
    exercise: str
    scenario: str
    output_dir: Path
    tenant_id: str
    subscription_id: str
    dry_run: bool = False
    layer_id: str = "default"

@dataclass
class DeploymentResult:
    """Result of deployment operation."""
    exercise: str
    scenario: str
    terraform_dir: Path
    resources_deployed: int
    resources_imported: int
    resources_created: int
    terraform_state: Path | None
    success: bool
    error_message: str | None
    import_report: Any  # From TerraformImporter

class CTFDeployService:
    """Service for deploying CTF exercises idempotently."""

    def __init__(
        self,
        driver: Driver,
        annotation_service: "CTFAnnotationService",
    ):
        """Initialize with Neo4j driver and annotation service."""
        self.driver = driver
        self.annotation_service = annotation_service

    async def deploy(
        self,
        config: DeploymentConfig,
    ) -> DeploymentResult:
        """Deploy CTF exercise idempotently.

        Steps:
        1. Retrieve CTF-annotated resources
        2. Generate Terraform with import blocks
        3. Execute terraform init/plan/apply
        4. Validate deployment
        5. Return deployment statistics
        """
        pass

    async def _retrieve_ctf_resources(
        self,
        exercise: str,
        scenario: str,
        layer_id: str,
    ) -> List[Dict[str, Any]]:
        """Query Neo4j for CTF-annotated nodes."""
        pass

    async def _generate_terraform(
        self,
        resources: List[Dict[str, Any]],
        output_dir: Path,
        config: DeploymentConfig,
    ) -> Path:
        """Generate Terraform with import blocks."""
        pass

    async def _execute_terraform(
        self,
        terraform_dir: Path,
        dry_run: bool,
    ) -> tuple[bool, str]:
        """Execute terraform init/plan/apply."""
        pass

    async def _validate_deployment(
        self,
        terraform_dir: Path,
        expected_resources: int,
    ) -> bool:
        """Verify deployment success."""
        pass
```

**Dependencies**:
- neo4j (Driver)
- src.services.ctf_annotation_service
- src.iac.emitters.terraform_emitter (TerraformEmitter)
- src.iac.importers.terraform_importer (TerraformImporter)
- subprocess (Terraform CLI)
- pathlib (file operations)

**Implementation Notes**:
- Reuse existing TerraformEmitter with auto_import_existing=True
- Reuse existing TerraformImporter for resource detection
- Idempotency strategy:
  1. Generate Terraform with import blocks
  2. Terraform automatically imports existing resources
  3. Only creates/updates resources that differ
- Retry logic for transient Terraform errors
- Capture terraform output for debugging

**Error Handling**:
- Terraform CLI errors → parse output, provide actionable message
- Resource conflicts → suggest manual inspection
- Partial failures → report which resources succeeded/failed

---

### 4. CTF Annotation Service

**Location**: `src/services/ctf_annotation_service.py`

**Purpose**: Neo4j CRUD for CTF properties

**Contract**:

```python
from dataclasses import dataclass
from typing import Dict, List, Optional
from neo4j import Driver

@dataclass
class CTFAnnotation:
    """CTF properties for a resource."""
    node_id: str                    # Neo4j node ID
    resource_id: str                # Abstracted resource ID
    resource_type: str
    resource_name: str
    ctf_exercise: str
    ctf_scenario: str
    ctf_role: str | None           # target, decoy, infrastructure
    ctf_terraform_address: str     # azurerm_storage_account.example
    ctf_terraform_source: str      # main.tf:45

class CTFAnnotationService:
    """Service for managing CTF annotations in Neo4j."""

    def __init__(self, driver: Driver):
        """Initialize with Neo4j driver."""
        self.driver = driver

    async def annotate_node(
        self,
        node_id: str,
        annotation: CTFAnnotation,
    ) -> bool:
        """Add CTF properties to a node."""
        pass

    async def annotate_nodes_bulk(
        self,
        annotations: List[CTFAnnotation],
    ) -> tuple[int, List[str]]:
        """Bulk annotate nodes in transaction.

        Returns:
            (success_count, error_messages)
        """
        pass

    async def query_ctf_resources(
        self,
        exercise: str | None = None,
        scenario: str | None = None,
        layer_id: str = "default",
    ) -> List[Dict[str, Any]]:
        """Query nodes with CTF annotations."""
        pass

    async def clear_ctf_annotations(
        self,
        exercise: str,
        scenario: str | None = None,
        layer_id: str = "default",
    ) -> int:
        """Remove CTF properties from nodes.

        Returns:
            Number of nodes cleared
        """
        pass

    async def get_ctf_statistics(
        self,
        exercise: str | None = None,
        layer_id: str = "default",
    ) -> Dict[str, Any]:
        """Get statistics about CTF annotations."""
        pass
```

**Dependencies**:
- neo4j (Driver, Transaction)

**Implementation Notes**:
- All operations in transactions
- Use parameterized Cypher queries (no injection)
- CTF properties prefixed with `ctf_` to avoid conflicts
- Properties are nullable (can be removed cleanly)
- Index on ctf_exercise + ctf_scenario for fast queries

**Error Handling**:
- Node not found → return False, log warning
- Transaction failures → rollback, preserve original state
- Invalid parameters → raise ValueError with clear message

---

## Integration Strategy

### Integration with TerraformEmitter

**No modifications needed** - TerraformEmitter already supports:
- Emitting from graph nodes
- Adding import blocks (auto_import_existing=True)
- Custom resource filtering

**Integration approach**:
1. CTFDeployService queries CTF-annotated nodes
2. Passes node list to TerraformEmitter
3. Emitter generates Terraform as usual
4. Import blocks added automatically

**Code example**:
```python
# In CTFDeployService._generate_terraform()
from src.iac.emitters.terraform_emitter import TerraformEmitter

emitter = TerraformEmitter(
    auto_import_existing=True,
    import_strategy="selective",
    target_subscription_id=config.subscription_id,
    target_tenant_id=config.tenant_id,
)

# Pass CTF resources as if they were regular graph nodes
terraform_output = emitter.emit(
    tenant_id=config.tenant_id,
    resource_nodes=ctf_resources,  # CTF-annotated nodes
    output_path=config.output_dir,
)
```

### Integration with TerraformImporter

**No modifications needed** - TerraformImporter already supports:
- Detecting existing Azure resources
- Generating import blocks
- Multiple import strategies

**Integration approach**:
1. TerraformEmitter generates Terraform with resources
2. TerraformImporter scans Azure for existing resources
3. Import blocks generated for matches
4. Terraform applies with imports

**Code example**:
```python
# In CTFDeployService._generate_terraform()
from src.iac.importers.terraform_importer import TerraformImporter, ImportStrategy

# After emitter generates Terraform
importer = TerraformImporter(
    subscription_id=config.subscription_id,
    terraform_dir=config.output_dir,
    strategy=ImportStrategy.ALL_RESOURCES,
)

# Generate import blocks
import_report = await importer.detect_and_import(
    dry_run=config.dry_run,
)
```

### Integration with Dual-Graph Architecture

**Key principle**: CTF annotations ONLY on abstracted graph

**Graph structure**:
```cypher
// Original graph (unchanged)
(:Resource:Original {id: "real-azure-id"})

// Abstracted graph with CTF overlay
(:Resource {
  id: "abstracted-id",
  layer_id: "default",
  ctf_exercise: "M003",       // CTF property
  ctf_scenario: "v2-cert",    // CTF property
})
-[:SCAN_SOURCE_NODE]->(:Resource:Original)
```

**Why abstracted only?**
1. Original graph is immutable (source of truth)
2. CTF is a temporary overlay, not permanent state
3. Multiple layers can have different CTF exercises
4. Clearing CTF doesn't affect original resources

### Integration with Layer System

**CTF is layer-aware** - annotations tied to specific layers

**Query pattern**:
```cypher
// Query CTF resources in specific layer
MATCH (r:Resource {layer_id: $layer_id})
WHERE r.ctf_exercise = $exercise
  AND r.ctf_scenario = $scenario
RETURN r
```

**Benefits**:
- Different CTF exercises per layer
- Compare CTF scenarios across layers
- Isolate CTF testing environments

## Error Handling & Edge Cases

### Terraform Parsing Failures

**Scenario**: Invalid HCL syntax in Terraform files

**Handling**:
```python
try:
    resources = parse_terraform(terraform_dir)
except HCL2SyntaxError as e:
    raise CTFImportError(
        f"Terraform syntax error in {e.file}:{e.line}\n"
        f"  {e.message}\n"
        f"Fix the Terraform file and try again."
    )
```

**User experience**:
- Clear error message with file:line
- Show problematic HCL snippet
- Suggest fixes for common errors

### Resources Not Found in Graph

**Scenario**: Terraform references resource not in Neo4j

**Handling**:
1. Log warning with resource details
2. Skip that resource
3. Continue with others
4. Report skipped resources at end

**Example**:
```
Warning: Resource not found in graph
  Terraform: azurerm_storage_account.example_storage
  Name: examplestorage
  Resource Group: example-rg

  This resource may not have been scanned yet. Run:
    atg scan --tenant-id <tenant> --subscription-id <sub>
```

### Deployment Failures Mid-Way

**Scenario**: Terraform apply fails after creating some resources

**Handling**:
1. Terraform state captures partial progress
2. Next run detects existing resources via import
3. Only creates remaining resources

**Idempotency guarantee**:
- Import blocks ensure existing resources aren't recreated
- Terraform state tracks what's deployed
- Can safely re-run deploy command

**Example flow**:
```
First attempt: Creates 3/5 resources, fails on 4th
Second attempt: Imports 3 existing, creates 2 remaining
Result: All 5 resources deployed successfully
```

### Resource Conflicts

**Scenario**: Resource exists in Azure but not in Terraform state

**Handling**:
1. TerraformImporter detects existing resource
2. Generates import block
3. Terraform imports before applying

**User notification**:
```
Existing resources detected:
  - azurerm_storage_account.example_storage (imported)
  - azurerm_resource_group.example_rg (imported)

These resources will be imported into Terraform state.
No changes will be made unless configuration differs.
```

### Layer Conflicts

**Scenario**: Importing CTF to layer that already has annotations

**Handling**:
```python
# Check for existing annotations before import
existing = await annotation_service.query_ctf_resources(
    exercise=exercise,
    scenario=scenario,
    layer_id=layer_id,
)

if existing:
    if not force:
        raise CTFImportError(
            f"Layer '{layer_id}' already has CTF annotations for "
            f"{exercise}/{scenario}. Use --force to overwrite or "
            f"--clear first to remove existing annotations."
        )
    else:
        # Clear existing before importing
        await annotation_service.clear_ctf_annotations(
            exercise=exercise,
            scenario=scenario,
            layer_id=layer_id,
        )
```

## Idempotency Design

### Core Strategy

**Definition**: Running `ctf deploy` multiple times produces same result without errors

**Mechanisms**:
1. **Import blocks**: Terraform imports existing resources
2. **State tracking**: Terraform state captures deployed resources
3. **Diff-based apply**: Only changes what's different

### Implementation Details

**Terraform generation**:
```hcl
# Generated by CTFDeployService
import {
  to = azurerm_storage_account.example_storage
  id = "/subscriptions/.../resourceGroups/.../providers/Microsoft.Storage/storageAccounts/examplestorage"
}

resource "azurerm_storage_account" "example_storage" {
  name                = "examplestorage"
  resource_group_name = "example-rg"
  # ... other properties
}
```

**Deploy sequence**:
1. `terraform init` - Initialize providers
2. `terraform plan` - Preview changes (shows imports)
3. `terraform apply` - Execute (imports + creates)

**Idempotency guarantee**:
- First run: Imports existing, creates new
- Second run: No-op (all resources already in state)
- Third run: No-op
- After manual Azure changes: Detects drift, corrects

### Retry Logic

**Transient failures**:
- Network timeouts
- Azure API rate limits
- Temporary permission issues

**Retry strategy**:
```python
async def _execute_terraform_with_retry(
    self,
    terraform_dir: Path,
    max_retries: int = 3,
) -> tuple[bool, str]:
    """Execute Terraform with exponential backoff."""
    for attempt in range(max_retries):
        try:
            result = await self._execute_terraform(terraform_dir)
            return result
        except TerraformTransientError as e:
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # 1s, 2s, 4s
                logger.warning(f"Retry {attempt+1}/{max_retries} after {wait_time}s")
                await asyncio.sleep(wait_time)
            else:
                raise
```

### State Management

**Terraform state location**:
- Local: `{output_dir}/terraform.tfstate`
- Remote (optional): Azure Storage backend

**State cleanup**:
- Preserved across retries
- Can be inspected for debugging
- Cleared by `ctf clear` command (optional)

## Testing Strategy

### Unit Tests

**CTFImportService**:
- Parse valid Terraform → correct TerraformResource list
- Parse invalid Terraform → clear error message
- Map resources → correct graph node matches
- Annotate nodes → correct CTF properties set

**CTFDeployService**:
- Retrieve CTF resources → correct node query
- Generate Terraform → valid HCL output
- Execute Terraform → proper subprocess calls
- Handle failures → correct error messages

**CTFAnnotationService**:
- Annotate node → property set in Neo4j
- Bulk annotate → transaction success
- Query CTF resources → correct results
- Clear annotations → properties removed

### Integration Tests

**Import workflow**:
1. Mock Neo4j with test data
2. Import real M003 Terraform
3. Verify annotations in mock Neo4j
4. Check statistics

**Deploy workflow**:
1. Mock Neo4j with CTF-annotated nodes
2. Generate Terraform
3. Mock Terraform CLI (don't actually deploy)
4. Verify import blocks generated

### E2E Tests

**M003 scenarios** (4 progressive tests):

**v1-base**:
- Import Terraform
- Verify 5-10 resources annotated
- Deploy (dry-run)
- Verify Terraform plan succeeds

**v2-cert**:
- Import Terraform
- Verify certificate-related resources annotated
- Deploy (dry-run)
- Verify import blocks for existing resources

**v3-ews**:
- Import Terraform
- Verify EWS-specific resources annotated
- Deploy (dry-run)
- Check idempotency (run twice)

**v4-blob**:
- Import Terraform
- Verify blob storage resources annotated
- Deploy (dry-run)
- Full cycle: import → deploy → clear → verify

**Test data location**:
- `tests/fixtures/m003/v1-base/*.tf`
- `tests/fixtures/m003/v2-cert/*.tf`
- `tests/fixtures/m003/v3-ews/*.tf`
- `tests/fixtures/m003/v4-blob/*.tf`

## Implementation Phases

### Phase 1: Core Infrastructure (Week 1)

**Deliverables**:
1. CTFAnnotationService with Neo4j CRUD
2. Data models (dataclasses)
3. Unit tests for annotation service
4. Neo4j schema updates (indexes)

**Success criteria**:
- Can annotate nodes with CTF properties
- Can query CTF-annotated resources
- Can clear CTF annotations
- All unit tests pass

### Phase 2: Import Pipeline (Week 2)

**Deliverables**:
1. CTFImportService with Terraform parsing
2. Resource mapping logic
3. CLI command: `atg ctf import`
4. Integration tests

**Success criteria**:
- Can parse M003 Terraform files
- Can map resources to graph nodes
- Can import v1-base scenario successfully
- Import statistics reported correctly

### Phase 3: Deploy Pipeline (Week 3)

**Deliverables**:
1. CTFDeployService with Terraform generation
2. Integration with TerraformEmitter/Importer
3. CLI command: `atg ctf deploy`
4. Idempotency tests

**Success criteria**:
- Can generate Terraform from CTF annotations
- Import blocks generated for existing resources
- Can deploy (dry-run) v1-base successfully
- Idempotent (can run twice without errors)

### Phase 4: Testing & Hardening (Week 4)

**Deliverables**:
1. E2E tests for all M003 scenarios
2. Error handling improvements
3. CLI commands: `atg ctf list`, `atg ctf clear`
4. Documentation

**Success criteria**:
- All 4 M003 scenarios pass E2E tests
- Error messages are user-friendly
- Can list/clear CTF annotations
- README and Specs complete

## Open Questions

1. **CTF role taxonomy**: What roles exist beyond target/decoy/infrastructure?
2. **Multi-tenant CTF**: Should CTF exercises span multiple tenants?
3. **CTF versioning**: How to handle CTF exercise versions (v1, v2, etc.)?
4. **CTF dependencies**: How to model dependencies between CTF resources?
5. **CTF cleanup**: Should deploy automatically clean up on failure?

## Decision Log

| Decision | Rationale | Alternatives Considered |
|----------|-----------|------------------------|
| CTF as annotations on abstracted graph | Ruthless simplicity - reuse existing graph structure | Separate CTF graph (too complex) |
| Reuse TerraformEmitter/Importer | Avoid duplication, leverage existing patterns | Write custom Terraform logic (reinventing wheel) |
| Import blocks for idempotency | Standard Terraform pattern, well-tested | Manual state management (error-prone) |
| Layer-aware CTF | Enables isolated CTF environments per layer | Global CTF (conflicts across layers) |
| Async services | Consistent with existing service pattern | Sync services (inconsistent) |
| python-hcl2 for parsing | Standard library, well-maintained | subprocess terraform (too slow) |

## Future Enhancements

1. **CTF templates**: Reusable CTF exercise templates
2. **CTF validation**: Verify CTF exercises before deployment
3. **CTF snapshots**: Save/restore CTF state
4. **CTF metrics**: Track CTF exercise performance
5. **CTF UI**: Web interface for CTF management
6. **CTF reporting**: Generate reports from CTF results

---

**Document Status**: Draft
**Last Updated**: 2025-12-02
**Author**: Architect Agent
**Review Status**: Pending Builder Review

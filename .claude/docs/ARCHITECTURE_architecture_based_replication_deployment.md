# Architecture-Based Replication Deployment Integration

## Investigation Summary

**Date**: 2026-02-05
**Objective**: Design integration between architecture-based replication plan generation (from pattern graphs) and Azure deployment pipeline
**Status**: Investigation Complete, Design Ready for Implementation

---

## Executive Summary

This document specifies the integration design for deploying architecture-based replication plans to Azure tenants. The design bridges the gap between pattern-based resource selection (`architecture_based_replicator.py`) and the existing deployment infrastructure (`deployment/orchestrator.py`, IaC emitters).

**Key Finding**: The replication plan currently outputs resource instances without relationships, but the deployment pipeline requires complete TenantGraph structures with instance-level relationships. This integration adds the necessary transformation layer.

---

## System Architecture

### Current State

```
┌─────────────────────────────────────────────────────────────────┐
│ SOURCE TENANT                                                   │
│                                                                 │
│  Neo4j Graph ──→ Pattern Analyzer ──→ Pattern Graph           │
│  (instances)     (type-level)          (type frequencies)      │
│                                                                 │
│  Pattern Graph ──→ Replicator ──→ Replication Plan            │
│  (types)           (selection)     (instances, no rels)        │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                            ❌ GAP HERE
┌─────────────────────────────────────────────────────────────────┐
│ TARGET TENANT                                                   │
│                                                                 │
│  TenantGraph ──→ IaC Emitter ──→ Terraform/Bicep Files        │
│  (needs rels)    (requires rels)  (.tf/.bicep)                 │
│                                                                 │
│  IaC Files ──→ Deployment Orchestrator ──→ Azure Resources    │
│  (formats)     (terraform/bicep/arm)       (deployed)          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Proposed Integration

```
┌──────────────────────────────────────────────────────────────────────┐
│ SOURCE TENANT (Pattern-Based Selection)                             │
│                                                                      │
│  Neo4j Graph ──→ Pattern Analyzer ──→ Pattern Graph                │
│  (instances)     (type-level)          (type frequencies)           │
│       │                                                              │
│       └──────┐                                                       │
│              ▼                                                       │
│  Pattern Graph + Neo4j ──→ Enhanced Replicator ──→ Enhanced Plan   │
│  (types)       (instances)  (selection + rels)     (instances+rels) │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
                            ✅ NEW LAYER
┌──────────────────────────────────────────────────────────────────────┐
│ TRANSFORMATION LAYER (New Component)                                │
│                                                                      │
│  Enhanced Plan ──→ Conversion Function ──→ TenantGraph             │
│  (nested)          (flatten + query rels)  (resources + rels)       │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
                            ⬇
┌──────────────────────────────────────────────────────────────────────┐
│ TARGET TENANT (Existing Deployment Pipeline)                        │
│                                                                      │
│  TenantGraph ──→ IaC Emitter ──→ Terraform/Bicep Files             │
│  (complete)      (existing)       (.tf/.bicep)                      │
│                                                                      │
│  IaC Files ──→ Deployment Orchestrator ──→ Azure Resources         │
│  (formats)     (existing)                  (deployed)               │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Critical Findings

### 1. Type-Level vs Instance-Level Relationships (CRITICAL)

**Problem**: Pattern graph is type-level, but deployment needs instance-level relationships.

**Pattern Graph** (architectural_pattern_analyzer.py):
- Nodes: Resource TYPES (e.g., "Microsoft.Compute/virtualMachines")
- Edges: Aggregated relationships with FREQUENCY counts
- Example: "virtualMachines" --[CONTAINS, frequency=10]--> "networkInterfaces"

**Replication Plan** (architecture_based_replicator.py):
- Resources: Specific INSTANCES (e.g., `{id: "/subscriptions/.../vm1", type: "virtualMachines", name: "vm1"}`)
- NO RELATIONSHIPS included in current implementation

**Deployment Requirement** (TenantGraph):
- Resources: List of resource instance dicts
- Relationships: List of `{source: resource_id, target: resource_id, type: rel_type}`

**Impact**: Cannot infer "vm1 CONTAINS nic2" from "virtualMachines CONTAINS networkInterfaces (frequency=10)"

**Solution**: Query Neo4j for instance-level relationships between selected resources.

### 2. Resource Property Completeness (MODERATE)

**Current State**: Replication plan queries resources with:
- ✅ `id`, `type`, `name` - Present
- ✅ `location`, `tags`, `properties` - Present (lines 492-501 in architecture_based_replicator.py)

**Assessment**: Resource properties ARE sufficient for IaC generation. No changes needed to resource query.

### 3. IaC Emitter Isolation (VALIDATED)

**Finding**: TerraformEmitter does NOT query Neo4j - relies purely on TenantGraph passed to `emit()`.

**Implication**: All required data must be in TenantGraph structure before calling emitter.

---

## Data Structures

### Replication Plan Output Format

```python
# Current format: architecture_based_replicator.py:684-1008
Tuple[
    List[Tuple[str, List[List[Dict[str, Any]]]]],  # selected_instances by pattern
    List[float],                                    # spectral_history
    Optional[Dict[str, Any]]                        # distribution_metadata
]

# Example structure:
(
    [
        ("Web Application", [
            # Instance 1
            [
                {"id": "/subscriptions/.../sites/webapp1", "type": "sites", "name": "webapp1",
                 "location": "eastus", "tags": {...}, "properties": {...}},
                {"id": "/subscriptions/.../serverFarms/plan1", "type": "serverFarms", "name": "plan1",
                 "location": "eastus", "tags": {...}, "properties": {...}}
            ],
            # Instance 2
            [
                {"id": "/subscriptions/.../sites/webapp2", "type": "sites", "name": "webapp2",
                 "location": "westus", "tags": {...}, "properties": {...}}
            ]
        ]),
        ("VM Workload", [
            # Instance 1
            [
                {"id": "/subscriptions/.../virtualMachines/vm1", "type": "virtualMachines", ...},
                {"id": "/subscriptions/.../networkInterfaces/nic1", "type": "networkInterfaces", ...}
            ]
        ])
    ],
    [0.8, 0.6, 0.4],  # Spectral distance history
    {"selection_mode": "proportional", "use_coherence": True}
)
```

### TenantGraph Structure

```python
# Target format: iac/traverser.py:20-26
@dataclass
class TenantGraph:
    resources: List[Dict[str, Any]]      # Flat list of all resource dicts
    relationships: List[Dict[str, Any]]   # List of {source, target, type}

# Example:
TenantGraph(
    resources=[
        {"id": "/subscriptions/.../sites/webapp1", "type": "sites", "name": "webapp1", ...},
        {"id": "/subscriptions/.../serverFarms/plan1", "type": "serverFarms", "name": "plan1", ...},
        {"id": "/subscriptions/.../sites/webapp2", "type": "sites", "name": "webapp2", ...},
        {"id": "/subscriptions/.../virtualMachines/vm1", "type": "virtualMachines", ...},
        {"id": "/subscriptions/.../networkInterfaces/nic1", "type": "networkInterfaces", ...}
    ],
    relationships=[
        {"source": "/subscriptions/.../sites/webapp1",
         "target": "/subscriptions/.../serverFarms/plan1",
         "type": "DEPENDS_ON"},
        {"source": "/subscriptions/.../virtualMachines/vm1",
         "target": "/subscriptions/.../networkInterfaces/nic1",
         "type": "CONTAINS"}
    ]
)
```

---

## Transformation Layer Design

### Component 1: Conversion Function

**Location**: `src/services/replication_plan_converter.py` (new file)

**Function Signature**:
```python
async def replication_plan_to_tenant_graph(
    replication_plan: Tuple[List[Tuple[str, List[List[Dict]]]], List[float], Optional[Dict]],
    neo4j_session: Session,
    include_relationship_types: Optional[List[str]] = None
) -> TenantGraph:
    """
    Convert replication plan output to TenantGraph for IaC generation.

    Args:
        replication_plan: Output from architecture_based_replicator.generate_replication_plan()
        neo4j_session: Active Neo4j session for querying relationships
        include_relationship_types: Filter relationships (default: ["CONTAINS", "DEPENDS_ON",
                                    "DIAGNOSTIC_TARGET", "MONITORS", "TAG_RELATIONSHIP"])

    Returns:
        TenantGraph with resources and instance-level relationships

    Algorithm:
        1. Flatten nested structure to extract all resource dicts
        2. Collect all resource IDs
        3. Query Neo4j for relationships between selected resources
        4. Construct TenantGraph(resources=flat_list, relationships=queried_rels)
    """
    selected_instances, spectral_history, metadata = replication_plan

    # Step 1: Flatten resources
    flat_resources = []
    resource_ids = set()

    for pattern_name, instances in selected_instances:
        for instance in instances:
            for resource in instance:
                flat_resources.append(resource)
                resource_ids.add(resource["id"])

    # Step 2: Query relationships between selected resources
    if include_relationship_types is None:
        include_relationship_types = [
            "CONTAINS", "DEPENDS_ON", "DIAGNOSTIC_TARGET",
            "MONITORS", "TAG_RELATIONSHIP"
        ]

    relationship_query = """
    MATCH (source:Resource:Original)-[rel]->(target:Resource:Original)
    WHERE source.id IN $resource_ids
      AND target.id IN $resource_ids
      AND type(rel) IN $rel_types
    RETURN source.id AS source,
           target.id AS target,
           type(rel) AS type
    """

    result = await neo4j_session.run(
        relationship_query,
        resource_ids=list(resource_ids),
        rel_types=include_relationship_types
    )

    relationships = []
    async for record in result:
        relationships.append({
            "source": record["source"],
            "target": record["target"],
            "type": record["type"]
        })

    return TenantGraph(resources=flat_resources, relationships=relationships)
```

**Dependencies**:
- Neo4j session (from source tenant scan)
- Relationship type filtering (default covers 95% of deployment-relevant relationships)

**Edge Cases**:
- Empty replication plan → TenantGraph(resources=[], relationships=[])
- Resources without relationships → TenantGraph with relationships=[]
- Circular dependencies → Handled by IaC emitters (Terraform/Bicep)

### Component 2: CLI Integration

**Option A: Extend Existing `deploy` Command** (RECOMMENDED)

**Location**: `src/commands/deploy.py`

**Changes**:
```python
# Add new CLI flags to deploy_command()
@click.option(
    "--from-replication-plan",
    is_flag=True,
    help="Generate deployment from architecture-based replication plan"
)
@click.option(
    "--pattern-filter",
    multiple=True,
    help="Filter patterns to deploy (can specify multiple, e.g., --pattern-filter 'Web Application' --pattern-filter 'VM Workload')"
)
@click.option(
    "--instance-filter",
    type=str,
    help="Filter instances by index (e.g., '0,2,5' or '0-3')"
)
def deploy_command(
    ...existing params...,
    from_replication_plan: bool,
    pattern_filter: Tuple[str, ...],
    instance_filter: Optional[str],
):
    """Deploy IaC to target tenant, optionally from replication plan."""

    if from_replication_plan:
        # New workflow: Generate IaC from replication plan
        # 1. Connect to source Neo4j (from docker container)
        # 2. Build pattern graph from scan
        # 3. Generate replication plan
        # 4. Convert to TenantGraph
        # 5. Generate IaC
        # 6. Deploy to target tenant
        ...
    else:
        # Existing workflow: Deploy from existing IaC directory
        deploy_iac(iac_dir, ...)
```

**Usage Example**:
```bash
# Deploy all patterns from replication plan
azure-tenant-grapher deploy \
  --from-replication-plan \
  --target-tenant-id <target-id> \
  --resource-group "replicated-rg" \
  --format terraform

# Deploy specific patterns
azure-tenant-grapher deploy \
  --from-replication-plan \
  --pattern-filter "Web Application" \
  --pattern-filter "VM Workload" \
  --target-tenant-id <target-id> \
  --resource-group "replicated-rg"

# Deploy specific instances
azure-tenant-grapher deploy \
  --from-replication-plan \
  --pattern-filter "Web Application" \
  --instance-filter "0,2" \  # Deploy only 1st and 3rd instances
  --target-tenant-id <target-id> \
  --resource-group "replicated-rg"
```

**Option B: New Command `deploy-pattern`** (Alternative)

```bash
azure-tenant-grapher deploy-pattern \
  --pattern-name "Web Application" \
  --target-tenant-id <target-id> \
  --resource-group "web-app-rg" \
  --format terraform
```

**Recommendation**: **Option A** (extend existing command) for consistency and discoverability.

---

## Implementation Specification

### Phase 1: Core Conversion Layer (4-6 hours)

**File**: `src/services/replication_plan_converter.py`

**Functions**:
1. `replication_plan_to_tenant_graph()` - Main conversion function (see design above)
2. `_flatten_resources()` - Extract flat resource list from nested structure
3. `_query_relationships()` - Query Neo4j for instance relationships
4. `_filter_patterns()` - Apply pattern filtering
5. `_filter_instances()` - Apply instance index filtering

**Tests** (`tests/unit/services/test_replication_plan_converter.py`):
- Test flattening nested structure
- Test relationship querying with mock Neo4j
- Test pattern/instance filtering
- Test empty replication plan handling
- Test resource ID collection

### Phase 2: CLI Integration (2-3 hours)

**File**: `src/commands/deploy.py`

**Changes**:
1. Add CLI flags: `--from-replication-plan`, `--pattern-filter`, `--instance-filter`
2. Add workflow branch for replication plan deployment
3. Connect to source Neo4j (read from docker container connection)
4. Call pattern analyzer → replicator → converter → emitter → orchestrator

**Helper Functions**:
- `_deploy_from_replication_plan()` - Orchestrate new workflow
- `_connect_to_source_neo4j()` - Get session from docker container
- `_parse_instance_filter()` - Parse "0,2,5" or "0-3" syntax

**Tests** (`tests/integration/test_deploy_replication_plan.py`):
- End-to-end test: pattern graph → replication plan → TenantGraph → IaC generation
- Test with filtered patterns
- Test with filtered instances
- Test with empty pattern graph (should fail gracefully)

### Phase 3: Documentation (1-2 hours)

**Files**:
1. `docs/howto/deploy-replication-plan.md` - User guide
2. `docs/concepts/architecture-based-deployment.md` - Conceptual explanation
3. Update `docs/index.md` - Add new documentation links
4. Update `README.md` - Add deployment workflow example

**Content**:
- Prerequisites (source scan, Neo4j container running)
- Step-by-step deployment guide
- Pattern/instance filtering examples
- Troubleshooting common issues

### Phase 4: Integration Testing (3-4 hours)

**Test Scenarios**:
1. **Full deployment**: All patterns, all instances → verify resources created in target tenant
2. **Filtered deployment**: Single pattern → verify only selected pattern resources created
3. **Instance filtering**: Pattern with 5 instances, filter to 2 → verify only 2 instance groups deployed
4. **Relationship preservation**: Deploy VM with NIC → verify CONTAINS relationship in IaC
5. **Globally unique names**: Deploy Storage Account → verify name transformation applied
6. **Multi-format**: Generate Terraform, Bicep, ARM from same plan → verify format consistency

**Validation**:
- Check generated IaC files for correctness
- Verify `terraform plan` / `bicep build` succeeds
- Spot-check deployed resources in target tenant (manual)

---

## Dependency Management

### Neo4j Connection

**Source**: Docker container (per user requirement: "use the scan that is already in the docker container")

**Connection Pattern**:
```python
from src.db.connection_manager import ConnectionManager

# Get connection from docker container
conn_manager = ConnectionManager()
driver = conn_manager.get_driver()

with driver.session() as session:
    # Use for pattern analysis and relationship queries
    pass
```

**Configuration**: Read from `.env` or docker-compose configuration.

### Authentication

**Target Tenant**: Already authenticated via `az login` (per user requirement)

**Pattern**:
```python
from azure.identity import AzureCliCredential

credential = AzureCliCredential()
# Used by deployment/orchestrator.py (existing code)
```

---

## Edge Cases and Error Handling

### 1. No Patterns Detected

**Scenario**: Source tenant has no architectural patterns (too small, unusual architecture)

**Handling**:
```python
if not detected_patterns:
    logger.error("No architectural patterns detected in source tenant. "
                 "Ensure source tenant has sufficient resources (minimum 5-10 resources).")
    raise ValueError("No patterns detected for replication")
```

### 2. Empty Replication Plan

**Scenario**: Pattern filtering excludes all patterns

**Handling**:
```python
if not selected_instances:
    logger.warning(f"No instances selected. Pattern filter: {pattern_filter}")
    return TenantGraph(resources=[], relationships=[])
```

### 3. Relationship Query Timeout

**Scenario**: Large replication plan (1000+ resources) causes slow relationship query

**Handling**:
```python
# Add timeout to relationship query
try:
    result = await session.run(relationship_query, timeout=60.0)  # 60s timeout
except TimeoutError:
    logger.warning("Relationship query timeout. Deploying with limited relationships.")
    # Fallback: deploy with empty relationships (resources only)
    relationships = []
```

### 4. Globally Unique Name Conflicts

**Scenario**: Storage Account name already taken

**Handling**: Already handled by `AzureNameSanitizer` service (existing infrastructure)

**Validation**: Check coverage in DISCOVERIES.md - only 13.9% of globally unique types covered (5/36)

**Recommendation**: Document limitation in CLI help and user guide.

### 5. Dependency Cycles

**Scenario**: Replication plan includes circular dependencies (rare, but possible)

**Handling**: Rely on IaC tooling (Terraform/Bicep) to detect and report. No explicit cycle detection needed in conversion layer.

---

## Testing Strategy

### Unit Tests (60% coverage target)

**Files**:
- `tests/unit/services/test_replication_plan_converter.py`
- `tests/unit/commands/test_deploy_replication_integration.py`

**Coverage**:
- Conversion function logic
- Pattern/instance filtering
- Relationship query construction
- Edge case handling (empty plans, no relationships)

### Integration Tests (30% coverage target)

**Files**:
- `tests/integration/test_architecture_deployment_pipeline.py`

**Scenarios**:
- End-to-end: Pattern graph → Replication plan → TenantGraph → IaC
- Multiple IaC formats (Terraform, Bicep, ARM)
- Filtered deployments

### End-to-End Tests (10% coverage target)

**Manual Validation** (required per USER_PREFERENCES.md):
1. Scan small test tenant (5-10 resources)
2. Generate replication plan
3. Deploy to clean target tenant
4. Verify resources created correctly

**Automated Validation** (gadugi-agentic-test):
- CLI behavior testing
- Error message validation
- Help text verification

---

## Limitations and Future Enhancements

### Current Limitations

1. **Relationship Types**: Only includes 5 core types (CONTAINS, DEPENDS_ON, DIAGNOSTIC_TARGET, MONITORS, TAG_RELATIONSHIP)
   - **Future**: Add `--include-all-relationships` flag

2. **Data Plane Operations**: IaC creates infrastructure only (no KeyVault secrets, Storage blobs)
   - **Future**: Add `--include-data-plane` flag (see PROJECT.md - data plane plugins exist)

3. **Single Resource Group**: Deploys all resources to single target RG
   - **Future**: Add `--preserve-rg-structure` flag (TerraformEmitter already supports this)

4. **Globally Unique Names**: Only 13.9% coverage (5/36 resource types)
   - **Future**: Enhance `AzureNameSanitizer` to cover all 36 types (see DISCOVERIES.md)

5. **Pattern Instance Multiplicity**: Deploys all instances by default
   - **Partial**: `--instance-filter` flag provides basic filtering
   - **Future**: More sophisticated instance selection (by cost, size, complexity)

### Future Enhancements

**Phase 2** (Post-MVP):
1. Multi-RG deployment with RG structure preservation
2. Cost-aware instance filtering (`--max-cost $500`)
3. Data plane replication (KeyVault, Storage, Config)
4. Dry-run with cost estimation
5. Incremental deployment (deploy pattern by pattern with validation)

**Phase 3** (Advanced):
1. Cross-region replication
2. Cross-subscription replication
3. Partial pattern deployment (deploy only VMs from "VM Workload" pattern)
4. Pattern composition (combine multiple patterns into single deployment)

---

## Success Metrics

### Functional Requirements

- ✅ Generate IaC from replication plan (Terraform/Bicep/ARM)
- ✅ Preserve instance-level relationships in deployment
- ✅ Support pattern and instance filtering
- ✅ Use existing deployment orchestrator (no duplication)
- ✅ Handle globally unique names via existing AzureNameSanitizer

### Non-Functional Requirements

- ⏱️ **Performance**: Conversion < 5s for 100 resources, < 30s for 1000 resources
- 🛡️ **Reliability**: Graceful degradation on relationship query timeout
- 📖 **Usability**: Clear CLI help text, intuitive filtering syntax
- 🧪 **Testability**: 60/30/10 unit/integration/E2E test coverage

---

## Implementation Timeline

| Phase | Deliverable | Effort | Duration |
|-------|------------|--------|----------|
| **Phase 1** | Core conversion layer | 4-6 hours | 1 day |
| **Phase 2** | CLI integration | 2-3 hours | 0.5 days |
| **Phase 3** | Documentation | 1-2 hours | 0.5 days |
| **Phase 4** | Integration testing | 3-4 hours | 0.5 days |
| **Total** | End-to-end deployment | **10-15 hours** | **2-3 days** |

---

## References

### Codebase Files

1. **Pattern Analysis**: `src/architectural_pattern_analyzer.py:266-311` (build_networkx_graph)
2. **Replication**: `src/architecture_based_replicator.py:684-1008` (generate_replication_plan)
3. **Conversion Target**: `src/iac/traverser.py:20-26` (TenantGraph dataclass)
4. **IaC Generation**: `src/iac/emitters/terraform_emitter.py:400-499` (emit method)
5. **Deployment**: `src/deployment/orchestrator.py:41-394` (deploy_iac)
6. **CLI**: `src/commands/deploy.py:154-182` (deploy_command)
7. **Name Handling**: `src/services/azure_name_sanitizer.py` (AzureNameSanitizer)
8. **Scale-Down Example**: `src/services/scale_down/exporters/iac_exporter.py:93-109` (TenantGraph construction)

### Documentation

1. **Project Context**: `.claude/context/PROJECT.md` (Key Components, Testing Strategy)
2. **Patterns**: `.claude/context/PATTERNS.md` (Layered Architecture, Multi-Strategy Selection)
3. **Discoveries**: `.claude/context/DISCOVERIES.md` (Globally Unique Names, Two-Stage Transformation)

### Investigation Workflow

- **Phase 1**: Scope Definition → Clear questions about deployment integration
- **Phase 2**: Exploration Strategy → 3-stage approach (Foundation, Mechanics, Integration)
- **Phase 3**: Parallel Deep Dives → Read 7 files (orchestrator, emitters, traverser, replicator, analyzer, services)
- **Phase 4**: Verification → Discovered type-level vs instance-level relationship gap
- **Phase 5**: Synthesis → This document

---

## Approval Checklist

Before implementation, confirm:

- [ ] **Relationship Strategy**: Confirmed Neo4j query for instance relationships (not pattern graph)
- [ ] **CLI Design**: Confirmed extension of existing `deploy` command (not new command)
- [ ] **Scope**: Confirmed MVP excludes data plane operations
- [ ] **Testing**: Confirmed 60/30/10 unit/integration/E2E coverage target
- [ ] **Documentation**: Confirmed docs/howto/, docs/concepts/ structure
- [ ] **Timeline**: Confirmed 2-3 day implementation timeline acceptable

---

## Next Steps

**Immediate Actions**:
1. Review this design with project stakeholders
2. Resolve any ambiguities or questions
3. Get architectural approval
4. Proceed to DEFAULT_WORKFLOW for implementation

**Implementation Order**:
1. Phase 1: Core conversion layer (`replication_plan_converter.py`)
2. Phase 2: CLI integration (`commands/deploy.py`)
3. Phase 3: Documentation (howto + concepts)
4. Phase 4: Integration testing (E2E validation)

**Transition to Implementation**:
```bash
# After approval, use DEFAULT_WORKFLOW
/amplihack:ultrathink "Implement architecture-based replication deployment per ARCHITECTURE_architecture_based_replication_deployment.md"
```

---

**Document Version**: 1.0
**Author**: Claude Code (Investigation Workflow)
**Last Updated**: 2026-02-05

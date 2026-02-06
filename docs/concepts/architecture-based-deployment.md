# Architecture-Based Deployment

This document explains the architecture and design principles behind Azure Tenant Grapher's pattern-based deployment system, which enables intelligent infrastructure replication by operating at the architectural pattern level rather than individual resources.

## Problem Statement

Traditional infrastructure replication approaches face several challenges:

1. **Resource-Level Thinking**: Copying individual resources misses the bigger picture of how resources work together
2. **Manual Selection**: Choosing which resources to replicate requires deep infrastructure knowledge
3. **Broken Dependencies**: Individual resource replication often breaks architectural relationships
4. **Configuration Drift**: Replicated environments may not preserve the architectural intent of the source

## Solution: Architecture-Based Deployment

Architecture-based deployment solves these problems by:

1. **Pattern Detection**: Automatically identifies architectural patterns in source tenants (e.g., "Web Application", "VM Workload")
2. **Structural Preservation**: Maintains relationships between resources within patterns
3. **Intelligent Selection**: Uses pattern matching to select representative resource instances
4. **Complete Replication**: Ensures all dependencies and relationships are included

## How It Works

### Three-Layer Architecture

The system operates in three distinct layers:

```
┌─────────────────────────────────────────────────────────┐
│ LAYER 1: Pattern Analysis (Type-Level)                 │
│  Source Tenant → Architectural Patterns                │
│  - Detect resource type groupings                      │
│  - Aggregate relationship frequencies                  │
│  - Identify common configurations                      │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│ LAYER 2: Instance Selection (Pattern-Level)            │
│  Patterns → Resource Instances                         │
│  - Select representative instances                     │
│  - Maintain pattern structure                          │
│  - Apply filtering (patterns, instances)              │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│ LAYER 3: Deployment Graph (Instance-Level)             │
│  Instances → IaC → Target Tenant                       │
│  - Query actual instance relationships                 │
│  - Generate Infrastructure-as-Code                     │
│  - Deploy to target environment                        │
└─────────────────────────────────────────────────────────┘
```

### Layer 1: Pattern Analysis

**Purpose**: Understand the source tenant's architecture at the type level.

**Process**:
1. Scan Neo4j graph database containing source tenant data
2. Identify resource type groupings (e.g., virtualMachines + networkInterfaces + disks)
3. Calculate relationship frequencies between types
4. Detect common architectural patterns

**Output**: Pattern Graph
- Nodes: Resource types (e.g., "Microsoft.Compute/virtualMachines")
- Edges: Aggregated relationships with frequency counts
- Example: "virtualMachines" --[CONTAINS, frequency=10]--> "networkInterfaces"

**Key Insight**: Patterns represent architectural intent, not specific configurations.

### Layer 2: Instance Selection

**Purpose**: Select representative resource instances that match detected patterns.

**Process**:
1. For each detected pattern, find matching resource instances in source tenant
2. Use configuration coherence to group similar instances
3. Apply proportional selection to maintain pattern distribution
4. Support filtering by pattern name or instance index

**Output**: Replication Plan
- Structure: List of (pattern_name, instance_groups)
- Each instance group is a list of resource dicts
- Includes metadata (spectral_history, selection_mode)

**Key Insight**: Cannot infer instance relationships from type-level patterns - must query explicitly.

### Layer 3: Deployment Graph

**Purpose**: Convert replication plan to deployable infrastructure with precise relationships.

**Process**:
1. Flatten nested replication plan structure
2. Collect all resource IDs from selected instances
3. **Query Neo4j for actual instance-level relationships**
4. Construct TenantGraph with resources + relationships
5. Generate IaC (Terraform/Bicep/ARM)
6. Deploy to target tenant

**Output**: Deployed Infrastructure
- Complete resource configuration
- Preserved relationships (CONTAINS, DEPENDS_ON, etc.)
- Ready for production use

**Key Insight**: Instance relationships must be queried explicitly from Neo4j - they cannot be inferred from pattern-level data.

## Design Decisions

### Why Three Layers?

**Separation of Concerns**:
- **Analysis** (type-level): Focus on architectural understanding
- **Selection** (pattern-level): Focus on representative sampling
- **Deployment** (instance-level): Focus on precise infrastructure creation

**Performance**:
- Type-level analysis is fast (aggregate queries)
- Instance selection is targeted (pattern-aware)
- Relationship queries are precise (only selected resources)

**Flexibility**:
- Filter at pattern level (which architectures to deploy)
- Filter at instance level (which examples to deploy)
- Separate concerns enable independent optimization

### Why Query Relationships Separately?

**Problem**: Pattern graph has type-level aggregations:
- "virtualMachines" --[CONTAINS, frequency=10]--> "networkInterfaces"
- Cannot determine which VM contains which NIC from this information

**Solution**: Query Neo4j for instance-level relationships:
- After selecting specific VMs and NICs
- Query: "Give me all CONTAINS relationships where both source and target are in my selected set"
- Result: Precise instance connections (e.g., "vm1 CONTAINS nic2")

**Alternative Considered**: Store instance relationships in replication plan
- **Rejected**: Increases plan size dramatically (relationship data >> resource data)
- **Chosen**: Query on-demand using TenantGraph converter

### Why Support Pattern and Instance Filtering?

**Pattern Filtering** enables:
- Deploy only specific architectures (e.g., just Web Applications)
- Gradual rollout (deploy and validate one pattern at a time)
- Cost control (exclude expensive patterns like databases)

**Instance Filtering** enables:
- Deploy representative samples (e.g., first 3 instances of each pattern)
- Subset testing (deploy instance 0 for validation, then deploy all)
- Resource limit compliance (stay within subscription quotas)

**Combined Filtering** enables precise control:
```bash
# Deploy only the first Web Application instance
--pattern-filter "Web Application" --instance-filter "0"
```

## Comparison to Alternative Approaches

### Resource-by-Resource Replication

**Traditional Approach**:
- Select individual resources manually
- Copy configuration one resource at a time
- Manually identify dependencies

**Limitations**:
- Time-consuming for large infrastructures
- Prone to missing relationships
- Difficult to maintain architectural consistency

**Architecture-Based Approach**:
- Automatically detects architectural patterns
- Selects complete pattern instances (resources + relationships)
- Maintains architectural intent by design

### Template-Based Deployment

**Template Approach**:
- Create generic ARM/Terraform templates
- Parameterize for different environments
- Deploy from templates

**Limitations**:
- Requires pre-existing templates (manual creation)
- Templates may not match actual architecture
- Difficult to update templates as architecture evolves

**Architecture-Based Approach**:
- Learns templates from actual source tenant
- Always reflects current architecture
- Adapts to architectural changes automatically

### Full Tenant Cloning

**Clone Approach**:
- Copy every resource from source to target
- Include all configurations and relationships

**Limitations**:
- Expensive (replicates everything, including unused resources)
- May violate naming constraints (globally unique names)
- No selective deployment

**Architecture-Based Approach**:
- Selective replication (only representative patterns)
- Cost-effective (deploy what you need)
- Supports gradual rollout and validation

## Benefits

### Architectural Preservation

- Maintains relationships between resources (CONTAINS, DEPENDS_ON, etc.)
- Preserves architectural patterns from source tenant
- Ensures deployed infrastructure matches intended design

### Automation

- Zero manual resource selection required
- Pattern detection is fully automated
- Relationship discovery is automatic

### Flexibility

- Filter by architectural pattern (deploy specific workload types)
- Filter by instance (deploy representative samples)
- Support multiple IaC formats (Terraform, Bicep, ARM)

### Cost Efficiency

- Deploy only what you need (not entire tenant)
- Selective pattern deployment controls costs
- Instance filtering enables subset testing

### Validation

- Dry-run mode generates IaC without deployment
- Review generated infrastructure before deploying
- Gradual rollout via pattern/instance filtering

## Use Cases

### Development/Test Environment Creation

Deploy representative samples to create dev/test environments:
```bash
# Deploy 2 instances of each pattern for testing
--instance-filter "0-1"
```

### Disaster Recovery Preparation

Replicate production architecture to DR environment:
```bash
# Deploy all patterns to DR region
--location "westus2"
```

### Multi-Region Deployment

Deploy same architecture across multiple regions:
```bash
# Deploy to region 1
azure-tenant-grapher deploy --from-replication-plan --location "eastus" --resource-group "prod-eastus"

# Deploy to region 2
azure-tenant-grapher deploy --from-replication-plan --location "westus" --resource-group "prod-westus"
```

### Incremental Migration

Migrate to new subscription pattern by pattern:
```bash
# Migrate web tier first
--pattern-filter "Web Application"

# Then migrate database tier
--pattern-filter "Database Services"
```

## Limitations and Future Enhancements

### Current Limitations

1. **Relationship Types**: Only includes 5 core types (CONTAINS, DEPENDS_ON, DIAGNOSTIC_TARGET, MONITORS, TAG_RELATIONSHIP)
   - Most deployments work fine with these
   - Advanced scenarios may need additional types

2. **Single Resource Group**: Deploys all resources to single target RG
   - Simplifies initial deployment
   - May not match complex multi-RG source architectures

3. **Control Plane Only**: Replicates infrastructure configuration, not data
   - Data plane plugins available separately (see DATAPLANE_PLUGIN_ARCHITECTURE.md)

4. **Globally Unique Names**: Limited coverage (13.9% - 5/36 resource types)
   - Storage Accounts, Key Vaults, Container Registries handled
   - Other types may require manual name adjustment

### Future Enhancements

**Phase 2** (Planned):
- Multi-RG deployment with structure preservation
- All relationship types support
- Enhanced name transformation coverage

**Phase 3** (Advanced):
- Cross-subscription replication
- Cross-region optimization
- Incremental deployment with validation gates
- Cost-aware instance selection

## Implementation Details

### Technologies Used

- **Pattern Detection**: NetworkX graph algorithms, spectral analysis
- **Neo4j**: Graph database for storing and querying tenant data
- **IaC Generation**: Terraform/Bicep/ARM template emitters
- **Deployment**: Azure SDK for Python, Azure CLI

### Key Components

1. **ArchitecturalPatternAnalyzer**: Detects patterns from Neo4j graph
2. **ArchitecturePatternReplicator**: Generates replication plans
3. **replication_plan_to_tenant_graph()**: Converts plans to deployment graphs
4. **IaC Emitters**: Generate Terraform/Bicep/ARM templates
5. **Deployment Orchestrator**: Deploys IaC to target tenant

### Integration Points

- **Neo4j**: Source tenant graph storage
- **Azure CLI**: Target tenant authentication
- **Docker**: Neo4j container management
- **Terraform/Bicep/ARM**: Infrastructure deployment

## Further Reading

- [How to Deploy from Replication Plans](../howto/deploy-replication-plan.md) - Practical deployment guide
- [Architectural Pattern Analysis](../ARCHITECTURAL_PATTERN_ANALYSIS.md) - Pattern detection details
- [Architecture-Based Replication](../ARCHITECTURE_BASED_REPLICATION.md) - Replication algorithm details
- [IaC Plugin Architecture](../DATAPLANE_PLUGIN_ARCHITECTURE.md) - Data plane replication

## See Also

- [Graph Version Tracking](GRAPH_VERSION_TRACKING.md) - Track graph changes over time
- [Terraform Import Blocks](TERRAFORM_IMPORT_BLOCKS.md) - Import existing infrastructure
- [Contributing Guidelines](../CONTRIBUTING.md) - Contribute improvements

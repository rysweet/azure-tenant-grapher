# Scale-Up Service Package

Modular architecture for synthetic resource generation in Azure Tenant Grapher.

## Overview

This package provides three distinct scale-up strategies for generating synthetic Azure resources in the abstracted graph layer. All strategies create resources marked with synthetic metadata and maintain graph topology consistency.

## Architecture

### Package Structure

```
src/services/scale_up/
├── __init__.py               # Main orchestrator (ScaleUpService)
├── template_strategy.py      # Template-based replication
├── scenario_strategy.py      # Scenario topology generation
├── random_strategy.py        # Random resource generation
└── common.py                 # Shared utilities
```

### Components

#### ScaleUpService (Orchestrator)

Main entry point that coordinates the three scaling strategies. Provides:
- `scale_up_template()` - Replicate existing resources with variations
- `scale_up_scenario()` - Generate topology patterns (hub-spoke, multi-region, etc.)
- `scale_up_random()` - Generate resources within defined constraints
- `rollback_operation()` - Rollback synthetic resources by operation ID

#### Template Strategy

Analyzes existing abstracted resources and replicates them with variations while maintaining topology structure.

**Key Methods:**
- `replicate_resources()` - Create synthetic copies of base resources
- `clone_relationships()` - Replicate relationship patterns
- `build_resource_mapping()` - Map base resources to synthetic IDs
- `get_relationship_patterns()` - Extract patterns from base resources

**Performance:**
- Adaptive batch sizing for large operations (>10k resources)
- Parallel batch inserts with controlled concurrency
- Relationship pattern chunking for large resource sets

#### Scenario Strategy

Generates realistic Azure topology patterns for testing and development.

**Supported Scenarios:**
- **Hub-Spoke**: Central hub VNet with multiple spoke VNets
- **Multi-Region**: Resources distributed across Azure regions
- **Dev-Test-Prod**: Environment-based resource grouping

**Key Methods:**
- `generate_hub_spoke()` - Create hub-spoke network topology
- `generate_multi_region()` - Create multi-region deployment
- `generate_dev_test_prod()` - Create environment-based topology

#### Random Strategy

Generates random resources based on type distributions and relationship density constraints.

**Key Methods:**
- `generate_random_resources()` - Create resources by type distribution
- `generate_random_relationships()` - Create relationships by density

**Configuration:**
```python
config = {
    "resource_type_distribution": {
        "Microsoft.Compute/virtualMachines": 0.3,
        "Microsoft.Network/virtualNetworks": 0.2,
        "Microsoft.Storage/storageAccounts": 0.5
    },
    "relationship_density": 0.3,  # 0.0-1.0
    "seed": 42  # Optional for reproducibility
}
```

#### Common Utilities

Shared functionality used across all strategies:

- **Batch Operations**: `insert_resource_batch()`, `insert_relationship_batch()`
- **Parallel Processing**: `insert_batches_parallel()`, `insert_relationship_batches_parallel()`
- **Performance**: `get_adaptive_batch_size()`, `ensure_indexes()`

## Usage

### Basic Template-Based Scaling

```python
from src.services.scale_up import ScaleUpService
from src.utils.session_manager import Neo4jSessionManager

session_manager = Neo4jSessionManager(uri, username, password)
service = ScaleUpService(session_manager)

result = await service.scale_up_template(
    tenant_id="abc123",
    scale_factor=2.0,  # Double the resources
    resource_types=["Microsoft.Compute/virtualMachines"]
)

print(f"Created {result.resources_created} resources")
print(f"Created {result.relationships_created} relationships")
```

### Scenario-Based Topology

```python
result = await service.scale_up_scenario(
    tenant_id="abc123",
    scenario="hub-spoke",
    params={
        "spoke_count": 5,
        "resources_per_spoke": 10
    }
)
```

### Random Generation

```python
result = await service.scale_up_random(
    tenant_id="abc123",
    target_count=1000,
    config={
        "resource_type_distribution": {
            "Microsoft.Compute/virtualMachines": 0.4,
            "Microsoft.Network/virtualNetworks": 0.3,
            "Microsoft.Storage/storageAccounts": 0.3
        },
        "relationship_density": 0.2,
        "seed": 42
    }
)
```

### Rollback Operations

```python
deleted_count = await service.rollback_operation(
    operation_id="scale-20250110T123045-a1b2c3d4"
)
```

## Performance

### Optimization Features

- **Adaptive Batch Sizing**: Automatically adjusts batch size based on operation scale
- **Parallel Processing**: Concurrent batch inserts for operations >10k resources
- **Query Optimization**: Indexes on critical fields (synthetic, scale_operation_id)
- **Performance Monitoring**: Optional metrics collection for analysis

### Performance Targets

- 1000 resources in <30 seconds
- Linear scaling up to 100k resources
- Controlled concurrency (max 5 parallel batches)

## Synthetic Resource Metadata

All synthetic resources are marked with:

```python
{
    "synthetic": True,
    "scale_operation_id": "scale-YYYYMMDDTHHMMSS-{uuid}",
    "generation_strategy": "template|scenario|random",
    "generation_timestamp": "ISO 8601 timestamp",

    # Template strategy only
    "template_source_id": "original-resource-id",

    # Scenario strategy only
    "scenario_name": "hub-spoke|multi-region|dev-test-prod",
    "role": "hub|spoke",  # For hub-spoke
    "spoke_index": 0,     # For hub-spoke
    "region": "eastus",   # For multi-region
    "environment": "dev"  # For dev-test-prod
}
```

## Validation

Post-operation validation checks:

- All synthetic resources have required metadata fields
- All relationships connect valid resources
- Resource counts match expectations
- No orphaned synthetic resources

## Error Handling

- Automatic rollback on operation failure
- Detailed error messages with context
- Rollback status tracking in result objects

## Testing

Run tests:

```bash
pytest src/services/scale_up/ -v
```

Test coverage includes:
- Unit tests for each strategy module
- Integration tests for orchestrator
- Performance tests for large operations
- Rollback and validation tests

## Migration from Monolithic Service

The refactored package maintains 100% backward compatibility:

```python
# Old import (still works)
from src.services.scale_up_service import ScaleUpService

# New import (preferred)
from src.services.scale_up import ScaleUpService
```

All public methods have identical signatures and behavior.

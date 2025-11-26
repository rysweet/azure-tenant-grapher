# Resource Processing Module

This module provides robust, resumable, and parallel processing of Azure resources with improved error handling, progress tracking, and database operations. It uses the dual-graph architecture where every resource is stored as both an Original node and an Abstracted node.

## Module Structure

```
src/services/resource_processing/
    __init__.py              # Public API exports (backward compatible)
    stats.py                 # ProcessingStats dataclass (~50 lines)
    serialization.py         # Value serialization for Neo4j (~80 lines)
    validation.py            # Input validation (~100 lines)
    node_manager.py          # Dual-graph node creation (~350 lines)
    relationship_emitter.py  # Relationship handling (~200 lines)
    batch_processor.py       # Retry queue, workers (~250 lines)
    llm_integration.py       # LLM description generation (~200 lines)
    processor.py             # Main orchestrator (~300 lines)
```

## Public Interface

The module exports the following public API via `__init__.py`:

```python
from src.services.resource_processing import (
    # Core classes
    ProcessingStats,           # Statistics dataclass
    ResourceProcessor,         # Main orchestrator

    # Supporting classes
    NodeManager,              # Dual-graph node operations
    RelationshipEmitter,      # Relationship creation
    BatchProcessor,           # Retry queue and workers
    LLMIntegration,           # LLM description generation
    ResourceState,            # State checking

    # Database operations (backward compat)
    DatabaseOperations,       # Alias for NodeManager + RelationshipEmitter

    # Utilities
    serialize_value,          # Value serialization
    validate_resource_data,   # Input validation
    extract_identity_fields,  # Identity field extraction

    # Factory
    create_resource_processor,  # Factory function
)
```

## Backward Compatibility

The original import path is preserved:

```python
# Original import (still works)
from src.resource_processor import (
    ProcessingStats,
    ResourceProcessor,
    DatabaseOperations,
    ResourceState,
    serialize_value,
    create_resource_processor,
)

# New recommended import
from src.services.resource_processing import (
    ProcessingStats,
    ResourceProcessor,
    # ...
)
```

## Usage Examples

### Basic Resource Processing

```python
from src.services.resource_processing import ResourceProcessor, create_resource_processor

# Using factory function
processor = create_resource_processor(
    session_manager=neo4j_session_manager,
    llm_generator=llm_gen,  # optional
    resource_limit=100,
    max_retries=3,
    tenant_id="your-tenant-id",
)

# Process resources
stats = await processor.process_resources(
    resources=resource_list,
    max_workers=5,
    progress_callback=my_callback,
)

print(f"Processed: {stats.processed}, Success: {stats.successful}")
```

### Direct Node Operations

```python
from src.services.resource_processing import NodeManager

node_manager = NodeManager(session_manager, tenant_id="your-tenant-id")

# Create subscription
node_manager.upsert_subscription("sub-123", "My Subscription")

# Create resource group
node_manager.upsert_resource_group(
    rg_id="/subscriptions/sub-123/resourceGroups/my-rg",
    rg_name="my-rg",
    subscription_id="sub-123",
)

# Create dual-graph resource
node_manager.upsert_resource(resource_dict, processing_status="completed")
```

### Relationship Creation

```python
from src.services.resource_processing import RelationshipEmitter

emitter = RelationshipEmitter(session_manager)

# Create subscription-resource relationship
emitter.create_subscription_relationship("sub-123", "resource-id")

# Create resource group relationships
emitter.create_resource_group_relationships(resource)

# Create generic relationships
emitter.create_relationship("src-id", "CONNECTED_TO", "tgt-id")
```

### Batch Processing with Retries

```python
from src.services.resource_processing import BatchProcessor, BatchResult

processor = BatchProcessor(max_workers=5, max_retries=3, base_delay=1.0)

async def process_item(resource, attempt):
    # Your processing logic
    return True  # or False on failure

result: BatchResult = await processor.process_batch(
    resources=resource_list,
    worker=process_item,
    progress_callback=my_callback,
)

print(f"Processed: {result.processed}, Poisoned: {len(result.poisoned)}")
```

## Dual-Graph Architecture

This module implements the dual-graph architecture where every Azure resource is stored as two nodes:

1. **Original nodes** (`:Resource:Original`): Store real Azure IDs from the source tenant
2. **Abstracted nodes** (`:Resource`): Store translated IDs suitable for cross-tenant deployment

These are linked by `SCAN_SOURCE_NODE` relationships:

```
(abstracted:Resource)-[:SCAN_SOURCE_NODE]->(original:Resource:Original)
```

### ID Abstraction

Original Azure resource IDs like:
```
/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/my-rg/providers/Microsoft.Compute/virtualMachines/my-vm
```

Are abstracted to deterministic hash-based IDs like:
```
vm-a1b2c3d4e5f67890
```

This enables:
- Cross-tenant deployments with safe ID abstraction
- Query flexibility (original topology OR deployment view)
- Simplified IaC generation (no runtime translation needed)

## Error Handling

The module implements robust error handling:

- **Retry Queue**: Failed resources are retried with exponential backoff
- **Poison List**: Resources that fail after max retries are tracked
- **Validation**: Resources are validated before processing
- **Transaction Safety**: Dual-graph nodes are created atomically

## Performance Considerations

- **Parallel Processing**: Configurable worker count for concurrent processing
- **Seen Guard**: Thread-safe deduplication prevents duplicate processing
- **Batch Flushing**: Relationship buffers are flushed at the end of processing
- **Progress Callbacks**: Support for real-time progress tracking

## Module Dependencies

```
processor.py
    -> node_manager.py
        -> serialization.py
        -> validation.py
        -> IDAbstractionService
        -> TenantSeedManager
    -> relationship_emitter.py
    -> batch_processor.py
    -> llm_integration.py
    -> stats.py
```

## Testing

Each module has comprehensive unit tests:

```bash
# Run all resource processing tests
uv run pytest tests/services/resource_processing/ -v

# Run specific module tests
uv run pytest tests/services/resource_processing/test_stats.py -v
uv run pytest tests/services/resource_processing/test_node_manager.py -v
```

## Migration Guide

If you're upgrading from the monolithic `resource_processor.py`:

1. **No immediate changes required**: The old import path still works
2. **Recommended**: Update imports to use new module structure
3. **For new code**: Import from `src.services.resource_processing`

### Before (still works)
```python
from src.resource_processor import ResourceProcessor, ProcessingStats
```

### After (recommended)
```python
from src.services.resource_processing import ResourceProcessor, ProcessingStats
```

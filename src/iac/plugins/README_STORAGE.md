# Storage Account Data Plane Plugin

Complete implementation of the Storage Account data plane replication plugin for Azure Tenant Grapher.

## Overview

The Storage Plugin handles discovery and replication of Azure Storage Account data plane items including:
- **Blob containers** and blobs
- **File shares** and files
- **Tables** and entities
- **Queues** and messages

## Features

### Two Operation Modes

1. **Template Mode**: Discovers structure only (containers, shares, tables, queues)
   - Fast discovery without sampling blobs/files
   - Creates empty structures in target
   - Requires read-only permissions

2. **Replication Mode**: Discovers structure with data sampling
   - Samples blobs, files, entities, messages
   - Tracks sizes for migration estimation
   - Provides warnings for large data sets
   - Requires read/write permissions

### Capabilities

- Full support for all four storage services (blobs, files, tables, queues)
- Progress reporting integration
- Size tracking and warnings for large storage accounts
- Smart blob sampling (limits to 100 blobs per container during discovery)
- Automatic warnings for containers > 10GB
- Mode-aware permission management
- Comprehensive Terraform code generation

## Usage

### Basic Discovery

```python
from src.iac.plugins.storage_plugin import StoragePlugin
from src.iac.plugins.base_plugin import ReplicationMode

# Initialize plugin
plugin = StoragePlugin()

# Storage Account resource
resource = {
    "id": "/subscriptions/.../storageAccounts/mysa",
    "type": "Microsoft.Storage/storageAccounts",
    "name": "mysa"
}

# Discover items
items = plugin.discover(resource)

# Generate Terraform code
terraform_code = plugin.generate_replication_code(items, "terraform")
```

### Mode-Aware Operations

```python
# Check required permissions for each mode
template_perms = plugin.get_required_permissions(ReplicationMode.TEMPLATE)
replication_perms = plugin.get_required_permissions(ReplicationMode.REPLICATION)

# Discover with mode awareness
items = plugin.discover_with_mode(resource, ReplicationMode.TEMPLATE)

# Estimate operation time
estimated_seconds = plugin.estimate_operation_time(items, ReplicationMode.REPLICATION)

# Replicate with mode
result = plugin.replicate_with_mode(
    source_resource,
    target_resource,
    ReplicationMode.TEMPLATE
)
```

### With Progress Reporting

```python
class MyProgressReporter:
    def report_discovery(self, resource_id: str, item_count: int):
        print(f"Discovered {item_count} items in {resource_id}")

    def report_replication_progress(self, item_name: str, progress_pct: float):
        print(f"Replicating {item_name}: {progress_pct:.1f}%")

    def report_completion(self, result):
        print(f"Completed: {result.items_replicated} items replicated")

# Use with progress reporting
plugin = StoragePlugin(progress_reporter=MyProgressReporter())
items = plugin.discover(resource)
```

## Permissions Required

### Template Mode (Read-Only)

```yaml
Scope: Resource
Actions:
  - Microsoft.Storage/storageAccounts/read
DataActions:
  - Microsoft.Storage/storageAccounts/blobServices/containers/read
  - Microsoft.Storage/storageAccounts/fileServices/fileshares/read
  - Microsoft.Storage/storageAccounts/tableServices/tables/read
  - Microsoft.Storage/storageAccounts/queueServices/queues/read
```

### Replication Mode (Read/Write)

```yaml
Scope: Resource
Actions:
  - Microsoft.Storage/storageAccounts/read
  - Microsoft.Storage/storageAccounts/listKeys/action  # For AzCopy
DataActions:
  - Microsoft.Storage/storageAccounts/blobServices/containers/read
  - Microsoft.Storage/storageAccounts/blobServices/containers/write
  - Microsoft.Storage/storageAccounts/blobServices/containers/blobs/read
  - Microsoft.Storage/storageAccounts/blobServices/containers/blobs/write
  - Microsoft.Storage/storageAccounts/fileServices/fileshares/read
  - Microsoft.Storage/storageAccounts/fileServices/fileshares/write
  - Microsoft.Storage/storageAccounts/tableServices/tables/read
  - Microsoft.Storage/storageAccounts/tableServices/tables/write
  - Microsoft.Storage/storageAccounts/tableServices/tables/entities/read
  - Microsoft.Storage/storageAccounts/tableServices/tables/entities/write
  - Microsoft.Storage/storageAccounts/queueServices/queues/read
  - Microsoft.Storage/storageAccounts/queueServices/queues/write
  - Microsoft.Storage/storageAccounts/queueServices/queues/messages/read
  - Microsoft.Storage/storageAccounts/queueServices/queues/messages/write
```

## Terraform Code Generation

The plugin generates Terraform resources for:

### Blob Containers

```hcl
resource "azurerm_storage_container" "data" {
  name                  = "data"
  storage_account_name  = azurerm_storage_account.REPLACE_ME.name
  container_access_type = "private"
}
```

### File Shares

```hcl
resource "azurerm_storage_share" "backup" {
  name                 = "backup"
  storage_account_name = azurerm_storage_account.REPLACE_ME.name
  quota                = 100
}
```

### Tables

```hcl
resource "azurerm_storage_table" "logs" {
  name                 = "logs"
  storage_account_name = azurerm_storage_account.REPLACE_ME.name
}
```

### Queues

```hcl
resource "azurerm_storage_queue" "processing" {
  name                 = "processing"
  storage_account_name = azurerm_storage_account.REPLACE_ME.name
}
```

### Migration Scripts

The generated code includes AzCopy migration scripts for data:

```bash
#!/bin/bash
SOURCE_ACCOUNT='source_account_name'
TARGET_ACCOUNT='target_account_name'

# Migrate container data
azcopy copy 'https://$SOURCE_ACCOUNT.blob.core.windows.net/data/*' \
            'https://$TARGET_ACCOUNT.blob.core.windows.net/data/' \
            --recursive
```

## Performance Considerations

### Blob Sampling Limits

- **Default**: 100 blobs sampled per container
- **Configurable**: Adjust `MAX_BLOB_SAMPLE` constant
- **Rationale**: Prevents excessive API calls on large containers

### Size Warnings

- **Large**: 1 GB threshold - informational warning
- **Very Large**: 10 GB threshold - explicit warning
- **Automatic**: Warnings included in generated Terraform comments

### Progress Tracking

```python
# Items include size_bytes for progress estimation
item = DataPlaneItem(
    name="container/large-blob.bin",
    item_type="blob",
    properties={"size": 1073741824},
    source_resource_id=resource_id,
    size_bytes=1073741824  # Used for progress calculations
)
```

## Error Handling

The plugin gracefully handles:

- **Missing Azure SDK**: Logs error with installation instructions
- **Permission errors**: Continues discovery, logs warnings
- **Network failures**: Logs specific service failures
- **Invalid resources**: Validates before processing

```python
try:
    items = plugin.discover(resource)
except ValueError as e:
    print(f"Invalid resource: {e}")
except Exception as e:
    print(f"Discovery error: {e}")
    # Plugin returns partial results, never crashes
```

## Testing

Comprehensive test suite with 32 tests covering:

- Basic plugin functionality
- Resource validation
- Permission management
- Code generation (all resource types)
- Mode-aware operations
- Time estimation
- Name sanitization
- Edge cases

Run tests:

```bash
uv run pytest tests/iac/plugins/test_storage_plugin.py -v
```

## Architecture Integration

### Base Plugin Inheritance

```python
class StoragePlugin(DataPlanePlugin):
    @property
    def supported_resource_type(self) -> str:
        return "Microsoft.Storage/storageAccounts"

    def get_required_permissions(self, mode: ReplicationMode) -> List[Permission]:
        # Mode-aware permissions
        ...

    def discover_with_mode(self, resource, mode) -> List[DataPlaneItem]:
        # Mode-aware discovery
        ...
```

### Plugin Registry

Automatically registered through plugin discovery:

```python
from src.iac.plugins.storage_plugin import StoragePlugin

# Automatically available to IaC generation
plugin = StoragePlugin()
if plugin.can_handle(resource):
    items = plugin.discover(resource)
```

## Data Migration Tools

The plugin recommends these tools for actual data migration:

1. **AzCopy**: Command-line utility for blob/file copy
   - Fast, optimized for Azure
   - Supports large files
   - Resumable transfers

2. **Azure Data Factory**: For large-scale, scheduled migrations
   - ETL pipeline support
   - Monitoring and logging
   - Complex transformation

3. **Azure Storage Explorer**: GUI tool for manual/selective migration
   - Visual interface
   - Good for small-scale migration
   - Supports all storage types

## Limitations

### Current Limitations

1. **Data replication not fully implemented**: Template mode works, but full data copy requires external tools (AzCopy, ADF)
2. **Blob type support**: Block blobs fully supported; page and append blobs discovered but may need special handling
3. **CORS/Lifecycle policies**: Not yet captured in discovery
4. **Encryption settings**: Not yet replicated

### Future Enhancements

- Direct data replication using Azure SDK
- CORS and lifecycle policy discovery
- Encryption key replication
- SAS token generation for secure copying
- Parallel blob transfer optimization
- Incremental sync support

## Examples

### Discover 61 Storage Accounts

```python
storage_accounts = [...]  # List of 61 storage account resources

results = []
for sa in storage_accounts:
    try:
        items = plugin.discover(sa)
        results.append({
            "account": sa["name"],
            "containers": len([i for i in items if i.item_type == "container"]),
            "blobs": len([i for i in items if i.item_type == "blob"]),
            "shares": len([i for i in items if i.item_type == "file_share"]),
            "tables": len([i for i in items if i.item_type == "table"]),
            "queues": len([i for i in items if i.item_type == "queue"]),
        })
    except Exception as e:
        results.append({"account": sa["name"], "error": str(e)})

# Generate summary report
total_containers = sum(r.get("containers", 0) for r in results)
total_blobs = sum(r.get("blobs", 0) for r in results)
print(f"Total: {total_containers} containers, {total_blobs} blobs (sampled)")
```

### Generate Complete IaC

```python
# Discover all items
all_items = []
for sa in storage_accounts:
    items = plugin.discover(sa)
    all_items.extend(items)

# Generate Terraform
terraform_code = plugin.generate_replication_code(all_items, "terraform")

# Write to file
with open("storage_dataplane.tf", "w") as f:
    f.write(terraform_code)
```

## Issue Tracking

- **GitHub Issue**: #353
- **Branch**: `feature/complete-storage-dataplane-plugin`
- **Status**: Implementation complete, awaiting integration tests

## References

- Architecture: `/docs/DATAPLANE_PLUGIN_ARCHITECTURE.md`
- Base plugin: `/src/iac/plugins/base_plugin.py`
- Tests: `/tests/iac/plugins/test_storage_plugin.py`
- AzCopy docs: https://docs.microsoft.com/azure/storage/common/storage-use-azcopy-v10

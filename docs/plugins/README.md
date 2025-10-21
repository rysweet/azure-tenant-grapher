# Data Plane Plugin System

This directory contains documentation for the Azure Tenant Grapher data plane plugin system.

## Overview

Data plane plugins enable replication of Azure resource data that exists outside the Azure Resource Manager control plane, such as:
- Key Vault secrets, keys, and certificates
- Storage Account blobs, containers, and files
- SQL Database schemas and data
- App Service configurations and content

## Documentation

- **[DATA_PLANE_PLUGIN_STATUS.md](DATA_PLANE_PLUGIN_STATUS.md)**: Current implementation status, completed work, and improvement roadmap
- **[PLUGIN_DEVELOPMENT_GUIDE.md](PLUGIN_DEVELOPMENT_GUIDE.md)**: Guide for developing new data plane plugins (coming soon)

## Plugin Architecture

### Core Components

1. **Base Plugin** (`src/iac/plugins/base_plugin.py`):
   - `DataPlanePlugin`: Abstract base class
   - `DataPlaneItem`: Represents discovered data
   - `ReplicationResult`: Operation results

2. **Plugin Registry** (`src/iac/plugins/__init__.py`):
   - Auto-discovery system
   - Resource type mapping
   - Public API

3. **Implemented Plugins**:
   - **KeyVaultPlugin** (`src/iac/plugins/keyvault_plugin.py`): Secrets, keys, certificates
   - **StoragePlugin** (`src/iac/plugins/storage_plugin.py`): Blobs, containers, file shares

## Quick Start

### Using Existing Plugins

```python
from src.iac.plugins import PluginRegistry

# Get plugin for a resource
resource = {"type": "Microsoft.KeyVault/vaults", "id": "...", "name": "my-kv"}
plugin = PluginRegistry.get_plugin_for_resource(resource)

# Discover data plane items
items = plugin.discover(resource)

# Generate IaC code
terraform_code = plugin.generate_replication_code(items, "terraform")

# Replicate data from source to target
result = plugin.replicate(source_resource, target_resource)
```

### Development Status

See [DATA_PLANE_PLUGIN_STATUS.md](DATA_PLANE_PLUGIN_STATUS.md) for detailed status.

**Summary:**
- ✅ Architecture complete
- ✅ KeyVault discovery and code generation
- ✅ Storage discovery and code generation
- ⚠️ KeyVault replication (in progress)
- ⚠️ Storage replication (in progress)
- ❌ SQL, App Service, Function App plugins (planned)

## Testing

```bash
# Run plugin tests
uv run pytest tests/iac/plugins/ -v

# Run specific plugin tests
uv run pytest tests/iac/plugins/test_keyvault_plugin.py -v
```

## Contributing

When adding a new data plane plugin:

1. Inherit from `DataPlanePlugin`
2. Implement required abstract methods:
   - `discover()`: Find data plane items
   - `generate_replication_code()`: Generate IaC
   - `replicate()`: Perform actual replication
3. Register in `PluginRegistry.discover_plugins()`
4. Add comprehensive tests (60% unit, 30% integration, 10% E2E)
5. Update documentation

## Integration

Plugins integrate with:
- **IaC Generation** (`src/iac/engine.py`): Called during `atg generate-iac`
- **Tenant Replication** (`src/tenant_creator.py`): Called during `atg create-tenant`

See integration documentation (coming soon) for details.

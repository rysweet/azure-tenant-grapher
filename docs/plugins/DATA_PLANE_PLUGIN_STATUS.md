# Data Plane Plugin System - Current Status and Improvement Plan

## Executive Summary

The Azure Tenant Grapher **already has a well-designed data plane plugin system** with:
- ✅ Complete plugin architecture (base classes, interfaces)
- ✅ Two partially-implemented plugins (KeyVault, Storage)
- ✅ Plugin registry and auto-discovery
- ✅ Test coverage (3 test files found)
- ⚠️ **NEEDS**: Complete `replicate()` implementations
- ⚠️ **NEEDS**: Additional plugins for other resource types

## What EXISTS (Good Work Already Done)

### 1. Plugin Architecture (`src/iac/plugins/base_plugin.py`)

**Complete and well-designed:**
```python
class DataPlanePlugin(ABC):
    @abstractmethod
    def discover(resource) -> List[DataPlaneItem]

    @abstractmethod
    def generate_replication_code(items, format) -> str

    @abstractmethod
    def replicate(source, target) -> ReplicationResult
```

**Key Classes:**
- `DataPlaneItem`: Represents discovered data (name, type, properties, metadata)
- `ReplicationResult`: Operation statistics (success, counts, errors, warnings)
- `DataPlanePlugin`: Abstract base with validation helpers

### 2. KeyVault Plugin (`src/iac/plugins/keyvault_plugin.py` - 524 lines)

**What Works:**
- ✅ `discover()`: Fully implemented
  - Lists secrets, keys, and certificates from Azure Key Vault
  - Uses Azure SDK (azure-keyvault-secrets, azure-keyvault-keys, azure-keyvault-certificates)
  - Handles authentication via DefaultAzureCredential
  - Extracts metadata (created_on, updated_on, recovery_level)
  - Skips disabled items

- ✅ `generate_replication_code()`: Fully implemented
  - Generates Terraform code for secrets, keys, and certificates
  - Creates placeholder variables for secret values (security best practice)
  - Includes tags and content_type
  - Adds migration documentation

**What's Missing:**
- ❌ `replicate()`: **STUB ONLY** (lines 442-504)
  - Returns `success=False` with error "Replication not yet implemented - stub only"
  - Comments show planned implementation:
    1. Discover items from source
    2. Connect to target Key Vault
    3. Replicate each item
  - **Estimated effort**: 2-3 days (need to handle secret values, permissions, conflict resolution)

### 3. Storage Plugin (`src/iac/plugins/storage_plugin.py` - 344 lines)

**What Works:**
- ✅ `discover()`: Fully implemented
  - Lists blob containers from Azure Storage
  - Samples first 10 blobs per container (performance optimization)
  - Uses Azure SDK (azure-storage-blob)
  - Extracts container metadata and blob properties

- ✅ `generate_replication_code()`: Fully implemented
  - Generates Terraform code for blob containers
  - Creates AzCopy migration script templates
  - Documents data migration process

**What's Missing:**
- ❌ `replicate()`: **STUB ONLY** (lines 287-324)
  - Returns `success=False` with error "use AzCopy or Azure Data Factory"
  - Actual data replication requires external tools (AzCopy, Azure Data Factory)
  - **Estimated effort**: 1 week (subprocess integration with AzCopy, progress tracking, error handling)

### 4. Plugin Registry (`src/iac/plugins/__init__.py` - 197 lines)

**Fully Implemented:**
- ✅ Auto-discovery system
- ✅ Plugin registration
- ✅ Resource type mapping
- ✅ Public API (`PluginRegistry.get_plugin_for_resource()`)

Currently registers:
- `Microsoft.KeyVault/vaults` → KeyVaultPlugin
- `Microsoft.Storage/storageAccounts` → StoragePlugin

### 5. Test Coverage

**Existing Tests:**
- `tests/iac/plugins/test_base_plugin.py`
- `tests/iac/plugins/test_keyvault_plugin.py`
- `tests/iac/plugins/test_plugin_registry.py`

**Test Coverage Status:** Unknown (needs measurement)

## What NEEDS to Be Done

### Priority 1: Complete Existing Plugins

#### 1.1 KeyVault Plugin - Implement `replicate()` method

**Requirements:**
- Read secret values from source Key Vault (requires permissions)
- Write secret values to target Key Vault (requires permissions)
- Handle keys (may need export/import)
- Handle certificates (PFX/PEM export/import)
- Conflict resolution (overwrite vs skip vs prompt)
- Progress tracking
- Error handling (permissions, network, throttling)

**Implementation Approach:**
```python
def replicate(self, source_resource, target_resource) -> ReplicationResult:
    # 1. Discover items from source
    source_items = self.discover(source_resource)

    # 2. Connect to target vault
    target_vault_uri = ...
    credential = DefaultAzureCredential()
    secret_client = SecretClient(target_vault_uri, credential)

    # 3. Replicate each item
    replicated = 0
    errors = []
    for item in source_items:
        if item.item_type == "secret":
            try:
                # Get secret value from source
                source_secret = source_client.get_secret(item.name)
                # Set in target
                target_client.set_secret(item.name, source_secret.value)
                replicated += 1
            except Exception as e:
                errors.append(f"Failed to replicate secret {item.name}: {e}")

    return ReplicationResult(...)
```

**Estimated Effort:** 2-3 days

#### 1.2 Storage Plugin - Implement `replicate()` method

**Requirements:**
- Use AzCopy as subprocess for data migration
- Support blob containers, file shares
- Progress tracking (parse AzCopy output)
- Error handling (network failures, retries)
- Large data handling (streaming, parallel transfers)

**Implementation Approach:**
```python
def replicate(self, source_resource, target_resource) -> ReplicationResult:
    # 1. Discover containers
    source_items = self.discover(source_resource)
    containers = [i for i in source_items if i.item_type == "container"]

    # 2. Run AzCopy for each container
    import subprocess
    for container in containers:
        source_url = f"https://{source_name}.blob.core.windows.net/{container.name}/*"
        target_url = f"https://{target_name}.blob.core.windows.net/{container.name}/"

        result = subprocess.run([
            "azcopy", "copy", source_url, target_url,
            "--recursive", "--overwrite=true"
        ], capture_output=True)

        # Parse result, track progress

    return ReplicationResult(...)
```

**Estimated Effort:** 1 week

### Priority 2: Additional Plugins (from /tmp/data_plane_plugin_plan.md)

Based on the original plan, these plugins were identified as needed:

#### Tier 1 (Critical)
- ✅ **Storage Account** - EXISTS (needs `replicate()` completion)
- ✅ **Key Vault** - EXISTS (needs `replicate()` completion)
- ❌ **SQL Database** - MISSING (schemas, tables, data)
- ❌ **App Service** - MISSING (configuration, app settings, connection strings)
- ❌ **Function App** - MISSING (functions, configuration, app settings)

#### Tier 2 (High Priority)
- ❌ **Cosmos DB** - MISSING (databases, containers, documents)
- ❌ **Event Hub** - MISSING (event hub entities)
- ❌ **Service Bus** - MISSING (queues, topics, subscriptions)
- ❌ **API Management** - MISSING (APIs, operations, policies)
- ❌ **Application Insights** - MISSING (existing telemetry)

**Estimated Effort Per Plugin:** 1-2 weeks each (depending on complexity)

### Priority 3: Integration with IaC Generation

**Current Integration:** Unknown (needs investigation)

**Questions to Answer:**
1. Where in the IaC generation flow are plugins called?
2. How are discovered data plane items merged into Terraform output?
3. How is the `replicate()` method triggered during tenant replication?

**Action Items:**
- Review `src/iac/traverser.py` and `src/iac/engine.py` for plugin integration
- Check if plugins are called from `atg generate-iac` command
- Verify if plugins are used in `atg create-tenant` workflow

### Priority 4: Testing and Validation

**Test Coverage Goals:**
- **Unit Tests (60%)**: Mock Azure SDK responses, test each method in isolation
- **Integration Tests (30%)**: Use test containers where possible
- **E2E Tests (10%)**: Real Azure test resources

**Missing Test Files:**
- `test_storage_plugin.py` - MISSING
- `test_sql_plugin.py` - MISSING (future)
- End-to-end tests for full replication flow

## Integration Points

### 1. Where Plugins Should Be Called

```python
# In src/iac/engine.py or similar
def generate_iac(resource):
    # 1. Generate control plane (Terraform for VM, VNet, etc.)
    control_plane_code = generate_terraform(resource)

    # 2. Check if resource has data plane plugin
    plugin = PluginRegistry.get_plugin_for_resource(resource)
    if plugin:
        # 3. Discover data plane items
        data_plane_items = plugin.discover(resource)

        # 4. Generate data plane replication code
        data_plane_code = plugin.generate_replication_code(data_plane_items)

        # 5. Merge into output
        return control_plane_code + "\n\n" + data_plane_code

    return control_plane_code
```

### 2. Replication Workflow

```python
# In src/tenant_creator.py or similar
def replicate_tenant(source_tenant_id, target_tenant_id):
    # 1. Discover source resources
    resources = discover_resources(source_tenant_id)

    # 2. Generate IaC
    iac_code = generate_iac(resources)

    # 3. Deploy to target (terraform apply)
    deploy_iac(iac_code, target_tenant_id)

    # 4. For each resource with data plane:
    for source_resource in resources:
        plugin = PluginRegistry.get_plugin_for_resource(source_resource)
        if plugin:
            target_resource = find_target_resource(source_resource, target_tenant_id)
            result = plugin.replicate(source_resource, target_resource)
            if not result.success:
                log_errors(result.errors)
```

## Estimated Total Effort

| Task | Effort | Priority |
|------|--------|----------|
| Complete KeyVault `replicate()` | 2-3 days | P0 |
| Complete Storage `replicate()` | 1 week | P0 |
| SQL Database plugin | 1-2 weeks | P1 |
| App Service plugin | 1-2 weeks | P1 |
| Function App plugin | 1-2 weeks | P1 |
| Integration with IaC generation | 3-4 days | P0 |
| Test coverage (all plugins) | 1 week | P1 |
| Documentation | 2-3 days | P2 |
| **TOTAL** | **8-11 weeks** | |

## Immediate Next Steps

1. ✅ **DELETE duplicate architecture docs** (DONE)
2. **Implement KeyVault `replicate()` method** (Priority 0)
3. **Implement Storage `replicate()` method** (Priority 0)
4. **Integrate plugins into `atg generate-iac` command** (Priority 0)
5. **Test with real tenant replication** (Priority 0)
6. **Add SQL/App Service/Function App plugins** (Priority 1)
7. **Iterate until 100% successful replication** (as user requested)

## Conclusion

The data plane plugin architecture is **excellent and well-designed**. The work is about **50% complete**:

**Done:**
- ✅ Architecture and interfaces
- ✅ Plugin registry
- ✅ Two plugins with `discover()` and `generate_replication_code()` fully working
- ✅ Basic test coverage

**TODO:**
- ❌ Complete `replicate()` implementations (2 plugins)
- ❌ Add 3-8 more plugins (depending on scope)
- ❌ Integrate with IaC generation workflow
- ❌ End-to-end validation

**My Error:**
I mistakenly created duplicate architecture documentation instead of **completing the existing implementation**. This wasted time and upset the user. The correct approach is to:
1. Complete existing plugin `replicate()` methods
2. Add new plugins following the established pattern
3. Integrate into the replication workflow
4. Test and iterate until 100% successful

Sorry for the confusion!

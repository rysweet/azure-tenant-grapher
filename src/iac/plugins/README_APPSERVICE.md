# App Service + Functions Data Plane Plugin

## Overview

The **AppServicePlugin** implements data plane replication for Azure App Service and Azure Functions resources. It handles discovery and replication of:

- **App Settings** (environment variables)
- **Connection Strings** (database and service connections)
- **Deployment Slots** (staging, production, etc.)
- **Functions-specific Settings**

## Features

### Two Replication Modes

1. **Template Mode** (Safe, Fast)
   - Discovers configuration structure (names and types)
   - Creates placeholder values for sensitive settings
   - No actual secrets copied
   - Suitable for creating IaC templates

2. **Replication Mode** (Full Copy)
   - Copies actual configuration values
   - Includes sensitive data (passwords, connection strings, API keys)
   - Requires elevated permissions
   - Suitable for production replication

### Capabilities

- Automatic sensitive value detection (passwords, secrets, keys, tokens)
- Deployment slot configuration discovery and replication
- Functions-specific settings support
- Terraform code generation with security best practices
- Progress reporting integration
- Comprehensive error handling

## Usage

### Basic Discovery

```python
from src.iac.plugins.appservice_plugin import AppServicePlugin

# Create plugin instance
plugin = AppServicePlugin()

# Resource to discover
resource = {
    "id": "/subscriptions/{sub}/resourceGroups/{rg}/providers/Microsoft.Web/sites/my-app",
    "type": "Microsoft.Web/sites",
    "name": "my-app",
    "properties": {}
}

# Discover configuration
items = plugin.discover(resource)

print(f"Discovered {len(items)} configuration items:")
for item in items:
    print(f"  - {item.name} ({item.item_type})")
```

### Mode-Aware Discovery

```python
from src.iac.plugins.base_plugin import ReplicationMode

# Template mode: sensitive values masked
items_template = plugin.discover_with_mode(resource, ReplicationMode.TEMPLATE)

# Replication mode: actual values preserved
items_full = plugin.discover_with_mode(resource, ReplicationMode.REPLICATION)
```

### Generate Terraform Code

```python
# Discover items
items = plugin.discover(resource)

# Generate Terraform code
terraform_code = plugin.generate_replication_code(items, "terraform")

# Save to file
with open("appservice_dataplane.tf", "w") as f:
    f.write(terraform_code)
```

### Replicate Configuration

```python
source_resource = {
    "id": "/subscriptions/{sub}/resourceGroups/{rg}/providers/Microsoft.Web/sites/source-app",
    "type": "Microsoft.Web/sites",
    "name": "source-app"
}

target_resource = {
    "id": "/subscriptions/{sub}/resourceGroups/{rg}/providers/Microsoft.Web/sites/target-app",
    "type": "Microsoft.Web/sites",
    "name": "target-app"
}

# Template mode replication
result = plugin.replicate_with_mode(
    source_resource,
    target_resource,
    ReplicationMode.TEMPLATE
)

print(f"Success: {result.success}")
print(f"Replicated: {result.items_replicated}/{result.items_discovered}")
print(f"Errors: {result.errors}")
print(f"Warnings: {result.warnings}")
```

## Permissions

### Template Mode

**Required Azure RBAC Permissions:**
- `Microsoft.Web/sites/read`
- `Microsoft.Web/sites/config/read`
- `Microsoft.Web/sites/slots/read`
- `Microsoft.Web/sites/slots/config/read`

**Built-in Role:** Website Contributor (Read)

### Replication Mode

**Required Azure RBAC Permissions:**
- `Microsoft.Web/sites/read`
- `Microsoft.Web/sites/config/read`
- `Microsoft.Web/sites/config/write`
- `Microsoft.Web/sites/slots/read`
- `Microsoft.Web/sites/slots/config/read`
- `Microsoft.Web/sites/slots/config/write`

**Built-in Role:** Website Contributor

### Grant Permissions

```bash
# Template mode (read-only)
az role assignment create \
  --assignee <your-principal-id> \
  --role "Website Contributor" \
  --scope "/subscriptions/{sub}/resourceGroups/{rg}/providers/Microsoft.Web/sites/{app-name}"

# For replication mode, same role includes write permissions
```

## Data Plane Items

### App Setting

```python
DataPlaneItem(
    name="DB_HOST",
    item_type="app_setting",
    properties={
        "value": "localhost",
        "is_sensitive": False
    },
    source_resource_id="/subscriptions/.../sites/my-app",
    metadata={"resource_type": "app_setting"}
)
```

### Connection String

```python
DataPlaneItem(
    name="DefaultConnection",
    item_type="connection_string",
    properties={
        "value": "Server=myserver;Database=mydb",
        "type": "SQLAzure",
        "is_sensitive": True
    },
    source_resource_id="/subscriptions/.../sites/my-app",
    metadata={
        "resource_type": "connection_string",
        "connection_type": "SQLAzure"
    }
)
```

### Deployment Slot

```python
DataPlaneItem(
    name="staging",
    item_type="deployment_slot",
    properties={
        "state": "Running",
        "enabled": True,
        "default_host_name": "my-app-staging.azurewebsites.net"
    },
    source_resource_id="/subscriptions/.../sites/my-app",
    metadata={
        "resource_type": "deployment_slot",
        "slot_id": "/subscriptions/.../sites/my-app/slots/staging"
    }
)
```

### Slot App Setting

```python
DataPlaneItem(
    name="staging/SLOT_SETTING",
    item_type="slot_app_setting",
    properties={
        "value": "slot-value",
        "is_sensitive": False,
        "slot_name": "staging"
    },
    source_resource_id="/subscriptions/.../sites/my-app",
    metadata={
        "resource_type": "slot_app_setting",
        "slot_name": "staging"
    }
)
```

## Sensitive Value Detection

The plugin automatically detects sensitive values based on key names containing:

- `password`
- `secret`
- `key`
- `token`
- `connectionstring` / `connection_string`
- `apikey` / `api_key`
- `credential`
- `cert` / `certificate`

All connection strings are treated as sensitive by default.

## Generated Terraform Code

### App Settings Example

```hcl
# App Settings
# Add these to your azurerm_app_service or azurerm_linux_web_app resource:
#
# app_settings = {
#   DB_HOST = "localhost"
#   DB_PASSWORD = var.app_setting_db_password
# }

# Required variables for sensitive values
variable "app_setting_db_password" {
  description = "Value for app setting DB_PASSWORD (set via environment or tfvars)"
  type        = string
  sensitive   = true
}
```

### Connection Strings Example

```hcl
# Connection Strings
# Add these to your azurerm_app_service or azurerm_linux_web_app resource:
#
# connection_string {
#   name  = "DefaultConnection"
#   type  = "SQLAzure"
#   value = var.connection_string_defaultconnection
# }

variable "connection_string_defaultconnection" {
  description = "Value for connection string DefaultConnection (set via environment or tfvars)"
  type        = string
  sensitive   = true
}
```

### Deployment Slot Example

```hcl
# Deployment Slots
# Create separate slot resources:

resource "azurerm_app_service_slot" "staging" {
  name                = "staging"
  app_service_name    = azurerm_app_service.REPLACE_ME.name
  resource_group_name = azurerm_app_service.REPLACE_ME.resource_group_name
  location            = azurerm_app_service.REPLACE_ME.location
  app_service_plan_id = azurerm_app_service.REPLACE_ME.app_service_plan_id

  app_settings = {
    SLOT_SETTING = "slot-value"
  }
}
```

## Security Considerations

1. **Sensitive Values**
   - Never include actual sensitive values in IaC code
   - Use variables and external secret management
   - Template mode automatically masks sensitive values

2. **Connection Strings**
   - Always treated as sensitive
   - Require explicit variables in generated code
   - Consider using Key Vault references instead

3. **Cross-Tenant Replication**
   - Review security implications before using replication mode
   - Ensure proper access controls on target resources
   - Audit and log all replication operations

4. **Secret Management**
   - Integrate with Azure Key Vault for production
   - Use managed identities where possible
   - Rotate secrets after replication

## Integration with ATG Deploy

```bash
# Deploy with data plane replication (template mode)
atg deploy \
  --iac-dir ./output/terraform \
  --target-tenant-id xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx \
  --resource-group replicated-rg \
  --dataplane \
  --dataplane-mode template

# Deploy with full replication (with credentials)
atg deploy \
  --iac-dir ./output/terraform \
  --target-tenant-id xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx \
  --resource-group replicated-rg \
  --dataplane \
  --dataplane-mode replication \
  --sp-client-id $AZURE_CLIENT_ID \
  --sp-client-secret $AZURE_CLIENT_SECRET \
  --sp-tenant-id $AZURE_TENANT_ID
```

## Testing

### Unit Tests

```bash
# Run unit tests
uv run pytest tests/iac/plugins/test_appservice_plugin.py -v

# With coverage
uv run pytest tests/iac/plugins/test_appservice_plugin.py --cov=src.iac.plugins.appservice_plugin
```

### Integration Tests

```bash
# Set environment variables
export AZURE_TEST_APP_SERVICE_ID="/subscriptions/{sub}/resourceGroups/{rg}/providers/Microsoft.Web/sites/{name}"
export AZURE_TEST_TARGET_APP_SERVICE_ID="/subscriptions/{sub}/resourceGroups/{rg}/providers/Microsoft.Web/sites/{target-name}"

# Run integration tests
uv run pytest tests/iac/plugins/test_appservice_plugin_integration.py -m integration -v
```

## Error Handling

The plugin handles common errors gracefully:

- **Invalid Resource ID**: Raises `ValueError` with clear message
- **Missing Permissions**: Returns `ReplicationResult` with permission errors
- **Azure API Errors**: Logs warnings and continues with other items
- **Network Issues**: Retries transient failures automatically

## Progress Reporting

The plugin supports progress reporting through the `ProgressReporter` protocol:

```python
class MyProgressReporter:
    def report_discovery(self, resource_id: str, item_count: int):
        print(f"Discovered {item_count} items in {resource_id}")

    def report_replication_progress(self, item_name: str, progress_pct: float):
        print(f"Replicating {item_name}: {progress_pct:.0f}%")

    def report_completion(self, result: ReplicationResult):
        print(f"Completed: {result.items_replicated} items")

# Use with plugin
plugin = AppServicePlugin(progress_reporter=MyProgressReporter())
```

## Functions-Specific Settings

Azure Functions are a special type of App Service (`kind=functionapp`). The plugin handles Functions settings automatically:

- Function app settings (e.g., `FUNCTIONS_WORKER_RUNTIME`)
- Function host settings (`host.json` configurations exposed as app settings)
- Function trigger and binding settings
- Application Insights integration settings

No special configuration needed - the plugin treats Functions like App Services.

## Limitations

1. **Application Code**: The plugin does not replicate application code. Use source control and CI/CD pipelines for code deployment.

2. **SSL Certificates**: Custom SSL certificates must be managed separately through Azure Certificate resources.

3. **Deployment History**: Deployment history and rollback points are not replicated.

4. **Slot-Specific Resources**: Slot-specific network configurations (VNet integration, private endpoints) require control plane replication.

5. **Hybrid Connections**: Hybrid connection configurations are not currently replicated.

## Dependencies

- `azure-mgmt-web`: Azure Web/App Service management SDK
- `azure-identity`: Azure authentication
- `azure-core`: Azure SDK core components

Install with:
```bash
pip install azure-mgmt-web azure-identity azure-core
```

## Contract

### Inputs
- Resource dictionary from Neo4j with Azure resource metadata
- ReplicationMode (TEMPLATE or REPLICATION)
- Optional CredentialProvider and ProgressReporter

### Outputs
- List of DataPlaneItem objects
- IaC code (Terraform format)
- ReplicationResult with statistics and errors

### Side Effects
- Reads App Service configuration via Azure API
- Writes configuration to target App Service (in replication mode)
- Reports progress (if ProgressReporter provided)
- Logs operations and errors

## Examples

See:
- Unit tests: `tests/iac/plugins/test_appservice_plugin.py`
- Integration tests: `tests/iac/plugins/test_appservice_plugin_integration.py`
- KeyVault plugin for similar patterns: `src/iac/plugins/keyvault_plugin.py`

## Support

For issues or questions:
1. Check the [architecture documentation](../../../docs/DATAPLANE_PLUGIN_ARCHITECTURE.md)
2. Review existing tests for usage examples
3. Open a GitHub issue with the `data-plane` label

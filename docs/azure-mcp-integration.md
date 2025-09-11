# Azure MCP Integration

## Overview

The Azure MCP (Model Context Protocol) Client provides a natural language interface to Azure operations, allowing users to query and manage Azure resources using human-friendly commands instead of complex API calls.

## Features

- **Natural Language Queries**: Query Azure resources using plain English
- **Tenant Discovery**: Automatically discover and enumerate Azure tenants
- **Identity Management**: Query identity information and permissions
- **Resource Operations**: Execute Azure operations via simple commands
- **Multi-Tenant Support**: Seamlessly work across multiple Azure tenants

## Architecture

The Azure MCP Client (`azure_mcp_client.py`) integrates with the existing Azure Tenant Grapher architecture:

```
┌─────────────────────┐
│   User/CLI          │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐     ┌─────────────────────┐
│  AzureMCPClient     │────▶│   MCP Server        │
└──────────┬──────────┘     └─────────────────────┘
           │
           ▼
┌─────────────────────┐     ┌─────────────────────┐
│ AzureDiscoveryService│────▶│  TenantManager      │
└─────────────────────┘     └─────────────────────┘
```

## Installation & Setup

1. **Start the MCP Server** (if not already running):
   ```bash
   python -m src.mcp_server
   ```

2. **Configure MCP in your environment**:
   ```python
   # In your .env file or configuration
   MCP_ENABLED=true
   MCP_ENDPOINT=http://localhost:8080
   ```

## Usage

### Basic Usage

```python
from src.services import create_mcp_client
from src.config_manager import AzureTenantGrapherConfig

# Create configuration
config = AzureTenantGrapherConfig(tenant_id="your-tenant-id")

# Create and connect MCP client
async with await create_mcp_client(config) as mcp_client:
    # Query resources with natural language
    result = await mcp_client.query_resources("show all VMs in production")

    for resource in result["results"]:
        print(f"- {resource['name']} ({resource['type']})")
```

### Natural Language Queries

The MCP client understands various natural language patterns:

```python
# Discovery queries
await mcp_client.query_resources("list all resource groups")
await mcp_client.query_resources("show virtual machines in East US")
await mcp_client.query_resources("find storage accounts with public access")

# Identity queries
await mcp_client.get_identity_info("what permissions do I have?")
await mcp_client.get_identity_info("show my current identity")

# Filtered queries
await mcp_client.query_resources("show resources tagged environment=production")
await mcp_client.query_resources("list resources created in the last 7 days")
```

### Integration with Discovery Service

The MCP client can be integrated with the existing `AzureDiscoveryService`:

```python
from src.services import (
    create_azure_discovery_service,
    create_mcp_client,
    integrate_with_discovery_service
)

# Create services
discovery_service = await create_azure_discovery_service(config)
mcp_client = await create_mcp_client(config)

# Integrate MCP with discovery
integrate_with_discovery_service(discovery_service, mcp_client)

# Now discovery service has natural language capabilities
result = await discovery_service.query_with_natural_language(
    "show all databases in production"
)
```

### Multi-Tenant Operations

```python
from src.services import TenantManager

# Create tenant manager
tenant_manager = TenantManager(neo4j_config)

# Create MCP client with tenant support
mcp_client = await create_mcp_client(
    config=config,
    tenant_manager=tenant_manager
)

# Discover tenants
tenants = await mcp_client.discover_tenants()
for tenant in tenants:
    print(f"Found: {tenant['display_name']}")

# Switch tenant context (if using tenant manager)
await tenant_manager.switch_tenant(tenant_id="other-tenant-id")

# Query resources in new tenant context
resources = await mcp_client.query_resources("list all resources")
```

## Examples

### Interactive Query Mode

Run the example script in interactive mode:

```bash
python examples/azure_mcp_example.py --interactive
```

This provides an interactive prompt where you can test natural language queries:

```
Azure MCP Interactive Query Mode
Type 'help' for examples, 'quit' to exit
--------------------------------------------------

Enter query > list all VMs
Executing: list all VMs
Found 3 resources:
  - prod-web-vm01 (Microsoft.Compute/virtualMachines)
  - prod-db-vm01 (Microsoft.Compute/virtualMachines)
  - dev-test-vm01 (Microsoft.Compute/virtualMachines)

Enter query > help
Example queries:
  - List all virtual machines in the tenant
  - Show resource groups in East US region
  - Find storage accounts with public access
  - Get my current identity and permissions
  ...
```

### Programmatic Usage

See `examples/azure_mcp_example.py` for a complete demonstration of:
- Tenant discovery
- Natural language resource queries
- Identity information retrieval
- Direct operation execution

## Configuration

### Environment Variables

- `MCP_ENABLED`: Enable/disable MCP integration (default: true)
- `MCP_ENDPOINT`: MCP server endpoint (default: http://localhost:8080)
- `AZURE_TENANT_ID`: Azure tenant ID for operations

### Config Object

```python
config = AzureTenantGrapherConfig(
    tenant_id="your-tenant-id",
    mcp_enabled=True,  # Enable MCP
    mcp_endpoint="http://localhost:8080"  # MCP server endpoint
)
```

## Error Handling

The MCP client provides specific exceptions for different failure scenarios:

```python
from src.services import MCPConnectionError, MCPOperationError

try:
    await mcp_client.connect()
except MCPConnectionError as e:
    print(f"Failed to connect to MCP server: {e}")
    # Fallback to direct Azure API calls

try:
    result = await mcp_client.execute_operation(operation)
except MCPOperationError as e:
    print(f"Operation failed: {e}")
    # Handle operation failure
```

## Testing

Run the test suite:

```bash
pytest tests/test_azure_mcp_client.py -v
```

The test suite covers:
- Connection management
- Natural language query parsing
- Tenant discovery
- Identity queries
- Integration with discovery service
- Error handling

## Limitations & Future Enhancements

### Current Limitations

- Basic natural language understanding (pattern matching)
- Limited to read operations initially
- Requires MCP server to be running

### Planned Enhancements

- Advanced NLP for query understanding
- Write operations (create, update, delete resources)
- Batch operations support
- Query optimization and caching
- Enhanced error recovery
- Support for complex Azure operations
- Integration with Azure Resource Graph for advanced queries

## Troubleshooting

### MCP Server Not Available

If you see "MCP is not available" errors:

1. Check if MCP server is running:
   ```bash
   curl http://localhost:8080/health
   ```

2. Start the MCP server:
   ```bash
   python -m src.mcp_server
   ```

3. Verify Neo4j is running (required by MCP server):
   ```bash
   docker ps | grep neo4j
   ```

### Connection Timeouts

If queries timeout:
- Check network connectivity to MCP endpoint
- Verify Azure credentials are configured
- Check MCP server logs for errors

### Natural Language Not Recognized

If queries aren't understood:
- Use simpler, more direct language
- Check available query examples with `get_natural_language_help()`
- Fall back to direct API operations if needed

## Contributing

When adding new natural language patterns:

1. Update `_operation_patterns` in `AzureMCPClient`
2. Add corresponding logic in `_execute_mcp_request`
3. Add tests for new patterns
4. Update documentation with examples

Follow the project's philosophy of starting simple and iterating based on real usage.

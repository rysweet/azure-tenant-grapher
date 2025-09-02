# MCP (Model Context Protocol) Integration

## Overview

The Azure Tenant Grapher now includes experimental support for MCP (Model Context Protocol) integration, allowing natural language queries and AI-powered analysis of Azure resources. This feature works alongside the existing discovery mechanisms, providing an optional enhancement rather than a replacement.

## Features

- **Natural Language Queries**: Query Azure resources using plain English
- **AI-Powered Insights**: Get security recommendations and resource analysis
- **Relationship Analysis**: Discover hidden dependencies between resources
- **Graceful Fallback**: Automatically falls back to traditional API methods when MCP is unavailable
- **Multiple Output Formats**: JSON, table, or plain text output

## Configuration

Add the following to your `.env` file to enable MCP integration:

```bash
# MCP Configuration
MCP_ENABLED=true                    # Enable MCP integration
MCP_ENDPOINT=http://localhost:8080  # MCP server endpoint
MCP_TIMEOUT=30                      # Request timeout in seconds
MCP_API_KEY=your-api-key            # Optional API key for authentication
```

## Usage

### Basic Natural Language Query

```bash
# List all virtual machines
atg mcp-query "list all virtual machines"

# Find storage accounts in a specific region
atg mcp-query "show storage accounts in westus2"

# Security analysis
atg mcp-query "find resources with public IP addresses"
atg mcp-query "analyze security posture of my key vaults"
```

### Command Options

```bash
atg mcp-query [OPTIONS] QUERY

Options:
  --tenant-id TEXT              Azure tenant ID (defaults to AZURE_TENANT_ID)
  --no-fallback                 Disable fallback to traditional API methods
  --format [json|table|text]    Output format for query results (default: json)
  --help                        Show this message and exit
```

### Examples

1. **List resources with specific characteristics**:
   ```bash
   atg mcp-query "show all resources tagged as production"
   ```

2. **Analyze resource relationships**:
   ```bash
   atg mcp-query "what resources depend on storage account mystorageaccount"
   ```

3. **Get security recommendations**:
   ```bash
   atg mcp-query "identify security risks in my network configuration"
   ```

4. **Table format output**:
   ```bash
   atg mcp-query --format table "list all databases"
   ```

5. **Disable fallback** (fail if MCP is unavailable):
   ```bash
   atg mcp-query --no-fallback "list VMs"
   ```

## Integration with Existing Features

The MCP integration works seamlessly with existing Azure Tenant Grapher features:

### During Resource Discovery

When MCP is enabled, the discovery service can use MCP for enhanced resource discovery:

```python
from src.services.mcp_integration import MCPIntegrationService
from src.config_manager import MCPConfig

# MCP will be used automatically if enabled in config
config = create_config_from_env(tenant_id)
if config.mcp.enabled:
    # MCP-enhanced discovery will be attempted first
    pass
```

### Programmatic Usage

You can also use the MCP integration programmatically:

```python
import asyncio
from src.services.mcp_integration import execute_mcp_query

async def main():
    success, result = await execute_mcp_query("list all virtual networks")
    if success:
        print(f"Found {len(result.get('resources', []))} resources")
    else:
        print(f"Query failed: {result.get('error')}")

asyncio.run(main())
```

## Architecture

The MCP integration follows a modular design:

```
┌─────────────────┐
│   CLI Command   │
└────────┬────────┘
         │
         v
┌─────────────────────────┐
│  MCPIntegrationService  │
├─────────────────────────┤
│ - Natural language      │
│ - Query translation     │
│ - Response formatting   │
└──────┬──────────────────┘
       │
       v
┌──────────────────────┐      ┌────────────────────────┐
│    MCP Server        │      │  AzureDiscoveryService │
│  (When Available)    │      │     (Fallback)         │
└──────────────────────┘      └────────────────────────┘
```

## Testing

Run the MCP integration tests:

```bash
# Run all MCP tests
pytest tests/test_mcp_integration.py -v

# Run specific test categories
pytest tests/test_mcp_integration.py::TestMCPConfig -v
pytest tests/test_mcp_integration.py::TestMCPIntegrationService -v
```

## Troubleshooting

### MCP Not Connecting

1. Check that MCP is enabled in your `.env`:
   ```bash
   MCP_ENABLED=true
   ```

2. Verify the MCP server is running:
   ```bash
   curl http://localhost:8080/health
   ```

3. Check logs for connection errors:
   ```bash
   atg --log-level DEBUG mcp-query "test"
   ```

### Timeout Issues

If queries are timing out, increase the timeout value:

```bash
MCP_TIMEOUT=60  # Increase to 60 seconds
```

### Fallback Behavior

By default, the system falls back to traditional API methods when MCP is unavailable. To debug MCP-specific issues, disable fallback:

```bash
atg mcp-query --no-fallback "your query"
```

## Limitations

- This is an **experimental feature** and may change in future versions
- MCP server must be running and accessible for full functionality
- Natural language understanding depends on the MCP server's capabilities
- Complex queries may take longer to process

## Future Enhancements

- Batch query support
- Query result caching
- Integration with graph visualization
- Custom query templates
- Query history and saved queries
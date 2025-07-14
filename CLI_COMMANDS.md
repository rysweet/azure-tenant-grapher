# Azure Tenant Grapher - CLI Commands

The Azure Tenant Grapher now provides convenient CLI commands that can be run directly without the `uv run python scripts/cli.py` prefix.

## Available Commands

After installation, you can use any of these command aliases:

### Short Commands
- `atg` - Short alias for Azure Tenant Grapher
- `azure-graph` - Medium alias
- `azure-tenant-grapher` - Full command name

All commands are identical and provide the same functionality.

## Usage Examples

### Quick Examples
```bash
# Show help
atg --help

# Build graph with dashboard (most common usage)
atg build

# Build with specific tenant and no dashboard
atg build --tenant-id "your-tenant-id" --no-dashboard

# Test with limited resources
atg test --limit 20

# Generate visualization
atg visualize

# Show configuration
atg config
```

### Detailed Examples
```bash
# Build graph with custom settings
atg build \
  --tenant-id "12345678-1234-1234-1234-123456789012" \
  --resource-limit 1000 \
  --max-llm-threads 10 \
  --generate-spec \
  --visualize

# Build without container auto-start
atg build --no-container --no-dashboard

# Generate specification only (requires existing graph)
atg spec

# Generate anonymized specification
atg generate-spec --output ./my-spec.md
```

## Dashboard Features

When using the dashboard (default for `atg build`):

- **Press 'x'** to exit the dashboard at any time
- **Press 'i'** to set log level to INFO
- **Press 'd'** to set log level to DEBUG
- **Press 'w'** to set log level to WARNING

The dashboard shows:
- **Config panel**: Shows all settings including log file location
- **Progress panel**: Real-time statistics and controls
- **Scrollable logs**: Filtered by level, with file logging to `/tmp/`

## File Logging

All dashboard sessions automatically create timestamped log files:
- **Location**: `/tmp/azure_tenant_grapher_YYYYMMDD_HHMMSS.log`
- **Content**: Complete debug-level logs regardless of dashboard filter
- **Path shown**: In the dashboard config panel

## Error Messages and Troubleshooting

All CLI commands provide actionable error messages for common issues, especially for Neo4j and Azure OpenAI (LLM) failures. If you see an error:
- **Neo4j errors:** Check that Neo4j is running, the container is healthy, and credentials are correct. Use `atg container` or `docker-compose up` to start the container if needed.
- **LLM errors:** Ensure all required Azure OpenAI environment variables are set and you have network connectivity.
- **Logs:** Run with `--log-level DEBUG` for more details. The dashboard and CLI will print the log file location for further inspection.

## Installation

The CLI commands are automatically available after running:
```bash
uv sync
```

This installs the package in development mode and makes the commands available in your PATH.

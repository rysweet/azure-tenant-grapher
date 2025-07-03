## mcp-server

The `mcp-server` command starts the MCP server, which enables agent-mode and natural language queries over your Azure graph. The command attempts to start Neo4j (via Docker Compose if needed) and then launch the server. This command may fail if Docker or Neo4j are not available or if there are code errors.

```bash
uv run azure-tenant-grapher mcp-server
```

**Output:**
```text
Starting Neo4j container...
{"event": "Setting up Neo4j container...", "timestamp": "...", "level": "info"}
{"event": "Docker Compose available: Docker Compose version 2.34.0", "timestamp": "...", "level": "info"}
{"event": "Starting Neo4j container...", "timestamp": "...", "level": "info"}
{"event": "Neo4j container started successfully", "timestamp": "...", "level": "info"}
{"event": "Waiting for Neo4j to be ready...", "timestamp": "...", "level": "info"}
❌ Failed to start MCP server: BoundLogger.info() got multiple values for argument 'event'
Traceback (most recent call last):
  ...
TypeError: BoundLogger.info() got multiple values for argument 'event'
```

**Troubleshooting:**
- If you see a TypeError or container startup error, check your Docker installation and ensure the code is up to date. This command may require additional setup or code fixes to run end-to-end.

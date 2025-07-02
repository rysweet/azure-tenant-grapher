## progress

The `progress` command checks the current processing status of your Azure graph in the Neo4j database. It is useful for monitoring long-running builds or verifying that the graph is up to date.

```bash
uv run azure-tenant-grapher progress
```

**Output:**
```text
INFO:src.config_manager:📝 Logging configured: level=INFO, file=console
📊 Checking processing progress...
🔍 Checking Neo4j database progress...
==================================================
❌ Error connecting to Neo4j: Couldn't connect to localhost:7687 (resolved to ('[::1]:7687', '127.0.0.1:7687')):
Failed to establish connection to ResolvedIPv6Address(('::1', 7687, 0, 0)) (reason [Errno 61] Connection refused)
Failed to establish connection to ResolvedIPv4Address(('127.0.0.1', 7687)) (reason [Errno 61] Connection refused)
💡 Make sure Neo4j is running on bolt://localhost:7688
```

**Troubleshooting:**
- If you see a connection error, ensure the Neo4j database is running and accessible at the configured address. You can start it with `docker-compose up` or the appropriate container management command.

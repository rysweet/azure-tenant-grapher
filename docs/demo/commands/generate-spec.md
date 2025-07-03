## generate-spec

The `generate-spec` command creates an anonymized tenant specification from the graph, suitable for sharing or further processing. The `--limit` flag restricts the number of resources for faster runs and easier testing. Requires a running Neo4j database.

```bash
uv run azure-tenant-grapher generate-spec --limit 3
```

**Output:**
```text
INFO:src.config_manager:📝 Logging configured: level=INFO, file=console
❌ Failed to generate tenant specification: Couldn't connect to localhost:7687 (resolved to ('[::1]:7687', '127.0.0.1:7687')):
Failed to establish connection to ResolvedIPv6Address(('::1', 7687, 0, 0)) (reason [Errno 61] Connection refused)
Failed to establish connection to ResolvedIPv4Address(('127.0.0.1', 7687)) (reason [Errno 61] Connection refused)
Traceback (most recent call last):
  ...
neo4j.exceptions.ServiceUnavailable: Couldn't connect to localhost:7687 (resolved to ('[::1]:7687', '127.0.0.1:7687')):
Failed to establish connection to ResolvedIPv6Address(('::1', 7687, 0, 0)) (reason [Errno 61] Connection refused)
Failed to establish connection to ResolvedIPv4Address(('127.0.0.1', 7687)) (reason [Errno 61] Connection refused)
```

**Troubleshooting:**
- If you see a connection error, ensure Neo4j is running and accessible at the configured URI. The graph must be built before running this command.

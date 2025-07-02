## visualize

The `visualize` command generates a 3D HTML visualization of your Azure graph from Neo4j data. This is useful for exploring relationships and resource topology visually. The `--no-container` flag disables auto-starting Neo4j, so you must ensure the database is running.

```bash
uv run azure-tenant-grapher visualize --no-container
```

**Output:**
```text
INFO:src.config_manager:📝 Logging configured: level=INFO, file=console
🎨 Generating graph visualization...
INFO:src.graph_visualizer:Generating 3D visualization HTML...
INFO:src.graph_visualizer:Extracting graph data from Neo4j...
INFO:src.graph_visualizer:Neo4j URI: bolt://localhost:7687
INFO:src.graph_visualizer:Neo4j User: neo4j
INFO:src.graph_visualizer:Neo4j Driver: None
INFO:src.graph_visualizer:Connecting to database: neo4j
ERROR:src.graph_visualizer:Failed to connect to Neo4j: Couldn't connect to localhost:7687 (resolved to ('[::1]:7687', '127.0.0.1:7687')):
Failed to establish connection to ResolvedIPv6Address(('::1', 7687, 0, 0)) (reason [Errno 61] Connection refused)
Failed to establish connection to ResolvedIPv4Address(('127.0.0.1', 7687)) (reason [Errno 61] Connection refused)
Traceback (most recent call last):
  ...
neo4j.exceptions.ServiceUnavailable: Couldn't connect to localhost:7687 (resolved to ('[::1]:7687', '127.0.0.1:7687')):
Failed to establish connection to ResolvedIPv6Address(('::1', 7687, 0, 0)) (reason [Errno 61] Connection refused)
Failed to establish connection to ResolvedIPv4Address(('127.0.0.1', 7687)) (reason [Errno 61] Connection refused)
⚠️  Failed to connect to Neo4j: Couldn't connect to localhost:7687 (resolved to ('[::1]:7687', '127.0.0.1:7687')):
Failed to establish connection to ResolvedIPv6Address(('::1', 7687, 0, 0)) (reason [Errno 61] Connection refused)
Failed to establish connection to ResolvedIPv4Address(('127.0.0.1', 7687)) (reason [Errno 61] Connection refused)
Action: Ensure Neo4j is running and accessible at the configured URI.
If using Docker, check that the container is started and healthy.
You can start the container with 'python scripts/cli.py container' or 'docker-compose up'.
❌ Neo4j is not running and --no-container was specified.
Action: Start Neo4j manually or remove --no-container to let the CLI manage it.
```

**Troubleshooting:**
- If you see a connection error, ensure Neo4j is running and accessible at the configured URI. Use Docker or your preferred method to start the database.

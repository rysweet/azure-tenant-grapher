## generate-iac

The `generate-iac` command generates Infrastructure-as-Code (IaC) templates from your Azure graph. The `--dry-run` flag allows you to test the command without writing files. Requires a running Neo4j database.

```bash
uv run azure-tenant-grapher generate-iac --dry-run
```

**Output:**
```text
🏗️ Starting IaC generation
Format: terraform
❌ IaC generation failed: [NEO4J_CONNECTION_FAILED] Failed to connect to Neo4j database (context: config_uri=bolt://localhost:7687, uri=bolt://localhost:7687) (caused by: Couldn't connect to localhost:7687 (resolved to ('[::1]:7687', '127.0.0.1:7687')):
Failed to establish connection to ResolvedIPv6Address(('::1', 7687, 0, 0)) (reason [Errno 61] Connection refused)
Failed to establish connection to ResolvedIPv4Address(('127.0.0.1', 7687)) (reason [Errno 61] Connection refused)) (suggestion: Check Neo4j connection settings and ensure the database is running)
❌ Error: [NEO4J_CONNECTION_FAILED] Failed to connect to Neo4j database (context: config_uri=bolt://localhost:7687, uri=bolt://localhost:7687) (caused by: Couldn't connect to localhost:7687 (resolved to ('[::1]:7687', '127.0.0.1:7687')):
Failed to establish connection to ResolvedIPv6Address(('::1', 7687, 0, 0)) (reason [Errno 61] Connection refused)
Failed to establish connection to ResolvedIPv4Address(('127.0.0.1', 7687)) (reason [Errno 61] Connection refused)) (suggestion: Check Neo4j connection settings and ensure the database is running)
```

**Troubleshooting:**
- If you see a connection error, ensure Neo4j is running and accessible at the configured URI. The graph must be built before running this command.

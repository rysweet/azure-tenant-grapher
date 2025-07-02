# `build` Command Walkthrough

The `build` command is the main entry point for discovering and processing your Azure tenant resources. This walkthrough demonstrates a minimal, fast invocation and includes real, redacted output.

## Usage

```bash
uv run azure-tenant-grapher build --resource-limit 3 --no-dashboard
```

## Example Output

```text
[DEBUG] CLI build command called
✅ Configuration validation successful
INFO:src.config_manager:📝 Logging configured: level=INFO, file=console
INFO:src.config_manager:✅ Configuration validation successful
INFO:src.llm_descriptions:{"endpoint": "...", "api_key_set": true, ...}
INFO:src.llm_descriptions:{"endpoint": "...", "event": "Initialized Azure LLM Description Generator", ...}
INFO:src.config_manager:============================================================
INFO:src.config_manager:🔧 AZURE TENANT GRAPHER CONFIGURATION
INFO:src.config_manager:============================================================
INFO:src.config_manager:📋 Tenant ID: [REDACTED]
INFO:src.config_manager:🗄️  Neo4j: bolt://localhost:7687 (user: neo4j)
INFO:src.config_manager:🤖 Azure OpenAI: https://...azure.com
INFO:src.config_manager:⚙️  Processing:
INFO:src.config_manager:   - Resource Limit: 3
INFO:src.config_manager:   - Max Concurrency: 5
INFO:src.config_manager:   - Max Retries: 3
INFO:src.config_manager:   - Parallel Processing: True
INFO:src.config_manager:   - Auto Start Container: True
INFO:src.config_manager:📄 Specification:
INFO:src.config_manager:   - Spec Resource Limit: 3
INFO:src.config_manager:   - Output Directory: .
INFO:src.config_manager:   - Include AI Summaries: True
INFO:src.config_manager:   - Include Config Details: True
INFO:src.config_manager:   - Template Style: comprehensive
INFO:src.config_manager:📝 Logging Level: INFO
INFO:src.config_manager:============================================================
INFO:src.cli_commands:{"log_file_path": "...azure_tenant_grapher_YYYYMMDD_HHMMSS.log", ...}
[YYYY/MM/DD HH:MM:SS] INFO     {"log_level": "INFO", "event": "Running in no-dashboard mode: logs will be emitted line by line.", ...}
❌ Failed to connect to Neo4j: [NEO4J_CONNECTION_FAILED] Failed to connect to Neo4j database (context: config_uri=bolt://localhost:7687, uri=bolt://localhost:7687) (caused by: Couldn't connect to localhost:7687 (resolved to ('[::1]:7687', '127.0.0.1:7687')):
Failed to establish connection to ResolvedIPv6Address(('::1', 7687, 0, 0)) (reason [Errno 61] Connection refused)
Failed to establish connection to ResolvedIPv4Address(('127.0.0.1', 7687)) (reason [Errno 61] Connection refused)) (suggestion: Check Neo4j connection settings and ensure the database is running)
Action: Ensure Neo4j is running and accessible at the configured URI.
If using Docker, check that the container is started and healthy.
You can start the container with 'python scripts/cli.py container' or 'docker-compose up'.
```

## Notes

- `--resource-limit 3` ensures the command completes quickly for demo/testing.
- `--no-dashboard` disables the interactive dashboard for CI/offline use.
- Output is redacted to remove tenant IDs, UUIDs, and credentials.
- For troubleshooting, see logs in the output directory or use `--log-level DEBUG`.
- If you see a Neo4j connection error, ensure the database is running (see above).

[Back to Command Index](README.md)

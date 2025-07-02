## agent-mode

The `agent-mode` command launches the AutoGen MCP agent for natural-language queries over your Azure graph. The `--question` flag allows you to run a one-off query and exit immediately. This command requires a running Neo4j database and MCP server.

```bash
uv run azure-tenant-grapher agent-mode --question "exit"
```

**Output:**
```text
Failed to start Neo4j: BoundLogger.info() got multiple values for argument 'event'
❌ Failed to start Neo4j: BoundLogger.info() got multiple values for argument 'event'
```

**Troubleshooting:**
- If you see a TypeError or Neo4j startup error, check your Docker installation and ensure the code is up to date. This command may require additional setup or code fixes to run end-to-end.

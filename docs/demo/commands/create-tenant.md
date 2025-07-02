## create-tenant

The `create-tenant` command ingests a tenant specification from a Markdown file and creates the corresponding resources in the graph. This is useful for bootstrapping a demo or test environment. The command requires a running Neo4j database and a valid tenant markdown file.

```bash
uv run azure-tenant-grapher create-tenant docs/demo/commands/create-tenant-sample.md
```

**Output:**
```text
{"event": "Setting up Neo4j container...", "timestamp": "...", "level": "info"}
{"event": "Docker Compose available: Docker Compose version 2.34.0", "timestamp": "...", "level": "info"}
{"event": "Starting Neo4j container...", "timestamp": "...", "level": "info"}
{"event": "Neo4j container started successfully", "timestamp": "...", "level": "info"}
{"event": "Waiting for Neo4j to be ready...", "timestamp": "...", "level": "info"}
❌ Failed to create tenant: BoundLogger.info() got multiple values for argument 'event'
Action: Check that the markdown file is valid and that Neo4j and Azure OpenAI are configured correctly. Run with --log-level DEBUG for more details.
```

**Troubleshooting:**
- If you see a TypeError or container startup error, check your Docker installation and ensure the code is up to date. This command may require additional setup or code fixes to run end-to-end.

## threat-model

The `threat-model` command runs the Threat Modeling Agent workflow, which attempts to start Neo4j (via Docker Compose if needed) and generate a threat model for your Azure tenant. This command demonstrates the agent's ability to orchestrate infrastructure and analysis, but may fail if Docker or Neo4j are not available or if there are code errors.

```bash
uv run azure-tenant-grapher threat-model
```

**Output:**
```text
🚀 Starting Threat Modeling Agent workflow...
{"event": "Setting up Neo4j container...", "timestamp": "...", "level": "info"}
{"event": "Docker Compose available: Docker Compose version 2.34.0", "timestamp": "...", "level": "info"}
{"event": "Starting Neo4j container...", "timestamp": "...", "level": "info"}
{"event": "Neo4j container started successfully", "timestamp": "...", "level": "info"}
{"event": "Waiting for Neo4j to be ready...", "timestamp": "...", "level": "info"}
Traceback (most recent call last):
  ...
TypeError: BoundLogger.info() got multiple values for argument 'event'
```

**Troubleshooting:**
- If you see a TypeError or container startup error, check your Docker installation and ensure the code is up to date. This command may require additional setup or code fixes to run end-to-end.

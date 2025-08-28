## backup-db

The `backup-db` command creates a backup of the Neo4j database and saves it to the specified path. This is useful for disaster recovery or migration scenarios. The command requires the Neo4j container to be running.

```bash
uv run azure-tenant-grapher backup-db outputs/my-neo4j-backup.dump
```

**Output:**
```text
{"event": "Starting Neo4j backup to outputs/my-neo4j-backup.dump", "timestamp": "...", "level": "info"}
{"event": "Neo4j container is not running. Cannot perform backup.", "timestamp": "...", "level": "error"}
❌ Neo4j backup failed
```

**Troubleshooting:**
- If you see a container error, ensure Neo4j is running before attempting a backup. Use Docker Compose or your preferred method to start the database.

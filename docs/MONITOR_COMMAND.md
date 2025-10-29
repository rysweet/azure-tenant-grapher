# ATG Monitor Command

The `atg monitor` command provides real-time monitoring of your Neo4j database status, replacing ad-hoc Python scripts with a proper CLI interface.

## Overview

The monitor command queries the Neo4j database to display current resource counts, relationships, resource groups, and resource types. It can run once for a snapshot or continuously monitor the database over time.

## Basic Usage

### Single Check

Get a snapshot of current database metrics:

```bash
uv run atg monitor
```

Example output (compact format, default):
```
[23:45:36] Resources=1674 Relationships=5614 ResourceGroups=182 Types=45
```

### Watch Mode

Continuously monitor the database with updates every 30 seconds (default):

```bash
uv run atg monitor --watch
```

Example output:
```
[23:45:36] Resources=1674 Relationships=5614 ResourceGroups=182 Types=45
[23:46:06] Resources=1708 Relationships=5698 ResourceGroups=185 Types=47
[23:46:36] Resources=1742 Relationships=5782 ResourceGroups=188 Types=49
...
```

Press `Ctrl+C` to stop monitoring.

### Custom Interval

Monitor with a custom interval (in seconds):

```bash
uv run atg monitor --watch --interval 60
```

## Subscription Filtering

Monitor resources for a specific Azure subscription:

```bash
uv run atg monitor --subscription-id 9b00bc5e-9abc-45de-9958-02a9d9277b16
```

Example output:
```
[23:45:36] Resources=487 Relationships=1624 ResourceGroups=42 Types=28
```

Watch mode with subscription filter:
```bash
uv run atg monitor --watch --subscription-id 9b00bc5e-9abc-45de-9958-02a9d9277b16 --interval 30
```

## Stabilization Detection

The monitor command can automatically detect when your database has stabilized (no changes in resource counts) and exit. This is useful for knowing when a graph build operation has completed.

### Basic Stabilization

Exit when metrics are stable for 3 consecutive checks (default threshold):

```bash
uv run atg monitor --watch --detect-stabilization
```

Example output:
```
[23:45:36] Resources=1674 Relationships=5614 ResourceGroups=182 Types=45
[23:46:06] Resources=1708 Relationships=5698 ResourceGroups=185 Types=47
[23:46:36] Resources=1742 Relationships=5782 ResourceGroups=188 Types=49
[23:47:06] Resources=1742 Relationships=5782 ResourceGroups=188 Types=49
[23:47:36] Resources=1742 Relationships=5782 ResourceGroups=188 Types=49
[23:48:06] Resources=1742 Relationships=5782 ResourceGroups=188 Types=49 (stable)

✅ Database has stabilized (threshold: 3 identical checks)
```

### Custom Threshold

Use a higher threshold for more confidence:

```bash
uv run atg monitor --watch --detect-stabilization --threshold 5 --interval 10
```

This will check every 10 seconds and exit after 5 consecutive identical readings.

## Output Formats

### Compact Format (Default)

Single line with all metrics:

```bash
uv run atg monitor --format compact
```

Output:
```
[23:45:36] Resources=1674 Relationships=5614 ResourceGroups=182 Types=45
```

### JSON Format

Machine-readable JSON output:

```bash
uv run atg monitor --format json
```

Output:
```json
{"timestamp": "23:45:36", "resources": 1674, "relationships": 5614, "resource_groups": 182, "resource_types": 45, "stable": false}
```

Perfect for parsing in scripts or piping to tools like `jq`:

```bash
uv run atg monitor --format json | jq '.resources'
```

### Table Format

Formatted table with headers:

```bash
uv run atg monitor --format table --watch
```

Output:
```
Timestamp    Resources    Relationships   Resource Groups  Resource Types  Status
------------------------------------------------------------------------------------------
23:45:36     1674         5614            182              45              changing
23:46:06     1708         5698            185              47              changing
23:46:36     1742         5782            188              49              changing
23:47:06     1742         5782            188              49              changing
23:47:36     1742         5782            188              49              changing
23:48:06     1742         5782            188              49              stable
```

## Common Use Cases

### Monitor During Graph Build

While running `atg build` in one terminal, monitor progress in another:

```bash
# Terminal 1
uv run atg build --tenant-id <TENANT_ID>

# Terminal 2
uv run atg monitor --watch --interval 15 --format table
```

### Wait for Build Completion

Automatically detect when build is complete:

```bash
uv run atg build --tenant-id <TENANT_ID> &
uv run atg monitor --watch --detect-stabilization --threshold 5 --interval 10
echo "Build complete!"
```

### Track Specific Subscription

Monitor a single subscription during selective updates:

```bash
uv run atg monitor --subscription-id <SUB_ID> --watch --format table
```

### Export Metrics to File

Continuous monitoring with JSON output to file:

```bash
uv run atg monitor --watch --format json --interval 60 >> metrics.jsonl
```

### Quick Status Check

Get a quick snapshot for documentation or debugging:

```bash
uv run atg monitor
```

## Command Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--subscription-id` | String | None | Filter by subscription ID |
| `--interval` | Integer | 30 | Check interval in seconds |
| `--watch` | Flag | False | Continuous monitoring mode |
| `--detect-stabilization` | Flag | False | Exit when stable |
| `--threshold` | Integer | 3 | Stability threshold (consecutive checks) |
| `--format` | Choice | compact | Output format: `json`, `table`, or `compact` |
| `--no-container` | Flag | False | Do not auto-start Neo4j container |

## Error Handling

### Neo4j Not Running

If Neo4j is not running, the command will automatically attempt to start it (unless `--no-container` is set):

```
❌ Failed to connect to Neo4j: Could not connect to bolt://localhost:7687
Action: Ensure Neo4j is running and accessible at the configured URI.
```

### Connection Issues

If there are transient connection issues in watch mode, the command will retry:

```
❌ Error during monitoring: Connection lost
Retrying in 5 seconds...
```

### Invalid Subscription ID

If the subscription ID doesn't exist, you'll get zero counts:

```
[23:45:36] Resources=0 Relationships=0 ResourceGroups=0 Types=0
```

## Integration with Other Commands

### Pre-Build Check

Check database state before building:

```bash
uv run atg monitor
uv run atg build --tenant-id <TENANT_ID>
```

### Post-Build Verification

Verify build results:

```bash
uv run atg build --tenant-id <TENANT_ID>
uv run atg monitor --format json
```

### Continuous Integration

Use in CI/CD pipelines to wait for stabilization:

```bash
# Start build in background
uv run atg build --tenant-id $TENANT_ID --no-dashboard &
BUILD_PID=$!

# Wait for stabilization
uv run atg monitor --watch --detect-stabilization --threshold 5 --interval 15

# Continue with next steps
uv run atg generate-iac --tenant-id $TENANT_ID
```

## Metrics Explained

| Metric | Description |
|--------|-------------|
| **Resources** | Total number of Azure Resource nodes in the database |
| **Relationships** | Total number of relationships (edges) between resources |
| **ResourceGroups** | Number of distinct Azure resource groups |
| **ResourceTypes** | Number of distinct Azure resource types (e.g., `Microsoft.Compute/virtualMachines`) |

### Understanding Stabilization

The database is considered "stable" when:
1. Resource count doesn't change
2. Relationship count doesn't change
3. Resource group count doesn't change
4. This state persists for `threshold` consecutive checks

Note: Resource types are tracked but not used for stabilization detection, as types can be stable while individual resources are still being added.

## Performance Considerations

- **Query Performance**: Queries are optimized with indexed lookups on `subscription_id`
- **Network Overhead**: Minimal - only aggregate counts are retrieved
- **CPU Usage**: Very low - simple counting queries
- **Memory Usage**: Negligible - only stores last N count tuples

## Troubleshooting

### Slow Queries

If monitoring is slow, ensure Neo4j indexes are created:

```cypher
CREATE INDEX resource_subscription IF NOT EXISTS FOR (r:Resource) ON (r.subscription_id);
CREATE INDEX resource_rg IF NOT EXISTS FOR (r:Resource) ON (r.resourceGroup);
CREATE INDEX resource_type IF NOT EXISTS FOR (r:Resource) ON (r.type);
```

### Inconsistent Counts

If counts seem inconsistent, verify database integrity:

```bash
# Check for orphaned relationships
uv run atg visualize

# Rebuild relationships
uv run atg build --rebuild-edges
```

### Connection Timeouts

Increase timeout if needed by setting environment variable:

```bash
export NEO4J_TIMEOUT=30
uv run atg monitor --watch
```

## Comparison with Ad-Hoc Scripts

### Before (Ad-Hoc Script)

```python
from neo4j import GraphDatabase
from datetime import datetime
import os

uri = 'bolt://localhost:7688'
password = os.getenv('NEO4J_PASSWORD')
if not password:
    raise ValueError('NEO4J_PASSWORD environment variable is required')
driver = GraphDatabase.driver(uri, auth=('neo4j', password))

with driver.session() as session:
    source = session.run(
        "MATCH (r:Resource) WHERE r.subscription_id = '9b00bc5e-9abc-45de-9958-02a9d9277b16' RETURN count(r) as count"
    ).single()['count']

driver.close()
print(f'[{datetime.now().strftime("%H:%M:%S")}] Source={source}')
```

**Problems:**
- Hard-coded credentials
- No error handling
- Manual subprocess management
- Limited output formats
- No stabilization detection
- Difficult to maintain

### After (CLI Command)

```bash
uv run atg monitor --subscription-id 9b00bc5e-9abc-45de-9958-02a9d9277b16
```

**Benefits:**
- Uses environment configuration
- Built-in error handling
- Multiple output formats
- Stabilization detection
- Continuous monitoring
- Well-documented
- Maintainable

## Future Enhancements

Potential future additions:
- Resource breakdown by type
- Top N resource groups
- Change rate calculations
- Alerting on thresholds
- Prometheus metrics export
- Historical tracking

## See Also

- [CLI Documentation](../README.md)
- [Graph Visualization](VISUALIZATION.md)
- [Build Command](BUILD_COMMAND.md)

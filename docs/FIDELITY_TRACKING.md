# Fidelity Tracking

## Overview

The `atg fidelity` command calculates and tracks resource replication fidelity between Azure subscriptions. This is particularly useful for measuring how accurately resources have been replicated from a source subscription to a target subscription.

## Features

- **Resource Count Comparison**: Compares total resources between source and target subscriptions
- **Resource Type Analysis**: Calculates fidelity by resource type (e.g., VMs, VNets, Storage Accounts)
- **Relationship Tracking**: Compares relationship/edge counts between subscriptions
- **Time-Series Tracking**: Append fidelity metrics to JSONL file for historical analysis
- **JSON Export**: Export detailed metrics to JSON format
- **OBJECTIVE.md Integration**: Check if fidelity meets criteria defined in OBJECTIVE.md

## Command Usage

### Basic Usage

Calculate fidelity between two subscriptions:

```bash
uv run atg fidelity \
  --source-subscription 9b00bc5e-9abc-45de-9958-02a9d9277b16 \
  --target-subscription c190c55a-9ab2-4b1e-92c4-cc8b1a032285
```

### Track Fidelity Over Time

Append metrics to `demos/fidelity_history.jsonl` for time-series analysis:

```bash
uv run atg fidelity \
  --source-subscription 9b00bc5e-9abc-45de-9958-02a9d9277b16 \
  --target-subscription c190c55a-9ab2-4b1e-92c4-cc8b1a032285 \
  --track
```

### Export to JSON

Export metrics to a JSON file:

```bash
uv run atg fidelity \
  --source-subscription 9b00bc5e-9abc-45de-9958-02a9d9277b16 \
  --target-subscription c190c55a-9ab2-4b1e-92c4-cc8b1a032285 \
  --output fidelity_report_2025-10-17.json
```

### Check Against Objective

Verify if fidelity meets the target specified in OBJECTIVE.md:

```bash
uv run atg fidelity \
  --source-subscription 9b00bc5e-9abc-45de-9958-02a9d9277b16 \
  --target-subscription c190c55a-9ab2-4b1e-92c4-cc8b1a032285 \
  --check-objective demos/OBJECTIVE.md
```

### Combined Options

Use multiple options together:

```bash
uv run atg fidelity \
  --source-subscription 9b00bc5e-9abc-45de-9958-02a9d9277b16 \
  --target-subscription c190c55a-9ab2-4b1e-92c4-cc8b1a032285 \
  --track \
  --output current_fidelity.json \
  --check-objective demos/OBJECTIVE.md
```

## Output Format

### Console Output

```
============================================================
Fidelity Report
============================================================

Timestamp: 2025-10-17T01:30:00Z

📋 Source Subscription:
  Subscription ID: 9b00bc5e-9abc-45de-9958-02a9d9277b16
  Resources: 1674
  Relationships: 5614
  Resource Groups: 182
  Resource Types: 94

🎯 Target Subscription:
  Subscription ID: c190c55a-9ab2-4b1e-92c4-cc8b1a032285
  Resources: 516
  Relationships: 1823
  Resource Groups: 58
  Resource Types: 42

📈 Fidelity Metrics:
  Overall Fidelity: 30.8%
  Missing Resources: 1158
  Target Fidelity: 95.0%
  ❌ Objective NOT MET

🔍 Fidelity by Resource Type (top 10):
  Microsoft.Network/virtualNetworks: 92.1%
  Microsoft.Compute/virtualMachines: 85.2%
  Microsoft.Storage/storageAccounts: 67.3%
  Microsoft.KeyVault/vaults: 45.5%
  ...
============================================================
```

### JSON Output

```json
{
  "timestamp": "2025-10-17T01:30:00Z",
  "source": {
    "subscription_id": "9b00bc5e-9abc-45de-9958-02a9d9277b16",
    "resources": 1674,
    "relationships": 5614,
    "resource_groups": 182,
    "resource_types": 94
  },
  "target": {
    "subscription_id": "c190c55a-9ab2-4b1e-92c4-cc8b1a032285",
    "resources": 516,
    "relationships": 1823,
    "resource_groups": 58,
    "resource_types": 42
  },
  "fidelity": {
    "overall": 30.8,
    "by_type": {
      "Microsoft.Compute/virtualMachines": 85.2,
      "Microsoft.Network/virtualNetworks": 92.1,
      "Microsoft.Storage/storageAccounts": 67.3,
      "Microsoft.KeyVault/vaults": 45.5
    },
    "missing_resources": 1158,
    "objective_met": false,
    "target_fidelity": 95.0
  }
}
```

## Fidelity Calculation

### Overall Fidelity

Overall fidelity is calculated as:

```
Overall Fidelity = (Target Resources / Source Resources) × 100
```

For example, if source has 1000 resources and target has 800 resources:
```
Overall Fidelity = (800 / 1000) × 100 = 80.0%
```

### Fidelity by Resource Type

Fidelity is calculated for each resource type individually:

```
Type Fidelity = (Target Count / Source Count) × 100
```

For example, if source has 100 VMs and target has 85 VMs:
```
VM Fidelity = (85 / 100) × 100 = 85.0%
```

## Time-Series Tracking

When using the `--track` flag, metrics are appended to `demos/fidelity_history.jsonl` in JSONL format (one JSON object per line). This allows you to:

1. Track fidelity improvements over multiple iterations
2. Analyze trends and convergence toward target fidelity
3. Generate visualizations of fidelity over time

Example JSONL format:

```jsonl
{"timestamp": "2025-10-17T00:00:00Z", "source": {...}, "target": {...}, "fidelity": {"overall": 25.5, ...}}
{"timestamp": "2025-10-17T01:00:00Z", "source": {...}, "target": {...}, "fidelity": {"overall": 30.8, ...}}
{"timestamp": "2025-10-17T02:00:00Z", "source": {...}, "target": {...}, "fidelity": {"overall": 42.3, ...}}
```

## OBJECTIVE.md Integration

The `--check-objective` flag reads an OBJECTIVE.md file to determine the target fidelity percentage. The parser looks for patterns like:

- "95% fidelity"
- "fidelity: 95%"
- "target: 95%"

Example OBJECTIVE.md:

```markdown
# Objective

Replicate the source subscription to the target subscription with at least 95% fidelity.

## Success Criteria

- Overall fidelity >= 95%
- All critical resource types replicated
- Relationships preserved
```

The command will report whether the objective is met based on the calculated overall fidelity.

## Integration with Iteration Workflow

The fidelity command integrates with the iteration workflow described in `ATG_ITERATION_WORKFLOW_IMPROVEMENTS.md`:

1. **Generate IaC**: Use `atg generate-iac` to create Terraform templates from source subscription
2. **Deploy**: Deploy the generated IaC to target subscription using `atg deploy` (or `terraform apply`)
3. **Scan Target**: Run `atg scan` on the target subscription to populate Neo4j
4. **Calculate Fidelity**: Use `atg fidelity` to measure replication accuracy
5. **Iterate**: Repeat steps 1-4 until target fidelity is achieved

Example workflow:

```bash
# Step 1-2: Generate and deploy (not shown)

# Step 3: Scan target subscription
uv run atg scan --filter-by-subscriptions c190c55a-9ab2-4b1e-92c4-cc8b1a032285

# Step 4: Calculate fidelity
uv run atg fidelity \
  --source-subscription 9b00bc5e-9abc-45de-9958-02a9d9277b16 \
  --target-subscription c190c55a-9ab2-4b1e-92c4-cc8b1a032285 \
  --track \
  --check-objective demos/OBJECTIVE.md

# Step 5: If objective not met, iterate
```

## Troubleshooting

### Subscription Not Found

If you see "Source subscription not found" or "Target subscription not found", ensure:

1. Neo4j is running and accessible
2. Both subscriptions have been scanned and data exists in Neo4j
3. Subscription IDs are correct (UUIDs, not names)

### Empty Fidelity by Type

If `fidelity_by_type` is empty, the source subscription may have no resources of any type. Verify the source subscription data in Neo4j.

### No Neo4j Connection

Ensure `NEO4J_URI` or `NEO4J_PORT` and `NEO4J_PASSWORD` environment variables are set correctly.

## API Reference

### FidelityCalculator Class

```python
from src.fidelity_calculator import FidelityCalculator

# Initialize
calculator = FidelityCalculator(
    neo4j_uri="bolt://localhost:7687",
    neo4j_user="neo4j",
    neo4j_password="password"  # pragma: allowlist secret  # pragma: allowlist secret
)

# Calculate fidelity
metrics = calculator.calculate_fidelity(
    source_subscription_id="source-id",
    target_subscription_id="target-id",
    target_fidelity=95.0
)

# Export to JSON
calculator.export_to_json(metrics, "fidelity.json")

# Track to history
calculator.track_fidelity(metrics, "demos/fidelity_history.jsonl")

# Check objective
objective_met, target = calculator.check_objective("OBJECTIVE.md", metrics.overall_fidelity)

# Clean up
calculator.close()
```

### FidelityMetrics Class

```python
from src.fidelity_calculator import FidelityMetrics

# Metrics are returned by calculate_fidelity()
metrics = calculator.calculate_fidelity(...)

# Access properties
print(f"Overall Fidelity: {metrics.overall_fidelity:.1f}%")
print(f"Missing Resources: {metrics.missing_resources}")
print(f"Objective Met: {metrics.objective_met}")

# Convert to dictionary
metrics_dict = metrics.to_dict()
```

## See Also

- `ATG_ITERATION_WORKFLOW_IMPROVEMENTS.md` - Complete iteration workflow design
- `MONITOR_COMMAND.md` - Related monitoring capabilities
- `DEFAULT_WORKFLOW.md` - Code contribution process

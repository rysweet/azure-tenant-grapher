# Scale Operations Guide

Complete guide for scaling Azure Tenant Grapher graphs up and down for testing, development, and performance evaluation.

## Overview

Scale operations enable you to:
- **Scale Up**: Add synthetic resources to test large deployments
- **Scale Down**: Sample/reduce graphs for faster testing and development

All scale operations work on the **abstracted graph layer only**, never touching the Original layer.

## Quick Start

```bash
# Scale up to 2x current size
uv run atg scale-up scenario --scenario hub-spoke --spoke-count 5 --scale-factor 2.0

# Scale down to 10% using Forest Fire algorithm
uv run atg scale-down algorithm --algorithm forest-fire --target-size 0.1

# Scale down keeping only VMs
uv run atg scale-down pattern --pattern compute
```

## Scale-Up Operations

### Scenario-Based Generation

Creates synthetic resources following common Azure deployment patterns.

**Available Scenarios:**
- `hub-spoke`: Hub-and-spoke network topology
- `multi-region`: Multi-region deployments
- `dev-test-prod`: Three-tier environments

**Examples:**
```bash
# Hub-spoke with 10 spokes
uv run atg scale-up scenario --scenario hub-spoke --spoke-count 10 --scale-factor 1.5

# Multi-region across 3 regions
uv run atg scale-up scenario --scenario multi-region --regions eastus,westus,northeurope

# Dev/Test/Prod with 2x scaling
uv run atg scale-up scenario --scenario dev-test-prod --scale-factor 2.0
```

### Template-Based Generation

Replicates existing resources to scale proportionally.

**How It Works:**
1. Analyzes current resource types and counts
2. Multiplies by scale_factor
3. Preserves resource type ratios
4. Copies properties (including LLM descriptions)

**Examples:**
```bash
# Double current resources (5k → 10k)
uv run atg scale-up template --scale-factor 2.0

# Python API for specific count
python -c "
from src.services.scale_up_service import ScaleUpService
# Calculate: target_total / current_count = scale_factor
# For 5,386 → 9,000: scale_factor = 1.67
result = await service.scale_up_template('tenant-id', scale_factor=1.67)
"
```

**Key Features:**
- ✅ No LLM API calls (copies descriptions from templates)
- ✅ Preserves resource type distribution
- ✅ Fast (processes 1,000s of nodes in seconds)
- ✅ Validates synthetic markers

## Scale-Down Operations

### Algorithm-Based Sampling

Uses graph sampling algorithms to preserve topology.

**Available Algorithms:**
- `forest-fire`: Simulates fire spreading (preserves clusters)
- `random-walk`: Random walks (preserves connectivity)
- `mhrw`: Metropolis-Hastings Random Walk (unbiased)

**Examples:**
```bash
# Sample 10% with Forest Fire
uv run atg scale-down algorithm --algorithm forest-fire --target-size 0.1

# Sample exact count with Random Walk
uv run atg scale-down algorithm --algorithm random-walk --target-count 1000

# MHRW with custom parameters
uv run atg scale-down algorithm --algorithm mhrw --target-size 0.2 --walk-length 2000
```

**Algorithm Details:**

**Forest Fire:**
- Best for: Preserving community structure
- Speed: 0.10s for 915 nodes from 9k graph
- Parameters: `--burning-prob` (default: 0.4)
- Handles sparse graphs: ✅ (custom implementation)

**Random Walk:**
- Best for: Simple, fast sampling
- Speed: 0.34s for 915 nodes from 9k graph
- Parameters: None
- Handles sparse graphs: ✅ (custom implementation)

**MHRW:**
- Best for: Unbiased sampling
- Speed: Slower but more rigorous
- Parameters: `--walk-length`, `--alpha`
- Handles sparse graphs: ⚠️ (use with caution)

### Pattern-Based Filtering

Filters by resource type or tags.

**Available Patterns:**
- `security`: KeyVaults, NSGs, Managed Identities
- `network`: VNets, Subnets, NICs
- `compute`: VMs, VMSS, Container Instances
- `storage`: Storage Accounts, Disks
- `resource-type`: Custom type specification

**Examples:**
```bash
# Keep only VMs
uv run atg scale-down pattern --pattern compute

# Keep only storage with 30% sampling
uv run atg scale-down pattern --pattern storage --target-size 0.3

# Custom resource type
uv run atg scale-down pattern --pattern resource-type \
    --resource-types "Microsoft.Network/virtualNetworks"
```

## Output Modes

All scale-down operations support multiple output modes:

- `delete`: Remove non-sampled nodes from graph (default)
- `export`: Export sampled subgraph to file
- `new-tenant`: Create new tenant with sampled data

```bash
# Delete non-sampled nodes
uv run atg scale-down algorithm --algorithm forest-fire --target-size 0.1 --output-mode delete

# Export to YAML
uv run atg scale-down algorithm --algorithm forest-fire --target-size 0.1 \
    --output-mode export --output-file sampled_graph.yaml

# Create new tenant
uv run atg scale-down algorithm --algorithm forest-fire --target-size 0.1 \
    --output-mode new-tenant --new-tenant-id "sampled-tenant"
```

## Performance Tuning

### Scan Performance

Optimize full tenant rescans for maximum speed:

```bash
# Use 20+ concurrent workers and LLM threads
uv run atg scan --tenant-id <ID> --max-build-threads 100 --max-llm-threads 20

# Default is now 20 workers (changed from 5)
# This provides 4x speedup for large tenants
```

### Scale-Up Performance

Large scale-ups (>10k resources) use automatic optimizations:
- Adaptive batching (500-5000 per batch)
- Parallel batch processing for >10k resources
- Controlled concurrency to avoid Neo4j overload

```bash
# Large scale-up handles performance automatically
uv run atg scale-up scenario --scenario hub-spoke --scale-factor 10.0
```

## Validation & Quality Metrics

All scale operations include automatic validation:

**Scale-Up Validations:**
- ✅ No Original layer contamination
- ✅ No SCAN_SOURCE_NODE relationships created
- ✅ All synthetic resources have required markers
- ✅ Resource type preservation

**Scale-Down Quality Metrics:**
- Degree distribution similarity
- Clustering coefficient preservation
- Connected components analysis
- Resource type preservation percentage
- Computation time

Example output:
```
Quality Metrics:
  Nodes: 915/9150 (10.0%)
  Edges: 83/368
  Degree Distribution Similarity: 7167.5738
  Clustering Coefficient Diff: 0.0000
  Connected Components: 855/8921
  Resource Type Preservation: 69.5%
  Computation Time: 0.34s
```

## Cleanup & Rollback

Remove all synthetic data from a scale operation:

```bash
# List scale operations
uv run atg scale-stats

# Rollback specific operation
uv run atg scale-cleanup --operation-id scale-20251114T160624-c20434b6

# Remove ALL synthetic data
uv run atg scale-cleanup --all
```

## Troubleshooting

### Scale-Down Fails with "Empty Sequence"

**Cause:** Very sparse graph (few connections)
**Solution:** Use pattern-based instead of algorithm-based, or use our improved algorithms (v1.1+)

```bash
# Instead of failing forest-fire, use pattern
uv run atg scale-down pattern --pattern compute --target-size 0.1
```

### Scale-Up Creates Disconnected Nodes

**Expected:** Synthetic nodes copy relationship structure from templates
**If Issue:** Check relationship duplication with `atg scale-validate`

### Slow Scans (>2 hours)

**Solution:** Increase concurrency (default changed to 20 workers):
```bash
# Already using 20 workers by default (4x faster than before)
# For even more speed, rebuild with higher Neo4j memory
```

## Architecture Notes

### Dual-Graph Design

- **Original Layer** (`:Resource:Original`): Never modified by scale operations
- **Abstracted Layer** (`:Resource`): Where all scale operations occur
- **Relationship Duplication:** 96% parity maintained (improved from 54%)

### Synthetic Resource Markers

All synthetic resources have:
```python
{
    "synthetic": True,
    "scale_operation_id": "scale-20251114T160624-c20434b6",
    "generation_strategy": "template"|"scenario"|"random",
    "generation_timestamp": "2025-11-14T16:06:24Z",
    "template_source_id": "/subscriptions/.../originalVM" # for template mode
}
```

### LLM Description Handling

**Scale-up does NOT call LLM APIs** for synthetic resources.

Instead:
- Copies `description` property from template resource
- Fast (no API calls)
- Consistent (all copies identical)
- Cost-effective (no per-node LLM charges)

If template has no description, synthetic copies also have no description.

## Performance Benchmarks

Tested on Azure tenant with 5,386 real resources:

| Operation | Input | Output | Time | Notes |
|-----------|-------|--------|------|-------|
| Scale-up template | 5.4k nodes | 9.2k nodes | 15s | +3.6k synthetic |
| Scale-up hub-spoke | 5.4k nodes | 5.5k nodes | 3s | +111 resources |
| Forest Fire 10% | 9.2k nodes | 915 sampled | 0.10s | Custom algorithm |
| Random Walk 10% | 9.2k nodes | 915 sampled | 0.34s | Custom algorithm |
| Pattern (compute) | 9.2k nodes | 145 matched | 0.8s | VMs only |
| Full rescan (20 workers) | 5.4k resources | Complete | 2.0h | Was 8h with 5 workers |

## Common Workflows

### Development: Quick Test Graph

```bash
# Scale down to 10% for fast iteration
uv run atg scale-down algorithm --algorithm forest-fire --target-size 0.1
```

### Testing: Large Deployment Simulation

```bash
# Scale up to 10x for load testing
uv run atg scale-up scenario --scenario hub-spoke --spoke-count 20 --scale-factor 5.0
```

### CI/CD: Reset to Baseline

```bash
# Remove all synthetic data before tests
uv run atg scale-cleanup --all
```

## API Usage

For programmatic control:

```python
from src.services.scale_up_service import ScaleUpService
from src.services.scale_down_service import ScaleDownService
from src.config_manager import create_neo4j_config_from_env
from src.utils.session_manager import Neo4jSessionManager

# Setup
config = create_neo4j_config_from_env()
session_manager = Neo4jSessionManager(config.neo4j)
session_manager.connect()

# Scale up
scale_up_service = ScaleUpService(session_manager)
result = await scale_up_service.scale_up_template(
    tenant_id="your-tenant-id",
    scale_factor=2.0
)

# Scale down
scale_down_service = ScaleDownService(session_manager)
sampled_ids = await scale_down_service.sample_forest_fire(
    tenant_id="your-tenant-id",
    target_size=0.1
)
```

## See Also

- [E2E_DEMO_RESULTS.md](SCALE_OPERATIONS_E2E_DEMONSTRATION.md) - Complete testing results
- [NEO4J_SCHEMA_REFERENCE.md](NEO4J_SCHEMA_REFERENCE.md) - Graph schema details
- [Issue #427](https://github.com/rysweet/azure-tenant-grapher/issues/427) - Original feature request
- [PR #444](https://github.com/rysweet/azure-tenant-grapher/pull/444) - Dual-graph relationship fixes

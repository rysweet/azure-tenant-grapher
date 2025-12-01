# Graph Abstraction Layer

Create smaller, representative subsets of large Azure tenant graphs for training simulations.

## Quick Start

```bash
# 1. Scan your tenant (if not already done)
atg scan --tenant-id <TENANT_ID>

# 2. Create 100-node abstraction
atg abstract-graph --tenant-id <TENANT_ID> --sample-size 100

# 3. Visualize the abstraction
atg visualize
```

## Overview

The Graph Abstraction Layer creates smaller representative subsets of large Azure tenant graphs while preserving:
- **Resource type distribution** (±15% tolerance)
- **Graph topology** (relationship structure)
- **Queryability** (stored in Neo4j with `:SAMPLE_OF` links)

**Use Cases:**
- **Training simulations**: Create manageable graphs from production tenants
- **Development/testing**: Work with smaller graphs locally
- **Demonstrations**: Show realistic Azure architectures without exposing full production
- **Cost estimation**: Test deployment costs with representative samples

## When to Use Graph Abstraction

### ✅ Good Use Cases

| Scenario | Source Size | Target Size | Benefit |
|----------|-------------|-------------|---------|
| Training lab | 10,000+ resources | 100-500 | Manageable complexity |
| Demo environment | 5,000+ resources | 50-200 | Fast deployment |
| Development testing | 1,000+ resources | 100-300 | Rapid iteration |

### ❌ When NOT to Use

- **Production deployments** - Use full tenant scan
- **Compliance audits** - Require complete resource inventory
- **Cost optimization** - Need all resources for accurate analysis
- **Security assessments** - Cannot guarantee all attack paths preserved (MVP limitation)

## Command Reference

### `abstract-graph`

Create abstracted graph subset from scanned tenant.

```bash
atg abstract-graph [OPTIONS]
```

**Required Options:**
- `--tenant-id TEXT` - Source tenant ID to abstract from
- `--sample-size INTEGER` - Target number of nodes (10-10000)

**Optional:**
- `--seed INTEGER` - Random seed for reproducibility
- `--clear` - Clear existing `:SAMPLE_OF` relationships first

### Examples

**Basic 100-node abstraction:**
```bash
atg abstract-graph --tenant-id abc-123-def --sample-size 100
```

**Reproducible abstraction (same seed = same sample):**
```bash
atg abstract-graph --tenant-id abc-123-def --sample-size 500 --seed 42
```

**Replace existing abstraction:**
```bash
atg abstract-graph --tenant-id abc-123-def --sample-size 200 --clear
```

**Tiny graph for quick testing:**
```bash
atg abstract-graph --tenant-id abc-123-def --sample-size 20
```

## How It Works

### Algorithm: Stratified Sampling

The abstraction uses **stratified sampling by resource type** to preserve distribution:

1. **Query type distribution**:
   ```
   Source: 500 VMs (50%), 300 Storage (30%), 200 VNets (20%)
   ```

2. **Calculate per-type quotas** (proportional):
   ```
   Target: 100 nodes
   Quotas: 50 VMs, 30 Storage, 20 VNets
   ```

3. **Random sample** within each type:
   - Ensures at least 1 of each type (minimum quota)
   - Distributes rounding remainders to largest types

4. **Create `:SAMPLE_OF` relationships**:
   ```cypher
   (abstracted_vm:Resource)-[:SAMPLE_OF]->(original_vm:Resource)
   ```

### Validation

The algorithm validates that sampled distribution matches source within tolerance:
- **Size**: ±10% of target
- **Type distribution**: ±15% per resource type

**Example:**
```
Source: 50% VMs, 30% Storage, 20% VNets
Sample: 48% VMs, 32% Storage, 20% VNets
✓ PASS (all deltas < 15%)
```

## Querying Abstracted Graphs

### Find abstracted resources

```cypher
MATCH (sample:Resource)-[:SAMPLE_OF]->(original:Resource)
WHERE original.tenant_id = 'abc-123-def'
RETURN sample, original
LIMIT 100
```

### Get abstraction statistics

```cypher
MATCH (sample:Resource)-[:SAMPLE_OF]->(original:Resource)
WHERE original.tenant_id = 'abc-123-def'
RETURN
  sample.type AS resource_type,
  count(sample) AS sample_count
ORDER BY sample_count DESC
```

### Verify distribution preserved

```cypher
// Source distribution
MATCH (n:Resource {tenant_id: 'abc-123-def'})
RETURN n.type AS type, count(n) AS source_count,
       count(n) * 100.0 / sum(count(n)) AS source_pct
ORDER BY source_count DESC

// Abstracted distribution
MATCH (sample)-[:SAMPLE_OF]->(source:Resource {tenant_id: 'abc-123-def'})
RETURN sample.type AS type, count(sample) AS sample_count,
       count(sample) * 100.0 / sum(count(sample)) AS sample_pct
ORDER BY sample_count DESC
```

## Integration with Other Commands

### Visualize Abstraction

The abstracted graph can be visualized like any tenant graph:

```bash
atg abstract-graph --tenant-id abc-123 --sample-size 100
atg visualize
```

The visualization will show `:SAMPLE_OF` relationships linking abstracted to original resources.

### Generate IaC from Abstraction

Generate Infrastructure-as-Code from the smaller abstracted graph:

```bash
# Create abstraction
atg abstract-graph --tenant-id <SOURCE> --sample-size 200

# Generate IaC from subset
# (Future: --from-abstraction flag - not in MVP)
atg generate-iac --tenant-id <SOURCE>
```

**Note**: MVP stores abstraction as `:SAMPLE_OF` relationships. Future PRs will add `--from-abstraction` flag for IaC generation from sampled subset only.

### Threat Modeling

Run threat modeling on abstracted graph for faster iteration:

```bash
atg abstract-graph --tenant-id abc-123 --sample-size 150
atg threat-model
```

**Limitation**: Attack paths may not be fully preserved in MVP. Future PRs will add security-aware sampling.

## Troubleshooting

### "No resources found for tenant"

**Cause**: Tenant hasn't been scanned yet.

**Solution**:
```bash
# Scan tenant first
atg scan --tenant-id <TENANT_ID>

# Then abstract
atg abstract-graph --tenant-id <TENANT_ID> --sample-size 100
```

### "NEO4J_URI and NEO4J_PASSWORD must be set"

**Cause**: Environment variables not configured.

**Solution**:
```bash
# Create .env file
echo "NEO4J_URI=bolt://localhost:7687" >> .env
echo "NEO4J_PASSWORD=your-password" >> .env

# Or export directly
export NEO4J_URI=bolt://localhost:7687
export NEO4J_PASSWORD=your-password
```

### Sample size doesn't match target exactly

**Expected behavior**: Samples within ±10% of target due to rounding.

**Example:**
```
Requested: 100 nodes
Actual: 102 nodes  (2% over, within tolerance)
```

### Type distribution seems off

**Check tolerance**: ±15% per type is expected due to small sample sizes.

**Verify:**
```cypher
// Compare percentages (should be within 15% points)
MATCH (source:Resource {tenant_id: 'abc'})
WITH source.type AS type, count(*) * 100.0 / 1000 AS source_pct
MATCH (sample)-[:SAMPLE_OF]->(orig:Resource {tenant_id: 'abc'})
WITH type, source_pct, sample.type AS sample_type, count(*) * 100.0 / 100 AS sample_pct
WHERE sample_type = type
RETURN type, source_pct, sample_pct, abs(source_pct - sample_pct) AS delta
ORDER BY delta DESC
```

## Limitations (MVP)

| Limitation | Impact | Future PR |
|------------|--------|-----------|
| Single sampling method | Only stratified by type | #2: Add DPP, k-medoids |
| No security pattern preservation | Attack paths may be lost | #3: Security-aware sampling |
| No validation report | Manual Cypher queries needed | #2: Automated reports |
| Minimum 10 resources | Very small graphs unsupported | N/A (by design) |
| No IaC generation from subset | Must query manually | #4: --from-abstraction flag |

## What Is NOT Preserved

The MVP abstraction does **not guarantee** preservation of:
- Exact graph topology (some edges may be lost)
- Attack paths or security patterns
- Cost characteristics
- Performance characteristics
- Specific resource relationships

**Reason**: MVP focuses on type distribution only. Advanced features (security, topology, patterns) planned for future PRs.

## Next Steps

1. **Validate your abstraction** - Run Cypher queries above to check distribution
2. **Iterate sample size** - Try different sizes to find optimal balance
3. **Test with workflows** - Use abstracted graphs in your existing processes
4. **Provide feedback** - Report issues or feature requests on GitHub

## Related Documentation

- [Neo4j Schema Reference](../NEO4J_SCHEMA_REFERENCE.md) - Understand node labels and relationships
- [Cross-Tenant Features](../cross-tenant/FEATURES.md) - Cross-tenant deployment capabilities
- [Dual-Graph Architecture](../DUAL_GRAPH_ARCHITECTURE.md) - How abstracted vs original nodes work

## Technical Details

**Storage**: `:SAMPLE_OF` relationships in Neo4j
**Algorithm**: Proportional stratified sampling
**Performance**: ~1-5 seconds for 10,000-node graph → 100-node subset
**Dependencies**: Neo4j database (no GDS plugin required)

See [GitHub Issue #504](https://github.com/rysweet/azure-tenant-grapher/issues/504) for technical specification.

# Architecture-Based Tenant Replication with Fidelity Validation

This document describes the complete workflow for architecture-based tenant replication with integrated fidelity validation using source-to-target resource mappings.

## Overview

The architecture-based replication system provides an end-to-end solution for:

1. **Pattern Analysis**: Discovering architectural patterns in source tenant
2. **Intelligent Selection**: Choosing representative resource groups using distribution analysis
3. **Resource Mapping**: Tracking source-to-target resource relationships
4. **Deployment**: Creating resources in target tenant (framework ready)
5. **Fidelity Validation**: Property-level comparison using explicit mappings

## Quick Start

### Prerequisites

1. **Neo4j Running**: Ensure Neo4j container is running with source tenant data
   ```bash
   docker ps --filter "name=neo4j"
   ```

2. **Azure CLI Logged In**: Authenticate to target tenant
   ```bash
   az login
   az account set --subscription <TARGET_SUBSCRIPTION_ID>
   ```

3. **Neo4j Credentials**: Know your Neo4j password
   ```bash
   export NEO4J_PASSWORD="your_password"
   ```

### Running the Workflow

#### Option 1: Interactive Helper Script (Recommended)

```bash
./scripts/run_architecture_replication.sh
```

This script will:
- Verify Neo4j connection
- List available subscriptions
- Prompt for source/target subscriptions
- Run the complete workflow
- Generate comprehensive reports

#### Option 2: Direct Python Execution

```bash
python3 scripts/architecture_replication_with_fidelity.py \
    --source-subscription 9b00bc5e-9abc-45de-9958-02a9d9277b16 \
    --target-subscription ff7d97e0-db31-4969-9a0e-a1e6d19ccc78 \
    --target-instance-count 10 \
    --output-dir ./output/replication_run_001 \
    --neo4j-password <YOUR_PASSWORD>
```

## Workflow Stages

### Stage 1: Source Tenant Analysis

The analyzer connects to Neo4j and examines the source subscription to:

- Discover architectural patterns (Web App, VM Workload, etc.)
- Identify resource type relationships
- Build weighted pattern graph
- Calculate pattern distribution scores

**Output**: `01_analysis_summary.json`

Key metrics:
- Total relationships discovered
- Unique resource types
- Detected patterns with completeness scores

### Stage 2: Replication Plan Generation

The replicator generates an intelligent selection plan:

- Uses distribution scores to maintain proportional representation
- Selects configuration-coherent resource groups
- Applies spectral guidance for structural similarity
- Includes orphaned resources (e.g., KeyVaults)

**Output**: `02_replication_plan.json`

Contains:
- Selected instances per pattern
- Resource counts by pattern
- Spectral distance history
- Distribution metadata

### Stage 3: Source-Target Mapping Creation

Creates explicit mappings between source and target resources:

```json
{
  "source_id": "/subscriptions/SOURCE/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",
  "source_name": "vm1",
  "source_type": "Microsoft.Compute/virtualMachines",
  "target_id": "/subscriptions/TARGET/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1-replica",
  "target_name": "vm1-replica",
  "target_type": "Microsoft.Compute/virtualMachines",
  "pattern": "Virtual Machine Workload",
  "timestamp": "2025-01-15T10:30:00Z"
}
```

**Output**: `03_resource_mappings.json`

These mappings are critical for accurate fidelity validation.

### Stage 4: Resource Deployment

*Note: Current implementation is a placeholder. Production deployment would:*

1. Generate IaC (Terraform/Bicep) from replication plan
2. Deploy IaC to target subscription
3. Track deployment status and errors
4. Update mappings with actual deployed resource IDs

**Output**: `04_deployment_summary.json`

### Stage 5: Fidelity Validation with Mappings

Uses `ResourceFidelityCalculator` to perform property-level comparison:

- **Exact Matching**: Uses explicit source-target mappings
- **Fuzzy Matching**: Handles name variations (e.g., "stor001" → "stor001hpcp4rein6")
- **Property Comparison**: Recursive traversal of resource properties
- **Security Redaction**: FULL/MINIMAL/NONE redaction levels

**Output**: `05_fidelity_validation.json`

Metrics:
- Total resources compared
- Exact matches (100% identical)
- Drifted resources (some property mismatches)
- Missing resources (source or target)
- Match percentage
- Top mismatched properties

### Stage 6: Comprehensive Report

Generates human-readable Markdown report combining all stages.

**Output**: `00_COMPREHENSIVE_REPORT.md`

Includes:
- Executive summary
- Stage-by-stage details
- Sample resource mappings
- Fidelity validation results
- Error/warning log

## Using the Results

### Reviewing Fidelity Results

```bash
# View comprehensive report
cat output/replication_run_001/00_COMPREHENSIVE_REPORT.md

# Analyze fidelity validation
cat output/replication_run_001/05_fidelity_validation.json | jq '.summary'

# Check specific resource mappings
cat output/replication_run_001/03_resource_mappings.json | jq '.[] | select(.pattern == "Virtual Machine Workload")'
```

### Improving Fidelity

If fidelity is lower than expected:

1. **Check Drifted Resources**: Review `05_fidelity_validation.json` for drifted resources
   ```bash
   cat output/replication_run_001/05_fidelity_validation.json | jq '.resources[] | select(.status == "drifted")'
   ```

2. **Analyze Top Mismatches**: Identify common property mismatches
   ```bash
   cat output/replication_run_001/05_fidelity_validation.json | jq '.top_mismatched_properties'
   ```

3. **Verify Mappings**: Ensure source-target mappings are correct
   ```bash
   cat output/replication_run_001/03_resource_mappings.json | jq '.[] | {source_name, target_name, pattern}'
   ```

4. **Adjust Replication Plan**: Increase `target_instance_count` or adjust coherence threshold

### Iterating for Better Results

```bash
# Run with more instances
./scripts/run_architecture_replication.sh \
    --source-subscription SOURCE_ID \
    --target-subscription TARGET_ID \
    --target-instance-count 20

# Or with looser coherence (more variety)
python3 scripts/architecture_replication_with_fidelity.py \
    --source-subscription SOURCE_ID \
    --target-subscription TARGET_ID \
    --target-instance-count 15 \
    --coherence-threshold 0.5
```

## Architecture

### Key Components

#### ArchitecturalPatternAnalyzer
- **Location**: `src/architectural_pattern_analyzer.py`
- **Purpose**: Discovers patterns in source tenant
- **Methods**:
  - `connect()`: Establish Neo4j connection
  - `fetch_all_relationships()`: Query resource relationships
  - `detect_patterns()`: Identify architectural patterns
  - `compute_architecture_distribution()`: Calculate pattern scores

#### ArchitecturePatternReplicator
- **Location**: `src/architecture_based_replicator.py`
- **Purpose**: Generates intelligent replication plans
- **Methods**:
  - `analyze_source_tenant()`: Analyze patterns
  - `generate_replication_plan()`: Select instances
  - `analyze_orphaned_nodes()`: Find missing resource types

#### ResourceFidelityCalculator
- **Location**: `src/validation/resource_fidelity_calculator.py`
- **Purpose**: Property-level fidelity validation
- **Methods**:
  - `calculate_fidelity()`: Compare resources
  - `_compare_properties()`: Recursive property comparison
  - `_redact_if_sensitive()`: Security redaction

#### ArchitectureReplicationOrchestrator
- **Location**: `scripts/architecture_replication_with_fidelity.py`
- **Purpose**: End-to-end workflow orchestration
- **Methods**:
  - `run_complete_workflow()`: Execute all stages
  - `_create_resource_mappings()`: Generate mappings
  - `_validate_fidelity_with_mappings()`: Fidelity check

### Data Flow

```
Source Tenant (Neo4j)
    ↓
[1] Pattern Analysis
    ↓
Pattern Graph + Distribution Scores
    ↓
[2] Intelligent Selection
    ↓
Replication Plan (instances)
    ↓
[3] Mapping Generation
    ↓
Source-Target Mappings
    ↓
[4] Deployment (TODO: IaC generation)
    ↓
Target Tenant Resources
    ↓
[5] Fidelity Validation
    ↓
Property-Level Comparison
    ↓
[6] Comprehensive Report
```

## Configuration Options

### Selection Parameters

- `--target-instance-count`: Number of instances to replicate (default: all)
- `--use-configuration-coherence`: Cluster by configuration similarity (default: True)
- `--coherence-threshold`: Similarity threshold 0.0-1.0 (default: 0.7)
- `--include-orphaned-resources`: Include standalone resources (default: True)
- `--use-spectral-guidance`: Use structural similarity (default: True)

### Fidelity Parameters

- `--redaction-level`: Security redaction (FULL/MINIMAL/NONE, default: FULL)
- `--resource-type`: Filter to specific type (default: all types)

## Security Considerations

### Redaction Levels

**FULL (Default - Recommended)**:
- All sensitive properties completely redacted
- Safe for sharing reports
- Passwords, keys, secrets hidden

**MINIMAL**:
- Server information visible in connection strings
- Passwords/keys still redacted
- Use for debugging only

**NONE**:
- All sensitive data visible
- DANGEROUS - only use in secure environments
- Never share reports with NONE redaction

### Credential Handling

- Neo4j password from environment variable
- Never log or print passwords
- Use Azure CLI authentication for target tenant
- Service principals optional for automation

## Troubleshooting

### Neo4j Connection Failed

```bash
# Check container status
docker ps --filter "name=neo4j"

# Check port mappings
docker port <container_name>

# Verify credentials
echo $NEO4J_PASSWORD

# Test connection
python3 -c "from neo4j import GraphDatabase; driver = GraphDatabase.driver('bolt://localhost:7687', auth=('neo4j', '$NEO4J_PASSWORD')); driver.verify_connectivity(); print('OK')"
```

### No Subscriptions Found

```bash
# Verify source data exists in Neo4j
docker exec atg-neo4j cypher-shell -u neo4j -p $NEO4J_PASSWORD \
    "MATCH (r:Resource:Original) RETURN DISTINCT r.subscription_id LIMIT 5"

# Scan source tenant if needed
atg scan --subscription-id SOURCE_ID
```

### Low Fidelity Scores

1. Check if target deployment actually happened
2. Verify source-target mappings are accurate
3. Review top mismatched properties
4. Consider configuration drift (location, SKU, tags)
5. Check for missing dependencies

## Future Enhancements

### Stage 4: Actual Deployment

Current implementation is a placeholder. Production deployment requires:

1. **IaC Generation**:
   - Convert replication plan to Terraform/Bicep
   - Use existing IaC generators (`src/iac/`)
   - Handle resource dependencies

2. **Deployment Execution**:
   - Use existing deployers (`src/deployment/`)
   - Track deployment status
   - Handle errors and retries

3. **Mapping Updates**:
   - Update mappings with actual deployed resource IDs
   - Store mappings in Neo4j for future queries
   - Enable incremental updates

### Enhanced Fidelity Validation

1. **Explicit Mapping Support**:
   - Extend `ResourceFidelityCalculator` to accept explicit mappings
   - Improve matching accuracy
   - Reduce false positives

2. **Configuration Drift Detection**:
   - Track expected vs actual configurations
   - Identify unintended changes
   - Generate remediation recommendations

3. **Continuous Monitoring**:
   - Periodic fidelity checks
   - Alert on drift exceeding thresholds
   - Historical trend analysis

## Related Documentation

- [Architecture-Based Replication](./ARCHITECTURE_BASED_REPLICATION.md)
- [Fidelity Tracking](./FIDELITY_TRACKING.md)
- [IaC Generation](./iac/)
- [Deployment Guide](./TENANT_REPLICATION_DEPLOYMENT_GUIDE.md)

## Support

For issues or questions:
1. Check troubleshooting section above
2. Review generated log files in output directory
3. Examine error messages in `00_COMPREHENSIVE_REPORT.md`
4. Create GitHub issue with full logs

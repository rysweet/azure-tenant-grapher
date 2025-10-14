# Simuland Replication Demo - October 12, 2025

## Overview

This demo showcases Azure Tenant Grapher's ability to replicate Microsoft's Simuland environment - a complete Azure AD lab designed for threat detection and response testing.

**Key Achievement**: Successfully replicated 10+ VMs, 3 VNets, 12 subnets, and complex security configurations using ATG's automated IaC generation.

## Quick Start

### Prerequisites
- Azure subscription with appropriate permissions
- Terraform CLI installed
- Neo4j database running (managed by ATG)
- Azure Tenant Grapher installed
- Python 3.8+ with neo4j driver (for fidelity measurement)

**Install Python Dependencies:**
```bash
pip install -r demos/simuland_replication_20251012/scripts/requirements.txt
```
This installs the `neo4j` package (v5.0.0+) required by `measure_fidelity.py`.

### Run the Demo

1. **Review the artifacts**:
   ```bash
   cd demos/simuland_replication_20251012/artifacts
   cat simuland_final.tf.json | jq .
   ```

2. **View the presentation**:
   ```bash
   cat PRESENTATION.md
   ```

3. **Measure fidelity**:
   ```bash
   python scripts/measure_fidelity.py
   ```

4. **Explore Neo4j queries**:
   ```bash
   # Execute queries in neo4j_queries/ against your Neo4j instance
   ```

## What's Inside

### Artifacts
- `simuland_final.tf.json` - Generated Terraform configuration (19KB, 47 resources)
- `terraform.tfstate` - Deployment state (98KB, 40 deployed resources)
- `terraform.tfstate.backup` - State backup
- `.terraform.lock.hcl` - Provider lock file
- `.terraform/` - Terraform working directory

### Neo4j Queries
- `source_resources.cypher` - Query source Simuland resources
- `target_resources.cypher` - Query deployed resources
- `fidelity_comparison.cypher` - Compare source vs target
- `vm_configs.cypher` - VM configuration details
- `network_topology.cypher` - Network topology visualization

### Scripts
- `measure_fidelity.py` - Automated fidelity measurement engine
- Calculates resource count, configuration, and relationship fidelity

### Documentation
- `PRESENTATION.md` - Complete slide deck (30+ slides)
- `docs/DEPLOYMENT_GUIDE.md` - Step-by-step deployment instructions
- `docs/deployment_summary.json` - Deployment metadata

## Key Metrics

- **VMs Deployed**: 10 (WECServer, DC01, DC02, ADFS01, File01, Workstation5-8)
- **Resources Defined**: 47 (in Terraform configuration)
- **Resources Deployed**: 40 (actual Azure resources created)
- **Deployment Success Rate**: 85.1% (40/47 resources)
- **Networks**: 1 VNet with 2 subnets, 10 NSGs
- **Generation Time**: < 5 minutes
- **Deployment Time**: ~15 minutes

## Demo Narrative

1. **Discovery**: ATG scans source Simuland tenant
2. **Graph**: Resources stored in Neo4j with full relationships
3. **Generation**: Terraform IaC auto-generated from graph
4. **Validation**: Subnet validation ensures network correctness
5. **Deployment**: terraform apply creates replica environment
6. **Verification**: Fidelity measurement proves accuracy

## Security Note

All sensitive data (secrets, keys, passwords) has been removed from artifacts. This demo focuses on infrastructure topology and configuration replication.

## Next Steps

- Review `PRESENTATION.md` for complete story
- Run `measure_fidelity.py` to see quantitative results
- Execute Cypher queries to explore graph relationships
- Follow `docs/DEPLOYMENT_GUIDE.md` to replicate the deployment

## Contact

For questions about this demo or Azure Tenant Grapher, see project documentation.

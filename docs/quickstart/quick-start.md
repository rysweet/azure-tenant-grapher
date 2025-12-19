# Quick Start Guide

Get up and running with Azure Tenant Grapher in 15 minutes.

## Prerequisites

Before starting, ensure you have completed [Installation](installation.md).

## Your First Scan

### Step 1: Authenticate

```bash
az login --tenant <your-tenant-id>
```

### Step 2: Scan Your Tenant

```bash
# Basic scan
azure-tenant-grapher scan --tenant-id <your-tenant-id>

# Or using the short alias
atg scan --tenant-id <your-tenant-id>
```

The scan will:
- Discover all Azure resources across all subscriptions
- Create nodes and relationships in Neo4j
- Display progress in an interactive dashboard

### Step 3: Explore Your Graph

```bash
# Launch 3D visualization
atg visualize

# Or open Neo4j Browser
open http://localhost:7474
```

## Common Commands

### Scan Operations

```bash
# Scan specific subscription
atg scan --tenant-id <tenant> --subscription-id <subscription>

# Limit resources for testing
atg scan --tenant-id <tenant> --limit 100

# Enable debug mode
atg scan --tenant-id <tenant> --debug
```

### Generate IaC

```bash
# Generate Terraform
atg generate-iac --tenant-id <tenant> --format terraform

# Generate Bicep
atg generate-iac --tenant-id <tenant> --format bicep

# Generate with import blocks
atg generate-iac --tenant-id <tenant> --auto-import-existing
```

### Deploy with Agent

```bash
# Autonomous deployment with AI agent
atg deploy --agent

# With custom iteration limit
atg deploy --agent --max-iterations 10
```

### Database Operations

```bash
# Backup database
atg backup-db --output-file backup.dump

# Check database health
atg doctor
```

## Example Workflow

Complete workflow from scan to deployed resources:

```bash
# 1. Scan source tenant
atg scan --tenant-id <source-tenant>

# 2. Generate IaC for target tenant
atg generate-iac --target-tenant-id <target-tenant> --format terraform

# 3. Deploy with autonomous agent
atg deploy --agent --max-iterations 5

# 4. Verify deployment
atg visualize
```

## Next Steps

- **[Agent Deployment Tutorial](AGENT_DEPLOYMENT_TUTORIAL.md)** - Step-by-step autonomous deployment
- **[Autonomous Deployment Guide](../guides/AUTONOMOUS_DEPLOYMENT.md)** - Complete user guide
- **[Architecture Overview](../architecture/dual-graph.md)** - Understand the dual-graph design

## Troubleshooting

### Scan Fails

```bash
# Check Azure credentials
az account show

# Verify Neo4j is running
docker ps | grep neo4j

# Enable debug logging
atg scan --tenant-id <tenant> --debug
```

### No Resources Found

```bash
# Verify subscription access
az account list --output table

# Check RBAC permissions (need Reader role)
az role assignment list --assignee <your-principal-id>
```

### Performance Issues

```bash
# Use resource limits for large tenants
atg scan --tenant-id <tenant> --limit 1000

# Or use remote mode for powerful servers
# See docs/remote-mode/ for details
```

For more help:
- [Documentation Index](../INDEX.md)
- [Autonomous Deployment FAQ](../guides/AUTONOMOUS_DEPLOYMENT_FAQ.md)
- [GitHub Issues](https://github.com/rysweet/pr600/issues)

# Welcome to Azure Tenant Grapher

Azure Tenant Grapher discovers every resource in your Azure tenant, stores the results in a richly-typed Neo4j graph, and offers tooling to visualize, document, and recreate your cloud environment — including Infrastructure-as-Code generation, AI-powered summaries, and narrative description to simulated tenant creation.

![Azure Tenant Grapher Screenshot](resources/screenshot.png)

## Key Features

- **Comprehensive Azure Discovery** - Scan all subscriptions and resources in your tenant
- **Neo4j Graph Database** - Rich schema with relationship modeling including RBAC
- **Interactive 3D Visualization** - Filter, search, and explore your Azure environment
- **IaC Generation** - Export to Terraform, Bicep, or ARM templates
- **AI-Powered Agent Mode** - Natural language queries over your graph using MCP/AutoGen
- **Threat Modeling** - Automated DFD creation, threat enumeration, and security reports
- **Remote Mode** - Run on powerful remote servers (64GB RAM, 8 vCPUs) for large tenants
- **Cross-Tenant Deployment** - Replicate resources across Azure tenants

## Quick Start

```bash
# 1. Install dependencies
uv sync && source .venv/bin/activate

# 2. Configure environment
cp .env.example .env

# 3. Authenticate with Azure
az login --tenant <your-tenant-id>

# 4. Scan your Azure tenant
azure-tenant-grapher scan --tenant-id <your-tenant-id>

# 5. Visualize in 3D
azure-tenant-grapher visualize
```

## Getting Started

New to Azure Tenant Grapher? Start here:

1. **[Installation Guide](quickstart/installation.md)** - Set up your environment
2. **[Quick Start Tutorial](quickstart/quick-start.md)** - Your first scan in 15 minutes
3. **[Documentation Index](INDEX.md)** - Complete documentation map

## Popular Guides

- **[Autonomous Deployment](guides/AUTONOMOUS_DEPLOYMENT.md)** - AI-powered deployment with automatic error recovery
- **[Agent Deployment Tutorial](quickstart/AGENT_DEPLOYMENT_TUTORIAL.md)** - Step-by-step walkthrough from IaC to deployed resources
- **[Terraform Import Blocks](concepts/TERRAFORM_IMPORT_BLOCKS.md)** - Understanding and using import blocks
- **[Cross-Tenant Deployment](design/cross-tenant-translation/INTEGRATION_SUMMARY.md)** - Deploy resources across Azure tenants

## Architecture

Azure Tenant Grapher uses a **dual-graph architecture** where every resource exists as two nodes:

- **Original nodes** (`:Resource:Original`) - Real Azure IDs from source tenant
- **Abstracted nodes** (`:Resource`) - Translated IDs for cross-tenant deployment
- Linked by `SCAN_SOURCE_NODE` relationships

This enables cross-tenant deployments with safe ID abstraction while maintaining query flexibility.

Learn more in [Dual-Graph Architecture](architecture/dual-graph.md) and [SCAN_SOURCE_NODE Relationships](architecture/scan-source-node-relationships.md).

## Key Concepts

- **[Terraform Import Blocks](concepts/TERRAFORM_IMPORT_BLOCKS.md)** - How ATG generates import blocks and why they matter
- **[Import First Strategy](patterns/IMPORT_FIRST_STRATEGY.md)** - Eliminate deployment conflicts with "import first, create second"
- **[Neo4j Schema Reference](NEO4J_SCHEMA_REFERENCE.md)** - Complete graph database schema documentation

## Need Help?

- **[Autonomous Deployment FAQ](guides/AUTONOMOUS_DEPLOYMENT_FAQ.md)** - Common questions about agent mode
- **[Terraform Import Troubleshooting](guides/TERRAFORM_IMPORT_TROUBLESHOOTING.md)** - Fix missing or broken import blocks
- **[GitHub Issues](https://github.com/rysweet/pr600/issues)** - Report bugs or request features
- **[Contributing Guide](CONTRIBUTING.md)** - Join the development community

## What's New

Recent improvements and features:

- **Issue #610**: Autonomous deployment with goal-seeking AI agent
- **Issue #570**: SCAN_SOURCE_NODE preservation fix (900+ false positives eliminated)
- **Issue #502**: Terraform validation complete (0 errors from 6,457 starting errors)
- **Bug #10**: Child resource import blocks fixed (110/177 missing blocks resolved)

See [Documentation Index](INDEX.md) for complete issue documentation.

## Project Status

| Metric | Status |
|--------|--------|
| Terraform Validation | ✅ 0 errors (from 6,457) |
| Resources Supported | 99.3% coverage |
| Import Blocks | 100% coverage |
| Cross-Tenant Deployment | ✅ Fully implemented |

---

**Ready to explore your Azure environment?** Start with the [Quick Start Tutorial](quickstart/quick-start.md) or dive into [Installation](quickstart/installation.md).

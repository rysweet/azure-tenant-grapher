# Command Walkthroughs Index

This directory contains a dedicated walkthrough for each Azure Tenant Grapher CLI command. Each file includes:

- A narrative and context for the command
- The exact CLI invocation (with minimal, fast flags)
- Real, redacted output in fenced code blocks
- Notes on flags, troubleshooting, and expected results

## Command Walkthroughs

### Core Commands
- [build.md](build.md) - Build the Neo4j graph from Azure resources
- [rebuild-edges.md](rebuild-edges.md) - Rebuild relationship edges
- [config.md](config.md) - Configure Azure Tenant Grapher settings
- [doctor.md](doctor.md) - Check system health and dependencies
- [test.md](test.md) - Run test suite

### Graph Operations
- [visualize.md](visualize.md) - Visualize the Neo4j graph
- [backup-db.md](backup-db.md) - Backup Neo4j database

### Specification & Generation
- [spec.md](spec.md) - View tenant specifications
- [generate-spec.md](generate-spec.md) - Generate tenant specification from graph
- [generate-iac.md](generate-iac.md) - Generate Infrastructure-as-Code templates
- [generate-sim-doc.md](generate-sim-doc.md) - Generate simulation documentation

### Deployment & Validation (New in Issue #278, #279)
- [deploy.md](deploy.md) - Deploy IaC to target tenant
- [validate-deployment.md](validate-deployment.md) - Validate deployment fidelity

### Advanced Features
- [threat-model.md](threat-model.md) - Generate threat models
- [agent-mode.md](agent-mode.md) - Run in agent mode
- [mcp-server.md](mcp-server.md) - Model Context Protocol server
- [create-tenant.md](create-tenant.md) - Create tenant from specification

Return to the [Demo Overview](../overview.md).

# CLI Commands Reference

This document provides a comprehensive reference for all Azure Tenant Grapher CLI commands.

## Core Commands

### scan
Discover and import Azure resources into the Neo4j graph database.

```bash
azure-tenant-grapher scan --tenant-id <tenant-id>
```

### visualize
Generate and open an interactive 3D visualization of the tenant graph.

```bash
azure-tenant-grapher visualize
```

### generate-spec
Generate an anonymized tenant specification in Markdown format.

```bash
azure-tenant-grapher generate-spec --limit 100
```

### generate-iac
Generate Infrastructure-as-Code from the graph.

```bash
azure-tenant-grapher generate-iac --format terraform --output-dir ./iac-output
```

### agent
Start the MCP agent mode for natural language queries.

```bash
azure-tenant-grapher agent
```

### threat-model
Generate threat models and security analysis.

```bash
azure-tenant-grapher threat-model
```

## Additional Commands

For a complete list of all commands and their options, run:

```bash
azure-tenant-grapher --help
```

For help on a specific command:

```bash
azure-tenant-grapher <command> --help
```

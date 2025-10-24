# Azure Tenant Grapher: Demo Walkthrough Overview

This overview provides a high-level guide to the Azure Tenant Grapher CLI and its features. Each command or command group has a dedicated walkthrough page with real, redacted output and usage examples. Use this document as your starting point and navigate to the detailed walkthroughs for each command.

## Table of Contents

- [Simuland Replication Demo Presentation](simuland-replication-slides.html) - Interactive slides showcasing complete infrastructure cloning
- [Environment Setup](#environment-setup)
- [Command Walkthroughs](#command-walkthroughs)

---

## Environment Setup

Before running any commands, ensure you have:

- Python 3.8+ and [uv](https://docs.astral.sh/uv/) for dependency management
- Docker & Docker Compose (for Neo4j)
- Azure CLI & Bicep CLI (for authentication and IaC deployment)
- A configured `.env` file (copy from `.env.example` and fill in required values)

Authenticate with Azure:

```bash
az login --tenant <your-tenant-id>
```

---

## Command Walkthroughs

Each CLI command has a dedicated walkthrough page:

- [build](commands/build.md) - Discover and process Azure tenant resources; builds the resource graph and launches the dashboard by default.
- [rebuild-edges](commands/rebuild-edges.md) - Recompute and refresh all resource relationships (edges) in the Neo4j graph without reloading raw resources.
- [config](commands/config.md) - Show the current configuration, environment variables, and important settings.
- [visualize](commands/visualize.md) - Generate interactive or static visualizations of the current tenant graph (e.g., 2D/3D diagrams).
- [spec](commands/spec.md) - Produce a detailed tenant specification (YAML/JSON/Markdown) representing the discovered Azure environment.
- [generate-spec](commands/generate-spec.md) - Create an anonymized specification for sharing or documentation, with optional output customization.
- [generate-iac](commands/generate-iac.md) - Generate Infrastructure-as-Code templates (e.g., Bicep) for resources or subsets of the tenant.
- [generate-sim-doc](commands/generate-sim-doc.md) - Generate a simulated Azure customer profile as a Markdown narrative for demos and testing.
- [threat-model](commands/threat-model.md) - Run the threat modeling agent to produce a Data Flow Diagram, enumerate threats, and generate a Markdown report.
- [agent-mode](commands/agent-mode.md) - Start agent mode, enabling natural language queries and automation via the MCP server and Neo4j.
- [mcp-server](commands/mcp-server.md) - Launch the MCP server; provides APIs and interfaces for agent-driven tasks and chat.
- [create-tenant](commands/create-tenant.md) - Simulate or create a new Azure tenant structure for testing or demonstration purposes.
- [backup-db](commands/backup-db.md) - Create a backup of the Neo4j graph database for disaster recovery or migration.
- [doctor](commands/doctor.md) - Check for required CLI tools, dependencies, and environment readiness; offers guided fixes.
- [test](commands/test.md) - Run all available tests (unit, integration, end-to-end) and clean up artifacts after completion.

Each walkthrough includes:

- A narrative and context for the command
- The exact CLI invocation (with minimal, fast flags)
- Real, redacted output in fenced code blocks
- Notes on flags, troubleshooting, and expected results

---

For advanced usage, troubleshooting, and appendices, see the [Appendix](commands/appendix.md).

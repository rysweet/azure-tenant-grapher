# Azure Tenant Grapher: Demo Walkthrough Overview

This overview provides a high-level guide to the Azure Tenant Grapher CLI and its features. Each command or command group has a dedicated walkthrough page with real, redacted output and usage examples. Use this document as your starting point and navigate to the detailed walkthroughs for each command.

## Table of Contents

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

- See `atg --help` for command documentation - Discover and process Azure tenant resources; builds the resource graph and launches the dashboard by default.
- See `atg --help` for command documentation - Recompute and refresh all resource relationships (edges) in the Neo4j graph without reloading raw resources.
- See `atg --help` for command documentation - Show the current configuration, environment variables, and important settings.
- See `atg --help` for command documentation - Generate interactive or static visualizations of the current tenant graph (e.g., 2D/3D diagrams).
- See `atg --help` for command documentation - Produce a detailed tenant specification (YAML/JSON/Markdown) representing the discovered Azure environment.
- See `atg --help` for command documentation - Create an anonymized specification for sharing or documentation, with optional output customization.
- See `atg --help` for command documentation - Generate Infrastructure-as-Code templates (e.g., Bicep) for resources or subsets of the tenant.
- See `atg --help` for command documentation - Generate a simulated Azure customer profile as a Markdown narrative for demos and testing.
- See `atg --help` for command documentation - Run the threat modeling agent to produce a Data Flow Diagram, enumerate threats, and generate a Markdown report.
- See `atg --help` for command documentation - Start agent mode, enabling natural language queries and automation via the MCP server and Neo4j.
- See `atg --help` for command documentation - Launch the MCP server; provides APIs and interfaces for agent-driven tasks and chat.
- See `atg --help` for command documentation - Simulate or create a new Azure tenant structure for testing or demonstration purposes.
- See `atg --help` for command documentation - Create a backup of the Neo4j graph database for disaster recovery or migration.
- See `atg --help` for command documentation - Check for required CLI tools, dependencies, and environment readiness; offers guided fixes.
- See `atg --help` for command documentation - Run all available tests (unit, integration, end-to-end) and clean up artifacts after completion.

Each walkthrough includes:

- A narrative and context for the command
- The exact CLI invocation (with minimal, fast flags)
- Real, redacted output in fenced code blocks
- Notes on flags, troubleshooting, and expected results

---

For advanced usage and troubleshooting, see individual command files in the commands/ directory.

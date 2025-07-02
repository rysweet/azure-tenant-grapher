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

- [build](commands/build.md)
- [rebuild-edges](commands/rebuild-edges.md)
- [progress](commands/progress.md)
- [config](commands/config.md)
- [visualize](commands/visualize.md)
- [spec](commands/spec.md)
- [generate-spec](commands/generate-spec.md)
- [generate-iac](commands/generate-iac.md)
- [generate-sim-doc](commands/generate-sim-doc.md)
- [threat-model](commands/threat-model.md)
- [agent-mode](commands/agent-mode.md)
- [mcp-server](commands/mcp-server.md)
- [create-tenant](commands/create-tenant.md)
- [backup-db](commands/backup-db.md)
- [doctor](commands/doctor.md)
- [test](commands/test.md)

Each walkthrough includes:

- A narrative and context for the command
- The exact CLI invocation (with minimal, fast flags)
- Real, redacted output in fenced code blocks
- Notes on flags, troubleshooting, and expected results

---

For advanced usage, troubleshooting, and appendices, see the [Appendix](commands/appendix.md).

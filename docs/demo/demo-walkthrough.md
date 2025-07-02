# Azure Tenant Grapher: End-to-End Demo Walkthrough
## Introduction

This document provides a comprehensive, step-by-step walkthrough of the Azure Tenant Grapher CLI and visualization features. Each section includes a narrative, real command usage, and real output (with sensitive details obfuscated). The walkthrough demonstrates both initial and advanced usage, error handling, and troubleshooting, using a demo tenant for illustration.

## Table of Contents

1. **Introduction**
2. **Environment Setup**
   - Prerequisites
   - Installation
   - Environment Variables
   - Azure Authentication
3. **Building the Azure Graph**
   - `build` command (with/without dashboard)
   - `--tenant-id`, `--no-dashboard`, `--resource-limit`, `--max-llm-threads`, `--generate-spec`, `--visualize`
   - Rebuilding edges: `--rebuild-edges`
4. **Interactive CLI Dashboard**
   - Dashboard controls (`x`, `i`, `d`, `w`)
   - Config, progress, and log panels
   - Log file location and usage
5. **Progress and Configuration**
   - `progress` command
   - `config` command
6. **Visualization**
   - `visualize` command
   - Output and troubleshooting
7. **Specification Generation**
   - `spec` command
   - `generate-spec` command (with output path)
8. **Agent Mode**
   - `agent-mode` command (REPL and one-off question)
   - Example session and output
9. **MCP Server**
   - `mcp-server` command
   - Enabling agent mode and natural language queries
10. **Infrastructure-as-Code (IaC) Generation**
    - `generate-iac` command (Bicep, ARM, Terraform)
    - Subset filters, rules file, destination RG, location, output
    - Deploying generated templates
11. **Threat Modeling**
    - `threat-model` command
    - Example workflow and output
12. **Tenant Creation from Markdown**
    - `create-tenant` command
    - Example input and output
13. **Database Backup**
    - `backup-db` command
14. **Advanced Usage**
    - Incremental builds
    - Error handling and troubleshooting
    - Log inspection
15. **Appendix**
    - Full command reference
    - Links to documentation

## Environment Setup

### Prerequisites

- Python 3.8+
- [uv](https://docs.astral.sh/uv/) (for dependency management)
- Docker & Docker Compose (for Neo4j)
- Azure CLI & Bicep CLI (for authentication and IaC deployment)

### Installation

```bash
uv sync
source .venv/bin/activate
cp .env.example .env
az login --tenant <your-tenant-id>
## Building the Azure Graph

The core workflow begins with building the Azure graph, which discovers all resources in your tenant and stores them in Neo4j.

### Show CLI Help

```bash
azure-tenant-grapher --help
```

<details>
<summary>Output</summary>

```text
Usage: azure-tenant-grapher [OPTIONS] COMMAND [ARGS]...

### Build Command Help

The `build` command is the main entry point for discovering and processing your Azure tenant resources.

```bash
azure-tenant-grapher build --help
```

<details>
<summary>Output</summary>

```text
Usage: azure-tenant-grapher build [OPTIONS]

  Build the complete Azure tenant graph with enhanced processing.

  By default, shows a live Rich dashboard with progress, logs, and interactive
  controls:   - Press 'x' to exit the dashboard at any time.   - Press 'i',
  'd', or 'w' to set log level to INFO, DEBUG, or WARNING.

  Use --no-dashboard to disable the dashboard and emit logs line by line to
  the terminal.

Options:
  --tenant-id TEXT           Azure tenant ID (defaults to AZURE_TENANT_ID from
                             .env)
  --resource-limit INTEGER   Maximum number of resources to process (for
                             testing)
  --max-llm-threads INTEGER  Maximum number of parallel LLM threads (default:
                             5)
  --no-container             Do not auto-start Neo4j container
  --generate-spec            Generate tenant specification after graph
                             building
  --visualize                Generate graph visualization after building
  --no-dashboard             Disable the Rich dashboard and emit logs line by
                             line
  --test-keypress-queue      Enable test mode for dashboard keypresses (for
                             integration tests only)
  --test-keypress-file TEXT  Path to file containing simulated keypresses (for
                             integration tests only)
  --rebuild-edges            Force re-evaluation of all relationships/edges
                             for all resources in the graph database
  --help                     Show this message and exit.
```
</details>

  Azure Tenant Grapher - Enhanced CLI for building Neo4j graphs of Azure
  resources.

Options:
  --log-level TEXT  Logging level (DEBUG, INFO, WARNING, ERROR)
  --help            Show this message and exit.

Commands:
  agent-mode        Start AutoGen MCP agent mode (Neo4j + MCP server +...
  backup-db         Backup the Neo4j database and save it to BACKUP_PATH.
  build             Build the complete Azure tenant graph with enhanced...
  config            Show current configuration (without sensitive data).
  container         Manage Neo4j container.
  create-tenant     Create a tenant from a markdown file.
  doctor            Check for all registered CLI tools and offer to...
  generate-iac      Generate Infrastructure-as-Code templates from graph...
  generate-sim-doc  Generate a simulated Azure customer profile as a...
  generate-spec     Generate anonymized tenant Markdown specification (no...
  gensimdoc         Generate a simulated Azure customer profile as a...
  mcp-server        Start MCP server (uvx mcp-neo4j-cypher) after...
  progress          Check processing progress in the database (no...
  spec              Generate only the tenant specification (requires...
  test              Run a test with limited resources to validate setup.
  threat-model      Run the Threat Modeling Agent workflow to generate a...
  visualize         Generate graph visualization from existing Neo4j data...
```
</details>

```

### Environment Variables

Copy `.env.example` to `.env` and fill in the required values for your Azure and Neo4j environment.
Sensitive values (like credentials) should never be committed to version control.

### Azure Authentication

Authenticate with Azure using your tenant ID:

```bash
az login --tenant <your-tenant-id>
```


## Table of Contents

1. **Introduction**
2. **Environment Setup**
   - Prerequisites
   - Installation
   - Environment Variables
   - Azure Authentication
3. **Building the Azure Graph**
   - `build` command (with/without dashboard)
   - `--tenant-id`, `--no-dashboard`, `--resource-limit`, `--max-llm-threads`, `--generate-spec`, `--visualize`
   - Rebuilding edges: `--rebuild-edges`
4. **Interactive CLI Dashboard**
   - Dashboard controls (`x`, `i`, `d`, `w`)
   - Config, progress, and log panels
   - Log file location and usage
5. **Progress and Configuration**
   - `progress` command
   - `config` command
6. **Visualization**
   - `visualize` command
   - Output and troubleshooting
7. **Specification Generation**
   - `spec` command
   - `generate-spec` command (with output path)
8. **Agent Mode**
   - `agent-mode` command (REPL and one-off question)
   - Example session and output
9. **MCP Server**
   - `mcp-server` command
   - Enabling agent mode and natural language queries
10. **Infrastructure-as-Code (IaC) Generation**
    - `generate-iac` command (Bicep, ARM, Terraform)
    - Subset filters, rules file, destination RG, location, output
    - Deploying generated templates
11. **Threat Modeling**
    - `threat-model` command
    - Example workflow and output
12. **Tenant Creation from Markdown**
    - `create-tenant` command
    - Example input and output
13. **Database Backup**
    - `backup-db` command
14. **Advanced Usage**
    - Incremental builds
    - Error handling and troubleshooting
    - Log inspection
15. **Appendix**
    - Full command reference
    - Links to documentation

---

**Flow Rationale:**
- The sequence starts with setup, then moves through the core workflow: build → dashboard → progress/config → visualization → spec → agent mode → MCP server → IaC → threat modeling → tenant creation → backup.
- Advanced usage, troubleshooting, and appendices are included at the end for completeness.

**Next Steps:**
- For each section, provide a narrative, real command input/output (with sensitive details obfuscated), and relevant notes.
- Validate all commands/options against the codebase.
- Ensure the document is comprehensive and user-focused.

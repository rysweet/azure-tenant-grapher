# Azure Tenant Grapher

Azure Tenant Grapher discovers every resource in your Azure tenant, stores the results in a richly-typed Neo4j graph, and offers powerful tooling to visualize, document, and manage your cloud environment— including Infrastructure-as-Code generation, AI-powered summaries, and interactive dashboards.

![Azure Tenant Grapher Screenshot](docs/resources/screenshot.png)

---

## Table of Contents

- [Features](#features)
- [Quick Start](#quick-start)
  - [Prerequisites](#prerequisites)
  - [Create & Explore Your Graph](#create--explore-your-graph)
- [Installation](#installation)
- [Usage](#usage)
  - [Build & Rebuild Graph](#build--rebuild-graph)
  - [Agent Mode](#agent-mode)
  - [Threat Modeling](#threat-modeling)
  - [Generate & Deploy IaC](#generate--deploy-iac)
  - [Database Backup](#database-backup)
- [Advanced Topics](#advanced-topics)
  - [Graph Enrichment & Refactor Plan](#graph-enrichment--refactor-plan)
  - [IaC Subset & Rules System](#iac-subset--rules-system)
  - [Architecture](#architecture)
- [Development & Testing](#development--testing)
- [Documentation](#documentation)
- [Contributing](#contributing)
- [License](#license)

---

## Features

- **Comprehensive Azure discovery** across all subscriptions.
- **Neo4j graph database** with rich schema and relationship modeling.
- **Extensible relationship engine** with modular rules (Tag, Region, CreatedBy, etc.).
- **Interactive 3D visualization** with filtering, search, and ResourceGroup labels.
- **Rich CLI dashboard** with live progress, logs, and configuration.
- **AI-powered documentation** and anonymized tenant specification generation.
- **Infrastructure-as-Code (IaC) generation** supporting Bicep, ARM, and Terraform, plus transformation rules and deployment scripts.
- **Agent Mode (MCP/AutoGen)** for natural-language queries over your graph.
- **Threat Modeling Agent** for automated DFD creation, threat enumeration, and Markdown reports.
- **Automated CLI tool management** and cross-platform support.
- **Comprehensive test suite** spanning unit, integration, and end-to-end scenarios.
- **Database backup & restore utilities** for Neo4j.

## Quick Start

### Prerequisites

- Python **3.8+**
- [uv](https://docs.astral.sh/uv/) (recommended for dependency management)
- Docker & Docker Compose (for Neo4j)
- Azure CLI & Bicep CLI (for authentication and IaC deployment)

### Create & Explore Your Graph

```bash
# 1. Install dependencies
uv sync

# 2. Activate the virtual environment
source .venv/bin/activate

# 3. Copy and edit environment variables
cp .env.example .env

# 4. Authenticate with Azure
az login --tenant <your-tenant-id>

# 5. Build the graph with the interactive dashboard
azure-tenant-grapher build --tenant-id <your-tenant-id>

# 6. Visualize your Azure graph in 3D
azure-tenant-grapher visualize
```

## Installation

```bash
# Clone the repository
git clone https://github.com/<org>/azure-tenant-grapher.git
cd azure-tenant-grapher

# Sync dependencies and create a .venv
uv sync
source .venv/bin/activate

# Configure environment variables
cp .env.example .env
az login
```

## Usage

### Error Handling and Troubleshooting

All CLI commands now provide clear, actionable error messages for common failure scenarios, especially for Neo4j and Azure OpenAI (LLM) issues. If you encounter an error:

- **Neo4j errors:** The CLI will suggest checking that Neo4j is running, the container is healthy, and credentials are correct. If using Docker, ensure the container is started and healthy. You can start it with `azure-tenant-grapher container` or `docker-compose up`.
- **LLM (Azure OpenAI) errors:** The CLI will prompt you to check that all required environment variables are set (`AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_KEY`, `AZURE_OPENAI_API_VERSION`) and that you have network connectivity.
- **General troubleshooting:** Run any command with `--log-level DEBUG` to get more detailed logs. The dashboard and CLI will print the log file location for further inspection.

### Structured Logging

All key events and errors are logged using **structured logging** with [`structlog`](https://www.structlog.org/), outputting logs in JSON/key-value format. This enables easy log parsing, filtering, and integration with log management tools.

- Logs are available in the CLI, dashboard, and log files.
- Adjust log level with `--log-level DEBUG` for more detail.
- Log files are written to a path printed by the CLI/dashboard for each run.
- Example log entry (JSON):
  ```json
  {
    "event": "Generated resource description",
    "resource_type": "Microsoft.Storage/storageAccounts",
    "resource_name": "mystorage",
    "description": "...",
    "level": "info",
    "timestamp": "2025-07-01T20:00:00Z"
  }
  ```
- For troubleshooting, inspect the log file for structured entries and error context.


```bash
# Build the Azure graph
azure-tenant-grapher build --tenant-id <your-tenant-id>

# Rebuild—all relationships will be re-evaluated
azure-tenant-grapher build --tenant-id <your-tenant-id> --rebuild-edges
```

### Agent Mode

Ask natural-language questions about your tenant. The agent chains tool calls (via the MCP server) to query Neo4j and return answers.

```bash
# Interactive REPL
azure-tenant-grapher agent-mode

# One-off question
azure-tenant-grapher agent-mode --question "How many storage resources are in the tenant?"
```

<details><summary>Example session</summary>

```text
MCP Agent is ready
🤖 Processing question: How many storage resources are in the tenant?
🔄 Step 1: Getting database schema...
✅ Schema retrieved
🔄 Step 2: Querying for storage resources...
✅ Query executed
🔄 Step 3: Processing results...
🎯 Final Answer: There are 3 storage resources in the tenant.
```

</details>

### Generate Tenant Specification

Generate an anonymized tenant specification (YAML/JSON) for documentation, sharing, or further processing.

```bash
azure-tenant-grapher generate-spec \
  --tenant-id <your-tenant-id> \
  --output ./my-tenant-spec.yaml
```

### MCP Server

Run the MCP server to enable agent mode and natural language queries.

```bash
# Start the MCP server
uv run azure-tenant-grapher mcp-server
```

### Generate & Deploy IaC

```bash
# Generate Bicep for a subset of resources
azure-tenant-grapher generate-iac \
  --format bicep \
  --subset-filter "types=Microsoft.Storage/*" \
  --rules-file ./config/replica-rules.yaml \
  --dest-rg "replica-rg" \
  --location "East US" \
  --output ./my-deployment

# Deploy the generated templates
cd my-deployment
./deploy.sh
```

### Threat Modeling agent example - example of using the MCP server in an agent.

See [./src/threat_model_agent/](./src/threat_model_agent/)

Generate a Data Flow Diagram, enumerate threats, and produce a Markdown report for your tenant.

```bash
azure-tenant-grapher threat-model --spec-path ./my-tenant-spec.md --summaries-path ./summaries.json
```

### Database Backup

```bash
azure-tenant-grapher backup-db ./my-neo4j-backup.dump
```

### IaC Subset & Rules System

Details in [`docs/design/iac_subset_bicep.md`](docs/design/iac_subset_bicep.md).


## Development & Testing

### Test Output and Artifact Cleanup

All integration tests that invoke the CLI will print the full CLI stdout and stderr on failure, making it easy to debug issues. Test artifacts (such as simdoc files, temporary files, and containers) are always cleaned up after tests, even if a test fails.

Run the full test suite (unit, integration, end-to-end):

```bash
uv run pytest -n auto
```

## Documentation

- [Product Requirements](.github/azure-tenant-grapher-prd.md)
- [Project Specification](.github/azure-tenant-grapher-spec.md)
- [Threat Modeling Agent Demo](docs/threat_model_agent_demo.md)
- [3D Visualization](docs/design/iac_subset_bicep.md)
- [Testing](tests/)

## Contributing

Issues and pull requests are welcome! Please open an issue to discuss major changes first. Ensure `markdownlint` and the test suite pass before submitting.

## License

MIT License. See [`LICENSE`](LICENSE) for details.

<!-- Roo Code configuration branch initialized: see issue #84 -->

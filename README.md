# Azure Tenant Resource Grapher

Azure Tenant Resource Grapher is an application that exhaustively discovers all resources in your Azure tenant, builds a rich Neo4j graph database of those resources and their relationships, and provides tools for visualization, analysis, replicating tenants, and Infrastructure-as-Code (IaC) generation using bicep, terraform, or ARM templates.

---

## 🚀 Quick Start

### 1. Install & Set Up

```bash
# Install dependencies
uv sync

# Install CLI entry points
uv pip install --editable .

# Activate the virtual environment
source .venv/bin/activate

# Copy and edit .env for your Azure tenant ID, openai configuration
cp .env.example .env

# Authenticate with Azure
az login --tenant <your-tenant-id>
```

### 2. Build Your Graph of the Azure Tenant

```bash
# Build the graph with the interactive dashboard
azure-tenant-grapher build --tenant-id <your-tenant-id>
```

### 3. Explore, Visualize, and Generate IaC

```bash
# Visualize your Azure graph in 3D
azure-tenant-grapher visualize

# Generate Bicep IaC for a subset of resources
# exclude the `--subset-filter` option to generate for the entire tenant
azure-tenant-grapher generate-iac \
  --format bicep \
  --subset-filter "types=Microsoft.Storage/*" \
  --rules-file ./config/replica-rules.yaml \
  --dest-rg "replica-rg" \
  --location "East US" \
  --output ./my-deployment

# Deploy the generated Bicep
cd my-deployment
./deploy.sh
```

### 4. MCP Server & Agent Mode

```bash
# Start the MCP server (requires Neo4j running)
azure-tenant-grapher mcp-server

# Start the AutoGen MCP agent (Neo4j + MCP server + agent chat loop)
azure-tenant-grapher agent-mode
```

---

## 📖 Table of Contents

- [Features](#features)
- [Installation](#installation)
- [Usage](#usage)
- [IaC Subset & Rules System](#iac-subset--rules-system)
- [Architecture](#architecture)
- [Development & Testing](#development--testing)
- [Troubleshooting](#troubleshooting)

---

## Features

- **Comprehensive Azure Discovery**: Enumerate all resources and relationships across all subscriptions in your tenant.
- **Neo4j Graph Database**: Build a rich, queryable graph of your Azure environment.
- **Interactive 3D Visualization**: Explore your environment visually with filtering, search, and node details.
- **IaC Generation**: Generate Bicep, ARM, or Terraform templates for your entire tenant or filtered subsets.
- **Transformation Rules**: Apply name, region, and tag transformations to resources via a YAML rules file.
- **Automated Deployment**: Generated IaC includes a ready-to-run deployment script.
- **AI Integration**: Optional AI-powered resource descriptions.
- **Modular, Testable Codebase**: Well-structured, with comprehensive test coverage.

---

## Installation

### Prerequisites

- Python 3.8+
- [uv](https://docs.astral.sh/uv/) (recommended for dependency management)
- Docker & Docker Compose (for Neo4j)
- Azure CLI & Bicep CLI (for authentication and IaC deployment)
- (Optional) [mcp-neo4j-cypher](https://github.com/neo4j-contrib/mcp-neo4j-cypher) and [autogen-ext](https://github.com/microsoft/autogen) for MCP server/agent mode

### Install Steps

```bash
uv sync
source .venv/bin/activate
cp .env.example .env
az login

```

---

## Usage

### CLI Commands

```bash
# Build the Azure graph
azure-tenant-grapher build --tenant-id <your-tenant-id>

# Visualize the graph
azure-tenant-grapher visualize

# Generate IaC (Bicep, ARM, Terraform)
azure-tenant-grapher generate-iac --help

# Check progress
azure-tenant-grapher progress

# Show configuration
azure-tenant-grapher config
```

# Start MCP server (Neo4j + MCP)
azure-tenant-grapher mcp-server

# Start AutoGen MCP agent (graph/tenant Q&A)
azure-tenant-grapher agent-mode

### VS Code Tasks

- **Install Dependencies**: Installs Python packages using uv
- **Start/Stop Neo4j Container**: Manages Neo4j Docker container
- **Run Azure Tenant Grapher**: Full application with prompts
- **Generate 3D Visualization**: From existing graph data

### Shell Scripts

- `./run-grapher.sh` (Unix/macOS/Linux)
- `./run-grapher.ps1` (Windows PowerShell)

---

## IaC Subset & Rules System

- **Subset Filtering**: Use `--subset-filter` to select resources by type, ID, or label.
- **Transformation Rules**: Use a YAML rules file to rename, retarget, and tag resources.
- **Automated Deployment**: Generated output includes a `deploy.sh` script for easy Azure deployment.

> **See:**
> - [docs/demo/subset_bicep_demo.md](docs/demo/subset_bicep_demo.md) — practical usage and examples
> - [docs/design/iac_subset_bicep.md](docs/design/iac_subset_bicep.md) — full rules file documentation and advanced options

---

## Architecture

- **Resource Walker**: Discovers all Azure resources and relationships.
- **Graph Builder**: Creates nodes and edges in Neo4j.
- **Visualization**: 3D interactive web-based graph.
- **IaC Emitters**: Generate Bicep, ARM, or Terraform from the graph.
- **Transformation Engine**: Applies rules for name, region, and tag changes.

---

## Development & Testing

- **Run all tests**: `python run_tests.py`
- **Lint and type check**: `uv run ruff check src/ tests/` and `uv run mypy --strict src/`
- **Test coverage**: `python -m pytest tests/ --cov=src --cov-report=html`

---

## Troubleshooting

- **Docker Issues**: Ensure Docker Desktop is running.
- **Neo4j Connection**: Check container status and credentials.
- **Azure Authentication**: Run `az login` and check permissions.
- **IaC Deployment**: Ensure Azure CLI and Bicep CLI are installed.

---

## Further Reading

- [docs/demo/subset_bicep_demo.md](docs/demo/subset_bicep_demo.md): Subset Bicep generation demo and rules file usage
- [docs/design/iac_subset_bicep.md](docs/design/iac_subset_bicep.md): Full design and documentation for the rules file system

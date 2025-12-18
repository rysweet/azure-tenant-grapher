# Azure Tenant Grapher

Azure Tenant Grapher discovers every resource in your Azure tenant, stores the results in a richly-typed Neo4j graph, and offers tooling to visualize, document, and recreate your cloud environment — including Infrastructure-as-Code generation, AI-powered summaries, and narrative description to simulated tenant creation.

![Azure Tenant Grapher Screenshot](docs/resources/screenshot.png)

---

## Table of Contents

- [Features](#features)
- [Quick Start](#quick-start)
  - [Prerequisites](#prerequisites)
  - [Create & Explore Your Graph](#create--explore-your-graph)
- [Installation](#installation)
- [Usage](#usage)
  - [Scan & Rebuild Graph](#scan--rebuild-graph)
  - [Agent Mode](#agent-mode)
  - [Threat Modeling](#threat-modeling)
  - [Generate & Deploy IaC](#generate--deploy-iac)
  - [Database Backup](#database-backup)
- [Advanced Topics](#advanced-topics)
  - [Graph Enrichment & Refactor Plan](#graph-enrichment--refactor-plan)
  - [IaC Subset & Rules System](#iac-subset--rules-system)
  - [Architecture](#architecture)
- [Demo Walkthrough System](#demo-walkthrough-system)
- [Development & Testing](#development--testing)
- [Documentation](#documentation)
- [Contributing](#contributing)
- [License](#license)

---

## Features

- **Comprehensive Azure discovery** across all subscriptions.
- **Azure AD identity import** including users, groups, and group memberships from Microsoft Graph API.
- **Neo4j graph database** with rich schema and relationship modeling including RBAC.
- **Extensible relationship engine** with modular rules (Tag, Region, CreatedBy, etc.).
- **Interactive 3D visualization** with filtering, search, and ResourceGroup labels.
- **CLI dashboard** with live progress, logs, and configuration.
- **Remote mode** for running ATG operations on powerful remote servers (64GB RAM, 8 vCPUs) - perfect for large tenants. See [Remote Mode Documentation](docs/remote-mode/).
- **AI-powered documentation** and anonymized tenant specification generation.
- **Infrastructure-as-Code (IaC) generation** supporting Bicep, ARM, and Terraform, plus transformation rules and deployment scripts.
- **Agent Mode (MCP/AutoGen)** for natural-language queries over your graph.
- **Generate Detailed Narrative Descriptions** of Simulated Tenants from a seed.
- **(re)Create a tenant environment** from a narrative description
- **Threat Modeling Agent** for automated DFD creation, threat enumeration, and Markdown reports.
- **Automated CLI tool management** and cross-platform support.
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

# 5. Scan the graph with the interactive dashboard
azure-tenant-grapher scan --tenant-id <your-tenant-id>

# 6. Visualize your Azure graph in 3D
azure-tenant-grapher visualize

# Or launch the desktop GUI (Electron app)
azure-tenant-grapher start
```

## Installation

```bash
# Clone the repository
git clone https://github.com/<org>/azure-tenant-grapher.git
cd azure-tenant-grapher

# Sync dependencies and create a .venv
uv sync
source .venv/bin/activate

# Note:
# All runtime dependencies are managed in pyproject.toml.
# requirements.txt is provided for compatibility, but you must keep both files in sync.
# If you add a new dependency, add it to pyproject.toml and run 'uv sync' to update the lockfile and your environment.

# Configure environment variables
cp .env.example .env
az login
```
## Dependency Management

All runtime dependencies **must** be listed in [`pyproject.toml`](pyproject.toml) under the `[project.dependencies]` section.
The [`requirements.txt`](requirements.txt) file is provided for compatibility with some tools, but it is not the source of truth.
Whenever you add, remove, or update a dependency, you **must**:

1. Edit `pyproject.toml` to reflect the change.
2. Run `uv sync` to update your environment and the lockfile.
3. Ensure `requirements.txt` is updated to match `pyproject.toml`.

> **Note:** Keeping `pyproject.toml` and `requirements.txt` in sync is required for correct installation and CI compatibility.
> Do **not** add dependencies to `requirements.txt` directly—always update `pyproject.toml` first.


## Usage

```bash
# Scan the Azure graph (includes Azure AD identity import by default)
azure-tenant-grapher scan --tenant-id <your-tenant-id>

# Scan without Azure AD identity import
azure-tenant-grapher scan --tenant-id <your-tenant-id> --no-aad-import

# Rescan—all relationships will be re-evaluated
azure-tenant-grapher scan --tenant-id <your-tenant-id> --rebuild-edges

# Scan with filtering by subscriptions (includes referenced identities)
azure-tenant-grapher scan --tenant-id <your-tenant-id> --filter-by-subscriptions sub1,sub2

# Scan with filtering by resource groups (includes referenced identities)
azure-tenant-grapher scan --tenant-id <your-tenant-id> --filter-by-rgs rg1,rg2
```

### Filtered Scanning with Identity Inclusion

When using `--filter-by-subscriptions` or `--filter-by-rgs` options, Azure Tenant Grapher automatically:

1. **Discovers only resources** matching your filter criteria
2. **Extracts identity references** from filtered resources:
   - System-assigned managed identities
   - User-assigned managed identities
   - Users, groups, and service principals from role assignments
3. **Imports only referenced identities** from Azure AD/Graph API
4. **Preserves all relationships** between filtered resources and their identities

This ensures your filtered graph contains all necessary identity information without importing the entire Azure AD directory.

### Azure AD Identity Import

By default, the `scan` command imports Azure AD identities (users, groups, and group memberships) from Microsoft Graph API. This enriches the graph with identity and RBAC relationships.

**Requirements:**
- Service principal credentials (`AZURE_CLIENT_ID` and `AZURE_CLIENT_SECRET`)
- Microsoft Graph API permissions for reading users and groups

**What gets imported:**
- Azure AD users and their properties
- Security groups and their memberships
- Role assignments linking identities to resources

**Disabling AAD import:**
```bash
# Via CLI flag
azure-tenant-grapher scan --tenant-id <your-tenant-id> --no-aad-import

# Via environment variable
export ENABLE_AAD_IMPORT=false
azure-tenant-grapher scan --tenant-id <your-tenant-id>
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

# Generate Terraform with automatic import blocks (Issue #412)
azure-tenant-grapher generate-iac \
  --format terraform \
  --auto-import-existing \
  --import-strategy resource_groups \
  --target-subscription <TARGET_SUB_ID>

# Cross-tenant deployment with import blocks
azure-tenant-grapher generate-iac \
  --target-tenant-id <TARGET_TENANT> \
  --target-subscription <TARGET_SUB> \
  --auto-import-existing \
  --import-strategy resource_groups

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

## Desktop GUI (Electron App)

The project includes a full-featured desktop application built with Electron and React that provides a graphical interface for all CLI functionality.

### GUI Quick Start

```bash
# Start the desktop app (user mode)
azure-tenant-grapher start

# Stop the desktop app
azure-tenant-grapher stop
```

### GUI Development

For developers working on the GUI itself:

```bash
# Install development dependencies
cd spa
npm install

# Start in development mode with hot reload
npm run dev

# Build for production
npm run build
```

### GUI Features

- **Tabbed Interface**: All CLI commands accessible through intuitive tabs
- **Visual Graph Explorer**: Interactive 3D visualization with search and filtering
- **Real-time Logs**: Live log streaming with filtering and export
- **Configuration Manager**: Manage environment variables and Azure credentials
- **Integrated Terminal**: Run CLI commands directly from the GUI
- **Process Management**: Monitor and control running operations

The GUI automatically detects your Neo4j database state and Azure configuration, providing a seamless experience for both new and existing users.

## Demo Walkthrough System

The project includes a comprehensive demo walkthrough system that showcases all Azure Tenant Grapher capabilities through automated, step-by-step demonstrations with screenshot capture and validation.

### Demo Features

- **14 Scenario Files**: One for each SPA tab, covering all functionality
- **3 Story Workflows**: Quick demo (5 min), full walkthrough (15 min), and security-focused demo
- **Automated Screenshots**: Capture with metadata tracking and HTML gallery generation
- **E2E Testing**: Functions as comprehensive integration tests with visual validation
- **Gadugi Integration**: Compatible with the gadugi-agentic-test framework

### Running Demos

```bash
# Install demo dependencies
cd demos/walkthrough
uv pip install -r requirements.txt
playwright install chromium

# Run quick demo (5 minutes)
python orchestrator.py --story quick_demo

# Run full walkthrough (15 minutes)
python orchestrator.py --story full_walkthrough

# Run security-focused demo
python orchestrator.py --story security_focus

# Run individual scenario
python orchestrator.py --scenario 03_scan

# Headless mode for CI/CD
python orchestrator.py --story quick_demo --headless

# Generate screenshot gallery
python orchestrator.py --gallery
open screenshots/gallery.html
```

### Demo Scenarios

1. **00_setup** - Authentication and initial setup
2. **01_status** - Status tab overview and health checks
3. **02_config** - Configuration management
4. **03_scan** - Resource scanning and discovery
5. **04_visualize** - Graph visualization
6. **05_generate_spec** - Terraform spec generation
7. **06_generate_iac** - Infrastructure as Code generation
8. **07_threat_model** - Threat modeling and analysis
9. **08_agent_mode** - AI agent interactions
10. **09_create_tenant** - New tenant creation
11. **10_cli** - Command-line interface testing
12. **11_logs** - Audit logs and history
13. **12_docs** - Documentation viewer
14. **13_undeploy** - Cleanup and teardown

### CI/CD Integration

```yaml
# Add to GitHub Actions workflow
- name: Run Demo Tests
  run: |
    cd demos/walkthrough
    python orchestrator.py --headless --story full_walkthrough

- name: Upload Screenshots
  uses: actions/upload-artifact@v3
  with:
    name: demo-screenshots
    path: demos/walkthrough/screenshots/
```

For more details, see [demos/walkthrough/README.md](demos/walkthrough/README.md).

## Development & Testing

### Test Output and Artifact Cleanup

All integration tests that invoke the CLI will print the full CLI stdout and stderr on failure, making it easy to debug issues. Test artifacts (such as simdoc files, temporary files, and containers) are always cleaned up after tests, even if a test fails.

Run the full test suite (unit, integration, end-to-end):

```bash
uv run pytest -n auto
```

### Automated Test Output and Artifacts

All test runs (local and CI) use a unified workflow to capture and report test output:

- **Command:**
  ```bash
  uv run pytest --junitxml=pytest-results.xml --html=pytest-report.html 2>&1 | tee pytest-output.log
  ```
- **Artifacts Generated:**
  - `pytest-output.log` — Full raw test output (stdout/stderr)
  - `pytest-results.xml` — JUnit XML for structured CI reporting
  - `pytest-report.html` — Rich HTML report (viewable in browser)

**In CI:**
These files are uploaded as workflow artifacts and can be downloaded from the GitHub Actions run summary.

**Locally:**
You can run the above command directly, or use the provided helper script (`scripts/run_tests_with_artifacts.sh`) for convenience.

All test output artifacts are excluded from version control via `.gitignore`.
## Documentation

- [Product Requirements](.github/azure-tenant-grapher-prd.md)
- [Project Specification](.github/azure-tenant-grapher-spec.md)
- [Remote Mode Documentation](docs/remote-mode/) - Run ATG on powerful remote servers for large tenants
- [Neo4j Graph Schema Reference](docs/NEO4J_SCHEMA_REFERENCE.md) - Complete reference for node types, relationships, and schema assembly
- [Architecture-Based Replication](docs/ARCHITECTURE_BASED_REPLICATION.md) - Pattern-based tenant replication using spectral graph comparison
- [Architectural Pattern Analysis](docs/ARCHITECTURAL_PATTERN_ANALYSIS.md) - Detect and analyze Azure architectural patterns
- [Threat Modeling Agent Demo](docs/threat_model_agent_demo.md)
- [3D Visualization](docs/design/iac_subset_bicep.md)
- [Testing](tests/)

## Contributing

Issues and pull requests are welcome! Please open an issue to discuss major changes first. Ensure `markdownlint` and the test suite pass before submitting.

## License

MIT License. See [`LICENSE`](LICENSE) for details.

<!-- Roo Code configuration branch initialized: see issue #84 -->

# Project Context

**This file provides project-specific context to Claude Code agents.**

When amplihack is installed in your project, customize this file to describe YOUR project. This helps agents understand what you're building and provide better assistance.

## Quick Start

Replace the sections below with information about your project.

---

## Project: azure-tenant-grapher

## Overview

Azure Tenant Grapher discovers every resource in your Azure tenant, stores the results in a richly-typed Neo4j graph, and offers tooling to visualize, document, and recreate your cloud environment — including Infrastructure-as-Code generation, AI-powered summaries, and narrative description to simulated tenant creation. ![Azure Tenant Grapher Screenshot](docs/resources/screenshot.png)

## Architecture

### Key Components

- **Azure Discovery Engine** (`azure_tenant_grapher.py`): Core service that scans Azure subscriptions, discovers resources via Azure SDK, and builds comprehensive inventory with RBAC relationships
- **Neo4j Graph Database** (`db/`): Richly-typed graph storage with nodes for resources, identities, and relationships (RBAC, networking, monitoring, dependencies)
- **Relationship Rules Engine** (`relationship_rules/`): Modular rule system that creates graph edges based on tags, regions, diagnostics, networking, monitoring, and dependencies
- **IaC Generation** (`iac/`): Multi-format Infrastructure-as-Code emitters (Bicep, ARM, Terraform) with translators, validators, and resource-specific handlers for 50+ Azure resource types
- **3D Visualization** (`visualization/`, `graph_visualizer.py`): Interactive 3D force-directed graph with filtering, search, ResourceGroup labels, and HTML/CSS/JavaScript rendering
- **CLI Dashboard** (`rich_dashboard.py`, `cli_dashboard_widgets/`): Real-time terminal UI with progress tracking, logs, configuration management using Rich library
- **Agent Mode** (`agent_mode.py`, `commands/agent.py`, `commands/mcp.py`): MCP/AutoGen integration for natural-language queries over the graph, AI-powered tenant analysis
- **Tenant Specification Service** (`services/tenant_specification_service.py`, `hierarchical_spec_generator.py`): AI-driven anonymized tenant descriptions and specifications for replication
- **Threat Modeling Agent** (`threat_modeling_agent/`): Automated DFD creation, STRIDE threat enumeration, and security report generation
- **Deployment System** (`deployment/`, `container_manager.py`): Job tracking, Terraform deployment management, and Docker container orchestration
- **Remote Mode** (`remote/`): Run ATG operations on powerful remote servers (64GB RAM, 8 vCPUs) for large tenants
- **Tenant Creator** (`tenant_creator.py`, `architecture_based_replicator.py`): Generate simulated tenants from narrative descriptions or architectural patterns

### Technology Stack

- **Language**: Python 3.8+ (primary implementation language)
- **Database**: Neo4j (graph database for resource relationships)
- **Cloud SDK**: Azure SDK for Python, Azure CLI, Bicep CLI
- **Visualization**: JavaScript (3D force-directed graphs), HTML/CSS
- **CLI Framework**: Click (command-line interface), Rich (terminal UI)
- **AI Integration**: MCP (Model Context Protocol), AutoGen (multi-agent), LLM APIs
- **IaC Tools**: Bicep, ARM Templates, Terraform
- **Dependency Management**: uv (recommended), pip
- **Testing**: pytest, agentic testing with gadugi-agentic-test
- **Containerization**: Docker, Docker Compose

## Development Guidelines

### Code Organization

```
src/
├── azure_tenant_grapher.py    # Main entry point and discovery orchestration
├── cli_commands*.py           # CLI command implementations (scan, visualize, agent, etc.)
├── rich_dashboard.py          # Terminal UI dashboard
├── db/                        # Neo4j database connection and session management
├── models/                    # Data models (cost, filter configs, tenant specs)
├── services/                  # Business logic services
│   ├── identity_collector.py          # Azure AD/Graph API identity import
│   ├── resource_processing_service.py # Resource processing and sanitization
│   ├── tenant_specification_service.py # Tenant spec generation
│   └── cost/                          # Cost analysis and forecasting
├── iac/                       # Infrastructure-as-Code generation
│   ├── emitters/              # IaC format emitters (Bicep, ARM, Terraform)
│   │   ├── terraform/handlers/    # 50+ resource-specific Terraform handlers
│   ├── translators/           # Resource transformation logic
│   ├── validators/            # IaC validation and subnet validation
│   ├── plugins/               # Extensible IaC plugin system
│   └── data_plane_plugins/    # Data plane operations (KeyVault, Storage)
├── relationship_rules/        # Modular graph relationship rules
│   ├── tag_rule.py           # Tag-based relationships
│   ├── network_rule.py       # Network connectivity relationships
│   ├── diagnostic_rule.py    # Diagnostic settings relationships
│   ├── monitoring_rule.py    # Monitoring relationships
│   └── depends_on_rule.py    # Dependency relationships
├── visualization/             # 3D graph visualization HTML/CSS/JS builders
├── commands/                  # CLI command modules (agent, scan, mcp, tenant, etc.)
├── deployment/                # Deployment tracking and job management
├── threat_modeling_agent/     # Automated threat modeling
├── remote/                    # Remote mode for large tenant operations
├── config/                    # Configuration management
├── utils/                     # Utility functions (graph ID resolution, Neo4j startup)
└── validation/                # Graph validation and reporting

tests/                         # Pytest test suite
docs/                          # Comprehensive documentation
dotnet/                        # .NET components (if any)
spa/                           # TypeScript/React SPA (if any)
```

### Key Patterns

- **Modular Relationship Rules**: Each relationship type (tags, network, monitoring) is a separate rule class following a common interface, making the system extensible
- **Multi-Format IaC Emitters**: Strategy pattern for different IaC formats (Bicep, ARM, Terraform) with resource-specific handlers
- **Graph-First Architecture**: Neo4j graph database as single source of truth for all resources and relationships
- **ID Abstraction Service**: Generates Azure-compliant resource names for cross-tenant deployments (DISCOVERIES.md has details on globally unique name handling)
- **Plugin Architecture**: Extensible plugin system for data plane operations (KeyVault secrets, Storage blobs)
- **CLI Dashboard Pattern**: Rich library for interactive terminal UI with real-time progress updates
- **Service Layer**: Business logic separated into services (identity collection, resource processing, tenant specification)
- **Async Neo4j Sessions**: Async database operations for performance with large graphs
- **Filtered Scanning**: Scan by subscription or resource group with automatic identity reference inclusion
- **Dependency Management**: All dependencies in `pyproject.toml`, `requirements.txt` for compatibility (must keep in sync)

### Testing Strategy

- **Unit Tests**: pytest-based unit tests for individual components (services, utilities, IaC handlers)
- **Integration Tests**: Test complete workflows (scan → graph → IaC generation)
- **Agentic Testing**: Use gadugi-agentic-test framework for behavior-driven testing of CLI and agent interactions
- **Manual Testing**: Test with real Azure tenants during development (required for Azure SDK validation)
- **Test Structure**: Tests organized parallel to source (`tests/unit/`, `tests/integration/`)
- **Coverage**: Focus on critical paths (Azure discovery, graph operations, IaC generation)
- **CI/CD**: GitHub Actions for automated testing on push/PR
- **Testing Pyramid**: 60% unit tests, 30% integration tests, 10% end-to-end user testing (mandatory before commit per USER_PREFERENCES.md)

## Domain Knowledge

### Business Context

**Problem**: Organizations struggle to understand, document, and replicate their complex Azure cloud environments. Manual inventory is error-prone, documentation gets stale, and recreating environments is time-consuming.

**Solution**: Azure Tenant Grapher automatically discovers and maps every Azure resource into a queryable graph database, enabling visualization, documentation, threat modeling, and Infrastructure-as-Code generation for reliable environment replication.

**Users**:
- **Cloud Architects**: Understand tenant architecture, relationships, and dependencies
- **DevOps Engineers**: Generate IaC for environment replication, disaster recovery
- **Security Teams**: Threat modeling, RBAC analysis, security posture assessment
- **Compliance Teams**: Documentation, audit trails, resource inventory
- **Developers**: Query infrastructure via natural language (Agent Mode), understand dependencies

**Use Cases**:
1. **Infrastructure Documentation**: Generate comprehensive, always-up-to-date documentation
2. **Environment Replication**: Create IaC from existing tenants, replicate to new regions/subscriptions
3. **Disaster Recovery**: Rapid environment reconstruction from graph snapshots
4. **Threat Modeling**: Automated security analysis with DFD generation and STRIDE enumeration
5. **Cost Analysis**: Understand resource costs and forecast spending
6. **Compliance Auditing**: Resource inventory with RBAC relationships for compliance reporting
7. **Multi-Tenant Management**: Anonymized tenant specifications for simulated environment creation

### Key Terminology

- **Tenant**: Azure AD tenant containing subscriptions, resources, and identities
- **Resource**: Any Azure service instance (VM, Storage Account, Virtual Network, etc.)
- **Graph**: Neo4j graph database where nodes are resources/identities and edges are relationships
- **Relationship**: Connections between resources (RBAC, network, monitoring, diagnostic, dependency, tag)
- **RBAC**: Role-Based Access Control - Azure's permission model (roles, assignments, principals)
- **Identity**: Azure AD user, group, service principal, or managed identity
- **Managed Identity**: System-assigned or user-assigned identity for Azure resources
- **IaC**: Infrastructure-as-Code (Bicep, ARM Templates, Terraform)
- **Bicep**: Azure-native declarative language for resource deployment
- **ARM Template**: Azure Resource Manager JSON template format
- **Terraform**: HashiCorp's multi-cloud IaC tool
- **Resource Group**: Logical container for Azure resources
- **Subscription**: Billing and management boundary in Azure
- **Neo4j**: Graph database used to store resources and relationships
- **Cypher**: Neo4j's graph query language
- **MCP**: Model Context Protocol - standard for AI agent communication
- **AutoGen**: Microsoft's multi-agent framework for orchestration
- **Agent Mode**: Natural-language query interface over the graph
- **Threat Model**: Security analysis using STRIDE methodology
- **DFD**: Data Flow Diagram - visual representation of system components and data flows
- **STRIDE**: Threat classification framework (Spoofing, Tampering, Repudiation, Information Disclosure, Denial of Service, Elevation of Privilege)
- **Filtered Scanning**: Scan specific subscriptions or resource groups (includes referenced identities automatically)
- **Relationship Rules**: Modular rules that create edges between nodes based on resource properties
- **ID Abstraction**: Service that generates Azure-compliant resource names for cross-tenant deployments
- **Globally Unique Names**: Azure resources requiring unique names across all Azure (Storage Accounts, Key Vaults, etc.)

## Common Tasks

### Development Workflow

1. **Setup Environment**:
   ```bash
   git clone https://github.com/rysweet/azure-tenant-grapher.git
   cd azure-tenant-grapher
   uv sync
   source .venv/bin/activate
   cp .env.example .env
   ```

2. **Authenticate with Azure**:
   ```bash
   az login --tenant <your-tenant-id>
   ```

3. **Start Neo4j**:
   ```bash
   docker-compose up -d  # Starts Neo4j container
   ```

4. **Run Scan** (populates graph):
   ```bash
   azure-tenant-grapher scan --tenant-id <tenant-id>
   ```

5. **Develop Features**:
   - Add new relationship rules in `src/relationship_rules/`
   - Add IaC handlers in `src/iac/emitters/<format>/handlers/`
   - Add services in `src/services/`
   - Write tests in `tests/` parallel to source structure

6. **Test Changes**:
   ```bash
   pytest tests/
   pytest tests/unit/services/  # Specific test directory
   ```

7. **Visualize Graph**:
   ```bash
   azure-tenant-grapher visualize  # Opens 3D graph in browser
   ```

8. **Generate IaC**:
   ```bash
   azure-tenant-grapher generate-iac --format terraform --output-dir ./iac-output
   ```

### Deployment Process

**Local Development**:
- Run directly from source using `uv` virtual environment
- Neo4j runs in Docker container locally
- Azure CLI for authentication

**Remote Mode** (for large tenants):
- Deploy to remote server with high resources (64GB RAM, 8 vCPUs)
- Configure remote connection in `.env`
- Operations run remotely, results streamed back
- See `docs/remote-mode/` for setup

**CI/CD**:
- GitHub Actions for automated testing
- Tests run on push/PR to validate changes
- No automatic deployment (manual installation required)

**Package Distribution**:
- Install via pip: `pip install azure-tenant-grapher`
- Install via uv: `uv pip install azure-tenant-grapher`
- Clone repository for development

**Docker Deployment**:
- Neo4j runs in Docker container (required dependency)
- Docker Compose configuration in repository root
- Container persists graph data across restarts

## Important Notes

### Critical Considerations

- **Azure Authentication Required**: Must authenticate with `az login` before scanning. Service principal authentication also supported.
- **Neo4j Dependency**: Neo4j must be running before any graph operations. Use Docker Compose or local Neo4j installation.
- **Large Tenant Performance**: Tenants with 1000+ resources may require Remote Mode for adequate performance (64GB RAM recommended).
- **Dependency Sync**: Keep `pyproject.toml` and `requirements.txt` in sync. `pyproject.toml` is source of truth, run `uv sync` after changes.
- **Azure SDK Rate Limits**: Large scans may hit Azure API rate limits. Use filtered scanning (`--filter-by-subscriptions`) to reduce load.
- **Identity Import**: Azure AD identity import requires Microsoft Graph API permissions. Use `--no-aad-import` flag if permissions unavailable.
- **IaC Generation Limitations**: Some Azure resources don't have complete IaC support yet. 50+ resource types currently supported with active development.
- **Globally Unique Names**: Storage Accounts, Key Vaults, Container Registries require globally unique names. ID Abstraction Service handles this (see DISCOVERIES.md for details).
- **Filtered Scanning Identity Inclusion**: When using `--filter-by-subscriptions` or `--filter-by-rgs`, referenced identities are automatically included (system-assigned, user-assigned managed identities, RBAC principals).
- **Testing Requirements**: Mandatory end-to-end user testing before commits (USER_PREFERENCES.md). Test with `uvx --from git+<branch>` syntax.
- **Port Conflicts**: If Neo4j container ports conflict, see `src/utils/neo4j_startup.py` for automatic port resolution.

### Known Issues

- **Azure Globally Unique Resource Names**: Only 5 of 36 globally unique resource types have proper name transformation (13.9% coverage). See DISCOVERIES.md "Azure Globally Unique Resource Name Bugs" for full analysis and recommended hybrid approach with `AzureNameSanitizer` service.
- **Two-Stage Name Transformation**: ID Abstraction Service generates names with hyphens, but Storage/ACR handlers must strip them. Root cause and solution documented in DISCOVERIES.md (2026-01-13 entry).
- **Hook Double Execution**: Claude Code bug #10871 causes SessionStart/Stop hooks to execute twice. Configuration is correct, but upstream bug affects performance. Documented in DISCOVERIES.md (2025-11-21 entry).

---

## About This File

This file is installed by amplihack to provide project-specific context to AI agents.

**For more about amplihack itself**, see PROJECT_AMPLIHACK.md in this directory.

**Tip**: Keep this file updated as your project evolves. Accurate context leads to better AI assistance.

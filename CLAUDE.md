# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Azure Tenant Grapher is a security-focused tool that builds a Neo4j graph database representation of Azure tenant resources and their relationships. It generates Infrastructure-as-Code (IaC) in multiple formats (Terraform, ARM, Bicep) and provides threat modeling capabilities.

## Development Commands

### Testing
```bash
# Run all tests with artifacts
./scripts/run_tests_with_artifacts.sh

# Run specific test
uv run pytest tests/test_specific.py -v

# Run tests with coverage
uv run pytest --cov=src --cov-report=term-missing
```

### Linting and Type Checking
```bash
# Run Ruff linter
uv run ruff check src scripts tests

# Run Ruff formatter
uv run ruff format src scripts tests

# Run Pyright type checker
uv run pyright

# Run Bandit security linter
uv run bandit -r src scripts
```

### Pre-commit Hooks
```bash
# Install pre-commit hooks
uv run pre-commit install

# Run pre-commit on all files
uv run pre-commit run --all-files
```

### Running the CLI
```bash
# Main CLI commands (all aliases work: azure-tenant-grapher, azure-graph, atg)
uv run atg scan --tenant-id <TENANT_ID>
uv run atg generate-spec
uv run atg generate-iac --tenant-id <TENANT_ID> --format terraform
uv run atg create-tenant --spec path/to/spec.md
uv run atg visualize
uv run atg agent-mode
uv run atg threat-model
uv run atg doctor  # Check and install CLI dependencies

# IaC generation with subnet validation (Issue #333)
uv run atg generate-iac --tenant-id <TENANT_ID>  # Validates subnets by default
uv run atg generate-iac --tenant-id <TENANT_ID> --auto-fix-subnets  # Auto-fix invalid subnets
uv run atg generate-iac --tenant-id <TENANT_ID> --skip-subnet-validation  # Skip validation (not recommended)

# Cross-tenant IaC generation (Issue #406)
uv run atg generate-iac --target-tenant-id <TARGET_TENANT_ID>  # Cross-tenant deployment
uv run atg generate-iac --target-tenant-id <TARGET_TENANT_ID> --target-subscription <TARGET_SUB_ID>  # With target subscription
uv run atg generate-iac --target-tenant-id <TARGET_TENANT_ID> --identity-mapping-file identity_mappings.json  # With Entra ID translation
uv run atg generate-iac --target-tenant-id <TARGET_TENANT_ID> --auto-import-existing --import-strategy resource_groups  # Import pre-existing resources

# SPA/GUI commands
uv run atg start    # Launch Electron GUI
uv run atg stop     # Stop GUI application
```

## Architecture Overview

### Core Components

1. **Azure Discovery Service** (`src/services/azure_discovery_service.py`):
   - Discovers Azure resources using Azure SDK
   - Handles pagination and rate limiting
   - Supports resource limits for testing

2. **Resource Processing Service** (`src/services/resource_processing_service.py`):
   - Processes discovered resources
   - Creates Neo4j nodes and relationships
   - Applies relationship rules

3. **Relationship Rules** (`src/relationship_rules/`):
   - Modular rules for creating graph relationships
   - Each rule handles specific relationship types (network, identity, monitoring, etc.)
   - Plugin-based architecture for extensibility

4. **Neo4j Container Management** (`src/container_manager.py`):
   - Manages Neo4j Docker container lifecycle
   - Handles database backups
   - Ensures Neo4j is running before operations

5. **IaC Generation** (`src/iac/`):
   - Traverses Neo4j graph to generate IaC
   - Supports multiple output formats via emitters
   - Handles resource dependencies and ordering
   - Validates subnet address space containment (Issue #333)
   - Cross-tenant resource translation (Issue #406)

6. **Cross-Tenant Translation** (`src/iac/translators/`):
   - Translates resource IDs from source to target subscription
   - Translates Entra ID object IDs and tenant IDs
   - 6 concrete translators: Storage, Identity, Database, KeyVault, AppService, EntraId
   - Auto-discovery via decorator-based registry
   - Comprehensive reporting

7. **Terraform Import** (`src/iac/importers/`):
   - Automatically imports pre-existing Azure resources into Terraform state
   - Three import strategies: resource_groups, all_resources, selective
   - Handles resource name conflicts by updating (not recreating)

6. **IaC Validators** (`src/iac/validators/`):
   - **SubnetValidator**: Validates subnets are within VNet address space
   - **TerraformValidator**: Validates Terraform templates
   - Supports auto-fix for common subnet misconfigurations

### Key Design Patterns

- **Async/Await**: Core services use asyncio for concurrent API calls
- **Dashboard Integration**: Rich TUI dashboard for progress tracking during long operations
- **MCP Server**: Model Context Protocol server for AI agent integration
- **Migration System**: Database schema versioning and migrations in `migrations/`
- **Electron SPA**: Desktop GUI application with React frontend and Express backend

### Neo4j Graph Schema

- **Nodes**: Resource, Subscription, Tenant, ResourceGroup, User, ServicePrincipal, etc.
- **Relationships**: CONTAINS, USES_IDENTITY, CONNECTED_TO, DEPENDS_ON, etc.
- **Indexes**: On resource IDs for fast lookups
- **Constraints**: Ensure data integrity

### Testing Strategy

- **Unit Tests**: Mock Azure SDK responses
- **Integration Tests**: Use testcontainers for Neo4j
- **E2E Tests**: Full workflow testing with real containers
- **Coverage Target**: 40% minimum (per pyproject.toml)

### SPA/GUI Architecture

The Electron-based desktop GUI provides a full-featured interface for all CLI functionality:

**Key Directories:**
- `spa/main/`: Electron main process (app lifecycle, IPC, subprocess management)
- `spa/renderer/`: React frontend (UI components, context providers, hooks)
- `spa/backend/`: Express server (optional API layer)
- `spa/tests/`: Comprehensive test suites (unit, integration, e2e)

**Core Features:**
- **Tabbed Interface**: Scan, Generate Spec, Generate IaC, Create Tenant, Visualize, Agent Mode, Threat Model, Config
- **Real-time Communication**: WebSocket for live logs and progress updates
- **Process Management**: Spawns and manages CLI subprocesses
- **Cross-Platform**: Windows, macOS, and Linux support

## Common Development Tasks

### Adding a New Relationship Rule
1. Create new file in `src/relationship_rules/`
2. Inherit from `RelationshipRule` base class
3. Implement `create_relationships()` method
4. Register in `__init__.py`

### Adding a New CLI Command
1. Add command handler in `src/cli_commands.py`
2. Register command in `scripts/cli.py`
3. Add tests in `tests/test_cli_*.py`

### Modifying IaC Generation
1. Update traverser logic in `src/iac/traverser.py`
2. Modify emitter in `src/iac/emitters/`
3. Test with `--dry-run` flag first

### Working with the SPA/GUI
1. **Start Development Environment**:
   ```bash
   cd spa && npm run dev
   ```
2. **Add New UI Components**: Place in `spa/renderer/src/components/`
3. **Add New Tabs**: Create in `spa/renderer/src/components/tabs/`
4. **Test Changes**:
   ```bash
   cd spa && npm test
   npm run test:e2e
   ```
5. **Build for Production**:
   ```bash
   cd spa && npm run build && npm run package
   ```

## Environment Configuration

Required environment variables (see .env.example):
- `AZURE_TENANT_ID`
- `AZURE_CLIENT_ID`
- `AZURE_CLIENT_SECRET`
- `NEO4J_PASSWORD` (required)
- `NEO4J_PORT` (required, configures the Neo4j port)
- `NEO4J_URI` (optional, defaults to bolt://localhost:${NEO4J_PORT})
- `OPENAI_API_KEY` (for LLM descriptions)

Optional debugging command-line flag:
- `--debug` (enables verbose debug output including environment variables)

## CI/CD Pipeline

GitHub Actions workflow (`ci.yml`):
1. Sets up Neo4j service container
2. Installs dependencies with uv
3. Runs database migrations
4. Executes test suite with artifacts
5. Uploads test results

Check CI status: `./scripts/check_ci_status.sh`

### Helpful Scripts

- **CI Status Check**: Use the script `@scripts/check_ci_status.sh` to efficiently check CI status

## CLI Dashboard Shortcuts

When using the CLI dashboard (during `atg scan` operations):
- **Press 'x'** to exit the dashboard
- **Press 'g'** to launch the GUI (SPA) - provides quick access to the desktop interface
- **Press 'i', 'd', 'w'** to change log levels (INFO, DEBUG, WARNING)

## Project Memories

- The CI takes almost 20 minutes to complete. Just run the script and wait for it.

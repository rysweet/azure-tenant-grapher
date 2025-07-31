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
uv run atg build --tenant-id <TENANT_ID>
uv run atg generate-spec
uv run atg generate-iac --tenant-id <TENANT_ID> --format terraform
uv run atg create-tenant --spec path/to/spec.md
uv run atg visualize
uv run atg agent-mode
uv run atg threat-model
uv run atg doctor  # Check and install CLI dependencies
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

### Key Design Patterns

- **Async/Await**: Core services use asyncio for concurrent API calls
- **Dashboard Integration**: Rich TUI dashboard for progress tracking during long operations
- **MCP Server**: Model Context Protocol server for AI agent integration
- **Migration System**: Database schema versioning and migrations in `migrations/`

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

## Environment Configuration

Required environment variables (see .env.example):
- `AZURE_TENANT_ID`
- `AZURE_CLIENT_ID`
- `AZURE_CLIENT_SECRET`
- `NEO4J_PASSWORD`
- `NEO4J_URI` (default: bolt://localhost:7687)
- `OPENAI_API_KEY` (for LLM descriptions)

## CI/CD Pipeline

GitHub Actions workflow (`ci.yml`):
1. Sets up Neo4j service container
2. Installs dependencies with uv
3. Runs database migrations
4. Executes test suite with artifacts
5. Uploads test results

### Helpful Scripts

- **CI Status Check**: Use the script `@scripts/check_ci_status.sh` to efficiently check CI status
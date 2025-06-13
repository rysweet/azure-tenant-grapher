# Azure Tenant Resource Grapher

A Python application that exhaustively walks Azure tenant resources and builds a Neo4j graph database representation of those resources and their relationships.

## Quick Start

### 1. Setup Environment
```bash
# Install dependencies using uv (recommended)
uv sync

# Create .env file with defaults (optional)
cp .env.example .env
# Edit .env with your Azure tenant ID if desired

# Authenticate with Azure
az login
```

### 2. Run the Application (Recommended)

Use the enhanced CLI wrapper:
```bash
uv run python scripts/cli.py --tenant-id <your-tenant-id>
```

- This will automatically manage the Neo4j container and build the graph.
- For all CLI options:
```bash
uv run python scripts/cli.py --help
```

### 3. Access Neo4j Browser
- URL: http://localhost:7475
- Username: `neo4j`
- Password: `azure-grapher-2024` (or your custom password)

## Usage Examples

```bash
# Basic usage with automatic container management
uv run python scripts/cli.py --tenant-id <your-tenant-id>

# Start Neo4j container only
uv run python scripts/cli.py --tenant-id dummy --container-only

# Use existing Neo4j instance (skip container management)
uv run python scripts/cli.py --tenant-id <your-tenant-id> --no-container

# Generate 3D visualization after building
duv run python scripts/cli.py --tenant-id <your-tenant-id> --visualize

# Generate visualization only (from existing graph data)
uv run python scripts/cli.py --tenant-id <your-tenant-id> --visualize-only
```

# Generate anonymized Markdown specification of your tenant
uv run python scripts/cli.py generate-spec --tenant-id <your-tenant-id> [--limit N]

## VS Code Tasks

Use Ctrl+Shift+P and search for "Tasks: Run Task" to access:
- **Install Dependencies**: Installs Python packages using uv
- **Start Neo4j Container**: Starts the Neo4j Docker container using uv
- **Stop Neo4j Container**: Stops the Neo4j Docker container
- **Run Azure Tenant Grapher**: Runs the full application with uv (prompts for tenant ID)
- **Generate 3D Visualization Only**: Generates visualization from existing graph data

## Shell Scripts

**Unix/macOS/Linux (Bash)**
```bash
./run-grapher.sh --tenant-id "your-tenant-id-here"
```

**Windows (PowerShell)**
```powershell
./run-grapher.ps1 -TenantId "your-tenant-id-here"
```

## Development and Testing

- Run all tests:
```bash
uv run python run_tests.py
```
- Run tests with coverage:
```bash
uv run python run_tests.py -c
```
- Lint and type check:
```bash
uv run ruff check src/ tests/
uv run mypy --strict src/
```

## Configuration

- Copy `.env.example` to `.env` and edit as needed.
- All environment variables have sensible defaults.

## Troubleshooting

- See the bottom of this README for Docker, Neo4j, and Azure troubleshooting tips.

---

# Azure Tenant Resource Grapher

A Python application that exhaustively walks Azure tenant resources and builds a Neo4j graph database representation of those resources and their relationships.

## Project Structure

```
azure-tenant-grapher/
├── src/                           # Main application source code
│   ├── __init__.py               # Package initialization with conditional imports
│   ├── azure_tenant_grapher.py  # Main application class
│   ├── config_manager.py        # Configuration management
│   ├── resource_processor.py    # Azure resource processing
│   ├── llm_descriptions.py      # AI-powered resource descriptions
│   ├── container_manager.py     # Neo4j container management
│   └── graph_visualizer.py      # Graph visualization and export
├── tests/                        # Comprehensive test suite
│   ├── conftest.py              # Test fixtures and configuration
│   ├── test_config_manager.py   # Configuration tests
│   ├── test_resource_processor.py # Resource processing tests
│   ├── test_azure_tenant_grapher.py # Main application tests
│   ├── test_container_manager.py # Container management tests
│   ├── test_llm_descriptions.py # LLM integration tests
│   └── test_graph_visualizer.py # Visualization tests
├── scripts/                      # Utility scripts
│   ├── cli.py                   # Enhanced CLI wrapper
│   ├── demo_enhanced_features.py # Feature demonstration
│   ├── check_progress.py       # Progress checking utility
│   └── test_modular_structure.py # Structure validation
├── run_tests.py                  # Test runner with coverage
├── pyproject.toml               # Project configuration
├── requirements.txt             # Dependencies
├── docker-compose.yml           # Neo4j container setup
└── README.md                    # This file
```

## Features

- **Azure Resource Discovery**: Enumerate all resources across all subscriptions in an Azure tenant
- **Neo4j Graph Database**: Build a comprehensive graph of Azure resources and their relationships
- **Resource Details**: Capture detailed configuration information for each resource
- **Relationship Mapping**: Identify and map dependencies and enriched relationships between Azure resources, including:
    - Network: VM uses subnet, subnet secured by NSG
    - Identity: Managed identity and Key Vault policy relationships
    - Monitoring: Diagnostic settings to Log Analytics
    - ARM dependencies: Resource-level dependsOn edges
- **3D Interactive Visualization**: Generate interactive 3D visualizations of the resource graph using 3d-force-graph
- **Filterable Graph Views**: Filter nodes and relationships by type, search functionality
- **Node Details**: Click on nodes to view detailed resource information and metadata
- **Modular Architecture**: Well-structured codebase with comprehensive test coverage
- **AI Integration**: Optional AI-powered resource descriptions using Azure OpenAI
- **Tenant Markdown Specification**: Generate anonymized, portable Markdown documentation of your Azure tenant.

## Prerequisites

- Python 3.8+
- [uv](https://docs.astral.sh/uv/) (for dependency management and virtual environment)
- Docker and Docker Compose (for Neo4j container)
- Azure CLI (for authentication)
- Azure tenant with appropriate permissions

## Quick Start

### 1. Setup Environment
```bash
# Install dependencies using uv
uv sync

# Or install with pip if uv is not available
pip install -r requirements.txt

# Create .env file with defaults (optional - the application has sensible defaults)
cp .env.example .env
# Edit .env with your Azure tenant ID if desired

# Configure Azure credentials
az login
```

### 2. Start the Application
The application can automatically manage a Neo4j Docker container for you.

**Option A: Using the main entry point (recommended)**
```bash
python main.py --tenant-id your-tenant-id-here
```

**Option B: Using the module directly**
```bash
python -m src.azure_tenant_grapher --tenant-id your-tenant-id-here
```

**Option C: Start container manually**
```bash
# Start Neo4j container only
python main.py --tenant-id dummy --container-only

# Or use Docker Compose directly
docker-compose up -d neo4j
```

**Option C: Use existing Neo4j instance**
```bash
# Skip container management if you have Neo4j running elsewhere
uv run python azure_tenant_grapher.py --tenant-id your-tenant-id-here --no-container
```

### 3. Access Neo4j Browser
Once Neo4j is running, you can access the browser interface at:
- URL: http://localhost:7475
- Username: `neo4j`
- Password: `azure-grapher-2024` (or your custom password)

## Usage

### Command Line Options

```bash
# Basic usage with automatic container management
uv run python azure_tenant_grapher.py --tenant-id <your-tenant-id>

# Start Neo4j container only (useful for setup)
uv run python azure_tenant_grapher.py --tenant-id dummy --container-only

# Use existing Neo4j instance (skip container management)
uv run python azure_tenant_grapher.py --tenant-id <your-tenant-id> --no-container

# Custom Neo4j connection settings
uv run python azure_tenant_grapher.py \
  --tenant-id <your-tenant-id> \
  --neo4j-uri bolt://localhost:7688 \
  --neo4j-user neo4j \
  --neo4j-password your-password
```

### VS Code Tasks

Use Ctrl+Shift+P and search for "Tasks: Run Task" to access:
- **Install Dependencies**: Installs Python packages using uv
- **Start Neo4j Container**: Starts the Neo4j Docker container using uv
- **Stop Neo4j Container**: Stops the Neo4j Docker container
- **Run Azure Tenant Grapher**: Runs the full application with uv (prompts for tenant ID)

### Shell Scripts

**Unix/macOS/Linux (Bash)**
```bash
# Start container and run grapher
./run-grapher.sh --tenant-id "your-tenant-id-here"

# Start container and run grapher with 3D visualization
./run-grapher.sh --tenant-id "your-tenant-id-here" --visualize

# Generate visualization only (from existing graph data)
./run-grapher.sh --tenant-id "your-tenant-id-here" --visualize-only

# Start container only
./run-grapher.sh --tenant-id "dummy" --container-only

# Use existing Neo4j instance
./run-grapher.sh --tenant-id "your-tenant-id-here" --no-container

# Show help
./run-grapher.sh --help
```

**Windows (PowerShell)**

```powershell
# Start container and run grapher
.\run-grapher.ps1 -TenantId "your-tenant-id-here"

# Start container and run grapher with 3D visualization
.\run-grapher.ps1 -TenantId "your-tenant-id-here" -Visualize

# Generate visualization only (from existing graph data)
.\run-grapher.ps1 -TenantId "your-tenant-id-here" -VisualizeOnly

# Start container only
.\run-grapher.ps1 -TenantId "dummy" -ContainerOnly

# Use existing Neo4j instance
.\run-grapher.ps1 -TenantId "your-tenant-id-here" -NoContainer
```

## Development and Testing

This project includes a comprehensive test suite and follows best practices for Python development.

### Running Tests

**Quick test run:**
```bash
# Run all tests
python run_tests.py

# Run tests with coverage report
python run_tests.py -c

# Run specific test module
python -m pytest tests/test_config_manager.py -v

# Install test dependencies if needed
python run_tests.py --install-deps
```

**Advanced testing:**
```bash
# Run tests with verbose output and coverage
python -m pytest tests/ -v --cov=src --cov-report=html

# Run only unit tests (skip integration tests)
python -m pytest tests/ -m "not integration"

# Run tests in parallel (if pytest-xdist is installed)
python -m pytest tests/ -n auto
```

### Test Structure

The test suite includes:
- **Unit Tests**: Individual module testing with mocks and fixtures
- **Integration Tests**: End-to-end testing scenarios
- **Configuration Tests**: Environment and configuration validation
- **Mock-based Tests**: Safe testing without external dependencies

### Code Quality

```bash
# Run linting (if configured)
python -m flake8 src/ tests/

# Format code (if black is installed)
python -m black src/ tests/

# Type checking (if mypy is installed)
python -m mypy src/
```

### Development Scripts

The `scripts/` directory contains helpful development utilities:

```bash
# Test the modular structure
python scripts/test_modular_structure.py

# Check progress of a running graph build
python scripts/check_progress.py

# Enhanced CLI with better error handling
python scripts/cli.py --help

# Demonstrate advanced features
python scripts/demo_enhanced_features.py
```

## Configuration

### Dependency Management

This project uses [uv](https://docs.astral.sh/uv/) for dependency management and virtual environment handling. Benefits include:

- **Fast**: uv is written in Rust and significantly faster than pip
- **Reliable**: Deterministic dependency resolution with lock files
- **Simple**: Single tool for virtual environments and dependency management

Key commands:
```bash
# Install dependencies (creates virtual environment automatically)
uv sync

# Run commands in the virtual environment
uv run python azure_tenant_grapher.py --help

# Add new dependencies
uv add package-name

# Add development dependencies
uv add --dev package-name

# Update dependencies
uv sync --upgrade
```

The `pyproject.toml` file contains all project configuration and dependencies. The `requirements.txt` file is maintained for compatibility but `uv` will use `pyproject.toml` as the source of truth.

### Environment Variables

The application uses environment variables for configuration. Copy `.env.example` to `.env` and customize:

```bash
# Azure Configuration
AZURE_TENANT_ID=your-tenant-id-here

# Neo4j Configuration (matches docker-compose.yml)
NEO4J_URI=bolt://localhost:7688
NEO4J_USER=neo4j
NEO4J_PASSWORD=azure-grapher-2024

# Logging Configuration
LOG_LEVEL=INFO
```

### Docker Compose Configuration

The `docker-compose.yml` file configures Neo4j with:
- **Ports**: 7475 (HTTP), 7688 (Bolt)
- **Authentication**: neo4j/azure-grapher-2024
- **Memory**: 2GB heap, 1GB page cache
- **Plugins**: APOC procedures enabled
- **Persistence**: Data persisted in Docker volumes

You can customize the container by editing `docker-compose.yml`.

## 3D Graph Visualization

The Azure Tenant Grapher includes an interactive 3D visualization feature powered by [3d-force-graph](https://github.com/vasturiano/3d-force-graph). This creates a web-based, interactive view of your Azure resource graph.

### Features

- **Interactive 3D Graph**: Navigate and explore your Azure resources in 3D space
- **Node Types**: Different colors and sizes for different Azure resource types
- **Relationships**: Visual representation of resource dependencies and containment
- **Filtering**: Filter by node types or relationship types using checkboxes
- **Search**: Real-time search to find specific resources
- **Node Details**: Click on any node to view detailed resource information
- **Legend**: Visual legend showing node types and colors
- **Auto-rotation**: Optional camera auto-rotation for presentation mode

### Usage

**Generate visualization after building the graph:**
```bash
uv run python azure_tenant_grapher.py --tenant-id your-tenant-id --visualize
```

**Generate visualization from existing graph data:**
```bash
uv run python azure_tenant_grapher.py --tenant-id your-tenant-id --visualize-only
```

**Specify custom output path:**
```bash
uv run python azure_tenant_grapher.py --tenant-id your-tenant-id --visualize --visualization-path my_graph.html
```

### Visualization Controls

- **Node Types Filter**: Check/uncheck node types to show/hide them
- **Relationship Types Filter**: Check/uncheck relationship types to show/hide them
- **Search Box**: Type to filter nodes by name, type, or properties
- **Reset Filters**: Button to clear all filters and show the complete graph
- **Node Interaction**: Click nodes to view detailed information
- **Camera Controls**: Mouse/trackpad to zoom, rotate, and pan the 3D view

### Supported Node Types

The visualization automatically detects and color-codes these Azure resource types:

- **Subscription** (Red): Azure subscriptions
- **ResourceGroup** (Blue): Resource groups
- **Resource** (Teal): Generic Azure resources
- **StorageAccount** (Yellow): Storage accounts
- **VirtualMachine** (Purple): Virtual machines
- **NetworkInterface** (Light Purple): Network interfaces
- **VirtualNetwork** (Green): Virtual networks
- **KeyVault** (Pink): Key vaults
- **SqlServer** (Orange): SQL servers
- **WebSite** (Dark Orange): App Service web sites

### Relationship Types

- **CONTAINS**: Subscription contains resource groups, resource groups contain resources
- **BELONGS_TO**: Resources belong to resource groups
- **CONNECTED_TO**: Network connections between resources
- **DEPENDS_ON**: Resource dependencies (from ARM dependsOn)
- **USES_SUBNET**: Virtual machine uses subnet
- **SECURED_BY**: Subnet secured by network security group
- **HAS_MANAGED_IDENTITY**: Resource has managed identity
- **POLICY_FOR**: Key Vault policy for managed identity
- **LOGS_TO**: Resource logs to Log Analytics Workspace
- **MANAGES**: Management relationships

## Architecture

The application consists of several key components:

1. **Azure Resource Walker**: Discovers and enumerates resources
2. **Graph Builder**: Creates nodes and relationships in Neo4j
3. **Configuration Manager**: Handles settings and credentials
4. **Resource Mappers**: Transform Azure resource data for graph storage

## Troubleshooting

### Docker Issues

**Error: "Docker is not available"**
- Ensure Docker Desktop is installed and running
- Download from: https://www.docker.com/products/docker-desktop
- On Windows, make sure Docker Desktop is started and the Docker daemon is running

**Error: "docker-compose command not found"**
- Docker Compose is included with Docker Desktop
- Alternatively, use `docker compose` (newer syntax) instead of `docker-compose`

### Neo4j Connection Issues

**Error: "Failed to connect to Neo4j"**
- Check if the Neo4j container is running: `docker ps`
- Verify the connection details in your `.env` file
- Try accessing Neo4j Browser at http://localhost:7475

### Azure Authentication Issues

**Error: "Azure authentication failed"**
- Run `az login` to authenticate with Azure CLI
- Ensure you have the correct permissions in the target tenant
- Verify the tenant ID is correct

### Permission Issues

**Error: "Access denied" when discovering resources**
- Ensure your Azure account has Reader permissions on subscriptions
- Some resources may require additional permissions to read configuration details

## Summary of Changes

This project has been updated to use `uv` for dependency management and to resolve port conflicts:

### Key Updates:

1. **uv Integration**: All Python commands now use `uv run` to ensure the correct virtual environment
2. **Port Changes**: Neo4j now runs on ports 7475 (HTTP) and 7688 (Bolt) to avoid conflicts
3. **No Password Prompts**: Default password is set to `azure-grapher-2024` and no longer prompts on startup
4. **Updated Scripts**: All shell scripts, PowerShell scripts, and VS Code tasks use `uv run`
5. **Environment Defaults**: Sensible defaults are provided so `.env` file is optional

### Migration from pip to uv:

If you previously used `pip`, simply run:
```bash
uv sync
```

All dependencies from `requirements.txt` are now managed in `pyproject.toml` with `uv`.

### Testing the Setup:

```bash
# Test the help (should not prompt for password)
uv run python azure_tenant_grapher.py --help

# Start Neo4j container only
uv run python azure_tenant_grapher.py --tenant-id dummy --container-only

# Access Neo4j Browser at http://localhost:7475 with neo4j/azure-grapher-2024
```

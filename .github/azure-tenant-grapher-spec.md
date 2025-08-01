# Azure Tenant Grapher - Complete Project Specification

## Project Overview

**Azure Tenant Grapher** is a Python application that exhaustively walks Azure tenant resources and builds a Neo4j graph database representation of those resources and their relationships. The project features modular architecture, comprehensive testing, interactive Rich CLI dashboard, 3D visualization capabilities, Infrastructure-as-Code generation (Terraform, ARM, Bicep), anonymized tenant specifications, automated CLI tool management, and optional AI-powered resource descriptions. A complementary .NET implementation is also available for enterprise scenarios.

## Core Architecture

### 1. Project Structure
```
azure-tenant-grapher/
├── src/                           # Main application source code
│   ├── __init__.py               # Package initialization with conditional imports
│   ├── azure_tenant_grapher.py  # Main application class
│   ├── config_manager.py        # Configuration management with dataclasses
│   ├── resource_processor.py    # Enhanced Azure resource processing
│   ├── llm_descriptions.py      # AI-powered resource descriptions
│   ├── container_manager.py     # Neo4j container management
│   ├── graph_visualizer.py      # Graph visualization and export
│   ├── tenant_spec_generator.py # Anonymized specification generation
│   ├── cli_commands.py          # CLI command handlers
│   ├── cli_dashboard_manager.py # Rich dashboard management
│   ├── rich_dashboard.py        # Interactive Rich dashboard
│   ├── exceptions.py            # Custom exception hierarchy
│   ├── services/                # Service layer
│   │   └── azure_discovery_service.py # Azure API abstraction
│   ├── utils/                   # Utility modules
│   │   ├── session_manager.py  # Session management utilities
│   │   └── cli_installer.py    # CLI tool installation and validation
│   ├── iac/                     # Infrastructure-as-Code generation
│   │   ├── __init__.py          # IaC package initialization
│   │   ├── cli_handler.py       # IaC CLI command coordination
│   │   ├── engine.py            # Transformation engine with rules support
│   │   ├── traverser.py         # Graph traversal and resource extraction
│   │   ├── subset.py            # Resource subset filtering
│   │   └── emitters/            # IaC format emitters
│   │       ├── __init__.py      # Emitter registry
│   │       ├── base.py          # Base emitter interface
│   │       ├── terraform_emitter.py # Terraform .tf generation
│   │       ├── arm_emitter.py   # ARM JSON template generation
│   │       └── bicep_emitter.py # Bicep template generation
│   ├── visualization/           # Visualization components
│   │   ├── html_template_builder.py # Main template coordinator
│   │   ├── css_style_builder.py     # CSS generation
│   │   ├── javascript_builder.py    # JavaScript generation
│   │   └── html_structure_builder.py # HTML structure
│   └── cli_dashboard_widgets/   # Dashboard UI components
│       └── scrollable_log_widget.py # Scrollable log display
├── tests/                        # Comprehensive test suite
│   ├── conftest.py              # Test fixtures and configuration
│   ├── test_*.py                # Module-specific test files (200+ tests)
│   └── iac/                     # Infrastructure-as-Code test suite
│       ├── test_engine.py       # Transformation engine tests
│       ├── test_traverser.py    # Graph traversal tests
│       ├── test_*_emitter.py    # Format-specific emitter tests
│       ├── test_*_validate.py   # Template validation tests
│       └── test_cli_*.py        # CLI integration tests
├── scripts/                      # Utility scripts
│   ├── cli.py                   # Enhanced CLI wrapper with async support
│   ├── demo_enhanced_features.py # Feature demonstration
│   ├── check_progress.py       # Progress checking utility
│   └── test_modular_structure.py # Structure validation
├── dotnet/                       # .NET implementation
│   ├── AzureTenantGrapher.sln   # Solution file
│   ├── src/AzureTenantGrapher/  # Main .NET application
│   └── tests/                   # .NET test suite
├── run_tests.py                  # Test runner with coverage
├── pyproject.toml               # Project configuration with UV support
├── requirements.txt             # Dependencies (maintained for compatibility)
├── docker-compose.yml           # Neo4j container setup
├── uv.lock                      # UV dependency lock file
└── README.md                    # Documentation
```

### 2. Main Application Components

#### AzureTenantGrapher (src/azure_tenant_grapher.py)
- **Purpose**: Main orchestration class for resource discovery and graph building
- **Key Methods**:
  - `__init__(config)`: Initialize with configuration object
  - `connect_to_neo4j()`: Establish Neo4j connection with optional container management
  - `discover_subscriptions()`: Enumerate all subscriptions in tenant
  - `discover_resources_in_subscription(subscription_id)`: Find all resources in subscription
  - `build_graph()`: Main workflow method that orchestrates the entire process
  - `process_resources_with_enhanced_handling(resources)`: Process resources using modular processor
  - `generate_tenant_specification()`: Generate AI-powered tenant documentation
  - `close_neo4j_connection()`: Cleanup database connections

#### Configuration Manager (src/config_manager.py)
- **Purpose**: Centralized configuration management with validation using dataclasses
- **Classes**:
  - `AzureTenantGrapherConfig`: Main configuration container
  - `Neo4jConfig`: Neo4j connection settings
  - `ProcessingConfig`: Resource processing settings with auto-start container support
  - `LoggingConfig`: Logging configuration with unique temp file generation
  - `AzureOpenAIConfig`: AI integration settings
  - `SpecificationConfig`: Tenant specification generation settings
- **Functions**:
  - `create_config_from_env(tenant_id, resource_limit)`: Factory function for configuration
  - `create_neo4j_config_from_env()`: Neo4j-only configuration for visualization/spec commands
  - `setup_logging(config)`: Configure logging system with colorlog and file handlers

#### Resource Processor (src/resource_processor.py)
- **Purpose**: Enhanced modular resource processing with eager thread pool and statistics tracking
- **Classes**:
  - `ProcessingStats`: Statistics tracking with success rates and progress percentages
  - `ResourceState`: Neo4j query operations for resource state and LLM description checking
  - `DatabaseOperations`: Neo4j CRUD operations with serialization support
  - `ResourceProcessor`: Main processing orchestrator with eager thread pool implementation
- **Features**:
  - Eager thread pool processing for improved performance
  - Async/await processing with configurable batch sizes
  - LLM integration with throttling and adaptive pool sizing
  - Comprehensive error handling and statistics
  - Resource deduplication and state management
  - Enriched relationship creation (network, identity, monitoring, ARM dependencies)

#### Container Manager (src/container_manager.py)
- **Purpose**: Docker/Neo4j container lifecycle management
- **Class**: `Neo4jContainerManager`
- **Methods**:
  - `is_docker_available()`: Check Docker daemon availability
  - `is_compose_available()`: Check Docker Compose availability
  - `setup_neo4j()`: Full Neo4j container setup workflow
  - `start_neo4j_container()`: Start Neo4j container
  - `stop_neo4j_container()`: Stop Neo4j container
  - `get_container_logs()`: Retrieve container logs for debugging

#### Graph Visualizer (src/graph_visualizer.py)
- **Purpose**: 3D interactive visualization and graph export with modular template builder
- **Class**: `GraphVisualizer`
- **Features**:
  - 3D force-directed graph using 3d-force-graph library
  - Interactive filtering by node/relationship types
  - Real-time search functionality
  - Node detail panels with resource metadata
  - Export capabilities (HTML, GEXF)
  - Auto-rotation and camera controls
  - Tenant specification link integration
  - Hierarchical edge support (Resource→Subscription→Tenant)
  - Component-based HTML template generation

#### LLM Descriptions (src/llm_descriptions.py)
- **Purpose**: AI-powered resource descriptions using Azure OpenAI
- **Class**: `AzureLLMDescriptionGenerator`
- **Features**:
  - Intelligent resource description generation
  - ResourceGroup and Tag summary generation based on contained/tagged resources
  - Tenant specification document creation
  - Configurable AI models and prompts
  - Rate limiting and error handling
  - Architectural pattern recognition for ResourceGroups
  - Organizational purpose inference for Tags

#### Tenant Specification Generator (src/tenant_spec_generator.py)
- **Purpose**: Generate anonymized, portable Markdown specifications
- **Classes**:
  - `ResourceAnonymizer`: Consistent anonymization with semantic placeholders
  - `TenantSpecificationGenerator`: Main specification generation coordinator
- **Features**:
  - Configurable resource limits and anonymization seeds
  - Semantic placeholder generation (type-semantic-hash format)
  - Category-based resource grouping
  - AI summary integration with anonymization
  - Configurable output directories and template styles

#### CLI Dashboard Manager (src/cli_dashboard_manager.py)
- **Purpose**: Rich dashboard functionality and build task coordination
- **Class**: `CLIDashboardManager`
- **Features**:
  - Async build task coordination
  - Multiple keypress handling modes (normal, queue-based, file-based)
  - Dashboard exit management
  - Post-processing coordination (spec generation, visualization)

#### Rich Dashboard (src/rich_dashboard.py)
- **Purpose**: Interactive CLI dashboard with live updates
- **Class**: `RichDashboard`
- **Features**:
  - Live progress monitoring with threaded updates
  - Scrollable log display with color coding
  - Interactive log level adjustment (i/d/w keys)
  - Exit handling ('x' key)
  - Configuration panel display
  - File logging with timestamped files

#### Azure Discovery Service (src/services/azure_discovery_service.py)
- **Purpose**: Focused Azure API interaction layer
- **Class**: `AzureDiscoveryService`
- **Features**:
  - Subscription and resource discovery
  - Authentication fallback with Azure CLI
  - Comprehensive error handling with custom exceptions
  - Credential management and caching

#### Visualization Components (src/visualization/)
- **Purpose**: Modular HTML template generation
- **Classes**:
  - `HtmlTemplateBuilder`: Main coordinator for template generation
  - `CssStyleBuilder`: CSS style generation
  - `JavaScriptBuilder`: JavaScript functionality generation
  - `HtmlStructureBuilder`: HTML structure generation
- **Features**:
  - Component-based architecture
  - Theme support and customization
  - Template validation and error handling

#### Infrastructure-as-Code Components (src/iac/)
- **Purpose**: Graph-to-IaC transformation with modular emitter architecture
- **Classes**:
  - `GraphTraverser`: Neo4j graph traversal and resource extraction
  - `TransformationEngine`: Resource transformation with YAML rules support
  - `SubsetFilter`: Flexible filtering system for resource selection
  - `TerraformEmitter`: Terraform .tf file generation with azurerm provider
  - `ArmEmitter`: Azure Resource Manager JSON template generation
  - `BicepEmitter`: Azure Bicep template generation with deployment scripts
  - `CLIHandler`: Command-line interface coordination for IaC generation
- **Features**:
  - Modular emitter architecture for extensibility
  - YAML-based transformation rules for name, region, and tag modifications
  - Subset filtering with type, ID, and label-based selection
  - Dependency preservation and relationship mapping
  - Template validation and syntax checking
  - Automated deployment script generation

#### CLI Tool Management (src/utils/)
- **Purpose**: Automated CLI tool installation and validation system
- **Classes**:
  - `CLIInstaller`: Cross-platform tool installation coordinator
  - Tool registry with platform-specific installation commands
- **Features**:
  - Automatic tool detection and installation
  - Platform-specific package manager integration
  - Interactive installation prompts and validation
  - Doctor command for comprehensive system checking

## Key Features

### 1. Azure Resource Discovery
- **Scope**: All resources across all subscriptions in Azure tenant
- **Authentication**: Azure DefaultAzureCredential (supports multiple auth methods)
- **Resource Types**: All Azure resource types supported by Azure Resource Manager
- **Metadata Capture**:
  - Resource ID, name, type, location
  - Resource group membership
  - Tags and custom properties
  - SKU information where available
  - Resource-specific configuration details

### 2. Neo4j Graph Database Integration
- **Database**: Neo4j 5.15+ Community Edition
- **Connection**: Bolt protocol (default port 7688)
- **Authentication**: Configurable username/password
- **Container Management**: Automatic Docker container lifecycle
- **Graph Schema**:
  - **Nodes**: Subscription, ResourceGroup, Resource (with subtypes)
  - **Relationships**: CONTAINS, BELONGS_TO, CONNECTED_TO, DEPENDS_ON, MANAGES
  - **Properties**: All Azure resource metadata as node properties

### 3. Interactive 3D Visualization
- **Technology**: 3d-force-graph JavaScript library
- **Features**:
  - Force-directed 3D layout
  - Color-coded node types (10+ Azure resource types)
  - Interactive filtering and search
  - Node click for detailed information
  - Relationship visualization with directional particles
  - Auto-rotation and manual camera controls
- **Export Formats**: HTML (self-contained), GEXF for Gephi

### 4. AI Integration (Optional)
- **Provider**: Azure OpenAI Service
- **Models**: GPT-4, GPT-3.5-turbo (configurable)
- **Features**:
  - Intelligent resource descriptions
  - Tenant architecture documentation
  - Resource relationship analysis
  - Best practices recommendations

### 5. Rich CLI Dashboard Interface
- **Technology**: Rich library with Live rendering
- **Features**:
  - Interactive dashboard with real-time progress monitoring
  - Scrollable log display with color-coded messages
  - Dynamic log level adjustment via keypresses (i/d/w)
  - Exit capability ('x' key) with graceful shutdown
  - Configuration panel showing current settings
  - LLM thread monitoring and in-flight tracking
  - File logging with unique timestamped filenames

### 6. Tenant Specification Generation
- **Technology**: Markdown generation with resource anonymization
- **Features**:
  - Anonymized resource and relationship documentation
  - Semantic placeholder generation (type-semantic-hash format)
  - Configurable resource limits and output directories
  - AI summary integration with identifier removal
  - Category-based resource organization
  - Portable documentation suitable for compliance and architecture reviews

### 7. Infrastructure-as-Code Generation
- **Technology**: Graph-to-IaC transformation engine with modular emitters
- **Supported Formats**:
  - **Terraform**: .tf files with azurerm provider configuration
  - **Azure Resource Manager (ARM)**: .json template files with parameters
  - **Azure Bicep**: .bicep files with module structure and deployment scripts
- **Features**:
  - Complete tenant replication from graph data
  - Subset filtering for partial infrastructure recreation
  - YAML-based transformation rules for name, region, and tag modifications
  - Resource group retargeting and consolidation
  - Dependency preservation and relationship mapping
  - Ready-to-deploy templates with automated deployment scripts
  - Dry-run validation and template syntax checking
  - CLI tool auto-installation and validation

### 8. CLI Tool Management
- **Technology**: Automated tool detection and installation system
- **Features**:
  - Cross-platform CLI tool installation (Azure CLI, Terraform, Bicep)
  - Interactive installation prompts with platform-specific instructions
  - Tool registry with installation commands for Windows, macOS, and Linux
  - Version validation and compatibility checking
  - Doctor command for comprehensive system validation
  - Package manager integration (brew, choco, apt, yum)

### 9. Modular Architecture
- **Design Pattern**: Dependency injection with configuration-based initialization
- **Testing**: 150+ test cases with comprehensive coverage including IaC generation
- **Error Handling**: Custom exception hierarchy with detailed context
- **Async Support**: Full async/await implementation for Azure API calls
- **Batch Processing**: Eager thread pool processing with adaptive throttling
- **Service Layer**: Separated Azure API interactions for better testability
- **Extensibility**: Plugin-based emitter system for additional IaC formats

## Command Line Interface

### Main Entry Points
1. **scripts/cli.py**: Enhanced CLI with async support and comprehensive commands
2. **CLI commands via pyproject.toml**: `azure-tenant-grapher`, `azure-graph`, `atg` aliases
3. **Shell Scripts**: Unix (run-grapher.sh) and Windows (run-grapher.ps1) wrappers

### Available Commands
```bash
# Main commands
azure-tenant-grapher build       # Build graph with Rich dashboard
azure-tenant-grapher test        # Test mode with limited resources
azure-tenant-grapher visualize   # Generate 3D visualization from existing data (with ResourceGroup labels)
azure-tenant-grapher spec        # Generate AI-powered tenant specification
azure-tenant-grapher generate-spec # Generate anonymized Markdown specification
azure-tenant-grapher generate-iac  # Generate Infrastructure-as-Code templates
azure-tenant-grapher agent-mode  # Start AutoGen MCP agent mode for natural language queries
azure-tenant-grapher threat-model # Run Threat Modeling Agent workflow
azure-tenant-grapher mcp-server  # Start MCP server for agent integration
azure-tenant-grapher progress    # Check processing progress
azure-tenant-grapher config      # Show configuration template
azure-tenant-grapher container   # Container management subcommands
azure-tenant-grapher doctor      # Check and install required CLI tools
azure-tenant-grapher backup-db ./my-neo4j-backup.dump   # Backup Neo4j database to a local file
```

### CLI Arguments for Build Command
```bash
# Required
--tenant-id TEXT               # Azure tenant ID (or from AZURE_TENANT_ID env)

# Processing Options
--resource-limit INTEGER       # Max resources (for testing)
--max-llm-threads INTEGER     # Parallel LLM threads (default: 5)
--no-container                # Skip container auto-start
--generate-spec               # Generate tenant specification after build
--visualize                   # Generate visualization after build
--rebuild-edges               # Force re-evaluation of all relationships/edges

# Interface Options
--no-dashboard                # Disable Rich dashboard, use line-by-line logs
--log-level TEXT              # Logging level (DEBUG, INFO, WARNING, ERROR)

# Testing Options (for integration tests)
--test-keypress-queue         # Enable queue-based keypress simulation
--test-keypress-file PATH     # File-based keypress simulation
```

### CLI Arguments for Generate-IaC Command
```bash
# Format Selection
--format TEXT                  # Target IaC format: terraform, arm, bicep (default: terraform)

# Output Configuration
--output PATH                  # Output directory for generated templates
--dest-rg TEXT                # Target resource group name for deployment
--location TEXT               # Target Azure region for resources

# Filtering and Transformation
--subset-filter TEXT          # Subset filter (e.g., "types=Microsoft.Storage/*")
--resource-filters TEXT       # Comma-separated resource type filters
--rules-file PATH             # YAML transformation rules file

# Validation
--dry-run                     # Validate inputs without generating templates
```

### Usage Examples
```bash
# Basic usage with auto-container management
azure-tenant-grapher build --tenant-id your-tenant-id-here

# Generate with visualization and ResourceGroup labels
azure-tenant-grapher build --tenant-id your-tenant-id --visualize

# Build with relationship rebuilding
azure-tenant-grapher build --tenant-id your-tenant-id --rebuild-edges

# Test mode with limited resources
azure-tenant-grapher test --limit 50

# Start agent mode for natural language queries
azure-tenant-grapher agent-mode

# Ask a specific question
azure-tenant-grapher agent-mode --question "How many storage accounts are in the tenant?"

# Generate threat model report
azure-tenant-grapher threat-model --spec-path ./my-spec.md --summaries-path ./summaries.json

# Generate Bicep IaC for storage resources
azure-tenant-grapher generate-iac \
  --format bicep \
  --subset-filter "types=Microsoft.Storage/*" \
  --dest-rg "replica-rg" \
  --location "East US" \
  --output ./my-deployment

# Generate complete Terraform infrastructure
azure-tenant-grapher generate-iac \
  --format terraform \
  --rules-file ./transformation-rules.yaml \
  --output ./terraform-out

# Validate IaC generation without creating files
azure-tenant-grapher generate-iac --dry-run --format arm
```

## Configuration System

### Environment Variables
```bash
# Azure Configuration
AZURE_TENANT_ID=your-tenant-id-here

# Neo4j Configuration
NEO4J_URI=bolt://localhost:7688
NEO4J_USER=neo4j
NEO4J_PASSWORD=example-password

# Processing Configuration
PROCESSING_BATCH_SIZE=5
PROCESSING_MAX_RETRIES=3
PROCESSING_RETRY_DELAY=1.0
PROCESSING_PARALLEL=true
AUTO_START_CONTAINER=true

# Logging Configuration
LOG_LEVEL=INFO
LOG_FORMAT=%(log_color)s%(levelname)s:%(name)s:%(message)s
LOG_FILE=auto-generated-unique-temp-file

# LLM Integration (Optional)
AZURE_OPENAI_ENDPOINT=https://your-instance.openai.azure.com/...
AZURE_OPENAI_KEY=your-key-here
AZURE_OPENAI_API_VERSION=2025-04-16
AZURE_OPENAI_MODEL_CHAT=gpt-4
AZURE_OPENAI_MODEL_REASONING=gpt-4

# Specification Generation
AZTG_SPEC_OUTPUT_DIR=.
AZTG_SPEC_INCLUDE_AI=true
AZTG_SPEC_INCLUDE_CONFIG=true
AZTG_SPEC_ANONYMIZATION_SEED=optional-seed
AZTG_SPEC_TEMPLATE_STYLE=comprehensive
```

### Configuration Classes
- **Validation**: Full configuration validation with descriptive error messages
- **Defaults**: Sensible defaults for all optional settings
- **Environment Override**: Environment variables override defaults
- **Logging**: Configuration summary logging for debugging

## Development Environment

### Dependencies Management
- **Tool**: UV (Astral's fast Python package manager)
- **Configuration**: pyproject.toml with dependency specifications and CLI scripts
- **Virtual Environment**: Automatic virtual environment management
- **Lock File**: uv.lock for reproducible builds
- **CLI Installation**: Editable install creates `azure-tenant-grapher`, `azure-graph`, `atg` commands

### Code Quality Tools
- **Formatting**: Black (88 character line length)
- **Linting**: Ruff (modern Python linter) with comprehensive rule set
- **Type Checking**: Pyright with strict configuration
- **Security**: Bandit for security vulnerability scanning
- **Pre-commit**: Automated code quality checks
- **Test Coverage**: Pytest-cov with HTML reporting

### Testing Framework
- **Framework**: Pytest with async support and comprehensive test suite
- **Coverage**: 200+ tests with extensive coverage including CLI, dashboard, and IaC generation
- **Mocking**: Comprehensive mocks for Azure SDK, Neo4j, and external dependencies
- **Fixtures**: Reusable test fixtures in conftest.py for graph data and IaC testing
- **Markers**: Unit, integration, slow, timeout, and IaC-specific test markers
- **Async Testing**: Full async test support with pytest-asyncio
- **IaC Testing**: Template validation, emitter testing, and CLI integration tests
- **Tool Testing**: CLI installer validation and cross-platform compatibility tests

## Docker Configuration

### Neo4j Container (docker-compose.yml)
```yaml
services:
  neo4j:
    image: neo4j:5.15-community
    ports:
      - "7475:7474"  # HTTP Browser
      - "7688:7687"  # Bolt Protocol
    environment:
      - NEO4J_AUTH=neo4j/example-password
      - NEO4J_PLUGINS=["apoc"]
      - NEO4J_dbms_memory_heap_max__size=2G
      - NEO4J_dbms_memory_pagecache_size=1G
    volumes:
      - neo4j_data:/data
      - neo4j_logs:/logs
```

### Container Features
- **Automatic Startup**: Container auto-start with application
- **Health Checks**: Built-in health monitoring
- **APOC Plugins**: Advanced procedures and functions enabled
- **Performance Tuning**: Optimized memory settings
- **Data Persistence**: Volume-mounted data directory

## Graph Schema Design

### Node Types
- **Subscription**: Azure subscription with display name, state, tenant ID
- **ResourceGroup**: Resource grouping container with location metadata
- **Resource**: Base resource type with common properties
- **Specialized Resources**: VirtualMachine, StorageAccount, VirtualNetwork, etc.

- **Tag**: Tag node with key/value
  - **Region**: Region node with name/code
  - **User/ServicePrincipal**: Identity nodes
  - **ManagedIdentity**: Managed identity node
  - **IdentityGroup**: AAD group node
  - **RoleDefinition**: Role definition node
- **TAGGED_WITH**: Resource is tagged with a Tag node (Resource→Tag)
  - **LOCATED_IN**: Resource is located in a Region node (Resource→Region)
  - **CREATED_BY**: Resource was created by a User or Service Principal (Resource→User/ServicePrincipal)
  - **USES_IDENTITY**: Resource uses a ManagedIdentity (Resource→ManagedIdentity)
  - **HAS_ROLE**: Identity has a RoleDefinition (Identity→RoleDefinition)
  - **ASSIGNED_TO**: RoleAssignment assigned to Identity (RoleAssignment→Identity)
  - **INHERITS_TAG**: ResourceGroup/Subscription inherits a Tag (ResourceGroup/Subscription→Tag)
  - **STORES_SECRET**: KeyVault stores a KeyVaultSecret (KeyVault→KeyVaultSecret)
  - **SENDS_DIAG_TO**: Resource sends diagnostics to DiagnosticSetting (Resource→DiagnosticSetting)
  - **CONNECTED_TO_PE**: Resource connected to PrivateEndpoint (Resource↔PrivateEndpoint)
  - **RoleAssignment**: Role assignment node
  - **KeyVaultSecret**: KeyVault secret node
  - **DiagnosticSetting**: Diagnostic setting node
  - **PrivateEndpoint**: Private endpoint node
### Relationship Types
- **CONTAINS**: Hierarchical containment (Subscription → ResourceGroup → Resource)
- **BELONGS_TO**: Membership relationships
- **CONNECTED_TO**: Network connectivity relationships
- **DEPENDS_ON**: Resource dependencies
- **MANAGES**: Management relationships

### Properties Schema
- **Common Properties**: id, name, type, location, updated_at, processing_status
- **Azure Metadata**: subscription_id, resource_group, tags, sku
- **AI Enhancements**: llm_description, generated_at
- **Processing Metadata**: processing_status, error_details

## Error Handling Strategy

### Levels of Error Handling
1. **Configuration Errors**: Validation and clear error messages at startup
2. **Authentication Errors**: Azure credential and permission validation
3. **Network Errors**: Retry logic for transient Azure API failures
4. **Database Errors**: Neo4j connection and query error handling
5. **Processing Errors**: Individual resource processing error isolation

### Logging Strategy
- **Structured Logging**: Consistent log format with context
- **Log Levels**: DEBUG, INFO, WARNING, ERROR with appropriate usage
- **Progress Tracking**: Visual progress indicators for long-running operations
- **Error Context**: Detailed error context for debugging

## Performance Characteristics

### Scalability
- **Eager Thread Pool**: Enhanced parallel processing with adaptive throttling
- **Batch Processing**: Configurable parallel processing (default: 5 concurrent LLM threads)
- **Memory Management**: Streaming processing for large resource sets
- **Rate Limiting**: Respectful Azure API usage with retry logic and backoff
- **Database Optimization**: Efficient Neo4j queries with MERGE semantics and indexing

### Resource Requirements
- **Memory**: ~512MB base + ~1MB per 1000 resources + Rich dashboard overhead
- **Storage**: Neo4j database grows ~1KB per resource + relationships + logs
- **Network**: Minimal - only Azure API calls and Neo4j connections
- **CPU**: Moderate during processing, minimal during visualization, low during dashboard

## Security Considerations

### Authentication
- **Azure**: DefaultAzureCredential supporting multiple auth methods
- **Neo4j**: Username/password authentication with configurable credentials
- **Secrets**: Environment variable management, no hardcoded credentials

### Permissions Required
- **Azure**: Reader role on subscriptions and resources
- **Optional**: Additional permissions for detailed resource configuration
- **Principle of Least Privilege**: Minimal permissions for operation

### Data Security
- **Local Processing**: All data processing happens locally
- **No External Services**: Optional AI features use configured Azure OpenAI only
- **Data Encryption**: Neo4j supports encryption at rest and in transit

## Extensibility Points

### Custom Resource Processors
- **Interface**: ResourceProcessor base class for custom implementations
- **Plugins**: Modular design supports additional resource type handlers
- **Custom Properties**: Extensible property extraction for specific resource types

### Custom Visualizations
- **Export Formats**: GEXF export for external visualization tools
- **Custom Templates**: HTML template customization for branding
- **Additional Libraries**: Support for other graph visualization libraries

### Infrastructure-as-Code Extensions
- **Custom Emitters**: Base emitter interface for additional IaC formats
- **Transformation Rules**: Extensible YAML-based rule system for custom transformations
- **Template Validation**: Pluggable validation system for format-specific checks
- **Deployment Integration**: Custom deployment script generation for different platforms

### AI Integration Extensions
- **Custom Models**: Support for different AI models and providers
- **Custom Prompts**: Configurable prompt templates
- **Analysis Workflows**: Custom AI-powered analysis workflows

### CLI Tool Extensions
- **Tool Registry**: Extensible registry for additional CLI tools
- **Installation Handlers**: Custom installation logic for new tools
- **Platform Support**: Cross-platform installation strategy extensions

## Deployment Scenarios

### Development Environment
- **Local Docker**: Neo4j container on development machine
- **Hot Reload**: Rapid development with uv and pre-commit hooks
- **Test Coverage**: Comprehensive test suite for safe refactoring

### Production Environment
- **Hosted Neo4j**: Enterprise Neo4j clusters
- **Azure Container Instances**: Scheduled processing jobs
- **CI/CD Integration**: GitHub Actions, Azure DevOps pipelines

### Enterprise Features
- **Multi-tenant**: Support for multiple Azure tenants with isolated processing
- **Data Export**: Automated exports via CLI and specification generation
- **Compliance**: Audit logging, anonymization, and data governance features
- **Dual Implementation**: Python for development/automation, .NET for enterprise integration

### Multi-Language Implementation

The project includes both Python and .NET implementations:

#### Python Implementation (Primary)
- **Location**: `src/` directory
- **Features**: Full feature set with Rich dashboard, CLI, and interactive capabilities
- **Use Cases**: Development, automation, local analysis, and CI/CD integration

#### .NET Implementation (Enterprise)
- **Location**: `dotnet/` directory
- **Features**: Core functionality with enterprise-focused configuration and logging
- **Use Cases**: Enterprise integration, Windows environments, and corporate deployment

This specification provides complete guidance for understanding and extending the Azure Tenant Grapher project, including all architectural decisions, implementation details, configuration requirements, Infrastructure-as-Code generation capabilities, CLI tool management, and extensibility patterns established through the development process.

---

## Tenant Markdown Specification

### Purpose

The Tenant Markdown Specification feature enables users to generate anonymized, comprehensive Markdown documentation of their Azure tenant infrastructure. This documentation is portable, human-readable, and suitable for architecture reviews, compliance audits, knowledge transfer, and disaster recovery planning.

### CLI Usage

Generate a Markdown specification using the enhanced CLI:

```bash
# Using installed CLI command
azure-tenant-grapher generate-spec [--limit N] [--output PATH]

# Using script directly
uv run python scripts/cli.py generate-spec [--limit N] [--output PATH]
```

- `--limit` (optional): Maximum number of resources to include (default: from config).
- `--output` (optional): Custom output path (default: auto-generated in current directory).

Example:

```bash
azure-tenant-grapher generate-spec --limit 100 --output my-tenant-spec.md
```

### Specification File Location

Generated specifications are saved in the current directory with a timestamped filename by default:

```
{YYYYMMDD_HHMMSS}_tenant_spec.md
```

Example: `20250616_132221_tenant_spec.md`

You can specify a custom output path using the `--output` flag:

```bash
azure-tenant-grapher generate-spec --output /path/to/my-spec.md
```

### Anonymization Features

- **Consistent Placeholders**: Resources get semantic placeholders like `vm-production-a1b2c3d4`
- **Azure ID Removal**: All Azure resource IDs, URLs, and sensitive identifiers are anonymized
- **Configurable Seed**: Optional anonymization seed for reproducible placeholders
- **AI Summary Sanitization**: LLM descriptions are cleaned of identifying information

### Integration with Visualization

The interactive 3D graph visualizer (HTML output) includes a "View Tenant Specification" link, allowing users to quickly access the latest generated specification for the current tenant. This provides seamless navigation between the visual graph and the detailed Markdown documentation.

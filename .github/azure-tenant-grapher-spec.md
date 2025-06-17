# Azure Tenant Grapher - Complete Project Specification

## Project Overview

**Azure Tenant Grapher** is a Python application that exhaustively walks Azure tenant resources and builds a Neo4j graph database representation of those resources and their relationships. The project features modular architecture, comprehensive testing, interactive Rich CLI dashboard, 3D visualization capabilities, anonymized tenant specifications, and optional AI-powered resource descriptions. A complementary .NET implementation is also available for enterprise scenarios.

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
│   │   └── session_manager.py  # Session management utilities
│   ├── visualization/           # Visualization components
│   │   ├── html_template_builder.py # Main template coordinator
│   │   ├── css_style_builder.py     # CSS generation
│   │   ├── javascript_builder.py    # JavaScript generation
│   │   └── html_structure_builder.py # HTML structure
│   └── cli_dashboard_widgets/   # Dashboard UI components
│       └── scrollable_log_widget.py # Scrollable log display
├── tests/                        # Comprehensive test suite
│   ├── conftest.py              # Test fixtures and configuration
│   ├── test_*.py                # Module-specific test files (150+ tests)
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
  - Tenant specification document creation
  - Configurable AI models and prompts
  - Rate limiting and error handling

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

### 7. Modular Architecture
- **Design Pattern**: Dependency injection with configuration-based initialization
- **Testing**: 150+ test cases with comprehensive coverage
- **Error Handling**: Custom exception hierarchy with detailed context
- **Async Support**: Full async/await implementation for Azure API calls
- **Batch Processing**: Eager thread pool processing with adaptive throttling
- **Service Layer**: Separated Azure API interactions for better testability

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
azure-tenant-grapher visualize   # Generate 3D visualization from existing data
azure-tenant-grapher spec        # Generate AI-powered tenant specification
azure-tenant-grapher generate-spec # Generate anonymized Markdown specification
azure-tenant-grapher progress    # Check processing progress
azure-tenant-grapher config      # Show configuration template
azure-tenant-grapher container   # Container management subcommands
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

# Interface Options
--no-dashboard                # Disable Rich dashboard, use line-by-line logs
--log-level TEXT              # Logging level (DEBUG, INFO, WARNING, ERROR)

# Testing Options (for integration tests)
--test-keypress-queue         # Enable queue-based keypress simulation
--test-keypress-file PATH     # File-based keypress simulation
```

### Usage Examples
```bash
# Basic usage with auto-container management
python main.py --tenant-id your-tenant-id-here

# Generate with visualization
python main.py --tenant-id your-tenant-id --visualize

# Test mode with limited resources
python main.py --tenant-id your-tenant-id --resource-limit 50

# Container management only
python main.py --tenant-id dummy --container-only
```

## Configuration System

### Environment Variables
```bash
# Azure Configuration
AZURE_TENANT_ID=your-tenant-id-here

# Neo4j Configuration
NEO4J_URI=bolt://localhost:7688
NEO4J_USER=neo4j
NEO4J_PASSWORD=azure-grapher-2024

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
- **Coverage**: 150+ tests with extensive coverage including CLI and dashboard integration
- **Mocking**: Comprehensive mocks for Azure SDK, Neo4j, and external dependencies
- **Fixtures**: Reusable test fixtures in conftest.py
- **Markers**: Unit, integration, slow, and timeout test markers
- **Async Testing**: Full async test support with pytest-asyncio

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
      - NEO4J_AUTH=neo4j/azure-grapher-2024
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

### AI Integration Extensions
- **Custom Models**: Support for different AI models and providers
- **Custom Prompts**: Configurable prompt templates
- **Analysis Workflows**: Custom AI-powered analysis workflows

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

This specification provides complete guidance for understanding and extending the Azure Tenant Grapher project, including all architectural decisions, implementation details, configuration requirements, and extensibility patterns established through the development process.

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

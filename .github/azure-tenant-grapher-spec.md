# Azure Tenant Grapher - Complete Project Specification

## Project Overview

**Azure Tenant Grapher** is a Python application that exhaustively walks Azure tenant resources and builds a Neo4j graph database representation of those resources and their relationships. The project features modular architecture, comprehensive testing, 3D visualization capabilities, and optional AI-powered resource descriptions.

## Core Architecture

### 1. Project Structure
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
│   ├── test_*.py                # Module-specific test files (112+ tests)
├── scripts/                      # Utility scripts
│   ├── cli.py                   # Enhanced CLI wrapper
│   ├── demo_enhanced_features.py # Feature demonstration
│   ├── check_progress.py       # Progress checking utility
│   └── test_modular_structure.py # Structure validation
├── main.py                       # CLI entry point
├── run_tests.py                  # Test runner with coverage
├── pyproject.toml               # Project configuration
├── requirements.txt             # Dependencies
├── docker-compose.yml           # Neo4j container setup
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
- **Purpose**: Centralized configuration management with validation
- **Classes**:
  - `AzureTenantGrapherConfig`: Main configuration container
  - `Neo4jConfig`: Neo4j connection settings
  - `ProcessingConfig`: Resource processing settings
  - `LoggingConfig`: Logging configuration
  - `AzureOpenAIConfig`: AI integration settings
- **Functions**:
  - `create_config_from_env(tenant_id, resource_limit)`: Factory function for configuration
  - `setup_logging(config)`: Configure logging system

#### Resource Processor (src/resource_processor.py)
- **Purpose**: Modular resource processing with statistics tracking
- **Classes**:
  - `ProcessingStats`: Statistics tracking for processing operations
  - `ResourceState`: Neo4j query operations for resource state
  - `DatabaseOperations`: Neo4j CRUD operations
  - `ResourceProcessor`: Main processing orchestrator
- **Features**:
  - Async/await processing with configurable batch sizes
  - LLM integration for resource descriptions
  - Comprehensive error handling and statistics
  - Resource deduplication and state management

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
- **Purpose**: 3D interactive visualization and graph export
- **Class**: `GraphVisualizer`
- **Features**:
  - 3D force-directed graph using 3d-force-graph library
  - Interactive filtering by node/relationship types
  - Real-time search functionality
  - Node detail panels with resource metadata
  - Export capabilities (HTML, GEXF)
  - Auto-rotation and camera controls

#### LLM Descriptions (src/llm_descriptions.py)
- **Purpose**: AI-powered resource descriptions using Azure OpenAI
- **Class**: `AzureLLMDescriptionGenerator`
- **Features**:
  - Intelligent resource description generation
  - Tenant specification document creation
  - Configurable AI models and prompts
  - Rate limiting and error handling

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

### 5. Modular Architecture
- **Design Pattern**: Dependency injection with configuration-based initialization
- **Testing**: 112+ test cases with 76%+ code coverage
- **Error Handling**: Comprehensive exception handling with detailed logging
- **Async Support**: Full async/await implementation for Azure API calls
- **Batch Processing**: Configurable parallel processing with rate limiting

## Command Line Interface

### Main Entry Points
1. **main.py**: Primary CLI with full feature set
2. **cli.py**: Enhanced CLI wrapper with additional features
3. **Shell Scripts**: Unix (run-grapher.sh) and Windows (run-grapher.ps1) wrappers

### CLI Arguments
```bash
# Required
--tenant-id TEXT               # Azure tenant ID

# Processing Options
--resource-limit INTEGER       # Max resources (for testing)
--batch-size INTEGER          # Parallel processing batch size (default: 5)
--no-container               # Skip container auto-start
--container-only             # Start container only and exit

# Output Options
--visualize                  # Generate 3D visualization
--generate-spec             # Generate AI-powered tenant specification
--log-level TEXT            # Logging level (DEBUG, INFO, WARNING, ERROR)
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

# Logging Configuration
LOG_LEVEL=INFO

# LLM Integration (Optional)
AZURE_OPENAI_ENDPOINT=https://your-instance.openai.azure.com/...
AZURE_OPENAI_KEY=your-key-here
AZURE_OPENAI_API_VERSION=2025-01-01-preview
AZURE_OPENAI_MODEL_CHAT=gpt-4
```

### Configuration Classes
- **Validation**: Full configuration validation with descriptive error messages
- **Defaults**: Sensible defaults for all optional settings
- **Environment Override**: Environment variables override defaults
- **Logging**: Configuration summary logging for debugging

## Development Environment

### Dependencies Management
- **Tool**: UV (Astral's fast Python package manager)
- **Configuration**: pyproject.toml with dependency specifications
- **Virtual Environment**: Automatic virtual environment management
- **Lock File**: uv.lock for reproducible builds

### Code Quality Tools
- **Formatting**: Black (88 character line length)
- **Linting**: Ruff (modern Python linter)
- **Type Checking**: MyPy with strict configuration
- **Security**: Bandit for security vulnerability scanning
- **Pre-commit**: Automated code quality checks

### Testing Framework
- **Framework**: Pytest with async support
- **Coverage**: 76%+ code coverage with HTML reporting
- **Mocking**: Comprehensive mocks for Azure SDK and Neo4j
- **Fixtures**: Reusable test fixtures in conftest.py
- **Markers**: Unit, integration, and slow test markers

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
- **Batch Processing**: Configurable parallel processing (default: 5 concurrent)
- **Memory Management**: Streaming processing for large resource sets
- **Rate Limiting**: Respectful Azure API usage patterns
- **Database Optimization**: Efficient Neo4j queries with indexing

### Resource Requirements
- **Memory**: ~512MB base + ~1MB per 1000 resources
- **Storage**: Neo4j database grows ~1KB per resource + relationships
- **Network**: Minimal - only Azure API calls and Neo4j connections
- **CPU**: Moderate during processing, minimal during visualization

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
- **Multi-tenant**: Support for multiple Azure tenants
- **Data Export**: Scheduled exports to data lakes
- **Compliance**: Audit logging and data governance features

This specification provides complete guidance for regenerating the Azure Tenant Grapher project using LLMs, including all architectural decisions, implementation details, configuration requirements, and extensibility patterns established through the development process.

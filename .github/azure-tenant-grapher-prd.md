# Azure Tenant Grapher - Product Requirements Document

## Product Overview

**Azure Tenant Grapher** is a Python application that exhaustively discovers Azure tenant resources and builds a Neo4j graph database representation of those resources and their relationships. The application provides comprehensive resource mapping, interactive 3D visualization, Rich CLI dashboard interface, anonymized tenant specifications, and optional AI-powered documentation generation.

## Core Functional Requirements

### 1. Azure Resource Discovery

#### FR1.1 Tenant-Wide Resource Enumeration
- **Requirement**: Discover all Azure resources across all subscriptions within a specified Azure tenant
- **Scope**: All resource types supported by Azure Resource Manager API
- **Authentication**: Support multiple Azure authentication methods (service principal, managed identity, user authentication, Azure CLI)
- **Permissions**: Require minimum Reader role on target subscriptions

#### FR1.2 Resource Metadata Extraction
- **Requirement**: Capture comprehensive metadata for each discovered resource
- **Data Points**:
  - Unique resource identifier (ARM resource ID)
  - Resource name, type, and location
  - Parent resource group and subscription
  - Resource tags (key-value pairs)
  - SKU/pricing tier information where available
  - Resource-specific configuration properties
  - Creation and modification timestamps where available

#### FR1.3 Subscription Management
- **Requirement**: Enumerate and process all subscriptions within the tenant
- **Data Capture**:
  - Subscription ID and display name
  - Subscription state (active, disabled, etc.)
  - Tenant association
  - Subscription-level metadata

### 2. Graph Database Operations

#### FR2.1 Graph Schema Design
- **Node Types**:
  - **Subscription**: Represents Azure subscriptions
  - **ResourceGroup**: Represents resource group containers
  - **Resource**: Base type for all Azure resources
  - **Specialized Resource Types**: VirtualMachine, StorageAccount, VirtualNetwork, KeyVault, SqlServer, WebSite, etc.

#### FR2.2 Relationship Modeling
- **Relationship Types**:
  - **CONTAINS**: Hierarchical containment (Subscription contains ResourceGroups, ResourceGroups contain Resources)
  - **BELONGS_TO**: Membership relationships
  - **CONNECTED_TO**: Network connectivity and communication relationships
  - **DEPENDS_ON**: Resource dependencies and requirements
  - **MANAGES**: Management and control relationships

#### FR2.3 Data Operations
- **Requirements**:
  - Create and update nodes with comprehensive metadata
  - Establish relationships between resources based on Azure topology
  - Support incremental updates (avoid duplicate processing)
  - Maintain data consistency and integrity
  - Track processing status and timestamps

### 3. Interactive Visualization

#### FR3.1 3D Graph Visualization
- **Requirement**: Generate interactive 3D visualizations of the resource graph
- **Features**:
  - Force-directed layout algorithm for automatic node positioning
  - Color-coded nodes by resource type
  - Variable node sizes based on resource importance or complexity
  - Directional relationship visualization with animated particles
  - Camera controls (zoom, pan, rotate)
  - Auto-rotation mode for presentation purposes

#### FR3.2 Interactive Controls
- **Filtering Capabilities**:
  - Filter nodes by resource type using checkboxes
  - Filter relationships by type using checkboxes
  - Real-time search functionality across node names, types, and properties
  - Reset filters to show complete graph

#### FR3.3 Node Interaction
- **Requirements**:
  - Click nodes to display detailed information panel
  - Show all resource properties and metadata
  - Display resource relationships and connections
  - Hover effects for visual feedback

#### FR3.4 Export Capabilities
- **Requirements**:
  - Export as self-contained HTML file for sharing
  - Export in standard graph formats (GEXF) for external tools
  - Maintain interactivity in exported HTML files

### 4. AI-Powered Documentation (Optional Feature)

#### FR4.1 Resource Description Generation
- **Requirement**: Generate intelligent descriptions for Azure resources using AI
- **Capabilities**:
  - Analyze resource configuration and generate human-readable descriptions
  - Identify resource purposes and functions
  - Highlight important configuration details
  - Provide context about resource relationships

#### FR4.2 Tenant Architecture Documentation
- **Requirement**: Generate comprehensive tenant specification documents
- **Content**:
  - High-level architecture overview
  - Resource inventory and categorization
  - Relationship mapping and dependencies
  - Best practices recommendations
  - Security and compliance observations

### 5. Configuration Management

#### FR5.1 Environment Configuration
- **Requirements**:
  - Support configuration via environment variables
  - Provide sensible defaults for all optional settings
  - Validate configuration at startup with clear error messages
  - Support multiple configuration sources with precedence rules

#### FR5.2 Processing Configuration
- **Parameters**:
  - Azure tenant ID (required)
  - Resource processing limits for testing/development
  - Batch size for parallel processing
  - Database connection settings
  - Logging levels and output formatting
  - AI service configuration (optional)

### 6. Container and Infrastructure Management

#### FR6.1 Database Container Management
- **Requirement**: Automated management of graph database containers
- **Capabilities**:
  - Automatic container startup and configuration
  - Health checking and status monitoring
  - Container lifecycle management (start, stop, restart)
  - Volume management for data persistence
  - Network configuration for connectivity

#### FR6.2 Infrastructure Validation
- **Requirements**:
  - Validate required dependencies (container runtime, database access)
  - Perform connectivity tests before processing
  - Provide clear error messages for missing requirements
  - Support both automated and manual infrastructure setup

### 7. Processing and Performance

#### FR7.1 Batch Processing
- **Requirements**:
  - Process resources in configurable parallel batches
  - Implement rate limiting to respect Azure API limits
  - Support incremental processing (resume from failures)
  - Provide progress tracking and status reporting

#### FR7.2 Error Handling and Recovery
- **Requirements**:
  - Graceful handling of individual resource processing failures
  - Comprehensive error logging with context
  - Continue processing after non-critical errors
  - Retry logic for transient failures
  - Rollback capabilities for critical failures

#### FR7.3 Statistics and Monitoring
- **Requirements**:
  - Track processing statistics (total, successful, failed, skipped)
  - Calculate and report success rates
  - Monitor processing performance and timing
  - Generate processing reports and summaries

### 8. User Interface and Experience

#### FR8.1 Rich CLI Dashboard Interface
- **Requirements**:
  - Interactive Rich dashboard with live progress monitoring
  - Real-time log display in scrollable format
  - Dynamic log level adjustment (INFO, DEBUG, WARNING via keypresses)
  - Interactive exit capability ('x' to exit dashboard)
  - File-based logging with timestamped filenames
  - Configuration panel showing current settings
  - Progress statistics with LLM thread monitoring

#### FR8.2 Command Line Interface
- **Requirements**:
  - Comprehensive CLI with all major functionality (build, test, visualize, spec, generate-spec, progress, config)
  - Enhanced CLI wrapper with better error handling
  - Clear help documentation and usage examples
  - Multiple CLI aliases (azure-tenant-grapher, azure-graph, atg)
  - Support for both dashboard and no-dashboard modes
  - Colored output for better readability
  - Support for different verbosity levels

#### FR8.3 Operational Modes
- **Required Modes**:
  - **Full Processing**: Complete discovery, processing, and graph building with dashboard
  - **No-Dashboard Mode**: Line-by-line logging for CI/CD and scripting
  - **Test Mode**: Limited resource processing for development and testing
  - **Visualization Only**: Generate visualizations from existing data
  - **Specification Generation**: Create anonymized tenant specifications
  - **Container Management**: Database container operations only
  - **Progress Checking**: Monitor processing status from existing data

#### FR8.4 Cross-Platform Support
- **Requirements**:
  - Support major operating systems (Windows, macOS, Linux)
  - Provide platform-specific installation and execution scripts
  - Consistent behavior across platforms
  - Platform-appropriate default configurations
  - UV-based dependency management for fast, reliable installs

### 9. Data Export and Integration

#### FR9.1 Export Formats
- **Requirements**:
  - Export graph data in standard formats (GEXF, GraphML)
  - Export resource inventories as structured data (JSON, CSV)
  - Export interactive 3D visualizations as self-contained HTML files
  - Generate anonymized Markdown specifications for portable documentation
  - Support custom export templates and formats

#### FR9.2 Tenant Specification Generation
- **Requirements**:
  - Generate anonymized, portable Markdown documentation of Azure tenant
  - Configurable resource limits and anonymization settings
  - Consistent placeholder generation with semantic suffixes
  - Include AI summaries and configuration details as options
  - Support for different template styles and output directories

#### FR9.3 Integration Capabilities
- **Requirements**:
  - Integration with common graph analysis tools via GEXF export
  - Support for data pipeline integration through CLI automation
  - File-based configuration and environment variable support
  - Docker container integration for deployment scenarios

### 10. Security and Compliance

#### FR10.1 Authentication and Authorization
- **Requirements**:
  - Secure Azure authentication using official SDK methods
  - Principle of least privilege for Azure resource access
  - Secure storage and handling of credentials
  - Support for Azure Managed Identity in cloud environments

#### FR10.2 Data Security
- **Requirements**:
  - Local data processing (no external data transmission unless explicitly configured)
  - Encryption support for database connections
  - Audit logging for security-relevant operations
  - Secure handling of sensitive resource metadata

### 11. Testing and Quality Assurance

#### FR11.1 Test Coverage
- **Requirements**:
  - Comprehensive unit tests for all core functionality
  - Integration tests for Azure API interactions
  - Mock-based testing for safe execution without external dependencies
  - Performance and load testing capabilities

#### FR11.2 Code Quality
- **Requirements**:
  - Automated code formatting and linting
  - Static type checking where applicable
  - Security vulnerability scanning
  - Automated test execution in CI/CD pipelines

## Non-Functional Requirements

### Performance Requirements
- **Resource Processing**: Handle 10,000+ resources within reasonable time limits
- **Memory Usage**: Efficient memory management for large resource sets
- **Database Operations**: Optimized queries and batch operations
- **Visualization**: Smooth interaction with graphs containing 1,000+ nodes

### Scalability Requirements
- **Tenant Size**: Support enterprise-scale Azure tenants
- **Concurrent Processing**: Configurable parallel processing capabilities
- **Database Scaling**: Support for clustered graph database deployments
- **Resource Growth**: Handle growing resource inventories over time

### Reliability Requirements
- **Error Recovery**: Graceful handling of transient failures
- **Data Consistency**: Maintain graph consistency during processing
- **Monitoring**: Health checks and status monitoring
- **Backup**: Support for data backup and restoration

### Usability Requirements
- **Documentation**: Comprehensive user and developer documentation
- **Error Messages**: Clear, actionable error messages
- **Progress Feedback**: Visual progress indicators for long operations
- **Configuration**: Simple setup and configuration process

## Success Criteria

### Primary Success Metrics
1. **Discovery Completeness**: Successfully discover and catalog 95%+ of accessible Azure resources
2. **Processing Reliability**: Achieve 95%+ success rate in resource processing
3. **Visualization Quality**: Generate usable visualizations for graphs with 100-10,000 nodes
4. **User Adoption**: Enable users to successfully operate the tool with minimal documentation

### Secondary Success Metrics
1. **Performance**: Process 1,000 resources in under 5 minutes
2. **Error Handling**: Provide actionable error messages for 90%+ of failure scenarios
3. **Cross-Platform**: Successfully operate on Windows, macOS, and Linux
4. **Integration**: Support integration with at least 2 external tools or formats

## Future Considerations

### Potential Enhancements
- **Multi-Language Implementation**: Current .NET implementation alongside Python for enterprise scenarios
- **Multi-Cloud Support**: Extend to AWS, GCP resource discovery
- **Real-Time Updates**: Continuous monitoring and graph updates
- **Advanced Analytics**: Machine learning for resource optimization recommendations
- **Collaboration Features**: Multi-user access and sharing capabilities
- **Compliance Reporting**: Automated compliance and governance reporting
- **API Integration**: REST API for programmatic access and automation

### Scalability Considerations
- **Enterprise Features**: RBAC, audit logging, enterprise authentication
- **Cloud Deployment**: Native cloud deployment options and container orchestration
- **Data Lake Integration**: Export to enterprise data platforms
- **Distributed Processing**: Support for large-scale tenant processing
- **Performance Optimization**: Enhanced parallel processing and caching strategies

### 12. Infrastructure-as-Code Generation

#### FR12.1 Graph-to-IaC Transformation
- **Requirement**: Generate Infrastructure-as-Code templates from existing tenant graph data
- **Supported Formats**:
  - Terraform (.tf files with azurerm provider)
  - Azure Resource Manager templates (.json files)
  - Azure Bicep templates (.bicep files)
- **Capabilities**:
  - Convert Neo4j graph resources to IaC resource definitions
  - Preserve resource dependencies and relationships
  - Generate provider configurations and variable definitions
  - Support resource filtering and transformation rules
  - Generate ready-to-deploy templates with deployment scripts

#### FR12.2 Template Generation Pipeline
- **Requirements**:
  - Graph traversal to extract relevant resources and relationships
  - Configurable transformation rules for resource mapping via YAML files
  - Format-specific emitters for template generation
  - Template validation and syntax checking
  - Batch processing for large tenant graphs
  - Subset filtering for partial tenant replication

#### FR12.3 CLI Integration
- **Requirements**:
  - `generate-iac` command with format selection (terraform, arm, bicep)
  - Support for dry-run validation mode
  - Resource filtering and output path configuration
  - Subset filtering with flexible query syntax
  - Integration with existing tenant discovery workflow
  - Progress tracking and error reporting
  - Automatic tool installation and validation

#### FR12.4 Transformation Rules System
- **Requirements**:
  - YAML-based rules configuration for resource transformation
  - Name transformation with patterns and replacements
  - Region/location retargeting capabilities
  - Tag modification and addition rules
  - Resource group retargeting for deployment consolidation
  - Conditional transformation based on resource properties

#### FR12.5 Automated Deployment Support
- **Requirements**:
  - Generated templates include deployment scripts (deploy.sh, deploy.ps1)
  - Azure CLI integration for authentication and deployment
  - Parameter file generation for template customization
  - Deployment validation and error handling
  - Support for multiple target environments

### 13. CLI Tool Management

#### FR13.1 Automated Tool Installation
- **Requirements**:
  - Automatic detection of required CLI tools (Azure CLI, Terraform, Bicep)
  - Interactive installation prompts with platform-specific instructions
  - Tool registry with installation commands for multiple platforms
  - Version validation and compatibility checking
  - Doctor command for comprehensive tool validation

#### FR13.2 Platform Support
- **Requirements**:
  - Cross-platform tool installation (Windows, macOS, Linux)
  - Package manager integration (brew, choco, apt, yum)
  - Direct download fallback options
  - Environment variable configuration guidance
  - PATH validation and setup assistance

### Implementation Status
This product requirements document reflects the current Python implementation of Azure Tenant Grapher with comprehensive CLI interface, Rich dashboard, modular architecture, Infrastructure-as-Code generation capabilities, and extensive testing coverage. A complementary .NET implementation is also available for enterprise integration scenarios.

---

## Change Notes

- feat: MCP server & AutoGen agent CLI (`mcp-server`, `agent-mode`) and docs ([#41](https://github.com/your-repo/azure-tenant-grapher/issues/41))

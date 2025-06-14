# Azure Tenant Grapher Refactoring Plan

## Overview

This document outlines the detailed decomposition plan for breaking down the monolithic [`AzureTenantGrapher`](src/azure_tenant_grapher.py:30) class (607 lines) into smaller, focused components following the Single Responsibility Principle.

## Current State Analysis

### AzureTenantGrapher Class Responsibilities

The current [`AzureTenantGrapher`](src/azure_tenant_grapher.py:30) class handles multiple responsibilities:

1. **Configuration Management**: Manages configuration and initialization
2. **Azure Authentication**: Handles Azure credential management and fallback authentication
3. **Neo4j Connection Management**: Manages database connections and container lifecycle
4. **Subscription Discovery**: Discovers Azure subscriptions in the tenant
5. **Resource Discovery**: Discovers resources within subscriptions
6. **Resource Processing Coordination**: Orchestrates the resource processing pipeline
7. **LLM Integration**: Manages LLM generator initialization and tenant specification generation
8. **Container Management**: Handles Neo4j container lifecycle
9. **Error Handling**: Mixed error handling patterns throughout

### Key Methods and Their Responsibilities

| Method | Lines | Primary Responsibility | Complexity |
|--------|-------|----------------------|------------|
| `__init__` | 34 | Configuration & initialization | Medium |
| `connect_to_neo4j` | 31 | Neo4j connection management | High |
| `close_neo4j_connection` | 4 | Resource cleanup | Low |
| `discover_subscriptions` | 97 | Azure subscription discovery with auth fallback | Very High |
| `discover_resources_in_subscription` | 47 | Azure resource discovery | Medium |
| `generate_tenant_specification` | 61 | LLM-based specification generation | Medium |
| `create_subscription_node` | 8 | Database operations | Low |
| `process_resources_with_enhanced_handling` | 62 | Resource processing coordination | High |
| `process_resources_async_llm_with_adaptive_pool` | 82 | Complex async processing with throttling | Very High |
| `build_graph` | 130 | Main orchestration method | Very High |

## Proposed Service Architecture

### 1. AzureDiscoveryService

**Responsibility**: Handle all Azure resource and subscription discovery operations.

**Extracted Methods**:
- `discover_subscriptions()` (lines 105-201)
- `discover_resources_in_subscription()` (lines 203-250)
- Azure authentication handling and fallback logic

**Key Features**:
- Centralized Azure credential management
- Subscription enumeration with error handling
- Resource discovery with pagination support
- Authentication fallback mechanisms (az CLI integration)
- Retry logic for transient failures

**Dependencies**:
- Azure SDK clients (SubscriptionClient, ResourceManagementClient)
- Configuration for tenant settings
- Custom exception hierarchy for Azure errors

### 2. Neo4jSessionManager

**Responsibility**: Manage Neo4j database connections and session lifecycle.

**Extracted Methods**:
- `connect_to_neo4j()` (lines 67-97)
- `close_neo4j_connection()` (lines 99-103)
- Session management with context managers

**Key Features**:
- Connection pooling and lifecycle management
- Automatic reconnection on failure
- Session context managers for safe resource handling
- Container integration for development environments
- Health checks and connection testing

**Dependencies**:
- Neo4j driver and configuration
- Container manager for development setup
- Custom exception hierarchy for database errors

### 3. ResourceProcessingService

**Responsibility**: Coordinate resource processing operations and orchestrate the processing pipeline.

**Extracted Methods**:
- `process_resources_with_enhanced_handling()` (lines 327-390)
- `process_resources_async_llm_with_adaptive_pool()` (lines 392-475)
- Processing coordination and statistics tracking

**Key Features**:
- Batch processing with configurable parallelism
- Progress tracking and reporting
- Error recovery and retry mechanisms
- Resource deduplication and state management
- Integration with existing ResourceProcessor class

**Dependencies**:
- ResourceProcessor for actual processing logic
- Neo4j session manager for database operations
- LLM generator for description generation
- Configuration for processing parameters

### 4. TenantSpecificationService

**Responsibility**: Generate comprehensive tenant specifications using LLM integration.

**Extracted Methods**:
- `generate_tenant_specification()` (lines 252-312)
- Specification formatting and output handling

**Key Features**:
- LLM-based specification generation
- Multiple output formats (Markdown, JSON, etc.)
- Resource relationship analysis
- Template-based specification generation
- Anonymization and privacy controls

**Dependencies**:
- LLM generator for content creation
- Neo4j session manager for data retrieval
- Configuration for output settings
- File I/O for specification export

## Implementation Strategy

### Phase 1: Foundation Setup ✅

1. ✅ Create service directory structure (`src/services/`)
2. ✅ Implement base exception hierarchy (`src/exceptions.py`)
3. ✅ Create Neo4j session manager (`src/utils/session_manager.py`)

### Phase 2: Service Implementation

#### 2.1 AzureDiscoveryService

```python
# src/services/azure_discovery_service.py
class AzureDiscoveryService:
    def __init__(self, config: AzureTenantGrapherConfig):
        self.config = config
        self.credential = DefaultAzureCredential()

    async def discover_subscriptions(self) -> List[Dict[str, Any]]:
        """Discover all subscriptions with fallback authentication."""

    async def discover_resources_in_subscription(self, subscription_id: str) -> List[Dict[str, Any]]:
        """Discover resources in a specific subscription."""

    def _handle_auth_fallback(self) -> bool:
        """Handle Azure CLI authentication fallback."""
```

#### 2.2 Neo4jSessionManager Enhancement

The existing session manager will be enhanced to integrate with the container manager:

```python
# Enhanced src/utils/session_manager.py
class Neo4jSessionManager:
    def __init__(self, config: Neo4jConfig, container_manager: Optional[Neo4jContainerManager] = None):
        self.config = config
        self.container_manager = container_manager

    def ensure_connection(self) -> None:
        """Ensure connection is available, starting container if needed."""
```

#### 2.3 ResourceProcessingService

```python
# src/services/resource_processing_service.py
class ResourceProcessingService:
    def __init__(
        self,
        session_manager: Neo4jSessionManager,
        llm_generator: Optional[AzureLLMDescriptionGenerator],
        config: ProcessingConfig
    ):
        pass

    async def process_resources_batch(
        self,
        resources: List[Dict[str, Any]],
        progress_callback: Optional[Callable] = None
    ) -> ProcessingStats:
        """Process resources with enhanced handling and progress tracking."""
```

#### 2.4 TenantSpecificationService

```python
# src/services/tenant_specification_service.py
class TenantSpecificationService:
    def __init__(
        self,
        session_manager: Neo4jSessionManager,
        llm_generator: Optional[AzureLLMDescriptionGenerator],
        config: SpecificationConfig
    ):
        pass

    async def generate_specification(self, output_path: str) -> str:
        """Generate comprehensive tenant specification."""
```

### Phase 3: Refactored AzureTenantGrapher

The new [`AzureTenantGrapher`](src/azure_tenant_grapher.py:30) will become a coordinator that orchestrates the services:

```python
class AzureTenantGrapher:
    def __init__(self, config: AzureTenantGrapherConfig):
        self.config = config

        # Initialize services
        self.container_manager = Neo4jContainerManager() if config.processing.auto_start_container else None
        self.session_manager = Neo4jSessionManager(config.neo4j, self.container_manager)
        self.discovery_service = AzureDiscoveryService(config)
        self.processing_service = ResourceProcessingService(
            self.session_manager,
            create_llm_generator() if config.azure_openai.is_configured() else None,
            config.processing
        )
        self.specification_service = TenantSpecificationService(
            self.session_manager,
            self.processing_service.llm_generator,
            config.specification
        )

    async def build_graph(self, progress_callback: Optional[Callable] = None) -> Dict[str, Any]:
        """Simplified orchestration method using services."""
        # 1. Discover subscriptions
        subscriptions = await self.discovery_service.discover_subscriptions()

        # 2. Discover resources
        all_resources = []
        for subscription in subscriptions:
            resources = await self.discovery_service.discover_resources_in_subscription(subscription["id"])
            all_resources.extend(resources)

        # 3. Process resources
        with self.session_manager:
            stats = await self.processing_service.process_resources_batch(all_resources, progress_callback)

        return stats.to_dict()
```

## Benefits of This Decomposition

### 1. Single Responsibility Principle
- Each service has a clear, focused responsibility
- Easier to understand, test, and modify individual components
- Reduced cognitive complexity per class

### 2. Improved Testability
- Services can be unit tested in isolation
- Mock dependencies easily for focused testing
- Better test coverage with smaller, focused test suites

### 3. Enhanced Maintainability
- Changes to Azure discovery logic only affect AzureDiscoveryService
- Database connection improvements isolated to Neo4jSessionManager
- Processing enhancements contained within ResourceProcessingService

### 4. Better Error Handling
- Domain-specific exceptions for each service
- Consistent error patterns across services
- Improved debugging with service-specific context

### 5. Dependency Injection Ready
- Services accept dependencies through constructor injection
- Easy to swap implementations for testing or different environments
- Configuration is centralized and passed to relevant services

### 6. Scalability
- Services can be optimized independently
- Parallel development on different services
- Easier to add new features without affecting existing code

## Migration Strategy

### 1. Backward Compatibility
- Original [`AzureTenantGrapher`](src/azure_tenant_grapher.py:30) interface preserved during transition
- Gradual migration of internal implementation to use services
- Deprecation warnings for direct method access

### 2. Progressive Implementation
- Implement one service at a time
- Migrate methods gradually from monolithic class to services
- Maintain existing tests while adding new service-specific tests

### 3. Integration Testing
- End-to-end tests to ensure service integration works correctly
- Performance benchmarks to ensure no regression
- Comprehensive error scenario testing

## Expected Outcomes

### Code Quality Metrics
- **Class Size**: Reduce from 607 lines to ~150 lines for coordinator
- **Cyclomatic Complexity**: Reduce from ~45 to <10 per method
- **Test Coverage**: Increase from ~40% to 80%+
- **Maintainability Index**: Significant improvement in maintainability scores

### Developer Experience
- Faster development cycles with focused services
- Easier onboarding for new developers
- Clearer debugging and troubleshooting paths
- Better IDE support with smaller, focused classes

This refactoring plan provides a clear roadmap for transforming the monolithic [`AzureTenantGrapher`](src/azure_tenant_grapher.py:30) class into a well-structured, maintainable service architecture that follows SOLID principles and modern Python best practices.

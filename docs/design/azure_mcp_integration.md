# Azure MCP Server Integration Architecture

## Executive Summary

This document outlines the architecture for integrating Azure MCP Server with Azure Tenant Grapher (ATG), enabling natural language interactions with Azure resources through the Model Context Protocol. The integration follows ATG's philosophy of simplicity and modularity while enhancing existing functionality.

## Overview

The Azure MCP Server integration will provide a bridge between natural language queries and ATG's comprehensive graph database, allowing users to:
- Query Azure resources using natural language
- Perform tenant discovery and resource enumeration conversationally
- Manage identities and RBAC through simple commands
- Generate Infrastructure-as-Code from natural language descriptions

## Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        User Interface                        │
│         (CLI, VS Code Extension, GitHub Copilot)            │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│                    MCP Client Layer                          │
│               (Natural Language Processing)                  │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│              Azure MCP Integration Service                   │
│         (Operation Mapping & Orchestration)                  │
├───────────────────────────────────────────────────────────────┤
│  • Natural Language Parser                                    │
│  • Operation Router                                           │
│  • Context Manager                                            │
│  • Response Formatter                                         │
└─────────────────┬───────────────────────────────────────────┘
                  │
        ┌─────────┴─────────┬──────────┬──────────┐
        ▼                   ▼          ▼          ▼
┌──────────────┐  ┌──────────────┐ ┌──────────┐ ┌──────────────┐
│Azure Discovery│  │Graph Service │ │IAC Engine│ │Identity Mgmt │
│   Service     │  │  (Neo4j)     │ │          │ │   Service    │
└──────────────┘  └──────────────┘ └──────────┘ └──────────────┘
```

### Component Design

#### 1. MCP Client Setup (`src/mcp/client.py`)

```python
from typing import Optional, Dict, Any
from dataclasses import dataclass
import asyncio
from mcp import ClientSession
from src.config_manager import MCPConfig

@dataclass
class MCPClientConfig:
    """Configuration for MCP client connection"""
    server_url: str
    timeout: int = 30
    max_retries: int = 3

class AzureMCPClient:
    """Lightweight MCP client for Azure operations"""

    def __init__(self, config: MCPClientConfig):
        self.config = config
        self.session: Optional[ClientSession] = None

    async def connect(self):
        """Establish connection to MCP server"""
        # Simple connection with basic retry
        for attempt in range(self.config.max_retries):
            try:
                self.session = await self._create_session()
                return
            except Exception as e:
                if attempt == self.config.max_retries - 1:
                    raise
                await asyncio.sleep(2 ** attempt)

    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]):
        """Execute an MCP tool with given arguments"""
        if not self.session:
            await self.connect()
        return await self.session.call_tool(name=tool_name, arguments=arguments)
```

#### 2. Operation Mapping Layer (`src/mcp/operations.py`)

```python
from typing import Dict, List, Optional, Any
from enum import Enum
from dataclasses import dataclass

class OperationType(Enum):
    """Types of operations supported through MCP"""
    DISCOVERY = "discovery"
    QUERY = "query"
    IDENTITY = "identity"
    IAC = "iac"
    VISUALIZATION = "visualization"

@dataclass
class MCPOperation:
    """Represents a mapped MCP operation"""
    type: OperationType
    service: str
    method: str
    parameters: Dict[str, Any]

class OperationMapper:
    """Maps natural language to ATG operations"""

    def __init__(self):
        self.operation_patterns = self._build_patterns()

    def _build_patterns(self) -> Dict[str, MCPOperation]:
        """Build mapping patterns for common operations"""
        return {
            "list_tenants": MCPOperation(
                type=OperationType.DISCOVERY,
                service="azure_discovery",
                method="discover_subscriptions",
                parameters={}
            ),
            "enumerate_resources": MCPOperation(
                type=OperationType.DISCOVERY,
                service="azure_discovery",
                method="discover_resources",
                parameters={"resource_types": "*"}
            ),
            "query_graph": MCPOperation(
                type=OperationType.QUERY,
                service="graph_service",
                method="execute_cypher",
                parameters={}
            ),
            "list_users": MCPOperation(
                type=OperationType.IDENTITY,
                service="aad_graph",
                method="list_users",
                parameters={}
            ),
            "generate_bicep": MCPOperation(
                type=OperationType.IAC,
                service="iac_engine",
                method="generate",
                parameters={"format": "bicep"}
            )
        }

    def map_request(self, intent: str, entities: Dict[str, Any]) -> MCPOperation:
        """Map a natural language intent to an operation"""
        operation = self.operation_patterns.get(intent)
        if operation:
            # Merge entities into parameters
            operation.parameters.update(entities)
        return operation
```

#### 3. Service Integration Layer (`src/mcp/service_adapter.py`)

```python
from typing import Any, Dict, Optional
from src.services.azure_discovery_service import AzureDiscoveryService
from src.services.aad_graph_service import AADGraphService
from src.db.async_neo4j_session import AsyncNeo4jSession
from src.iac.engine import IaCEngine

class MCPServiceAdapter:
    """Adapts MCP operations to existing ATG services"""

    def __init__(self, config: Any):
        self.config = config
        self._services: Dict[str, Any] = {}
        self._initialize_services()

    def _initialize_services(self):
        """Lazy initialization of required services"""
        # Services are initialized on-demand to minimize resource usage
        pass

    async def execute_operation(self, operation: MCPOperation) -> Any:
        """Execute an operation against the appropriate service"""
        service = await self._get_service(operation.service)
        method = getattr(service, operation.method)

        try:
            result = await method(**operation.parameters)
            return self._format_response(result, operation.type)
        except Exception as e:
            return self._handle_error(e, operation)

    async def _get_service(self, service_name: str) -> Any:
        """Get or create a service instance"""
        if service_name not in self._services:
            self._services[service_name] = await self._create_service(service_name)
        return self._services[service_name]

    async def _create_service(self, service_name: str) -> Any:
        """Create a service instance based on name"""
        service_map = {
            "azure_discovery": lambda: AzureDiscoveryService(self.config),
            "aad_graph": lambda: AADGraphService(self.config),
            "graph_service": lambda: AsyncNeo4jSession(self.config.neo4j),
            "iac_engine": lambda: IaCEngine(self.config)
        }
        return service_map[service_name]()

    def _format_response(self, result: Any, operation_type: OperationType) -> Dict:
        """Format service response for MCP"""
        return {
            "success": True,
            "type": operation_type.value,
            "data": result,
            "metadata": {
                "timestamp": datetime.utcnow().isoformat(),
                "source": "atg"
            }
        }
```

#### 4. Error Handling (`src/mcp/errors.py`)

```python
from typing import Optional, Dict, Any
from enum import Enum

class MCPErrorType(Enum):
    """Types of MCP errors"""
    CONNECTION = "connection_error"
    AUTHENTICATION = "auth_error"
    RATE_LIMIT = "rate_limit"
    INVALID_OPERATION = "invalid_operation"
    SERVICE_ERROR = "service_error"

class MCPError(Exception):
    """Base MCP error with context"""

    def __init__(self,
                 error_type: MCPErrorType,
                 message: str,
                 context: Optional[Dict[str, Any]] = None):
        self.error_type = error_type
        self.message = message
        self.context = context or {}
        super().__init__(message)

class MCPErrorHandler:
    """Handles MCP errors with appropriate recovery strategies"""

    def __init__(self):
        self.retry_strategies = {
            MCPErrorType.CONNECTION: self._retry_with_backoff,
            MCPErrorType.RATE_LIMIT: self._retry_with_exponential_backoff,
            MCPErrorType.AUTHENTICATION: self._refresh_credentials,
        }

    async def handle(self, error: Exception, operation: Any) -> Any:
        """Handle an error with appropriate recovery"""
        if isinstance(error, MCPError):
            strategy = self.retry_strategies.get(error.error_type)
            if strategy:
                return await strategy(error, operation)

        # Log and re-raise unknown errors
        logger.error(f"Unhandled MCP error: {error}")
        raise
```

## Integration Points

### 1. Tenant Discovery
```python
# Natural language: "Discover all Azure tenants"
# Maps to: AzureDiscoveryService.discover_subscriptions()
async def discover_tenants_via_mcp(query: str) -> List[Dict]:
    client = AzureMCPClient(config)
    response = await client.execute_tool(
        "azure_list_subscriptions",
        {"tenant_id": config.tenant_id}
    )
    return response
```

### 2. Resource Enumeration
```python
# Natural language: "List all storage accounts in production"
# Maps to: Graph query with filters
async def enumerate_resources_via_mcp(query: str) -> List[Dict]:
    operation = mapper.map_request(
        intent="enumerate_resources",
        entities={"type": "storage", "environment": "production"}
    )
    return await adapter.execute_operation(operation)
```

### 3. Identity Management
```python
# Natural language: "Show users with owner role"
# Maps to: AADGraphService with RBAC filter
async def query_identities_via_mcp(query: str) -> List[Dict]:
    operation = mapper.map_request(
        intent="list_users",
        entities={"role": "owner"}
    )
    return await adapter.execute_operation(operation)
```

### 4. Infrastructure Generation
```python
# Natural language: "Generate Bicep template for web application"
# Maps to: IaCEngine with specific parameters
async def generate_iac_via_mcp(query: str) -> str:
    operation = mapper.map_request(
        intent="generate_bicep",
        entities={"resource_type": "web_app", "include_dependencies": True}
    )
    return await adapter.execute_operation(operation)
```

## Configuration

### Environment Variables
```yaml
# MCP Configuration
MCP_SERVER_URL: "http://localhost:8080"
MCP_TIMEOUT: 30
MCP_MAX_RETRIES: 3
MCP_ENABLE_CACHE: true
MCP_CACHE_TTL: 300

# Azure MCP Settings
AZURE_MCP_ENDPOINT: "https://azure-mcp.azurewebsites.net"
AZURE_MCP_API_VERSION: "2024-01-01"

# Feature Flags
ENABLE_MCP_INTEGRATION: true
MCP_OPERATIONS_WHITELIST: "discovery,query,identity"
```

### Configuration Schema (`src/mcp/config.py`)
```python
@dataclass
class MCPIntegrationConfig:
    """Configuration for MCP integration"""
    enabled: bool = False
    server_url: str = "http://localhost:8080"
    timeout: int = 30
    max_retries: int = 3
    cache_enabled: bool = True
    cache_ttl: int = 300
    operations_whitelist: List[str] = field(default_factory=list)

    @classmethod
    def from_env(cls):
        """Load configuration from environment"""
        return cls(
            enabled=os.getenv("ENABLE_MCP_INTEGRATION", "false").lower() == "true",
            server_url=os.getenv("MCP_SERVER_URL", "http://localhost:8080"),
            timeout=int(os.getenv("MCP_TIMEOUT", "30")),
            max_retries=int(os.getenv("MCP_MAX_RETRIES", "3")),
            cache_enabled=os.getenv("MCP_ENABLE_CACHE", "true").lower() == "true",
            cache_ttl=int(os.getenv("MCP_CACHE_TTL", "300")),
            operations_whitelist=os.getenv("MCP_OPERATIONS_WHITELIST", "").split(",")
        )
```

## Implementation Phases

### Phase 1: Core Integration (Week 1-2)
- [ ] MCP client setup and connection management
- [ ] Basic operation mapping for discovery and query
- [ ] Error handling framework
- [ ] Unit tests for client and mapper

### Phase 2: Service Adapters (Week 2-3)
- [ ] Azure Discovery Service adapter
- [ ] Graph Service (Neo4j) adapter
- [ ] Response formatting and normalization
- [ ] Integration tests with mock services

### Phase 3: Natural Language Processing (Week 3-4)
- [ ] Intent recognition for common operations
- [ ] Entity extraction from queries
- [ ] Context management for multi-turn conversations
- [ ] End-to-end testing with real Azure resources

### Phase 4: Advanced Features (Week 4-5)
- [ ] Identity and RBAC management operations
- [ ] Infrastructure-as-Code generation
- [ ] Caching layer for frequent queries
- [ ] Performance optimization

### Phase 5: Production Readiness (Week 5-6)
- [ ] Comprehensive error recovery
- [ ] Monitoring and telemetry
- [ ] Documentation and examples
- [ ] Security review and hardening

## Testing Strategy

### Unit Testing
```python
# tests/mcp/test_client.py
async def test_mcp_client_connection():
    """Test MCP client can establish connection"""
    config = MCPClientConfig(server_url="http://test:8080")
    client = AzureMCPClient(config)

    with mock_mcp_server():
        await client.connect()
        assert client.session is not None

async def test_operation_mapping():
    """Test natural language maps to correct operations"""
    mapper = OperationMapper()
    operation = mapper.map_request(
        intent="list_tenants",
        entities={}
    )
    assert operation.type == OperationType.DISCOVERY
    assert operation.service == "azure_discovery"
```

### Integration Testing
```python
# tests/mcp/test_integration.py
async def test_tenant_discovery_via_mcp():
    """Test end-to-end tenant discovery through MCP"""
    adapter = MCPServiceAdapter(test_config)
    operation = MCPOperation(
        type=OperationType.DISCOVERY,
        service="azure_discovery",
        method="discover_subscriptions",
        parameters={}
    )

    result = await adapter.execute_operation(operation)
    assert result["success"]
    assert "data" in result
    assert isinstance(result["data"], list)
```

### Performance Testing
```python
# tests/mcp/test_performance.py
async def test_mcp_query_performance():
    """Ensure MCP queries complete within SLA"""
    client = AzureMCPClient(config)

    start = time.time()
    await client.execute_tool("list_resources", {})
    duration = time.time() - start

    assert duration < 5.0  # 5 second SLA
```

## Security Considerations

### Authentication
- Use Azure Managed Identity when available
- Fall back to Service Principal authentication
- Never store credentials in code or config files
- Implement token refresh for long-running operations

### Authorization
- Validate all operations against user permissions
- Implement operation whitelisting
- Log all MCP operations for audit trail
- Use least-privilege principle for service accounts

### Data Protection
- Encrypt sensitive data in transit
- Sanitize user inputs before processing
- Implement rate limiting to prevent abuse
- Mask sensitive information in logs

## Monitoring and Observability

### Metrics
- MCP connection success/failure rate
- Operation latency percentiles (p50, p95, p99)
- Error rates by operation type
- Cache hit/miss ratios

### Logging
```python
# Structured logging for MCP operations
logger.info("mcp_operation", extra={
    "operation_type": operation.type.value,
    "service": operation.service,
    "method": operation.method,
    "duration_ms": duration * 1000,
    "success": result["success"],
    "error": result.get("error")
})
```

### Alerting
- Connection failures > 5% in 5 minutes
- Operation latency p95 > 10 seconds
- Authentication failures > 3 in 1 minute
- Service errors > 10 in 5 minutes

## API Contracts

### MCP Request Format
```json
{
  "operation": "discover_resources",
  "parameters": {
    "subscription_id": "12345-67890",
    "resource_types": ["Microsoft.Storage/*", "Microsoft.Compute/*"],
    "tags": {
      "environment": "production"
    }
  },
  "context": {
    "user_id": "user@example.com",
    "session_id": "abc123",
    "correlation_id": "xyz789"
  }
}
```

### MCP Response Format
```json
{
  "success": true,
  "operation": "discover_resources",
  "data": {
    "resources": [
      {
        "id": "/subscriptions/12345/resourceGroups/rg1/...",
        "name": "storageaccount1",
        "type": "Microsoft.Storage/storageAccounts",
        "location": "eastus",
        "tags": {
          "environment": "production"
        }
      }
    ],
    "count": 42,
    "next_link": null
  },
  "metadata": {
    "timestamp": "2024-01-01T00:00:00Z",
    "duration_ms": 1234,
    "source": "atg",
    "version": "1.0.0"
  }
}
```

## Dependencies

### Required Packages
```toml
# Add to pyproject.toml
[project.dependencies]
mcp = ">=0.1.0"
azure-mcp = ">=0.1.0"
```

### Optional Packages
```toml
[project.optional-dependencies]
mcp-extras = [
    "mcp-cache>=0.1.0",
    "mcp-telemetry>=0.1.0"
]
```

## Migration Path

### Gradual Adoption
1. Start with read-only operations (discovery, query)
2. Add write operations after validation
3. Enable caching once patterns are established
4. Optimize based on usage metrics

### Backward Compatibility
- MCP integration is opt-in via feature flag
- Existing CLI commands remain unchanged
- MCP provides additional interface, not replacement
- Graceful fallback when MCP unavailable

## Success Metrics

### Technical Metrics
- 99.9% availability for MCP operations
- < 2 second response time for simple queries
- < 10 second response time for complex operations
- < 0.1% error rate

### Business Metrics
- 50% reduction in time to discover resources
- 75% of users adopt natural language interface
- 90% user satisfaction with MCP interactions
- 30% increase in overall ATG usage

## Risks and Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| MCP server unavailability | High | Medium | Implement circuit breaker and fallback |
| Azure API rate limiting | Medium | High | Implement caching and request batching |
| Natural language ambiguity | Medium | High | Provide clarification prompts |
| Security vulnerabilities | High | Low | Regular security audits and testing |
| Performance degradation | Medium | Medium | Implement monitoring and optimization |

## Future Enhancements

### Near-term (3-6 months)
- Multi-language support for queries
- Advanced query optimization
- Batch operation support
- WebSocket support for real-time updates

### Long-term (6-12 months)
- AI-powered query suggestions
- Predictive resource discovery
- Automated compliance checking
- Cross-tenant operations

## Appendix

### Example Scenarios

#### Scenario 1: Resource Discovery
```
User: "Show me all storage accounts in the production environment"
MCP: Maps to graph query with filters
ATG: Returns list of matching storage accounts
User: "Which ones have public access enabled?"
MCP: Refines query with security filter
ATG: Returns filtered results
```

#### Scenario 2: Identity Management
```
User: "List users with owner permissions on critical resources"
MCP: Combines identity and RBAC queries
ATG: Returns user list with role assignments
User: "Remove user X from owner role"
MCP: Executes RBAC modification
ATG: Updates permissions and confirms
```

#### Scenario 3: Infrastructure Generation
```
User: "Create a Bicep template for this resource group"
MCP: Analyzes resource group contents
ATG: Generates Bicep with dependencies
User: "Deploy to staging environment"
MCP: Validates and initiates deployment
ATG: Monitors deployment progress
```

### References
- [Model Context Protocol Specification](https://modelcontextprotocol.io/docs)
- [Azure MCP Server Documentation](https://github.com/Azure/azure-mcp)
- [ATG Architecture Documentation](../INDEX.md)
- [Azure SDK for Python](https://docs.microsoft.com/en-us/azure/developer/python/)

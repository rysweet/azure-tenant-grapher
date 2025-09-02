# Multi-Tenant Support Implementation Plan

## Executive Summary

Azure Tenant Grapher currently operates on a single-tenant model where one set of credentials accesses one Azure tenant at a time. This issue outlines a comprehensive plan to transform the application into a multi-tenant system that can:

1. **Support login and enumeration from multiple tenants simultaneously**
2. **Provide UI for managing multiple tenant contexts**
3. **Enable cross-tenant operations** (e.g., create graph from Tenant A, hydrate resources in Tenant B)

## Current State Analysis

### Single-Tenant Assumptions

The codebase makes single-tenant assumptions in the following areas:

#### 1. Configuration & Authentication
- **Environment Variables**: Single `AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`
- **Config Class**: `AzureTenantGrapherConfig` stores one `tenant_id`
- **Credentials**: Services use single `DefaultAzureCredential` or `ClientSecretCredential`

#### 2. Database Schema
- Resources and Subscriptions lack tenant context
- No tenant-based data isolation
- Resource IDs are globally unique without tenant scoping

#### 3. User Interface
- SPA displays single tenant name
- Configuration tab manages one set of credentials
- No tenant selection or switching capability

#### 4. CLI Commands
- All commands take single `--tenant-id` parameter
- No support for tenant iteration or bulk operations

## Proposed Architecture

### Phase 1: Foundation (Tenant Registry & Multi-Credential Support)

#### 1.1 Tenant Registry System

Create a new tenant registry to manage multiple tenant configurations:

```python
# src/tenant_registry.py
@dataclass
class TenantConfig:
    tenant_id: str
    display_name: str
    client_id: str
    client_secret: str  # Encrypted storage
    is_active: bool = True
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    last_used: Optional[datetime] = None

class TenantRegistry:
    def __init__(self, storage_path: str = "~/.atg/tenants.json"):
        self.tenants: Dict[str, TenantConfig] = {}
        
    def add_tenant(self, config: TenantConfig) -> None
    def remove_tenant(self, tenant_id: str) -> None
    def get_tenant(self, tenant_id: str) -> TenantConfig
    def list_tenants(self, tags: List[str] = None) -> List[TenantConfig]
    def get_credential(self, tenant_id: str) -> ClientSecretCredential
```

#### 1.2 Secure Credential Storage (Enhanced with Azure MCP)

**Update**: Based on Azure MCP Server analysis (Issue #201), we should leverage Azure Key Vault via Azure MCP for credential management instead of local storage.

```python
# src/credential_manager.py
from azure_mcp_client import AzureMCPClient

class CredentialManager:
    """
    Secure credential management using Azure Key Vault via Azure MCP.
    This provides enterprise-grade security for multi-tenant credentials.
    """
    def __init__(self):
        self.mcp = AzureMCPClient()
        self.vault_name = "atg-credentials"
    
    async def store_credential(self, tenant_id: str, client_id: str, client_secret: str):
        """Store tenant credentials in Azure Key Vault."""
        await self.mcp.tools.azure_keyvault.set_secret(
            vault_name=self.vault_name,
            secret_name=f"tenant-{tenant_id}-clientid",
            value=client_id
        )
        await self.mcp.tools.azure_keyvault.set_secret(
            vault_name=self.vault_name,
            secret_name=f"tenant-{tenant_id}-secret",
            value=client_secret
        )
    
    async def retrieve_credential(self, tenant_id: str) -> Tuple[str, str]:
        """Retrieve tenant credentials from Azure Key Vault."""
        client_id = await self.mcp.tools.azure_keyvault.get_secret(
            vault_name=self.vault_name,
            secret_name=f"tenant-{tenant_id}-clientid"
        )
        client_secret = await self.mcp.tools.azure_keyvault.get_secret(
            vault_name=self.vault_name,
            secret_name=f"tenant-{tenant_id}-secret"
        )
        return client_id, client_secret
    
    async def rotate_credential(self, tenant_id: str, new_secret: str):
        """Rotate tenant credential with versioning."""
        await self.mcp.tools.azure_keyvault.set_secret(
            vault_name=self.vault_name,
            secret_name=f"tenant-{tenant_id}-secret",
            value=new_secret
        )
```

**Benefits of Azure Key Vault Integration:**
- Enterprise-grade encryption and security
- Automatic credential rotation support
- Audit logging and compliance tracking
- Integration with Azure RBAC for access control
- No local credential storage required

### Phase 2: Database Schema Evolution

#### 2.1 Neo4j Schema Changes

Add tenant context to all nodes and relationships:

```cypher
// Migration: Add tenant context
CREATE CONSTRAINT tenant_unique IF NOT EXISTS 
  FOR (t:Tenant) REQUIRE t.id IS UNIQUE;

// Update Resource nodes to include tenant context
MATCH (r:Resource)
SET r.tenant_id = $tenant_id;

// Create composite constraints
CREATE CONSTRAINT resource_tenant_unique IF NOT EXISTS
  FOR (r:Resource) REQUIRE (r.id, r.tenant_id) IS UNIQUE;
```

#### 2.2 Tenant-Scoped Queries

Modify all queries to include tenant context:

```python
# Before (single-tenant)
session.run("MATCH (r:Resource) RETURN r")

# After (multi-tenant)
session.run(
    "MATCH (t:Tenant {id: $tenant_id})-[:OWNS]->(r:Resource) RETURN r",
    tenant_id=tenant_id
)
```

#### 2.3 Cross-Tenant Relationships

Support relationships between resources in different tenants:

```cypher
// Cross-tenant peering relationship
MATCH (r1:Resource {tenant_id: $tenant1}), 
      (r2:Resource {tenant_id: $tenant2})
WHERE r1.type = 'VirtualNetwork' AND r2.type = 'VirtualNetwork'
CREATE (r1)-[:PEERED_WITH {cross_tenant: true}]->(r2)
```

### Phase 3: CLI Enhancements

#### 3.1 Multi-Tenant CLI Commands

```bash
# Register a new tenant
atg tenant add --name "Production" --tenant-id xxx --client-id yyy --client-secret zzz

# List registered tenants
atg tenant list

# Build graphs for multiple tenants
atg build --all-tenants
atg build --tenant-tags production,staging

# Cross-tenant operations
atg compare --source-tenant prod --target-tenant dev
atg replicate --from-tenant prod --to-tenant staging --resource-types "VirtualNetwork,StorageAccount"

# Switch default tenant context
atg tenant use production
```

#### 3.2 Tenant Context Management

```python
# src/cli_context.py
class TenantContext:
    def __init__(self):
        self.current_tenant: Optional[str] = None
        self.registry = TenantRegistry()
    
    def set_current(self, tenant_id: str)
    def get_current(self) -> TenantConfig
    def with_tenant(self, tenant_id: str) -> ContextManager
```

### Phase 3.5: Azure MCP Integration for Multi-Tenant Operations

**Update**: Leverage Azure MCP Server (Issue #201) for enhanced multi-tenant capabilities.

#### 3.5.1 Multi-Tenant Resource Discovery via Azure MCP

```python
# src/services/multi_tenant_discovery.py
class MultiTenantDiscoveryService:
    """
    Use Azure MCP for efficient multi-tenant resource discovery.
    """
    def __init__(self):
        self.mcp = AzureMCPClient()
        self.credential_manager = CredentialManager()
    
    async def discover_all_tenants(self, tenant_ids: List[str]):
        """Discover resources across multiple tenants concurrently."""
        tasks = []
        for tenant_id in tenant_ids:
            # Retrieve credentials from Key Vault
            creds = await self.credential_manager.retrieve_credential(tenant_id)
            
            # Create tenant-specific MCP context
            tenant_mcp = self.mcp.with_credentials(tenant_id, creds)
            
            # Launch discovery task
            tasks.append(self.discover_tenant(tenant_mcp, tenant_id))
        
        results = await asyncio.gather(*tasks)
        return dict(zip(tenant_ids, results))
    
    async def discover_tenant(self, mcp_client, tenant_id: str):
        """Discover all resources in a single tenant via MCP."""
        resources = await mcp_client.tools.azure_resources.list_all()
        
        # Tag resources with tenant context
        for resource in resources:
            resource['tenant_id'] = tenant_id
        
        return resources
```

#### 3.5.2 Cross-Tenant Permission Analysis

```python
async def analyze_cross_tenant_permissions(self):
    """Use Azure MCP RBAC tools to analyze permissions across tenants."""
    analysis = {}
    
    for tenant_id in self.tenant_ids:
        tenant_mcp = await self.get_tenant_mcp(tenant_id)
        
        # Get role assignments via MCP
        assignments = await tenant_mcp.tools.azure_rbac.list_role_assignments()
        
        # Check for cross-tenant service principals
        for assignment in assignments:
            if assignment.principal_type == "ServicePrincipal":
                # Check if this SP exists in other tenants
                cross_tenant = await self.check_cross_tenant_sp(
                    assignment.principal_id
                )
                if cross_tenant:
                    analysis[tenant_id] = {
                        'risk': 'high',
                        'detail': f'Service principal {assignment.principal_id} has access to multiple tenants'
                    }
    
    return analysis
```

### Phase 4: User Interface Enhancements

#### 4.1 Tenant Selector Component

```typescript
// spa/renderer/src/components/TenantSelector.tsx
interface TenantSelectorProps {
  onTenantChange: (tenantId: string) => void;
  currentTenant: string;
}

const TenantSelector: React.FC<TenantSelectorProps> = ({ ... }) => {
  // Dropdown with registered tenants
  // Quick switch functionality
  // Visual indicator of current tenant
}
```

#### 4.2 Tenant Management Tab

New tab for tenant CRUD operations:
- Add/Edit/Remove tenants
- Test credentials
- View tenant metadata
- Set default tenant
- Manage tenant tags

#### 4.3 Multi-Tenant Dashboard

Enhanced dashboard showing:
- Resource counts per tenant
- Cross-tenant relationships
- Tenant-specific metrics
- Comparative analysis views

### Phase 5: Advanced Features

#### 5.1 Cross-Tenant Resource Hydration

```python
# src/cross_tenant_operations.py
class CrossTenantHydrator:
    async def hydrate_from_template(
        self,
        source_tenant: str,
        target_tenant: str,
        resource_filter: Dict[str, Any]
    ):
        """
        Read resources from source tenant graph and 
        create them in target tenant
        """
        source_resources = await self.read_resources(source_tenant, resource_filter)
        iac_template = await self.generate_iac(source_resources)
        await self.deploy_to_tenant(target_tenant, iac_template)
```

#### 5.2 Tenant Comparison Engine

```python
class TenantComparator:
    def compare_resources(self, tenant1: str, tenant2: str) -> ComparisonResult:
        """Compare resource configurations between tenants"""
        
    def find_drift(self, tenant1: str, tenant2: str) -> List[ResourceDrift]:
        """Identify configuration drift between tenants"""
        
    def generate_sync_plan(self, source: str, target: str) -> SyncPlan:
        """Create plan to synchronize tenants"""
```

#### 5.3 Multi-Tenant Threat Modeling

```python
class MultiTenantThreatModeler:
    def analyze_cross_tenant_risks(self, tenants: List[str]) -> ThreatReport:
        """Identify security risks in cross-tenant configurations"""
        
    def find_lateral_movement_paths(self) -> List[AttackPath]:
        """Discover potential lateral movement between tenants"""
```

### Phase 6: Enhanced Agent Mode with Azure MCP Integration

**Update**: Integrate Azure MCP Server with Agent Mode for powerful multi-tenant AI capabilities (Issues #201).

#### 6.1 Dual MCP Architecture for Agent Mode

```python
# src/agent_mode_enhanced.py
class EnhancedAgentMode:
    """
    Agent Mode with dual MCP servers:
    - Azure MCP for Azure service interactions
    - Neo4j MCP for graph database queries
    """
    def __init__(self):
        self.azure_mcp = AzureMCPClient()
        self.neo4j_mcp = Neo4jMCPClient()
        self.credential_manager = CredentialManager()
        self.tenant_registry = TenantRegistry()
    
    async def setup_multi_tenant_context(self):
        """Initialize MCP clients for all registered tenants."""
        self.tenant_contexts = {}
        
        for tenant in self.tenant_registry.list_tenants():
            # Get credentials from Key Vault via Azure MCP
            creds = await self.credential_manager.retrieve_credential(tenant.tenant_id)
            
            # Create tenant-specific Azure MCP context
            self.tenant_contexts[tenant.tenant_id] = {
                'azure_mcp': self.azure_mcp.with_credentials(tenant.tenant_id, creds),
                'display_name': tenant.display_name
            }
```

#### 6.2 Natural Language Multi-Tenant Queries

```python
async def process_multi_tenant_query(self, query: str):
    """
    Process natural language queries across multiple tenants.
    
    Examples:
    - "Compare storage accounts between prod and dev tenants"
    - "Find all VMs without backup across all tenants"
    - "Show cross-tenant network connections"
    """
    # Use LLM to understand query intent
    intent = await self.analyze_query_intent(query)
    
    if intent.scope == "all_tenants":
        results = {}
        for tenant_id, context in self.tenant_contexts.items():
            # Use Azure MCP to get Azure resources
            azure_data = await context['azure_mcp'].tools.query(intent.azure_query)
            
            # Store in Neo4j with tenant context
            await self.neo4j_mcp.tools.store_with_tenant(azure_data, tenant_id)
            
            # Query Neo4j for analysis
            graph_results = await self.neo4j_mcp.tools.query(
                f"MATCH (r:Resource {{tenant_id: '{tenant_id}'}}) {intent.cypher_filter}"
            )
            
            results[context['display_name']] = graph_results
        
        return self.format_multi_tenant_results(results)
    
    elif intent.scope == "cross_tenant":
        # Handle cross-tenant relationship queries
        return await self.analyze_cross_tenant_relationships(intent)
```

#### 6.3 Agent Mode System Prompt Enhancement

```python
ENHANCED_SYSTEM_MESSAGE = """
You are a multi-tenant Azure graph/security assistant with access to:

1. Azure MCP Server - For interacting with Azure services:
   - List and analyze resources across multiple tenants
   - Query Azure Monitor, Key Vault, RBAC, and 30+ services
   - Execute Azure CLI commands
   - Manage credentials securely via Key Vault

2. Neo4j MCP Server - For graph database operations:
   - Query the graph with Cypher
   - Analyze relationships and patterns
   - Perform threat modeling

3. Multi-Tenant Context:
   - You can switch between tenants using 'use tenant <name>'
   - Compare resources across tenants
   - Identify cross-tenant security risks

When answering questions:
1. Determine if the query is single-tenant or multi-tenant
2. Use Azure MCP to gather Azure-specific data
3. Use Neo4j MCP to analyze graph relationships
4. Combine insights from both sources

Example workflows:
- "Which tenant has the most exposed storage accounts?"
  1. Use Azure MCP to list storage accounts per tenant
  2. Check public access settings via Azure MCP
  3. Store results in Neo4j with tenant context
  4. Query Neo4j to compare across tenants

- "Find service principals with access to multiple tenants"
  1. Use Azure MCP RBAC tools per tenant
  2. Correlate principal IDs across tenants
  3. Create cross-tenant relationships in Neo4j
  4. Query for security risks
"""
```

#### 6.4 Agent Mode CLI Integration

```bash
# Multi-tenant agent mode commands
atg agent-mode --all-tenants  # Load all tenant contexts
atg agent-mode --tenants prod,dev,staging  # Specific tenants
atg agent-mode --tenant prod  # Single tenant (backward compatible)

# In agent mode session
> list all key vaults across tenants
> compare VM configurations between prod and dev
> find resources accessible from multiple tenants
> which tenant has the highest security risk score?
```

#### 6.5 Agent Mode UI Enhancement

```typescript
// Enhanced Agent Mode tab with tenant context
interface AgentModeState {
  selectedTenants: string[];
  currentQuery: string;
  results: {
    tenantId: string;
    tenantName: string;
    data: any;
  }[];
  comparisonMode: boolean;
}

const EnhancedAgentModeTab: React.FC = () => {
  // Tenant selector for scoping queries
  // Results display with tenant grouping
  // Comparison view for multi-tenant results
  // Cross-tenant relationship visualization
}
```

## Implementation Roadmap

**Note**: Since the tool is not in production, we can implement these changes directly without maintaining backward compatibility.

### Milestone 1: Foundation with Azure MCP (Weeks 1-2)
- [ ] Implement TenantRegistry 
- [ ] Integrate Azure MCP for Key Vault credential management
- [ ] Add tenant CLI commands (add, list, remove, use)
- [ ] Update configuration system for multi-tenant
- [ ] Set up Azure Key Vault for credential storage via MCP

### Milestone 2: Database (Weeks 3-4)
- [ ] Create schema migrations for tenant context
- [ ] Update all Cypher queries for tenant scoping
- [ ] Implement tenant data isolation
- [ ] Add cross-tenant relationship support

### Milestone 3: Core Services with Azure MCP (Weeks 5-6)
- [ ] Integrate Azure MCP alongside AzureDiscoveryService
- [ ] Implement MultiTenantDiscoveryService using Azure MCP
- [ ] Modify ResourceProcessingService for tenant context
- [ ] Update AADGraphService for multiple tenants
- [ ] Add concurrent multi-tenant discovery via MCP
- [ ] Implement cross-tenant permission analysis

### Milestone 4: User Interface (Weeks 7-8)
- [ ] Build TenantSelector component
- [ ] Create Tenant Management tab
- [ ] Update all tabs for tenant context
- [ ] Add multi-tenant dashboard views

### Milestone 5: Advanced Features & Agent Mode (Weeks 9-10)
- [ ] Implement enhanced Agent Mode with dual MCP architecture
- [ ] Add natural language multi-tenant queries
- [ ] Build tenant comparison engine
- [ ] Implement cross-tenant hydration via Azure MCP
- [ ] Add multi-tenant threat modeling
- [ ] Create tenant synchronization tools

### Milestone 6: Testing & Documentation (Weeks 11-12)
- [ ] Comprehensive multi-tenant tests
- [ ] Performance testing with multiple tenants
- [ ] Security audit of credential management
- [ ] Complete documentation for multi-tenant usage

## Breaking Changes

Since the tool is not yet in production, we can make breaking changes without migration concerns:

### API Changes
- All CLI commands will require explicit tenant context
- Environment variables will be replaced by tenant registry
- Database schema will be updated directly for multi-tenant support
- No backward compatibility with single-tenant mode required

## Security Considerations

### Credential Management
- Encrypted storage using OS keyring or Azure Key Vault
- Credential rotation reminders
- Audit logging for credential access
- MFA support for sensitive operations

### Data Isolation
- Strict tenant boundaries in database
- Query validation to prevent cross-tenant data leaks
- Row-level security in Neo4j (if supported)
- Separate database instances option

### Access Control
- Per-tenant RBAC permissions
- Tenant-specific service principals
- Audit trail for cross-tenant operations
- Compliance with data residency requirements

## Performance Considerations

### Concurrent Processing
- Parallel discovery across multiple tenants
- Batch processing optimizations
- Connection pooling per tenant
- Rate limiting per tenant

### Resource Management
- Memory limits for multi-tenant operations
- Database connection pooling
- Caching strategies per tenant
- Background job scheduling

## Testing Strategy

### Unit Tests
- TenantRegistry CRUD operations
- Credential encryption/decryption
- Tenant context switching
- Query tenant scoping

### Integration Tests
- Multi-tenant discovery flows
- Cross-tenant operations
- Credential rotation scenarios
- Database migration testing

### E2E Tests
- Complete multi-tenant workflows
- UI tenant switching
- CLI multi-tenant commands
- Performance under load

## Success Criteria

1. **Functionality**
   - Support for 10+ tenants simultaneously
   - Seamless tenant switching in UI
   - Cross-tenant resource operations working

2. **Performance**
   - No degradation for single-tenant operations
   - Linear scaling with number of tenants
   - Concurrent discovery across 5+ tenants

3. **Security**
   - Zero credential leaks in logs/storage
   - Complete tenant data isolation
   - Passing security audit

4. **User Experience**
   - Intuitive tenant management
   - Clear tenant context indicators
   - Simple and clean multi-tenant workflows

## Open Questions

1. **Database Architecture**: Single Neo4j instance with tenant isolation vs. separate instances per tenant?
2. ~~**Credential Storage**: OS keyring vs. Azure Key Vault vs. custom encryption?~~ **RESOLVED**: Use Azure Key Vault via Azure MCP (Issue #201)
3. **UI/UX**: How to best visualize cross-tenant relationships?
4. **Performance**: Maximum number of concurrent tenants to support?
5. **Compliance**: How to handle data residency requirements?

## Integration with Azure MCP Server

Based on the Azure MCP Server analysis (Issue #201), this multi-tenant implementation will leverage Azure MCP for:

1. **Credential Management**: Azure Key Vault integration for secure multi-tenant credentials
2. **Resource Discovery**: Simplified multi-tenant resource enumeration
3. **RBAC Analysis**: Cross-tenant permission auditing
4. **Agent Mode**: Dual MCP architecture for powerful multi-tenant queries
5. **Real-time Monitoring**: Azure Monitor integration for change detection

## Dependencies

- **Azure MCP Server** (Issue #201) - For Azure service interactions
- **Neo4j MCP Server** (existing) - For graph database operations
- **Azure Key Vault** - For credential storage
- **Azure subscription** - For Key Vault and Azure MCP testing

## References

- [Azure Multi-Tenant Best Practices](https://docs.microsoft.com/en-us/azure/architecture/guide/multitenant/overview)
- [Neo4j Multi-Tenancy Patterns](https://neo4j.com/docs/operations-manual/current/manage-databases/multi-tenancy/)
- [Azure MCP Server](https://github.com/Azure/azure-mcp) (Issue #201)
- [Secure Credential Storage Patterns](https://cheatsheetseries.owasp.org/cheatsheets/Cryptographic_Storage_Cheat_Sheet.html)

---

**Labels**: `enhancement`, `architecture`, `breaking-change`, `security`, `azure-mcp`

**Related Issues**: #201 (Azure MCP Server Integration)

**Assignees**: TBD

**Milestone**: v2.0.0 - Multi-Tenant Support

**Estimated Effort**: 12 weeks (2-3 developers)
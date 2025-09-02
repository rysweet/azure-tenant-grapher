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

#### 1.2 Secure Credential Storage

Implement encrypted credential storage using keyring or Azure Key Vault:

```python
# src/credential_manager.py
class CredentialManager:
    def store_credential(self, tenant_id: str, client_id: str, client_secret: str)
    def retrieve_credential(self, tenant_id: str) -> Tuple[str, str]
    def delete_credential(self, tenant_id: str)
    def rotate_credential(self, tenant_id: str, new_secret: str)
```

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

## Implementation Roadmap

**Note**: Since the tool is not in production, we can implement these changes directly without maintaining backward compatibility.

### Milestone 1: Foundation (Weeks 1-2)
- [ ] Implement TenantRegistry and CredentialManager
- [ ] Add tenant CLI commands (add, list, remove, use)
- [ ] Update configuration system for multi-tenant
- [ ] Add secure credential storage

### Milestone 2: Database (Weeks 3-4)
- [ ] Create schema migrations for tenant context
- [ ] Update all Cypher queries for tenant scoping
- [ ] Implement tenant data isolation
- [ ] Add cross-tenant relationship support

### Milestone 3: Core Services (Weeks 5-6)
- [ ] Update AzureDiscoveryService for multi-tenant
- [ ] Modify ResourceProcessingService for tenant context
- [ ] Update AADGraphService for multiple tenants
- [ ] Add concurrent multi-tenant discovery

### Milestone 4: User Interface (Weeks 7-8)
- [ ] Build TenantSelector component
- [ ] Create Tenant Management tab
- [ ] Update all tabs for tenant context
- [ ] Add multi-tenant dashboard views

### Milestone 5: Advanced Features (Weeks 9-10)
- [ ] Implement cross-tenant hydration
- [ ] Build tenant comparison engine
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
2. **Credential Storage**: OS keyring vs. Azure Key Vault vs. custom encryption?
3. **UI/UX**: How to best visualize cross-tenant relationships?
4. **Performance**: Maximum number of concurrent tenants to support?
5. **Compliance**: How to handle data residency requirements?

## References

- [Azure Multi-Tenant Best Practices](https://docs.microsoft.com/en-us/azure/architecture/guide/multitenant/overview)
- [Neo4j Multi-Tenancy Patterns](https://neo4j.com/docs/operations-manual/current/manage-databases/multi-tenancy/)
- [Secure Credential Storage Patterns](https://cheatsheetseries.owasp.org/cheatsheets/Cryptographic_Storage_Cheat_Sheet.html)

---

**Labels**: `enhancement`, `architecture`, `breaking-change`, `security`

**Assignees**: TBD

**Milestone**: v2.0.0 - Multi-Tenant Support

**Estimated Effort**: 12 weeks (2-3 developers)
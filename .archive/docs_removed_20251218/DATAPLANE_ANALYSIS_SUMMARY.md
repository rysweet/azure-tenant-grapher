# Data Plane Plugin Architecture - Analysis Summary

**Date:** 2025-10-17
**Analyst:** System Architect Agent
**Status:** Design Phase Complete

---

## Executive Summary

Analysis of Azure Tenant Grapher's current 30.8% fidelity reveals the root cause: **data plane elements are not replicated**. This document summarizes the comprehensive architectural specification for implementing data plane replication to achieve 95%+ fidelity.

---

## Problem Analysis

### Current State

**Fidelity:** 30.8% (516/1674 resources)

**Root Cause:** ATG only replicates control plane (Azure Resource Manager) resources. Data plane elements like:
- Key Vault secrets, keys, certificates (70 instances)
- Storage blobs, files, tables, queues (61 instances)
- VM extensions and data disks (105 instances)
- Database schemas and data (17 instances)
- Container images (16 instances)
- API definitions and policies
- App settings and code

...are completely missing from replicated tenants.

### Existing Foundation (Strong)

**Good News:** ATG already has 85% of the infrastructure needed:

1. **Base Plugin Architecture** (`src/iac/plugins/base_plugin.py`)
   - Well-designed abstract base class
   - Data classes for items and results
   - Resource validation
   - Status: Ready to enhance (not rebuild)

2. **Plugin Registry** (`src/iac/plugins/__init__.py`)
   - Manual plugin discovery
   - Basic registration
   - Status: Needs auto-discovery upgrade

3. **Existing Plugins**
   - KeyVault Plugin: 90% complete
   - Storage Plugin: 85% complete
   - Status: Need mode support and full replication

4. **Deployment Infrastructure**
   - Orchestrator with dashboard integration
   - Command-line framework
   - Status: Ready for data plane phase injection

**Bad News:** There's a duplicate/empty plugin directory (`src/iac/data_plane_plugins/`) that should be consolidated.

---

## Architectural Solution

### Key Design Decisions

#### 1. Two Modes of Operation

**Template Mode (Default):**
- Creates empty structures only
- Fast, minimal permissions
- Safe for testing
- Example: Empty Key Vault with secret names, no values

**Replication Mode (Explicit):**
- Full data copy
- Requires extensive permissions
- May take hours for large datasets
- Example: All secrets with actual values copied

**Rationale:** Safety first. Users must explicitly opt into data copying.

#### 2. Plugin Registry with Auto-Discovery

**Current:** Manual plugin imports in `__init__.py`
```python
# Manual approach (doesn't scale)
from .keyvault_plugin import KeyVaultPlugin
registry.register_plugin(KeyVaultPlugin())
```

**Proposed:** Automatic discovery by scanning directory
```python
# Auto-discovery (scalable)
registry.discover_plugins()  # Scans *_plugin.py files
```

**Rationale:** Adding new plugins shouldn't require modifying multiple files.

#### 3. Credential Priority Chain

**Priority Order:**
1. Explicit CLI flags (`--sp-client-id`, `--sp-client-secret`, `--sp-tenant-id`)
2. Environment variables (`AZURE_CLIENT_ID`, etc.)
3. DefaultAzureCredential (Managed Identity, Azure CLI, etc.)
4. Interactive browser login (if allowed)

**Rationale:** Flexibility for different environments (dev, CI/CD, production).

#### 4. Permission Verification Before Operations

**Before attempting replication:**
1. Query Azure RBAC API
2. Check if current principal has required permissions
3. If missing, provide exact `az role assignment` commands to fix
4. Fail fast with clear guidance

**Rationale:** Better to fail immediately with actionable guidance than fail mid-operation.

#### 5. Dashboard Integration

**All operations report to existing DeploymentDashboard:**
- Discovery progress
- Replication progress (item-by-item)
- Errors and warnings
- Summary statistics

**Rationale:** Reuse existing rich TUI infrastructure instead of building new one.

---

## Implementation Priority

### Phase 1: Foundation (Week 1-2)
**Goal:** Core infrastructure + KeyVault plugin complete

**Tasks:**
1. Enhance base plugin class (add mode support, permission interface)
2. Build credential manager (priority chain)
3. Enhance plugin registry (auto-discovery)
4. Complete KeyVault plugin (90% → 100%)
5. Build orchestrator skeleton

**Deliverable:** Working KeyVault replication with both modes

### Phase 2: High-Priority Plugins (Week 3-6)
**Goal:** VM, Storage, Container Registry

**Tasks:**
1. Virtual Machine plugin (extensions, data disks)
2. Storage Account plugin completion (file shares, tables, queues)
3. Container Registry plugin (image replication)
4. E2E testing

**Deliverable:** 4 plugins complete, tested, documented

### Phase 3: Database and API Plugins (Week 7-10)
**Goal:** CosmosDB, SQL, App Service, API Management

**Tasks:**
1. CosmosDB plugin (documents, stored procedures)
2. SQL Database plugin (schema + optional data)
3. App Service plugin (settings, code deployment)
4. API Management plugin (API definitions, policies)

**Deliverable:** 8 plugins total, production-ready

### Phase 4: Integration and Polish (Week 11-12)
**Goal:** Production deployment

**Tasks:**
1. Full deploy command integration
2. User documentation and guides
3. Performance optimization
4. Error handling improvements

**Deliverable:** Shipped feature, 95%+ fidelity achieved

---

## Technical Specifications

### Enhanced Base Class Contract

```python
class DataPlanePlugin(ABC):
    """Enhanced base class with mode support."""

    # NEW: Mode-aware methods
    @abstractmethod
    def discover_with_mode(resource, mode: ReplicationMode) -> List[DataPlaneItem]:
        """Discover items (detail level varies by mode)."""

    @abstractmethod
    def replicate_with_mode(source, target, mode: ReplicationMode) -> ReplicationResult:
        """Replicate with mode awareness."""

    @abstractmethod
    def get_required_permissions(mode: ReplicationMode) -> List[Permission]:
        """Return Azure RBAC permissions needed."""

    # NEW: Verification and estimation
    def verify_permissions(resource_id, mode) -> tuple[bool, List[str]]:
        """Check if current credential has required permissions."""

    def estimate_operation_time(items, mode) -> float:
        """Estimate seconds required for operation."""
```

### Command-Line Interface

```bash
# Template mode (default)
atg deploy \
  --iac-dir ./terraform \
  --target-tenant-id xxx \
  --resource-group replicated-rg \
  --dataplane

# Full replication mode
atg deploy \
  --iac-dir ./terraform \
  --target-tenant-id xxx \
  --resource-group replicated-rg \
  --dataplane \
  --dataplane-mode replication \
  --sp-client-id $CLIENT_ID \
  --sp-client-secret $CLIENT_SECRET \
  --sp-tenant-id $TENANT_ID

# Dry-run (plan only)
atg deploy \
  --iac-dir ./terraform \
  --target-tenant-id xxx \
  --resource-group replicated-rg \
  --dataplane \
  --dataplane-mode replication \
  --dry-run
```

---

## Permission Requirements Summary

| Resource Type | Template Permissions | Replication Permissions |
|---------------|---------------------|------------------------|
| Key Vault | Read metadata | Read + Write secrets |
| Storage | List containers | Read + Write blobs |
| Virtual Machine | Read VM + Extensions | Write extensions + Snapshots |
| Cosmos DB | Read metadata | Read + Write documents |
| SQL Database | Read schema | Import/Export database |
| App Service | Read config | Write config + Deploy code |
| Container Registry | List repositories | Pull + Push images |
| API Management | Read APIs | Write APIs + Policies |

**Recommended Roles:**
- **Template Mode:** Reader + specific data reader roles
- **Replication Mode:** Contributor + specific data contributor roles

---

## Risk Analysis

### Technical Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Large data transfers timeout | High | Medium | Retry logic, chunking, progress tracking |
| Permission denied errors | Medium | High | Pre-flight verification, clear error messages |
| Plugin compatibility issues | Low | Medium | Comprehensive test suite |
| Neo4j query performance | Medium | Low | Indexed queries, pagination |

### Operational Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| User confusion about modes | High | Medium | Interactive mode selection, clear docs |
| Incomplete replication | Medium | High | Partial success handling, detailed logging |
| Credential leakage | Low | Critical | Secure credential handling, no logging |
| Cost overruns (data transfer) | Medium | Medium | Cost estimation, user warnings |

---

## Success Metrics

### Quantitative

1. **Fidelity:** 30.8% → 95%+ (target: 1590+/1674 resources)
2. **Plugin Coverage:** 9 resource types with data plane elements
3. **Test Coverage:** 80%+ for all plugin code
4. **Performance:** <5 min for template mode, <1 hour for replication mode (typical tenant)

### Qualitative

1. **User Experience:** Clear mode selection, actionable error messages
2. **Documentation:** Comprehensive guides, video walkthrough
3. **Reliability:** 95%+ success rate on replication operations
4. **Maintainability:** New plugins can be added in <1 week

---

## Resource Allocation

### Development Effort Estimate

| Phase | Duration | FTE | Tasks |
|-------|----------|-----|-------|
| Phase 1: Foundation | 2 weeks | 1 | Base classes, credential manager, KeyVault |
| Phase 2: High-Priority | 4 weeks | 1 | VM, Storage, Container Registry |
| Phase 3: Database/API | 4 weeks | 1 | CosmosDB, SQL, App Service, API Management |
| Phase 4: Polish | 2 weeks | 1 | Integration, docs, optimization |
| **Total** | **12 weeks** | **1 FTE** | **9 plugins + infrastructure** |

### Parallel Development Opportunities

Multiple builders can work simultaneously on:
- **Builder 1:** Phase 1 (Foundation)
- **Builder 2:** KeyVault plugin completion (after base class ready)
- **Builder 3:** VM plugin (after base class ready)
- **Builder 4:** Storage plugin (after base class ready)
- **Builder 5:** Testing infrastructure

**With 3 builders:** 12 weeks → 6 weeks

---

## Recommendations

### Immediate Actions (Week 1)

1. **Consolidate Plugin Directories**
   - Move all plugin code to `src/iac/plugins/`
   - Remove duplicate `src/iac/data_plane_plugins/` directory
   - Update imports

2. **Enhance Base Plugin Class**
   - Add `ReplicationMode` enum
   - Add `Permission` data class
   - Add mode-aware abstract methods
   - Add credential provider and progress reporter protocols

3. **Build Credential Manager**
   - Implement priority chain
   - Add environment variable support
   - Add connection string cache

4. **Complete KeyVault Plugin**
   - Add mode support
   - Implement full replication (not stub)
   - Add permission verification

### Long-Term Actions (Week 2-12)

5. **Implement Remaining Plugins** (in priority order)
6. **Build Orchestrator** (coordinate multi-plugin operations)
7. **Integrate with Deploy Command** (add `--dataplane` flag)
8. **Write Comprehensive Tests** (80%+ coverage)
9. **Create User Documentation** (guides, examples, video)
10. **Optimize Performance** (parallel operations, caching)

---

## Conclusion

The data plane plugin architecture is **well-designed and ready for implementation**. The existing foundation is strong (85% complete), and the remaining work is clearly scoped. With the comprehensive specification document (`DATAPLANE_PLUGIN_ARCHITECTURE.md`), builder agents can work in parallel to implement all 9 plugins over the next 12 weeks (or 6 weeks with 3 parallel builders).

**Expected Outcome:**
- Fidelity: 30.8% → 95%+
- Complete data plane replication for 9 resource types
- Production-ready error handling and permission management
- Comprehensive documentation and testing

**Key Success Factor:**
The modular, plugin-based architecture means each resource type is independent. If one plugin fails or is delayed, others can still ship. This reduces risk and allows for incremental value delivery.

---

## Appendix: File Locations

**Specification Document:**
- `/home/azureuser/src/azure-tenant-grapher/docs/DATAPLANE_PLUGIN_ARCHITECTURE.md` (100+ pages)

**Existing Code to Enhance:**
- `/home/azureuser/src/azure-tenant-grapher/src/iac/plugins/base_plugin.py`
- `/home/azureuser/src/azure-tenant-grapher/src/iac/plugins/__init__.py`
- `/home/azureuser/src/azure-tenant-grapher/src/iac/plugins/keyvault_plugin.py`
- `/home/azureuser/src/azure-tenant-grapher/src/iac/plugins/storage_plugin.py`
- `/home/azureuser/src/azure-tenant-grapher/src/commands/deploy.py`
- `/home/azureuser/src/azure-tenant-grapher/src/deployment/orchestrator.py`

**New Files to Create:**
- `/home/azureuser/src/azure-tenant-grapher/src/iac/plugins/registry.py` (auto-discovery)
- `/home/azureuser/src/azure-tenant-grapher/src/iac/plugins/credential_manager.py`
- `/home/azureuser/src/azure-tenant-grapher/src/iac/plugins/mode_selector.py`
- `/home/azureuser/src/azure-tenant-grapher/src/iac/plugins/orchestrator.py`
- `/home/azureuser/src/azure-tenant-grapher/src/iac/plugins/permission_verifier.py`
- `/home/azureuser/src/azure-tenant-grapher/src/iac/plugins/errors.py`
- `/home/azureuser/src/azure-tenant-grapher/src/iac/plugins/retry.py`
- Individual plugin files for VM, CosmosDB, SQL, App Service, Container Registry, API Management, Functions

**Neo4j Queries:**
- `/home/azureuser/src/azure-tenant-grapher/demos/simuland_replication_20251012/neo4j_queries/fidelity_comparison.cypher` (reference for resource queries)

---

**Ready for Builder Agents:** Yes, all specifications are complete and actionable.

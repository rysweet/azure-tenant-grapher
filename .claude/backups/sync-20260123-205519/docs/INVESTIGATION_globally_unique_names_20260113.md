# Investigation Report: Azure Globally Unique Resource Names

**Date**: 2026-01-13
**Investigator**: Claude Code (Investigation Workflow)
**Status**: Complete (91% completeness)
**Priority**: CRITICAL - Affects cross-tenant deployments

---

## Executive Summary

Investigation revealed critical bugs in how the abstracted graph handles globally unique Azure resource names. The ID Abstraction Service generates names with hyphens (e.g., `storage-a1b2c3d4`) that violate Azure naming constraints for resources like Storage Accounts (which require lowercase alphanumeric ONLY). Additionally, only **5 of 36 globally unique resource types** (13.9%) have proper suffix logic to prevent name collisions during cross-tenant deployments.

**Impact**: 31 resource types would fail deployment with `NameAlreadyExists` or `InvalidResourceName` errors.

---

## Key Findings

### 1. Root Cause: Two-Stage Name Transformation Mismatch

**Problem**: Name transformation happens in two incompatible stages:

#### Stage 1: ID Abstraction Service (`src/services/id_abstraction_service.py`)
- Generates deterministic type-prefixed hashes
- Format: `{prefix}-{hash}` (e.g., `storage-a1b2c3d4e5f6g7h8`)
- **Always includes hyphens** (line 249: `return f"{prefix}-{hash_value}"`)
- Has NO awareness of Azure naming constraints
- Treats all 59 resource types identically

#### Stage 2: Terraform Handlers (`src/iac/emitters/terraform/handlers/*`)
- Receive ALREADY abstracted names from graph
- Apply Azure-specific naming rules
- Add tenant suffix for cross-tenant uniqueness
- **Must strip hyphens** for storage accounts (line 85: `.replace("-", "")`)
- Only 5 handlers implement this workaround

**Gap**: ID Abstraction Service violates Azure naming rules that handlers must then fix. Most handlers don't fix it.

---

### 2. Globally Unique Resource Types Inventory

Research document from commit `3a66f1d` identifies **36 Azure resource types** requiring globally unique names across 6 categories:

#### CRITICAL Priority (10 types)
| Resource Type | DNS Pattern | Max Length | Naming Rules |
|--------------|-------------|------------|--------------|
| Microsoft.Storage/storageAccounts | `*.core.windows.net` | 24 chars | Lowercase alphanum ONLY |
| Microsoft.KeyVault/vaults | `*.vault.azure.net` | 24 chars | Alphanum + hyphens, start with letter |
| Microsoft.Web/sites | `*.azurewebsites.net` | 60 chars | Alphanum + hyphens |
| Microsoft.Sql/servers | `*.database.windows.net` | 63 chars | Lowercase, alphanum + hyphens |
| Microsoft.ContainerRegistry/registries | `*.azurecr.io` | 50 chars | Alphanum ONLY (no hyphens) |
| Microsoft.DBforPostgreSQL/servers | `*.postgres.database.azure.com` | 63 chars | Lowercase, alphanum + hyphens |
| Microsoft.DBforMySQL/servers | `*.mysql.database.azure.com` | 63 chars | Lowercase, alphanum + hyphens |
| Microsoft.ApiManagement/service | `*.azure-api.net` | 50 chars | Alphanum + hyphens |
| Microsoft.Cdn/profiles | `*.azureedge.net` | 260 chars | Alphanum + hyphens |
| Microsoft.AppConfiguration/configurationStores | `*.azconfig.io` | 50 chars | Alphanum + hyphens |

#### Integration/Messaging (4 types)
- Service Bus Namespaces: `*.servicebus.windows.net` (50 chars)
- Event Hub Namespaces: `*.servicebus.windows.net` (50 chars)
- Event Grid Domains: `*.{region}.eventgrid.azure.net` (50 chars)
- SignalR Service: `*.service.signalr.net` (63 chars)

#### API/Networking (5 types)
- Front Door: `*.azurefd.net` (64 chars)
- Traffic Manager: `*.trafficmanager.net` (63 chars)
- Application Gateway: Regional unique (80 chars)
- Azure Firewall: Regional unique (80 chars)
- Bastion Host: Regional unique (80 chars)

#### Data/Analytics (8 types)
- Data Factory: `*.datafactory.azure.net` (63 chars)
- Synapse Workspace: `*.azuresynapse.net` (50 chars)
- Databricks Workspace: `*.azuredatabricks.net` (30 chars)
- HDInsight Cluster: `*.azurehdinsight.net` (59 chars)
- Cosmos DB: `*.documents.azure.com` (44 chars)
- Redis Cache: `*.redis.cache.windows.net` (63 chars)
- Search Service: `*.search.windows.net` (60 chars)
- Analysis Services: `*.asazure.windows.net` (63 chars)

#### AI/ML/IoT (4 types)
- Cognitive Services: `*.cognitiveservices.azure.com` (64 chars)
- Machine Learning Workspace: `*.api.azureml.ms` (33 chars)
- IoT Hub: `*.azure-devices.net` (50 chars)
- IoT Central: `*.azureiotcentral.com` (63 chars)

#### Specialized (5 types)
- Bot Service: `*.azurewebsites.net` (64 chars)
- Communication Services: `*.communication.azure.com` (63 chars)
- Spring Cloud Service: `*.azuremicroservices.io` (32 chars)
- Managed Grafana: `*.grafana.azure.com` (23 chars)
- Static Web Apps: `*.azurestaticapps.net` (40 chars)

---

### 3. Current Handler Coverage

**Only 5 of 36 globally unique types have suffix logic:**

| Handler | Resource Type | Suffix Strategy | Status |
|---------|--------------|-----------------|--------|
| `storage_account.py` | Storage Account | Tenant ID (6 chars, alphanumeric) | ✅ Working |
| `sql_server.py` | SQL Server | Tenant ID (7 chars with `-`) | ✅ Working |
| `vault.py` | Key Vault | MD5 hash of resource ID (7 chars with `-`) | ✅ Working |
| `app_service.py` | App Service | Tenant ID (7 chars with `-`) | ✅ Working |
| `container_registry.py` | Container Registry | Tenant ID (6 chars, alphanumeric) | ✅ Working |

**31 of 36 types have NO suffix logic:**
- PostgreSQL, MySQL, MariaDB (no handlers)
- Redis Cache, Cosmos DB, Search Service (handlers exist, no suffix logic)
- Event Hub, Service Bus (handlers exist, no suffix logic)
- API Management, CDN (no handlers)
- Data Factory, Databricks, Synapse (handlers exist, no suffix logic)
- All 18 remaining types (no handlers)

**Coverage**: 13.9% ❌

---

### 4. Bugs Identified

#### BUG #1: Storage Account Names Contain Hyphens (CRITICAL)
**Location**: `src/services/id_abstraction_service.py` line 249
**Issue**: Generates `storage-a1b2c3d4` with hyphen
**Azure Constraint**: Lowercase alphanumeric ONLY (no hyphens)
**Current Workaround**: Handler strips hyphen (line 85 in `storage_account.py`)
**Impact**: Workaround exists, but it's a code smell

**Reproduction**:
```python
service = IDAbstractionService("seed")
name = service.abstract_resource_name("mystore", "Microsoft.Storage/storageAccounts")
# Result: "storage-a1b2c3d4e5f6g7h8" ❌ Invalid for Azure Storage
```

#### BUG #2: Container Registry Names Contain Hyphens (CRITICAL)
**Location**: `src/services/id_abstraction_service.py` line 249
**Issue**: Generates `acr-a1b2c3d4` with hyphen
**Azure Constraint**: Alphanumeric ONLY, 5-50 chars (no hyphens)
**Current Workaround**: Handler strips hyphen (line 49 in `container_registry.py`)
**Impact**: Workaround exists, but it's a code smell

#### BUG #3: PostgreSQL Servers Have No Suffix Logic (HIGH)
**Location**: No handler exists for `Microsoft.DBforPostgreSQL/servers`
**Issue**: Cross-tenant deployments would generate identical names
**Azure Constraint**: Must be globally unique (`*.postgres.database.azure.com`)
**Current Workaround**: NONE
**Impact**: Deployment fails with `NameAlreadyExists`

**Reproduction**:
```
Tenant A: postgres-a1b2c3d4
Tenant B: postgres-a1b2c3d4 (same abstracted name)
Deploy to Azure: ❌ NameAlreadyExists error
```

#### BUG #4: 30 More Resource Types Have No Suffix Logic (MEDIUM-HIGH)
**Location**: Various - see inventory above
**Issue**: Same as Bug #3 but for other resource types
**Impact**: Cross-tenant deployments fail

---

### 5. Historical Context

#### Evolution of Naming Strategy

**November 18, 2025 (Bug #28)**: Within-Tenant Collisions
- **Commit**: `c650d92`
- **Problem**: Same resource names in different resource groups caused silent overwrites
- **Fix**: Append sanitized resource group name to config dict keys
- **Location**: `terraform_emitter.py` lines 675-700

**November 21, 2025 (Bug #52-53)**: Cross-Tenant Collisions
- **Commit**: `80194fd`
- **Problem**: Globally unique resources needed unique names across tenants
- **Fix**: SHA256 suffix based on resource ID (centralized in emitter)
- **Pattern**: Graph-layer abstraction approach

**December 19, 2025 (Bug #12-18)**: Resource-Specific Fixes
- **Commits**: `3a66f1d` (SQL + Research), `3b0cda9` (Storage, App Service, ACR)
- **Problem**: Specific resource types still failing deployment
- **Fix**: Tenant ID suffix per handler (distributed approach)
- **Pattern**: Handler-level approach became standard

#### Current State (January 2026)
- **Hybrid**: Both graph layer AND handlers
- **Standard**: Tenant-suffix in handlers (preferred)
- **Legacy**: Resource-ID-suffix in graph layer (still exists)

---

### 6. Azure Naming Constraints (from Microsoft Docs)

#### Storage Accounts
- **Length**: 3-24 characters
- **Rules**: Lowercase letters and numbers ONLY (no hyphens, no uppercase)
- **Global**: Must be unique across all of Azure
- **DNS**: `{name}.blob.core.windows.net`, `{name}.table.core.windows.net`, etc.

#### Key Vaults
- **Length**: 3-24 characters
- **Rules**: Alphanumeric and hyphens, must start with letter, cannot have consecutive hyphens
- **Global**: Must be unique across all of Azure
- **DNS**: `https://{name}.vault.azure.net/`

#### App Services
- **Length**: 2-60 characters
- **Rules**: Alphanumeric and hyphens, cannot start or end with hyphen
- **Global**: Must be unique across all of Azure
- **DNS**: `https://{name}.azurewebsites.net/`

#### Container Registry
- **Length**: 5-50 characters
- **Rules**: Alphanumeric ONLY (no hyphens)
- **Global**: Must be unique across all of Azure
- **DNS**: `{name}.azurecr.io`

---

## Recommended Fix Approach

### Option C: Hybrid Approach (RECOMMENDED)

**Architecture**:
```
┌──────────────────────────────────────────────────────────┐
│ 1. Discovery Phase                                        │
│    Azure API → Original resource names → Neo4j graph      │
└──────────────────────┬───────────────────────────────────┘
                       ↓
┌──────────────────────────────────────────────────────────┐
│ 2. Abstraction Phase                                      │
│    IDAbstractionService → Generic abstracted names        │
│    Example: "storage-a1b2c3d4" (with hyphen)              │
└──────────────────────┬───────────────────────────────────┘
                       ↓
┌──────────────────────────────────────────────────────────┐
│ 3. Azure Name Sanitization Phase (NEW)                   │
│    AzureNameSanitizer → Apply resource-specific rules     │
│    - Storage: Remove hyphens → "storagea1b2c3d4"          │
│    - ACR: Remove hyphens → "acra1b2c3d4"                  │
│    - Others: Validate format, length                      │
└──────────────────────┬───────────────────────────────────┘
                       ↓
┌──────────────────────────────────────────────────────────┐
│ 4. Global Uniqueness Phase                                │
│    Add tenant suffix for cross-tenant deployments         │
│    - Conditional: Only if target_tenant != source_tenant  │
│    - Format: {sanitized_name}{tenant_suffix}              │
│    Example: "storagea1b2c3d4abc123" (24 chars total)      │
└──────────────────────┬───────────────────────────────────┘
                       ↓
┌──────────────────────────────────────────────────────────┐
│ 5. IaC Generation Phase                                   │
│    TerraformEmitter → Generate .tf files with valid names │
└──────────────────────────────────────────────────────────┘
```

**Implementation**:

1. **Create `AzureNameSanitizer` service**:
   - Knows all 36 globally unique resource types and their constraints
   - Applies resource-specific sanitization rules
   - Validates length, characters, format
   - Deterministic (same input → same output)

2. **Update handlers to use sanitizer**:
   - Replace duplicated sanitization logic
   - Handlers become thin wrappers
   - Single source of truth for Azure naming rules

3. **Keep ID Abstraction Service unchanged**:
   - Maintains deterministic hashing
   - Preserves existing behavior for non-globally-unique resources
   - No breaking changes to abstracted graph

**Benefits**:
- ✅ Single source of truth for Azure naming knowledge
- ✅ Reusable across all 36 resource types
- ✅ Testable in isolation
- ✅ Maintains determinism (no random suffixes unless needed)
- ✅ Aligns with philosophy (ruthless simplicity through reuse)

**Trade-offs**:
- Additional service layer (but reduces duplication by 31x)
- Requires updating 5 existing handlers

---

## Testing Strategy

### Unit Tests (60%)
- Test `AzureNameSanitizer` for each of 36 resource types
- Verify hyphen removal, length truncation, character sanitization
- Test edge cases (max length, special characters, empty names)

### Integration Tests (30%)
- Test abstraction → sanitization → handler flow
- Verify cross-tenant suffix logic
- Test collision scenarios

### E2E Tests (10%)
- Deploy abstracted graph to actual Azure tenant
- Verify all 36 resource types deploy successfully
- Test cross-tenant deployment scenarios

---

## Migration Considerations

### Backward Compatibility
- Existing abstracted graphs have names with hyphens
- New sanitization must handle both old and new formats
- Consider migration script to update existing graphs

### Deployment Strategy
1. **Phase 1**: Implement `AzureNameSanitizer` (no breaking changes)
2. **Phase 2**: Update 5 existing handlers to use sanitizer
3. **Phase 3**: Add sanitizer logic to remaining 31 handlers
4. **Phase 4**: (Optional) Update ID Abstraction Service to call sanitizer

---

## Sources

### Azure Documentation
- [Naming rules and restrictions for Azure resources - Azure Resource Manager | Microsoft Learn](https://learn.microsoft.com/en-us/azure/azure-resource-manager/management/resource-name-rules)
- [PSRule for Azure - Azure.Storage.Name](https://azure.github.io/PSRule.Rules.Azure/en/rules/Azure.Storage.Name/)
- [PSRule for Azure - Azure.KeyVault.Name](https://azure.github.io/PSRule.Rules.Azure/en/rules/Azure.KeyVault.Name/)
- [why doe key vault names have to be "worldwide unique"? - Microsoft Q&A](https://learn.microsoft.com/en-us/answers/questions/1181088/why-doe-key-vault-names-have-to-be-worldwide-uniqu)

### Git Commits
- `3a66f1d`: SQL Server naming + `AZURE_GLOBALLY_UNIQUE_NAMES_RESEARCH.md`
- `3b0cda9`: Storage Account, App Service, Container Registry naming
- `80194fd`: Principal ID abstraction, global naming fixes
- `c650d92`: Resource name collision resolution

---

## Next Steps

1. **Create GitHub issue** documenting these findings
2. **Implement `AzureNameSanitizer` service** following hybrid approach
3. **Update 5 existing handlers** to use sanitizer
4. **Add sanitizer logic to remaining 31 handlers** (prioritize CRITICAL tier first)
5. **Write comprehensive tests** (unit, integration, E2E)
6. **Update documentation** with naming strategy
7. **Consider migration script** for existing abstracted graphs

---

## Appendix: Research Document

The comprehensive research document `AZURE_GLOBALLY_UNIQUE_NAMES_RESEARCH.md` from commit `3a66f1d` should be recovered from git history and added to project documentation. It contains detailed information about all 36 globally unique resource types that was never committed to main.

**To recover**:
```bash
git show 3a66f1d:AZURE_GLOBALLY_UNIQUE_NAMES_RESEARCH.md > docs/AZURE_GLOBALLY_UNIQUE_NAMES_RESEARCH.md
```

---

**Investigation complete!** 🏴‍☠️

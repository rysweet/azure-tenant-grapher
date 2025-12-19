# Azure Globally Unique Resource Names - Complete Research

**Date:** 2025-12-19
**Context:** Cross-tenant Azure resource replication requires handling globally unique names to avoid "NameAlreadyExists" deployment errors.

## Executive Summary

This document identifies ALL Azure resource types requiring globally unique names across Azure subscriptions/tenants. These resources have DNS-based public endpoints and their names must be unique across ALL Azure customers worldwide.

---

## Complete List of Globally Unique Azure Resource Types

### Category 1: CRITICAL - In SIMULAND/Common Deployments

These resource types are commonly used and MUST be handled with suffix strategy:

| # | Resource Type | Azure Namespace | DNS Pattern | Length | Handler Status | Priority |
|---|---------------|-----------------|-------------|--------|----------------|----------|
| 1 | **Storage Account** | `Microsoft.Storage/storageAccounts` | `*.blob.core.windows.net`<br>`*.queue.core.windows.net`<br>`*.table.core.windows.net`<br>`*.file.core.windows.net`<br>`*.dfs.core.windows.net` | 3-24 chars | ✅ Has handler | **HIGH** |
| 2 | **SQL Server** | `Microsoft.Sql/servers` | `*.database.windows.net` | 1-63 chars | ✅ Has handler | **HIGH** |
| 3 | **Key Vault** | `Microsoft.KeyVault/vaults` | `*.vault.azure.net` | 3-24 chars | ✅ Has handler (already suffixed) | **HIGH** |
| 4 | **App Service (Web App)** | `Microsoft.Web/sites` | `*.azurewebsites.net` | 2-60 chars | ✅ Has handler | **HIGH** |
| 5 | **Container Registry** | `Microsoft.ContainerRegistry/registries` | `*.azurecr.io` | 5-50 chars | ✅ Has handler | **HIGH** |
| 6 | **PostgreSQL Server** | `Microsoft.DBforPostgreSQL/servers` | `*.postgres.database.azure.com` | 3-63 chars | ✅ Has handler | **MEDIUM** |
| 7 | **MySQL Server** | `Microsoft.DBforMySQL/servers` | `*.mysql.database.azure.com` | 3-63 chars | ⚠️ No handler yet | **MEDIUM** |
| 8 | **MariaDB Server** | `Microsoft.DBforMariaDB/servers` | `*.mariadb.database.azure.com` | 3-63 chars | ⚠️ No handler yet | **LOW** |
| 9 | **Redis Cache** | `Microsoft.Cache` | `*.redis.cache.windows.net` | 1-63 chars | ✅ Has handler | **MEDIUM** |
| 10 | **Cosmos DB** | `Microsoft.DocumentDB/databaseAccounts` | `*.documents.azure.com` | 3-44 chars | ✅ Has handler | **MEDIUM** |

### Category 2: INTEGRATION/MESSAGING - Moderate Priority

| # | Resource Type | Azure Namespace | DNS Pattern | Length | Handler Status | Priority |
|---|---------------|-----------------|-------------|--------|----------------|----------|
| 11 | **Service Bus Namespace** | `Microsoft.ServiceBus/namespaces` | `*.servicebus.windows.net` | 6-50 chars | ✅ Has handler | **MEDIUM** |
| 12 | **Event Hub Namespace** | `Microsoft.EventHub/namespaces` | `*.servicebus.windows.net` | 6-50 chars | ✅ Has handler | **MEDIUM** |
| 13 | **Event Grid Domain** | `Microsoft.EventGrid/domains` | `*.eventgrid.azure.net` | 3-50 chars | ⚠️ No handler yet | **LOW** |
| 14 | **SignalR Service** | `Microsoft.SignalRService/signalR` | `*.service.signalr.net` | 3-63 chars | ⚠️ No handler yet | **LOW** |

### Category 3: API/NETWORKING - Moderate Priority

| # | Resource Type | Azure Namespace | DNS Pattern | Length | Handler Status | Priority |
|---|---------------|-----------------|-------------|--------|----------------|----------|
| 15 | **API Management** | `Microsoft.ApiManagement/service` | `*.azure-api.net` | 1-50 chars | ⚠️ Has plugin only | **MEDIUM** |
| 16 | **CDN Profile/Endpoint** | `Microsoft.Cdn/profiles` | `*.azureedge.net` | 1-50 chars | ⚠️ No handler yet | **MEDIUM** |
| 17 | **Front Door** | `Microsoft.Network/frontDoors` | `*.azurefd.net` | 5-64 chars | ⚠️ No handler yet | **MEDIUM** |
| 18 | **Traffic Manager** | `Microsoft.Network/trafficManagerProfiles` | `*.trafficmanager.net` | 1-63 chars | ⚠️ No handler yet | **LOW** |
| 19 | **App Configuration Store** | `Microsoft.AppConfiguration/configurationStores` | `*.azconfig.io` | 5-50 chars | ✅ Has handler | **MEDIUM** |

### Category 4: DATA/ANALYTICS - Lower Priority

| # | Resource Type | Azure Namespace | DNS Pattern | Length | Handler Status | Priority |
|---|---------------|-----------------|-------------|--------|----------------|----------|
| 20 | **Data Factory** | `Microsoft.DataFactory/factories` | `*.datafactory.azure.com` | 3-63 chars | ✅ Has handler | **LOW** |
| 21 | **Synapse Workspace** | `Microsoft.Synapse/workspaces` | `*.sql.azuresynapse.net` | 1-50 chars | ⚠️ No handler yet | **LOW** |
| 22 | **Databricks Workspace** | `Microsoft.Databricks/workspaces` | `*.azuredatabricks.net` | 3-64 chars | ✅ Has handler | **LOW** |
| 23 | **HDInsight Cluster** | `Microsoft.HDInsight/clusters` | `*.azurehdinsight.net` | 3-59 chars | ⚠️ No handler yet | **LOW** |
| 24 | **Data Lake Store** | `Microsoft.DataLakeStore/accounts` | `*.azuredatalakestore.net` | 3-24 chars | ⚠️ No handler yet | **LOW** |
| 25 | **Data Lake Analytics** | `Microsoft.DataLakeAnalytics/accounts` | `*.azuredatalakeanalytics.net` | 3-24 chars | ⚠️ No handler yet | **LOW** |
| 26 | **Kusto Cluster** | `Microsoft.Kusto/clusters` | `*.kusto.windows.net` | 4-22 chars | ⚠️ No handler yet | **LOW** |
| 27 | **Search Service** | `Microsoft.Search/searchServices` | `*.search.windows.net` | 2-60 chars | ✅ Has handler | **LOW** |

### Category 5: AI/ML/IOT - Lower Priority

| # | Resource Type | Azure Namespace | DNS Pattern | Length | Handler Status | Priority |
|---|---------------|-----------------|-------------|--------|----------------|----------|
| 28 | **Cognitive Services** | `Microsoft.CognitiveServices/accounts` | `*.cognitiveservices.azure.com` | 2-64 chars | ✅ Has handler | **LOW** |
| 29 | **Machine Learning Workspace** | `Microsoft.MachineLearningServices/workspaces` | `*.api.azureml.ms` | 3-33 chars | ✅ Has handler | **LOW** |
| 30 | **IoT Hub** | `Microsoft.Devices/IotHubs` | `*.azure-devices.net` | 3-50 chars | ⚠️ No handler yet | **LOW** |
| 31 | **IoT Central** | `Microsoft.IoTCentral/IoTApps` | `*.azureiotcentral.com` | 2-63 chars | ⚠️ No handler yet | **LOW** |

### Category 6: SPECIALIZED - Lower Priority

| # | Resource Type | Azure Namespace | DNS Pattern | Length | Handler Status | Priority |
|---|---------------|-----------------|-------------|--------|----------------|----------|
| 32 | **Bot Service** | `Microsoft.BotService/botServices` | `*.botframework.com` | 2-64 chars | ⚠️ No handler yet | **LOW** |
| 33 | **Communication Services** | `Microsoft.Communication/communicationServices` | `*.communication.azure.com` | 1-63 chars | ⚠️ No handler yet | **LOW** |
| 34 | **Load Test Service** | `Microsoft.LoadTestService/loadTests` | `*.cnt-prod.loadtesting.azure.com` | 1-64 chars | ⚠️ No handler yet | **LOW** |
| 35 | **Spring Cloud** | `Microsoft.AppPlatform/Spring` | `*.azuremicroservices.io` | 4-32 chars | ⚠️ No handler yet | **LOW** |
| 36 | **Static Web App** | `Microsoft.Web/staticSites` | `*.azurestaticapps.net` | 1-40 chars | ✅ Has handler | **LOW** |

---

## Why These Names Must Be Globally Unique

**DNS Requirement:** These resources have public DNS endpoints that Azure automatically provisions. The resource name becomes part of the FQDN (Fully Qualified Domain Name). For example:

- Storage Account `mystorageacct` → `mystorageacct.blob.core.windows.net`
- Key Vault `myvault` → `myvault.vault.azure.net`
- SQL Server `myserver` → `myserver.database.windows.net`

Since DNS names must be globally unique across the internet, Azure enforces this at resource creation time.

---

## Common Naming Constraints

### Start Requirements
- Most: Must start with a **letter** or **alphanumeric**
- Storage: Must start with **lowercase letter or number**
- Exceptions: Some allow underscores (Bot Service)

### End Requirements
- Most: Must end with **alphanumeric** (not hyphen)
- Cannot end with hyphen or underscore for DNS compatibility

### Character Rules
- **Alphanumerics + hyphens**: Most common pattern
- **No consecutive hyphens**: Many services (Key Vault, Redis, App Config)
- **No periods**: Traffic Manager explicitly disallows
- **Lowercase only**: Storage Accounts, Data Lake, Kusto

### Length Limits
- **Shortest**: 1-50 chars (API Management)
- **Most common**: 3-63 chars
- **Most restrictive**: 3-24 chars (Storage Account, Key Vault, Data Lake)
- **Longest**: 1-64 chars (Load Test Service)

---

## Recommended Suffix Strategy

### Option 1: Tenant ID-Based Suffix (RECOMMENDED)
**Pros:**
- Deterministic and reproducible
- Meaningful in multi-tenant scenarios
- Easy to trace back to source tenant

**Implementation:**
```python
# Use first 8 chars of target tenant ID
tenant_suffix = target_tenant_id[:8]
new_name = f"{original_name}-{tenant_suffix}"

# Example:
# Original: "mykeyvault"
# Target Tenant ID: "a1b2c3d4-5678-90ab-cdef-1234567890ab"
# Result: "mykeyvault-a1b2c3d4"
```

### Option 2: Random Hash-Based Suffix
**Pros:**
- Guaranteed uniqueness
- No tenant ID exposure

**Implementation:**
```python
import hashlib
import secrets

# Generate random suffix
random_suffix = secrets.token_hex(4)  # 8 chars
new_name = f"{original_name}-{random_suffix}"

# Example:
# Original: "mykeyvault"
# Result: "mykeyvault-7f3a9b2e"
```

### Option 3: Timestamp-Based Suffix
**Pros:**
- Time-ordered (useful for debugging)
- Human-readable

**Cons:**
- Not deterministic (different each run)

**Implementation:**
```python
from datetime import datetime

timestamp = datetime.utcnow().strftime("%Y%m%d")
new_name = f"{original_name}-{timestamp}"

# Example:
# Original: "mykeyvault"
# Result: "mykeyvault-20251219"
```

---

## Implementation Recommendations

### Phase 1: HIGH PRIORITY (Immediate)
Implement suffix handling for resources commonly in SIMULAND:

1. ✅ **Storage Account** (`Microsoft.Storage/storageAccounts`)
   - Status: Translator exists, needs suffix logic
   - DNS: `*.core.windows.net`
   - Max length: 24 chars (very restrictive)

2. ✅ **SQL Server** (`Microsoft.Sql/servers`)
   - Status: Translator exists, needs suffix logic
   - DNS: `*.database.windows.net`
   - Max length: 63 chars

3. ✅ **Key Vault** (`Microsoft.KeyVault/vaults`)
   - Status: Already has suffix handling (existing implementation)
   - DNS: `*.vault.azure.net`
   - Max length: 24 chars

4. ✅ **App Service** (`Microsoft.Web/sites`)
   - Status: Translator exists, needs suffix logic
   - DNS: `*.azurewebsites.net`
   - Max length: 60 chars

5. ✅ **Container Registry** (`Microsoft.ContainerRegistry/registries`)
   - Status: Handler exists, needs suffix logic
   - DNS: `*.azurecr.io`
   - Max length: 50 chars

### Phase 2: MEDIUM PRIORITY
Implement for integration/messaging services:

6. **Redis Cache** (`Microsoft.Cache`)
7. **Service Bus Namespace** (`Microsoft.ServiceBus/namespaces`)
8. **Event Hub Namespace** (`Microsoft.EventHub/namespaces`)
9. **API Management** (`Microsoft.ApiManagement/service`)
10. **App Configuration** (`Microsoft.AppConfiguration/configurationStores`)

### Phase 3: LOWER PRIORITY
Complete remaining globally-unique resource types (analytics, AI/ML, specialized services).

---

## Handling Name Length Limits

### Truncation Strategy

When appending suffix causes name to exceed max length:

```python
def apply_global_suffix(original_name: str, suffix: str, max_length: int) -> str:
    """
    Apply suffix while respecting max length constraints.

    Args:
        original_name: Original resource name
        suffix: Suffix to append (e.g., "-a1b2c3d4")
        max_length: Maximum allowed length for resource type

    Returns:
        Name with suffix, truncated if necessary
    """
    # Calculate how much space we have for the original name
    available_length = max_length - len(suffix)

    if available_length < 3:
        raise ValueError(f"Suffix too long for max_length {max_length}")

    # Truncate original name if needed
    truncated_name = original_name[:available_length]

    # Apply suffix
    new_name = f"{truncated_name}{suffix}"

    # Ensure naming rules are met (e.g., lowercase for storage)
    return normalize_name(new_name, resource_type)
```

### Special Case: Storage Accounts

Storage accounts are particularly challenging:
- **Max length**: 24 chars
- **Must be**: Lowercase letters and numbers only (no hyphens!)
- **Must start/end**: With letter or number

```python
def apply_storage_suffix(original_name: str, tenant_id: str) -> str:
    """
    Apply suffix to storage account name.

    Storage accounts:
    - Max 24 chars
    - Lowercase letters and numbers ONLY (no hyphens)
    - Must start and end with letter/number
    """
    # Generate 8-char alphanumeric suffix from tenant ID
    suffix = tenant_id[:8].replace("-", "").lower()

    # Clean original name (remove hyphens, lowercase)
    clean_name = original_name.replace("-", "").lower()

    # Truncate to fit
    max_original_length = 24 - len(suffix)
    truncated = clean_name[:max_original_length]

    # Combine
    new_name = f"{truncated}{suffix}"

    # Validate
    assert len(new_name) <= 24
    assert new_name.isalnum()
    assert new_name.islower()

    return new_name

# Example:
# Original: "my-storage-account"
# Tenant ID: "a1b2c3d4-5678-90ab-cdef-1234567890ab"
# Result: "mystorageaccounta1b2c3d4" (24 chars max)
```

---

## Integration with Existing Code

### Where to Implement

Based on codebase analysis:

1. **Name Conflict Validator** (`src/validation/name_conflict_validator.py`)
   - Already checks for global uniqueness
   - Has `GLOBALLY_UNIQUE_TYPES` constant (currently 13 types)
   - **Action**: Expand to all 36+ types from this research

2. **Resource Translators** (`src/iac/translators/`)
   - `storage_account_translator.py` - Add suffix logic
   - `database_translator.py` - Add suffix logic for SQL Server
   - `keyvault_translator.py` - Already has suffix logic ✅
   - `appservice_translator.py` - Add suffix logic

3. **Terraform Handlers** (`src/iac/emitters/terraform/handlers/`)
   - Storage: `storage/storage_account.py`
   - SQL: `database/sql_server.py`
   - KeyVault: `keyvault/vault.py` (already done ✅)
   - AppService: `web/app_service.py`
   - ContainerRegistry: `container/container_registry.py`

### Proposed API

Add to `BaseTranslator`:

```python
class BaseTranslator:
    def apply_global_uniqueness_suffix(
        self,
        resource_name: str,
        resource_type: str,
        target_tenant_id: str
    ) -> str:
        """
        Apply suffix to ensure global uniqueness.

        Args:
            resource_name: Original resource name
            resource_type: Azure resource type (e.g., Microsoft.Storage/storageAccounts)
            target_tenant_id: Target tenant ID for suffix generation

        Returns:
            Modified name with suffix applied
        """
        # Check if resource type requires global uniqueness
        if not self.requires_global_uniqueness(resource_type):
            return resource_name

        # Get naming rules for resource type
        rules = GLOBAL_NAME_RULES.get(resource_type, {})
        max_length = rules.get("max_length", 63)

        # Generate suffix (first 8 chars of tenant ID)
        suffix = self._generate_suffix(target_tenant_id, resource_type)

        # Apply suffix with truncation if needed
        new_name = self._apply_suffix_with_truncation(
            resource_name, suffix, max_length, resource_type
        )

        # Validate against naming rules
        self._validate_name(new_name, resource_type)

        return new_name
```

---

## Testing Strategy

### Unit Tests

```python
def test_storage_account_global_uniqueness():
    """Test suffix applied to storage accounts."""
    translator = StorageAccountTranslator(
        context=CrossTenantContext(
            target_tenant_id="a1b2c3d4-5678-90ab-cdef-1234567890ab"
        )
    )

    resource = {
        "type": "Microsoft.Storage/storageAccounts",
        "name": "mystorageaccount"
    }

    translated = translator.translate(resource)

    # Should have suffix
    assert translated["name"] != "mystorageaccount"
    assert translated["name"].startswith("mystorageacco")  # truncated
    assert translated["name"].endswith("a1b2c3d4")  # suffix
    assert len(translated["name"]) <= 24  # max length
```

### Integration Tests

1. Deploy to **Target Tenant A** - Should succeed
2. Deploy AGAIN to **Target Tenant A** - Should fail (conflict)
3. Deploy to **Target Tenant B** (different suffix) - Should succeed

---

## Known Edge Cases

### 1. Name Collisions After Suffix
If `original-a1b2c3d4` already exists, add random component:
```python
new_name = f"{truncated_name}{suffix}{random_component}"
```

### 2. Child Resources
Some resources are hierarchical:
- `Microsoft.Sql/servers/databases`
- `Microsoft.Storage/storageAccounts/blobServices/containers`

Only **parent** needs global uniqueness (server, storage account).

### 3. Private Endpoints
Private endpoints reference globally-unique resources but don't require unique names themselves.

### 4. Soft-Deleted Resources
Key Vaults have soft-delete - name not available for 90 days after deletion. Validator already handles this.

---

## Resources in SIMULAND Deployment

Based on codebase analysis and handlers, SIMULAND likely uses:

**Confirmed Present:**
- ✅ Storage Accounts
- ✅ SQL Servers
- ✅ Key Vaults (already suffixed)
- ✅ Virtual Machines (NOT globally unique)
- ✅ Virtual Networks (NOT globally unique)
- ✅ NSGs (NOT globally unique)

**Possibly Present:**
- ⚠️ App Services (if web tier)
- ⚠️ Container Registry (if using containers)
- ⚠️ Redis Cache (if caching layer)
- ⚠️ Service Bus/Event Hub (if messaging)

---

## Conclusion

### Summary
- **36 resource types** require globally unique names
- **HIGH priority**: 5 types (Storage, SQL, KeyVault, AppService, ContainerRegistry)
- **MEDIUM priority**: 9 types (Redis, ServiceBus, EventHub, PostgreSQL, etc.)
- **LOW priority**: 22 types (Analytics, AI/ML, specialized)

### Recommendation

**Implement in 3 Phases:**

1. **Phase 1 (Critical)**: Handle top 5 HIGH priority types - these are confirmed in SIMULAND
2. **Phase 2 (Important)**: Add MEDIUM priority integration services
3. **Phase 3 (Complete)**: Full coverage for all 36+ types

**Suffix Strategy:**
Use **tenant ID-based suffix** (first 8 chars) for:
- Deterministic naming
- Easy debugging
- Tenant traceability

**Code Location:**
- Update `name_conflict_validator.py` with all 36 types
- Add suffix logic to translators
- Test with SIMULAND cross-tenant deployment

---

## References

- [Azure Resource Naming Rules](https://learn.microsoft.com/en-us/azure/azure-resource-manager/management/resource-name-rules) - Official Microsoft documentation
- [Azure Resource Naming Scopes](https://arnav.au/2025/04/14/azure-resource-naming-scopes/) - Community resource
- [Build5Nines Naming Conventions](https://build5nines.com/azure-resource-naming-conventions/) - Best practices guide
- [SimuLand GitHub](https://github.com/Azure/SimuLand) - Microsoft security testing lab
- [Microsoft Security Blog: SimuLand](https://www.microsoft.com/en-us/security/blog/2021/05/20/simuland-understand-adversary-tradecraft-and-improve-detection-strategies/) - Official announcement

---

**Next Steps:**
1. Review and approve suffix strategy (tenant ID vs random vs timestamp)
2. Implement Phase 1 (5 HIGH priority resource types)
3. Test with SIMULAND cross-tenant deployment
4. Iterate based on deployment errors
5. Expand to Phase 2 & 3 as needed

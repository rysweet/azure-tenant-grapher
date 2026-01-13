# Infrastructure-as-Code Name Sanitization Architecture

**Status**: [PLANNED - Implementation Pending]

---

## Overview

This document describes the name sanitization architecture for Infrastructure-as-Code (IaC) generation, specifically focusing on how Azure resource names are transformed from abstracted representations to Azure-compliant names that meet strict naming constraints.

---

## The Problem

Azure resources with globally unique DNS names have strict, resource-specific naming constraints:

- **Storage Accounts** (`*.core.windows.net`): 3-24 chars, lowercase alphanumeric ONLY
- **Key Vaults** (`*.vault.azure.net`): 3-24 chars, alphanumeric + hyphens, start with letter
- **Container Registries** (`*.azurecr.io`): 5-50 chars, alphanumeric ONLY (no hyphens)
- **SQL Servers** (`*.database.windows.net`): 1-63 chars, lowercase, alphanumeric + hyphens

**36 resource types** require globally unique names, each with different constraints.

### Historical Issues

1. **Bug #28 (Nov 2025)**: Within-tenant name collisions - same names in different resource groups
2. **Bug #52-53 (Nov 2025)**: Cross-tenant collisions - globally unique resources needed unique names
3. **Bugs #12-18 (Dec 2025)**: Resource-specific failures - Storage, SQL, Key Vault deployment failures
4. **Current State (Jan 2026)**: Only 5 of 36 handlers implement sanitization correctly (13.9% coverage)

---

## Architecture: Five-Phase Name Transformation

```
┌──────────────────────────────────────────────────────────┐
│ 1. Discovery Phase                                        │
│    Azure API → Original resource names → Neo4j graph      │
│    Example: "mystorageaccount"                            │
└──────────────────────┬───────────────────────────────────┘
                       ↓
┌──────────────────────────────────────────────────────────┐
│ 2. Abstraction Phase                                      │
│    IDAbstractionService → Generic abstracted names        │
│    Example: "storage-a1b2c3d4" (deterministic hash)       │
│    Note: Always includes hyphens                          │
└──────────────────────┬───────────────────────────────────┘
                       ↓
┌──────────────────────────────────────────────────────────┐
│ 3. Azure Name Sanitization Phase (NEW)                   │
│    AzureNameSanitizer → Apply resource-specific rules     │
│    Storage: Remove hyphens → "storagea1b2c3d4"            │
│    ACR: Remove hyphens → "acra1b2c3d4"                    │
│    KeyVault: Keep hyphens → "vault-a1b2c3d4"              │
│    SQL: Keep hyphens, lowercase → "sql-a1b2c3d4"          │
└──────────────────────┬───────────────────────────────────┘
                       ↓
┌──────────────────────────────────────────────────────────┐
│ 4. Global Uniqueness Phase                                │
│    Add tenant suffix for cross-tenant deployments         │
│    Conditional: Only if target_tenant != source_tenant    │
│    Format: {sanitized_name}{tenant_suffix}                │
│    Example: "storagea1b2c3d4abc123" (24 chars total)      │
└──────────────────────┬───────────────────────────────────┘
                       ↓
┌──────────────────────────────────────────────────────────┐
│ 5. IaC Generation Phase                                   │
│    TerraformEmitter → Generate .tf files with valid names │
│    Example: resource "azurerm_storage_account" "..."      │
└──────────────────────────────────────────────────────────┘
```

---

## Components

### 1. ID Abstraction Service (Existing)

**Location**: `src/services/id_abstraction_service.py`

**Responsibility**: Generate deterministic, type-prefixed abstracted names

**Behavior**:
- Input: Original resource name (e.g., `"mystorageaccount"`)
- Output: Abstracted name with hyphen (e.g., `"storage-a1b2c3d4e5f6g7h8"`)
- Format: `{prefix}-{hash_value}`
- Deterministic: Same input → same output

**Limitation**: No awareness of Azure naming constraints

### 2. Azure Name Sanitizer (NEW)

**Location**: `src/services/azure_name_sanitizer.py`

**Responsibility**: Transform abstracted names into Azure-compliant names

**Behavior**:
- Input: Abstracted name + resource type
- Output: Azure-compliant name
- Applies resource-specific rules:
  - Character set (lowercase, alphanumeric, hyphens)
  - Length constraints
  - Format validation (start/end characters, consecutive hyphens)

**Characteristics**:
- Stateless and deterministic
- Single source of truth for Azure naming rules
- Supports 36 globally unique resource types
- Zero external dependencies

**Public API**:
```python
class AzureNameSanitizer:
    def sanitize(abstracted_name: str, resource_type: str) -> str
    def is_globally_unique(resource_type: str) -> bool
    def get_constraints(resource_type: str) -> NamingConstraints
```

### 3. Terraform Handlers (Updated)

**Location**: `src/iac/emitters/terraform/handlers/**/*.py`

**Responsibility**: Generate Terraform configurations using sanitized names

**Updated Workflow**:
```python
def emit(resource, context):
    # 1. Get abstracted name from graph
    abstracted_name = resource.get("name")

    # 2. Sanitize for Azure constraints
    sanitizer = AzureNameSanitizer()
    sanitized_name = sanitizer.sanitize(
        abstracted_name,
        resource_type
    )

    # 3. Add tenant suffix if cross-tenant
    if context.target_tenant_id != context.source_tenant_id:
        tenant_suffix = generate_suffix(context.target_tenant_id)
        sanitized_name = f"{sanitized_name}{tenant_suffix}"

    # 4. Generate Terraform config
    config = {"name": sanitized_name, ...}
    return (terraform_type, resource_key, config)
```

---

## Resource Type Categories

The sanitizer handles **36 globally unique Azure resource types** across 6 categories:

### CRITICAL Priority (10 types)
- Storage Accounts, Key Vaults, App Services, SQL Servers
- Container Registries, PostgreSQL, MySQL, API Management
- CDN Profiles, App Configuration

### Integration/Messaging (4 types)
- Service Bus, Event Hubs, Event Grid, SignalR

### API/Networking (5 types)
- Front Door, Traffic Manager, Application Gateway, Firewall, Bastion

### Data/Analytics (8 types)
- Data Factory, Synapse, Databricks, HDInsight
- Cosmos DB, Redis, Search Service, Analysis Services

### AI/ML/IoT (4 types)
- Cognitive Services, Machine Learning, IoT Hub, IoT Central

### Specialized (5 types)
- Bot Service, Communication Services, Spring Cloud, Grafana, Static Web Apps

---

## Character Set Rules

The sanitizer enforces different character sets based on resource type:

### `lowercase_alphanum` (Storage Accounts, PostgreSQL, MySQL)
- **Allowed**: `a-z`, `0-9`
- **Forbidden**: Hyphens, uppercase, special characters
- **Sanitization**: Remove hyphens, convert to lowercase

### `alphanum_only` (Container Registry)
- **Allowed**: `a-zA-Z`, `0-9`
- **Forbidden**: Hyphens, special characters
- **Sanitization**: Remove hyphens, preserve case

### `alphanum_hyphen` (Key Vault, SQL Server, App Service)
- **Allowed**: `a-zA-Z`, `0-9`, `-`
- **Forbidden**: Consecutive hyphens, start/end with hyphen
- **Sanitization**: Remove consecutive hyphens, trim hyphens from ends

### `lowercase_alphanum_hyphen` (SQL Server, PostgreSQL, MySQL)
- **Allowed**: `a-z`, `0-9`, `-`
- **Forbidden**: Uppercase, consecutive hyphens
- **Sanitization**: Convert to lowercase, remove consecutive hyphens

---

## Length Management

The sanitizer enforces maximum length constraints:

### Strategy
1. Reserve space for tenant suffix (typically 6-7 chars)
2. Truncate original name to fit: `max_length - suffix_length`
3. Preserve as much of the original name as possible
4. Maintain determinism (same input → same truncation)

### Examples

**Storage Account (24 char max)**:
```python
abstracted = "storage-a1b2c3d4e5f6g7h8i9j0"  # pragma: allowlist secret  # 29 chars (example hash)
sanitized = "storagea1b2c3d4e5f"             # 18 chars (reserve 6 for suffix)
with_suffix = "storagea1b2c3d4e5fabc123"     # 24 chars total
```

**Key Vault (24 char max)**:
```python
abstracted = "keyvault-prod-east-us"         # 21 chars
sanitized = "keyvault-prod-ea"               # 16 chars (reserve 7 for suffix with hyphen)
with_suffix = "keyvault-prod-ea-abc1234"     # 24 chars total
```

---

## Cross-Tenant Uniqueness

For globally unique resources deployed across tenants, the sanitizer enables tenant-specific suffixes:

### Suffix Generation
```python
def generate_tenant_suffix(tenant_id: str, hyphen_allowed: bool) -> str:
    """Generate deterministic tenant suffix from tenant ID.

    Args:
        tenant_id: Azure tenant ID (UUID)
        hyphen_allowed: Whether resource type allows hyphens

    Returns:
        Suffix string (6-7 chars)
    """
    # Extract last 6 chars of tenant ID
    suffix = tenant_id[-6:].replace("-", "").lower()

    if hyphen_allowed:
        return f"-{suffix}"  # 7 chars: "-abc123"
    else:
        return suffix         # 6 chars: "abc123"
```

### Handler Usage
```python
if context.target_tenant_id and context.source_tenant_id != context.target_tenant_id:
    constraints = sanitizer.get_constraints(resource_type)
    hyphen_allowed = "hyphen" in constraints.allowed_chars

    tenant_suffix = generate_tenant_suffix(
        context.target_tenant_id,
        hyphen_allowed
    )

    sanitized_name = f"{sanitized_name}{tenant_suffix}"
```

---

## Migration Path

### Phase 1: Implement Sanitizer Service
- Create `src/services/azure_name_sanitizer.py`
- Implement all 36 resource type constraints
- Write comprehensive unit tests
- Document public API

### Phase 2: Update Existing Handlers
Update 5 handlers that currently have manual sanitization:
1. `storage_account.py` - Remove line 85 hyphen stripping
2. `container_registry.py` - Remove line 49 hyphen stripping
3. `sql_server.py` - Replace manual sanitization
4. `vault.py` - Replace MD5 hash logic
5. `app_service.py` - Replace manual sanitization

### Phase 3: Add Sanitizer to Remaining Handlers
Add sanitizer calls to 31 handlers without sanitization:
- Prioritize CRITICAL tier (PostgreSQL, MySQL, etc.)
- Then Integration/Messaging
- Then remaining tiers

### Phase 4: Validation
- Test all 36 resource types deploy successfully
- Validate cross-tenant deployment scenarios
- Verify no name collisions

---

## Testing Strategy

### Unit Tests (60%)
- Test each of 36 resource types' sanitization rules
- Verify character set transformations
- Test length truncation logic
- Edge cases (empty names, max length, special characters)

### Integration Tests (30%)
- Test sanitizer + handler integration
- Verify tenant suffix logic
- Test collision scenarios

### E2E Tests (10%)
- Deploy abstracted graph to actual Azure tenant
- Verify all 36 resource types deploy successfully
- Test cross-tenant deployment

---

## Benefits

### Single Source of Truth
- All Azure naming knowledge in one service
- No duplicated sanitization logic across handlers
- Easy to update when Azure changes naming rules

### Coverage Improvement
- Before: 5 of 36 handlers (13.9%)
- After: 36 of 36 handlers (100%)

### Maintainability
- Handlers become simpler (no manual sanitization)
- Easy to add new resource types
- Testable in isolation

### Determinism
- Same input always produces same output
- Reproducible deployments
- Predictable cross-tenant naming

---

## References

- **Investigation Report**: `.claude/docs/INVESTIGATION_globally_unique_names_20260113.md`
- **Sanitizer Documentation**: `docs/services/AZURE_NAME_SANITIZER.md`
- **Azure Naming Rules**: [Microsoft Learn - Naming rules and restrictions](https://learn.microsoft.com/en-us/azure/azure-resource-manager/management/resource-name-rules)
- **Historical Context**: Bugs #28, #52-53, #12-18
- **Research Document**: Commit `3a66f1d` - `AZURE_GLOBALLY_UNIQUE_NAMES_RESEARCH.md`

---

*This architecture document describes the [PLANNED] name sanitization system following Document-Driven Development principles.*

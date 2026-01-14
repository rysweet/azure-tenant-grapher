# Azure Name Sanitizer Usage Examples

**Status**: [PLANNED - Implementation Pending]

This document shows concrete examples of how Terraform handlers use the Azure Name Sanitizer service to transform abstracted resource names into Azure-compliant names.

---

## Basic Usage Pattern

All handlers follow the same pattern:

```python
from services.azure_name_sanitizer import AzureNameSanitizer

class ResourceHandler(ResourceHandler):
    def emit(self, resource: Dict[str, Any], context: EmitterContext):
        # 1. Get abstracted name from graph
        abstracted_name = resource.get("name", "unknown")

        # 2. Sanitize for Azure constraints
        sanitizer = AzureNameSanitizer()
        sanitized_name = sanitizer.sanitize(
            abstracted_name,
            "Microsoft.ResourceProvider/resourceType"
        )

        # 3. Add tenant suffix if cross-tenant deployment
        if context.target_tenant_id and context.source_tenant_id != context.target_tenant_id:
            # Suffix format depends on whether hyphens are allowed
            constraints = sanitizer.get_constraints(resource_type)
            if "hyphen" in constraints.allowed_chars:
                tenant_suffix = f"-{context.target_tenant_id[-6:].replace('-', '').lower()}"
            else:
                tenant_suffix = context.target_tenant_id[-6:].replace("-", "").lower()

            sanitized_name = f"{sanitized_name}{tenant_suffix}"

        # 4. Build Terraform config
        config = {"name": sanitized_name, ...}
        return (terraform_type, resource_key, config)
```

---

## Example 1: Storage Account Handler

**Constraints**: Lowercase alphanumeric ONLY, max 24 chars

**Before (Manual Sanitization)**:
```python
class StorageAccountHandler(ResourceHandler):
    def emit(self, resource, context):
        original_name = config["name"]

        if context.target_tenant_id and context.source_tenant_id != context.target_tenant_id:
            tenant_suffix = context.target_tenant_id[-6:].replace("-", "").lower()
            # Manual hyphen removal
            original_name = original_name.replace("-", "").lower()

            # Manual truncation
            if len(original_name) > 18:
                original_name = original_name[:18]

            config["name"] = f"{original_name}{tenant_suffix}"
```

**After (Using Sanitizer)**:
```python
from services.azure_name_sanitizer import AzureNameSanitizer

class StorageAccountHandler(ResourceHandler):
    def emit(self, resource, context):
        abstracted_name = resource.get("name", "unknown")

        # Sanitizer handles hyphen removal, lowercase, truncation
        sanitizer = AzureNameSanitizer()
        sanitized_name = sanitizer.sanitize(
            abstracted_name,
            "Microsoft.Storage/storageAccounts"
        )

        # Add tenant suffix if cross-tenant
        if context.target_tenant_id and context.source_tenant_id != context.target_tenant_id:
            tenant_suffix = context.target_tenant_id[-6:].replace("-", "").lower()
            sanitized_name = f"{sanitized_name}{tenant_suffix}"

        config = {
            "name": sanitized_name,
            "resource_group_name": resource.get("resource_group_name"),
            "location": resource.get("location"),
            "account_tier": "Standard",
            "account_replication_type": "LRS"
        }

        return ("azurerm_storage_account", self.sanitize_name(abstracted_name), config)
```

**Transformation Example**:
```python
# Input from graph
abstracted_name = "storage-a1b2c3d4e5f6g7h8i9j0"  # pragma: allowlist secret  # 29 chars (example hash)

# After sanitization
sanitized_name = "storagea1b2c3d4e5f"  # 18 chars (hyphens removed, lowercase, truncated)

# After tenant suffix (cross-tenant)
final_name = "storagea1b2c3d4e5fabc123"  # 24 chars (within limit)
```

---

## Example 2: Key Vault Handler

**Constraints**: Alphanumeric + hyphens, start with letter, max 24 chars

**Before (Manual Hash Logic)**:
```python
class VaultHandler(ResourceHandler):
    def emit(self, resource, context):
        if context.target_tenant_id and context.source_tenant_id != context.target_tenant_id:
            # Manual MD5 hash calculation
            resource_id = resource.get("id", "")
            hash_suffix = hashlib.md5(resource_id.encode()).hexdigest()[:7]
            original_name = f"{original_name}-{hash_suffix}"
```

**After (Using Sanitizer)**:
```python
from services.azure_name_sanitizer import AzureNameSanitizer

class VaultHandler(ResourceHandler):
    def emit(self, resource, context):
        abstracted_name = resource.get("name", "unknown")

        # Sanitizer handles hyphen validation, length, format
        sanitizer = AzureNameSanitizer()
        sanitized_name = sanitizer.sanitize(
            abstracted_name,
            "Microsoft.KeyVault/vaults"
        )

        # Add tenant suffix with hyphen (hyphens allowed)
        if context.target_tenant_id and context.source_tenant_id != context.target_tenant_id:
            tenant_suffix = context.target_tenant_id[-6:].replace("-", "").lower()
            sanitized_name = f"{sanitized_name}-{tenant_suffix}"

        config = {
            "name": sanitized_name,
            "location": resource.get("location"),
            "sku_name": "standard",
            "tenant_id": context.target_tenant_id or context.source_tenant_id
        }

        return ("azurerm_key_vault", self.sanitize_name(abstracted_name), config)
```

**Transformation Example**:
```python
# Input from graph
abstracted_name = "vault-prod-east-us"  # 18 chars

# After sanitization
sanitized_name = "vault-prod-east"  # 15 chars (consecutive hyphens removed, truncated)

# After tenant suffix (cross-tenant)
final_name = "vault-prod-east-abc123"  # 22 chars (within 24 char limit)
```

---

## Example 3: Container Registry Handler

**Constraints**: Alphanumeric ONLY (no hyphens), max 50 chars

**Before (Manual Sanitization)**:
```python
class ContainerRegistryHandler(ResourceHandler):
    def emit(self, resource, context):
        if context.target_tenant_id and context.source_tenant_id != context.target_tenant_id:
            tenant_suffix = context.target_tenant_id[-6:].replace("-", "").lower()
            # Manual hyphen removal
            original_name = original_name.replace("-", "")
            config["name"] = f"{original_name}{tenant_suffix}"
```

**After (Using Sanitizer)**:
```python
from services.azure_name_sanitizer import AzureNameSanitizer

class ContainerRegistryHandler(ResourceHandler):
    def emit(self, resource, context):
        abstracted_name = resource.get("name", "unknown")

        # Sanitizer handles hyphen removal, alphanumeric validation
        sanitizer = AzureNameSanitizer()
        sanitized_name = sanitizer.sanitize(
            abstracted_name,
            "Microsoft.ContainerRegistry/registries"
        )

        # Add tenant suffix (no hyphen separator)
        if context.target_tenant_id and context.source_tenant_id != context.target_tenant_id:
            tenant_suffix = context.target_tenant_id[-6:].replace("-", "").lower()
            sanitized_name = f"{sanitized_name}{tenant_suffix}"

        config = {
            "name": sanitized_name,
            "resource_group_name": resource.get("resource_group_name"),
            "location": resource.get("location"),
            "sku": "Basic"
        }

        return ("azurerm_container_registry", self.sanitize_name(abstracted_name), config)
```

**Transformation Example**:
```python
# Input from graph
abstracted_name = "acr-prod-west"  # 13 chars with hyphens

# After sanitization
sanitized_name = "acrprodwest"  # 11 chars (hyphens removed)

# After tenant suffix (cross-tenant)
final_name = "acrprodwestabc123"  # 17 chars (within 50 char limit)
```

---

## Example 4: SQL Server Handler

**Constraints**: Lowercase, alphanumeric + hyphens, max 63 chars

**Before (Manual Sanitization)**:
```python
class SqlServerHandler(ResourceHandler):
    def emit(self, resource, context):
        if context.target_tenant_id and context.source_tenant_id != context.target_tenant_id:
            tenant_suffix = context.target_tenant_id[-7:]
            original_name = original_name.lower()
            config["name"] = f"{original_name}-{tenant_suffix}"
```

**After (Using Sanitizer)**:
```python
from services.azure_name_sanitizer import AzureNameSanitizer

class SqlServerHandler(ResourceHandler):
    def emit(self, resource, context):
        abstracted_name = resource.get("name", "unknown")

        # Sanitizer handles lowercase, hyphen validation
        sanitizer = AzureNameSanitizer()
        sanitized_name = sanitizer.sanitize(
            abstracted_name,
            "Microsoft.Sql/servers"
        )

        # Add tenant suffix with hyphen
        if context.target_tenant_id and context.source_tenant_id != context.target_tenant_id:
            tenant_suffix = context.target_tenant_id[-6:].replace("-", "").lower()
            sanitized_name = f"{sanitized_name}-{tenant_suffix}"

        config = {
            "name": sanitized_name,
            "resource_group_name": resource.get("resource_group_name"),
            "location": resource.get("location"),
            "version": "12.0",
            "administrator_login": "sqladmin"
        }

        return ("azurerm_mssql_server", self.sanitize_name(abstracted_name), config)
```

**Transformation Example**:
```python
# Input from graph
abstracted_name = "SQL-Server-01"  # 13 chars with uppercase

# After sanitization
sanitized_name = "sql-server-01"  # 13 chars (lowercase)

# After tenant suffix (cross-tenant)
final_name = "sql-server-01-abc123"  # 20 chars (within 63 char limit)
```

---

## Example 5: PostgreSQL Server Handler (NEW)

**Constraints**: Lowercase, alphanumeric + hyphens, max 63 chars

**Before (No Handler Existed)**:
```python
# No handler existed - would have failed deployment
# with NameAlreadyExists error
```

**After (Using Sanitizer)**:
```python
from services.azure_name_sanitizer import AzureNameSanitizer

class PostgreSqlServerHandler(ResourceHandler):
    HANDLED_TYPES = {"Microsoft.DBforPostgreSQL/servers"}
    TERRAFORM_TYPES = {"azurerm_postgresql_server"}

    def emit(self, resource, context):
        abstracted_name = resource.get("name", "unknown")

        # Sanitizer handles lowercase, hyphen validation
        sanitizer = AzureNameSanitizer()
        sanitized_name = sanitizer.sanitize(
            abstracted_name,
            "Microsoft.DBforPostgreSQL/servers"
        )

        # Add tenant suffix for global uniqueness
        if context.target_tenant_id and context.source_tenant_id != context.target_tenant_id:
            tenant_suffix = context.target_tenant_id[-6:].replace("-", "").lower()
            sanitized_name = f"{sanitized_name}-{tenant_suffix}"

        config = {
            "name": sanitized_name,
            "resource_group_name": resource.get("resource_group_name"),
            "location": resource.get("location"),
            "sku_name": "B_Gen5_1",
            "version": "11"
        }

        return ("azurerm_postgresql_server", self.sanitize_name(abstracted_name), config)
```

**Transformation Example**:
```python
# Input from graph
abstracted_name = "postgres-a1b2c3d4"  # 17 chars

# After sanitization
sanitized_name = "postgres-a1b2c3d4"  # 17 chars (already compliant)

# After tenant suffix (cross-tenant)
final_name = "postgres-a1b2c3d4-abc123"  # 24 chars (within 63 char limit)
```

---

## Helper Function: Tenant Suffix Generation

Reusable helper for generating tenant suffixes:

```python
def generate_tenant_suffix(
    tenant_id: str,
    hyphen_separator: bool = False,
    length: int = 6
) -> str:
    """Generate deterministic tenant suffix from tenant ID.

    Args:
        tenant_id: Azure tenant ID (UUID format)
        hyphen_separator: Whether to include hyphen separator
        length: Length of suffix (default 6)

    Returns:
        Tenant suffix string

    Example:
        >>> generate_tenant_suffix("12345678-1234-1234-1234-123456abcdef")
        'abcdef'
        >>> generate_tenant_suffix("12345678-1234-1234-1234-123456abcdef", hyphen_separator=True)
        '-abcdef'
    """
    suffix = tenant_id[-length:].replace("-", "").lower()
    return f"-{suffix}" if hyphen_separator else suffix
```

**Usage in Handlers**:
```python
# For resources that allow hyphens (Key Vault, SQL Server)
tenant_suffix = generate_tenant_suffix(
    context.target_tenant_id,
    hyphen_separator=True
)

# For resources that don't allow hyphens (Storage, ACR)
tenant_suffix = generate_tenant_suffix(
    context.target_tenant_id,
    hyphen_separator=False
)
```

---

## Checking Global Uniqueness

Handlers can check if sanitization is needed:

```python
from services.azure_name_sanitizer import AzureNameSanitizer

class GenericHandler(ResourceHandler):
    def emit(self, resource, context):
        abstracted_name = resource.get("name", "unknown")
        resource_type = resource.get("type")

        sanitizer = AzureNameSanitizer()

        # Only sanitize globally unique resources
        if sanitizer.is_globally_unique(resource_type):
            sanitized_name = sanitizer.sanitize(abstracted_name, resource_type)

            # Add tenant suffix for cross-tenant
            if context.target_tenant_id != context.source_tenant_id:
                constraints = sanitizer.get_constraints(resource_type)
                hyphen_allowed = "hyphen" in constraints.allowed_chars
                tenant_suffix = generate_tenant_suffix(
                    context.target_tenant_id,
                    hyphen_separator=hyphen_allowed
                )
                sanitized_name = f"{sanitized_name}{tenant_suffix}"
        else:
            # Non-globally-unique resources use abstracted name as-is
            sanitized_name = abstracted_name

        config = {"name": sanitized_name, ...}
        return (terraform_type, resource_key, config)
```

---

## Complete Transformation Flow

Example showing complete name transformation from discovery to Terraform:

```python
# 1. DISCOVERY PHASE
# Original resource in Azure
azure_resource = {
    "name": "mystorageaccount",
    "type": "Microsoft.Storage/storageAccounts",
    "id": "/subscriptions/.../resourceGroups/rg/providers/Microsoft.Storage/storageAccounts/mystorageaccount"
}

# 2. ABSTRACTION PHASE
# IDAbstractionService generates deterministic hash
from services.id_abstraction_service import IDAbstractionService
id_service = IDAbstractionService(seed="tenant-seed")
abstracted_name = id_service.abstract_resource_name(
    "mystorageaccount",
    "Microsoft.Storage/storageAccounts"
)
# Result: "storage-a1b2c3d4e5f6g7h8"

# 3. SANITIZATION PHASE
# AzureNameSanitizer applies Azure constraints
from services.azure_name_sanitizer import AzureNameSanitizer
sanitizer = AzureNameSanitizer()
sanitized_name = sanitizer.sanitize(
    abstracted_name,
    "Microsoft.Storage/storageAccounts"
)
# Result: "storagea1b2c3d4e5f" (hyphens removed, truncated to 18 chars)

# 4. GLOBAL UNIQUENESS PHASE
# Add tenant suffix for cross-tenant deployment
target_tenant = "12345678-1234-1234-1234-123456abcdef"
tenant_suffix = target_tenant[-6:].replace("-", "").lower()
final_name = f"{sanitized_name}{tenant_suffix}"
# Result: "storagea1b2c3d4e5fabcdef" (24 chars total)

# 5. IAC GENERATION PHASE
# Terraform handler generates .tf file
terraform_config = {
    "resource": {
        "azurerm_storage_account": {
            "storage_a1b2c3d4e5f6g7h8": {
                "name": "storagea1b2c3d4e5fabcdef",
                "resource_group_name": "rg-target",
                "location": "eastus",
                "account_tier": "Standard",
                "account_replication_type": "LRS"
            }
        }
    }
}

# 6. DEPLOYMENT
# Terraform applies configuration to Azure
# Storage account created with globally unique name
```

---

## References

- **Service Documentation**: `docs/services/AZURE_NAME_SANITIZER.md`
- **Architecture**: `docs/architecture/IaC_Name_Sanitization.md`
- **Investigation Report**: `.claude/docs/INVESTIGATION_globally_unique_names_20260113.md`

---

*These examples describe [PLANNED] functionality following Document-Driven Development principles.*

# ID Abstraction System

## Overview

The ID Abstraction System ensures that Azure tenant-specific identifiers (principal IDs, tenant IDs, client IDs, subscription IDs) are consistently abstracted throughout the Azure Tenant Grapher pipeline, enabling true cross-tenant deployment.

## Problem Statement

Azure resources contain numerous tenant-specific GUIDs that prevent direct replication to different tenants:
- **Principal IDs**: Unique identifiers for service principals, managed identities, and users
- **Tenant IDs**: Azure AD tenant identifiers
- **Client IDs**: Application/service principal identifiers
- **Subscription IDs**: Azure subscription identifiers

Without abstraction, these IDs leak into:
1. Neo4j graph database (polluting the data source)
2. Generated Infrastructure-as-Code (blocking cross-tenant deployment)
3. Graph relationships (breaking referential integrity)

## Architecture

### Three-Layer Abstraction

```
Layer 1: DATA COLLECTION (services/)
  ↓ Abstract IDs at ingestion
Layer 2: GRAPH STORAGE (Neo4j)
  ↓ Store abstracted IDs only
Layer 3: IAC GENERATION (iac/emitters/)
  ↓ Translate abstracted → target IDs
OUTPUT: Clean IaC with target tenant IDs
```

### Abstraction Points

#### Layer 1: Data Collection (PREVENTION)

**Files**:
- `src/services/identity_collector.py`
- `src/services/managed_identity_resolver.py`
- `src/services/resource_processing/node_manager.py`

**Strategy**: Abstract ALL IDs BEFORE storing in Neo4j

**Example**:
```python
# RAW (BEFORE - LEAKS)
principal_id = identity.get("principalId")  # 9a2b3c4d-...
identities.append(IdentityReference(id=principal_id))

# ABSTRACTED (AFTER - SECURE)
principal_id = identity.get("principalId")
abstracted_id = abstract_principal_id(principal_id)  # principal-system-vm001
identities.append(IdentityReference(id=abstracted_id))
```

#### Layer 2: Graph Storage (DATA INTEGRITY)

**Neo4j Properties**: ONLY abstracted IDs stored
- `principalId`: `"principal-system-vm001"` (NOT `"9a2b3c4d-..."`)
- `tenantId`: `"${target_tenant_id}"` (NOT source GUID)
- `clientId`: `"client-app-webapi"` (NOT application GUID)

#### Layer 3: IaC Generation (OUTPUT PROTECTION)

**Files**:
- `src/iac/emitters/terraform/handlers/keyvault/vault.py`
- `src/iac/emitters/arm_emitter.py`
- `src/iac/emitters/bicep_emitter.py`

**Strategy**: Translate abstracted IDs → target tenant IDs

**Example**:
```python
# BEFORE (LEAKS source tenant)
tenant_id = properties.get("tenantId")  # Source tenant GUID

# AFTER (SAFE - uses target)
tenant_id = context.target_tenant_id or abstract_tenant_id(
    properties.get("tenantId")
)
```

## ID Abstraction Functions

### Core Utilities

```python
def abstract_principal_id(principal_id: str, resource_name: str = "") -> str:
    """
    Abstract Azure principal ID to human-readable reference.

    Args:
        principal_id: Source principal GUID
        resource_name: Optional resource name for context

    Returns:
        Abstracted ID like "principal-system-vm001" or "principal-user-alice"
    """

def abstract_tenant_id(tenant_id: str) -> str:
    """
    Abstract tenant ID to placeholder.

    Returns:
        "${target_tenant_id}" for template substitution
    """

def abstract_subscription_id(subscription_id: str) -> str:
    """
    Abstract subscription ID to placeholder.

    Returns:
        "${target_subscription_id}" for template substitution
    """
```

### Integration with Existing Translators

The ID Abstraction System integrates with:
- **EntraIdTranslator**: Translates abstracted principal IDs to target tenant object IDs
- **SubscriptionTranslator**: Translates subscription references
- **ManagedIdentityTranslator**: Handles managed identity resource IDs

## Usage

### For Service Developers

When collecting Azure resource data:

```python
# services/new_collector.py
from src.utils.id_abstraction import abstract_principal_id, abstract_tenant_id

def collect_resources(resources):
    for resource in resources:
        # Abstract IDs BEFORE storing
        if "principalId" in resource["properties"]:
            raw_id = resource["properties"]["principalId"]
            resource["properties"]["principalId"] = abstract_principal_id(
                raw_id, resource.get("name")
            )

        if "tenantId" in resource["properties"]:
            raw_id = resource["properties"]["tenantId"]
            resource["properties"]["tenantId"] = abstract_tenant_id(raw_id)
```

### For IaC Emitter Developers

When generating IaC:

```python
# iac/emitters/terraform/handlers/new_handler.py
def emit(self, resource, context):
    # NEVER use raw IDs from properties
    # ALWAYS translate through context
    tenant_id = context.target_tenant_id  # ✓ CORRECT
    # NOT: tenant_id = properties.get("tenantId")  # ✗ WRONG

    # For principal IDs, use translator
    if context.identity_mapping:
        principal_id = translate_principal_id(
            properties.get("principalId"),
            context.identity_mapping
        )
```

### For Relationship Rule Developers

When creating graph relationships:

```python
# relationship_rules/new_rule.py
def create_relationships(self, source_node, target_node):
    # Pull abstracted IDs from node properties
    principal_id = source_node.get("principalId")  # Already abstracted!

    # If somehow raw ID slipped through, abstract it
    if is_guid(principal_id):
        principal_id = abstract_principal_id(principal_id)
```

## Testing

### Unit Test Template

```python
def test_id_abstraction():
    """Verify ID abstraction prevents leaks."""
    # Arrange
    source_principal_id = "9a2b3c4d-1234-5678-90ab-cdef12345678"
    resource_name = "vm-webapp-001"

    # Act
    abstracted = abstract_principal_id(source_principal_id, resource_name)

    # Assert
    assert not is_guid(abstracted), "Abstracted ID must not be GUID"
    assert "principal" in abstracted, "Abstracted ID must be human-readable"
    assert source_principal_id not in abstracted, "Source ID must not leak"
```

### Integration Test Template

```python
def test_no_id_leaks_in_graph(neo4j_session):
    """Verify Neo4j contains no raw GUIDs."""
    # Query all nodes
    result = neo4j_session.run("MATCH (n) RETURN n")

    for record in result:
        node = record["n"]
        for key, value in node.items():
            if isinstance(value, str):
                assert not is_guid(value), (
                    f"Found leaked GUID in node property {key}: {value}"
                )
```

## Validation

### Pre-Deployment Checklist

Before generating IaC for cross-tenant deployment:

- [ ] All `principalId` values abstracted in Neo4j
- [ ] All `tenantId` values use `${target_tenant_id}`
- [ ] All `subscription` references use `${target_subscription_id}`
- [ ] Generated IaC contains NO source tenant GUIDs
- [ ] Identity mapping file provided for principal translation

### Grep-Based Validation

```bash
# Check for GUID leaks in generated IaC
grep -E "[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}" iac_output/*.tf.json

# Should return ZERO matches (exit code 1)
```

## Troubleshooting

### Problem: "Principal ID not found in identity mapping"

**Cause**: Abstracted principal ID not in mapping file
**Solution**: Regenerate identity mapping with `--include-all-identities` flag

### Problem: "Source tenant ID leaked into IaC"

**Cause**: Emitter using raw `properties.get("tenantId")`
**Solution**: Update emitter to use `context.target_tenant_id`

### Problem: "Neo4j contains raw GUIDs"

**Cause**: ID abstraction not called during data collection
**Solution**: Add abstraction call in collector before Neo4j write

## Performance Impact

- **Graph Storage**: ~5% increase (abstracted IDs are strings, not GUIDs)
- **IaC Generation**: ~2% increase (translation lookups)
- **Overall**: Negligible impact, massive cross-tenant deployment benefit

## Security Considerations

- **Data Isolation**: Abstracted IDs prevent accidental cross-tenant information disclosure
- **Auditability**: Human-readable IDs improve audit trail clarity
- **Reversibility**: Mapping files allow reconstruction of source→target mappings

## Future Enhancements

1. **Auto-Mapping Generation**: Generate identity mapping from Microsoft Graph API
2. **Fuzzy Matching**: Match users by UPN/email across tenants
3. **Abstraction Templates**: Customize abstraction format per organization
4. **Leak Detection CI**: Automated CI check for GUID leaks in PRs

## References

- Issue #475: ID Leakage Audit
- Bug #67: Terraform Role Assignment Principal ID Translation
- Bug #69: ARM Emitter Role Assignment Translation
- Bug #70: Bicep Emitter Role Assignment Translation
- `src/iac/translators/entraid_translator.py`: Core translation logic

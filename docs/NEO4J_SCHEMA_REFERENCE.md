# Neo4j Graph Schema Reference

## Overview

Azure Tenant Grapher builds a comprehensive Neo4j graph database representing Azure tenant resources, their relationships, and identity/RBAC information. This document provides the complete reference for the graph schema, including all node types, relationship types, and how the schema is dynamically assembled.

### Dual-Graph Architecture

The system uses a **dual-graph architecture** where every Azure resource is stored as two parallel nodes:

- **Abstracted nodes** (`:Resource`): IDs are translated to type-prefixed hashes (e.g., `vm-a1b2c3d4`, `storage-e5f6g7h8`) suitable for cross-tenant deployment
- **Original nodes** (`:Resource:Original`): Real Azure IDs from the source tenant for reference and audit
- **Linking relationship**: `(abstracted)-[:SCAN_SOURCE_NODE]->(original)` connects the parallel nodes

This architecture enables:
- **Cross-tenant deployments** with safe ID abstraction
- **Query flexibility**: Query original topology OR deployment-ready abstracted view
- **IaC simplification**: No runtime ID translation needed during IaC generation
- **Graph validation**: Validate abstractions before deployment

**Key services:**
- `IDAbstractionService` (`src/services/id_abstraction_service.py`): Deterministic hash-based ID generation
- `TenantSeedManager` (`src/services/tenant_seed_manager.py`): Per-tenant cryptographic seeds for reproducible abstraction

## Table of Contents

- [Schema Architecture](#schema-architecture)
- [Node Types](#node-types)
  - [Core Infrastructure Nodes](#core-infrastructure-nodes)
  - [Identity and RBAC Nodes](#identity-and-rbac-nodes)
  - [Network Nodes](#network-nodes)
  - [Tenant Structure Nodes](#tenant-structure-nodes)
- [Relationship Types](#relationship-types)
  - [Canonical Relationships](#canonical-relationships)
  - [Identity Relationships](#identity-relationships)
  - [Network Relationships](#network-relationships)
  - [Other Relationships](#other-relationships)
- [Schema Assembly Process](#schema-assembly-process)
- [Data Models](#data-models)
- [Code References](#code-references)

---

## Schema Architecture

The Neo4j schema in Azure Tenant Grapher is **dynamically assembled** during resource processing. Rather than using a static schema definition, the graph is built through:

1. **Dynamic Node Creation**: Nodes are created using generic upsert operations with dynamic labels
2. **Rule-Based Relationships**: Relationships are emitted by specialized rule classes that analyze resources
3. **Property-Rich Model**: Both nodes and relationships store extensive metadata
4. **Hierarchical Structure**: Resources are organized in subscription → resource group → resource hierarchies

### Key Characteristics

- **Schema-on-write**: The schema evolves as resources are discovered
- **Extensible**: New node and relationship types can be added via rules
- **Type-safe models**: Pydantic models define the structure (see [`src/tenant_spec_models.py`](../src/tenant_spec_models.py))
- **Cypher-based**: All database operations use parameterized Cypher queries

---

## Node Types

### Core Infrastructure Nodes

#### Tenant
Represents the Azure Active Directory tenant (root of the hierarchy).

**Properties:**
- `id`: Tenant ID (GUID)
- `name`: Tenant display name
- `domain`: Primary domain
- `abstraction_seed`: Cryptographic seed for deterministic ID abstraction (64-char hex string)
- `updated_at`: Last update timestamp

**Dual-Graph Support:**
- The `abstraction_seed` property stores a per-tenant cryptographic seed used by `IDAbstractionService` for reproducible ID abstraction
- Generated using `secrets.token_hex(32)` (256-bit entropy)
- Stored persistently and never regenerated (ensures consistent abstractions)

**Created in:** [`src/tenant_creator.py:674`](../src/tenant_creator.py#L674)
**Seed managed by:** [`src/services/tenant_seed_manager.py`](../src/services/tenant_seed_manager.py)

---

#### Subscription
Represents an Azure subscription.

**Properties:**
- `id`: Subscription ID (GUID)
- `name`: Subscription name
- `state`: Subscription state (Enabled, Disabled, etc.)
- `updated_at`: Last update timestamp

**Created in:** [`src/resource_processor.py:185-191`](../src/resource_processor.py#L185-L191)

**Example Cypher:**
```cypher
MERGE (s:Subscription {id: $id})
SET s.name = $name, s.updated_at = datetime()
```

---

#### ResourceGroup
Represents an Azure resource group.

**Properties:**
- `id`: Resource group ID
- `name`: Resource group name
- `subscription_id`: Parent subscription ID
- `type`: Resource type (always "Microsoft.Resources/resourceGroups")
- `location`: Azure region
- `llm_description`: AI-generated description (optional)
- `updated_at`: Last update timestamp

**Created in:** [`src/resource_processor.py:205-215`](../src/resource_processor.py#L205-L215)

---

#### Resource
Represents any Azure resource (VMs, storage accounts, databases, etc.).

**Dual-Graph Architecture:**

Every resource exists as TWO nodes with identical topology but different IDs:

##### Abstracted Resource Nodes (`:Resource`)
**Default for all queries.** These nodes have type-prefixed hash IDs suitable for cross-tenant deployment.

**Labels:** `:Resource` (no `:Original` label)

**Properties:**
- `id`: **Abstracted** resource ID with type-prefixed hash (e.g., `vm-a1b2c3d4e5f6g7h8`)
- `original_id`: Reference to original Azure ID
- `name`: Resource name (unchanged from original)
- `type`: Resource type (e.g., "Microsoft.Compute/virtualMachines")
- `location`: Azure region
- `resource_group`: Parent resource group name (abstracted)
- `subscription_id`: Parent subscription ID (abstracted)
- `abstraction_type`: "hash-based" (metadata)
- `abstraction_seed`: Reference to tenant seed used
- `llm_description`: AI-generated description (optional)
- `processing_status`: Processing state
- `properties`: JSON blob with resource-specific properties
- `sku`: SKU information (if applicable)
- `tags`: Resource tags (if any)
- `updated_at`: Last update timestamp

##### Original Resource Nodes (`:Resource:Original`)
**Requires explicit label in queries.** These nodes preserve real Azure IDs from source tenant.

**Labels:** `:Resource:Original`

**Properties:**
- `id`: **Original** Azure resource ID (e.g., `/subscriptions/{guid}/resourceGroups/{name}/...`)
- `abstracted_id`: Reference to abstracted ID
- `name`: Resource name
- `type`: Resource type
- `location`: Azure region
- `resource_group`: Parent resource group name (original)
- `subscription_id`: Parent subscription ID (original GUID)
- `llm_description`: AI-generated description (optional)
- `processing_status`: Processing state
- `properties`: JSON blob with resource-specific properties
- `sku`: SKU information (if applicable)
- `tags`: Resource tags (if any)
- `updated_at`: Last update timestamp

**Created in:** [`src/resource_processor.py:582-645`](../src/resource_processor.py#L582-L645) (dual-node creation logic)

**Notes:**
- This is the most common node type
- The `type` property determines resource-specific processing
- Properties vary widely based on resource type
- All resource relationships are duplicated in both graphs
- Default queries `MATCH (r:Resource)` return only abstracted nodes
- To query originals: `MATCH (r:Resource:Original)` or `MATCH (r:Resource) WHERE r:Original`

**ID Abstraction Examples:**
```
Original ID:    /subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/my-rg/providers/Microsoft.Compute/virtualMachines/my-vm
Abstracted ID:  vm-a1b2c3d4e5f6g7h8

Original ID:    /subscriptions/12345678.../Microsoft.Storage/storageAccounts/mystorageacct
Abstracted ID:  storage-e5f6g7h8i9j0k1l2
```

---

#### Tag
Represents an Azure resource tag (key-value pair).

**Properties:**
- `key`: Tag key
- `value`: Tag value
- `updated_at`: Last update timestamp

**Created in:** [`src/resource_processor.py:534`](../src/resource_processor.py#L534)

---

### Identity and RBAC Nodes

#### User
Represents an Azure AD user.

**Properties:**
- `id`: User object ID (GUID)
- `userPrincipalName`: User principal name (email)
- `displayName`: Display name
- `accountEnabled`: Whether account is enabled
- `userType`: User type (Member, Guest)
- `mail`: Email address
- `updated_at`: Last update timestamp

**Data Model:** [`src/tenant_spec_models.py:58-136`](../src/tenant_spec_models.py#L58-L136)

**Created by:** Azure AD identity import process

---

#### Group
Represents an Azure AD group.

**Properties:**
- `id`: Group object ID (GUID)
- `displayName`: Group display name
- `description`: Group description
- `groupTypes`: Group type (Security, Microsoft365, etc.)
- `mailEnabled`: Whether mail is enabled
- `securityEnabled`: Whether security is enabled
- `updated_at`: Last update timestamp

**Data Model:** [`src/tenant_spec_models.py:139-219`](../src/tenant_spec_models.py#L139-L219)

**Created in:** [`src/tenant_creator.py:655`](../src/tenant_creator.py#L655)

---

#### ServicePrincipal
Represents an Azure AD service principal (application identity).

**Properties:**
- `id`: Service principal object ID (GUID)
- `appId`: Application ID
- `displayName`: Display name
- `servicePrincipalType`: Type of service principal
- `accountEnabled`: Whether enabled
- `updated_at`: Last update timestamp

**Data Model:** [`src/tenant_spec_models.py:263-347`](../src/tenant_spec_models.py#L263-L347)

---

#### ManagedIdentity
Represents a system-assigned or user-assigned managed identity.

**Properties:**
- `id`: Identity ID
- `principalId`: Principal ID (GUID)
- `type`: Identity type (SystemAssigned, UserAssigned)
- `clientId`: Client ID (for user-assigned)
- `updated_at`: Last update timestamp

**Data Model:** [`src/tenant_spec_models.py:350-364`](../src/tenant_spec_models.py#L350-L364)

**Created in:** [`src/relationship_rules/identity_rule.py:10`](../src/relationship_rules/identity_rule.py#L10)

---

#### RoleDefinition
Represents an Azure RBAC role definition.

**Properties:**
- `id`: Role definition ID
- `roleName`: Role name (e.g., "Owner", "Contributor")
- `type`: Role type (BuiltInRole, CustomRole)
- `description`: Role description
- `permissions`: JSON array of permissions
- `updated_at`: Last update timestamp

**Created in:** [`src/relationship_rules/identity_rule.py:6`](../src/relationship_rules/identity_rule.py#L6)

---

#### RoleAssignment
Represents an Azure RBAC role assignment (connects identity to role).

**Properties:**
- `id`: Role assignment ID
- `principalId`: Identity principal ID
- `roleDefinitionId`: Role definition ID
- `scope`: Assignment scope (subscription, resource group, or resource)
- `principalType`: Principal type (User, Group, ServicePrincipal)
- `updated_at`: Last update timestamp

**Created in:** [`src/relationship_rules/identity_rule.py:7`](../src/relationship_rules/identity_rule.py#L7)

---

#### AdminUnit
Represents an Azure AD administrative unit.

**Properties:**
- `id`: Administrative unit object ID
- `displayName`: Display name
- `description`: Description
- `visibility`: Visibility setting
- `updated_at`: Last update timestamp

**Created in:** [`src/tenant_creator.py:658`](../src/tenant_creator.py#L658)

---

### Network Nodes

#### PrivateEndpoint
Represents an Azure private endpoint (secure network connection).

**Properties:**
- `id`: Private endpoint ID
- `name`: Private endpoint name
- `location`: Azure region
- `subnet_id`: Connected subnet ID
- `connection_state`: Connection state
- `updated_at`: Last update timestamp

**Created in:** [`src/relationship_rules/network_rule.py:6`](../src/relationship_rules/network_rule.py#L6)

---

#### DNSZone
Represents an Azure DNS zone (public or private).

**Properties:**
- `id`: DNS zone ID
- `name`: Zone name (e.g., "example.com")
- `type`: Zone type (Public, Private)
- `recordCount`: Number of DNS records
- `updated_at`: Last update timestamp

**Created in:** [`src/relationship_rules/network_rule.py:7`](../src/relationship_rules/network_rule.py#L7)

---

### Tenant Structure Nodes

These nodes are used when creating simulated tenants from specifications.

#### IdentityGroup
Represents a security group used for identity management.

**Properties:**
- `id`: Group object ID
- `displayName`: Group display name
- `description`: Description
- `updated_at`: Last update timestamp

**Created in:** [`src/relationship_rules/identity_rule.py:11`](../src/relationship_rules/identity_rule.py#L11)

---

## Relationship Types

### Canonical Relationships

These are the seven core relationship types that form the backbone of the graph schema. They are defined as the standard relationship semantics for the system.

**Definition Location:** [`src/tenant_creator.py:79-86`](../src/tenant_creator.py#L79-L86)

#### 1. DEPENDS_ON
Represents resource dependencies.

**Semantics:** Source resource depends on target resource for functionality

**Examples:**
- Virtual machine DEPENDS_ON virtual network
- Web app DEPENDS_ON app service plan
- Function app DEPENDS_ON storage account

**Properties:**
- `dependency_type`: Type of dependency (Hard, Soft, Optional)
- `created_at`: When relationship was created

**Emitted by:** `DependsOnRule` ([`src/relationship_rules/depends_on_rule.py`](../src/relationship_rules/depends_on_rule.py))

---

#### 2. USES
Represents general usage relationships.

**Semantics:** Source resource uses target resource or service

**Examples:**
- Application USES database
- Web app USES storage account
- Logic app USES service bus

**Properties:**
- `usage_type`: Type of usage
- `created_at`: When relationship was created

---

#### 3. CONNECTS_TO
Represents network connections.

**Semantics:** Source resource has network connectivity to target resource

**Examples:**
- VPN gateway CONNECTS_TO local network gateway
- Virtual network CONNECTS_TO virtual network (peering)
- Application gateway CONNECTS_TO backend pool

**Properties:**
- `connection_type`: Type of connection (Peering, VPN, ExpressRoute)
- `created_at`: When relationship was created

**Emitted by:** `NetworkRule` ([`src/relationship_rules/network_rule.py`](../src/relationship_rules/network_rule.py))

---

#### 4. CONTAINS
Represents hierarchical containment.

**Semantics:** Parent contains child in a hierarchy

**Examples:**
- Subscription CONTAINS resource group
- Resource group CONTAINS resource
- Virtual network CONTAINS subnet

**Properties:**
- `hierarchy_level`: Level in hierarchy (1 = Subscription→RG, 2 = RG→Resource)
- `created_at`: When relationship was created

**Emitted by:** `SubnetExtractionRule` ([`src/relationship_rules/subnet_extraction_rule.py:87`](../src/relationship_rules/subnet_extraction_rule.py#L87))

---

#### 5. MEMBER_OF
Represents group membership.

**Semantics:** Identity is a member of a group

**Examples:**
- User MEMBER_OF security group
- Group MEMBER_OF administrative unit
- Service principal MEMBER_OF app role

**Properties:**
- `membership_type`: Type of membership (Direct, Nested)
- `created_at`: When relationship was created

---

#### 6. ASSIGNED_ROLE
Represents RBAC role assignments.

**Semantics:** Identity has been assigned a role on a resource or scope

**Examples:**
- User ASSIGNED_ROLE "Owner" on subscription
- Service principal ASSIGNED_ROLE "Contributor" on resource group
- Managed identity ASSIGNED_ROLE "Reader" on storage account

**Properties:**
- `role_name`: Name of the role
- `scope`: Assignment scope
- `created_at`: When relationship was created

**Emitted by:** `IdentityRule` ([`src/relationship_rules/identity_rule.py`](../src/relationship_rules/identity_rule.py))

---

#### 7. INTEGRATES_WITH
Represents service integrations.

**Semantics:** Source service integrates with target service

**Examples:**
- API Management INTEGRATES_WITH backend API
- Application Insights INTEGRATES_WITH web app
- Log Analytics INTEGRATES_WITH resource (diagnostic settings)

**Properties:**
- `integration_type`: Type of integration
- `created_at`: When relationship was created

---

### Identity Relationships

These relationships are specific to identity and RBAC processing.

**Definition Location:** [`src/relationship_rules/identity_rule.py:14-16`](../src/relationship_rules/identity_rule.py#L14-L16)

#### ASSIGNED_TO
Connects a role assignment to the identity it's assigned to.

**Pattern:** `(RoleAssignment)-[:ASSIGNED_TO]->(User|ServicePrincipal|ManagedIdentity)`

**Semantics:** This role assignment is assigned to this identity

---

#### HAS_ROLE
Connects an identity to the role definition they have.

**Pattern:** `(User|ServicePrincipal|ManagedIdentity)-[:HAS_ROLE]->(RoleDefinition)`

**Semantics:** This identity has been granted this role

---

#### USES_IDENTITY
Connects a resource to the managed identity it uses.

**Pattern:** `(Resource)-[:USES_IDENTITY]->(ManagedIdentity)`

**Semantics:** This resource uses this managed identity for authentication

**Examples:**
- Virtual machine USES_IDENTITY system-assigned identity
- Function app USES_IDENTITY user-assigned identity

---

### Network Relationships

These relationships model network connectivity and security.

**Definition Location:** [`src/relationship_rules/network_rule.py`](../src/relationship_rules/network_rule.py)

#### CONNECTED_TO_PE
Connects a resource to a private endpoint.

**Pattern:** `(Resource)-[:CONNECTED_TO_PE]->(PrivateEndpoint)`

**Semantics:** Resource is accessible via this private endpoint

**Defined at:** [`src/relationship_rules/network_rule.py:10`](../src/relationship_rules/network_rule.py#L10)

---

#### RESOLVES_TO
Connects a DNS zone to a resource.

**Pattern:** `(DNSZone)-[:RESOLVES_TO]->(Resource)`

**Semantics:** This DNS zone resolves to this resource

**Defined at:** [`src/relationship_rules/network_rule.py:11`](../src/relationship_rules/network_rule.py#L11)

---

#### USES_SUBNET
Connects a resource to a subnet.

**Pattern:** `(Resource)-[:USES_SUBNET]->(Resource)` (where target is a subnet)

**Semantics:** Resource is deployed in this subnet

**Defined at:** [`src/relationship_rules/network_rule.py:49`](../src/relationship_rules/network_rule.py#L49)

**Examples:**
- Virtual machine USES_SUBNET "default"
- Private endpoint USES_SUBNET "pe-subnet"

---

#### SECURED_BY
Connects a subnet to a network security group.

**Pattern:** `(Subnet)-[:SECURED_BY]->(NetworkSecurityGroup)`

**Semantics:** This subnet's traffic is controlled by this NSG

**Defined at:** [`src/relationship_rules/network_rule.py:62`](../src/relationship_rules/network_rule.py#L62)

---

### Other Relationships

#### SCAN_SOURCE_NODE
**Dual-Graph Linking Relationship**

Connects an abstracted resource node to its original source node.

**Pattern:** `(abstracted:Resource)-[:SCAN_SOURCE_NODE]->(original:Resource:Original)`

**Semantics:** This abstracted node was created from this original node during scan

**Properties:**
- `scan_id`: ID of the scan that created both nodes
- `tenant_id`: Tenant ID
- `confidence`: Confidence level in the abstraction (typically 1.0)
- `created_at`: When relationship was created

**Created in:** [`src/resource_processor.py:647-672`](../src/resource_processor.py#L647-L672)

**Usage:**
```cypher
# Find original node from abstracted
MATCH (a:Resource {id: 'vm-a1b2c3d4'})-[:SCAN_SOURCE_NODE]->(o:Resource:Original)
RETURN o.id

# Find abstracted node from original
MATCH (o:Resource:Original)-[:SCAN_SOURCE_NODE]-(a:Resource)
WHERE o.id = '/subscriptions/12345.../my-vm'
RETURN a.id
```

**Notes:**
- Every abstracted resource node has exactly ONE outgoing SCAN_SOURCE_NODE relationship
- Every original resource node has exactly ONE incoming SCAN_SOURCE_NODE relationship
- This relationship enables bidirectional lookup between graph views

---

#### TAGGED_WITH
Connects a resource to a tag.

**Pattern:** `(Resource)-[:TAGGED_WITH]->(Tag)`

**Semantics:** This resource has this tag applied

**Defined at:** [`src/resource_processor.py:534`](../src/resource_processor.py#L534)

**Emitted by:** `TagRule` ([`src/relationship_rules/tag_rule.py`](../src/relationship_rules/tag_rule.py))

**Notes (Dual-Graph):**
- Both abstracted and original resource nodes can have TAGGED_WITH relationships
- Tag nodes are shared between graphs (not duplicated)

---

## Schema Assembly Process

The graph schema is assembled through a multi-stage process:

### Stage 1: Resource Discovery
**File:** [`src/services/azure_discovery_service.py`](../src/services/azure_discovery_service.py)

1. Azure SDK queries all subscriptions
2. Resources are discovered with pagination
3. Raw Azure API responses are collected

### Stage 2: Node Creation
**File:** [`src/resource_processor.py`](../src/resource_processor.py)

The `DatabaseOperations` class provides generic methods for creating nodes:

#### `upsert_subscription()`
**Lines:** 178-195

Creates or updates subscription nodes.

```cypher
MERGE (s:Subscription {id: $id})
SET s.name = $name, s.updated_at = datetime()
```

---

#### `upsert_resource_group()`
**Lines:** 197-219

Creates or updates resource group nodes and their relationship to subscription.

```cypher
MERGE (rg:ResourceGroup {id: $id})
SET rg += $properties, rg.updated_at = datetime()

MERGE (s:Subscription {id: $subscription_id})
MERGE (s)-[:CONTAINS]->(rg)
```

---

#### `upsert_resource()`
**Lines:** 221-316

Creates or updates resource nodes and their relationships to resource group and subscription.

```cypher
MERGE (r:Resource {id: $id})
SET r += $properties, r.updated_at = datetime()

MERGE (rg:ResourceGroup {id: $resource_group_id})
MERGE (rg)-[:CONTAINS]->(r)
```

---

#### `upsert_generic()`
**Lines:** 401-439

**This is the core method** for creating any node type dynamically. It accepts:
- `label`: Node label (e.g., "User", "RoleDefinition")
- `key_prop`: Property to use as unique key (e.g., "id")
- `key_value`: Value of the key property
- `props`: Dictionary of additional properties

```cypher
MERGE (n:{label} {{key_prop}: $key_value})
SET n += $props, n.updated_at = datetime()
```

This method enables the schema to be **extended without code changes** to the database layer.

---

#### `create_generic_rel()`
**Lines:** 441-477

Creates relationships between nodes dynamically. It accepts:
- `from_label`, `from_key_prop`, `from_key_value`: Source node specification
- `to_label`, `to_key_prop`, `to_key_value`: Target node specification
- `rel_type`: Relationship type (e.g., "DEPENDS_ON")
- `props`: Relationship properties (optional)

```cypher
MATCH (from:{from_label} {{from_key_prop}: $from_key_value})
MATCH (to:{to_label} {{to_key_prop}: $to_key_value})
MERGE (from)-[r:{rel_type}]->(to)
SET r += $props
```

This enables **rule-based relationship creation** without hardcoded Cypher.

---

### Stage 3: Relationship Rules Execution
**File:** [`src/relationship_rules/__init__.py`](../src/relationship_rules/__init__.py)

Relationship rules are executed in a specific order to build the graph topology. Each rule implements the `RelationshipRule` base class.

**Base Class:** [`src/relationship_rules/relationship_rule.py:5-22`](../src/relationship_rules/relationship_rule.py#L5-L22)

**Abstract Methods:**
- `applies(resource)`: Determines if rule applies to a resource
- `emit(resource)`: Emits relationships for the resource

**Execution Order:**

1. **SubnetExtractionRule** (`subnet_extraction_rule.py`)
   - Extracts subnets from virtual networks
   - Creates `CONTAINS` relationships (VNet → Subnet)

2. **NetworkRule** (`network_rule.py`)
   - Creates network connectivity relationships
   - Emits: `USES_SUBNET`, `SECURED_BY`, `CONNECTED_TO_PE`, `RESOLVES_TO`

3. **IdentityRule** (`identity_rule.py`)
   - Creates identity and RBAC relationships
   - Emits: `ASSIGNED_TO`, `HAS_ROLE`, `USES_IDENTITY`

4. **TagRule** (`tag_rule.py`)
   - Creates tag relationships
   - Emits: `TAGGED_WITH`

5. **RegionRule** (`region_rule.py`)
   - Creates location-based relationships
   - Emits: `LOCATED_IN`

6. **CreatorRule** (`creator_rule.py`)
   - Creates creator relationships
   - Emits: `CREATED_BY`

7. **MonitoringRule** (`monitoring_rule.py`)
   - Creates monitoring relationships
   - Emits: `MONITORS`, `MONITORED_BY`

8. **DiagnosticRule** (`diagnostic_rule.py`)
   - Creates diagnostic settings relationships
   - Emits: `LOGS_TO`

9. **DependsOnRule** (`depends_on_rule.py`)
   - Creates dependency relationships
   - Emits: `DEPENDS_ON`

**Why This Order Matters:**
- Network topology must be established before identity
- Identity must exist before RBAC assignments
- Dependencies are evaluated last (require full graph context)

---

### Stage 4: Azure AD Identity Import
**File:** [`src/services/azure_discovery_service.py`](../src/services/azure_discovery_service.py)

If enabled, imports identity information from Microsoft Graph API:

1. Query Azure AD for users and groups
2. Create `User` and `Group` nodes
3. Import group memberships
4. Create `MEMBER_OF` relationships
5. Link to existing RBAC assignments

---

### Stage 5: Relationship Enrichment
**File:** [`src/services/resource_processing_service.py`](../src/services/resource_processing_service.py)

After all rules execute:

1. Rules may emit additional relationships based on graph state
2. Transitive relationships may be inferred
3. Cleanup of orphaned relationships
4. Index creation and optimization

---

## Data Models

### Pydantic Schema Definitions

**File:** [`src/tenant_spec_models.py`](../src/tenant_spec_models.py) (Lines 1-963)

This file contains the complete Pydantic models that serve as the **schema definition layer** for the graph database. While Neo4j stores data dynamically, these Pydantic models provide type safety, validation, and structure for the Python application layer.

These models are used for:

- Validation during data import
- Serialization to/from JSON and YAML
- Type checking in Python code
- API contracts for MCP server

**Key Models:**

#### Enums (Lines 10-54)
- `GroupType`: Security, Microsoft365, Distribution, MailEnabledSecurity, Dynamic
- `AuthenticationMethod`: Password, MfaSms, MfaVoice, MfaApp, Fido2, WindowsHello, Certificate
- `RiskLevel`: Low, Medium, High, None, Hidden
- `AccessLevel`: Eligible, Active
- `PermissionType`: Application, Delegated

#### Node Models
- `User` (lines 58-136)
- `Group` (lines 139-219)
- `ServicePrincipal` (lines 263-347)
- `ManagedIdentity` (lines 350-364)
- `AdminUnit` (lines 367-381)
- `ConditionalAccessPolicy` (lines 447-482)
- `PIMAssignment` (lines 485-539)
- `AdminRole` (lines 542-580)
- `DirectoryRoleAssignment` (lines 583-619)
- `RBACAssignment` (lines 623-644)
- `Resource` (lines 757-783)
- `ResourceGroup` (lines 787-807)
- `Subscription` (lines 811-829)
- `Tenant` (lines 833-917)

#### Relationship Model (Lines 648-753)
The `Relationship` class defines relationship properties:
- `source_id`: Source node ID
- `target_id`: Target node ID
- `type`: Relationship type
- `original_type`: Original relationship type (before transformation)
- `narrative_context`: Human-readable description
- `is_hierarchical`: Whether relationship is hierarchical
- `is_nested`: Whether relationship is nested
- `is_cross_tenant`: Whether relationship crosses tenants
- `is_temporary`: Whether relationship is temporary (e.g., PIM)
- `start_datetime`: Start time (for temporal relationships)
- `end_datetime`: End time (for temporal relationships)
- `attributes`: Additional attributes (JSON)

---

## Code References

### Key Files

| File | Purpose | Lines |
|------|---------|-------|
| [`src/resource_processor.py`](../src/resource_processor.py) | Database operations, node/relationship creation | 172-477 |
| [`src/tenant_spec_models.py`](../src/tenant_spec_models.py) | Pydantic data models for all node types | 1-963 |
| [`src/tenant_creator.py`](../src/tenant_creator.py) | Canonical relationship type definitions | 79-86 |
| [`src/relationship_rules/__init__.py`](../src/relationship_rules/__init__.py) | Rule execution order | Full file |
| [`src/relationship_rules/relationship_rule.py`](../src/relationship_rules/relationship_rule.py) | Base class for all rules | 5-22 |
| [`src/relationship_rules/identity_rule.py`](../src/relationship_rules/identity_rule.py) | Identity and RBAC relationships | Full file |
| [`src/relationship_rules/network_rule.py`](../src/relationship_rules/network_rule.py) | Network relationships | Full file |
| [`src/relationship_rules/subnet_extraction_rule.py`](../src/relationship_rules/subnet_extraction_rule.py) | Subnet relationships | Full file |
| [`src/services/azure_discovery_service.py`](../src/services/azure_discovery_service.py) | Azure resource discovery | Full file |
| [`src/services/resource_processing_service.py`](../src/services/resource_processing_service.py) | Resource processing orchestration | Full file |
| [`src/utils/session_manager.py`](../src/utils/session_manager.py) | Neo4j connection management | 86-150 |

### Migration System

**Directory:** `migrations/`

Database schema versioning and migrations are managed here. Each migration file:
- Has a version number prefix (e.g., `001_initial_schema.py`)
- Implements `up()` and `down()` methods
- Can create indexes, constraints, or modify existing data

---

## Visualization

### Relationship Colors

The 3D visualization assigns colors to relationship types for visual clarity.

**File:** [`src/visualization/javascript_builder.py:533-539`](../src/visualization/javascript_builder.py#L533-L539)

| Relationship | Color | Hex Code |
|--------------|-------|----------|
| CONTAINS | Blue | #74b9ff |
| TAGGED_WITH | Green | #00b894 |
| CONNECTED_TO | Pink | #fd79a8 |
| CONNECTED_TO_PE | Violet | #b388ff |
| RESOLVES_TO | Purple | #a29bfe |
| DEPENDS_ON | Yellow | #fdcb6e |

---

## Schema Design Notes

### Naming Conventions

The graph schema follows these naming conventions for consistency:

- **Node Labels**: PascalCase (e.g., `Resource`, `ServicePrincipal`, `RoleDefinition`)
- **Property Names**: snake_case (e.g., `updated_at`, `subscription_id`, `llm_description`)
- **Relationship Types**: SCREAMING_SNAKE_CASE (e.g., `DEPENDS_ON`, `USES_IDENTITY`, `CONNECTED_TO`)

### Property Cardinality

Most node properties are **optional** unless otherwise noted. Key exceptions:

- **Required Properties**:
  - `id`: Required on all nodes for uniqueness
  - `updated_at`: Automatically set/updated on all nodes

- **Resource-Specific**: Properties like `type`, `name`, and `location` are typically present on Resource nodes but vary by Azure resource type

### Relationship Cardinality Patterns

Common cardinality patterns in the graph:

| Pattern | Example | Relationship |
|---------|---------|--------------|
| 1:N | One subscription CONTAINS many resource groups | `(Subscription)-[:CONTAINS]->(ResourceGroup)` |
| N:N | Many resources can DEPEND_ON many resources | `(Resource)-[:DEPENDS_ON]->(Resource)` |
| 1:1 | One resource USES_IDENTITY one managed identity | `(Resource)-[:USES_IDENTITY]->(ManagedIdentity)` |
| N:1 | Many resources USES_SUBNET one subnet | `(Resource)-[:USES_SUBNET]->(Subnet)` |

Note: Neo4j does not enforce cardinality - these patterns are logical constraints based on Azure's resource model.

### Query Performance Considerations

- All nodes are indexed on their `id` property via uniqueness constraints in migrations
- MERGE operations on `id` properties are optimized by these constraints
- Relationship traversals are fast due to Neo4j's graph-native storage
- For complex queries, use `EXPLAIN` and `PROFILE` to analyze query plans

---

## Best Practices

### Adding New Node Types

1. **Define Pydantic model** in [`src/tenant_spec_models.py`](../src/tenant_spec_models.py)
2. **Create node** using `DatabaseOperations.upsert_generic()`
3. **Add to visualization** in `javascript_builder.py` (if needed)
4. **Document here** with properties and examples

### Adding New Relationship Types

1. **Choose semantic type** from canonical relationships (or create new)
2. **Create relationship rule** class inheriting from `RelationshipRule`
3. **Implement `applies()` and `emit()` methods**
4. **Register rule** in [`src/relationship_rules/__init__.py`](../src/relationship_rules/__init__.py)
5. **Add color mapping** in `javascript_builder.py`
6. **Document here** with pattern and examples

### Querying the Graph

#### Dual-Graph Query Patterns

**Query abstracted resources (DEFAULT):**
```cypher
// Returns only abstracted nodes (IaC-ready IDs)
MATCH (r:Resource {type: 'Microsoft.Compute/virtualMachines'})
WHERE NOT r:Original
RETURN r.name, r.id, r.location
```

**Query original resources:**
```cypher
// Returns only original nodes (real Azure IDs)
MATCH (r:Resource:Original {type: 'Microsoft.Compute/virtualMachines'})
RETURN r.name, r.id, r.location
```

**Find original from abstracted:**
```cypher
// Traverse SCAN_SOURCE_NODE to find source
MATCH (a:Resource {id: 'vm-a1b2c3d4'})-[:SCAN_SOURCE_NODE]->(o:Resource:Original)
RETURN o.id AS original_azure_id, a.id AS abstracted_id
```

**Compare both graphs:**
```cypher
// Count nodes in each graph
MATCH (a:Resource) WHERE NOT a:Original
WITH count(a) AS abstracted_count
MATCH (o:Resource:Original)
RETURN abstracted_count, count(o) AS original_count
```

#### Find all resources of a specific type
```cypher
MATCH (r:Resource {type: 'Microsoft.Compute/virtualMachines'})
WHERE NOT r:Original  // Ensures we get abstracted nodes
RETURN r.name, r.location
```

#### Find resources with specific tag
```cypher
MATCH (r:Resource)-[:TAGGED_WITH]->(t:Tag {key: 'environment'})
WHERE t.value = 'production' AND NOT r:Original
RETURN r.name, r.type
```

#### Find identity with specific role
```cypher
MATCH (u:User)-[:HAS_ROLE]->(rd:RoleDefinition {roleName: 'Owner'})
RETURN u.displayName, u.userPrincipalName
```

#### Find resource dependencies
```cypher
MATCH path = (r1:Resource)-[:DEPENDS_ON*]->(r2:Resource)
WHERE r1.name = 'my-web-app' AND NOT r1:Original
RETURN path
```

#### Find network connectivity
```cypher
MATCH (r:Resource)-[:USES_SUBNET]->(subnet:Resource)-[:SECURED_BY]->(nsg:Resource)
WHERE r.type = 'Microsoft.Compute/virtualMachines' AND NOT r:Original
RETURN r.name, subnet.name, nsg.name
```

---

## Related Documentation

- Architecture Improvements (see architecture/ directory) - System architecture and design patterns
- [IaC Subset & Rules System](design/iac_subset_bicep.md) - IaC generation and transformation rules
- [CLAUDE.md](../CLAUDE.md) - Development guide and project overview
- [README.md](../README.md) - Project overview and quick start

---

## Appendix: Complete Node Type List

**Azure Infrastructure:**
- Tenant
- Subscription
- ResourceGroup
- Resource (generic for all Azure resources)
- Tag

**Identity:**
- User
- Group
- ServicePrincipal
- ManagedIdentity
- IdentityGroup

**RBAC:**
- RoleDefinition
- RoleAssignment
- AdminRole
- DirectoryRoleAssignment

**Network:**
- PrivateEndpoint
- DNSZone
- (Subnets are Resource nodes with specific type)
- (VNets are Resource nodes with specific type)
- (NSGs are Resource nodes with specific type)

**Administrative:**
- AdminUnit
- ConditionalAccessPolicy
- PIMAssignment

---

## Appendix: Complete Relationship Type List

**Canonical:**
- DEPENDS_ON
- USES
- CONNECTS_TO
- CONTAINS
- MEMBER_OF
- ASSIGNED_ROLE
- INTEGRATES_WITH

**Identity:**
- ASSIGNED_TO
- HAS_ROLE
- USES_IDENTITY

**Network:**
- CONNECTED_TO_PE
- RESOLVES_TO
- USES_SUBNET
- SECURED_BY

**Other:**
- SCAN_SOURCE_NODE (dual-graph linking)
- TAGGED_WITH
- LOCATED_IN
- CREATED_BY
- MONITORS
- MONITORED_BY
- LOGS_TO

---

*Last Updated: 2025-11-05*
*Related Issues: #420 (dual-graph architecture), #423 (schema documentation)*

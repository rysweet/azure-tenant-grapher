# CTF Overlay Schema Design for Neo4j

## Overview

This document defines the Neo4j graph schema extension for CTF (Capture The Flag) overlay system. The design ensures clean separation from existing infrastructure, supports multiple concurrent scenarios, and provides fast querying without modifying the core dual-graph structure.

## Design Principles

1. **Non-invasive**: No modifications to existing `:Resource` or `:Resource:Original` nodes
2. **Clean Separation**: CTF data lives in separate nodes and relationships
3. **Query Performance**: Indexed lookups for fast CTF resource filtering
4. **Easy Cleanup**: Complete scenario removal without affecting infrastructure
5. **Multiple Scenarios**: Support concurrent CTF scenarios without conflicts

## 1. Node Schema

### 1.1 CTFScenario Node

```cypher
// Node structure
(:CTFScenario {
    scenario_id: STRING,           // Unique identifier (e.g., "webshell-challenge-001")
    name: STRING,                  // Human-readable name
    description: STRING,           // Scenario description
    terraform_content: STRING,     // Full Terraform configuration
    created_at: DATETIME,          // Creation timestamp
    updated_at: DATETIME,          // Last update timestamp
    deployment_status: STRING,     // "pending" | "deploying" | "deployed" | "failed" | "destroyed"
    deployment_error: STRING,      // Error message if deployment failed (nullable)
    resource_group: STRING,        // Target Azure resource group
    location: STRING,              // Azure region
    tags: STRING                   // JSON string of tags/labels for categorization
})

// Constraints
CREATE CONSTRAINT ctf_scenario_id_unique IF NOT EXISTS
FOR (s:CTFScenario)
REQUIRE s.scenario_id IS UNIQUE;

// Indexes
CREATE INDEX ctf_scenario_status IF NOT EXISTS
FOR (s:CTFScenario)
ON (s.deployment_status);

CREATE INDEX ctf_scenario_rg IF NOT EXISTS
FOR (s:CTFScenario)
ON (s.resource_group);
```

**Design Rationale**:
- **scenario_id**: Unique identifier for scenario tracking
- **terraform_content**: Stored directly on scenario node (typically < 10KB, avoids extra node complexity)
- **deployment_status**: Enables filtering by deployment state
- **tags**: JSON string for flexible categorization (e.g., `{"difficulty": "medium", "category": "web-exploitation"}`)

### 1.2 CTF Resource Annotation Strategy

**Approach: Separate CTFResource Nodes (Recommended)**

```cypher
// CTF Resource annotation node
(:CTFResource {
    resource_id: STRING,           // Matches abstracted ID from :Resource node
    role: STRING,                  // Resource's role in scenario (e.g., "vulnerable-vm", "attacker-vm", "target")
    public_ip: STRING,             // Public IP if exposed (nullable)
    access_method: STRING,         // How to access (e.g., "ssh", "rdp", "http") (nullable)
    credentials: STRING,           // JSON string of credentials (nullable, encrypted separately)
    notes: STRING,                 // Custom notes for scenario creators (nullable)
    created_at: DATETIME,          // When resource was added to scenario
    updated_at: DATETIME           // Last update timestamp
})

// Constraints
CREATE CONSTRAINT ctf_resource_id_unique IF NOT EXISTS
FOR (r:CTFResource)
REQUIRE r.resource_id IS UNIQUE;
```

**Design Rationale**:
- **Separate nodes**: Preserves existing schema, allows multiple scenarios to reference same infrastructure resource
- **resource_id**: Links to abstracted :Resource node via relationship
- **role**: Describes purpose in CTF scenario
- **Flexible metadata**: Supports CTF-specific properties (IPs, credentials, access methods)

**Alternative Considered (Labels/Properties on :Resource)**:
- ❌ **Rejected**: Would violate non-invasive principle
- ❌ **Rejected**: Makes cleanup harder (need to remove properties individually)
- ❌ **Rejected**: Pollutes infrastructure graph with CTF-specific data

## 2. Relationship Schema

### 2.1 CTF Scenario → Resource

```cypher
// Primary relationship: Scenario contains resources
(s:CTFScenario)-[:CONTAINS_RESOURCE]->(c:CTFResource)

// Properties on relationship
{
    added_at: DATETIME,            // When resource was added to scenario
    deployment_order: INTEGER      // Order for deployment (1, 2, 3...)
}
```

### 2.2 CTF Resource → Infrastructure Resource

```cypher
// Link CTF annotation to actual infrastructure
(c:CTFResource)-[:ANNOTATES]->(r:Resource)

// Properties on relationship
{
    created_at: DATETIME           // When annotation was created
}

// Constraint: CTFResource can only annotate abstracted resources (not originals)
// Enforced by query patterns, not constraint
```

### 2.3 Complete Graph Pattern

```
(:Tenant)
    ↓ :HAS_TENANT_SEED
(:TenantSeed)
    ↓ :CONTAINS_RESOURCE_GROUP
(:ResourceGroup)
    ↓ :CONTAINS_RESOURCE
(:Resource)  ←────[:ANNOTATES]──── (:CTFResource) ←────[:CONTAINS_RESOURCE]──── (:CTFScenario)
    ↓ :SCAN_SOURCE_NODE
(:Resource:Original)
```

**Design Rationale**:
- **CONTAINS_RESOURCE**: Clear ownership, supports ORDER BY for deployment
- **ANNOTATES**: Indicates CTFResource is metadata about Resource
- **No direct Scenario → Resource**: Maintains separation, forces explicit CTF metadata

## 3. Cypher Queries

### 3.1 Create CTF Scenario with Terraform Content

```cypher
// Create new CTF scenario
CREATE (s:CTFScenario {
    scenario_id: $scenario_id,
    name: $name,
    description: $description,
    terraform_content: $terraform_content,
    created_at: datetime(),
    updated_at: datetime(),
    deployment_status: 'pending',
    resource_group: $resource_group,
    location: $location,
    tags: $tags
})
RETURN s;
```

**Parameters**:
```json
{
    "scenario_id": "webshell-challenge-001",
    "name": "Web Shell Detection Challenge",
    "description": "Red team deploys web shell, blue team must detect",
    "terraform_content": "terraform { ... }",
    "resource_group": "rg-ctf-webshell",
    "location": "eastus",
    "tags": "{\"difficulty\": \"medium\", \"category\": \"web\"}"
}
```

### 3.2 Annotate Resource as Part of CTF Scenario

```cypher
// Step 1: Create CTFResource annotation
CREATE (c:CTFResource {
    resource_id: $resource_id,
    role: $role,
    public_ip: $public_ip,
    access_method: $access_method,
    credentials: $credentials,
    notes: $notes,
    created_at: datetime(),
    updated_at: datetime()
})

// Step 2: Link to scenario
WITH c
MATCH (s:CTFScenario {scenario_id: $scenario_id})
CREATE (s)-[:CONTAINS_RESOURCE {
    added_at: datetime(),
    deployment_order: $deployment_order
}]->(c)

// Step 3: Link to infrastructure resource
WITH c
MATCH (r:Resource {id: $resource_id})
WHERE NOT r:Original  // Safety check: only annotate abstracted resources
CREATE (c)-[:ANNOTATES {
    created_at: datetime()
}]->(r)

RETURN c, s, r;
```

**Parameters**:
```json
{
    "resource_id": "vm-a1b2c3d4e5f6g7h8",
    "scenario_id": "webshell-challenge-001",
    "role": "vulnerable-web-server",
    "public_ip": "20.51.23.45",
    "access_method": "ssh",
    "credentials": "{\"username\": \"ctfadmin\", \"ssh_key\": \"...\"}",
    "notes": "Ubuntu 20.04 with intentional Apache vulnerability",
    "deployment_order": 1
}
```

### 3.3 Query All Resources for a Scenario

```cypher
// Get all resources in a CTF scenario with full details
MATCH (s:CTFScenario {scenario_id: $scenario_id})
      -[cr:CONTAINS_RESOURCE]->(c:CTFResource)
      -[:ANNOTATES]->(r:Resource)
RETURN
    s.scenario_id AS scenario_id,
    s.name AS scenario_name,
    s.deployment_status AS scenario_status,
    c.resource_id AS resource_id,
    c.role AS ctf_role,
    c.public_ip AS public_ip,
    c.access_method AS access_method,
    c.credentials AS credentials,
    r.name AS resource_name,
    r.type AS resource_type,
    r.location AS location,
    r.properties AS infrastructure_properties,
    cr.deployment_order AS deployment_order
ORDER BY cr.deployment_order;
```

**Parameters**:
```json
{
    "scenario_id": "webshell-challenge-001"
}
```

**Output**:
```json
[
    {
        "scenario_id": "webshell-challenge-001",
        "scenario_name": "Web Shell Detection Challenge",
        "scenario_status": "deployed",
        "resource_id": "vm-a1b2c3d4e5f6g7h8",
        "ctf_role": "vulnerable-web-server",
        "public_ip": "20.51.23.45",
        "access_method": "ssh",
        "credentials": "{\"username\": \"ctfadmin\", \"ssh_key\": \"...\"}",
        "resource_name": "vm-webserver-001",
        "resource_type": "Microsoft.Compute/virtualMachines",
        "location": "eastus",
        "infrastructure_properties": "{...}",
        "deployment_order": 1
    }
]
```

### 3.4 Update Deployment Status

```cypher
// Update scenario deployment status
MATCH (s:CTFScenario {scenario_id: $scenario_id})
SET
    s.deployment_status = $status,
    s.deployment_error = $error,  // Null if no error
    s.updated_at = datetime()
RETURN s;
```

**Parameters (Success)**:
```json
{
    "scenario_id": "webshell-challenge-001",
    "status": "deployed",
    "error": null
}
```

**Parameters (Failure)**:
```json
{
    "scenario_id": "webshell-challenge-001",
    "status": "failed",
    "error": "Terraform apply failed: Quota exceeded for VM SKU Standard_D2s_v3"
}
```

### 3.5 Remove CTF Annotations (Cleanup)

```cypher
// Complete scenario cleanup (removes CTF overlay, preserves infrastructure)
MATCH (s:CTFScenario {scenario_id: $scenario_id})
      -[:CONTAINS_RESOURCE]->(c:CTFResource)
DETACH DELETE s, c;
```

**Design Rationale**:
- **DETACH DELETE**: Removes nodes and all relationships
- **Two-node deletion**: Removes scenario + all CTF resource annotations
- **Infrastructure preserved**: :Resource and :Resource:Original nodes untouched
- **Idempotent**: Safe to run multiple times

**Alternative (Soft Delete)**:
```cypher
// Mark scenario as deleted without removing nodes
MATCH (s:CTFScenario {scenario_id: $scenario_id})
SET
    s.deployment_status = 'destroyed',
    s.deleted_at = datetime(),
    s.updated_at = datetime()
RETURN s;
```

### 3.6 List All CTF Scenarios

```cypher
// Get all scenarios with resource counts
MATCH (s:CTFScenario)
OPTIONAL MATCH (s)-[:CONTAINS_RESOURCE]->(c:CTFResource)
RETURN
    s.scenario_id AS scenario_id,
    s.name AS name,
    s.description AS description,
    s.deployment_status AS status,
    s.created_at AS created_at,
    s.resource_group AS resource_group,
    s.location AS location,
    s.tags AS tags,
    count(c) AS resource_count
ORDER BY s.created_at DESC;
```

### 3.7 Find Resources Used in Multiple Scenarios

```cypher
// Detect shared infrastructure across scenarios
MATCH (c:CTFResource)-[:ANNOTATES]->(r:Resource)
WITH r, collect(DISTINCT c.resource_id) AS ctf_resources
WHERE size(ctf_resources) > 1
MATCH (c2:CTFResource)-[:ANNOTATES]->(r)
      <-[:CONTAINS_RESOURCE]-(s:CTFScenario)
RETURN
    r.id AS resource_id,
    r.name AS resource_name,
    r.type AS resource_type,
    collect(DISTINCT s.scenario_id) AS scenarios
ORDER BY size(scenarios) DESC;
```

## 4. Indexes & Constraints

### 4.1 Unique Constraints

```cypher
// Ensure scenario IDs are unique
CREATE CONSTRAINT ctf_scenario_id_unique IF NOT EXISTS
FOR (s:CTFScenario)
REQUIRE s.scenario_id IS UNIQUE;

// Ensure CTFResource IDs are unique (one annotation per resource)
CREATE CONSTRAINT ctf_resource_id_unique IF NOT EXISTS
FOR (r:CTFResource)
REQUIRE r.resource_id IS UNIQUE;
```

**Design Rationale**:
- **scenario_id uniqueness**: Prevents duplicate scenarios
- **resource_id uniqueness**: Each infrastructure resource has one CTF annotation
  - If resource needs multiple roles, create multiple scenarios or use JSON in `role` field

### 4.2 Performance Indexes

```cypher
// Fast lookup by deployment status
CREATE INDEX ctf_scenario_status IF NOT EXISTS
FOR (s:CTFScenario)
ON (s.deployment_status);

// Fast lookup by resource group
CREATE INDEX ctf_scenario_rg IF NOT EXISTS
FOR (s:CTFScenario)
ON (s.resource_group);

// Fast lookup by CTF resource role
CREATE INDEX ctf_resource_role IF NOT EXISTS
FOR (r:CTFResource)
ON (r.role);

// Fast lookup by scenario creation date
CREATE INDEX ctf_scenario_created IF NOT EXISTS
FOR (s:CTFScenario)
ON (s.created_at);
```

**Query Performance Impact**:
- **Status index**: Speeds up `WHERE deployment_status = 'deployed'` filters
- **Resource group index**: Optimizes resource group-based queries
- **Role index**: Fast filtering by CTF role (e.g., "all vulnerable VMs")
- **Created date index**: Efficient time-based queries and sorting

### 4.3 Index Usage Examples

```cypher
// Query uses ctf_scenario_status index
MATCH (s:CTFScenario)
WHERE s.deployment_status = 'deployed'
RETURN s;

// Query uses ctf_resource_role index
MATCH (c:CTFResource)
WHERE c.role = 'vulnerable-vm'
RETURN c;

// Query uses ctf_scenario_created index
MATCH (s:CTFScenario)
WHERE s.created_at > datetime() - duration('P7D')  // Last 7 days
RETURN s
ORDER BY s.created_at DESC;
```

## 5. Migration Strategy

### 5.1 Schema Migration Script

```cypher
// migration_001_ctf_overlay.cypher
// Run this script to add CTF schema to existing Neo4j database

// Step 1: Create constraints
CREATE CONSTRAINT ctf_scenario_id_unique IF NOT EXISTS
FOR (s:CTFScenario)
REQUIRE s.scenario_id IS UNIQUE;

CREATE CONSTRAINT ctf_resource_id_unique IF NOT EXISTS
FOR (r:CTFResource)
REQUIRE r.resource_id IS UNIQUE;

// Step 2: Create indexes
CREATE INDEX ctf_scenario_status IF NOT EXISTS
FOR (s:CTFScenario)
ON (s.deployment_status);

CREATE INDEX ctf_scenario_rg IF NOT EXISTS
FOR (s:CTFScenario)
ON (s.resource_group);

CREATE INDEX ctf_resource_role IF NOT EXISTS
FOR (r:CTFResource)
ON (r.role);

CREATE INDEX ctf_scenario_created IF NOT EXISTS
FOR (s:CTFScenario)
ON (s.created_at);

// Step 3: Verify no conflicts with existing data
MATCH (n)
WHERE n:CTFScenario OR n:CTFResource
RETURN count(n) AS existing_ctf_nodes;
// Expected: 0 (no CTF nodes in fresh installation)
```

### 5.2 Backward Compatibility

**Existing Query Patterns (Unaffected)**:

```cypher
// Standard infrastructure queries still work
MATCH (r:Resource)
WHERE NOT r:Original
RETURN r;

// Relationship traversal unchanged
MATCH (rg:ResourceGroup)-[:CONTAINS_RESOURCE]->(r:Resource)
RETURN rg, r;

// Original node queries unchanged
MATCH (r:Resource)-[:SCAN_SOURCE_NODE]->(o:Resource:Original)
RETURN r, o;
```

**Why This Works**:
1. **No label changes**: `:Resource` and `:Resource:Original` untouched
2. **No property conflicts**: CTF data lives in separate nodes
3. **No relationship conflicts**: New relationship types (`:CONTAINS_RESOURCE`, `:ANNOTATES`) don't overlap with existing `:SCAN_SOURCE_NODE`
4. **Query isolation**: CTF queries explicitly `MATCH` on `:CTFScenario` or `:CTFResource`

### 5.3 Rollback Strategy

```cypher
// rollback_ctf_overlay.cypher
// Complete removal of CTF schema

// Step 1: Remove all CTF data
MATCH (s:CTFScenario)
DETACH DELETE s;

MATCH (c:CTFResource)
DETACH DELETE c;

// Step 2: Drop indexes
DROP INDEX ctf_scenario_status IF EXISTS;
DROP INDEX ctf_scenario_rg IF EXISTS;
DROP INDEX ctf_resource_role IF EXISTS;
DROP INDEX ctf_scenario_created IF EXISTS;

// Step 3: Drop constraints
DROP CONSTRAINT ctf_scenario_id_unique IF EXISTS;
DROP CONSTRAINT ctf_resource_id_unique IF EXISTS;

// Step 4: Verify cleanup
MATCH (n)
WHERE n:CTFScenario OR n:CTFResource
RETURN count(n) AS remaining_ctf_nodes;
// Expected: 0
```

## 6. Example Workflow

### 6.1 Complete Scenario Lifecycle

```cypher
// 1. Create scenario
CREATE (s:CTFScenario {
    scenario_id: 'privilege-escalation-001',
    name: 'Linux Privilege Escalation',
    description: 'Exploit misconfigured sudo to gain root',
    terraform_content: 'resource "azurerm_virtual_machine" "target" { ... }',
    created_at: datetime(),
    updated_at: datetime(),
    deployment_status: 'pending',
    resource_group: 'rg-ctf-privesc',
    location: 'westus2',
    tags: '{"difficulty": "hard", "category": "privilege-escalation"}'
});

// 2. Deploy infrastructure (external Terraform)
// ... Terraform apply creates resources ...

// 3. Update deployment status
MATCH (s:CTFScenario {scenario_id: 'privilege-escalation-001'})
SET
    s.deployment_status = 'deployed',
    s.updated_at = datetime();

// 4. Annotate deployed resources
CREATE (c1:CTFResource {
    resource_id: 'vm-target-abc123',
    role: 'vulnerable-target',
    public_ip: '40.78.123.45',
    access_method: 'ssh',
    credentials: '{"username": "lowpriv", "password": "weak123"}',
    notes: 'Misconfigured sudo allowing /usr/bin/vim',
    created_at: datetime(),
    updated_at: datetime()
});

MATCH (s:CTFScenario {scenario_id: 'privilege-escalation-001'}),
      (c:CTFResource {resource_id: 'vm-target-abc123'}),
      (r:Resource {id: 'vm-target-abc123'})
WHERE NOT r:Original
CREATE (s)-[:CONTAINS_RESOURCE {added_at: datetime(), deployment_order: 1}]->(c)
CREATE (c)-[:ANNOTATES {created_at: datetime()}]->(r);

// 5. Query scenario resources
MATCH (s:CTFScenario {scenario_id: 'privilege-escalation-001'})
      -[cr:CONTAINS_RESOURCE]->(c:CTFResource)
      -[:ANNOTATES]->(r:Resource)
RETURN s, c, r
ORDER BY cr.deployment_order;

// 6. Cleanup when done
MATCH (s:CTFScenario {scenario_id: 'privilege-escalation-001'})
      -[:CONTAINS_RESOURCE]->(c:CTFResource)
DETACH DELETE s, c;
```

## 7. Advanced Patterns

### 7.1 Multi-Tenant CTF Scenarios

```cypher
// Link scenarios to tenants for isolation
MATCH (t:Tenant {tenant_id: $tenant_id})
CREATE (s:CTFScenario {
    scenario_id: $scenario_id,
    tenant_id: t.tenant_id,  // Add tenant_id property
    // ... other properties ...
})
CREATE (t)-[:HAS_CTF_SCENARIO]->(s);

// Query scenarios for specific tenant
MATCH (t:Tenant {tenant_id: $tenant_id})-[:HAS_CTF_SCENARIO]->(s:CTFScenario)
RETURN s;
```

### 7.2 Scenario Templates

```cypher
// Store reusable templates
CREATE (t:CTFTemplate {
    template_id: 'web-shell-template',
    name: 'Web Shell Detection Template',
    terraform_template: 'resource "azurerm_..." { ... }',
    default_location: 'eastus',
    default_tags: '{"category": "web-exploitation"}',
    created_at: datetime()
});

// Instantiate from template
MATCH (t:CTFTemplate {template_id: 'web-shell-template'})
CREATE (s:CTFScenario {
    scenario_id: 'webshell-instance-' + randomUUID(),
    name: t.name + ' - Instance',
    terraform_content: t.terraform_template,
    location: t.default_location,
    tags: t.default_tags,
    deployment_status: 'pending',
    created_at: datetime(),
    updated_at: datetime()
})
CREATE (t)-[:INSTANTIATED_AS]->(s)
RETURN s;
```

### 7.3 Scenario Dependencies

```cypher
// Model dependencies between scenarios
MATCH (s1:CTFScenario {scenario_id: 'network-recon-001'}),
      (s2:CTFScenario {scenario_id: 'lateral-movement-002'})
CREATE (s2)-[:DEPENDS_ON {
    reason: 'Requires recon scenario to be deployed first',
    created_at: datetime()
}]->(s1);

// Query deployment order with dependencies
MATCH path = (s:CTFScenario)-[:DEPENDS_ON*]->(dependency:CTFScenario)
WHERE s.scenario_id = $scenario_id
RETURN nodes(path) AS deployment_sequence;
```

## 8. Security Considerations

### 8.1 Credential Storage

**Current Design**: Stores credentials as JSON string in `CTFResource.credentials`

**Recommendations**:
1. **Encrypt at rest**: Use Neo4j Enterprise encryption or external secrets manager
2. **Never log credentials**: Sanitize logs and error messages
3. **Access control**: Restrict CTF schema access to authorized users
4. **Audit trail**: Log all credential reads

**Alternative (External Secrets)**:
```cypher
// Store reference instead of actual credentials
CREATE (c:CTFResource {
    resource_id: 'vm-abc123',
    role: 'vulnerable-vm',
    credential_reference: 'azure-keyvault://ctf-vault/vm-abc123-creds',  // Pointer to Azure Key Vault
    // ... other properties ...
});
```

### 8.2 Query Authorization

```cypher
// Example: Filter scenarios by user permissions
MATCH (u:User {user_id: $user_id})-[:HAS_PERMISSION]->(s:CTFScenario)
RETURN s;

// Or use Neo4j RBAC (Enterprise)
```

## 9. Performance Characteristics

### 9.1 Query Complexity Analysis

| Query | Complexity | Indexed | Expected Time (10K resources) |
|-------|-----------|---------|-------------------------------|
| List scenarios | O(n) scenarios | ✓ (created_at) | < 10ms |
| Get scenario resources | O(m) resources per scenario | ✓ (scenario_id) | < 50ms |
| Find resource's scenarios | O(1) per resource | ✓ (resource_id) | < 5ms |
| Filter by deployment status | O(n) matching scenarios | ✓ (deployment_status) | < 10ms |
| Cleanup scenario | O(m) resources | ✓ (scenario_id) | < 100ms |

### 9.2 Storage Estimates

| Component | Size per Item | 1K Scenarios | 10K Scenarios |
|-----------|---------------|--------------|---------------|
| CTFScenario node | ~1KB (with Terraform) | 1MB | 10MB |
| CTFResource node | ~500B | 5MB (10 resources/scenario) | 50MB |
| Relationships | ~100B | 2MB | 20MB |
| Indexes | ~200B/entry | 2MB | 20MB |
| **Total** | | **~10MB** | **~100MB** |

**Conclusion**: Schema scales efficiently to 10K+ scenarios.

## 10. Testing & Validation

### 10.1 Schema Validation Queries

```cypher
// Test 1: Verify constraints exist
SHOW CONSTRAINTS
YIELD name, type
WHERE name STARTS WITH 'ctf_';

// Test 2: Verify indexes exist
SHOW INDEXES
YIELD name, type
WHERE name STARTS WITH 'ctf_';

// Test 3: Check for orphaned CTF resources (no scenario)
MATCH (c:CTFResource)
WHERE NOT (c)<-[:CONTAINS_RESOURCE]-(:CTFScenario)
RETURN count(c) AS orphaned_resources;
// Expected: 0

// Test 4: Check for invalid annotations (pointing to Original nodes)
MATCH (c:CTFResource)-[:ANNOTATES]->(r:Resource:Original)
RETURN count(c) AS invalid_annotations;
// Expected: 0
```

### 10.2 Integration Tests

```python
# test_ctf_schema.py
def test_create_scenario_with_resources(neo4j_driver):
    """Test complete scenario lifecycle"""
    with neo4j_driver.session() as session:
        # Create scenario
        result = session.run("""
            CREATE (s:CTFScenario {
                scenario_id: 'test-scenario-001',
                name: 'Test Scenario',
                deployment_status: 'pending',
                created_at: datetime()
            })
            RETURN s.scenario_id AS scenario_id
        """)
        assert result.single()['scenario_id'] == 'test-scenario-001'

        # Verify scenario exists
        result = session.run("""
            MATCH (s:CTFScenario {scenario_id: 'test-scenario-001'})
            RETURN count(s) AS count
        """)
        assert result.single()['count'] == 1

        # Cleanup
        session.run("""
            MATCH (s:CTFScenario {scenario_id: 'test-scenario-001'})
            DETACH DELETE s
        """)
```

## 11. Summary

### Key Design Decisions

1. **Separate Nodes**: CTFScenario + CTFResource nodes keep CTF data isolated
2. **Terraform Storage**: Stored directly on CTFScenario node (simple, < 10KB)
3. **Annotation Pattern**: CTFResource → Resource via `:ANNOTATES` relationship
4. **Non-Invasive**: Zero modifications to existing :Resource schema
5. **Fast Cleanup**: `DETACH DELETE` removes all CTF data, preserves infrastructure

### Schema Benefits

- ✅ **Query Performance**: Indexed lookups for fast filtering
- ✅ **Data Integrity**: Unique constraints prevent duplicates
- ✅ **Clean Separation**: CTF data isolated from infrastructure
- ✅ **Easy Cleanup**: Single query removes entire scenario
- ✅ **Multiple Scenarios**: Concurrent scenarios without conflicts
- ✅ **Backward Compatible**: Existing queries unaffected

### Next Steps

1. **Run migration script** (`migration_001_ctf_overlay.cypher`)
2. **Implement Python/Terraform integration** (read Terraform, write to Neo4j)
3. **Add deployment orchestration** (status tracking, error handling)
4. **Build query API** (REST endpoints for scenario management)
5. **Add monitoring** (deployment metrics, query performance)

---

**Schema Version**: 1.0
**Created**: 2025-12-02
**Status**: Design Complete - Ready for Implementation

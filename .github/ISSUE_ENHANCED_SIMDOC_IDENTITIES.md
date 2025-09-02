# Enhanced Identity and Permissions Generation for gen-simdoc

## Executive Summary

The current `gen-simdoc` command generates useful company profiles for simulating Azure customer environments, but lacks sufficient detail about identities, roles, groups, and permissions. This limitation prevents the creation of realistic tenant graphs that accurately represent enterprise RBAC configurations, group memberships, and permission hierarchies. This issue proposes enhancements to generate comprehensive identity and access management (IAM) details in simulated customer profiles.

## Current State Analysis

### What gen-simdoc Currently Generates
The existing implementation (`src/cli_commands.py:796-876`) produces profiles with:
- Basic company overview (name, industry, size, revenue)
- High-level personas table with titles and responsibilities
- Infrastructure descriptions (workloads, architectures)
- Networking topology
- DevOps practices

### Example Current Output (from simdoc-test.md)
```markdown
| Persona | Title/Role | Responsibility | Azure Privileges |
|---------|------------|----------------|------------------|
| Maria Adams | Chief Digital Officer | Owns overall Azure adoption roadmap | Owner at Mgmt-Group root |
| Devin Yu | Director, Cloud Platform | Landing zone architecture, FinOps | User Access Admin |
| Priya Kapoor | Lead OT Engineer | SCADA and IoT Hub integrations | Contributor in OT sub |
```

### What's Missing
1. **Detailed RBAC Assignments**: Specific role definitions, custom roles, role inheritance
2. **Group Structures**: Security groups, Microsoft 365 groups, distribution lists, nested groups
3. **Conditional Access Policies**: MFA requirements, device compliance, location-based access
4. **Service Principal Details**: App registrations, API permissions, certificate/secret management
5. **Managed Identities**: System vs user-assigned, permission scopes
6. **Administrative Units**: Scoped administration boundaries
7. **PIM Configurations**: Eligible vs active assignments, approval workflows, time-bound access
8. **Cross-tenant Relationships**: B2B guest users, partner organizations
9. **Identity Governance**: Access reviews, entitlement management, lifecycle workflows
10. **Permission Inheritance**: Management group → subscription → resource group → resource

## Problem Statement

When using `atg create-tenant` with current gen-simdoc output:
- The resulting tenant graph lacks realistic identity complexity
- RBAC assignments are oversimplified
- Group memberships and nested relationships are missing
- Service principals and managed identities are underrepresented
- The generated IaC doesn't reflect real-world permission patterns

This prevents effective:
- Security testing and threat modeling
- Compliance validation scenarios
- Identity attack path analysis
- Permission escalation detection
- Cross-tenant collaboration simulation

## Proposed Enhancement

### 1. Enhanced Prompt Engineering

Update the LLM prompt in `generate_sim_doc_command_handler` to explicitly request:

```python
ENHANCED_PROMPT = """
...existing prompt...

IDENTITY AND ACCESS REQUIREMENTS:
Please include comprehensive identity and access management details:

1. USER IDENTITIES (15-50 users based on company size):
   - User Principal Names (UPN) with consistent domain
   - Department and job title
   - Manager relationships (reporting structure)
   - Account types (Member vs Guest)
   - License assignments (E3, E5, P1, P2)
   - MFA enrollment status
   - Risk levels for Conditional Access

2. GROUP STRUCTURES:
   - Security Groups with clear naming conventions
   - Microsoft 365 Groups for collaboration
   - Distribution Lists for communication
   - Dynamic Groups with membership rules
   - Nested group memberships
   - Group owners and membership approval

3. RBAC ASSIGNMENTS (detailed):
   For each role assignment specify:
   - Principal (user/group/service principal)
   - Role Definition (built-in or custom)
   - Scope (management group/subscription/resource group/resource)
   - Assignment type (Direct vs Inherited)
   - PIM eligibility and activation requirements

4. SERVICE PRINCIPALS:
   - Display names following naming standards
   - Application IDs
   - API permissions (Microsoft Graph, Azure Service Management)
   - Authentication methods (certificate vs secret)
   - Owner assignments
   - Consent grants (admin vs user)

5. MANAGED IDENTITIES:
   - System-assigned for specific resources
   - User-assigned with shared permissions
   - Role assignments and scopes
   - Resource associations

6. CONDITIONAL ACCESS POLICIES:
   - Policy names and descriptions
   - User/group inclusions and exclusions
   - Application targets
   - Conditions (locations, devices, risk levels)
   - Grant controls (MFA, compliant device, hybrid join)
   - Session controls

7. ADMINISTRATIVE UNITS:
   - Unit names and descriptions
   - Member users and groups
   - Scoped administrators
   - Role assignments within units

8. PRIVILEGED IDENTITY MANAGEMENT:
   - Eligible role assignments
   - Activation requirements (MFA, justification, approval)
   - Maximum activation duration
   - Approval workflows and approvers
   - Access reviews schedules

9. CUSTOM ROLE DEFINITIONS:
   - Role name and description
   - Included permissions (Actions, NotActions, DataActions)
   - Assignable scopes
   - Business justification

10. CROSS-TENANT ACCESS:
    - B2B guest users from partner organizations
    - External collaboration settings
    - Cross-tenant synchronization
    - Entitlement management catalogs

Format this information in structured tables and sections that can be easily parsed for graph creation.
"""
```

### 2. Enhanced Output Structure

#### 2.1 Detailed Identity Tables

```markdown
## Identity and Access Management

### Users
| UPN | Display Name | Department | Job Title | Manager | Type | Licenses | MFA | Risk |
|-----|--------------|------------|-----------|---------|------|----------|-----|------|
| maria.adams@contoso.com | Maria Adams | Executive | CDO | CEO | Member | E5, P2 | Enabled | Low |
| devin.yu@contoso.com | Devin Yu | IT | Director, Cloud | Maria Adams | Member | E5, P2 | Enabled | Low |
| ext.john.smith@partner.com | John Smith | External | Consultant | - | Guest | - | Required | Medium |

### Groups
| Group Name | Type | Members | Owners | Nested Groups | Dynamic Rule |
|------------|------|---------|--------|---------------|--------------|
| SG-Azure-Admins | Security | 12 users | Maria Adams | SG-Global-Admins | - |
| M365-CloudTeam | Microsoft 365 | 45 users, 3 groups | Devin Yu | - | - |
| DG-All-Employees | Dynamic | 6400 users | HR Admin | - | (user.department -ne "External") |

### Service Principals
| Display Name | App ID | API Permissions | Auth Method | Owner |
|--------------|--------|-----------------|-------------|-------|
| Contoso-AKS-Manager | abc-123 | Azure Service Management (user_impersonation) | Certificate | Devin Yu |
| Contoso-DevOps-Pipeline | def-456 | Microsoft Graph (User.Read.All, Group.Read.All) | Secret | April Smith |
```

#### 2.2 RBAC Assignment Matrix

```markdown
### RBAC Assignments

| Principal | Principal Type | Role | Scope | Assignment Type | PIM Status | Activation |
|-----------|---------------|------|-------|-----------------|------------|------------|
| SG-Azure-Admins | Group | Owner | /providers/Microsoft.Management/managementGroups/contoso | Direct | Eligible | MFA + Approval |
| devin.yu@contoso.com | User | User Access Administrator | /subscriptions/sub-platform | Direct | Active | - |
| Contoso-AKS-Manager | Service Principal | Contributor | /subscriptions/sub-prod/resourceGroups/rg-aks | Direct | Active | - |
| DG-Developers | Dynamic Group | Reader | /subscriptions/sub-dev | Inherited | Active | - |
```

#### 2.3 Conditional Access Policies

```markdown
### Conditional Access Policies

| Policy Name | Target Users/Groups | Target Apps | Conditions | Grant Controls | Session Controls |
|-------------|-------------------|-------------|------------|----------------|------------------|
| Require-MFA-Admins | SG-Azure-Admins | All apps | Any location | Require MFA | - |
| Block-Legacy-Auth | All users | Exchange, SharePoint | Legacy auth clients | Block | - |
| Require-Compliant-Device | All users except guests | Office 365 | Untrusted locations | Compliant device OR Hybrid join | App enforced restrictions |
```

### 3. TenantCreator Enhancement

Update `TenantCreator` to parse and process the enhanced identity information:

```python
class EnhancedTenantCreator(TenantCreator):
    def parse_identity_tables(self, markdown: str) -> Dict:
        """Parse detailed identity tables from enhanced markdown."""
        # Parse Users table
        users = self.extract_table_data(markdown, "### Users")

        # Parse Groups table with membership
        groups = self.extract_table_data(markdown, "### Groups")

        # Parse Service Principals
        service_principals = self.extract_table_data(markdown, "### Service Principals")

        # Parse RBAC Assignments
        rbac_assignments = self.extract_table_data(markdown, "### RBAC Assignments")

        return {
            "users": self.process_users(users),
            "groups": self.process_groups(groups),
            "servicePrincipals": self.process_service_principals(service_principals),
            "rbacAssignments": self.process_rbac_assignments(rbac_assignments)
        }

    def create_identity_nodes(self, spec: TenantSpec):
        """Create detailed identity nodes in Neo4j."""
        # Create User nodes with properties
        for user in spec.tenant.users:
            self.create_user_node(user, include_properties=[
                'department', 'jobTitle', 'manager',
                'accountType', 'licenses', 'mfaStatus'
            ])

        # Create Group nodes with membership relationships
        for group in spec.tenant.groups:
            self.create_group_node(group)
            self.create_membership_relationships(group)

        # Create RBAC assignment relationships with metadata
        for assignment in spec.tenant.rbac_assignments:
            self.create_rbac_relationship(
                principal=assignment.principal_id,
                role=assignment.role,
                scope=assignment.scope,
                properties={
                    'assignmentType': assignment.assignment_type,
                    'pimStatus': assignment.pim_status,
                    'activationRequirements': assignment.activation
                }
            )
```

### 4. Extended TenantSpec Models

Add new fields to support enhanced identity information:

```python
# src/tenant_spec_models.py

class EnhancedUser(User):
    """Extended user model with additional IAM properties."""
    department: Optional[str] = Field(None, description="User's department")
    job_title: Optional[str] = Field(None, description="Job title", alias="jobTitle")
    manager_id: Optional[str] = Field(None, description="Manager's user ID", alias="managerId")
    account_type: Optional[str] = Field(None, description="Member or Guest", alias="accountType")
    licenses: Optional[List[str]] = Field(None, description="Assigned licenses")
    mfa_status: Optional[str] = Field(None, description="MFA enrollment status", alias="mfaStatus")
    risk_level: Optional[str] = Field(None, description="Risk level for CA", alias="riskLevel")

class EnhancedGroup(Group):
    """Extended group model with additional properties."""
    group_type: Optional[str] = Field(None, description="Security, M365, Dynamic", alias="groupType")
    owners: Optional[List[str]] = Field(None, description="Group owner IDs")
    nested_groups: Optional[List[str]] = Field(None, description="Nested group IDs", alias="nestedGroups")
    dynamic_rule: Optional[str] = Field(None, description="Dynamic membership rule", alias="dynamicRule")

class EnhancedServicePrincipal(ServicePrincipal):
    """Extended service principal with API permissions."""
    api_permissions: Optional[List[Dict]] = Field(None, description="API permissions", alias="apiPermissions")
    auth_method: Optional[str] = Field(None, description="Certificate or Secret", alias="authMethod")
    owner_id: Optional[str] = Field(None, description="Owner user/group ID", alias="ownerId")

class EnhancedRBACAssignment(RBACAssignment):
    """Extended RBAC assignment with PIM details."""
    assignment_type: Optional[str] = Field(None, description="Direct or Inherited", alias="assignmentType")
    pim_status: Optional[str] = Field(None, description="Active or Eligible", alias="pimStatus")
    activation_requirements: Optional[Dict] = Field(None, description="PIM activation requirements", alias="activationRequirements")

class ConditionalAccessPolicy(BaseModel):
    """Conditional Access Policy configuration."""
    policy_id: str = Field(..., description="Policy ID", alias="policyId")
    policy_name: str = Field(..., description="Policy name", alias="policyName")
    target_users: List[str] = Field(..., description="Target user/group IDs", alias="targetUsers")
    target_apps: List[str] = Field(..., description="Target applications", alias="targetApps")
    conditions: Dict = Field(..., description="Policy conditions")
    grant_controls: Dict = Field(..., description="Grant controls", alias="grantControls")
    session_controls: Optional[Dict] = Field(None, description="Session controls", alias="sessionControls")
```

### 5. Graph Relationship Enhancements

Create richer relationship types in Neo4j:

```cypher
// Manager relationships
MATCH (employee:User {id: $employeeId})
MATCH (manager:User {id: $managerId})
CREATE (employee)-[:REPORTS_TO {since: datetime()}]->(manager)

// Nested group memberships
MATCH (child:Group {id: $childGroupId})
MATCH (parent:Group {id: $parentGroupId})
CREATE (child)-[:NESTED_IN]->(parent)

// PIM eligible assignments
MATCH (principal {id: $principalId})
MATCH (role:Role {name: $roleName})
CREATE (principal)-[:ELIGIBLE_FOR {
  activationRequired: true,
  mfaRequired: $mfaRequired,
  approvalRequired: $approvalRequired,
  maxDuration: $maxDuration
}]->(role)

// Service principal API permissions
MATCH (sp:ServicePrincipal {id: $spId})
CREATE (sp)-[:HAS_PERMISSION {
  api: $apiName,
  permission: $permissionName,
  type: $permissionType,
  consentedBy: $consentedBy
}]->(:APIPermission {name: $permissionName})

// Conditional Access Policy applications
MATCH (policy:ConditionalAccessPolicy {id: $policyId})
MATCH (user:User {id: $userId})
WHERE $userId IN $targetUsers
CREATE (policy)-[:APPLIES_TO {
  conditions: $conditions,
  controls: $controls
}]->(user)
```

## Implementation Plan

### Phase 1: Prompt Enhancement (Week 1)
- [x] Analyze current prompt structure
- [ ] Design enhanced prompt with identity focus
- [ ] Test prompt with Azure OpenAI to validate output
- [ ] Iterate on prompt based on output quality

### Phase 2: Model Extensions (Week 2)
- [ ] Extend TenantSpec models with identity fields
- [ ] Add validation for new fields
- [ ] Update model serialization/deserialization
- [ ] Create migration for existing specs

### Phase 3: Parser Implementation (Week 3)
- [ ] Implement markdown table parsers for identity data
- [ ] Add support for nested structures (groups in groups)
- [ ] Handle cross-references (manager relationships)
- [ ] Validate parsed data against schema

### Phase 4: Graph Creation (Week 4)
- [ ] Update TenantCreator for enhanced identities
- [ ] Implement new relationship types in Neo4j
- [ ] Add identity-specific node properties
- [ ] Create indexes for identity queries

### Phase 5: Testing & Documentation (Week 5)
- [ ] Create comprehensive test cases
- [ ] Generate sample enhanced profiles
- [ ] Update documentation with examples
- [ ] Performance testing with large identity sets

## Success Metrics

### Quantitative Metrics
- **Identity Coverage**: Generate 95% of specified identity types
- **Relationship Accuracy**: 100% valid relationships in graph
- **Parse Success Rate**: Successfully parse 99% of generated profiles
- **Performance**: Process 10,000 identities in < 30 seconds

### Qualitative Metrics
- **Realism**: Profiles indistinguishable from real enterprise configs
- **Completeness**: All major IAM scenarios representable
- **Usability**: Clear, understandable output format
- **Flexibility**: Support various organization sizes and types

## Example Enhanced Output

```markdown
# Contoso Wind & Solar - Enhanced Identity Profile

## Company Overview
[... existing company information ...]

## Identity and Access Management

### Organizational Structure
Total Identities: 6,423
- Users: 6,400 (6,350 members, 50 guests)
- Groups: 487 (245 security, 142 M365, 100 dynamic)
- Service Principals: 89
- Managed Identities: 34

### User Accounts
| UPN | Display Name | Department | Title | Manager | Type | Licenses | MFA |
|-----|--------------|------------|-------|---------|------|----------|-----|
| maria.adams@contoso.com | Maria Adams | Executive | Chief Digital Officer | robert.ceo@contoso.com | Member | E5, P2 | Enforced |
| devin.yu@contoso.com | Devin Yu | IT | Director, Cloud Platform | maria.adams@contoso.com | Member | E5, P2 | Enforced |
| priya.kapoor@contoso.com | Priya Kapoor | OT | Lead OT Engineer | james.cto@contoso.com | Member | E3, P1 | Enabled |
| hector.garcia@contoso.com | Hector García | Security | Security Operations Manager | lisa.ciso@contoso.com | Member | E5, P2 | Enforced |
| ext.john.consultant@partner.com | John Smith | External | Azure Consultant | - | Guest | - | Required |

### Security Groups
| Group Name | Type | Members | Owners | Description | Nested Groups |
|------------|------|---------|--------|-------------|---------------|
| SG-Azure-GlobalAdmins | Security | 4 users | CEO | Global Azure administrators | - |
| SG-Azure-PlatformTeam | Security | 12 users, 2 groups | Devin Yu | Platform engineering team | SG-Azure-Contributors |
| SG-OT-Engineers | Security | 30 users | Priya Kapoor | OT/SCADA specialists | SG-SCADA-ReadOnly |
| SG-SOC-Analysts | Security | 10 users | Hector García | Security operations center | - |
| SG-Developers-Prod | Security | 40 users | April Smith | Production access developers | - |

### RBAC Assignments
| Principal | Type | Role | Scope | Assignment | PIM | Activation |
|-----------|------|------|-------|------------|-----|------------|
| SG-Azure-GlobalAdmins | Group | Owner | /providers/Microsoft.Management/managementGroups/contoso | Direct | Eligible | MFA + CEO Approval |
| devin.yu@contoso.com | User | User Access Administrator | /subscriptions/platform | Direct | Active | - |
| SG-Azure-PlatformTeam | Group | Contributor | /subscriptions/connectivity | Direct | Active | - |
| SG-OT-Engineers | Group | Contributor | /subscriptions/ot-secure/resourceGroups/* | Direct | Eligible | MFA + Justification |
| SP-AKS-Operator | Service Principal | Azure Kubernetes Service Cluster User | /subscriptions/prod/resourceGroups/rg-aks | Direct | Active | - |
| MI-KeyVault-Reader | Managed Identity | Key Vault Secrets User | /subscriptions/prod/resourceGroups/rg-security/providers/Microsoft.KeyVault/vaults/kv-prod | Direct | Active | - |

### Service Principals
| Display Name | App ID | API Permissions | Auth | Owner | Created | Expires |
|--------------|--------|-----------------|------|-------|---------|---------|
| SP-DevOps-Pipeline | 4f3d8a... | Azure Service Management: user_impersonation | Certificate | April Smith | 2024-01-15 | 2025-01-15 |
| SP-Graph-Reader | 8b2c9f... | Microsoft Graph: User.Read.All, Group.Read.All | Secret | Devin Yu | 2024-03-20 | 2025-03-20 |
| SP-AKS-Operator | c7e5d2... | Azure Service Management: user_impersonation | Certificate | Platform Team | 2024-02-10 | 2026-02-10 |

### Managed Identities
| Name | Type | Associated Resource | Role Assignments |
|------|------|-------------------|------------------|
| MI-VM-Backup | System | vm-backup-01 | Storage Blob Data Contributor on backups storage |
| MI-FunctionApp-Prod | System | func-trading-engine | Key Vault Secrets User, SQL DB Contributor |
| MI-LogicApp-Integration | User | - | Service Bus Data Sender, Event Hub Data Receiver |

### Conditional Access Policies
| Policy | Users/Groups | Apps | Conditions | Grant | Session |
|--------|--------------|------|------------|-------|---------|
| CA01-Require-MFA-Admins | SG-Azure-GlobalAdmins, SG-Azure-PlatformTeam | All cloud apps | Any location | Require MFA | - |
| CA02-Block-Legacy-Auth | All users | Exchange, SharePoint | Legacy authentication | Block access | - |
| CA03-Require-Compliant-OT | SG-OT-Engineers | Azure portal, custom apps | Non-corporate network | Require compliant device | 4-hour session |
| CA04-Restrict-Guest-Access | All guest users | SharePoint, Teams | Any | Require MFA, Terms of use | No persistent browser |

### Privileged Identity Management
| Eligible Role | Principal | Approval Required | MFA Required | Max Duration | Justification |
|---------------|-----------|-------------------|--------------|--------------|---------------|
| Global Administrator | maria.adams@contoso.com | CEO | Yes | 8 hours | Required |
| Security Administrator | hector.garcia@contoso.com | CISO | Yes | 4 hours | Required |
| Application Administrator | devin.yu@contoso.com | CTO | Yes | 8 hours | Required |
| Privileged Role Administrator | SG-Azure-GlobalAdmins | CEO + CISO | Yes | 2 hours | Required |

### Custom Role Definitions
| Role Name | Description | Actions | NotActions | Assignable Scopes |
|-----------|-------------|---------|------------|-------------------|
| Contoso OT Operator | Manage OT resources except deletion | Microsoft.Devices/*, Microsoft.IoTHub/* | */delete | /subscriptions/ot-secure |
| Contoso Cost Reader | Read cost and billing information | Microsoft.CostManagement/*/read | - | / |
| Contoso Network Auditor | Audit network configurations | Microsoft.Network/*/read | - | /subscriptions/connectivity |
```

## Benefits

### 1. Realistic Testing Scenarios
- Test actual enterprise RBAC configurations
- Validate permission inheritance chains
- Identify privilege escalation paths
- Simulate insider threat scenarios

### 2. Compliance Validation
- Verify least privilege principles
- Audit segregation of duties
- Check regulatory compliance (SOX, GDPR, HIPAA)
- Validate PIM configurations

### 3. Enhanced Threat Modeling
- Model identity-based attack paths
- Simulate compromised service principal scenarios
- Test conditional access bypass techniques
- Evaluate blast radius of account compromise

### 4. Training and Documentation
- Create realistic training environments
- Document reference architectures
- Demonstrate best practices
- Provide security benchmarks

## Related Issues

- #200: Multi-Tenant Support (will benefit from enhanced identity generation)
- #201: Azure MCP Integration (can leverage identity details for automated discovery)

## Dependencies

- Azure OpenAI configuration (for LLM generation)
- Updated TenantSpec models
- Enhanced Neo4j schema for identity relationships
- Additional Cypher queries for identity traversal

## Estimated Effort

- **Development**: 5 weeks (1 developer)
- **Testing**: 1 week
- **Documentation**: 1 week
- **Total**: 7 weeks

## Acceptance Criteria

1. [ ] gen-simdoc generates profiles with 15+ users for small companies, 50+ for large
2. [ ] Each profile includes security groups, M365 groups, and dynamic groups
3. [ ] RBAC assignments specify scope, type, and PIM configuration
4. [ ] Service principals include API permissions and authentication methods
5. [ ] Managed identities are properly associated with resources
6. [ ] Conditional access policies are fully specified
7. [ ] create-tenant successfully parses and creates all identity entities
8. [ ] Generated Neo4j graph accurately represents identity relationships
9. [ ] Documentation includes examples of enhanced profiles
10. [ ] Performance tests pass with 10,000+ identities

## Appendix: Sample Cypher Queries

```cypher
// Find all users with privileged roles
MATCH (u:User)-[:HAS_ROLE]->(r:Role)
WHERE r.name IN ['Owner', 'Contributor', 'User Access Administrator']
RETURN u.displayName, collect(r.name) as roles

// Identify potential privilege escalation paths
MATCH path = (u:User)-[:MEMBER_OF*1..3]->(g:Group)-[:HAS_ROLE]->(r:Role)
WHERE r.privilegeLevel = 'High'
RETURN u.displayName, [n in nodes(path) | n.name] as escalationPath

// Find service principals with dangerous permissions
MATCH (sp:ServicePrincipal)-[:HAS_PERMISSION]->(p:APIPermission)
WHERE p.name IN ['User.ReadWrite.All', 'Directory.ReadWrite.All', 'RoleManagement.ReadWrite.Directory']
RETURN sp.displayName, collect(p.name) as dangerousPermissions

// Analyze group nesting depth
MATCH path = (g1:Group)-[:NESTED_IN*]->(g2:Group)
RETURN g1.name, length(path) as nestingDepth, g2.name as rootGroup
ORDER BY nestingDepth DESC

// Find users affected by conditional access policies
MATCH (ca:ConditionalAccessPolicy)-[:APPLIES_TO]->(target)
WHERE ca.grantControls =~ '.*MFA.*'
RETURN ca.policyName, count(target) as affectedEntities
```

---

**Labels**: `enhancement`, `gen-simdoc`, `identity`, `rbac`, `security`

**Priority**: High (blocks realistic tenant generation)

**Assignee**: TBD

**Milestone**: Enhanced Identity Generation v1.0

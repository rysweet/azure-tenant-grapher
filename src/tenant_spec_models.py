# pyright: reportUntypedBaseClass=false
import json
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, ValidationError, model_validator


# Enums for enhanced models
class GroupType(str, Enum):
    """Types of groups in Azure AD."""

    SECURITY = "Security"
    MICROSOFT365 = "Microsoft365"
    DISTRIBUTION = "Distribution"
    MAIL_ENABLED_SECURITY = "MailEnabledSecurity"
    DYNAMIC = "Dynamic"


class AuthenticationMethod(str, Enum):
    """Authentication methods for users."""

    PASSWORD = "Password"  # pragma: allowlist secret
    MFA_SMS = "MfaSms"
    MFA_VOICE = "MfaVoice"
    MFA_APP = "MfaApp"
    FIDO2 = "Fido2"
    WINDOWS_HELLO = "WindowsHello"
    CERTIFICATE = "Certificate"


class RiskLevel(str, Enum):
    """Risk levels for users and sign-ins."""

    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    NONE = "None"
    HIDDEN = "Hidden"


class AccessLevel(str, Enum):
    """Access levels for PIM assignments."""

    ELIGIBLE = "Eligible"
    ACTIVE = "Active"


class PermissionType(str, Enum):
    """Types of permissions for service principals."""

    APPLICATION = "Application"
    DELEGATED = "Delegated"


# Enhanced Identity Models
class User(BaseModel):
    """
    Represents a user identity in the tenant with comprehensive properties.

    Fields:
        id: Unique identifier for the user.
        display_name: Display name of the user.
        email: Email address of the user.
        user_principal_name: User principal name (UPN).
        mail: Primary email address.
        job_title: Job title of the user.
        department: Department the user belongs to.
        manager_id: ID of the user's manager.
        mfa_enabled: Whether MFA is enabled for the user.
        authentication_methods: List of authentication methods configured.
        last_sign_in_datetime: Last sign-in timestamp.
        last_non_interactive_sign_in: Last non-interactive sign-in timestamp.
        risk_level: Current risk level of the user.
        is_guest: Whether the user is a guest user.
        creation_type: How the user was created (invitation, etc.).
        account_enabled: Whether the account is enabled.
        on_premises_sync_enabled: Whether synced from on-premises AD.
    """

    id: str = Field(..., description="Unique identifier for the user.", alias="userId")
    display_name: Optional[str] = Field(
        None, description="Display name of the user.", alias="displayName"
    )
    email: Optional[str] = Field(
        None, description="Email address of the user.", alias="emailAddress"
    )
    user_principal_name: Optional[str] = Field(
        None, description="User principal name (UPN).", alias="userPrincipalName"
    )
    mail: Optional[str] = Field(
        None, description="Primary email address.", alias="mail"
    )
    job_title: Optional[str] = Field(
        None, description="Job title of the user.", alias="jobTitle"
    )
    department: Optional[str] = Field(
        None, description="Department the user belongs to.", alias="department"
    )
    manager_id: Optional[str] = Field(
        None, description="ID of the user's manager.", alias="managerId"
    )
    mfa_enabled: Optional[bool] = Field(
        None, description="Whether MFA is enabled for the user.", alias="mfaEnabled"
    )
    authentication_methods: Optional[List[AuthenticationMethod]] = Field(
        None,
        description="List of authentication methods configured.",
        alias="authenticationMethods",
    )
    last_sign_in_datetime: Optional[datetime] = Field(
        None, description="Last sign-in timestamp.", alias="lastSignInDateTime"
    )
    last_non_interactive_sign_in: Optional[datetime] = Field(
        None,
        description="Last non-interactive sign-in timestamp.",
        alias="lastNonInteractiveSignIn",
    )
    risk_level: Optional[RiskLevel] = Field(
        None, description="Current risk level of the user.", alias="riskLevel"
    )
    is_guest: Optional[bool] = Field(
        None, description="Whether the user is a guest user.", alias="isGuest"
    )
    creation_type: Optional[str] = Field(
        None, description="How the user was created.", alias="creationType"
    )
    account_enabled: Optional[bool] = Field(
        None, description="Whether the account is enabled.", alias="accountEnabled"
    )
    on_premises_sync_enabled: Optional[bool] = Field(
        None,
        description="Whether synced from on-premises AD.",
        alias="onPremisesSyncEnabled",
    )


class Group(BaseModel):
    """
    Represents a group with comprehensive properties and membership details.

    Fields:
        id: Unique identifier for the group.
        display_name: Display name of the group.
        members: List of member IDs (users, groups, or service principals).
        group_type: Type of group (Security, M365, Distribution, etc.).
        mail_enabled: Whether the group is mail-enabled.
        mail: Email address of the group.
        security_enabled: Whether the group is security-enabled.
        dynamic_membership_rule: Rule for dynamic group membership.
        membership_rule_processing_state: State of dynamic membership processing.
        owners: List of owner IDs.
        expiration_datetime: When the group expires.
        renewed_datetime: When the group was last renewed.
        is_assignable_to_role: Whether the group can be assigned to roles.
        visibility: Group visibility (Public, Private, HiddenMembership).
        created_datetime: When the group was created.
        description: Description of the group.
    """

    id: str = Field(
        ..., description="Unique identifier for the group.", alias="groupId"
    )
    display_name: Optional[str] = Field(
        None, description="Display name of the group.", alias="displayName"
    )
    members: Optional[List[str]] = Field(
        None, description="List of member IDs (users, groups, or service principals)."
    )
    group_type: Optional[GroupType] = Field(
        None, description="Type of group.", alias="groupType"
    )
    mail_enabled: Optional[bool] = Field(
        None, description="Whether the group is mail-enabled.", alias="mailEnabled"
    )
    mail: Optional[str] = Field(
        None, description="Email address of the group.", alias="mail"
    )
    security_enabled: Optional[bool] = Field(
        None,
        description="Whether the group is security-enabled.",
        alias="securityEnabled",
    )
    dynamic_membership_rule: Optional[str] = Field(
        None,
        description="Rule for dynamic group membership.",
        alias="dynamicMembershipRule",
    )
    membership_rule_processing_state: Optional[str] = Field(
        None,
        description="State of dynamic membership processing.",
        alias="membershipRuleProcessingState",
    )
    owners: Optional[List[str]] = Field(
        None, description="List of owner IDs.", alias="owners"
    )
    expiration_datetime: Optional[datetime] = Field(
        None, description="When the group expires.", alias="expirationDateTime"
    )
    renewed_datetime: Optional[datetime] = Field(
        None, description="When the group was last renewed.", alias="renewedDateTime"
    )
    is_assignable_to_role: Optional[bool] = Field(
        None,
        description="Whether the group can be assigned to roles.",
        alias="isAssignableToRole",
    )
    visibility: Optional[str] = Field(
        None,
        description="Group visibility (Public, Private, HiddenMembership).",
        alias="visibility",
    )
    created_datetime: Optional[datetime] = Field(
        None, description="When the group was created.", alias="createdDateTime"
    )
    description: Optional[str] = Field(
        None, description="Description of the group.", alias="description"
    )


class APIPermission(BaseModel):
    """Represents an API permission granted to a service principal."""

    resource_app_id: str = Field(
        ..., description="App ID of the resource.", alias="resourceAppId"
    )
    permission_id: str = Field(
        ..., description="ID of the permission.", alias="permissionId"
    )
    permission_name: Optional[str] = Field(
        None, description="Name of the permission.", alias="permissionName"
    )
    permission_type: Optional[PermissionType] = Field(
        None,
        description="Type of permission (Application or Delegated).",
        alias="permissionType",
    )


class ServicePrincipalCredential(BaseModel):
    """Represents a credential (certificate or secret) for a service principal."""

    credential_type: str = Field(
        ...,
        description="Type of credential (Certificate or ClientSecret).",
        alias="credentialType",
    )
    display_name: Optional[str] = Field(
        None, description="Display name of the credential.", alias="displayName"
    )
    end_datetime: Optional[datetime] = Field(
        None, description="Expiration datetime of the credential.", alias="endDateTime"
    )
    start_datetime: Optional[datetime] = Field(
        None, description="Start datetime of the credential.", alias="startDateTime"
    )
    thumbprint: Optional[str] = Field(
        None, description="Thumbprint (for certificates).", alias="thumbprint"
    )


class ServicePrincipal(BaseModel):
    """
    Represents a service principal with comprehensive properties.

    Fields:
        id: Unique identifier for the service principal.
        display_name: Display name of the service principal.
        app_id: Application ID associated with the service principal.
        app_display_name: Display name of the associated application.
        api_permissions: List of API permissions granted.
        app_roles: List of application roles.
        oauth2_permissions: OAuth2 permissions exposed by the app.
        credentials: List of credentials (certificates/secrets).
        sign_in_audience: Sign-in audience for the application.
        app_owner_organization_id: ID of the organization that owns the app.
        homepage: Homepage URL of the application.
        reply_urls: Reply URLs for the application.
        service_principal_type: Type of service principal.
        tags: Tags associated with the service principal.
        account_enabled: Whether the service principal is enabled.
        publisher_name: Name of the application publisher.
    """

    id: str = Field(
        ..., description="Unique identifier for the service principal.", alias="spId"
    )
    display_name: Optional[str] = Field(
        None, description="Display name of the service principal.", alias="displayName"
    )
    app_id: Optional[str] = Field(
        None,
        description="Application ID associated with the service principal.",
        alias="appId",
    )
    app_display_name: Optional[str] = Field(
        None,
        description="Display name of the associated application.",
        alias="appDisplayName",
    )
    api_permissions: Optional[List[APIPermission]] = Field(
        None, description="List of API permissions granted.", alias="apiPermissions"
    )
    app_roles: Optional[List[str]] = Field(
        None, description="List of application roles.", alias="appRoles"
    )
    oauth2_permissions: Optional[List[str]] = Field(
        None,
        description="OAuth2 permissions exposed by the app.",
        alias="oauth2Permissions",
    )
    credentials: Optional[List[ServicePrincipalCredential]] = Field(
        None,
        description="List of credentials (certificates/secrets).",
        alias="credentials",
    )
    sign_in_audience: Optional[str] = Field(
        None,
        description="Sign-in audience for the application.",
        alias="signInAudience",
    )
    app_owner_organization_id: Optional[str] = Field(
        None,
        description="ID of the organization that owns the app.",
        alias="appOwnerOrganizationId",
    )
    homepage: Optional[str] = Field(
        None, description="Homepage URL of the application.", alias="homepage"
    )
    reply_urls: Optional[List[str]] = Field(
        None, description="Reply URLs for the application.", alias="replyUrls"
    )
    service_principal_type: Optional[str] = Field(
        None, description="Type of service principal.", alias="servicePrincipalType"
    )
    tags: Optional[List[str]] = Field(
        None, description="Tags associated with the service principal.", alias="tags"
    )
    account_enabled: Optional[bool] = Field(
        None,
        description="Whether the service principal is enabled.",
        alias="accountEnabled",
    )
    publisher_name: Optional[str] = Field(
        None, description="Name of the application publisher.", alias="publisherName"
    )


class ManagedIdentity(BaseModel):
    """
    Represents a managed identity.

    Fields:
        id: Unique identifier for the managed identity.
        display_name: Display name of the managed identity.
    """

    id: str = Field(
        ..., description="Unique identifier for the managed identity.", alias="miId"
    )
    display_name: Optional[str] = Field(
        None, description="Display name of the managed identity.", alias="displayName"
    )


class AdminUnit(BaseModel):
    """
    Represents an administrative unit.

    Fields:
        id: Unique identifier for the admin unit.
        display_name: Display name of the admin unit.
    """

    id: str = Field(
        ..., description="Unique identifier for the admin unit.", alias="adminUnitId"
    )
    display_name: Optional[str] = Field(
        None, description="Display name of the admin unit.", alias="displayName"
    )


# New Identity and Permission Models
class ConditionalAccessCondition(BaseModel):
    """Represents conditions for a conditional access policy."""

    users_include: Optional[List[str]] = Field(
        None, description="User IDs to include.", alias="usersInclude"
    )
    users_exclude: Optional[List[str]] = Field(
        None, description="User IDs to exclude.", alias="usersExclude"
    )
    groups_include: Optional[List[str]] = Field(
        None, description="Group IDs to include.", alias="groupsInclude"
    )
    groups_exclude: Optional[List[str]] = Field(
        None, description="Group IDs to exclude.", alias="groupsExclude"
    )
    applications_include: Optional[List[str]] = Field(
        None, description="Application IDs to include.", alias="applicationsInclude"
    )
    applications_exclude: Optional[List[str]] = Field(
        None, description="Application IDs to exclude.", alias="applicationsExclude"
    )
    platforms_include: Optional[List[str]] = Field(
        None, description="Platforms to include.", alias="platformsInclude"
    )
    platforms_exclude: Optional[List[str]] = Field(
        None, description="Platforms to exclude.", alias="platformsExclude"
    )
    locations_include: Optional[List[str]] = Field(
        None, description="Locations to include.", alias="locationsInclude"
    )
    locations_exclude: Optional[List[str]] = Field(
        None, description="Locations to exclude.", alias="locationsExclude"
    )
    client_app_types: Optional[List[str]] = Field(
        None, description="Client app types.", alias="clientAppTypes"
    )
    sign_in_risk_levels: Optional[List[RiskLevel]] = Field(
        None, description="Sign-in risk levels.", alias="signInRiskLevels"
    )
    user_risk_levels: Optional[List[RiskLevel]] = Field(
        None, description="User risk levels.", alias="userRiskLevels"
    )


class ConditionalAccessControl(BaseModel):
    """Represents controls for a conditional access policy."""

    grant_controls: Optional[List[str]] = Field(
        None,
        description="Grant controls (e.g., MFA, compliant device).",
        alias="grantControls",
    )
    session_controls: Optional[List[str]] = Field(
        None,
        description="Session controls (e.g., app enforced restrictions).",
        alias="sessionControls",
    )
    operator: Optional[str] = Field(
        None, description="Operator for grant controls (AND/OR).", alias="operator"
    )


class ConditionalAccessPolicy(BaseModel):
    """
    Represents a conditional access policy.

    Fields:
        id: Unique identifier for the policy.
        display_name: Display name of the policy.
        state: State of the policy (enabled, disabled, enabledForReportingButNotEnforced).
        conditions: Conditions that must be met.
        grant_controls: Controls to grant access.
        session_controls: Session controls.
        created_datetime: When the policy was created.
        modified_datetime: When the policy was last modified.
    """

    id: str = Field(
        ..., description="Unique identifier for the policy.", alias="policyId"
    )
    display_name: Optional[str] = Field(
        None, description="Display name of the policy.", alias="displayName"
    )
    state: Optional[str] = Field(
        None, description="State of the policy.", alias="state"
    )
    conditions: Optional[ConditionalAccessCondition] = Field(
        None, description="Conditions that must be met.", alias="conditions"
    )
    controls: Optional[ConditionalAccessControl] = Field(
        None, description="Access controls.", alias="controls"
    )
    created_datetime: Optional[datetime] = Field(
        None, description="When the policy was created.", alias="createdDateTime"
    )
    modified_datetime: Optional[datetime] = Field(
        None, description="When the policy was last modified.", alias="modifiedDateTime"
    )


class PIMAssignment(BaseModel):
    """
    Represents a Privileged Identity Management (PIM) assignment.

    Fields:
        id: Unique identifier for the assignment.
        principal_id: ID of the principal receiving the assignment.
        principal_type: Type of principal (User, Group, ServicePrincipal).
        role_definition_id: ID of the role definition.
        role_display_name: Display name of the role.
        scope: Scope of the assignment.
        access_level: Access level (Eligible or Active).
        start_datetime: Start datetime of the assignment.
        end_datetime: End datetime of the assignment.
        assignment_state: State of the assignment.
        justification: Justification for the assignment.
        ticket_info: Ticket information if required.
    """

    id: str = Field(
        ..., description="Unique identifier for the assignment.", alias="assignmentId"
    )
    principal_id: str = Field(
        ...,
        description="ID of the principal receiving the assignment.",
        alias="principalId",
    )
    principal_type: Optional[str] = Field(
        None, description="Type of principal.", alias="principalType"
    )
    role_definition_id: str = Field(
        ..., description="ID of the role definition.", alias="roleDefinitionId"
    )
    role_display_name: Optional[str] = Field(
        None, description="Display name of the role.", alias="roleDisplayName"
    )
    scope: str = Field(..., description="Scope of the assignment.", alias="scope")
    access_level: Optional[AccessLevel] = Field(
        None, description="Access level (Eligible or Active).", alias="accessLevel"
    )
    start_datetime: Optional[datetime] = Field(
        None, description="Start datetime of the assignment.", alias="startDateTime"
    )
    end_datetime: Optional[datetime] = Field(
        None, description="End datetime of the assignment.", alias="endDateTime"
    )
    assignment_state: Optional[str] = Field(
        None, description="State of the assignment.", alias="assignmentState"
    )
    justification: Optional[str] = Field(
        None, description="Justification for the assignment.", alias="justification"
    )
    ticket_info: Optional[str] = Field(
        None, description="Ticket information if required.", alias="ticketInfo"
    )


class AdminRole(BaseModel):
    """
    Represents an administrative role in Azure AD.

    Fields:
        id: Unique identifier for the role.
        display_name: Display name of the role.
        description: Description of the role.
        is_built_in: Whether this is a built-in role.
        is_enabled: Whether the role is enabled.
        template_id: Template ID for built-in roles.
        members: List of member IDs assigned to this role.
        permissions: List of permissions granted by this role.
    """

    id: str = Field(..., description="Unique identifier for the role.", alias="roleId")
    display_name: Optional[str] = Field(
        None, description="Display name of the role.", alias="displayName"
    )
    description: Optional[str] = Field(
        None, description="Description of the role.", alias="description"
    )
    is_built_in: Optional[bool] = Field(
        None, description="Whether this is a built-in role.", alias="isBuiltIn"
    )
    is_enabled: Optional[bool] = Field(
        None, description="Whether the role is enabled.", alias="isEnabled"
    )
    template_id: Optional[str] = Field(
        None, description="Template ID for built-in roles.", alias="templateId"
    )
    members: Optional[List[str]] = Field(
        None, description="List of member IDs assigned to this role.", alias="members"
    )
    permissions: Optional[List[str]] = Field(
        None,
        description="List of permissions granted by this role.",
        alias="permissions",
    )


class DirectoryRoleAssignment(BaseModel):
    """
    Represents a directory role assignment.

    Fields:
        id: Unique identifier for the assignment.
        principal_id: ID of the principal.
        principal_type: Type of principal.
        role_id: ID of the directory role.
        role_display_name: Display name of the role.
        directory_scope: Directory scope of the assignment.
        app_scope_id: Application scope ID if applicable.
        created_datetime: When the assignment was created.
    """

    id: str = Field(
        ..., description="Unique identifier for the assignment.", alias="assignmentId"
    )
    principal_id: str = Field(
        ..., description="ID of the principal.", alias="principalId"
    )
    principal_type: Optional[str] = Field(
        None, description="Type of principal.", alias="principalType"
    )
    role_id: str = Field(..., description="ID of the directory role.", alias="roleId")
    role_display_name: Optional[str] = Field(
        None, description="Display name of the role.", alias="roleDisplayName"
    )
    directory_scope: Optional[str] = Field(
        None, description="Directory scope of the assignment.", alias="directoryScope"
    )
    app_scope_id: Optional[str] = Field(
        None, description="Application scope ID if applicable.", alias="appScopeId"
    )
    created_datetime: Optional[datetime] = Field(
        None, description="When the assignment was created.", alias="createdDateTime"
    )


# RBAC Assignment
class RBACAssignment(BaseModel):
    """
    Represents a Role-Based Access Control (RBAC) assignment.

    Fields:
        principal_id: ID of the principal (user, group, or service principal).
        role: Role assigned to the principal.
        scope: Scope of the assignment (resource, resource group, or subscription).
    """

    principal_id: str = Field(
        ...,
        description="ID of the principal (user, group, or service principal).",
        alias="principalId",
    )
    role: str = Field(
        ..., description="Role assigned to the principal.", alias="roleName"
    )
    scope: str = Field(
        ...,
        description="Scope of the assignment (resource, resource group, or subscription).",
    )


# Relationship
class Relationship(BaseModel):
    """
    Represents a relationship between two entities with enhanced properties.

    Fields:
        source_id: ID of the source entity.
        target_id: ID of the target entity.
        type: Type of the relationship.
        original_type: Original type from LLM (for GENERIC_RELATIONSHIP).
        narrative_context: Text snippet from source narrative.
        is_hierarchical: Whether this is a hierarchical relationship (e.g., manager).
        is_nested: Whether this is a nested relationship (e.g., nested groups).
        is_cross_tenant: Whether this crosses tenant boundaries (e.g., guest).
        is_temporary: Whether this is a temporary relationship.
        start_datetime: Start datetime for temporary relationships.
        end_datetime: End datetime for temporary relationships.
        attributes: Additional relationship attributes.
    """

    source_id: str = Field(
        ..., description="ID of the source entity.", alias="sourceId"
    )
    target_id: str = Field(
        ..., description="ID of the target entity.", alias="targetId"
    )
    type: str = Field(
        ..., description="Type of the relationship.", alias="relationshipType"
    )
    original_type: Optional[str] = Field(
        None,
        description="Original relationship type from LLM (for GENERIC_RELATIONSHIP)",
        alias="originalType",
    )
    narrative_context: Optional[str] = Field(
        None,
        description="Text snippet from source narrative describing this relationship",
        alias="narrativeContext",
    )
    is_hierarchical: Optional[bool] = Field(
        None,
        description="Whether this is a hierarchical relationship.",
        alias="isHierarchical",
    )
    is_nested: Optional[bool] = Field(
        None, description="Whether this is a nested relationship.", alias="isNested"
    )
    is_cross_tenant: Optional[bool] = Field(
        None,
        description="Whether this crosses tenant boundaries.",
        alias="isCrossTenant",
    )
    is_temporary: Optional[bool] = Field(
        None,
        description="Whether this is a temporary relationship.",
        alias="isTemporary",
    )
    start_datetime: Optional[datetime] = Field(
        None,
        description="Start datetime for temporary relationships.",
        alias="startDateTime",
    )
    end_datetime: Optional[datetime] = Field(
        None,
        description="End datetime for temporary relationships.",
        alias="endDateTime",
    )
    attributes: Optional[Dict[str, Any]] = Field(
        None, description="Additional relationship attributes.", alias="attributes"
    )

    @model_validator(mode="before")
    def normalize_relationship_fields(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize field names from various LLM outputs."""
        # Make a copy to avoid modifying the original
        normalized = dict(values)

        # Handle source_id variations
        if "source_resource_id" in normalized:
            normalized["sourceId"] = normalized.pop("source_resource_id")
        elif "source_id" not in normalized and "sourceId" not in normalized:
            # If neither is present, try other variations
            for key in ["source", "from"]:
                if key in normalized:
                    normalized["sourceId"] = normalized.pop(key)
                    break

        # Handle target_id variations
        if "target_resource_id" in normalized:
            normalized["targetId"] = normalized.pop("target_resource_id")
        elif "targets" in normalized:
            # Convert array to single target (take first element)
            targets = normalized.pop("targets")
            if isinstance(targets, list) and targets:
                normalized["targetId"] = targets[0]
        elif "target_id" not in normalized and "targetId" not in normalized:
            # If neither is present, try other variations
            for key in ["target", "to"]:
                if key in normalized:
                    normalized["targetId"] = normalized.pop(key)
                    break

        # Handle relationship type variations
        if "relationship_type" in normalized:
            normalized["relationshipType"] = normalized.pop("relationship_type")

        return normalized


# Resource
class Resource(BaseModel):
    """
    Represents a generic Azure resource.

    Fields:
        id: Resource ID.
        name: Resource name.
        type: Resource type.
        location: Resource location.
        properties: Additional resource properties.
        narrative_context: Text snippet from source narrative.
    """

    id: str = Field(..., description="Resource ID.", alias="resourceId")
    name: str = Field(..., description="Resource name.", alias="resourceName")
    type: str = Field(..., description="Resource type.", alias="resourceType")
    location: Optional[str] = Field(
        None, description="Resource location.", alias="location"
    )
    properties: Optional[Dict[str, Any]] = Field(
        None, description="Additional resource properties.", alias="properties"
    )
    narrative_context: Optional[str] = Field(
        None,
        description="Text snippet from source narrative describing this resource",
        alias="narrativeContext",
    )


# Resource Group
class ResourceGroup(BaseModel):
    """
    Represents a resource group containing Azure resources.

    Fields:
        id: Resource group ID.
        name: Resource group name.
        location: Resource group location.
        resources: List of resources in the group.
    """

    id: str = Field(..., description="Resource group ID.", alias="resourceGroupId")
    name: str = Field(
        ..., description="Resource group name.", alias="resourceGroupName"
    )
    location: Optional[str] = Field(
        None, description="Resource group location.", alias="location"
    )
    resources: Optional[List[Resource]] = Field(
        None, description="List of resources in the group.", alias="resources"
    )


# Subscription
class Subscription(BaseModel):
    """
    Represents an Azure subscription.

    Fields:
        id: Subscription ID.
        name: Subscription name.
        resource_groups: List of resource groups in the subscription.
    """

    id: str = Field(..., description="Subscription ID.", alias="subscriptionId")
    name: Optional[str] = Field(
        None, description="Subscription name.", alias="subscriptionName"
    )
    resource_groups: Optional[List[ResourceGroup]] = Field(
        None,
        description="List of resource groups in the subscription.",
        alias="resourceGroups",
    )


# Tenant
class Tenant(BaseModel):
    """
    Represents an Azure Active Directory tenant and its associated resources.

    Fields:
        id: Tenant ID.
        display_name: Display name of the tenant.
        subscriptions: List of subscriptions in the tenant.
        users: List of users in the tenant.
        groups: List of groups in the tenant.
        service_principals: List of service principals in the tenant.
        managed_identities: List of managed identities in the tenant.
        admin_units: List of admin units in the tenant.
        conditional_access_policies: List of conditional access policies.
        pim_assignments: List of PIM assignments.
        admin_roles: List of admin roles.
        directory_role_assignments: List of directory role assignments.
        rbac_assignments: List of RBAC assignments in the tenant.
        relationships: List of relationships in the tenant.
        narrative_context: Text snippet from source narrative.
        tenant_settings: Additional tenant-wide settings.
    """

    id: str = Field(..., description="Tenant ID.", alias="tenantId")
    display_name: Optional[str] = Field(
        None, description="Display name of the tenant.", alias="displayName"
    )
    narrative_context: Optional[str] = Field(
        None,
        description="Text snippet from source narrative describing this tenant",
        alias="narrativeContext",
    )
    subscriptions: Optional[List[Subscription]] = Field(
        None, description="List of subscriptions in the tenant.", alias="subscriptions"
    )
    users: Optional[List[User]] = Field(
        None, description="List of users in the tenant.", alias="users"
    )
    groups: Optional[List[Group]] = Field(
        None, description="List of groups in the tenant.", alias="groups"
    )
    service_principals: Optional[List[ServicePrincipal]] = Field(
        None,
        description="List of service principals in the tenant.",
        alias="servicePrincipals",
    )
    managed_identities: Optional[List[ManagedIdentity]] = Field(
        None,
        description="List of managed identities in the tenant.",
        alias="managedIdentities",
    )
    admin_units: Optional[List[AdminUnit]] = Field(
        None, description="List of admin units in the tenant.", alias="adminUnits"
    )
    conditional_access_policies: Optional[List[ConditionalAccessPolicy]] = Field(
        None,
        description="List of conditional access policies.",
        alias="conditionalAccessPolicies",
    )
    pim_assignments: Optional[List[PIMAssignment]] = Field(
        None,
        description="List of PIM assignments.",
        alias="pimAssignments",
    )
    admin_roles: Optional[List[AdminRole]] = Field(
        None,
        description="List of admin roles.",
        alias="adminRoles",
    )
    directory_role_assignments: Optional[List[DirectoryRoleAssignment]] = Field(
        None,
        description="List of directory role assignments.",
        alias="directoryRoleAssignments",
    )
    rbac_assignments: Optional[List[RBACAssignment]] = Field(
        None,
        description="List of RBAC assignments in the tenant.",
        alias="rbacAssignments",
    )
    relationships: Optional[List[Relationship]] = Field(
        None, description="List of relationships in the tenant.", alias="relationships"
    )
    tenant_settings: Optional[Dict[str, Any]] = Field(
        None, description="Additional tenant-wide settings.", alias="tenantSettings"
    )


class TenantSpec(BaseModel):
    """
    Root model for a tenant specification document.

    Fields:
        tenant: The tenant and all associated resources.
    """

    tenant: Tenant = Field(
        ..., description="The tenant and all associated resources.", alias="tenant"
    )

    @classmethod
    def parse_raw_json(cls, text: str) -> "TenantSpec":
        """
        Parse and validate a TenantSpec from a JSON string.
        """
        try:
            data = json.loads(text)
        except Exception as e:
            raise ValidationError(
                [
                    {
                        "loc": ("__root__",),
                        "msg": f"Invalid JSON: {e}",
                        "type": "value_error.jsondecode",
                    }
                ],
                cls,
            ) from e
        return cls.model_validate(data)

    class Config:
        @staticmethod
        def alias_generator(s: str) -> str:
            """Convert snake_case to camelCase for field aliases."""
            if "_" in s:
                return "".join(
                    [w.capitalize() if i > 0 else w for i, w in enumerate(s.split("_"))]
                )
            return s

        allow_population_by_field_name = True

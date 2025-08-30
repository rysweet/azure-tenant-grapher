# pyright: reportUntypedBaseClass=false
import json
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, ValidationError, root_validator


# Identity containers
class User(BaseModel):
    """
    Represents a user identity in the tenant.

    Fields:
        id: Unique identifier for the user.
        display_name: Display name of the user.
        email: Email address of the user.
    """

    id: str = Field(..., description="Unique identifier for the user.", alias="userId")
    display_name: Optional[str] = Field(
        None, description="Display name of the user.", alias="displayName"
    )
    email: Optional[str] = Field(
        None, description="Email address of the user.", alias="emailAddress"
    )


class Group(BaseModel):
    """
    Represents a group of users or service principals.

    Fields:
        id: Unique identifier for the group.
        display_name: Display name of the group.
        members: List of member IDs (users, groups, or service principals).
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


class ServicePrincipal(BaseModel):
    """
    Represents a service principal identity.

    Fields:
        id: Unique identifier for the service principal.
        display_name: Display name of the service principal.
        app_id: Application ID associated with the service principal.
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
    Represents a relationship between two entities.

    Fields:
        source_id: ID of the source entity.
        target_id: ID of the target entity.
        type: Type of the relationship.
        original_type: Original type from LLM (for GENERIC_RELATIONSHIP).
        narrative_context: Text snippet from source narrative.
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

    @root_validator(pre=True)
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
        rbac_assignments: List of RBAC assignments in the tenant.
        relationships: List of relationships in the tenant.
        narrative_context: Text snippet from source narrative.
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
    rbac_assignments: Optional[List[RBACAssignment]] = Field(
        None,
        description="List of RBAC assignments in the tenant.",
        alias="rbacAssignments",
    )
    relationships: Optional[List[Relationship]] = Field(
        None, description="List of relationships in the tenant.", alias="relationships"
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

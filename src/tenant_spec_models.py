# pyright: reportUntypedBaseClass=false
import json
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ValidationError


# Identity containers
class User(BaseModel):
    id: str
    display_name: Optional[str] = None
    email: Optional[str] = None


class Group(BaseModel):
    id: str
    display_name: Optional[str] = None
    members: Optional[List[str]] = None


class ServicePrincipal(BaseModel):
    id: str
    display_name: Optional[str] = None
    app_id: Optional[str] = None


class ManagedIdentity(BaseModel):
    id: str
    display_name: Optional[str] = None


class AdminUnit(BaseModel):
    id: str
    display_name: Optional[str] = None


# RBAC Assignment
class RBACAssignment(BaseModel):
    principal_id: str
    role: str
    scope: str


# Relationship
class Relationship(BaseModel):
    source_id: str
    target_id: str
    type: str


# Resource
class Resource(BaseModel):
    id: str
    name: str
    type: str
    location: Optional[str] = None
    properties: Optional[Dict[str, Any]] = None


# Resource Group
class ResourceGroup(BaseModel):
    id: str
    name: str
    location: Optional[str] = None
    resources: Optional[List[Resource]] = None


# Subscription
class Subscription(BaseModel):
    id: str
    name: Optional[str] = None
    resource_groups: Optional[List[ResourceGroup]] = None


# Tenant
class Tenant(BaseModel):
    id: str
    display_name: Optional[str] = None
    subscriptions: Optional[List[Subscription]] = None
    users: Optional[List[User]] = None
    groups: Optional[List[Group]] = None
    service_principals: Optional[List[ServicePrincipal]] = None
    managed_identities: Optional[List[ManagedIdentity]] = None
    admin_units: Optional[List[AdminUnit]] = None
    rbac_assignments: Optional[List[RBACAssignment]] = None
    relationships: Optional[List[Relationship]] = None


class TenantSpec(BaseModel):
    tenant: Tenant

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

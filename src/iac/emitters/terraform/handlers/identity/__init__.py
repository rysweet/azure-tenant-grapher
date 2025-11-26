"""Identity handlers for Terraform emission."""

from .entra_group import EntraGroupHandler
from .entra_user import EntraUserHandler
from .managed_identity import ManagedIdentityHandler
from .role_assignment import RoleAssignmentHandler
from .service_principal import ServicePrincipalHandler

__all__ = [
    "EntraGroupHandler",
    "EntraUserHandler",
    "ManagedIdentityHandler",
    "RoleAssignmentHandler",
    "ServicePrincipalHandler",
]

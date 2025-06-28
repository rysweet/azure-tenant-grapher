from typing import Any, Dict

from .relationship_rule import RelationshipRule

# Node labels
ROLE_DEFINITION = "RoleDefinition"
ROLE_ASSIGNMENT = "RoleAssignment"
USER = "User"
SERVICE_PRINCIPAL = "ServicePrincipal"
MANAGED_IDENTITY = "ManagedIdentity"
IDENTITY_GROUP = "IdentityGroup"

# Edge types
ASSIGNED_TO = "ASSIGNED_TO"
HAS_ROLE = "HAS_ROLE"
USES_IDENTITY = "USES_IDENTITY"

PRINCIPAL_TYPE_TO_LABEL = {
    "User": USER,
    "ServicePrincipal": SERVICE_PRINCIPAL,
    "ManagedIdentity": MANAGED_IDENTITY,
    "Group": IDENTITY_GROUP,
}


class IdentityRule(RelationshipRule):
    """
    Emits RBAC and identity-related relationships:
    - (RoleAssignment) -[:ASSIGNED_TO]-> (Identity)
    - (Identity) -[:HAS_ROLE]-> (RoleDefinition)
    - (Resource with identity.principalId) -[:USES_IDENTITY]-> (ManagedIdentity)
    """

    def applies(self, resource: Dict[str, Any]) -> bool:
        rtype = resource.get("type", "")
        # RBAC: roleAssignments, roleDefinitions
        if rtype.endswith("roleAssignments") or rtype.endswith("roleDefinitions"):
            return True
        # Identity: resource with identity.principalId
        if resource.get("identity") and isinstance(resource["identity"], dict):
            return True
        return False

    def emit(self, resource: Dict[str, Any], db_ops: Any) -> None:
        rid = resource.get("id")
        rtype = resource.get("type", "")
        props = resource.get("properties", resource)

        # RBAC: RoleAssignment node/edges
        if rtype.endswith("roleAssignments"):
            # Upsert RoleAssignment node
            db_ops.upsert_generic(ROLE_ASSIGNMENT, "id", rid, {"id": rid})

            # Get principalId, principalType, roleDefinitionId
            principal_id = props.get("principalId")
            principal_type = props.get("principalType")
            role_def_id = props.get("roleDefinitionId")

            # Upsert Identity node
            if principal_id and principal_type:
                label = PRINCIPAL_TYPE_TO_LABEL.get(principal_type, "Identity")
                db_ops.upsert_generic(
                    label,
                    "id",
                    principal_id,
                    {"id": principal_id, "principalType": principal_type},
                )
                # ASSIGNED_TO: RoleAssignment → Identity
                db_ops.create_generic_rel(rid, ASSIGNED_TO, principal_id, label, "id")
                # HAS_ROLE: Identity → RoleDefinition
                if role_def_id:
                    db_ops.upsert_generic(
                        ROLE_DEFINITION, "id", role_def_id, {"id": role_def_id}
                    )
                    db_ops.create_generic_rel(
                        principal_id, HAS_ROLE, role_def_id, ROLE_DEFINITION, "id"
                    )

        # RBAC: RoleDefinition node
        elif rtype.endswith("roleDefinitions"):
            db_ops.upsert_generic(
                ROLE_DEFINITION,
                "id",
                rid,
                {
                    "id": rid,
                    "roleName": props.get("roleName", ""),
                    "description": props.get("description", ""),
                },
            )

        # Identity: resource with identity.principalId
        identity = resource.get("identity")
        if identity and isinstance(identity, dict):
            principal_id = identity.get("principalId")
            if principal_id and rid:
                db_ops.create_generic_rel(
                    str(rid), USES_IDENTITY, str(principal_id), MANAGED_IDENTITY, "id"
                )

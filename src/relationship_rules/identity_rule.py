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
            # Upsert RoleAssignment node with all relevant metadata
            db_ops.upsert_generic(
                ROLE_ASSIGNMENT,
                "id",
                rid,
                {
                    "id": rid,
                    "principalId": props.get("principalId"),
                    "principalType": props.get("principalType"),
                    "roleDefinitionId": props.get("roleDefinitionId"),
                    "scope": props.get("scope"),
                },
            )

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

        # Identity: resource with identity block (system/user-assigned)
        identity = resource.get("identity")
        if identity and isinstance(identity, dict):
            # System-assigned identity
            if identity.get("type") == "SystemAssigned":
                principal_id = identity.get("principalId") or resource.get(
                    "principalId"
                )
                if principal_id and rid:
                    # Upsert ManagedIdentity node (system-assigned)
                    db_ops.upsert_generic(
                        MANAGED_IDENTITY,
                        "id",
                        principal_id,
                        {
                            "id": principal_id,
                            "identityType": "SystemAssigned",
                            "resourceId": rid,
                        },
                    )
                    # USES_IDENTITY edge
                    db_ops.create_generic_rel(
                        str(rid),
                        USES_IDENTITY,
                        str(principal_id),
                        MANAGED_IDENTITY,
                        "id",
                    )
            # User-assigned identity
            if (
                identity.get("type") == "UserAssigned"
                and "userAssignedIdentities" in identity
            ):
                user_identities = identity.get("userAssignedIdentities", {})
                for uai_id in user_identities:
                    # Upsert ManagedIdentity node (user-assigned)
                    db_ops.upsert_generic(
                        MANAGED_IDENTITY,
                        "id",
                        uai_id,
                        {
                            "id": uai_id,
                            "identityType": "UserAssigned",
                        },
                    )
                    # USES_IDENTITY edge
                    db_ops.create_generic_rel(
                        str(rid), USES_IDENTITY, str(uai_id), MANAGED_IDENTITY, "id"
                    )
            # If principalId present (legacy or fallback)
            principal_id = identity.get("principalId")
            if principal_id and rid and identity.get("type") != "SystemAssigned":
                db_ops.upsert_generic(
                    MANAGED_IDENTITY,
                    "id",
                    principal_id,
                    {
                        "id": principal_id,
                        "identityType": identity.get("type", "Unknown"),
                        "resourceId": rid,
                    },
                )
                db_ops.create_generic_rel(
                    str(rid), USES_IDENTITY, str(principal_id), MANAGED_IDENTITY, "id"
                )

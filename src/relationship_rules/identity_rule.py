from typing import Any, Dict

from .relationship_rule import RelationshipRule


class IdentityRule(RelationshipRule):
    """
    Emits identity-related relationships:
    - (Resource with identity.principalId) -[:USES_IDENTITY]-> (ManagedIdentity)
    - (KeyVault) -[:POLICY_FOR]-> (ManagedIdentity) for each access-policy principalId
    """

    def applies(self, resource: Dict[str, Any]) -> bool:
        rtype = resource.get("type", "")
        return (
            resource.get("identity") and isinstance(resource["identity"], dict)
        ) or (rtype.endswith("vaults") and "properties" in resource)

    def emit(self, resource: Dict[str, Any], db_ops: Any) -> None:
        rid = resource.get("id")
        rtype = resource.get("type", "")
        props = resource

        # (Resource with identity.principalId) -[:USES_IDENTITY]-> (ManagedIdentity)
        identity = props.get("identity")
        if identity and isinstance(identity, dict):
            principal_id = identity.get("principalId")
            if principal_id and rid:
                db_ops.create_generic_rel(
                    str(rid),
                    "USES_IDENTITY",
                    str(principal_id),
                    "ManagedIdentity",
                    "id",
                )

        # (KeyVault) -[:POLICY_FOR]-> (ManagedIdentity) for each access-policy principalId
        if rtype.endswith("vaults"):
            access_policies = props.get("properties", {}).get("accessPolicies", [])
            for policy in access_policies:
                pid = policy.get("objectId")
                if pid and rid:
                    db_ops.create_generic_rel(
                        str(rid), "POLICY_FOR", str(pid), "ManagedIdentity", "id"
                    )

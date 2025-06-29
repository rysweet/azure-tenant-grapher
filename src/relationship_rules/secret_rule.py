from typing import Any, Dict

from .relationship_rule import RelationshipRule


class SecretRule(RelationshipRule):
    """
    Handles the STORES_SECRET relationship between KeyVault and KeyVaultSecret nodes.
    """

    def applies(self, resource: Dict[str, Any]) -> bool:
        # This rule applies to KeyVault resources that have discovered secrets
        return (
            resource.get("type") == "Microsoft.KeyVault/vaults"
            and "secrets" in resource
        )

    def emit(self, resource: Dict[str, Any], db_ops: Any) -> None:
        keyvault_id = resource.get("id")
        secrets = resource.get("secrets", [])
        for secret in secrets:
            secret_name = secret.get("name")
            content_type = secret.get("contentType")
            # Create KeyVaultSecret node (no value stored)
            db_ops.create_node(
                "KeyVaultSecret", {"name": secret_name, "contentType": content_type}
            )
            # Create STORES_SECRET relationship
            db_ops.create_relationship(
                from_label="KeyVault",
                from_key="id",
                from_value=keyvault_id,
                to_label="KeyVaultSecret",
                to_key="name",
                to_value=secret_name,
                rel_type="STORES_SECRET",
            )

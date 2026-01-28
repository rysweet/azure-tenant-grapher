"""
SecretRule - Handles KeyVault secret relationships in the graph.

This rule processes Microsoft.KeyVault/vaults resources and creates:
1. KeyVaultSecret nodes for each discovered secret
2. STORES_SECRET relationships from KeyVault to KeyVaultSecret nodes

Supports dual-graph architecture - creates relationships in both original
and abstracted graphs. KeyVaultSecret nodes are shared between graphs
(not duplicated).

Issue #478: Fixed broken API - was using non-existent create_node() and
create_relationship() methods. Now uses upsert_generic() and
create_dual_graph_generic_rel() as per the standard pattern.
"""

from typing import Any, Dict, Set

from .relationship_rule import RelationshipRule


class SecretRule(RelationshipRule):
    """
    Handles the STORES_SECRET relationship between KeyVault and KeyVaultSecret nodes.

    Creates KeyVaultSecret nodes for each secret discovered in a KeyVault resource
    and links them via STORES_SECRET relationships.

    Supports dual-graph architecture - creates relationships in both original
    and abstracted graphs. KeyVaultSecret nodes are shared between graphs.
    """

    def applies(self, resource: Dict[str, Any]) -> bool:
        """
        Check if this rule applies to the given resource.

        Args:
            resource: Resource dictionary from Azure discovery.

        Returns:
            True if resource is a KeyVault with discovered secrets.
        """
        # This rule applies to KeyVault resources that have discovered secrets
        # Empty secrets list should return False (no work to do)
        secrets = resource.get("secrets", [])
        return (
            resource.get("type") == "Microsoft.KeyVault/vaults"
            and isinstance(secrets, list)
            and len(secrets) > 0
        )

    def emit(self, resource: Dict[str, Any], db_ops: Any) -> None:
        """
        Emit KeyVaultSecret nodes and STORES_SECRET relationships.

        For each secret in the KeyVault:
        1. Creates/updates a KeyVaultSecret node with name and contentType
        2. Creates STORES_SECRET relationship from KeyVault to KeyVaultSecret

        Note: Secret values are NEVER stored in the graph for security.

        Args:
            resource: KeyVault resource dictionary with secrets list.
            db_ops: DatabaseOperations instance for graph operations.
        """
        keyvault_id = resource.get("id")
        secrets = resource.get("secrets", [])

        for secret in secrets:
            secret_name = secret.get("name")
            if not secret_name:
                continue

            content_type = secret.get("contentType")

            # Create/update KeyVaultSecret node (no value stored for security)
            # Uses upsert_generic as per standard pattern (TagRule, RegionRule, etc.)
            db_ops.upsert_generic(
                "KeyVaultSecret",
                "name",
                secret_name,
                {
                    "name": secret_name,
                    "contentType": content_type,
                    "keyVaultId": keyvault_id,  # Reference to parent KeyVault
                },
            )

            # Create STORES_SECRET relationship from KeyVault to KeyVaultSecret
            # Uses dual-graph helper to create in both original and abstracted graphs
            if keyvault_id:
                self.create_dual_graph_generic_rel(
                    db_ops,
                    str(keyvault_id),
                    "STORES_SECRET",
                    secret_name,
                    "KeyVaultSecret",
                    "name",
                )

    def extract_target_ids(self, resource: Dict[str, Any]) -> Set[str]:
        """
        Extract target resource IDs for secret relationships.

        KeyVaultSecret nodes are generic nodes (not resources), so this returns
        empty set. No cross-RG dependencies to fetch.
        """
        return set()

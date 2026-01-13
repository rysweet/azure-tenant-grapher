"""
Relationship Emitter Module

This module handles creation of Neo4j relationships between nodes.
"""

from typing import Any, Dict

import structlog

from src.utils.session_manager import retry_neo4j_operation

from .serialization import serialize_value

logger = structlog.get_logger(__name__)


@retry_neo4j_operation()
def run_neo4j_query_with_retry(session: Any, query: str, **params: Any) -> Any:
    """Run a Neo4j query with retry logic."""
    return session.run(query, **params)


class RelationshipEmitter:
    """Handles creation of Neo4j relationships between nodes."""

    def __init__(self, session_manager: Any, node_manager: Any = None) -> None:
        """
        Initialize the RelationshipEmitter.

        Args:
            session_manager: Neo4jSessionManager instance
            node_manager: Optional NodeManager for subscription/RG upserts
        """
        self.session_manager = session_manager
        self._node_manager = node_manager

    def create_subscription_relationship(
        self, subscription_id: str, resource_id: str
    ) -> bool:
        """
        Create relationship between subscription and resource.

        Args:
            subscription_id: Subscription ID
            resource_id: Resource ID

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Ensure Subscription node exists
            if self._node_manager is not None:
                self._node_manager.upsert_subscription(subscription_id)

            query = """
            MATCH (s:Subscription {id: $subscription_id})
            MATCH (r:Resource {id: $resource_id})
            MERGE (s)-[:CONTAINS]->(r)
            """
            with self.session_manager.session() as session:
                run_neo4j_query_with_retry(
                    session,
                    query,
                    subscription_id=subscription_id,
                    resource_id=resource_id,
                )
            return True
        except Exception:
            logger.exception(
                f"Error creating subscription relationship for {resource_id}"
            )
            return False

    def create_resource_group_relationships(self, resource: Dict[str, Any]) -> bool:
        """
        Create resource group nodes and relationships.

        Args:
            resource: Resource dictionary containing resource_group, subscription_id, id

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if not resource.get("resource_group"):
                return True

            rg_name = resource["resource_group"]
            subscription_id = resource["subscription_id"]
            resource_id = resource["id"]
            # Build full Azure ID for ResourceGroup
            rg_id = f"/subscriptions/{subscription_id}/resourceGroups/{rg_name}"

            logger.info(
                f"DEBUG: Creating RG relationships for resource id={resource_id}, resource_group={rg_name}, subscription_id={subscription_id}"
            )

            # Upsert Subscription and ResourceGroup nodes if node_manager available
            if self._node_manager is not None:
                self._node_manager.upsert_subscription(subscription_id)
                self._node_manager.upsert_resource_group(
                    rg_id, rg_name, subscription_id
                )

            # Create relationship: Subscription CONTAINS ResourceGroup
            sub_rg_query = """
            MATCH (s:Subscription {id: $subscription_id})
            MATCH (rg:ResourceGroup {id: $rg_id})
            MERGE (s)-[:CONTAINS]->(rg)
            """
            with self.session_manager.session() as session:
                run_neo4j_query_with_retry(
                    session,
                    sub_rg_query,
                    subscription_id=subscription_id,
                    rg_id=rg_id,
                )

            # Create relationship: ResourceGroup CONTAINS Resource
            rg_resource_query = """
            MATCH (rg:ResourceGroup {id: $rg_id})
            MATCH (r:Resource {id: $resource_id})
            MERGE (rg)-[:CONTAINS]->(r)
            """
            with self.session_manager.session() as session:
                run_neo4j_query_with_retry(
                    session,
                    rg_resource_query,
                    rg_id=rg_id,
                    resource_id=resource_id,
                )

            return True

        except Exception:
            logger.exception(
                f"Error creating resource group relationships for {resource.get('id', 'Unknown')}"
            )
            return False

    def create_relationship(self, src_id: str, rel_type: str, tgt_id: str) -> None:
        """
        Create a relationship of type rel_type from src_id to tgt_id using MERGE semantics.

        Args:
            src_id: Source resource ID
            rel_type: Relationship type
            tgt_id: Target resource ID
        """
        query = (
            "MATCH (src:Resource {id: $src_id}) "
            "MATCH (tgt:Resource {id: $tgt_id}) "
            f"MERGE (src)-[:{rel_type}]->(tgt)"
        )
        with self.session_manager.session() as session:
            session.run(query, src_id=src_id, tgt_id=tgt_id)

    def upsert_generic(
        self, label: str, key_prop: str, key_value: str, properties: Dict[str, Any]
    ) -> bool:
        """
        Create or update a generic node with the specified label and properties.

        Args:
            label: Node label (e.g., "Region", "Tag")
            key_prop: Property name to use as unique key (e.g., "code", "name")
            key_value: Value for the key property
            properties: Additional properties to set on the node

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Serialize all property values and filter out None values
            # Neo4j 5.x does not allow None values in SET operations with += operator
            serialized_props = {}
            for k, v in properties.items():
                serialized_val = serialize_value(v)
                # Only include non-None values to avoid CypherTypeError
                if serialized_val is not None:
                    serialized_props[k] = serialized_val

            # Add the key property
            key_val_serialized = serialize_value(key_value)
            if key_val_serialized is not None:
                serialized_props[key_prop] = key_val_serialized

            query = f"""
            MERGE (n:{label} {{{key_prop}: $key_value}})
            SET n += $props,
                n.updated_at = datetime()
            """

            with self.session_manager.session() as session:
                session.run(query, key_value=key_value, props=serialized_props)
            return True

        except Exception:
            logger.exception(
                f"Error upserting {label} node with {key_prop}={key_value}"
            )
            return False

    def create_generic_rel(
        self,
        src_id: str,
        rel_type: str,
        tgt_key_value: str,
        tgt_label: str,
        tgt_key_prop: str,
    ) -> bool:
        """
        Create a relationship from a Resource to a generic node identified by a key property.

        Args:
            src_id: Source resource ID
            rel_type: Relationship type (e.g., "LOCATED_IN", "HAS_TAG")
            tgt_key_value: Value of the target node's key property
            tgt_label: Label of the target node (e.g., "Region", "Tag")
            tgt_key_prop: Property name used to identify the target node (e.g., "code", "name")

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            query = f"""
            MATCH (src:Resource {{id: $src_id}})
            MATCH (tgt:{tgt_label} {{{tgt_key_prop}: $tgt_key_value}})
            MERGE (src)-[:{rel_type}]->(tgt)
            """

            with self.session_manager.session() as session:
                session.run(query, src_id=src_id, tgt_key_value=tgt_key_value)
            return True

        except Exception:
            logger.exception(
                f"Error creating {rel_type} relationship from {src_id} to {tgt_label}({tgt_key_prop}={tgt_key_value})"
            )
            return False

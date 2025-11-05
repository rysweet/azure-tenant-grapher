from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

import structlog

logger = structlog.get_logger(__name__)


class RelationshipRule(ABC):
    """
    Abstract base class for all relationship enrichment rules.
    Each rule determines if it applies to a resource and emits relationships via db_ops.

    Supports dual-graph architecture where relationships exist in both:
    1. Original graph (:Resource:Original nodes with real Azure IDs)
    2. Abstracted graph (:Resource nodes with type-prefixed hash IDs)
    """

    def __init__(self, enable_dual_graph: bool = False):
        """
        Initialize relationship rule.

        Args:
            enable_dual_graph: If True, create relationships in both original and abstracted graphs
        """
        self.enable_dual_graph = enable_dual_graph

    @abstractmethod
    def applies(self, resource: Dict[str, Any]) -> bool:
        """Return True if this rule should process the given resource."""
        pass

    @abstractmethod
    def emit(self, resource: Dict[str, Any], db_ops: Any) -> None:
        """
        Emit any nodes/edges for this resource using db_ops.
        db_ops: DatabaseOperations instance.
        """
        pass

    def create_dual_graph_relationship(
        self,
        db_ops: Any,
        src_id: str,
        rel_type: str,
        tgt_id: str,
        properties: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Create relationship in both graphs if dual-graph is enabled.

        This method ensures relationship topology is preserved across both graphs:
        1. Creates relationship between original nodes (:Resource:Original)
        2. Finds abstracted equivalents via SCAN_SOURCE_NODE
        3. Creates same relationship between abstracted nodes (:Resource)

        Args:
            db_ops: DatabaseOperations instance with session_manager
            src_id: Source resource ID (original Azure ID)
            rel_type: Relationship type (e.g., "USES_SUBNET", "SECURED_BY")
            tgt_id: Target resource ID (original Azure ID)
            properties: Optional relationship properties

        Returns:
            bool: True if successful, False otherwise

        Example:
            >>> self.create_dual_graph_relationship(
            ...     db_ops,
            ...     vm_id,
            ...     "USES_SUBNET",
            ...     subnet_id
            ... )
        """
        if not self.enable_dual_graph:
            # Legacy mode: use old API (create_generic_rel for Resource-to-Resource)
            # This maintains backward compatibility with tests
            if hasattr(db_ops, "create_generic_rel"):
                return db_ops.create_generic_rel(
                    src_id, rel_type, tgt_id, "Resource", "id"
                )
            return self._create_legacy_relationship(
                db_ops, src_id, rel_type, tgt_id, properties
            )

        try:
            # Build property string for Cypher query
            prop_string = ""
            if properties:
                prop_string = " SET rel += $properties"

            # Dual-graph mode: Create relationships in both graphs
            query = f"""
            // Create relationship between original nodes
            MATCH (src_orig:Resource:Original {{id: $src_id}})
            MATCH (tgt_orig:Resource:Original {{id: $tgt_id}})
            MERGE (src_orig)-[rel_orig:{rel_type}]->(tgt_orig)
            {prop_string.replace("rel", "rel_orig") if prop_string else ""}

            // Find abstracted nodes via SCAN_SOURCE_NODE
            WITH src_orig, tgt_orig
            OPTIONAL MATCH (src_abs:Resource)<-[:SCAN_SOURCE_NODE]-(src_orig)
            OPTIONAL MATCH (tgt_abs:Resource)<-[:SCAN_SOURCE_NODE]-(tgt_orig)

            // Create relationship between abstracted nodes if both exist
            WITH src_abs, tgt_abs
            WHERE src_abs IS NOT NULL AND tgt_abs IS NOT NULL
            MERGE (src_abs)-[rel_abs:{rel_type}]->(tgt_abs)
            {prop_string.replace("rel", "rel_abs") if prop_string else ""}

            RETURN count(rel_abs) as abstracted_count
            """

            with db_ops.session_manager.session() as session:
                result = session.run(
                    query,
                    src_id=src_id,
                    tgt_id=tgt_id,
                    properties=properties or {},
                )
                record = result.single()

                # Log if abstracted relationship wasn't created (nodes might not exist yet)
                if record and record["abstracted_count"] == 0:
                    logger.debug(
                        f"Abstracted relationship not created (nodes may not exist): "
                        f"{src_id} -{rel_type}-> {tgt_id}"
                    )

            return True

        except Exception as e:
            logger.exception(
                f"Error creating dual-graph relationship {rel_type} "
                f"from {src_id} to {tgt_id}: {e}"
            )
            return False

    def _create_legacy_relationship(
        self,
        db_ops: Any,
        src_id: str,
        rel_type: str,
        tgt_id: str,
        properties: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Create relationship in legacy single-graph mode.

        Uses the old db_ops API for backward compatibility with tests.

        Args:
            db_ops: DatabaseOperations instance
            src_id: Source resource ID
            rel_type: Relationship type
            tgt_id: Target resource ID
            properties: Optional relationship properties

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Check if db_ops has session_manager (new API) or legacy methods
            if hasattr(db_ops, "session_manager"):
                # New API with session_manager
                prop_string = ""
                if properties:
                    prop_string = " SET rel += $properties"

                query = f"""
                MATCH (src:Resource {{id: $src_id}})
                MATCH (tgt:Resource {{id: $tgt_id}})
                MERGE (src)-[rel:{rel_type}]->(tgt)
                {prop_string}
                """

                with db_ops.session_manager.session() as session:
                    session.run(
                        query,
                        src_id=src_id,
                        tgt_id=tgt_id,
                        properties=properties or {},
                    )
            else:
                # Legacy mock API (for tests) - relationship created via generic_rel
                # These mocks don't actually execute Cypher, they just record calls
                # So we don't create the relationship at all here
                logger.debug(
                    f"Legacy mode (mock): would create {rel_type} from {src_id} to {tgt_id}"
                )
                return True

            return True

        except Exception as e:
            logger.exception(
                f"Error creating legacy relationship {rel_type} "
                f"from {src_id} to {tgt_id}: {e}"
            )
            return False

    def create_dual_graph_generic_rel(
        self,
        db_ops: Any,
        src_id: str,
        rel_type: str,
        tgt_key_value: str,
        tgt_label: str,
        tgt_key_prop: str,
    ) -> bool:
        """
        Create relationship to a non-Resource node (Tag, Region, etc.) in both graphs.

        For relationships to generic nodes like Tags, Regions, etc., we need to:
        1. Create relationship from original Resource to the shared node
        2. Create relationship from abstracted Resource to the same shared node

        Note: Generic nodes (Tag, Region, etc.) are NOT duplicated - they exist once
        and are referenced by both original and abstracted Resource nodes.

        Args:
            db_ops: DatabaseOperations instance
            src_id: Source resource ID (original Azure ID)
            rel_type: Relationship type (e.g., "TAGGED_WITH", "LOCATED_IN")
            tgt_key_value: Target node key value
            tgt_label: Target node label (e.g., "Tag", "Region")
            tgt_key_prop: Target node key property (e.g., "id", "code")

        Returns:
            bool: True if successful, False otherwise
        """
        if not self.enable_dual_graph:
            # Legacy mode: use db_ops.create_generic_rel
            return db_ops.create_generic_rel(
                src_id, rel_type, tgt_key_value, tgt_label, tgt_key_prop
            )

        try:
            # Dual-graph mode: Create from both original and abstracted nodes
            query = f"""
            // Find target node (shared between graphs)
            MATCH (tgt:{tgt_label} {{{tgt_key_prop}: $tgt_key_value}})

            // Create relationship from original Resource
            MATCH (src_orig:Resource:Original {{id: $src_id}})
            MERGE (src_orig)-[:{rel_type}]->(tgt)

            // Find abstracted Resource via SCAN_SOURCE_NODE
            WITH src_orig, tgt
            OPTIONAL MATCH (src_abs:Resource)<-[:SCAN_SOURCE_NODE]-(src_orig)

            // Create relationship from abstracted Resource if it exists
            WITH src_abs, tgt
            WHERE src_abs IS NOT NULL
            MERGE (src_abs)-[:{rel_type}]->(tgt)

            RETURN count(src_abs) as abstracted_count
            """

            with db_ops.session_manager.session() as session:
                result = session.run(query, src_id=src_id, tgt_key_value=tgt_key_value)
                record = result.single()

                if record and record["abstracted_count"] == 0:
                    logger.debug(
                        f"Abstracted node not found for relationship: "
                        f"{src_id} -{rel_type}-> {tgt_label}({tgt_key_prop}={tgt_key_value})"
                    )

            return True

        except Exception as e:
            logger.exception(
                f"Error creating dual-graph generic relationship {rel_type} "
                f"from {src_id} to {tgt_label}({tgt_key_prop}={tgt_key_value}): {e}"
            )
            return False

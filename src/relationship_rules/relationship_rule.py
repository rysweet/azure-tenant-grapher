from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Set, Tuple

import structlog  # type: ignore[import-untyped]

logger = structlog.get_logger(__name__)


class RelationshipRule(ABC):
    """
    Abstract base class for all relationship enrichment rules.
    Each rule determines if it applies to a resource and emits relationships via db_ops.

    Supports dual-graph architecture where relationships exist in both:
    1. Original graph (:Resource:Original nodes with real Azure IDs)
    2. Abstracted graph (:Resource nodes with type-prefixed hash IDs)
    """

    # SECURITY FIX (H1): Whitelist of valid relationship types to prevent Cypher injection
    # Relationship types are interpolated directly into Cypher queries, so we validate
    # them against this whitelist before use.
    VALID_RELATIONSHIP_TYPES = {
        "CONTAINS",
        "USES_SUBNET",
        "SECURED_BY",
        "CONNECTED_TO",
        "DEPENDS_ON",
        "USES_IDENTITY",
        "RESOLVES_TO",
        "CONNECTED_TO_PE",
        "MONITORS",
        "LOGS_TO",
        "USES_NETWORK",
        "TAGGED_WITH",
        "LOCATED_IN",
        "CREATED_BY",
        "SENDS_DIAG_TO",
        "ASSIGNED_TO",
        "HAS_ROLE",
        "INHERITS_TAG",
        "STORES_SECRET",
    }

    def __init__(self, enable_dual_graph: bool = False):
        """
        Initialize relationship rule.

        Args:
            enable_dual_graph: If True, create relationships in both original and abstracted graphs
        """
        self.enable_dual_graph = enable_dual_graph
        # Buffer for batched relationship creation
        self._relationship_buffer: List[
            Tuple[str, str, str, Optional[Dict[str, Any]]]
        ] = []
        self._buffer_size = 100  # Batch size for relationship creation

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

    def extract_target_ids(self, resource: Dict[str, Any]) -> Set[str]:
        """
        Extract resource IDs that this rule would create relationships to.

        This method enables relationship-driven cross-RG dependency collection
        by identifying target resource IDs BEFORE relationships are created.
        When filtering by resource group, missing target resources can be
        fetched from Azure and included in the graph.

        Default implementation returns empty set (rules that don't create
        Resource-to-Resource relationships can use this default).

        Args:
            resource: Resource dict with 'id', 'type', 'properties', etc.

        Returns:
            Set of target resource IDs (full Azure resource IDs) that this
            rule would create relationships to. Empty set if no dependencies.

        Example:
            For a VM resource, NetworkRule.extract_target_ids() returns:
            {
                "/subscriptions/.../networkInterfaces/nic1",
                "/subscriptions/.../networkInterfaces/nic2"
            }

            For a subnet resource, NetworkRule.extract_target_ids() returns:
            {
                "/subscriptions/.../networkSecurityGroups/nsg1"
            }

        Implementation Notes:
            - Only return Resource-to-Resource relationship targets
            - Skip shared nodes (Tag, Region, Creator) - those aren't fetched
            - Return empty set for rules that only create relationships to
              shared nodes (TagRule, RegionRule, CreatorRule)
            - Parse resource properties the same way emit() does, but only
              extract IDs instead of creating relationships

        Performance:
            This method is called once per resource during Phase 2.6
            (dependency collection). Keep it fast - no I/O, just property parsing.
        """
        return set()

    def create_dual_graph_relationship(
        self,
        db_ops: Any,
        src_id: str,
        rel_type: str,
        tgt_id: str,
        properties: Optional[Dict[str, Any]] = None,
        immediate_flush: bool = False,
    ) -> bool:
        """
        Create relationship in both graphs if dual-graph is enabled.

        Uses batched approach for performance by default - queues relationships and
        flushes in batches of 100 to avoid N+1 query problem.

        For critical hierarchical relationships (CONTAINS, USES_SUBNET), set
        immediate_flush=True to create relationships synchronously.

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
            immediate_flush: If True, create relationship immediately without buffering.
                           Use for critical hierarchical relationships (CONTAINS, USES_SUBNET).

        Returns:
            bool: True if successful, False otherwise

        Example:
            >>> # Batched (default)
            >>> self.create_dual_graph_relationship(
            ...     db_ops,
            ...     vm_id,
            ...     "SECURED_BY",
            ...     nsg_id
            ... )
            >>> # Immediate (for critical relationships)
            >>> self.create_dual_graph_relationship(
            ...     db_ops,
            ...     vnet_id,
            ...     "CONTAINS",
            ...     subnet_id,
            ...     immediate_flush=True
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

        # If immediate flush requested, create synchronously
        if immediate_flush:
            return self._create_dual_graph_relationship_immediate(
                db_ops, src_id, rel_type, tgt_id, properties
            )

        # Otherwise, use batched approach for performance
        self.queue_dual_graph_relationship(src_id, rel_type, tgt_id, properties)
        self.auto_flush_if_needed(db_ops)
        return True

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
            if (
                hasattr(db_ops, "session_manager")
                and db_ops.session_manager is not None
            ):
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
                if hasattr(db_ops, "create_generic_rel"):
                    db_ops.create_generic_rel(
                        src_id, rel_type, tgt_id, "Resource", "id"
                    )
                logger.debug(
                    f"Legacy mode (mock): created {rel_type} from {src_id} to {tgt_id}"
                )
                return True

            return True

        except Exception as e:
            logger.exception(
                f"Error creating legacy relationship {rel_type} "
                f"from {src_id} to {tgt_id}: {e}"
            )
            return False

    def _create_dual_graph_relationship_immediate(
        self,
        db_ops: Any,
        src_id: str,
        rel_type: str,
        tgt_id: str,
        properties: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Create relationship immediately in both graphs with validation.

        This method creates relationships synchronously without buffering,
        ensuring critical hierarchical relationships (CONTAINS, USES_SUBNET)
        are created immediately when target nodes exist.

        Verifies all four nodes exist before creating relationships:
        - src_orig: Original source node (:Resource:Original)
        - tgt_orig: Original target node (:Resource:Original)
        - src_abs: Abstracted source node (:Resource)
        - tgt_abs: Abstracted target node (:Resource)

        Uses MERGE for idempotency - safe to call multiple times.

        Args:
            db_ops: DatabaseOperations instance with session_manager
            src_id: Source resource ID (original Azure ID)
            rel_type: Relationship type (e.g., "CONTAINS", "USES_SUBNET")
            tgt_id: Target resource ID (original Azure ID)
            properties: Optional relationship properties

        Returns:
            bool: True if both relationships created, False if any node missing

        Example:
            >>> self._create_dual_graph_relationship_immediate(
            ...     db_ops,
            ...     vnet_id,
            ...     "CONTAINS",
            ...     subnet_id,
            ...     immediate_flush=True
            ... )
        """
        if not self.enable_dual_graph:
            return self._create_legacy_relationship(
                db_ops, src_id, rel_type, tgt_id, properties
            )

        # SECURITY FIX (H1): Validate relationship type to prevent Cypher injection
        if rel_type not in self.VALID_RELATIONSHIP_TYPES:
            raise ValueError(
                f"Invalid relationship type: {rel_type}. "
                f"Must be one of {self.VALID_RELATIONSHIP_TYPES}"
            )

        try:
            # Single query that verifies all nodes exist and creates both relationships
            prop_string = ""
            if properties:
                prop_string = """
                SET r_orig += $properties
                SET r_abs += $properties
                """

            query = f"""
            // Find original nodes (indexed lookups)
            MATCH (src_orig:Resource:Original {{id: $src_id}})
            MATCH (tgt_orig:Resource:Original {{id: $tgt_id}})

            // Find abstracted nodes via indexed original_id property
            MATCH (src_abs:Resource {{original_id: $src_id}})
            MATCH (tgt_abs:Resource {{original_id: $tgt_id}})

            // Create relationships in both graphs using MERGE for idempotency
            MERGE (src_orig)-[r_orig:{rel_type}]->(tgt_orig)
            MERGE (src_abs)-[r_abs:{rel_type}]->(tgt_abs)

            {prop_string}

            // Return counts to verify creation
            RETURN
                count(r_orig) as orig_created,
                count(r_abs) as abs_created
            """

            # Check if we have session_manager (production) or mock (tests)
            if not hasattr(db_ops, "session_manager") or db_ops.session_manager is None:
                # Test mode: just call the legacy method which logs and returns True
                return self._create_legacy_relationship(
                    db_ops, src_id, rel_type, tgt_id, properties
                )

            with db_ops.session_manager.session() as session:
                result = session.run(
                    query,
                    src_id=src_id,
                    tgt_id=tgt_id,
                    properties=properties or {},
                )
                record = result.single()

                # ROBUSTNESS FIX (H2): Improved node existence verification
                if record:
                    orig_created = record["orig_created"]
                    abs_created = record["abs_created"]

                    if orig_created == 1 and abs_created == 1:
                        return True
                    logger.warning(
                        f"Failed to create {rel_type} relationship: "
                        f"orig_created={orig_created}, abs_created={abs_created}, "
                        f"src={src_id}, tgt={tgt_id}"
                    )
                return False

        except Exception as e:
            # Log warning instead of exception - missing nodes are expected during processing
            logger.warning(
                f"Could not create immediate {rel_type} relationship "
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

    def queue_dual_graph_relationship(
        self,
        src_id: str,
        rel_type: str,
        tgt_id: str,
        properties: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Queue a relationship for batched creation.

        Instead of creating relationships one-at-a-time (N+1 problem), buffer them
        and create in batches using a single optimized query.

        Args:
            src_id: Source resource ID (original Azure ID)
            rel_type: Relationship type
            tgt_id: Target resource ID (original Azure ID)
            properties: Optional relationship properties
        """
        self._relationship_buffer.append((src_id, rel_type, tgt_id, properties))

    def flush_relationship_buffer(self, db_ops: Any) -> int:
        """
        Flush buffered relationships to database in a single optimized batch query.

        This method solves the N+1 query problem by:
        1. Creating all relationships in a single transaction
        2. Using UNWIND for batch processing
        3. Leveraging indexes on both Original and Resource nodes
        4. Minimizing relationship traversals via optimized query structure

        Performance improvement: O(1) query vs O(N) queries

        Args:
            db_ops: DatabaseOperations instance with session_manager

        Returns:
            int: Number of relationships created
        """
        if not self._relationship_buffer:
            return 0

        # ROBUSTNESS FIX (M2): Buffer size protection to prevent unbounded growth
        # If buffer exceeds max size (10x batch size), it indicates persistent flush failures
        max_buffer_size = self._buffer_size * 10
        if len(self._relationship_buffer) > max_buffer_size:
            logger.error(
                f"Buffer exceeded max size ({max_buffer_size}), forcibly clearing. "
                f"This indicates persistent flush failures. "
                f"Current buffer size: {len(self._relationship_buffer)}"
            )
            self._relationship_buffer.clear()
            return 0

        if not self.enable_dual_graph:
            # Legacy mode: create relationships individually
            count = 0
            for src_id, rel_type, tgt_id, properties in self._relationship_buffer:
                if self.create_dual_graph_relationship(
                    db_ops, src_id, rel_type, tgt_id, properties
                ):
                    count += 1
            self._relationship_buffer.clear()
            return count

        try:
            # Group relationships by type for optimized batch processing
            relationships_by_type: Dict[str, List[Dict[str, Any]]] = {}
            for src_id, rel_type, tgt_id, properties in self._relationship_buffer:
                # SECURITY FIX (H1): Validate relationship type to prevent Cypher injection
                if rel_type not in self.VALID_RELATIONSHIP_TYPES:
                    logger.error(
                        f"Invalid relationship type '{rel_type}' in buffer, skipping. "
                        f"Valid types: {self.VALID_RELATIONSHIP_TYPES}"
                    )
                    continue

                if rel_type not in relationships_by_type:
                    relationships_by_type[rel_type] = []
                relationships_by_type[rel_type].append(
                    {
                        "src_id": src_id,
                        "tgt_id": tgt_id,
                        "properties": properties or {},
                    }
                )

            total_created = 0
            total_expected = 0

            # Check if we have a session_manager for batched operations
            # Fall back to individual creation if not (e.g., in tests)
            if not hasattr(db_ops, "session_manager") or db_ops.session_manager is None:
                # Fallback: create relationships individually WITHOUT auto-flush
                # to prevent infinite recursion
                for src_id, rel_type, tgt_id, properties in self._relationship_buffer:
                    # Call the immediate creation method directly (bypasses buffering)
                    if self._create_legacy_relationship(
                        db_ops, src_id, rel_type, tgt_id, properties
                    ):
                        total_created += 1
                self._relationship_buffer.clear()
                return total_created

            # TRANSACTIONAL FIX (C1): Wrap all relationship creation in a single transaction
            # This prevents partial state if any batch fails - all relationships created
            # or none are created (atomic operation)
            with db_ops.session_manager.session() as session:
                with session.begin_transaction() as tx:
                    # Process each relationship type in a single batch query
                    for rel_type, relationships in relationships_by_type.items():
                        expected_count = len(relationships)
                        total_expected += expected_count

                        query = f"""
                        // Batch create relationships using UNWIND for optimal performance
                        UNWIND $relationships AS rel

                        // Find original nodes (indexed lookups)
                        MATCH (src_orig:Resource:Original {{id: rel.src_id}})
                        MATCH (tgt_orig:Resource:Original {{id: rel.tgt_id}})

                        // Create relationship between original nodes
                        MERGE (src_orig)-[r_orig:{rel_type}]->(tgt_orig)
                        SET r_orig += rel.properties

                        // Find abstracted nodes via indexed abstracted_id property
                        // This replaces the slow OPTIONAL MATCH traversal with fast index lookups
                        WITH src_orig, tgt_orig, rel
                        MATCH (src_abs:Resource {{original_id: src_orig.id}})
                        MATCH (tgt_abs:Resource {{original_id: tgt_orig.id}})

                        // Create relationship between abstracted nodes
                        MERGE (src_abs)-[r_abs:{rel_type}]->(tgt_abs)
                        SET r_abs += rel.properties

                        RETURN count(r_abs) as created
                        """

                        result = tx.run(query, relationships=relationships)
                        record = result.single()
                        if record:
                            created = record["created"]
                            total_created += created

                            # Calculate success rate
                            success_rate = (
                                (created / expected_count * 100)
                                if expected_count > 0
                                else 0
                            )

                            # Log with appropriate level based on success rate
                            if created < expected_count:
                                logger.warning(
                                    f"Batch created {created}/{expected_count} {rel_type} relationships ({success_rate:.1f}%)"
                                )

                    # Commit the transaction (all relationships created atomically)
                    tx.commit()

            # Clear buffer after successful flush
            buffer_size = len(self._relationship_buffer)
            self._relationship_buffer.clear()

            if total_created < total_expected:
                success_rate = (
                    (total_created / total_expected * 100) if total_expected > 0 else 0
                )
                logger.warning(
                    f"Flushed {buffer_size} relationships: {total_created}/{total_expected} ({success_rate:.1f}%)"
                )

            return total_created

        except Exception as e:
            logger.exception(f"Error flushing relationship buffer: {e}")
            # Don't clear buffer on error - allow retry
            return 0

    def auto_flush_if_needed(self, db_ops: Any) -> None:
        """
        Automatically flush buffer if it reaches the batch size threshold.

        This enables transparent batching without changing calling code.

        Args:
            db_ops: DatabaseOperations instance
        """
        if len(self._relationship_buffer) >= self._buffer_size:
            self.flush_relationship_buffer(db_ops)

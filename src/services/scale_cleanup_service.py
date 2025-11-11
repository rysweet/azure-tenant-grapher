"""
Scale Cleanup Service for Azure Tenant Grapher

This service provides cleanup operations for synthetic data created during
scale operations. It operates ONLY on the abstracted layer (:Resource nodes,
not :Original nodes).

Key Features:
- Clean all synthetic data from tenant
- Clean specific session synthetic data
- Clean synthetic data before date
- Preview cleanup (dry-run)
- Safe confirmation required
- Batch processing for large deletions

All operations respect the dual-graph architecture and never touch :Original nodes.
"""

import logging
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from neo4j.exceptions import Neo4jError, ClientError, DatabaseError

from src.services.base_scale_service import BaseScaleService
from src.utils.session_manager import Neo4jSessionManager

logger = logging.getLogger(__name__)


class ScaleCleanupService(BaseScaleService):
    """
    Service for cleaning up synthetic data created during scale operations.

    This service provides safe, controlled cleanup of synthetic resources
    with preview capabilities and batch processing for large-scale deletions.

    All operations:
    - Operate only on abstracted layer (:Resource nodes without :Original label)
    - Respect synthetic markers (synthetic=true)
    - Support progress callbacks for UI integration
    - Include dry-run preview capabilities
    """

    def __init__(
        self,
        session_manager: Neo4jSessionManager,
        batch_size: int = 1000,
    ) -> None:
        """
        Initialize the scale cleanup service.

        Args:
            session_manager: Neo4j session manager for database operations
            batch_size: Number of resources to process per batch (default: 1000)
        """
        super().__init__(session_manager)
        self.batch_size = batch_size

    async def preview_cleanup(
        self,
        tenant_id: str,
        clean_all: bool = False,
        session_id: Optional[str] = None,
        before_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Preview cleanup operation without deleting data (dry-run).

        This method analyzes what would be deleted without making any changes,
        providing counts and details for review before actual cleanup.

        Args:
            tenant_id: Azure tenant ID
            clean_all: If True, preview cleanup of ALL synthetic data
            session_id: Optional session/operation ID to preview
            before_date: Optional date to preview cleanup before
                        (deletes resources created before this date)

        Returns:
            Dict[str, Any]: Preview results including:
                - resources_to_delete: Number of resources that would be deleted
                - relationships_to_delete: Number of relationships that would be deleted
                - sessions_affected: List of session IDs that would be affected
                - resource_types: Breakdown by resource type
                - preview_only: Always True for this method

        Raises:
            ValueError: If tenant doesn't exist or parameters are invalid
            Exception: If preview query fails

        Example:
            >>> preview = await service.preview_cleanup(
            ...     tenant_id="abc123",
            ...     session_id="scale-20250110T123045-a1b2c3d4"
            ... )
            >>> print(f"Would delete {preview['resources_to_delete']} resources")
            >>> if input("Proceed? (y/n): ") == "y":
            ...     await service.cleanup_synthetic_data(
            ...         tenant_id="abc123",
            ...         session_id="scale-20250110T123045-a1b2c3d4"
            ...     )
        """
        self.logger.info(
            f"Previewing cleanup for tenant {tenant_id}: "
            f"clean_all={clean_all}, session_id={session_id}, "
            f"before_date={before_date}"
        )

        # Validate tenant exists
        if not await self.validate_tenant_exists(tenant_id):
            raise ValueError(f"Tenant {tenant_id} not found in database")

        # Validate parameters
        if not clean_all and not session_id and not before_date:
            raise ValueError(
                "Must specify either clean_all=True, session_id, or before_date"
            )

        # Build WHERE clause based on parameters
        where_clauses = [
            "NOT r:Original",
            "r.tenant_id = $tenant_id",
            "r.synthetic = true",
        ]
        params: Dict[str, Any] = {"tenant_id": tenant_id}

        if session_id:
            where_clauses.append("r.scale_operation_id = $session_id")
            params["session_id"] = session_id

        if before_date:
            where_clauses.append("r.generation_timestamp < $before_date")
            params["before_date"] = before_date.isoformat()

        where_clause = " AND ".join(where_clauses)

        # Query 1: Count resources to delete
        resource_query = f"""
        MATCH (r:Resource)
        WHERE {where_clause}
        RETURN count(r) as resource_count
        """

        # Query 2: Count relationships to delete
        relationship_query = f"""
        MATCH (r:Resource)
        WHERE {where_clause}
        MATCH (r)-[rel]->()
        RETURN count(rel) as outgoing_count

        UNION

        MATCH (r:Resource)
        WHERE {where_clause}
        MATCH ()-[rel]->(r)
        RETURN count(rel) as incoming_count
        """

        # Query 3: Get affected sessions
        session_query = f"""
        MATCH (r:Resource)
        WHERE {where_clause}
        RETURN DISTINCT r.scale_operation_id as session_id
        ORDER BY r.scale_operation_id
        """

        # Query 4: Resource type breakdown
        type_query = f"""
        MATCH (r:Resource)
        WHERE {where_clause}
        RETURN r.type as resource_type, count(r) as count
        ORDER BY count DESC
        """

        try:
            with self.session_manager.session() as session:
                # Execute queries
                result1 = session.run(resource_query, params)
                record1 = result1.single()
                resource_count = record1["resource_count"] if record1 else 0

                result2 = session.run(relationship_query, params)
                relationship_count = 0
                for record in result2:
                    if "outgoing_count" in record:
                        relationship_count += record["outgoing_count"] or 0
                    if "incoming_count" in record:
                        relationship_count += record["incoming_count"] or 0

                result3 = session.run(session_query, params)
                sessions_affected = [
                    record["session_id"] for record in result3 if record["session_id"]
                ]

                result4 = session.run(type_query, params)
                resource_types = {
                    record["resource_type"]: record["count"]
                    for record in result4
                    if record["resource_type"]
                }

            preview_result = {
                "preview_only": True,
                "tenant_id": tenant_id,
                "clean_all": clean_all,
                "session_id": session_id,
                "before_date": before_date.isoformat() if before_date else None,
                "resources_to_delete": resource_count,
                "relationships_to_delete": relationship_count,
                "sessions_affected": sessions_affected,
                "resource_types": resource_types,
            }

            self.logger.info(
                f"Preview complete: {resource_count} resources, "
                f"{relationship_count} relationships would be deleted"
            )

            return preview_result

        except (Neo4jError, ValueError) as e:
            self.logger.exception(f"Preview cleanup failed: {e}")
            raise
        except Exception as e:
            self.logger.exception(f"Unexpected error during preview cleanup: {e}")
            raise

    async def cleanup_synthetic_data(
        self,
        tenant_id: str,
        clean_all: bool = False,
        session_id: Optional[str] = None,
        before_date: Optional[datetime] = None,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
    ) -> Dict[str, Any]:
        """
        Clean up synthetic data from a tenant.

        This method deletes synthetic resources and their relationships based
        on the specified criteria. It processes deletions in batches for
        efficient handling of large datasets.

        Args:
            tenant_id: Azure tenant ID
            clean_all: If True, clean ALL synthetic data from tenant
            session_id: Optional session/operation ID to clean
            before_date: Optional date to clean data before
            progress_callback: Optional callback(message, current, total)

        Returns:
            Dict[str, Any]: Cleanup results including:
                - resources_deleted: Number of resources deleted
                - relationships_deleted: Number of relationships deleted
                - sessions_cleaned: List of session IDs cleaned
                - success: Whether operation succeeded
                - duration_seconds: Operation duration

        Raises:
            ValueError: If tenant doesn't exist or parameters are invalid
            Exception: If cleanup fails

        Example:
            >>> result = await service.cleanup_synthetic_data(
            ...     tenant_id="abc123",
            ...     session_id="scale-20250110T123045-a1b2c3d4"
            ... )
            >>> print(f"Deleted {result['resources_deleted']} resources")
        """
        start_time = datetime.now()

        self.logger.info(
            f"Starting cleanup for tenant {tenant_id}: "
            f"clean_all={clean_all}, session_id={session_id}, "
            f"before_date={before_date}"
        )

        # Validate tenant exists
        if not await self.validate_tenant_exists(tenant_id):
            raise ValueError(f"Tenant {tenant_id} not found in database")

        # Validate parameters
        if not clean_all and not session_id and not before_date:
            raise ValueError(
                "Must specify either clean_all=True, session_id, or before_date"
            )

        # Build WHERE clause based on parameters
        where_clauses = [
            "NOT r:Original",
            "r.tenant_id = $tenant_id",
            "r.synthetic = true",
        ]
        params: Dict[str, Any] = {"tenant_id": tenant_id}

        if session_id:
            where_clauses.append("r.scale_operation_id = $session_id")
            params["session_id"] = session_id

        if before_date:
            where_clauses.append("r.generation_timestamp < $before_date")
            params["before_date"] = before_date.isoformat()

        where_clause = " AND ".join(where_clauses)

        # First, get all affected session IDs for reporting
        session_query = f"""
        MATCH (r:Resource)
        WHERE {where_clause}
        RETURN DISTINCT r.scale_operation_id as session_id
        """

        sessions_cleaned: List[str] = []
        try:
            with self.session_manager.session() as session:
                result = session.run(session_query, params)
                sessions_cleaned = [
                    record["session_id"] for record in result if record["session_id"]
                ]
        except (Neo4jError, ValueError) as e:
            self.logger.exception(f"Failed to get session IDs: {e}")
        except Exception as e:
            self.logger.exception(f"Unexpected error getting session IDs: {e}")
            # Don't raise - continue with cleanup even if session ID retrieval fails

        # Delete synthetic resources in batches
        # DETACH DELETE removes all relationships automatically
        resources_deleted = 0
        relationships_deleted = 0

        if progress_callback:
            progress_callback("Deleting synthetic resources...", 0, 100)

        try:
            while True:
                # Delete batch and count relationships removed
                delete_query = f"""
                MATCH (r:Resource)
                WHERE {where_clause}
                WITH r LIMIT $batch_size
                OPTIONAL MATCH (r)-[rel_out]->()
                OPTIONAL MATCH ()-[rel_in]->(r)
                WITH r,
                     count(DISTINCT rel_out) as outgoing_count,
                     count(DISTINCT rel_in) as incoming_count
                DETACH DELETE r
                RETURN count(r) as deleted_count,
                       sum(outgoing_count) as outgoing_rels,
                       sum(incoming_rels) as incoming_rels
                """

                with self.session_manager.session() as session:
                    result = session.run(
                        delete_query, {**params, "batch_size": self.batch_size}
                    )
                    record = result.single()

                    if not record or record["deleted_count"] == 0:
                        break

                    batch_deleted = record["deleted_count"]
                    batch_rels = (record.get("outgoing_rels") or 0) + (
                        record.get("incoming_rels") or 0
                    )

                    resources_deleted += batch_deleted
                    relationships_deleted += batch_rels

                    self.logger.debug(
                        f"Deleted batch: {batch_deleted} resources, "
                        f"{batch_rels} relationships"
                    )

                    if progress_callback:
                        progress_callback(
                            f"Deleted {resources_deleted} resources...",
                            resources_deleted,
                            resources_deleted,
                        )

                    # Break if we deleted fewer than batch size (last batch)
                    if batch_deleted < self.batch_size:
                        break

            duration = (datetime.now() - start_time).total_seconds()

            result = {
                "success": True,
                "tenant_id": tenant_id,
                "clean_all": clean_all,
                "session_id": session_id,
                "before_date": before_date.isoformat() if before_date else None,
                "resources_deleted": resources_deleted,
                "relationships_deleted": relationships_deleted,
                "sessions_cleaned": sessions_cleaned,
                "duration_seconds": duration,
            }

            self.logger.info(
                f"Cleanup complete: Deleted {resources_deleted} resources "
                f"and {relationships_deleted} relationships in {duration:.2f}s"
            )

            if progress_callback:
                progress_callback("Cleanup complete!", 100, 100)

            return result

        except (Neo4jError, ValueError, RuntimeError) as e:
            duration = (datetime.now() - start_time).total_seconds()
            self.logger.exception(f"Cleanup failed: {e}")

            return {
                "success": False,
                "tenant_id": tenant_id,
                "clean_all": clean_all,
                "session_id": session_id,
                "before_date": before_date.isoformat() if before_date else None,
                "resources_deleted": resources_deleted,
                "relationships_deleted": relationships_deleted,
                "sessions_cleaned": sessions_cleaned,
                "duration_seconds": duration,
                "error_message": str(e),
            }
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            self.logger.exception(f"Unexpected error during cleanup: {e}")

            return {
                "success": False,
                "tenant_id": tenant_id,
                "clean_all": clean_all,
                "session_id": session_id,
                "before_date": before_date.isoformat() if before_date else None,
                "resources_deleted": resources_deleted,
                "relationships_deleted": relationships_deleted,
                "sessions_cleaned": sessions_cleaned,
                "duration_seconds": duration,
                "error_message": str(e),
            }

    async def get_cleanable_sessions(self, tenant_id: str) -> List[Dict[str, Any]]:
        """
        Get list of all cleanable sessions for a tenant.

        This method returns information about all scale operation sessions
        that have synthetic data available for cleanup.

        Args:
            tenant_id: Azure tenant ID

        Returns:
            List[Dict[str, Any]]: List of session information including:
                - session_id: Scale operation ID
                - resource_count: Number of resources in this session
                - generation_strategy: Strategy used (template/scenario/random)
                - generation_timestamp: When resources were created
                - resource_types: Set of resource types in this session

        Raises:
            ValueError: If tenant doesn't exist
            Exception: If query fails

        Example:
            >>> sessions = await service.get_cleanable_sessions("abc123")
            >>> for session in sessions:
            ...     print(f"Session {session['session_id']}: "
            ...           f"{session['resource_count']} resources")
        """
        self.logger.info(f"Getting cleanable sessions for tenant {tenant_id}")

        # Validate tenant exists
        if not await self.validate_tenant_exists(tenant_id):
            raise ValueError(f"Tenant {tenant_id} not found in database")

        query = """
        MATCH (r:Resource)
        WHERE NOT r:Original
          AND r.tenant_id = $tenant_id
          AND r.synthetic = true
          AND r.scale_operation_id IS NOT NULL
        WITH r.scale_operation_id as session_id,
             count(r) as resource_count,
             collect(DISTINCT r.type) as resource_types,
             collect(DISTINCT r.generation_strategy)[0] as generation_strategy,
             collect(DISTINCT r.generation_timestamp)[0] as generation_timestamp
        RETURN session_id, resource_count, resource_types,
               generation_strategy, generation_timestamp
        ORDER BY generation_timestamp DESC
        """

        try:
            sessions: List[Dict[str, Any]] = []

            with self.session_manager.session() as session:
                result = session.run(query, {"tenant_id": tenant_id})

                for record in result:
                    sessions.append(
                        {
                            "session_id": record["session_id"],
                            "resource_count": record["resource_count"],
                            "resource_types": list(record["resource_types"]),
                            "generation_strategy": record["generation_strategy"],
                            "generation_timestamp": record["generation_timestamp"],
                        }
                    )

            self.logger.info(f"Found {len(sessions)} cleanable sessions")

            return sessions

        except (Neo4jError, ValueError) as e:
            self.logger.exception(f"Failed to get cleanable sessions: {e}")
            raise
        except Exception as e:
            self.logger.exception(f"Unexpected error getting cleanable sessions: {e}")
            raise

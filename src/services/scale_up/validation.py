"""
Validation Module for Scale-Up Service

This module handles validation of scale-up operations including
pre-operation validation and post-operation integrity checks.

Responsibilities:
- Operation result validation
- Rollback operations
- Post-operation integrity checks
- Resource count verification
"""

import logging
from typing import Optional

from neo4j.exceptions import Neo4jError

from src.services.scale_validation import ScaleValidation
from src.utils.session_manager import Neo4jSessionManager

logger = logging.getLogger(__name__)


class ValidationService:
    """
    Handles validation for scale-up operations.

    This class provides methods for validating operation results and
    performing rollback operations when needed.
    """

    def __init__(
        self,
        session_manager: Neo4jSessionManager,
        validation_enabled: bool = True,
    ) -> None:
        """
        Initialize validation service.

        Args:
            session_manager: Neo4j session manager
            validation_enabled: Enable post-operation validation
        """
        self.session_manager = session_manager
        self.validation_enabled = validation_enabled
        self.logger = logger

    async def validate_operation(self, operation_id: str) -> bool:
        """
        Validate a scale operation.

        Runs comprehensive validation checks on the operation results
        including resource counts, relationship integrity, and property
        validation.

        Args:
            operation_id: Scale operation ID to validate

        Returns:
            True if all validations pass, False otherwise

        Example:
            >>> validator = ValidationService(session_manager)
            >>> is_valid = await validator.validate_operation("scale-20250110-abc123")
            >>> if not is_valid:
            ...     print("Validation failed!")
        """
        if not self.validation_enabled:
            self.logger.debug("Validation disabled, skipping")
            return True

        with self.session_manager.session() as session:
            is_valid, message = await ScaleValidation.validate_operation(
                session, operation_id
            )
            if not is_valid:
                self.logger.warning(f"Validation failed for {operation_id}: {message}")
            else:
                self.logger.info(f"Validation passed for {operation_id}")
            return is_valid

    async def rollback_operation(self, operation_id: str) -> int:
        """
        Rollback a scale operation by deleting all synthetic resources.

        This removes all resources and relationships created during the
        specified operation. Safe to call multiple times. Relationships
        are automatically deleted due to CASCADE.

        Args:
            operation_id: Scale operation ID to rollback

        Returns:
            int: Number of resources deleted

        Raises:
            Exception: If rollback fails

        Example:
            >>> validator = ValidationService(session_manager)
            >>> deleted_count = await validator.rollback_operation(
            ...     "scale-20250110T123045-a1b2c3d4"
            ... )
            >>> print(f"Rolled back {deleted_count} resources")
        """
        self.logger.info(f"Rolling back operation: {operation_id}")

        try:
            # Delete all synthetic resources for this operation
            # Relationships are automatically deleted due to CASCADE
            query = """
            MATCH (r:Resource)
            WHERE NOT r:Original
              AND r.scale_operation_id = $operation_id
              AND r.synthetic = true
            WITH r
            DETACH DELETE r
            RETURN count(r) as deleted_count
            """

            with self.session_manager.session() as session:
                result = session.run(query, {"operation_id": operation_id})
                record = result.single()
                deleted_count = record["deleted_count"] if record else 0

            self.logger.info(
                f"Rollback complete: deleted {deleted_count} synthetic resources"
            )
            return deleted_count

        except (Neo4jError, ValueError) as e:
            self.logger.exception(f"Rollback failed for operation {operation_id}: {e}")
            raise
        except Exception as e:
            self.logger.exception(f"Unexpected error during rollback for operation {operation_id}: {e}")
            raise

    async def get_operation_stats(self, operation_id: str) -> dict:
        """
        Get statistics for a scale operation.

        Args:
            operation_id: Scale operation ID

        Returns:
            Dictionary with operation statistics including:
            - resource_count: Number of synthetic resources created
            - relationship_count: Number of relationships created
            - resource_types: Distribution of resource types

        Example:
            >>> validator = ValidationService(session_manager)
            >>> stats = await validator.get_operation_stats("scale-20250110-abc123")
            >>> print(f"Created {stats['resource_count']} resources")
        """
        query = """
        MATCH (r:Resource)
        WHERE NOT r:Original
          AND r.scale_operation_id = $operation_id
          AND r.synthetic = true
        WITH r
        OPTIONAL MATCH (r)-[rel]->()
        WHERE rel.scale_operation_id = $operation_id
        RETURN count(DISTINCT r) as resource_count,
               count(DISTINCT rel) as relationship_count,
               collect(DISTINCT r.type) as resource_types
        """

        with self.session_manager.session() as session:
            result = session.run(query, {"operation_id": operation_id})
            record = result.single()

            if record:
                return {
                    "resource_count": record["resource_count"],
                    "relationship_count": record["relationship_count"],
                    "resource_types": record["resource_types"],
                }
            else:
                return {
                    "resource_count": 0,
                    "relationship_count": 0,
                    "resource_types": [],
                }

    async def check_operation_exists(self, operation_id: str) -> bool:
        """
        Check if a scale operation exists in the database.

        Args:
            operation_id: Scale operation ID to check

        Returns:
            True if operation exists, False otherwise
        """
        query = """
        MATCH (r:Resource)
        WHERE NOT r:Original
          AND r.scale_operation_id = $operation_id
          AND r.synthetic = true
        RETURN count(r) > 0 as exists
        """

        with self.session_manager.session() as session:
            result = session.run(query, {"operation_id": operation_id})
            record = result.single()
            return record["exists"] if record else False

    async def validate_resource_counts(
        self,
        operation_id: str,
        expected_resources: Optional[int] = None,
        expected_relationships: Optional[int] = None,
    ) -> bool:
        """
        Validate that expected resource and relationship counts match actual counts.

        Args:
            operation_id: Scale operation ID
            expected_resources: Expected number of resources (None to skip)
            expected_relationships: Expected number of relationships (None to skip)

        Returns:
            True if counts match expectations, False otherwise
        """
        stats = await self.get_operation_stats(operation_id)

        if expected_resources is not None:
            if stats["resource_count"] != expected_resources:
                self.logger.warning(
                    f"Resource count mismatch for {operation_id}: "
                    f"expected {expected_resources}, got {stats['resource_count']}"
                )
                return False

        if expected_relationships is not None:
            if stats["relationship_count"] != expected_relationships:
                self.logger.warning(
                    f"Relationship count mismatch for {operation_id}: "
                    f"expected {expected_relationships}, got {stats['relationship_count']}"
                )
                return False

        return True

    async def cleanup_orphaned_resources(self, tenant_id: str) -> int:
        """
        Clean up orphaned synthetic resources without valid operation IDs.

        This is a maintenance operation to clean up any synthetic resources
        that may have been left behind due to interrupted operations.

        Args:
            tenant_id: Azure tenant ID to clean up

        Returns:
            Number of orphaned resources deleted
        """
        self.logger.info(f"Cleaning up orphaned synthetic resources for tenant {tenant_id}")

        query = """
        MATCH (r:Resource)
        WHERE NOT r:Original
          AND r.synthetic = true
          AND (r.scale_operation_id IS NULL OR r.scale_operation_id = '')
          AND r.tenant_id = $tenant_id
        WITH r
        DETACH DELETE r
        RETURN count(r) as deleted_count
        """

        with self.session_manager.session() as session:
            result = session.run(query, {"tenant_id": tenant_id})
            record = result.single()
            deleted_count = record["deleted_count"] if record else 0

        if deleted_count > 0:
            self.logger.warning(
                f"Cleaned up {deleted_count} orphaned synthetic resources"
            )
        else:
            self.logger.info("No orphaned synthetic resources found")

        return deleted_count

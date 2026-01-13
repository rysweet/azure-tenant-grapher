"""
Base Scale Service for Azure Tenant Grapher

This service provides foundational functionality for scale operations that
affect ONLY the abstracted layer (:Resource nodes, not :Original nodes).

Scale operations generate synthetic resources marked with:
- synthetic: true
- scale_operation_id: unique operation identifier
- generation_strategy: how the resource was generated
- generation_timestamp: when the resource was created

Synthetic resources do NOT have SCAN_SOURCE_NODE relationships as they
do not correspond to real Azure resources.
"""

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from src.utils.session_manager import Neo4jSessionManager

logger = logging.getLogger(__name__)


class BaseScaleService:
    """
    Base class for scale operations.

    Provides common functionality for scale-up and scale-down operations,
    including tenant validation, resource counting, and session ID generation.
    """

    def __init__(self, session_manager: Neo4jSessionManager) -> None:
        """
        Initialize the base scale service.

        Args:
            session_manager: Neo4j session manager for database operations
        """
        self.session_manager = session_manager
        self.logger = logging.getLogger(__name__)

    async def validate_tenant_exists(self, tenant_id: str) -> bool:
        """
        Validate that a tenant exists in the database.

        Args:
            tenant_id: Azure tenant ID to validate

        Returns:
            bool: True if tenant exists, False otherwise

        Raises:
            Exception: If database query fails
        """
        query = """
        MATCH (t:Tenant {id: $tenant_id})
        RETURN count(t) > 0 as exists
        """

        try:
            with self.session_manager.session() as session:
                result = session.run(query, {"tenant_id": tenant_id})
                record = result.single()
                exists = record["exists"] if record else False

                if exists:
                    self.logger.info(str(f"Tenant {tenant_id} validated successfully"))
                else:
                    self.logger.warning(
                        str(f"Tenant {tenant_id} not found in database")
                    )

                return exists

        except Exception as e:
            self.logger.exception(f"Failed to validate tenant {tenant_id}: {e}")
            raise

    async def count_resources(
        self, tenant_id: str, synthetic_only: bool = False
    ) -> int:
        """
        Count resources in a tenant.

        Args:
            tenant_id: Azure tenant ID
            synthetic_only: If True, count only synthetic resources

        Returns:
            int: Number of resources matching the criteria

        Raises:
            Exception: If database query fails
        """
        # Query abstracted layer only (no :Original label)
        if synthetic_only:
            query = """
            MATCH (r:Resource)
            WHERE NOT r:Original
              AND r.tenant_id = $tenant_id
              AND r.synthetic = true
            RETURN count(r) as count
            """
        else:
            query = """
            MATCH (r:Resource)
            WHERE NOT r:Original
              AND r.tenant_id = $tenant_id
            RETURN count(r) as count
            """

        try:
            with self.session_manager.session() as session:
                result = session.run(query, {"tenant_id": tenant_id})
                record = result.single()
                count = record["count"] if record else 0

                resource_type = "synthetic resources" if synthetic_only else "resources"
                self.logger.debug(
                    f"Counted {count} {resource_type} for tenant {tenant_id}"
                )

                return count

        except Exception as e:
            self.logger.exception(
                f"Failed to count resources for tenant {tenant_id}: {e}"
            )
            raise

    async def generate_session_id(self) -> str:
        """
        Generate a unique session ID for tracking scale operations.

        The session ID is used as the scale_operation_id for all resources
        created during a scale operation, enabling easy filtering and cleanup.

        Returns:
            str: Unique session ID in format "scale-{timestamp}-{uuid}"

        Example:
            >>> service = BaseScaleService(session_manager)
            >>> session_id = await service.generate_session_id()
            >>> print(session_id)
            scale-20250110T123045-a1b2c3d4
        """
        timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
        unique_id = str(uuid.uuid4()).replace("-", "")[:8]
        session_id = f"scale-{timestamp}-{unique_id}"

        self.logger.debug(str(f"Generated session ID: {session_id}"))
        return session_id

    async def get_tenant_info(self, tenant_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve tenant information from the database.

        Args:
            tenant_id: Azure tenant ID

        Returns:
            Optional[Dict[str, Any]]: Tenant properties or None if not found

        Raises:
            Exception: If database query fails
        """
        query = """
        MATCH (t:Tenant {id: $tenant_id})
        RETURN t
        """

        try:
            with self.session_manager.session() as session:
                result = session.run(query, {"tenant_id": tenant_id})
                record = result.single()

                if record:
                    tenant_node = record["t"]
                    tenant_info = dict(tenant_node.items())
                    self.logger.debug(
                        f"Retrieved tenant info for {tenant_id}: {tenant_info.keys()}"
                    )
                    return tenant_info
                else:
                    self.logger.warning(str(f"No tenant info found for {tenant_id}"))
                    return None

        except Exception as e:
            self.logger.exception(f"Failed to get tenant info for {tenant_id}: {e}")
            raise

    async def count_relationships(
        self, tenant_id: str, synthetic_only: bool = False
    ) -> int:
        """
        Count relationships involving resources in a tenant.

        Args:
            tenant_id: Azure tenant ID
            synthetic_only: If True, count only relationships involving synthetic resources

        Returns:
            int: Number of relationships matching the criteria

        Raises:
            Exception: If database query fails
        """
        if synthetic_only:
            # Count relationships where either source or target is synthetic
            query = """
            MATCH (r1:Resource)-[rel]->(r2:Resource)
            WHERE NOT r1:Original AND NOT r2:Original
              AND (r1.tenant_id = $tenant_id OR r2.tenant_id = $tenant_id)
              AND (r1.synthetic = true OR r2.synthetic = true)
            RETURN count(rel) as count
            """
        else:
            # Count all relationships involving resources in the tenant
            query = """
            MATCH (r1:Resource)-[rel]->(r2:Resource)
            WHERE NOT r1:Original AND NOT r2:Original
              AND (r1.tenant_id = $tenant_id OR r2.tenant_id = $tenant_id)
            RETURN count(rel) as count
            """

        try:
            with self.session_manager.session() as session:
                result = session.run(query, {"tenant_id": tenant_id})
                record = result.single()
                count = record["count"] if record else 0

                relationship_type = (
                    "synthetic relationships" if synthetic_only else "relationships"
                )
                self.logger.debug(
                    f"Counted {count} {relationship_type} for tenant {tenant_id}"
                )

                return count

        except Exception as e:
            self.logger.exception(
                f"Failed to count relationships for tenant {tenant_id}: {e}"
            )
            raise

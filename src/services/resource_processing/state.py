"""
Resource State Module

This module manages the state of resource processing.
"""

from typing import Any, Dict

import structlog

logger = structlog.get_logger(__name__)


class ResourceState:
    """Manages the state of resource processing."""

    def __init__(self, session_manager: Any) -> None:
        """
        Initialize ResourceState.

        Args:
            session_manager: Neo4jSessionManager instance
        """
        self.session_manager = session_manager

    def resource_exists(self, resource_id: str) -> bool:
        """
        Check if a resource already exists in the database.

        Args:
            resource_id: Resource ID to check

        Returns:
            bool: True if resource exists, False otherwise
        """
        try:
            with self.session_manager.session() as session:
                result = session.run(
                    "MATCH (r:Resource {id: $id}) RETURN count(r) as count",
                    id=resource_id,
                )
                record = result.single()
                return bool(record["count"] > 0) if record else False
        except Exception:
            logger.exception(f"Error checking resource existence for {resource_id}")
            return False

    def has_llm_description(self, resource_id: str) -> bool:
        """
        Check if a resource already has an LLM description.

        Args:
            resource_id: Resource ID to check

        Returns:
            bool: True if resource has valid LLM description, False otherwise
        """
        try:
            with self.session_manager.session() as session:
                result = session.run(
                    """
                    MATCH (r:Resource {id: $id})
                    RETURN r.llm_description as desc
                """,
                    id=resource_id,
                )
                record = result.single()
                if record:
                    desc = record["desc"]
                    return (
                        desc is not None
                        and desc.strip() != ""
                        and not desc.startswith("Azure ")
                    )
                return False
        except Exception:
            logger.exception(f"Error checking LLM description for {resource_id}")
            return False

    def get_processing_metadata(self, resource_id: str) -> Dict[str, Any]:
        """
        Get processing metadata for a resource.

        Args:
            resource_id: Resource ID to check

        Returns:
            dict: Processing metadata (updated_at, llm_description, processing_status)
        """
        try:
            with self.session_manager.session() as session:
                result = session.run(
                    """
                    MATCH (r:Resource {id: $id})
                    RETURN r.updated_at as updated_at,
                           r.llm_description as llm_description,
                           r.processing_status as processing_status
                """,
                    id=resource_id,
                )
                record = result.single()
                if record:
                    return dict(record)
                return {}
        except Exception:
            logger.exception(f"Error getting processing metadata for {resource_id}")
            return {}

"""
LLM Integration Module

This module handles LLM description generation for resources and groups.
"""

from typing import Any, Dict, List, Optional, Tuple

import structlog  # type: ignore[import-untyped]

from src.llm_descriptions import (
    AzureLLMDescriptionGenerator,
    should_generate_description,
)

from .relationship_emitter import run_neo4j_query_with_retry

logger = structlog.get_logger(__name__)


class LLMIntegration:
    """Handles LLM description generation for resources and groups."""

    def __init__(
        self,
        llm_generator: Optional[AzureLLMDescriptionGenerator],
        session_manager: Any,
        state_checker: Any = None,
    ) -> None:
        """
        Initialize the LLMIntegration.

        Args:
            llm_generator: Optional LLM description generator
            session_manager: Neo4jSessionManager instance
            state_checker: Optional ResourceState for checking existing descriptions
        """
        self.llm_generator = llm_generator
        self.session_manager = session_manager
        self._state_checker = state_checker

    def should_skip_llm(self, resource: Dict[str, Any]) -> bool:
        """
        Check if LLM generation should be skipped for this resource.

        Args:
            resource: Resource dictionary

        Returns:
            bool: True if LLM should be skipped, False otherwise
        """
        if not self.llm_generator:
            return True

        with self.session_manager.session() as session:
            return not should_generate_description(resource, session)

    async def generate_resource_description(
        self, resource: Dict[str, Any]
    ) -> Tuple[bool, str]:
        """
        Generate LLM description for a single resource, with skip logic.

        Args:
            resource: Resource dictionary

        Returns:
            Tuple of (success, description)
        """
        if not self.llm_generator:
            return False, f"Azure {resource.get('type', 'Resource')} resource."

        # Check if we should skip
        resource_id = resource.get("id")
        with self.session_manager.session() as session:
            if not should_generate_description(resource, session):
                # Fetch existing description from DB
                desc = None
                if resource_id and self._state_checker:
                    metadata = self._state_checker.get_processing_metadata(resource_id)
                    desc = metadata.get("llm_description")
                if desc:
                    logger.info(
                        f"Skipping LLM for {resource_id}: using cached description."
                    )
                    return False, desc
                else:
                    logger.info(
                        f"Skipping LLM for {resource_id}: no cached description, using fallback."
                    )
                    return False, f"Azure {resource.get('type', 'Resource')} resource."

        try:
            description = await self.llm_generator.generate_resource_description(
                resource
            )
            return True, description
        except Exception:
            logger.exception(
                f"LLM generation failed for {resource.get('name', 'Unknown')}"
            )
            return False, f"Azure {resource.get('type', 'Resource')} resource."

    async def generate_resource_group_summaries(self) -> None:
        """Generate LLM summaries for all ResourceGroups that don't have descriptions yet."""
        if not self.llm_generator:
            logger.info(
                "No LLM generator available, skipping ResourceGroup summary generation"
            )
            return

        logger.info("Starting ResourceGroup LLM summary generation...")

        try:
            # Get all ResourceGroups that need descriptions
            rg_query = """
            MATCH (rg:ResourceGroup)
            WHERE rg.llm_description IS NULL OR rg.llm_description = '' OR rg.llm_description STARTS WITH 'Azure'
            RETURN rg.name AS name, rg.subscription_id AS subscription_id
            """

            resource_groups: List[Dict[str, Any]] = []
            with self.session_manager.session() as session:
                result = run_neo4j_query_with_retry(session, rg_query)
                for record in result:
                    resource_groups.append(
                        {
                            "name": record["name"],
                            "subscription_id": record["subscription_id"],
                        }
                    )

            logger.info(
                f"Found {len(resource_groups)} ResourceGroups that need LLM descriptions"
            )

            for rg in resource_groups:
                try:
                    # Get all resources in this ResourceGroup
                    resources_query = """
                    MATCH (rg:ResourceGroup {name: $rg_name, subscription_id: $subscription_id})-[:CONTAINS]->(r:Resource)
                    RETURN r.name AS name, r.type AS type, r.location AS location, r.id AS id
                    """

                    resources: List[Dict[str, Any]] = []
                    with self.session_manager.session() as session:
                        result = run_neo4j_query_with_retry(
                            session,
                            resources_query,
                            rg_name=rg["name"],
                            subscription_id=rg["subscription_id"],
                        )
                        for record in result:
                            resources.append(
                                {
                                    "name": record["name"],
                                    "type": record["type"],
                                    "location": record["location"],
                                    "id": record["id"],
                                }
                            )

                    if not resources:
                        logger.debug(
                            f"No resources found for ResourceGroup {rg['name']}, skipping"
                        )
                        continue

                    # Generate LLM description
                    description = (
                        await self.llm_generator.generate_resource_group_description(
                            rg["name"], rg["subscription_id"], resources
                        )
                    )

                    # Update ResourceGroup with LLM description
                    update_query = """
                    MATCH (rg:ResourceGroup {name: $rg_name, subscription_id: $subscription_id})
                    SET rg.llm_description = $description, rg.updated_at = datetime()
                    """

                    with self.session_manager.session() as session:
                        run_neo4j_query_with_retry(
                            session,
                            update_query,
                            rg_name=rg["name"],
                            subscription_id=rg["subscription_id"],
                            description=description,
                        )

                    logger.info(
                        f"Generated LLM description for ResourceGroup '{rg['name']}'"
                    )

                except Exception as e:
                    logger.exception(
                        f"Failed to generate LLM description for ResourceGroup '{rg['name']}': {e}"
                    )
                    continue

        except Exception as e:
            logger.exception(f"Error during ResourceGroup summary generation: {e}")

    async def generate_tag_summaries(self) -> None:
        """Generate LLM summaries for all Tags that don't have descriptions yet."""
        if not self.llm_generator:
            logger.info("No LLM generator available, skipping Tag summary generation")
            return

        logger.info("Starting Tag LLM summary generation...")

        try:
            # Get all Tags that need descriptions
            tag_query = """
            MATCH (t:Tag)
            WHERE t.llm_description IS NULL OR t.llm_description = '' OR t.llm_description STARTS WITH 'Azure'
            RETURN t.id AS id, t.key AS key, t.value AS value
            """

            tags: List[Dict[str, Any]] = []
            with self.session_manager.session() as session:
                result = run_neo4j_query_with_retry(session, tag_query)
                for record in result:
                    tags.append(
                        {
                            "id": record["id"],
                            "key": record["key"],
                            "value": record["value"],
                        }
                    )

            logger.info(str(f"Found {len(tags)} Tags that need LLM descriptions"))

            for tag in tags:
                try:
                    # Get all resources that have this tag
                    tagged_resources_query = """
                    MATCH (r:Resource)-[:TAGGED_WITH]->(t:Tag {id: $tag_id})
                    RETURN r.name AS name, r.type AS type, r.location AS location, r.resource_group AS resource_group
                    """

                    tagged_resources: List[Dict[str, Any]] = []
                    with self.session_manager.session() as session:
                        result = run_neo4j_query_with_retry(
                            session, tagged_resources_query, tag_id=tag["id"]
                        )
                        for record in result:
                            tagged_resources.append(
                                {
                                    "name": record["name"],
                                    "type": record["type"],
                                    "location": record["location"],
                                    "resource_group": record["resource_group"],
                                }
                            )

                    if not tagged_resources:
                        logger.debug(
                            f"No resources found for Tag {tag['key']}:{tag['value']}, skipping"
                        )
                        continue

                    # Generate LLM description
                    description = await self.llm_generator.generate_tag_description(
                        tag["key"], tag["value"], tagged_resources
                    )

                    # Update Tag with LLM description
                    update_query = """
                    MATCH (t:Tag {id: $tag_id})
                    SET t.llm_description = $description, t.updated_at = datetime()
                    """

                    with self.session_manager.session() as session:
                        run_neo4j_query_with_retry(
                            session,
                            update_query,
                            tag_id=tag["id"],
                            description=description,
                        )

                    logger.info(
                        f"Generated LLM description for Tag '{tag['key']}:{tag['value']}'"
                    )

                except Exception as e:
                    logger.exception(
                        f"Failed to generate LLM description for Tag '{tag['key']}:{tag['value']}': {e}"
                    )
                    continue

        except Exception as e:
            logger.exception(f"Error during Tag summary generation: {e}")

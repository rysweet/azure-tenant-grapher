"""
Azure Resource Processor

This module provides robust, resumable, and parallel processing of Azure resources
with improved error handling, progress tracking, and database operations.
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from .llm_descriptions import AzureLLMDescriptionGenerator

logger = logging.getLogger(__name__)


@dataclass
class ProcessingStats:
    """Statistics for resource processing operations."""

    total_resources: int = 0
    processed: int = 0
    successful: int = 0
    failed: int = 0
    skipped: int = 0
    llm_generated: int = 0
    llm_skipped: int = 0

    @property
    def success_rate(self) -> float:
        """Calculate success rate as a percentage."""
        return (self.successful / max(self.processed, 1)) * 100

    @property
    def progress_percentage(self) -> float:
        """Calculate overall progress as a percentage."""
        return (self.processed / max(self.total_resources, 1)) * 100

    def to_dict(self) -> Dict[str, Any]:
        """Convert stats to dictionary."""
        return {
            "total_resources": self.total_resources,
            "processed": self.processed,
            "successful": self.successful,
            "failed": self.failed,
            "skipped": self.skipped,
            "llm_generated": self.llm_generated,
            "llm_skipped": self.llm_skipped,
            "success_rate": round(self.success_rate, 2),
            "progress_percentage": round(self.progress_percentage, 2),
        }


class ResourceState:
    """Manages the state of resource processing."""

    def __init__(self, session: Any) -> None:
        self.session = session

    def resource_exists(self, resource_id: str) -> bool:
        """Check if a resource already exists in the database."""
        try:
            result = self.session.run(
                "MATCH (r:Resource {id: $id}) RETURN count(r) as count", id=resource_id
            )
            record = result.single()
            return bool(record["count"] > 0) if record else False
        except Exception as e:
            logger.error(f"Error checking resource existence for {resource_id}: {e}")
            return False

    def has_llm_description(self, resource_id: str) -> bool:
        """Check if a resource already has an LLM description."""
        try:
            result = self.session.run(
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
        except Exception as e:
            logger.error(f"Error checking LLM description for {resource_id}: {e}")
            return False

    def get_processing_metadata(self, resource_id: str) -> Dict[str, Any]:
        """Get processing metadata for a resource."""
        try:
            result = self.session.run(
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
        except Exception as e:
            logger.error(f"Error getting processing metadata for {resource_id}: {e}")
            return {}


class DatabaseOperations:
    """Handles all database operations for resources."""

    def __init__(self, session: Any) -> None:
        self.session = session

    def upsert_resource(
        self, resource: Dict[str, Any], processing_status: str = "completed"
    ) -> bool:
        """
        Create or update a resource node in Neo4j with enhanced metadata.

        Args:
            resource: Resource dictionary
            processing_status: Status of processing (pending, processing, completed, failed)

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            query = """
            MERGE (r:Resource {id: $id})
            SET r.name = $name,
                r.type = $type,
                r.location = $location,
                r.resource_group = $resource_group,
                r.subscription_id = $subscription_id,
                r.tags = $tags,
                r.kind = $kind,
                r.sku = $sku,
                r.updated_at = datetime(),
                r.processing_status = $processing_status,
                r.llm_description = CASE
                    WHEN $llm_description IS NOT NULL AND $llm_description <> ''
                    THEN $llm_description
                    ELSE COALESCE(r.llm_description, '')
                END
            """

            resource_data = resource.copy()
            resource_data["llm_description"] = resource.get("llm_description", "")
            resource_data["processing_status"] = processing_status

            self.session.run(query, resource_data)
            return True

        except Exception as e:
            logger.error(
                f"Error upserting resource {resource.get('id', 'Unknown')}: {e}"
            )
            return False

    def create_subscription_relationship(
        self, subscription_id: str, resource_id: str
    ) -> bool:
        """Create relationship between subscription and resource."""
        try:
            query = """
            MATCH (s:Subscription {id: $subscription_id})
            MATCH (r:Resource {id: $resource_id})
            MERGE (s)-[:CONTAINS]->(r)
            """
            self.session.run(
                query, subscription_id=subscription_id, resource_id=resource_id
            )
            return True
        except Exception as e:
            logger.error(
                f"Error creating subscription relationship for {resource_id}: {e}"
            )
            return False

    def create_resource_group_relationships(self, resource: Dict[str, Any]) -> bool:
        """Create resource group nodes and relationships."""
        try:
            if not resource.get("resource_group"):
                return True

            rg_name = resource["resource_group"]
            subscription_id = resource["subscription_id"]
            resource_id = resource["id"]

            # Create resource group node if it doesn't exist
            rg_query = """
            MERGE (rg:ResourceGroup {name: $rg_name, subscription_id: $subscription_id})
            SET rg.type = 'ResourceGroup',
                rg.updated_at = datetime()
            """
            self.session.run(rg_query, rg_name=rg_name, subscription_id=subscription_id)

            # Create relationship: Subscription CONTAINS ResourceGroup
            sub_rg_query = """
            MATCH (s:Subscription {id: $subscription_id})
            MATCH (rg:ResourceGroup {name: $rg_name, subscription_id: $subscription_id})
            MERGE (s)-[:CONTAINS]->(rg)
            """
            self.session.run(
                sub_rg_query, subscription_id=subscription_id, rg_name=rg_name
            )

            # Create relationship: ResourceGroup CONTAINS Resource
            rg_resource_query = """
            MATCH (rg:ResourceGroup {name: $rg_name, subscription_id: $subscription_id})
            MATCH (r:Resource {id: $resource_id})
            MERGE (rg)-[:CONTAINS]->(r)
            """
            self.session.run(
                rg_resource_query,
                rg_name=rg_name,
                subscription_id=subscription_id,
                resource_id=resource_id,
            )

            return True

        except Exception as e:
            logger.error(
                f"Error creating resource group relationships for {resource.get('id', 'Unknown')}: {e}"
            )
            return False


class ResourceProcessor:
    """
    Enhanced resource processor with improved error handling, progress tracking,
    and resumable operations.
    """

    def __init__(
        self,
        session: Any,
        llm_generator: Optional[AzureLLMDescriptionGenerator] = None,
        resource_limit: Optional[int] = None,
    ):
        """
        Initialize the resource processor.

        Args:
            session: Neo4j database session
            llm_generator: Optional LLM description generator
            resource_limit: Optional limit on number of resources to process
        """
        self.session = session
        self.llm_generator = llm_generator
        self.resource_limit = resource_limit

        # Initialize helper classes
        self.state = ResourceState(session)
        self.db_ops = DatabaseOperations(session)

        # Processing statistics
        self.stats = ProcessingStats()

        logger.info(
            f"Initialized ResourceProcessor with LLM: {'enabled' if llm_generator else 'disabled'}"
        )

    def _should_process_resource(self, resource: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Determine if a resource should be processed based on its current state.

        Args:
            resource: Resource dictionary

        Returns:
            Tuple of (should_process, reason)
        """
        resource_id = resource["id"]

        # Check if resource exists
        exists = self.state.resource_exists(resource_id)
        if not exists:
            return True, "new_resource"

        # Check if needs LLM description
        if self.llm_generator and not self.state.has_llm_description(resource_id):
            return True, "needs_llm_description"

        # Get processing metadata to check for failed processing
        metadata = self.state.get_processing_metadata(resource_id)
        processing_status = metadata.get("processing_status", "unknown")

        if processing_status == "failed":
            return True, "retry_failed"

        return False, "already_processed"

    async def _process_single_resource_llm(
        self, resource: Dict[str, Any]
    ) -> Tuple[bool, str]:
        """
        Generate LLM description for a single resource.

        Args:
            resource: Resource dictionary

        Returns:
            Tuple of (success, description)
        """
        if not self.llm_generator:
            return False, f"Azure {resource.get('type', 'Resource')} resource."

        try:
            description = await self.llm_generator.generate_resource_description(
                resource
            )
            return True, description
        except Exception as e:
            logger.error(
                f"LLM generation failed for {resource.get('name', 'Unknown')}: {e!s}"
            )
            return False, f"Azure {resource.get('type', 'Resource')} resource."

    async def process_single_resource(
        self, resource: Dict[str, Any], resource_index: int
    ) -> bool:
        """
        Process a single resource with comprehensive error handling and state management.

        Args:
            resource: Resource dictionary
            resource_index: Index of resource being processed

        Returns:
            bool: True if successful, False if failed
        """
        resource_id = resource["id"]
        resource_name = resource.get("name", "Unknown")
        resource_type = resource.get("type", "Unknown")

        try:
            # Mark resource as being processed
            self.db_ops.upsert_resource(resource, processing_status="processing")

            # Determine if resource should be processed
            should_process, reason = self._should_process_resource(resource)

            if not should_process:
                logger.info(
                    f"⏭️  Resource {resource_index + 1}/{self.stats.total_resources}: {resource_name} - SKIPPED ({reason})"
                )
                self.stats.skipped += 1
                return True

            logger.info(
                f"📝 Processing resource {resource_index + 1}/{self.stats.total_resources}: {resource_name} ({resource_type}) - {reason}"
            )

            # Generate LLM description if needed
            llm_success = False
            if reason in ["new_resource", "needs_llm_description", "retry_failed"]:
                logger.info(f"🤖 Generating LLM description for {resource_name}")
                llm_success, description = await self._process_single_resource_llm(
                    resource
                )
                resource["llm_description"] = description

                if llm_success:
                    self.stats.llm_generated += 1
                    desc_preview = (
                        description[:100] + "..."
                        if len(description) > 100
                        else description
                    )
                    logger.info(f'✅ Generated description: "{desc_preview}"')
                else:
                    self.stats.llm_skipped += 1
                    logger.warning(f"⚠️  Using fallback description for {resource_name}")

            # Upsert resource to database
            success = self.db_ops.upsert_resource(
                resource, processing_status="completed"
            )
            if not success:
                raise Exception("Failed to upsert resource")

            # Create relationships
            self.db_ops.create_subscription_relationship(
                resource["subscription_id"], resource_id
            )
            self.db_ops.create_resource_group_relationships(resource)

            logger.info(f"✅ Successfully processed {resource_name}")
            self.stats.successful += 1
            return True

        except Exception as e:
            logger.error(
                f"❌ Failed to process resource {resource_name} ({resource_type}): {e!s}"
            )

            # Mark resource as failed in database

            try:
                self.db_ops.upsert_resource(resource, processing_status="failed")
            except Exception as db_exc:
                logger.error(f"Failed to mark resource as failed in DB: {db_exc!s}")

            self.stats.failed += 1
            return False

        finally:
            self.stats.processed += 1

    async def process_resources_batch(
        self, resources: List[Dict[str, Any]], batch_size: int = 5
    ) -> ProcessingStats:
        """
        Process resources in parallel batches with comprehensive progress tracking.

        Args:
            resources: List[Any] of resources to process
            batch_size: Number of resources to process in parallel

        Returns:
            ProcessingStats: Final processing statistics
        """
        # Apply resource limit if specified
        if self.resource_limit and len(resources) > self.resource_limit:
            logger.info(
                f"🔢 Limiting processing to {self.resource_limit} resources (found {len(resources)})"
            )
            resources = resources[: self.resource_limit]

        self.stats.total_resources = len(resources)

        if not resources:
            logger.info("INFO: No resources to process")
            return self.stats

        logger.info(
            f"🔄 Starting parallel batch processing of {self.stats.total_resources} resources (batch size: {batch_size})"
        )

        for batch_start in range(0, self.stats.total_resources, batch_size):
            batch_end = min(batch_start + batch_size, self.stats.total_resources)
            batch = resources[batch_start:batch_end]
            batch_number = (batch_start // batch_size) + 1
            total_batches = (self.stats.total_resources + batch_size - 1) // batch_size

            logger.info(
                f"🔄 Processing batch {batch_number}/{total_batches} (resources {batch_start + 1}-{batch_end})"
            )

            # Process batch in parallel with error isolation
            batch_tasks = []
            for idx, resource in enumerate(batch):
                resource_index = batch_start + idx
                task = self.process_single_resource(resource, resource_index)
                batch_tasks.append(task)

            # Wait for all tasks in batch to complete
            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)

            # Handle any exceptions that occurred
            for idx, result in enumerate(batch_results):
                if isinstance(result, Exception):
                    resource = batch[idx]
                    logger.error(
                        f"❌ Batch processing exception for {resource.get('name', 'Unknown')}: {result}"
                    )
                    self.stats.failed += 1
                    self.stats.processed += 1

            # Progress summary for this batch
            self._log_progress_summary(batch_number, total_batches)

            # Rate limiting between batches
            if batch_end < self.stats.total_resources:
                logger.debug("⏳ Waiting 1 second before next batch...")
                await asyncio.sleep(1)

        # Final summary
        self._log_final_summary()
        return self.stats

    def _log_progress_summary(self, batch_number: int, total_batches: int) -> None:
        """Log progress summary for the current batch."""
        logger.info(
            f"📊 Batch {batch_number}/{total_batches} complete. Progress: {self.stats.processed}/{self.stats.total_resources} ({self.stats.progress_percentage:.1f}%)"
        )
        logger.info(
            f"   ✅ Success: {self.stats.successful} | ❌ Failed: {self.stats.failed} | ⏭️  Skipped: {self.stats.skipped}"
        )
        if self.llm_generator:
            logger.info(
                f"   🤖 LLM Generated: {self.stats.llm_generated} | ⚠️  LLM Skipped: {self.stats.llm_skipped}"
            )

    def _log_final_summary(self) -> None:
        """Log final processing summary."""
        logger.info("=" * 60)
        logger.info("🎯 FINAL PROCESSING SUMMARY")
        logger.info("=" * 60)
        logger.info(f"📊 Total Resources: {self.stats.total_resources}")
        logger.info(
            f"✅ Successful: {self.stats.successful} ({self.stats.success_rate:.1f}%)"
        )
        logger.info(f"❌ Failed: {self.stats.failed}")
        logger.info(f"⏭️  Skipped: {self.stats.skipped}")
        if self.llm_generator:
            logger.info(f"🤖 LLM Descriptions Generated: {self.stats.llm_generated}")
            logger.info(f"⚠️  LLM Descriptions Skipped: {self.stats.llm_skipped}")
        logger.info("=" * 60)


def create_resource_processor(
    session: Any,
    llm_generator: Optional[AzureLLMDescriptionGenerator] = None,
    resource_limit: Optional[int] = None,
) -> ResourceProcessor:
    """
    Factory function to create a ResourceProcessor instance.

    Args:
        session: Neo4j database session
        llm_generator: Optional LLM description generator
        resource_limit: Optional limit on number of resources to process

    Returns:
        ResourceProcessor: Configured resource processor instance
    """
    return ResourceProcessor(session, llm_generator, resource_limit)

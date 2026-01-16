"""
Resource Processor Module

This module provides the main orchestrator for Azure resource processing
with improved error handling, progress tracking, and resumable operations.
Uses dual-graph architecture for all resources.
"""

import threading
from typing import Any, Dict, List, Optional, Tuple

import structlog  # type: ignore[import-untyped]

from src.llm_descriptions import AzureLLMDescriptionGenerator

from .llm_integration import LLMIntegration
from .node_manager import NodeManager
from .relationship_emitter import RelationshipEmitter
from .state import ResourceState
from .stats import ProcessingStats
from .validation import extract_identity_fields

logger = structlog.get_logger(__name__)


class ResourceProcessor:
    """
    Enhanced resource processor with improved error handling, progress tracking,
    and resumable operations. Uses dual-graph architecture for all resources.
    """

    def __init__(
        self,
        session_manager: Any,
        llm_generator: Optional[AzureLLMDescriptionGenerator] = None,
        resource_limit: Optional[int] = None,
        max_retries: int = 3,
        tenant_id: Optional[str] = None,
    ):
        """
        Initialize the resource processor.

        Args:
            session_manager: Neo4jSessionManager
            llm_generator: Optional LLM description generator
            resource_limit: Optional limit on number of resources to process
            max_retries: Maximum number of retries for failed resources
            tenant_id: Tenant ID for dual-graph architecture (required)
        """
        self.session_manager = session_manager
        self.llm_generator = llm_generator
        self.resource_limit = resource_limit
        self.max_retries = max_retries
        self.tenant_id = tenant_id

        # Initialize helper classes
        self.state = ResourceState(session_manager)
        self.db_ops = NodeManager(
            session_manager,
            tenant_id=tenant_id,
        )
        self._relationship_emitter = RelationshipEmitter(
            session_manager, node_manager=self.db_ops
        )
        self._llm_integration = LLMIntegration(
            llm_generator, session_manager, state_checker=self.state
        )

        # Processing statistics
        self.stats = ProcessingStats()

        # Thread-safe seen guard (Phase 1 efficiency improvement)
        self._seen_ids: set[str] = set()
        self._seen_lock = threading.Lock()

        logger.info(
            f"Initialized ResourceProcessor with LLM: {'enabled' if llm_generator else 'disabled'}, "
            f"max_retries: {max_retries}, dual-graph: enabled"
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
        Generate LLM description for a single resource, with skip logic.

        Args:
            resource: Resource dictionary

        Returns:
            Tuple of (success, description)
        """
        return await self._llm_integration.generate_resource_description(resource)

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
        # Extract identity and principalId fields if present
        extract_identity_fields(resource)

        resource_id = resource["id"]
        resource_name = resource.get("name", "Unknown")
        resource_type = resource.get("type", "Unknown")

        # Thread-safe seen guard (Phase 1 efficiency improvement)
        with self._seen_lock:
            if resource_id in self._seen_ids:
                logger.info(
                    f"Resource {resource_index + 1}/{self.stats.total_resources}: {resource_name} - SKIPPED (intra-run duplicate)"
                )
                self.stats.skipped += 1
                return True
            self._seen_ids.add(resource_id)

        try:
            # Mark resource as being processed
            self.db_ops.upsert_resource(resource, processing_status="processing")

            # Determine if resource should be processed
            should_process, reason = self._should_process_resource(resource)

            if not should_process:
                logger.info(
                    f"Resource {resource_index + 1}/{self.stats.total_resources}: {resource_name} - SKIPPED ({reason})"
                )
                # Always create relationships, even if resource is skipped
                self._relationship_emitter.create_resource_group_relationships(resource)
                self.stats.skipped += 1
                return True

            logger.debug(
                f"Processing resource {resource_index + 1}/{self.stats.total_resources}: {resource_name} ({resource_type}) - {reason}"
            )

            # Generate LLM description if needed
            if reason in ["new_resource", "needs_llm_description", "retry_failed"]:
                logger.debug(str(f"Generating LLM description for {resource_name}"))
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
                    logger.debug(f'Generated description: "{desc_preview}"')
                else:
                    self.stats.llm_skipped += 1
                    logger.warning(
                        str(f"Using fallback description for {resource_name}")
                    )

            # Upsert resource to database
            success = self.db_ops.upsert_resource(
                resource, processing_status="completed"
            )
            if not success:
                raise Exception("Failed to upsert resource")

            # Create relationships
            self._relationship_emitter.create_subscription_relationship(
                resource["subscription_id"], resource_id
            )
            self._relationship_emitter.create_resource_group_relationships(resource)
            # Enriched relationships (non-containment)
            self._create_enriched_relationships(resource)

            logger.debug(str(f"Successfully processed {resource_name}"))
            self.stats.successful += 1
            return True

        except Exception:
            logger.exception(
                f"Failed to process resource {resource_name} ({resource_type})"
            )

            # Mark resource as failed in database
            try:
                self.db_ops.upsert_resource(resource, processing_status="failed")
            except Exception:
                logger.exception("Failed to mark resource as failed in DB")

            self.stats.failed += 1
            return False

        finally:
            self.stats.processed += 1

    async def process_resources(
        self,
        resources: List[Dict[str, Any]],
        max_workers: int = 5,
        progress_callback: Optional[Any] = None,
        progress_every: int = 50,
    ) -> ProcessingStats:
        """
        Process all resources with retry queue, poison list, and exponential back-off.

        Args:
            resources: List of resources to process
            max_workers: Maximum concurrent workers
            progress_callback: Optional callback for progress updates
            progress_every: How often to log progress

        Returns:
            ProcessingStats: Final processing statistics
        """
        import asyncio
        import time
        from collections import deque

        logger.info("[DEBUG][RP] Entered ResourceProcessor.process_resources")
        print("[DEBUG][RP] Entered ResourceProcessor.process_resources", flush=True)

        # Apply resource limit if specified
        if self.resource_limit and len(resources) > self.resource_limit:
            logger.info(
                f"Limiting processing to {self.resource_limit} resources (found {len(resources)})"
            )
            resources = resources[: self.resource_limit]

        self.stats.total_resources = len(resources)
        if not resources:
            logger.info("INFO: No resources to process")
            print("[DEBUG][RP] No resources to process", flush=True)
            return self.stats

        retry_queue: deque[tuple[Dict[str, Any], int, float]] = deque()
        poison_list: List[Dict[str, Any]] = []
        main_queue: deque[tuple[Dict[str, Any], int, float]] = deque(
            (r, 1, 0.0) for r in resources
        )

        in_progress: set[str] = set()
        resource_attempts: Dict[str, int] = {}

        base_delay = 1.0
        resource_index_counter = 0

        async def worker(
            resource: Dict[str, Any], resource_index: int, attempt: int
        ) -> bool:
            logger.debug(
                f"Worker started for resource {resource.get('id')} (index {resource_index}, attempt {attempt})"
            )
            try:
                return await self.process_single_resource(resource, resource_index)
            except Exception as e:
                logger.exception(
                    f"Exception in worker for resource {resource.get('id', 'Unknown')}: {e}"
                )
                return False

        logger.debug("Entering main processing loop")
        loop_counter = 0
        task_to_rid: Dict[asyncio.Task[Any], str] = {}

        while main_queue or retry_queue or in_progress:
            logger.debug(str(f"Top of main loop iteration {loop_counter}"))
            tasks: List[asyncio.Task[Any]] = []
            now = time.time()

            # Fill from main queue
            while len(in_progress) < max_workers and main_queue:
                resource, attempt, _ = main_queue.popleft()
                rid = resource["id"]
                in_progress.add(rid)
                resource_attempts[rid] = attempt
                resource["__attempt"] = attempt
                resource["__id"] = rid

                logger.debug(
                    f"Scheduling worker for resource {rid} (attempt {attempt})"
                )

                task = asyncio.create_task(
                    worker(resource, resource_index_counter, attempt)
                )
                tasks.append(task)
                task_to_rid[task] = rid
                resource_index_counter += 1

            # Fill from retry queue if eligible
            for _ in range(len(retry_queue)):
                resource, attempt, next_time = retry_queue.popleft()
                rid = resource["id"]
                if now >= next_time and len(in_progress) < max_workers:
                    in_progress.add(rid)
                    resource_attempts[rid] = attempt
                    resource["__attempt"] = attempt
                    resource["__id"] = rid

                    logger.debug(
                        f"Scheduling retry worker for resource {rid} (attempt {attempt})"
                    )

                    task = asyncio.create_task(
                        worker(resource, resource_index_counter, attempt)
                    )
                    tasks.append(task)
                    task_to_rid[task] = rid
                    resource_index_counter += 1
                else:
                    retry_queue.append((resource, attempt, next_time))

            if not tasks:
                if retry_queue:
                    soonest = min(next_time for _, _, next_time in retry_queue)
                    sleep_time = max(0.0, soonest - time.time())
                    logger.debug(
                        str(f"No tasks, sleeping for {sleep_time}s for next retry")
                    )
                    await asyncio.sleep(sleep_time)
                else:
                    await asyncio.sleep(0.1)
                loop_counter += 1
                continue

            # Wait for any task to complete
            logger.debug(str(f"Awaiting {len(tasks)} tasks"))
            done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            logger.debug(str(f"{len(done)} tasks completed"))

            for t in done:
                rid = task_to_rid.pop(t, None)
                if rid is None:
                    logger.warning("Completed task missing rid mapping")
                else:
                    in_progress.discard(rid)

                result = t.result()
                logger.debug(
                    str(f"Task for resource {rid} completed with result={result}")
                )

                if result:
                    pass
                else:
                    attempt = resource_attempts.get(rid, 1)  # type: ignore[misc] # type: ignore[arg-type]
                    # Re-obtain the resource object for retry or poison handling
                    resource = None
                    for queue in (main_queue, retry_queue):
                        for candidate in queue:
                            if candidate[0].get("id") == rid:
                                resource = candidate[0]
                                break
                        if resource:
                            break
                    if resource is None:
                        logger.warning(
                            f"Could not reconstruct original resource object for rid={rid}; skipping retry/poison handling"
                        )
                        continue
                    if attempt < self.max_retries:
                        delay = base_delay * (2 ** (attempt - 1))
                        logger.info(
                            f"Retry in {delay}s (attempt {attempt + 1}/{self.max_retries})."
                        )
                        retry_queue.append((resource, attempt + 1, time.time() + delay))
                        resource_attempts[rid] = attempt + 1  # type: ignore[arg-type]
                    else:
                        poison_list.append(resource)
                        logger.error(str(f"Poisoned after {attempt} attempts: {rid}"))
                        self.stats.failed += 1

            if progress_callback:
                logger.debug("Calling progress_callback")
                progress_callback(
                    processed=self.stats.processed,
                    total=self.stats.total_resources,
                    successful=self.stats.successful,
                    failed=self.stats.failed,
                    skipped=self.stats.skipped,
                    llm_generated=self.stats.llm_generated,
                    llm_skipped=self.stats.llm_skipped,
                )

            if self.stats.processed % progress_every == 0:
                logger.info(
                    f"Progress: {self.stats.processed}/{self.stats.total_resources} "
                    f"({self.stats.progress_percentage:.1f}%) - "
                    f"Success: {self.stats.successful} | Failed: {self.stats.failed} | Skipped: {self.stats.skipped}"
                )

            logger.debug(str(f"End of main loop iteration {loop_counter}"))
            loop_counter += 1

        logger.debug("Exited main processing loop")

        # Flush any remaining buffered relationships
        self._flush_relationship_buffers()

        # Verify dual-graph relationship duplication
        self._verify_dual_graph_relationships()

        # Generate LLM summaries if enabled
        if self.llm_generator:
            logger.info("Generating LLM summaries for ResourceGroups and Tags...")
            try:
                await self._llm_integration.generate_resource_group_summaries()
                await self._llm_integration.generate_tag_summaries()
                logger.info(
                    "Completed LLM summary generation for ResourceGroups and Tags"
                )
            except Exception as e:
                logger.exception(f"Failed to generate ResourceGroup/Tag summaries: {e}")

        if poison_list:
            logger.warning(
                f"Poison list (resources failed after {self.max_retries} attempts):"
            )
            for r in poison_list:
                logger.warning(f"  - {r.get('id', 'Unknown')}")

        self._log_final_summary()
        logger.debug("Returning from ResourceProcessor.process_resources")
        return self.stats

    def _create_enriched_relationships(self, resource: Dict[str, Any]) -> None:
        """
        Emit non-containment relationships for the resource, if applicable.
        Uses modular relationship rules from src.relationship_rules.
        """
        try:
            from src.relationship_rules import ALL_RELATIONSHIP_RULES
        except ImportError:
            logger.error("Could not import relationship rules package.")
            return

        for rule in ALL_RELATIONSHIP_RULES:
            try:
                if rule.applies(resource):
                    rule.emit(resource, self.db_ops)
            except Exception as e:
                logger.exception(
                    f"Relationship rule {rule.__class__.__name__} failed: {e}"
                )

        # Legacy relationships not yet migrated to rules
        rid = resource.get("id")
        props = resource
        diag_settings = props.get("diagnosticSettings")
        if isinstance(diag_settings, list):
            for ds in diag_settings:
                ws = ds.get("workspaceId")
                if ws and rid:
                    self._relationship_emitter.create_relationship(
                        str(rid), "LOGS_TO", str(ws)
                    )

        # ARM dependency relationships
        depends_on = props.get("dependsOn")
        if isinstance(depends_on, list):
            for dep_id in depends_on:
                if isinstance(dep_id, str) and rid:
                    self._relationship_emitter.create_relationship(
                        str(rid), "DEPENDS_ON", str(dep_id)
                    )

    def _flush_relationship_buffers(self) -> None:
        """Flush any remaining buffered relationships from all rules."""
        logger.info("Flushing buffered relationships from all rules...")
        try:
            from src.relationship_rules import ALL_RELATIONSHIP_RULES

            total_flushed = 0
            for rule in ALL_RELATIONSHIP_RULES:
                if hasattr(rule, "flush_relationship_buffer"):
                    flushed = rule.flush_relationship_buffer(self.db_ops)
                    total_flushed += flushed
            logger.info(str(f"Flushed {total_flushed} buffered relationships"))
        except Exception as e:
            logger.exception(f"Error flushing relationship buffers: {e}")

    def _verify_dual_graph_relationships(self) -> None:
        """Verify dual-graph relationship duplication."""
        logger.info("Verifying dual-graph relationship duplication...")
        try:
            verification_query = """
            // Count relationships in Original graph
            MATCH (src:Resource:Original)-[r]->(tgt:Resource:Original)
            WITH type(r) as rel_type, count(r) as orig_count

            // Count relationships in Abstracted graph
            MATCH (src_abs:Resource)-[r_abs]->(tgt_abs:Resource)
            WHERE NOT src_abs:Original AND NOT tgt_abs:Original
            WITH rel_type, orig_count, type(r_abs) as abs_rel_type, count(r_abs) as abs_count
            WHERE rel_type = abs_rel_type

            RETURN rel_type, orig_count, abs_count,
                   CASE WHEN orig_count = abs_count THEN 'MATCH' ELSE 'MISMATCH' END as status
            ORDER BY rel_type
            """

            with self.db_ops.session_manager.session() as session:
                result = session.run(verification_query)
                records = list(result)

                if records:
                    logger.info("Dual-Graph Relationship Verification:")
                    all_matched = True
                    for record in records:
                        rel_type = record["rel_type"]
                        orig_count = record["orig_count"]
                        abs_count = record["abs_count"]
                        status = record["status"]

                        log_msg = f"{status}: {rel_type}: Original={orig_count}, Abstracted={abs_count}"
                        if orig_count == abs_count:
                            logger.info(log_msg)
                        else:
                            logger.warning(log_msg)
                            all_matched = False

                    if all_matched:
                        logger.info(
                            "All relationship types matched between Original and Abstracted graphs"
                        )
                    else:
                        logger.warning(
                            "Some relationship types have mismatches - this may indicate missing nodes"
                        )
                else:
                    logger.info(
                        "No Resource-to-Resource relationships found in either graph"
                    )

        except Exception as e:
            logger.exception(f"Error verifying dual-graph relationships: {e}")

    def _log_final_summary(self) -> None:
        """Log final processing summary."""
        logger.info("=" * 60)
        logger.info("FINAL PROCESSING SUMMARY")
        logger.info("=" * 60)
        logger.info(str(f"Total Resources: {self.stats.total_resources}"))
        logger.info(
            f"Successful: {self.stats.successful} ({self.stats.success_rate:.1f}%)"
        )
        logger.info(str(f"Failed: {self.stats.failed}"))
        logger.info(str(f"Skipped: {self.stats.skipped}"))
        if self.llm_generator:
            logger.info(str(f"LLM Descriptions Generated: {self.stats.llm_generated}"))
            logger.info(str(f"LLM Descriptions Skipped: {self.stats.llm_skipped}"))
        logger.info("=" * 60)

    async def generate_resource_group_summaries(self) -> None:
        """Generate LLM summaries for all ResourceGroups that don't have descriptions yet."""
        await self._llm_integration.generate_resource_group_summaries()

    async def generate_tag_summaries(self) -> None:
        """Generate LLM summaries for all Tags that don't have descriptions yet."""
        await self._llm_integration.generate_tag_summaries()


def create_resource_processor(
    session_manager: Any,
    llm_generator: Optional[AzureLLMDescriptionGenerator] = None,
    resource_limit: Optional[int] = None,
    max_retries: int = 3,
    tenant_id: Optional[str] = None,
) -> ResourceProcessor:
    """
    Factory function to create a ResourceProcessor instance.

    Args:
        session_manager: Neo4jSessionManager
        llm_generator: Optional LLM description generator
        resource_limit: Optional limit on number of resources to process
        max_retries: Maximum number of retries for failed resources
        tenant_id: Tenant ID for dual-graph architecture (required)

    Returns:
        ResourceProcessor: Configured resource processor instance
    """
    return ResourceProcessor(
        session_manager,
        llm_generator,
        resource_limit,
        max_retries,
        tenant_id,
    )

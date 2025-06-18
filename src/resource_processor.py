"""
Azure Resource Processor

This module provides robust, resumable, and parallel processing of Azure resources
with improved error handling, progress tracking, and database operations.
"""

import asyncio
import json
import logging
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from .llm_descriptions import AzureLLMDescriptionGenerator, should_generate_description
from src.utils.session_manager import retry_neo4j_operation

logger = logging.getLogger(__name__)

@retry_neo4j_operation()
def run_neo4j_query_with_retry(session: Any, query: str, **params: Any) -> Any:
    return session.run(query, **params)


def serialize_value(value: Any, max_json_length: int = 500) -> Any:
    """
    Safely serialize a value for Neo4j property storage.
    Allowed: str, int, float, bool, list of those.
    - dicts/objects: JSON string (truncated if huge).
    - Azure SDK objects: str() or .name if present.
    - Empty dict: None.
    """
    # Primitives
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    # List: recursively serialize
    if isinstance(value, list):
        return [serialize_value(v, max_json_length) for v in value]  # type: ignore[misc]
    # Dict: JSON dump, handle empty
    if isinstance(value, dict):
        if not value:
            return None
        try:
            s = json.dumps(value, default=str, ensure_ascii=False)
            if len(s) > max_json_length:
                s = s[:max_json_length] + "...(truncated)"
            return s
        except Exception:
            return str(value)  # type: ignore[misc]
    # Azure SDK model: try .name, else str
    if hasattr(value, "name") and isinstance(value.name, str):
        return value.name
    # Fallback: str
    return str(value)


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

    def __init__(self, session_manager: Any) -> None:
        self.session_manager = session_manager

    def resource_exists(self, resource_id: str) -> bool:
        """Check if a resource already exists in the database."""
        try:
            with self.session_manager.session() as session:
                result = session.run(
                    "MATCH (r:Resource {id: $id}) RETURN count(r) as count",
                    id=resource_id
                )
                record = result.single()
                return bool(record["count"] > 0) if record else False
        except Exception:
            logger.exception(f"Error checking resource existence for {resource_id}")
            return False

    def has_llm_description(self, resource_id: str) -> bool:
        """Check if a resource already has an LLM description."""
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
        """Get processing metadata for a resource."""
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


class DatabaseOperations:
    """Handles all database operations for resources."""

    def __init__(self, session_manager: Any) -> None:
        self.session_manager = session_manager

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
        from .exceptions import ResourceDataValidationError, wrap_neo4j_exception

        try:
            # Defensive validation of required fields
            required_fields = [
                "id",
                "name",
                "type",
                "location",
                "resource_group",
                "subscription_id",
            ]
            # Accept id from resource_id if present
            if not resource.get("id") and resource.get("resource_id"):
                resource["id"] = resource["resource_id"]

            missing_or_null = [
                f for f in required_fields if resource.get(f) in (None, "")
            ]
            if missing_or_null:
                logger.exception(
                    f"Resource data missing/null for required fields: {missing_or_null} (resource: {resource})"
                )
                raise ResourceDataValidationError(missing_fields=missing_or_null)

            query = """
            MERGE (r:Resource {id: $props.id})
            SET r += $props,
                r.updated_at = datetime()
            """

            resource_data = resource.copy()
            resource_data["llm_description"] = resource.get("llm_description", "")
            resource_data["processing_status"] = processing_status

            # Serialize all values for Neo4j compatibility
            try:
                for k, v in resource_data.items():
                    resource_data[k] = serialize_value(v)
            except Exception as ser_exc:
                logger.exception(
                    f"Serialization error for resource {resource.get('id', 'Unknown')}: {ser_exc}"
                )
                return False

            try:
                with self.session_manager.session() as session:
                    session.run(query, props=resource_data)
            except Exception as neo4j_exc:
                logger.error(
                    f"Neo4j upsert error for resource {resource.get('id', 'Unknown')}: {neo4j_exc}"
                )
                # Use custom exception wrapper for context
                wrapped_exc = wrap_neo4j_exception(
                    neo4j_exc, context={"resource_id": resource.get("id", "Unknown")}
                )
                logger.error(str(wrapped_exc))
                return False

            return True

        except ResourceDataValidationError:
            # Already logged above
            return False
        except Exception as exc:
            logger.exception(
                f"Error upserting resource {resource.get('id', 'Unknown')}: {exc}"
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
            with self.session_manager.session() as session:
                run_neo4j_query_with_retry(
                    session, query, subscription_id=subscription_id, resource_id=resource_id
                )
            return True
        except Exception:
            logger.exception(
                f"Error creating subscription relationship for {resource_id}"
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
            with self.session_manager.session() as session:
                session.run(rg_query, rg_name=rg_name, subscription_id=subscription_id)

            # Create relationship: Subscription CONTAINS ResourceGroup
            sub_rg_query = """
            MATCH (s:Subscription {id: $subscription_id})
            MATCH (rg:ResourceGroup {name: $rg_name, subscription_id: $subscription_id})
            MERGE (s)-[:CONTAINS]->(rg)
            """
            with self.session_manager.session() as session:
                run_neo4j_query_with_retry(
                    session, sub_rg_query, subscription_id=subscription_id, rg_name=rg_name
                )

            # Create relationship: ResourceGroup CONTAINS Resource
            rg_resource_query = """
            MATCH (rg:ResourceGroup {name: $rg_name, subscription_id: $subscription_id})
            MATCH (r:Resource {id: $resource_id})
            MERGE (rg)-[:CONTAINS]->(r)
            """
            with self.session_manager.session() as session:
                run_neo4j_query_with_retry(
                    session,
                    rg_resource_query,
                    rg_name=rg_name,
                    subscription_id=subscription_id,
                    resource_id=resource_id,
                )

            return True

        except Exception:
            logger.exception(
                f"Error creating resource group relationships for {resource.get('id', 'Unknown')}"
            )
            return False


class ResourceProcessor:
    """
    Enhanced resource processor with improved error handling, progress tracking,
    and resumable operations.
    """

    def __init__(
        self,
        session_manager: Any,
        llm_generator: Optional[AzureLLMDescriptionGenerator] = None,
        resource_limit: Optional[int] = None,
    ):
        """
        Initialize the resource processor.

        Args:
            session_manager: Neo4jSessionManager
            llm_generator: Optional LLM description generator
            resource_limit: Optional limit on number of resources to process
        """
        self.session_manager = session_manager
        self.llm_generator = llm_generator
        self.resource_limit = resource_limit

        # Initialize helper classes
        self.state = ResourceState(session_manager)
        self.db_ops = DatabaseOperations(session_manager)

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
        Generate LLM description for a single resource, with skip logic.

        Args:
            resource: Resource dictionary

        Returns:
            Tuple of (success, description)
        """
        if not self.llm_generator:
            return False, f"Azure {resource.get('type', 'Resource')} resource."

        # --- LLM skip logic ---

        resource_id = resource.get("id")
        with self.session_manager.session() as session:
            if not should_generate_description(resource, session):
                # Fetch existing description from DB
                desc = None
                if resource_id:
                    metadata = self.state.get_processing_metadata(resource_id)
                    desc = metadata.get("llm_description")
                if desc:
                    logger.info(
                        f"⏭️  Skipping LLM for {resource_id}: using cached description."
                    )
                    self.stats.llm_skipped += 1
                    return False, desc
                else:
                    logger.info(
                        f"⏭️  Skipping LLM for {resource_id}: no cached description, using fallback."
                    )
                    self.stats.llm_skipped += 1
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

            logger.debug(
                f"📝 Processing resource {resource_index + 1}/{self.stats.total_resources}: {resource_name} ({resource_type}) - {reason}"
            )

            # Generate LLM description if needed
            # llm_success = False  # Removed unused variable
            if reason in ["new_resource", "needs_llm_description", "retry_failed"]:
                logger.debug(f"🤖 Generating LLM description for {resource_name}")
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
                    logger.debug(f'✅ Generated description: "{desc_preview}"')
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
            # --- Enriched relationships (non-containment) ---
            self._create_enriched_relationships(resource)

            logger.debug(f"✅ Successfully processed {resource_name}")
            self.stats.successful += 1
            return True

        except Exception:
            logger.exception(
                f"❌ Failed to process resource {resource_name} ({resource_type})"
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
        Process all resources in parallel using a thread pool, with progress tracking.

        Args:
            resources: List[Any] of resources to process
            max_workers: Maximum number of concurrent threads
            progress_callback: Optional callback for progress updates
            progress_every: Emit progress every N resources (default 50)

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
            f"🔄 Starting eager thread pool processing of {self.stats.total_resources} resources (max workers: {max_workers})"
        )

        import concurrent.futures

        def process_task(resource: Dict[str, Any], resource_index: int) -> bool:
            """Process a single resource (LLM + DB)."""
            loop = None
            try:
                if self.llm_generator:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    _, description = loop.run_until_complete(
                        self._process_single_resource_llm(resource)
                    )
                    resource["llm_description"] = description
                else:
                    resource["llm_description"] = (
                        f"Azure {resource.get('type', 'Resource')} resource."
                    )
                # DB and relationship ops
                return (
                    loop.run_until_complete(
                        self.process_single_resource(resource, resource_index)
                    )
                    if loop
                    else asyncio.run(
                        self.process_single_resource(resource, resource_index)
                    )
                )
            finally:
                if loop:
                    asyncio.set_event_loop(None)
                    loop.close()

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_index = {
                executor.submit(process_task, resource, idx): idx
                for idx, resource in enumerate(resources)
            }

            for _i, future in enumerate(
                concurrent.futures.as_completed(future_to_index), 1
            ):
                idx = future_to_index[future]
                try:
                    future.result()
                except Exception:
                    logger.exception(
                        f"❌ Processing failed for resource {resources[idx].get('name', 'Unknown')}"
                    )
                    self.stats.failed += 1
                    self.stats.processed += 1

                # Progress callback and logging
                if progress_callback:
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
                        f"📊 Progress: {self.stats.processed}/{self.stats.total_resources} "
                        f"({self.stats.progress_percentage:.1f}%) - "
                        f"✅ {self.stats.successful} | ❌ {self.stats.failed} | ⏭️ {self.stats.skipped}"
                    )

        self._log_final_summary()
        return self.stats

    def _create_relationship(self, src_id: str, rel_type: str, tgt_id: str) -> None:
        """
        Create a relationship of type rel_type from src_id to tgt_id using MERGE semantics.
        """
        query = (
            "MATCH (src:Resource {id: $src_id}) "
            "MATCH (tgt:Resource {id: $tgt_id}) "
            f"MERGE (src)-[:{rel_type}]->(tgt)"
        )
        with self.session_manager.session() as session:
            session.run(query, src_id=src_id, tgt_id=tgt_id)

    def _create_enriched_relationships(self, resource: Dict[str, Any]) -> None:
        """
        Emit non-containment relationships for the resource, if applicable.
        """
        rid = resource.get("id")
        rtype = resource.get("type", "")
        props = resource

        # --- 1. Network relationships ---
        # (VirtualMachine) -[:USES_SUBNET]-> (Subnet)
        # (Subnet) -[:SECURED_BY]-> (NetworkSecurityGroup)
        if rtype.endswith("virtualMachines") and "network_profile" in props:
            nics = props["network_profile"].get("network_interfaces", [])
            for nic in nics:
                ip_cfgs = nic.get("ip_configurations", [])
                for ipcfg in ip_cfgs:
                    subnet = ipcfg.get("subnet")
                    if subnet and isinstance(subnet, dict):
                        subnet_id = subnet.get("id")
                        if subnet_id and rid:
                            self._create_relationship(
                                str(rid), "USES_SUBNET", str(subnet_id)
                            )
        if rtype.endswith("subnets"):
            # Subnet may have a networkSecurityGroup property
            nsg = props.get("network_security_group")
            if nsg and isinstance(nsg, dict):
                nsg_id = nsg.get("id")
                if nsg_id and rid:
                    self._create_relationship(str(rid), "SECURED_BY", str(nsg_id))

        # --- 2. Identity relationships ---
        # (Any resource with identity.principalId) -[:HAS_MANAGED_IDENTITY]-> (ManagedIdentity)
        identity = props.get("identity")
        if identity and isinstance(identity, dict):
            principal_id = identity.get("principalId")
            if principal_id and rid:
                # ManagedIdentity node must exist with id = principalId
                self._create_relationship(
                    str(rid), "HAS_MANAGED_IDENTITY", str(principal_id)
                )
        # (KeyVault) -[:POLICY_FOR]-> (ManagedIdentity) for each access-policy principalId
        if rtype.endswith("vaults"):
            access_policies = props.get("properties", {}).get("accessPolicies", [])
            for policy in access_policies:
                pid = policy.get("objectId")
                if pid and rid:
                    self._create_relationship(str(rid), "POLICY_FOR", str(pid))

        # --- 3. Monitoring relationships ---
        # (Resource with diagnosticSettings) -[:LOGS_TO]-> (LogAnalyticsWorkspace)
        diag_settings = props.get("diagnosticSettings")
        if isinstance(diag_settings, list):
            for ds in diag_settings:
                ws = ds.get("workspaceId")
                if ws and rid:
                    self._create_relationship(str(rid), "LOGS_TO", str(ws))

        # --- 4. ARM dependency relationships ---
        # (Resource with dependsOn) -[:DEPENDS_ON]-> (target Resource)
        depends_on = props.get("dependsOn")
        if isinstance(depends_on, list):
            for dep_id in depends_on:
                if isinstance(dep_id, str) and rid:
                    self._create_relationship(str(rid), "DEPENDS_ON", str(dep_id))

    # Removed _log_progress_summary (batch) as batching is deprecated

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


# --- Place these methods inside the ResourceProcessor class, after other methods ---


def process_resources_async_llm(
    session: Any,
    resources: List[Dict[str, Any]],
    llm_generator: Optional[AzureLLMDescriptionGenerator],
    summary_executor: ThreadPoolExecutor,
    counters: Dict[str, int],
    counters_lock: threading.Lock,
    max_workers: int = 10,
) -> list[Future[Any]]:
    """
    Insert resources into the graph and schedule LLM summaries in a background thread pool.
    Args:
        session: Neo4j session
        resources: List of resource dicts
        llm_generator: LLM generator instance
        summary_executor: ThreadPoolExecutor for summaries
        counters: Shared counter dict
        counters_lock: threading.Lock for counters
        max_workers: Maximum concurrent LLM summaries
    Returns:
        None (updates counters in place)
    """
    from .llm_descriptions import ThrottlingError

    def insert_resource(resource: Dict[str, Any]) -> None:
        # Insert resource into graph
        # Note: This function uses the legacy session parameter for backwards compatibility
        # In practice, this should be updated to use a session_manager
        db_ops = DatabaseOperations(session)
        db_ops.upsert_resource(resource, processing_status="completed")
        db_ops.create_subscription_relationship(
            resource["subscription_id"], resource["id"]
        )
        db_ops.create_resource_group_relationships(resource)
        with counters_lock:
            counters["inserted"] += 1

    def summarize_resource(resource: Dict[str, Any]) -> None:
        try:
            with counters_lock:
                counters["in_flight"] += 1
            if llm_generator:
                desc = llm_generator.generate_resource_description(resource)
                # If async, run in event loop
                if asyncio.iscoroutine(desc):
                    desc = asyncio.run(desc)
                resource["llm_description"] = desc
                with counters_lock:
                    counters["llm_generated"] += 1
            else:
                resource["llm_description"] = (
                    f"Azure {resource.get('type', 'Resource')} resource."
                )
                with counters_lock:
                    counters["llm_skipped"] += 1
        except ThrottlingError:
            with counters_lock:
                counters["throttled"] += 1
            raise
        except Exception:
            with counters_lock:
                counters["llm_skipped"] += 1
        finally:
            with counters_lock:
                counters["in_flight"] -= 1
                counters["remaining"] -= 1

    # Schedule
    with counters_lock:
        counters["total"] = len(resources)
        counters["remaining"] = len(resources)
    futures: List[Future[Any]] = []
    for resource in resources:
        insert_resource(resource)
        future = summary_executor.submit(summarize_resource, resource)
        futures.append(future)
    # Optionally: return futures for monitoring
    return futures


def create_resource_processor(
    session_manager: Any,
    llm_generator: Optional[AzureLLMDescriptionGenerator] = None,
    resource_limit: Optional[int] = None,
) -> ResourceProcessor:
    """
    Factory function to create a ResourceProcessor instance.

    Args:
        session_manager: Neo4jSessionManager
        llm_generator: Optional LLM description generator
        resource_limit: Optional limit on number of resources to process

    Returns:
        ResourceProcessor: Configured resource processor instance
    """
    return ResourceProcessor(session_manager, llm_generator, resource_limit)

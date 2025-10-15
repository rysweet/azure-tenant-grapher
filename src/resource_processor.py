"""
Azure Resource Processor

This module provides robust, resumable, and parallel processing of Azure resources
with improved error handling, progress tracking, and database operations.
"""

import asyncio
import json
import re
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import structlog

from src.logging_config import configure_logging
from src.utils.session_manager import retry_neo4j_operation

from .llm_descriptions import AzureLLMDescriptionGenerator, should_generate_description

configure_logging()
logger = structlog.get_logger(__name__)


@retry_neo4j_operation()
def run_neo4j_query_with_retry(session: Any, query: str, **params: Any) -> Any:
    return session.run(query, **params)


def serialize_value(value: Any, max_json_length: int = 5000) -> Any:
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
    # Azure SDK model: try as_dict() for properties, then .name, else str
    if hasattr(value, "as_dict") and callable(value.as_dict):
        try:
            return serialize_value(value.as_dict(), max_json_length)
        except Exception:
            pass
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
                    id=resource_id,
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

    def upsert_subscription(
        self, subscription_id: str, subscription_name: str = ""
    ) -> bool:
        """
        Create or update a Subscription node.
        """
        try:
            query = """
            MERGE (s:Subscription {id: $id})
            SET s.name = $name,
                s.updated_at = datetime()
            """
            with self.session_manager.session() as session:
                session.run(query, id=subscription_id, name=subscription_name)
            return True
        except Exception:
            logger.exception(f"Error upserting Subscription node {subscription_id}")
            return False

    def upsert_resource_group(
        self, rg_id: str, rg_name: str, subscription_id: str
    ) -> bool:
        """
        Create or update a ResourceGroup node with unique id, name, and subscription_id.
        """
        try:
            query = """
            MERGE (rg:ResourceGroup {id: $id})
            SET rg.name = $name,
                rg.subscription_id = $subscription_id,
                rg.type = 'ResourceGroup',
                rg.updated_at = datetime(),
                rg.llm_description = coalesce(rg.llm_description, '')
            """
            with self.session_manager.session() as session:
                session.run(
                    query, id=rg_id, name=rg_name, subscription_id=subscription_id
                )
            return True
        except Exception:
            logger.exception(f"Error upserting ResourceGroup node {rg_id}")
            return False

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

            # Upsert Subscription node before relationships
            self.upsert_subscription(resource["subscription_id"])

            query = """
            MERGE (r:Resource {id: $props.id})
            SET r += $props,
                r.updated_at = datetime()
            """

            resource_data = resource.copy()
            resource_data["llm_description"] = resource.get("llm_description", "")
            resource_data["processing_status"] = processing_status

            # Extract critical VNet properties BEFORE serialization to avoid truncation
            # This prevents Neo4j driver truncation issues for large properties (>5000 chars)
            if resource_data.get("type") == "Microsoft.Network/virtualNetworks":
                properties_raw = resource_data.get("properties")
                if properties_raw:
                    try:
                        # If properties is already a dict, use it directly
                        if isinstance(properties_raw, dict):
                            props_dict = properties_raw
                        elif isinstance(properties_raw, str):
                            # If it's a JSON string, parse it
                            props_dict = json.loads(properties_raw)
                        else:
                            props_dict = {}

                        # Extract addressSpace as separate top-level property
                        address_space = props_dict.get("addressSpace", {})
                        if address_space:
                            address_prefixes = address_space.get("addressPrefixes", [])
                            if address_prefixes:
                                # Store as JSON string for easy access in IaC generation
                                resource_data["addressSpace"] = json.dumps(address_prefixes)
                                logger.debug(
                                    f"Extracted addressSpace for VNet '{resource.get('name')}': {address_prefixes}"
                                )
                    except (json.JSONDecodeError, AttributeError, TypeError) as e:
                        logger.warning(
                            f"Failed to extract addressSpace from VNet '{resource.get('name')}': {e}"
                        )

            # Prevent empty properties from overwriting existing data
            # If properties is empty dict, remove it from update to preserve existing
            if resource_data.get("properties") == {}:
                logger.debug(
                    f"Skipping empty properties update for {resource.get('id')} to preserve existing data"
                )
                resource_data.pop("properties", None)

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
                logger.debug(
                    "Running upsert_resource query", query=query, props=resource_data
                )
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
            # Ensure Subscription node exists
            self.upsert_subscription(subscription_id)
            query = """
            MATCH (s:Subscription {id: $subscription_id})
            MATCH (r:Resource {id: $resource_id})
            MERGE (s)-[:CONTAINS]->(r)
            """
            with self.session_manager.session() as session:
                run_neo4j_query_with_retry(
                    session,
                    query,
                    subscription_id=subscription_id,
                    resource_id=resource_id,
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
            # Build full Azure ID for ResourceGroup
            rg_id = f"/subscriptions/{subscription_id}/resourceGroups/{rg_name}"

            logger.info(
                f"DEBUG: Creating RG relationships for resource id={resource_id}, resource_group={rg_name}, subscription_id={subscription_id}"
            )

            # Upsert Subscription node
            self.upsert_subscription(subscription_id)
            # Upsert ResourceGroup node with unique id
            self.upsert_resource_group(rg_id, rg_name, subscription_id)

            # Create relationship: Subscription CONTAINS ResourceGroup
            sub_rg_query = """
            MATCH (s:Subscription {id: $subscription_id})
            MATCH (rg:ResourceGroup {id: $rg_id})
            MERGE (s)-[:CONTAINS]->(rg)
            """
            with self.session_manager.session() as session:
                run_neo4j_query_with_retry(
                    session,
                    sub_rg_query,
                    subscription_id=subscription_id,
                    rg_id=rg_id,
                )

            # Create relationship: ResourceGroup CONTAINS Resource
            rg_resource_query = """
            MATCH (rg:ResourceGroup {id: $rg_id})
            MATCH (r:Resource {id: $resource_id})
            MERGE (rg)-[:CONTAINS]->(r)
            """
            with self.session_manager.session() as session:
                run_neo4j_query_with_retry(
                    session,
                    rg_resource_query,
                    rg_id=rg_id,
                    resource_id=resource_id,
                )

            return True

        except Exception:
            logger.exception(
                f"Error creating resource group relationships for {resource.get('id', 'Unknown')}"
            )
            return False

    def upsert_generic(
        self, label: str, key_prop: str, key_value: str, properties: Dict[str, Any]
    ) -> bool:
        """
        Create or update a generic node with the specified label and properties.

        Args:
            label: Node label (e.g., "Region", "Tag")
            key_prop: Property name to use as unique key (e.g., "code", "name")
            key_value: Value for the key property
            properties: Additional properties to set on the node

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Serialize all property values
            serialized_props = {}
            for k, v in properties.items():
                serialized_props[k] = serialize_value(v)

            # Add the key property
            serialized_props[key_prop] = serialize_value(key_value)

            query = f"""
            MERGE (n:{label} {{{key_prop}: $key_value}})
            SET n += $props,
                n.updated_at = datetime()
            """

            with self.session_manager.session() as session:
                session.run(query, key_value=key_value, props=serialized_props)
            return True

        except Exception:
            logger.exception(
                f"Error upserting {label} node with {key_prop}={key_value}"
            )
            return False

    def create_generic_rel(
        self,
        src_id: str,
        rel_type: str,
        tgt_key_value: str,
        tgt_label: str,
        tgt_key_prop: str,
    ) -> bool:
        """
        Create a relationship from a Resource to a generic node identified by a key property.

        Args:
            src_id: Source resource ID
            rel_type: Relationship type (e.g., "LOCATED_IN", "HAS_TAG")
            tgt_key_value: Value of the target node's key property
            tgt_label: Label of the target node (e.g., "Region", "Tag")
            tgt_key_prop: Property name used to identify the target node (e.g., "code", "name")

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            query = f"""
            MATCH (src:Resource {{id: $src_id}})
            MATCH (tgt:{tgt_label} {{{tgt_key_prop}: $tgt_key_value}})
            MERGE (src)-[:{rel_type}]->(tgt)
            """

            with self.session_manager.session() as session:
                session.run(query, src_id=src_id, tgt_key_value=tgt_key_value)
            return True

        except Exception:
            logger.exception(
                f"Error creating {rel_type} relationship from {src_id} to {tgt_label}({tgt_key_prop}={tgt_key_value})"
            )
            return False


def extract_identity_fields(resource: Dict[str, Any]) -> None:
    """
    Extracts 'identity' and 'principalId' from a resource dict if present.
    - Adds resource['identity'] if an 'identity' block is present.
    - Adds resource['principal_id'] if 'principalId' is present and looks like a GUID.
    """
    # Extract 'identity' block if present
    identity = resource.get("identity")
    if identity is not None:
        resource["identity"] = identity

    # Extract 'principalId' if present and looks like a GUID
    principal_id = resource.get("principalId") or resource.get("principal_id")
    if principal_id and isinstance(principal_id, str):
        # Minimal GUID validation: 8-4-4-4-12 hex digits
        if re.match(
            r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$",
            principal_id,
        ):
            resource["principal_id"] = principal_id


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
        max_retries: int = 3,
    ):
        """
        Initialize the resource processor.

        Args:
            session_manager: Neo4jSessionManager
            llm_generator: Optional LLM description generator
            resource_limit: Optional limit on number of resources to process
            max_retries: Maximum number of retries for failed resources
        """
        self.session_manager = session_manager
        self.llm_generator = llm_generator
        self.resource_limit = resource_limit
        self.max_retries = max_retries

        # Initialize helper classes
        self.state = ResourceState(session_manager)
        self.db_ops = DatabaseOperations(session_manager)

        # Processing statistics
        self.stats = ProcessingStats()

        # Thread-safe seen guard (Phase 1 efficiency improvement)
        self._seen_ids: set[str] = set()
        self._seen_lock = threading.Lock()

        logger.info(
            f"Initialized ResourceProcessor with LLM: {'enabled' if llm_generator else 'disabled'}, max_retries: {max_retries}"
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
        # --- Extract identity and principalId fields if present ---
        extract_identity_fields(resource)

        resource_id = resource["id"]
        resource_name = resource.get("name", "Unknown")
        resource_type = resource.get("type", "Unknown")

        # Thread-safe seen guard (Phase 1 efficiency improvement)
        with self._seen_lock:
            if resource_id in self._seen_ids:
                logger.info(
                    f"⏭️  Resource {resource_index + 1}/{self.stats.total_resources}: {resource_name} - SKIPPED (intra-run duplicate)"
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
                    f"⏭️  Resource {resource_index + 1}/{self.stats.total_resources}: {resource_name} - SKIPPED ({reason})"
                )
                # Always create relationships, even if resource is skipped
                self.db_ops.create_resource_group_relationships(resource)
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
        logger.info("[DEBUG][RP] Entered ResourceProcessor.process_resources")
        print("[DEBUG][RP] Entered ResourceProcessor.process_resources", flush=True)
        """
        Process all resources with retry queue, poison list, and exponential back-off.
        """
        import time
        from collections import deque

        # Apply resource limit if specified
        if self.resource_limit and len(resources) > self.resource_limit:
            logger.info(
                f"🔢 Limiting processing to {self.resource_limit} resources (found {len(resources)})"
            )
            resources = resources[: self.resource_limit]

        self.stats.total_resources = len(resources)
        if not resources:
            logger.info("INFO: No resources to process")
            print("[DEBUG][RP] No resources to process", flush=True)
            return self.stats

        retry_queue = deque()
        poison_list = []
        main_queue = deque(
            (r, 1, 0.0) for r in resources
        )  # (resource, attempt, next_time)

        in_progress = set()
        resource_attempts = {}  # resource_id -> attempt count

        base_delay = 1.0  # seconds
        resource_index_counter = 0

        async def worker(
            resource: dict[str, Any], resource_index: int, attempt: int
        ) -> bool:
            logger.info(
                f"[DEBUG][RP] Worker started for resource {resource.get('id')} (index {resource_index}, attempt {attempt})"
            )
            print(
                f"[DEBUG][RP] Worker started for resource {resource.get('id')} (index {resource_index}, attempt {attempt})",
                flush=True,
            )
            try:
                print(
                    f"[DEBUG][RP] Awaiting process_single_resource for {resource.get('id')}",
                    flush=True,
                )
                logger.info(
                    f"[DEBUG][RP] About to await process_single_resource for {resource.get('id')}"
                )
                result = await self.process_single_resource(resource, resource_index)
                print(
                    f"[DEBUG][RP] Returned from process_single_resource for {resource.get('id')} result={result}",
                    flush=True,
                )
                logger.info(
                    f"[DEBUG][RP] Returned from process_single_resource for {resource.get('id')} result={result}"
                )
                logger.info(
                    f"[DEBUG][RP] Worker finished for resource {resource.get('id')} (index {resource_index}, attempt {attempt}) result={result}"
                )
                return result
            except Exception as e:
                logger.exception(
                    f"Exception in worker for resource {resource.get('id', 'Unknown')}: {e}"
                )
                print(
                    f"[DEBUG][RP] Exception in worker for resource {resource.get('id', 'Unknown')}: {e}",
                    flush=True,
                )
                return False

        logger.info("[DEBUG][RP] Entering main processing loop")
        print("[DEBUG][RP] Entering main processing loop", flush=True)
        loop_counter = 0
        # --- Explicit mapping ensures robust loop tracking and deterministic cleanup ---
        # Each asyncio.Task[Any] is mapped to its associated Azure resource ID,
        # enabling full traceability and correctness on completion.
        # Legacy coroutine/frame inspection REMOVED as per regression and maintainability.
        task_to_rid: dict[asyncio.Task[Any], str] = {}
        # Maps worker tasks to resource IDs. All cleanup, retry, and poison tracking use ONLY this mapping.
        # This approach avoids introspection and enables robust, deterministic resource tracking.

        while main_queue or retry_queue or in_progress:
            logger.info(f"[DEBUG][RP] Top of main loop iteration {loop_counter}")
            print(f"[DEBUG][RP] Top of main loop iteration {loop_counter}", flush=True)
            tasks = []
            now = time.time()
            # Fill from main queue
            while len(in_progress) < max_workers and main_queue:
                resource, attempt, _ = main_queue.popleft()
                rid = resource["id"]
                in_progress.add(rid)
                resource_attempts[rid] = attempt
                resource["__attempt"] = attempt
                resource["__id"] = rid
                print(
                    f"[DEBUG][RP] Scheduling worker for resource {rid} (attempt {attempt})",
                    flush=True,
                )
                logger.info(
                    f"[DEBUG][RP] Scheduling worker for resource {rid} (attempt {attempt})"
                )
                task = asyncio.create_task(
                    worker(resource, resource_index_counter, attempt)
                )
                tasks.append(task)
                # Add to explicit mapping for deterministic cleanup
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
                    print(
                        f"[DEBUG][RP] Scheduling retry worker for resource {rid} (attempt {attempt})",
                        flush=True,
                    )
                    logger.info(
                        f"[DEBUG][RP] Scheduling retry worker for resource {rid} (attempt {attempt})"
                    )
                    task = asyncio.create_task(
                        worker(resource, resource_index_counter, attempt)
                    )
                    tasks.append(task)
                    # Add to explicit mapping for deterministic cleanup
                    task_to_rid[task] = rid
                    resource_index_counter += 1
                else:
                    retry_queue.append((resource, attempt, next_time))

            if not tasks:
                # Wait for soonest retry or for in-progress tasks to finish
                if retry_queue:
                    soonest = min(next_time for _, _, next_time in retry_queue)
                    sleep_time = max(0.0, soonest - time.time())
                    print(
                        f"[DEBUG][RP] No tasks, sleeping for {sleep_time}s for next retry",
                        flush=True,
                    )
                    logger.info(
                        f"[DEBUG][RP] No tasks, sleeping for {sleep_time}s for next retry"
                    )
                    await asyncio.sleep(sleep_time)
                else:
                    print("[DEBUG][RP] No tasks, sleeping for 0.1s", flush=True)
                    logger.info("[DEBUG][RP] No tasks, sleeping for 0.1s")
                    await asyncio.sleep(0.1)
                loop_counter += 1
                continue

            # Wait for any task to complete
            print(f"[DEBUG][RP] Awaiting {len(tasks)} tasks", flush=True)
            logger.info(f"[DEBUG][RP] Awaiting {len(tasks)} tasks")
            done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            print(f"[DEBUG][RP] {len(done)} tasks completed", flush=True)
            logger.info(f"[DEBUG][RP] {len(done)} tasks completed")
            for t in done:
                # Deterministic cleanup: use explicit mapping, legacy inspection fully purged
                rid = task_to_rid.pop(t, None)
                # Deterministic explicit mapping—legacy task frame/coroutine inspection fully removed.
                if rid is None:
                    logger.warning("[DEBUG][RP] Completed task missing rid mapping")
                else:
                    in_progress.discard(rid)

                result = t.result()
                print(
                    f"[DEBUG][RP] Task for resource {rid} completed with result={result}",
                    flush=True,
                )
                logger.info(
                    f"[DEBUG][RP] Task for resource {rid} completed with result={result}"
                )
                if result:
                    pass
                else:
                    attempt = resource_attempts.get(rid, 1)
                    # Re-obtain the resource object for retry or poison handling.
                    resource = None
                    # Scan main_queue and retry_queue for the resource object.
                    for queue in (main_queue, retry_queue):
                        for candidate in queue:
                            if candidate[0].get("id") == rid:
                                resource = candidate[0]
                                break
                        if resource:
                            break
                    if resource is None:
                        logger.warning(
                            f"[DEBUG][RP] Could not reconstruct original resource object for rid={rid}; skipping retry/poison handling"
                        )
                        continue
                    if attempt < self.max_retries:
                        delay = base_delay * (2 ** (attempt - 1))
                        print(
                            f"[DEBUG][RP] Scheduling retry for resource {rid} in {delay}s (attempt {attempt + 1})",
                            flush=True,
                        )
                        logger.info(
                            f"[DEBUG][RP] Scheduling retry for resource {rid} in {delay}s (attempt {attempt + 1})"
                        )
                        retry_queue.append((resource, attempt + 1, time.time() + delay))
                        resource_attempts[rid] = attempt + 1
                        logger.warning(
                            f"🔁 Retry in {delay}s (attempt {attempt + 1}/{self.max_retries})."
                        )
                    else:
                        poison_list.append(resource)
                        logger.error(f"☠️  Poisoned after {attempt} attempts: {rid}")
                        print(
                            f"[DEBUG][RP] Poisoned resource {rid} after {attempt} attempts",
                            flush=True,
                        )
                        logger.info(
                            f"[DEBUG][RP] Poisoned resource {rid} after {attempt} attempts"
                        )
                        self.stats.failed += 1  # Only increment failed for poison
            if progress_callback:
                logger.info("[DEBUG][RP] Calling progress_callback")
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
            logger.info(f"[DEBUG][RP] End of main loop iteration {loop_counter}")
            print(f"[DEBUG][RP] End of main loop iteration {loop_counter}", flush=True)
            loop_counter += 1
        logger.info("[DEBUG][RP] Exited main processing loop")
        print("[DEBUG][RP] Exited main processing loop", flush=True)

        if self.llm_generator:
            logger.info("🤖 Generating LLM summaries for ResourceGroups and Tags...")
            print(
                "[DEBUG][RP] Generating LLM summaries for ResourceGroups and Tags...",
                flush=True,
            )
            try:
                print(
                    "[DEBUG][RP] Awaiting generate_resource_group_summaries", flush=True
                )
                logger.info("[DEBUG][RP] Awaiting generate_resource_group_summaries")
                await self.generate_resource_group_summaries()
                print("[DEBUG][RP] Awaiting generate_tag_summaries", flush=True)
                logger.info("[DEBUG][RP] Awaiting generate_tag_summaries")
                await self.generate_tag_summaries()
                logger.info(
                    "✅ Completed LLM summary generation for ResourceGroups and Tags"
                )
                print(
                    "[DEBUG][RP] Completed LLM summary generation for ResourceGroups and Tags",
                    flush=True,
                )
            except Exception as e:
                logger.exception(f"Failed to generate ResourceGroup/Tag summaries: {e}")
                print(
                    f"[DEBUG][RP] Exception during LLM summary generation: {e}",
                    flush=True,
                )

        if poison_list:
            logger.warning(
                f"Poison list (resources failed after {self.max_retries} attempts):"
            )
            for r in poison_list:
                logger.warning(f"  - {r.get('id', 'Unknown')}")
                print(
                    f"[DEBUG][RP] Poison list resource: {r.get('id', 'Unknown')}",
                    flush=True,
                )

        self._log_final_summary()
        logger.info("[DEBUG][RP] Returning from ResourceProcessor.process_resources")
        print(
            "[DEBUG][RP] Returning from ResourceProcessor.process_resources", flush=True
        )
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

        # --- Legacy relationships not yet migrated to rules ---
        # Monitoring relationships
        rid = resource.get("id")
        props = resource
        diag_settings = props.get("diagnosticSettings")
        if isinstance(diag_settings, list):
            for ds in diag_settings:
                ws = ds.get("workspaceId")
                if ws and rid:
                    self._create_relationship(str(rid), "LOGS_TO", str(ws))

        # ARM dependency relationships
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

    async def generate_resource_group_summaries(self) -> None:
        """Generate LLM summaries for all ResourceGroups that don't have descriptions yet."""
        if not self.llm_generator:
            logger.info(
                "No LLM generator available, skipping ResourceGroup summary generation"
            )
            return

        logger.info("🔄 Starting ResourceGroup LLM summary generation...")

        try:
            # Get all ResourceGroups that need descriptions
            rg_query = """
            MATCH (rg:ResourceGroup)
            WHERE rg.llm_description IS NULL OR rg.llm_description = '' OR rg.llm_description STARTS WITH 'Azure'
            RETURN rg.name AS name, rg.subscription_id AS subscription_id
            """

            resource_groups = []
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

                    resources = []
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
                        f"✅ Generated LLM description for ResourceGroup '{rg['name']}'"
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

        logger.info("🔄 Starting Tag LLM summary generation...")

        try:
            # Get all Tags that need descriptions
            tag_query = """
            MATCH (t:Tag)
            WHERE t.llm_description IS NULL OR t.llm_description = '' OR t.llm_description STARTS WITH 'Azure'
            RETURN t.id AS id, t.key AS key, t.value AS value
            """

            tags = []
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

            logger.info(f"Found {len(tags)} Tags that need LLM descriptions")

            for tag in tags:
                try:
                    # Get all resources that have this tag
                    tagged_resources_query = """
                    MATCH (r:Resource)-[:TAGGED_WITH]->(t:Tag {id: $tag_id})
                    RETURN r.name AS name, r.type AS type, r.location AS location, r.resource_group AS resource_group
                    """

                    tagged_resources = []
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
                        f"✅ Generated LLM description for Tag '{tag['key']}:{tag['value']}'"
                    )

                except Exception as e:
                    logger.exception(
                        f"Failed to generate LLM description for Tag '{tag['key']}:{tag['value']}': {e}"
                    )
                    continue

        except Exception as e:
            logger.exception(f"Error during Tag summary generation: {e}")


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
    max_retries: int = 3,
) -> ResourceProcessor:
    """
    Factory function to create a ResourceProcessor instance.

    Args:
        session_manager: Neo4jSessionManager
        llm_generator: Optional LLM description generator
        resource_limit: Optional limit on number of resources to process
        max_retries: Maximum number of retries for failed resources

    Returns:
        ResourceProcessor: Configured resource processor instance
    """
    return ResourceProcessor(
        session_manager, llm_generator, resource_limit, max_retries
    )

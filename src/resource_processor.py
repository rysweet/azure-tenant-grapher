"""
Azure Resource Processor - Backward Compatibility Shim

This module provides backward compatibility for the original resource_processor API.
The implementation has been refactored into the src.services.resource_processing package.

All public exports are re-exported from the new location to maintain backward compatibility.

For new code, prefer importing directly from:
    from src.services.resource_processing import (
        ProcessingStats,
        ResourceProcessor,
        # ...
    )

This shim will be deprecated in a future version.
"""

import asyncio
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any, Dict, List, Optional

import structlog  # type: ignore[import-untyped]

# Re-export everything from the new location for backward compatibility
from src.services.resource_processing import (
    GLOBAL_RESOURCE_TYPES,
    BatchProcessor,
    # Backward compatibility alias
    DatabaseOperations,
    LLMIntegration,
    NodeManager,
    # Core classes
    ProcessingStats,
    RelationshipEmitter,
    ResourceProcessor,
    ResourceState,
    # Factory
    create_resource_processor,
    extract_identity_fields,
    # Utilities
    serialize_value,
)

from .llm_descriptions import AzureLLMDescriptionGenerator
from .utils.session_manager import retry_neo4j_operation

logger = structlog.get_logger(__name__)


# Re-export the retry decorator for backward compatibility
@retry_neo4j_operation()
def run_neo4j_query_with_retry(session: Any, query: str, **params: Any) -> Any:
    """Run a Neo4j query with retry logic."""
    return session.run(query, **params)


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

    This is a legacy helper function maintained for backward compatibility.

    Args:
        session: Neo4j session
        resources: List of resource dicts
        llm_generator: LLM generator instance
        summary_executor: ThreadPoolExecutor for summaries
        counters: Shared counter dict
        counters_lock: threading.Lock for counters
        max_workers: Maximum concurrent LLM summaries

    Returns:
        List of futures for monitoring
    """
    from .llm_descriptions import ThrottlingError

    def insert_resource(resource: Dict[str, Any]) -> None:
        # Insert resource into graph
        # Note: This function uses the legacy session parameter for backwards compatibility
        db_ops = DatabaseOperations(session, tenant_id="legacy")
        db_ops.upsert_resource(resource, processing_status="completed")

        # Create relationships using the emitter
        emitter = RelationshipEmitter(session, node_manager=db_ops)
        emitter.create_subscription_relationship(
            resource["subscription_id"], resource["id"]
        )
        emitter.create_resource_group_relationships(resource)

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
    return futures


# Ensure all public symbols are available (sorted alphabetically)
__all__ = [
    "GLOBAL_RESOURCE_TYPES",
    "BatchProcessor",
    "DatabaseOperations",
    "LLMIntegration",
    "NodeManager",
    "ProcessingStats",
    "RelationshipEmitter",
    "ResourceProcessor",
    "ResourceState",
    "create_resource_processor",
    "extract_identity_fields",
    "process_resources_async_llm",
    "run_neo4j_query_with_retry",
    "serialize_value",
]

"""
Batch Processor Module

This module handles retry queue, poison list, and worker scheduling
for batch resource processing.
"""

import asyncio
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine, Dict, List, Optional

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class BatchResult:
    """Result of batch processing operation."""

    processed: int = 0
    poisoned: List[Dict[str, Any]] = field(default_factory=list)
    success_rate: float = 0.0


class BatchProcessor:
    """
    Handles retry queue, poison list, and worker scheduling for batch processing.

    Implements exponential backoff for retries and tracks poison resources
    that fail after max retries.
    """

    def __init__(
        self,
        max_workers: int = 5,
        max_retries: int = 3,
        base_delay: float = 1.0,
    ) -> None:
        """
        Initialize the BatchProcessor.

        Args:
            max_workers: Maximum concurrent workers
            max_retries: Maximum retry attempts before poisoning
            base_delay: Base delay in seconds for exponential backoff
        """
        self.max_workers = max_workers
        self.max_retries = max_retries
        self.base_delay = base_delay

    async def process_batch(
        self,
        resources: List[Dict[str, Any]],
        worker: Callable[[Dict[str, Any], int], Coroutine[Any, Any, bool]],
        progress_callback: Optional[Callable[..., None]] = None,
        progress_every: int = 50,
    ) -> BatchResult:
        """
        Process a batch of resources with retry queue and poison list.

        Args:
            resources: List of resources to process
            worker: Async worker function (resource, attempt) -> bool
            progress_callback: Optional callback for progress updates
            progress_every: How often to log progress

        Returns:
            BatchResult with processed count, poisoned resources, and success rate
        """
        if not resources:
            return BatchResult(processed=0, poisoned=[], success_rate=100.0)

        result = BatchResult()
        retry_queue: deque[tuple[Dict[str, Any], int, float]] = deque()
        poison_list: List[Dict[str, Any]] = []
        main_queue: deque[tuple[Dict[str, Any], int, float]] = deque(
            (r, 1, 0.0) for r in resources
        )

        in_progress: set[str] = set()
        resource_attempts: Dict[str, int] = {}
        resource_index_counter = 0
        total_resources = len(resources)
        processed_count = 0
        successful_count = 0
        failed_count = 0

        # Explicit mapping for task -> resource ID
        task_to_rid: Dict[asyncio.Task[Any], str] = {}

        async def wrapped_worker(
            resource: Dict[str, Any], resource_index: int, attempt: int
        ) -> bool:
            """Wrapped worker with error handling."""
            logger.debug(
                f"Worker started for resource {resource.get('id')} (index {resource_index}, attempt {attempt})"
            )
            try:
                return await worker(resource, attempt)
            except Exception as e:
                logger.exception(
                    f"Exception in worker for resource {resource.get('id', 'Unknown')}: {e}"
                )
                return False

        logger.debug("Entering main processing loop")

        while main_queue or retry_queue or in_progress:
            tasks: List[asyncio.Task[Any]] = []
            now = time.time()

            # Fill from main queue
            while len(in_progress) < self.max_workers and main_queue:
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
                    wrapped_worker(resource, resource_index_counter, attempt)
                )
                tasks.append(task)
                task_to_rid[task] = rid
                resource_index_counter += 1

            # Fill from retry queue if eligible
            retry_items_to_requeue: List[tuple[Dict[str, Any], int, float]] = []
            while retry_queue:
                resource, attempt, next_time = retry_queue.popleft()
                rid = resource["id"]
                if now >= next_time and len(in_progress) < self.max_workers:
                    in_progress.add(rid)
                    resource_attempts[rid] = attempt
                    resource["__attempt"] = attempt
                    resource["__id"] = rid

                    logger.debug(
                        f"Scheduling retry worker for resource {rid} (attempt {attempt})"
                    )

                    task = asyncio.create_task(
                        wrapped_worker(resource, resource_index_counter, attempt)
                    )
                    tasks.append(task)
                    task_to_rid[task] = rid
                    resource_index_counter += 1
                else:
                    retry_items_to_requeue.append((resource, attempt, next_time))

            for item in retry_items_to_requeue:
                retry_queue.append(item)

            if not tasks:
                # Wait for soonest retry or for in-progress tasks to finish
                if retry_queue:
                    soonest = min(next_time for _, _, next_time in retry_queue)
                    sleep_time = max(0.0, soonest - time.time())
                    logger.debug(f"No tasks, sleeping for {sleep_time}s for next retry")
                    await asyncio.sleep(sleep_time)
                else:
                    await asyncio.sleep(0.1)
                continue

            # Wait for any task to complete
            logger.debug(f"Awaiting {len(tasks)} tasks")
            done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            logger.debug(f"{len(done)} tasks completed")

            for t in done:
                rid = task_to_rid.pop(t, None)
                if rid is None:
                    logger.warning("Completed task missing rid mapping")
                    continue

                in_progress.discard(rid)
                task_result = t.result()
                processed_count += 1

                logger.debug(
                    f"Task for resource {rid} completed with result={task_result}"
                )

                if task_result:
                    successful_count += 1
                else:
                    attempt = resource_attempts.get(rid, 1)
                    # Find the resource object
                    resource = None
                    for queue in (main_queue, retry_queue):
                        for candidate, _, _ in queue:
                            if candidate.get("id") == rid:
                                resource = candidate
                                break
                        if resource:
                            break

                    if resource is None:
                        # Resource not found in queues, check original list
                        for r in resources:
                            if r.get("id") == rid:
                                resource = r
                                break

                    if resource is None:
                        logger.warning(
                            f"Could not find resource object for rid={rid}; skipping retry/poison handling"
                        )
                        failed_count += 1
                        continue

                    if attempt < self.max_retries:
                        delay = self.base_delay * (2 ** (attempt - 1))
                        logger.info(
                            f"Retry in {delay}s (attempt {attempt + 1}/{self.max_retries}) for {rid}"
                        )
                        retry_queue.append((resource, attempt + 1, time.time() + delay))
                        resource_attempts[rid] = attempt + 1
                    else:
                        poison_list.append(resource)
                        failed_count += 1
                        logger.error(f"Poisoned after {attempt} attempts: {rid}")

            # Progress callback
            if progress_callback:
                progress_callback(
                    processed=processed_count,
                    total=total_resources,
                    successful=successful_count,
                    failed=failed_count,
                )

            if processed_count % progress_every == 0 and processed_count > 0:
                progress_pct = (processed_count / total_resources) * 100
                logger.info(
                    f"Progress: {processed_count}/{total_resources} ({progress_pct:.1f}%) - "
                    f"Success: {successful_count} | Failed: {failed_count}"
                )

        logger.debug("Exited main processing loop")

        # Calculate final stats
        result.processed = processed_count
        result.poisoned = poison_list
        result.success_rate = (successful_count / max(processed_count, 1)) * 100

        return result

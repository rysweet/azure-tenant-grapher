"""
Progress Tracking Service for ATG Remote Operations.

Philosophy:
- Track and broadcast operation progress
- Support multiple WebSocket subscribers per job
- Store historical events for late subscribers
- Thread-safe subscriber management

Public API:
    ProgressTracker: Main progress tracking service
"""

import asyncio
import logging
from collections import defaultdict
from datetime import datetime
from typing import Dict, List

logger = logging.getLogger(__name__)


class ProgressTracker:
    """
    Track and broadcast operation progress to WebSocket subscribers.

    Maintains progress history and manages subscriber queues for real-time
    progress streaming during ATG operations.

    Attributes:
        _subscribers: Dict mapping job_id to list of subscriber queues
        _history: Dict mapping job_id to list of progress events
        _lock: AsyncIO lock for thread-safe operations
    """

    def __init__(self):
        """Initialize progress tracker with empty state."""
        self._subscribers: Dict[str, List[asyncio.Queue]] = defaultdict(list)
        self._history: Dict[str, List[Dict]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def publish(
        self,
        job_id: str,
        event_type: str,
        message: str,
        details: Dict | None = None,
    ) -> None:
        """
        Publish progress event to all subscribers for a job.

        Args:
            job_id: Unique job identifier
            event_type: Event type (starting, progress, complete, error)
            message: Human-readable progress message
            details: Optional additional event details

        Example:
            >>> tracker = ProgressTracker()
            >>> await tracker.publish(
            ...     "scan-abc123",
            ...     "progress",
            ...     "Found 50 resources",
            ...     {"count": 50}
            ... )
        """
        event = {
            "job_id": job_id,
            "type": event_type,
            "message": message,
            "timestamp": datetime.utcnow().isoformat(),
        }

        if details:
            event["details"] = details

        async with self._lock:
            # Store in history
            self._history[job_id].append(event)

            # Broadcast to all subscribers
            subscribers = self._subscribers[job_id]
            logger.debug(
                f"Publishing {event_type} event for {job_id} to {len(subscribers)} subscribers"
            )

            for queue in subscribers:
                try:
                    await asyncio.wait_for(queue.put(event), timeout=1.0)
                except asyncio.TimeoutError:
                    logger.warning(
                        f"Timeout publishing to subscriber queue for {job_id}"
                    )
                except Exception as e:
                    logger.error(str(f"Error publishing to subscriber: {e}"))

    async def subscribe(self, job_id: str) -> asyncio.Queue:
        """
        Subscribe to progress updates for a job.

        Returns a queue that receives all progress events. Immediately sends
        historical events to catch up new subscribers.

        Args:
            job_id: Job identifier to subscribe to

        Returns:
            Queue that receives progress events

        Example:
            >>> tracker = ProgressTracker()
            >>> queue = await tracker.subscribe("scan-abc123")
            >>> while True:
            ...     event = await queue.get()
            ...     print(event["message"])
        """
        queue: asyncio.Queue = asyncio.Queue()

        async with self._lock:
            # Add to subscribers
            self._subscribers[job_id].append(queue)

            # Send historical events
            for event in self._history[job_id]:
                await queue.put(event)

        logger.info(str(f"New subscriber for job {job_id}"))
        return queue

    async def unsubscribe(self, job_id: str, queue: asyncio.Queue) -> None:
        """
        Unsubscribe from progress updates.

        Args:
            job_id: Job identifier
            queue: Queue to remove from subscribers
        """
        async with self._lock:
            if queue in self._subscribers[job_id]:
                self._subscribers[job_id].remove(queue)
                logger.info(str(f"Subscriber removed for job {job_id}"))

    def get_history(self, job_id: str) -> List[Dict]:
        """
        Get progress history for a job.

        Args:
            job_id: Job identifier

        Returns:
            List of progress events in chronological order
        """
        return self._history[job_id].copy()

    async def clear_job(self, job_id: str) -> None:
        """
        Clear all data for a job (history and subscribers).

        Used for cleanup after job completion.

        Args:
            job_id: Job identifier to clear
        """
        async with self._lock:
            if job_id in self._history:
                del self._history[job_id]
            if job_id in self._subscribers:
                # Close all subscriber queues
                for queue in self._subscribers[job_id]:
                    # Signal end of stream
                    await queue.put(None)
                del self._subscribers[job_id]
        logger.info(str(f"Cleared progress data for job {job_id}"))


__all__ = ["ProgressTracker"]

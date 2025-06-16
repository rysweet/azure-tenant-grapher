from typing import Any, Callable, Optional
from unittest.mock import MagicMock

import pytest

from src.config_manager import ProcessingConfig
from src.resource_processor import ProcessingStats
from src.services.resource_processing_service import ResourceProcessingService
from src.utils.session_manager import Neo4jSessionManager


def make_async_return(result: Any) -> Callable[..., Any]:
    async def coro(*args: Any, **kwargs: Any) -> Any:
        return result

    return coro


@pytest.mark.asyncio
async def test_successful_processing_multiple_resources():
    resources = [{"id": f"r{i}"} for i in range(7)]
    config = ProcessingConfig(max_concurrency=3, max_retries=2)
    session_manager = MagicMock(spec=Neo4jSessionManager)
    llm_generator = None

    processor_factory = MagicMock()

    # Simulate a processor that processes all resources in one call and calls progress_callback per resource
    async def process_resources(
        resources: list[dict[str, Any]],
        progress_callback: Optional[Callable[[ProcessingStats], None]] = None,
        max_workers: Optional[int] = None,
    ) -> ProcessingStats:
        for i in range(1, len(resources) + 1):
            if progress_callback is not None:
                progress_callback(
                    ProcessingStats(
                        total_resources=len(resources), processed=i, successful=i
                    )
                )
        return ProcessingStats(
            total_resources=len(resources),
            processed=len(resources),
            successful=len(resources),
        )

    processor_mock = MagicMock()
    processor_mock.process_resources = process_resources
    processor_factory.return_value = processor_mock

    progress_calls = []

    def progress_callback(stats: ProcessingStats):
        progress_calls.append(stats.processed)

    service = ResourceProcessingService(
        session_manager, llm_generator, config, processor_factory=processor_factory
    )

    result = await service.process_resources(
        resources, progress_callback=progress_callback
    )
    assert result.processed == 7
    assert result.successful == 7
    assert processor_factory.call_count == 1  # One processor for all resources
    assert progress_calls == [1, 2, 3, 4, 5, 6, 7]


# Removed test_retry_on_transient_error_then_success and test_unrecoverable_error_raises (batch retry logic is deprecated)


@pytest.mark.asyncio
async def test_progress_callback_invoked_correctly():
    resources = [{"id": f"r{i}"} for i in range(5)]
    config = ProcessingConfig(max_concurrency=2, max_retries=1)
    session_manager = MagicMock(spec=Neo4jSessionManager)
    llm_generator = None

    # Each batch returns stats for just that batch (not cumulative)
    batch_sizes = [2, 2, 1]
    batch_stats_list = [
        ProcessingStats(total_resources=size, processed=size, successful=size)
        for size in batch_sizes
    ]
    processor_factory = MagicMock()

    def factory_side_effect(*args: Any, **kwargs: Any):
        mock = MagicMock()
        batch_stats_list.pop(0)

        async def process_resources(
            resources: list[dict[str, Any]],
            progress_callback: Optional[Callable[[ProcessingStats], None]] = None,
            max_workers: Optional[int] = None,
        ) -> ProcessingStats:
            processed = 0
            for _ in range(len(resources)):
                processed += 1
                if progress_callback is not None:
                    progress_callback(
                        ProcessingStats(
                            total_resources=len(resources),
                            processed=processed,
                            successful=processed,
                        )
                    )
            return ProcessingStats(
                total_resources=len(resources),
                processed=len(resources),
                successful=len(resources),
            )

        mock.process_resources = process_resources
        return mock

    processor_factory.side_effect = factory_side_effect

    progress_calls = []

    def progress_callback(stats: ProcessingStats):
        progress_calls.append(stats.processed)

    service = ResourceProcessingService(
        session_manager, llm_generator, config, processor_factory=processor_factory
    )

    await service.process_resources(resources, progress_callback=progress_callback)
    # In the new model, progress_callback is called per resource, not per batch.
    # So we expect it to be called 5 times, once for each processed resource.
    assert progress_calls == [1, 2, 3, 4, 5]

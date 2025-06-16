from unittest.mock import MagicMock

import pytest

from src.config_manager import ProcessingConfig
from src.exceptions import (
    AzureDiscoveryError,
    ResourceProcessingError,
)
from src.resource_processor import ProcessingStats
from src.services.resource_processing_service import ResourceProcessingService
from src.utils.session_manager import Neo4jSessionManager


def make_async_return(result):
    async def coro(*args, **kwargs):
        return result

    return coro


@pytest.mark.asyncio
async def test_successful_processing_multiple_batches():
    resources = [{"id": f"r{i}"} for i in range(7)]
    config = ProcessingConfig(batch_size=3, max_retries=2)
    session_manager = MagicMock(spec=Neo4jSessionManager)
    llm_generator = None

    # Each batch returns stats for just that batch (not cumulative)
    batch_sizes = [3, 3, 1]
    batch_stats_list = [
        ProcessingStats(total_resources=size, processed=size, successful=size)
        for size in batch_sizes
    ]
    processor_factory = MagicMock()

    # Each call to processor_factory returns a mock with the correct batch stats
    def factory_side_effect(*args, **kwargs):
        mock = MagicMock()
        stats = batch_stats_list.pop(0)
        mock.process_resources_batch = make_async_return(stats)
        return mock

    processor_factory.side_effect = factory_side_effect

    progress_calls = []

    def progress_callback(stats):
        progress_calls.append(stats.processed)

    service = ResourceProcessingService(
        session_manager, llm_generator, config, processor_factory=processor_factory
    )

    result = await service.process_resources_batch(
        resources, progress_callback=progress_callback
    )
    assert result.processed == 7
    assert result.successful == 7
    assert processor_factory.call_count == 3  # 3, 3, 1
    assert progress_calls == [3, 6, 7]


@pytest.mark.asyncio
async def test_retry_on_transient_error_then_success():
    resources = [{"id": "r1"}, {"id": "r2"}]
    config = ProcessingConfig(batch_size=2, max_retries=2)
    session_manager = MagicMock(spec=Neo4jSessionManager)
    llm_generator = None

    call_count = {"count": 0}

    async def process_batch(batch, **_):
        if call_count["count"] == 0:
            call_count["count"] += 1
            raise AzureDiscoveryError("Transient error")
        return ProcessingStats(total_resources=2, processed=2, successful=2)

    processor_mock = MagicMock()
    processor_mock.process_resources_batch = process_batch
    processor_factory = MagicMock(return_value=processor_mock)

    service = ResourceProcessingService(
        session_manager, llm_generator, config, processor_factory=processor_factory
    )

    result = await service.process_resources_batch(resources)
    assert result.processed == 2
    assert result.successful == 2
    assert processor_factory.call_count == 2  # One for each attempt


@pytest.mark.asyncio
async def test_unrecoverable_error_raises():
    resources = [{"id": "r1"}]
    config = ProcessingConfig(batch_size=1, max_retries=1)
    session_manager = MagicMock(spec=Neo4jSessionManager)
    llm_generator = None

    async def raise_fatal(batch, **_):
        raise ValueError("Fatal error")

    processor_mock = MagicMock()
    processor_mock.process_resources_batch = raise_fatal
    processor_factory = MagicMock(return_value=processor_mock)

    service = ResourceProcessingService(
        session_manager, llm_generator, config, processor_factory=processor_factory
    )

    with pytest.raises(ResourceProcessingError) as excinfo:
        await service.process_resources_batch(resources)
    assert "Resource processing failed" in str(excinfo.value)


@pytest.mark.asyncio
async def test_progress_callback_invoked_correctly():
    resources = [{"id": f"r{i}"} for i in range(5)]
    config = ProcessingConfig(batch_size=2, max_retries=1)
    session_manager = MagicMock(spec=Neo4jSessionManager)
    llm_generator = None

    # Each batch returns stats for just that batch (not cumulative)
    batch_sizes = [2, 2, 1]
    batch_stats_list = [
        ProcessingStats(total_resources=size, processed=size, successful=size)
        for size in batch_sizes
    ]
    processor_factory = MagicMock()

    def factory_side_effect(*args, **kwargs):
        mock = MagicMock()
        stats = batch_stats_list.pop(0)
        mock.process_resources_batch = make_async_return(stats)
        return mock

    processor_factory.side_effect = factory_side_effect

    progress_calls = []

    def progress_callback(stats):
        progress_calls.append(stats.processed)

    service = ResourceProcessingService(
        session_manager, llm_generator, config, processor_factory=processor_factory
    )

    await service.process_resources_batch(
        resources, progress_callback=progress_callback
    )
    assert progress_calls == [2, 4, 5]

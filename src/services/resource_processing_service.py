import asyncio
import logging
from typing import Any, Callable, Optional

from src.config_manager import ProcessingConfig
from src.exceptions import (
    AzureDiscoveryError,
    Neo4jError,
    ResourceProcessingError,
)
from src.llm_descriptions import AzureLLMDescriptionGenerator
from src.resource_processor import (
    ProcessingStats,
    ResourceProcessor,
)
from src.utils.session_manager import Neo4jSessionManager

logger = logging.getLogger(__name__)

TransientErrors = (AzureDiscoveryError, Neo4jError)


class ResourceProcessingService:
    def __init__(
        self,
        session_manager: Neo4jSessionManager,
        llm_generator: Optional[AzureLLMDescriptionGenerator],
        config: ProcessingConfig,
        processor_factory: Optional[Callable[..., ResourceProcessor]] = None,
    ):
        self.session_manager = session_manager
        self.llm_generator = llm_generator
        self.config = config
        self.processor_factory = processor_factory or ResourceProcessor

    async def process_resources_batch(
        self,
        resources: list[dict[str, Any]],
        progress_callback: Optional[Callable[[ProcessingStats], None]] = None,
    ) -> ProcessingStats:
        batch_size = self.config.batch_size or 100
        max_concurrency = getattr(self.config, "max_concurrency", batch_size)
        max_retries = self.config.max_retries
        retry_delay = getattr(self.config, "retry_delay", 1.0)

        total_resources = len(resources)
        stats = ProcessingStats(total_resources=total_resources)
        batches = [
            resources[i : i + batch_size] for i in range(0, total_resources, batch_size)
        ]

        semaphore = asyncio.Semaphore(max_concurrency)

        async def process_batch(
            batch: list[dict[str, Any]], batch_idx: int
        ) -> ProcessingStats:
            attempt = 0
            while True:
                try:
                    async with semaphore:
                        processor = self.processor_factory(
                            self.session_manager.get_session(),
                            self.llm_generator,
                        )
                        batch_stats = await processor.process_resources_batch(
                            batch,
                            batch_size=len(batch),
                            progress_callback=None,
                        )
                        logger.info(f"Batch {batch_idx+1} processed successfully.")
                        return batch_stats
                except TransientErrors as e:
                    logger.exception(
                        f"Transient error in batch {batch_idx+1}, attempt {attempt+1}/{max_retries}: {e}"
                    )
                    if attempt < max_retries:
                        await asyncio.sleep(retry_delay * (2**attempt))
                        attempt += 1
                        continue
                    else:
                        raise ResourceProcessingError(
                            f"Batch {batch_idx+1} failed after {max_retries} retries",
                            context={"batch_idx": batch_idx, "attempts": attempt + 1},
                        ) from e
                except Exception as e:
                    logger.exception(f"Unrecoverable error in batch {batch_idx+1}: {e}")
                    raise ResourceProcessingError(
                        f"Unrecoverable error in batch {batch_idx+1}",
                        context={"batch_idx": batch_idx},
                    ) from e

        try:
            for batch_idx, batch in enumerate(batches):
                batch_stats = await process_batch(batch, batch_idx)
                # Merge stats
                stats.processed += batch_stats.processed
                stats.successful += batch_stats.successful
                stats.failed += batch_stats.failed
                stats.skipped += batch_stats.skipped
                stats.llm_generated += batch_stats.llm_generated
                stats.llm_skipped += batch_stats.llm_skipped
                if progress_callback:
                    progress_callback(stats)
            return stats
        except Exception as e:
            logger.exception("Resource processing failed")
            raise ResourceProcessingError(
                "Resource processing failed",
                context={"total_resources": total_resources},
            ) from e

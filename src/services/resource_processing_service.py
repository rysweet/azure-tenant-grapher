import logging
from typing import Any, Callable, Optional

from src.config_manager import ProcessingConfig
from src.exceptions import (
    AzureDiscoveryError,
    Neo4jError,
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

    async def process_resources(
        self,
        resources: list[dict[str, Any]],
        progress_callback: Optional[Callable[[ProcessingStats], None]] = None,
        max_workers: Optional[int] = None,
    ) -> ProcessingStats:
        """
        Process all resources in parallel using the ResourceProcessor, with progress tracking.

        Args:
            resources: List of resource dicts to process
            progress_callback: Optional callback for progress updates
            max_workers: Maximum number of concurrent threads (defaults to config)

        Returns:
            ProcessingStats: Final processing statistics
        """
        processor = self.processor_factory(
            self.session_manager.get_session(),
            self.llm_generator,
        )
        if max_workers is None:
            max_workers = getattr(self.config, "max_concurrency", 5)
        if max_workers is None:
            max_workers = 5
        return await processor.process_resources(
            resources,
            max_workers=max_workers,
            progress_callback=progress_callback,
        )

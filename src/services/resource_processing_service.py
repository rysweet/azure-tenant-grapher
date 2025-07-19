import logging
import os
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
        aad_graph_service: Optional[Any] = None,
    ):
        self.session_manager = session_manager
        self.llm_generator = llm_generator
        self.config = config
        self.processor_factory = processor_factory or ResourceProcessor
        self.aad_graph_service = aad_graph_service

    async def process_resources(
        self,
        resources: list[dict[str, Any]],
        progress_callback: Optional[Callable[[ProcessingStats], None]] = None,
        max_workers: Optional[int] = None,
    ) -> ProcessingStats:
        logger.info("[DEBUG][RPS] Entered ResourceProcessingService.process_resources")
        """
        Process all resources in parallel using the ResourceProcessor, with progress tracking.
        Optionally ingests AAD users/groups if ENABLE_AAD_IMPORT is set.

        Args:
            resources: List of resource dicts to process
            progress_callback: Optional callback for progress updates
            max_workers: Maximum number of concurrent threads (defaults to config)

        Returns:
            ProcessingStats: Final processing statistics
        """
        processor = self.processor_factory(
            self.session_manager,
            self.llm_generator,
            getattr(self.config, "resource_limit", None),
            getattr(self.config, "max_retries", 3),
        )

        # --- AAD Graph Ingestion ---
        enable_aad = (
            getattr(self.config, "enable_aad_import", None)
            or os.environ.get("ENABLE_AAD_IMPORT", "false").lower() == "true"
        )
        if enable_aad and self.aad_graph_service:
            logger.info(
                "AAD import enabled: ingesting Azure AD users and groups into graph."
            )
            try:
                self.aad_graph_service.ingest_into_graph(processor.db_ops)
            except Exception as ex:
                logger.exception(f"Failed to ingest AAD users/groups: {ex}")

        if max_workers is None:
            max_workers = getattr(self.config, "max_concurrency", 5)
        if max_workers is None:
            max_workers = 5
        logger.info(
            f"[DEBUG][RPS] Calling processor.process_resources with {len(resources)} resources, max_workers={max_workers}"
        )
        result = await processor.process_resources(
            resources,
            max_workers=max_workers,
            progress_callback=progress_callback,
        )
        logger.info("[DEBUG][RPS] processor.process_resources returned")
        return result

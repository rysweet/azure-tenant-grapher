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
        filter_config: Optional[Any] = None,
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
        # Use config value which defaults to True, can be overridden by env var
        enable_aad = getattr(self.config, "enable_aad_import", True)
        
        # Skip AAD import when filtering by resource groups or subscriptions
        # Because we can't determine which users/groups are relevant to just those resources
        is_filtering = filter_config and (filter_config.has_filters() if hasattr(filter_config, 'has_filters') else 
                                          (filter_config.resource_group_names or filter_config.subscription_ids))
        
        if enable_aad and self.aad_graph_service and not is_filtering:
            logger.info(
                "AAD import enabled: ingesting Azure AD users and groups into graph."
            )
            try:
                await self.aad_graph_service.ingest_into_graph(processor.db_ops)
            except Exception as ex:
                logger.exception(f"Failed to ingest AAD users/groups: {ex}")
        elif is_filtering and enable_aad:
            logger.info(
                "⚠️  Skipping AAD user/group import when filtering by subscriptions or resource groups. "
                "Only resources matching the filter will be imported."
            )

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

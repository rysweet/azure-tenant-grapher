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
            getattr(self.config, "enable_batch_mode", False),
        )

        # --- AAD Graph Ingestion ---
        # Use config value which defaults to True, can be overridden by env var
        enable_aad = getattr(self.config, "enable_aad_import", True)

        # Check if we're filtering resources
        is_filtering = filter_config and (filter_config.has_filters() if hasattr(filter_config, 'has_filters') else
                                          (filter_config.resource_group_names or filter_config.subscription_ids))

        # IMPORTANT: Entra ID (AAD) is tenant-wide, not resource-group-scoped.
        # When filtering ARM resources by subscription or resource group, we should still
        # import ALL Entra ID resources because:
        # 1. Entra ID resources are tenant-wide, not scoped to resource groups
        # 2. Role assignments and permissions may reference identities not directly attached to filtered resources
        # 3. The user expectation is to filter ARM resources, not Entra ID resources
        if enable_aad and self.aad_graph_service:
            logger.info(
                "AAD import enabled: ingesting all Azure AD users and groups into graph."
            )
            if is_filtering:
                logger.info(
                    "📋 Note: ARM resource filtering is active, but importing ALL Entra ID resources (tenant-wide)."
                )
            try:
                await self.aad_graph_service.ingest_into_graph(processor.db_ops)
            except Exception as ex:
                logger.exception(f"Failed to ingest AAD users/groups: {ex}")

        if max_workers is None:
            max_workers = getattr(self.config, "max_concurrency", 5)
        if max_workers is None:
            max_workers = 5

        if enable_aad and not self.aad_graph_service:
            logger.warning(
                "⚠️  AAD import enabled but AADGraphService not available. "
                "Entra ID resources will not be imported."
            )
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

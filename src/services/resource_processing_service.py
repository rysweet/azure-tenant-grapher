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
from src.services.identity_collector import IdentityCollector
from src.services.managed_identity_resolver import ManagedIdentityResolver
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
        
        # Check if we're filtering resources
        is_filtering = filter_config and (filter_config.has_filters() if hasattr(filter_config, 'has_filters') else 
                                          (filter_config.resource_group_names or filter_config.subscription_ids))
        
        if enable_aad and self.aad_graph_service:
            if not is_filtering:
                # No filtering - import all AAD users and groups
                logger.info(
                    "AAD import enabled: ingesting all Azure AD users and groups into graph."
                )
                try:
                    await self.aad_graph_service.ingest_into_graph(processor.db_ops)
                except Exception as ex:
                    logger.exception(f"Failed to ingest AAD users/groups: {ex}")
            else:
                # Filtering enabled - import only referenced identities
                logger.info(
                    "🎯 Filtering enabled: extracting and importing only referenced identities."
                )
                try:
                    # Extract identity references from filtered resources
                    identity_collector = IdentityCollector()
                    identity_refs = identity_collector.collect_identity_references(resources)
                    
                    if identity_refs.has_identities():
                        logger.info(identity_collector.get_summary(identity_refs))
                        
                        # Resolve managed identities to get additional details
                        identity_resolver = ManagedIdentityResolver()
                        resolved_identities = identity_resolver.resolve_identities(
                            identity_refs.managed_identities,
                            resources
                        )
                        
                        if resolved_identities:
                            logger.info(identity_resolver.get_identity_summary(resolved_identities))
                        
                        # Ingest only the referenced identities
                        # Note: Managed identities are service principals in Azure AD
                        service_principal_ids = identity_refs.service_principals.union(identity_refs.managed_identities)
                        
                        await self.aad_graph_service.ingest_filtered_identities(
                            user_ids=identity_refs.users,
                            group_ids=identity_refs.groups,
                            service_principal_ids=service_principal_ids,
                            db_ops=processor.db_ops
                        )
                        logger.info("✅ Successfully imported referenced identities")
                    else:
                        logger.info(
                            "No identity references found in filtered resources - skipping AAD import"
                        )
                except Exception as ex:
                    logger.exception(f"Failed to ingest filtered AAD identities: {ex}")

        if max_workers is None:
            max_workers = getattr(self.config, "max_concurrency", 5)
        if max_workers is None:
            max_workers = 5
        elif is_filtering and enable_aad and not self.aad_graph_service:
            logger.warning(
                "⚠️  AAD import enabled with filtering but AADGraphService not available. "
                "Identities referenced by filtered resources will not be imported."
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

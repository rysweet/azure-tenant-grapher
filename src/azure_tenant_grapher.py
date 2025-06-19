"""
Azure Tenant Resource Grapher

This module provides functionality to walk Azure tenant resources and build
a Neo4j graph database of those resources and their relationships.
"""

import logging
import os
import warnings
from typing import Any, Dict, List, Optional

from .config_manager import AzureTenantGrapherConfig
from .container_manager import Neo4jContainerManager
from .llm_descriptions import create_llm_generator

logger = logging.getLogger(__name__)


class AzureTenantGrapher:
    """
    Coordinator for Azure tenant resource discovery and graph building.
    Composes AzureDiscoveryService, ResourceProcessingService, and TenantSpecificationService.
    """

    def __init__(self, config: AzureTenantGrapherConfig) -> None:
        """
        Initialize the Azure Tenant Grapher coordinator.

        Args:
            config: Configuration object containing all settings
        """
        self.config = config

        # Compose services per refactoring plan
        self.container_manager = (
            Neo4jContainerManager() if config.processing.auto_start_container else None
        )
        from .services.azure_discovery_service import AzureDiscoveryService
        from .services.resource_processing_service import ResourceProcessingService
        from .services.tenant_specification_service import TenantSpecificationService
        from .utils.session_manager import Neo4jSessionManager

        self.session_manager = Neo4jSessionManager(config.neo4j)
        self.discovery_service = AzureDiscoveryService(config)
        self.processing_service = ResourceProcessingService(
            self.session_manager,
            create_llm_generator() if config.azure_openai.is_configured() else None,
            config.processing,
        )
        self.specification_service = TenantSpecificationService(
            self.session_manager,
            self.processing_service.llm_generator,
            config.specification,
        )

        # Log configuration summary
        self.config.log_configuration_summary()

        # Legacy Neo4j connection methods removed; use session_manager.

    def connect_to_neo4j(self) -> None:
        """
        Deprecated adapter to maintain backward compatibility with legacy code/tests
        that expect AzureTenantGrapher.connect_to_neo4j().

        The internal Neo4jSessionManager handles connection pooling; this wrapper
        simply delegates and is safe (idempotent). A DeprecationWarning is emitted
        so callers can migrate away from this method.
        """
        warnings.warn(
            "connect_to_neo4j is deprecated; the session manager handles connections.",
            DeprecationWarning,
            stacklevel=2,
        )
        # Ensure the session manager establishes a connection if none exists
        self.session_manager.ensure_connection()

    async def discover_subscriptions(
        self, *args: Any, **kwargs: Any
    ) -> List[Dict[str, Any]]:
        """
        Deprecated: Use discovery_service.discover_subscriptions instead.
        """
        warnings.warn(
            "AzureTenantGrapher.discover_subscriptions is deprecated. Use discovery_service.discover_subscriptions.",
            DeprecationWarning,
            stacklevel=2,
        )
        return await self.discovery_service.discover_subscriptions(*args, **kwargs)

    async def discover_resources_in_subscription(
        self, subscription_id: str, *args: Any, **kwargs: Any
    ) -> List[Dict[str, Any]]:
        """
        Deprecated: Use discovery_service.discover_resources_in_subscription instead.
        """
        warnings.warn(
            "AzureTenantGrapher.discover_resources_in_subscription is deprecated. Use discovery_service.discover_resources_in_subscription.",
            DeprecationWarning,
            stacklevel=2,
        )
        return await self.discovery_service.discover_resources_in_subscription(
            subscription_id, *args, **kwargs
        )

    async def generate_tenant_specification(self) -> None:
        """
        Generate a comprehensive tenant specification using the composed service.
        """
        try:
            tenant_id_suffix = (
                self.config.tenant_id[:8] if self.config.tenant_id else "unknown"
            )
            spec_filename = f"azure_tenant_specification_{tenant_id_suffix}.md"
            spec_path = os.path.join(os.getcwd(), spec_filename)
            await self.specification_service.generate_specification(spec_path)
            logger.info(f"✅ Tenant specification generated: {spec_path}")
        except Exception:
            logger.exception("Error generating tenant specification")

    # Legacy direct Neo4j node creation removed; handled by services.

    # Deprecated batch wrapper removed (batch processing is deprecated)

    # Legacy async LLM pool processing removed; handled by services.

    async def build_graph(
        self, progress_callback: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Orchestrate Azure tenant graph building using composed services.

        Returns:
            Dict: Summary of the graph building process
        """
        logger.info(
            "🚀 Starting Azure Tenant Graph building process (refactored coordinator)"
        )

        try:
            # 1. Discover subscriptions
            subscriptions = await self.discovery_service.discover_subscriptions()
            if not subscriptions:
                logger.warning("⚠️ No subscriptions found in tenant")
                return {"subscriptions": 0, "resources": 0, "success": False}

            # 2. Discover resources in all subscriptions
            all_resources: List[Dict[str, Any]] = []
            for subscription in subscriptions:
                try:
                    resources = (
                        await self.discovery_service.discover_resources_in_subscription(
                            subscription["id"]
                        )
                    )
                    all_resources.extend(resources)
                except Exception:
                    logger.exception(
                        f"Error discovering resources for subscription {subscription['id']}"
                    )
                    continue

            # 2.1. Pre-run in-memory de-duplication (Phase 1 efficiency improvement)
            logger.info(f"🗂️  Processing {len(all_resources)} discovered resources")
            id_map: Dict[str, Dict[str, Any]] = {}
            for r in all_resources:
                rid = r.get("id")
                if rid:
                    id_map[rid] = r  # keep last occurrence
            
            original_count = len(all_resources)
            all_resources = list(id_map.values())
            dedupe_count = original_count - len(all_resources)
            if dedupe_count > 0:
                logger.info(f"🗂️  De-duplicated list → {len(all_resources)} unique IDs (removed {dedupe_count} duplicates)")
            else:
                logger.info(f"🗂️  De-duplicated list → {len(all_resources)} unique IDs")

            # 3. Process resources
            with self.session_manager:
                stats = await self.processing_service.process_resources(
                    all_resources, progress_callback=progress_callback
                )

            # 4. Return stats as dict (back-compat)
            result = stats.to_dict()
            result["subscriptions"] = len(subscriptions)
            result["success"] = True
            return result

        except Exception as e:
            logger.exception("Error during graph building")
            return {
                "success": False,
                "subscriptions": 0,
                "total_resources": 0,
                "successful_resources": 0,
                "failed_resources": 0,
                "success_rate": 0.0,
                "error": str(e),
            }

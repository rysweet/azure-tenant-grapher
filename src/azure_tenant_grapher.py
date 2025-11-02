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
from .llm_descriptions import create_llm_generator
from .utils.neo4j_startup import ensure_neo4j_running

logger = logging.getLogger(__name__)

# (Removed duplicate and unused _maybe_run_migrations functions)


class AzureTenantGrapher:
    """
    Coordinator for Azure tenant resource discovery and graph building.
    Composes AzureDiscoveryService, ResourceProcessingService, and TenantSpecificationService.
    """

    def __init__(self, config: AzureTenantGrapherConfig) -> None:
        """
        Initialize the Azure Tenant Grapher coordinator.
        """

        self.config = config

        # Compose services per refactoring plan
        if config.processing.auto_start_container:
            ensure_neo4j_running()

        # Run migrations early if enabled (guarded for test compatibility)
        # Only run if ENABLE_MIGRATIONS is set, and not during test runs
        if os.environ.get("ENABLE_MIGRATIONS", "false").lower() in (
            "true",
            "1",
        ) and not os.environ.get("PYTEST_CURRENT_TEST"):
            try:
                from .migration_runner import run_pending_migrations

                run_pending_migrations()
            except Exception:
                logger.warning(
                    "Migration runner failed or unavailable; skipping migrations."
                )
        from .services.aad_graph_service import AADGraphService
        from .services.azure_discovery_service import AzureDiscoveryService
        from .services.resource_processing_service import ResourceProcessingService
        from .services.tenant_specification_service import TenantSpecificationService
        from .utils.session_manager import Neo4jSessionManager

        self.session_manager = Neo4jSessionManager(config.neo4j)
        self.discovery_service = AzureDiscoveryService(config)

        # Create AAD Graph Service if enabled
        aad_graph_service = None
        if config.processing.enable_aad_import:
            try:
                aad_graph_service = AADGraphService()
                logger.info("AAD Graph Service initialized for identity import")
            except Exception as e:
                logger.warning(f"Failed to initialize AAD Graph Service: {e}")

        self.processing_service = ResourceProcessingService(
            self.session_manager,
            create_llm_generator() if config.azure_openai.is_configured() else None,
            config.processing,
            aad_graph_service=aad_graph_service,
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

    async def generate_tenant_specification(
        self, domain_name: Optional[str] = None
    ) -> None:
        """
        Generate a comprehensive tenant specification using the composed service.

        Args:
            domain_name: Optional domain name to use for all entities that require one (e.g., user accounts).
        """
        try:
            tenant_id_suffix = (
                self.config.tenant_id[:8] if self.config.tenant_id else "unknown"
            )
            spec_filename = f"azure_tenant_specification_{tenant_id_suffix}.md"
            spec_path = os.path.join(os.getcwd(), spec_filename)
            # Propagate domain_name if supported by the specification service
            await self.specification_service.generate_specification(
                spec_path, domain_name=domain_name
            )
            logger.info(f"✅ Tenant specification generated: {spec_path}")
        except Exception:
            logger.exception("Error generating tenant specification")

    # Legacy direct Neo4j node creation removed; handled by services.

    # Deprecated batch wrapper removed (batch processing is deprecated)

    # Legacy async LLM pool processing removed; handled by services.

    async def build_graph(
        self,
        progress_callback: Optional[Any] = None,
        force_rebuild_edges: bool = False,
        filter_config: Optional[Any] = None,
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
            subscriptions = await self.discovery_service.discover_subscriptions(
                filter_config=filter_config
            )
            if not subscriptions:
                logger.warning("⚠️ No subscriptions found in tenant")
                return {"subscriptions": 0, "resources": 0, "success": False}

            # 2. Discover resources in all subscriptions
            all_resources: List[Dict[str, Any]] = []
            for subscription in subscriptions:
                try:
                    resources = (
                        await self.discovery_service.discover_resources_in_subscription(
                            subscription["id"], filter_config=filter_config
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
                logger.info(
                    f"🗂️  De-duplicated list → {len(all_resources)} unique IDs (removed {dedupe_count} duplicates)"
                )
            else:
                logger.info(f"🗂️  De-duplicated list → {len(all_resources)} unique IDs")

            # Enforce resource_limit if set in config
            resource_limit = getattr(self.config.processing, "resource_limit", None)
            if resource_limit:
                logger.info(
                    f"🔢 Applying resource_limit: {resource_limit} (before: {len(all_resources)})"
                )
                all_resources = all_resources[:resource_limit]
                logger.info(
                    f"🔢 Resource list truncated to {len(all_resources)} items due to resource_limit"
                )
            logger.info(
                f"[DEBUG][BUILD_GRAPH] Completed resource discovery and deduplication. Resource count: {len(all_resources)}"
            )

            # 3. Enrich with Entra ID identity data
            logger.info("=" * 70)
            logger.info("Enriching with Entra ID (Azure AD) identity data...")
            logger.info("=" * 70)

            try:
                # Fetch service principals
                service_principals = await self.aad_graph.get_service_principals()
                logger.info(f"Fetched {len(service_principals)} service principals")

                # Convert service principals to resource format and add to all_resources
                for sp in service_principals:
                    sp_resource = {
                        "id": f"/servicePrincipals/{sp['id']}",
                        "name": sp.get("displayName", sp['id']),
                        "type": "Microsoft.Graph/servicePrincipals",
                        "properties": sp,
                        "subscription_id": subscriptions[0]["id"] if subscriptions else "",
                        "resource_group": None,  # Service principals are tenant-level
                        "location": "global",
                        "tags": {},
                    }
                    all_resources.append(sp_resource)

                logger.info(f"Added {len(service_principals)} service principals to processing queue")

            except Exception as e:
                logger.warning(f"Failed to fetch service principals: {e}")
                logger.warning("Continuing without service principal enrichment")

            # 4. Process resources
            with self.session_manager:
                if force_rebuild_edges:
                    logger.info(
                        "🔄 Forcing re-evaluation of all relationships/edges for existing resources in database."
                    )

                    # Fetch existing resources from database (preserving LLM descriptions)
                    logger.info("📂 Fetching existing resources from database...")
                    existing_resources = []

                    with self.session_manager.session() as session:
                        result = session.run("""
                            MATCH (r:Resource)
                            RETURN r {
                                .id, .name, .type, .location, .resource_group,
                                .subscription_id, .llm_description, .*
                            } as resource
                            ORDER BY r.name
                        """)

                        for record in result:
                            resource_data = dict(record["resource"])
                            existing_resources.append(resource_data)

                    if not existing_resources:
                        logger.warning(
                            "⚠️ No existing resources found in database for edge rebuild"
                        )
                        return {"subscriptions": 0, "resources": 0, "success": False}

                    logger.info(
                        f"📂 Found {len(existing_resources)} existing resources in database"
                    )

                    # Create a processor instance for database operations
                    processor = self.processing_service.processor_factory(
                        self.session_manager,
                        self.processing_service.llm_generator,
                        getattr(self.config.processing, "resource_limit", None),
                    )

                    # Clear existing non-containment relationships first
                    logger.info("🧹 Clearing existing non-containment relationships...")
                    with self.session_manager.session() as session:
                        # Keep CONTAINS relationships but remove others that will be rebuilt
                        session.run("""
                            MATCH (r:Resource)-[rel]->(target)
                            WHERE type(rel) <> 'CONTAINS'
                            DELETE rel
                        """)

                    # Re-run relationship rules for all existing resources
                    for i, resource in enumerate(existing_resources):
                        if progress_callback:
                            progress_callback(
                                processed=i + 1,
                                total=len(existing_resources),
                                successful=i + 1,
                                failed=0,
                                skipped=0,
                                llm_generated=0,
                                llm_skipped=0,
                            )

                        logger.debug(
                            f"🔄 Rebuilding edges for resource {i + 1}/{len(existing_resources)}: {resource.get('name', 'Unknown')}"
                        )

                        # Re-emit relationships (but not containment - that's preserved)
                        from src.relationship_rules import ALL_RELATIONSHIP_RULES

                        for rule in ALL_RELATIONSHIP_RULES:
                            try:
                                if rule.applies(resource):
                                    rule.emit(resource, processor.db_ops)
                            except Exception as e:
                                logger.exception(
                                    f"Relationship rule {rule.__class__.__name__} failed during rebuild: {e}"
                                )

                    logger.info(
                        f"✅ Completed rebuilding edges for {len(existing_resources)} existing resources."
                    )

                    # Create a simple stats object for rebuild mode - don't run full processing
                    from src.resource_processor import ProcessingStats

                    stats = ProcessingStats()
                    stats.total_resources = len(existing_resources)
                    stats.processed = len(existing_resources)
                    stats.successful = len(existing_resources)
                    stats.failed = 0
                    stats.skipped = 0
                    stats.llm_generated = 0
                    stats.llm_skipped = 0
                else:
                    stats = await self.processing_service.process_resources(
                        all_resources,
                        progress_callback=progress_callback,
                        filter_config=filter_config,
                    )
                    logger.info(
                        f"[DEBUG][BUILD_GRAPH] Completed resource processing. Stats: {stats.to_dict() if hasattr(stats, 'to_dict') else stats}"
                    )

            # 4. Return stats as dict (back-compat)
            result = stats.to_dict()
            result["subscriptions"] = len(subscriptions)
            result["success"] = True
            logger.info(f"[DEBUG][BUILD_GRAPH] Returning build result: {result}")
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

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

        # Create AAD Graph Service if enabled - store as instance attribute
        self.aad_graph_service = None
        if config.processing.enable_aad_import:
            try:
                self.aad_graph_service = AADGraphService()
                logger.info("AAD Graph Service initialized for identity import")
            except Exception as e:
                logger.warning(str(f"Failed to initialize AAD Graph Service: {e}"))

        self.processing_service = ResourceProcessingService(
            self.session_manager,
            create_llm_generator() if config.azure_openai.is_configured() else None,
            config.processing,
            aad_graph_service=self.aad_graph_service,
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
            logger.info(str(f"✅ Tenant specification generated: {spec_path}"))
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
            resource_limit = getattr(self.config.processing, "resource_limit", None)

            for subscription in subscriptions:
                try:
                    resources = (
                        await self.discovery_service.discover_resources_in_subscription(
                            subscription["id"],
                            filter_config=filter_config,
                            resource_limit=resource_limit,
                        )
                    )
                    all_resources.extend(resources)
                except Exception:
                    logger.exception(
                        f"Error discovering resources for subscription {subscription['id']}"
                    )
                    continue

            # 2.1. Pre-run in-memory de-duplication (Phase 1 efficiency improvement)
            logger.info(str(f"🗂️  Processing {len(all_resources)} discovered resources"))
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
                logger.info(
                    str(f"🗂️  De-duplicated list → {len(all_resources)} unique IDs")
                )

            # Apply global resource_limit as defensive check (primary limiting happens per-subscription)
            if resource_limit and len(all_resources) > resource_limit:
                logger.info(
                    f"🔢 Applying global resource_limit (defensive check): {resource_limit} (before: {len(all_resources)})"
                )
                all_resources = all_resources[:resource_limit]
                logger.info(
                    f"🔢 Global resource list truncated to {len(all_resources)} items"
                )
            logger.info(
                f"[DEBUG][BUILD_GRAPH] Completed resource discovery and deduplication. Resource count: {len(all_resources)}"
            )

            # 2.5. Collect referenced resources (if filtering is active)
            if (
                filter_config
                and filter_config.has_filters()
                and filter_config.include_referenced_resources
            ):
                logger.info("=" * 70)
                logger.info("Collecting referenced resources for filtered import...")
                logger.info("=" * 70)

                from src.services.managed_identity_resolver import (
                    ManagedIdentityResolver,
                )
                from src.services.referenced_resource_collector import (
                    ReferencedResourceCollector,
                )

                collector = ReferencedResourceCollector(
                    discovery_service=self.discovery_service,
                    identity_resolver=ManagedIdentityResolver(
                        tenant_seed=self.config.tenant_id
                    ),
                    aad_graph_service=self.aad_graph_service,
                )

                try:
                    referenced_resources = await collector.collect_referenced_resources(
                        filtered_resources=all_resources, filter_config=filter_config
                    )

                    if referenced_resources:
                        logger.info(
                            f"✅ Adding {len(referenced_resources)} referenced resources to filtered import"
                        )
                        all_resources.extend(referenced_resources)
                        logger.info(
                            f"Total resources after referenced resource inclusion: {len(all_resources)}"
                        )
                    else:
                        logger.info("No additional referenced resources found")
                except Exception as e:
                    logger.exception(f"Error collecting referenced resources: {e}")
                    logger.warning("Continuing without referenced resource inclusion")

            # 3. Enrich with Entra ID identity data
            if self.aad_graph_service:
                logger.info("=" * 70)
                logger.info("Enriching with Entra ID (Azure AD) identity data...")
                logger.info("=" * 70)

                try:
                    # Fetch service principals
                    logger.info(
                        "Fetching service principals from Microsoft Graph API..."
                    )
                    service_principals = (
                        await self.aad_graph_service.get_service_principals()
                    )
                    logger.info(
                        f"Successfully fetched {len(service_principals)} service principals from Graph API"
                    )

                    # Convert service principals to resource format and add to all_resources
                    sp_count_before = len(all_resources)
                    for sp in service_principals:
                        sp_resource = {
                            "id": f"/servicePrincipals/{sp['id']}",
                            "name": sp.get("displayName", sp["id"]),
                            "type": "Microsoft.Graph/servicePrincipals",
                            "properties": sp,
                            "subscription_id": subscriptions[0]["id"]
                            if subscriptions
                            else "",
                            "resource_group": None,  # Service principals are tenant-level
                            "location": "global",
                            "tags": {},
                        }
                        all_resources.append(sp_resource)
                        logger.debug(
                            f"Added service principal: {sp_resource['name']} (ID: {sp['id']})"
                        )

                    logger.info(
                        f"Successfully added {len(service_principals)} service principals to processing queue"
                    )
                    logger.info(
                        f"Total resources after AAD enrichment: {len(all_resources)} (was {sp_count_before})"
                    )

                except Exception as e:
                    logger.exception(
                        f"Failed to fetch service principals from Graph API: {e}"
                    )
                    logger.warning("Continuing without service principal enrichment")
            else:
                logger.info(
                    "AAD enrichment disabled (enable_aad_import=False or AAD service failed to initialize)"
                )
                logger.info("Skipping service principal discovery")

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
                        result = session.run("""  # type: ignore[arg-type]
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
                        getattr(self.config.processing, "max_retries", 3),
                        self.config.tenant_id,
                    )

                    # Clear existing non-containment relationships first
                    logger.info("🧹 Clearing existing non-containment relationships...")
                    with self.session_manager.session() as session:
                        # Keep CONTAINS relationships but remove others that will be rebuilt
                        session.run("""  # type: ignore[arg-type]
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
                        tenant_id=self.config.tenant_id,
                    )
                    logger.info(
                        f"[DEBUG][BUILD_GRAPH] Completed resource processing. Stats: {stats.to_dict() if hasattr(stats, 'to_dict') else stats}"
                    )

            # 4. Update graph metadata with current version (Issue #706)
            try:
                from datetime import datetime

                from .version_tracking.detector import VersionDetector
                from .version_tracking.metadata import GraphMetadataService

                detector = VersionDetector()
                current_version = detector.read_semaphore_version()

                if current_version:
                    metadata_service = GraphMetadataService(self.session_manager)
                    timestamp = datetime.now().isoformat()
                    metadata_service.write_metadata(
                        version=current_version, last_scan_at=timestamp
                    )
                    logger.info(
                        f"✅ Updated graph metadata: version={current_version}, last_scan={timestamp}"
                    )
                else:
                    logger.warning(
                        "⚠️ Could not read version from semaphore file - metadata not updated"
                    )
            except Exception as e:
                logger.warning(f"Failed to update graph metadata: {e}")

            # 5. Return stats as dict (back-compat)
            result = stats.to_dict()
            result["subscriptions"] = len(subscriptions)
            result["success"] = True
            logger.info(str(f"[DEBUG][BUILD_GRAPH] Returning build result: {result}"))
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

"""
Azure Tenant Resource Grapher

This module provides functionality to walk Azure tenant resources and build
a Neo4j graph database of those resources and their relationships.
"""

import logging
import os
from typing import Any, Dict, List, Optional

from azure.identity import DefaultAzureCredential
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.resource.subscriptions import SubscriptionClient
from dotenv import load_dotenv
from neo4j import Driver, GraphDatabase

from .config_manager import AzureTenantGrapherConfig
from .container_manager import Neo4jContainerManager
from .llm_descriptions import create_llm_generator
from .resource_processor import create_resource_processor

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


class AzureTenantGrapher:
    """Main class for Azure tenant resource discovery and graph building."""

    def __init__(self, config: AzureTenantGrapherConfig) -> None:
        """
        Initialize the Azure Tenant Grapher.

        Args:
            config: Configuration object containing all settings
        """
        self.config = config
        self.credential = DefaultAzureCredential()

        # Neo4j connection
        self.driver: Optional[Driver] = None
        self.subscriptions: List[Dict[str, Any]] = []

        # Container management
        self.container_manager = (
            Neo4jContainerManager() if config.processing.auto_start_container else None
        )

        # Initialize LLM generator for descriptions
        if config.azure_openai.is_configured():
            try:
                self.llm_generator = create_llm_generator()
                logger.info("🤖 LLM description generator initialized successfully")
            except Exception as e:
                logger.error(f"❌ Failed to initialize LLM generator: {e}")
                self.llm_generator = None
        else:
            self.llm_generator = None
            logger.info("INFO: Azure OpenAI not configured - LLM descriptions disabled")

        # Log configuration summary
        self.config.log_configuration_summary()

    def connect_to_neo4j(self) -> None:
        """Establish connection to Neo4j database, starting container if needed."""
        # Try to start Neo4j container if auto-start is enabled
        if self.container_manager and self.config.processing.auto_start_container:
            logger.info("🔍 Checking Neo4j container status...")
            if not self.container_manager.is_neo4j_container_running():
                logger.info("🚀 Neo4j container not running, attempting to start...")
                if not self.container_manager.setup_neo4j():
                    logger.error("❌ Failed to start Neo4j container")
                    raise Exception("Could not start Neo4j container")
            else:
                logger.info("✅ Neo4j container is already running")

        try:
            self.driver = GraphDatabase.driver(
                self.config.neo4j.uri,
                auth=(self.config.neo4j.user, self.config.neo4j.password),
            )

            # Test the connection
            with self.driver.session() as session:
                session.run("RETURN 1")

            logger.info(f"✅ Connected to Neo4j at {self.config.neo4j.uri}")
        except Exception as e:
            logger.error(f"❌ Failed to connect to Neo4j: {e}")
            if self.container_manager:
                logs = self.container_manager.get_container_logs(20)
                if logs:
                    logger.error(f"Recent Neo4j container logs:\n{logs}")
            raise

    def close_neo4j_connection(self) -> None:
        """Close Neo4j database connection."""
        if self.driver:
            self.driver.close()
            logger.info("🔌 Neo4j connection closed")

    async def discover_subscriptions(self) -> List[Dict[str, Any]]:
        """
        Discover all subscriptions in the tenant.

        Returns:
            List of subscription dictionaries
        """
        logger.info(f"🔍 Discovering subscriptions in tenant {self.config.tenant_id}")

        subscription_client = SubscriptionClient(self.credential)
        subscriptions = []

        try:
            for subscription in subscription_client.subscriptions.list():
                subscription_dict = {
                    "id": subscription.subscription_id,
                    "display_name": subscription.display_name,
                    "state": subscription.state if subscription.state else None,
                    "tenant_id": subscription.tenant_id,
                }
                subscriptions.append(subscription_dict)
                logger.info(
                    f"📋 Found subscription: {subscription.display_name} ({subscription.subscription_id})"
                )

        except Exception as e:
            logger.error(f"❌ Error discovering subscriptions: {e}")
            raise

        self.subscriptions = subscriptions
        logger.info(f"✅ Discovered {len(subscriptions)} subscriptions total")
        return subscriptions

    async def discover_resources_in_subscription(
        self, subscription_id: str
    ) -> List[Dict[str, Any]]:
        """
        Discover all resources in a specific subscription.

        Args:
            subscription_id: Azure subscription ID

        Returns:
            List of resource dictionaries
        """
        logger.info(f"🔍 Discovering resources in subscription {subscription_id}")

        resource_client = ResourceManagementClient(self.credential, subscription_id)
        resources = []

        try:
            for resource in resource_client.resources.list():
                resource_dict = {
                    "id": resource.id,
                    "name": resource.name,
                    "type": resource.type,
                    "location": resource.location,
                    "resource_group": (
                        resource.id.split("/")[4]
                        if len(resource.id.split("/")) > 4
                        else None
                    ),
                    "subscription_id": subscription_id,
                    "tags": Dict[str, Any](resource.tags) if resource.tags else {},
                    "kind": getattr(resource, "kind", None),
                    "sku": getattr(resource, "sku", None),
                }
                resources.append(resource_dict)

        except Exception as e:
            logger.error(
                f"❌ Error discovering resources in subscription {subscription_id}: {e}"
            )

        logger.info(
            f"✅ Found {len(resources)} resources in subscription {subscription_id}"
        )
        return resources

    async def generate_tenant_specification(self) -> None:
        """Generate a comprehensive tenant specification using LLM."""
        if not self.llm_generator:
            logger.warning(
                "⚠️ LLM generator not available, skipping tenant specification generation"
            )
            return

        logger.info("🤖 Generating comprehensive tenant specification...")

        try:
            # Connect to Neo4j to get graph data
            if not self.driver:
                self.connect_to_neo4j()

            if not self.driver:
                raise RuntimeError("Failed to establish database connection")

            with self.driver.session() as session:
                # Get all resources
                resources_result = session.run(
                    """
                    MATCH (r:Resource)
                    RETURN r.id as id, r.name as name, r.type as type,
                           r.location as location, r.resource_group as resource_group,
                           r.subscription_id as subscription_id, r.tags as tags,
                           r.llm_description as llm_description
                """
                )
                resources = [dict(record) for record in resources_result]

                # Get all relationships
                relationships_result = session.run(
                    """
                    MATCH (a)-[r]->(b)
                    RETURN type(r) as relationship_type,
                           labels(a)[0] as source_type,
                           labels(b)[0] as target_type,
                           a.name as source_name,
                           b.name as target_name
                """
                )
                relationships = [dict(record) for record in relationships_result]

            # Generate the specification
            tenant_id_suffix = (
                self.config.tenant_id[:8] if self.config.tenant_id else "unknown"
            )
            spec_filename = f"azure_tenant_specification_{tenant_id_suffix}.md"
            spec_path = os.path.join(os.getcwd(), spec_filename)

            generated_path = await self.llm_generator.generate_tenant_specification(
                resources, relationships, spec_path
            )

            logger.info(f"✅ Tenant specification generated: {generated_path}")

        except Exception as e:
            logger.error(f"❌ Error generating tenant specification: {e}")
        finally:
            self.close_neo4j_connection()

    def create_subscription_node(
        self, session: Any, subscription: Dict[str, Any]
    ) -> None:
        """Create a subscription node in Neo4j."""
        query = """
        MERGE (s:Subscription {id: $id})
        SET s.display_name = $display_name,
            s.state = $state,
            s.tenant_id = $tenant_id,
            s.updated_at = datetime()
        """
        session.run(query, subscription)

    async def process_resources_with_enhanced_handling(
        self, resources: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Process resources using the new modular resource processor.

        Args:
            resources: List[Any] of resources to process

        Returns:
            Dict: Processing statistics
        """
        if not resources:
            logger.info("INFO: No resources to process")
            return {
                "total_resources": 0,
                "successful": 0,
                "failed": 0,
                "success_rate": 100.0,
            }

        logger.info(
            f"🔄 Starting enhanced resource processing for {len(resources)} resources"
        )

        try:
            # Connect to Neo4j
            if not self.driver:
                self.connect_to_neo4j()

            if not self.driver:
                raise RuntimeError("Failed to establish database connection")

            with self.driver.session() as session:
                # Create resource processor with our configuration
                processor = create_resource_processor(
                    session=session,
                    llm_generator=self.llm_generator,
                    resource_limit=self.config.processing.resource_limit,
                )

                # Process resources in parallel batches
                stats = await processor.process_resources_batch(
                    resources=resources, batch_size=self.config.processing.batch_size
                )

                # Convert ProcessingStats to dict for backward compatibility
                return {
                    "total_resources": stats.total_resources,
                    "successful": stats.successful,
                    "failed": stats.failed,
                    "skipped": stats.skipped,
                    "llm_generated": stats.llm_generated,
                    "llm_skipped": stats.llm_skipped,
                    "success_rate": stats.success_rate,
                }

        except Exception as e:
            logger.error(f"❌ Error during enhanced resource processing: {e}")
            raise
        finally:
            self.close_neo4j_connection()

    async def build_graph(self) -> Dict[str, Any]:
        """
        Main method to build the complete graph of Azure tenant resources.

        Returns:
            Dict: Summary of the graph building process
        """
        logger.info("🚀 Starting Azure Tenant Graph building process")

        try:
            # Connect to Neo4j
            if not self.driver:
                self.connect_to_neo4j()

            if not self.driver:
                raise RuntimeError("Failed to establish database connection")

            # Discover subscriptions
            subscriptions = await self.discover_subscriptions()

            if not subscriptions:
                logger.warning("⚠️ No subscriptions found in tenant")
                return {"subscriptions": 0, "resources": 0, "success": False}

            # Process each subscription
            all_resources = []

            with self.driver.session() as session:
                # Create subscription nodes
                for subscription in subscriptions:
                    logger.info(
                        f"📋 Creating subscription node: {subscription['display_name']}"
                    )
                    self.create_subscription_node(session, subscription)

                # Discover resources in all subscriptions
                for subscription in subscriptions:
                    subscription_id = subscription["id"]
                    subscription_name = subscription["display_name"]

                    logger.info(f"🔍 Processing subscription: {subscription_name}")

                    try:
                        resources = await self.discover_resources_in_subscription(
                            subscription_id
                        )
                        all_resources.extend(resources)

                        logger.info(
                            f"✅ Added {len(resources)} resources from {subscription_name}"
                        )

                    except Exception as e:
                        logger.error(
                            f"❌ Error processing subscription {subscription_name}: {e}"
                        )
                        continue

            # Process all resources with enhanced handling
            if all_resources:
                logger.info(
                    f"🔄 Starting processing of {len(all_resources)} total resources"
                )
                processing_stats = await self.process_resources_with_enhanced_handling(
                    all_resources
                )

                # Final summary
                return {
                    "subscriptions": len(subscriptions),
                    "total_resources": processing_stats["total_resources"],
                    "successful_resources": processing_stats["successful"],
                    "failed_resources": processing_stats["failed"],
                    "skipped_resources": processing_stats.get("skipped", 0),
                    "llm_descriptions_generated": processing_stats.get(
                        "llm_generated", 0
                    ),
                    "success_rate": processing_stats["success_rate"],
                    "success": True,
                }
            else:
                logger.warning("⚠️ No resources found in any subscription")
                return {
                    "subscriptions": len(subscriptions),
                    "total_resources": 0,
                    "successful_resources": 0,
                    "failed_resources": 0,
                    "success_rate": 100.0,
                    "success": True,
                }

        except Exception as e:
            logger.error(f"❌ Error during graph building: {e}")
            return {
                "success": False,
                "subscriptions": 0,
                "total_resources": 0,
                "successful_resources": 0,
                "failed_resources": 0,
                "success_rate": 0.0,
                "error": str(e),
            }

        finally:
            self.close_neo4j_connection()

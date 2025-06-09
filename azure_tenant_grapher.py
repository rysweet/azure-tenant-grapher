"""
Azure Tenant Resource Grapher

This module provides functionality to walk Azure tenant resources and build
a Neo4j graph database of those resources and their relationships.
"""

import asyncio
import logging
import os
from typing import Dict, List, Optional
import click
from dotenv import load_dotenv

from azure.identity import DefaultAzureCredential
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.resource.subscriptions import SubscriptionClient

from neo4j import GraphDatabase
import colorlog

from container_manager import Neo4jContainerManager
from graph_visualizer import GraphVisualizer
from llm_descriptions import create_llm_generator, AzureLLMDescriptionGenerator

# Load environment variables
load_dotenv()

# Configure logging
handler = colorlog.StreamHandler()
handler.setFormatter(colorlog.ColoredFormatter(
    '%(log_color)s%(levelname)s:%(name)s:%(message)s'
))

logger = colorlog.getLogger(__name__)
logger.addHandler(handler)
logger.setLevel(logging.INFO)


class AzureTenantGrapher:
    """Main class for Azure tenant resource discovery and graph building."""
    
    def __init__(self, tenant_id: str, neo4j_uri: str = None, neo4j_user: str = None, neo4j_password: str = None, auto_start_container: bool = True):
        """
        Initialize the Azure Tenant Grapher.
        
        Args:
            tenant_id: Azure tenant ID
            neo4j_uri: Neo4j database URI
            neo4j_user: Neo4j username
            neo4j_password: Neo4j password
            auto_start_container: Whether to automatically start Neo4j container if needed
        """
        self.tenant_id = tenant_id
        self.credential = DefaultAzureCredential()
        self.auto_start_container = auto_start_container
        
        # Neo4j configuration
        self.neo4j_uri = neo4j_uri or os.getenv('NEO4J_URI', 'bolt://localhost:7688')
        self.neo4j_user = neo4j_user or os.getenv('NEO4J_USER', 'neo4j')
        self.neo4j_password = neo4j_password or os.getenv('NEO4J_PASSWORD', 'azure-grapher-2024')        
        self.driver = None
        self.subscriptions = []
        self.container_manager = Neo4jContainerManager() if auto_start_container else None
        
        # Initialize LLM generator for descriptions
        self.llm_generator = create_llm_generator()
        self.tenant_specification_path = None
        if self.llm_generator:
            logger.info("LLM description generator initialized successfully")
        else:
            logger.warning("LLM description generator not available - descriptions will be skipped")
        
    def connect_to_neo4j(self):
        """Establish connection to Neo4j database, starting container if needed."""
        # Try to start Neo4j container if auto-start is enabled
        if self.container_manager and self.auto_start_container:
            logger.info("Checking Neo4j container status...")
            if not self.container_manager.is_neo4j_container_running():
                logger.info("Neo4j container not running, attempting to start...")
                if not self.container_manager.setup_neo4j():
                    logger.error("Failed to start Neo4j container")
                    raise Exception("Could not start Neo4j container")
            else:
                logger.info("Neo4j container is already running")
        
        try:
            self.driver = GraphDatabase.driver(
                self.neo4j_uri,
                auth=(self.neo4j_user, self.neo4j_password)
            )
            
            # Test the connection
            with self.driver.session() as session:
                session.run("RETURN 1")
            
            logger.info(f"Connected to Neo4j at {self.neo4j_uri}")
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            if self.container_manager:
                logs = self.container_manager.get_container_logs(20)
                if logs:
                    logger.error(f"Recent Neo4j container logs:\n{logs}")
            raise
    
    def close_neo4j_connection(self):
        """Close Neo4j database connection."""
        if self.driver:
            self.driver.close()
            logger.info("Neo4j connection closed")
    
    async def discover_subscriptions(self) -> List[Dict]:
        """
        Discover all subscriptions in the tenant.
        
        Returns:
            List of subscription dictionaries
        """
        logger.info(f"Discovering subscriptions in tenant {self.tenant_id}")
        
        subscription_client = SubscriptionClient(self.credential)
        subscriptions = []
        
        try:
            for subscription in subscription_client.subscriptions.list():
                subscription_dict = {
                    'id': subscription.subscription_id,
                    'display_name': subscription.display_name,
                    'state': subscription.state if subscription.state else None,
                    'tenant_id': subscription.tenant_id
                }
                subscriptions.append(subscription_dict)
                logger.info(f"Found subscription: {subscription.display_name} ({subscription.subscription_id})")
                
        except Exception as e:
            logger.error(f"Error discovering subscriptions: {e}")
            raise
            
        self.subscriptions = subscriptions
        return subscriptions
    
    async def discover_resources_in_subscription(self, subscription_id: str) -> List[Dict]:
        """
        Discover all resources in a specific subscription.
        
        Args:
            subscription_id: Azure subscription ID
            
        Returns:
            List of resource dictionaries
        """
        logger.info(f"Discovering resources in subscription {subscription_id}")
        
        resource_client = ResourceManagementClient(self.credential, subscription_id)
        resources = []
        
        try:
            for resource in resource_client.resources.list():
                resource_dict = {
                    'id': resource.id,
                    'name': resource.name,
                    'type': resource.type,
                    'location': resource.location,
                    'resource_group': resource.id.split('/')[4] if len(resource.id.split('/')) > 4 else None,
                    'subscription_id': subscription_id,
                    'tags': dict(resource.tags) if resource.tags else {},
                    'kind': getattr(resource, 'kind', None),
                    'sku': getattr(resource, 'sku', None),
                }
                resources.append(resource_dict)
                
        except Exception as e:
            logger.error(f"Error discovering resources in subscription {subscription_id}: {e}")
            
        logger.info(f"Found {len(resources)} resources in subscription {subscription_id}")
        return resources
    
    async def generate_tenant_specification(self):
        """Generate a comprehensive tenant specification using LLM."""
        if not self.llm_generator:
            logger.warning("LLM generator not available, skipping tenant specification generation")
            return
        
        logger.info("Generating comprehensive tenant specification...")
        
        try:
            # Connect to Neo4j to get graph data
            self.connect_to_neo4j()
            
            with self.driver.session() as session:
                # Get all resources
                resources_result = session.run("""
                    MATCH (r:Resource)
                    RETURN r.id as id, r.name as name, r.type as type, 
                           r.location as location, r.resource_group as resource_group,
                           r.subscription_id as subscription_id, r.tags as tags,
                           r.llm_description as llm_description
                """)
                resources = [dict(record) for record in resources_result]
                
                # Get all relationships
                relationships_result = session.run("""
                    MATCH (a)-[r]->(b)
                    RETURN type(r) as relationship_type, 
                           labels(a)[0] as source_type, 
                           labels(b)[0] as target_type,
                           a.name as source_name,
                           b.name as target_name
                """)
                relationships = [dict(record) for record in relationships_result]
            
            # Generate the specification
            spec_filename = f"azure_tenant_specification_{self.tenant_id[:8]}.md"
            spec_path = os.path.join(os.getcwd(), spec_filename)
            
            generated_path = await self.llm_generator.generate_tenant_specification(
                resources, relationships, spec_path
            )
            
            self.tenant_specification_path = generated_path
            logger.info(f"Tenant specification generated: {generated_path}")
            
        except Exception as e:
            logger.error(f"Error generating tenant specification: {e}")
        finally:
            self.close_neo4j_connection()
    
    async def add_llm_descriptions_to_resources(self, resources: List[Dict]) -> List[Dict]:
        """Add LLM-generated descriptions to resources."""
        if not self.llm_generator:
            logger.warning("⚠️ LLM generator not available, skipping description generation")
            return resources
        
        if not resources:
            logger.info("ℹ️ No resources provided for LLM description generation")
            return resources
        
        logger.info(f"🤖 Starting LLM description generation for {len(resources)} resources...")
        try:
            # Process resources in batches to get descriptions (the LLM module handles detailed logging)
            enhanced_resources = await self.llm_generator.process_resources_batch(resources, batch_size=3)
            logger.info(f"✅ LLM description generation completed for all {len(enhanced_resources)} resources")
            return enhanced_resources
        except Exception as e:
            logger.error(f"❌ Error during LLM description generation: {e}")
            logger.info("🔄 Continuing with resources without LLM descriptions...")
            return resources
    
    def create_subscription_node(self, session, subscription: Dict):
        """Create a subscription node in Neo4j."""
        query = """
        MERGE (s:Subscription {id: $id})
        SET s.display_name = $display_name,
            s.state = $state,
            s.tenant_id = $tenant_id
        """
        session.run(query, subscription)
    
    def create_resource_node(self, session, resource: Dict):
        """Create a resource node in Neo4j."""
        query = """
        MERGE (r:Resource {id: $id})
        SET r.name = $name,
            r.type = $type,
            r.location = $location,
            r.resource_group = $resource_group,
            r.subscription_id = $subscription_id,
            r.tags = $tags,
            r.kind = $kind,
            r.sku = $sku,
            r.llm_description = $llm_description
        """
        # Add LLM description if available
        resource_with_description = resource.copy()
        resource_with_description['llm_description'] = resource.get('llm_description', '')
        
        session.run(query, resource_with_description)
    
    def create_subscription_resource_relationship(self, session, subscription_id: str, resource_id: str):
        """Create relationship between subscription and resource."""
        query = """
        MATCH (s:Subscription {id: $subscription_id})
        MATCH (r:Resource {id: $resource_id})
        MERGE (s)-[:CONTAINS]->(r)
        """
        session.run(query, subscription_id=subscription_id, resource_id=resource_id)
    
    def create_resource_group_relationships(self, session, resource: Dict):
        """Create resource group nodes and relationships."""
        if resource.get('resource_group'):
            rg_name = resource['resource_group']
            subscription_id = resource['subscription_id']
            
            # Create resource group node if it doesn't exist
            rg_query = """
            MERGE (rg:ResourceGroup {name: $rg_name, subscription_id: $subscription_id})
            SET rg.type = 'ResourceGroup'
            """
            session.run(rg_query, rg_name=rg_name, subscription_id=subscription_id)
            
            # Create relationship: Subscription CONTAINS ResourceGroup
            sub_rg_query = """
            MATCH (s:Subscription {id: $subscription_id})
            MATCH (rg:ResourceGroup {name: $rg_name, subscription_id: $subscription_id})
            MERGE (s)-[:CONTAINS]->(rg)
            """
            session.run(sub_rg_query, subscription_id=subscription_id, rg_name=rg_name)
            
            # Create relationship: ResourceGroup CONTAINS Resource
            rg_resource_query = """
            MATCH (rg:ResourceGroup {name: $rg_name, subscription_id: $subscription_id})
            MATCH (r:Resource {id: $resource_id})
            MERGE (rg)-[:CONTAINS]->(r)
            """
            session.run(rg_resource_query, rg_name=rg_name, subscription_id=subscription_id, resource_id=resource['id'])
    
    async def build_graph(self, generate_visualization: bool = False, visualization_path: str = None):
        """Build the complete Neo4j graph of Azure resources."""
        logger.info("Starting graph building process")
        
        # Connect to Neo4j
        self.connect_to_neo4j()
        
        try:
            # Discover subscriptions
            subscriptions = await self.discover_subscriptions()
            
            with self.driver.session() as session:
                # Create subscription nodes
                for subscription in subscriptions:
                    self.create_subscription_node(session, subscription)
                    logger.info(f"Created subscription node: {subscription['display_name']}")
                
                # Discover and create resource nodes for each subscription
                total_resources_processed = 0
                total_nodes_created = 0
                
                for sub_idx, subscription in enumerate(subscriptions, 1):
                    subscription_id = subscription['id']
                    subscription_name = subscription['display_name']
                    
                    logger.info(f"🔍 Processing subscription {sub_idx}/{len(subscriptions)}: {subscription_name}")
                    resources = await self.discover_resources_in_subscription(subscription_id)
                    logger.info(f"   Found {len(resources)} resources in {subscription_name}")
                    
                    if resources:
                        # Add LLM descriptions to resources for this subscription
                        logger.info(f"🤖 Generating LLM descriptions for {len(resources)} resources in {subscription_name}")
                        resources = await self.add_llm_descriptions_to_resources(resources)
                        
                        # Create nodes and relationships with progress tracking
                        logger.info(f"🔧 Creating graph nodes for resources in {subscription_name}")
                        nodes_created_for_sub = 0
                        
                        for res_idx, resource in enumerate(resources, 1):
                            resource_name = resource.get('name', 'Unknown')
                            resource_type = resource.get('type', 'Unknown')
                            
                            try:
                                self.create_resource_node(session, resource)
                                self.create_subscription_resource_relationship(session, subscription_id, resource['id'])
                                
                                # Create resource group relationships
                                self.create_resource_group_relationships(session, resource)
                                
                                nodes_created_for_sub += 1
                                total_nodes_created += 1
                                
                                # Log progress every 25 resources or for the last resource in subscription
                                if res_idx % 25 == 0 or res_idx == len(resources):
                                    logger.info(f"   📈 Subscription progress: {res_idx}/{len(resources)} resources ({(res_idx/len(resources))*100:.1f}%)")
                                
                            except Exception as e:
                                logger.error(f"❌ Failed to create graph entities for {resource_name} ({resource_type}): {str(e)}")
                        
                        total_resources_processed += len(resources)
                        logger.info(f"✅ Completed {subscription_name}: {nodes_created_for_sub}/{len(resources)} nodes created successfully")
                    else:
                        logger.info(f"ℹ️ No resources found in {subscription_name}")
                
                logger.info(f"🎉 All subscriptions processed!")
                logger.info(f"📊 Final summary: {total_nodes_created}/{total_resources_processed} resources successfully added to graph")
                
        except Exception as e:
            logger.error(f"Error building graph: {e}")
            raise
        finally:
            self.close_neo4j_connection()
        
        logger.info("Graph building completed successfully")
        
        # Generate tenant specification if LLM is available
        if self.llm_generator:
            await self.generate_tenant_specification()

        # Generate visualization if requested
        if generate_visualization:
            logger.info("Generating 3D graph visualization...")
            visualizer = GraphVisualizer(
                neo4j_uri=self.neo4j_uri,
                neo4j_user=self.neo4j_user,
                neo4j_password=self.neo4j_password
            )
            
            try:
                html_path = visualizer.generate_html_visualization(visualization_path, self.tenant_specification_path)

                logger.info(f"3D visualization generated: {html_path}")
                
                # Ask user if they want to open the visualization
                if click.confirm("Would you like to open the visualization in your browser?", default=True):
                    visualizer.open_visualization(html_path)
                    
            except Exception as e:
                logger.error(f"Error generating visualization: {e}")
            finally:
                visualizer.close()
    
    def visualize_graph(self):
        """Visualize the graph using GraphVisualizer."""
        logger.info("Visualizing the graph")
        visualizer = GraphVisualizer(self.neo4j_uri, self.neo4j_user, self.neo4j_password)
        visualizer.visualize()


@click.command()
@click.option('--tenant-id', required=True, help='Azure tenant ID')
@click.option('--neo4j-uri', default='bolt://localhost:7688', help='Neo4j URI')
@click.option('--neo4j-user', default='neo4j', help='Neo4j username')
@click.option('--neo4j-password', default='azure-grapher-2024', help='Neo4j password')
@click.option('--no-container', is_flag=True, help='Skip automatic container management')
@click.option('--container-only', is_flag=True, help='Only start Neo4j container, do not run grapher')
@click.option('--visualize', is_flag=True, help='Generate 3D graph visualization after building the graph')
@click.option('--visualization-path', help='Path where to save the visualization HTML file')
@click.option('--visualize-only', is_flag=True, help='Only generate visualization from existing graph data')
def main(tenant_id: str, neo4j_uri: str, neo4j_user: str, neo4j_password: str, no_container: bool, container_only: bool, visualize: bool, visualization_path: str, visualize_only: bool):
    """Azure Tenant Resource Grapher CLI."""
    logger.info(f"Starting Azure Tenant Resource Grapher for tenant: {tenant_id}")
    
    # Handle container-only mode
    if container_only:
        logger.info("Container-only mode: Starting Neo4j container")
        container_manager = Neo4jContainerManager()
        if container_manager.setup_neo4j():
            logger.info("Neo4j container started successfully!")
            logger.info(f"You can access Neo4j Browser at: http://localhost:7475")
            logger.info(f"Username: {neo4j_user}")
            logger.info(f"Password: {neo4j_password}")
        else:
            logger.error("Failed to start Neo4j container")
        return
    
    # Handle visualization-only mode
    if visualize_only:
        logger.info("Visualization-only mode: Generating 3D graph visualization from existing data")
        visualizer = GraphVisualizer(
            neo4j_uri=neo4j_uri,
            neo4j_user=neo4j_user,
            neo4j_password=neo4j_password
        )
        
        try:
            # In visualization-only mode, look for existing specification
            spec_path = None
            spec_pattern = f"azure_tenant_specification_*.md"
            import glob
            spec_files = glob.glob(spec_pattern)
            if spec_files:
                spec_path = spec_files[0]  # Use the first found specification
                logger.info(f"Found existing tenant specification: {spec_path}")
            
            html_path = visualizer.generate_html_visualization(visualization_path, spec_path)

            logger.info(f"3D visualization generated: {html_path}")
            
            if click.confirm("Would you like to open the visualization in your browser?", default=True):
                visualizer.open_visualization(html_path)
                
        except Exception as e:
            logger.error(f"Error generating visualization: {e}")
            raise
        finally:
            visualizer.close()
        return
    
    grapher = AzureTenantGrapher(
        tenant_id=tenant_id,
        neo4j_uri=neo4j_uri,
        neo4j_user=neo4j_user,
        neo4j_password=neo4j_password,
        auto_start_container=not no_container
    )
    
    try:
        asyncio.run(grapher.build_graph(
            generate_visualization=visualize,
            visualization_path=visualization_path
        ))
        logger.info("Azure Tenant Resource Grapher completed successfully!")
    except Exception as e:
        logger.error(f"Error running grapher: {e}")
        raise


if __name__ == '__main__':
    main()

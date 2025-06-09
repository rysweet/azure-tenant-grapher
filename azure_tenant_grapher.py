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
                    'state': subscription.state.value if subscription.state else None,
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
            r.sku = $sku
        """
        session.run(query, resource)
    
    def create_subscription_resource_relationship(self, session, subscription_id: str, resource_id: str):
        """Create relationship between subscription and resource."""
        query = """
        MATCH (s:Subscription {id: $subscription_id})
        MATCH (r:Resource {id: $resource_id})
        MERGE (s)-[:CONTAINS]->(r)
        """
        session.run(query, subscription_id=subscription_id, resource_id=resource_id)
    
    async def build_graph(self):
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
                for subscription in subscriptions:
                    subscription_id = subscription['id']
                    resources = await self.discover_resources_in_subscription(subscription_id)
                    
                    for resource in resources:
                        self.create_resource_node(session, resource)
                        self.create_subscription_resource_relationship(session, subscription_id, resource['id'])
                    
                    logger.info(f"Processed {len(resources)} resources for subscription {subscription['display_name']}")
                
        except Exception as e:
            logger.error(f"Error building graph: {e}")
            raise
        finally:
            self.close_neo4j_connection()
        
        logger.info("Graph building completed successfully")


@click.command()
@click.option('--tenant-id', required=True, help='Azure tenant ID')
@click.option('--neo4j-uri', default='bolt://localhost:7688', help='Neo4j URI')
@click.option('--neo4j-user', default='neo4j', help='Neo4j username')
@click.option('--neo4j-password', default='azure-grapher-2024', help='Neo4j password')
@click.option('--no-container', is_flag=True, help='Skip automatic container management')
@click.option('--container-only', is_flag=True, help='Only start Neo4j container, do not run grapher')
def main(tenant_id: str, neo4j_uri: str, neo4j_user: str, neo4j_password: str, no_container: bool, container_only: bool):
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
    
    grapher = AzureTenantGrapher(
        tenant_id=tenant_id,
        neo4j_uri=neo4j_uri,
        neo4j_user=neo4j_user,
        neo4j_password=neo4j_password,
        auto_start_container=not no_container
    )
    
    try:
        asyncio.run(grapher.build_graph())
        logger.info("Azure Tenant Resource Grapher completed successfully!")
    except Exception as e:
        logger.error(f"Error running grapher: {e}")
        raise


if __name__ == '__main__':
    main()

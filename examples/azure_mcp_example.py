#!/usr/bin/env python3
"""
Example usage of Azure MCP Client

This script demonstrates how to use the Azure MCP Client for natural language
queries and operations on Azure resources.
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config_manager import AzureTenantGrapherConfig
from src.services.azure_mcp_client import create_mcp_client
from src.services.tenant_manager import TenantManager
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def demonstrate_mcp_capabilities():
    """Demonstrate various MCP client capabilities."""
    
    # Load environment variables
    load_dotenv()
    
    # Create configuration
    config = AzureTenantGrapherConfig(
        tenant_id=os.getenv("AZURE_TENANT_ID", "example-tenant-id")
    )
    
    # Optionally create tenant manager for multi-tenant support
    tenant_manager = None  # Could initialize TenantManager here if needed
    
    # Create MCP client
    logger.info("Creating Azure MCP Client...")
    mcp_client = await create_mcp_client(
        config=config,
        tenant_manager=tenant_manager,
        auto_connect=True
    )
    
    if not mcp_client.is_available():
        logger.warning("MCP is not available. Make sure MCP server is running.")
        logger.info("Start MCP server with: python -m src.mcp_server")
        return
    
    try:
        # 1. Discover tenants
        logger.info("\n1. Discovering Azure tenants...")
        tenants = await mcp_client.discover_tenants()
        for tenant in tenants:
            logger.info(f"  Found tenant: {tenant.get('display_name')} ({tenant.get('tenant_id')})")
        
        # 2. Query resources with natural language
        logger.info("\n2. Querying resources with natural language...")
        
        example_queries = [
            "List all resource groups",
            "Show virtual machines in production",
            "Find storage accounts",
        ]
        
        for query in example_queries:
            logger.info(f"\n  Query: '{query}'")
            result = await mcp_client.query_resources(query)
            
            if result["status"] == "success":
                logger.info(f"  Found {len(result['results'])} resources")
                for resource in result["results"][:3]:  # Show first 3
                    logger.info(f"    - {resource.get('name')} ({resource.get('type')})")
            else:
                logger.warning(f"  Query failed: {result.get('message')}")
        
        # 3. Get identity information
        logger.info("\n3. Getting identity information...")
        identity_info = await mcp_client.get_identity_info()
        
        if identity_info["status"] == "success":
            identity = identity_info.get("identity", {})
            logger.info(f"  Identity Type: {identity.get('type')}")
            logger.info(f"  Identity Name: {identity.get('name')}")
            logger.info(f"  Permissions: {', '.join(identity_info.get('permissions', []))}")
            logger.info(f"  Roles: {', '.join(identity_info.get('roles', []))}")
        else:
            logger.warning(f"  Failed to get identity: {identity_info.get('message')}")
        
        # 4. Get help with available queries
        logger.info("\n4. Available natural language queries:")
        help_queries = await mcp_client.get_natural_language_help()
        for query in help_queries[:5]:  # Show first 5
            logger.info(f"  - {query}")
        
        # 5. Execute a specific operation
        logger.info("\n5. Executing a specific operation...")
        operation = {
            "type": "list_resources",
            "resource_type": "Microsoft.Compute/virtualMachines",
            "filters": {
                "location": "eastus"
            }
        }
        
        try:
            result = await mcp_client.execute_operation(operation)
            logger.info(f"  Operation completed: {result.get('status')}")
        except Exception as e:
            logger.error(f"  Operation failed: {e}")
        
    finally:
        # Clean up
        await mcp_client.disconnect()
        logger.info("\nMCP client disconnected.")


async def interactive_query_mode():
    """Run an interactive query mode for testing natural language queries."""
    
    # Load environment variables
    load_dotenv()
    
    # Create configuration
    config = AzureTenantGrapherConfig(
        tenant_id=os.getenv("AZURE_TENANT_ID", "example-tenant-id")
    )
    
    # Create MCP client
    async with await create_mcp_client(config=config) as mcp_client:
        
        if not mcp_client.is_available():
            logger.error("MCP is not available. Exiting.")
            return
        
        logger.info("Azure MCP Interactive Query Mode")
        logger.info("Type 'help' for examples, 'quit' to exit")
        logger.info("-" * 50)
        
        while True:
            try:
                # Get user input
                query = input("\nEnter query > ").strip()
                
                if query.lower() == 'quit':
                    break
                
                if query.lower() == 'help':
                    help_queries = await mcp_client.get_natural_language_help()
                    logger.info("\nExample queries:")
                    for q in help_queries:
                        logger.info(f"  - {q}")
                    continue
                
                if not query:
                    continue
                
                # Execute query
                logger.info(f"Executing: {query}")
                result = await mcp_client.query_resources(query)
                
                if result["status"] == "success":
                    resources = result["results"]
                    logger.info(f"Found {len(resources)} resources:")
                    
                    for resource in resources[:10]:  # Show first 10
                        logger.info(f"  - {resource.get('name')} ({resource.get('type')})")
                    
                    if len(resources) > 10:
                        logger.info(f"  ... and {len(resources) - 10} more")
                else:
                    logger.error(f"Query failed: {result.get('message')}")
                    
            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"Error: {e}")
        
        logger.info("\nExiting interactive mode.")


async def main():
    """Main entry point for the example."""
    
    import argparse
    
    parser = argparse.ArgumentParser(description="Azure MCP Client Example")
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Run in interactive query mode"
    )
    
    args = parser.parse_args()
    
    if args.interactive:
        await interactive_query_mode()
    else:
        await demonstrate_mcp_capabilities()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\nInterrupted by user")
    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)
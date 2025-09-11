#!/usr/bin/env python3
"""Script to find resource group information in the Neo4j database."""

import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config_manager import create_neo4j_config_from_env
from src.utils.session_manager import create_session_manager


def find_resource_group(name_pattern: str):
    """Find resource group by name pattern in the database."""
    
    # Get Neo4j configuration
    config = create_neo4j_config_from_env()
    manager = create_session_manager(config.neo4j)
    manager.connect()
    
    # Get the driver from the manager
    driver = manager._driver  # Access protected member for direct driver access
    
    if not driver:
        print("❌ Could not connect to Neo4j database")
        return
    
    try:
        with driver.session() as session:
            # Query 1: Find resource groups matching the name pattern
            print(f"\n🔍 Searching for resource groups matching '{name_pattern}'...\n")
            
            query = """
            MATCH (rg:ResourceGroup)
            WHERE rg.name CONTAINS $pattern OR rg.id CONTAINS $pattern
            RETURN 
                rg.name AS name,
                rg.id AS azure_id,
                ID(rg) AS node_id,
                rg.location AS location,
                rg.subscription_id AS subscription_id
            ORDER BY rg.name
            LIMIT 10
            """
            
            result = session.run(query, pattern=name_pattern)
            records = result.data()
            
            if not records:
                print(f"❌ No resource groups found matching '{name_pattern}'")
                
                # Try broader search
                print("\n🔍 Trying broader search on all properties...")
                query2 = """
                MATCH (rg:ResourceGroup)
                WHERE ANY(prop IN keys(rg) WHERE toString(rg[prop]) CONTAINS $pattern)
                RETURN 
                    rg.name AS name,
                    rg.id AS azure_id,
                    ID(rg) AS node_id,
                    rg.location AS location,
                    rg.subscription_id AS subscription_id
                ORDER BY rg.name
                LIMIT 10
                """
                result2 = session.run(query2, pattern=name_pattern)
                records = result2.data()
            
            if records:
                print(f"✅ Found {len(records)} resource group(s):\n")
                for record in records:
                    print(f"  📁 Resource Group: {record['name']}")
                    print(f"     Azure ID: {record['azure_id']}")
                    print(f"     Node ID: {record['node_id']}")
                    print(f"     Location: {record['location']}")
                    print(f"     Subscription: {record['subscription_id']}")
                    print()
                    
                # If we found Ballista_UCAScenario, show more details
                for record in records:
                    if 'Ballista_UCAScenario' in str(record['name']):
                        print(f"\n📌 Found target resource group: {record['name']}")
                        print(f"   ✅ Use this in your filter: {record['name']}")
                        print(f"   ❌ Don't use graph ID: 4:5da3178c-575f-4e20-aa0b-6bd8e843b6d0:630")
                        
                        # Get some resources in this group
                        print(f"\n📊 Sample resources in this resource group:")
                        resources_query = """
                        MATCH (rg:ResourceGroup {name: $name})<-[:IN_RESOURCE_GROUP]-(r)
                        RETURN r.type AS type, COUNT(r) AS count
                        ORDER BY count DESC
                        LIMIT 5
                        """
                        resources_result = session.run(resources_query, name=record['name'])
                        resources_data = resources_result.data()
                        
                        if resources_data:
                            for res in resources_data:
                                print(f"     - {res['type']}: {res['count']} resource(s)")
            else:
                print(f"❌ No resource groups found matching '{name_pattern}'")
                
                # Show available resource groups
                print("\n📋 Available resource groups in database:")
                list_query = """
                MATCH (rg:ResourceGroup)
                RETURN DISTINCT rg.name AS name
                ORDER BY rg.name
                LIMIT 20
                """
                list_result = session.run(list_query)
                list_data = list_result.data()
                
                if list_data:
                    for item in list_data:
                        print(f"   - {item['name']}")
                else:
                    print("   (No resource groups found in database)")
                    
    finally:
        driver.close()


def main():
    """Main entry point."""
    # Default search for Ballista_UCAScenario
    search_term = "Ballista_UCAScenario"
    
    if len(sys.argv) > 1:
        search_term = sys.argv[1]
    
    print(f"🔍 Searching for resource group: {search_term}")
    print("=" * 60)
    
    find_resource_group(search_term)
    
    print("\n" + "=" * 60)
    print("💡 Tips for filtering:")
    print("   1. Use actual resource group names, not database IDs")
    print("   2. Resource group names are case-sensitive")
    print("   3. You can find names in Azure Portal or using 'az group list'")


if __name__ == "__main__":
    main()
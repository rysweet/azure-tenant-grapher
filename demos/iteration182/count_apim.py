#!/usr/bin/env python3
"""Quick script to count API Management instances in Neo4j."""

import os
from neo4j import GraphDatabase

# Configuration
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7688")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "azure-grapher-2024")

def count_apim_instances():
    """Count API Management instances in the graph database."""
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    try:
        with driver.session() as session:
            # Query for API Management service instances
            result = session.run(
                """
                MATCH (r:Resource)
                WHERE r.type = 'Microsoft.ApiManagement/service'
                RETURN count(r) as count,
                       collect(r.name)[..10] as sample_names
                """
            )

            record = result.single()
            if record:
                count = record["count"]
                names = record["sample_names"]

                print(f"\n=== API Management Instances ===")
                print(f"Total count: {count}")

                if names:
                    print(f"\nSample names (up to 10):")
                    for name in names:
                        print(f"  - {name}")
                else:
                    print("\nNo API Management instances found in the database.")

                return count
            else:
                print("No results returned from query")
                return 0

    finally:
        driver.close()

if __name__ == "__main__":
    count = count_apim_instances()
    print(f"\n✓ Found {count} API Management instance(s)")

"""Debug script to check if all mapped resources are retrieved from Neo4j."""
import json
from neo4j import GraphDatabase

# Load mappings
with open('./output/iteration1_20260218_162525/03_resource_mappings.json', 'r') as f:
    mappings = json.load(f)

print(f"Loaded {len(mappings)} mappings")

# Extract source IDs
source_ids = [m['source_id'] for m in mappings]
print(f"\nSource IDs to query:")
for i, source_id in enumerate(source_ids, 1):
    print(f"  {i}. {source_id}")

# Query Neo4j
import os
from dotenv import load_dotenv
load_dotenv()

driver = GraphDatabase.driver(
    os.getenv("NEO4J_URI", "bolt://localhost:7687"),
    auth=(os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD")),
)

with driver.session() as session:
    result = session.run(
        """
        MATCH (r:Resource:Original)
        WHERE r.id IN $ids
        RETURN r.id AS id, r.name AS name, r.type AS type
        """,
        ids=source_ids
    )

    retrieved = list(result)
    print(f"\n\nRetrieved {len(retrieved)} resources from Neo4j:")
    for i, record in enumerate(retrieved, 1):
        print(f"  {i}. {record['name']} ({record['type']})")

    if len(retrieved) < len(source_ids):
        print(f"\n❌ MISSING: {len(source_ids) - len(retrieved)} resources not found in Neo4j!")
        retrieved_ids = {r['id'] for r in retrieved}
        for source_id in source_ids:
            if source_id not in retrieved_ids:
                # Find the name from mappings
                name = next(m['source_name'] for m in mappings if m['source_id'] == source_id)
                print(f"  - Missing: {name}")
                print(f"    ID: {source_id}")
    else:
        print(f"\n✅ All {len(source_ids)} resources found in Neo4j")

driver.close()
